"""Communication System Certification (TS Cl. 11.4.3 p.119-126; FRD CC-01..16)."""
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.rbac import get_current_user, is_admin, is_external, role_codes, sees_all_centres
from app.db.base import utcnow
from app.db.session import get_db
from app.integrations.notifier import notify_users
from app.modules.auth_rbac.models import Centre, User
from app.modules.comm_cert.models import CommCertApplication
from app.modules.dms_files.service import doc_out, list_docs, store_upload
from app.modules.master_registry.models import CommElement, Entity
from app.modules.workflow_engine import service as wf
from app.modules.workflow_engine.models import WorkflowCase
from app.utils.certificates import render_pdf

router = APIRouter(prefix="/api/v1/comm-cert", tags=["communication-certification"])
STAGES = {1: {"name": "Stage 1 - Intimation & trial run (CA-annexures)", "annexures": ["CA1", "CA2", "CA3", "CA4", "CA5", "OTHER"],
              "required": ["CA1", "CA2", "CA3", "CA4", "CA5"]},
          2: {"name": "Stage 2 - Commercial operation (CB-annexures)", "annexures": ["CB1", "CB2", "CB3", "CB4", "SAT_REPORT", "OTHER"],
              "required": ["CB1", "CB2", "CB3", "CB4", "SAT_REPORT"]}}
LABELS = {"CA1": "Intimation of anticipated commissioning", "CA2": "Equipment list & capacity", "CA3": "Proposed link connectivity",
          "CA4": "Channel diagram (telemetry/voice) with redundancy", "CA5": "Approval details of links", "CB1": "Request for commercial operation",
          "CB2": "Terminal equipment undertaking", "CB3": "Telemetry & voice undertaking", "CB4": "SAT completion undertaking",
          "SAT_REPORT": "Site Acceptance Test report", "OTHER": "Other supporting documents"}


def _coord(user, centre_id=None) -> bool:
    return is_admin(user) or ("COMM_COORDINATOR" in role_codes(user) and (centre_id is None or sees_all_centres(user) or user.centre_id == centre_id))


def _get(db: Session, aid: int, user):
    a = db.get(CommCertApplication, aid)
    if a is None:
        raise HTTPException(404)
    case = db.get(WorkflowCase, a.case_id)
    third_party = any(tp.get("entity_id") == user.entity_id for tp in a.third_party_consents_json)
    if is_external(user) and a.entity_id != user.entity_id and not third_party:
        raise HTTPException(403)
    return a, case


def groups(a: CommCertApplication, other_centre: str | None) -> list[list[tuple[str, str]]]:
    g = [[("SCADA", "GENERAL")], [("SCADA", "HOD")]]
    if a.route in ("A", "B") and other_centre:
        g += [[(f"SCADA@{other_centre}", "GENERAL")], [(f"SCADA@{other_centre}", "HOD")]]
    if a.route == "B":
        g += [[("SCADA@NLDC", "GENERAL")], [("SCADA@NLDC", "HOD")]]
    if a.stage == 2:
        g += [[("HEAD_RLDC", "GENERAL")]]
    return g


def out(db: Session, a: CommCertApplication, case: WorkflowCase, user, full=False) -> dict:
    el = db.get(CommElement, a.comm_element_id)
    o = {**wf.case_out(case), "app_id": a.id, "scope": a.scope, "route": a.route, "stage": a.stage, "stage_name": STAGES[a.stage]["name"],
         "stage_status": a.stage_status, "element": el.name, "comm_type": el.comm_type, "unique_comm_id": el.unique_comm_id,
         "element_status": el.status, "entity": db.get(Entity, a.entity_id).name, "anticipated_sat_date": a.anticipated_sat_date,
         "acknowledged_on": a.acknowledged_on, "ctuil_sync_status": a.ctuil_sync_status}
    if full:
        requester = is_external(user)
        rows = wf.consents(db, case, f"STAGE{a.stage}")
        o.update({"third_party_consents": a.third_party_consents_json, "documents": list_docs(db, f"case:{case.id}", applicant_view=requester),
                  "consents": [] if requester else [wf.consent_out(r, user, case, rows) for r in rows],
                  "tracker": wf.tracker(db, case, applicant_view=requester), "is_coordinator": _coord(user, case.centre_id),
                  "stages": [{"no": k, "name": v["name"], "annexures": [{"code": x, "label": LABELS[x], "required": x in v["required"]} for x in v["annexures"]]}
                             for k, v in STAGES.items()],
                  "can_sign_stage1": a.stage_status == "AWAITING_SIGNATURE" and a.stage == 1 and ("HOD" in role_codes(user) and user.department == "SCADA" or is_admin(user)),
                  "can_sign_stage2": a.stage_status == "AWAITING_SIGNATURE" and a.stage == 2 and ("HEAD_RLDC" in role_codes(user) or is_admin(user)),
                  "my_third_party": next((tp for tp in a.third_party_consents_json if tp.get("entity_id") == user.entity_id), None)})
    return o


@router.get("/cases")
def list_cases(db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(CommCertApplication).order_by(CommCertApplication.id.desc())
    rows = db.scalars(stmt).all()
    res = []
    for a in rows:
        case = db.get(WorkflowCase, a.case_id)
        if is_external(user) and a.entity_id != user.entity_id and not any(tp.get("entity_id") == user.entity_id for tp in a.third_party_consents_json):
            continue
        if not is_external(user) and not sees_all_centres(user) and case.centre_id != user.centre_id:
            continue
        res.append(out(db, a, case, user))
    return res


@router.get("/cases/{aid}")
def get_case(aid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    a, case = _get(db, aid, user)
    return out(db, a, case, user, full=True)


class NewIn(BaseModel):
    comm_element_id: int
    scope: str = Field(pattern="^(INTRA_REGIONAL|INTER_REGIONAL|TRANS_NATIONAL)$")
    anticipated_sat_date: date


@router.post("/cases")
def create(body: NewIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    el = db.get(CommElement, body.comm_element_id)
    if el is None:
        raise HTTPException(404)
    if is_external(user) and el.owner_entity_id != user.entity_id:
        raise HTTPException(403, "Element not owned by your organisation")
    if (body.anticipated_sat_date - utcnow().date()).days < 7:
        raise HTTPException(422, "Intimation must be at least 7 days before the anticipated SAT/integration date (TS p.121)")
    centre = db.get(Centre, el.centre_id)
    case = wf.new_case(db, "COMM", centre, user, f"Comm certification: {el.name}", applicant_entity_id=el.owner_entity_id)
    a = CommCertApplication(case_id=case.id, comm_element_id=el.id, entity_id=el.owner_entity_id, scope=body.scope,
                            route="B" if body.scope != "INTRA_REGIONAL" else "C", anticipated_sat_date=body.anticipated_sat_date)
    db.add(a)
    wf.set_pending(case, "APPLICANT", stage="STAGE1_DRAFT")
    db.commit()
    return out(db, a, case, user)


@router.post("/cases/{aid}/documents")
def upload(aid: int, doc_category: str = Form(...), file: UploadFile = File(...), change_note: str = Form(""),
           db: Session = Depends(get_db), user=Depends(get_current_user)):
    a, case = _get(db, aid, user)
    if is_external(user) and case.is_locked:
        raise HTTPException(409, "Locked after submission")
    d = store_upload(db, file=file, module="comm_cert", doc_category=doc_category, owner_ref=f"case:{case.id}", centre_code=case.centre.code,
                     case_id=case.id, user=user, change_note=change_note, visible_to_applicant=not doc_category.startswith("RLDC_"))
    db.commit()
    return doc_out(d)


@router.post("/cases/{aid}/submit")
def submit(aid: int, sat_completed_date: date | None = Form(None), db: Session = Depends(get_db), user=Depends(get_current_user)):
    a, case = _get(db, aid, user)
    have = {d["doc_category"] for d in list_docs(db, f"case:{case.id}")}
    missing = [x for x in STAGES[a.stage]["required"] if x not in have]
    if missing:
        raise HTTPException(422, "Upload: " + ", ".join(missing))
    if a.stage == 2:
        if not sat_completed_date:
            raise HTTPException(422, "SAT completion date required")
        if (utcnow().date() - sat_completed_date).days > 7:
            raise HTTPException(422, "Certification request must be within 7 days of SAT completion (TS p.122)")
        a.sat_completed_date = sat_completed_date
    case.is_locked, case.status, a.stage_status = True, "SUBMITTED", "SUBMITTED"
    wf.add_step(db, case, f"{STAGES[a.stage]['name']} submitted", user, "SUBMIT")
    wf.set_pending(case, "COMM_COORDINATOR", stage=f"STAGE{a.stage}_COORD")
    notify_users(db, wf.users_for(db, case.centre_id, {"COMM_COORDINATOR"}), f"{case.case_number} submitted", module="comm_cert",
                 step_code="CASE_FORWARDED", link=f"/comm-cert/{a.id}", centre_id=case.centre_id)
    db.commit()
    return out(db, a, case, user, full=True)


class ThirdPartyIn(BaseModel):
    entity_ids: list[int]


@router.post("/cases/{aid}/third-party")
def add_third_party(aid: int, body: ThirdPartyIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Consent from third parties at the other end (IPP, other licensee, NTPC...) before acknowledgement (TS p.122)."""
    a, case = _get(db, aid, user)
    if not _coord(user, case.centre_id):
        raise HTTPException(403)
    cur = {tp["entity_id"] for tp in a.third_party_consents_json}
    a.third_party_consents_json = [*a.third_party_consents_json, *[
        {"entity_id": e, "name": db.get(Entity, e).name, "status": "PENDING", "remarks": ""} for e in body.entity_ids if e not in cur]]
    for e in body.entity_ids:
        notify_users(db, db.scalars(select(User).where(User.entity_id == e)).all(), f"Consent requested on {case.case_number}",
                     module="comm_cert", link=f"/comm-cert/{a.id}")
    wf.add_step(db, case, "Third-party consent requested", user, "FORWARD", ", ".join(db.get(Entity, e).name for e in body.entity_ids))
    db.commit()
    return out(db, a, case, user, full=True)


@router.post("/cases/{aid}/third-party/respond")
def third_party_respond(aid: int, approve: bool = Form(...), remarks: str = Form(""), db: Session = Depends(get_db), user=Depends(get_current_user)):
    a, case = _get(db, aid, user)
    items = [dict(x) for x in a.third_party_consents_json]
    tp = next((x for x in items if x["entity_id"] == user.entity_id), None)
    if tp is None:
        raise HTTPException(403)
    tp["status"], tp["remarks"] = ("APPROVED" if approve else "REJECTED"), remarks
    a.third_party_consents_json = items
    wf.add_step(db, case, f"Third-party consent by {tp['name']}: {tp['status']}", user, "CONSENT", remarks)
    db.commit()
    return out(db, a, case, user, full=True)


class CoordIn(BaseModel):
    action: str = Field(pattern="^(ACKNOWLEDGE|FORWARD|RETURN|ACCEPT)$")
    remarks: str = ""
    route: str | None = Field(None, pattern="^(A|B|C)$")
    other_centre: str | None = None
    checklist: dict = {}


@router.post("/cases/{aid}/coordinator")
def coordinator(aid: int, body: CoordIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    a, case = _get(db, aid, user)
    if not _coord(user, case.centre_id):
        raise HTTPException(403)
    stage_key = f"STAGE{a.stage}"
    if body.action == "ACKNOWLEDGE":
        if any(tp["status"] != "APPROVED" for tp in a.third_party_consents_json):
            raise HTTPException(409, "Third-party consents pending")
        a.acknowledged_on = utcnow().date()
        pdf = render_pdf("Format II - Acknowledgement of certificate requisition", "फॉर्मेट II - प्रमाणपत्र मांग की पावती", case.case_number,
                         [("Element", db.get(CommElement, a.comm_element_id).name), ("Scope", a.scope), ("Acknowledged on", a.acknowledged_on)],
                         signer=user, signer_role="Communication Coordinator")
        d = store_upload(db, data=pdf, filename="Format_II.pdf", module="comm_cert", doc_category="FORMAT_II", owner_ref=f"case:{case.id}",
                         centre_code=case.centre.code, case_id=case.id, user=user)
        a.format_ii_doc_id = d.id
        wf.add_step(db, case, "Receipt acknowledged (Format II)", user, "APPROVE", body.remarks)
    elif body.action == "RETURN":
        case.is_locked, case.status, a.stage_status = False, "RETURNED", "RETURNED"
        wf.add_step(db, case, "Returned to applicant", user, "RETURN", body.remarks)
        wf.set_pending(case, "APPLICANT", stage=f"{stage_key}_RETURNED")
    elif body.action == "FORWARD":
        if a.stage == 1 and not a.acknowledged_on:
            raise HTTPException(409, "Acknowledge receipt (Format II) first")
        if body.route:
            a.route = body.route
        if body.checklist:
            wf.validate_checklist(db, case, "COMM_CA_COORD", body.checklist, user, stage_key)
        g = groups(a, body.other_centre)
        wf.open_consents(db, case, stage_key, g)
        case.status, a.stage_status = "UNDER_REVIEW", "DEPT_REVIEW"
        wf.add_step(db, case, f"Forwarded for consent (route {a.route})", user, "FORWARD", body.remarks, forwarded_to=" -> ".join(x[0][0] for x in g))
        wf.set_pending(case, g[0][0][0], stage=f"{stage_key}_CONSENT")
    else:
        if wf.stage_consent_state(db, case, stage_key) != "ALL_ACCEPTED":
            raise HTTPException(409, "All consents required")
        el = db.get(CommElement, a.comm_element_id)
        title = ("Certificate of successful trial run - communication equipment", "संचार उपकरण के सफल ट्रायल रन का प्रमाणपत्र") if a.stage == 1 else \
                ("Format III - Certificate for commercial operation of communication system", "फॉर्मेट III - संचार प्रणाली के वाणिज्यिक प्रचालन हेतु प्रमाणपत्र")
        pdf = render_pdf(title[0], title[1], case.case_number, [("Element", el.name), ("ID", el.unique_comm_id), ("Scope", a.scope)], draft=True)
        d = store_upload(db, data=pdf, filename=f"Comm_Cert_Stage{a.stage}.pdf", module="comm_cert", doc_category=f"CERT_STAGE{a.stage}",
                         owner_ref=f"case:{case.id}", centre_code=case.centre.code, case_id=case.id, user=user, visible_to_applicant=False)
        if a.stage == 1:
            a.stage1_cert_doc_id = d.id
        else:
            a.cert_doc_id = d.id
        a.stage_status = "AWAITING_SIGNATURE"
        signer = "HOD SCADA" if a.stage == 1 else "HEAD_RLDC"
        wf.add_step(db, case, f"Certificate auto-prepared; awaiting digital signature by {signer}", user, "APPROVE", internal=True)
        wf.set_pending(case, signer, stage=f"{stage_key}_SIGNATURE")
    audit(db, user, "comm_cert", f"COORDINATOR_{body.action}", "case", case.case_number)
    db.commit()
    return out(db, a, case, user, full=True)


class ConsentIn(BaseModel):
    decision: str = Field(pattern="^(ACCEPTED|RETURNED)$")
    remarks: str = ""


@router.post("/cases/{aid}/consents/{cid}")
def consent(aid: int, cid: int, body: ConsentIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    a, case = _get(db, aid, user)
    wf.record_consent(db, case, f"STAGE{a.stage}", cid, user, body.decision, body.remarks)
    if wf.stage_consent_state(db, case, f"STAGE{a.stage}") in ("RETURNED", "ALL_ACCEPTED"):
        wf.set_pending(case, "COMM_COORDINATOR")
    db.commit()
    return out(db, a, case, user, full=True)


@router.post("/cases/{aid}/sign")
def sign(aid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Stage 1 certificate signed by Head of SCADA; Stage 2 (Format III) by Head of RLDC (TS p.123-125)."""
    a, case = _get(db, aid, user)
    if a.stage_status != "AWAITING_SIGNATURE":
        raise HTTPException(409)
    codes = role_codes(user)
    ok = is_admin(user) or (a.stage == 1 and "HOD" in codes and user.department == "SCADA") or (a.stage == 2 and "HEAD_RLDC" in codes)
    if not ok:
        raise HTTPException(403, "Head of SCADA signs Stage 1; Head of RLDC signs Stage 2")
    el = db.get(CommElement, a.comm_element_id)
    title = ("Certificate of successful trial run - communication equipment", "संचार उपकरण के सफल ट्रायल रन का प्रमाणपत्र") if a.stage == 1 else \
            ("Format III - Certificate for commercial operation of communication system", "फॉर्मेट III - संचार प्रणाली के वाणिज्यिक प्रचालन हेतु प्रमाणपत्र")
    pdf = render_pdf(title[0], title[1], case.case_number, [("Element", el.name), ("ID", el.unique_comm_id), ("Scope", a.scope),
                                                            ("SAT completed", a.sat_completed_date)],
                     signer=user, signer_role="Head of SCADA" if a.stage == 1 else f"Head of {case.centre.code}")
    d = store_upload(db, data=pdf, filename=f"Comm_Cert_Stage{a.stage}_signed.pdf", module="comm_cert", doc_category=f"CERT_STAGE{a.stage}",
                     owner_ref=f"case:{case.id}", centre_code=case.centre.code, case_id=case.id, user=user)
    wf.add_step(db, case, f"Stage {a.stage} certificate digitally signed and released", user, "APPROVE", signed=True)
    if a.stage == 1:
        a.stage1_cert_doc_id = d.id
        a.stage, a.stage_status = 2, "DRAFT"
        case.is_locked, case.status = False, "APPROVED"
        wf.set_pending(case, "APPLICANT", stage="STAGE2_DRAFT")
    else:
        a.cert_doc_id, a.stage_status = d.id, "ACCEPTED"
        case.status, case.is_locked = "CLOSED", True
        el.status = "IN_SERVICE"
        a.ctuil_sync_status = "SYNCED"  # mock push to CTUIL Communication Outage Planning software (TS p.125)
        wf.set_pending(case, None, stage="COMPLETED")
    notify_users(db, [db.get(User, case.applicant_user_id)], f"{case.case_number}: certificate issued", module="comm_cert", link=f"/comm-cert/{a.id}")
    db.commit()
    return out(db, a, case, user, full=True)
