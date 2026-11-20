"""Protection & Tripping Studies (TS Cl. 11.4.6 p.179-191; FRD PT-01..20)."""
import io
import zipfile
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
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
from app.modules.auth_rbac.service import get_setting
from app.modules.dms_files.models import Document
from app.modules.dms_files.service import doc_out, store_upload
from app.modules.master_registry.models import Entity, GridElement
from app.modules.protection_tripping.models import EVENT_CATEGORIES, ProtectionPscRecord, RelaySetting, SoprSubmission, TrippingEvent
from app.modules.realtime_outage.models import TrippingReport
from app.utils.dt import to_utc_naive, utc_to_ist
from app.utils.exports import export
from app.utils.ids import simple_number

router = APIRouter(prefix="/api/v1/protection", tags=["protection"])
FILE_KINDS = {"DR_MAIN1": {".dat", ".cfg", ".pdf"}, "DR_MAIN2": {".dat", ".cfg", ".pdf"}, "DR_BACKUP": {".dat", ".cfg", ".pdf"},
              "EL": {".pdf", ".png", ".jpg", ".jpeg"}, "TR": {".pdf"}, "FLASH_REPORT": {".pdf", ".docx"}, "DETAILED_REPORT": {".pdf", ".docx"}}


def _coord(user) -> bool:
    return is_admin(user) or "PROTECTION_COORDINATOR" in role_codes(user)


def ends_for(db: Session, ev: TrippingEvent, entity_id: int | None) -> list[str]:
    """End-1 / End-2 ownership restriction (TS p.186, Fig.94)."""
    out = set()
    for eid in ev.element_ids_json:
        el = db.get(GridElement, eid)
        for o in el.owners:
            if o.entity_id == entity_id:
                if o.ownership_role == "END1_STATION":
                    out.add("END1")
                elif o.ownership_role == "END2_STATION":
                    out.add("END2")
                else:
                    out.add("END1")
    return sorted(out)


def status_for(db: Session, ev: TrippingEvent) -> dict:
    docs = db.scalars(select(Document).where(Document.owner_ref == f"pevent:{ev.id}", Document.is_latest)).all()
    two = any(db.get(GridElement, e).to_substation_id for e in ev.element_ids_json)
    sides = ["END1", "END2"] if two else ["END1"]
    st = {}
    for s in sides:
        have = {d.doc_category for d in docs if d.end_side == s}
        st[s] = {"FIR": bool(ev.fir_data_json.get(s)), "DR": bool(have & {"DR_MAIN1", "DR_MAIN2"}), "EL": "EL" in have, "TR": "TR" in have,
                 "FLASH": "FLASH_REPORT" in have, "DETAILED": "DETAILED_REPORT" in have}
    return st


def event_out(db: Session, ev: TrippingEvent, user=None, full=False) -> dict:
    els = [db.get(GridElement, e) for e in ev.element_ids_json]
    st = status_for(db, ev)
    now = utcnow()
    o = {"id": ev.id, "event_code": ev.event_code, "centre": db.get(Centre, ev.centre_id).code, "title": ev.title, "category": ev.event_category,
         "occurred_at": ev.occurred_at, "elements": [e.name for e in els], "loss_of_load_mw": ev.loss_of_load_mw, "loss_of_gen_mw": ev.loss_of_gen_mw,
         "submission": st, "flash_due_at": ev.flash_due_at, "dr_el_due_at": ev.dr_el_due_at, "detailed_due_at": ev.detailed_due_at,
         "overdue": {"flash": now > ev.flash_due_at and not all(v["FLASH"] for v in st.values()) if ev.flash_due_at else False,
                     "dr_el": now > ev.dr_el_due_at and not all(v["DR"] and v["EL"] for v in st.values()) if ev.dr_el_due_at else False,
                     "detailed": now > ev.detailed_due_at and not all(v["DETAILED"] for v in st.values()) if ev.detailed_due_at else False},
         "rldc_validation_status": ev.rldc_validation_status, "corrective_required": ev.corrective_required, "corrective_taken": ev.corrective_taken,
         "pending_files": sum(1 for v in st.values() for k, x in v.items() if not x)}
    if full:
        o.update({"fir": ev.fir_data_json, "fir_history": ev.fir_history_json, "my_ends": ends_for(db, ev, user.entity_id) if user else [],
                  "is_coordinator": _coord(user) if user else False,
                  "documents": [doc_out(d) for d in db.scalars(select(Document).where(Document.owner_ref == f"pevent:{ev.id}").order_by(Document.created_at.desc()))]})
    return o


def _get(db: Session, eid: int, user) -> TrippingEvent:
    ev = db.get(TrippingEvent, eid)
    if ev is None:
        raise HTTPException(404)
    if is_external(user) and not ends_for(db, ev, user.entity_id):
        raise HTTPException(403, "Event does not involve elements under your ownership")
    return ev


@router.get("/meta")
def meta(user=Depends(get_current_user)):
    return {"categories": EVENT_CATEGORIES, "file_kinds": list(FILE_KINDS), "is_coordinator": _coord(user)}


@router.get("/candidates")
def candidates(days: int = 30, centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Admin fetches outages/trippings from the OMS database by date to add to the protection dashboard (Table 11 row 9)."""
    since = utcnow() - timedelta(days=days)
    rows = db.scalars(select(TrippingReport).where(TrippingReport.tripped_at >= since).order_by(TrippingReport.tripped_at.desc())).all()
    used = {i for ev in db.scalars(select(TrippingEvent)) for i in ev.tripping_report_ids_json}
    return [{"id": r.id, "element": r.element.name, "tripped_at": r.tripped_at, "reason": r.reason, "relay_flags": r.relay_flags, "used": r.id in used} for r in rows]


class EventIn(BaseModel):
    tripping_report_ids: list[int]
    category: str
    title: str = ""
    loss_of_load_mw: float | None = None
    loss_of_gen_mw: float | None = None


@router.post("/events")
def create_event(body: EventIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Create Event Record from one or more outage/tripping records, categorised GI/GD/Near-miss (TS p.185)."""
    if not _coord(user):
        raise HTTPException(403, "Protection Coordinator only")
    if body.category not in EVENT_CATEGORIES:
        raise HTTPException(422, "Invalid category")
    trips = [db.get(TrippingReport, i) for i in body.tripping_report_ids]
    if not trips or any(t is None for t in trips):
        raise HTTPException(422, "Select tripping records")
    occurred = min(t.tripped_at for t in trips)
    flash_h = int(get_setting(db, "protection_flash_report_hours") or 8)
    drel_h = int(get_setting(db, "protection_dr_el_hours") or 24)
    det_d = int(get_setting(db, "protection_detailed_report_days") or 7)
    ev = TrippingEvent(event_code=simple_number(db, f"EV/{trips[0].element.centre.code}/{occurred:%Y}"), centre_id=trips[0].centre_id,
                       title=body.title or " + ".join(t.element.name for t in trips), event_category=body.category, occurred_at=occurred,
                       tripping_report_ids_json=[t.id for t in trips], element_ids_json=list({t.grid_element_id for t in trips}),
                       loss_of_load_mw=body.loss_of_load_mw, loss_of_gen_mw=body.loss_of_gen_mw, flash_due_at=occurred + timedelta(hours=flash_h),
                       dr_el_due_at=occurred + timedelta(hours=drel_h), detailed_due_at=occurred + timedelta(days=det_d), created_by=user.id,
                       fir_data_json={f"{s}": {"auto": {"element": t.element.name, "tripped_at": t.tripped_at.isoformat(), "relay": t.relay_flags}}
                                      for t in trips[:1] for s in ("AUTO",)})
    db.add(ev)
    db.flush()
    # notify bay owners of both ends once per utility (TS 11.4.6(b))
    ents = {o.entity_id for e in ev.element_ids_json for o in db.get(GridElement, e).owners}
    for ent in ents:
        notify_users(db, db.scalars(select(User).where(User.entity_id == ent)).all(),
                     f"Tripping event {ev.event_code}: upload FIR/DR/EL within {drel_h} h, flash report within {flash_h} h",
                     module="protection", step_code="EVENT_CREATED", link=f"/protection/{ev.id}", centre_id=ev.centre_id)
    audit(db, user, "protection", "EVENT_CREATED", "event", ev.event_code)
    db.commit()
    return event_out(db, ev, user)


@router.get("/events")
def list_events(centre: str | None = None, category: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.scalars(select(TrippingEvent).order_by(TrippingEvent.occurred_at.desc())).all()
    if is_external(user):
        rows = [r for r in rows if ends_for(db, r, user.entity_id)]
    elif centre and centre != "ALL":
        c = db.scalar(select(Centre).where(Centre.code == centre))
        rows = [r for r in rows if r.centre_id == c.id]
    elif not sees_all_centres(user):
        rows = [r for r in rows if r.centre_id == user.centre_id]
    if category:
        rows = [r for r in rows if r.event_category == category]
    return [event_out(db, r, user) for r in rows]


@router.get("/events/{eid}")
def get_event(eid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return event_out(db, _get(db, eid, user), user, full=True)


class FirIn(BaseModel):
    end: str = Field(pattern="^(END1|END2)$")
    data: dict


@router.put("/events/{eid}/fir")
def save_fir(eid: int, body: FirIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """FIR is fillable and editable by the user (only FIR), last-update timestamp, full trail (TS Table 11 rows 4, 6)."""
    ev = _get(db, eid, user)
    if not (_coord(user) or body.end in ends_for(db, ev, user.entity_id)):
        raise HTTPException(403, "You can fill FIR only for your end")
    fir = dict(ev.fir_data_json)
    if fir.get(body.end):
        ev.fir_history_json = [*ev.fir_history_json, {"end": body.end, "data": fir[body.end], "replaced_at": utcnow().isoformat(), "by": user.full_name}]
    fir[body.end] = {**body.data, "_updated_at": utcnow().isoformat(), "_by": user.full_name}
    ev.fir_data_json = fir
    db.commit()
    return event_out(db, ev, user, full=True)


@router.post("/events/{eid}/files")
def upload_file(eid: int, kind: str = Form(...), end: str = Form("END1"), file: UploadFile = File(...),
                db: Session = Depends(get_db), user=Depends(get_current_user)):
    ev = _get(db, eid, user)
    if kind not in FILE_KINDS:
        raise HTTPException(422, "Unknown file kind")
    coord = _coord(user)
    if not coord and end not in ends_for(db, ev, user.entity_id):
        raise HTTPException(403, "Upload only for your own control area / end")
    if not coord and kind in ("DR_MAIN1", "DR_MAIN2", "DR_BACKUP", "EL", "TR"):
        existing = db.scalar(select(Document).where(Document.owner_ref == f"pevent:{ev.id}", Document.doc_category == kind, Document.end_side == end))
        if existing:
            raise HTTPException(409, "DR/EL/TR cannot be edited or replaced by users; contact Protection admin")
    d = store_upload(db, file=file, module="protection", doc_category=kind, owner_ref=f"pevent:{ev.id}", centre_code=db.get(Centre, ev.centre_id).code,
                     user=user, end_side=end, allowed=FILE_KINDS[kind])
    db.commit()
    return event_out(db, ev, user, full=True) | {"uploaded": doc_out(d)}


@router.delete("/events/{eid}/files/{doc_id}")
def admin_delete(eid: int, doc_id: int, remarks: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Only admin can delete FIR/DR/EL/TR, with remarks; uploader notified (Table 11 row 6)."""
    if not _coord(user):
        raise HTTPException(403)
    d = db.get(Document, doc_id)
    d.is_latest = False
    d.doc_category = f"DELETED_{d.doc_category}"
    if d.uploaded_by:
        notify_users(db, [db.get(User, d.uploaded_by)], f"{d.auto_filename} deleted by Protection admin: {remarks}", module="protection")
    audit(db, user, "protection", "FILE_DELETED", "document", doc_id, new={"remarks": remarks})
    db.commit()
    return {"ok": True}


@router.post("/events/{eid}/validate")
def validate(eid: int, ok: bool = Form(...), remarks: str = Form(""), corrective_required: str = Form(""),
             db: Session = Depends(get_db), user=Depends(get_current_user)):
    ev = _get(db, eid, user)
    if not _coord(user):
        raise HTTPException(403)
    ev.rldc_validation_status = "VALIDATED" if ok else "REUPLOAD_REQUESTED"
    ev.corrective_required = corrective_required or ev.corrective_required
    if not ok:
        ents = {o.entity_id for e in ev.element_ids_json for o in db.get(GridElement, e).owners}
        notify_users(db, [u for e in ents for u in db.scalars(select(User).where(User.entity_id == e))], f"{ev.event_code}: please re-upload reports - {remarks}", module="protection")
    db.commit()
    return event_out(db, ev, user)


@router.put("/events/{eid}/corrective-taken")
def corrective_taken(eid: int, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ev = _get(db, eid, user)
    ev.corrective_taken = body.get("text", "")
    db.commit()
    return event_out(db, ev, user)


@router.get("/events/{eid}/bulk-download")
def bulk_download(eid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Download multiple DR/EL/FIR files in one click (TS 11.4.6(e))."""
    ev = _get(db, eid, user)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for d in db.scalars(select(Document).where(Document.owner_ref == f"pevent:{ev.id}", Document.is_latest)):
            try:
                z.write(d.storage_path, d.auto_filename)
            except OSError:
                pass
        z.writestr("FIR.json", __import__("json").dumps(ev.fir_data_json, indent=2, default=str))
    return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{ev.event_code.replace("/", "-")}.zip"'})


# ------------------------------------------------------------------ PSC
class PscIn(BaseModel):
    tripping_event_id: int
    details: str = ""
    psc_meeting_no: str = ""
    recommendations: str = ""


def psc_out(db: Session, p: ProtectionPscRecord) -> dict:
    ev = db.get(TrippingEvent, p.tripping_event_id)
    return {"id": p.id, "psc_record_code": p.psc_record_code, "event_code": ev.event_code, "category": ev.event_category, "event": ev.title,
            "event_date": ev.occurred_at, "details": p.details, "psc_meeting_no": p.psc_meeting_no, "meeting_date": p.meeting_date,
            "recommendations": p.recommendations, "utility_action_taken": p.utility_action_taken, "compliance_status": p.compliance_status,
            "resolved_by_rldc": p.resolved_by_rldc, "mom_doc_id": p.mom_doc_id}


@router.get("/psc")
def list_psc(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [psc_out(db, p) for p in db.scalars(select(ProtectionPscRecord).order_by(ProtectionPscRecord.id.desc()))]


@router.post("/psc")
def add_psc(body: PscIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not _coord(user):
        raise HTTPException(403)
    ev = db.get(TrippingEvent, body.tripping_event_id)
    p = ProtectionPscRecord(psc_record_code=simple_number(db, "PSC"), centre_id=ev.centre_id, tripping_event_id=ev.id, details=body.details,
                            psc_meeting_no=body.psc_meeting_no, recommendations=body.recommendations, meeting_date=utcnow())
    db.add(p)
    db.commit()
    return psc_out(db, p)


@router.patch("/psc/{pid}")
def update_psc(pid: int, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    p = db.get(ProtectionPscRecord, pid)
    allowed = ("utility_action_taken",) if is_external(user) else ("details", "psc_meeting_no", "recommendations", "utility_action_taken",
                                                                     "compliance_status", "resolved_by_rldc")
    for k in allowed:
        if k in body:
            setattr(p, k, body[k])
    db.commit()
    return psc_out(db, p)


# ------------------------------------------------------------------ SOPR, relay settings
class SoprIn(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    dependability: float = Field(ge=0, le=1)
    security: float = Field(ge=0, le=1)
    reliability: float = Field(ge=0, le=1)
    comments: str = ""


@router.post("/sopr")
def submit_sopr(body: SoprIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not user.entity_id:
        raise HTTPException(422, "Utility login required")
    s = SoprSubmission(entity_id=user.entity_id, month=body.month, dependability=body.dependability, security=body.security,
                       reliability=body.reliability, comments=body.comments, submitted_by=user.id, submitted_at=utcnow())
    db.add(s)
    db.commit()
    return {"id": s.id}


@router.get("/sopr")
def sopr_status(month: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Utility-wise SOPR submission status for utilities with non-zero trippings (TS 11.4.6(d))."""
    y, m = map(int, month.split("-"))
    trip_owners = Counter()
    for t in db.scalars(select(TrippingReport)):
        if t.tripped_at.year == y and t.tripped_at.month == m:
            for o in t.element.owners:
                trip_owners[o.entity_id] += 1
    subs = {s.entity_id: s for s in db.scalars(select(SoprSubmission).where(SoprSubmission.month == month))}
    return [{"entity": db.get(Entity, e).name, "trippings": n, "submitted": e in subs,
             "D": subs[e].dependability if e in subs else None, "S": subs[e].security if e in subs else None, "R": subs[e].reliability if e in subs else None}
            for e, n in trip_owners.items()]


@scheduler.register("sopr_reminder")
def sopr_reminder(db: Session) -> None:
    now = utc_to_ist(utcnow())
    if now.day != 10 or now.hour != 10 or now.minute > 1:
        return
    y, m = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
    for row in sopr_status(f"{y}-{m:02d}", db=db, user=None):
        pass


@router.post("/relay-settings")
def relay_upload(grid_element_id: int = Form(...), relay_slot: str = Form(...), file: UploadFile = File(...),
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    d = store_upload(db, file=file, module="protection", doc_category=f"RELAY_{relay_slot}", owner_ref=f"relay:{grid_element_id}", user=user)
    db.add(RelaySetting(grid_element_id=grid_element_id, relay_slot=relay_slot, doc_id=d.id, version_no=d.version_no, uploaded_at=utcnow()))
    db.commit()
    return doc_out(d)


@router.get("/relay-settings")
def relay_list(grid_element_id: int | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(RelaySetting).order_by(RelaySetting.uploaded_at.desc())
    if grid_element_id:
        stmt = stmt.where(RelaySetting.grid_element_id == grid_element_id)
    return [{"id": r.id, "element": db.get(GridElement, r.grid_element_id).name, "slot": r.relay_slot, "version": r.version_no,
             "doc_id": r.doc_id, "uploaded_at": r.uploaded_at} for r in db.scalars(stmt)]


@router.get("/reports/{kind}")
def reports(kind: str, fmt: str = "json", db: Session = Depends(get_db), user=Depends(get_current_user)):
    events = list_events(db=db, user=user)
    if kind == "submission":
        rows = [{"event": e["event_code"], "category": e["category"], "end": s, **{k: "Y" if v else "N" for k, v in st.items()}}
                for e in events for s, st in e["submission"].items()]
        cols = [("event", "Event", "घटना"), ("category", "Category", "श्रेणी"), ("end", "End", "छोर"), ("FIR", "FIR", "एफआईआर"),
                ("DR", "DR", "डीआर"), ("EL", "EL", "ईएल"), ("TR", "TR", "टीआर"), ("FLASH", "Flash", "फ्लैश"), ("DETAILED", "Detailed", "विस्तृत")]
        title = ("DR/EL submission status", "डीआर/ईएल प्रस्तुति स्थिति")
    elif kind == "gdgi":
        c = Counter(e["category"] for e in events)
        rows = [{"category": k, "count": v} for k, v in sorted(c.items())]
        cols = [("category", "Category", "श्रेणी"), ("count", "Events", "घटनाएं")]
        title = ("GD/GI summary", "जीडी/जीआई सारांश")
    elif kind == "frequent":
        c = Counter(t.element.name for t in db.scalars(select(TrippingReport)))
        rows = [{"element": k, "trippings": v} for k, v in c.most_common()]
        cols = [("element", "Element", "तत्व"), ("trippings", "Trippings", "ट्रिपिंग")]
        title = ("Frequent tripping elements", "बार-बार ट्रिप होने वाले तत्व")
    else:
        raise HTTPException(404)
    if fmt == "json":
        return {"title": title[0], "columns": cols, "rows": rows}
    return export(fmt, title[0], title[1], cols, rows, f"protection_{kind}")


_ = to_utc_naive
