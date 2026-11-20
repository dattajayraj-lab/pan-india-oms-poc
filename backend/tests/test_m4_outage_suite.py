"""Milestone 4 verification (development plan): open Morning shift -> approve OCC outage -> stakeholder consents ->
issue code -> execution time -> close shift -> open Evening shift -> monthly availability sheet and tripping-event linkage."""
from datetime import datetime, timedelta, timezone

from app.db.base import utcnow


def iso(dt: datetime) -> str:
    return dt.replace(tzinfo=timezone.utc).isoformat()


def find_element(client, h, q):
    return client.get("/api/v1/master/elements", headers=h, params={"q": q}).json()[0]


def test_control_room_end_to_end(client, auth):
    sic, op, pg, ntpc, rpc, oc = (auth(u) for u in ("nr_shiftic", "nr_operator", "pg_user", "ntpc_user", "nrpc_user", "nr_outage"))
    staff = client.get("/api/v1/realtime/staff", headers=sic, params={"centre": "NRLDC"}).json()
    opid = next(s["id"] for s in staff if s["username"] == "nr_operator")
    # only shift in-charge creates shifts
    assert client.post("/api/v1/realtime/shifts/open", headers=op, json={"centre_code": "NRLDC", "shift_type": "MORNING"}).status_code == 403
    sh = client.post("/api/v1/realtime/shifts/open", headers=sic, json={"centre_code": "NRLDC", "shift_type": "MORNING",
                     "staff": [{"user_id": opid, "desk": "RTSD"}]}).json()
    assert sh["shift_type"] == "MORNING"
    assert client.post("/api/v1/realtime/shifts/open", headers=sic, json={"centre_code": "NRLDC", "shift_type": "EVENING"}).status_code == 409

    # OCC outage planning: late request -> RPC enables -> forwards -> OCC approval -> RLDC review -> D-1 approval
    el = find_element(client, pg, "Ballabhgarh-Dadri")
    start = utcnow() + timedelta(days=2)
    p = client.post("/api/v1/outage/plans", headers=pg, json={"grid_element_id": el["id"], "req_from": iso(start), "req_to": iso(start + timedelta(hours=8)),
                    "reason": "Insulator replacement", "availability_head_proposed": "SELF", "availability_comments": "Planned AMP"}).json()
    assert p["plan_route"] == "OCC_M2"
    pid = p["id"]
    if p["status"] == "LATE_PENDING_RPC":
        assert client.post("/api/v1/outage/rpc", headers=rpc, json={"plan_ids": [pid], "action": "ENABLE_LATE"}).status_code == 200
    client.post("/api/v1/outage/rpc", headers=rpc, json={"plan_ids": [pid], "action": "FORWARD"})
    client.post(f"/api/v1/outage/plans/{pid}/rldc-review", headers=oc, json={"rldc_comments": "OK from grid security", "availability_head_rldc": "SELF", "category_code": "C01"})
    client.post("/api/v1/outage/rpc", headers=rpc, json={"plan_ids": [pid], "action": "OCC_APPROVE", "remarks": "Approved in 230th OCC"})
    sheets = client.get("/api/v1/outage/utility-sheets", headers=oc, params={"centre": "NRLDC"}).json()
    assert any("POWERGRID" in k for k in sheets)
    r = client.post(f"/api/v1/outage/plans/{pid}/d1", headers=oc, data={"approve": "true", "comment_coordinator": "Study OK", "comment_hod": "ok", "comment_head": "ok"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "D1_APPROVED"

    # planned request appears in real-time with NTPC (other end) consent pending
    reqs = client.get("/api/v1/realtime/requests", headers=op, params={"centre": "NRLDC", "category": "PLANNED"}).json()
    req = next(x for x in reqs if x["element_id"] == el["id"])
    assert req["status"] == "CONSENT_PENDING" and not req["consents_complete"]
    assert client.post(f"/api/v1/realtime/requests/{req['id']}/issue-code", headers=op, json={}).status_code == 409
    client.post(f"/api/v1/realtime/requests/{req['id']}/consent", headers=ntpc, json={"approve": True, "remarks": "Agreed"})
    # code only by executives on the active shift
    assert client.post(f"/api/v1/realtime/requests/{req['id']}/issue-code", headers=auth("nr_head"), json={}).status_code == 403
    code = client.post(f"/api/v1/realtime/requests/{req['id']}/issue-code", headers=op, json={"description": "Open line for insulator replacement"}).json()
    assert code["code_type"] == "OUTAGE" and code["two_ended"]

    # both ends enter times; earlier = shutdown time; future time rejected
    now = utcnow()
    assert client.post(f"/api/v1/realtime/codes/{code['id']}/execute", headers=pg, json={"exec_time": iso(now + timedelta(hours=1))}).status_code == 422
    c1 = client.post(f"/api/v1/realtime/codes/{code['id']}/execute", headers=pg, json={"exec_time": iso(now)}).json()
    assert c1["final_exec_time"] is None
    c2 = client.post(f"/api/v1/realtime/codes/{code['id']}/execute", headers=ntpc, json={"exec_time": iso(now - timedelta(seconds=30))}).json()
    assert c2["final_exec_time"]
    assert find_element(client, op, "Ballabhgarh-Dadri")["status"] == "OUTAGE"

    # charging back: request -> consent -> code -> both ends (later = charging time) -> IN_SERVICE -> availability record
    rq = client.post("/api/v1/realtime/requests", headers=pg, json={"request_category": "PLANNED", "grid_element_id": el["id"], "action": "CHARGING",
                     "availability_head_proposed": "SELF"}).json()
    client.post(f"/api/v1/realtime/requests/{rq['id']}/consent", headers=ntpc, json={"approve": True})
    cc = client.post(f"/api/v1/realtime/requests/{rq['id']}/issue-code", headers=op, json={}).json()
    t2 = utcnow()
    client.post(f"/api/v1/realtime/codes/{cc['id']}/execute", headers=pg, json={"exec_time": iso(t2)})
    client.post(f"/api/v1/realtime/codes/{cc['id']}/execute", headers=ntpc, json={"exec_time": iso(t2)})
    assert find_element(client, op, "Ballabhgarh-Dadri")["status"] == "IN_SERVICE"

    # tripping of a generating unit by NTPC -> protection event with End restriction
    unit = find_element(client, ntpc, "Dadri Unit-1")
    client.post("/api/v1/realtime/trippings", headers=ntpc, json={"grid_element_id": unit["id"], "relay_flags": "Generator differential",
                "tripped_at": iso(utcnow() - timedelta(minutes=10)), "reason": "Stator earth fault", "expected_revival_at": iso(utcnow() + timedelta(days=1))})
    trips = client.get("/api/v1/protection/candidates", headers=auth("nr_protection")).json()
    ev = client.post("/api/v1/protection/events", headers=auth("nr_protection"), json={"tripping_report_ids": [trips[0]["id"]], "category": "GI-1"}).json()
    assert ev["event_code"].startswith("EV/NRLDC")
    assert client.put(f"/api/v1/protection/events/{ev['id']}/fir", headers=pg, json={"end": "END1", "data": {"x": 1}}).status_code == 403
    assert client.put(f"/api/v1/protection/events/{ev['id']}/fir", headers=ntpc, json={"end": "END1", "data": {"cause": "SEF"}}).status_code == 200
    r = client.post(f"/api/v1/protection/events/{ev['id']}/files", headers=ntpc, data={"kind": "DR_MAIN1", "end": "END1"},
                    files={"file": ("dr.cfg", b"station,1999", "text/plain")})
    assert r.status_code == 200, r.text
    assert client.post(f"/api/v1/protection/events/{ev['id']}/files", headers=ntpc, data={"kind": "DR_MAIN1", "end": "END1"},
                       files={"file": ("dr2.cfg", b"x", "text/plain")}).status_code == 409
    full = client.get(f"/api/v1/protection/events/{ev['id']}", headers=ntpc).json()
    assert full["submission"]["END1"]["FIR"] and full["submission"]["END1"]["DR"]
    psc = client.post("/api/v1/protection/psc", headers=auth("nr_protection"), json={"tripping_event_id": ev["id"], "psc_meeting_no": "PSC-58", "recommendations": "Review SEF setting"}).json()
    assert psc["compliance_status"] == "NOT_COMPLIED"

    # close Morning shift (works + handover mandatory) -> open Evening; Morning sessions auto-logged out
    s = client.get("/api/v1/realtime/shifts/active", headers=sic, params={"centre": "NRLDC"}).json()["active"]
    assert client.post(f"/api/v1/realtime/shifts/{s['id']}/close", headers=sic).status_code == 422
    for w in s["works"]:
        client.patch(f"/api/v1/realtime/shifts/{s['id']}/works", headers=op, json={"key": w["key"], "done": True})
    client.put(f"/api/v1/realtime/shifts/{s['id']}/handover", headers=sic, json={"handover_notes": "Dadri U-1 tripped; Ballabhgarh-Dadri restored"})
    closed = client.post(f"/api/v1/realtime/shifts/{s['id']}/close", headers=sic).json()
    assert closed["status"] == "CLOSED" and closed["report_status"] == "FINAL"
    rep = client.get(f"/api/v1/realtime/shifts/{s['id']}/report", headers=sic).json()
    assert len(rep["report"]["codes"]) >= 2
    assert client.put(f"/api/v1/realtime/shifts/{s['id']}/report", headers=sic, json={"x": 1}).status_code == 409
    assert client.post("/api/v1/realtime/shifts/open", headers=sic, json={"centre_code": "NRLDC", "shift_type": "NIGHT"}).status_code == 409
    ev2 = client.post("/api/v1/realtime/shifts/open", headers=sic, json={"centre_code": "NRLDC", "shift_type": "EVENING"})
    assert ev2.status_code == 200, ev2.text

    # monthly availability sheet: licensee sees its outage, accepts (locks)
    month = f"{utcnow():%Y-%m}"
    sheet = client.get("/api/v1/availability/sheet", headers=pg, params={"month": month}).json()
    rows = [r for tab in sheet["tabs"].values() for r in tab]
    row = next(r for r in rows if r["element_id"] == el["id"])
    assert row["tab"] == "Outage_Self" and row["category_code"] == "C01"
    a = client.post(f"/api/v1/availability/records/{row['id']}/action", headers=pg, json={"action": "ACCEPT"}).json()
    assert a["is_locked"]
    assert client.post(f"/api/v1/availability/records/{row['id']}/action", headers=pg, json={"action": "OBJECT", "comments": "x"}).status_code == 409
    x = client.get("/api/v1/availability/sheet/export", headers=oc, params={"month": month})
    assert x.status_code == 200 and x.content[:2] == b"PK"


def test_availability_bifurcation_and_rpc(client, auth):
    oc = auth("nr_outage")
    month = f"{utcnow():%Y-%m}"
    rows = [r for tab in client.get("/api/v1/availability/sheet", headers=oc, params={"month": month, "centre": "NRLDC"}).json()["tabs"].values() for r in tab]
    r = rows[0]
    s, e = datetime.fromisoformat(r["outage_start"]), datetime.fromisoformat(r["outage_end"])
    mid = s + (e - s) / 2
    bad = client.post(f"/api/v1/availability/records/{r['id']}/bifurcate", headers=oc, json={"segments": [{"start": iso(s), "end": iso(mid)}, {"start": iso(mid + timedelta(seconds=1)), "end": iso(e)}]})
    assert bad.status_code == 422
    kids = client.post(f"/api/v1/availability/records/{r['id']}/bifurcate", headers=oc, json={"segments": [
        {"start": iso(s), "end": iso(mid), "head": "DEEMED", "category_code": "C14"}, {"start": iso(mid), "end": iso(e), "head": "SELF"}]}).json()
    assert len(kids) == 2 and kids[0]["tab"] == "Outage_System"
    ids = [k["id"] for k in kids]
    assert client.post("/api/v1/availability/coordinator", headers=oc, json={"record_ids": ids, "action": "FORWARD_RPC"}).status_code == 409
    client.post("/api/v1/availability/coordinator", headers=oc, json={"record_ids": ids, "action": "VERIFY", "comment": "ok"})
    assert client.post("/api/v1/availability/coordinator", headers=oc, json={"record_ids": ids, "action": "FORWARD_RPC"}).status_code == 200
    rpc_rows = [x for tab in client.get("/api/v1/availability/sheet", headers=auth("nrpc_user"), params={"month": month}).json()["tabs"].values() for x in tab]
    assert {x["id"] for x in rpc_rows} >= set(ids)


def test_gate_blocks_requests_and_other_element_check(client, auth):
    op = auth("nr_operator")
    r = client.post("/api/v1/realtime/requests", headers=op, json={"request_category": "OTHER_ELEMENT", "other_element_desc": "400 kV Bikaner-Bhadla Ckt-1", "centre_code": "NRLDC"})
    assert r.status_code == 409  # element exists in master DB
    rv = auth("rvpn_user")
    el = find_element(client, op, "Agra-Gwalior")
    assert client.post("/api/v1/realtime/requests", headers=rv, json={"request_category": "FORCED", "grid_element_id": el["id"], "reason": "x"}).status_code == 403


def test_hv_batch_codes_and_re_single_window(client, auth):
    op = auth("nr_shiftic")  # in-charge of the currently open Evening shift
    lines = [e["id"] for e in client.get("/api/v1/master/elements", headers=op, params={"element_type": "AC_LINE", "centre": "NRLDC", "voltage": 400}).json()[:2]]
    r = client.post("/api/v1/realtime/batch-codes", headers=op, json={"kind": "HV_CODE", "element_ids": lines, "description": "High voltage at Bikaner"})
    assert r.status_code == 200, r.text
    assert len(r.json()["codes"]) == 2
    plants = client.get("/api/v1/realtime/re-plants", headers=op, params={"centre": "NRLDC"}).json()
    assert plants
    bad = client.post("/api/v1/realtime/re-mvar", headers=op, json={"mode": "FIXED_PF", "items": [{"element_id": plants[0]["element_id"], "value": 0.5}]})
    assert bad.status_code == 422
    ok = client.post("/api/v1/realtime/re-mvar", headers=op, json={"mode": "FIXED_Q", "items": [{"element_id": p["element_id"], "value": 30} for p in plants]})
    assert ok.status_code == 200 and "FIXED_Q" in ok.json()["description"]


def test_alerts_and_sps(client, auth):
    h = auth("nr_alerts")
    prev = client.post("/api/v1/alerts/send", headers=h, json={"template_code": "HIGH_VOLTAGE", "category": "STATE", "targets": ["RVPN"],
                       "payload": {"station": "Bhiwadi", "voltage": 432}, "preview": True}).json()
    assert "432" in prev["messages"][0]["sms"] and prev["total_recipients"] == 0
    sent = client.post("/api/v1/alerts/send", headers=h, json={"template_code": "HIGH_VOLTAGE", "category": "STATE", "targets": ["RVPN"],
                       "payload": {"station": "Bhiwadi", "voltage": 432}}).json()
    assert sent["total_recipients"] >= 2
    assert client.get("/api/v1/alerts/history", headers=h).json()["by_target"]["RVPN"] >= 1
    assert client.post("/api/v1/alerts/send", headers=auth("pg_user"), json={"template_code": "HIGH_VOLTAGE", "category": "STATE", "targets": ["RVPN"]}).status_code == 403
    s = client.get("/api/v1/sps/schemes", headers=h).json()[0]
    assert client.post(f"/api/v1/sps/schemes/{s['id']}/status", headers=h, json={"status": "OFF", "remarks": "maintenance"}).json()["status"] == "OFF"
    assert len(client.get(f"/api/v1/sps/schemes/{s['id']}/timeline", headers=h).json()) >= 5
    assert client.get("/api/v1/sps/schemes", headers=h, params={"fmt": "xlsx"}).status_code == 200


def test_code_auto_revoke_after_one_hour(client, auth, db_session):
    from app.modules.realtime_outage import service
    from app.modules.realtime_outage.models import OutageCode
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        c = db.query(OutageCode).filter(OutageCode.final_exec_time.is_(None), OutageCode.is_revoked.is_(False)).first()
        assert c is not None
        stats = service.code_timers(db, now=c.issued_at + timedelta(minutes=61))
        db.commit()
        assert stats["revoked"] >= 1
