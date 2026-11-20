"""Registration Module (TS Cl. 11.4.1 p.83-98; FRD REG-01..48)."""
import io
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.rbac import get_current_user, is_admin, is_external, role_codes, sees_all_centres
from app.core.security import hash_password, password_policy_errors, verify_captcha
from app.db.base import utcnow
from app.db.session import get_db
from app.integrations import nsws_adapter
from app.integrations.notifier import notify_users
from app.modules.auth_rbac.models import Centre, Role, User, UserRole
from app.modules.auth_rbac.service import random_password
from app.modules.dms_files.service import doc_out, list_docs, store_upload
from app.modules.master_registry.models import Entity
from app.modules.registration.models import AccountRequest, FncImportBatch, RegApplication, RegFileReview, RegShiftLog
from app.modules.workflow_engine import service as wf
from app.modules.workflow_engine.models import WorkflowCase
from app.utils.certificates import render_pdf

router = APIRouter(prefix="/api/v1/registration", tags=["registration"])
RE_CATEGORIES = {"RE_POWER_PARK": ["SOLAR", "WIND", "HYBRID", "PUMPED_STORAGE"], "RE_GEN_STATION": ["SOLAR", "WIND", "HYBRID", "PUMPED_STORAGE"],
                 "BESS": ["BESS"], "CONV_GEN": ["THERMAL", "HYDRO", "GAS", "NUCLEAR"], "TRANS_LICENSEE": ["ISTS", "INTRA_STATE"],
                 "COMM_PROVIDER": ["OPGW", "FOTE", "STATE_CSP"]}
REG_DOC_TYPES = ["SHEET1_FORM", "BOARD_RESOLUTION", "GST_PAN_CERT", "SLD", "UNDERTAKING", "CONNECTIVITY_GRANT", "OTHER"]
CONSENT_DEPTS = ["SO-1", "SO-2", "MO", "SCADA", "MIS"]
EXT_ROLE_FOR = {"RE_REGISTRATION": ["EXT_REGISTRATION", "EXT_FTC"], "FTC": ["EXT_FTC"], "OUTAGE": ["EXT_REALTIME", "EXT_OUTAGE"],
                "COMM": ["EXT_COMM"], "PROTECTION": ["EXT_PROTECTION"], "AVAILABILITY": ["EXT_AVAILABILITY"]}


def _coord(user, centre_id: int | None = None) -> bool:
    codes = role_codes(user)
    if is_admin(user):
        return True
    if "REG_COORDINATOR" not in codes:
        return False
    return centre_id is None or sees_all_centres(user) or user.centre_id == centre_id


def _app(db: Session, aid: int, user) -> RegApplication:
    a = db.get(RegApplication, aid)
    if a is None:
        raise HTTPException(404, "Application not found")
    case = db.get(WorkflowCase, a.case_id)
    codes = role_codes(user)
    if is_external(user) and "CTU" not in codes:
        if case.applicant_user_id != user.id and (not user.entity_id or a.entity_id != user.entity_id):
            raise HTTPException(403, "Not your application")
    return a


def app_out(db: Session, a: RegApplication, user, full: bool = False) -> dict:
    case = db.get(WorkflowCase, a.case_id)
    codes = role_codes(user)
    requester = is_external(user) and "CTU" not in codes
    ent = db.get(Entity, a.entity_id) if a.entity_id else None
    out = {**wf.case_out(case), "application_id": a.id, "application_type": a.application_type, "category": a.category,
           "sub_category": a.sub_category, "is_renewable": a.is_renewable, "is_modified_element": a.is_modified_element,
           "nsws_ref_no": a.nsws_ref_no, "entity": ent.name if ent else "", "entity_id": a.entity_id,
           "nodal_centre": db.get(Centre, a.nodal_centre_id).code, "current_centre": db.get(Centre, a.current_centre_id).code,
           "processing_started": a.processing_started, "ctu_shared_with_rldc": a.ctu_shared_with_rldc,
           "files_total": len(a.files), "files_ctu_approved": sum(f.ctu_status == "CTU_APPROVED" for f in a.files)}
    if full:
        files = []
        for f in a.files:
            row = {"id": f.id, "file_category": f.file_category, "iteration": f.iteration, "document_id": f.document_id,
                   "joint_comment": f.joint_comment if (f.joint_released or not requester) else "",
                   "joint_released": f.joint_released, "requester_change_note": f.requester_change_note}
            if not requester or f.joint_released:
                row.update({"rldc_status": f.rldc_status, "ctu_status": f.ctu_status})
            if not requester:
                row.update({"rldc_comment": f.rldc_comment, "ctu_comment": f.ctu_comment, "nldc_comment": f.nldc_comment})
            files.append(row)
        rows = wf.consents(db, case, "REGISTRATION")
        out.update({
            "form_data": a.form_data_json, "compliance_sheet": a.compliance_sheet_json if not requester or any(f.joint_released for f in a.files) else {},
            "files": files, "documents": list_docs(db, f"case:{case.id}", applicant_view=requester),
            "consents": [] if requester else [wf.consent_out(r, user, case, rows) for r in rows],
            "consent_summary": [{"department": r.department, "status": r.status, "remarks": r.remarks if r.status == "RETURNED" else ""} for r in rows],
            "shifts": [{"from": db.get(Centre, s.from_centre_id).code, "to": db.get(Centre, s.to_centre_id).code, "shifted_at": s.shifted_at,
                        "nldc_comment": s.nldc_comment, "returned_at": s.returned_at, "return_comment": s.return_comment} for s in a.shifts],
            "tracker": wf.tracker(db, case, applicant_view=requester),
            "draft": case.draft_data_json, "doc_types": REG_DOC_TYPES,
            "is_coordinator": _coord(user, a.current_centre_id), "is_ctu": "CTU" in codes, "is_requester": requester,
        })
    return out


@router.get("/meta")
def meta(user=Depends(get_current_user)):
    return {"categories": RE_CATEGORIES, "doc_types": REG_DOC_TYPES, "consent_departments": CONSENT_DEPTS,
            "model_file_categories": nsws_adapter.MODEL_FILE_CATEGORIES}


@router.get("/applications")
def list_apps(app_type: str | None = None, centre: str | None = None, status: str | None = None,
              db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(RegApplication).join(WorkflowCase, RegApplication.case_id == WorkflowCase.id).order_by(WorkflowCase.created_at.desc())
    codes = role_codes(user)
    if "CTU" in codes:
        stmt = stmt.where(RegApplication.application_type == "NSWS_CONNECTIVITY")
    elif is_external(user):
        stmt = stmt.where(or_(WorkflowCase.applicant_user_id == user.id, RegApplication.entity_id == (user.entity_id or -1)))
    elif not sees_all_centres(user):
        stmt = stmt.where(or_(RegApplication.nodal_centre_id == user.centre_id, RegApplication.current_centre_id == user.centre_id))
    if app_type:
        stmt = stmt.where(RegApplication.application_type == app_type)
    if centre and centre != "ALL":
        c = db.scalar(select(Centre).where(Centre.code == centre))
        if c:
            stmt = stmt.where(or_(RegApplication.nodal_centre_id == c.id, RegApplication.current_centre_id == c.id))
    if status:
        stmt = stmt.where(WorkflowCase.status == status)
    return [app_out(db, a, user) for a in db.scalars(stmt)]


@router.get("/applications/{aid}")
def get_app(aid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return app_out(db, _app(db, aid, user), user, full=True)


# ================================================================== A. NSWS connectivity (CONN-4)
class NswsSyncIn(BaseModel):
    nsws_ref_no: str = Field(pattern=r"^[A-Z0-9/-]{6,30}$")
    nodal_centre: str = "NRLDC"


@router.post("/nsws/sync")
def nsws_sync(body: NswsSyncIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """After CTUIL acknowledges on NSWS, data + segregated model files are fetched by API (steps 2-3)."""
    if not ("CTU" in role_codes(user) or is_admin(user)):
        raise HTTPException(403, "Only CTUIL acknowledges and pulls NSWS applications")
    if db.scalar(select(RegApplication).where(RegApplication.nsws_ref_no == body.nsws_ref_no)):
        raise HTTPException(409, "NSWS application already synced")
    data = nsws_adapter.fetch(body.nsws_ref_no)
    centre = db.scalar(select(Centre).where(Centre.code == body.nodal_centre))
    ent = Entity(name=data["applicant"]["name"], entity_type="REGS", sub_category=data["project"]["energy_source"], sector="PRIVATE",
                 state=data["applicant"]["state"], centre_id=centre.id, nsws_reg_no=body.nsws_ref_no, gst_no=data["applicant"]["gst_no"],
                 pan_no=data["applicant"]["pan_no"], installed_capacity_mw=data["project"]["installed_capacity_mw"], status="APPLICANT")
    db.add(ent)
    db.flush()
    case = wf.new_case(db, "REG", centre, user, f"CONN-4: {data['project']['name']}", applicant_entity_id=ent.id)
    a = RegApplication(case_id=case.id, application_type="NSWS_CONNECTIVITY", category="RE_POWER_PARK", sub_category=data["project"]["energy_source"],
                       nsws_ref_no=body.nsws_ref_no, entity_id=ent.id, nodal_centre_id=centre.id, current_centre_id=centre.id,
                       form_data_json={"applicant": data["applicant"], "project": data["project"]},
                       compliance_sheet_json={"items": [{"point": p, "status": "OPEN"} for p in
                                                        ["Reactive power capability", "LVRT/HVRT compliance", "Model validation", "Protection settings"]]})
    db.add(a)
    db.flush()
    for f in data["files"]:
        d = store_upload(db, data=f["content"], filename=f["filename"], module="registration", doc_category=f["category"],
                         owner_ref=f"case:{case.id}", centre_code=centre.code, case_id=case.id, user=user, block_zip=True)
        db.add(RegFileReview(application_id=a.id, file_category=f["category"], document_id=d.id))
    case.status = "SUBMITTED"
    wf.add_step(db, case, "Fetched from NSWS after CTUIL acknowledgement", user, "SUBMIT", f"NSWS {body.nsws_ref_no}")
    wf.set_pending(case, "CTU", stage="CTU_REVIEW")
    audit(db, user, "registration", "NSWS_SYNCED", "application", body.nsws_ref_no)
    db.commit()
    return app_out(db, a, user)


class CtuSubmitIn(BaseModel):
    comments: dict[int, str] = {}


@router.post("/applications/{aid}/ctu-submit")
def ctu_submit(aid: int, body: CtuSubmitIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """CTUIL comments per file then 'Submit to RLDC'; blank -> 'Shared for inputs from RLDC' (step 6)."""
    a = _app(db, aid, user)
    if not ("CTU" in role_codes(user) or is_admin(user)):
        raise HTTPException(403)
    for f in a.files:
        f.ctu_comment = body.comments.get(f.id) or f.ctu_comment or "Shared for inputs from RLDC"
    a.ctu_shared_with_rldc = True
    case = db.get(WorkflowCase, a.case_id)
    case.status = "UNDER_REVIEW"
    wf.add_step(db, case, "CTUIL submitted to RLDC", user, "FORWARD", forwarded_to="REG_COORDINATOR")
    wf.set_pending(case, "REG_COORDINATOR", stage="RLDC_REVIEW")
    notify_users(db, wf.users_for(db, a.current_centre_id, {"REG_COORDINATOR"}), f"{case.case_number} shared by CTUIL for RLDC comments",
                 module="registration", step_code="CASE_SUBMITTED", link=f"/registration/{a.id}", centre_id=a.current_centre_id)
    db.commit()
    return app_out(db, a, user, full=True)


class FileReviewIn(BaseModel):
    reviewer: str = Field(pattern="^(RLDC|CTU|NLDC)$")
    status: str = Field(pattern="^(APPROVED|NEEDS_REVISION)$")
    comment: str = ""


@router.post("/files/{fid}/review")
def review_file(fid: int, body: FileReviewIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """File-wise validation against checklist by RLDC (step 7) and CTUIL (step 8)."""
    f = db.get(RegFileReview, fid)
    if f is None:
        raise HTTPException(404)
    a = f.application
    case = db.get(WorkflowCase, a.case_id)
    if body.status == "NEEDS_REVISION" and not body.comment.strip():
        raise HTTPException(422, "Comment required for revision")
    if body.reviewer == "RLDC":
        if not _coord(user, a.current_centre_id) or not a.ctu_shared_with_rldc:
            raise HTTPException(403, "RLDC review by the (current) RLDC coordinator after CTUIL shares the files")
        f.rldc_status = "RLDC_APPROVED" if body.status == "APPROVED" else "RLDC_NEEDS_REVISION"
        f.rldc_comment = body.comment
        a.processing_started = True
    elif body.reviewer == "CTU":
        if not ("CTU" in role_codes(user) or is_admin(user)):
            raise HTTPException(403)
        f.ctu_status = "CTU_APPROVED" if body.status == "APPROVED" else "CTU_NEEDS_REVISION"
        f.ctu_comment = body.comment
    else:
        if "NLDC_USER" not in role_codes(user) and not is_admin(user):
            raise HTTPException(403)
        f.nldc_comment = body.comment
    wf.add_step(db, case, f"{body.reviewer} reviewed {f.file_category}: {body.status}", user, "COMMENT", body.comment, internal=True)
    # auto-return a shifted application once the helping RLDC has validated all files (TS p.88)
    if a.current_centre_id != a.nodal_centre_id and all(x.rldc_status != "UNDER_PROCESSING" for x in a.files):
        _return_to_nodal(db, a, user, "Model-data validation completed by helping RLDC")
    db.commit()
    return {"ok": True, "rldc_status": f.rldc_status, "ctu_status": f.ctu_status, "returned_to_nodal": a.current_centre_id == a.nodal_centre_id}


class JointIn(BaseModel):
    items: list[dict]  # [{"file_id": 1, "source": "CTU"|"RLDC"|"MANUAL", "text": "..."}]
    share_compliance: bool = True


@router.post("/applications/{aid}/joint-comments")
def joint_comments(aid: int, body: JointIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """CTUIL consolidates joint comments (CTU/RLDC/manual) and may release only some files (step 10 + note)."""
    a = _app(db, aid, user)
    if not ("CTU" in role_codes(user) or is_admin(user)):
        raise HTTPException(403, "Joint comments are moderated by CTUIL")
    by_id = {f.id: f for f in a.files}
    released = []
    for it in body.items:
        f = by_id.get(int(it["file_id"]))
        if f is None:
            continue
        src = it.get("source", "MANUAL")
        f.joint_comment = f.ctu_comment if src == "CTU" else f.rldc_comment if src == "RLDC" else it.get("text", "")
        f.joint_released = True
        released.append(f.file_category)
    case = db.get(WorkflowCase, a.case_id)
    wf.add_step(db, case, f"Joint comments released for {len(released)} file(s)", user, "RETURN", ", ".join(released))
    wf.set_pending(case, "APPLICANT", stage="REQUESTER_REVISION", status="RETURNED")
    nsws_adapter.push_status(a.nsws_ref_no, {"event": "JOINT_COMMENTS", "files": {f.file_category: [f.rldc_status, f.ctu_status] for f in a.files},
                                             "compliance": a.compliance_sheet_json if body.share_compliance else None})
    a.nsws_last_push_at = utcnow()
    applicants = db.scalars(select(User).where(User.entity_id == a.entity_id)).all() if a.entity_id else []
    notify_users(db, list(applicants), f"Joint comments available on {case.case_number}", module="registration",
                 step_code="CASE_RETURNED", link=f"/registration/{a.id}")
    db.commit()
    return app_out(db, a, user, full=True)


@router.post("/files/{fid}/revise")
def revise_file(fid: int, change_note: str = Form(..., min_length=3), file: UploadFile = File(...),
                db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Requester uploads revised file with a note of what changed (step 12); earlier versions retained."""
    f = db.get(RegFileReview, fid)
    a = _app(db, f.application_id, user)
    case = db.get(WorkflowCase, a.case_id)
    d = store_upload(db, file=file, module="registration", doc_category=f.file_category, owner_ref=f"case:{case.id}",
                     centre_code=case.centre.code, case_id=case.id, user=user, change_note=change_note, block_zip=True)
    f.document_id, f.requester_change_note, f.iteration = d.id, change_note, f.iteration + 1
    f.rldc_status = f.ctu_status = "UNDER_PROCESSING"
    f.joint_released = False
    case.status = "UNDER_REVIEW"
    wf.add_step(db, case, f"Revised {f.file_category} uploaded (v{d.version_no})", user, "SUBMIT", change_note)
    wf.set_pending(case, "CTU", stage="CTU_REVIEW")
    notify_users(db, db.scalars(select(User).join(UserRole).join(Role).where(Role.code == "CTU")).all(),
                 f"Revised file on {case.case_number}", module="registration", link=f"/registration/{a.id}")
    db.commit()
    return {"ok": True, "document": doc_out(d)}


@router.post("/applications/{aid}/complete")
def complete_conn4(aid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """All files approved by CTUIL -> CONN-4 certificate generated by CTUIL and pushed to NSWS (steps 13-14)."""
    a = _app(db, aid, user)
    if not ("CTU" in role_codes(user) or is_admin(user)):
        raise HTTPException(403)
    pending = [f.file_category for f in a.files if f.ctu_status != "CTU_APPROVED"]
    if pending:
        raise HTTPException(409, "Files not yet approved by CTUIL: " + ", ".join(pending))
    case = db.get(WorkflowCase, a.case_id)
    proj = a.form_data_json.get("project", {})
    pdf = render_pdf("CONN-4 Certificate - Connectivity model validation", "सीओएनएन-4 प्रमाणपत्र - कनेक्टिविटी मॉडल सत्यापन", case.case_number,
                     [("NSWS registration", a.nsws_ref_no), ("Applicant", a.form_data_json.get("applicant", {}).get("name")),
                      ("Project", proj.get("name")), ("Capacity (MW)", proj.get("installed_capacity_mw")),
                      ("Nodal RLDC", db.get(Centre, a.nodal_centre_id).code),
                      ("Validated files", ", ".join(f.file_category for f in a.files))], signer=user, signer_role="CTUIL")
    d = store_upload(db, data=pdf, filename="CONN4.pdf", module="registration", doc_category="CONN4_CERTIFICATE",
                     owner_ref=f"case:{case.id}", centre_code=case.centre.code, case_id=case.id, user=user)
    a.conn4_cert_doc_id = d.id
    case.status, case.is_locked = "APPROVED", True
    wf.add_step(db, case, "CONN-4 certificate issued; approved files sent to NSWS", user, "APPROVE", signed=True)
    wf.set_pending(case, None, stage="COMPLETED")
    nsws_adapter.push_status(a.nsws_ref_no, {"event": "COMPLETED", "conn4_doc": d.auto_filename})
    if a.entity_id:
        db.get(Entity, a.entity_id).status = "ACTIVE"
    audit(db, user, "registration", "CONN4_ISSUED", "application", a.id)
    db.commit()
    return {"ok": True, "conn4_doc_id": d.id}


# ================================================================== NLDC workload shifting
@router.get("/workload")
def workload(db: Session = Depends(get_db), user=Depends(get_current_user)):
    out = []
    for c in db.scalars(select(Centre).where(Centre.code != "NLDC")):
        apps = db.scalars(select(RegApplication).join(WorkflowCase, RegApplication.case_id == WorkflowCase.id).where(
            RegApplication.current_centre_id == c.id, RegApplication.is_renewable, WorkflowCase.status.notin_(["APPROVED", "CLOSED"]))).all()
        out.append({"centre": c.code, "pending": len(apps), "unstarted": sum(not a.processing_started for a in apps),
                    "applications": [app_out(db, a, user) for a in apps]})
    return out


class ShiftIn(BaseModel):
    application_ids: list[int]
    to_centre: str
    comment: str = Field(min_length=3)


@router.post("/shift")
def shift(body: ShiftIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """NLDC Registration Coordinator shifts unstarted RE applications to a lightly loaded RLDC (TS p.87-88)."""
    if not (is_admin(user) or ("REG_COORDINATOR" in role_codes(user) and user.centre and user.centre.code == "NLDC")):
        raise HTTPException(403, "Only the NLDC Registration Coordinator can shift applications")
    to = db.scalar(select(Centre).where(Centre.code == body.to_centre))
    if to is None or to.code == "NLDC":
        raise HTTPException(422, "Target must be an RLDC")
    moved = []
    for aid in body.application_ids:
        a = db.get(RegApplication, aid)
        if a is None or not a.is_renewable:
            raise HTTPException(422, f"Application {aid} is not an RE application")
        if a.processing_started:
            raise HTTPException(409, f"Processing already started by nodal RLDC for application {aid}")
        if a.current_centre_id == to.id:
            continue
        db.add(RegShiftLog(application_id=a.id, from_centre_id=a.current_centre_id, to_centre_id=to.id, shifted_by=user.id, nldc_comment=body.comment))
        a.current_centre_id = to.id
        case = db.get(WorkflowCase, a.case_id)
        wf.add_step(db, case, f"Shifted by NLDC to {to.code} for model validation", user, "SHIFT", body.comment, forwarded_to=to.code)
        moved.append(case.case_number)
        notify_users(db, wf.users_for(db, to.id, {"REG_COORDINATOR"}), f"{case.case_number} shifted to {to.code} by NLDC",
                     module="registration", link=f"/registration/{a.id}", centre_id=to.id)
    audit(db, user, "registration", "WORKLOAD_SHIFTED", "application", ",".join(map(str, body.application_ids)), new=body.model_dump())
    db.commit()
    return {"moved": moved}


def _return_to_nodal(db: Session, a: RegApplication, user, comment: str) -> None:
    log = next((s for s in reversed(a.shifts) if s.returned_at is None), None)
    if log:
        log.returned_at, log.return_comment = utcnow(), comment
    a.current_centre_id = a.nodal_centre_id
    case = db.get(WorkflowCase, a.case_id)
    wf.add_step(db, case, f"Returned to nodal RLDC {db.get(Centre, a.nodal_centre_id).code}", user, "SHIFT", comment)


@router.post("/applications/{aid}/return-to-nodal")
def return_to_nodal(aid: int, comment: str = Form(...), db: Session = Depends(get_db), user=Depends(get_current_user)):
    a = _app(db, aid, user)
    if not _coord(user, a.current_centre_id):
        raise HTTPException(403)
    _return_to_nodal(db, a, user, comment)
    db.commit()
    return {"ok": True}


# ================================================================== B. account requests (self sign-up)
class SignupIn(BaseModel):
    user_type: str = Field(pattern="^(RE_REGISTRATION|FTC|OUTAGE|COMM|PROTECTION|AVAILABILITY)$")
    organisation: str = Field(min_length=3)
    first_name: str
    last_name: str = ""
    additional_names: list[str] = []
    mobile: str = Field(pattern=r"^\+?[0-9]{10,13}$")
    username: str = Field(min_length=4, max_length=40, pattern=r"^[A-Za-z0-9_.]+$")
    email: EmailStr
    password: str
    confirm_password: str
    centre_code: str = "NRLDC"
    nsws_reg_no: str = ""
    cea_egen_no: str = ""
    fnc_reg_no: str = ""
    connectivity_reg_no: str = ""
    captcha_token: str | None = None
    captcha_answer: str | None = None


@router.post("/signup")
def signup(body: SignupIn, db: Session = Depends(get_db)):
    """Pre-registration self sign-up; RLDC Admin approves with role/rights (TS p.90-91)."""
    if not verify_captcha(body.captcha_token, body.captcha_answer):
        raise HTTPException(400, "CAPTCHA verification failed")
    if body.password != body.confirm_password:
        raise HTTPException(422, "Passwords do not match")
    errs = password_policy_errors(body.password)
    if errs:
        raise HTTPException(422, "Password must contain " + ", ".join(errs))
    if db.scalar(select(User).where(func.lower(User.username) == body.username.lower())) or db.scalar(
            select(AccountRequest).where(func.lower(AccountRequest.username) == body.username.lower(), AccountRequest.status == "PENDING")):
        raise HTTPException(409, "Username not available")
    centre = db.scalar(select(Centre).where(Centre.code == body.centre_code))
    r = AccountRequest(username=body.username, first_name=body.first_name, last_name=body.last_name, additional_names_json=body.additional_names,
                       email=body.email, mobile=body.mobile, organisation=body.organisation, user_type=body.user_type, centre_id=centre.id,
                       password_hash=hash_password(body.password), nsws_reg_no=body.nsws_reg_no, cea_egen_no=body.cea_egen_no,
                       fnc_reg_no=body.fnc_reg_no, connectivity_reg_no=body.connectivity_reg_no)
    db.add(r)
    db.flush()
    notify_users(db, wf.users_for(db, centre.id, {"REG_COORDINATOR", "SUPER_ADMIN", "MODULE_ADMIN"}),
                 f"Pre-registration request from {body.organisation} ({body.username})", module="registration",
                 link="/registration/account-requests", centre_id=centre.id)
    db.commit()
    return {"id": r.id, "message": "Your request is under process. Thank you.", "submitted_at": r.created_at}


@router.get("/account-requests")
def account_requests(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not _coord(user):
        raise HTTPException(403)
    return [{"id": r.id, "username": r.username, "name": f"{r.first_name} {r.last_name}".strip(), "organisation": r.organisation,
             "user_type": r.user_type, "email": r.email, "mobile": r.mobile, "centre": db.get(Centre, r.centre_id).code,
             "nsws_reg_no": r.nsws_reg_no, "fnc_reg_no": r.fnc_reg_no, "status": r.status, "created_at": r.created_at}
            for r in db.scalars(select(AccountRequest).order_by(AccountRequest.id.desc()))]


class DecideIn(BaseModel):
    approve: bool
    extra_user_types: list[str] = []
    entity_id: int | None = None
    remarks: str = ""


@router.post("/account-requests/{rid}/decide")
def decide_account(rid: int, body: DecideIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Approve with role/rights; multiple permissions per login (TS p.97-98)."""
    if not _coord(user):
        raise HTTPException(403)
    r = db.get(AccountRequest, rid)
    if r is None or r.status != "PENDING":
        raise HTTPException(409)
    r.status, r.decided_by, r.remarks = ("APPROVED" if body.approve else "REJECTED"), user.id, body.remarks
    out = {"status": r.status}
    if body.approve:
        ent_id = body.entity_id
        if ent_id is None:
            ent = db.scalar(select(Entity).where(Entity.name == r.organisation))
            if ent is None:
                ent = Entity(name=r.organisation, entity_type="REGS" if r.user_type == "RE_REGISTRATION" else "TRANS_LICENSEE",
                             centre_id=r.centre_id, nsws_reg_no=r.nsws_reg_no or None, cea_egen_no=r.cea_egen_no or None,
                             fnc_reg_no=r.fnc_reg_no or None)
                db.add(ent)
                db.flush()
            ent_id = ent.id
        u = User(username=r.username, password_hash=r.password_hash, full_name=f"{r.first_name} {r.last_name}".strip(), email=r.email,
                 mobile=r.mobile, user_category="EXTERNAL", centre_id=r.centre_id, entity_id=ent_id, is_2fa_enabled=True,
                 last_contact_verified_at=utcnow())
        db.add(u)
        db.flush()
        for code in {"EXTERNAL_USER", *EXT_ROLE_FOR.get(r.user_type, []), *[c for t in body.extra_user_types for c in EXT_ROLE_FOR.get(t, [])]}:
            role = db.scalar(select(Role).where(Role.code == code))
            db.add(UserRole(user_id=u.id, role_id=role.id, centre_id=r.centre_id))
        db.flush()
        notify_users(db, [u], "Your Grid-India OMS account request has been approved", module="registration")
        out["user_id"] = u.id
    audit(db, user, "registration", "ACCOUNT_REQUEST_" + r.status, "account_request", r.id, new=body.model_dump())
    db.commit()
    return out


# ================================================================== Fees & Charges import
FNC_COLUMNS = ["Registration No", "Entity Name", "Entity Type", "Sub-category", "State", "GST No", "PAN No", "E-mail", "Mobile", "Capacity MW"]


@router.get("/fnc-import/template")
def fnc_template(user=Depends(get_current_user)):
    from openpyxl import Workbook

    from app.utils.exports import file_response

    wb = Workbook()
    ws = wb.active
    ws.title = "FnC"
    ws.append(FNC_COLUMNS)
    ws.append(["FNC-RE-0101", "Marudhar Solar Pvt Ltd", "REGS", "SOLAR", "Rajasthan", "08ABCDE1234F1Z5", "ABCDE1234F", "ops@marudhar.example", "9876500001", 250])
    buf = io.BytesIO()
    wb.save(buf)
    return file_response(buf.getvalue(), "fnc_import_template.xlsx")


@router.post("/fnc-import/preview")
def fnc_preview(file: UploadFile = File(...), db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Excel import from RLDC Fees & Charges software with error notification and preview (TS p.93-97; CMN-12, CMN-19)."""
    if not _coord(user):
        raise HTTPException(403)
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(file.file.read()), read_only=True)
    except Exception:  # noqa: BLE001
        raise HTTPException(422, "Not a valid Excel (.xlsx) file in the defined format")
    rows = list(wb.active.iter_rows(values_only=True))
    if not rows or [str(c or "").strip() for c in rows[0][:len(FNC_COLUMNS)]] != FNC_COLUMNS:
        raise HTTPException(422, "Header row does not match the defined template: " + ", ".join(FNC_COLUMNS))
    parsed, errors = [], []
    for i, r in enumerate(rows[1:], start=2):
        if not any(r):
            continue
        rec = {k: (str(v).strip() if v is not None else "") for k, v in zip(FNC_COLUMNS, r)}
        errs = []
        if not rec["Registration No"]:
            errs.append("Registration No missing")
        if rec["Entity Type"] not in ("REGS", "CONV_GEN", "TRANS_LICENSEE"):
            errs.append("Entity Type must be REGS / CONV_GEN / TRANS_LICENSEE")
        if "@" not in rec["E-mail"]:
            errs.append("Invalid e-mail")
        if db.scalar(select(Entity).where(Entity.fnc_reg_no == rec["Registration No"])):
            errs.append("Already registered")
        try:
            float(rec["Capacity MW"] or 0)
        except ValueError:
            errs.append("Capacity must be numeric")
        rec["row"] = i
        rec["errors"] = errs
        parsed.append(rec)
        if errs:
            errors.append({"row": i, "errors": errs})
    b = FncImportBatch(entity_type="MIXED", filename=file.filename or "import.xlsx", rows_json=parsed, errors_json=errors, imported_by=user.id)
    db.add(b)
    db.commit()
    return {"batch_id": b.id, "rows": parsed, "errors": errors, "valid": sum(not r["errors"] for r in parsed)}


@router.post("/fnc-import/{bid}/commit")
def fnc_commit(bid: int, centre_code: str = "NRLDC", db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Create entities in the master DB and login IDs (username from F&C registration number, default password)."""
    if not _coord(user):
        raise HTTPException(403)
    b = db.get(FncImportBatch, bid)
    if b is None or b.status != "PREVIEW":
        raise HTTPException(409)
    centre = db.scalar(select(Centre).where(Centre.code == centre_code))
    created = []
    for r in b.rows_json:
        if r["errors"]:
            continue
        ent = Entity(name=r["Entity Name"], entity_type=r["Entity Type"], sub_category=r["Sub-category"], state=r["State"], centre_id=centre.id,
                     fnc_reg_no=r["Registration No"], gst_no=r["GST No"] or None, pan_no=r["PAN No"] or None,
                     installed_capacity_mw=float(r["Capacity MW"] or 0) or None, sector="PRIVATE")
        db.add(ent)
        db.flush()
        username = r["Registration No"].lower().replace("-", "_")
        temp = random_password()
        u = User(username=username, password_hash=hash_password(temp), full_name=r["Entity Name"], email=r["E-mail"], mobile=r["Mobile"],
                 user_category="EXTERNAL", centre_id=centre.id, entity_id=ent.id, must_change_password=True, is_2fa_enabled=True,
                 last_contact_verified_at=utcnow())
        db.add(u)
        db.flush()
        for code in ("EXTERNAL_USER", "EXT_REGISTRATION", "EXT_FTC"):
            db.add(UserRole(user_id=u.id, role_id=db.scalar(select(Role).where(Role.code == code)).id, centre_id=centre.id))
        notify_users(db, [u], f"Grid-India OMS login created: username {username}. Change password at first login.", module="registration")
        created.append({"entity": ent.name, "username": username, "temp_password": temp})
    b.status = "COMMITTED"
    audit(db, user, "registration", "FNC_IMPORT_COMMITTED", "batch", b.id, new={"created": len(created)})
    db.commit()
    return {"created": created}


# ================================================================== F&C registration application
class RegAppIn(BaseModel):
    category: str
    sub_category: str
    form_data: dict = {}
    is_modified_element: bool = False
    centre_code: str | None = None


@router.post("/applications")
def create_application(body: RegAppIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if body.category not in RE_CATEGORIES:
        raise HTTPException(422, "Unknown category")
    centre = db.scalar(select(Centre).where(Centre.code == (body.centre_code or (user.centre.code if user.centre else "NRLDC"))))
    case = wf.new_case(db, "REG", centre, user, f"Registration: {body.category}/{body.sub_category}", applicant_entity_id=user.entity_id)
    a = RegApplication(case_id=case.id, application_type="FNC_REGISTRATION" if body.category != "COMM_PROVIDER" else "DIRECT_COMM",
                       category=body.category, sub_category=body.sub_category, is_renewable=body.category in ("RE_POWER_PARK", "RE_GEN_STATION", "BESS"),
                       is_modified_element=body.is_modified_element, entity_id=user.entity_id, nodal_centre_id=centre.id,
                       current_centre_id=centre.id, form_data_json=body.form_data)
    db.add(a)
    wf.set_pending(case, "APPLICANT", stage="DRAFT")
    db.commit()
    return app_out(db, a, user)


@router.put("/applications/{aid}/form")
def update_form(aid: int, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    a = _app(db, aid, user)
    case = db.get(WorkflowCase, a.case_id)
    if case.is_locked:
        raise HTTPException(409, "Application is locked after submission until RLDC responds")
    a.form_data_json = {**a.form_data_json, **body}
    db.commit()
    return {"ok": True}


@router.post("/applications/{aid}/documents")
def upload_doc(aid: int, doc_category: str = Form(...), change_note: str = Form(""), file: UploadFile = File(...),
               db: Session = Depends(get_db), user=Depends(get_current_user)):
    a = _app(db, aid, user)
    case = db.get(WorkflowCase, a.case_id)
    requester = is_external(user)
    if requester and case.is_locked:
        raise HTTPException(409, "Locked after submission")
    d = store_upload(db, file=file, module="registration", doc_category=doc_category, owner_ref=f"case:{case.id}", centre_code=case.centre.code,
                     case_id=case.id, user=user, change_note=change_note, visible_to_applicant=requester or doc_category.startswith("LETTER"))
    db.commit()
    return doc_out(d)


@router.post("/applications/{aid}/submit")
def submit(aid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Submit -> locked; e-mail to RLDC coordinators SO-1, SO-2, MO, SCADA, MIS (TS p.91-92 steps 5-6)."""
    a = _app(db, aid, user)
    case = db.get(WorkflowCase, a.case_id)
    if case.is_locked:
        raise HTTPException(409, "Already submitted")
    have = {d["doc_category"] for d in list_docs(db, f"case:{case.id}")}
    missing = [d for d in ("SHEET1_FORM", "UNDERTAKING") if d not in have]
    if missing:
        raise HTTPException(422, "Upload mandatory documents first: " + ", ".join(missing))
    case.is_locked, case.status = True, "SUBMITTED"
    depts = ["SO-1", "SCADA"] if a.is_modified_element else CONSENT_DEPTS
    existing = wf.consents(db, case, "REGISTRATION")
    if existing:
        for r in existing:
            if r.status in ("RETURNED", "REJECTED"):
                r.status, r.remarks = "PENDING", ""
    else:
        wf.open_consents(db, case, "REGISTRATION", [[(d, "GENERAL") for d in depts]])
    wf.add_step(db, case, "Application submitted", user, "SUBMIT", forwarded_to=", ".join(depts))
    wf.set_pending(case, ",".join(depts), stage="DEPT_CONSENT")
    notify_users(db, [u for d in depts for u in wf.users_for(db, case.centre_id, {"DEPT_USER"}, d)],
                 f"Registration {case.case_number} submitted for consent", module="registration", step_code="CASE_SUBMITTED",
                 link=f"/registration/{a.id}", centre_id=case.centre_id)
    db.commit()
    return app_out(db, a, user, full=True)


class ConsentIn(BaseModel):
    decision: str = Field(pattern="^(ACCEPTED|RETURNED|REJECTED)$")
    remarks: str = ""


@router.post("/applications/{aid}/consents/{cid}")
def consent(aid: int, cid: int, body: ConsentIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    a = _app(db, aid, user)
    case = db.get(WorkflowCase, a.case_id)
    wf.record_consent(db, case, "REGISTRATION", cid, user, body.decision, body.remarks)
    state = wf.stage_consent_state(db, case, "REGISTRATION")
    if state == "RETURNED":
        case.is_locked, case.status = False, "RETURNED"
        wf.set_pending(case, "APPLICANT", stage="RETURNED")
        notify_users(db, db.scalars(select(User).where(User.id == case.applicant_user_id)).all(),
                     f"{case.case_number} returned: {body.remarks}", module="registration", step_code="CASE_RETURNED", link=f"/registration/{a.id}")
    elif state == "ALL_ACCEPTED":
        wf.set_pending(case, "REG_COORDINATOR", stage="LETTER")
    db.commit()
    return app_out(db, a, user, full=True)


@router.post("/applications/{aid}/issue-letter")
def issue_letter(aid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Registration Letter PDF with signature image after all consents (TS p.92 steps 14-17)."""
    a = _app(db, aid, user)
    case = db.get(WorkflowCase, a.case_id)
    if not _coord(user, case.centre_id):
        raise HTTPException(403, "Registration Coordinator only")
    if wf.stage_consent_state(db, case, "REGISTRATION") != "ALL_ACCEPTED":
        raise HTTPException(409, "Consents from all departments are required before issuing the letter")
    ent = db.get(Entity, a.entity_id) if a.entity_id else None
    pdf = render_pdf("Registration Letter", "पंजीकरण पत्र", case.case_number,
                     [("Entity", ent.name if ent else ""), ("Category", f"{a.category} / {a.sub_category}"),
                      ("Registered with", case.centre.name_en), ("Regulation", "CERC (Fees & Charges of RLDC) Regulations, 2019"),
                      ("Date", datetime.now().strftime("%d-%m-%Y"))],
                     body=f"This is to certify that registration of {ent.name if ent else 'the applicant'} has been successfully done with {case.centre.code}.",
                     signer=user, signer_role="Registration Coordinator")
    d = store_upload(db, data=pdf, filename="registration_letter.pdf", module="registration", doc_category="LETTER_REGISTRATION",
                     owner_ref=f"case:{case.id}", centre_code=case.centre.code, case_id=case.id, user=user)
    a.reg_letter_doc_id = d.id
    case.status, case.is_locked = "APPROVED", True
    wf.add_step(db, case, "Registration letter issued", user, "APPROVE", signed=True)
    wf.set_pending(case, None, stage="REGISTERED")
    if ent:
        ent.status = "ACTIVE"
    recipients = db.scalars(select(User).where(or_(User.id == case.applicant_user_id, User.entity_id == (a.entity_id or -1)))).all()
    notify_users(db, list(recipients), f"Registration of {ent.name if ent else ''} done - letter attached", module="registration",
                 step_code="LETTER_ISSUED", link=f"/registration/{a.id}")
    audit(db, user, "registration", "LETTER_ISSUED", "application", a.id)
    db.commit()
    return {"ok": True, "letter_doc_id": d.id}


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user=Depends(get_current_user)):
    apps = list_apps(db=db, user=user)
    from collections import Counter

    return {"total": len(apps), "by_status": dict(Counter(a["status"] for a in apps)), "by_type": dict(Counter(a["application_type"] for a in apps)),
            "by_centre": dict(Counter(a["current_centre"] for a in apps)), "by_category": dict(Counter(a["category"] for a in apps))}
