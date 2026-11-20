"""Document download (with OTP gate for confidential files), filename search, directory (FRD UI-01, UM-23, CMN-06)."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.rbac import get_current_user, is_external
from app.db.session import get_db
from app.modules.auth_rbac import service as auth_svc
from app.modules.dms_files.models import Document
from app.modules.dms_files.service import doc_out

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.get("/search")
def search(q: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    like = f"%{q}%"
    rows = db.scalars(select(Document).where(or_(Document.auto_filename.ilike(like), Document.original_filename.ilike(like)),
                                             Document.is_latest).order_by(Document.created_at.desc()).limit(100)).all()
    if is_external(user):
        rows = [d for d in rows if d.visible_to_applicant and not d.is_confidential]
    return [doc_out(d) for d in rows]


@router.get("/{doc_id}/versions")
def versions(doc_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    d = db.get(Document, doc_id)
    if d is None:
        raise HTTPException(404)
    rows = db.scalars(select(Document).where(Document.owner_ref == d.owner_ref, Document.doc_category == d.doc_category,
                                             Document.end_side == d.end_side).order_by(Document.version_no.desc())).all()
    return [doc_out(x) for x in rows]


@router.post("/{doc_id}/otp")
def confidential_otp(doc_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Confidential documents need an OTP before view/download (TS Cl. 11.1 p.76)."""
    out = auth_svc.issue_otp(db, user, "CONFIDENTIAL_DOC")
    db.commit()
    return out


@router.get("/{doc_id}/download")
def download(doc_id: int, challenge_id: str | None = None, otp: str | None = None,
             db: Session = Depends(get_db), user=Depends(get_current_user)):
    d = db.get(Document, doc_id)
    if d is None:
        raise HTTPException(404, "Document not found")
    if is_external(user) and not d.visible_to_applicant:
        raise HTTPException(403, "Not visible to applicant")
    if d.is_confidential:
        if not challenge_id or not otp:
            raise HTTPException(428, "Confidential document: OTP verification required")
        auth_svc.consume_otp(db, challenge_id, otp, "CONFIDENTIAL_DOC")
    audit(db, user, d.module, "DOCUMENT_DOWNLOADED", "document", d.id, new={"file": d.auto_filename})
    db.commit()
    if not Path(d.storage_path).exists():
        raise HTTPException(410, "File missing from storage")
    return FileResponse(d.storage_path, filename=d.auto_filename)
