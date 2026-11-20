"""Audit trail: explicit domain audit calls + a middleware that records every
state-changing API request (TS Cl. 2.4 'Audit Trails', Cl. 11.3(e); FRD UI-06, CMN-16)."""
from datetime import date, datetime

from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.security import decode_access_token


def _jsonable(v):
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def audit(db: Session, user, module: str, action: str, entity_type: str = "", entity_id: object = "",
          old: dict | None = None, new: dict | None = None, ip: str = "", commit: bool = False) -> None:
    from app.modules.auth_rbac.models import AuditLog

    db.add(AuditLog(
        user_id=getattr(user, "id", None), username=getattr(user, "username", "") or "",
        centre_id=getattr(user, "centre_id", None), module=module, action=action,
        entity_type=entity_type, entity_id=str(entity_id or ""),
        old_values_json=_jsonable(old) if old else None, new_values_json=_jsonable(new) if new else None,
        ip_address=ip,
    ))
    if commit:
        db.commit()


class AuditMiddleware(BaseHTTPMiddleware):
    MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
    SKIP = ("/api/v1/auth/captcha",)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if request.method in self.MUTATING and path.startswith("/api/") and not path.startswith(self.SKIP):
            try:
                self._record(request, response.status_code)
            except Exception:  # noqa: BLE001 - auditing must never break the request
                pass
        return response

    @staticmethod
    def _record(request: Request, status_code: int) -> None:
        from app.db.session import SessionLocal, get_engine
        from app.modules.auth_rbac.models import AuditLog, User

        get_engine()
        user_id, username = None, ""
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            payload = decode_access_token(auth[7:])
            if payload:
                user_id = int(payload["sub"])
        parts = request.url.path.split("/")
        module = parts[3] if len(parts) > 3 else "api"
        with SessionLocal() as db:
            if user_id:
                u = db.get(User, user_id)
                username = u.username if u else ""
            db.add(AuditLog(user_id=user_id, username=username, module=module,
                            action=f"HTTP {request.method}", entity_type="endpoint",
                            entity_id=request.url.path[:60],
                            new_values_json={"status": status_code},
                            ip_address=request.client.host if request.client else ""))
            db.commit()
