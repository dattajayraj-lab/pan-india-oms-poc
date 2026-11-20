"""Real-Time Outage Management (TS Cl. 11.4.4; FRD RTO-*)."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, utcnow

SHIFT_ORDER = ["MORNING", "EVENING", "NIGHT"]

REQUEST_CATEGORIES = [
    "PLANNED", "FORCED", "EMERGENCY", "TRIPPED", "FTC", "ANTI_THEFT", "AR_OFF", "SUO_MOTO",
    "SPS_TEST", "HOT_LINE", "TAP_CHANGE", "HV_CODE", "LV_CODE", "RE_MVAR", "OPPORTUNITY",
    "BREAKDOWN", "OTHER_ELEMENT", "MINOR_ALTERATION", "AGC", "PHYSICAL_REGULATION",
]

# TS Table 9 (p.151): 23 suo-moto cases. True => fetch bus voltage from SCADA (p.151).
SUO_MOTO_CASES = {
    1: ("HV line Open and Close", True), 2: ("Bus Reactor Open and Close", True),
    3: ("L/R Reactor Open and Close", True), 4: ("HVDC power flow and direction (+, -)", False),
    5: ("Line open and close for load management", False), 6: ("ICT Open and Close for load management", False),
    7: ("Mode of the solar plant", True), 8: ("STATCOM/MSR/TSC/SVC/Capacitor Bank operation", True),
    9: ("Operate feeder under physical regulation to control frequency", False), 10: ("ICT Tap changing", True),
    11: ("HVDC pole block/de-block", False), 12: ("FSC switching", False),
    13: ("Synchronous Condenser operation", False), 14: ("SPS operation", False), 15: ("Filter Bank", True),
    16: ("MVAR injection to STATCOM and solar plant", True), 17: ("Infirm power (MW quantum)", False),
    18: ("Physical regulation", False), 19: ("Trial-run", False), 20: ("Closing/opening of interconnectors", False),
    21: ("Testing only for solar plants during non-solar hours", False),
    22: ("Shifting of unit from one bus to other bus in generating station", False),
    23: ("Group selection of ISGS thermal plant for maximisation of generation", False),
}


class Shift(IdMixin, Base):
    __tablename__ = "shifts"
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)
    shift_date: Mapped[date] = mapped_column(Date)
    shift_type: Mapped[str] = mapped_column(String(8))  # MORNING | EVENING | NIGHT
    shift_incharge_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    # [{"user_id": 4, "name": "...", "desk": "RTSD"}]
    assigned_staff_json: Mapped[list] = mapped_column(JSON, default=list)
    # [{"key": "r1", "text": "...", "done": false}]
    regular_works_checklist_json: Mapped[list] = mapped_column(JSON, default=list)
    handover_notes: Mapped[str] = mapped_column(Text, default="")
    important_events: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(8), default="OPEN")  # OPEN | CLOSED
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    report_status: Mapped[str] = mapped_column(String(8), default="NONE")  # NONE | DRAFT | FINAL
    report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    report_finalised_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    incharge = relationship("User", lazy="joined")


class OutageCodeRequest(IdMixin, TimestampMixin, Base):
    __tablename__ = "outage_code_requests"
    request_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id"), nullable=True)
    occ_plan_id: Mapped[int | None] = mapped_column(ForeignKey("occ_outage_plans.id"), nullable=True)
    grid_element_id: Mapped[int | None] = mapped_column(ForeignKey("grid_elements.id"), nullable=True)
    other_element_desc: Mapped[str] = mapped_column(String(300), default="")
    requester_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    requester_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    request_category: Mapped[str] = mapped_column(String(20), index=True)
    action: Mapped[str] = mapped_column(String(10), default="OPENING")  # OPENING | CHARGING
    suo_moto_case_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anti_theft_case: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 | 2 | 3
    # requested | consent_pending | remarks_pending | consent_approved | approved | disapproved | code_issued | closed
    status: Mapped[str] = mapped_column(String(18), default="REQUESTED", index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    remarks: Mapped[str] = mapped_column(Text, default="")
    availability_head_proposed: Mapped[str] = mapped_column(String(30), default="")
    constraint_type: Mapped[str] = mapped_column(String(30), default="")
    protection_details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)  # e.g. RE MVAr values
    planned_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_on_behalf_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    element = relationship("GridElement", lazy="joined")
    consents = relationship("OutageConsent", back_populates="request", cascade="all, delete-orphan", lazy="selectin")
    codes = relationship("OutageCode", back_populates="request", lazy="selectin")


class OutageConsent(IdMixin, Base):
    __tablename__ = "outage_consents"
    code_request_id: Mapped[int] = mapped_column(ForeignKey("outage_code_requests.id", ondelete="CASCADE"), index=True)
    stakeholder_entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    stakeholder_role: Mapped[str] = mapped_column(String(20), default="")  # LINE_OWNER | END1 | END2 | INFO
    for_information_only: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(10), default="PENDING")  # PENDING | APPROVED | REJECTED
    rldc_remarks: Mapped[str] = mapped_column(Text, default="")
    remarks: Mapped[str] = mapped_column(Text, default="")
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    request = relationship("OutageCodeRequest", back_populates="consents")
    entity = relationship("Entity", lazy="joined")


class OutageCode(IdMixin, TimestampMixin, Base):
    __tablename__ = "outage_codes"
    code_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    code_request_id: Mapped[int | None] = mapped_column(ForeignKey("outage_code_requests.id"), nullable=True)
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)
    shift_id: Mapped[int] = mapped_column(ForeignKey("shifts.id"))
    grid_element_id: Mapped[int | None] = mapped_column(ForeignKey("grid_elements.id"), nullable=True)
    issued_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    issued_by_name: Mapped[str] = mapped_column(String(160), default="")
    issued_to_json: Mapped[list] = mapped_column(JSON, default=list)  # entity ids/names
    code_type: Mapped[str] = mapped_column(String(10))  # OUTAGE | CHARGING | REVIVAL | OPERATION
    description: Mapped[str] = mapped_column(Text, default="")
    tags_json: Mapped[list] = mapped_column(JSON, default=list)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_reason: Mapped[str] = mapped_column(String(120), default="")
    end1_exec_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end1_entered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end2_exec_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end2_entered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    final_exec_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exec_overridden_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    expected_revival_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scada_voltage_kv: Mapped[float | None] = mapped_column(Float, nullable=True)
    pre_alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    action_not_taken_alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    # reporting software sync ids (TS p.146-147)
    reporting_outage_event_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    request = relationship("OutageCodeRequest", back_populates="codes")
    element = relationship("GridElement", lazy="joined")


class TrippingReport(IdMixin, TimestampMixin, Base):
    """Tripping notification by user logins (TS Cl. 11.4.4(12), p.161-162)."""

    __tablename__ = "tripping_reports"
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)
    grid_element_id: Mapped[int] = mapped_column(ForeignKey("grid_elements.id"))
    reported_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    substation_name: Mapped[str] = mapped_column(String(160), default="")
    relay_flags: Mapped[str] = mapped_column(Text, default="")
    tripped_at: Mapped[datetime] = mapped_column(DateTime)
    reason: Mapped[str] = mapped_column(Text, default="")
    expected_revival_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    element = relationship("GridElement", lazy="joined")


class ReasonListItem(IdMixin, Base):
    """Pre-defined reason list; additions require Shift In-charge (TS 14(c), p.164)."""

    __tablename__ = "reason_list"
    text: Mapped[str] = mapped_column(String(200), unique=True)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ElogEntry(IdMixin, Base):
    """Control-room e-logbook entries (grid events, grid ops messages, curtailment, tech orders)."""

    __tablename__ = "elog_entries"
    centre_id: Mapped[int] = mapped_column(ForeignKey("centres.id"), index=True)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(20))  # GRID_EVENT | GRID_OPS | CURTAILMENT | TECH_ORDER | STOA | NOTE
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    entity_name: Mapped[str] = mapped_column(String(200), default="")
    doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class ScadaAlert(IdMixin, Base):
    """Feed of SCADA / weather alerts shown in the control room ticker (mock adapters)."""

    __tablename__ = "scada_alerts"
    centre_id: Mapped[int | None] = mapped_column(ForeignKey("centres.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(10))  # SCADA | WEATHER
    area: Mapped[str] = mapped_column(String(60), default="")
    severity: Mapped[str] = mapped_column(String(10), default="INFO")
    message: Mapped[str] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
