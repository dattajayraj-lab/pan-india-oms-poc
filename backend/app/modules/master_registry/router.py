"""Master registry: entities, ownership history, substations, grid elements (FRD RTO-14..20, UM-24, API-14)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.rbac import get_current_user, is_admin, is_external, role_codes, visible_centre_ids
from app.db.base import utcnow
from app.db.session import get_db
from app.modules.auth_rbac.models import Centre
from app.modules.master_registry.models import (ELEMENT_TYPES, CommElement, ElementOwner, Entity, EntityOwnershipHistory,
                                                GridElement, Substation)
from app.utils.ids import element_id

router = APIRouter(prefix="/api/v1/master", tags=["master-registry"])


def entity_out(e: Entity) -> dict:
    return {"id": e.id, "name": e.name, "short_name": e.short_name, "entity_type": e.entity_type, "sub_category": e.sub_category,
            "sector": e.sector, "state": e.state, "centre_id": e.centre_id, "nsws_reg_no": e.nsws_reg_no,
            "cea_egen_no": e.cea_egen_no, "fnc_reg_no": e.fnc_reg_no, "gst_no": e.gst_no, "pan_no": e.pan_no,
            "installed_capacity_mw": e.installed_capacity_mw, "status": e.status}


def element_out(g: GridElement) -> dict:
    return {"id": g.id, "unique_element_id": g.unique_element_id, "name": g.name, "element_type": g.element_type,
            "element_type_label": ELEMENT_TYPES.get(g.element_type, ("", g.element_type))[1], "centre": g.centre.code,
            "voltage_kv": g.voltage_kv, "from_substation": g.from_substation.name if g.from_substation else None,
            "to_substation": g.to_substation.name if g.to_substation else None,
            "from_region": g.from_substation.centre.code if g.from_substation else None,
            "to_region": g.to_substation.centre.code if g.to_substation else None,
            "weather_area": g.from_substation.weather_area if g.from_substation else "",
            "is_inter_regional": g.is_inter_regional, "is_trans_national": g.is_trans_national, "is_ists": g.is_ists,
            "status": g.status, "rating": g.rating, "length_km": g.length_km, "ftc_date": g.ftc_date, "cod_date": g.cod_date,
            "realtime_enabled": g.realtime_enabled, "metadata": g.metadata_json,
            "owners": [{"entity_id": o.entity_id, "entity": o.entity.short_name or o.entity.name, "role": o.ownership_role,
                        "section_km": o.section_km} for o in g.owners],
            "notes": g.operator_notes_append_only_json, "comments": g.operator_comments,
            "last_status_change_at": g.last_status_change_at, "source_ftc_case_id": g.source_ftc_case_id}


# ------------------------------------------------------------------ entities
@router.get("/entities")
def entities(entity_type: str | None = None, q: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(Entity).order_by(Entity.name)
    if entity_type:
        stmt = stmt.where(Entity.entity_type == entity_type)
    if q:
        stmt = stmt.where(Entity.name.ilike(f"%{q}%"))
    return [entity_out(e) for e in db.scalars(stmt)]


class EntityIn(BaseModel):
    name: str
    short_name: str = ""
    entity_type: str = Field(pattern="^(REGS|CONV_GEN|TRANS_LICENSEE|COMM_PROVIDER|BULK_CONSUMER|SLDC|CTU|RPC)$")
    sub_category: str = ""
    sector: str = "PRIVATE"
    state: str = ""
    centre_code: str = "NRLDC"
    gst_no: str | None = Field(None, pattern=r"^[0-9A-Z]{15}$")
    pan_no: str | None = Field(None, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    installed_capacity_mw: float | None = Field(None, ge=0, le=20000)


@router.post("/entities")
def create_entity(body: EntityIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if is_external(user):
        raise HTTPException(403)
    centre = db.scalar(select(Centre).where(Centre.code == body.centre_code))
    e = Entity(**body.model_dump(exclude={"centre_code"}), centre_id=centre.id if centre else None)
    db.add(e)
    audit(db, user, "master", "ENTITY_CREATED", "entity", body.name, new=body.model_dump())
    db.commit()
    return entity_out(e)


class OwnershipIn(BaseModel):
    new_owner: str
    remarks: str = ""


@router.post("/entities/{eid}/ownership-change")
def request_ownership_change(eid: int, body: OwnershipIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """REGS ownership changes apply only after NLDC/RLDC Admin approval, with history (TS Cl. 11.1 p.76)."""
    e = db.get(Entity, eid)
    if e is None:
        raise HTTPException(404)
    h = EntityOwnershipHistory(entity_id=e.id, previous_owner=e.name, new_owner=body.new_owner, requested_by=user.id, remarks=body.remarks)
    db.add(h)
    audit(db, user, "master", "OWNERSHIP_CHANGE_REQUESTED", "entity", e.id, new=body.model_dump())
    db.commit()
    return {"id": h.id, "status": h.status}


@router.post("/ownership-changes/{hid}/decide")
def decide_ownership(hid: int, approve: bool, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not is_admin(user):
        raise HTTPException(403, "Admin approval required")
    h = db.get(EntityOwnershipHistory, hid)
    if h is None or h.status != "PENDING":
        raise HTTPException(409)
    h.status, h.approved_by, h.approved_at = ("APPROVED" if approve else "REJECTED"), user.id, utcnow()
    if approve:
        e = db.get(Entity, h.entity_id)
        e.name = h.new_owner
    audit(db, user, "master", "OWNERSHIP_CHANGE_" + h.status, "entity", h.entity_id)
    db.commit()
    return {"status": h.status}


@router.get("/ownership-changes")
def ownership_changes(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return [{"id": h.id, "entity_id": h.entity_id, "previous_owner": h.previous_owner, "new_owner": h.new_owner,
             "status": h.status, "remarks": h.remarks, "created_at": h.created_at, "approved_at": h.approved_at}
            for h in db.scalars(select(EntityOwnershipHistory).order_by(EntityOwnershipHistory.id.desc()))]


# ------------------------------------------------------------------ substations
@router.get("/substations")
def substations(centre: str | None = None, db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(Substation).order_by(Substation.name)
    if centre and centre != "ALL":
        stmt = stmt.join(Centre, Substation.centre_id == Centre.id).where(Centre.code == centre)
    return [{"id": s.id, "code": s.code, "name": s.name, "centre": s.centre.code, "state": s.state, "voltage_levels": s.voltage_levels_json,
             "substation_type": s.substation_type, "bus_scheme": s.bus_scheme, "lat": s.lat, "lng": s.lng,
             "owner": s.owner.short_name if s.owner else "", "weather_area": s.weather_area, "is_pooling_station": s.is_pooling_station}
            for s in db.scalars(stmt)]


class SubstationIn(BaseModel):
    code: str
    name: str
    centre_code: str
    state: str = ""
    voltage_levels: list[int]
    substation_type: str = "AIS"
    bus_scheme: str = "Double main & transfer"
    lat: float | None = Field(None, ge=6, le=38)
    lng: float | None = Field(None, ge=68, le=98)
    owner_entity_id: int | None = None
    weather_area: str = ""


@router.post("/substations")
def create_substation(body: SubstationIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """New station; its bus records are created automatically from the bus scheme (Table 8 row 22)."""
    if is_external(user) and not (role_codes(user) & {"EXT_FTC"}):
        raise HTTPException(403)
    centre = db.scalar(select(Centre).where(Centre.code == body.centre_code))
    s = Substation(code=body.code.upper(), name=body.name, centre_id=centre.id, state=body.state, voltage_levels_json=body.voltage_levels,
                   substation_type=body.substation_type, bus_scheme=body.bus_scheme, lat=body.lat, lng=body.lng,
                   owner_entity_id=body.owner_entity_id, weather_area=body.weather_area)
    db.add(s)
    db.flush()
    buses = 2 if "double" in body.bus_scheme.lower() else 1
    for kv in body.voltage_levels:
        for n in range(1, buses + 1):
            db.add(GridElement(unique_element_id=element_id(db, centre.code, kv, "BUS"), name=f"{kv} kV Bus-{n} at {body.name}",
                               element_type="BUS", centre_id=centre.id, voltage_kv=kv, from_substation_id=s.id,
                               status="PRE_COMMISSIONING"))
    audit(db, user, "master", "SUBSTATION_CREATED", "substation", s.code, new=body.model_dump())
    db.commit()
    return {"id": s.id, "code": s.code, "buses_created": buses * len(body.voltage_levels)}


# ------------------------------------------------------------------ elements
@router.get("/element-types")
def element_types():
    return [{"code": k, "id_code": v[0], "label": v[1]} for k, v in ELEMENT_TYPES.items()]


@router.get("/elements")
def elements(centre: str | None = None, element_type: str | None = None, voltage: float | None = None, status: str | None = None,
             q: str | None = None, mine: bool = False, db: Session = Depends(get_db), user=Depends(get_current_user)):
    stmt = select(GridElement).order_by(GridElement.voltage_kv.desc(), GridElement.name)
    ids = visible_centre_ids(db, user)
    if ids is not None and not is_external(user):
        stmt = stmt.where(or_(GridElement.centre_id.in_(ids), GridElement.is_inter_regional))
    if centre and centre != "ALL":
        stmt = stmt.join(Centre, GridElement.centre_id == Centre.id).where(Centre.code == centre)
    if element_type:
        stmt = stmt.where(GridElement.element_type == element_type)
    if voltage:
        stmt = stmt.where(GridElement.voltage_kv == voltage)
    if status:
        stmt = stmt.where(GridElement.status == status)
    if q:
        stmt = stmt.where(or_(GridElement.name.ilike(f"%{q}%"), GridElement.unique_element_id.ilike(f"%{q}%")))
    rows = db.scalars(stmt).unique().all()
    if is_external(user) or mine:
        rows = [g for g in rows if any(o.entity_id == user.entity_id for o in g.owners)]
    return [element_out(g) for g in rows]


@router.get("/elements/{gid}")
def element(gid: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    g = db.get(GridElement, gid)
    if g is None:
        raise HTTPException(404)
    return element_out(g)


class ElementIn(BaseModel):
    name: str
    element_type: str
    centre_code: str
    voltage_kv: float = Field(gt=0, le=1200)
    from_substation_id: int | None = None
    to_substation_id: int | None = None
    is_inter_regional: bool = False
    rating: str = ""
    length_km: float | None = Field(None, ge=0, le=3000)
    status: str = "PRE_COMMISSIONING"
    metadata: dict = {}
    owners: list[dict] = []


def create_element(db: Session, body: ElementIn, user, ftc_case_id: int | None = None) -> GridElement:
    if body.element_type not in ELEMENT_TYPES:
        raise HTTPException(422, f"Unknown element type {body.element_type}")
    centre = db.scalar(select(Centre).where(Centre.code == body.centre_code))
    g = GridElement(unique_element_id=element_id(db, centre.code, body.voltage_kv, body.element_type), name=body.name,
                    element_type=body.element_type, centre_id=centre.id, voltage_kv=body.voltage_kv,
                    from_substation_id=body.from_substation_id, to_substation_id=body.to_substation_id,
                    is_inter_regional=body.is_inter_regional, rating=body.rating, length_km=body.length_km, status=body.status,
                    metadata_json=body.metadata, source_ftc_case_id=ftc_case_id, realtime_enabled=ftc_case_id is None)
    db.add(g)
    db.flush()
    for o in body.owners:
        db.add(ElementOwner(grid_element_id=g.id, entity_id=o["entity_id"], ownership_role=o.get("role", "ASSET_OWNER"),
                            section_km=o.get("section_km")))
    db.flush()
    db.refresh(g)
    return g


@router.post("/elements")
def add_element(body: ElementIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if is_external(user):
        raise HTTPException(403, "External users add elements via FTC Annexure A2")
    g = create_element(db, body, user)
    audit(db, user, "master", "ELEMENT_CREATED", "element", g.unique_element_id, new=body.model_dump())
    db.commit()
    return element_out(g)


class NoteIn(BaseModel):
    text: str = Field(min_length=2, max_length=2000)


@router.post("/elements/{gid}/notes")
def add_note(gid: int, body: NoteIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Operator 'Notes' are append-only (cannot be deleted) (Table 8 note, p.145)."""
    if is_external(user):
        raise HTTPException(403)
    g = db.get(GridElement, gid)
    g.operator_notes_append_only_json = [*g.operator_notes_append_only_json,
                                         {"by": user.full_name, "at": utcnow().isoformat(), "text": body.text}]
    audit(db, user, "master", "ELEMENT_NOTE_ADDED", "element", g.unique_element_id, new={"text": body.text})
    db.commit()
    return {"notes": g.operator_notes_append_only_json}


@router.put("/elements/{gid}/comments")
def set_comments(gid: int, body: NoteIn, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """'Comments' can be overridden (Table 8 note)."""
    if is_external(user):
        raise HTTPException(403)
    g = db.get(GridElement, gid)
    old = g.operator_comments
    g.operator_comments = body.text
    audit(db, user, "master", "ELEMENT_COMMENT_SET", "element", g.unique_element_id, old={"c": old}, new={"c": body.text})
    db.commit()
    return {"comments": g.operator_comments}


@router.patch("/elements/{gid}")
def edit_static(gid: int, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Static data editable by Real-time Outage Coordinator from the UI (Table 8 note)."""
    if not (is_admin(user) or role_codes(user) & {"RT_COORDINATOR", "SHIFT_INCHARGE"}):
        raise HTTPException(403)
    g = db.get(GridElement, gid)
    old = element_out(g)
    for k in ("name", "rating", "length_km"):
        if k in body:
            setattr(g, k, body[k])
    if "metadata" in body:
        g.metadata_json = {**g.metadata_json, **body["metadata"]}
    audit(db, user, "master", "ELEMENT_STATIC_EDITED", "element", g.unique_element_id, old={k: old[k] for k in ("name", "rating")}, new=body)
    db.commit()
    return element_out(g)


@router.get("/comm-elements")
def comm_elements(db: Session = Depends(get_db), user=Depends(get_current_user)):
    rows = db.scalars(select(CommElement).order_by(CommElement.id)).all()
    if is_external(user):
        rows = [c for c in rows if c.owner_entity_id == user.entity_id]
    return [{"id": c.id, "unique_comm_id": c.unique_comm_id, "name": c.name, "comm_type": c.comm_type, "from_station": c.from_station,
             "to_station": c.to_station, "status": c.status, "owner_entity_id": c.owner_entity_id} for c in rows]


def today() -> date:
    return utcnow().date()
