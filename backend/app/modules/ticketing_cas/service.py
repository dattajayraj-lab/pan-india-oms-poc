"""CAS business rules: SLA matrix, escalation levels 0-3, availability & AMC penalty (TS Ch.5, Cl. 10.6)."""
import calendar
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import scheduler
from app.db.base import utcnow
from app.modules.ticketing_cas.models import DowntimeEvent, Ticket, TicketHistory

# Severity -> (initial response, resolution)  (TS Cl. 10.6 p.67; CS F2-F5)
SLA = {1: (timedelta(minutes=30), timedelta(hours=2)), 2: (timedelta(hours=2), timedelta(hours=12)),
       3: (timedelta(days=1), timedelta(days=2)), 4: (timedelta(days=1), timedelta(days=5))}

# Availability slab -> penalty % of monthly AMC (TS Cl. 10.6 p.68-69)
SLABS = [(99.95, 0), (99.45, 10), (98.95, 20), (98.45, 30), (97.95, 40), (97.45, 50), (96.95, 55),
         (96.45, 60), (95.95, 65), (95.45, 70), (94.95, 75), (90.00, 80), (0.0, 80)]

OPEN_STATES = ("OPEN", "ASSIGNED", "IN_PROGRESS", "AWAITING_INPUT", "REOPENED")


def history(db: Session, t: Ticket, event: str, user=None, comment: str = "", from_level=None, to_level=None,
            doc_id=None, internal=False) -> None:
    db.add(TicketHistory(ticket_id=t.id, actor_user_id=getattr(user, "id", None),
                         actor_name=getattr(user, "full_name", "SYSTEM"), event=event, from_level=from_level,
                         to_level=to_level, status=t.status, comment=comment, attachment_doc_id=doc_id, is_internal=internal))


def apply_sla(t: Ticket) -> None:
    if t.severity:
        resp, reso = SLA[t.severity]
        t.sla_response_due = t.created_at + resp
        t.sla_resolution_due = t.created_at + reso


def escalation_thresholds(db: Session) -> tuple[float, float]:
    from app.modules.auth_rbac.service import get_setting

    return float(get_setting(db, "cas_l1_to_l2_hours") or 4), float(get_setting(db, "cas_l2_to_l3_hours") or 8)


@scheduler.register("cas_auto_escalation")
def auto_escalate(db: Session, now: datetime | None = None) -> list[str]:
    """Level 1 -> 2 -> 3 when unresolved beyond Admin-configured time (TS Ch.5 p.46)."""
    from app.integrations.notifier import notify_users
    from app.modules.auth_rbac.models import User

    now = now or utcnow()
    h12, h23 = escalation_thresholds(db)
    escalated = []
    for t in db.scalars(select(Ticket).where(Ticket.status.in_(OPEN_STATES), Ticket.escalation_level.in_([1, 2]))).all():
        limit = timedelta(hours=h12 if t.escalation_level == 1 else h23)
        if now - t.level_entered_at >= limit:
            frm = t.escalation_level
            t.escalation_level += 1
            t.level_entered_at = now
            history(db, t, "AUTO_ESCALATED", comment=f"Unresolved for {limit} at Level {frm}", from_level=frm, to_level=t.escalation_level)
            escalated.append(t.ticket_number)
            heads = db.scalars(select(User).where(User.centre_id == t.centre_id, User.is_active)).all()
            heads = [u for u in heads if {r.role.code for r in u.roles} & {"HEAD_RLDC", "HEAD_NLDC", "CAS_HELPDESK"}]
            notify_users(db, heads, f"Ticket {t.ticket_number} auto-escalated to Level {t.escalation_level}",
                         module="cas", step_code="TICKET_ESCALATED", link=f"/cas/{t.id}", centre_id=t.centre_id)
    return escalated


def sla_status(t: Ticket, now: datetime | None = None) -> dict:
    now = now or utcnow()
    out = {"response_breached": False, "resolution_breached": False, "response_delay_min": 0, "resolution_delay_min": 0}
    if t.sla_response_due:
        actual = t.responded_at or now
        if actual > t.sla_response_due:
            out["response_breached"] = True
            out["response_delay_min"] = int((actual - t.sla_response_due).total_seconds() // 60)
    if t.sla_resolution_due:
        actual = t.resolved_at or now
        if actual > t.sla_resolution_due:
            out["resolution_breached"] = True
            out["resolution_delay_min"] = int((actual - t.sla_resolution_due).total_seconds() // 60)
    return out


def penalty_pct(availability: float) -> int:
    for floor, pct in SLABS:
        if availability >= floor:
            return pct
    return 80


def _overlap_minutes(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> float:
    s, e = max(a0, b0), min(a1, b1)
    return max((e - s).total_seconds() / 60, 0)


def month_availability(db: Session, year: int, month: int) -> dict:
    """Availability % = (SU - D)/SU x 100, SU = T - M (TS Cl. 10.6 p.68)."""
    days = calendar.monthrange(year, month)[1]
    m0 = datetime(year, month, 1)
    m1 = m0 + timedelta(days=days)
    total = days * 1440
    maint = down = 0.0
    for ev in db.scalars(select(DowntimeEvent).where(DowntimeEvent.started_at < m1, DowntimeEvent.ended_at > m0)):
        mins = _overlap_minutes(ev.started_at, ev.ended_at, m0, m1)
        if ev.kind == "MAINTENANCE":
            maint += mins
        elif ev.kind == "DOWNTIME":
            down += mins
    # Severity-1 tickets (complete application failure) beyond resolution SLA count as downtime (POC assumption).
    for t in db.scalars(select(Ticket).where(Ticket.severity == 1, Ticket.created_at < m1)):
        if t.sla_resolution_due:
            end = t.resolved_at or min(utcnow(), m1)
            down += _overlap_minutes(t.created_at, end, m0, m1)
    su = total - maint
    avail = round((su - down) / su * 100, 2) if su else 100.0
    return {"month": f"{year}-{month:02d}", "total_min": total, "maintenance_min": round(maint), "scheduled_uptime_min": round(su),
            "downtime_min": round(down), "availability_pct": avail, "penalty_pct": penalty_pct(avail)}


def quarter_months(year: int, quarter: int) -> list[tuple[int, int]]:
    start = 3 * (quarter - 1) + 1
    return [(year, m) for m in range(start, start + 3)]
