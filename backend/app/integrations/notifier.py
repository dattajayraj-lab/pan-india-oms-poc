"""Configurable e-mail / SMS / in-app / push dispatcher (TS Cl. 2.3; FRD NOT-01..05).

POC: e-mail and SMS are written to the `notifications` outbox table and logged to the
console instead of hitting the Owner's SMTP server and SMS gateway. Each send checks
the per-step enable/disable toggles managed by Coordinator/Admin logins.
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

log = logging.getLogger("oms.notifier")


def _toggle(db: Session, module: str, step_code: str, centre_id: int | None):
    from app.modules.auth_rbac.models import NotificationToggle

    q = select(NotificationToggle).where(NotificationToggle.module == module,
                                         NotificationToggle.step_code == step_code)
    rows = db.scalars(q).all()
    specific = next((r for r in rows if r.centre_id == centre_id), None)
    generic = next((r for r in rows if r.centre_id is None), None)
    t = specific or generic
    return (t.email_enabled, t.sms_enabled) if t else (True, True)


def notify_users(db: Session, users, subject: str, body: str = "", module: str = "", step_code: str = "",
                 link: str = "", centre_id: int | None = None, channels=("INAPP", "EMAIL", "SMS")) -> int:
    from app.core.events import hub
    from app.modules.auth_rbac.models import Notification

    email_on, sms_on = _toggle(db, module, step_code, centre_id) if step_code else (True, True)
    sent = 0
    for u in users:
        if u is None:
            continue
        if "INAPP" in channels:
            db.add(Notification(user_id=u.id, channel="INAPP", recipient=u.username, module=module,
                                subject=subject, body=body, link=link))
            sent += 1
        if "EMAIL" in channels and email_on and u.email:
            db.add(Notification(user_id=u.id, channel="EMAIL", recipient=u.email, module=module,
                                subject=subject, body=body, link=link, is_read=True))
            log.info("EMAIL to %s: %s", u.email, subject)
        if "SMS" in channels and sms_on and u.mobile:
            db.add(Notification(user_id=u.id, channel="SMS", recipient=u.mobile, module=module,
                                subject=subject[:160], body="", link=link, is_read=True))
            log.info("SMS to %s: %s", u.mobile, subject[:160])
        hub.publish(f"user:{u.id}", "notification", {"subject": subject, "module": module, "link": link})
    return sent


def send_raw(db: Session, channel: str, recipient: str, subject: str, body: str = "", module: str = "") -> None:
    """For recipients that are contacts rather than user logins (Message Alerts module)."""
    from app.modules.auth_rbac.models import Notification

    db.add(Notification(user_id=None, channel=channel, recipient=recipient, module=module,
                        subject=subject[:300], body=body, is_read=True))
    log.info("%s to %s: %s", channel, recipient, subject[:120])
