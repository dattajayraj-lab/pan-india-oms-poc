"""Outage-period records for availability verification (TS Cl. 11.4.5; FRD AV-05..13)."""
import calendar
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.availability_verify.models import AvailabilityRecord
from app.modules.master_registry.models import GridElement

EXCLUDED_TAGS = {"NOT_FOR_AVAILABILITY"}


def _owner(el: GridElement) -> int | None:
    pref = ["LINE_OWNER", "ASSET_OWNER", "SECTION_OWNER", "END1_STATION"]
    for role in pref:
        for o in el.owners:
            if o.ownership_role == role:
                return o.entity_id
    return el.owners[0].entity_id if el.owners else None


def record_outage_period(db: Session, el: GridElement, start: datetime, end: datetime, code=None, req=None) -> list[AvailabilityRecord]:
    """Each shutdown is a separate outage-period record; split at month boundaries (month N reviewed in N+1)."""
    if code is not None and set(code.tags_json or []) & EXCLUDED_TAGS:
        return []
    owner = _owner(el)
    if owner is None or end <= start:
        return []
    head = (req.availability_head_proposed if req and req.availability_head_proposed else "SELF")
    if req and req.occ_plan_id:
        from app.modules.outage_coord.models import OccOutagePlan

        plan = db.get(OccOutagePlan, req.occ_plan_id)
        if plan and plan.non_auto_ar:
            return []
        head = plan.availability_head_rldc or plan.availability_head_proposed or head
        cat = plan.category_code
    else:
        cat = "C03" if req and req.request_category == "TRIPPED" else ""
    out = []
    s = start
    while s < end:
        last_day = calendar.monthrange(s.year, s.month)[1]
        month_end = datetime(s.year, s.month, last_day) + timedelta(days=1)
        e = min(end, month_end)
        r = AvailabilityRecord(centre_id=el.centre_id, billing_month=f"{s.year}-{s.month:02d}", outage_code_id=code.id if code else None,
                               grid_element_id=el.id, owner_entity_id=owner, outage_start=s, outage_end=e,
                               availability_head=head.upper() if head else "SELF", category_code=cat)
        db.add(r)
        out.append(r)
        s = e
    db.flush()
    return out


def hours(r: AvailabilityRecord) -> float:
    return round((r.outage_end - r.outage_start).total_seconds() / 3600, 2)


_ = select
