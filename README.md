# Pan-Grid-India OMS – Proof of Concept

POC for GeM bid **GEM/2026/B/8083674** (Grid Controller of India Ltd). It covers the 11 modules in the TS
(`../scope-of-work-1791363725.pdf`) and follows the build plan in `Docs/pan_grid_india_oms_development_plan.md`.
Requirements traceability is in `../OMS_GridIndia_FRD.md`: 432 requirements, each mapped to its SOW clause, page and POC milestone.

## Stack
- **Backend:** Python 3.13, FastAPI, SQLAlchemy 2 ORM + Alembic, SQLite (WAL, FK on), Strawberry GraphQL (`/graphql`), WebSockets (`/ws/{channel}`), ReportLab/openpyxl for bilingual exports.
- **Frontend:** React 18 + TypeScript + Vite + Tailwind CSS, TanStack Table, React Flow, Recharts, i18next (English/हिन्दी), vite-plugin-pwa.
- **Deliberate deviations from the TS** (see FRD §17.2): FastAPI instead of a Cl. 2.8 framework, SQLite instead of an enterprise database, a modular monolith instead of microservices, and mock adapters for NSWS, SCADA, weather, CTUIL, SMS and e-mail.

## Quick start (one command)
```powershell
powershell -ExecutionPolicy Bypass -File .\start-oms.ps1            # sets up on first run, starts API + web, opens browser
powershell -ExecutionPolicy Bypass -File .\start-oms.ps1 -Reset -Demo   # fresh database with demo activity
powershell -ExecutionPolicy Bypass -File .\stop-oms.ps1             # stop both servers
```
On first run the script creates the Python virtual environment, installs the npm packages and seeds the database. Each server runs in its own window, so you can watch its log.

## Run (manual)
```powershell
cd backend
py -3.13 -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.db.seed --reset      # 6 centres, 35 roles, 50 users, master data, 300 graphs
.\.venv\Scripts\python.exe -m scripts.demo_data        # optional: replays the acceptance scenarios as demo activity
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```
```powershell
cd frontend
npm install
npx vite            # http://localhost:5173 (proxies /api, /graphql, /ws to :8000)
```
All demo users have the password `Grid@2026`. The 2FA OTP is shown on screen (`OMS_DEV_EXPOSE_OTP=true`).

| User | Role |
|---|---|
| superadmin | Super Admin |
| nr_coord | NRLDC Registration/FTC/Comm coordinator |
| nr_shiftic / nr_operator | Shift in-charge / grid operator |
| nr_outage | Outage & availability coordinator |
| nr_protection, nr_alerts | Protection, Alerts & SPS coordinators |
| nr_scada, nr_metering, nr_protdept, nr_hod_* , nr_subhead_so, nr_head_so, nr_head | Department, HoD and head chain |
| nldc_coord, nldc_head, director_so | NLDC |
| ctu_user, nrpc_user | CTUIL, RPC |
| re_dev, pg_user, ntpc_user, rvpn_user, tpcomm_user | External stakeholders |

## Tests
```powershell
cd backend;  .\.venv\Scripts\python.exe -m pytest -q        # 46 tests: M1-M5 acceptance flows
cd frontend; npx vitest run; npx tsc -b; npx vite build      # 6 component tests, typecheck, PWA build
```

## Milestones delivered
| Milestone | What is demonstrated |
|---|---|
| M1 | Dual login, CAPTCHA, OTP 2FA, 5-attempt lockout, password policy, multi-session control and force-logout, 3-monthly contact review, idle timeout, audit trail, RBAC module launcher with greyed-out modules, English/Hindi |
| M2 | Public portal (notices, flashers, banner, tiles, FAQ, feedback, external-link warning), verify-and-publish CMS, menus; Complaint Addressal System with 4 channels, priority vs severity, Levels 0–3 auto-escalation, re-open, feedback, tracker, 14 dashboards, 14 reports, quarterly SLA/AMC penalty sheet |
| M3 | Master registry (22 element types, Unique Element IDs, append-only notes, section ownership); Registration (NSWS→CTUIL/RLDC joint comments→CONN-4, NLDC workload shifting with auto-return, F&C Excel import with preview, sign-up approval, consents, registration letter); FTC Stages 1–5 (A2 duplicate helper, 10-day rule, Format TR ≥7 working days, parallel then sequential consents, Format II/IV, real-time access grant, signed certificate, DOCO, compliance tracker, start-up power); Communication certification (CA/CB, third-party consent, route A/B/C, signed certificates) |
| M4 | Control room: Morning→Evening→Night shift lifecycle with auto-logout; consent engine; codebook (planned/forced/emergency/tripped/FTC/anti-theft/AR/suo-moto 23 cases/HV/LV/RE single window); 1-hour validity and auto-revoke; both-end execution times; execution and revival gates; shift report Draft→Final. Outage coordination: OCC M+2 window, RPC, D-3/D-2, NLDC routing, D-1 with study file and weather. Availability: monthly sheet tabs, Accept/Object, protection review, verify, RPC, bifurcation. Protection: GD/GI events, End-1/End-2 FIR/DR/EL/TR, PSC, SOPR. Alerts: 16 violation templates, contact flags, flash report. SPS status and timeline. |
| M5 | MIS: template engine with no hard-coding, ad-hoc builder, 300 graphs (30 per module), NPMC daily, generation outage & ENS, FTC/comm MIS, scheduled e-mail, bilingual PDF/XLSX/CSV with Hindi before English, Power BI/Tableau SQL views. GraphQL nested queries, mutations, subscriptions, DataLoader. Security headers, rate limiting, upload sandbox and magic-byte checks, latency check, CycloneDX SBOM (`sbom/oms-poc.cdx.json`, via `python -m app.utils.sbom`) |

## Known POC limitations
- Hindi PDFs use the Windows Nirmala font through ReportLab, which does no Devanagari shaping, so some conjuncts render approximately. Production would use HarfBuzz.
- Authentication uses bearer tokens in an Authorization header (no cookies), so CSRF tokens are not needed in this POC. A cookie-based deployment would add them.
- The background scheduler runs in-process: escalation, code timers, weather feed, monthly sheet and SOPR reminder.
