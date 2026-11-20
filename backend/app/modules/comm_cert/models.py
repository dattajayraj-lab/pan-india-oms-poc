"""Communication System Certification (TS Cl. 11.4.3; FRD CC-*)."""
from datetime import date

from sqlalchemy import JSON, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class CommCertApplication(IdMixin, TimestampMixin, Base):
    __tablename__ = "comm_cert_applications"
    case_id: Mapped[int] = mapped_column(ForeignKey("workflow_cases.id", ondelete="CASCADE"), unique=True)
    comm_element_id: Mapped[int] = mapped_column(ForeignKey("comm_elements.id"))
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    scope: Mapped[str] = mapped_column(String(16))  # INTRA_REGIONAL | INTER_REGIONAL | TRANS_NATIONAL
    route: Mapped[str] = mapped_column(String(4), default="C")  # A | B | C consent route (p.123)
    stage: Mapped[int] = mapped_column(Integer, default=1)
    stage_status: Mapped[str] = mapped_column(String(14), default="DRAFT")
    anticipated_sat_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sat_completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    acknowledged_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # [{"entity_id": 3, "name": "NTPC", "status": "PENDING", "remarks": ""}]
    third_party_consents_json: Mapped[list] = mapped_column(JSON, default=list)
    ca_cb_data_json: Mapped[dict] = mapped_column(JSON, default=dict)
    format_ii_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    stage1_cert_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    cert_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    ctuil_sync_status: Mapped[str] = mapped_column(String(12), default="NOT_SYNCED")
