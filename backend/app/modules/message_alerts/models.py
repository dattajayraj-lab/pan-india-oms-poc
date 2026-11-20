"""Message Alerts (TS Cl. 11.4.8; FRD MA-*)."""
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, utcnow


class MessageTemplate(IdMixin, Base):
    __tablename__ = "message_templates"
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name_en: Mapped[str] = mapped_column(String(160))
    name_hi: Mapped[str] = mapped_column(String(160), default="")
    category: Mapped[str] = mapped_column(String(10), default="STATE")  # STATE | RE_GEN | MISC
    severity: Mapped[str] = mapped_column(String(10), default="ALERT")  # ALERT | EMERGENCY | EXTREME
    # Python str.format template, e.g. "{utility}: frequency {frequency} Hz ..."
    sms_template: Mapped[str] = mapped_column(Text)
    email_subject: Mapped[str] = mapped_column(String(300))
    email_template: Mapped[str] = mapped_column(Text)
    fields_json: Mapped[list] = mapped_column(JSON, default=list)  # [{"key","label","type","options"}]


class ViolationMessage(IdMixin, Base):
    __tablename__ = "violation_messages"
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)
    category: Mapped[str] = mapped_column(String(10))
    template_code: Mapped[str] = mapped_column(String(40))
    target_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    target_label: Mapped[str] = mapped_column(String(200), default="")
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    rendered_sms: Mapped[str] = mapped_column(Text, default="")
    rendered_email: Mapped[str] = mapped_column(Text, default="")
    channels_json: Mapped[list] = mapped_column(JSON, default=list)
    recipients_count: Mapped[int] = mapped_column(Integer, default=0)
    sent_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(10), default="VIOLATION")  # VIOLATION | FLASH | BULK
