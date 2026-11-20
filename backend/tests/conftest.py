import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_tmp = tempfile.mkdtemp(prefix="oms_test_")
os.environ["OMS_DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"
os.environ["OMS_STORAGE_DIR"] = str(Path(_tmp, "storage"))
os.environ["OMS_CAPTCHA_ENABLED"] = "false"
os.environ["OMS_RATE_LIMIT"] = "100000/minute"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.db.seed import DEMO_PASSWORD, seed  # noqa: E402
from app.db.session import SessionLocal, get_engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    eng = get_engine()
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    with SessionLocal() as db:
        seed(db)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def db_session():
    with SessionLocal() as db:
        yield db


_tokens: dict[str, str] = {}


def login(client, username: str, login_type: str | None = None, password: str = DEMO_PASSWORD) -> dict:
    """Returns auth headers; goes through password + OTP (2FA) steps."""
    if username in _tokens:
        return {"Authorization": f"Bearer {_tokens[username]}"}
    if login_type is None:
        external = username in {"re_dev", "adani_user", "pg_user", "ntpc_user", "rvpn_user", "mp_user", "tpcomm_user",
                                "public_user", "ctu_user", "nrpc_user"}
        login_type = "EXTERNAL" if external else "GRID_INDIA"
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password, "login_type": login_type})
    assert r.status_code == 200, r.text
    body = r.json()
    if body["otp_required"]:
        r = client.post("/api/v1/auth/verify-otp", json={"challenge_id": body["challenge_id"], "otp": body["dev_otp"]})
        assert r.status_code == 200, r.text
        body = r.json()
    _tokens[username] = body["access_token"]
    return {"Authorization": f"Bearer {body['access_token']}"}


@pytest.fixture
def auth(client):
    return lambda username, **kw: login(client, username, **kw)
