"""Role catalogue, module permissions, and FastAPI auth dependencies (FRD UM-01, UM-19, UM-20)."""
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.base import utcnow
from app.db.session import get_db

# Module keys used throughout the app; order = launcher order (TS Cl. 2.5, BoQ Part C).
MODULES: list[dict] = [
    {"key": "cas", "name_en": "Complaint Addressal System", "name_hi": "शिकायत निवारण प्रणाली", "icon": "ticket"},
    {"key": "registration", "name_en": "Registration", "name_hi": "पंजीकरण", "icon": "id"},
    {"key": "ftc", "name_en": "First Time Charging", "name_hi": "प्रथम चार्जिंग", "icon": "bolt"},
    {"key": "comm_cert", "name_en": "Communication Certification", "name_hi": "संचार प्रमाणन", "icon": "signal"},
    {"key": "realtime", "name_en": "Real-time Outage Management", "name_hi": "वास्तविक-समय आउटेज प्रबंधन", "icon": "pulse"},
    {"key": "outage_coord", "name_en": "Outage Coordination", "name_hi": "आउटेज समन्वय", "icon": "calendar"},
    {"key": "availability", "name_en": "Availability Inputs Verification", "name_hi": "उपलब्धता इनपुट सत्यापन", "icon": "check"},
    {"key": "protection", "name_en": "Protection & Tripping Studies", "name_hi": "संरक्षण एवं ट्रिपिंग अध्ययन", "icon": "shield"},
    {"key": "alerts", "name_en": "Message Alerts", "name_hi": "संदेश अलर्ट", "icon": "bell"},
    {"key": "sps", "name_en": "SPS Status", "name_hi": "एसपीएस स्थिति", "icon": "toggle"},
    {"key": "mis", "name_en": "MIS & Reporting", "name_hi": "एमआईएस एवं रिपोर्टिंग", "icon": "chart"},
]
MODULE_KEYS = [m["key"] for m in MODULES]
ALL = ["*"]
INTERNAL_ALL = MODULE_KEYS

# code: (name_en, name_hi, modules, level, internal)
# level: read < write < approve < admin
ROLE_DEFS: dict[str, tuple[str, str, list[str], str, bool]] = {
    "SUPER_ADMIN": ("Super Admin", "सुपर एडमिन", ALL, "admin", True),
    "MODULE_ADMIN": ("Module Admin", "मॉड्यूल एडमिन", ALL, "admin", True),
    "REG_COORDINATOR": ("Registration Coordinator", "पंजीकरण समन्वयक", ["registration", "cas", "mis"], "approve", True),
    "FTC_COORDINATOR": ("FTC Coordinator", "एफटीसी समन्वयक", ["ftc", "registration", "cas", "mis", "realtime"], "approve", True),
    "COMM_COORDINATOR": ("Communication Certification Coordinator", "संचार प्रमाणन समन्वयक", ["comm_cert", "cas", "mis"], "approve", True),
    "RT_COORDINATOR": ("Real-time Outage Coordinator / Grid Operator", "ग्रिड ऑपरेटर", ["realtime", "outage_coord", "alerts", "sps", "protection", "cas", "mis"], "approve", True),
    "SHIFT_INCHARGE": ("Shift In-charge", "शिफ्ट प्रभारी", ["realtime", "outage_coord", "alerts", "sps", "protection", "cas", "mis"], "approve", True),
    "OUTAGE_COORDINATOR": ("Outage Coordinator", "आउटेज समन्वयक", ["outage_coord", "availability", "realtime", "cas", "mis"], "approve", True),
    "AVAIL_COORDINATOR": ("Availability Coordinator", "उपलब्धता समन्वयक", ["availability", "outage_coord", "cas", "mis"], "approve", True),
    "PROTECTION_COORDINATOR": ("Protection Coordinator", "संरक्षण समन्वयक", ["protection", "availability", "ftc", "cas", "mis"], "approve", True),
    "ALERTS_COORDINATOR": ("Alerts Coordinator", "अलर्ट समन्वयक", ["alerts", "realtime", "cas", "mis"], "approve", True),
    "SPS_COORDINATOR": ("SPS Coordinator", "एसपीएस समन्वयक", ["sps", "cas", "mis"], "approve", True),
    "MIS_COORDINATOR": ("MIS Coordinator", "एमआईएस समन्वयक", INTERNAL_ALL, "read", True),
    "DEPT_USER": ("Department User", "विभागीय उपयोगकर्ता", ["registration", "ftc", "comm_cert", "protection", "cas", "mis"], "approve", True),
    "HOD": ("Head of Department", "विभागाध्यक्ष", ["registration", "ftc", "comm_cert", "outage_coord", "cas", "mis"], "approve", True),
    "SUB_HEAD_SO": ("Sub-Head System Operation", "उप-प्रमुख प्रणाली प्रचालन", ["ftc", "outage_coord", "cas", "mis"], "approve", True),
    "HEAD_SO": ("Head of System Operation", "प्रमुख प्रणाली प्रचालन", ["ftc", "outage_coord", "cas", "mis"], "approve", True),
    "HEAD_RLDC": ("Head of RLDC", "प्रमुख आरएलडीसी", INTERNAL_ALL, "approve", True),
    "NLDC_USER": ("NLDC User", "एनएलडीसी उपयोगकर्ता", INTERNAL_ALL, "approve", True),
    "HEAD_NLDC": ("Head of NLDC", "प्रमुख एनएलडीसी", INTERNAL_ALL, "approve", True),
    "DIRECTOR": ("Director (SO/MO)", "निदेशक", INTERNAL_ALL, "read", True),
    "CAS_HELPDESK": ("AMC Helpdesk", "एएमसी हेल्पडेस्क", ["cas"], "approve", True),
    "INTERNAL_USER": ("Internal / Intranet User", "आंतरिक उपयोगकर्ता", INTERNAL_ALL, "read", True),
    "CTU": ("CTU (CTUIL) Login", "सीटीयू लॉगिन", ["registration", "comm_cert", "cas"], "approve", False),
    "RPC": ("RPC Login", "आरपीसी लॉगिन", ["outage_coord", "availability", "protection", "cas"], "approve", False),
    "EXTERNAL_USER": ("Registered External User", "पंजीकृत बाहरी उपयोगकर्ता", ["cas"], "write", False),
    "EXT_REGISTRATION": ("External: Registration", "बाहरी: पंजीकरण", ["registration"], "write", False),
    "EXT_FTC": ("External: FTC", "बाहरी: एफटीसी", ["ftc"], "write", False),
    "EXT_COMM": ("External: Communication Certification", "बाहरी: संचार प्रमाणन", ["comm_cert"], "write", False),
    "EXT_REALTIME": ("External: Real-time Outage", "बाहरी: वास्तविक-समय आउटेज", ["realtime"], "write", False),
    "EXT_OUTAGE": ("External: Outage Coordination", "बाहरी: आउटेज समन्वय", ["outage_coord"], "write", False),
    "EXT_AVAILABILITY": ("External: Availability", "बाहरी: उपलब्धता", ["availability"], "write", False),
    "EXT_PROTECTION": ("External: Protection", "बाहरी: संरक्षण", ["protection"], "write", False),
    "EXT_SPS": ("External: SPS", "बाहरी: एसपीएस", ["sps"], "write", False),
    "PUBLIC_USER": ("Public User", "सार्वजनिक उपयोगकर्ता", [], "read", False),
}
LEVELS = {"read": 1, "write": 2, "approve": 3, "admin": 4}
ADMIN_ROLES = {"SUPER_ADMIN", "MODULE_ADMIN"}
NLDC_WIDE_ROLES = {"SUPER_ADMIN", "MODULE_ADMIN", "NLDC_USER", "HEAD_NLDC", "DIRECTOR"}

bearer = HTTPBearer(auto_error=False)


def role_codes(user) -> set[str]:
    return {ur.role.code for ur in user.roles}


def module_level(user, module: str) -> int:
    best = 0
    for ur in user.roles:
        _, _, mods, level, _ = ROLE_DEFS.get(ur.role.code, ("", "", [], "read", True))
        if "*" in mods or module in mods:
            best = max(best, LEVELS[level])
    return best


def can_access(user, module: str, level: str = "read") -> bool:
    return module_level(user, module) >= LEVELS[level]


def is_admin(user) -> bool:
    return bool(role_codes(user) & ADMIN_ROLES)


def is_external(user) -> bool:
    return user.user_category in ("EXTERNAL", "CTU", "RPC", "PUBLIC")


def sees_all_centres(user) -> bool:
    """NLDC has view access to all RLDC data (TS Cl. 2.5 p.30)."""
    if role_codes(user) & NLDC_WIDE_ROLES:
        return True
    return bool(user.centre and user.centre.code == "NLDC" and not is_external(user))


def visible_centre_ids(db: Session, user) -> list[int] | None:
    """None means 'all centres'."""
    if sees_all_centres(user):
        return None
    ids = {ur.centre_id for ur in user.roles if ur.centre_id}
    if user.centre_id:
        ids.add(user.centre_id)
    return sorted(ids)


def get_current_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_db)):
    from app.modules.auth_rbac.models import User, UserSession
    from app.modules.auth_rbac.service import get_setting

    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_access_token(creds.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    sess = db.scalar(select(UserSession).where(UserSession.token_jti == payload["jti"]))
    if sess is None or not sess.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session ended")
    idle = int(get_setting(db, "idle_logout_minutes") or 30)
    now = utcnow()
    if now - sess.last_seen_at > timedelta(minutes=idle):
        sess.is_active = False
        sess.ended_reason = "IDLE_TIMEOUT"
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired due to inactivity")
    if (now - sess.last_seen_at).total_seconds() > 30:
        sess.last_seen_at = now
        db.commit()
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive")
    request.state.user = user
    request.state.session_id = sess.id
    return user


def require_module(module: str, level: str = "read"):
    def dep(user=Depends(get_current_user)):
        if not can_access(user, module, level):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Not authorised for {module} ({level})")
        return user

    return dep


def require_roles(*codes: str):
    def dep(user=Depends(get_current_user)):
        if not (role_codes(user) & (set(codes) | ADMIN_ROLES)):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Role not permitted for this action")
        return user

    return dep


def require_admin(user=Depends(get_current_user)):
    if not is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user
