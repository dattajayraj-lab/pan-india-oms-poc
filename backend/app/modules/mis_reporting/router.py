"""MIS & Reporting (TS Cl. 11.4.10 p.206-215, Ch.9 p.59, Cl. 2.7; FRD MIS-01..11, BI-01, CMS-11/12)."""
import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core import scheduler
from app.core.audit import audit
from app.core.rbac import can_access, get_current_user, is_admin, role_codes
from app.db.base import utcnow
from app.db.session import get_db
from app.integrations.notifier import send_raw
from app.modules.mis_reporting import catalog
from app.modules.mis_reporting.models import ChartDefinition, ReportTemplate
from app.utils.dt import utc_to_ist
from app.utils.exports import export

router = APIRouter(prefix="/api/v1/mis", tags=["mis"])

HI = {"count": "संख्या", "month": "माह", "centre": "केंद्र", "status": "स्थिति", "owner": "स्वामी", "category": "श्रेणी", "type": "प्रकार",
      "unit": "इकाई", "plant": "संयंत्र", "fuel": "ईंधन", "location": "स्थान", "hours": "घंटे", "outage_hours": "आउटेज घंटे", "ens_mwh": "ईएनएस (मेगावाट-घंटा)",
      "installed_mw": "स्थापित क्षमता (मेगावाट)", "stage": "चरण", "module": "मॉड्यूल", "severity": "गंभीरता", "head": "शीर्ष"}


def cols_for(rows: list[dict]) -> list[tuple[str, str, str]]:
    keys = list(rows[0].keys()) if rows else ["count"]
    return [(k, k.replace("_", " ").title(), HI.get(k, HI.get(k.split("_")[-1], ""))) for k in keys]


def _mis(user):
    if not (can_access(user, "mis") or is_admin(user)):
        raise HTTPException(403)


def run_template(db: Session, cfg: dict, from_date: str | None = None, to_date: str | None = None) -> list[dict]:
    src = cfg.get("source", "")
    if src == "special:npmc":
        return npmc_rows(db)
    if src == "special:gen_outage":
        f0 = datetime.fromisoformat(from_date) if from_date else None
        f1 = datetime.fromisoformat(to_date) if to_date else None
        rows = catalog.gen_outage(db, f0, f1)
        gb = cfg.get("group_by") or []
        if gb and gb != ["unit"]:
            acc: dict = {}
            for r in rows:
                k = r[gb[0]]
                a = acc.setdefault(k, {gb[0]: k, "installed_mw": 0.0, "outage_hours": 0.0, "ens_mwh": 0.0})
                a["installed_mw"] += r["installed_mw"]
                a["outage_hours"] += r["outage_hours"]
                a["ens_mwh"] += r["ens_mwh"]
            rows = [{k: round(v, 2) if isinstance(v, float) else v for k, v in a.items()} for a in acc.values()]
        return rows
    if src not in catalog.DATASETS:
        raise HTTPException(422, f"Unknown data source {src}")
    rows = catalog.run_query(db, cfg)
    if (from_date or to_date) and rows and "month" in rows[0]:
        rows = [r for r in rows if (not from_date or r["month"] >= from_date[:7]) and (not to_date or r["month"] <= to_date[:7])]
    return rows


def npmc_rows(db: Session) -> list[dict]:
    from app.modules.master_registry.models import GridElement
    from app.modules.realtime_outage.models import OutageCode, TrippingReport

    out = []
    for u in db.scalars(select(GridElement).where(GridElement.element_type == "GEN_UNIT", GridElement.status.in_(["OUTAGE", "TRIPPED"]))):
        trip = db.scalar(select(TrippingReport).where(TrippingReport.grid_element_id == u.id).order_by(TrippingReport.id.desc()))
        code = db.scalar(select(OutageCode).where(OutageCode.grid_element_id == u.id).order_by(OutageCode.id.desc()))
        exp = (code.expected_revival_time if code and code.expected_revival_time else None) or (trip.expected_revival_at if trip else None)
        out.append({"unit": u.name, "plant": (u.metadata_json or {}).get("plant", ""), "installed_mw": (u.metadata_json or {}).get("installed_mw"),
                    "fuel": (u.metadata_json or {}).get("fuel", ""), "owner": ", ".join(o.entity.short_name for o in u.owners),
                    "outage_since": u.last_status_change_at.strftime("%d-%m-%Y %H:%M"), "type": "FORCED" if u.status == "TRIPPED" else "PLANNED",
                    "reason": trip.reason if trip else "", "expected_revival": exp.strftime("%d-%m-%Y %H:%M") if exp else ""})
    return out


@router.get("/meta")
def meta(user=Depends(get_current_user)):
    return {"datasets": {k: {"group_by": v, "numeric": ["count"] + catalog.NUMERIC.get(k, [])} for k, v in catalog.GROUPABLE.items()},
            "special": ["special:npmc", "special:gen_outage"], "functions": ["sum", "count", "avg", "min", "max"]}


def tpl_out(t: ReportTemplate) -> dict:
    return {"id": t.id, "code": t.code, "module": t.module, "name_en": t.name_en, "name_hi": t.name_hi, "query_config": t.query_config_json,
            "chart_config": t.chart_config_json, "schedule_cron": t.schedule_cron, "distribution_emails": t.distribution_emails_json, "is_standard": t.is_standard}


@router.get("/templates")
def templates(module: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(ReportTemplate).order_by(ReportTemplate.module, ReportTemplate.code)
    if module:
        stmt = stmt.where(ReportTemplate.module == module)
    return [tpl_out(t) for t in db.scalars(stmt) if can_access(user, t.module if t.module != "mis" else "mis") or is_admin(user)]


class TemplateIn(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9_]{3,60}$")
    module: str = "mis"
    name_en: str
    name_hi: str = ""
    query_config: dict
    chart_config: dict = {}
    schedule_cron: str = ""
    distribution_emails: list[str] = []


@router.post("/templates")
def create_template(body: TemplateIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Ad-hoc / new report templates created from the front end without code (TS p.59, p.208)."""
    _mis(user)
    if db.scalar(select(ReportTemplate).where(ReportTemplate.code == body.code)):
        raise HTTPException(409, "Template code exists")
    run_template(db, body.query_config)  # validate
    t = ReportTemplate(code=body.code, module=body.module, name_en=body.name_en, name_hi=body.name_hi, query_config_json=body.query_config,
                       chart_config_json=body.chart_config, schedule_cron=body.schedule_cron, distribution_emails_json=body.distribution_emails,
                       is_standard=False, created_by=user.id)
    db.add(t)
    audit(db, user, "mis", "TEMPLATE_CREATED", "report_template", body.code, new=body.model_dump())
    db.commit()
    return tpl_out(t)


@router.put("/templates/{code}")
def update_template(code: str, body: TemplateIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    _mis(user)
    t = db.scalar(select(ReportTemplate).where(ReportTemplate.code == code))
    if t is None:
        raise HTTPException(404)
    run_template(db, body.query_config)
    t.name_en, t.name_hi, t.query_config_json, t.chart_config_json = body.name_en, body.name_hi, body.query_config, body.chart_config
    t.schedule_cron, t.distribution_emails_json = body.schedule_cron, body.distribution_emails
    db.commit()
    return tpl_out(t)


class AdhocIn(BaseModel):
    query_config: dict
    from_date: str | None = None
    to_date: str | None = None


@router.post("/run")
def run_adhoc(body: AdhocIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = run_template(db, body.query_config, body.from_date, body.to_date)
    return {"columns": cols_for(rows), "rows": rows}


@router.get("/reports/{code}")
def run_report(code: str, fmt: str = "json", from_date: str | None = None, to_date: str | None = None,
               db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Web preview first, then bilingual (Hindi before English) PDF / Excel / CSV (TS p.208, p.59)."""
    t = db.scalar(select(ReportTemplate).where(ReportTemplate.code == code))
    if t is None:
        raise HTTPException(404)
    rows = run_template(db, t.query_config_json, from_date, to_date)
    cols = cols_for(rows)
    if fmt == "json":
        return {"template": tpl_out(t), "columns": cols, "rows": rows}
    sub = f"{from_date or '...'} to {to_date or utc_to_ist(utcnow()).strftime('%Y-%m-%d')}"
    return export(fmt, t.name_en, t.name_hi, cols, rows, code.lower(), subtitle=sub)


class EmailIn(BaseModel):
    recipients: list[str]
    fmt: str = "xlsx"


@router.post("/reports/{code}/email")
def email_report(code: str, body: EmailIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    t = db.scalar(select(ReportTemplate).where(ReportTemplate.code == code))
    rows = run_template(db, t.query_config_json)
    for r in body.recipients:
        send_raw(db, "EMAIL", r, f"[Grid-India OMS] {t.name_en}", f"{len(rows)} rows attached ({body.fmt.upper()})", module="mis")
    db.commit()
    return {"sent": len(body.recipients)}


@scheduler.register("mis_scheduled_reports")
def scheduled(db: Session) -> None:
    """Automated generation & e-mail distribution (daily templates at 09:00 IST)."""
    now = utc_to_ist(utcnow())
    if now.hour != 9 or now.minute > 0:
        return
    for t in db.scalars(select(ReportTemplate).where(ReportTemplate.schedule_cron != "")):
        rows = run_template(db, t.query_config_json)
        for r in t.distribution_emails_json or ["npmc@powermin.example"]:
            send_raw(db, "EMAIL", r, f"[Scheduled] {t.name_en}", f"{len(rows)} rows", module="mis")


# ------------------------------------------------------------------ graphs (300)
@router.get("/charts")
def charts(module: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(ChartDefinition).order_by(ChartDefinition.module, ChartDefinition.code)
    if module:
        stmt = stmt.where(ChartDefinition.module == module)
    return [{"code": c.code, "module": c.module, "title_en": c.title_en, "title_hi": c.title_hi, "chart_type": c.chart_type, "dataset": c.dataset,
             "config": c.config_json, "menu_assignment": c.menu_assignment} for c in db.scalars(stmt)]


@router.get("/charts/{code}/data")
def chart_data(code: str, centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    c = db.scalar(select(ChartDefinition).where(ChartDefinition.code == code))
    if c is None:
        raise HTTPException(404)
    cfg = dict(c.config_json)
    if centre and centre != "ALL" and "centre" in catalog.GROUPABLE.get(cfg["source"], []):
        cfg["filters"] = {**cfg.get("filters", {}), "centre": centre}
    rows = catalog.run_query(db, cfg)
    gb = cfg["group_by"]
    metric = next((k for k in (rows[0].keys() if rows else []) if k not in gb), "count")
    if len(gb) == 2:  # pivot second dimension into series
        series = sorted({str(r[gb[1]]) for r in rows})
        piv: dict = {}
        for r in rows:
            piv.setdefault(r[gb[0]], {gb[0]: r[gb[0]]})[str(r[gb[1]])] = r[metric]
        return {"type": c.chart_type, "x": gb[0], "series": series, "data": list(piv.values())}
    return {"type": c.chart_type, "x": gb[0], "series": [metric], "data": rows}


@router.put("/charts/{code}/menu")
def assign_menu(code: str, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Assign a graph to a menu item / post acronym (TS 11.2(e))."""
    c = db.scalar(select(ChartDefinition).where(ChartDefinition.code == code))
    c.menu_assignment = body.get("menu", "")
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ BI views for Power BI / Tableau (TS Cl. 2.7)
BI_VIEWS = {
    "bi_outage_codes": "SELECT c.code_number, c.code_type, c.issued_at, c.final_exec_time, c.is_revoked, e.unique_element_id, e.name AS element, "
                       "e.voltage_kv, ce.code AS centre FROM outage_codes c LEFT JOIN grid_elements e ON e.id = c.grid_element_id JOIN centres ce ON ce.id = c.centre_id",
    "bi_tickets": "SELECT t.ticket_number, t.module, t.severity, t.escalation_level, t.status, t.created_at, t.resolved_at, ce.code AS centre "
                  "FROM tickets t JOIN centres ce ON ce.id = t.centre_id",
    "bi_ftc": "SELECT w.case_number, f.stage, f.jurisdiction, f.element_category, w.status, w.created_at, en.name AS entity "
              "FROM ftc_applications f JOIN workflow_cases w ON w.id = f.case_id JOIN entities en ON en.id = f.entity_id",
    "bi_availability": "SELECT a.billing_month, a.availability_head, a.category_code, a.outage_start, a.outage_end, a.user_action, a.rldc_verified_status, "
                       "e.name AS element, en.name AS owner FROM availability_records a JOIN grid_elements e ON e.id = a.grid_element_id "
                       "JOIN entities en ON en.id = a.owner_entity_id WHERE a.is_bifurcated_parent = 0",
    "bi_trippings": "SELECT r.tripped_at, r.reason, r.relay_flags, e.name AS element, e.voltage_kv, ce.code AS centre "
                    "FROM tripping_reports r JOIN grid_elements e ON e.id = r.grid_element_id JOIN centres ce ON ce.id = r.centre_id",
}


def ensure_views(db: Session) -> None:
    for name, sql in BI_VIEWS.items():
        db.execute(text(f"CREATE VIEW IF NOT EXISTS {name} AS {sql}"))
    db.commit()


@router.get("/bi-views")
def list_views(user=Depends(get_current_user)):
    return [{"name": k, "sql": v} for k, v in BI_VIEWS.items()]


@router.get("/bi-views/{name}")
def bi_view(name: str, fmt: str = "json", db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Read-only SQL views consumed by Power BI / Tableau connectors (5 dashboards each, TS Cl. 2.7)."""
    if name not in BI_VIEWS:
        raise HTTPException(404)
    ensure_views(db)
    res = db.execute(text(f"SELECT * FROM {name} LIMIT 5000"))
    keys = list(res.keys())
    rows = [dict(zip(keys, r)) for r in res.fetchall()]
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
        return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    return {"columns": keys, "rows": rows}


_ = role_codes
