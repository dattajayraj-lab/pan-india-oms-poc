"""MIS & Reporting (TS Cl. 11.4.10, Ch.9; FRD MIS-*)."""
from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class ReportTemplate(IdMixin, TimestampMixin, Base):
    """Non-hard-coded report definition (TS Ch.9 p.59; Cl. 11.4.10 p.208).

    query_config_json = {"source": "<dataset key>", "filters": {...}, "group_by": [...],
                         "aggregates": [{"field": "...", "fn": "sum|count|avg"}]}
    columns_json      = [{"key": "...", "label_en": "...", "label_hi": "..."}]
    """

    __tablename__ = "report_templates"
    code: Mapped[str] = mapped_column(String(60), unique=True)
    module: Mapped[str] = mapped_column(String(30), index=True)
    name_en: Mapped[str] = mapped_column(String(200))
    name_hi: Mapped[str] = mapped_column(String(200), default="")
    query_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    columns_json: Mapped[list] = mapped_column(JSON, default=list)
    chart_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    schedule_cron: Mapped[str] = mapped_column(String(60), default="")
    distribution_emails_json: Mapped[list] = mapped_column(JSON, default=list)
    is_standard: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class ChartDefinition(IdMixin, Base):
    """Graph catalogue: 30 initial graphs per module (TS Cl. 11.2(e), Table 6)."""

    __tablename__ = "chart_definitions"
    code: Mapped[str] = mapped_column(String(60), unique=True)
    module: Mapped[str] = mapped_column(String(30), index=True)
    title_en: Mapped[str] = mapped_column(String(200))
    title_hi: Mapped[str] = mapped_column(String(200), default="")
    chart_type: Mapped[str] = mapped_column(String(10))  # line | bar | pie | stacked | area
    dataset: Mapped[str] = mapped_column(String(60))
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    menu_assignment: Mapped[str] = mapped_column(String(60), default="")
