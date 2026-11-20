"""Outage Coordination System (TS Cl. 11.4.7 p.191-200; FRD OC-01..17)."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.rbac import get_current_user, is_admin, is_external, role_codes, sees_all_centres
from app.db.base import utcnow
from app.db.session import get_db
from app.integrations.notifier import notify_users, send_raw
from app.integrations.weather_adapter import alerts_for_area
from app.modules.auth_rbac.models import Centre, User
from app.modules.dms_files.service import store_upload
from app.modules.master_registry.models import Entity, GridElement
from app.modules.outage_coord.models import OccOutagePlan
from app.utils.dt import ist_to_utc_naive, to_utc_naive, utc_to_ist
from app.utils.exports import bilingual_xlsx, export, file_response
from app.utils.ids import simple_number

router = APIRouter(prefix="/api/v1/outage", tags=["outage-coordination"])
COORD = {"OUTAGE_COORDINATOR"}


def _coord(user, centre_id=None) -> bool:
    return is_admin(user) or (bool(role_codes(user) & COORD) and (centre_id is None or sees_all_centres(user) or user.centre_id == centre_id))


def determine_route(el: GridElement, requester: Entity | None) -> str:
    """Interconnection routing (TS Table 12 p.191-192): 400 kV+, central/private-owned, HVDC, inter-regional, inter-state -> OCC;
    220 kV and below state-owned lines -> D-3; bays -> D-2."""
    if el.element_type == "BAY":
        return "D2"
    line_owner = next((o.entity for o in el.owners if o.ownership_role in ("LINE_OWNER", "ASSET_OWNER")), None)
    if el.voltage_kv >= 400 or el.is_inter_regional or el.element_type in ("HVDC_POLE", "HVDC_LINE"):
        return "OCC_M2"
    if line_owner and line_owner.sector == "STATE" and (requester is None or requester.sector == "STATE"):
        return "D3"
    if line_owner and line_owner.sector == "STATE":
        return "OCC_M2"
    return "OCC_M2" if el.is_ists else "D3"


def occ_window_open(today: date) -> tuple[bool, str]:
    """Requests for M+2 between the 26th of M and the 5th of M+1 (TS p.192)."""
    if today.day >= 26:
        tgt = date(today.year + (today.month + 2 > 12), (today.month + 1) % 12 + 1, 1)
        return True, f"{tgt:%Y-%m}"
    if today.day <= 5:
        tgt = date(today.year + (today.month + 1 > 12), today.month % 12 + 1, 1)
        return True, f"{tgt:%Y-%m}"
    nxt = date(today.year + (today.month + 2 > 12), (today.month + 1) % 12 + 1, 1)
    return False, f"{nxt:%Y-%m}"


def plan_out(db: Session, p: OccOutagePlan, user=None) -> dict:
    el = p.element
    area = el.from_substation.weather_area if el.from_substation else ""
    return {"id": p.id, "reference_number": p.reference_number, "centre": db.get(Centre, p.centre_id).code, "occ_number": p.occ_number,
            "target_month": p.target_month, "plan_route": p.plan_route, "element_id": el.id, "element": el.name, "element_type": el.element_type,
            "voltage_kv": el.voltage_kv, "owner": p.owner_name, "requester": db.get(Entity, p.requester_entity_id).short_name if p.requester_entity_id else "",
            "req_from": p.req_from, "req_to": p.req_to, "approved_from": p.approved_from, "approved_to": p.approved_to,
            "daily_or_continuous": p.daily_or_continuous, "request_type": p.request_type, "reason": p.reason, "requester_remarks": p.requester_remarks,
            "availability_comments": p.availability_comments if (not is_external(user) or p.share_availability_with_occ) else "",
            "availability_head_proposed": p.availability_head_proposed, "availability_head_rldc": p.availability_head_rldc,
            "category_code": p.category_code, "share_availability_with_occ": p.share_availability_with_occ, "is_inter_regional": p.is_inter_regional,
            "nldc_status": p.nldc_status, "non_auto_ar": p.non_auto_ar, "status": p.status, "rpc_remarks": p.rpc_remarks, "rldc_comments": p.rldc_comments,
            "d1_comment_coordinator": p.d1_comment_coordinator, "d1_comment_hod": p.d1_comment_hod, "d1_comment_head": p.d1_comment_head,
            "weather_alerts": alerts_for_area(db, area) if area else [], "stakeholders": p.stakeholders_json, "change_requests": p.change_requests_json,
            "created_at": p.created_at}


class PlanIn(BaseModel):
    grid_element_id: int
    req_from: datetime
    req_to: datetime
    daily_or_continuous: str = Field("CONTINUOUS", pattern="^(DAILY|CONTINUOUS)$")
    request_type: str = "MAINTENANCE"
    reason: str = Field(min_length=3)
    requester_remarks: str = ""
    availability_comments: str = ""
    availability_head_proposed: str = "SELF"
    non_auto_ar: bool = False
    route: str | None = Field(None, pattern="^(OCC_M2|D3|D2|EMERGENCY|NON_AUTO)$")


@router.post("/plans")
def create_plan(body: PlanIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    el = db.get(GridElement, body.grid_element_id)
    if el is None:
        raise HTTPException(404)
    if is_external(user) and not any(o.entity_id == user.entity_id for o in el.owners):
        raise HTTPException(403, "Request outages only for elements where you are an owner")
    f, t = to_utc_naive(body.req_from), to_utc_naive(body.req_to)
    if t <= f:
        raise HTTPException(422, "To time must be after From time")
    requester = db.get(Entity, user.entity_id) if user.entity_id else None
    route = body.route or ("NON_AUTO" if body.non_auto_ar else determine_route(el, requester))
    today = utc_to_ist(utcnow()).date()
    status, target = "SUBMITTED", f"{f:%Y-%m}"
    if route == "OCC_M2":
        open_, target = occ_window_open(today)
        status = "SUBMITTED" if open_ else "LATE_PENDING_RPC"
    owner = next((o.entity.short_name or o.entity.name for o in el.owners if o.ownership_role in ("LINE_OWNER", "ASSET_OWNER", "SECTION_OWNER")), "")
    stakeholders = [{"entity_id": o.entity_id, "name": o.entity.short_name or o.entity.name, "role": o.ownership_role, "selected": True} for o in el.owners]
    p = OccOutagePlan(reference_number=simple_number(db, f"SD/{el.centre.code}/{today:%Y%m}"), centre_id=el.centre_id,
                      occ_number=f"OCC-{target}" if route == "OCC_M2" else "", target_month=target, plan_route=route, grid_element_id=el.id,
                      requester_entity_id=user.entity_id, requester_user_id=user.id, owner_name=owner, req_from=f, req_to=t,
                      daily_or_continuous=body.daily_or_continuous, request_type=body.request_type, reason=body.reason,
                      requester_remarks=body.requester_remarks + (" (Req. for AR)" if body.non_auto_ar else ""),
                      availability_comments=body.availability_comments, availability_head_proposed=body.availability_head_proposed.upper(),
                      is_inter_regional=el.is_inter_regional, nldc_status="PENDING" if el.is_inter_regional or el.voltage_kv >= 765 else "NA",
                      non_auto_ar=body.non_auto_ar, status=status if route == "OCC_M2" else "D3_APPLIED", stakeholders_json=stakeholders)
    db.add(p)
    db.flush()
    who = {"RPC"} if route == "OCC_M2" else COORD
    notify_users(db, [u for u in db.scalars(select(User).where(User.is_active)) if {r.role.code for r in u.roles} & who],
                 f"Shutdown request {p.reference_number} ({route}) for {el.name}", module="outage_coord", link="/outage", channels=("INAPP",))
    audit(db, user, "outage_coord", "PLAN_SUBMITTED", "plan", p.reference_number, new=body.model_dump(mode="json"))
    db.commit()
    return plan_out(db, p, user)


@router.get("/plans")
def list_plans(centre: str | None = None, status: str | None = None, route: str | None = None, target_month: str | None = None,
               db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(OccOutagePlan).order_by(OccOutagePlan.req_from.desc()).limit(500)
    if is_external(user) and "RPC" not in role_codes(user):
        stmt = stmt.where(OccOutagePlan.requester_entity_id == user.entity_id)
    elif centre and centre != "ALL":
        stmt = stmt.join(Centre, OccOutagePlan.centre_id == Centre.id).where(Centre.code == centre)
    elif not sees_all_centres(user) and not is_external(user):
        stmt = stmt.where(or_(OccOutagePlan.centre_id == user.centre_id, OccOutagePlan.is_inter_regional))
    if status:
        stmt = stmt.where(OccOutagePlan.status == status)
    if route:
        stmt = stmt.where(OccOutagePlan.plan_route == route)
    if target_month:
        stmt = stmt.where(OccOutagePlan.target_month == target_month)
    return [plan_out(db, p, user) for p in db.scalars(stmt)]


class RpcIn(BaseModel):
    plan_ids: list[int]
    action: str = Field(pattern="^(ENABLE_LATE|FORWARD|OCC_APPROVE|OCC_REJECT|SEND_BACK)$")
    remarks: str = ""
    approved_from: datetime | None = None
    approved_to: datetime | None = None


@router.post("/rpc")
def rpc_action(body: RpcIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """RPC login: enable late entries, forward to RLDC by 6th, final OCC verdict (TS p.192-197)."""
    if not ("RPC" in role_codes(user) or is_admin(user)):
        raise HTTPException(403, "RPC login only")
    out = []
    for pid in body.plan_ids:
        p = db.get(OccOutagePlan, pid)
        if body.action == "ENABLE_LATE":
            if p.status != "LATE_PENDING_RPC":
                raise HTTPException(409, f"{p.reference_number} is not a late request")
            p.status = "SUBMITTED"
        elif body.action == "FORWARD":
            p.status = "RPC_FORWARDED"
        elif body.action == "OCC_APPROVE":
            p.status = "OCC_APPROVED"
            p.approved_from = to_utc_naive(body.approved_from) or p.req_from
            p.approved_to = to_utc_naive(body.approved_to) or p.req_to
        elif body.action == "OCC_REJECT":
            p.status = "OCC_REJECTED"
        else:
            p.status = "RLDC_REVIEW"
        p.rpc_remarks = body.remarks or p.rpc_remarks
        out.append(p.reference_number)
        if p.requester_user_id and body.action in ("OCC_APPROVE", "OCC_REJECT"):
            notify_users(db, [db.get(User, p.requester_user_id)], f"OCC verdict on {p.reference_number}: {p.status}", body=body.remarks,
                         module="outage_coord", link="/outage")
    audit(db, user, "outage_coord", f"RPC_{body.action}", "plan", ",".join(out))
    db.commit()
    return {"updated": out}


class RldcReviewIn(BaseModel):
    rldc_comments: str = ""
    availability_head_rldc: str = ""
    category_code: str = ""
    share_availability_with_occ: bool = True
    stakeholders: list[dict] | None = None


@router.post("/plans/{pid}/rldc-review")
def rldc_review(pid: int, body: RldcReviewIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """RLDC Outage Coordinator appends comments, RLDC availability head and category code (Stage 2, TS p.174)."""
    p = db.get(OccOutagePlan, pid)
    if not _coord(user, p.centre_id):
        raise HTTPException(403)
    p.rldc_comments = body.rldc_comments or p.rldc_comments
    p.availability_head_rldc = body.availability_head_rldc.upper() or p.availability_head_rldc
    p.category_code = body.category_code or p.category_code
    p.share_availability_with_occ = body.share_availability_with_occ
    if body.stakeholders is not None:
        p.stakeholders_json = body.stakeholders
    if p.status == "RPC_FORWARDED":
        p.status = "RLDC_REVIEW"
    db.commit()
    return plan_out(db, p, user)


@router.get("/utility-sheets")
def utility_sheets(centre: str | None = None, target_month: str | None = None, fmt: str = "json",
                   db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Master data segregated into utility-wise sheets, shared with users and e-mailed (TS p.194-196)."""
    plans = list_plans(centre=centre, target_month=target_month, db=db, user=user)
    sheets: dict[str, list] = defaultdict(list)
    for p in plans:
        sheets[f"{p['owner'] or 'Other'} Owned"].append(p)
    if fmt == "json":
        return {k: v for k, v in sheets.items()}
    cols = [("reference_number", "Reference", "संदर्भ"), ("element", "Element", "तत्व"), ("owner", "Owner", "स्वामी"),
            ("daily_or_continuous", "Daily/Continuous", "दैनिक/निरंतर"), ("reason", "Reason", "कारण"), ("req_from", "From", "से"),
            ("req_to", "To", "तक"), ("request_type", "Type", "प्रकार"), ("rldc_comments", "RLDC comments", "आरएलडीसी टिप्पणी"), ("status", "Status", "स्थिति")]
    return file_response(bilingual_xlsx("Utility-wise shutdown sheets", "उपयोगिता-वार शटडाउन शीट", cols, [], sheets=dict(sheets) or {"Empty": []}),
                         "utility_wise_shutdowns.xlsx")


@router.post("/plans/{pid}/apply-d3")
def apply_d3(pid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """After OCC approval the constituent applies on D-3 within the configurable window (default D-3 10:00-17:00)."""
    p = db.get(OccOutagePlan, pid)
    if p.status != "OCC_APPROVED":
        raise HTTPException(409, "Only OCC-approved shutdowns can be applied on D-3")
    if is_external(user) and p.requester_entity_id != user.entity_id:
        raise HTTPException(403)
    d = utc_to_ist(p.approved_from or p.req_from).date()
    win_start = ist_to_utc_naive(d - timedelta(days=4 if "D-4" in "D-3" else 3), time(10, 0))
    win_end = ist_to_utc_naive(d - timedelta(days=3), time(17, 0))
    now = utcnow()
    if not (win_start - timedelta(days=1) <= now <= win_end) and not is_admin(user):
        raise HTTPException(409, f"D-3 application window is {utc_to_ist(win_start):%d-%m %H:%M} to {utc_to_ist(win_end):%d-%m %H:%M} IST")
    p.status = "D3_APPLIED"
    db.commit()
    return plan_out(db, p, user)


class ChangeIn(BaseModel):
    new_from: datetime
    new_to: datetime
    reason: str


@router.post("/plans/{pid}/change-request")
def change_request(pid: int, body: ChangeIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Change of date/time against the same Shutdown ID, approved/rejected by RLDC (TS p.197)."""
    p = db.get(OccOutagePlan, pid)
    p.change_requests_json = [*p.change_requests_json, {"new_from": to_utc_naive(body.new_from).isoformat(), "new_to": to_utc_naive(body.new_to).isoformat(),
                                                        "reason": body.reason, "status": "PENDING", "at": utcnow().isoformat()}]
    db.commit()
    return plan_out(db, p, user)


@router.post("/plans/{pid}/change-request/{idx}")
def decide_change(pid: int, idx: int, approve: bool, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = db.get(OccOutagePlan, pid)
    if not _coord(user, p.centre_id):
        raise HTTPException(403)
    items = [dict(x) for x in p.change_requests_json]
    items[idx]["status"] = "APPROVED" if approve else "REJECTED"
    if approve:
        p.approved_from = datetime.fromisoformat(items[idx]["new_from"])
        p.approved_to = datetime.fromisoformat(items[idx]["new_to"])
    p.change_requests_json = items
    db.commit()
    return plan_out(db, p, user)


@router.post("/plans/{pid}/nldc")
def nldc_action(pid: int, approve: bool = Form(...), remarks: str = Form(""), db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Inter-regional / 765 kV shutdowns are routed via NLDC; no forwarding among RLDCs (TS p.198-199)."""
    if not ({"NLDC_USER", "HEAD_NLDC"} & role_codes(user) or is_admin(user)):
        raise HTTPException(403, "NLDC only")
    p = db.get(OccOutagePlan, pid)
    p.nldc_status = "APPROVED" if approve else "REJECTED"
    p.rldc_comments = (p.rldc_comments + f" | NLDC: {remarks}").strip(" |")
    for c in db.scalars(select(Centre).where(Centre.code != "NLDC")):
        if c.id != p.centre_id and p.is_inter_regional:
            send_raw(db, "EMAIL", f"outage.{c.code.lower()}@grid-india.local", f"NLDC decision on inter-regional shutdown {p.reference_number}: {p.nldc_status}",
                     module="outage_coord")
    db.commit()
    return plan_out(db, p, user)


@router.post("/plans/{pid}/d1")
def d1_decision(pid: int, approve: bool = Form(...), comment_coordinator: str = Form(""), comment_hod: str = Form(""), comment_head: str = Form(""),
                request_reason: str | None = Form(None), study_file: UploadFile | None = File(None),
                db: Session = Depends(get_db), user=Depends(get_current_user)):
    """D-1 final approval with PSS/E study file, weather check and three-level comments; approved shutdowns flow into the
    Real-time module's planned list and an e-mail list is circulated (TS p.199)."""
    p = db.get(OccOutagePlan, pid)
    if not _coord(user, p.centre_id):
        raise HTTPException(403)
    if p.status not in ("D3_APPLIED", "OCC_APPROVED", "RLDC_REVIEW", "SUBMITTED"):
        raise HTTPException(409, f"Not ready for D-1 decision (status {p.status})")
    if approve and p.nldc_status == "PENDING":
        raise HTTPException(409, "NLDC approval pending for inter-regional / 765 kV shutdown")
    if study_file is not None and study_file.filename:
        p.study_doc_id = store_upload(db, file=study_file, module="outage_coord", doc_category="PSSE_STUDY", owner_ref=f"plan:{p.id}", user=user,
                                      allowed={".pdf", ".jpg", ".jpeg", ".png"}).id
    if request_reason:
        p.reason = request_reason
    p.d1_comment_coordinator, p.d1_comment_hod, p.d1_comment_head = comment_coordinator, comment_hod, comment_head
    el = p.element
    p.weather_alert = "; ".join(alerts_for_area(db, el.from_substation.weather_area)) if el.from_substation else ""
    p.status = "D1_APPROVED" if approve else "D1_REJECTED"
    p.approved_from = p.approved_from or p.req_from
    p.approved_to = p.approved_to or p.req_to
    if approve:
        from app.modules.realtime_outage.models import OutageCodeRequest
        from app.modules.realtime_outage import service as rt

        req = OutageCodeRequest(request_number=simple_number(db, f"REQ/{el.centre.code}/{utcnow():%y%m%d}"), centre_id=p.centre_id,
                                grid_element_id=el.id, requester_user_id=p.requester_user_id or user.id, requester_entity_id=p.requester_entity_id,
                                request_category="PLANNED", action="OPENING", reason=p.reason, planned_time=p.approved_from,
                                availability_head_proposed=p.availability_head_rldc or p.availability_head_proposed, occ_plan_id=p.id,
                                status="REQUESTED")
        db.add(req)
        db.flush()
        rt.build_consents(db, req)
    recipients = db.scalars(select(User).where(or_(User.id == p.requester_user_id, User.entity_id.in_([s["entity_id"] for s in p.stakeholders_json if s.get("selected")])))).all()
    notify_users(db, list(recipients), f"D-1 decision on {p.reference_number} ({el.name}): {p.status}", body=comment_coordinator,
                 module="outage_coord", step_code="D1_DECISION", link="/outage", centre_id=p.centre_id)
    audit(db, user, "outage_coord", p.status, "plan", p.reference_number)
    db.commit()
    return plan_out(db, p, user)


@router.get("/d1-list")
def d1_list(day: date | None = None, centre: str | None = None, fmt: str = "json", db: Session = Depends(get_db), user=Depends(get_current_user)):
    """D-1 list of approved and rejected shutdowns with reasons e-mailed to all RLDC staff (Annexure-3 format)."""
    day = day or (utc_to_ist(utcnow()).date() + timedelta(days=1))
    d0, d1 = ist_to_utc_naive(day, time(0)), ist_to_utc_naive(day + timedelta(days=1), time(0))
    rows = [p for p in list_plans(centre=centre, db=db, user=user) if p["status"] in ("D1_APPROVED", "D1_REJECTED") and d0 <= (p["approved_from"] or p["req_from"]) < d1]
    if fmt == "json":
        return rows
    cols = [("reference_number", "Ref", "संदर्भ"), ("element", "Element", "तत्व"), ("owner", "Owner", "स्वामी"), ("approved_from", "From", "से"),
            ("approved_to", "To", "तक"), ("status", "Decision", "निर्णय"), ("reason", "Reason", "कारण"), ("d1_comment_coordinator", "Comments", "टिप्पणी")]
    return export(fmt, f"D-1 shutdown list for {day:%d-%m-%Y}", f"{day:%d-%m-%Y} हेतु डी-1 शटडाउन सूची", cols, rows, f"d1_list_{day}")


@router.get("/route-preview")
def route_preview(grid_element_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    el = db.get(GridElement, grid_element_id)
    requester = db.get(Entity, user.entity_id) if user.entity_id else None
    open_, target = occ_window_open(utc_to_ist(utcnow()).date())
    return {"route": determine_route(el, requester), "occ_window_open": open_, "target_month": target,
            "via_nldc": el.is_inter_regional or el.voltage_kv >= 765}
