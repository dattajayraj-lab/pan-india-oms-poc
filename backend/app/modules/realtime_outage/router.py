"""Real-Time Outage Management API (TS Cl. 11.4.4 p.126-173; FRD RTO-01..62)."""
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.events import hub
from app.core.rbac import get_current_user, is_admin, is_external, role_codes, sees_all_centres
from app.db.base import utcnow
from app.db.session import get_db
from app.integrations import scada_adapter
from app.integrations.notifier import notify_users
from app.integrations.weather_adapter import alerts_for_area
from app.modules.auth_rbac.models import Centre, User
from app.modules.auth_rbac.service import get_setting
from app.modules.master_registry.models import ElementOwner, Entity, GridElement, Substation
from app.modules.realtime_outage import service as svc
from app.modules.realtime_outage.models import (REQUEST_CATEGORIES, SUO_MOTO_CASES, ElogEntry, OutageCode, OutageCodeRequest,
                                                OutageConsent, ReasonListItem, ScadaAlert, Shift, TrippingReport)
from app.utils.dt import to_utc_naive, utc_to_ist
from app.utils.ids import code_number, simple_number

router = APIRouter(prefix="/api/v1/realtime", tags=["real-time-outage"])
RLDC_ROLES = {"RT_COORDINATOR", "SHIFT_INCHARGE", "NLDC_USER"}
NO_CONSENT = {"SUO_MOTO", "HV_CODE", "LV_CODE", "RE_MVAR", "AGC", "PHYSICAL_REGULATION", "TRIPPED", "EMERGENCY"}
EXCLUDED_FROM_AVAILABILITY = {"AR_OFF", "ANTI_THEFT", "SPS_TEST"}


def is_operator(user, centre_id: int | None = None) -> bool:
    if is_admin(user):
        return True
    if not role_codes(user) & RLDC_ROLES or is_external(user):
        return False
    return centre_id is None or sees_all_centres(user) or user.centre_id == centre_id


def _centre(db: Session, code: str | None, user) -> Centre:
    code = code if code and code != "ALL" else (user.centre.code if user.centre else "NRLDC")
    c = db.scalar(select(Centre).where(Centre.code == code))
    if c is None:
        raise HTTPException(404, "Centre not found")
    return c


def shift_out(db: Session, s: Shift | None) -> dict | None:
    if s is None:
        return None
    c = db.get(Centre, s.centre_id)
    start, end = svc.shift_window(c, s.shift_type, s.shift_date)
    return {"id": s.id, "centre": c.code, "shift_date": s.shift_date, "shift_type": s.shift_type, "incharge": s.incharge.full_name,
            "incharge_id": s.shift_incharge_id, "staff": s.assigned_staff_json, "works": s.regular_works_checklist_json,
            "handover_notes": s.handover_notes, "important_events": s.important_events, "status": s.status, "opened_at": s.opened_at,
            "closed_at": s.closed_at, "window_start": start, "window_end": end, "report_status": s.report_status}


# ================================================================== shifts
@router.get("/shifts/active")
def get_active(centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _centre(db, centre, user)
    act = svc.active_shift(db, c.id)
    last = svc.last_shift(db, c.id)
    return {"centre": c.code, "active": shift_out(db, act), "last": shift_out(db, last), "expected_next": svc.expected_next(last) if not act else None,
            "on_shift": svc.is_on_shift(user, act), "timings": {t: [x.isoformat() for x in svc.shift_window(c, t, utc_to_ist(utcnow()).date())]
                                                               for t in ("MORNING", "EVENING", "NIGHT")}}


@router.get("/shifts")
def list_shifts(centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _centre(db, centre, user)
    return [shift_out(db, s) for s in db.scalars(select(Shift).where(Shift.centre_id == c.id).order_by(Shift.id.desc()).limit(30))]


@router.get("/staff")
def staff(centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _centre(db, centre, user)
    return [{"id": u.id, "name": u.full_name, "username": u.username} for u in db.scalars(select(User).where(User.centre_id == c.id, User.is_active))
            if {r.role.code for r in u.roles} & RLDC_ROLES]


class OpenShiftIn(BaseModel):
    centre_code: str
    shift_type: str = Field(pattern="^(MORNING|EVENING|NIGHT)$")
    staff: list[dict] = []
    shift_date: date | None = None


@router.post("/shifts/open")
def open_shift(body: OpenShiftIn, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not ("SHIFT_INCHARGE" in role_codes(user) or is_admin(user)):
        raise HTTPException(403, "Only the Shift In-charge creates a shift")
    c = _centre(db, body.centre_code, user)
    if not is_operator(user, c.id):
        raise HTTPException(403)
    staff = [{"user_id": int(s["user_id"]), "name": db.get(User, int(s["user_id"])).full_name, "desk": s.get("desk", "RTSD")} for s in body.staff
             if int(s["user_id"]) != user.id]
    s = svc.open_shift(db, c, body.shift_type, user, staff, body.shift_date, current_session_id=request.state.session_id)
    audit(db, user, "realtime", "SHIFT_OPENED", "shift", s.id, new={"type": body.shift_type, "staff": staff})
    db.commit()
    return shift_out(db, s)


@router.post("/shifts/{sid}/join")
def join_shift(sid: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.get(Shift, sid)
    if s is None or s.status != "OPEN" or not svc.is_on_shift(user, s):
        raise HTTPException(403, "You are not assigned to this active shift")
    from app.modules.auth_rbac.models import UserSession

    db.get(UserSession, request.state.session_id).shift_id = s.id
    db.commit()
    return {"ok": True}


@router.patch("/shifts/{sid}/works")
def tick_work(sid: int, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.get(Shift, sid)
    if s.status != "OPEN" or not svc.is_on_shift(user, s):
        raise HTTPException(403)
    works = [dict(w) for w in s.regular_works_checklist_json]
    if body.get("add"):
        works.append({"key": f"r{len(works) + 1}", "text": body["add"], "done": False})
    for w in works:
        if w["key"] == body.get("key"):
            w["done"] = bool(body.get("done"))
    s.regular_works_checklist_json = works
    db.commit()
    return shift_out(db, s)


class HandoverIn(BaseModel):
    handover_notes: str = ""
    important_events: str = ""


@router.put("/shifts/{sid}/handover")
def handover(sid: int, body: HandoverIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.get(Shift, sid)
    if s.status != "OPEN" or s.shift_incharge_id != user.id and not is_admin(user):
        raise HTTPException(403, "Shift In-charge only; content cannot be edited after handover")
    s.handover_notes, s.important_events = body.handover_notes, body.important_events
    db.commit()
    return shift_out(db, s)


@router.post("/shifts/{sid}/close")
def close_shift(sid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Closure status with required details must be submitted before the next shift (TS p.126)."""
    s = db.get(Shift, sid)
    if s is None or s.status != "OPEN":
        raise HTTPException(409, "Shift not open")
    if s.shift_incharge_id != user.id and not is_admin(user):
        raise HTTPException(403, "Only the Shift In-charge closes the shift")
    pending = [w["text"] for w in s.regular_works_checklist_json if not w["done"]]
    if pending:
        raise HTTPException(422, "Regular works not completed: " + "; ".join(pending))
    if not s.handover_notes.strip():
        raise HTTPException(422, "Handover notes (important events) are required")
    s.report_json = {**build_shift_report(db, s), **(s.report_json or {}).get("edits", {})}
    s.status, s.closed_at, s.report_status, s.report_finalised_at = "CLOSED", utcnow(), "FINAL", utcnow()
    audit(db, user, "realtime", "SHIFT_CLOSED", "shift", s.id)
    hub.publish(db.get(Centre, s.centre_id).code, "shift_closed", {"shift_id": s.id})
    db.commit()
    return shift_out(db, s)


def build_shift_report(db: Session, s: Shift) -> dict:
    c = db.get(Centre, s.centre_id)
    start, end = svc.shift_window(c, s.shift_type, s.shift_date)
    end = min(end, utcnow()) if s.status == "OPEN" else end
    codes = db.scalars(select(OutageCode).where(OutageCode.shift_id == s.id).order_by(OutageCode.issued_at)).all()
    trips = db.scalars(select(TrippingReport).where(TrippingReport.centre_id == c.id, TrippingReport.tripped_at >= start - timedelta(hours=12))).all()
    units_out = db.scalars(select(GridElement).where(GridElement.centre_id == c.id, GridElement.element_type == "GEN_UNIT",
                                                     GridElement.status.in_(["OUTAGE", "TRIPPED"]))).all()
    from app.modules.sps_status.models import SpsScheme

    sps = db.scalars(select(SpsScheme).where(SpsScheme.centre_id == c.id)).all()
    f = [scada_adapter.analog("FREQ", c.code)["value"] for _ in range(24)]
    return {
        "centre": c.code, "shift": f"{s.shift_type} {s.shift_date}", "incharge": s.incharge.full_name,
        "frequency": {"max": max(f), "min": min(f), "pct_in_band": round(sum(49.9 <= x <= 50.05 for x in f) / len(f) * 100, 1)},
        "codes": [{"code": x.code_number, "type": x.code_type, "element": x.element.name if x.element else "", "issued_at": x.issued_at.isoformat(),
                   "by": x.issued_by_name, "executed": x.final_exec_time.isoformat() if x.final_exec_time else None, "revoked": x.is_revoked} for x in codes],
        "trippings": [{"element": t.element.name, "at": t.tripped_at.isoformat(), "reason": t.reason, "revival": t.expected_revival_at.isoformat() if t.expected_revival_at else None} for t in trips],
        "units_under_outage": [{"unit": u.name, "since": u.last_status_change_at.isoformat()} for u in units_out],
        "sps": [{"sps_id": x.sps_id, "name": x.sps_name, "status": x.current_status} for x in sps],
        "regular_works": s.regular_works_checklist_json, "handover_notes": s.handover_notes, "important_events": s.important_events,
    }


@router.get("/shifts/{sid}/report")
def shift_report(sid: int, fmt: str = "json", db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.get(Shift, sid)
    data = s.report_json if s.report_status == "FINAL" else {**build_shift_report(db, s), **(s.report_json or {}).get("edits", {})}
    if fmt == "json":
        return {"status": s.report_status, "report": data}
    from app.utils.exports import export

    rows = [{"time": x["issued_at"], "item": f"Code {x['code']} ({x['type']})", "detail": x["element"], "by": x["by"]} for x in data["codes"]] + \
           [{"time": t["at"], "item": "Tripping", "detail": t["element"], "by": t["reason"]} for t in data["trippings"]]
    return export(fmt, f"Shift report {data['shift']} - {data['centre']}", f"शिफ्ट रिपोर्ट {data['shift']}",
                  [("time", "Time", "समय"), ("item", "Item", "मद"), ("detail", "Element", "तत्व"), ("by", "By / reason", "द्वारा / कारण")], rows,
                  f"shift_report_{sid}", subtitle=f"In-charge {data['incharge']} · Freq max {data['frequency']['max']} min {data['frequency']['min']} · {s.report_status}",
                  footer_note=f"Handover: {data['handover_notes']}")


@router.put("/shifts/{sid}/report")
def save_report_draft(sid: int, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Draft/preview edits by operators; Final version becomes immutable (TS p.160-161)."""
    s = db.get(Shift, sid)
    if s.report_status == "FINAL":
        raise HTTPException(409, "Final shift report cannot be edited")
    if not svc.is_on_shift(user, s) and not is_admin(user):
        raise HTTPException(403)
    s.report_json = {"edits": body}
    s.report_status = "DRAFT"
    db.commit()
    return {"ok": True}


# ================================================================== gate & requests
@router.get("/gate")
def gate(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Execution-time and expected-revival gates for constituents (TS p.156)."""
    codes = svc.pending_exec_codes(db, user.entity_id)
    units = svc.pending_revival_units(db, user.entity_id)
    return {"blocked": bool(codes or units), "pending_exec": [{"id": c.id, "code_number": c.code_number, "element": c.element.name if c.element else c.description,
                                                              "issued_at": c.issued_at} for c in codes],
            "pending_revival": [{"id": u.id, "name": u.name} for u in units]}


class RequestIn(BaseModel):
    request_category: str
    grid_element_id: int | None = None
    other_element_desc: str = ""
    action: str = Field("OPENING", pattern="^(OPENING|CHARGING)$")
    reason: str = ""
    remarks: str = ""
    suo_moto_case_no: int | None = Field(None, ge=1, le=23)
    anti_theft_case: int | None = Field(None, ge=1, le=3)
    planned_time: datetime | None = None
    availability_head_proposed: str = ""
    constraint_type: str = ""
    protection_details: dict = {}
    params: dict = {}
    on_behalf_entity_id: int | None = None
    occ_plan_id: int | None = None
    centre_code: str | None = None


def create_request(db: Session, body: RequestIn, user) -> OutageCodeRequest:
    if body.request_category not in REQUEST_CATEGORIES:
        raise HTTPException(422, "Unknown request category")
    el = db.get(GridElement, body.grid_element_id) if body.grid_element_id else None
    if body.request_category == "OTHER_ELEMENT":
        if not body.other_element_desc:
            raise HTTPException(422, "Describe the element not found in master database")
        dup = db.scalar(select(GridElement).where(func.lower(GridElement.name) == body.other_element_desc.strip().lower()))
        if dup:
            raise HTTPException(409, f"Element exists in master database ({dup.unique_element_id}); use the normal request process")
    elif el is None:
        raise HTTPException(422, "Select an element from the master database")
    operator = is_operator(user, el.centre_id if el else None)
    requester_entity = body.on_behalf_entity_id if operator and body.on_behalf_entity_id else user.entity_id
    if not operator:
        if "EXT_REALTIME" not in role_codes(user):
            raise HTTPException(403, "Real-time Outage access not granted (granted after FTC Format IV)")
        if body.request_category in ("HV_CODE", "LV_CODE", "RE_MVAR", "PHYSICAL_REGULATION", "AGC"):
            raise HTTPException(403, "Issued by NLDC/RLDC only")
        g = gate(db=db, user=user)
        if g["blocked"]:
            raise HTTPException(423, "Fill pending execution times / expected revival before requesting another code")
        if el and not any(o.entity_id == user.entity_id for o in el.owners) and body.request_category not in ("OPPORTUNITY",):
            raise HTTPException(403, "You can request codes only for elements under your ownership")
        if el and not el.realtime_enabled:
            raise HTTPException(403, "Element not yet enabled for real-time codes (pending FTC Format IV)")
    if body.request_category == "FORCED" and not body.reason:
        raise HTTPException(422, "Reason is mandatory for forced outage")
    if body.request_category == "FTC" and (el is None or el.source_ftc_case_id is None):
        raise HTTPException(422, "FTC code only for elements approved by the FTC department")
    if body.request_category == "ANTI_THEFT" and body.anti_theft_case is None and el and el.element_type == "AC_LINE":
        body.anti_theft_case = 1
    if body.request_category == "OPPORTUNITY" and el and el.status not in ("OUTAGE",):
        raise HTTPException(409, "Opportunity shutdown only when the element is already under planned/forced outage")
    centre = el.centre if el else _centre(db, body.centre_code, user)
    req = OutageCodeRequest(request_number=simple_number(db, f"REQ/{centre.code}/{utcnow():%y%m%d}"), centre_id=centre.id,
                            grid_element_id=el.id if el else None, other_element_desc=body.other_element_desc,
                            requester_user_id=user.id, requester_entity_id=requester_entity, request_category=body.request_category,
                            action=body.action, suo_moto_case_no=body.suo_moto_case_no, anti_theft_case=body.anti_theft_case,
                            reason=body.reason, remarks=body.remarks, availability_head_proposed=body.availability_head_proposed,
                            constraint_type=body.constraint_type, protection_details_json=body.protection_details, params_json=body.params,
                            planned_time=to_utc_naive(body.planned_time), occ_plan_id=body.occ_plan_id,
                            created_on_behalf_by=user.id if operator and body.on_behalf_entity_id else None)
    shift = svc.active_shift(db, centre.id)
    req.shift_id = shift.id if shift else None
    db.add(req)
    db.flush()
    if body.request_category not in NO_CONSENT:
        svc.build_consents(db, req)
    hub.publish(centre.code, "code_request", {"id": req.id, "category": req.request_category})
    return req


def request_out(db: Session, r: OutageCodeRequest, user=None) -> dict:
    el = r.element
    ent = db.get(Entity, r.requester_entity_id) if r.requester_entity_id else None
    weather = alerts_for_area(db, el.from_substation.weather_area) if el and el.from_substation else []
    return {"id": r.id, "request_number": r.request_number, "centre": db.get(Centre, r.centre_id).code, "category": r.request_category,
            "action": r.action, "status": r.status, "element_id": r.grid_element_id, "element": el.name if el else r.other_element_desc,
            "element_uid": el.unique_element_id if el else "", "element_status": el.status if el else "",
            "requester": db.get(User, r.requester_user_id).full_name, "requester_entity": ent.short_name or ent.name if ent else "",
            "reason": r.reason, "remarks": r.remarks, "suo_moto_case_no": r.suo_moto_case_no,
            "suo_moto_desc": SUO_MOTO_CASES.get(r.suo_moto_case_no, ("",))[0] if r.suo_moto_case_no else "",
            "anti_theft_case": r.anti_theft_case, "planned_time": r.planned_time, "availability_head_proposed": r.availability_head_proposed,
            "params": r.params_json, "created_at": r.created_at, "weather_alerts": weather,
            "notes": el.operator_notes_append_only_json if el else [], "comments": el.operator_comments if el else "",
            "consents": [{"id": c.id, "entity_id": c.stakeholder_entity_id, "entity": c.entity.short_name or c.entity.name, "role": c.stakeholder_role,
                          "status": c.status, "remarks": c.remarks, "info_only": c.for_information_only, "responded_at": c.responded_at,
                          "mine": bool(user and user.entity_id == c.stakeholder_entity_id)} for c in r.consents],
            "consents_complete": svc.consents_complete(r),
            "codes": [{"id": c.id, "code_number": c.code_number, "code_type": c.code_type, "issued_at": c.issued_at, "is_revoked": c.is_revoked,
                       "final_exec_time": c.final_exec_time} for c in r.codes],
            "excluded_from_availability": r.request_category in EXCLUDED_FROM_AVAILABILITY}


@router.post("/requests")
def new_request(body: RequestIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    req = create_request(db, body, user)
    audit(db, user, "realtime", "CODE_REQUESTED", "request", req.request_number, new=body.model_dump(mode="json"))
    db.commit()
    return request_out(db, req, user)


@router.get("/requests")
def list_requests(centre: str | None = None, category: str | None = None, status: str | None = None, mine: bool = False,
                  db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(OutageCodeRequest).order_by(OutageCodeRequest.created_at.desc()).limit(300)
    if is_external(user):
        stmt = stmt.where(or_(OutageCodeRequest.requester_entity_id == user.entity_id,
                              OutageCodeRequest.id.in_(select(OutageConsent.code_request_id).where(OutageConsent.stakeholder_entity_id == user.entity_id))))
    elif centre and centre != "ALL":
        stmt = stmt.where(OutageCodeRequest.centre_id == _centre(db, centre, user).id)
    elif not sees_all_centres(user):
        stmt = stmt.where(OutageCodeRequest.centre_id == user.centre_id)
    if category:
        stmt = stmt.where(OutageCodeRequest.request_category == category)
    if status == "OPEN":
        stmt = stmt.where(OutageCodeRequest.status.in_(["REQUESTED", "CONSENT_PENDING", "REMARKS_PENDING", "CONSENT_APPROVED", "APPROVED"]))
    elif status:
        stmt = stmt.where(OutageCodeRequest.status == status)
    return [request_out(db, r, user) for r in db.scalars(stmt)]


class ConsentIn(BaseModel):
    approve: bool
    remarks: str = ""


@router.post("/requests/{rid}/consent")
def give_consent(rid: int, body: ConsentIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    r = db.get(OutageCodeRequest, rid)
    c = next((x for x in r.consents if x.stakeholder_entity_id == user.entity_id and not x.for_information_only), None)
    if c is None:
        raise HTTPException(403, "No consent requested from your organisation")
    c.status, c.remarks, c.responded_at = ("APPROVED" if body.approve else "REJECTED"), body.remarks, utcnow()
    if svc.consents_complete(r):
        r.status = "CONSENT_APPROVED"
    elif not body.approve:
        r.status = "CONSENT_PENDING"
    notify_users(db, [u for u in db.scalars(select(User).where(User.centre_id == r.centre_id)) if is_operator(u, r.centre_id)],
                 f"Consent {c.status.lower()} by {c.entity.short_name} on {r.request_number}", module="realtime", centre_id=r.centre_id, channels=("INAPP",))
    hub.publish(db.get(Centre, r.centre_id).code, "consent", {"request_id": r.id, "status": c.status})
    db.commit()
    return request_out(db, r, user)


class StakeIn(BaseModel):
    entity_ids: list[int]
    info_only: bool = True
    rldc_remarks: str = ""


@router.post("/requests/{rid}/stakeholders")
def add_stakeholders(rid: int, body: StakeIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Grid operator adds other interested stakeholders (info) or asks additional consents/remarks (TS p.155, p.171)."""
    r = db.get(OutageCodeRequest, rid)
    if not is_operator(user, r.centre_id):
        raise HTTPException(403)
    for e in body.entity_ids:
        r.consents.append(OutageConsent(stakeholder_entity_id=e, stakeholder_role="INFO" if body.info_only else "ADDITIONAL",
                                        for_information_only=body.info_only, rldc_remarks=body.rldc_remarks))
    if not body.info_only:
        r.status = "CONSENT_PENDING"
    db.commit()
    return request_out(db, r, user)


@router.post("/requests/{rid}/decide")
def decide(rid: int, body: ConsentIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    r = db.get(OutageCodeRequest, rid)
    if not is_operator(user, r.centre_id):
        raise HTTPException(403)
    if body.approve and not svc.consents_complete(r):
        raise HTTPException(409, "Consent pending from associated stakeholders - code cannot be issued without consent")
    r.status = "APPROVED" if body.approve else "DISAPPROVED"
    r.remarks = body.remarks or r.remarks
    audit(db, user, "realtime", f"REQUEST_{r.status}", "request", r.request_number)
    db.commit()
    return request_out(db, r, user)


class IssueIn(BaseModel):
    description: str = ""
    expected_revival_time: datetime | None = None


def issue_code(db: Session, user, centre: Centre, req: OutageCodeRequest | None, el: GridElement | None, code_type: str,
               description: str, expected_revival: datetime | None = None, tags: list[str] | None = None) -> OutageCode:
    shift = svc.active_shift(db, centre.id)
    if shift is None:
        raise HTTPException(409, "No active shift - the Shift In-charge must create the shift first")
    if not (svc.is_on_shift(user, shift) or is_admin(user)):
        raise HTTPException(403, "Codes can be issued only by executives assigned to the active (ongoing) shift")
    validity = int(get_setting(db, "code_validity_minutes") or 60)
    issued_to = []
    if el:
        for ent_id, role in svc.stakeholder_entities(el):
            issued_to.append({"entity_id": ent_id, "name": db.get(Entity, ent_id).short_name, "role": role})
    if req:
        for c in req.consents:
            if c.for_information_only and not any(x["entity_id"] == c.stakeholder_entity_id for x in issued_to):
                issued_to.append({"entity_id": c.stakeholder_entity_id, "name": c.entity.short_name, "role": "INFO"})
    volt = None
    if req and req.suo_moto_case_no and SUO_MOTO_CASES[req.suo_moto_case_no][1] and el and el.from_substation:
        volt = scada_adapter.bus_voltage(el.from_substation.code, el.voltage_kv)["value"]
    code = OutageCode(code_number=code_number(db, centre.code), code_request_id=req.id if req else None, centre_id=centre.id,
                      shift_id=shift.id, grid_element_id=el.id if el else None, issued_by_user_id=user.id, issued_by_name=user.full_name,
                      issued_to_json=issued_to, code_type=code_type, description=description, tags_json=tags or [],
                      expires_at=utcnow() + timedelta(minutes=validity), expected_revival_time=to_utc_naive(expected_revival),
                      scada_voltage_kv=volt, reporting_outage_event_id=f"RPT-{centre.code}-{utcnow():%y%m%d%H%M%S}")
    db.add(code)
    db.flush()
    recipients = [u for x in issued_to for u in db.scalars(select(User).where(User.entity_id == x["entity_id"]))]
    notify_users(db, recipients, f"Code {code.code_number} issued: {code_type} {el.name if el else description}", module="realtime",
                 step_code="CODE_ISSUED", link="/realtime/codes", centre_id=centre.id)
    hub.publish(centre.code, "code_issued", {"code": code.code_number, "element": el.name if el else ""})
    return code


@router.post("/requests/{rid}/issue-code")
def issue_for_request(rid: int, body: IssueIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    r = db.get(OutageCodeRequest, rid)
    if not is_operator(user, r.centre_id):
        raise HTTPException(403)
    if r.request_category not in NO_CONSENT and not svc.consents_complete(r):
        raise HTTPException(409, "Consent pending from associated stakeholders - code cannot be issued without consent")
    if r.status in ("DISAPPROVED", "CLOSED"):
        raise HTTPException(409, "Request is closed / disapproved")
    el = r.element
    ctype = "CHARGING" if r.action == "CHARGING" else "OUTAGE"
    if r.request_category in ("AR_OFF", "SPS_TEST", "TAP_CHANGE", "AGC"):
        ctype = "OPERATION"
    code = issue_code(db, user, db.get(Centre, r.centre_id), r, el, ctype, body.description or f"{r.request_category} {r.action.lower()} {el.name if el else r.other_element_desc}",
                      body.expected_revival_time, tags=[r.request_category] + (["NOT_FOR_AVAILABILITY"] if r.request_category in EXCLUDED_FROM_AVAILABILITY else []))
    r.status = "CODE_ISSUED"
    audit(db, user, "realtime", "CODE_ISSUED", "code", code.code_number, new={"request": r.request_number})
    db.commit()
    return code_out(db, code, user)


class BatchIn(BaseModel):
    kind: str = Field(pattern="^(HV_CODE|LV_CODE|SUO_MOTO)$")
    element_ids: list[int]
    action: str = Field("OPENING", pattern="^(OPENING|CHARGING)$")
    suo_moto_case_no: int | None = Field(None, ge=1, le=23)
    description: str = ""


@router.post("/batch-codes")
def batch_codes(body: BatchIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """HV code (multiple lines with/without LR), LV code (reactors/STATCOM/TSC/MSR) and suo-moto codes (TS p.150-153)."""
    out = []
    for eid in body.element_ids:
        el = db.get(GridElement, eid)
        if not is_operator(user, el.centre_id):
            raise HTTPException(403)
        req = create_request(db, RequestIn(request_category=body.kind if body.kind != "SUO_MOTO" else "SUO_MOTO", grid_element_id=eid,
                                           action=body.action, suo_moto_case_no=body.suo_moto_case_no or (1 if body.kind == "HV_CODE" else 2 if body.kind == "LV_CODE" else None),
                                           reason=body.description or body.kind), user)
        code = issue_code(db, user, el.centre, req, el, "OUTAGE" if body.action == "OPENING" else "CHARGING",
                          body.description or f"{body.kind}: {body.action.lower()} {el.name}", tags=[body.kind])
        req.status = "CODE_ISSUED"
        out.append(code.code_number)
    db.commit()
    return {"codes": out}


@router.get("/re-plants")
def re_plants(centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Pooling-station-wise RE plants for the single-window MVAr/Vref/PF code (TS p.164-165)."""
    c = _centre(db, centre, user)
    rows = []
    for el in db.scalars(select(GridElement).where(GridElement.centre_id == c.id, GridElement.element_type.in_(["GEN_STATION", "SOLAR_ICR_BLOCK"]),
                                                   GridElement.status != "DECOMMISSIONED")):
        mw = float((el.metadata_json or {}).get("installed_mw") or (el.rating.split()[0] if el.rating and el.rating.split()[0].replace(".", "").isdigit() else 0) or 0)
        if mw <= 0:
            continue
        pss = el.from_substation
        evac = db.scalar(select(GridElement).where(GridElement.from_substation_id == el.from_substation_id, GridElement.element_type == "AC_LINE")) if pss else None
        rows.append({"element_id": el.id, "plant": el.name, "pooling_station": evac.to_substation.name if evac and evac.to_substation else (pss.name if pss else ""),
                     "rated_mw": mw, "q_capability_mvar": round(mw * 0.33), "evacuating_line": evac.name if evac else "", "poi": evac.to_substation.name if evac and evac.to_substation else ""})
    return rows


class MvarIn(BaseModel):
    mode: str = Field(pattern="^(FIXED_Q|VOLTAGE|FIXED_PF)$")
    items: list[dict]


@router.post("/re-mvar")
def re_mvar(body: MvarIn, centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Single code issued to all ticked RE plants with their respective Q / Vref / PF (TS p.164)."""
    c = _centre(db, centre, user)
    if not is_operator(user, c.id):
        raise HTTPException(403)
    if not body.items:
        raise HTTPException(422, "Tick at least one plant")
    unit = {"FIXED_Q": "MVAr", "VOLTAGE": "kV", "FIXED_PF": "PF"}[body.mode]
    parts = []
    for it in body.items:
        el = db.get(GridElement, int(it["element_id"]))
        v = float(it["value"])
        if body.mode == "FIXED_PF" and not (0.8 <= abs(v) <= 1.0):
            raise HTTPException(422, f"PF for {el.name} must be between 0.8 and 1.0")
        parts.append(f"{el.name}: {v} {unit}")
    req = create_request(db, RequestIn(request_category="RE_MVAR", other_element_desc=f"RE single window ({len(body.items)} plants)",
                                       grid_element_id=int(body.items[0]["element_id"]), params={"mode": body.mode, "items": body.items}), user)
    code = issue_code(db, user, c, req, None, "OPERATION", f"{body.mode} mode code to RE plants - " + "; ".join(parts), tags=["RE_MVAR", body.mode])
    code.issued_to_json = [{"entity_id": o.entity_id, "name": o.entity.short_name, "role": "RE_PLANT"}
                           for it in body.items for o in db.get(GridElement, int(it["element_id"])).owners]
    req.status = "CODE_ISSUED"
    db.commit()
    return code_out(db, code, user)


# ================================================================== codes
def code_out(db: Session, c: OutageCode, user=None) -> dict:
    el = c.element
    window = int(get_setting(db, "time_edit_window_minutes") or 15)
    mine = svc._my_end(db, c, user.entity_id) if user and user.entity_id else None
    return {"id": c.id, "code_number": c.code_number, "code_type": c.code_type, "centre": db.get(Centre, c.centre_id).code,
            "element_id": c.grid_element_id, "element": el.name if el else "", "element_uid": el.unique_element_id if el else "",
            "two_ended": svc.two_ended(el), "description": c.description, "issued_at": c.issued_at, "expires_at": c.expires_at,
            "issued_by": c.issued_by_name, "issued_to": c.issued_to_json, "is_revoked": c.is_revoked, "revoked_reason": c.revoked_reason,
            "end1_exec_time": c.end1_exec_time, "end2_exec_time": c.end2_exec_time, "final_exec_time": c.final_exec_time,
            "expected_revival_time": c.expected_revival_time, "scada_voltage_kv": c.scada_voltage_kv, "tags": c.tags_json,
            "expired": utcnow() > c.expires_at and c.final_exec_time is None, "my_end": mine, "edit_window_min": window,
            "status": "REVOKED" if c.is_revoked else "EXECUTED" if c.final_exec_time else "EXPIRED" if utcnow() > c.expires_at else "ISSUED"}


@router.get("/codes")
def list_codes(view: str = "ALL", centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(OutageCode).where(OutageCode.is_deleted.is_(False)).order_by(OutageCode.issued_at.desc()).limit(300)
    if not is_external(user):
        if centre and centre != "ALL":
            stmt = stmt.where(OutageCode.centre_id == _centre(db, centre, user).id)
        elif not sees_all_centres(user):
            stmt = stmt.where(OutageCode.centre_id == user.centre_id)
    rows = db.scalars(stmt).all()
    if is_external(user):
        rows = [c for c in rows if any(int(x.get("entity_id", 0)) == user.entity_id for x in c.issued_to_json)]
    if view == "DUE_CHARGING":
        rows = [c for c in rows if c.code_type in ("CHARGING", "REVIVAL") and not c.final_exec_time and not c.is_revoked]
    elif view == "DUE_OUTAGE":
        rows = [c for c in rows if c.code_type == "OUTAGE" and not c.final_exec_time and not c.is_revoked]
    elif view == "TODAY":
        start = utcnow() - timedelta(hours=24)
        rows = [c for c in rows if c.issued_at >= start]
    return [code_out(db, c, user) for c in rows]


class ExecIn(BaseModel):
    exec_time: datetime
    end: str | None = Field(None, pattern="^(END1|END2)$")


@router.post("/codes/{cid}/execute")
def execute(cid: int, body: ExecIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Constituent enters actual execution time for its end; no future dates; 15-min edit window (TS p.156-157, p.164)."""
    c = db.get(OutageCode, cid)
    t = to_utc_naive(body.exec_time)
    now = utcnow()
    if t > now + timedelta(minutes=1):
        raise HTTPException(422, "Actual execution time cannot be in the future")
    if t < c.issued_at - timedelta(minutes=1):
        raise HTTPException(422, "Execution time cannot be before code issue time")
    if c.is_revoked:
        raise HTTPException(409, "Code revoked; request a fresh code")
    operator = is_operator(user, c.centre_id)
    end = body.end or (svc._my_end(db, c, user.entity_id) if user.entity_id else "END1")
    if not operator:
        mine = svc._my_end(db, c, user.entity_id)
        if mine is None or (body.end and body.end != mine):
            raise HTTPException(403, "You can enter time only for your own end of the element")
        end = mine
    window = int(get_setting(db, "time_edit_window_minutes") or 15)
    prev, prev_at = (c.end1_exec_time, c.end1_entered_at) if end == "END1" else (c.end2_exec_time, c.end2_entered_at)
    if prev and not operator:
        other_acted = (c.end2_entered_at if end == "END1" else c.end1_entered_at) and (c.end2_entered_at if end == "END1" else c.end1_entered_at) > prev_at
        if now - prev_at > timedelta(minutes=window) or other_acted or c.final_exec_time:
            raise HTTPException(409, f"Edit window of {window} minutes has lapsed; contact the grid operator")
    if end == "END1":
        c.end1_exec_time, c.end1_entered_at = t, now
    else:
        c.end2_exec_time, c.end2_entered_at = t, now
    c.final_exec_time = None
    svc.finalise_exec(db, c)
    audit(db, user, "realtime", "EXECUTION_TIME_ENTERED", "code", c.code_number, new={"end": end, "time": t.isoformat()})
    hub.publish(db.get(Centre, c.centre_id).code, "code_executed", {"code": c.code_number, "end": end})
    db.commit()
    return code_out(db, c, user)


class OverrideIn(BaseModel):
    final_exec_time: datetime


@router.post("/codes/{cid}/override")
def override(cid: int, body: OverrideIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Grid operator may override entered timings if found incorrect (TS p.157, p.170)."""
    c = db.get(OutageCode, cid)
    if not is_operator(user, c.centre_id):
        raise HTTPException(403)
    old = c.final_exec_time
    c.final_exec_time, c.exec_overridden_by = to_utc_naive(body.final_exec_time), user.id
    c.end1_exec_time = c.end1_exec_time or c.final_exec_time
    svc.apply_element_state(db, c)
    audit(db, user, "realtime", "EXECUTION_TIME_OVERRIDDEN", "code", c.code_number, old={"t": old}, new={"t": c.final_exec_time})
    db.commit()
    return code_out(db, c, user)


@router.post("/codes/{cid}/revoke")
def revoke(cid: int, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = db.get(OutageCode, cid)
    if not is_operator(user, c.centre_id):
        raise HTTPException(403)
    c.is_revoked, c.revoked_reason = True, body.get("reason", "Revoked by grid operator")
    db.commit()
    return code_out(db, c, user)


@router.post("/codes/{cid}/revival")
def set_revival(cid: int, body: OverrideIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = db.get(OutageCode, cid)
    c.expected_revival_time = to_utc_naive(body.final_exec_time)
    db.commit()
    return code_out(db, c, user)


@router.post("/run-timers")
def run_timers(db: Session = Depends(get_db), user=Depends(get_current_user)):
    out = svc.code_timers(db)
    db.commit()
    return out


# ================================================================== trippings
class TripIn(BaseModel):
    grid_element_id: int
    substation_name: str = ""
    relay_flags: str = ""
    tripped_at: datetime
    reason: str = ""
    expected_revival_at: datetime | None = None


@router.post("/trippings")
def report_tripping(body: TripIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    el = db.get(GridElement, body.grid_element_id)
    if is_external(user) and not any(o.entity_id == user.entity_id for o in el.owners):
        raise HTTPException(403)
    t = TrippingReport(centre_id=el.centre_id, grid_element_id=el.id, reported_by=user.id, substation_name=body.substation_name or (el.from_substation.name if el.from_substation else ""),
                       relay_flags=body.relay_flags, tripped_at=to_utc_naive(body.tripped_at), reason=body.reason,
                       expected_revival_at=to_utc_naive(body.expected_revival_at))
    db.add(t)
    el.status, el.last_status_change_at = "TRIPPED", to_utc_naive(body.tripped_at)
    hub.publish(el.centre.code, "tripping", {"element": el.name})
    audit(db, user, "realtime", "TRIPPING_REPORTED", "element", el.unique_element_id)
    db.commit()
    return {"id": t.id}


@router.get("/trippings")
def trippings(centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(TrippingReport).order_by(TrippingReport.tripped_at.desc()).limit(200)
    rows = db.scalars(stmt).all()
    if is_external(user):
        owned = svc.owned_element_ids(db, user.entity_id)
        rows = [r for r in rows if r.grid_element_id in owned]
    elif centre and centre != "ALL":
        cid = _centre(db, centre, user).id
        rows = [r for r in rows if r.centre_id == cid]
    return [{"id": r.id, "element_id": r.grid_element_id, "element": r.element.name, "element_type": r.element.element_type,
             "voltage_kv": r.element.voltage_kv, "substation": r.substation_name, "relay_flags": r.relay_flags, "tripped_at": r.tripped_at,
             "reason": r.reason, "expected_revival_at": r.expected_revival_at, "acknowledged": r.acknowledged_at is not None,
             "element_status": r.element.status} for r in rows]


@router.post("/trippings/{tid}/ack")
def ack(tid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    t = db.get(TrippingReport, tid)
    if not is_operator(user, t.centre_id):
        raise HTTPException(403)
    t.acknowledged_by, t.acknowledged_at = user.id, utcnow()
    db.commit()
    return {"ok": True}


# ================================================================== dashboard, e-log, reasons, feeds
@router.get("/dashboard")
def dashboard(centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _centre(db, centre, user)
    els = db.scalars(select(GridElement).where(GridElement.centre_id == c.id)).all()
    if is_external(user):
        owned = svc.owned_element_ids(db, user.entity_id)
        els = [e for e in els if e.id in owned]
    since = utcnow() - timedelta(hours=24)
    codes_q = select(OutageCode).where(OutageCode.centre_id == c.id, OutageCode.issued_at >= since)
    codes = db.scalars(codes_q).all()
    if is_external(user):
        codes = [x for x in codes if any(int(i.get("entity_id", 0)) == user.entity_id for i in x.issued_to_json)]
    reqs = db.scalars(select(OutageCodeRequest).where(OutageCodeRequest.centre_id == c.id, OutageCodeRequest.status.in_(
        ["REQUESTED", "CONSENT_PENDING", "CONSENT_APPROVED", "APPROVED"]))).all()
    alerts = db.scalars(select(ScadaAlert).where(or_(ScadaAlert.centre_id == c.id, ScadaAlert.centre_id.is_(None)))
                        .order_by(ScadaAlert.created_at.desc()).limit(8)).all()
    now = utcnow()

    def avail_hours(e):
        return round((now - e.last_status_change_at).total_seconds() / 3600, 1) if e.status == "IN_SERVICE" else 0
    return {
        "centre": c.code, "tiles": scada_adapter.grid_tiles(c.code),
        "re_generation_mw": round(scada_adapter.analog("DEMAND", c.code)["value"] * 0.22),
        "elements_total": len(els), "under_outage": sum(e.status == "OUTAGE" for e in els), "tripped": sum(e.status == "TRIPPED" for e in els),
        "units_out": [{"name": e.name, "since": e.last_status_change_at} for e in els if e.element_type == "GEN_UNIT" and e.status in ("OUTAGE", "TRIPPED")],
        "codes_today": len(codes), "pending_by_category": {k: sum(r.request_category == k for r in reqs) for k in {r.request_category for r in reqs}},
        "pending_consents": sum(1 for r in reqs for x in r.consents if x.status == "PENDING" and not x.for_information_only),
        "alerts": [{"source": a.source, "area": a.area, "severity": a.severity, "message": a.message, "at": a.created_at} for a in alerts],
        "availability_hours": sorted([{"element": e.name, "hours": avail_hours(e)} for e in els if e.status == "IN_SERVICE"], key=lambda x: -x["hours"])[:8],
    }


class ElogIn(BaseModel):
    category: str = Field(pattern="^(GRID_EVENT|GRID_OPS|CURTAILMENT|TECH_ORDER|STOA|NOTE)$")
    title: str
    body: str = ""
    entity_name: str = ""
    centre_code: str | None = None


@router.get("/elog")
def elog(category: str | None = None, centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _centre(db, centre, user)
    stmt = select(ElogEntry).where(ElogEntry.centre_id == c.id, ElogEntry.is_deleted.is_(False)).order_by(ElogEntry.created_at.desc())
    if category:
        stmt = stmt.where(ElogEntry.category == category)
    return [{"id": e.id, "category": e.category, "title": e.title, "body": e.body, "entity_name": e.entity_name, "created_at": e.created_at,
             "by": db.get(User, e.created_by).full_name} for e in db.scalars(stmt)]


@router.post("/elog")
def add_elog(body: ElogIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = _centre(db, body.centre_code, user)
    if not is_operator(user, c.id):
        raise HTTPException(403)
    shift = svc.active_shift(db, c.id)
    e = ElogEntry(centre_id=c.id, shift_id=shift.id if shift else None, category=body.category, title=body.title, body=body.body,
                  entity_name=body.entity_name, created_by=user.id)
    db.add(e)
    if body.category == "GRID_OPS" and body.entity_name:
        from app.integrations.notifier import send_raw

        send_raw(db, "EMAIL", body.entity_name, body.title, body.body, module="realtime")
    db.commit()
    return {"id": e.id}


@router.delete("/elog/{eid}")
def del_elog(eid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Delete wrongly entered e-logbook data so it doesn't reflect in shift summaries (TS p.160, 170)."""
    e = db.get(ElogEntry, eid)
    if not is_operator(user, e.centre_id):
        raise HTTPException(403)
    e.is_deleted = True
    audit(db, user, "realtime", "ELOG_DELETED", "elog", eid)
    db.commit()
    return {"ok": True}


@router.get("/reasons")
def reasons(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = [r.text for r in db.scalars(select(ReasonListItem).order_by(ReasonListItem.text))]
    return rows or ["Planned maintenance", "Breakdown maintenance", "Insulator replacement", "Hot spot rectification", "Tree cutting", "Bay extension work"]


@router.post("/reasons")
def add_reason(body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Adding a reason requires Shift In-charge authorisation (TS p.164)."""
    if not ("SHIFT_INCHARGE" in role_codes(user) or is_admin(user)):
        raise HTTPException(403, "Only the Shift In-charge can add reasons")
    db.add(ReasonListItem(text=body["text"][:200], added_by=user.id))
    db.commit()
    return {"ok": True}


@router.get("/meta")
def meta(user=Depends(get_current_user)):
    return {"categories": REQUEST_CATEGORIES, "suo_moto_cases": [{"no": k, "desc": v[0], "needs_scada_voltage": v[1]} for k, v in SUO_MOTO_CASES.items()],
            "availability_heads": ["SELF", "OTHERS", "DEEMED", "SYSTEM", "CONSTRUCTION", "DIVERSION", "HVDC_SELF", "HVDC_OTHERS", "KITE", "WEATHER"],
            "constraint_types": ["HVRT", "LVRT", "SYSTEM_CONSTRAINT", "LOADING", "GRID_SECURITY"],
            "is_operator": is_operator(user), "desks": ["RTSD", "SCHEDULING", "OUTAGE_DESK", "SCADA_DESK", "MARKET_DESK"]}


@router.get("/weather")
def weather(area: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return alerts_for_area(db, area)


_ = (Substation, ElementOwner)
