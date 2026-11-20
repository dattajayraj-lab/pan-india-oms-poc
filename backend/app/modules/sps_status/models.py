"""SPS Status (TS Cl. 11.4.9; FRD SPS-*)."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, utcnow


class SpsScheme(IdMixin, Base):
    __tablename__ = "sps_schemes"
    sps_id: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    sps_name: Mapped[str] = mapped_column(String(200))
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)
    grid_element_id: Mapped[int | None] = mapped_column(ForeignKey("grid_elements.id"), nullable=True)
    owner_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    logic_description: Mapped[str] = mapped_column(Text, default="")
    template_fields_json: Mapped[dict] = mapped_column(JSON, default=dict)
    current_status: Mapped[str] = mapped_column(String(10), default="ON")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SpsStatusLog(IdMixin, Base):
    __tablename__ = "sps_status_logs"
    sps_scheme_id: Mapped[int] = mapped_column(ForeignKey("sps_schemes.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(10))  # ON | OFF | DEGRADED
    source: Mapped[str] = mapped_column(String(6), default="USER")  # USER | SCADA
    remarks: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
