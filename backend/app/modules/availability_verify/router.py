"""Availability Inputs Verification (TS Cl. 11.4.5 p.173-179; FRD AV-01..13)."""
import calendar
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import scheduler
from app.core.audit import audit
from app.core.rbac import get_current_user, is_admin, is_external, role_codes, sees_all_centres
from app.db.base import utcnow
from app.db.session import get_db
from app.integrations.notifier import notify_users
from app.modules.auth_rbac.models import Centre, User
from app.modules.availability_verify.models import AVAILABILITY_HEADS, SHEET_TABS, AvailabilityRecord, CategoryCode
from app.modules.availability_verify.service import hours
from app.modules.dms_files.service import store_upload
from app.modules.master_registry.models import Entity, GridElement
from app.utils.dt import to_utc_naive, utc_to_ist
from app.utils.exports import bilingual_xlsx, file_response

router = APIRouter(prefix="/api/v1/availability", tags=["availability"])


def _coord(user) -> bool:
    return is_admin(user) or "AVAIL_COORDINATOR" in role_codes(user)


def rec_out(db: Session, r: AvailabilityRecord) -> dict:
    return {"id": r.id, "billing_month": r.billing_month, "element_id": r.grid_element_id, "element": r.element.name,
            "element_uid": r.element.unique_element_id, "owner": db.get(Entity, r.owner_entity_id).short_name or db.get(Entity, r.owner_entity_id).name,
            "owner_entity_id": r.owner_entity_id, "outage_start": r.outage_start, "outage_end": r.outage_end, "hours": hours(r),
            "availability_head": r.availability_head, "tab": SHEET_TABS.get(r.availability_head, "Outage_Others"), "category_code": r.category_code,
            "user_action": r.user_action, "is_locked": r.is_locked, "proposed_changes": r.proposed_changes_json, "stakeholder_comment": r.stakeholder_comment,
            "sent_to_protection": r.sent_to_protection, "protection_remarks": r.protection_remarks, "rldc_verified_status": r.rldc_verified_status,
            "rldc_comment": r.rldc_comment, "rpc_status": r.rpc_status, "parent_record_id": r.parent_record_id, "is_bifurcated_parent": r.is_bifurcated_parent,
            "added_by_licensee": r.added_by_licensee, "submitted_at": r.submitted_at}


@router.get("/meta")
def meta(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {"heads": AVAILABILITY_HEADS, "tabs": sorted(set(SHEET_TABS.values())),
            "category_codes": [{"code": c.code, "description": c.description, "owner_fault": c.owner_fault}
                               for c in db.scalars(select(CategoryCode).order_by(CategoryCode.code))],
            "is_coordinator": _coord(user), "is_rpc": "RPC" in role_codes(user), "is_protection": "PROTECTION_COORDINATOR" in role_codes(user)}


@router.get("/sheet")
def sheet(month: str, centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Spreadsheet web page for month N, auto-generated on the 1st of N+1, one tab per availability head (TS p.176-177)."""
    stmt = select(AvailabilityRecord).where(AvailabilityRecord.billing_month == month, AvailabilityRecord.is_bifurcated_parent.is_(False)).order_by(AvailabilityRecord.outage_start)
    rows = db.scalars(stmt).all()
    codes = role_codes(user)
    if is_external(user) and "RPC" not in codes:
        rows = [r for r in rows if r.owner_entity_id == user.entity_id]
    elif "RPC" in codes:
        rows = [r for r in rows if r.rldc_verified_status]
    elif centre and centre != "ALL":
        c = db.scalar(select(Centre).where(Centre.code == centre))
        rows = [r for r in rows if r.centre_id == c.id]
    elif not sees_all_centres(user):
        rows = [r for r in rows if r.centre_id == user.centre_id]
    if "PROTECTION_COORDINATOR" in codes and not _coord(user):
        rows = [r for r in rows if r.sent_to_protection]
    tabs: dict[str, list] = defaultdict(list)
    for r in rows:
        tabs[SHEET_TABS.get(r.availability_head, "Outage_Others")].append(rec_out(db, r))
    y, m = map(int, month.split("-"))
    nxt = datetime(y + (m == 12), m % 12 + 1, 1)
    return {"month": month, "generated_on": f"{nxt:%Y-%m}-01", "objection_deadline": f"{nxt:%Y-%m}-05", "publish_on": f"{nxt:%Y-%m}-06",
            "tabs": dict(tabs), "total": len(rows)}


@router.get("/sheet/export")
def sheet_export(month: str, owner_entity_id: int | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Excel by licensee with worksheets per availability head (Step 1 export / Step 3 coordinator download)."""
    data = sheet(month=month, db=db, user=user)["tabs"]
    if owner_entity_id:
        data = {k: [r for r in v if r["owner_entity_id"] == owner_entity_id] for k, v in data.items()}
    cols = [("element_uid", "Element ID", "तत्व आईडी"), ("element", "Element", "तत्व"), ("owner", "Owner", "स्वामी"),
            ("outage_start", "Outage time", "आउटेज समय"), ("outage_end", "Charging time", "चार्जिंग समय"), ("hours", "Hours", "घंटे"),
            ("availability_head", "Availability head", "उपलब्धता शीर्ष"), ("category_code", "Category", "श्रेणी"), ("user_action", "Action", "कार्रवाई"),
            ("stakeholder_comment", "Stakeholders comment", "हितधारक टिप्पणी"), ("rldc_verified_status", "Verified", "सत्यापित")]
    return file_response(bilingual_xlsx(f"Outage periods for availability - {month}", f"उपलब्धता हेतु आउटेज अवधि - {month}", cols, [],
                                        sheets=data or {"No data": []}), f"availability_{month}.xlsx")


@scheduler.register("availability_monthly_sheet")
def monthly_sheet_job(db: Session) -> None:
    """On the 1st of N+1, notify licensees that the month-N review sheet is ready (TS Step 1)."""
    now = utc_to_ist(utcnow())
    if now.day != 1 or now.hour != 0 or now.minute > 1:
        return
    y, m = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
    owners = {r.owner_entity_id for r in db.scalars(select(AvailabilityRecord).where(AvailabilityRecord.billing_month == f"{y}-{m:02d}"))}
    for o in owners:
        notify_users(db, db.scalars(select(User).where(User.entity_id == o)).all(), f"Availability review sheet for {y}-{m:02d} is ready (respond by 5th)",
                     module="availability", step_code="SHEET_GENERATED", link="/availability")


def _deadline(month: str) -> datetime:
    y, m = map(int, month.split("-"))
    return datetime(y + (m == 12), m % 12 + 1, 5, 23, 59)


class ActionIn(BaseModel):
    action: str = Field(pattern="^(ACCEPT|OBJECT)$")
    modified_outage_time: datetime | None = None
    modified_charging_time: datetime | None = None
    modified_head: str | None = None
    comments: str = ""


@router.post("/records/{rid}/action")
def licensee_action(rid: int, body: ActionIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Accept locks the row; Object adds proposed modified times/head; submit by 5th of N+1 (TS Step 2)."""
    r = db.get(AvailabilityRecord, rid)
    if r is None:
        raise HTTPException(404)
    if not (is_admin(user) or r.owner_entity_id == user.entity_id):
        raise HTTPException(403, "Only the owner licensee acts on its rows")
    if r.is_locked:
        raise HTTPException(409, "Row already accepted and locked")
    if utcnow() > _deadline(r.billing_month) and not is_admin(user):
        raise HTTPException(409, "Submission window closed on the 5th")
    if body.action == "ACCEPT":
        r.user_action, r.is_locked = "ACCEPTED", True
    else:
        if not (body.modified_outage_time or body.modified_charging_time or body.modified_head):
            raise HTTPException(422, "Propose modified outage time, charging time or availability head")
        r.user_action = "OBJECTED"
        r.proposed_changes_json = {"outage_time": to_utc_naive(body.modified_outage_time).isoformat() if body.modified_outage_time else None,
                                   "charging_time": to_utc_naive(body.modified_charging_time).isoformat() if body.modified_charging_time else None,
                                   "head": body.modified_head, "comments": body.comments}
    r.submitted_at = utcnow()
    audit(db, user, "availability", f"ROW_{r.user_action}", "availability_record", r.id, new=body.model_dump(mode="json"))
    db.commit()
    return rec_out(db, r)


class AddRowIn(BaseModel):
    month: str
    grid_element_id: int
    outage_start: datetime
    outage_end: datetime
    availability_head: str = "SELF"
    comments: str = ""


@router.post("/records")
def add_row(body: AddRowIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Licensee adds a shutdown row skipped by the software (TS Step 2)."""
    el = db.get(GridElement, body.grid_element_id)
    if not (is_admin(user) or any(o.entity_id == user.entity_id for o in el.owners)):
        raise HTTPException(403)
    r = AvailabilityRecord(centre_id=el.centre_id, billing_month=body.month, grid_element_id=el.id, owner_entity_id=user.entity_id or el.owners[0].entity_id,
                           outage_start=to_utc_naive(body.outage_start), outage_end=to_utc_naive(body.outage_end), availability_head=body.availability_head,
                           added_by_licensee=True, user_action="OBJECTED", proposed_changes_json={"comments": body.comments, "added_row": True})
    db.add(r)
    db.commit()
    return rec_out(db, r)


class CoordIn(BaseModel):
    record_ids: list[int]
    action: str = Field(pattern="^(SEND_TO_PROTECTION|VERIFY|NOT_VERIFY|FORWARD_RPC|STAKEHOLDER_COMMENT)$")
    comment: str = ""


@router.post("/coordinator")
def coordinator(body: CoordIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Steps 3-5: stakeholders' comments, selection for Protection, verify (not approve), forward selected columns to RPC."""
    if not _coord(user):
        raise HTTPException(403, "Availability Coordinator only")
    for rid in body.record_ids:
        r = db.get(AvailabilityRecord, rid)
        if body.action == "SEND_TO_PROTECTION":
            r.sent_to_protection = True
        elif body.action in ("VERIFY", "NOT_VERIFY"):
            r.rldc_verified_status = "VERIFIED" if body.action == "VERIFY" else "NOT_VERIFIED"
            r.rldc_comment = body.comment
        elif body.action == "FORWARD_RPC":
            if not r.rldc_verified_status:
                raise HTTPException(409, "Verify rows before forwarding to RPC")
            r.rpc_status = "FORWARDED"
        else:
            r.stakeholder_comment = body.comment
    if body.action == "SEND_TO_PROTECTION":
        notify_users(db, [u for u in db.scalars(select(User)) if "PROTECTION_COORDINATOR" in {x.role.code for x in u.roles}],
                     f"{len(body.record_ids)} outage row(s) sent for protection verification", module="availability", link="/availability")
    audit(db, user, "availability", body.action, "availability_record", ",".join(map(str, body.record_ids)))
    db.commit()
    return {"ok": True}


@router.post("/records/{rid}/protection")
def protection_remarks(rid: int, remarks: str = Form(...), file: UploadFile | None = File(None), db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Step 4: Protection Coordinator adds comments and file, row returns to Availability Coordinator."""
    if not ("PROTECTION_COORDINATOR" in role_codes(user) or is_admin(user)):
        raise HTTPException(403)
    r = db.get(AvailabilityRecord, rid)
    if not r.sent_to_protection:
        raise HTTPException(409, "Row not sent to Protection")
    r.protection_remarks = remarks
    if file is not None and file.filename:
        r.protection_doc_id = store_upload(db, file=file, module="availability", doc_category="PROTECTION_ANALYSIS", owner_ref=f"avail:{r.id}", user=user).id
    db.commit()
    return rec_out(db, r)


@router.post("/rpc")
def rpc(record_ids: list[int], action: str, comment: str = "", db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Step 6: RPC downloads (calculation outside portal) or sends back for correction."""
    if not ("RPC" in role_codes(user) or is_admin(user)):
        raise HTTPException(403)
    for rid in record_ids:
        r = db.get(AvailabilityRecord, rid)
        r.rpc_status = "DOWNLOADED" if action == "DOWNLOAD" else "SENT_BACK"
        if action != "DOWNLOAD":
            r.rldc_verified_status = ""
            r.rldc_comment = f"RPC: {comment}"
    db.commit()
    return {"ok": True}


class BifurcateIn(BaseModel):
    segments: list[dict]  # [{"start": iso, "end": iso, "head": "DEEMED", "category_code": "C14"}]


@router.post("/records/{rid}/bifurcate")
def bifurcate(rid: int, body: BifurcateIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Split one outage into contiguous segments with different heads/categories (TS p.178-179, Fig.88)."""
    if not _coord(user):
        raise HTTPException(403)
    r = db.get(AvailabilityRecord, rid)
    segs = sorted(({"start": to_utc_naive(datetime.fromisoformat(s["start"].replace("Z", "+00:00"))),
                    "end": to_utc_naive(datetime.fromisoformat(s["end"].replace("Z", "+00:00"))),
                    "head": s.get("head", r.availability_head), "category_code": s.get("category_code", r.category_code)} for s in body.segments),
                  key=lambda x: x["start"])
    if len(segs) < 2:
        raise HTTPException(422, "At least two segments required")
    if segs[0]["start"] != r.outage_start or segs[-1]["end"] != r.outage_end or any(a["end"] != b["start"] for a, b in zip(segs, segs[1:])):
        raise HTTPException(422, "Segments must be contiguous and exactly cover the original outage period")
    r.is_bifurcated_parent = True
    children = []
    for s in segs:
        c = AvailabilityRecord(centre_id=r.centre_id, billing_month=r.billing_month, outage_code_id=r.outage_code_id, grid_element_id=r.grid_element_id,
                               owner_entity_id=r.owner_entity_id, parent_record_id=r.id, outage_start=s["start"], outage_end=s["end"],
                               availability_head=s["head"].upper(), category_code=s["category_code"], user_action=r.user_action)
        db.add(c)
        children.append(c)
    audit(db, user, "availability", "BIFURCATED", "availability_record", r.id, new={"segments": len(segs)})
    db.commit()
    return [rec_out(db, c) for c in children]


@router.get("/summary")
def summary(month: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.scalars(select(AvailabilityRecord).where(AvailabilityRecord.billing_month == month, AvailabilityRecord.is_bifurcated_parent.is_(False))).all()
    y, m = map(int, month.split("-"))
    total_h = calendar.monthrange(y, m)[1] * 24
    per_el: dict[int, float] = defaultdict(float)
    for r in rows:
        if r.availability_head not in ("DEEMED", "OTHERS", "SYSTEM", "WEATHER", "CONSTRUCTION", "DIVERSION"):
            per_el[r.grid_element_id] += hours(r)
    return [{"element": db.get(GridElement, k).name, "outage_hours_counted": round(v, 2), "availability_pct": round((total_h - v) / total_h * 100, 3)}
            for k, v in per_el.items()]
