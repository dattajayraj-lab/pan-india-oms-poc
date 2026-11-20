"""Group C: Generic workflow cases, steps, checklists (FRD CMN-04, CMN-20, CMN-27)."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, utcnow


class WorkflowCase(IdMixin, TimestampMixin, Base):
    __tablename__ = "workflow_cases"
    case_number: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    module: Mapped[str] = mapped_column(String(30), index=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)
    applicant_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    applicant_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    current_stage: Mapped[str] = mapped_column(String(60), default="DRAFT")
    # DRAFT | SUBMITTED | UNDER_REVIEW | RETURNED | APPROVED | REJECTED | PUBLISHED | CLOSED
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    pending_with_role: Mapped[str | None] = mapped_column(String(60), nullable=True)
    pending_with_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    pending_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    draft_data_json: Mapped[dict] = mapped_column(JSON, default=dict)  # save-draft (CMN-17)

    steps = relationship("WorkflowStep", back_populates="case", cascade="all, delete-orphan",
                         order_by="WorkflowStep.step_order", lazy="selectin")
    centre = relationship("Centre", lazy="joined")


class WorkflowStep(IdMixin, Base):
    __tablename__ = "workflow_steps"
    case_id: Mapped[int] = mapped_column(ForeignKey("workflow_cases.id", ondelete="CASCADE"), index=True)
    step_order: Mapped[int] = mapped_column(Integer)
    step_name: Mapped[str] = mapped_column(String(120))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(160), default="")
    actor_role: Mapped[str] = mapped_column(String(60), default="")
    # SUBMIT | FORWARD | CONSENT | APPROVE | REJECT | RETURN | SHIFT | PUBLISH | COMMENT | PENDING
    action: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(12), default="DONE")  # DONE | PENDING | RETURNED
    forwarded_to: Mapped[str] = mapped_column(String(160), default="")
    remarks: Mapped[str] = mapped_column(Text, default="")
    is_internal_only: Mapped[bool] = mapped_column(Boolean, default=False)
    signature_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    case = relationship("WorkflowCase", back_populates="steps")


class Checklist(IdMixin, Base):
    """Front-end editable checklist template (TS Cl. 11.4.2(e)2, p.104-105)."""

    __tablename__ = "checklists"
    code: Mapped[str] = mapped_column(String(60), unique=True)
    module: Mapped[str] = mapped_column(String(30), index=True)
    element_category: Mapped[str] = mapped_column(String(40), default="*")
    owner_role: Mapped[str] = mapped_column(String(30))  # RLDC | CTUIL | SCADA | METERING | PROTECTION | COORDINATOR
    title: Mapped[str] = mapped_column(String(200))
    # [{"key": "c1", "text_en": "...", "text_hi": "...", "mandatory": true}]
    items_json: Mapped[list] = mapped_column(JSON, default=list)


class ChecklistResponse(IdMixin, Base):
    __tablename__ = "checklist_responses"
    case_id: Mapped[int] = mapped_column(ForeignKey("workflow_cases.id", ondelete="CASCADE"), index=True)
    checklist_id: Mapped[int] = mapped_column(ForeignKey("checklists.id"))
    reviewer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    stage: Mapped[str] = mapped_column(String(40), default="")
    # {"c1": {"state": "TICKED"|"PENDING"|"UNTICKED", "comment": "..."}}
    responses_json: Mapped[dict] = mapped_column(JSON, default=dict)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DeptConsent(IdMixin, TimestampMixin, Base):
    """Parallel departmental consent tracker used by FTC / Registration / Comm Cert."""

    __tablename__ = "dept_consents"
    case_id: Mapped[int] = mapped_column(ForeignKey("workflow_cases.id", ondelete="CASCADE"), index=True)
    stage: Mapped[str] = mapped_column(String(40))
    department: Mapped[str] = mapped_column(String(40))  # SCADA | PROTECTION | METERING | NLDC | SO-1 ...
    level: Mapped[str] = mapped_column(String(20), default="GENERAL")  # GENERAL | HOD
    sequence_group: Mapped[int] = mapped_column(Integer, default=1)  # 1 = parallel, 2.. = sequential chain
    status: Mapped[str] = mapped_column(String(12), default="PENDING")  # PENDING | ACCEPTED | RETURNED | REJECTED
    remarks: Mapped[str] = mapped_column(Text, default="")
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    visible_to_applicant: Mapped[bool] = mapped_column(Boolean, default=False)
