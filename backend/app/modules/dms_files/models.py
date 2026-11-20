"""Versioned document store with auto-naming (FRD CMN-10, CMN-21, UM-23)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, utcnow


class Document(IdMixin, Base):
    __tablename__ = "documents"
    case_id: Mapped[int | None] = mapped_column(ForeignKey("workflow_cases.id"), nullable=True, index=True)
    module: Mapped[str] = mapped_column(String(30), index=True)
    owner_ref: Mapped[str] = mapped_column(String(80), default="", index=True)  # e.g. "ticket:12", "event:3"
    doc_category: Mapped[str] = mapped_column(String(60))  # A1, FORMAT_TR, DR_MAIN1, CONN4 ...
    original_filename: Mapped[str] = mapped_column(String(260))
    auto_filename: Mapped[str] = mapped_column(String(260), index=True)
    storage_path: Mapped[str] = mapped_column(String(400))
    mime_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    uploader_name: Mapped[str] = mapped_column(String(160), default="")
    change_note: Mapped[str] = mapped_column(String(500), default="")
    is_confidential: Mapped[bool] = mapped_column(Boolean, default=False)
    visible_to_applicant: Mapped[bool] = mapped_column(Boolean, default=True)
    scan_status: Mapped[str] = mapped_column(String(12), default="CLEAN")  # PENDING | CLEAN | INFECTED
    end_side: Mapped[str] = mapped_column(String(6), default="")  # END1 | END2 for protection files
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
