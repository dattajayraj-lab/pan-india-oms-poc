"""ID generators: case numbers, ticket numbers, Unique Element IDs (FRD API-14, FTC-16).

POC syntax pending the Naming Convention Document (TS Cl. 2.6(m)):
  Case   : {MODULE}/{CENTRE}/{YYYY}/{SEQ:05d}       e.g. FTC/NRLDC/2026/00012
  Ticket : CAS/{CENTRE}/{YYYYMM}/{SEQ:05d}
  Element: {REGION}-{KV}{TYPE}-{SEQ:05d}             e.g. NR-400TL-00012
  Code   : {CENTRE}/{YYMMDD}/{SEQ:04d}               e.g. NRLDC/261120/0007
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow

REGION_OF_CENTRE = {"NLDC": "NL", "NRLDC": "NR", "ERLDC": "ER", "WRLDC": "WR", "SRLDC": "SR", "NERLDC": "NE"}


def next_seq(db: Session, key: str) -> int:
    from app.modules.master_registry.models import ElementIdSequence

    row = db.scalar(select(ElementIdSequence).where(ElementIdSequence.key == key))
    if row is None:
        row = ElementIdSequence(key=key, value=0)
        db.add(row)
        db.flush()
    row.value += 1
    db.flush()
    return row.value


def case_number(db: Session, module: str, centre_code: str, when: datetime | None = None) -> str:
    year = (when or utcnow()).year
    prefix = f"{module.upper()}/{centre_code}/{year}"
    return f"{prefix}/{next_seq(db, prefix):05d}"


def ticket_number(db: Session, centre_code: str) -> str:
    prefix = f"CAS/{centre_code}/{utcnow():%Y%m}"
    return f"{prefix}/{next_seq(db, prefix):05d}"


def element_id(db: Session, centre_code: str, voltage_kv: float, element_type: str) -> str:
    from app.modules.master_registry.models import ELEMENT_TYPES

    type_code = ELEMENT_TYPES.get(element_type, ("XX", ""))[0]
    region = REGION_OF_CENTRE.get(centre_code, "XX")
    prefix = f"{region}-{int(voltage_kv)}{type_code}"
    return f"{prefix}-{next_seq(db, 'EL:' + prefix):05d}"


def code_number(db: Session, centre_code: str) -> str:
    prefix = f"{centre_code}/{utcnow():%y%m%d}"
    return f"{prefix}/{next_seq(db, 'CODE:' + prefix):04d}"


def simple_number(db: Session, prefix: str) -> str:
    return f"{prefix}/{next_seq(db, prefix):05d}"
