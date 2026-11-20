"""Shared workflow endpoints: tracker, documents, checklists (front-end editable), save draft."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.rbac import get_current_user, is_admin, is_external, role_codes
from app.db.session import get_db
from app.modules.dms_files.service import list_docs
from app.modules.workflow_engine import service as wf
from app.modules.workflow_engine.models import Checklist, WorkflowCase

router = APIRouter(prefix="/api/v1/workflow", tags=["workflow"])


def get_case_for(db: Session, case_id: int, user) -> WorkflowCase:
    c = db.get(WorkflowCase, case_id)
    if c is None:
        raise HTTPException(404, "Case not found")
    if is_external(user):
        same_entity = user.entity_id and c.applicant_entity_id == user.entity_id
        if c.applicant_user_id != user.id and not same_entity and "CTU" not in role_codes(user):
            raise HTTPException(403, "Not your case")
    return c


@router.get("/cases/{case_id}/tracker")
def tracker(case_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = get_case_for(db, case_id, user)
    return wf.tracker(db, c, applicant_view=is_external(user))


@router.get("/cases/{case_id}/documents")
def documents(case_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = get_case_for(db, case_id, user)
    return list_docs(db, f"case:{c.id}", applicant_view=is_external(user))


@router.put("/cases/{case_id}/draft")
def save_draft(case_id: int, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Save entered data and resume after re-login (TS Cl. 11.3(i))."""
    c = get_case_for(db, case_id, user)
    if c.is_locked:
        raise HTTPException(409, "Submitted application is locked")
    c.draft_data_json = {**(c.draft_data_json or {}), **body}
    db.commit()
    return {"ok": True}


@router.get("/checklists")
def list_checklists(module: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(Checklist).order_by(Checklist.module, Checklist.code)
    if module:
        stmt = stmt.where(Checklist.module == module)
    return [wf.checklist_out(c) for c in db.scalars(stmt)]


class ChecklistIn(BaseModel):
    title: str
    items: list[dict]


@router.put("/checklists/{code}")
def edit_checklist(code: str, body: ChecklistIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Checklists are editable from the front end by coordinators/admin (TS p.86, p.104)."""
    if not (is_admin(user) or any(r.endswith("COORDINATOR") for r in role_codes(user))):
        raise HTTPException(403)
    cl = db.scalar(select(Checklist).where(Checklist.code == code))
    if cl is None:
        raise HTTPException(404)
    old = cl.items_json
    cl.title = body.title
    cl.items_json = [{"key": i.get("key") or f"c{n + 1}", "text_en": i["text_en"], "text_hi": i.get("text_hi", ""),
                      "mandatory": i.get("mandatory", True)} for n, i in enumerate(body.items)]
    audit(db, user, cl.module, "CHECKLIST_EDITED", "checklist", code, old={"items": old}, new={"items": cl.items_json})
    db.commit()
    return wf.checklist_out(cl)
