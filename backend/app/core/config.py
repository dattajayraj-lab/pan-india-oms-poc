"""Runtime settings. Values can be overridden with OMS_* environment variables.

Admin-configurable operational parameters (refresh rate, lockout, code validity,
etc.) are *also* persisted in the `system_settings` table so the Admin can change
them from the front end (TS Cl. 2.4 refresh rate, Cl. 11.4.4 configurable fields).
The values here are only the defaults used when seeding that table.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OMS_", env_file=".env", extra="ignore")

    app_name: str = "Pan-Grid-India Operations Management System"
    database_url: str = f"sqlite:///{(BASE_DIR / 'oms_dev.db').as_posix()}"
    storage_dir: Path = BASE_DIR / "storage"

    jwt_secret: str = "change-me-in-production-oms-poc-secret-key-2026"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 480

    # Security policy (TS Ch.4, p.43)
    max_failed_logins: int = 5
    lockout_minutes: int = 30
    password_max_age_days: int = 90
    contact_verify_interval_days: int = 90  # TS Cl. 2.1, p.24: every 3 months
    otp_ttl_minutes: int = 10
    # POC convenience: echo OTPs in API responses so demos work without SMS/e-mail.
    dev_expose_otp: bool = True
    # Tests can disable CAPTCHA checking.
    captcha_enabled: bool = True

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    rate_limit: str = "300/minute"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.storage_dir.mkdir(parents=True, exist_ok=True)
    return s


# Defaults for the admin-editable `system_settings` table.
DEFAULT_SYSTEM_SETTINGS: dict[str, object] = {
    "refresh_interval_ms": 2000,           # Cl. 2.4: <= 2 s, admin configurable
    "idle_logout_minutes": 30,             # Table 1 note: auto-logout
    "allow_multi_session_default": True,   # Table 1 note
    "code_validity_minutes": 60,           # Cl. 11.4.4(6): code valid 1 hour
    "code_auto_revoke": True,
    "pre_charging_alert_minutes": 15,      # Cl. 11.4.4(6)
    "action_not_taken_minutes": 60,        # Cl. 11.4.4(7)
    "time_edit_window_minutes": 15,        # Cl. 11.4.4(8) note
    "exec_time_gate_hours_before_handover": 2,  # Cl. 11.4.4(7)
    "d3_window_start": "D-3 10:00",        # Cl. 11.4.7(b) note
    "d3_window_end": "D-3 17:00",
    "cas_l1_to_l2_hours": 4,               # Ch.5: admin-configured escalation
    "cas_l2_to_l3_hours": 8,
    "ftc_min_days_before_charging": 10,    # Cl. 11.4.2(e)3
    "trial_run_notice_working_days": 7,    # Cl. 11.4.2(e)4
    "protection_detailed_report_days": 7,  # Cl. 11.4.6
    "protection_flash_report_hours": 8,
    "protection_dr_el_hours": 24,
}
