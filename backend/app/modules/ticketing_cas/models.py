"""Complaint Addressal System (TS Ch.5 p.44-49; SLA Cl. 10.6; FRD CAS-*)."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, utcnow


class Ticket(IdMixin, TimestampMixin, Base):
    __tablename__ = "tickets"
    ticket_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)  # establishment escalated to
    module: Mapped[str] = mapped_column(String(30))
    complaint_type: Mapped[str] = mapped_column(String(30), default="ISSUE")  # SYSTEM_ACCESS | ISSUE | NEW_DEVELOPMENT | ...
    channel: Mapped[str] = mapped_column(String(10), default="PORTAL")  # PORTAL | EMAIL | PHONE | WALKIN
    complainant_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    complainant_name: Mapped[str] = mapped_column(String(160), default="")
    complainant_contact: Mapped[str] = mapped_column(String(200), default="")
    logged_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    linked_ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id"), nullable=True)
    priority_requested: Mapped[str] = mapped_column(String(10), default="MEDIUM")  # by stakeholder
    priority: Mapped[str | None] = mapped_column(String(10), nullable=True)  # assessed by AMC
    severity: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1..4, assessed by RLDC/NLDC
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)  # 0..3
    # OPEN | ASSIGNED | IN_PROGRESS | AWAITING_INPUT | RESOLVED | CLOSED | REOPENED
    status: Mapped[str] = mapped_column(String(16), default="OPEN", index=True)
    assigned_team: Mapped[str] = mapped_column(String(60), default="HELPDESK")
    assigned_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    comments: Mapped[str] = mapped_column(Text, default="")
    tags_json: Mapped[list] = mapped_column(JSON, default=list)
    level_entered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    sla_response_due: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sla_resolution_due: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0)
    feedback_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_text: Mapped[str] = mapped_column(Text, default="")

    history = relationship("TicketHistory", back_populates="ticket", cascade="all, delete-orphan",
                           order_by="TicketHistory.created_at", lazy="selectin")
    centre = relationship("Centre", lazy="joined")


class TicketHistory(IdMixin, Base):
    __tablename__ = "ticket_history"
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(160), default="SYSTEM")
    event: Mapped[str] = mapped_column(String(30))  # CREATED, ASSESSED, ESCALATED, COMMENT, RESOLVED ...
    from_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="")
    comment: Mapped[str] = mapped_column(Text, default="")
    attachment_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    ticket = relationship("Ticket", back_populates="history")


class KnowledgeBaseArticle(IdMixin, TimestampMixin, Base):
    """FAQ / knowledge base built from tickets (TS Ch.5 p.44)."""

    __tablename__ = "kb_articles"
    module: Mapped[str] = mapped_column(String(30))
    question_en: Mapped[str] = mapped_column(String(400))
    question_hi: Mapped[str] = mapped_column(String(400), default="")
    answer_en: Mapped[str] = mapped_column(Text)
    answer_hi: Mapped[str] = mapped_column(Text, default="")
    source_ticket_id: Mapped[int | None] = mapped_column(ForeignKey("tickets.id"), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)


class DowntimeEvent(IdMixin, Base):
    """APM-logged downtime / approved maintenance used for monthly availability (TS Cl. 10.6)."""

    __tablename__ = "downtime_events"
    kind: Mapped[str] = mapped_column(String(12))  # DOWNTIME | MAINTENANCE | EXCLUDED
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(String(300), default="")
