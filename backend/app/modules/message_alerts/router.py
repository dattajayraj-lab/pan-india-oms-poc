"""Message Alerts (TS Cl. 11.4.8 p.200-205; FRD MA-01..08)."""
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.rbac import get_current_user, is_admin, role_codes
from app.db.session import get_db
from app.integrations import scada_adapter
from app.integrations.notifier import send_raw
from app.modules.auth_rbac.models import Centre
from app.modules.master_registry.models import Entity, EntityContact, GridElement, Substation
from app.modules.message_alerts.models import MessageTemplate, ViolationMessage

router = APIRouter(prefix="/api/v1/alerts", tags=["message-alerts"])


def _coord(user) -> bool:
    return is_admin(user) or bool(role_codes(user) & {"ALERTS_COORDINATOR", "RT_COORDINATOR", "SHIFT_INCHARGE"})


class _Safe(dict):
    def __missing__(self, k):
        return "{" + k + "}"


def render(t: MessageTemplate, payload: dict, centre: str) -> tuple[str, str]:
    data = _Safe({**payload, "centre": centre})
    return t.sms_template.format_map(data), t.email_template.format_map(data)


@router.get("/templates")
def templates(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [{"code": t.code, "name_en": t.name_en, "category": t.category, "severity": t.severity, "fields": t.fields_json,
             "sms_template": t.sms_template} for t in db.scalars(select(MessageTemplate).order_by(MessageTemplate.id))]


@router.get("/targets")
def targets(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Drop-downs: utilities (State), pooling stations with RE generators under them, misc organisations."""
    pools = []
    for s in db.scalars(select(Substation).where(Substation.is_pooling_station)):
        gens = {o.entity.name for e in db.scalars(select(GridElement)) for o in e.owners
                if o.entity.entity_type == "REGS" and (e.to_substation_id == s.id or e.from_substation_id == s.id)}
        pools.append({"pooling_station": s.name, "generators": sorted(gens)})
    states = sorted({c.organisation for c in db.scalars(select(EntityContact).where(EntityContact.category == "STATE"))})
    return {"STATE": states, "RE_GEN": pools, "MISC": sorted({c.organisation for c in db.scalars(select(EntityContact).where(EntityContact.category == "MISC"))}),
            "live": {"frequency": scada_adapter.analog("FREQ")["value"]}}


class SendIn(BaseModel):
    template_code: str
    category: str = Field(pattern="^(STATE|RE_GEN|MISC)$")
    targets: list[str]
    payload: dict = {}
    channels: list[str] = ["SMS", "EMAIL"]
    centre_code: str = "NRLDC"
    preview: bool = False


@router.post("/send")
def send(body: SendIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Bulk SMS/e-mail to contacts of selected utilities/RE generators honouring per-contact enable flags (TS p.201-203)."""
    if not _coord(user):
        raise HTTPException(403, "Alerts Coordinator only")
    t = db.scalar(select(MessageTemplate).where(MessageTemplate.code == body.template_code))
    if t is None:
        raise HTTPException(404, "Template not found")
    if not body.targets:
        raise HTTPException(422, "Select at least one recipient group")
    sev = {"ALERT": "ALERT", "EMERGENCY": "EMERGENCY", "EXTREME": "EXTREME"}[t.severity]
    out = []
    total = 0
    for tgt in body.targets:
        payload = {**body.payload, "utility": tgt, "generator": tgt}
        sms, email = render(t, payload, body.centre_code)
        contacts = db.scalars(select(EntityContact).where(EntityContact.organisation == tgt)).all()
        n = 0
        if not body.preview:
            for c in contacts:
                if "SMS" in body.channels and c.alert_sms_flags_json.get(sev):
                    for ph, on in ((c.phone1, c.phone1_enabled), (c.phone2, c.phone2_enabled)):
                        if ph and on:
                            send_raw(db, "SMS", ph, sms, module="alerts")
                            n += 1
                if "EMAIL" in body.channels and c.alert_email_flags_json.get(sev):
                    for em, on in ((c.email1, c.email1_enabled), (c.email2, c.email2_enabled)):
                        if em and on:
                            send_raw(db, "EMAIL", em, t.email_subject, email, module="alerts")
                            n += 1
            ent = db.scalar(select(Entity).where(Entity.name == tgt))
            db.add(ViolationMessage(centre_id=db.scalar(select(Centre).where(Centre.code == body.centre_code)).id, category=body.category,
                                    template_code=t.code, target_entity_id=ent.id if ent else None, target_label=tgt, payload_json=payload,
                                    rendered_sms=sms, rendered_email=email, channels_json=body.channels, recipients_count=n, sent_by=user.id,
                                    kind="FLASH" if t.code.startswith("FLASH") else "VIOLATION"))
        total += n
        out.append({"target": tgt, "sms": sms, "recipients": n})
    if not body.preview:
        audit(db, user, "alerts", "ALERT_SENT", "template", t.code, new={"targets": body.targets, "recipients": total})
        db.commit()
    return {"messages": out, "total_recipients": total, "preview": body.preview}


class FlashIn(BaseModel):
    subject: str
    html: str
    recipients: list[str]


@router.post("/flash-report")
def flash_report(body: FlashIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Rich-text flash report e-mailed from the same page (TS p.205)."""
    if not _coord(user):
        raise HTTPException(403)
    for r in body.recipients:
        send_raw(db, "EMAIL", r, body.subject, body.html, module="alerts")
    db.add(ViolationMessage(centre_id=user.centre_id or 1, category="MISC", template_code="FLASH_REPORT", target_label=", ".join(body.recipients),
                            rendered_email=body.html, rendered_sms=body.subject, channels_json=["EMAIL"], recipients_count=len(body.recipients),
                            sent_by=user.id, kind="FLASH"))
    db.commit()
    return {"sent": len(body.recipients)}


@router.get("/history")
def history(target: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(ViolationMessage).order_by(ViolationMessage.sent_at.desc()).limit(500)
    if target:
        stmt = stmt.where(ViolationMessage.target_label == target)
    rows = db.scalars(stmt).all()
    return {"rows": [{"id": m.id, "sent_at": m.sent_at, "category": m.category, "template": m.template_code, "target": m.target_label,
                      "sms": m.rendered_sms, "recipients": m.recipients_count, "kind": m.kind} for m in rows],
            "by_target": dict(Counter(m.target_label for m in rows)), "by_template": dict(Counter(m.template_code for m in rows))}


def contact_out(c: EntityContact) -> dict:
    return {k: getattr(c, k) for k in ("id", "entity_id", "name", "designation", "organisation", "location", "category", "phone1", "phone1_enabled",
                                       "phone2", "phone2_enabled", "email1", "email1_enabled", "email2", "email2_enabled",
                                       "alert_sms_flags_json", "alert_email_flags_json")}


@router.get("/contacts")
def contacts(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [contact_out(c) for c in db.scalars(select(EntityContact).order_by(EntityContact.organisation, EntityContact.name))]


@router.post("/contacts")
def add_contact(body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not _coord(user):
        raise HTTPException(403)
    allowed = set(contact_out(EntityContact(name="")).keys()) - {"id"}
    c = EntityContact(**{k: v for k, v in body.items() if k in allowed})
    c.alert_sms_flags_json = c.alert_sms_flags_json or {"ALERT": True, "EMERGENCY": True, "EXTREME": True}
    c.alert_email_flags_json = c.alert_email_flags_json or {"ALERT": True, "EMERGENCY": True, "EXTREME": True}
    db.add(c)
    db.commit()
    return contact_out(c)


@router.patch("/contacts/{cid}")
def edit_contact(cid: int, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not _coord(user):
        raise HTTPException(403)
    c = db.get(EntityContact, cid)
    for k, v in body.items():
        if k in contact_out(c) and k != "id":
            setattr(c, k, v)
    db.commit()
    return contact_out(c)


@router.delete("/contacts/{cid}")
def del_contact(cid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not _coord(user):
        raise HTTPException(403)
    db.delete(db.get(EntityContact, cid))
    db.commit()
    return {"ok": True}
