"""Outage Coordination System (TS Cl. 11.4.7; FRD OC-*)."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin


class OccOutagePlan(IdMixin, TimestampMixin, Base):
    __tablename__ = "occ_outage_plans"
    reference_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)
    occ_number: Mapped[str] = mapped_column(String(20), default="")
    target_month: Mapped[str] = mapped_column(String(7), default="")  # YYYY-MM (M+2 for OCC)
    plan_route: Mapped[str] = mapped_column(String(10))  # OCC_M2 | D3 | D2 | EMERGENCY | NON_AUTO
    grid_element_id: Mapped[int] = mapped_column(ForeignKey("grid_elements.id"))
    requester_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    requester_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    owner_name: Mapped[str] = mapped_column(String(200), default="")
    req_from: Mapped[datetime] = mapped_column(DateTime)
    req_to: Mapped[datetime] = mapped_column(DateTime)
    approved_from: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    daily_or_continuous: Mapped[str] = mapped_column(String(10), default="CONTINUOUS")
    request_type: Mapped[str] = mapped_column(String(30), default="MAINTENANCE")
    reason: Mapped[str] = mapped_column(Text, default="")
    requester_remarks: Mapped[str] = mapped_column(Text, default="")
    availability_comments: Mapped[str] = mapped_column(Text, default="")
    availability_head_proposed: Mapped[str] = mapped_column(String(30), default="")
    availability_head_rldc: Mapped[str] = mapped_column(String(30), default="")
    category_code: Mapped[str] = mapped_column(String(10), default="")
    share_availability_with_occ: Mapped[bool] = mapped_column(Boolean, default=True)
    is_inter_regional: Mapped[bool] = mapped_column(Boolean, default=False)
    nldc_status: Mapped[str] = mapped_column(String(12), default="NA")  # NA | PENDING | CONSENTED | APPROVED
    non_auto_ar: Mapped[bool] = mapped_column(Boolean, default=False)  # "(Req. for AR)"
    # SUBMITTED | RPC_FORWARDED | RLDC_REVIEW | OCC_APPROVED | OCC_REJECTED | D3_APPLIED | D1_APPROVED | D1_REJECTED | DEFERRED
    status: Mapped[str] = mapped_column(String(14), default="SUBMITTED", index=True)
    rpc_remarks: Mapped[str] = mapped_column(Text, default="")
    rldc_comments: Mapped[str] = mapped_column(Text, default="")
    d1_comment_coordinator: Mapped[str] = mapped_column(Text, default="")
    d1_comment_hod: Mapped[str] = mapped_column(Text, default="")
    d1_comment_head: Mapped[str] = mapped_column(Text, default="")
    study_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    weather_alert: Mapped[str] = mapped_column(String(300), default="")
    stakeholders_json: Mapped[list] = mapped_column(JSON, default=list)  # pre-defined checklist of stakeholders
    action_flags_json: Mapped[list] = mapped_column(JSON, default=list)  # two-executive flags
    change_requests_json: Mapped[list] = mapped_column(JSON, default=list)

    element = relationship("GridElement", lazy="joined")
