"""First Time Charging Module (TS Cl. 11.4.2 p.98-119; FRD FTC-01..48)."""
from collections import Counter
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.rbac import get_current_user, is_admin, is_external, role_codes, sees_all_centres
from app.db.base import utcnow
from app.db.session import get_db
from app.integrations.notifier import notify_users
from app.modules.auth_rbac.models import Centre, Role, User, UserRole
from app.modules.auth_rbac.service import get_setting
from app.modules.dms_files.models import Document
from app.modules.dms_files.service import doc_out, list_docs, store_upload
from app.modules.ftc.models import FtcApplication, FtcIssueLog, PostCommCompliance, StartupPowerRequest
from app.modules.master_registry.models import ELEMENT_TYPES, Entity, GridElement, Substation
from app.modules.master_registry.router import ElementIn, create_element
from app.modules.workflow_engine import service as wf
from app.modules.workflow_engine.models import WorkflowCase
from app.utils.certificates import render_pdf
from app.utils.exports import export

router = APIRouter(prefix="/api/v1/ftc", tags=["ftc"])

THREE = ["SCADA", "PROTECTION", "METERING"]
CHAIN = [[(d, "GENERAL") for d in THREE], [(d, "HOD") for d in THREE], [("SUB_HEAD_SO", "GENERAL")], [("HEAD_SO", "GENERAL")], [("HEAD_RLDC", "GENERAL")]]
STAGES = {
    1: {"name": "Stage 1 - Intimation (A-annexures)", "name_hi": "चरण 1 - सूचना (ए-अनुलग्नक)",
        "annexures": ["A1", "A2", "A3", "A4", "A5", "A6", "STANDING_MEETING", "OTHER"], "required": ["A1", "A2", "A3", "A4", "A5", "A6"],
        "checklist": "FTC_A_COORD", "output": "FORMAT_II"},
    2: {"name": "Stage 2 - Request & trial-run notice (B-annexures)", "name_hi": "चरण 2 - अनुरोध एवं ट्रायल-रन सूचना",
        "annexures": ["B1", "B2", "B3", "B4", "B5", "B5A", "ELEC_INSPECTOR", "PTCC", "CHARGING_INSTRUCTION", "DR", "EL", "RELAY_SETTING",
                      "MODEL_DATA", "DUMMY_METER", "TIME_DRIFT", "OPGW_OTDR", "FOTE_SAT", "INTERPATCH", "B6", "B7", "B8", "OTHER"],
        "required": ["B1", "B2", "B3", "B4", "B5", "B5A", "ELEC_INSPECTOR"], "checklist": "FTC_B_COORD", "output": "FORMAT_IV"},
    3: {"name": "Stage 3 - Trial-run completion (C-annexures)", "name_hi": "चरण 3 - ट्रायल-रन पूर्णता (सी-अनुलग्नक)",
        "annexures": ["C1", "C2", "C3", "C4", "DECLARATION", "TEST_DOCS", "CORROBORATION", "INTIMATION", "RATED_CAPACITY_SCADA",
                      "RATED_CAPACITY_SEM", "REACTIVE_TEST", "FREQ_RESPONSE", "LVRT_HVRT", "OTHER"],
        "required": ["C1", "C2", "C3", "C4", "DECLARATION"], "checklist": "FTC_C_COORD", "output": "STAGE4"},
    4: {"name": "Stage 4 - Certificate of successful trial run", "name_hi": "चरण 4 - सफल ट्रायल रन प्रमाणपत्र",
        "annexures": ["OTHER"], "required": [], "checklist": None, "output": "CERTIFICATE"},
    5: {"name": "Stage 5 - DOCO letter", "name_hi": "चरण 5 - डीओसीओ पत्र", "annexures": ["DOCO"], "required": ["DOCO"], "checklist": None,
        "output": "CLOSE"},
}
ANNEXURE_LABELS = {
    "A1": "Intimation of expected first time energisation + document list", "A2": "List of elements to be charged and details",
    "A3": "SLD with dia/bus/breaker completion status", "A4": "List of SCADA points to RLDC", "A5": "Type & location of energy meters",
    "A6": "Connection agreement & site responsibility schedule", "STANDING_MEETING": "Standing meeting approval",
    "B1": "Request for energisation + notice for trial run", "B2": "Protection undertaking (Format III A)",
    "B3": "Telemetry & communication undertaking (Format III B)", "B4": "Energy metering undertaking (Format III C)",
    "B5": "Statutory clearances undertaking (Format III D)", "B5A": "Cyber security undertaking", "ELEC_INSPECTOR": "Electrical Inspector safety clearance",
    "PTCC": "PTCC route approval (lines only)", "CHARGING_INSTRUCTION": "Charging instruction (lines only)", "DR": "Disturbance recorder",
    "EL": "Event logger", "RELAY_SETTING": "Relay settings", "MODEL_DATA": "Model data (generating units)", "DUMMY_METER": "Dummy meter reading",
    "TIME_DRIFT": "SEM time drift report", "OPGW_OTDR": "OTDR report of OPGW", "FOTE_SAT": "SAT report of FOTE", "INTERPATCH": "Inter-patching report",
    "B6": "B6 undertaking: bay/line alteration", "B7": "B7 undertaking: line diversion/ERS", "B8": "B8 undertaking: anti-theft charging",
    "C1": "Completion of trial run & certificate request (Format V)", "C2": "SCADA P/Q/V during trial run", "C3": "Interface energy meter readings",
    "C4": "DR/EL outputs during trial run", "DECLARATION": "Declaration by generating company/licensee", "TEST_DOCS": "Test documents",
    "CORROBORATION": "Trial-run corroboration sheet (Solar ICR/Block only)", "INTIMATION": "Intimation letter", "RATED_CAPACITY_SCADA": "Rated capacity - SCADA data",
    "RATED_CAPACITY_SEM": "Rated capacity - SEM data", "REACTIVE_TEST": "Reactive power capability test", "FREQ_RESPONSE": "Frequency response test",
    "LVRT_HVRT": "LVRT / HVRT test", "DOCO": "Date of Commercial Operation (DOCO) letter", "OTHER": "Any other supporting document",
}
LINE_TYPES = {"AC_LINE", "HVDC_LINE"}
HVDC_TYPES = {"HVDC_POLE", "HVDC_LINE"}


def _coord(user, centre_id: int | None = None) -> bool:
    if is_admin(user):
        return True
    codes = role_codes(user)
    return "FTC_COORDINATOR" in codes and (centre_id is None or sees_all_centres(user) or user.centre_id == centre_id)


def _get(db: Session, fid: int, user) -> tuple[FtcApplication, WorkflowCase]:
    f = db.get(FtcApplication, fid)
    if f is None:
        raise HTTPException(404, "FTC case not found")
    case = db.get(WorkflowCase, f.case_id)
    if is_external(user) and case.applicant_user_id != user.id and (not user.entity_id or f.entity_id != user.entity_id):
        raise HTTPException(403, "Not your case")
    return f, case


def jurisdiction(elements: list[dict]) -> tuple[str, str]:
    """IEGC 2023 routing (TS p.98-100): NLDC for 765 kV, inter-regional, HVDC, trans-national; RLDC otherwise."""
    code, cert = "RLDC", "RLDC"
    for e in elements:
        kv = float(e.get("voltage_kv") or 0)
        ir, tn = bool(e.get("is_inter_regional")), bool(e.get("is_trans_national"))
        if kv >= 765 or ir or tn or e.get("element_type") in HVDC_TYPES:
            code = "NLDC"
        if ir or tn or (e.get("element_type") in HVDC_TYPES and ir):
            cert = "NLDC"
    return code, cert


def working_days_between(d0: date, d1: date) -> int:
    n, d = 0, d0
    while d < d1:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return n


def ftc_out(db: Session, f: FtcApplication, case: WorkflowCase, user, full: bool = False) -> dict:
    ent = db.get(Entity, f.entity_id)
    out = {**wf.case_out(case), "ftc_id": f.id, "entity": ent.name, "entity_id": ent.id, "jurisdiction": f.jurisdiction,
           "cert_jurisdiction": f.cert_jurisdiction, "element_category": f.element_category, "stage": f.stage,
           "stage_name": STAGES[f.stage]["name"], "stage_status": f.stage_status, "proposed_charging_date": f.proposed_charging_date,
           "is_modified_element": f.is_modified_element, "elements_count": len(f.a2_elements_json),
           "format_tr_date": f.format_tr_date, "format_tr_status": f.format_tr_status, "realtime_access_granted": f.realtime_access_granted,
           "realtime_charging_time": f.realtime_charging_time, "trial_cert_signed": f.trial_cert_signed, "doco_status": f.doco_status,
           "doco_date": f.doco_date}
    if full:
        requester = is_external(user)
        rows = wf.consents(db, case, f"STAGE{f.stage}")
        all_rows = []
        for s in range(1, 6):
            all_rows += wf.consents(db, case, f"STAGE{s}")
        created = [db.get(GridElement, i) for i in f.created_element_ids_json]
        out.update({
            "annexures": f.annexures_data_json, "a2_elements": f.a2_elements_json,
            "created_elements": [{"id": g.id, "unique_element_id": g.unique_element_id, "name": g.name, "status": g.status,
                                  "realtime_enabled": g.realtime_enabled} for g in created if g],
            "documents": list_docs(db, f"case:{case.id}", applicant_view=requester),
            "consents": [] if requester else [wf.consent_out(r, user, case, rows) for r in rows],
            "consent_history": [] if requester else [wf.consent_out(r) for r in all_rows],
            "tracker": wf.tracker(db, case, applicant_view=requester),
            "stages": [{"no": k, "name": v["name"], "name_hi": v["name_hi"], "annexures": [{"code": a, "label": ANNEXURE_LABELS.get(a, a),
                                                                                          "required": a in v["required"]} for a in v["annexures"]],
                        "checklist": v["checklist"]} for k, v in STAGES.items()],
            "pre_certificate": f.pre_certificate_json, "compliances": [_comp_out(c) for c in f.compliances],
            "issues": [{"by": i.author_name, "direction": i.direction, "message": i.message, "at": i.created_at}
                       for i in db.scalars(select(FtcIssueLog).where(FtcIssueLog.ftc_application_id == f.id).order_by(FtcIssueLog.id))],
            "is_coordinator": _coord(user, case.centre_id), "is_requester": requester,
            "can_sign": "HEAD_RLDC" in role_codes(user) or is_admin(user),
        })
    return out


def _comp_out(c: PostCommCompliance) -> dict:
    days = (c.due_date - utcnow().date()).days
    return {"id": c.id, "ftc_application_id": c.ftc_application_id, "compliance_type": c.compliance_type, "description": c.description,
            "due_date": c.due_date, "status": c.status, "signed_by": c.signed_by, "doc_id": c.doc_id, "remarks": c.remarks,
            "days_left": days, "timeline": "EXPIRED" if days < 0 and c.status != "ACCEPTED" else "EXPIRING_SOON" if days <= 30 and c.status != "ACCEPTED" else "OK"}


@router.get("/meta")
def meta(user=Depends(get_current_user)):
    return {"stages": {k: {"name": v["name"], "annexures": v["annexures"], "required": v["required"]} for k, v in STAGES.items()},
            "labels": ANNEXURE_LABELS, "element_types": [{"code": k, "label": v[1]} for k, v in ELEMENT_TYPES.items()],
            "categories": ["RE_PLANT", "NON_RE_PLANT", "TRANSMISSION"]}


@router.get("/cases")
def list_cases(stage: int | None = None, centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(FtcApplication).join(WorkflowCase, FtcApplication.case_id == WorkflowCase.id).order_by(WorkflowCase.created_at.desc())
    if is_external(user):
        stmt = stmt.where(or_(WorkflowCase.applicant_user_id == user.id, FtcApplication.entity_id == (user.entity_id or -1)))
    elif not sees_all_centres(user):
        stmt = stmt.where(or_(WorkflowCase.centre_id == user.centre_id, FtcApplication.jurisdiction == "NLDC"))
    if stage:
        stmt = stmt.where(FtcApplication.stage == stage)
    if centre and centre != "ALL":
        stmt = stmt.join(Centre, WorkflowCase.centre_id == Centre.id).where(Centre.code == centre)
    return [ftc_out(db, f, db.get(WorkflowCase, f.case_id), user) for f in db.scalars(stmt)]


@router.get("/cases/{fid}")
def get_case(fid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    f, case = _get(db, fid, user)
    return ftc_out(db, f, case, user, full=True)


class NewFtcIn(BaseModel):
    element_category: str = Field(pattern="^(RE_PLANT|NON_RE_PLANT|TRANSMISSION)$")
    proposed_charging_date: date
    is_modified_element: bool = False
    entity_id: int | None = None
    centre_code: str | None = None
    title: str = ""


@router.post("/cases")
def create_case(body: NewFtcIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ent_id = body.entity_id or user.entity_id
    if ent_id is None:
        raise HTTPException(422, "Applicant entity required (register first in the Registration Module)")
    ent = db.get(Entity, ent_id)
    if is_external(user) and ent.id != user.entity_id:
        raise HTTPException(403)
    centre = db.scalar(select(Centre).where(Centre.code == (body.centre_code or (db.get(Centre, ent.centre_id).code if ent.centre_id else "NRLDC"))))
    case = wf.new_case(db, "FTC", centre, user, body.title or f"FTC: {ent.name}", applicant_entity_id=ent.id)
    f = FtcApplication(case_id=case.id, entity_id=ent.id, jurisdiction="RLDC", element_category=body.element_category,
                       proposed_charging_date=body.proposed_charging_date, is_modified_element=body.is_modified_element)
    db.add(f)
    wf.set_pending(case, "APPLICANT", stage="STAGE1_DRAFT")
    audit(db, user, "ftc", "FTC_CASE_CREATED", "case", case.case_number)
    db.commit()
    return ftc_out(db, f, case, user)


@router.put("/cases/{fid}/annexure/{code}")
def save_annexure(fid: int, code: str, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Online fillable annexures; A2 drives Element ID generation (TS p.104-105)."""
    f, case = _get(db, fid, user)
    if case.is_locked:
        raise HTTPException(409, "Application locked after submission")
    if code == "A2":
        elements = body.get("elements", [])
        for i, e in enumerate(elements):
            if e.get("element_type") not in ELEMENT_TYPES:
                raise HTTPException(422, f"Row {i + 1}: invalid element type")
            if not (0 < float(e.get("voltage_kv") or 0) <= 1200):
                raise HTTPException(422, f"Row {i + 1}: voltage must be between 0 and 1200 kV")
            if not e.get("name"):
                raise HTTPException(422, f"Row {i + 1}: element name required")
        f.a2_elements_json = elements
        f.jurisdiction, f.cert_jurisdiction = jurisdiction(elements)
    else:
        f.annexures_data_json = {**f.annexures_data_json, code: body}
    db.commit()
    return {"ok": True, "jurisdiction": f.jurisdiction, "cert_jurisdiction": f.cert_jurisdiction}


class DuplicateIn(BaseModel):
    index: int
    count: int = Field(1, ge=1, le=200)


@router.post("/cases/{fid}/a2/duplicate")
def duplicate_element(fid: int, body: DuplicateIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Duplicate-element helper for identical blocks (e.g. Solar ICR) (TS p.105-106)."""
    f, case = _get(db, fid, user)
    if case.is_locked:
        raise HTTPException(409)
    base = f.a2_elements_json[body.index]
    copies = [{**base, "name": f"{base['name']} (copy {i + 1})"} for i in range(body.count)]
    f.a2_elements_json = [*f.a2_elements_json, *copies]
    db.commit()
    return {"elements": f.a2_elements_json}


@router.post("/cases/{fid}/documents")
def upload(fid: int, doc_category: str = Form(...), change_note: str = Form(""), file: UploadFile = File(...),
           db: Session = Depends(get_db), user=Depends(get_current_user)):
    f, case = _get(db, fid, user)
    requester = is_external(user)
    if requester and case.is_locked and doc_category not in ("FORMAT_TR", "DOCO"):
        raise HTTPException(409, "Application locked; documents can be revised only after it is returned")
    if doc_category in ("PTCC", "CHARGING_INSTRUCTION") and not any(e.get("element_type") in LINE_TYPES for e in f.a2_elements_json):
        raise HTTPException(422, "PTCC / charging instruction apply to AC or HVDC transmission lines only")
    if doc_category == "CORROBORATION" and not any(e.get("element_type") == "SOLAR_ICR_BLOCK" for e in f.a2_elements_json):
        raise HTTPException(422, "Corroboration sheet applies to Solar ICR/Block elements only")
    hidden = not requester and doc_category.startswith("RLDC_")
    d = store_upload(db, file=file, module="ftc", doc_category=doc_category, owner_ref=f"case:{case.id}", centre_code=case.centre.code,
                     case_id=case.id, user=user, change_note=change_note, visible_to_applicant=not hidden)
    if doc_category == "DOCO":
        f.doco_doc_id, f.doco_status = d.id, "SUBMITTED"
        wf.add_step(db, case, "DOCO letter uploaded", user, "SUBMIT")
        wf.set_pending(case, "FTC_COORDINATOR", stage="STAGE5_REVIEW")
    db.commit()
    return doc_out(d)


@router.post("/cases/{fid}/generate/{code}")
def generate_annexure_pdf(fid: int, code: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Portal generates the annexure PDF in the defined format from the filled data, for the user to sign & upload."""
    f, case = _get(db, fid, user)
    ent = db.get(Entity, f.entity_id)
    if code == "A2":
        fields = [(f"{i + 1}. {e['name']}", f"{e.get('element_type')} · {e.get('voltage_kv')} kV · {e.get('rating', '')}") for i, e in enumerate(f.a2_elements_json)]
    else:
        fields = [(k, v) for k, v in (f.annexures_data_json.get(code) or {}).items()]
    pdf = render_pdf(f"Annexure {code}: {ANNEXURE_LABELS.get(code, code)}", f"अनुलग्नक {code}", case.case_number,
                     [("Applicant", ent.name), ("FTC Case ID", case.case_number), *fields], draft=True)
    d = store_upload(db, data=pdf, filename=f"{code}.pdf", module="ftc", doc_category=f"{code}_GENERATED", owner_ref=f"case:{case.id}",
                     centre_code=case.centre.code, case_id=case.id, user=user)
    db.commit()
    return doc_out(d)


@router.post("/cases/{fid}/submit")
def submit(fid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    f, case = _get(db, fid, user)
    if case.is_locked:
        raise HTTPException(409, "Already submitted")
    st = STAGES[f.stage]
    have = {d["doc_category"] for d in list_docs(db, f"case:{case.id}")}
    req = list(st["required"])
    if f.stage == 2 and any(e.get("element_type") in LINE_TYPES for e in f.a2_elements_json):
        req.append("PTCC")
    if f.stage == 1:
        if not f.a2_elements_json:
            raise HTTPException(422, "Annexure A2 must list at least one element")
        have.add("A2")
        min_days = int(get_setting(db, "ftc_min_days_before_charging") or 10)
        if f.proposed_charging_date and (f.proposed_charging_date - utcnow().date()).days < min_days:
            raise HTTPException(422, f"A-annexures must be uploaded at least {min_days} days before the charging date (TS p.106)")
    if f.stage == 2 and f.format_tr_status not in ("SUBMITTED", "APPROVED"):
        raise HTTPException(422, "Submit the trial-run notice (Format TR) first")
    missing = [a for a in req if a not in have]
    if missing:
        raise HTTPException(422, "Upload signed annexures: " + ", ".join(missing))
    case.is_locked, case.status, f.stage_status = True, "SUBMITTED", "SUBMITTED"
    wf.add_step(db, case, f"{st['name']} submitted", user, "SUBMIT", forwarded_to="FTC Coordinator")
    wf.set_pending(case, "FTC_COORDINATOR", stage=f"STAGE{f.stage}_COORD_CHECK")
    notify_users(db, wf.users_for(db, case.centre_id, {"FTC_COORDINATOR"}), f"{case.case_number}: {st['name']} submitted",
                 module="ftc", step_code="CASE_FORWARDED", link=f"/ftc/{f.id}", centre_id=case.centre_id)
    db.commit()
    return ftc_out(db, f, case, user, full=True)


class CoordIn(BaseModel):
    action: str = Field(pattern="^(FORWARD|RETURN|ACCEPT)$")
    remarks: str = ""
    checklist: dict = {}
    include_nldc: bool = False


def _groups(f: FtcApplication, include_nldc: bool) -> list[list[tuple[str, str]]]:
    nldc = [("NLDC", "GENERAL")] if (include_nldc or f.jurisdiction == "NLDC") else []
    if f.stage == 1:
        return [[(d, "GENERAL") for d in THREE] + nldc]
    if f.stage == 2:
        return [[(d, "GENERAL") for d in THREE] + nldc, [(d, "HOD") for d in THREE]]
    return [list(g) for g in CHAIN]


@router.post("/cases/{fid}/coordinator")
def coordinator(fid: int, body: CoordIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    f, case = _get(db, fid, user)
    if not _coord(user, case.centre_id):
        raise HTTPException(403, "FTC Coordinator only")
    stage_key = f"STAGE{f.stage}"
    st = STAGES[f.stage]
    if body.action == "RETURN":
        if not body.remarks.strip():
            raise HTTPException(422, "Remarks required when returning")
        case.is_locked, case.status, f.stage_status = False, "RETURNED", "RETURNED"
        wf.add_step(db, case, f"{st['name']} returned to applicant", user, "RETURN", body.remarks)
        wf.set_pending(case, "APPLICANT", stage=f"STAGE{f.stage}_RETURNED")
        notify_users(db, [db.get(User, case.applicant_user_id)], f"{case.case_number} returned with observations", body=body.remarks,
                     module="ftc", step_code="CASE_RETURNED", link=f"/ftc/{f.id}")
    elif body.action == "FORWARD":
        if f.stage == 4 and not f.pre_certificate_json:
            raise HTTPException(422, "Fill the pre-certificate before forwarding")
        if st["checklist"]:
            res = wf.validate_checklist(db, case, st["checklist"], body.checklist, user, stage_key)
            if res["pending_items"]:
                wf.add_step(db, case, "Checklist items marked pending", user, "COMMENT", "; ".join(res["pending_items"]), internal=True)
        wf.open_consents(db, case, stage_key, _groups(f, body.include_nldc))
        case.status, f.stage_status = "UNDER_REVIEW", "DEPT_REVIEW"
        first = [d for d, _ in _groups(f, body.include_nldc)[0]]
        wf.add_step(db, case, f"Forwarded for departmental consent ({', '.join(first)})", user, "FORWARD", body.remarks, forwarded_to=", ".join(first))
        wf.set_pending(case, ",".join(first), stage=f"{stage_key}_CONSENT")
        for d in first:
            notify_users(db, wf.users_for(db, case.centre_id, {"DEPT_USER", "NLDC_USER"} if d == "NLDC" else {"DEPT_USER"}, None if d == "NLDC" else d),
                         f"{case.case_number}: consent requested ({st['name']})", module="ftc", step_code="CASE_FORWARDED",
                         link=f"/ftc/{f.id}", centre_id=case.centre_id)
    else:  # ACCEPT
        if wf.stage_consent_state(db, case, stage_key) != "ALL_ACCEPTED":
            raise HTTPException(409, "Coordinator can accept only after consents from all departments (TS p.107)")
        _accept_stage(db, f, case, user, body.remarks)
    audit(db, user, "ftc", f"COORDINATOR_{body.action}", "case", case.case_number, new={"stage": f.stage, "remarks": body.remarks})
    db.commit()
    return ftc_out(db, f, case, user, full=True)


def _grant_realtime(db: Session, f: FtcApplication, case: WorkflowCase) -> None:
    role = db.scalar(select(Role).where(Role.code == "EXT_REALTIME"))
    for u in db.scalars(select(User).where(or_(User.id == case.applicant_user_id, User.entity_id == f.entity_id))).all():
        if not any(ur.role.code == "EXT_REALTIME" for ur in u.roles):
            db.add(UserRole(user_id=u.id, role_id=role.id, centre_id=case.centre_id))
    f.realtime_access_granted = True


def _accept_stage(db: Session, f: FtcApplication, case: WorkflowCase, user, remarks: str) -> None:
    ent = db.get(Entity, f.entity_id)
    st = STAGES[f.stage]
    if f.stage == 1:
        created = []
        for e in f.a2_elements_json:
            owners = [{"entity_id": ent.id, "role": "ASSET_OWNER" if e.get("element_type") not in LINE_TYPES else "LINE_OWNER"}]
            g = create_element(db, ElementIn(name=e["name"], element_type=e["element_type"], centre_code=case.centre.code,
                                             voltage_kv=float(e["voltage_kv"]), from_substation_id=e.get("from_substation_id") or None,
                                             to_substation_id=e.get("to_substation_id") or None, is_inter_regional=bool(e.get("is_inter_regional")),
                                             rating=str(e.get("rating", "")), length_km=e.get("length_km") or None, status="PRE_COMMISSIONING",
                                             metadata={"ftc_case": case.case_number}, owners=owners), user, ftc_case_id=f.id)
            created.append(g.id)
        f.created_element_ids_json = created
        ids = ", ".join(db.get(GridElement, i).unique_element_id for i in created)
        pdf = render_pdf("Format II - Acknowledgement & approval of A-annexures", "फॉर्मेट II - ए-अनुलग्नक की पावती एवं अनुमोदन", case.case_number,
                         [("Applicant", ent.name), ("Jurisdiction", f.jurisdiction), ("Proposed charging date", f.proposed_charging_date),
                          ("Unique Element IDs created", ids)], signer=user, signer_role="FTC Coordinator")
        d = store_upload(db, data=pdf, filename="Format_II.pdf", module="ftc", doc_category="FORMAT_II", owner_ref=f"case:{case.id}",
                         centre_code=case.centre.code, case_id=case.id, user=user)
        f.format_ii_doc_id = d.id
        _advance(db, f, case, user, 2, f"Stage 1 accepted; Format II issued; {len(created)} element ID(s) created in master DB", remarks)
    elif f.stage == 2:
        pdf = render_pdf("Format IV - Provisional approval for first time energisation & trial run",
                         "फॉर्मेट IV - प्रथम ऊर्जीकरण एवं ट्रायल रन हेतु अनंतिम अनुमोदन", case.case_number,
                         [("Applicant", ent.name), ("Trial-run date (Format TR)", f.format_tr_date), ("Quantum (MW)", f.format_tr_quantum_mw),
                          ("Elements", ", ".join(db.get(GridElement, i).unique_element_id for i in f.created_element_ids_json))],
                         signer=user, signer_role="FTC Coordinator")
        d = store_upload(db, data=pdf, filename="Format_IV.pdf", module="ftc", doc_category="FORMAT_IV", owner_ref=f"case:{case.id}",
                         centre_code=case.centre.code, case_id=case.id, user=user)
        f.format_iv_doc_id = d.id
        for gid in f.created_element_ids_json:
            db.get(GridElement, gid).realtime_enabled = True
        _grant_realtime(db, f, case)
        _advance(db, f, case, user, 3, "Stage 2 accepted; Format IV issued; Real-time Outage access granted; elements enabled for charging code", remarks)
    elif f.stage == 3:
        _advance(db, f, case, user, 4, "Stage 3 accepted (all departments and Head of RLDC)", remarks)
    elif f.stage == 4:
        pdf = render_pdf("Certificate of successful trial run", "सफल ट्रायल रन का प्रमाणपत्र", case.case_number,
                         [("Applicant", ent.name), *[(k, v) for k, v in f.pre_certificate_json.items()],
                          ("Elements", ", ".join(db.get(GridElement, i).unique_element_id for i in f.created_element_ids_json))],
                         draft=True)
        d = store_upload(db, data=pdf, filename="Trial_Run_Certificate.pdf", module="ftc", doc_category="TRIAL_CERTIFICATE",
                         owner_ref=f"case:{case.id}", centre_code=case.centre.code, case_id=case.id, user=user, visible_to_applicant=False)
        f.trial_cert_doc_id = d.id
        f.stage_status = "AWAITING_SIGNATURE"
        wf.add_step(db, case, "Certificate auto-generated (not visible to user) - awaiting Head of RLDC signature", user, "APPROVE", remarks, internal=True)
        wf.set_pending(case, "HEAD_RLDC", stage="STAGE4_SIGNATURE")
    elif f.stage == 5:
        f.doco_status = "ACCEPTED"
        f.doco_date = f.doco_date or utcnow().date()
        for gid in f.created_element_ids_json:
            g = db.get(GridElement, gid)
            g.cod_date = f.doco_date
        today = utcnow().date()
        for ctype, desc, days in [("AS_BUILT_MODEL", "Final as-built validated model", 90), ("FINAL_SLD", "Final SLD and test reports", 60),
                                  ("POWER_QUALITY", "Annual power quality report", 365), ("PERIODIC_TEST", "Periodic testing report", 180)]:
            f.compliances.append(PostCommCompliance(compliance_type=ctype, description=desc, due_date=today + timedelta(days=days)))
        case.status, case.is_locked, f.stage_status = "CLOSED", True, "ACCEPTED"
        wf.add_step(db, case, "DOCO accepted; post-commissioning compliance tracking started", user, "APPROVE", remarks)
        wf.set_pending(case, None, stage="COMPLETED")


def _advance(db: Session, f: FtcApplication, case: WorkflowCase, user, next_stage: int, msg: str, remarks: str) -> None:
    wf.add_step(db, case, msg, user, "APPROVE", remarks)
    f.stage, f.stage_status = next_stage, "DRAFT"
    case.is_locked, case.status = False, "APPROVED"
    wf.set_pending(case, "APPLICANT" if next_stage != 4 else "FTC_COORDINATOR", stage=f"STAGE{next_stage}_DRAFT")
    notify_users(db, [db.get(User, case.applicant_user_id)], f"{case.case_number}: {msg}", module="ftc", step_code="CASE_FORWARDED",
                 link=f"/ftc/{f.id}")


class ConsentIn(BaseModel):
    decision: str = Field(pattern="^(ACCEPTED|RETURNED)$")
    remarks: str = ""


@router.post("/cases/{fid}/consents/{cid}")
def consent(fid: int, cid: int, body: ConsentIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Departmental consent; observations are not visible to the user (TS p.107)."""
    f, case = _get(db, fid, user)
    stage_key = f"STAGE{f.stage}"
    wf.record_consent(db, case, stage_key, cid, user, body.decision, body.remarks)
    state = wf.stage_consent_state(db, case, stage_key)
    if state == "RETURNED":
        wf.set_pending(case, "FTC_COORDINATOR", stage=f"{stage_key}_DEPT_RETURNED")
        notify_users(db, wf.users_for(db, case.centre_id, {"FTC_COORDINATOR"}), f"{case.case_number}: department returned with observation",
                     module="ftc", step_code="CASE_RETURNED", link=f"/ftc/{f.id}", centre_id=case.centre_id)
    elif state == "ALL_ACCEPTED":
        wf.set_pending(case, "FTC_COORDINATOR", stage=f"{stage_key}_READY_TO_ACCEPT")
    db.commit()
    return ftc_out(db, f, case, user, full=True)


class FormatTrIn(BaseModel):
    trial_run_date: date
    quantum_mw: float = Field(gt=0, le=10000)
    remarks: str = ""


@router.post("/cases/{fid}/format-tr")
def format_tr(fid: int, body: FormatTrIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Trial-run notice >= 7 working days ahead (IEGC Cl. 21); stays open for withdraw/re-upload with versions (TS p.107-108)."""
    f, case = _get(db, fid, user)
    if f.stage != 2:
        raise HTTPException(409, "Format TR is submitted in Stage 2")
    need = int(get_setting(db, "trial_run_notice_working_days") or 7)
    wd = working_days_between(utcnow().date(), body.trial_run_date)
    if wd < need:
        raise HTTPException(422, f"Trial-run notice must be given at least {need} working days in advance (only {wd} working days)")
    ent = db.get(Entity, f.entity_id)
    pdf = render_pdf("Format TR - Notice of trial run", "फॉर्मेट टीआर - ट्रायल रन की सूचना", case.case_number,
                     [("Owner", ent.name), ("Trial-run date", body.trial_run_date), ("Notice upload date", utcnow().date()),
                      ("Quantum (MW)", body.quantum_mw), ("Elements", ", ".join(e["name"] for e in f.a2_elements_json)), ("Remarks", body.remarks)])
    d = store_upload(db, data=pdf, filename="Format_TR.pdf", module="ftc", doc_category="FORMAT_TR", owner_ref=f"case:{case.id}",
                     centre_code=case.centre.code, case_id=case.id, user=user, change_note=body.remarks)
    f.format_tr_date, f.format_tr_quantum_mw, f.format_tr_uploaded_at, f.format_tr_status = body.trial_run_date, body.quantum_mw, utcnow(), "SUBMITTED"
    wf.add_step(db, case, f"Trial-run notice (Format TR v{d.version_no}) for {body.trial_run_date:%d-%m-%Y}", user, "SUBMIT", body.remarks)
    notify_users(db, wf.users_for(db, case.centre_id, {"FTC_COORDINATOR"}),
                 f"Trial-run notice: {ent.name}, {body.quantum_mw} MW on {body.trial_run_date:%d-%m-%Y} (uploaded {utcnow():%d-%m-%Y})",
                 module="ftc", step_code="FORMAT_TR_UPLOADED", link=f"/ftc/{f.id}", centre_id=case.centre_id)
    db.commit()
    return ftc_out(db, f, case, user)


@router.post("/cases/{fid}/format-tr/decide")
def format_tr_decide(fid: int, approve: bool = Form(...), remarks: str = Form(""), db: Session = Depends(get_db), user=Depends(get_current_user)):
    f, case = _get(db, fid, user)
    if not _coord(user, case.centre_id):
        raise HTTPException(403)
    f.format_tr_status = "APPROVED" if approve else "RETURNED"
    wf.add_step(db, case, f"Format TR {f.format_tr_status.lower()}", user, "APPROVE" if approve else "RETURN", remarks)
    db.commit()
    return {"format_tr_status": f.format_tr_status}


@router.put("/cases/{fid}/pre-certificate")
def pre_certificate(fid: int, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    f, case = _get(db, fid, user)
    if not _coord(user, case.centre_id) or f.stage != 4:
        raise HTTPException(403, "FTC Coordinator fills the pre-certificate in Stage 4")
    f.pre_certificate_json = body
    pdf = render_pdf("Pre-certificate (trial run)", "पूर्व-प्रमाणपत्र (ट्रायल रन)", case.case_number, list(body.items()), draft=True)
    store_upload(db, data=pdf, filename="Pre_Certificate.pdf", module="ftc", doc_category="PRE_CERTIFICATE", owner_ref=f"case:{case.id}",
                 centre_code=case.centre.code, case_id=case.id, user=user, visible_to_applicant=False)
    wf.add_step(db, case, "Pre-certificate prepared", user, "COMMENT", internal=True)
    db.commit()
    return {"ok": True}


@router.post("/cases/{fid}/sign-certificate")
def sign_certificate(fid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Head of RLDC signs; certificate then becomes visible/downloadable to the user (TS p.112-113)."""
    f, case = _get(db, fid, user)
    if not ("HEAD_RLDC" in role_codes(user) or is_admin(user)):
        raise HTTPException(403, "Head of RLDC signs the certificate")
    if f.stage != 4 or f.stage_status != "AWAITING_SIGNATURE":
        raise HTTPException(409, "No certificate awaiting signature")
    ent = db.get(Entity, f.entity_id)
    pdf = render_pdf("Certificate of successful trial run", "सफल ट्रायल रन का प्रमाणपत्र", case.case_number,
                     [("Applicant", ent.name), *[(k, v) for k, v in f.pre_certificate_json.items()],
                      ("Elements", ", ".join(db.get(GridElement, i).unique_element_id for i in f.created_element_ids_json)),
                      ("Charging date/time (from real-time module)", f.realtime_charging_time)],
                     signer=user, signer_role=f"Head of {case.centre.code}")
    d = store_upload(db, data=pdf, filename="Trial_Run_Certificate_signed.pdf", module="ftc", doc_category="TRIAL_CERTIFICATE",
                     owner_ref=f"case:{case.id}", centre_code=case.centre.code, case_id=case.id, user=user, visible_to_applicant=True)
    f.trial_cert_doc_id, f.trial_cert_signed = d.id, True
    _advance(db, f, case, user, 5, "Trial-run certificate digitally signed by Head of RLDC and released", "")
    notify_users(db, [db.get(User, case.applicant_user_id)], f"{case.case_number}: trial-run certificate issued", module="ftc",
                 step_code="CERTIFICATE_ISSUED", link=f"/ftc/{f.id}")
    audit(db, user, "ftc", "CERTIFICATE_SIGNED", "case", case.case_number)
    db.commit()
    return ftc_out(db, f, case, user, full=True)


@router.post("/cases/{fid}/doco/decide")
def doco_decide(fid: int, approve: bool = Form(...), remarks: str = Form(""), doco_date: date | None = Form(None),
                db: Session = Depends(get_db), user=Depends(get_current_user)):
    f, case = _get(db, fid, user)
    if not _coord(user, case.centre_id) or f.stage != 5:
        raise HTTPException(403)
    if approve:
        f.doco_date = doco_date or utcnow().date()
        _accept_stage(db, f, case, user, remarks)
    else:
        f.doco_status = "RETURNED"
        wf.add_step(db, case, "DOCO letter returned", user, "RETURN", remarks)
        wf.set_pending(case, "APPLICANT", stage="STAGE5_RETURNED")
    db.commit()
    return ftc_out(db, f, case, user, full=True)


@router.post("/cases/{fid}/send-to-beneficiaries")
def send_c_annexures(fid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    f, case = _get(db, fid, user)
    if not _coord(user, case.centre_id):
        raise HTTPException(403)
    from app.integrations.notifier import send_raw

    for r in ("beneficiary1@states.example", "beneficiary2@states.example"):
        send_raw(db, "EMAIL", r, f"C-annexures of {case.case_number}", module="ftc")
    wf.add_step(db, case, "C-annexures sent to beneficiaries", user, "COMMENT")
    db.commit()
    return {"ok": True}


class IssueIn(BaseModel):
    message: str = Field(min_length=3)


@router.post("/cases/{fid}/issues")
def log_issue(fid: int, body: IssueIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Real-time issues flagged to REGS and their replies, chronological (TS p.114)."""
    f, case = _get(db, fid, user)
    db.add(FtcIssueLog(ftc_application_id=f.id, author_user_id=user.id, author_name=user.full_name,
                       direction="FROM_REGS" if is_external(user) else "TO_REGS", message=body.message))
    target = [db.get(User, case.applicant_user_id)] if not is_external(user) else wf.users_for(db, case.centre_id, {"FTC_COORDINATOR"})
    notify_users(db, target, f"{case.case_number}: {body.message[:80]}", module="ftc", link=f"/ftc/{f.id}")
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ real-time linkage (called by Real-time module)
def on_charging_executed(db: Session, element: GridElement, when: datetime) -> None:
    """Charging date/time entered by grid operators is populated into the FTC case automatically (TS p.110)."""
    if not element.source_ftc_case_id:
        return
    f = db.get(FtcApplication, element.source_ftc_case_id)
    if f and f.realtime_charging_time is None:
        f.realtime_charging_time = when
        element.ftc_date = when.date()
        case = db.get(WorkflowCase, f.case_id)
        wf.add_step(db, case, f"First time charging executed for {element.unique_element_id} at {when:%d-%m-%Y %H:%M}", None, "COMMENT",
                    "Populated automatically from Real-time Outage Management")


# ------------------------------------------------------------------ post-commissioning compliance
@router.get("/compliance")
def compliance(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.scalars(select(PostCommCompliance).order_by(PostCommCompliance.due_date)).all()
    out = []
    for c in rows:
        f = db.get(FtcApplication, c.ftc_application_id)
        if is_external(user) and f.entity_id != user.entity_id:
            continue
        case = db.get(WorkflowCase, f.case_id)
        out.append({**_comp_out(c), "case_number": case.case_number, "entity": db.get(Entity, f.entity_id).name})
    return out


@router.post("/compliance/{cid}/submit")
def compliance_submit(cid: int, signed_by: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = db.get(PostCommCompliance, cid)
    f = db.get(FtcApplication, c.ftc_application_id)
    if is_external(user) and f.entity_id != user.entity_id:
        raise HTTPException(403)
    d = store_upload(db, file=file, module="ftc", doc_category=c.compliance_type, owner_ref=f"compliance:{c.id}", user=user)
    c.doc_id, c.signed_by, c.status = d.id, signed_by, "SUBMITTED"
    db.commit()
    return _comp_out(c)


@router.post("/compliance/{cid}/decide")
def compliance_decide(cid: int, approve: bool = Form(...), remarks: str = Form(""), db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not _coord(user):
        raise HTTPException(403)
    c = db.get(PostCommCompliance, cid)
    c.status, c.remarks = ("ACCEPTED" if approve else "REJECTED"), remarks
    db.commit()
    return _comp_out(c)


# ------------------------------------------------------------------ start-up power (TS p.115-116)
class StartupIn(BaseModel):
    unit_details: str
    quantum_mw: float = Field(gt=0, le=2000)
    period_from: date
    period_to: date


@router.post("/startup-power")
def startup_apply(body: StartupIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if user.entity_id is None:
        raise HTTPException(422, "Generating station login required")
    ent = db.get(Entity, user.entity_id)
    centre = db.get(Centre, ent.centre_id) if ent.centre_id else db.scalar(select(Centre).where(Centre.code == "NRLDC"))
    case = wf.new_case(db, "SUP", centre, user, f"Start-up power: {ent.name}", applicant_entity_id=ent.id)
    r = StartupPowerRequest(case_id=case.id, entity_id=ent.id, **body.model_dump())
    db.add(r)
    case.status = "SUBMITTED"
    wf.set_pending(case, "FTC_COORDINATOR", stage="GRANT")
    db.commit()
    return {"id": r.id, "case_number": case.case_number}


@router.get("/startup-power")
def startup_list(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.scalars(select(StartupPowerRequest).order_by(StartupPowerRequest.id.desc())).all()
    if is_external(user):
        rows = [r for r in rows if r.entity_id == user.entity_id]
    return [{"id": r.id, "case_number": db.get(WorkflowCase, r.case_id).case_number, "entity": db.get(Entity, r.entity_id).name,
             "unit_details": r.unit_details, "quantum_mw": r.quantum_mw, "period_from": r.period_from, "period_to": r.period_to,
             "granted_quantum_mw": r.granted_quantum_mw, "granted_from": r.granted_from, "granted_to": r.granted_to,
             "grant_status": r.grant_status, "weekly_updates": r.weekly_updates_json, "monthly_energy": r.monthly_energy_json} for r in rows]


class GrantIn(BaseModel):
    approve: bool
    quantum_mw: float | None = None
    period_from: date | None = None
    period_to: date | None = None


@router.post("/startup-power/{rid}/grant")
def startup_grant(rid: int, body: GrantIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not _coord(user):
        raise HTTPException(403)
    r = db.get(StartupPowerRequest, rid)
    r.grant_status = "GRANTED" if body.approve else "REJECTED"
    r.granted_quantum_mw, r.granted_from, r.granted_to = body.quantum_mw or r.quantum_mw, body.period_from or r.period_from, body.period_to or r.period_to
    case = db.get(WorkflowCase, r.case_id)
    case.status = "APPROVED" if body.approve else "REJECTED"
    wf.add_step(db, case, f"Start-up power {r.grant_status.lower()} (copy to RPC)", user, "APPROVE" if body.approve else "REJECT")
    db.commit()
    return {"grant_status": r.grant_status}


@router.post("/startup-power/{rid}/update")
def startup_update(rid: int, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Weekly quantum/schedule and monthly construction-power energy updates (TS p.115)."""
    r = db.get(StartupPowerRequest, rid)
    if is_external(user) and r.entity_id != user.entity_id:
        raise HTTPException(403)
    entry = {**body, "at": utcnow().isoformat()}
    if body.get("kind") == "MONTHLY":
        r.monthly_energy_json = [*r.monthly_energy_json, entry]
    else:
        r.weekly_updates_json = [*r.weekly_updates_json, entry]
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ reports & dashboard (TS p.116-119)
@router.get("/reports/{kind}")
def reports(kind: str, fmt: str = "json", from_date: str | None = None, to_date: str | None = None, element_type: str | None = None,
            db: Session = Depends(get_db), user=Depends(get_current_user)):
    d0 = date.fromisoformat(from_date) if from_date else date(2000, 1, 1)
    d1 = date.fromisoformat(to_date) if to_date else date(2100, 1, 1)
    if kind in ("ftc", "cod"):
        attr = GridElement.ftc_date if kind == "ftc" else GridElement.cod_date
        stmt = select(GridElement).where(attr.isnot(None), attr >= d0, attr <= d1).order_by(attr.desc())
        if element_type:
            stmt = stmt.where(GridElement.element_type == element_type)
        rows = [{"unique_element_id": g.unique_element_id, "name": g.name, "element_type": g.element_type, "voltage_kv": g.voltage_kv,
                 "centre": g.centre.code, "ftc_date": g.ftc_date, "cod_date": g.cod_date,
                 "owner": ", ".join(o.entity.short_name or o.entity.name for o in g.owners)} for g in db.scalars(stmt)]
        cols = [("unique_element_id", "Element ID", "तत्व आईडी"), ("name", "Element", "तत्व"), ("element_type", "Type", "प्रकार"),
                ("voltage_kv", "kV", "केवी"), ("centre", "Centre", "केंद्र"), ("ftc_date", "FTC date", "एफटीसी तिथि"),
                ("cod_date", "COD", "सीओडी"), ("owner", "Owner", "स्वामी")]
        title = ("First-time charged elements", "प्रथम चार्ज किए गए तत्व") if kind == "ftc" else ("Elements declared COD", "सीओडी घोषित तत्व")
    elif kind == "comments":
        rows = []
        for f in db.scalars(select(FtcApplication)):
            case = db.get(WorkflowCase, f.case_id)
            for s in range(1, 6):
                for r in wf.consents(db, case, f"STAGE{s}"):
                    if r.status != "PENDING":
                        rows.append({"case_number": case.case_number, "entity": db.get(Entity, f.entity_id).name, "stage": s,
                                     "department": r.department, "level": r.level, "status": r.status, "remarks": r.remarks, "at": r.updated_at})
        cols = [("case_number", "Case ID", "मामला आईडी"), ("entity", "User", "उपयोगकर्ता"), ("stage", "Stage", "चरण"),
                ("department", "Department", "विभाग"), ("level", "Level", "स्तर"), ("status", "Status", "स्थिति"),
                ("remarks", "Comments", "टिप्पणी"), ("at", "Date", "दिनांक")]
        title = ("Departmental comments report", "विभागीय टिप्पणी रिपोर्ट")
    else:
        raise HTTPException(404)
    if fmt == "json":
        return {"title": title[0], "columns": cols, "rows": rows}
    return export(fmt, title[0], title[1], cols, rows, f"ftc_{kind}")


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    cases = list_cases(db=db, user=user)
    comments = reports("comments", db=db, user=user)["rows"]
    closed = [c for c in cases if c["status"] == "CLOSED"]
    avg = round(sum((c["updated_at"] - c["created_at"]).total_seconds() for c in closed) / 86400 / len(closed), 1) if closed else 0
    return {"total": len(cases), "by_stage": dict(Counter(f"Stage {c['stage']}" for c in cases)),
            "by_status": dict(Counter(c["status"] for c in cases)), "by_jurisdiction": dict(Counter(c["jurisdiction"] for c in cases)),
            "accepted": sum(r["status"] == "ACCEPTED" for r in comments), "returned": sum(r["status"] == "RETURNED" for r in comments),
            "return_by_department": dict(Counter(r["department"] for r in comments if r["status"] == "RETURNED")),
            "avg_clearance_days": avg}


