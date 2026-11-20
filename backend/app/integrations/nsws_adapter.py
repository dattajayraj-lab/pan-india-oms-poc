"""NSWS (National Single Window System) adapter - mock (TS Cl. 11.4.1 A, p.84-86; FRD API-18, REG-01/02/10).

Contract: fetch(nsws_ref) returns applicant data (Annexure-1) and category-wise model files after CTUIL
acknowledges on NSWS; push_status() sends file-wise verification + compliance sheet status back.
NSWS itself is not customised under this project; only API integration is in scope.
"""
import logging

log = logging.getLogger("oms.nsws")
PUSH_LOG: list[dict] = []

MODEL_FILE_CATEGORIES = ["PSSE_STEADY_STATE", "PSSE_DYNAMIC", "PSCAD_EMT_MODEL", "MODEL_USER_GUIDE", "SIMULATION_REPORT",
                         "SINGLE_GEN_EQUIVALENT", "IBR_DATASHEET"]


def fetch(nsws_ref: str) -> dict:
    n = sum(ord(c) for c in nsws_ref) % 90 + 10
    return {
        "nsws_ref_no": nsws_ref,
        "applicant": {"name": f"Suryodaya Renewables {n} Pvt Ltd", "state": "Rajasthan", "gst_no": f"08ABCDE{n:04d}F1Z5",
                      "pan_no": f"ABCDE{n:04d}F", "contact_email": f"connectivity{n}@suryodaya.example",
                      "contact_mobile": f"98{n:08d}"},
        "project": {"name": f"Suryodaya Solar Park {n}", "energy_source": "SOLAR", "installed_capacity_mw": 50 * (n % 6 + 2),
                    "connectivity_mw": 50 * (n % 6 + 2), "nearest_ists_substation": "Bikaner (PG)", "voltage_kv": 220,
                    "district": "Bikaner", "lat": 28.0, "lng": 73.3},
        "files": [{"category": c, "filename": f"{nsws_ref}_{c}.pdf", "content": b"%PDF-1.4 NSWS mock file " + c.encode()}
                  for c in MODEL_FILE_CATEGORIES],
    }


def push_status(nsws_ref: str, payload: dict) -> None:
    PUSH_LOG.append({"nsws_ref": nsws_ref, **payload})
    log.info("NSWS push %s: %s", nsws_ref, payload.get("event"))
