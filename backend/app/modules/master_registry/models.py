"""Group B: Master registry of entities, substations and grid elements.

Single master database shared by all modules (TS Cl. 11.4.6 'Database
Synchronization', p.182; FRD GEN-03, RTO-15..20).
"""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, utcnow

# 22 element types of TS Table 8 (p.136-145) + communication types handled separately.
ELEMENT_TYPES = {
    "AC_LINE": ("TL", "AC Transmission Line Circuit"),
    "BAY": ("BY", "Bay"),
    "BUS_REACTOR": ("BR", "Bus Reactor / BSR / MSC / MSR"),
    "BUS": ("BS", "Bus"),
    "FILTER_BANK": ("FB", "Filter Bank"),
    "SUB_FILTER_BANK": ("SF", "Sub-filter Bank"),
    "FSC": ("FS", "Fixed Series Capacitor"),
    "GEN_UNIT": ("GU", "Generating Unit"),
    "HVDC_POLE": ("HP", "HVDC Pole"),
    "HVDC_LINE": ("HL", "HVDC Line Circuit"),
    "LINE_REACTOR": ("LR", "Line Reactor"),
    "SVC_STATCOM": ("SC", "SVC / STATCOM"),
    "TCSC": ("TC", "TCSC"),
    "ICT": ("IT", "Transformer Type 1 (ICT)"),
    "STATION_TRANSFORMER": ("ST", "Transformer Type 2 (Station Transformer)"),
    "COUPLING_TRANSFORMER": ("CT", "Transformer Type 3 (Coupling)"),
    "GENERATOR_TRANSFORMER": ("GT", "Transformer Type 4 (Generator Transformer)"),
    "IBR_TRANSFORMER": ("IB", "Transformer Type 5 (Inverter-based)"),
    "GEN_STATION": ("GS", "Generating Station Type 1 (Conventional/RE)"),
    "PSP_STATION": ("PS", "Generating Station Type 2 (Pumped Storage)"),
    "BESS_STATION": ("ES", "Generating Station Type 3 (BESS)"),
    "SOLAR_ICR_BLOCK": ("SB", "Solar ICR / Inverter Block"),
    "WTG": ("WT", "Wind Turbine Generator"),
}

ELEMENT_STATUSES = ["IN_SERVICE", "OUTAGE", "TRIPPED", "PRE_COMMISSIONING", "DECOMMISSIONED"]


class Entity(IdMixin, TimestampMixin, Base):
    __tablename__ = "entities"
    name: Mapped[str] = mapped_column(String(200), index=True)
    short_name: Mapped[str] = mapped_column(String(40), default="")
    # REGS | CONV_GEN | TRANS_LICENSEE | COMM_PROVIDER | BULK_CONSUMER | SLDC | CTU | RPC
    entity_type: Mapped[str] = mapped_column(String(20), index=True)
    # SOLAR | WIND | HYBRID | BESS | PSP | THERMAL | HYDRO | GAS | NUCLEAR | ...
    sub_category: Mapped[str] = mapped_column(String(20), default="")
    sector: Mapped[str] = mapped_column(String(20), default="CENTRAL")  # CENTRAL | STATE | PRIVATE
    state: Mapped[str] = mapped_column(String(40), default="")
    centre_id: Mapped[int | None] = mapped_column(ForeignKey("centres.id"), nullable=True)
    nsws_reg_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    cea_egen_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fnc_reg_no: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    gst_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    pan_no: Mapped[str | None] = mapped_column(String(12), nullable=True)
    address: Mapped[str] = mapped_column(Text, default="")
    installed_capacity_mw: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")

    contacts = relationship("EntityContact", back_populates="entity", cascade="all, delete-orphan")


class EntityOwnershipHistory(IdMixin, Base):
    """REGS ownership/name changes, applied only after Admin approval (TS Cl. 11.1, p.76)."""

    __tablename__ = "entity_ownership_history"
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    previous_owner: Mapped[str] = mapped_column(String(200))
    new_owner: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING | APPROVED | REJECTED
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remarks: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class EntityContact(IdMixin, Base):
    """Contact directory (TS Cl. 11.4.8 p.201-202; Cl. 11.1 telephone directory)."""

    __tablename__ = "entity_contacts"
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    designation: Mapped[str] = mapped_column(String(80), default="")
    organisation: Mapped[str] = mapped_column(String(160), default="")
    department: Mapped[str] = mapped_column(String(60), default="")
    location: Mapped[str] = mapped_column(String(80), default="")
    category: Mapped[str] = mapped_column(String(20), default="MISC")  # STATE | RE_GEN | MISC
    phone1: Mapped[str] = mapped_column(String(20), default="")
    phone1_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    phone2: Mapped[str] = mapped_column(String(20), default="")
    phone2_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    email1: Mapped[str] = mapped_column(String(160), default="")
    email1_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    email2: Mapped[str] = mapped_column(String(160), default="")
    email2_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # {"ALERT": true, "EMERGENCY": true, "EXTREME": false}
    alert_sms_flags_json: Mapped[dict] = mapped_column(JSON, default=dict)
    alert_email_flags_json: Mapped[dict] = mapped_column(JSON, default=dict)

    entity = relationship("Entity", back_populates="contacts")


class Substation(IdMixin, TimestampMixin, Base):
    __tablename__ = "substations"
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"))
    state: Mapped[str] = mapped_column(String(40), default="")
    voltage_levels_json: Mapped[list] = mapped_column(JSON, default=list)
    substation_type: Mapped[str] = mapped_column(String(10), default="AIS")  # AIS | GIS | HVDC
    bus_scheme: Mapped[str] = mapped_column(String(60), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_area: Mapped[str] = mapped_column(String(60), default="")
    owner_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    is_pooling_station: Mapped[bool] = mapped_column(Boolean, default=False)

    centre = relationship("Centre", lazy="joined")
    owner = relationship("Entity", lazy="joined")


class GridElement(IdMixin, TimestampMixin, Base):
    __tablename__ = "grid_elements"
    unique_element_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    element_type: Mapped[str] = mapped_column(String(30), index=True)
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)
    voltage_kv: Mapped[float] = mapped_column(Float, default=400)
    from_substation_id: Mapped[int | None] = mapped_column(ForeignKey("substations.id"), nullable=True)
    to_substation_id: Mapped[int | None] = mapped_column(ForeignKey("substations.id"), nullable=True)
    is_inter_regional: Mapped[bool] = mapped_column(Boolean, default=False)
    is_trans_national: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ists: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="IN_SERVICE", index=True)
    rating: Mapped[str] = mapped_column(String(60), default="")
    length_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    ftc_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cod_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    decommission_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_status_change_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    source_ftc_case_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    realtime_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # Append-only operator notes (TS Table 8 note, p.145) — list of {by, at, text}
    operator_notes_append_only_json: Mapped[list] = mapped_column(JSON, default=list)
    operator_comments: Mapped[str] = mapped_column(Text, default="")

    centre = relationship("Centre", lazy="joined")
    from_substation = relationship("Substation", foreign_keys=[from_substation_id], lazy="joined")
    to_substation = relationship("Substation", foreign_keys=[to_substation_id], lazy="joined")
    owners = relationship("ElementOwner", back_populates="element", cascade="all, delete-orphan", lazy="selectin")


class ElementOwner(IdMixin, Base):
    """Multiple ownership incl. section-wise line ownership (TS Table 8 note, p.136-137)."""

    __tablename__ = "element_owners"
    grid_element_id: Mapped[int] = mapped_column(ForeignKey("grid_elements.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    # LINE_OWNER | END1_STATION | END2_STATION | SECTION_OWNER | ASSET_OWNER
    ownership_role: Mapped[str] = mapped_column(String(20))
    section_km: Mapped[float | None] = mapped_column(Float, nullable=True)

    element = relationship("GridElement", back_populates="owners")
    entity = relationship("Entity", lazy="joined")


class CommElement(IdMixin, TimestampMixin, Base):
    """Communication inventory (TS Cl. 11.4.3, p.120)."""

    __tablename__ = "comm_elements"
    unique_comm_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    comm_type: Mapped[str] = mapped_column(String(20))  # OPGW | FOTE | AUX_POWER | STATE_CSP
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"))
    from_station: Mapped[str] = mapped_column(String(160), default="")
    to_station: Mapped[str] = mapped_column(String(160), default="")
    owner_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PRE_COMMISSIONING")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ElementIdSequence(IdMixin, Base):
    """Sequence counters for Unique Element IDs and Case IDs."""

    __tablename__ = "id_sequences"
    key: Mapped[str] = mapped_column(String(80), unique=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
