"""Milestone 1 verification: auth, 2FA, lockout, RBAC launcher, sessions, audit (FRD UM-*, UI-06)."""
from app.core.security import new_captcha, password_policy_errors, verify_captcha
from app.core.config import get_settings


def test_superadmin_login_with_otp_and_full_launcher(client, auth):
    h = auth("superadmin")
    me = client.get("/api/v1/auth/me", headers=h).json()
    assert me["user"]["roles"] == ["SUPER_ADMIN"]
    assert all(m["enabled"] for m in me["launcher"])
    assert len(me["launcher"]) == 11


def test_external_re_user_sees_greyed_out_modules(client, auth):
    h = auth("re_dev")
    launcher = {m["key"]: m["enabled"] for m in client.get("/api/v1/auth/me", headers=h).json()["launcher"]}
    assert launcher["registration"] and launcher["ftc"] and launcher["cas"]
    assert not launcher["realtime"] and not launcher["mis"] and not launcher["protection"]


def test_login_type_must_match_category(client):
    r = client.post("/api/v1/auth/login", json={"username": "re_dev", "password": "Grid@2026", "login_type": "GRID_INDIA"})
    assert r.status_code == 403


def test_lockout_after_five_failures(client):
    for i in range(4):
        r = client.post("/api/v1/auth/login", json={"username": "director_mo", "password": "wrong", "login_type": "GRID_INDIA"})
        assert r.status_code == 401
    r = client.post("/api/v1/auth/login", json={"username": "director_mo", "password": "wrong", "login_type": "GRID_INDIA"})
    assert r.status_code == 423
    # even the right password is refused while locked
    r = client.post("/api/v1/auth/login", json={"username": "director_mo", "password": "Grid@2026", "login_type": "GRID_INDIA"})
    assert r.status_code == 423


def test_password_policy():
    assert password_policy_errors("short") != []
    assert "a special character" in password_policy_errors("Abcdefg1")
    assert password_policy_errors("Abcdef1!") == []


def test_captcha_roundtrip(monkeypatch):
    monkeypatch.setattr(get_settings(), "captcha_enabled", True)
    cap = new_captcha()
    a, op, b = cap["question"].split(" = ")[0].split()
    ans = int(a) + int(b) if op == "+" else int(a) * int(b)
    assert verify_captcha(cap["captcha_token"], str(ans))
    assert not verify_captcha(cap["captcha_token"], str(ans + 1))


def test_audit_records_login(client, auth):
    h = auth("superadmin")
    logs = client.get("/api/v1/admin/audit-logs", params={"module": "auth"}, headers=h).json()
    assert any(l["action"] == "LOGIN_SUCCESS" for l in logs)


def test_sessions_and_force_logout(client, auth):
    h_admin = auth("superadmin")
    # second, independent login for nr_head
    r = client.post("/api/v1/auth/login", json={"username": "nr_head", "password": "Grid@2026", "login_type": "GRID_INDIA"}).json()
    tok = client.post("/api/v1/auth/verify-otp", json={"challenge_id": r["challenge_id"], "otp": r["dev_otp"]}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/v1/auth/me", headers=h).status_code == 200
    sessions = client.get("/api/v1/admin/sessions", headers=h_admin).json()
    sid = next(s["id"] for s in sessions if s["username"] == "nr_head")
    assert client.delete(f"/api/v1/auth/sessions/{sid}", headers=h_admin).status_code == 200
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401


def test_single_session_mode_supersedes_old_session(client, auth):
    h_admin = auth("superadmin")
    users = client.get("/api/v1/admin/users", params={"q": "nr_mo"}, headers=h_admin).json()
    uid = users[0]["id"]
    client.patch(f"/api/v1/admin/users/{uid}", json={"allow_multi_session": False}, headers=h_admin)

    def fresh():
        r = client.post("/api/v1/auth/login", json={"username": "nr_mo", "password": "Grid@2026", "login_type": "GRID_INDIA"}).json()
        return client.post("/api/v1/auth/verify-otp", json={"challenge_id": r["challenge_id"], "otp": r["dev_otp"]}).json()["access_token"]

    t1 = fresh()
    t2 = fresh()
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t1}"}).status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t2}"}).status_code == 200


def test_admin_creates_user_and_requires_password_change(client, auth):
    h = auth("superadmin")
    r = client.post("/api/v1/admin/users", headers=h, json={
        "username": "new_scada", "full_name": "New SCADA Engineer", "email": "new_scada@example.org",
        "mobile": "9876543210", "user_category": "GRID_INDIA", "centre_code": "WRLDC", "roles": ["DEPT_USER"]})
    assert r.status_code == 200, r.text
    act = r.json()["activation"]
    r = client.post("/api/v1/auth/reset-password", json={"challenge_id": act["challenge_id"], "otp": act["dev_otp"], "new_password": "weak"})
    assert r.status_code == 422
    r = client.post("/api/v1/auth/reset-password", json={"challenge_id": act["challenge_id"], "otp": act["dev_otp"], "new_password": "Strong@123"})
    assert r.status_code == 200


def test_contact_review_flag_for_stale_user(client, auth):
    h = auth("pg_user")
    me = client.get("/api/v1/auth/me", headers=h).json()
    assert me["contact_verification_due"] is True
    client.post("/api/v1/auth/verify-contacts", json={"retain": True}, headers=h)
    assert client.get("/api/v1/auth/me", headers=h).json()["contact_verification_due"] is False


def test_refresh_interval_bounded(client, auth):
    h = auth("superadmin")
    assert client.put("/api/v1/admin/settings", json={"refresh_interval_ms": 5000}, headers=h).status_code == 422
    assert client.put("/api/v1/admin/settings", json={"refresh_interval_ms": 2000}, headers=h).status_code == 200


def test_security_headers(client):
    r = client.get("/api/v1/health")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "Server-Timing" in r.headers
