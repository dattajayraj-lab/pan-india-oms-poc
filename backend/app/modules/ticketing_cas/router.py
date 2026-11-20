"""Complaint Addressal System API (TS Ch.5 p.44-49, Cl. 10.6; FRD CAS-01..27)."""
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.rbac import MODULES, can_access, get_current_user, is_admin, is_external, role_codes, visible_centre_ids
from app.db.base import utcnow
from app.db.session import get_db
from app.integrations.notifier import notify_users
from app.modules.auth_rbac.models import Centre, User
from app.modules.dms_files.service import list_docs, store_upload
from app.modules.ticketing_cas import service as svc
from app.modules.ticketing_cas.models import KnowledgeBaseArticle, Ticket
from app.utils.exports import export
from app.utils.ids import ticket_number

router = APIRouter(prefix="/api/v1/cas", tags=["complaint-addressal"])
STAFF_ROLES = {"CAS_HELPDESK", "SUPER_ADMIN", "MODULE_ADMIN", "HEAD_RLDC", "HEAD_NLDC", "NLDC_USER"}
COMPLAINT_TYPES = ["SYSTEM_ACCESS", "ISSUE", "BUG", "DATA_CORRECTION", "NEW_DEVELOPMENT", "HARDWARE", "SOFTWARE", "OTHER"]


def is_staff(user) -> bool:
    return bool(role_codes(user) & STAFF_ROLES) or (user.user_category == "GRID_INDIA" and any(
        c.endswith("COORDINATOR") for c in role_codes(user)))


def ticket_out(t: Ticket, user, full: bool = False, db: Session | None = None) -> dict:
    out = {"id": t.id, "ticket_number": t.ticket_number, "centre": t.centre.code, "module": t.module,
           "complaint_type": t.complaint_type, "channel": t.channel, "complainant_name": t.complainant_name,
           "complainant_contact": t.complainant_contact, "complainant_user_id": t.complainant_user_id, "priority_requested": t.priority_requested, "priority": t.priority,
           "severity": t.severity, "escalation_level": t.escalation_level, "status": t.status, "subject": t.subject,
           "assigned_team": t.assigned_team, "tags": t.tags_json, "linked_ticket_id": t.linked_ticket_id,
           "created_at": t.created_at, "sla_response_due": t.sla_response_due, "sla_resolution_due": t.sla_resolution_due,
           "responded_at": t.responded_at, "resolved_at": t.resolved_at, "closed_at": t.closed_at,
           "reopen_count": t.reopen_count, "feedback_rating": t.feedback_rating, **svc.sla_status(t)}
    if full:
        staff = is_staff(user)
        out.update({"description": t.description, "comments": t.comments, "feedback_text": t.feedback_text,
                    "history": [{"event": h.event, "actor_name": h.actor_name, "comment": h.comment, "status": h.status,
                                 "from_level": h.from_level, "to_level": h.to_level, "created_at": h.created_at,
                                 "attachment_doc_id": h.attachment_doc_id}
                                for h in t.history if staff or not h.is_internal],
                    "documents": list_docs(db, f"ticket:{t.id}") if db is not None else [],
                    "tracker": tracker(t)})
    return out



def tracker(t: Ticket) -> list[dict]:
    """Stage-wise progress with timestamps for the stakeholder tracking display (Fig.9)."""
    def first(*events):
        return next((h for h in t.history if h.event in events), None)

    stages = [("LOGGED", "Complaint logged (Level 0)", first("CREATED")),
              ("ASSESSED", "Assessed by AMC / RLDC (Level 1)", first("ASSESSED", "ACKNOWLEDGED")),
              ("IN_PROGRESS", "Resolution in progress", first("COMMENT", "INPUT_REQUESTED", "TRANSFERRED", "AUTO_ESCALATED", "ESCALATED")),
              ("RESOLVED", "Resolved", first("RESOLVED")),
              ("CLOSED", "Closed / feedback", first("CLOSED"))]
    out = []
    pending_marked = False
    for key, label, h in stages:
        if h:
            out.append({"key": key, "label": label, "state": "DONE", "at": h.created_at, "by": h.actor_name, "remarks": h.comment})
        else:
            out.append({"key": key, "label": label, "state": "PENDING" if not pending_marked else "TODO",
                        "at": None, "by": t.assigned_team if not pending_marked else "", "remarks": ""})
            pending_marked = True
    if t.status == "REOPENED":
        out.append({"key": "REOPENED", "label": f"Re-opened ({t.reopen_count})", "state": "RETURNED", "at": t.updated_at, "by": "", "remarks": ""})
    return out


def _get(db: Session, tid: int, user) -> Ticket:
    t = db.get(Ticket, tid)
    if t is None:
        raise HTTPException(404, "Ticket not found")
    if not is_staff(user) and t.complainant_user_id != user.id:
        raise HTTPException(403, "Not your ticket")
    return t


@router.get("/meta")
def meta(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Drop-downs: modules (unauthorised shown disabled/grey), complaint types, centres (TS Ch.5 p.45)."""
    return {"modules": [{"key": m["key"], "name_en": m["name_en"], "name_hi": m["name_hi"], "enabled": can_access(user, m["key"])}
                        for m in MODULES] + [{"key": "portal", "name_en": "Common web portal", "name_hi": "सामान्य वेब पोर्टल", "enabled": True}],
            "complaint_types": COMPLAINT_TYPES, "priorities": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            "centres": [c.code for c in db.scalars(select(Centre).order_by(Centre.id))],
            "sla": {str(k): {"response_min": int(v[0].total_seconds() // 60), "resolution_min": int(v[1].total_seconds() // 60)} for k, v in svc.SLA.items()},
            "is_staff": is_staff(user),
            "my_tickets": [{"id": t.id, "ticket_number": t.ticket_number, "subject": t.subject} for t in db.scalars(
                select(Ticket).where(Ticket.complainant_user_id == user.id).order_by(Ticket.id.desc()).limit(50))]}


@router.post("/tickets")
def create_ticket(module: str = Form(...), subject: str = Form(..., min_length=4), description: str = Form(..., min_length=5),
                  complaint_type: str = Form("ISSUE"), priority_requested: str = Form("MEDIUM"), centre_code: str = Form(...),
                  channel: str = Form("PORTAL"), linked_ticket_id: int | None = Form(None), comments: str = Form(""),
                  on_behalf_username: str | None = Form(None), file: UploadFile | None = File(None),
                  db: Session = Depends(get_db), user=Depends(get_current_user)):
    if module != "portal" and module not in [m["key"] for m in MODULES]:
        raise HTTPException(422, "Unknown module")
    if module != "portal" and not can_access(user, module) and not is_staff(user):
        raise HTTPException(422, "You can raise complaints only for modules you are authorised for")
    if channel not in ("PORTAL", "EMAIL", "PHONE", "WALKIN"):
        raise HTTPException(422, "Invalid channel")
    complainant = user
    if channel != "PORTAL":
        if not is_staff(user):
            raise HTTPException(403, "Walk-in / phone / e-mail tickets are logged by AMC helpdesk personnel")
        if on_behalf_username:
            complainant = db.scalar(select(User).where(User.username == on_behalf_username)) or user
    centre = db.scalar(select(Centre).where(Centre.code == centre_code))
    if centre is None:
        raise HTTPException(422, "Unknown centre")
    t = Ticket(ticket_number=ticket_number(db, centre.code), centre_id=centre.id, module=module, complaint_type=complaint_type,
               channel=channel, complainant_user_id=complainant.id, complainant_name=complainant.full_name,
               complainant_contact=f"{complainant.email} / {complainant.mobile}", logged_by_user_id=user.id,
               linked_ticket_id=linked_ticket_id, priority_requested=priority_requested, subject=subject,
               description=description, comments=comments, escalation_level=0, level_entered_at=utcnow())
    db.add(t)
    db.flush()
    doc_id = None
    if file is not None and file.filename:
        doc_id = store_upload(db, file=file, module="cas", doc_category="ATTACHMENT", owner_ref=f"ticket:{t.id}",
                              centre_code=centre.code, user=user).id
    svc.history(db, t, "CREATED", user, f"Logged via {channel}", to_level=0, doc_id=doc_id)
    notify_users(db, [complainant], f"Complaint {t.ticket_number} registered: {subject}", body=description[:300],
                 module="cas", step_code="TICKET_CREATED", link=f"/cas/{t.id}", centre_id=centre.id)
    helpdesk = [u for u in db.scalars(select(User).where(User.centre_id == centre.id, User.is_active)).all()
                if {r.role.code for r in u.roles} & {"CAS_HELPDESK"}]
    notify_users(db, helpdesk, f"New complaint {t.ticket_number} ({module})", module="cas", step_code="TICKET_CREATED",
                 link=f"/cas/{t.id}", centre_id=centre.id, channels=("INAPP", "EMAIL"))
    audit(db, user, "cas", "TICKET_CREATED", "ticket", t.ticket_number, new={"module": module, "channel": channel})
    db.commit()
    return {"id": t.id, "ticket_number": t.ticket_number}


@router.get("/tickets")
def list_tickets(status: str | None = None, centre: str | None = None, mine: bool = False, q: str | None = None,
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(Ticket).order_by(Ticket.created_at.desc())
    if not is_staff(user) or mine:
        stmt = stmt.where(Ticket.complainant_user_id == user.id)
    else:
        ids = visible_centre_ids(db, user)
        if ids is not None:
            stmt = stmt.where(Ticket.centre_id.in_(ids))
    if centre and centre != "ALL":
        stmt = stmt.join(Centre).where(Centre.code == centre)
    if status == "ACTIVE":
        stmt = stmt.where(Ticket.status.in_(svc.OPEN_STATES))
    elif status == "COMPLETED":
        stmt = stmt.where(Ticket.status.in_(["RESOLVED", "CLOSED"]))
    elif status:
        stmt = stmt.where(Ticket.status == status)
    if q:
        stmt = stmt.where(or_(Ticket.subject.ilike(f"%{q}%"), Ticket.ticket_number.ilike(f"%{q}%")))
    return [ticket_out(t, user) for t in db.scalars(stmt.limit(500))]


@router.get("/tickets/{tid}")
def get_ticket(tid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    t = _get(db, tid, user)
    return ticket_out(t, user, full=True, db=db)


class AssessIn(BaseModel):
    priority: str | None = Field(None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    severity: int | None = Field(None, ge=1, le=4)
    tags: list[str] | None = None
    assigned_team: str | None = None
    remarks: str = ""


@router.post("/tickets/{tid}/assess")
def assess(tid: int, body: AssessIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """AMC assesses priority & tags; RLDC/NLDC assesses severity (separate fields, TS p.45)."""
    t = _get(db, tid, user)
    if not is_staff(user):
        raise HTTPException(403, "Only helpdesk / RLDC / NLDC staff can assess")
    codes = role_codes(user)
    if body.severity is not None and "CAS_HELPDESK" in codes and not (codes - {"CAS_HELPDESK"}):
        raise HTTPException(403, "Severity is assessed by RLDC/NLDC, not by AMC personnel")
    if body.priority:
        t.priority = body.priority
    if body.severity:
        t.severity = body.severity
        svc.apply_sla(t)
    if body.tags is not None:
        t.tags_json = body.tags
    if body.assigned_team:
        t.assigned_team = body.assigned_team
    if t.escalation_level == 0:
        t.escalation_level, t.level_entered_at = 1, utcnow()
        t.responded_at = t.responded_at or utcnow()
        t.status = "ASSIGNED"
    svc.history(db, t, "ASSESSED", user, body.remarks or f"Priority={t.priority} Severity={t.severity}", from_level=0, to_level=t.escalation_level)
    audit(db, user, "cas", "TICKET_ASSESSED", "ticket", t.ticket_number, new=body.model_dump())
    db.commit()
    return ticket_out(t, user)


@router.post("/tickets/{tid}/action")
def action(tid: int, action: str = Form(...), comment: str = Form(""), target: str | None = Form(None),
           rating: int | None = Form(None), internal: bool = Form(False), file: UploadFile | None = File(None),
           db: Session = Depends(get_db), user=Depends(get_current_user)):
    """COMMENT | REQUEST_INPUT | PROVIDE_INPUT | ESCALATE | TRANSFER | RESOLVE | CLOSE | REOPEN | FEEDBACK."""
    t = _get(db, tid, user)
    staff = is_staff(user)
    owner = t.complainant_user_id == user.id
    doc_id = None
    if file is not None and file.filename:
        doc_id = store_upload(db, file=file, module="cas", doc_category="ATTACHMENT", owner_ref=f"ticket:{t.id}",
                              centre_code=t.centre.code, user=user).id
    a = action.upper()
    notify_target = []
    if a == "COMMENT":
        if t.status in ("ASSIGNED", "OPEN") and staff:
            t.status = "IN_PROGRESS"
    elif a == "REQUEST_INPUT":
        if not staff:
            raise HTTPException(403)
        t.status = "AWAITING_INPUT"
        notify_target = [db.get(User, t.complainant_user_id)]
    elif a == "PROVIDE_INPUT":
        if not owner:
            raise HTTPException(403)
        t.status = "IN_PROGRESS"
    elif a == "ESCALATE":
        if t.status not in svc.OPEN_STATES or t.escalation_level >= 3:
            raise HTTPException(409, "Ticket cannot be escalated further")
        frm = t.escalation_level
        t.escalation_level = max(t.escalation_level + 1, 1)
        t.level_entered_at = utcnow()
        svc.history(db, t, "ESCALATED", user, comment or "Escalated by user", from_level=frm, to_level=t.escalation_level, doc_id=doc_id)
        db.commit()
        return ticket_out(t, user)
    elif a == "TRANSFER":
        if not staff and not owner:
            raise HTTPException(403)
        centre = db.scalar(select(Centre).where(Centre.code == target)) if target in [c.code for c in db.scalars(select(Centre))] else None
        if centre:
            t.centre_id = centre.id
        elif target:
            t.assigned_team = target
        else:
            raise HTTPException(422, "Transfer target required")
    elif a == "RESOLVE":
        if not staff:
            raise HTTPException(403)
        t.status, t.resolved_at = "RESOLVED", utcnow()
        notify_target = [db.get(User, t.complainant_user_id)]
        if not db.scalar(select(KnowledgeBaseArticle).where(KnowledgeBaseArticle.source_ticket_id == t.id)) and comment:
            db.add(KnowledgeBaseArticle(module=t.module, question_en=t.subject, answer_en=comment, source_ticket_id=t.id, is_published=False))
    elif a == "CLOSE":
        if not (owner or staff):
            raise HTTPException(403)
        t.status, t.closed_at = "CLOSED", utcnow()
        t.resolved_at = t.resolved_at or utcnow()
    elif a == "REOPEN":
        if not (owner or staff) or t.status not in ("RESOLVED", "CLOSED"):
            raise HTTPException(409, "Only resolved/closed tickets can be re-opened")
        t.status, t.reopen_count = "REOPENED", t.reopen_count + 1
        t.resolved_at = t.closed_at = None
        t.escalation_level, t.level_entered_at = max(t.escalation_level, 1), utcnow()
    elif a == "FEEDBACK":
        if not owner or t.status not in ("RESOLVED", "CLOSED"):
            raise HTTPException(409, "Feedback is given by the complainant after closure")
        t.feedback_rating, t.feedback_text = rating, comment
        if t.status == "RESOLVED":
            t.status, t.closed_at = "CLOSED", utcnow()
    else:
        raise HTTPException(422, "Unknown action")
    svc.history(db, t, {"RESOLVE": "RESOLVED", "CLOSE": "CLOSED", "REOPEN": "REOPENED", "TRANSFER": "TRANSFERRED",
                        "REQUEST_INPUT": "INPUT_REQUESTED"}.get(a, a), user, comment, doc_id=doc_id, internal=internal and staff)
    notify_users(db, [u for u in notify_target if u], f"Ticket {t.ticket_number}: {a.replace('_', ' ').lower()}", body=comment,
                 module="cas", step_code="TICKET_RESOLVED" if a == "RESOLVE" else "", link=f"/cas/{t.id}", centre_id=t.centre_id)
    audit(db, user, "cas", f"TICKET_{a}", "ticket", t.ticket_number, new={"comment": comment[:200]})
    db.commit()
    return ticket_out(t, user)


# ------------------------------------------------------------------- dashboards (14)
DASHBOARDS = [(f"{c}_{r}", f"{'Coordinator' if r == 'COORD' else 'Head'} of {c}", c)
              for c in ("NRLDC", "ERLDC", "WRLDC", "SRLDC", "NERLDC", "NLDC") for r in ("COORD", "HEAD")] + \
             [("DIRECTOR_SO", "Director (System Operation)", None), ("DIRECTOR_MO", "Director (Market Operation)", None)]


@router.get("/dashboards")
def dashboard_list(user=Depends(get_current_user)):
    return [{"key": k, "title": t, "centre": c} for k, t, c in DASHBOARDS]


@router.get("/dashboards/{key}")
def dashboard(key: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not is_staff(user) and not role_codes(user) & {"DIRECTOR"}:
        raise HTTPException(403)
    d = next((x for x in DASHBOARDS if x[0] == key), None)
    if d is None:
        raise HTTPException(404)
    stmt = select(Ticket)
    if d[2]:
        stmt = stmt.join(Centre).where(Centre.code == d[2])
    rows = db.scalars(stmt).all()
    if key == "DIRECTOR_MO":
        rows = [t for t in rows if t.module in ("registration", "ftc", "mis", "portal")]
    now = utcnow()
    resolved = [t for t in rows if t.resolved_at]
    avg_h = round(sum((t.resolved_at - t.created_at).total_seconds() for t in resolved) / 3600 / len(resolved), 1) if resolved else 0
    days = [(now - timedelta(days=i)).date() for i in range(13, -1, -1)]
    trend = [{"date": dd.strftime("%d-%m"), "logged": sum(1 for t in rows if t.created_at.date() == dd),
              "resolved": sum(1 for t in rows if t.resolved_at and t.resolved_at.date() == dd)} for dd in days]
    return {
        "title": d[1], "total": len(rows), "open": sum(t.status in svc.OPEN_STATES for t in rows),
        "resolved": len(resolved), "avg_resolution_hours": avg_h,
        "sla_breached": sum(1 for t in rows if svc.sla_status(t)["resolution_breached"]),
        "by_status": dict(Counter(t.status for t in rows)), "by_severity": dict(Counter(f"S{t.severity or '-'}" for t in rows)),
        "by_module": dict(Counter(t.module for t in rows)), "by_level": dict(Counter(f"L{t.escalation_level}" for t in rows)),
        "by_centre": dict(Counter(t.centre.code for t in rows)), "trend": trend,
        "pending": [ticket_out(t, user) for t in sorted(rows, key=lambda x: x.created_at) if t.status in svc.OPEN_STATES][:15],
    }


# ------------------------------------------------------------------- reports (14) + SLA penalty
REPORTS = [("TICKET", "Report for a Complaint ID", "शिकायत आईडी रिपोर्ट"),
           ("HW_SW", "Hardware/software complaint statistics", "हार्डवेयर/सॉफ्टवेयर शिकायत सांख्यिकी")] + \
          [(f"CENTRE_{c}", f"Complaint statistics - {c}", f"शिकायत सांख्यिकी - {c}") for c in ("NRLDC", "ERLDC", "WRLDC", "SRLDC", "NERLDC", "NLDC")] + \
          [("MODULE", "Module-wise complaints", "मॉड्यूल-वार शिकायतें"), ("SEVERITY_SLA", "Severity-wise SLA compliance", "गंभीरता-वार एसएलए अनुपालन"),
           ("ESCALATION", "Escalation level summary", "एस्केलेशन स्तर सारांश"), ("AGEING", "Pending complaints ageing", "लंबित शिकायतों की आयु"),
           ("FEEDBACK", "Feedback summary", "प्रतिक्रिया सारांश"), ("CHANNEL", "Channel-wise intake", "चैनल-वार प्राप्ति")]

TICKET_COLS = [("ticket_number", "Ticket ID", "टिकट आईडी"), ("centre", "Centre", "केंद्र"), ("module", "Module", "मॉड्यूल"),
               ("subject", "Subject", "विषय"), ("severity", "Severity", "गंभीरता"), ("escalation_level", "Level", "स्तर"),
               ("status", "Status", "स्थिति"), ("created_at", "Logged", "दर्ज"), ("resolved_at", "Resolved", "समाधान")]


@router.get("/reports")
def reports_catalogue(user=Depends(get_current_user)):
    return [{"code": c, "name_en": en, "name_hi": hi} for c, en, hi in REPORTS]


def _parse_day(s: str | None, default: datetime) -> datetime:
    return datetime.fromisoformat(s) if s else default


@router.get("/reports/{code}")
def run_report(code: str, fmt: str = "json", from_date: str | None = None, to_date: str | None = None, ticket_id: int | None = None,
               db: Session = Depends(get_db), user=Depends(get_current_user)):
    rep = next((r for r in REPORTS if r[0] == code), None)
    if rep is None:
        raise HTTPException(404)
    if code == "TICKET":
        t = _get(db, ticket_id or 0, user)
        rows = [{"time": h.created_at, "event": h.event, "by": h.actor_name, "status": h.status, "comment": h.comment}
                for h in t.history if is_staff(user) or not h.is_internal]
        cols = [("time", "Time", "समय"), ("event", "Event", "घटना"), ("by", "By", "द्वारा"), ("status", "Status", "स्थिति"), ("comment", "Comment", "टिप्पणी")]
        sub = f"{t.ticket_number} · {t.subject} · Severity {t.severity or '-'} · Status {t.status}"
        if fmt == "json":
            return {"title": rep[1], "columns": cols, "rows": rows, "subtitle": sub}
        return export(fmt, f"{rep[1]}: {t.ticket_number}", rep[2], cols, rows, f"ticket_{t.ticket_number.replace('/', '-')}", subtitle=sub)
    if not is_staff(user) and not role_codes(user) & {"DIRECTOR"}:
        raise HTTPException(403)
    f0 = _parse_day(from_date, utcnow() - timedelta(days=90))
    f1 = _parse_day(to_date, utcnow()) + timedelta(days=1)
    tickets = db.scalars(select(Ticket).where(Ticket.created_at >= f0, Ticket.created_at < f1)).all()
    group_cols = [("key", "Group", "समूह"), ("total", "Total", "कुल"), ("open", "Pending", "लंबित"),
                  ("resolved", "Solved", "समाधान"), ("breached", "SLA breached", "एसएलए उल्लंघन")]

    def grouped(keyfn):
        acc: dict[str, dict] = {}
        for t in tickets:
            k = keyfn(t)
            g = acc.setdefault(k, {"key": k, "total": 0, "open": 0, "resolved": 0, "breached": 0})
            g["total"] += 1
            g["open"] += t.status in svc.OPEN_STATES
            g["resolved"] += t.status in ("RESOLVED", "CLOSED")
            g["breached"] += svc.sla_status(t)["resolution_breached"]
        return sorted(acc.values(), key=lambda x: x["key"])

    if code.startswith("CENTRE_"):
        c = code.split("_", 1)[1]
        tickets = [t for t in tickets if t.centre.code == c]
        rows, cols = [ticket_out(t, user) for t in tickets], TICKET_COLS
    elif code == "HW_SW":
        tickets = [t for t in tickets if t.complaint_type in ("HARDWARE", "SOFTWARE", "BUG", "SYSTEM_ACCESS")]
        rows, cols = grouped(lambda t: t.complaint_type), group_cols
    elif code == "MODULE":
        rows, cols = grouped(lambda t: t.module), group_cols
    elif code == "SEVERITY_SLA":
        rows, cols = grouped(lambda t: f"Severity {t.severity or 'unassessed'}"), group_cols
    elif code == "ESCALATION":
        rows, cols = grouped(lambda t: f"Level {t.escalation_level}"), group_cols
    elif code == "CHANNEL":
        rows, cols = grouped(lambda t: t.channel), group_cols
    elif code == "AGEING":
        now = utcnow()

        def bucket(t):
            d = (now - t.created_at).days
            return "0-1 days" if d <= 1 else "2-7 days" if d <= 7 else "8-30 days" if d <= 30 else ">30 days"
        tickets = [t for t in tickets if t.status in svc.OPEN_STATES]
        rows, cols = grouped(bucket), group_cols
    else:  # FEEDBACK
        rated = [t for t in tickets if t.feedback_rating]
        rows = [{"key": f"{r} star", "total": sum(1 for t in rated if t.feedback_rating == r), "open": 0, "resolved": 0, "breached": 0} for r in range(5, 0, -1)]
        cols = group_cols[:2]
    sub = f"{f0:%d-%m-%Y} to {(f1 - timedelta(days=1)):%d-%m-%Y}"
    if fmt == "json":
        return {"title": rep[1], "columns": cols, "rows": rows, "subtitle": sub}
    return export(fmt, rep[1], rep[2], cols, rows, f"cas_{code.lower()}", subtitle=sub)


@router.get("/sla-penalty-report")
def sla_penalty_report(from_month: str | None = None, quarterly_amc_value: float = 3_000_000.0, fmt: str = "json",
                       db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Quarterly SLA downtime & AMC penalty sheet, submitted with the AMC invoice (TS Ch.5 p.48; Cl. 10.6 p.68-69)."""
    if not is_staff(user):
        raise HTTPException(403)
    now = utcnow()
    y, m = (int(from_month[:4]), int(from_month[5:7])) if from_month else (now.year, ((now.month - 1) // 3) * 3 + 1)
    months = [((y * 12 + (m - 1) + i) // 12, (m - 1 + i) % 12 + 1) for i in range(3)]
    monthly_amc = quarterly_amc_value / 3
    avail_rows = []
    total_penalty = 0.0
    for yy, mm in months:
        a = svc.month_availability(db, yy, mm)
        a["penalty_amount"] = round(monthly_amc * a["penalty_pct"] / 100, 2)
        total_penalty += a["penalty_amount"]
        avail_rows.append(a)
    q0 = datetime(months[0][0], months[0][1], 1)
    ly, lm = months[-1]
    q1 = datetime(ly + (lm == 12), lm % 12 + 1, 1)
    tick_rows = []
    for t in db.scalars(select(Ticket).where(Ticket.created_at >= q0, Ticket.created_at < q1, Ticket.severity.isnot(None))):
        s = svc.sla_status(t)
        resp_allowed, reso_allowed = svc.SLA[t.severity]
        tick_rows.append({"ticket_number": t.ticket_number, "severity": t.severity, "logged": t.created_at,
                          "allowed_response_min": int(resp_allowed.total_seconds() // 60),
                          "actual_response_min": int(((t.responded_at or now) - t.created_at).total_seconds() // 60),
                          "allowed_resolution_min": int(reso_allowed.total_seconds() // 60),
                          "actual_resolution_min": int(((t.resolved_at or now) - t.created_at).total_seconds() // 60),
                          "delay_min": s["resolution_delay_min"], "breached": "YES" if s["resolution_breached"] or s["response_breached"] else "NO"})
    result = {"quarter": f"{months[0][0]}-{months[0][1]:02d} to {months[-1][0]}-{months[-1][1]:02d}",
              "quarterly_amc_value": quarterly_amc_value, "monthly_amc": round(monthly_amc, 2),
              "months": avail_rows, "tickets": tick_rows, "total_penalty": round(total_penalty, 2),
              "net_payable": round(quarterly_amc_value - total_penalty, 2)}
    if fmt == "json":
        return result
    cols = [("ticket_number", "Ticket", "टिकट"), ("severity", "Severity", "गंभीरता"), ("logged", "Logged", "दर्ज"),
            ("allowed_response_min", "Allowed response (min)", "अनुमत प्रतिक्रिया (मिनट)"),
            ("actual_response_min", "Actual response (min)", "वास्तविक प्रतिक्रिया (मिनट)"),
            ("allowed_resolution_min", "Allowed resolution (min)", "अनुमत समाधान (मिनट)"),
            ("actual_resolution_min", "Actual resolution (min)", "वास्तविक समाधान (मिनट)"),
            ("delay_min", "Delay (min)", "विलंब (मिनट)"), ("breached", "Breached", "उल्लंघन")]
    note = " | ".join(f"{a['month']}: availability {a['availability_pct']}% → penalty {a['penalty_pct']}% (₹{a['penalty_amount']:,.0f})"
                      for a in avail_rows) + f" | Total deduction ₹{total_penalty:,.0f}; net payable ₹{result['net_payable']:,.0f}"
    if fmt == "xlsx":
        from app.utils.exports import bilingual_xlsx, file_response

        acols = [("month", "Month", "माह"), ("total_min", "Total (min)", "कुल (मिनट)"), ("maintenance_min", "Planned maint. (min)", "नियोजित रखरखाव"),
                 ("scheduled_uptime_min", "Scheduled uptime (min)", "निर्धारित अपटाइम"), ("downtime_min", "Downtime (min)", "डाउनटाइम"),
                 ("availability_pct", "Availability %", "उपलब्धता %"), ("penalty_pct", "Penalty %", "दंड %"), ("penalty_amount", "Penalty ₹", "दंड ₹")]
        wb = bilingual_xlsx("Quarterly SLA & AMC penalty", "त्रैमासिक एसएलए एवं एएमसी दंड", acols, avail_rows)
        tb = bilingual_xlsx("Ticket SLA compliance", "टिकट एसएलए अनुपालन", cols, tick_rows)
        from openpyxl import load_workbook
        import io

        w1, w2 = load_workbook(io.BytesIO(wb)), load_workbook(io.BytesIO(tb))
        ws_t = w1.create_sheet("Tickets")
        for row in w2.active.iter_rows(values_only=True):
            ws_t.append(row)
        w1.active.title = "Availability"
        buf = io.BytesIO()
        w1.save(buf)
        return file_response(buf.getvalue(), "sla_penalty_report.xlsx")
    return export(fmt, "Quarterly SLA downtime & AMC penalty report", "त्रैमासिक एसएलए डाउनटाइम एवं एएमसी दंड रिपोर्ट", cols, tick_rows,
                  "sla_penalty_report", subtitle=f"Quarter {result['quarter']} · Quarterly AMC ₹{quarterly_amc_value:,.0f}", footer_note=note)


# ------------------------------------------------------------------- knowledge base
@router.get("/kb")
def kb(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.scalars(select(KnowledgeBaseArticle).order_by(KnowledgeBaseArticle.id.desc())).all()
    staff = is_staff(user)
    return [{"id": a.id, "module": a.module, "question_en": a.question_en, "question_hi": a.question_hi, "answer_en": a.answer_en,
             "answer_hi": a.answer_hi, "is_published": a.is_published, "source_ticket_id": a.source_ticket_id}
            for a in rows if a.is_published or staff]


class KbIn(BaseModel):
    module: str
    question_en: str
    question_hi: str = ""
    answer_en: str
    answer_hi: str = ""
    is_published: bool = True


@router.post("/kb")
def kb_add(body: KbIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403)
    a = KnowledgeBaseArticle(**body.model_dump())
    db.add(a)
    db.commit()
    return {"id": a.id}


@router.patch("/kb/{aid}")
def kb_publish(aid: int, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not is_staff(user):
        raise HTTPException(403)
    a = db.get(KnowledgeBaseArticle, aid)
    for k in ("question_en", "question_hi", "answer_en", "answer_hi", "is_published"):
        if k in body:
            setattr(a, k, body[k])
    db.commit()
    return {"ok": True}


@router.post("/run-escalation")
def run_escalation(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Manual trigger of the background escalation job (POC demo convenience)."""
    if not is_admin(user) and not is_staff(user):
        raise HTTPException(403)
    out = svc.auto_escalate(db)
    db.commit()
    return {"escalated": out}
