"""Availability Inputs Verification (TS Cl. 11.4.5; FRD AV-*)."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

AVAILABILITY_HEADS = [
    "SELF", "OSPD", "SYSTEM", "OTHERS", "KITE", "OPGW", "OVERFLUX", "GRID_LNCC",
    "CONSTRUCTION", "DIVERSION", "HVDC_SELF", "HVDC_OTHERS", "WEATHER", "DEEMED",
]
# Tabs of the monthly sheet (TS p.177)
SHEET_TABS = {
    "SELF": "Outage_Self", "OSPD": "Outage_OSPD", "SYSTEM": "Outage_System", "OTHERS": "Outage_Others",
    "KITE": "Outage_Kite", "OPGW": "Outage_OPGW", "OVERFLUX": "Outage_Overflux", "GRID_LNCC": "Outage_Grid_LNCC",
    "CONSTRUCTION": "Outage_Construction", "DIVERSION": "Outage_Diversion", "HVDC_SELF": "Outage_HVDC_Self",
    "HVDC_OTHERS": "Outage_HVDC_Others", "WEATHER": "Outage_Others", "DEEMED": "Outage_System",
}


class CategoryCode(Base):
    """39 category codes (TS p.174), extensible."""

    __tablename__ = "availability_category_codes"
    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    description: Mapped[str] = mapped_column(String(300))
    owner_fault: Mapped[bool] = mapped_column(Boolean, default=False)


class AvailabilityRecord(IdMixin, TimestampMixin, Base):
    __tablename__ = "availability_records"
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)
    billing_month: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM (month N)
    outage_code_id: Mapped[int | None] = mapped_column(ForeignKey("outage_codes.id"), nullable=True)
    grid_element_id: Mapped[int] = mapped_column(ForeignKey("grid_elements.id"))
    owner_entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    parent_record_id: Mapped[int | None] = mapped_column(ForeignKey("availability_records.id"), nullable=True)
    is_bifurcated_parent: Mapped[bool] = mapped_column(Boolean, default=False)
    added_by_licensee: Mapped[bool] = mapped_column(Boolean, default=False)
    outage_start: Mapped[datetime] = mapped_column(DateTime)
    outage_end: Mapped[datetime] = mapped_column(DateTime)
    availability_head: Mapped[str] = mapped_column(String(20))
    category_code: Mapped[str] = mapped_column(String(10), default="")
    user_action: Mapped[str] = mapped_column(String(10), default="PENDING")  # PENDING | ACCEPTED | OBJECTED
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    proposed_changes_json: Mapped[dict] = mapped_column(JSON, default=dict)
    stakeholder_comment: Mapped[str] = mapped_column(Text, default="")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_to_protection: Mapped[bool] = mapped_column(Boolean, default=False)
    protection_remarks: Mapped[str] = mapped_column(Text, default="")
    protection_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    rldc_verified_status: Mapped[str] = mapped_column(String(14), default="")  # VERIFIED | NOT_VERIFIED
    rldc_comment: Mapped[str] = mapped_column(Text, default="")
    rpc_status: Mapped[str] = mapped_column(String(14), default="")  # FORWARDED | SENT_BACK | DOWNLOADED

    element = relationship("GridElement", lazy="joined")
