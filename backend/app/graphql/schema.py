"""Unified GraphQL API (TS Ch.2 intro, Cl. 2.6(a)-(h); FRD API-02..09).

- SDL is introspectable at /graphql (GraphiQL explorer for interactive documentation)
- Nested queries: ftcCase -> elements -> owners, documents, workflowSteps in one request
- Mutations return updated state; structured errors
- Subscriptions over WebSocket (graphql-transport-ws) stream live control-room events
- DataLoader batches entity / document lookups to avoid N+1 queries
"""
import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime

import strawberry
from sqlalchemy import select
from strawberry.dataloader import DataLoader
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info
from starlette.requests import HTTPConnection

from app.core.events import hub
from app.core.rbac import can_access, is_external
from app.core.security import decode_access_token
from app.db.session import SessionLocal, get_engine
from app.modules.auth_rbac.models import User, UserSession


def _db():
    get_engine()
    return SessionLocal()


async def get_context(conn: HTTPConnection):
    db = _db()
    user = None
    auth = conn.headers.get("authorization", "") or conn.query_params.get("token", "")
    if auth and not auth.lower().startswith("bearer "):
        auth = "Bearer " + auth
    if auth.lower().startswith("bearer "):
        p = decode_access_token(auth[7:])
        if p:
            sess = db.scalar(select(UserSession).where(UserSession.token_jti == p["jti"], UserSession.is_active))
            if sess:
                user = db.get(User, int(p["sub"]))

    async def load_entities(ids: list[int]):
        from app.modules.master_registry.models import Entity
        rows = {e.id: e for e in db.scalars(select(Entity).where(Entity.id.in_(ids)))}
        return [rows.get(i) for i in ids]

    async def load_docs(refs: list[str]):
        from app.modules.dms_files.models import Document
        rows = db.scalars(select(Document).where(Document.owner_ref.in_(refs), Document.is_latest)).all()
        return [[d for d in rows if d.owner_ref == r] for r in refs]

    return {"db": db, "user": user, "entity_loader": DataLoader(load_fn=load_entities), "doc_loader": DataLoader(load_fn=load_docs)}


def require(info: Info, module: str | None = None) -> User:
    u = info.context["user"]
    if u is None:
        raise PermissionError("Not authenticated: send Authorization: Bearer <token>")
    if module and not can_access(u, module):
        raise PermissionError(f"Not authorised for {module}")
    return u


@strawberry.type
class EntityT:
    id: int
    name: str
    short_name: str
    entity_type: str
    sector: str


@strawberry.type
class OwnerT:
    role: str
    section_km: float | None
    entity_id: strawberry.Private[int]

    @strawberry.field
    async def entity(self, info: Info) -> EntityT | None:
        e = await info.context["entity_loader"].load(self.entity_id)
        return EntityT(id=e.id, name=e.name, short_name=e.short_name, entity_type=e.entity_type, sector=e.sector) if e else None


@strawberry.type
class ElementT:
    id: int
    unique_element_id: str
    name: str
    element_type: str
    voltage_kv: float
    status: str
    centre: str
    notes: list[str]
    owners: list[OwnerT]


def element_t(g) -> ElementT:
    return ElementT(id=g.id, unique_element_id=g.unique_element_id, name=g.name, element_type=g.element_type, voltage_kv=g.voltage_kv,
                    status=g.status, centre=g.centre.code, notes=[n["text"] for n in g.operator_notes_append_only_json],
                    owners=[OwnerT(role=o.ownership_role, section_km=o.section_km, entity_id=o.entity_id) for o in g.owners])


@strawberry.type
class DocumentT:
    id: int
    doc_category: str
    auto_filename: str
    version_no: int
    created_at: datetime


@strawberry.type
class StepT:
    step_order: int
    step_name: str
    actor_name: str
    action: str
    remarks: str
    created_at: datetime


@strawberry.type
class FtcCaseT:
    id: int
    case_number: str
    stage: int
    status: str
    jurisdiction: str
    case_id: strawberry.Private[int]
    element_ids: strawberry.Private[list[int]]
    internal: strawberry.Private[bool]

    @strawberry.field
    def elements(self, info: Info) -> list[ElementT]:
        from app.modules.master_registry.models import GridElement
        return [element_t(info.context["db"].get(GridElement, i)) for i in self.element_ids]

    @strawberry.field
    async def documents(self, info: Info) -> list[DocumentT]:
        docs = await info.context["doc_loader"].load(f"case:{self.case_id}")
        return [DocumentT(id=d.id, doc_category=d.doc_category, auto_filename=d.auto_filename, version_no=d.version_no, created_at=d.created_at)
                for d in docs if self.internal or d.visible_to_applicant]

    @strawberry.field
    def workflow_steps(self, info: Info) -> list[StepT]:
        from app.modules.workflow_engine.models import WorkflowCase
        c = info.context["db"].get(WorkflowCase, self.case_id)
        return [StepT(step_order=s.step_order, step_name=s.step_name, actor_name=s.actor_name, action=s.action, remarks=s.remarks,
                      created_at=s.created_at) for s in c.steps if self.internal or not s.is_internal_only]


@strawberry.type
class CodeT:
    code_number: str
    code_type: str
    element: str
    issued_at: datetime
    final_exec_time: datetime | None
    is_revoked: bool


@strawberry.type
class TicketT:
    ticket_number: str
    subject: str
    status: str
    severity: int | None
    escalation_level: int


@strawberry.type
class GridEventT:
    type: str
    channel: str
    data: strawberry.scalars.JSON


def ftc_t(db, f, user) -> FtcCaseT:
    from app.modules.workflow_engine.models import WorkflowCase
    c = db.get(WorkflowCase, f.case_id)
    return FtcCaseT(id=f.id, case_number=c.case_number, stage=f.stage, status=c.status, jurisdiction=f.jurisdiction, case_id=c.id,
                    element_ids=list(f.created_element_ids_json), internal=not is_external(user))


@strawberry.type
class Query:
    @strawberry.field(description="Grid elements from the master database, optionally filtered by centre code and voltage")
    def elements(self, info: Info, centre: str | None = None, voltage_kv: float | None = None, limit: int = 100) -> list[ElementT]:
        user = require(info)
        from app.modules.auth_rbac.models import Centre
        from app.modules.master_registry.models import GridElement
        stmt = select(GridElement)
        if centre:
            stmt = stmt.join(Centre, GridElement.centre_id == Centre.id).where(Centre.code == centre)
        if voltage_kv:
            stmt = stmt.where(GridElement.voltage_kv == voltage_kv)
        rows = info.context["db"].scalars(stmt.limit(limit)).unique().all()
        if is_external(user):
            rows = [g for g in rows if any(o.entity_id == user.entity_id for o in g.owners)]
        return [element_t(g) for g in rows]

    @strawberry.field(description="FTC cases with nested elements, documents and workflow steps")
    def ftc_cases(self, info: Info) -> list[FtcCaseT]:
        user = require(info, "ftc")
        from app.modules.ftc.models import FtcApplication
        db = info.context["db"]
        rows = db.scalars(select(FtcApplication)).all()
        if is_external(user):
            rows = [f for f in rows if f.entity_id == user.entity_id]
        return [ftc_t(db, f, user) for f in rows]

    @strawberry.field
    def ftc_case(self, info: Info, id: int) -> FtcCaseT | None:
        user = require(info, "ftc")
        from app.modules.ftc.models import FtcApplication
        f = info.context["db"].get(FtcApplication, id)
        if f is None or (is_external(user) and f.entity_id != user.entity_id):
            return None
        return ftc_t(info.context["db"], f, user)

    @strawberry.field
    def codes(self, info: Info, limit: int = 50) -> list[CodeT]:
        require(info, "realtime")
        from app.modules.realtime_outage.models import OutageCode
        rows = info.context["db"].scalars(select(OutageCode).order_by(OutageCode.id.desc()).limit(limit)).all()
        return [CodeT(code_number=c.code_number, code_type=c.code_type, element=c.element.name if c.element else c.description,
                      issued_at=c.issued_at, final_exec_time=c.final_exec_time, is_revoked=c.is_revoked) for c in rows]

    @strawberry.field
    def my_tickets(self, info: Info) -> list[TicketT]:
        user = require(info, "cas")
        from app.modules.ticketing_cas.models import Ticket
        rows = info.context["db"].scalars(select(Ticket).where(Ticket.complainant_user_id == user.id)).all()
        return [TicketT(ticket_number=t.ticket_number, subject=t.subject, status=t.status, severity=t.severity, escalation_level=t.escalation_level) for t in rows]


@strawberry.type
class Mutation:
    @strawberry.mutation(description="Append an operator note (append-only) and return the updated element")
    def add_element_note(self, info: Info, element_id: int, text: str) -> ElementT:
        user = require(info, "realtime")
        if is_external(user):
            raise PermissionError("Grid operators only")
        from app.db.base import utcnow
        from app.modules.master_registry.models import GridElement
        db = info.context["db"]
        g = db.get(GridElement, element_id)
        if g is None:
            raise ValueError("Element not found")
        if len(text.strip()) < 2:
            raise ValueError("Note too short")
        g.operator_notes_append_only_json = [*g.operator_notes_append_only_json, {"by": user.full_name, "at": utcnow().isoformat(), "text": text}]
        db.commit()
        return element_t(g)

    @strawberry.mutation(description="Update SPS healthiness and return the new status")
    def set_sps_status(self, info: Info, sps_id: str, status: str) -> str:
        require(info, "sps")
        if status not in ("ON", "OFF", "DEGRADED"):
            raise ValueError("status must be ON, OFF or DEGRADED")
        from app.db.base import utcnow
        from app.modules.sps_status.models import SpsScheme, SpsStatusLog
        db = info.context["db"]
        s = db.scalar(select(SpsScheme).where(SpsScheme.sps_id == sps_id))
        s.current_status, s.updated_at = status, utcnow()
        db.add(SpsStatusLog(sps_scheme_id=s.id, status=status, source="USER", updated_by=info.context["user"].id))
        db.commit()
        return s.current_status


@strawberry.type
class Subscription:
    @strawberry.subscription(description="Live control-room events (codes, consents, trippings, shift changes, SPS)")
    async def grid_events(self, info: Info, channel: str | None = None) -> AsyncGenerator[GridEventT, None]:
        q = hub.subscribe_queue()
        try:
            while True:
                ev = await q.get()
                if channel and ev.get("channel") not in (channel, "ALL"):
                    continue
                yield GridEventT(type=ev.get("type", ""), channel=ev.get("channel", ""), data=ev.get("data", {}))
        except asyncio.CancelledError:
            pass
        finally:
            hub.unsubscribe_queue(q)


schema = strawberry.Schema(query=Query, mutation=Mutation, subscription=Subscription)
graphql_app = GraphQLRouter(schema, context_getter=get_context)
