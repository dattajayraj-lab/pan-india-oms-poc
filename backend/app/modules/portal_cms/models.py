"""Common web portal content (TS Cl. 11.2(a)-(j); FRD CMS-*)."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin, utcnow


class PortalContent(IdMixin, TimestampMixin, Base):
    __tablename__ = "portal_content_i18n"
    # NOTICE | FLASHER | BANNER | POST | FAQ | GALLERY | HELP | FORM
    content_type: Mapped[str] = mapped_column(String(12), index=True)
    acronym: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    centre_id: Mapped[int | None] = mapped_column(ForeignKey("centres.id"), nullable=True)
    module: Mapped[str] = mapped_column(String(30), default="portal")
    title_en: Mapped[str] = mapped_column(String(300))
    title_hi: Mapped[str] = mapped_column(String(300), default="")
    body_en: Mapped[str] = mapped_column(Text, default="")
    body_hi: Mapped[str] = mapped_column(Text, default="")
    body_format: Mapped[str] = mapped_column(String(6), default="TEXT")  # TEXT | HTML
    attachment_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    link_url: Mapped[str] = mapped_column(String(400), default="")
    # DRAFT -> SUBMITTED -> PUBLISHED (verify & publish, TS Cl. 11.1 / Fig.12)
    workflow_state: Mapped[str] = mapped_column(String(12), default="DRAFT")
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    audience: Mapped[str] = mapped_column(String(12), default="PUBLIC")  # PUBLIC | REGISTERED | INTERNAL
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MenuItem(IdMixin, Base):
    """Nested, admin-managed navigation (TS Cl. 11.1 Menu Management; 11.2(a) Navbar)."""

    __tablename__ = "menu_items"
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("menu_items.id"), nullable=True)
    label_en: Mapped[str] = mapped_column(String(120))
    label_hi: Mapped[str] = mapped_column(String(120), default="")
    icon: Mapped[str] = mapped_column(String(40), default="")
    # INTERNAL route, POST acronym, EXTERNAL url (shows redirection warning)
    target_type: Mapped[str] = mapped_column(String(10), default="INTERNAL")
    target: Mapped[str] = mapped_column(String(300), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    location: Mapped[str] = mapped_column(String(10), default="NAVBAR")  # NAVBAR | FOOTER
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Feedback(IdMixin, Base):
    """Customer Feedback & Suggestions (TS Cl. 11.2(i), p.80)."""

    __tablename__ = "feedback"
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), default="")
    organisation: Mapped[str] = mapped_column(String(160), default="")
    category: Mapped[str] = mapped_column(String(30), default="SUGGESTION")
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text)
    extra_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
