"""Group A: Centres, users, roles, sessions, OTP, audit (FRD UM-*, UI-06)."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, utcnow


class Centre(IdMixin, Base):
    __tablename__ = "centres"
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name_en: Mapped[str] = mapped_column(String(120))
    name_hi: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(60), default="")
    region_code: Mapped[str] = mapped_column(String(4), default="")  # NR, ER, WR, SR, NER, NLDC
    shift_start_time: Mapped[str] = mapped_column(String(5), default="08:30")


class Role(IdMixin, Base):
    __tablename__ = "roles"
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    name_hi: Mapped[str] = mapped_column(String(120), default="")
    module_scope: Mapped[str] = mapped_column(String(40), default="*")
    # permissions: {"modules": ["ftc", ...] | ["*"], "actions": ["read","write","approve","admin"]}
    permissions_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=True)


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(160), default="")
    mobile: Mapped[str] = mapped_column(String(20), default="")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    mobile_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # GRID_INDIA | EXTERNAL | CTU | RPC | PUBLIC
    user_category: Mapped[str] = mapped_column(String(20), default="GRID_INDIA")
    department: Mapped[str] = mapped_column(String(40), default="")  # SO-1, SCADA, METERING ...
    designation: Mapped[str] = mapped_column(String(80), default="")
    centre_id: Mapped[int | None] = mapped_column(ForeignKey("centres.id"), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_2fa_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_multi_session: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_contact_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    signature_file_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    dsc_serial: Mapped[str | None] = mapped_column(String(80), nullable=True)
    preferred_lang: Mapped[str] = mapped_column(String(2), default="en")

    centre = relationship("Centre", lazy="joined")
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan", lazy="selectin")


class UserRole(IdMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", "centre_id"),)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    centre_id: Mapped[int | None] = mapped_column(ForeignKey("centres.id"), nullable=True)

    user = relationship("User", back_populates="roles")
    role = relationship("Role", lazy="joined")
    centre = relationship("Centre", lazy="joined")


class UserSession(IdMixin, Base):
    __tablename__ = "user_sessions"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id"), nullable=True)
    ended_reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user = relationship("User", lazy="joined")


class OtpVerification(IdMixin, Base):
    __tablename__ = "otp_verifications"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(10))  # EMAIL | SMS
    otp_hash: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(String(30))  # LOGIN | RESET | VERIFY_CONTACT | CONFIDENTIAL_DOC
    challenge_id: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(IdMixin, Base):
    """Immutable audit trail (TS Cl. 2.4 'Audit Trails'; Cl. 11.3(e))."""

    __tablename__ = "audit_logs"
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(80), default="")
    centre_id: Mapped[int | None] = mapped_column(ForeignKey("centres.id"), nullable=True)
    module: Mapped[str] = mapped_column(String(40), index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), default="")
    entity_id: Mapped[str] = mapped_column(String(60), default="")
    old_values_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_values_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class SystemSetting(IdMixin, Base):
    """Admin-editable runtime parameters (refresh rate, code validity...)."""

    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(80), unique=True)
    value_json: Mapped[object] = mapped_column(JSON)
    description: Mapped[str] = mapped_column(Text, default="")


class NotificationToggle(IdMixin, Base):
    """Per-workflow-step enable/disable of SMS and e-mail (TS Cl. 2.3, p.25)."""

    __tablename__ = "notification_toggles"
    __table_args__ = (UniqueConstraint("module", "step_code", "centre_id"),)
    module: Mapped[str] = mapped_column(String(40))
    step_code: Mapped[str] = mapped_column(String(80))
    centre_id: Mapped[int | None] = mapped_column(ForeignKey("centres.id"), nullable=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Notification(IdMixin, Base):
    """In-app notification inbox + outbox log for e-mail/SMS (mock dispatcher)."""

    __tablename__ = "notifications"
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(10))  # INAPP | EMAIL | SMS | PUSH
    recipient: Mapped[str] = mapped_column(String(160), default="")
    module: Mapped[str] = mapped_column(String(40), default="")
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(String(300), default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
