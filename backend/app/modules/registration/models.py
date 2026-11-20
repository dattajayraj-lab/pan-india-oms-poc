"""Registration Module (TS Cl. 11.4.1; FRD REG-*)."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, utcnow


class RegApplication(IdMixin, TimestampMixin, Base):
    __tablename__ = "reg_applications"
    case_id: Mapped[int] = mapped_column(ForeignKey("workflow_cases.id", ondelete="CASCADE"), unique=True)
    # NSWS_CONNECTIVITY | FNC_REGISTRATION | DIRECT_COMM | PRE_REGISTRATION
    application_type: Mapped[str] = mapped_column(String(24))
    category: Mapped[str] = mapped_column(String(30), default="")  # RE_POWER_PARK | RE_GEN_STATION | BESS | CONV | TRANS | COMM
    sub_category: Mapped[str] = mapped_column(String(40), default="")  # SOLAR | WIND | HYBRID:SOLAR+BESS ...
    is_renewable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_modified_element: Mapped[bool] = mapped_column(Boolean, default=False)
    nsws_ref_no: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    nodal_centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"))
    current_centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"))
    processing_started: Mapped[bool] = mapped_column(Boolean, default=False)
    ctu_shared_with_rldc: Mapped[bool] = mapped_column(Boolean, default=False)
    form_data_json: Mapped[dict] = mapped_column(JSON, default=dict)  # Annexure-1 Sheet-1 fields
    compliance_sheet_json: Mapped[dict] = mapped_column(JSON, default=dict)
    conn4_cert_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    reg_letter_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    nsws_last_push_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    files = relationship("RegFileReview", back_populates="application", cascade="all, delete-orphan", lazy="selectin")
    shifts = relationship("RegShiftLog", back_populates="application", cascade="all, delete-orphan", lazy="selectin")


class RegFileReview(IdMixin, TimestampMixin, Base):
    """File-wise review status/comments by CTUIL and RLDC with joint comments (steps 6-13, p.84-85)."""

    __tablename__ = "reg_file_reviews"
    application_id: Mapped[int] = mapped_column(ForeignKey("reg_applications.id", ondelete="CASCADE"), index=True)
    file_category: Mapped[str] = mapped_column(String(60))  # PSCAD_MODEL, PSSE_MODEL, SIM_REPORT ...
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    # UNDER_PROCESSING | RLDC_APPROVED | RLDC_NEEDS_REVISION | CTU_APPROVED | CTU_NEEDS_REVISION
    rldc_status: Mapped[str] = mapped_column(String(24), default="UNDER_PROCESSING")
    ctu_status: Mapped[str] = mapped_column(String(24), default="UNDER_PROCESSING")
    rldc_comment: Mapped[str] = mapped_column(Text, default="")
    ctu_comment: Mapped[str] = mapped_column(Text, default="")
    nldc_comment: Mapped[str] = mapped_column(Text, default="")
    joint_comment: Mapped[str] = mapped_column(Text, default="")
    joint_released: Mapped[bool] = mapped_column(Boolean, default=False)
    requester_change_note: Mapped[str] = mapped_column(Text, default="")
    iteration: Mapped[int] = mapped_column(Integer, default=1)

    application = relationship("RegApplication", back_populates="files")


class RegShiftLog(IdMixin, Base):
    """NLDC workload shifting log (TS p.88)."""

    __tablename__ = "reg_shift_logs"
    application_id: Mapped[int] = mapped_column(ForeignKey("reg_applications.id", ondelete="CASCADE"), index=True)
    from_centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"))
    to_centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"))
    shifted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    shifted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    nldc_comment: Mapped[str] = mapped_column(Text, default="")
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    return_comment: Mapped[str] = mapped_column(Text, default="")

    application = relationship("RegApplication", back_populates="shifts")


class FncImportBatch(IdMixin, Base):
    """Fees & Charges Excel import batches with preview-before-commit (TS p.93; CMN-19)."""

    __tablename__ = "fnc_import_batches"
    entity_type: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str] = mapped_column(String(260))
    rows_json: Mapped[list] = mapped_column(JSON, default=list)
    errors_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(12), default="PREVIEW")  # PREVIEW | COMMITTED | DISCARDED
    imported_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AccountRequest(IdMixin, Base):
    """Self sign-up / user-ID requests pending coordinator validation (TS p.90-91, 93)."""

    __tablename__ = "account_requests"
    username: Mapped[str] = mapped_column(String(80), index=True)
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80), default="")
    additional_names_json: Mapped[list] = mapped_column(JSON, default=list)
    email: Mapped[str] = mapped_column(String(160))
    mobile: Mapped[str] = mapped_column(String(20))
    organisation: Mapped[str] = mapped_column(String(200))
    user_type: Mapped[str] = mapped_column(String(30))  # RE_REGISTRATION | FTC | OUTAGE | COMM ...
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"))
    password_hash: Mapped[str] = mapped_column(String(200))
    nsws_reg_no: Mapped[str] = mapped_column(String(40), default="")
    cea_egen_no: Mapped[str] = mapped_column(String(40), default="")
    fnc_reg_no: Mapped[str] = mapped_column(String(40), default="")
    connectivity_reg_no: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(12), default="PENDING")  # PENDING | APPROVED | REJECTED
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    remarks: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
