"""Protection & Tripping Studies (TS Cl. 11.4.6; FRD PT-*)."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin

EVENT_CATEGORIES = ["GI-1", "GI-2", "GD-1", "GD-2", "GD-3", "GD-4", "GD-5", "NEAR_MISS", "SINGLE_TRIP"]


class TrippingEvent(IdMixin, TimestampMixin, Base):
    __tablename__ = "tripping_events"
    event_code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    event_category: Mapped[str] = mapped_column(String(12))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    tripping_report_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    element_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    loss_of_load_mw: Mapped[float | None] = mapped_column(default=None, nullable=True)
    loss_of_gen_mw: Mapped[float | None] = mapped_column(default=None, nullable=True)
    # {"END1": {...FIR fields...}, "END2": {...}} with revision trail kept in fir_history_json
    fir_data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    fir_history_json: Mapped[list] = mapped_column(JSON, default=list)
    flash_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dr_el_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    detailed_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    corrective_required: Mapped[str] = mapped_column(Text, default="")
    corrective_taken: Mapped[str] = mapped_column(Text, default="")
    rldc_validation_status: Mapped[str] = mapped_column(String(14), default="PENDING")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class ProtectionPscRecord(IdMixin, TimestampMixin, Base):
    __tablename__ = "protection_psc_records"
    psc_record_code: Mapped[str] = mapped_column(String(40), unique=True)
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)
    tripping_event_id: Mapped[int] = mapped_column(ForeignKey("tripping_events.id"))
    details: Mapped[str] = mapped_column(Text, default="")
    psc_meeting_no: Mapped[str] = mapped_column(String(20), default="")
    meeting_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recommendations: Mapped[str] = mapped_column(Text, default="")
    mom_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    utility_action_taken: Mapped[str] = mapped_column(Text, default="")
    compliance_status: Mapped[str] = mapped_column(String(14), default="NOT_COMPLIED")  # COMPLIED | PARTIAL | NOT_COMPLIED
    resolved_by_rldc: Mapped[bool] = mapped_column(Boolean, default=False)


class SoprSubmission(IdMixin, Base):
    """Monthly Protection Performance Indices D, S, R (TS 11.4.6(d), p.189-190)."""

    __tablename__ = "sopr_submissions"
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    month: Mapped[str] = mapped_column(String(7))
    dependability: Mapped[float] = mapped_column()
    security: Mapped[float] = mapped_column()
    reliability: Mapped[float] = mapped_column()
    comments: Mapped[str] = mapped_column(Text, default="")
    submitted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime)


class RelaySetting(IdMixin, Base):
    __tablename__ = "relay_settings"
    grid_element_id: Mapped[int] = mapped_column(ForeignKey("grid_elements.id"), index=True)
    relay_slot: Mapped[str] = mapped_column(String(20))  # MAIN1 | MAIN2 | BACKUP
    doc_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime)
