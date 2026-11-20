"""First Time Charging Module (TS Cl. 11.4.2; FRD FTC-*)."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, utcnow


class FtcApplication(IdMixin, TimestampMixin, Base):
    __tablename__ = "ftc_applications"
    case_id: Mapped[int] = mapped_column(ForeignKey("workflow_cases.id", ondelete="CASCADE"), unique=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    jurisdiction: Mapped[str] = mapped_column(String(6))  # NLDC | RLDC
    cert_jurisdiction: Mapped[str] = mapped_column(String(6), default="RLDC")
    element_category: Mapped[str] = mapped_column(String(20))  # RE_PLANT | NON_RE_PLANT | TRANSMISSION
    stage: Mapped[int] = mapped_column(Integer, default=1)  # 1..5
    # stage_status per stage: DRAFT | SUBMITTED | DEPT_REVIEW | RETURNED | ACCEPTED
    stage_status: Mapped[str] = mapped_column(String(14), default="DRAFT")
    proposed_charging_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_modified_element: Mapped[bool] = mapped_column(Boolean, default=False)
    annexures_data_json: Mapped[dict] = mapped_column(JSON, default=dict)  # {"A1": {...}, "A2": {...}}
    a2_elements_json: Mapped[list] = mapped_column(JSON, default=list)
    created_element_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    format_ii_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    format_tr_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    format_tr_quantum_mw: Mapped[float | None] = mapped_column(Float, nullable=True)
    format_tr_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    format_tr_status: Mapped[str] = mapped_column(String(12), default="NONE")  # NONE | SUBMITTED | APPROVED | RETURNED
    format_iv_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    realtime_access_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    realtime_charging_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pre_certificate_json: Mapped[dict] = mapped_column(JSON, default=dict)
    trial_cert_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    trial_cert_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    doco_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    doco_status: Mapped[str] = mapped_column(String(12), default="NONE")
    doco_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    compliances = relationship("PostCommCompliance", back_populates="ftc", cascade="all, delete-orphan", lazy="selectin")


class PostCommCompliance(IdMixin, TimestampMixin, Base):
    __tablename__ = "post_comm_compliances"
    ftc_application_id: Mapped[int] = mapped_column(ForeignKey("ftc_applications.id", ondelete="CASCADE"), index=True)
    # AS_BUILT_MODEL | FINAL_SLD | POWER_QUALITY | PERIODIC_TEST | UNDERTAKING
    compliance_type: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(300), default="")
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12), default="PENDING")  # PENDING | SUBMITTED | ACCEPTED | REJECTED
    signed_by: Mapped[str] = mapped_column(String(160), default="")
    doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    remarks: Mapped[str] = mapped_column(Text, default="")

    ftc = relationship("FtcApplication", back_populates="compliances")


class StartupPowerRequest(IdMixin, TimestampMixin, Base):
    """Start-up power grant (TS Cl. 11.4.2(e)12, p.115-116)."""

    __tablename__ = "startup_power_requests"
    case_id: Mapped[int] = mapped_column(ForeignKey("workflow_cases.id", ondelete="CASCADE"), unique=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    unit_details: Mapped[str] = mapped_column(String(300), default="")
    quantum_mw: Mapped[float] = mapped_column(Float)
    period_from: Mapped[date] = mapped_column(Date)
    period_to: Mapped[date] = mapped_column(Date)
    granted_quantum_mw: Mapped[float | None] = mapped_column(Float, nullable=True)
    granted_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    granted_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    weekly_updates_json: Mapped[list] = mapped_column(JSON, default=list)
    monthly_energy_json: Mapped[list] = mapped_column(JSON, default=list)
    grant_status: Mapped[str] = mapped_column(String(12), default="APPLIED")  # APPLIED | GRANTED | REJECTED | CLOSED


class FtcIssueLog(IdMixin, Base):
    """Real-time issues flagged to REGS and chronological replies (TS p.114)."""

    __tablename__ = "ftc_issue_logs"
    ftc_application_id: Mapped[int] = mapped_column(ForeignKey("ftc_applications.id", ondelete="CASCADE"), index=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    author_name: Mapped[str] = mapped_column(String(160))
    direction: Mapped[str] = mapped_column(String(10))  # TO_REGS | FROM_REGS
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
