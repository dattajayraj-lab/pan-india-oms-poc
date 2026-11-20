"""Auth, sessions, admin user management, settings, audit logs (FRD UM-*, UI-04, UI-06)."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import DEFAULT_SYSTEM_SETTINGS, get_settings
from app.core.rbac import ROLE_DEFS, get_current_user, is_admin, require_admin
from app.core.security import hash_password, new_captcha, password_policy_errors, verify_captcha, verify_password
from app.db.base import utcnow
from app.db.session import get_db
from app.modules.auth_rbac import service as svc
from app.modules.auth_rbac.models import (AuditLog, Centre, Notification, NotificationToggle, Role, SystemSetting,
                                          User, UserRole, UserSession)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _ip(req: Request) -> str:
    return req.client.host if req.client else ""


# ------------------------------------------------------------------ public auth
@router.get("/captcha")
def captcha():
    return new_captcha()


class LoginIn(BaseModel):
    username: str
    password: str
    login_type: str = Field("GRID_INDIA", pattern="^(GRID_INDIA|EXTERNAL)$")
    captcha_token: str | None = None
    captcha_answer: str | None = None


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    if not verify_captcha(body.captcha_token, body.captcha_answer):
        raise HTTPException(400, "CAPTCHA verification failed")
    user = db.scalar(select(User).where(func.lower(User.username) == body.username.strip().lower()))
    generic = HTTPException(401, "Invalid username or password")
    if user is None:
        raise generic
    now = utcnow()
    if user.locked_until and user.locked_until > now:
        audit(db, user, "auth", "LOGIN_BLOCKED_LOCKED", "user", user.id, ip=_ip(request), commit=True)
        raise HTTPException(423, f"Account locked until {user.locked_until:%d-%m-%Y %H:%M} after repeated failures")
    if not verify_password(body.password, user.password_hash):
        user.failed_login_count += 1
        s = get_settings()
        if user.failed_login_count >= s.max_failed_logins:
            user.locked_until = now + timedelta(minutes=s.lockout_minutes)
            audit(db, user, "auth", "ACCOUNT_LOCKED", "user", user.id, ip=_ip(request))
        audit(db, user, "auth", "LOGIN_FAILED", "user", user.id,
              new={"failed_count": user.failed_login_count}, ip=_ip(request))
        db.commit()
        remaining = max(s.max_failed_logins - user.failed_login_count, 0)
        if remaining == 0:
            raise HTTPException(423, "Account locked after 5 unsuccessful attempts")
        raise HTTPException(401, f"Invalid username or password. {remaining} attempt(s) left before lockout")
    if not user.is_active:
        raise HTTPException(403, "Account is inactive")
    internal = user.user_category == "GRID_INDIA"
    if (body.login_type == "GRID_INDIA") != internal:
        raise HTTPException(403, "Use the " + ("Grid-India" if internal else "External") + " login option")
    if user.is_2fa_enabled:
        out = svc.issue_otp(db, user, "LOGIN")
        audit(db, user, "auth", "LOGIN_PASSWORD_OK_OTP_SENT", "user", user.id, ip=_ip(request))
        db.commit()
        return {"otp_required": True, **out}
    return _complete_login(db, user, request)


def _complete_login(db: Session, user: User, request: Request) -> dict:
    token, sess = svc.start_session(db, user, _ip(request), request.headers.get("user-agent", ""))
    audit(db, user, "auth", "LOGIN_SUCCESS", "session", sess.id, ip=_ip(request))
    db.commit()
    return {"otp_required": False, "access_token": token, "token_type": "bearer",
            "user": svc.user_out(user), **svc.login_flags(db, user)}


class OtpIn(BaseModel):
    challenge_id: str
    otp: str


@router.post("/verify-otp")
def verify_otp(body: OtpIn, request: Request, db: Session = Depends(get_db)):
    row = svc.consume_otp(db, body.challenge_id, body.otp, "LOGIN")
    user = db.get(User, row.user_id)
    return _complete_login(db, user, request)


class ForgotIn(BaseModel):
    identifier: str  # username or e-mail
    captcha_token: str | None = None
    captcha_answer: str | None = None


@router.post("/forgot-password")
def forgot_password(body: ForgotIn, db: Session = Depends(get_db)):
    if not verify_captcha(body.captcha_token, body.captcha_answer):
        raise HTTPException(400, "CAPTCHA verification failed")
    ident = body.identifier.strip().lower()
    user = db.scalar(select(User).where(or_(func.lower(User.username) == ident, func.lower(User.email) == ident)))
    if user is None:
        return {"message": "If the account exists, a reset link and OTP have been sent."}
    out = svc.issue_otp(db, user, "RESET", "EMAIL")
    audit(db, user, "auth", "PASSWORD_RESET_REQUESTED", "user", user.id)
    db.commit()
    return {"message": "Reset link and OTP sent to registered e-mail and mobile.", **out}


class ResetIn(BaseModel):
    challenge_id: str
    otp: str
    new_password: str


@router.post("/reset-password")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    errs = password_policy_errors(body.new_password)
    if errs:
        raise HTTPException(422, "Password must contain " + ", ".join(errs))
    row = svc.consume_otp(db, body.challenge_id, body.otp, "RESET")
    user = db.get(User, row.user_id)
    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = False
    user.failed_login_count = 0
    user.locked_until = None
    audit(db, user, "auth", "PASSWORD_RESET", "user", user.id)
    db.commit()
    return {"message": "Password updated. Please log in."}


class ForgotUserIn(BaseModel):
    email: str
    captcha_token: str | None = None
    captcha_answer: str | None = None


@router.post("/forgot-username")
def forgot_username(body: ForgotUserIn, db: Session = Depends(get_db)):
    if not verify_captcha(body.captcha_token, body.captcha_answer):
        raise HTTPException(400, "CAPTCHA verification failed")
    users = db.scalars(select(User).where(func.lower(User.email) == body.email.strip().lower())).all()
    from app.integrations.notifier import notify_users

    for u in users:
        notify_users(db, [u], f"Your Grid-India OMS username is {u.username}", module="auth", channels=("EMAIL", "SMS"))
    db.commit()
    return {"message": "If the e-mail is registered, the username has been sent to it and the registered mobile."}


@router.get("/username-available")
def username_available(username: str, db: Session = Depends(get_db)):
    """Real-time availability check used in sign-up (TS p.84, p.90)."""
    from app.modules.registration.models import AccountRequest

    taken = db.scalar(select(func.count()).select_from(User).where(func.lower(User.username) == username.lower()))
    pending = db.scalar(select(func.count()).select_from(AccountRequest).where(
        func.lower(AccountRequest.username) == username.lower(), AccountRequest.status == "PENDING"))
    return {"username": username, "available": not taken and not pending}


# ------------------------------------------------------------------ authenticated
@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"user": svc.user_out(user), "launcher": svc.module_launcher(user), **svc.login_flags(db, user),
            "settings": {"refresh_interval_ms": svc.get_setting(db, "refresh_interval_ms")}}


@router.post("/logout")
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sess = db.get(UserSession, request.state.session_id)
    sess.is_active = False
    sess.ended_reason = "LOGOUT"
    audit(db, user, "auth", "LOGOUT", "session", sess.id)
    db.commit()
    return {"ok": True}


class ChangePwdIn(BaseModel):
    old_password: str
    new_password: str


@router.post("/change-password")
def change_password(body: ChangePwdIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    errs = password_policy_errors(body.new_password)
    if errs:
        raise HTTPException(422, "Password must contain " + ", ".join(errs))
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(422, "New password must differ from the current password")
    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = False
    audit(db, user, "auth", "PASSWORD_CHANGED", "user", user.id)
    db.commit()
    return {"ok": True}


class ContactsIn(BaseModel):
    retain: bool = True
    email: EmailStr | None = None
    mobile: str | None = Field(None, pattern=r"^\+?[0-9]{10,13}$")


@router.post("/verify-contacts")
def verify_contacts(body: ContactsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """3-monthly contact review pop-up (TS Cl. 2.1, p.24)."""
    old = {"email": user.email, "mobile": user.mobile}
    changed = False
    if not body.retain:
        if body.email and body.email != user.email:
            user.email, user.email_verified, changed = body.email, False, True
        if body.mobile and body.mobile != user.mobile:
            user.mobile, user.mobile_verified, changed = body.mobile, False, True
    user.last_contact_verified_at = utcnow()
    audit(db, user, "auth", "CONTACTS_REVIEWED", "user", user.id, old=old,
          new={"email": user.email, "mobile": user.mobile, "retained": body.retain})
    out = {"ok": True}
    if changed:
        out["verification"] = svc.issue_otp(db, user, "VERIFY_CONTACT")
    db.commit()
    return out


@router.post("/verify-contact-otp")
def verify_contact_otp(body: OtpIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = svc.consume_otp(db, body.challenge_id, body.otp, "VERIFY_CONTACT")
    if row.user_id != user.id:
        raise HTTPException(403, "OTP does not belong to this user")
    user.email_verified = user.mobile_verified = True
    db.commit()
    return {"ok": True}


@router.get("/sessions")
def my_sessions(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Details of all present login sessions are shown in each session (Table 1 note, p.23)."""
    rows = db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.is_active)
                      .order_by(desc(UserSession.created_at))).all()
    return [{"id": s.id, "ip_address": s.ip_address, "user_agent": s.user_agent, "created_at": s.created_at,
             "last_seen_at": s.last_seen_at, "current": s.id == request.state.session_id} for s in rows]


@router.delete("/sessions/{session_id}")
def end_session(session_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.get(UserSession, session_id)
    if s is None or (s.user_id != user.id and not is_admin(user)):
        raise HTTPException(404, "Session not found")
    s.is_active = False
    s.ended_reason = "FORCED_LOGOUT_BY_ADMIN" if s.user_id != user.id else "LOGOUT_OTHER_SESSION"
    audit(db, user, "auth", "SESSION_TERMINATED", "session", s.id, new={"target_user": s.user_id})
    db.commit()
    return {"ok": True}


@router.get("/notifications")
def my_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db), limit: int = 30):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.channel == "INAPP")
                      .order_by(desc(Notification.created_at)).limit(limit)).all()
    unread = db.scalar(select(func.count()).select_from(Notification).where(
        Notification.user_id == user.id, Notification.channel == "INAPP", Notification.is_read.is_(False)))
    return {"unread": unread, "items": [{"id": n.id, "subject": n.subject, "body": n.body, "module": n.module,
                                         "link": n.link, "is_read": n.is_read, "created_at": n.created_at} for n in rows]}


@router.post("/notifications/read-all")
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for n in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False))):
        n.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/signature")
def upload_signature(payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Store a base64 signature image or DSC serial for signing consents (Table 1 note, p.24)."""
    import base64

    data = payload.get("image_base64")
    if data:
        raw = base64.b64decode(data.split(",")[-1])
        if len(raw) > 512_000:
            raise HTTPException(413, "Signature image too large")
        path = get_settings().storage_dir / "signatures" / f"user_{user.id}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        user.signature_file_path = str(path)
    if payload.get("dsc_serial"):
        user.dsc_serial = payload["dsc_serial"][:80]
    audit(db, user, "auth", "SIGNATURE_UPDATED", "user", user.id)
    db.commit()
    return {"ok": True, "has_signature": bool(user.signature_file_path)}


# ------------------------------------------------------------------ admin
@admin_router.get("/centres")
def centres(db: Session = Depends(get_db)):
    return [{"id": c.id, "code": c.code, "name_en": c.name_en, "name_hi": c.name_hi, "city": c.city,
             "shift_start_time": c.shift_start_time} for c in db.scalars(select(Centre).order_by(Centre.id))]


@admin_router.get("/roles")
def roles(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return [{"id": r.id, "code": r.code, "name": r.name, "name_hi": r.name_hi, "modules": ROLE_DEFS.get(r.code, ("", "", []))[2],
             "is_internal": r.is_internal} for r in db.scalars(select(Role).order_by(Role.id))]


class RoleIn(BaseModel):
    code: str = Field(pattern=r"^[A-Z_]{3,40}$")
    name: str
    modules: list[str]
    level: str = Field("read", pattern="^(read|write|approve|admin)$")
    is_internal: bool = True


@admin_router.post("/roles")
def create_role(body: RoleIn, db: Session = Depends(get_db), admin=Depends(require_admin)):
    """Create new roles and map permissions from the front end (Table 1 note, p.23)."""
    if db.scalar(select(Role).where(Role.code == body.code)):
        raise HTTPException(409, "Role exists")
    ROLE_DEFS[body.code] = (body.name, body.name, body.modules, body.level, body.is_internal)
    r = Role(code=body.code, name=body.name, permissions_json={"modules": body.modules, "level": body.level},
             is_internal=body.is_internal)
    db.add(r)
    audit(db, admin, "admin", "ROLE_CREATED", "role", body.code, new=body.model_dump())
    db.commit()
    return {"id": r.id}


@admin_router.get("/users")
def list_users(q: str = "", db: Session = Depends(get_db), admin=Depends(require_admin)):
    stmt = select(User).order_by(User.id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(User.username).like(like), func.lower(User.full_name).like(like)))
    return [svc.user_out(u) for u in db.scalars(stmt).all()]


class UserIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    full_name: str
    email: EmailStr
    mobile: str = Field(pattern=r"^\+?[0-9]{10,13}$")
    user_category: str = Field("GRID_INDIA", pattern="^(GRID_INDIA|EXTERNAL|CTU|RPC|PUBLIC)$")
    department: str = ""
    centre_code: str | None = None
    entity_id: int | None = None
    roles: list[str] = []
    is_2fa_enabled: bool = True
    is_active: bool = True
    allow_multi_session: bool = True


@admin_router.post("/users")
def create_user(body: UserIn, db: Session = Depends(get_db), admin=Depends(require_admin)):
    """Owner-created account: activation link + OTP flow (TS Cl. 2.1 p.24)."""
    if db.scalar(select(User).where(func.lower(User.username) == body.username.lower())):
        raise HTTPException(409, "Username already taken")
    centre = db.scalar(select(Centre).where(Centre.code == body.centre_code)) if body.centre_code else None
    temp = svc.random_password()
    u = User(username=body.username, full_name=body.full_name, email=body.email, mobile=body.mobile,
             user_category=body.user_category, department=body.department,
             centre_id=centre.id if centre else None, entity_id=body.entity_id,
             password_hash=hash_password(temp), must_change_password=True,
             is_2fa_enabled=body.is_2fa_enabled, is_active=body.is_active,
             allow_multi_session=body.allow_multi_session)
    db.add(u)
    db.flush()
    _set_roles(db, u, body.roles, centre)
    activation = svc.issue_otp(db, u, "RESET", "EMAIL")
    audit(db, admin, "admin", "USER_CREATED", "user", u.id, new=body.model_dump())
    db.commit()
    return {"id": u.id, "activation": activation,
            "message": "Activation link with password-set step e-mailed and SMS sent to the user."}


def _set_roles(db: Session, u: User, codes: list[str], centre) -> None:
    for ur in list(u.roles):
        db.delete(ur)
    db.flush()
    for code in codes:
        role = db.scalar(select(Role).where(Role.code == code))
        if role is None:
            raise HTTPException(422, f"Unknown role {code}")
        db.add(UserRole(user_id=u.id, role_id=role.id, centre_id=centre.id if centre else None))
    db.flush()
    db.refresh(u)


class UserPatch(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    mobile: str | None = None
    department: str | None = None
    is_active: bool | None = None
    is_2fa_enabled: bool | None = None
    allow_multi_session: bool | None = None
    roles: list[str] | None = None
    unlock: bool = False


@admin_router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserPatch, db: Session = Depends(get_db), admin=Depends(require_admin)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "User not found")
    old = svc.user_out(u)
    for f in ("full_name", "email", "mobile", "department", "is_active", "is_2fa_enabled", "allow_multi_session"):
        v = getattr(body, f)
        if v is not None:
            setattr(u, f, v)
    if body.unlock:
        u.failed_login_count, u.locked_until = 0, None
    if body.roles is not None:
        _set_roles(db, u, body.roles, u.centre)
    audit(db, admin, "admin", "USER_UPDATED", "user", u.id, old={"roles": old["roles"]}, new=body.model_dump())
    db.commit()
    return svc.user_out(u)


@admin_router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), admin=Depends(require_admin)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(400, "Cannot delete yourself")
    u.is_active = False  # soft delete keeps audit integrity
    for s in db.scalars(select(UserSession).where(UserSession.user_id == u.id, UserSession.is_active)):
        s.is_active, s.ended_reason = False, "USER_DEACTIVATED"
    audit(db, admin, "admin", "USER_DEACTIVATED", "user", u.id)
    db.commit()
    return {"ok": True}


@admin_router.get("/sessions")
def all_sessions(db: Session = Depends(get_db), admin=Depends(require_admin)):
    """Admin view of all active sessions with force-logout (Table 1 note, p.23)."""
    rows = db.scalars(select(UserSession).where(UserSession.is_active).order_by(desc(UserSession.last_seen_at))).all()
    return [{"id": s.id, "user_id": s.user_id, "username": s.user.username, "full_name": s.user.full_name,
             "ip_address": s.ip_address, "user_agent": s.user_agent, "created_at": s.created_at,
             "last_seen_at": s.last_seen_at} for s in rows]


@admin_router.get("/settings")
def get_settings_api(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return svc.all_settings(db)


@admin_router.put("/settings")
def put_settings(body: dict, db: Session = Depends(get_db), admin=Depends(require_admin)):
    for k, v in body.items():
        if k not in DEFAULT_SYSTEM_SETTINGS:
            raise HTTPException(422, f"Unknown setting {k}")
        if k == "refresh_interval_ms" and (int(v) < 500 or int(v) > 2000):
            raise HTTPException(422, "Refresh interval must be between 500 and 2000 ms (TS Cl. 2.4)")
        row = db.scalar(select(SystemSetting).where(SystemSetting.key == k))
        old = row.value_json if row else DEFAULT_SYSTEM_SETTINGS[k]
        if row is None:
            db.add(SystemSetting(key=k, value_json=v))
        else:
            row.value_json = v
        audit(db, admin, "admin", "SETTING_CHANGED", "setting", k, old={"value": old}, new={"value": v})
    db.commit()
    return svc.all_settings(db)


@admin_router.get("/notification-toggles")
def get_toggles(module: str | None = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    stmt = select(NotificationToggle).order_by(NotificationToggle.module, NotificationToggle.step_code)
    if module:
        stmt = stmt.where(NotificationToggle.module == module)
    return [{"id": t.id, "module": t.module, "step_code": t.step_code, "centre_id": t.centre_id,
             "email_enabled": t.email_enabled, "sms_enabled": t.sms_enabled} for t in db.scalars(stmt)]


@admin_router.patch("/notification-toggles/{toggle_id}")
def patch_toggle(toggle_id: int, body: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Coordinator and Admin can enable/disable SMS and e-mail per step (TS Cl. 2.3)."""
    from app.core.rbac import role_codes

    if not (is_admin(user) or any(c.endswith("COORDINATOR") for c in role_codes(user))):
        raise HTTPException(403, "Coordinator or Admin only")
    t = db.get(NotificationToggle, toggle_id)
    if t is None:
        raise HTTPException(404)
    for f in ("email_enabled", "sms_enabled"):
        if f in body:
            setattr(t, f, bool(body[f]))
    audit(db, user, "admin", "NOTIFICATION_TOGGLE", "toggle", t.id, new=body)
    db.commit()
    return {"ok": True}


@admin_router.get("/audit-logs")
def audit_logs(module: str | None = None, username: str | None = None, limit: int = 200,
               db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Admins see all; other users see their own activity timeline (TS Cl. 11.3(e))."""
    stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(min(limit, 1000))
    if not is_admin(user):
        stmt = stmt.where(AuditLog.user_id == user.id)
    if module:
        stmt = stmt.where(AuditLog.module == module)
    if username:
        stmt = stmt.where(AuditLog.username == username)
    return [{"id": a.id, "username": a.username, "module": a.module, "action": a.action,
             "entity_type": a.entity_type, "entity_id": a.entity_id, "old": a.old_values_json,
             "new": a.new_values_json, "ip_address": a.ip_address, "created_at": a.created_at}
            for a in db.scalars(stmt)]
