"""FastAPI entrypoint: REST /api/v1, GraphQL /graphql, WebSockets /ws/{channel}."""
import asyncio
import importlib
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.audit import AuditMiddleware
from app.core.config import get_settings
from app.core.events import hub
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()

# Routers are registered as modules are delivered milestone by milestone.
ROUTER_MODULES = [
    "app.modules.auth_rbac.router",
    "app.modules.portal_cms.router",
    "app.modules.ticketing_cas.router",
    "app.modules.master_registry.router",
    "app.modules.dms_files.router",
    "app.modules.workflow_engine.router",
    "app.modules.registration.router",
    "app.modules.ftc.router",
    "app.modules.comm_cert.router",
    "app.modules.outage_coord.router",
    "app.modules.realtime_outage.router",
    "app.modules.availability_verify.router",
    "app.modules.protection_tripping.router",
    "app.modules.message_alerts.router",
    "app.modules.sps_status.router",
    "app.modules.mis_reporting.router",
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(get_engine())
    hub.loop = asyncio.get_running_loop()
    from app.core import scheduler

    task = asyncio.create_task(scheduler.run_forever())
    yield
    task.cancel()


limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])
app = FastAPI(title=settings.app_name, version="0.1.0-poc", lifespan=lifespan,
              description="Proof of concept for GeM bid GEM/2026/B/8083674 (Grid-India OMS).")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class SecurityHeaders(BaseHTTPMiddleware):
    """OWASP-recommended headers (TS Ch.4; FRD NFR-15) + server timing for the latency check (NFR-11)."""

    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if not request.url.path.startswith(("/docs", "/redoc", "/graphql")):
            response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
        response.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - t0) * 1000:.1f}"
        return response


app.add_middleware(AuditMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeaders)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"], expose_headers=["Content-Disposition", "Server-Timing"])


@app.exception_handler(RequestValidationError)
async def validation_handler(_req: Request, exc: RequestValidationError):
    """Structured, meaningful validation errors (TS Cl. 2.6(e))."""
    errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Validation failed", "errors": errors})


for mod_path in ROUTER_MODULES:
    try:
        mod = importlib.import_module(mod_path)
    except ModuleNotFoundError as e:
        if e.name == mod_path:
            continue
        raise
    for attr in ("router", "admin_router", "public_router"):
        r = getattr(mod, attr, None)
        if r is not None:
            app.include_router(r)

try:
    from app.graphql.schema import graphql_app

    app.include_router(graphql_app, prefix="/graphql")
except ModuleNotFoundError:
    pass


@app.get("/api/v1/health", tags=["system"])
def health():
    return {"status": "ok", "app": settings.app_name}


@app.websocket("/ws/{channel}")
async def ws_endpoint(websocket: WebSocket, channel: str):
    """Live push for control room (centre code channel), users (user:{id}) and 'ALL'."""
    await hub.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(channel, websocket)
