"""Generic workflow engine used by Registration, FTC and Communication Certification.

- Cases with numbered steps (full time-stamped history) and a pending pointer (pending-with role/user/since)
- Configurable consent *groups*: departments inside a group act in parallel; group N+1 opens only when
  group N has fully accepted (TS Cl. 11.4.2(e)8 p.111-112: SCADA/Protection/Metering in parallel, then
  Sub-Head SO -> Head SO -> Head RLDC in sequence).
- Front-end editable checklists: every mandatory item must be TICKED, or marked PENDING with a comment
  to allow escalation (TS Cl. 11.4.2(e)2 p.104-105; FRD CMN-27).
- Tracker nodes for the graphical case flowchart (TS Cl. 11.3(m); FRD CMN-20).
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import is_admin, role_codes
from app.db.base import utcnow
from app.modules.auth_rbac.models import Centre, User
from app.modules.workflow_engine.models import Checklist, ChecklistResponse, DeptConsent, WorkflowCase, WorkflowStep
from app.utils.ids import case_number

DEPT_LABEL = {"SCADA": "SCADA", "PROTECTION": "Protection", "METERING": "Metering", "NLDC": "NLDC",
              "SO-1": "SO-1", "SO-2": "SO-2", "MO": "Market Operation", "MIS": "MIS", "SUB_HEAD_SO": "Sub-Head SO",
              "HEAD_SO": "Head of System Operation", "HEAD_RLDC": "Head of RLDC", "HEAD_NLDC": "Head of NLDC",
              "REG_COORDINATOR": "Registration Coordinator"}


def new_case(db: Session, module: str, centre: Centre, applicant: User | None, title: str,
             applicant_entity_id: int | None = None) -> WorkflowCase:
    c = WorkflowCase(case_number=case_number(db, module, centre.code), module=module, title=title, centre_id=centre.id,
                     applicant_user_id=getattr(applicant, "id", None), applicant_entity_id=applicant_entity_id,
                     current_stage="DRAFT", status="DRAFT")
    db.add(c)
    db.flush()
    add_step(db, c, "Case created (draft)", applicant, "CREATE")
    return c


def add_step(db: Session, case: WorkflowCase, name: str, user, action: str, remarks: str = "", status: str = "DONE",
             forwarded_to: str = "", internal: bool = False, signed: bool = False) -> WorkflowStep:
    order = (max((s.step_order for s in case.steps), default=0) + 1) if case.steps else 1
    s = WorkflowStep(case_id=case.id, step_order=order, step_name=name, actor_user_id=getattr(user, "id", None),
                     actor_name=getattr(user, "full_name", "SYSTEM"), actor_role=",".join(sorted(role_codes(user))) if user else "",
                     action=action, status=status, forwarded_to=forwarded_to, remarks=remarks,
                     is_internal_only=internal, signature_applied=signed)
    db.add(s)
    case.steps.append(s)
    db.flush()
    return s


def set_pending(case: WorkflowCase, role: str | None, user_id: int | None = None, stage: str | None = None,
                status: str | None = None) -> None:
    case.pending_with_role, case.pending_with_user_id, case.pending_since = role, user_id, utcnow()
    if stage:
        case.current_stage = stage
    if status:
        case.status = status


# ------------------------------------------------------------------ consents
def open_consents(db: Session, case: WorkflowCase, stage: str, groups: list[list[tuple[str, str]]]) -> None:
    """groups = [[(dept, level), ...], [...]]; earlier pending rows for the stage are reset."""
    for row in db.scalars(select(DeptConsent).where(DeptConsent.case_id == case.id, DeptConsent.stage == stage)):
        db.delete(row)
    db.flush()
    for gi, group in enumerate(groups, start=1):
        for dept, level in group:
            db.add(DeptConsent(case_id=case.id, stage=stage, department=dept, level=level, sequence_group=gi))
    db.flush()


def consents(db: Session, case: WorkflowCase, stage: str) -> list[DeptConsent]:
    return db.scalars(select(DeptConsent).where(DeptConsent.case_id == case.id, DeptConsent.stage == stage)
                      .order_by(DeptConsent.sequence_group, DeptConsent.id)).all()


def active_group(rows: list[DeptConsent]) -> int | None:
    for g in sorted({r.sequence_group for r in rows}):
        if any(r.status != "ACCEPTED" for r in rows if r.sequence_group == g):
            return g
    return None


def _dept_and_centre(dept: str, case: WorkflowCase) -> tuple[str, int | None, str | None]:
    if "@" in dept:
        d, cc = dept.split("@", 1)
        return d, None, cc
    return dept, case.centre_id, None


def can_act_on(user: User, row: DeptConsent, case: WorkflowCase) -> bool:
    if is_admin(user):
        return True
    codes = role_codes(user)
    dept, centre_id, centre_code = _dept_and_centre(row.department, case)
    if centre_code is not None:
        if not user.centre or user.centre.code != centre_code:
            return False
    elif dept not in ("NLDC", "HEAD_NLDC") and user.centre_id != centre_id:
        return False
    if dept == "NLDC":
        return "NLDC_USER" in codes
    if dept in ("SUB_HEAD_SO", "HEAD_SO", "HEAD_RLDC", "HEAD_NLDC"):
        return dept in codes
    if row.level == "HOD":
        return "HOD" in codes and user.department == dept
    return bool(codes & {"DEPT_USER", "HOD"}) and user.department == dept


def record_consent(db: Session, case: WorkflowCase, stage: str, consent_id: int, user: User, decision: str,
                   remarks: str = "") -> DeptConsent:
    rows = consents(db, case, stage)
    row = next((r for r in rows if r.id == consent_id), None)
    if row is None:
        raise HTTPException(404, "Consent item not found")
    if row.status != "PENDING":
        raise HTTPException(409, "Consent already recorded")
    if row.sequence_group != active_group(rows):
        raise HTTPException(409, "This consent step is not open yet (earlier sequential step pending)")
    if not can_act_on(user, row, case):
        raise HTTPException(403, f"Only {DEPT_LABEL.get(row.department, row.department)} ({row.level}) can act on this step")
    if decision not in ("ACCEPTED", "RETURNED", "REJECTED"):
        raise HTTPException(422, "Decision must be ACCEPTED, RETURNED or REJECTED")
    if decision != "ACCEPTED" and not remarks.strip():
        raise HTTPException(422, "Remarks are mandatory when returning or rejecting")
    row.status, row.remarks, row.actor_user_id = decision, remarks, user.id
    add_step(db, case, f"{DEPT_LABEL.get(row.department.split('@')[0], row.department)} {row.level.lower()} consent: {decision}",
             user, "CONSENT" if decision == "ACCEPTED" else "RETURN", remarks, internal=True)
    nxt = active_group(rows)
    if decision == "ACCEPTED" and nxt and nxt != row.sequence_group:
        pending = [r for r in rows if r.sequence_group == nxt]
        set_pending(case, ",".join(r.department for r in pending))
    return row


def stage_consent_state(db: Session, case: WorkflowCase, stage: str) -> str:
    rows = consents(db, case, stage)
    if not rows:
        return "NONE"
    if any(r.status in ("RETURNED", "REJECTED") for r in rows):
        return "RETURNED"
    if all(r.status == "ACCEPTED" for r in rows):
        return "ALL_ACCEPTED"
    return "PENDING"


def consent_out(r: DeptConsent, user: User | None = None, case: WorkflowCase | None = None, rows=None) -> dict:
    out = {"id": r.id, "stage": r.stage, "department": r.department,
           "label": DEPT_LABEL.get(r.department.split("@")[0], r.department) + (f" ({r.department.split('@')[1]})" if "@" in r.department else ""),
           "level": r.level, "group": r.sequence_group, "status": r.status, "remarks": r.remarks, "updated_at": r.updated_at}
    if user is not None and case is not None:
        out["can_act"] = r.status == "PENDING" and r.sequence_group == active_group(rows or []) and can_act_on(user, r, case)
    return out


# ------------------------------------------------------------------ checklists
def validate_checklist(db: Session, case: WorkflowCase, code: str, responses: dict, user: User, stage: str) -> dict:
    cl = db.scalar(select(Checklist).where(Checklist.code == code))
    if cl is None:
        raise HTTPException(404, f"Checklist {code} not configured")
    missing, pending = [], []
    for item in cl.items_json:
        r = responses.get(item["key"], {})
        state = r.get("state", "UNTICKED")
        if state == "PENDING":
            if not (r.get("comment") or "").strip():
                raise HTTPException(422, f"Item '{item['text_en']}' marked Pending needs a comment")
            pending.append(item["text_en"])
        elif state != "TICKED" and item.get("mandatory", True):
            missing.append(item["text_en"])
    if missing:
        raise HTTPException(422, "All checklist items must be ticked or marked Pending with comments: " + "; ".join(missing))
    db.add(ChecklistResponse(case_id=case.id, checklist_id=cl.id, reviewer_user_id=user.id, stage=stage, responses_json=responses))
    return {"pending_items": pending}


def checklist_out(cl: Checklist) -> dict:
    return {"id": cl.id, "code": cl.code, "module": cl.module, "element_category": cl.element_category,
            "owner_role": cl.owner_role, "title": cl.title, "items": cl.items_json}


# ------------------------------------------------------------------ tracker
def tracker(db: Session, case: WorkflowCase, applicant_view: bool = False) -> list[dict]:
    nodes = []
    for s in case.steps:
        if applicant_view and s.is_internal_only:
            continue
        nodes.append({"key": f"s{s.id}", "label": s.step_name, "state": "RETURNED" if s.action in ("RETURN", "REJECT") else "DONE",
                      "at": s.created_at, "by": s.actor_name, "remarks": s.remarks, "forwarded_to": s.forwarded_to})
    if case.status not in ("APPROVED", "CLOSED", "REJECTED", "PUBLISHED"):
        nodes.append({"key": "pending", "label": f"Pending: {case.pending_with_role or 'applicant'}", "state": "PENDING",
                      "at": case.pending_since, "by": case.pending_with_role or "Applicant", "remarks": case.current_stage})
    return nodes[-14:]


def case_out(c: WorkflowCase) -> dict:
    return {"id": c.id, "case_number": c.case_number, "module": c.module, "title": c.title, "centre": c.centre.code,
            "current_stage": c.current_stage, "status": c.status, "pending_with_role": c.pending_with_role,
            "pending_since": c.pending_since, "is_locked": c.is_locked, "created_at": c.created_at, "updated_at": c.updated_at,
            "applicant_user_id": c.applicant_user_id, "applicant_entity_id": c.applicant_entity_id}


def users_for(db: Session, centre_id: int, roles: set[str], department: str | None = None) -> list[User]:
    out = []
    for u in db.scalars(select(User).where(User.is_active)).all():
        if {r.role.code for r in u.roles} & roles and (u.centre_id == centre_id or "NLDC_USER" in roles):
            if department is None or u.department == department:
                out.append(u)
    return out
