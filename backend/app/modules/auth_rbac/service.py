"""Auth domain services: settings, login, OTP, sessions, user serialisation."""
import secrets
import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_SYSTEM_SETTINGS, get_settings
from app.core.rbac import MODULES, can_access, is_admin, is_external, module_level, role_codes, sees_all_centres
from app.core.security import create_access_token, generate_otp, hash_otp
from app.db.base import utcnow
from app.modules.auth_rbac.models import OtpVerification, SystemSetting, User, UserSession


def get_setting(db: Session, key: str):
    row = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    return row.value_json if row else DEFAULT_SYSTEM_SETTINGS.get(key)


def all_settings(db: Session) -> dict:
    out = dict(DEFAULT_SYSTEM_SETTINGS)
    for row in db.scalars(select(SystemSetting)).all():
        out[row.key] = row.value_json
    return out


def issue_otp(db: Session, user: User, purpose: str, channel: str = "SMS") -> dict:
    otp = generate_otp()
    challenge = uuid.uuid4().hex
    db.add(OtpVerification(user_id=user.id, channel=channel, otp_hash=hash_otp(otp), purpose=purpose,
                           challenge_id=challenge,
                           expires_at=utcnow() + timedelta(minutes=get_settings().otp_ttl_minutes)))
    from app.integrations.notifier import notify_users

    notify_users(db, [user], f"Grid-India OMS OTP for {purpose.lower()}: {otp}", module="auth",
                 channels=("EMAIL", "SMS"))
    out = {"challenge_id": challenge, "channel": channel,
           "masked_destination": _mask(user.mobile if channel == "SMS" else user.email)}
    if get_settings().dev_expose_otp:
        out["dev_otp"] = otp
    return out


def _mask(value: str) -> str:
    if not value:
        return ""
    return value[:2] + "*" * max(len(value) - 4, 2) + value[-2:]


def consume_otp(db: Session, challenge_id: str, otp: str, purpose: str) -> OtpVerification:
    row = db.scalar(select(OtpVerification).where(OtpVerification.challenge_id == challenge_id,
                                                  OtpVerification.purpose == purpose))
    if row is None or row.is_used or row.expires_at < utcnow() or row.otp_hash != hash_otp(otp.strip()):
        raise HTTPException(400, "Invalid or expired OTP")
    row.is_used = True
    return row


def start_session(db: Session, user: User, ip: str, ua: str) -> tuple[str, UserSession]:
    multi = user.allow_multi_session and bool(get_setting(db, "allow_multi_session_default"))
    if not multi:
        for s in db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.is_active)):
            s.is_active = False
            s.ended_reason = "SUPERSEDED_BY_NEW_LOGIN"
    token, jti = create_access_token(user.id)
    sess = UserSession(user_id=user.id, token_jti=jti, ip_address=ip, user_agent=ua[:300])
    db.add(sess)
    user.last_login_at = utcnow()
    user.failed_login_count = 0
    user.locked_until = None
    db.flush()
    return token, sess


def login_flags(db: Session, user: User) -> dict:
    s = get_settings()
    now = utcnow()
    contact_due = user.last_contact_verified_at is None or \
        now - user.last_contact_verified_at > timedelta(days=s.contact_verify_interval_days)
    pwd_expired = now - user.password_changed_at > timedelta(days=s.password_max_age_days)
    return {"must_change_password": user.must_change_password or pwd_expired,
            "password_expired": pwd_expired, "contact_verification_due": contact_due}


def user_out(user: User) -> dict:
    roles = sorted(role_codes(user))
    return {
        "id": user.id, "username": user.username, "full_name": user.full_name,
        "email": user.email, "mobile": user.mobile, "user_category": user.user_category,
        "department": user.department, "designation": user.designation,
        "centre": {"id": user.centre.id, "code": user.centre.code, "name_en": user.centre.name_en,
                   "name_hi": user.centre.name_hi} if user.centre else None,
        "entity_id": user.entity_id,
        "roles": roles,
        "role_centres": [{"role": ur.role.code, "centre": ur.centre.code if ur.centre else None} for ur in user.roles],
        "is_admin": is_admin(user), "is_external": is_external(user), "sees_all_centres": sees_all_centres(user),
        "is_active": user.is_active, "is_2fa_enabled": user.is_2fa_enabled,
        "allow_multi_session": user.allow_multi_session, "preferred_lang": user.preferred_lang,
        "has_signature": bool(user.signature_file_path),
        "modules": {m["key"]: module_level(user, m["key"]) for m in MODULES},
        "last_login_at": user.last_login_at,
    }


def module_launcher(user: User) -> list[dict]:
    return [{**m, "enabled": can_access(user, m["key"])} for m in MODULES]


def random_password() -> str:
    return "Oms@" + secrets.token_urlsafe(6) + "9a"
