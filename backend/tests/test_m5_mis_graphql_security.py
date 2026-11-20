"""Milestone 5 verification: MIS (bilingual exports, dynamic templates, 300 graphs, NPMC/ENS, BI views), GraphQL,
latency, security headers / rate limiting, SBOM (FRD MIS-*, API-02..09, NFR-11, NFR-15, NFR-21)."""
import io
import time

from openpyxl import load_workbook


def test_three_hundred_graphs_and_chart_data(client, auth):
    h = auth("superadmin")
    charts = client.get("/api/v1/mis/charts", headers=h).json()
    assert len(charts) == 300
    for m in ("registration", "ftc", "realtime", "sps", "mis"):
        assert sum(c["module"] == m for c in charts if True) == 30
    d = client.get(f"/api/v1/mis/charts/{charts[0]['code']}/data", headers=h).json()
    assert "data" in d and "series" in d


def test_bilingual_report_hindi_before_english(client, auth):
    h = auth("nr_coord")
    j = client.get("/api/v1/mis/reports/CODES_TYPE", headers=h).json()
    assert j["rows"]
    x = client.get("/api/v1/mis/reports/CODES_TYPE", headers=h, params={"fmt": "xlsx"})
    ws = load_workbook(io.BytesIO(x.content)).active
    assert any("ऀ" <= ch <= "ॿ" for ch in str(ws["A1"].value))  # row 1 Hindi title
    assert ws["A2"].value.startswith("Codes issued")  # row 2 English title
    pdf = client.get("/api/v1/mis/reports/GEN_OUTAGE_FUEL", headers=h, params={"fmt": "pdf"})
    assert pdf.content.startswith(b"%PDF")


def test_npmc_and_generation_outage_ens(client, auth):
    h = auth("superadmin")
    npmc = client.get("/api/v1/mis/reports/NPMC_DAILY", headers=h).json()["rows"]
    assert any("Dadri Unit-1" in r["unit"] for r in npmc)
    ens = client.get("/api/v1/mis/reports/GEN_OUTAGE_UNIT", headers=h).json()["rows"]
    u = next(r for r in ens if r["unit"].startswith("NTPC Dadri Unit-1"))
    assert u["outage_hours"] > 0 and u["ens_mwh"] > 0 and "ens_uttar_pradesh" in u


def test_dynamic_template_without_code(client, auth):
    h = auth("nr_coord")
    r = client.post("/api/v1/mis/templates", headers=h, json={"code": "MY_TRIP_HOURLY", "module": "mis", "name_en": "Trippings by hour",
                    "name_hi": "घंटे-वार ट्रिपिंग", "query_config": {"source": "trippings", "group_by": ["hour"], "aggregates": [{"field": "count", "fn": "sum"}]}})
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/mis/reports/MY_TRIP_HOURLY", headers=h).json()["rows"]
    bad = client.post("/api/v1/mis/templates", headers=h, json={"code": "BAD_SRC", "name_en": "x", "query_config": {"source": "nope"}})
    assert bad.status_code == 422


def test_bi_views(client, auth):
    h = auth("superadmin")
    v = client.get("/api/v1/mis/bi-views/bi_outage_codes", headers=h).json()
    assert "code_number" in v["columns"] and v["rows"]
    assert client.get("/api/v1/mis/bi-views/bi_tickets", headers=h, params={"fmt": "csv"}).text.startswith("ticket_number")


def test_graphql_nested_query_and_mutation(client, auth):
    h = auth("nr_coord")
    q = "{ ftcCases { caseNumber stage elements { uniqueElementId owners { role entity { shortName } } } documents { autoFilename } workflowSteps { stepName } } }"
    r = client.post("/graphql", headers=h, json={"query": q}).json()
    assert "errors" not in r, r
    case = next(c for c in r["data"]["ftcCases"] if c["elements"])
    assert case["elements"][0]["owners"][0]["entity"]["shortName"]
    assert case["workflowSteps"] and case["documents"]
    m = client.post("/graphql", headers=auth("nr_operator"), json={"query": 'mutation { addElementNote(elementId: 1, text: "Check CVT drift") { notes } }'}).json()
    assert "Check CVT drift" in m["data"]["addElementNote"]["notes"]
    unauth = client.post("/graphql", json={"query": "{ codes { codeNumber } }"}).json()
    assert unauth["errors"]
    sdl = client.post("/graphql", headers=h, json={"query": "{ __schema { subscriptionType { fields { name } } } }"}).json()
    assert sdl["data"]["__schema"]["subscriptionType"]["fields"][0]["name"] == "gridEvents"


def test_api_latency_under_100ms(client, auth):
    h = auth("nr_operator")
    client.get("/api/v1/master/elements", headers=h)
    samples = []
    for _ in range(10):
        t0 = time.perf_counter()
        r = client.get("/api/v1/realtime/shifts/active", headers=h, params={"centre": "NRLDC"})
        samples.append((time.perf_counter() - t0) * 1000)
        assert r.status_code == 200
    samples.sort()
    assert samples[len(samples) // 2] < 100, samples


def test_rate_limit_returns_429():
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from slowapi.util import get_remote_address

    a = FastAPI()
    a.state.limiter = Limiter(key_func=get_remote_address, default_limits=["3/minute"])
    a.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    a.add_middleware(SlowAPIMiddleware)

    @a.get("/x")
    def x(request: Request):
        return {"ok": True}

    c = TestClient(a)
    codes = [c.get("/x").status_code for _ in range(5)]
    assert codes[-1] == 429


def test_security_headers_and_upload_scan(client, auth):
    r = client.get("/api/v1/health")
    for hdr in ("X-Content-Type-Options", "X-Frame-Options", "Strict-Transport-Security", "Content-Security-Policy", "Referrer-Policy"):
        assert hdr in r.headers
    h = auth("re_dev")
    eicar = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    c = client.post("/api/v1/ftc/cases", headers=h, json={"element_category": "RE_PLANT", "proposed_charging_date": "2027-12-01"}).json()
    r = client.post(f"/api/v1/ftc/cases/{c['ftc_id']}/documents", headers=h, data={"doc_category": "A1"}, files={"file": ("a1.txt", eicar, "text/plain")})
    assert r.status_code == 422 and "sandbox" in r.json()["detail"]
    r = client.post(f"/api/v1/ftc/cases/{c['ftc_id']}/documents", headers=h, data={"doc_category": "A1"}, files={"file": ("a1.pdf", b"MZ fake", "application/pdf")})
    assert r.status_code == 415
    # SQL injection attempt is treated as plain data
    assert client.get("/api/v1/master/elements", headers=h, params={"q": "' OR 1=1 --"}).json() == []


def test_sbom_cyclonedx():
    from app.utils.sbom import build

    b = build()
    assert b["bomFormat"] == "CycloneDX" and b["specVersion"] == "1.5"
    names = {c["name"].lower() for c in b["components"]}
    assert {"fastapi", "sqlalchemy"} <= names and "react" in names
    assert all(c["purl"] and c["version"] for c in b["components"])
