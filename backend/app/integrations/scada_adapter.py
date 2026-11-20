"""SCADA adapter (mock). Bi-directional JSON / XML / CSV exchange contract (TS Cl. 11.2(f) p.79-80; FRD API-17).

The mock generates plausible analog values (frequency, demand, bus voltage) with value,
timestamp and quality code, exactly the tuple the upgraded SCADA web services will provide.
`ingest_csv` shows the existing-SCADA path (CSV file exchange).
"""
import csv
import io
import math
import random
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

REGION_DEMAND = {"NLDC": 245000, "NRLDC": 82000, "WRLDC": 74000, "SRLDC": 61000, "ERLDC": 30000, "NERLDC": 3600}


def _wave(period_s: int, amp: float) -> float:
    t = datetime.now(timezone.utc).timestamp()
    return amp * math.sin(2 * math.pi * (t % period_s) / period_s)


def analog(tag: str, centre: str = "NLDC") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    if tag == "FREQ":
        v = round(50.0 + _wave(300, 0.06) + random.uniform(-0.01, 0.01), 3)
    elif tag == "DEMAND":
        v = round(REGION_DEMAND.get(centre, 50000) * (1 + _wave(3600, 0.04)) + random.uniform(-200, 200))
    elif tag.startswith("V:"):
        nominal = float(tag.split(":")[2]) if tag.count(":") >= 2 else 400.0
        v = round(nominal * (1.0 + _wave(900, 0.03) + random.uniform(-0.005, 0.005)), 1)
    elif tag == "DSM_RATE":
        v = round(3.2 + _wave(1800, 0.8), 2)
    else:
        v = round(random.uniform(0, 100), 2)
    return {"tag": tag, "value": v, "timestamp": now, "quality": "GOOD"}


def bus_voltage(station_code: str, kv: float) -> dict:
    return analog(f"V:{station_code}:{int(kv)}")


def grid_tiles(centre: str = "NLDC") -> list[dict]:
    f = analog("FREQ", centre)
    d = analog("DEMAND", centre)
    dsm = analog("DSM_RATE", centre)
    rev = int(datetime.now(timezone.utc).timestamp() // 900) % 120 + 1
    return [
        {"key": "freq", "label_en": "Grid frequency (Hz)", "label_hi": "ग्रिड आवृत्ति (हर्ट्ज़)", "value": f["value"],
         "tone": "green" if 49.9 <= f["value"] <= 50.05 else "amber"},
        {"key": "demand", "label_en": f"Demand met {centre} (MW)", "label_hi": f"पूरी की गई मांग {centre} (मेगावाट)", "value": d["value"], "tone": "grid"},
        {"key": "dsm", "label_en": "DSM rate (₹/kWh)", "label_hi": "डीएसएम दर (₹/kWh)", "value": dsm["value"], "tone": "grid"},
        {"key": "rev", "label_en": "Current schedule revision", "label_hi": "वर्तमान शेड्यूल संशोधन", "value": f"R{rev}", "tone": "grid",
         "sub": "Changes from last revision: 3 entities"},
    ]


def to_xml(points: list[dict]) -> str:
    root = ET.Element("ScadaData")
    for p in points:
        ET.SubElement(root, "Point", {k: str(v) for k, v in p.items()})
    return ET.tostring(root, encoding="unicode")


def ingest_csv(text: str) -> list[dict]:
    """Existing SCADA systems share data only via CSV/Excel (TS p.80 note)."""
    return [{"tag": r["tag"], "value": float(r["value"]), "timestamp": r.get("timestamp", ""), "quality": r.get("quality", "GOOD")}
            for r in csv.DictReader(io.StringIO(text))]
