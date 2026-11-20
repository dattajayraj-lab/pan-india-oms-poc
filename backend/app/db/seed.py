"""Seed data: 6 centres, roles, demo users, master registry, checklists, templates.

Run:  python -m app.db.seed            (creates tables if missing and seeds once)
      python -m app.db.seed --reset    (drops the SQLite file content and reseeds)

All demo logins use the password in DEMO_PASSWORD (POC only; see README).
"""
import sys
import zlib
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_SYSTEM_SETTINGS
from app.core.rbac import ROLE_DEFS
from app.core.security import hash_password
from app.db import models  # noqa: F401  (register all tables)
from app.db.base import Base, utcnow
from app.db.session import SessionLocal, get_engine
from app.modules.auth_rbac.models import Centre, NotificationToggle, Role, SystemSetting, User, UserRole
from app.modules.master_registry.models import (CommElement, ElementOwner, Entity, EntityContact, GridElement,
                                                Substation)
from app.modules.workflow_engine.models import Checklist
from app.utils.ids import element_id

DEMO_PASSWORD = "Grid@2026"

CENTRES = [
    ("NLDC", "National Load Despatch Centre", "राष्ट्रीय भार प्रेषण केंद्र", "New Delhi", "NL", "08:30"),
    ("NRLDC", "Northern Regional Load Despatch Centre", "उत्तरी क्षेत्रीय भार प्रेषण केंद्र", "New Delhi", "NR", "08:30"),
    ("ERLDC", "Eastern Regional Load Despatch Centre", "पूर्वी क्षेत्रीय भार प्रेषण केंद्र", "Kolkata", "ER", "08:30"),
    ("WRLDC", "Western Regional Load Despatch Centre", "पश्चिमी क्षेत्रीय भार प्रेषण केंद्र", "Mumbai", "WR", "08:30"),
    ("SRLDC", "Southern Regional Load Despatch Centre", "दक्षिणी क्षेत्रीय भार प्रेषण केंद्र", "Bengaluru", "SR", "08:30"),
    ("NERLDC", "North Eastern Regional Load Despatch Centre", "उत्तर पूर्वी क्षेत्रीय भार प्रेषण केंद्र", "Shillong", "NE", "08:00"),
]

ENTITIES = [
    # key, name, short, type, sub, sector, state, centre
    ("PG", "Power Grid Corporation of India Ltd", "POWERGRID", "TRANS_LICENSEE", "", "CENTRAL", "Haryana", "NRLDC"),
    ("RVPN", "Rajasthan Rajya Vidyut Prasaran Nigam Ltd", "RVPN", "TRANS_LICENSEE", "", "STATE", "Rajasthan", "NRLDC"),
    ("UPPTCL", "UP Power Transmission Corporation Ltd", "UPPTCL", "TRANS_LICENSEE", "", "STATE", "Uttar Pradesh", "NRLDC"),
    ("NTPC", "NTPC Ltd (Dadri)", "NTPC", "CONV_GEN", "THERMAL", "CENTRAL", "Uttar Pradesh", "NRLDC"),
    ("THAR", "Thar Surya 1 Pvt Ltd", "THAR SURYA", "REGS", "SOLAR", "PRIVATE", "Rajasthan", "NRLDC"),
    ("ADANI", "Adani Hybrid Energy Jaisalmer One Ltd", "AHEJOL", "REGS", "HYBRID", "PRIVATE", "Rajasthan", "NRLDC"),
    ("CTUIL", "Central Transmission Utility of India Ltd", "CTUIL", "CTU", "", "CENTRAL", "Haryana", "NLDC"),
    ("NRPC", "Northern Regional Power Committee", "NRPC", "RPC", "", "CENTRAL", "Delhi", "NRLDC"),
    ("MPPTCL", "MP Power Transmission Co Ltd", "MPPTCL", "TRANS_LICENSEE", "", "STATE", "Madhya Pradesh", "WRLDC"),
    ("TPCOMM", "Tata Power Communications (CSP)", "TPCOMM", "COMM_PROVIDER", "", "PRIVATE", "Delhi", "NRLDC"),
    ("HVPN", "Haryana Vidyut Prasaran Nigam Ltd", "HVPN", "TRANS_LICENSEE", "", "STATE", "Haryana", "NRLDC"),
]

SUBSTATIONS = [
    # code, name, centre, state, kv, type, lat, lng, owner, weather_area, pooling
    ("NR-AGRA-PG", "Agra (PG)", "NRLDC", "Uttar Pradesh", [765, 400], "AIS", 27.17, 78.0, "PG", "Agra", False),
    ("WR-GWALIOR-PG", "Gwalior (PG)", "WRLDC", "Madhya Pradesh", [765, 400], "AIS", 26.21, 78.18, "PG", "Gwalior", False),
    ("NR-BIKANER-PG", "Bikaner (PG)", "NRLDC", "Rajasthan", [765, 400, 220], "AIS", 28.02, 73.31, "PG", "Bikaner", True),
    ("NR-BHADLA-PG", "Bhadla (PG)", "NRLDC", "Rajasthan", [765, 400, 220], "AIS", 27.54, 71.91, "PG", "Jodhpur", True),
    ("NR-BALLABGARH-PG", "Ballabhgarh (PG)", "NRLDC", "Haryana", [400, 220], "AIS", 28.34, 77.32, "PG", "Faridabad", False),
    ("NR-DADRI-NTPC", "Dadri (NTPC)", "NRLDC", "Uttar Pradesh", [400, 220], "AIS", 28.6, 77.6, "NTPC", "Gautam Buddh Nagar", False),
    ("NR-MOGA-PG", "Moga (PG)", "NRLDC", "Punjab", [765, 400], "AIS", 30.8, 75.17, "PG", "Moga", False),
    ("NR-BHIWADI-RVPN", "Bhiwadi (RVPN)", "NRLDC", "Rajasthan", [400, 220], "AIS", 28.21, 76.86, "RVPN", "Alwar", False),
    ("NR-FATEHGARH2-PG", "Fatehgarh-II (PG)", "NRLDC", "Rajasthan", [765, 400, 220], "GIS", 26.9, 70.9, "PG", "Jaisalmer", True),
    ("NR-THARSURYA-PSS", "Thar Surya Pooling S/S", "NRLDC", "Rajasthan", [220, 33], "AIS", 28.1, 73.4, "THAR", "Bikaner", False),
    ("NR-JAIPUR-RVPN", "Jaipur South (RVPN)", "NRLDC", "Rajasthan", [220], "AIS", 26.8, 75.8, "RVPN", "Jaipur", False),
    ("NR-SIKAR-RVPN", "Sikar (RVPN)", "NRLDC", "Rajasthan", [220], "AIS", 27.6, 75.1, "RVPN", "Sikar", False),
    ("WR-INDORE-PG", "Indore (PG)", "WRLDC", "Madhya Pradesh", [765, 400], "AIS", 22.7, 75.8, "PG", "Indore", False),
    ("WR-ITARSI-MP", "Itarsi (MPPTCL)", "WRLDC", "Madhya Pradesh", [400], "AIS", 22.6, 77.7, "MPPTCL", "Hoshangabad", False),
]

# name, type, centre, kv, from, to, owners[(entity, role, km)], extra
ELEMENTS = [
    ("765 kV Agra-Gwalior Ckt-1", "AC_LINE", "NRLDC", 765, "NR-AGRA-PG", "WR-GWALIOR-PG",
     [("PG", "LINE_OWNER", None), ("PG", "END1_STATION", None), ("PG", "END2_STATION", None)],
     {"is_inter_regional": True, "length_km": 128.0, "rating": "3000 MW", "metadata": {"conductor": "Quad ACSR Bersimis"}}),
    ("400 kV Bikaner-Bhadla Ckt-1", "AC_LINE", "NRLDC", 400, "NR-BIKANER-PG", "NR-BHADLA-PG",
     [("PG", "LINE_OWNER", None), ("PG", "END1_STATION", None), ("PG", "END2_STATION", None)],
     {"length_km": 214.0, "rating": "1200 MW", "metadata": {"conductor": "Twin ACSR Moose"}}),
    ("400 kV Ballabhgarh-Dadri Ckt-1", "AC_LINE", "NRLDC", 400, "NR-BALLABGARH-PG", "NR-DADRI-NTPC",
     [("PG", "LINE_OWNER", None), ("PG", "END1_STATION", None), ("NTPC", "END2_STATION", None)],
     {"length_km": 61.0, "rating": "900 MW", "metadata": {"conductor": "Twin ACSR Moose"}}),
    ("400 kV Moga-Bhiwadi Ckt-1", "AC_LINE", "NRLDC", 400, "NR-MOGA-PG", "NR-BHIWADI-RVPN",
     [("PG", "SECTION_OWNER", 75.0), ("RVPN", "SECTION_OWNER", 25.0), ("PG", "END1_STATION", None), ("RVPN", "END2_STATION", None)],
     {"length_km": 100.0, "rating": "1000 MW", "metadata": {"conductor": "Quad ACSR Zebra", "note": "Section ownership 75 km PG / 25 km RVPN"}}),
    ("765/400 kV 1500 MVA ICT-1 at Bhadla", "ICT", "NRLDC", 765, "NR-BHADLA-PG", None,
     [("PG", "ASSET_OWNER", None)], {"rating": "1500 MVA"}),
    ("400 kV 125 MVAr Bus Reactor-1 at Bikaner", "BUS_REACTOR", "NRLDC", 400, "NR-BIKANER-PG", None,
     [("PG", "ASSET_OWNER", None)], {"rating": "125 MVAr"}),
    ("220 kV Thar Surya-Bikaner (PG) S/C", "AC_LINE", "NRLDC", 220, "NR-THARSURYA-PSS", "NR-BIKANER-PG",
     [("THAR", "LINE_OWNER", None), ("THAR", "END1_STATION", None), ("PG", "END2_STATION", None)],
     {"length_km": 18.0, "rating": "300 MW"}),
    ("NTPC Dadri Unit-1 490 MW", "GEN_UNIT", "NRLDC", 400, "NR-DADRI-NTPC", None,
     [("NTPC", "ASSET_OWNER", None)], {"rating": "490 MW", "metadata": {"fuel": "COAL", "installed_mw": 490, "plant": "Dadri TPS"}}),
    ("NTPC Dadri Unit-2 490 MW", "GEN_UNIT", "NRLDC", 400, "NR-DADRI-NTPC", None,
     [("NTPC", "ASSET_OWNER", None)], {"rating": "490 MW", "metadata": {"fuel": "COAL", "installed_mw": 490, "plant": "Dadri TPS"}}),
    ("Thar Surya Solar Plant 300 MW", "GEN_STATION", "NRLDC", 220, "NR-THARSURYA-PSS", None,
     [("THAR", "ASSET_OWNER", None)], {"rating": "300 MW", "metadata": {"fuel": "SOLAR", "installed_mw": 300, "plant": "Thar Surya"}}),
    ("400 kV 63 MVAr Line Reactor at Moga (Moga-Bhiwadi)", "LINE_REACTOR", "NRLDC", 400, "NR-MOGA-PG", None,
     [("PG", "ASSET_OWNER", None)], {"rating": "63 MVAr"}),
    ("±300 MVAr STATCOM at Fatehgarh-II", "SVC_STATCOM", "NRLDC", 400, "NR-FATEHGARH2-PG", None,
     [("PG", "ASSET_OWNER", None)], {"rating": "±300 MVAr"}),
    ("765 kV Bus-1 at Bikaner", "BUS", "NRLDC", 765, "NR-BIKANER-PG", None, [("PG", "ASSET_OWNER", None)], {}),
    ("220 kV Jaipur South-Sikar Ckt-1", "AC_LINE", "NRLDC", 220, "NR-JAIPUR-RVPN", "NR-SIKAR-RVPN",
     [("RVPN", "LINE_OWNER", None), ("RVPN", "END1_STATION", None), ("RVPN", "END2_STATION", None)],
     {"is_ists": False, "length_km": 110.0, "rating": "250 MW"}),
    ("765 kV Indore-Gwalior Ckt-1", "AC_LINE", "WRLDC", 765, "WR-INDORE-PG", "WR-GWALIOR-PG",
     [("PG", "LINE_OWNER", None), ("PG", "END1_STATION", None), ("PG", "END2_STATION", None)],
     {"length_km": 380.0, "rating": "3000 MW"}),
    ("400 kV Indore-Itarsi Ckt-1", "AC_LINE", "WRLDC", 400, "WR-INDORE-PG", "WR-ITARSI-MP",
     [("MPPTCL", "LINE_OWNER", None), ("PG", "END1_STATION", None), ("MPPTCL", "END2_STATION", None)],
     {"length_km": 220.0, "rating": "1000 MW"}),
]

# username, full name, category, dept, centre, roles, entity
USERS = [
    ("superadmin", "OMS Super Administrator", "GRID_INDIA", "IT", "NLDC", ["SUPER_ADMIN"], None),
    ("nldc_coord", "NLDC Registration Coordinator", "GRID_INDIA", "MO", "NLDC", ["REG_COORDINATOR", "NLDC_USER", "OUTAGE_COORDINATOR"], None),
    ("nldc_operator", "NLDC Grid Operator", "GRID_INDIA", "SO-1", "NLDC", ["RT_COORDINATOR", "SHIFT_INCHARGE", "NLDC_USER"], None),
    ("nldc_head", "Head of NLDC", "GRID_INDIA", "SO", "NLDC", ["HEAD_NLDC"], None),
    ("director_so", "Director (System Operation)", "GRID_INDIA", "SO", "NLDC", ["DIRECTOR"], None),
    ("director_mo", "Director (Market Operation)", "GRID_INDIA", "MO", "NLDC", ["DIRECTOR"], None),
    ("nr_coord", "NRLDC Coordinator (Reg/FTC/Comm)", "GRID_INDIA", "SO-2", "NRLDC", ["REG_COORDINATOR", "FTC_COORDINATOR", "COMM_COORDINATOR", "MIS_COORDINATOR"], None),
    ("nr_shiftic", "NRLDC Shift In-charge", "GRID_INDIA", "SO-1", "NRLDC", ["SHIFT_INCHARGE", "RT_COORDINATOR"], None),
    ("nr_operator", "NRLDC Grid Operator", "GRID_INDIA", "SO-1", "NRLDC", ["RT_COORDINATOR"], None),
    ("nr_outage", "NRLDC Outage & Availability Coordinator", "GRID_INDIA", "SO-2", "NRLDC", ["OUTAGE_COORDINATOR", "AVAIL_COORDINATOR"], None),
    ("nr_protection", "NRLDC Protection Coordinator", "GRID_INDIA", "PROTECTION", "NRLDC", ["PROTECTION_COORDINATOR"], None),
    ("nr_alerts", "NRLDC Alerts & SPS Coordinator", "GRID_INDIA", "SO-1", "NRLDC", ["ALERTS_COORDINATOR", "SPS_COORDINATOR"], None),
    ("nr_scada", "NRLDC SCADA Engineer", "GRID_INDIA", "SCADA", "NRLDC", ["DEPT_USER"], None),
    ("nr_metering", "NRLDC Metering Engineer", "GRID_INDIA", "METERING", "NRLDC", ["DEPT_USER"], None),
    ("nr_protdept", "NRLDC Protection Engineer", "GRID_INDIA", "PROTECTION", "NRLDC", ["DEPT_USER"], None),
    ("nr_so1", "NRLDC SO-1 Engineer", "GRID_INDIA", "SO-1", "NRLDC", ["DEPT_USER"], None),
    ("nr_mo", "NRLDC MO Engineer", "GRID_INDIA", "MO", "NRLDC", ["DEPT_USER"], None),
    ("nr_hod_scada", "NRLDC HoD SCADA", "GRID_INDIA", "SCADA", "NRLDC", ["HOD"], None),
    ("nr_hod_metering", "NRLDC HoD Metering", "GRID_INDIA", "METERING", "NRLDC", ["HOD"], None),
    ("nr_hod_prot", "NRLDC HoD Protection", "GRID_INDIA", "PROTECTION", "NRLDC", ["HOD"], None),
    ("nr_subhead_so", "NRLDC Sub-Head SO", "GRID_INDIA", "SO", "NRLDC", ["SUB_HEAD_SO", "HOD"], None),
    ("nr_head_so", "NRLDC Head of System Operation", "GRID_INDIA", "SO", "NRLDC", ["HEAD_SO"], None),
    ("nr_head", "Head of NRLDC", "GRID_INDIA", "MGMT", "NRLDC", ["HEAD_RLDC"], None),
    ("nr_helpdesk", "AMC Helpdesk (NRLDC)", "GRID_INDIA", "AMC", "NRLDC", ["CAS_HELPDESK"], None),
    ("wr_coord", "WRLDC Coordinator", "GRID_INDIA", "SO-2", "WRLDC", ["REG_COORDINATOR", "FTC_COORDINATOR", "COMM_COORDINATOR", "OUTAGE_COORDINATOR"], None),
    ("wr_operator", "WRLDC Grid Operator", "GRID_INDIA", "SO-1", "WRLDC", ["RT_COORDINATOR", "SHIFT_INCHARGE"], None),
    ("wr_scada", "WRLDC SCADA Engineer", "GRID_INDIA", "SCADA", "WRLDC", ["DEPT_USER"], None),
    ("wr_hod_scada", "WRLDC HoD SCADA", "GRID_INDIA", "SCADA", "WRLDC", ["HOD"], None),
    ("nldc_scada", "NLDC SCADA Engineer", "GRID_INDIA", "SCADA", "NLDC", ["DEPT_USER", "NLDC_USER"], None),
    ("nldc_hod_scada", "NLDC HoD SCADA", "GRID_INDIA", "SCADA", "NLDC", ["HOD"], None),
    ("wr_head", "Head of WRLDC", "GRID_INDIA", "MGMT", "WRLDC", ["HEAD_RLDC"], None),
    ("er_coord", "ERLDC Coordinator", "GRID_INDIA", "SO-2", "ERLDC", ["REG_COORDINATOR", "FTC_COORDINATOR", "OUTAGE_COORDINATOR"], None),
    ("er_operator", "ERLDC Grid Operator", "GRID_INDIA", "SO-1", "ERLDC", ["RT_COORDINATOR", "SHIFT_INCHARGE"], None),
    ("er_head", "Head of ERLDC", "GRID_INDIA", "MGMT", "ERLDC", ["HEAD_RLDC"], None),
    ("sr_coord", "SRLDC Coordinator", "GRID_INDIA", "SO-2", "SRLDC", ["REG_COORDINATOR", "FTC_COORDINATOR"], None),
    ("sr_operator", "SRLDC Grid Operator", "GRID_INDIA", "SO-1", "SRLDC", ["RT_COORDINATOR", "SHIFT_INCHARGE"], None),
    ("sr_head", "Head of SRLDC", "GRID_INDIA", "MGMT", "SRLDC", ["HEAD_RLDC"], None),
    ("ne_coord", "NERLDC Coordinator", "GRID_INDIA", "SO-2", "NERLDC", ["REG_COORDINATOR", "FTC_COORDINATOR"], None),
    ("ne_operator", "NERLDC Grid Operator", "GRID_INDIA", "SO-1", "NERLDC", ["RT_COORDINATOR", "SHIFT_INCHARGE"], None),
    ("ne_head", "Head of NERLDC", "GRID_INDIA", "MGMT", "NERLDC", ["HEAD_RLDC"], None),
    ("ctu_user", "CTUIL Connectivity Officer", "CTU", "CTU", "NLDC", ["CTU"], "CTUIL"),
    ("nrpc_user", "NRPC Outage Planning Officer", "RPC", "RPC", "NRLDC", ["RPC"], "NRPC"),
    ("re_dev", "Thar Surya - RE Developer", "EXTERNAL", "", "NRLDC", ["EXTERNAL_USER", "EXT_REGISTRATION", "EXT_FTC"], "THAR"),
    ("adani_user", "Adani Hybrid - RE Developer", "EXTERNAL", "", "NRLDC", ["EXTERNAL_USER", "EXT_REGISTRATION", "EXT_FTC"], "ADANI"),
    ("pg_user", "POWERGRID NR-1 Control Room", "EXTERNAL", "", "NRLDC",
     ["EXTERNAL_USER", "EXT_REALTIME", "EXT_OUTAGE", "EXT_AVAILABILITY", "EXT_PROTECTION", "EXT_COMM", "EXT_SPS", "EXT_FTC"], "PG"),
    ("ntpc_user", "NTPC Dadri Control Room", "EXTERNAL", "", "NRLDC", ["EXTERNAL_USER", "EXT_REALTIME", "EXT_PROTECTION", "EXT_OUTAGE"], "NTPC"),
    ("rvpn_user", "RVPN SLDC Desk", "EXTERNAL", "", "NRLDC", ["EXTERNAL_USER", "EXT_REALTIME", "EXT_OUTAGE", "EXT_PROTECTION", "EXT_AVAILABILITY"], "RVPN"),
    ("mp_user", "MPPTCL Control Room", "EXTERNAL", "", "WRLDC", ["EXTERNAL_USER", "EXT_REALTIME", "EXT_OUTAGE"], "MPPTCL"),
    ("tpcomm_user", "Tata Power Comm Officer", "EXTERNAL", "", "NRLDC", ["EXTERNAL_USER", "EXT_COMM", "EXT_REGISTRATION"], "TPCOMM"),
    ("public_user", "Public Visitor", "PUBLIC", "", None, ["PUBLIC_USER"], None),
]

CHECKLISTS = [
    ("CONN4_RLDC", "registration", "RE", "RLDC", "CONN-4 model validation checklist (RLDC)", [
        "PSS/E steady-state model received in prescribed format",
        "PSCAD/EMT model runs with given user guide",
        "Simulation report covers LVRT/HVRT per CEA standards",
        "Single generator equivalent model consistent with plant capacity",
        "IBR mapping table complete (make, model, count)",
    ]),
    ("CONN4_CTUIL", "registration", "RE", "CTUIL", "CONN-4 compliance checklist (CTUIL)", [
        "Connectivity application data matches NSWS record",
        "Bank guarantee / land documents verified",
        "Reactive power capability within regulation",
        "Model files segregated by category (no .zip dump)",
    ]),
    ("REG_FNC_CONSENT", "registration", "*", "RLDC", "Registration document checklist (Annexure-1 Sheet-2)", [
        "Fillable format (Sheet-1) complete", "Board resolution uploaded", "GST and PAN certificate valid",
        "SLD of the station uploaded", "Undertakings signed by authorised signatory",
    ]),
    ("FTC_A_COORD", "ftc", "*", "COORDINATOR", "FTC Stage-1 coordinator checklist (A-annexures)", [
        "Annexure A1 intimation signed", "Annexure A2 element list complete", "Annexure A3 SLD shows dia/bus/breaker status",
        "Annexure A4 SCADA point list attached", "Annexure A5 meter type and location attached",
        "Annexure A6 connection agreement attached", "Submitted at least 10 days before charging",
    ]),
    ("FTC_SCADA", "ftc", "*", "SCADA", "SCADA department checklist", [
        "All SCADA points (A4) mapped at RLDC", "Telemetry undertaking (Format III B) valid", "Data reporting to RLDC verified",
    ]),
    ("FTC_METERING", "ftc", "*", "METERING", "Metering department checklist", [
        "SEM location as per CEA metering regulations", "Dummy meter reading received", "Time drift report within limits",
    ]),
    ("FTC_PROTECTION", "ftc", "*", "PROTECTION", "Protection department checklist", [
        "Relay settings submitted (Main-1/Main-2)", "Protection undertaking (Format III A) signed", "DR/EL channels as per RPC guidelines",
    ]),
    ("FTC_B_COORD", "ftc", "*", "COORDINATOR", "FTC Stage-2 coordinator checklist (B-annexures)", [
        "B1 request and trial-run notice", "B2-B5(a) undertakings", "Statutory clearances (Electrical Inspector)",
        "PTCC route approval (lines only)", "Format TR at least 7 working days ahead",
    ]),
    ("FTC_C_COORD", "ftc", "*", "COORDINATOR", "FTC Stage-3 coordinator checklist (C-annexures)", [
        "C1 Format V request", "C2 SCADA P/Q/V during trial run", "C3 interface meter readings", "C4 DR/EL outputs",
    ]),
    ("COMM_CA_COORD", "comm_cert", "*", "COORDINATOR", "Communication Stage-1 checklist (CA-annexures)", [
        "CA1 intimation 7 days before SAT", "CA2 equipment list", "CA3 link connectivity", "CA4 channel diagram with redundancy",
        "CA5 approval details",
    ]),
    ("COMM_SCADA", "comm_cert", "*", "SCADA", "SCADA department checklist (communication)", [
        "Telemetry received at control centre", "Voice communication tested", "Redundant path verified",
    ]),
]


def _seed_centres(db: Session) -> dict[str, Centre]:
    out = {}
    for code, en, hi, city, region, start in CENTRES:
        c = Centre(code=code, name_en=en, name_hi=hi, city=city, region_code=region, shift_start_time=start)
        db.add(c)
        out[code] = c
    db.flush()
    return out


def _seed_roles(db: Session) -> dict[str, Role]:
    out = {}
    for code, (name, name_hi, mods, level, internal) in ROLE_DEFS.items():
        r = Role(code=code, name=name, name_hi=name_hi, module_scope="*" if "*" in mods else ",".join(mods),
                 permissions_json={"modules": mods, "level": level}, is_internal=internal)
        db.add(r)
        out[code] = r
    db.flush()
    return out


def seed(db: Session) -> None:
    if db.scalar(select(Centre).limit(1)):
        print("Seed: database already seeded; skipping.")
        return
    centres = _seed_centres(db)
    roles = _seed_roles(db)

    for k, v in DEFAULT_SYSTEM_SETTINGS.items():
        db.add(SystemSetting(key=k, value_json=v))

    ents: dict[str, Entity] = {}
    for key, name, short, et, sub, sector, state, cc in ENTITIES:
        e = Entity(name=name, short_name=short, entity_type=et, sub_category=sub, sector=sector, state=state,
                   centre_id=centres[cc].id, fnc_reg_no=f"FNC-{key}-001" if et in ("REGS", "CONV_GEN", "TRANS_LICENSEE") else None,
                   installed_capacity_mw={"THAR": 300.0, "ADANI": 390.0, "NTPC": 1820.0}.get(key))
        db.add(e)
        ents[key] = e
    db.flush()

    subs: dict[str, Substation] = {}
    for code, name, cc, state, kv, st, lat, lng, owner, area, pooling in SUBSTATIONS:
        s = Substation(code=code, name=name, centre_id=centres[cc].id, state=state, voltage_levels_json=kv,
                       substation_type=st, lat=lat, lng=lng, owner_entity_id=ents[owner].id, weather_area=area,
                       bus_scheme="Double main & transfer", is_pooling_station=pooling)
        db.add(s)
        subs[code] = s
    db.flush()

    for name, et, cc, kv, frm, to, owners, extra in ELEMENTS:
        meta = dict(extra.get("metadata", {}))
        g = GridElement(unique_element_id=element_id(db, cc, kv, et), name=name, element_type=et,
                        centre_id=centres[cc].id, voltage_kv=kv,
                        from_substation_id=subs[frm].id if frm else None, to_substation_id=subs[to].id if to else None,
                        is_inter_regional=extra.get("is_inter_regional", False), is_ists=extra.get("is_ists", True),
                        rating=extra.get("rating", ""), length_km=extra.get("length_km"),
                        ftc_date=date(2019, 4, 1), cod_date=date(2019, 6, 1), metadata_json=meta,
                        last_status_change_at=utcnow() - timedelta(days=200))
        db.add(g)
        db.flush()
        for ek, role, km in owners:
            db.add(ElementOwner(grid_element_id=g.id, entity_id=ents[ek].id, ownership_role=role, section_km=km))

    db.add(CommElement(unique_comm_id="NR-OPGW-00001", name="OPGW on 400 kV Bikaner-Bhadla Ckt-1", comm_type="OPGW",
                       centre_id=centres["NRLDC"].id, from_station="Bikaner (PG)", to_station="Bhadla (PG)",
                       owner_entity_id=ents["PG"].id, status="PRE_COMMISSIONING"))
    db.add(CommElement(unique_comm_id="NR-FOTE-00001", name="FOTE (STM-16) at Thar Surya PSS", comm_type="FOTE",
                       centre_id=centres["NRLDC"].id, from_station="Thar Surya PSS", to_station="Bikaner (PG)",
                       owner_entity_id=ents["TPCOMM"].id, status="PRE_COMMISSIONING"))

    for username, full, cat, dept, cc, rcodes, ek in USERS:
        u = User(username=username, full_name=full, user_category=cat, department=dept,
                 email=f"{username}@oms-demo.grid-india.local", mobile=f"98{zlib.crc32(username.encode()) % 10**8:08d}",
                 email_verified=True, mobile_verified=True,
                 centre_id=centres[cc].id if cc else None, entity_id=ents[ek].id if ek else None,
                 password_hash=hash_password(DEMO_PASSWORD), is_2fa_enabled=True,
                 last_contact_verified_at=utcnow() - timedelta(days=10),
                 password_changed_at=utcnow())
        db.add(u)
        db.flush()
        for rc in rcodes:
            db.add(UserRole(user_id=u.id, role_id=roles[rc].id, centre_id=centres[cc].id if cc else None))
    db.flush()
    # one user due for 3-monthly contact review to demonstrate the pop-up
    demo = db.scalar(select(User).where(User.username == "pg_user"))
    demo.last_contact_verified_at = utcnow() - timedelta(days=120)

    for code, module, cat, owner, title, items in CHECKLISTS:
        db.add(Checklist(code=code, module=module, element_category=cat, owner_role=owner, title=title,
                         items_json=[{"key": f"c{i + 1}", "text_en": t, "text_hi": "", "mandatory": True}
                                     for i, t in enumerate(items)]))

    for module, step in [
        ("cas", "TICKET_CREATED"), ("cas", "TICKET_ESCALATED"), ("cas", "TICKET_RESOLVED"),
        ("registration", "CASE_SUBMITTED"), ("registration", "CASE_RETURNED"), ("registration", "LETTER_ISSUED"),
        ("ftc", "CASE_FORWARDED"), ("ftc", "CASE_RETURNED"), ("ftc", "FORMAT_TR_UPLOADED"), ("ftc", "CERTIFICATE_ISSUED"),
        ("comm_cert", "CASE_FORWARDED"), ("realtime", "CONSENT_REQUESTED"), ("realtime", "CODE_ISSUED"),
        ("realtime", "PRE_CHARGING_ALERT"), ("outage_coord", "D1_DECISION"), ("protection", "EVENT_CREATED"),
        ("availability", "SHEET_GENERATED"),
    ]:
        db.add(NotificationToggle(module=module, step_code=step, email_enabled=True, sms_enabled=True))

    contacts = [
        ("Chief Engineer (SLDC)", "RVPN", "STATE", "Jaipur", "RVPN"),
        ("SE Grid Operation", "UPPTCL", "STATE", "Lucknow", "UPPTCL"),
        ("Plant In-charge", "Thar Surya 1 Pvt Ltd", "RE_GEN", "Bikaner", "THAR"),
        ("Control Room", "Adani Hybrid Energy Jaisalmer One Ltd", "RE_GEN", "Jaisalmer", "ADANI"),
        ("Shift Charge Engineer", "NTPC Dadri", "MISC", "Dadri", "NTPC"),
        ("NR-1 Control Room", "POWERGRID", "MISC", "Ballabhgarh", "PG"),
        ("SLDC Shift In-charge", "HVPN", "STATE", "Panipat", "HVPN"),
    ]
    for desig, org, cat, loc, ek in contacts:
        db.add(EntityContact(entity_id=ents[ek].id, name=f"{org} {desig}", designation=desig, organisation=org,
                             category=cat, location=loc, phone1=f"91{zlib.crc32(org.encode()) % 10**8:08d}",
                             email1=f"{ek.lower()}@oms-demo.local",
                             alert_sms_flags_json={"ALERT": True, "EMERGENCY": True, "EXTREME": True},
                             alert_email_flags_json={"ALERT": True, "EMERGENCY": True, "EXTREME": cat != "MISC"}))

    from app.db import seed_modules

    seed_modules.seed_all(db, centres, ents, subs)
    db.commit()
    print(f"Seed complete: {len(CENTRES)} centres, {len(ROLE_DEFS)} roles, {len(USERS)} users, "
          f"{len(ELEMENTS)} grid elements. Demo password: {DEMO_PASSWORD}")


def main(argv: list[str]) -> None:
    eng = get_engine()
    if "--reset" in argv:
        Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    with SessionLocal() as db:
        seed(db)


if __name__ == "__main__":
    main(sys.argv[1:])
