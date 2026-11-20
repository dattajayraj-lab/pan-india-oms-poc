"""SPS Status (TS Cl. 11.4.9 p.206; FRD SPS-01..04)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import scheduler
from app.core.audit import audit
from app.core.events import hub
from app.core.rbac import get_current_user, is_admin, is_external, role_codes
from app.db.base import utcnow
from app.db.session import get_db
from app.modules.auth_rbac.models import Centre
from app.modules.sps_status.models import SpsScheme, SpsStatusLog
from app.utils.exports import export

router = APIRouter(prefix="/api/v1/sps", tags=["sps"])


def out(db: Session, s: SpsScheme) -> dict:
    return {"id": s.id, "sps_id": s.sps_id, "sps_name": s.sps_name, "centre": db.get(Centre, s.centre_id).code, "owner_entity_id": s.owner_entity_id,
            "status": s.current_status, "updated_at": s.updated_at, "logic": s.logic_description, "fields": s.template_fields_json}


@router.get("/schemes")
def schemes(fmt: str = "json", db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = [out(db, s) for s in db.scalars(select(SpsScheme).order_by(SpsScheme.sps_id))]
    if is_external(user):
        rows = [r for r in rows if r["owner_entity_id"] == user.entity_id]
    if fmt != "json":
        return export(fmt, "SPS healthiness status", "एसपीएस स्थिति", [("sps_id", "SPS ID", "एसपीएस आईडी"), ("sps_name", "Scheme", "योजना"),
                      ("centre", "Centre", "केंद्र"), ("status", "Status", "स्थिति"), ("updated_at", "Updated", "अद्यतन")], rows, "sps_status")
    return rows


class StatusIn(BaseModel):
    status: str = Field(pattern="^(ON|OFF|DEGRADED)$")
    remarks: str = ""


@router.post("/schemes/{sid}/status")
def set_status(sid: int, body: StatusIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    s = db.get(SpsScheme, sid)
    if not (is_admin(user) or role_codes(user) & {"SPS_COORDINATOR", "RT_COORDINATOR"} or (is_external(user) and s.owner_entity_id == user.entity_id)):
        raise HTTPException(403)
    s.current_status, s.updated_at = body.status, utcnow()
    db.add(SpsStatusLog(sps_scheme_id=s.id, status=body.status, source="USER", remarks=body.remarks, updated_by=user.id))
    audit(db, user, "sps", "SPS_STATUS", "sps", s.sps_id, new=body.model_dump())
    hub.publish(db.get(Centre, s.centre_id).code, "sps_status", {"sps_id": s.sps_id, "status": body.status})
    db.commit()
    return out(db, s)


@router.get("/schemes/{sid}/timeline")
def timeline(sid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [{"status": l.status, "source": l.source, "remarks": l.remarks, "at": l.updated_at}
            for l in db.scalars(select(SpsStatusLog).where(SpsStatusLog.sps_scheme_id == sid).order_by(SpsStatusLog.updated_at))]


@router.post("/scada-sync")
def scada_sync(body: list[dict], db: Session = Depends(get_db), user=Depends(get_current_user)):
    """SCADA push of SPS status [{"sps_id","status"}] (mock of the bi-directional interface)."""
    n = 0
    for item in body:
        s = db.scalar(select(SpsScheme).where(SpsScheme.sps_id == item["sps_id"]))
        if s and item["status"] in ("ON", "OFF", "DEGRADED") and s.current_status != item["status"]:
            s.current_status, s.updated_at = item["status"], utcnow()
            db.add(SpsStatusLog(sps_scheme_id=s.id, status=item["status"], source="SCADA"))
            n += 1
    db.commit()
    return {"updated": n}


_ = scheduler
