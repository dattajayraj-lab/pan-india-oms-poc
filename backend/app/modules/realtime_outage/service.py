"""Real-time control room rules (TS Cl. 11.4.4; FRD RTO-*)."""
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core import scheduler
from app.core.events import hub
from app.db.base import utcnow
from app.integrations.notifier import notify_users
from app.modules.auth_rbac.models import Centre, User, UserSession
from app.modules.master_registry.models import ElementOwner, GridElement
from app.modules.realtime_outage.models import SHIFT_ORDER, OutageCode, OutageCodeRequest, OutageConsent, Shift
from app.utils.dt import IST, ist_to_utc_naive, utc_to_ist


def shift_window(centre: Centre, shift_type: str, shift_date: date) -> tuple[datetime, datetime]:
    """Shift timings per TS Table 7 (NERLDC 08:00 base, others 08:30), returned as naive UTC."""
    h, m = map(int, centre.shift_start_time.split(":"))
    start = {"MORNING": time(h, m), "EVENING": time(h + 6, m), "NIGHT": time(h + 12, m)}[shift_type]
    s = ist_to_utc_naive(shift_date, start)
    return s, s + timedelta(hours=6 if shift_type != "NIGHT" else 12)


def expected_next(last: Shift | None) -> str | None:
    if last is None:
        return None
    return SHIFT_ORDER[(SHIFT_ORDER.index(last.shift_type) + 1) % 3]


def active_shift(db: Session, centre_id: int) -> Shift | None:
    return db.scalar(select(Shift).where(Shift.centre_id == centre_id, Shift.status == "OPEN").order_by(Shift.id.desc()))


def last_shift(db: Session, centre_id: int) -> Shift | None:
    return db.scalar(select(Shift).where(Shift.centre_id == centre_id).order_by(Shift.id.desc()))


def open_shift(db: Session, centre: Centre, shift_type: str, user: User, staff: list[dict], shift_date: date | None = None,
               works: list[str] | None = None, current_session_id: int | None = None) -> Shift:
    if active_shift(db, centre.id):
        raise HTTPException(409, "Previous shift is still open. Submit its closure before creating the next shift.")
    last = last_shift(db, centre.id)
    exp = expected_next(last)
    if exp and shift_type != exp:
        raise HTTPException(409, f"Wrong shift selection: previous shift was {last.shift_type.title()}, only {exp.title()} shift can be created next.")
    if shift_date is None:
        now = utc_to_ist(utcnow())
        shift_date = (now - timedelta(hours=8, minutes=30)).date() if shift_type == "NIGHT" and now.hour < 8 else now.date()
    s = Shift(centre_id=centre.id, shift_date=shift_date, shift_type=shift_type, shift_incharge_id=user.id,
              assigned_staff_json=[{"user_id": user.id, "name": user.full_name, "desk": "SHIFT_INCHARGE"}, *staff],
              regular_works_checklist_json=[{"key": f"r{i + 1}", "text": t, "done": False} for i, t in enumerate(works or DEFAULT_WORKS)])
    db.add(s)
    db.flush()
    # auto-logout every session that was bound to the previous shift (TS p.126)
    if last:
        for sess in db.scalars(select(UserSession).where(UserSession.shift_id == last.id, UserSession.is_active)):
            if sess.id != current_session_id:
                sess.is_active, sess.ended_reason = False, "SHIFT_HANDOVER_AUTO_LOGOUT"
    if current_session_id:
        db.get(UserSession, current_session_id).shift_id = s.id
    hub.publish(centre.code, "shift_opened", {"shift_id": s.id, "type": shift_type})
    return s


DEFAULT_WORKS = ["Check SCADA telemetry healthiness and report failures", "Review weather alerts for planned shutdowns",
                 "Update unit outage / expected revival list", "Verify pending execution times with constituents",
                 "Prepare and review shift report draft", "Brief incoming shift on important events"]


def is_on_shift(user: User, shift: Shift | None) -> bool:
    return shift is not None and any(s.get("user_id") == user.id for s in shift.assigned_staff_json)


# ------------------------------------------------------------------ consents
def stakeholder_entities(element: GridElement) -> list[tuple[int, str]]:
    seen, out = set(), []
    for o in element.owners:
        if o.entity_id not in seen:
            seen.add(o.entity_id)
            out.append((o.entity_id, {"LINE_OWNER": "LINE_OWNER", "END1_STATION": "END1", "END2_STATION": "END2"}.get(o.ownership_role, o.ownership_role)))
    return out


def build_consents(db: Session, req: OutageCodeRequest) -> None:
    if req.grid_element_id is None:
        return
    el = db.get(GridElement, req.grid_element_id)
    for ent_id, role in stakeholder_entities(el):
        if ent_id == req.requester_entity_id:
            continue
        req.consents.append(OutageConsent(stakeholder_entity_id=ent_id, stakeholder_role=role))
    db.flush()
    if any(not c.for_information_only for c in req.consents):
        req.status = "CONSENT_PENDING"
        for c in req.consents:
            notify_users(db, db.scalars(select(User).where(User.entity_id == c.stakeholder_entity_id)).all(),
                         f"Consent requested: {req.request_category} on {el.name} ({req.request_number})", module="realtime",
                         step_code="CONSENT_REQUESTED", link="/realtime/codes", centre_id=req.centre_id)


def consents_complete(req: OutageCodeRequest) -> bool:
    return all(c.status == "APPROVED" for c in req.consents if not c.for_information_only)


# ------------------------------------------------------------------ execution-time gate (TS p.156)
def pending_exec_codes(db: Session, entity_id: int | None, now: datetime | None = None) -> list[OutageCode]:
    if not entity_id:
        return []
    now = now or utcnow()
    out = []
    rows = db.scalars(select(OutageCode).where(OutageCode.is_revoked.is_(False), OutageCode.final_exec_time.is_(None),
                                               OutageCode.is_deleted.is_(False))).all()
    for c in rows:
        if not any(int(x.get("entity_id", 0)) == entity_id for x in c.issued_to_json):
            continue
        shift = db.get(Shift, c.shift_id)
        _, end = shift_window(db.get(Centre, shift.centre_id), shift.shift_type, shift.shift_date)
        if c.issued_at <= end - timedelta(hours=2) and now >= end - timedelta(hours=1):
            mine = _my_end(db, c, entity_id)
            if (mine == "END1" and c.end1_exec_time is None) or (mine == "END2" and c.end2_exec_time is None) or mine is None:
                out.append(c)
    return out


def pending_revival_units(db: Session, entity_id: int | None, now: datetime | None = None) -> list[GridElement]:
    """Generator owners must fill expected revival date/time before 00:00 hrs (TS p.156)."""
    if not entity_id:
        return []
    now = now or utcnow()
    midnight_today = ist_to_utc_naive(utc_to_ist(now).date(), time(0, 0))
    units = db.scalars(select(GridElement).join(ElementOwner).where(
        ElementOwner.entity_id == entity_id, GridElement.element_type == "GEN_UNIT", GridElement.status.in_(["OUTAGE", "TRIPPED"]))).all()
    out = []
    for u in units:
        if u.last_status_change_at >= midnight_today:
            continue
        code = db.scalar(select(OutageCode).where(OutageCode.grid_element_id == u.id).order_by(OutageCode.id.desc()))
        from app.modules.realtime_outage.models import TrippingReport

        trip = db.scalar(select(TrippingReport).where(TrippingReport.grid_element_id == u.id).order_by(TrippingReport.id.desc()))
        exp = (code.expected_revival_time if code else None) or (trip.expected_revival_at if trip else None)
        if exp is None or exp < now:
            out.append(u)
    return out


def _my_end(db: Session, code: OutageCode, entity_id: int) -> str | None:
    if code.grid_element_id is None:
        return None
    el = db.get(GridElement, code.grid_element_id)
    for o in el.owners:
        if o.entity_id == entity_id and o.ownership_role in ("END1_STATION", "END2_STATION"):
            return "END1" if o.ownership_role == "END1_STATION" else "END2"
    if any(o.entity_id == entity_id for o in el.owners):
        return "END1"
    return None


def two_ended(el: GridElement | None) -> bool:
    return bool(el and el.to_substation_id and el.element_type in ("AC_LINE", "HVDC_LINE"))


def finalise_exec(db: Session, code: OutageCode) -> None:
    """Both ends entered: later time = charging time, earlier = shutdown time (TS p.157)."""
    el = db.get(GridElement, code.grid_element_id) if code.grid_element_id else None
    times = [t for t in (code.end1_exec_time, code.end2_exec_time) if t]
    if not times or (two_ended(el) and len(times) < 2):
        return
    code.final_exec_time = max(times) if code.code_type in ("CHARGING", "REVIVAL") else min(times)
    apply_element_state(db, code)


def apply_element_state(db: Session, code: OutageCode) -> None:
    if code.grid_element_id is None or code.final_exec_time is None:
        return
    el = db.get(GridElement, code.grid_element_id)
    req = db.get(OutageCodeRequest, code.code_request_id) if code.code_request_id else None
    if code.code_type == "OUTAGE":
        el.status = "OUTAGE"
        el.last_status_change_at = code.final_exec_time
    elif code.code_type in ("CHARGING", "REVIVAL"):
        prev_status, prev_start = el.status, el.last_status_change_at
        el.status = "IN_SERVICE"
        el.last_status_change_at = code.final_exec_time
        from app.modules.ftc.router import on_charging_executed

        on_charging_executed(db, el, code.final_exec_time)
        if prev_status in ("OUTAGE", "TRIPPED"):
            from app.modules.availability_verify.service import record_outage_period

            open_code = db.scalar(select(OutageCode).where(OutageCode.grid_element_id == el.id, OutageCode.code_type == "OUTAGE",
                                                           OutageCode.final_exec_time.isnot(None)).order_by(OutageCode.id.desc()))
            open_req = db.get(OutageCodeRequest, open_code.code_request_id) if open_code and open_code.code_request_id else req
            record_outage_period(db, el, prev_start, code.final_exec_time, open_code or code, open_req)
    hub.publish(el.centre.code, "element_status", {"element_id": el.id, "status": el.status})


# ------------------------------------------------------------------ background jobs
@scheduler.register("realtime_code_timers")
def code_timers(db: Session, now: datetime | None = None) -> dict:
    from app.modules.auth_rbac.service import get_setting

    now = now or utcnow()
    pre = int(get_setting(db, "pre_charging_alert_minutes") or 15)
    not_taken = int(get_setting(db, "action_not_taken_minutes") or 60)
    auto_revoke = bool(get_setting(db, "code_auto_revoke"))
    stats = {"pre_alerts": 0, "not_taken": 0, "revoked": 0}
    for c in db.scalars(select(OutageCode).where(OutageCode.is_revoked.is_(False), OutageCode.final_exec_time.is_(None))).all():
        req = db.get(OutageCodeRequest, c.code_request_id) if c.code_request_id else None
        users = [u for x in c.issued_to_json for u in db.scalars(select(User).where(User.entity_id == x.get("entity_id"))).all()]
        if req and req.planned_time and c.code_type == "CHARGING" and not c.pre_alert_sent and \
                req.planned_time - timedelta(minutes=pre) <= now < req.planned_time:
            notify_users(db, users, f"Charging due in {pre} min: {c.code_number}", module="realtime", step_code="PRE_CHARGING_ALERT",
                         centre_id=c.centre_id)
            c.pre_alert_sent = True
            stats["pre_alerts"] += 1
        if not c.action_not_taken_alert_sent and now - c.issued_at >= timedelta(minutes=not_taken) and c.end1_exec_time is None:
            notify_users(db, users, f"Action not taken within {not_taken} min on code {c.code_number}", module="realtime", centre_id=c.centre_id)
            c.action_not_taken_alert_sent = True
            stats["not_taken"] += 1
        if auto_revoke and now >= c.expires_at and c.end1_exec_time is None and c.end2_exec_time is None:
            c.is_revoked, c.revoked_reason = True, "AUTO: validity of 1 hour lapsed (IEGC)"
            stats["revoked"] += 1
            hub.publish(db.get(Centre, c.centre_id).code, "code_revoked", {"code": c.code_number})
    return stats


@scheduler.register("weather_feed")
def weather_feed(db: Session) -> None:
    from app.integrations.weather_adapter import poll

    poll(db)


def owned_element_ids(db: Session, entity_id: int | None) -> set[int]:
    if not entity_id:
        return set()
    return {o.grid_element_id for o in db.scalars(select(ElementOwner).where(ElementOwner.entity_id == entity_id))}


_ = (and_, or_, IST)
