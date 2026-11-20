"""Versioned document store (FRD CMN-10, CMN-21, CMN-23, UM-23, DQ-05).

- Auto-naming: {CENTRE}_{MODULE}_{REF}_{DOC_TYPE}_v{REV}.{ext}  (TS Cl. 11.2(g), 11.4.1 p.86)
- Strict versioning: a new upload for the same (owner_ref, doc_category, end_side) adds v+1; old revisions are never overwritten.
- Allowed extensions per TS Cl. 11.1 / 11.4.6, and .zip blocked where the module forbids dumps (Registration model files).
- scan hook: placeholder for the appliance sandbox (TS Ch.4) — EICAR signature is flagged as INFECTED for demo.
"""
import hashlib
import re
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.dms_files.models import Document

ALLOWED_EXT = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".zip", ".rar", ".dat", ".cfg", ".sav", ".dyr",
               ".sld", ".raw", ".png", ".jpg", ".jpeg", ".gif", ".txt", ".pptx", ".mp4", ".json", ".xml", ".pscx"}
MAX_BYTES = 200 * 1024 * 1024
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
_MAGIC = {".pdf": b"%PDF", ".png": b"\x89PNG", ".zip": b"PK", ".docx": b"PK", ".xlsx": b"PK", ".pptx": b"PK"}


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")[:40] or "NA"


def scan_bytes(data: bytes) -> str:
    """Sandbox hook. Production: submit to the RLDC/NLDC appliance sandbox and await verdict."""
    return "INFECTED" if EICAR in data else "CLEAN"


def store_upload(db: Session, *, file: UploadFile | None = None, data: bytes | None = None, filename: str | None = None,
                 module: str, doc_category: str, owner_ref: str, centre_code: str = "OMS", case_id: int | None = None,
                 user=None, change_note: str = "", is_confidential: bool = False, visible_to_applicant: bool = True,
                 end_side: str = "", block_zip: bool = False, allowed: set[str] | None = None) -> Document:
    if file is not None:
        data = file.file.read()
        filename = file.filename or "upload.bin"
    assert data is not None and filename
    ext = Path(filename).suffix.lower()
    allowed_set = allowed or ALLOWED_EXT
    if ext not in allowed_set:
        raise HTTPException(415, f"File type {ext or '(none)'} not allowed. Allowed: {', '.join(sorted(allowed_set))}")
    if block_zip and ext in (".zip", ".rar"):
        raise HTTPException(415, "Compressed dumps are not accepted; upload each file under its category head")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large")
    magic = _MAGIC.get(ext)
    if magic and data and not data.startswith(magic):
        raise HTTPException(415, f"File content does not match {ext} format")
    verdict = scan_bytes(data)
    if verdict == "INFECTED":
        raise HTTPException(422, "File rejected by sandbox scan (malware signature detected)")

    prev = db.scalars(select(Document).where(Document.owner_ref == owner_ref, Document.doc_category == doc_category,
                                             Document.end_side == end_side).order_by(Document.version_no.desc())).first()
    version = (prev.version_no + 1) if prev else 1
    if prev:
        db.execute(update(Document).where(Document.owner_ref == owner_ref, Document.doc_category == doc_category,
                                          Document.end_side == end_side).values(is_latest=False))
    ref = _slug(owner_ref.split(":")[-1] if ":" in owner_ref else owner_ref)
    auto = f"{centre_code}_{module.upper()}_{ref}_{_slug(doc_category).upper()}{('_' + end_side) if end_side else ''}_v{version}{ext}"
    folder = get_settings().storage_dir / module / _slug(owner_ref)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / auto
    path.write_bytes(data)
    doc = Document(case_id=case_id, module=module, owner_ref=owner_ref, doc_category=doc_category,
                   original_filename=filename, auto_filename=auto, storage_path=str(path),
                   mime_type=getattr(file, "content_type", None) or "application/octet-stream",
                   file_size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), version_no=version,
                   uploaded_by=getattr(user, "id", None), uploader_name=getattr(user, "full_name", "SYSTEM"),
                   change_note=change_note, is_confidential=is_confidential, visible_to_applicant=visible_to_applicant,
                   scan_status=verdict, end_side=end_side)
    db.add(doc)
    db.flush()
    return doc


def doc_out(d: Document) -> dict:
    return {"id": d.id, "doc_category": d.doc_category, "original_filename": d.original_filename,
            "auto_filename": d.auto_filename, "version_no": d.version_no, "is_latest": d.is_latest,
            "file_size_bytes": d.file_size_bytes, "uploader_name": d.uploader_name, "change_note": d.change_note,
            "is_confidential": d.is_confidential, "scan_status": d.scan_status, "end_side": d.end_side,
            "visible_to_applicant": d.visible_to_applicant, "created_at": d.created_at, "sha256": d.sha256[:12]}


def list_docs(db: Session, owner_ref: str, applicant_view: bool = False) -> list[dict]:
    stmt = select(Document).where(Document.owner_ref == owner_ref).order_by(Document.created_at.desc(), Document.id.desc())
    rows = db.scalars(stmt).all()
    return [doc_out(d) for d in rows if not (applicant_view and not d.visible_to_applicant)]
