"""Milestone 3 verification: RE plant lifecycle NSWS -> NLDC shift & return -> CONN-4 -> FTC Stage 1-5 ->
Element IDs in master DB and enabled for Real-time Outage (development plan M3 'Verify')."""
import io
from datetime import date, timedelta

from openpyxl import Workbook

PDF = b"%PDF-1.4 signed annexure"


def up(client, h, url, cat, name="doc.pdf", data=PDF, extra=None):
    r = client.post(url, headers=h, data={"doc_category": cat, **(extra or {})}, files={"file": (name, data, "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()


def test_nsws_connectivity_with_nldc_shift_and_conn4(client, auth):
    ctu, nr, nldc, wr = auth("ctu_user"), auth("nr_coord"), auth("nldc_coord"), auth("wr_coord")
    app = client.post("/api/v1/registration/nsws/sync", headers=ctu, json={"nsws_ref_no": "NSWS-RE-2026-0042", "nodal_centre": "NRLDC"}).json()
    aid = app["application_id"]
    assert app["files_total"] == 7
    # RLDC cannot review before CTUIL shares
    full = client.get(f"/api/v1/registration/applications/{aid}", headers=nr).json()
    fid = full["files"][0]["id"]
    assert client.post(f"/api/v1/registration/files/{fid}/review", headers=nr, json={"reviewer": "RLDC", "status": "APPROVED"}).status_code == 403
    client.post(f"/api/v1/registration/applications/{aid}/ctu-submit", headers=ctu, json={"comments": {}})
    full = client.get(f"/api/v1/registration/applications/{aid}", headers=nr).json()
    assert full["files"][0]["ctu_comment"] == "Shared for inputs from RLDC"

    # NLDC shifts the unstarted RE application from NRLDC to WRLDC
    wl = client.get("/api/v1/registration/workload", headers=nldc).json()
    assert any(c["centre"] == "NRLDC" and c["unstarted"] >= 1 for c in wl)
    assert client.post("/api/v1/registration/shift", headers=nr, json={"application_ids": [aid], "to_centre": "WRLDC", "comment": "load"}).status_code == 403
    r = client.post("/api/v1/registration/shift", headers=nldc, json={"application_ids": [aid], "to_centre": "WRLDC", "comment": "NRLDC overloaded"})
    assert r.status_code == 200, r.text
    # WRLDC validates all files -> automatically returned to nodal NRLDC
    for f in full["files"]:
        r = client.post(f"/api/v1/registration/files/{f['id']}/review", headers=wr, json={"reviewer": "RLDC", "status": "APPROVED", "comment": "ok"})
        assert r.status_code == 200, r.text
    assert r.json()["returned_to_nodal"] is True
    full = client.get(f"/api/v1/registration/applications/{aid}", headers=nr).json()
    assert full["current_centre"] == "NRLDC" and full["shifts"][0]["returned_at"]
    # shifting after processing started is refused
    assert client.post("/api/v1/registration/shift", headers=nldc, json={"application_ids": [aid], "to_centre": "SRLDC", "comment": "again"}).status_code == 409

    # CTUIL marks one file for revision, releases partial joint comments
    first = full["files"][0]["id"]
    client.post(f"/api/v1/registration/files/{first}/review", headers=ctu, json={"reviewer": "CTU", "status": "NEEDS_REVISION", "comment": "Governor model missing"})
    client.post(f"/api/v1/registration/applications/{aid}/joint-comments", headers=ctu, json={"items": [{"file_id": first, "source": "CTU"}]})
    assert client.post(f"/api/v1/registration/applications/{aid}/complete", headers=ctu).status_code == 409
    # requester revises (no zip allowed)
    assert client.post(f"/api/v1/registration/files/{first}/revise", headers=ctu, data={"change_note": "zip"},
                       files={"file": ("m.zip", b"PK..", "application/zip")}).status_code == 415
    r = client.post(f"/api/v1/registration/files/{first}/revise", headers=ctu, data={"change_note": "Added governor model"},
                    files={"file": ("model.pdf", PDF, "application/pdf")})
    assert r.json()["document"]["version_no"] == 2
    for f in full["files"]:
        client.post(f"/api/v1/registration/files/{f['id']}/review", headers=ctu, json={"reviewer": "CTU", "status": "APPROVED"})
    r = client.post(f"/api/v1/registration/applications/{aid}/complete", headers=ctu)
    assert r.status_code == 200, r.text
    assert client.get(f"/api/v1/registration/applications/{aid}", headers=nr).json()["status"] == "APPROVED"


def test_fnc_import_preview_commit(client, auth):
    h = auth("nr_coord")
    wb = Workbook()
    ws = wb.active
    ws.append(["Registration No", "Entity Name", "Entity Type", "Sub-category", "State", "GST No", "PAN No", "E-mail", "Mobile", "Capacity MW"])
    ws.append(["FNC-RE-0901", "Marwar Wind Pvt Ltd", "REGS", "WIND", "Rajasthan", "", "", "ops@marwar.example", "9876500009", 150])
    ws.append(["", "Bad Row", "XYZ", "", "", "", "", "bad", "", "abc"])
    buf = io.BytesIO()
    wb.save(buf)
    r = client.post("/api/v1/registration/fnc-import/preview", headers=h, files={"file": ("fnc.xlsx", buf.getvalue(), "application/octet-stream")}).json()
    assert r["valid"] == 1 and len(r["errors"]) == 1
    c = client.post(f"/api/v1/registration/fnc-import/{r['batch_id']}/commit", headers=h).json()
    assert c["created"][0]["username"] == "fnc_re_0901"


def test_signup_and_approval(client, auth):
    r = client.post("/api/v1/registration/signup", json={"user_type": "RE_REGISTRATION", "organisation": "Sunbeam Hybrid Ltd", "first_name": "Asha",
                    "mobile": "9876543299", "username": "sunbeam_ops", "email": "ops@sunbeam.example", "password": "Sunbeam@123",
                    "confirm_password": "Sunbeam@123", "nsws_reg_no": "NSWS-1"})
    assert r.status_code == 200 and "under process" in r.json()["message"]
    assert client.get("/api/v1/auth/username-available", params={"username": "sunbeam_ops"}).json()["available"] is False
    h = auth("nr_coord")
    req = next(x for x in client.get("/api/v1/registration/account-requests", headers=h).json() if x["username"] == "sunbeam_ops")
    assert client.post(f"/api/v1/registration/account-requests/{req['id']}/decide", headers=h, json={"approve": True, "extra_user_types": ["OUTAGE"]}).status_code == 200


def test_fnc_registration_consents_and_letter(client, auth):
    dev, coord = auth("re_dev"), auth("nr_coord")
    a = client.post("/api/v1/registration/applications", headers=dev, json={"category": "RE_GEN_STATION", "sub_category": "SOLAR", "form_data": {"capacity": 300}}).json()
    aid = a["application_id"]
    assert client.post(f"/api/v1/registration/applications/{aid}/submit", headers=dev).status_code == 422
    for cat in ("SHEET1_FORM", "UNDERTAKING", "SLD"):
        up(client, dev, f"/api/v1/registration/applications/{aid}/documents", cat)
    client.post(f"/api/v1/registration/applications/{aid}/submit", headers=dev)
    full = client.get(f"/api/v1/registration/applications/{aid}", headers=coord).json()
    assert {c["department"] for c in full["consents"]} == {"SO-1", "SO-2", "MO", "SCADA", "MIS"}
    users = {"SO-1": "nr_so1", "SCADA": "nr_scada", "MO": "nr_mo"}
    # SO-1 returns with remarks -> applicant re-uploads -> resubmits
    so1 = next(c for c in full["consents"] if c["department"] == "SO-1")
    assert client.post(f"/api/v1/registration/applications/{aid}/consents/{so1['id']}", headers=auth("nr_scada"), json={"decision": "ACCEPTED"}).status_code == 403
    client.post(f"/api/v1/registration/applications/{aid}/consents/{so1['id']}", headers=auth("nr_so1"), json={"decision": "RETURNED", "remarks": "SLD unsigned"})
    assert client.get(f"/api/v1/registration/applications/{aid}", headers=dev).json()["status"] == "RETURNED"
    up(client, dev, f"/api/v1/registration/applications/{aid}/documents", "SLD", extra={"change_note": "signed SLD"})
    client.post(f"/api/v1/registration/applications/{aid}/submit", headers=dev)
    full = client.get(f"/api/v1/registration/applications/{aid}", headers=coord).json()
    admin = auth("superadmin")
    for c in full["consents"]:
        if c["status"] == "PENDING":
            h = auth(users[c["department"]]) if c["department"] in users else admin
            r = client.post(f"/api/v1/registration/applications/{aid}/consents/{c['id']}", headers=h, json={"decision": "ACCEPTED"})
            assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/registration/applications/{aid}/issue-letter", headers=coord)
    assert r.status_code == 200, r.text
    docs = client.get(f"/api/v1/registration/applications/{aid}", headers=dev).json()["documents"]
    assert any(d["doc_category"] == "LETTER_REGISTRATION" for d in docs)
    sld = [d for d in docs if d["doc_category"] == "SLD"]
    assert {d["version_no"] for d in sld} == {1, 2}  # old revision retained


def _consent_all(client, auth, fid, stage_users):
    """Act on every open consent step in order until none is pending."""
    for _ in range(20):
        case = client.get(f"/api/v1/ftc/cases/{fid}", headers=auth("superadmin")).json()
        open_rows = [c for c in case["consents"] if c["status"] == "PENDING" and c["can_act"]]
        if not open_rows:
            return case
        for c in open_rows:
            who = stage_users.get((c["department"], c["level"]), "superadmin")
            r = client.post(f"/api/v1/ftc/cases/{fid}/consents/{c['id']}", headers=auth(who), json={"decision": "ACCEPTED", "remarks": "ok"})
            assert r.status_code == 200, (c, r.text)
    raise AssertionError("consents did not finish")


STAGE_USERS = {("SCADA", "GENERAL"): "nr_scada", ("PROTECTION", "GENERAL"): "nr_protdept", ("METERING", "GENERAL"): "nr_metering",
               ("SCADA", "HOD"): "nr_hod_scada", ("PROTECTION", "HOD"): "nr_hod_prot", ("METERING", "HOD"): "nr_hod_metering",
               ("SUB_HEAD_SO", "GENERAL"): "nr_subhead_so", ("HEAD_SO", "GENERAL"): "nr_head_so", ("HEAD_RLDC", "GENERAL"): "nr_head"}


def test_ftc_stage_1_to_5_creates_elements_enabled_for_realtime(client, auth):
    dev, coord = auth("re_dev"), auth("nr_coord")
    charge = date.today() + timedelta(days=30)
    # too-late submission is rejected (10-day rule)
    late = client.post("/api/v1/ftc/cases", headers=dev, json={"element_category": "RE_PLANT", "proposed_charging_date": str(date.today() + timedelta(days=3))}).json()
    client.put(f"/api/v1/ftc/cases/{late['ftc_id']}/annexure/A2", headers=dev, json={"elements": [{"name": "x", "element_type": "AC_LINE", "voltage_kv": 220}]})
    for a in ("A1", "A3", "A4", "A5", "A6"):
        up(client, dev, f"/api/v1/ftc/cases/{late['ftc_id']}/documents", a)
    r = client.post(f"/api/v1/ftc/cases/{late['ftc_id']}/submit", headers=dev)
    assert r.status_code == 422 and "10 days" in r.json()["detail"]

    c = client.post("/api/v1/ftc/cases", headers=dev, json={"element_category": "RE_PLANT", "proposed_charging_date": str(charge), "title": "Thar Surya Phase-2 100 MW"}).json()
    fid = c["ftc_id"]
    a2 = [{"name": "Thar Surya Ph-2 ICR Block-1 25 MW", "element_type": "SOLAR_ICR_BLOCK", "voltage_kv": 33, "rating": "25 MW"},
          {"name": "220 kV Thar Surya Ph-2 - Bikaner (PG) S/C", "element_type": "AC_LINE", "voltage_kv": 220, "rating": "150 MW", "length_km": 20}]
    client.put(f"/api/v1/ftc/cases/{fid}/annexure/A2", headers=dev, json={"elements": a2})
    els = client.post(f"/api/v1/ftc/cases/{fid}/a2/duplicate", headers=dev, json={"index": 0, "count": 3}).json()["elements"]
    assert len(els) == 5
    assert client.post(f"/api/v1/ftc/cases/{fid}/generate/A2", headers=dev).status_code == 200
    for a in ("A1", "A3", "A4", "A5", "A6"):
        up(client, dev, f"/api/v1/ftc/cases/{fid}/documents", a)
    assert client.post(f"/api/v1/ftc/cases/{fid}/submit", headers=dev).status_code == 200
    assert client.put(f"/api/v1/ftc/cases/{fid}/annexure/A1", headers=dev, json={"x": 1}).status_code == 409  # locked

    # coordinator must tick checklist (or mark pending with comment)
    bad = client.post(f"/api/v1/ftc/cases/{fid}/coordinator", headers=coord, json={"action": "FORWARD", "checklist": {}})
    assert bad.status_code == 422
    chk = {f"c{i}": {"state": "TICKED"} for i in range(1, 8)}
    chk["c7"] = {"state": "PENDING"}
    assert client.post(f"/api/v1/ftc/cases/{fid}/coordinator", headers=coord, json={"action": "FORWARD", "checklist": chk}).status_code == 422
    chk["c7"] = {"state": "PENDING", "comment": "Date confirmed on phone"}
    assert client.post(f"/api/v1/ftc/cases/{fid}/coordinator", headers=coord, json={"action": "FORWARD", "checklist": chk}).status_code == 200
    assert client.post(f"/api/v1/ftc/cases/{fid}/coordinator", headers=coord, json={"action": "ACCEPT"}).status_code == 409
    # applicant cannot see departmental observations
    assert client.get(f"/api/v1/ftc/cases/{fid}", headers=dev).json()["consents"] == []
    _consent_all(client, auth, fid, STAGE_USERS)
    r = client.post(f"/api/v1/ftc/cases/{fid}/coordinator", headers=coord, json={"action": "ACCEPT"}).json()
    assert r["stage"] == 2 and len(r["created_elements"]) == 5
    ids = [e["unique_element_id"] for e in r["created_elements"]]
    assert ids[0].startswith("NR-33SB-") and any(i.startswith("NR-220TL-") for i in ids)
    assert not any(e["realtime_enabled"] for e in r["created_elements"])

    # Stage 2: Format TR >= 7 working days, B-annexures, consents (general + HoD), Format IV
    assert client.post(f"/api/v1/ftc/cases/{fid}/format-tr", headers=dev, json={"trial_run_date": str(date.today() + timedelta(days=3)), "quantum_mw": 100}).status_code == 422
    assert client.post(f"/api/v1/ftc/cases/{fid}/format-tr", headers=dev, json={"trial_run_date": str(charge), "quantum_mw": 100}).status_code == 200
    client.post(f"/api/v1/ftc/cases/{fid}/format-tr", headers=dev, json={"trial_run_date": str(charge + timedelta(days=1)), "quantum_mw": 100})
    for a in ("B1", "B2", "B3", "B4", "B5", "B5A", "ELEC_INSPECTOR", "PTCC"):
        up(client, dev, f"/api/v1/ftc/cases/{fid}/documents", a)
    assert client.post(f"/api/v1/ftc/cases/{fid}/submit", headers=dev).status_code == 200
    chkb = {f"c{i}": {"state": "TICKED"} for i in range(1, 6)}
    client.post(f"/api/v1/ftc/cases/{fid}/coordinator", headers=coord, json={"action": "FORWARD", "checklist": chkb})
    _consent_all(client, auth, fid, STAGE_USERS)
    r = client.post(f"/api/v1/ftc/cases/{fid}/coordinator", headers=coord, json={"action": "ACCEPT"}).json()
    assert r["stage"] == 3 and r["realtime_access_granted"]
    assert all(e["realtime_enabled"] for e in r["created_elements"])
    master = client.get("/api/v1/master/elements", headers=auth("nr_operator"), params={"q": "Thar Surya Ph-2"}).json()
    assert len(master) == 5 and all(m["status"] == "PRE_COMMISSIONING" for m in master)

    # Stage 3: C-annexures -> parallel depts -> HoDs -> Sub-Head SO -> Head SO -> Head RLDC
    for a in ("C1", "C2", "C3", "C4", "DECLARATION", "CORROBORATION"):
        up(client, dev, f"/api/v1/ftc/cases/{fid}/documents", a)
    client.post(f"/api/v1/ftc/cases/{fid}/submit", headers=dev)
    client.post(f"/api/v1/ftc/cases/{fid}/coordinator", headers=coord, json={"action": "FORWARD", "checklist": {f"c{i}": {"state": "TICKED"} for i in range(1, 5)}})
    case = client.get(f"/api/v1/ftc/cases/{fid}", headers=coord).json()
    assert max(c["group"] for c in case["consents"]) == 5
    head_row = next(c for c in case["consents"] if c["department"] == "HEAD_RLDC")
    assert client.post(f"/api/v1/ftc/cases/{fid}/consents/{head_row['id']}", headers=auth("nr_head"), json={"decision": "ACCEPTED"}).status_code == 409
    _consent_all(client, auth, fid, STAGE_USERS)
    r = client.post(f"/api/v1/ftc/cases/{fid}/coordinator", headers=coord, json={"action": "ACCEPT"}).json()
    assert r["stage"] == 4

    # Stage 4: pre-certificate -> chain -> auto certificate hidden -> Head of RLDC signs -> visible
    client.put(f"/api/v1/ftc/cases/{fid}/pre-certificate", headers=coord, json={"Trial run period": "72 hours", "Result": "Successful"})
    client.post(f"/api/v1/ftc/cases/{fid}/coordinator", headers=coord, json={"action": "FORWARD"})
    _consent_all(client, auth, fid, STAGE_USERS)
    r = client.post(f"/api/v1/ftc/cases/{fid}/coordinator", headers=coord, json={"action": "ACCEPT"}).json()
    assert r["stage_status"] == "AWAITING_SIGNATURE"
    assert not any(d["doc_category"] == "TRIAL_CERTIFICATE" for d in client.get(f"/api/v1/ftc/cases/{fid}", headers=dev).json()["documents"])
    assert client.post(f"/api/v1/ftc/cases/{fid}/sign-certificate", headers=coord).status_code == 403
    r = client.post(f"/api/v1/ftc/cases/{fid}/sign-certificate", headers=auth("nr_head")).json()
    assert r["stage"] == 5 and r["trial_cert_signed"]
    assert any(d["doc_category"] == "TRIAL_CERTIFICATE" for d in client.get(f"/api/v1/ftc/cases/{fid}", headers=dev).json()["documents"])

    # Stage 5: DOCO -> accepted -> compliance tracker
    up(client, dev, f"/api/v1/ftc/cases/{fid}/documents", "DOCO")
    r = client.post(f"/api/v1/ftc/cases/{fid}/doco/decide", headers=coord, data={"approve": "true"}).json()
    assert r["status"] == "CLOSED" and len(r["compliances"]) == 4
    assert client.get("/api/v1/ftc/compliance", headers=dev).json()
    rep = client.get("/api/v1/ftc/reports/comments", headers=coord).json()
    assert len(rep["rows"]) > 20
    assert client.get("/api/v1/ftc/reports/cod", headers=coord, params={"fmt": "xlsx"}).status_code == 200


def test_ftc_jurisdiction_routing():
    from app.modules.ftc.router import jurisdiction

    assert jurisdiction([{"voltage_kv": 400, "element_type": "AC_LINE"}]) == ("RLDC", "RLDC")
    assert jurisdiction([{"voltage_kv": 765, "element_type": "AC_LINE"}])[0] == "NLDC"
    assert jurisdiction([{"voltage_kv": 400, "element_type": "AC_LINE", "is_inter_regional": True}]) == ("NLDC", "NLDC")
    assert jurisdiction([{"voltage_kv": 500, "element_type": "HVDC_POLE"}])[0] == "NLDC"


def test_comm_cert_two_stages(client, auth):
    tp, coord = auth("tpcomm_user"), auth("nr_coord")
    els = client.get("/api/v1/master/comm-elements", headers=tp).json()
    el = els[0]
    assert client.post("/api/v1/comm-cert/cases", headers=tp, json={"comm_element_id": el["id"], "scope": "INTRA_REGIONAL",
                       "anticipated_sat_date": str(date.today() + timedelta(days=2))}).status_code == 422
    c = client.post("/api/v1/comm-cert/cases", headers=tp, json={"comm_element_id": el["id"], "scope": "INTRA_REGIONAL",
                    "anticipated_sat_date": str(date.today() + timedelta(days=10))}).json()
    aid = c["app_id"]
    for a in ("CA1", "CA2", "CA3", "CA4", "CA5"):
        up(client, tp, f"/api/v1/comm-cert/cases/{aid}/documents", a)
    client.post(f"/api/v1/comm-cert/cases/{aid}/submit", headers=tp)
    # third-party consent (POWERGRID at other end) before acknowledgement
    pg_entity = next(e for e in client.get("/api/v1/master/entities", headers=coord).json() if e["short_name"] == "POWERGRID")
    client.post(f"/api/v1/comm-cert/cases/{aid}/third-party", headers=coord, json={"entity_ids": [pg_entity["id"]]})
    assert client.post(f"/api/v1/comm-cert/cases/{aid}/coordinator", headers=coord, json={"action": "ACKNOWLEDGE"}).status_code == 409
    r = client.post(f"/api/v1/comm-cert/cases/{aid}/third-party/respond", headers=auth("pg_user"), data={"approve": "true"})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/comm-cert/cases/{aid}/coordinator", headers=coord, json={"action": "ACKNOWLEDGE"})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/comm-cert/cases/{aid}/coordinator", headers=coord, json={"action": "FORWARD", "route": "A", "other_centre": "WRLDC"})
    assert r.status_code == 200, r.text
    seq = [("nr_scada"), ("nr_hod_scada"), ("wr_scada"), ("wr_hod_scada")]
    for who in seq:
        case = client.get(f"/api/v1/comm-cert/cases/{aid}", headers=auth(who)).json()
        row = next((x for x in case["consents"] if x["can_act"]), None)
        assert row, (who, case["consents"], case.get("detail"))
        assert client.post(f"/api/v1/comm-cert/cases/{aid}/consents/{row['id']}", headers=auth(who), json={"decision": "ACCEPTED"}).status_code == 200
    client.post(f"/api/v1/comm-cert/cases/{aid}/coordinator", headers=coord, json={"action": "ACCEPT"})
    assert client.post(f"/api/v1/comm-cert/cases/{aid}/sign", headers=auth("nr_head")).status_code == 403
    r = client.post(f"/api/v1/comm-cert/cases/{aid}/sign", headers=auth("nr_hod_scada")).json()
    assert r["stage"] == 2
    for a in ("CB1", "CB2", "CB3", "CB4", "SAT_REPORT"):
        up(client, tp, f"/api/v1/comm-cert/cases/{aid}/documents", a)
    client.post(f"/api/v1/comm-cert/cases/{aid}/submit", headers=tp, data={"sat_completed_date": str(date.today())})
    client.post(f"/api/v1/comm-cert/cases/{aid}/coordinator", headers=coord, json={"action": "FORWARD", "route": "C"})
    for who in ("nr_scada", "nr_hod_scada", "nr_head"):
        case = client.get(f"/api/v1/comm-cert/cases/{aid}", headers=auth(who)).json()
        row = next(x for x in case["consents"] if x["can_act"])
        client.post(f"/api/v1/comm-cert/cases/{aid}/consents/{row['id']}", headers=auth(who), json={"decision": "ACCEPTED"})
    client.post(f"/api/v1/comm-cert/cases/{aid}/coordinator", headers=coord, json={"action": "ACCEPT"})
    r = client.post(f"/api/v1/comm-cert/cases/{aid}/sign", headers=auth("nr_head")).json()
    assert r["status"] == "CLOSED" and r["element_status"] == "IN_SERVICE" and r["ctuil_sync_status"] == "SYNCED"


def test_element_notes_append_only_and_substation_buses(client, auth):
    op = auth("nr_operator")
    el = client.get("/api/v1/master/elements", headers=op, params={"q": "Bikaner-Bhadla"}).json()[0]
    client.post(f"/api/v1/master/elements/{el['id']}/notes", headers=op, json={"text": "Avoid charging from Bhadla end during high RE"})
    client.put(f"/api/v1/master/elements/{el['id']}/comments", headers=op, json={"text": "first"})
    r = client.put(f"/api/v1/master/elements/{el['id']}/comments", headers=op, json={"text": "second"}).json()
    assert r["comments"] == "second"
    assert len(client.get(f"/api/v1/master/elements/{el['id']}", headers=op).json()["notes"]) == 1
    s = client.post("/api/v1/master/substations", headers=auth("superadmin"), json={"code": "NR-NEWSS", "name": "New S/S", "centre_code": "NRLDC",
                    "voltage_levels": [400, 220], "bus_scheme": "Double main"}).json()
    assert s["buses_created"] == 4
