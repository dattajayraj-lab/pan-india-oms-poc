"""Milestone 2 verification: portal CMS + Complaint Addressal System (FRD CMS-*, CAS-*)."""
from datetime import timedelta

from app.db.base import utcnow
from app.db.session import SessionLocal
from app.modules.ticketing_cas import service as svc
from app.modules.ticketing_cas.models import Ticket


def test_public_portal_without_login(client):
    r = client.get("/api/v1/portal/public")
    assert r.status_code == 200
    body = r.json()
    assert body["notice"] and body["flasher"] and body["banner"]
    assert body["notice"][0]["title_hi"]  # bilingual
    assert any(m["target_type"] == "EXTERNAL" for m in body["menu"])
    assert len(body["tiles"]) == 4


def test_verify_and_publish_workflow(client, auth):
    coord = auth("nr_coord")
    admin = auth("superadmin")
    r = client.post("/api/v1/portal/content", headers=coord, data={"content_type": "FLASHER", "title_en": "New A4 template",
                    "title_hi": "नया ए4 टेम्पलेट"}, files={"file": ("a4.pdf", b"%PDF-1.4 test", "application/pdf")})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    assert client.post(f"/api/v1/portal/content/{cid}/transition", headers=coord, json={"action": "PUBLISH"}).status_code in (403, 409)
    assert client.post(f"/api/v1/portal/content/{cid}/transition", headers=coord, json={"action": "SUBMIT"}).status_code == 200
    assert client.post(f"/api/v1/portal/content/{cid}/transition", headers=coord, json={"action": "PUBLISH"}).status_code == 403
    assert client.post(f"/api/v1/portal/content/{cid}/transition", headers=admin, json={"action": "PUBLISH"}).json()["is_published"]
    pub = client.get("/api/v1/portal/public").json()
    fl = next(f for f in pub["flasher"] if f["id"] == cid)
    assert client.get(f"/api/v1/portal/public/file/{fl['attachment_doc_id']}").status_code == 200


def test_flasher_rejects_wrong_type(client, auth):
    coord = auth("nr_coord")
    r = client.post("/api/v1/portal/content", headers=coord, data={"content_type": "FLASHER", "title_en": "x"},
                    files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415


def test_feedback_public(client):
    r = client.post("/api/v1/portal/feedback", json={"name": "Visitor", "message": "Great portal, add more graphs", "rating": 5})
    assert r.status_code == 200


def test_severity1_ticket_full_lifecycle(client, auth):
    pg = auth("pg_user")
    helpdesk = auth("nr_helpdesk")
    rldc = auth("nr_head")
    r = client.post("/api/v1/cas/tickets", headers=pg, data={"module": "realtime", "subject": "Codebook page not loading",
                    "description": "Real-time outage page returns error since 10:00", "centre_code": "NRLDC", "priority_requested": "HIGH"})
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    assert r.json()["ticket_number"].startswith("CAS/NRLDC/")

    # helpdesk assesses priority (level 0 -> 1); AMC cannot set severity
    assert client.post(f"/api/v1/cas/tickets/{tid}/assess", headers=helpdesk, json={"severity": 1}).status_code == 403
    t = client.post(f"/api/v1/cas/tickets/{tid}/assess", headers=helpdesk, json={"priority": "CRITICAL", "tags": ["codebook"]}).json()
    assert t["escalation_level"] == 1 and t["priority"] == "CRITICAL"
    # RLDC assesses severity 1 -> SLA 30 min / 2 h
    t = client.post(f"/api/v1/cas/tickets/{tid}/assess", headers=rldc, json={"severity": 1}).json()
    assert t["severity"] == 1 and t["sla_resolution_due"]

    # backdate level entry and run auto-escalation: L1 -> L2
    with SessionLocal() as db:
        tk = db.get(Ticket, tid)
        tk.level_entered_at = utcnow() - timedelta(hours=5)
        tk.created_at = utcnow() - timedelta(hours=5)
        svc.apply_sla(tk)
        db.commit()
        assert tk.ticket_number in svc.auto_escalate(db)
        db.commit()
    t = client.get(f"/api/v1/cas/tickets/{tid}", headers=pg).json()
    assert t["escalation_level"] == 2
    assert t["resolution_breached"] is True
    assert any(h["event"] == "AUTO_ESCALATED" for h in t["history"])

    # resolve -> stakeholder re-opens -> resolve -> feedback closes
    assert client.post(f"/api/v1/cas/tickets/{tid}/action", headers=helpdesk, data={"action": "RESOLVE", "comment": "Cache cleared"}).json()["status"] == "RESOLVED"
    assert client.post(f"/api/v1/cas/tickets/{tid}/action", headers=pg, data={"action": "REOPEN", "comment": "Still failing"}).json()["status"] == "REOPENED"
    client.post(f"/api/v1/cas/tickets/{tid}/action", headers=helpdesk, data={"action": "RESOLVE", "comment": "Pod restarted"})
    t = client.post(f"/api/v1/cas/tickets/{tid}/action", headers=pg, data={"action": "FEEDBACK", "rating": 4, "comment": "ok"}).json()
    assert t["status"] == "CLOSED" and t["reopen_count"] == 1

    # tracker visible to stakeholder
    full = client.get(f"/api/v1/cas/tickets/{tid}", headers=pg).json()
    assert [s["state"] for s in full["tracker"]][:4] == ["DONE", "DONE", "DONE", "DONE"]


def test_sla_penalty_report_exports(client, auth):
    h = auth("nr_helpdesk")
    now = utcnow()
    month = f"{now.year}-{now.month:02d}"
    j = client.get("/api/v1/cas/sla-penalty-report", headers=h, params={"from_month": month}).json()
    assert len(j["months"]) == 3 and "total_penalty" in j
    pdf = client.get("/api/v1/cas/sla-penalty-report", headers=h, params={"from_month": month, "fmt": "pdf"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    x = client.get("/api/v1/cas/sla-penalty-report", headers=h, params={"from_month": month, "fmt": "xlsx"})
    assert x.status_code == 200 and x.content[:2] == b"PK"


def test_penalty_slabs():
    assert svc.penalty_pct(99.96) == 0
    assert svc.penalty_pct(99.93) == 10   # TS worked example
    assert svc.penalty_pct(97.0) == 55
    assert svc.penalty_pct(85.0) == 80


def test_fourteen_dashboards_and_reports(client, auth):
    h = auth("nldc_head")
    dashes = client.get("/api/v1/cas/dashboards", headers=h).json()
    assert len(dashes) == 14
    assert client.get("/api/v1/cas/dashboards/NRLDC_COORD", headers=h).json()["total"] >= 1
    reps = client.get("/api/v1/cas/reports", headers=h).json()
    assert len(reps) == 14
    assert client.get("/api/v1/cas/reports/CENTRE_NRLDC", headers=h, params={"fmt": "pdf"}).content.startswith(b"%PDF")


def test_external_cannot_see_others_tickets(client, auth):
    rv = auth("rvpn_user")
    assert client.get("/api/v1/cas/tickets", headers=rv).json() == []
