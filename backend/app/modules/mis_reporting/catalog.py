"""MIS datasets, the non-hard-coded report engine and the 300-graph catalogue (TS Cl. 11.2(e) Table 6, Cl. 11.4.10, Ch.9).

Every report/graph is *data*: a dataset key + filters + group-by + aggregates stored in `report_templates` /
`chart_definitions`, so new reports are created from the front end without code (TS p.59, p.208).
"""
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow


def _month(d) -> str:
    return f"{d:%Y-%m}" if d else ""


def ds_tickets(db):
    from app.modules.ticketing_cas.models import Ticket
    return [{"module": t.module, "centre": t.centre.code, "status": t.status, "severity": f"S{t.severity or '-'}", "channel": t.channel,
             "level": f"L{t.escalation_level}", "type": t.complaint_type, "month": _month(t.created_at), "count": 1,
             "resolution_hours": round((t.resolved_at - t.created_at).total_seconds() / 3600, 2) if t.resolved_at else None} for t in db.scalars(select(Ticket))]


def _cases(db, module):
    from app.modules.workflow_engine.models import WorkflowCase
    return db.scalars(select(WorkflowCase).where(WorkflowCase.module == module)).all()


def ds_registration(db):
    from app.modules.registration.models import RegApplication
    from app.modules.workflow_engine.models import WorkflowCase
    out = []
    for a in db.scalars(select(RegApplication)):
        c = db.get(WorkflowCase, a.case_id)
        out.append({"type": a.application_type, "category": a.category, "sub_category": a.sub_category, "status": c.status, "centre": c.centre.code,
                    "shifted": "YES" if a.shifts else "NO", "month": _month(c.created_at), "count": 1})
    return out


def ds_ftc(db):
    from app.modules.ftc.models import FtcApplication
    from app.modules.master_registry.models import Entity
    from app.modules.workflow_engine.models import WorkflowCase
    out = []
    for f in db.scalars(select(FtcApplication)):
        c = db.get(WorkflowCase, f.case_id)
        out.append({"stage": f"Stage {f.stage}", "status": c.status, "jurisdiction": f.jurisdiction, "category": f.element_category, "centre": c.centre.code,
                    "owner": db.get(Entity, f.entity_id).name, "elements": len(f.a2_elements_json), "month": _month(c.created_at),
                    "format_ii": "YES" if f.format_ii_doc_id else "NO", "format_iv": "YES" if f.format_iv_doc_id else "NO",
                    "mw": sum(float(str(e.get("rating", "0")).split()[0] or 0) for e in f.a2_elements_json if str(e.get("rating", "")).split() and str(e.get("rating")).split()[0].replace(".", "").isdigit()),
                    "count": 1})
    return out


def ds_comm(db):
    from app.modules.comm_cert.models import CommCertApplication
    from app.modules.workflow_engine.models import WorkflowCase
    return [{"scope": a.scope, "stage": f"Stage {a.stage}", "status": db.get(WorkflowCase, a.case_id).status, "route": a.route,
             "month": _month(a.created_at), "count": 1} for a in db.scalars(select(CommCertApplication))]


def ds_codes(db):
    from app.modules.realtime_outage.models import OutageCode
    return [{"centre": c.element.centre.code if c.element else "", "code_type": c.code_type, "element_type": c.element.element_type if c.element else "MULTI",
             "voltage": f"{int(c.element.voltage_kv)} kV" if c.element else "", "status": "REVOKED" if c.is_revoked else "EXECUTED" if c.final_exec_time else "PENDING",
             "issued_by": c.issued_by_name, "hour": f"{c.issued_at:%H}", "day": f"{c.issued_at:%Y-%m-%d}", "month": _month(c.issued_at),
             "tag": (c.tags_json or ["-"])[0], "count": 1} for c in db.scalars(select(OutageCode))]


def ds_requests(db):
    from app.modules.realtime_outage.models import OutageCodeRequest
    return [{"category": r.request_category, "status": r.status, "action": r.action, "month": _month(r.created_at),
             "consents": len(r.consents), "count": 1} for r in db.scalars(select(OutageCodeRequest))]


def ds_elements(db):
    from app.modules.master_registry.models import GridElement
    return [{"centre": g.centre.code, "type": g.element_type, "voltage": f"{int(g.voltage_kv)} kV", "status": g.status,
             "ftc_year": str(g.ftc_date.year) if g.ftc_date else "", "count": 1} for g in db.scalars(select(GridElement))]


def ds_outage_plans(db):
    from app.modules.outage_coord.models import OccOutagePlan
    return [{"route": p.plan_route, "status": p.status, "owner": p.owner_name, "type": p.request_type, "month": p.target_month,
             "head": p.availability_head_proposed, "inter_regional": "YES" if p.is_inter_regional else "NO",
             "hours": round((p.req_to - p.req_from).total_seconds() / 3600, 1), "count": 1} for p in db.scalars(select(OccOutagePlan))]


def ds_availability(db):
    from app.modules.availability_verify.models import AvailabilityRecord
    from app.modules.master_registry.models import Entity
    return [{"month": r.billing_month, "head": r.availability_head, "owner": db.get(Entity, r.owner_entity_id).short_name, "action": r.user_action,
             "verified": r.rldc_verified_status or "PENDING", "category": r.category_code or "-",
             "hours": round((r.outage_end - r.outage_start).total_seconds() / 3600, 2), "count": 1}
            for r in db.scalars(select(AvailabilityRecord).where(AvailabilityRecord.is_bifurcated_parent.is_(False)))]


def ds_trippings(db):
    from app.modules.realtime_outage.models import TrippingReport
    return [{"element": t.element.name, "type": t.element.element_type, "voltage": f"{int(t.element.voltage_kv)} kV", "centre": t.element.centre.code,
             "month": _month(t.tripped_at), "hour": f"{t.tripped_at:%H}", "count": 1} for t in db.scalars(select(TrippingReport))]


def ds_events(db):
    from app.modules.protection_tripping.models import TrippingEvent
    return [{"category": e.event_category, "month": _month(e.occurred_at), "validation": e.rldc_validation_status, "count": 1}
            for e in db.scalars(select(TrippingEvent))]


def ds_alerts(db):
    from app.modules.message_alerts.models import ViolationMessage
    return [{"template": m.template_code, "category": m.category, "target": m.target_label, "kind": m.kind, "month": _month(m.sent_at),
             "day": f"{m.sent_at:%Y-%m-%d}", "recipients": m.recipients_count, "count": 1} for m in db.scalars(select(ViolationMessage))]


def ds_sps(db):
    from app.modules.sps_status.models import SpsScheme, SpsStatusLog
    return [{"sps": db.get(SpsScheme, l.sps_scheme_id).sps_id, "status": l.status, "source": l.source, "day": f"{l.updated_at:%Y-%m-%d}",
             "month": _month(l.updated_at), "count": 1} for l in db.scalars(select(SpsStatusLog))]


DATASETS = {"tickets": ds_tickets, "registration": ds_registration, "ftc": ds_ftc, "comm_cert": ds_comm, "codes": ds_codes,
            "requests": ds_requests, "elements": ds_elements, "outage_plans": ds_outage_plans, "availability": ds_availability,
            "trippings": ds_trippings, "events": ds_events, "alerts": ds_alerts, "sps": ds_sps}

MODULE_DATASETS = {"registration": ["registration"], "ftc": ["ftc", "elements"], "comm_cert": ["comm_cert"], "realtime": ["codes", "requests", "trippings"],
                   "availability": ["availability"], "protection": ["events", "trippings"], "outage_coord": ["outage_plans"], "alerts": ["alerts"],
                   "sps": ["sps"], "mis": list(DATASETS)}


def run_query(db: Session, cfg: dict) -> list[dict]:
    """Generic engine: filters -> group_by -> aggregates (count/sum/avg/min/max)."""
    rows = DATASETS[cfg["source"]](db)
    for k, v in (cfg.get("filters") or {}).items():
        if v not in (None, "", "ALL"):
            rows = [r for r in rows if str(r.get(k)) == str(v)]
    gb = cfg.get("group_by") or []
    aggs = cfg.get("aggregates") or [{"field": "count", "fn": "sum"}]
    if not gb:
        return rows
    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        groups[tuple(r.get(g, "") for g in gb)].append(r)
    out = []
    for key, items in sorted(groups.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        row = dict(zip(gb, key))
        for a in aggs:
            vals = [x.get(a["field"]) for x in items if isinstance(x.get(a["field"]), (int, float))]
            name = a.get("as") or (a["field"] if a["fn"] == "sum" and a["field"] == "count" else f"{a['fn']}_{a['field']}")
            fn = a["fn"]
            row[name] = (len(items) if fn == "count" else round(sum(vals), 2) if fn == "sum" else round(sum(vals) / len(vals), 2) if fn == "avg" and vals
                         else (min(vals) if vals else None) if fn == "min" else (max(vals) if vals else None) if fn == "max" else None)
        out.append(row)
    return out


# ------------------------------------------------------------------ catalogue
GROUPABLE = {
    "tickets": ["module", "centre", "status", "severity", "channel", "level", "type", "month"],
    "registration": ["type", "category", "sub_category", "status", "centre", "shifted", "month"],
    "ftc": ["stage", "status", "jurisdiction", "category", "centre", "owner", "month", "format_ii", "format_iv"],
    "comm_cert": ["scope", "stage", "status", "route", "month"],
    "codes": ["centre", "code_type", "element_type", "voltage", "status", "issued_by", "hour", "day", "month", "tag"],
    "requests": ["category", "status", "action", "month"],
    "elements": ["centre", "type", "voltage", "status", "ftc_year"],
    "outage_plans": ["route", "status", "owner", "type", "month", "head", "inter_regional"],
    "availability": ["month", "head", "owner", "action", "verified", "category"],
    "trippings": ["element", "type", "voltage", "centre", "month", "hour"],
    "events": ["category", "month", "validation"],
    "alerts": ["template", "category", "target", "kind", "month", "day"],
    "sps": ["sps", "status", "source", "day", "month"],
}
NUMERIC = {"tickets": ["resolution_hours"], "ftc": ["elements", "mw"], "outage_plans": ["hours"], "availability": ["hours"], "alerts": ["recipients"],
           "requests": ["consents"]}
TYPES = ["bar", "pie", "line", "stacked", "area"]


def chart_catalogue() -> list[dict]:
    """Exactly 30 initial graphs for each of the 10 modules (TS Table 6)."""
    out = []
    for module in ["registration", "ftc", "comm_cert", "realtime", "availability", "protection", "outage_coord", "alerts", "sps", "mis"]:
        combos = []
        for ds in MODULE_DATASETS[module]:
            g = GROUPABLE[ds]
            for f in g:
                combos.append((ds, [f], [{"field": "count", "fn": "sum"}]))
            for n in NUMERIC.get(ds, []):
                for f in g:
                    combos.append((ds, [f], [{"field": n, "fn": "sum"}]))
            for i, f1 in enumerate(g):
                for f2 in g[i + 1:]:
                    combos.append((ds, [f1, f2], [{"field": "count", "fn": "sum"}]))
        base = len(combos)
        k = 0
        while len(combos) < 30:  # same data source rendered as an alternate chart type
            ds, gb, ag = combos[k % base]
            combos.append((ds, gb, ag, TYPES[(k + 2) % len(TYPES)]))
            k += 1
        for i, combo in enumerate(combos[:30]):
            ds, gb, ag = combo[:3]
            t = combo[3] if len(combo) > 3 else "line" if gb[0] in ("month", "day", "hour") else TYPES[i % len(TYPES)] if len(gb) == 1 else "stacked"
            label = " by ".join(x.replace("_", " ") for x in gb)
            metric = ag[0]["field"] if ag[0]["field"] != "count" else "count"
            out.append({"code": f"{module.upper()}_G{i + 1:02d}", "module": module, "chart_type": t, "dataset": ds,
                        "title_en": f"{ds.replace('_', ' ').title()}: {metric} by {label}", "title_hi": f"{ds} - {label}",
                        "config_json": {"source": ds, "group_by": gb, "aggregates": ag}})
    return out


STANDARD_REPORTS = [
    ("NPMC_DAILY", "mis", "NPMC daily - generating units under outage", "एनपीएमसी दैनिक - आउटेज में उत्पादन इकाइयाँ", {"source": "special:npmc"}),
    ("GEN_OUTAGE_UNIT", "mis", "Generation outage & ENS - unit-wise", "उत्पादन आउटेज एवं ईएनएस - इकाई-वार", {"source": "special:gen_outage", "group_by": ["unit"]}),
    ("GEN_OUTAGE_PLANT", "mis", "Generation outage & ENS - plant-wise", "उत्पादन आउटेज एवं ईएनएस - संयंत्र-वार", {"source": "special:gen_outage", "group_by": ["plant"]}),
    ("GEN_OUTAGE_OWNER", "mis", "Generation outage & ENS - ownership-wise", "उत्पादन आउटेज एवं ईएनएस - स्वामित्व-वार", {"source": "special:gen_outage", "group_by": ["owner"]}),
    ("GEN_OUTAGE_FUEL", "mis", "Generation outage & ENS - fuel-wise", "उत्पादन आउटेज एवं ईएनएस - ईंधन-वार", {"source": "special:gen_outage", "group_by": ["fuel"]}),
    ("GEN_OUTAGE_LOCATION", "mis", "Generation outage & ENS - location-wise", "उत्पादन आउटेज एवं ईएनएस - स्थान-वार", {"source": "special:gen_outage", "group_by": ["location"]}),
    ("FTC_MONTHLY", "ftc", "Monthly FTC report to NLDC", "एनएलडीसी को मासिक एफटीसी रिपोर्ट", {"source": "ftc", "group_by": ["month", "centre"], "aggregates": [{"field": "count", "fn": "sum"}, {"field": "elements", "fn": "sum"}]}),
    ("FTC_OWNER", "ftc", "Owner-wise FTC detail", "स्वामी-वार एफटीसी विवरण", {"source": "ftc", "group_by": ["owner"], "aggregates": [{"field": "count", "fn": "sum"}, {"field": "mw", "fn": "sum"}]}),
    ("FTC_STAGE", "ftc", "FTC in progress by stage", "चरण-वार प्रगतिरत एफटीसी", {"source": "ftc", "group_by": ["stage", "jurisdiction"]}),
    ("COMM_CERT", "comm_cert", "Communication certification summary", "संचार प्रमाणन सारांश", {"source": "comm_cert", "group_by": ["scope", "status"]}),
    ("CODES_TYPE", "realtime", "Codes issued by type and centre", "प्रकार एवं केंद्र-वार जारी कोड", {"source": "codes", "group_by": ["centre", "code_type"]}),
    ("REQUESTS_CATEGORY", "realtime", "Code requests by category", "श्रेणी-वार कोड अनुरोध", {"source": "requests", "group_by": ["category", "status"]}),
    ("OUTAGE_OWNER", "outage_coord", "Shutdown requests by owner", "स्वामी-वार शटडाउन अनुरोध", {"source": "outage_plans", "group_by": ["owner", "route"], "aggregates": [{"field": "count", "fn": "sum"}, {"field": "hours", "fn": "sum"}]}),
    ("AVAIL_HEAD", "availability", "Outage hours by availability head", "उपलब्धता शीर्ष-वार आउटेज घंटे", {"source": "availability", "group_by": ["head"], "aggregates": [{"field": "hours", "fn": "sum"}]}),
    ("EVENTS_GDGI", "protection", "Grid events by GD/GI category", "जीडी/जीआई श्रेणी-वार ग्रिड घटनाएं", {"source": "events", "group_by": ["category"]}),
    ("ALERTS_TARGET", "alerts", "Violation messages by constituent", "घटक-वार उल्लंघन संदेश", {"source": "alerts", "group_by": ["target", "template"]}),
    ("SPS_STATUS", "sps", "SPS status changes", "एसपीएस स्थिति परिवर्तन", {"source": "sps", "group_by": ["sps", "status"]}),
    ("TICKETS_SEV", "mis", "Complaints by severity and status", "गंभीरता एवं स्थिति-वार शिकायतें", {"source": "tickets", "group_by": ["severity", "status"]}),
]


def gen_outage(db: Session, from_dt: datetime | None = None, to_dt: datetime | None = None) -> list[dict]:
    """Generation outage duration & Energy Not Served per unit (TS p.206-208). ENS = capacity x outage hours x entitlement share."""
    from app.modules.availability_verify.models import AvailabilityRecord
    from app.modules.master_registry.models import GridElement

    from_dt = from_dt or datetime(utcnow().year, 1, 1)
    to_dt = to_dt or utcnow()
    out = []
    for u in db.scalars(select(GridElement).where(GridElement.element_type.in_(["GEN_UNIT", "GEN_STATION"]))):
        meta = u.metadata_json or {}
        cap = float(meta.get("installed_mw") or 0)
        hrs = 0.0
        for r in db.scalars(select(AvailabilityRecord).where(AvailabilityRecord.grid_element_id == u.id, AvailabilityRecord.is_bifurcated_parent.is_(False))):
            s, e = max(r.outage_start, from_dt), min(r.outage_end, to_dt)
            hrs += max((e - s).total_seconds() / 3600, 0)
        if u.status in ("OUTAGE", "TRIPPED"):
            s = max(u.last_status_change_at, from_dt)
            hrs += max((to_dt - s).total_seconds() / 3600, 0)
        ent = meta.get("entitlement") or {"Uttar Pradesh": 0.4, "Delhi": 0.25, "Haryana": 0.2, "Rajasthan": 0.15}
        owner = next((o.entity.short_name or o.entity.name for o in u.owners), "")
        out.append({"unit": u.name, "plant": meta.get("plant", u.name), "owner": owner, "fuel": meta.get("fuel", "OTHER"),
                    "location": u.from_substation.state if u.from_substation else "", "installed_mw": cap, "outage_hours": round(hrs, 2),
                    "ens_mwh": round(cap * hrs, 1), **{f"ens_{k.lower().replace(' ', '_')}": round(cap * hrs * v, 1) for k, v in ent.items()}})
    return out


def seed_mis(db: Session) -> None:
    from app.modules.mis_reporting.models import ChartDefinition, ReportTemplate

    for c in chart_catalogue():
        db.add(ChartDefinition(**c))
    for code, module, en, hi, cfg in STANDARD_REPORTS:
        db.add(ReportTemplate(code=code, module=module, name_en=en, name_hi=hi, query_config_json=cfg, is_standard=True,
                              schedule_cron="0 9 * * *" if code == "NPMC_DAILY" else ""))
