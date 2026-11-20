# Pan-GRID-INDIA Operations Management System (OMS) — Development Plan

> **Reference:** GeM Bid No. `GEM/2026/B/8083674` | Buyer: Grid Controller of India Limited (GRID-INDIA)  
> **Target Audience:** Engineering Team / AI Coding Agent (Claude Code)  
> **Build Sequence:** Module Design → SQLite Database → React + Tailwind CSS UI → Python FastAPI Backend

---

## 0. Executive Summary & Tech Stack Notes

This plan specifies the end-to-end architecture and implementation roadmap for the **Pan-GRID-INDIA Operations Management System (OMS)** spanning **6 Load Despatch Centres**:
- **NLDC** (National Load Despatch Centre, New Delhi) — *View access across all RLDC modules*
- **NRLDC** (Northern, New Delhi)
- **ERLDC** (Eastern, Kolkata)
- **WRLDC** (Western, Mumbai)
- **SRLDC** (Southern, Bengaluru)
- **NERLDC** (North Eastern, Shillong/Guwahati)

### Selected Development Stack (PoC / Local-First Build)
- **Database:** SQLite 3 (`WAL` mode, `PRAGMA foreign_keys = ON`) via **SQLAlchemy 2.0 (async)** + **Alembic**
- **Frontend:** **React 18+ (TypeScript, Vite)** + **Tailwind CSS** + `vite-plugin-pwa`
- **Backend:** **Python 3.11+ FastAPI** + **Pydantic v2** + **Strawberry GraphQL** (`/graphql`) + **WebSockets**

### Production Migration Readiness Note (RFP Compliance)
While SQLite and FastAPI are used for rapid local development and PoC execution:
1. Keep all database access strictly through **SQLAlchemy ORM + Alembic migrations** (avoid raw SQLite-only SQL) so the database can be switched cleanly to **PostgreSQL Enterprise** (RFP Cl. 2.9 requires Enterprise-licensed DB, ~6.64 TB combined sizing).
2. Expose a **Strawberry GraphQL** API (`/graphql`) alongside REST (`/api/v1`) to align with RFP Cl. 2.6.
3. Structure backend modules cleanly as isolated domain packages so they can be split into independent microservices per RFP Cl. 2.8.

---

## 1. Monorepo Project Structure

Scaffold the repository using the following layout:

```text
pan-grid-india-oms/
├── README.md
├── backend/
│   ├── pyproject.toml / requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── oms_dev.db                    # SQLite database file (gitignored)
│   └── app/
│       ├── main.py                   # FastAPI entrypoint, middleware, CORS, /graphql, WebSockets
│       ├── core/
│       │   ├── config.py             # Env settings, refresh intervals, lockout thresholds
│       │   ├── security.py           # JWT, password policy, 2FA OTP, CSRF, CAPTCHA, rate-limit
│       │   ├── rbac.py               # Role & centre-level permission dependencies
│       │   └── audit.py              # Automatic user activity & mutation audit logger
│       ├── db/
│       │   ├── session.py            # Async SQLite engine (aiosqlite + WAL mode)
│       │   ├── base.py               # DeclarativeBase & common mixins (timestamps, soft-delete)
│       │   └── seed.py               # Initial 6 centres, 13 roles, shift rules, sample checklists
│       ├── modules/
│       │   ├── auth_rbac/            # Users, Roles, Sessions, 2FA, Digital Signature
│       │   ├── master_registry/      # Entities, Substations, 20+ Grid Element types, Contacts
│       │   ├── workflow_engine/      # Generic state machine, dynamic checklists, Case ID tracker
│       │   ├── dms_files/            # Auto-naming, versioned uploads, sandbox hook
│       │   ├── portal_cms/           # Public portal, Notice Board, Flashers, Feedback, Bi-lingual
│       │   ├── ticketing_cas/        # Complaint Addressal (Levels 0–3, SLA, AMC penalty calc)
│       │   ├── registration/         # NSWS API sync, CTUIL/RLDC review, NLDC shifting, F&C import
│       │   ├── ftc/                  # Stages 1–5 (A/B/C Annexures), Start-up Power, Post-comm
│       │   ├── comm_cert/            # Communication Certification (CA/CB Annexures, CTUIL sync)
│       │   ├── realtime_outage/      # 24x7 Shifts, Codebook, Consent Engine, SCADA/Weather overlay
│       │   ├── outage_coord/         # OCC/RPC planned shutdown pipeline (M+2, D-3, D-2, D-1)
│       │   ├── availability_verify/  # Monthly outage review, objections, outage bifurcation
│       │   ├── protection_tripping/  # FIR/DR/EL/TR, GD/GI Events, End-1/End-2 RBAC, PSC
│       │   ├── message_alerts/       # Bulk SMS/Email, Violation templates, Flash reports
│       │   ├── sps_status/           # System Protection Scheme ON/OFF real-time status & timeline
│       │   └── mis_reporting/        # Cross-module analytics, 30 graphs/module, Bi-lingual PDF/XLSX
│       ├── graphql/
│       │   └── schema.py             # Unified Strawberry GraphQL Queries, Mutations, Subscriptions
│       ├── integrations/
│       │   ├── scada_adapter.py      # Bi-directional JSON/XML/CSV SCADA telemetry & events
│       │   ├── nsws_adapter.py       # NSWS connectivity data/file sync mock & client
│       │   ├── weather_adapter.py    # Weather portal area alert fetcher
│       │   └── notifier.py           # Configurable Email/SMS/WebPush dispatcher
│       └── utils/
│           ├── exports.py            # Bi-lingual PDF (Hindi before English), CSV, XLSX builders
│           └── sbom.py               # SPDX / CycloneDX SBOM generation helper
└── frontend/
    ├── package.json
    ├── vite.config.ts                # React + TypeScript + vite-plugin-pwa
    ├── tailwind.config.ts
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── i18n/                     # Manual English (en.json) & Hindi (hi.json) translations
        ├── api/                      # Axios REST client, GraphQL client, WebSocket hook
        ├── store/                    # Auth, Active Centre, Language, Recent-5 pages
        ├── components/
        │   ├── layout/               # Sidebar, Topbar, Centre Switcher, Breadcrumbs, Last-5
        │   ├── common/               # SpreadsheetGrid, ExportButtons, FileUploadVersioned
        │   ├── workflow/             # CaseFlowchartTracker (React Flow), ChecklistDrawer
        │   └── charts/               # AutoRefreshDashboardCard, DynamicChart (Chart.js/Recharts)
        └── pages/
            ├── public/               # Landing, Notice Board, Flashers, Dual Login, 2FA
            ├── portal/               # Module Launcher Grid (Active vs. Greyed-out cards)
            ├── ticketing/            # Complaint Portal, Escalation Tracker, 14 Dashboards
            ├── registration/         # NSWS Intake, CTUIL/RLDC Joint Review, NLDC Shifting
            ├── ftc/                  # Stages 1–5 Wizard, Element ID Creator, Start-up Power
            ├── comm_cert/            # CA/CB Annexures, Third-Party/Inter-Regional Consent
            ├── realtime_outage/      # Shift Manager, Control Room Codeboard, Consent, Analysis View
            ├── outage_coord/         # OCC/RPC Pipeline, D-3/D-2/D-1 Approvals
            ├── availability/         # Monthly Spreadsheet Review, Accept/Object, Bifurcation
            ├── protection/           # Tripping Records, FIR/DR/EL/TR, GD/GI Events, PSC
            ├── alerts/               # Bulk SMS/Email, Violation Forms, Flash Reports
            ├── sps/                  # SPS Healthiness Matrix & Timeline
            └── mis/                  # Report Builder, NPMC/Outage Stats, 30-Graph Explorer
```

---

## 2. Step 1 — Module Design & Functional Specifications

Every business module must support **6 Centre Work-Areas** (`NLDC`, `NRLDC`, `ERLDC`, `WRLDC`, `SRLDC`, `NERLDC`). NLDC users must be able to view all RLDC data in read-only mode unless explicitly authorized to act (e.g., NLDC Registration load-shifting or 765 kV / Inter-Regional FTC & Outages).

### 2.1 Core Platform Services (Cross-Cutting)
1. **User Management & RBAC (`auth_rbac`):**
   - **13+ Roles:** Super Admin, Module Admin, Coordinator, Department User (SCADA, Metering, Protection, SO-1, SO-2, MO, MIS), HoD, Head of RLDC, NLDC User, Head of NLDC, CTU, RPC, Public User, Registered External User, Internal/Intranet User.
   - **Security Flows:** Dual Login (External vs. Grid-India), CAPTCHA on Login/Forgot Password, 2FA (OTP on Email/Mobile), Password policy (≥8 chars, upper, lower, digit, special char), account lockout after 5 failed attempts, 3-month contact-details verification pop-up on login.
   - **Session Control:** Configurable multi-session toggle per user; Admin view of all active sessions with remote force-logout; configurable idle auto-logout.
   - **Digital Signature & Audit:** Attach uploaded signature image or DSC metadata on consents/certificates; immutable audit trail for every create/update/delete/approve action.
2. **Generic Workflow Engine (`workflow_engine`):**
   - Lifecycle: `Draft → Submitted → Coordinator Check → Parallel Dept Review (SCADA/Metering/Protection/NLDC) → HoD / Head Approval → Approved / Returned with Remarks → Published`.
   - Dynamic front-end configurable checklists (must tick all items or mark `Pending` with mandatory comments to escalate).
   - Visual Case ID status flowchart (Green = Completed, Red = Pending) with clickable node pop-ups showing officer, login, timestamp, and remarks.
3. **Document Management (`dms_files`):**
   - Allowed formats: `.pdf`, `.docx`, `.xlsx`, `.csv`, `.zip`, `.rar`, `.dat`, `.cfg`, `.sav`, `.dyr`, `.sld`, images.
   - Auto-renaming syntax engine (`{CENTRE}_{MODULE}_{CASE_ID}_{DOC_TYPE}_v{REV}.{ext}`).
   - Strict version history (old revisions never overwritten; visible with timestamps).
   - File scan hook (placeholder for appliance sandbox integration) and confidential-file flag (requires OTP to view/download).
4. **Bi-Lingual Support:**
   - **Hindi & English** manual translation store (no auto-translate plugins).
   - All generated reports and templates must display **Hindi text prior to English text**.

### 2.2 Business Modules (11 Modules)

| # | Module | Core Functional Scope |
| :--- | :--- | :--- |
| **0** | **Common Web Portal & CMS** | Public landing page, customizable Navbar, Header/Footer, Notice Board, moving Flashers (clickable file download), Pop-up Banners, Image Gallery, Breadcrumbs, Customer Feedback form, External links with redirection warning pop-up. |
| **1** | **Complaint Addressal System (Ticketing)** | Multi-channel intake (Portal, Email, Phone, Walk-in); auto-generated Ticket ID; separate Priority (AMC-assessed) vs. Severity 1–4 (RLDC/NLDC-assessed); **Levels 0–3** time-based auto-escalation; re-open closed tickets; FAQ/Knowledge Base builder; **14 role-based dashboards**; **14 standard reports** + automated quarterly SLA downtime & AMC penalty calculation sheet. |
| **2** | **Registration Module** | (A) **NSWS Connectivity Flow:** Fetch NSWS ref & segregated model files (block raw `.zip` dumps), iterative CTUIL + RLDC checklist validation, CTUIL joint-comment moderation, status push back to NSWS, CONN-4 certificate generation. (B) **NLDC Workload Shifting:** NLDC Coordinator shifts unstarted RE applications from overloaded RLDC to lightly loaded RLDC; auto-reverts to nodal RLDC after model validation. (C) **Fees & Charges Import:** Excel import for REGS (Solar/Wind/Hybrid/BESS/PSP), Conventional Generators, and Transmission Licensees to generate logins; direct registration for Communication entities. |
| **3** | **First Time Charging (FTC) Module** | IEGC 2023 jurisdiction routing (NLDC: 765 kV, Inter-Regional, HVDC, Trans-national; RLDC: 400 kV / 220 kV NER, ISTS/ISGS, FACTS, Regional Generators/Bulk Consumers). **5-Stage Flow:** Stage 1 (`A1–A6`, Format II; `A2` auto-generates **Unique Element IDs** in Master DB with duplicate-element helper for Solar ICR/WTG blocks); Stage 2 (`B1–B5a`, statutory/PTCC clearances, open-ended `Format-TR` trial-run notice ≥7 working days prior, Format IV, auto-grant Real-time Outage access); Stage 3 (`C1–C4`, corroboration sheet, post-trial RE docs); Stage 4 (Pre-certificate + digitally signed Trial-Run Certificate); Stage 5 (DOCO letter + post-commissioning compliance expiry dashboard). Includes **Start-up Power Grant** sub-module (weekly/monthly schedules). |
| **4** | **Communication System Certification** | Dedicated inventory for OPGW, FOTE, Auxiliary Power Supply, and State CSP links. Stage 1 (`CA1–CA5`, third-party/inter-regional consent, Format II); Stage 2 (`CB1–CB4`, SAT report, digitally signed certificate by Head of SCADA/RLDC). API/file sync adapter for CTUIL Communication Outage Planning software. |
| **5** | **Real-Time Outage Management** | 24×7 Control Room engine. **Sequential Shift Management:** `Morning → Evening → Night` (NLDC/NRLDC/ERLDC/WRLDC/SRLDC: `08:30/14:30/20:30`; NERLDC: `08:00/14:00/20:00`), strict prior-shift closure before creating next shift, auto-logout of prior shift sessions. **Master Inventory:** 20+ element types with immutable Operator Notes (append-only) & editable Comments. **Codebook & Consent Engine:** Planned (OCC/D-3/D-2/D-0), Forced, Emergency, Tripped, FTC, Anti-theft (3 tower-collapse cases), AR Off, 23 Suo-Moto cases, HV/LV batch codes, Single-Window RE MVAr/PF/Vref code, Opportunity S/D, B6/B7/B8 minor alterations. Code 1-hour validity & auto-revoke; 15-min pre-charging alert; mandatory execution-time entry gate (blocks new code requests if overdue). **Shift Reports** (Draft → Final immutable handover), SCADA/Weather alert overlay, Analysis View, Last-5 visited links. |
| **6** | **Outage Coordination System** | Multi-horizon shutdown planning: **OCC/RPC (M+2)** submitted 26th of M to 5th of M+1 → RPC review → RLDC utility-wise sheets → OCC approval; **D-3** (220 kV & below / RE) and **D-2** (Central sector bays) requests; **D-1** final approval with PSS/E study & weather check; Inter-regional routing strictly via NLDC; Non-auto mode `(Req. for AR)` tagging; feeds approved outages directly into Real-Time Outage Management. |
| **7** | **Availability Inputs Verification** | Captures Availability Head (`Self`, `Others`, `Deemed Available`, `System Constraint`, `Construction`, `Diversion`, `HVDC`, `Kite`, `Weather`, etc.) and 39 Category Codes across Stage 1–3. Auto-generates monthly review spreadsheet on **1st of N+1 month** grouped by tabs; Licensee clicks **Accept** (locks row) or **Object** (proposes modified times/head) by **5th**; Availability Coordinator publishes on **6th**, routes selected rows to Protection Dept, verifies, and forwards to **RPC Login**. Supports **Outage Bifurcation** (splitting a single outage into multiple time/category segments). |
| **8** | **Protection & Tripping Studies** | Directly uses Master OMS Database (no manual sync). Captures **FIR** (fillable, user-editable), **DR** (`.dat`, `.cfg`, `.pdf`, Main-1/Main-2 mandatory), **EL**, and **TR** from both **End-1 and End-2** substations with ownership-restricted RBAC. Groups single/multiple outages into **GD-1 to GD-5 / GI-1 to GI-2 / Near-Miss** Event Records; tracks Flash Reports (8 hrs), DR/EL (24 hrs), Detailed Reports (7 days), Monthly **SOPR (D, S, R indices)**, Relay Settings repository, and **PSC (Protection Sub-Committee)** agenda & compliance tracking. |
| **9** | **Message Alerts Module** | Real-time control room bulk SMS/Email dispatcher categorized by State, RE Pooling Station/Generator, and Miscellaneous. Editable contact directory with granular toggles (Alert / Emergency / Extreme Emergency for SMS & Email). 15+ pre-filled **Violation Message Templates** (Frequency, Deviation, Physical Regulation, HV/LV, ICT/Corridor Loading, SCADA Telemetry), Flash Report composer, and constituent-wise past-message audit view. |
| **10** | **SPS Status Module** | Captures healthiness (`ON`/`OFF`/Working status) of Special Protection Schemes under unique SPS IDs; constituent self-update + SCADA sync; real-time graphical/tabular display and Excel export. |
| **11** | **MIS & Reporting Module** | Unified cross-module reporting engine. Includes **NPMC daily Excel reports**, **Generation Outage Duration & Energy Not Served (ENS)** statistics (unit/plant/owner/fuel/location-wise), Monthly FTC & Comm Cert summaries, **30 initial graphs per module (300 total)**, non-hardcoded dynamic report template builder, scheduled email distribution, bi-lingual PDF/CSV/XLSX export, and read-only SQL views/endpoints for **Power BI & Tableau** (5 dashboards each). |

---

## 3. Step 2 — SQLite Database Design

### 3.1 SQLite Engine Configuration
Configure SQLite on every connection in `backend/app/db/session.py`:
```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
```

### 3.2 Core Relational Schema (6 Domain Groups)

#### Group A: Auth, RBAC, Centres & Audit
- `centres` (`id`, `code` UNIQUE [`NLDC`, `NRLDC`, `ERLDC`, `WRLDC`, `SRLDC`, `NERLDC`], `name_en`, `name_hi`, `shift_start_time`)
- `users` (`id`, `username` UNIQUE, `password_hash`, `full_name`, `email`, `mobile`, `user_category` [`GRID_INDIA`, `EXTERNAL`, `CTU`, `RPC`, `PUBLIC`], `centre_id`, `entity_id`, `is_active`, `is_2fa_enabled`, `failed_login_count`, `locked_until`, `last_contact_verified_at`, `signature_file_path`, `created_at`)
- `roles` (`id`, `code` UNIQUE, `name`, `module_scope`, `permissions_json`)
- `user_roles` (`user_id`, `role_id`, `centre_id`)
- `user_sessions` (`id`, `user_id`, `token_jti`, `ip_address`, `user_agent`, `is_active`, `shift_id`, `created_at`, `last_seen_at`)
- `otp_verifications` (`id`, `user_id`, `channel` [`EMAIL`, `SMS`], `otp_hash`, `purpose`, `expires_at`, `is_used`)
- `audit_logs` (`id`, `user_id`, `centre_id`, `module`, `action`, `entity_type`, `entity_id`, `old_values_json`, `new_values_json`, `ip_address`, `created_at`)

#### Group B: Master Registry & Grid Elements
- `entities` (`id`, `name`, `entity_type` [`REGS`, `CONV_GEN`, `TRANS_LICENSEE`, `COMM_PROVIDER`, `BULK_CONSUMER`, `SLDC`], `sub_category` [`SOLAR`, `WIND`, `HYBRID`, `BESS`, `PSP`, `THERMAL`, `HYDRO`, `GAS`, `NUCLEAR`], `centre_id`, `nsws_reg_no`, `cea_egen_no`, `fnc_reg_no`, `gst_no`, `pan_no`, `address`, `status`)
- `entity_ownership_history` (`id`, `entity_id`, `previous_owner`, `new_owner`, `approved_by`, `approved_at`, `remarks`)
- `entity_contacts` (`id`, `entity_id`, `name`, `designation`, `department`, `phone1`, `phone2`, `email1`, `email2`, `alert_sms_flags_json`, `alert_email_flags_json`)
- `substations` (`id`, `code` UNIQUE, `name`, `centre_id`, `state`, `voltage_levels_json`, `substation_type` [`AIS`, `GIS`, `HVDC`], `bus_scheme`, `lat`, `lng`, `owner_entity_id`)
- `grid_elements` (`id`, `unique_element_id` UNIQUE, `name`, `element_type` [20+ enum types], `centre_id`, `voltage_kv`, `from_substation_id`, `to_substation_id`, `status` [`IN_SERVICE`, `OUTAGE`, `TRIPPED`, `PRE_COMMISSIONING`, `DECOMMISSIONED`], `ftc_date`, `cod_date`, `metadata_json`, `operator_notes_append_only_json`, `operator_comments`)
- `element_owners` (`id`, `grid_element_id`, `entity_id`, `ownership_role` [`LINE_OWNER`, `END1_STATION`, `END2_STATION`, `SECTION_OWNER`], `section_km`)
- `comm_elements` (`id`, `unique_comm_id` UNIQUE, `name`, `comm_type` [`OPGW`, `FOTE`, `AUX_POWER`, `STATE_CSP`], `centre_id`, `from_station`, `to_station`, `owner_entity_id`, `status`)

#### Group C: Generic Workflow, Checklists & Versioned DMS
- `workflow_cases` (`id`, `case_number` UNIQUE, `module`, `centre_id`, `applicant_user_id`, `current_stage`, `status`, `pending_with_role`, `pending_with_user_id`, `created_at`, `updated_at`)
- `workflow_steps` (`id`, `case_id`, `step_order`, `step_name`, `actor_user_id`, `actor_role`, `action` [`SUBMIT`, `APPROVE`, `REJECT`, `RETURN`, `SHIFT`, `PUBLISH`], `remarks`, `is_internal_only`, `signature_applied`, `created_at`)
- `checklists` (`id`, `module`, `element_category`, `owner_role` [`RLDC`, `CTUIL`, `SCADA`, `METERING`, `PROTECTION`], `items_json`)
- `checklist_responses` (`id`, `case_id`, `checklist_id`, `reviewer_user_id`, `responses_json`, `submitted_at`)
- `documents` (`id`, `case_id`, `module`, `doc_category`, `original_filename`, `auto_filename`, `storage_path`, `mime_type`, `file_size_bytes`, `version_no`, `uploaded_by`, `is_confidential`, `scan_status`, `created_at`)

#### Group D: Registration, FTC & Communication Certification
- `reg_applications` (`id`, `case_id`, `application_type` [`NSWS_CONNECTIVITY`, `FNC_IMPORT`, `DIRECT_COMM`], `nsws_ref_no`, `nodal_centre_id`, `shifted_to_centre_id`, `shifted_at`, `returned_at`, `ctu_joint_comments_json`, `conn4_cert_doc_id`)
- `ftc_applications` (`id`, `case_id`, `entity_id`, `jurisdiction` [`NLDC`, `RLDC`], `element_category`, `stage` [1..5], `format_ii_doc_id`, `format_tr_date`, `format_iv_doc_id`, `realtime_charging_time`, `trial_cert_doc_id`, `doco_date`, `annexures_data_json`)
- `startup_power_requests` (`id`, `case_id`, `entity_id`, `quantum_mw`, `period_from`, `period_to`, `weekly_updates_json`, `monthly_energy_json`, `grant_status`)
- `post_comm_compliances` (`id`, `ftc_application_id`, `compliance_type` [`AS_BUILT_MODEL`, `FINAL_SLD`, `POWER_QUALITY`, `PERIODIC_TEST`, `UNDERTAKING`], `due_date`, `status`, `doc_id`)
- `comm_cert_applications` (`id`, `case_id`, `comm_element_id`, `scope` [`INTRA_REGIONAL`, `INTER_REGIONAL`, `TRANS_NATIONAL`], `stage` [1..2], `third_party_consents_json`, `ca_cb_data_json`, `cert_doc_id`)

#### Group E: Outage Coordination, Real-Time Outage, Availability & Protection
- `shifts` (`id`, `centre_id`, `shift_date`, `shift_type` [`MORNING`, `EVENING`, `NIGHT`], `shift_incharge_id`, `assigned_staff_json`, `regular_works_checklist_json`, `handover_notes`, `status` [`OPEN`, `CLOSED`], `opened_at`, `closed_at`)
- `occ_outage_plans` (`id`, `centre_id`, `occ_number`, `plan_route` [`OCC_M2`, `D3`, `D2`, `EMERGENCY`, `NON_AUTO`], `grid_element_id`, `requester_entity_id`, `req_from`, `req_to`, `approved_from`, `approved_to`, `daily_or_continuous`, `reason`, `availability_head_proposed`, `availability_head_rldc`, `category_code`, `status`, `rpc_remarks`, `rldc_comments`)
- `outage_code_requests` (`id`, `centre_id`, `shift_id`, `occ_plan_id`, `grid_element_id`, `requester_user_id`, `request_category` [`PLANNED`, `FORCED`, `EMERGENCY`, `TRIPPED`, `FTC`, `ANTI_THEFT`, `AR_OFF`, `SUO_MOTO`, `SPS_TEST`, `HOT_LINE`, `HV_CODE`, `LV_CODE`, `RE_MVAR`, `OTHER`], `suo_moto_case_no`, `status`, `remarks`, `created_at`)
- `outage_consents` (`id`, `code_request_id`, `stakeholder_entity_id`, `status` [`PENDING`, `APPROVED`, `REJECTED`], `remarks`, `responded_at`)
- `outage_codes` (`id`, `code_number` UNIQUE, `code_request_id`, `shift_id`, `issued_by_user_id`, `code_type` [`OUTAGE`, `CHARGING`, `REVIVAL`, `OPERATION`], `issued_at`, `expires_at`, `is_revoked`, `end1_exec_time`, `end2_exec_time`, `final_exec_time`, `expected_revival_time`, `scada_voltage_kv`)
- `availability_records` (`id`, `centre_id`, `billing_month`, `outage_code_id`, `grid_element_id`, `owner_entity_id`, `parent_record_id` [for bifurcation], `outage_start`, `outage_end`, `availability_head`, `category_code`, `user_action` [`PENDING`, `ACCEPTED`, `OBJECTED`], `proposed_changes_json`, `protection_remarks`, `rldc_verified_status`, `rpc_status`)
- `tripping_events` (`id`, `centre_id`, `event_code`, `event_category` [`GD-1`..`GD-5`, `GI-1`, `GI-2`, `NEAR_MISS`, `SINGLE_TRIP`], `outage_code_ids_json`, `fir_data_json`, `dr_doc_ids_json`, `el_doc_ids_json`, `tr_doc_ids_json`, `flash_report_doc_id`, `detailed_report_doc_id`, `sopr_indices_json`, `occurred_at`)
- `protection_psc_records` (`id`, `centre_id`, `tripping_event_id`, `psc_meeting_no`, `meeting_date`, `recommendations`, `utility_action_taken`, `compliance_status` [`COMPLIED`, `PARTIAL`, `NOT_COMPLIED`], `resolved_by_rldc`)

#### Group F: Ticketing, Alerts, SPS, Portal CMS & MIS
- `tickets` (`id`, `ticket_number` UNIQUE, `centre_id`, `module`, `channel`, `complainant_user_id`, `linked_ticket_id`, `priority`, `severity` [1..4], `escalation_level` [0..3], `status`, `subject`, `description`, `tags_json`, `sla_response_due`, `sla_resolution_due`, `responded_at`, `resolved_at`, `feedback_rating`)
- `ticket_history` (`id`, `ticket_id`, `actor_user_id`, `from_level`, `to_level`, `status`, `comment`, `attachment_doc_id`, `created_at`)
- `violation_messages` (`id`, `centre_id`, `category` [`STATE`, `RE_GEN`, `MISC`], `template_type`, `target_entity_id`, `payload_json`, `channels_json`, `sent_by`, `sent_at`)
- `sps_status_logs` (`id`, `sps_id`, `sps_name`, `centre_id`, `grid_element_id`, `status` [`ON`, `OFF`, `DEGRADED`], `source` [`USER`, `SCADA`], `updated_by`, `updated_at`)
- `portal_content_i18n` (`id`, `content_type` [`NOTICE`, `FLASHER`, `BANNER`, `POST`, `FAQ`, `GALLERY`], `centre_id`, `title_en`, `title_hi`, `body_en`, `body_hi`, `attachment_doc_id`, `is_published`, `created_at`)
- `report_templates` (`id`, `module`, `name_en`, `name_hi`, `query_config_json`, `columns_json`, `chart_config_json`, `schedule_cron`)

### 3.3 Mandatory Seed Data (`seed.py`)
- Seed all **6 Centres** (with NERLDC shift start `08:00`, others `08:30`).
- Seed all **13+ Roles** and a default `superadmin` + sample users per centre (Coordinator, Grid Operator, External RE Developer, CTU, RPC).
- Seed sample **Substations**, **10+ Grid Elements** (400 kV/765 kV lines, ICT, Bus Reactor, Solar Plant), **Checklist Templates** (CONN-TD-4, FTC A/B/C), and **Violation Message Templates**.

---

## 4. Step 3 — Frontend UI Plan (React + TypeScript + Tailwind CSS)

### 4.1 Core App Shell & Standards
- **PWA Setup:** Configure `vite-plugin-pwa` with manifest (GRID-INDIA icon/favicon), offline static-asset caching, and web push registration.
- **Responsive Design:** Desktop, Laptop, Tablet, and Mobile layouts using Tailwind breakpoints.
- **Navigation:**
  - Collapsible left **Sidebar** (module sub-menus with icons) + **Top-bar** (GRID-INDIA branding, active Centre selector, **English / हिन्दी** toggle, Last-5-Visited dropdown, Notification bell, User profile + Active Sessions modal).
  - **Module Launcher Home:** Grid of 11 module cards—authorized modules enabled and highlighted; unauthorized modules greyed-out/disabled.
  - **Breadcrumbs** on every inner view.
- **Dynamic Auto-Refresh:** Custom `useAutoRefresh(intervalMs)` hook reading Admin-configured refresh rate (default `2000ms`), displaying a live `"Last Updated: DD-MM-YYYY HH:mm:ss"` pill.

### 4.2 Reusable Power-Sector UI Components
1. **`SpreadsheetDataGrid` (TanStack Table + SheetJS):**
   - Inline editing with input masks & standard dropdowns.
   - Direct **Copy-Paste from Excel** into table cells + **Bulk Upload Preview Modal** before committing to API.
   - Single-click top-left toolbar buttons: **PDF**, **CSV**, **Excel**, **Copy**.
   - Multi-column sorting, voltage-level tabs (`765 kV`, `400 kV`, `220 kV`, `HVDC`), and status color-coding.
2. **`CaseFlowchartTracker` (React Flow):**
   - Renders step-by-step workflow nodes for any Case ID / Ticket ID.
   - Green = Completed, Red = Pending, Amber = Returned.
   - Clicking any node opens a detail popover (`Pending Officer`, `Login ID`, `Pending Since`, `Remarks`, `Forwarded By/To`).
3. **`DocumentVersionDrawer` & `ChecklistPanel`:**
   - Displays all revisions with auto-generated filenames and timestamps.
   - Side-by-side dynamic checklist with `Accept / Reject / Return with Remarks` actions (blocks approval if mandatory checklist items are unticked unless marked `Pending` with remarks).
4. **`ControlRoomShiftBar`:**
   - Sticky banner in Real-Time Outage Management showing active shift (`Morning/Evening/Night`), Shift In-charge, countdown to handover, Weather Alerts ticker, and quick-action buttons (`Request Code`, `Issue Code`, `Report Tripping`, `Shift Handover`).
5. **`DynamicChartCard` (Chart.js / Recharts):**
   - Supports Line, Bar, Pie, and Stacked charts with hover tooltips, date/centre/utility filters, and PNG/JPEG/PDF/CSV download.

---

## 5. Step 4 — Backend API Plan (Python FastAPI + GraphQL)

### 5.1 API Architecture
- **REST API (`/api/v1/...`):** Standard OpenAPI/Swagger endpoints for auth, file uploads (multipart), Excel imports, report downloads, and CRUD operations.
- **GraphQL API (`/graphql` via Strawberry):** Exposes nested queries (e.g., `ftcCase -> elements -> documents -> workflowSteps`), mutations returning updated state, and **GraphQL Subscriptions** (over WebSockets) for real-time control room updates. Include `DataLoader` batching to eliminate N+1 queries.
- **WebSockets (`/ws/{centre_code}`):** Pushes live outage code updates, consent notifications, shift changes, and SCADA/weather alerts to connected clients within `< 100ms` latency.

### 5.2 Key Endpoint Blueprints
- **Auth & RBAC:** `POST /api/v1/auth/login`, `/verify-otp`, `/forgot-password`, `/reset-password`, `GET/DELETE /api/v1/auth/sessions`, `POST /api/v1/auth/verify-contacts`, `GET /api/v1/audit-logs`
- **Portal & Ticketing:** `CRUD /api/v1/portal/content`, `POST /api/v1/tickets`, `PATCH /api/v1/tickets/{id}/escalate`, `GET /api/v1/tickets/dashboards/{role}`, `GET /api/v1/tickets/sla-penalty-report`
- **Master Registry:** `CRUD /api/v1/master/entities`, `/substations`, `/elements` (auto-generates Unique Element IDs from Annexure A2 syntax), `POST /api/v1/master/elements/duplicate`
- **Registration:** `POST /api/v1/registration/nsws-sync`, `POST /api/v1/registration/fnc-import`, `POST /api/v1/registration/{id}/review`, `POST /api/v1/registration/nldc-shift`
- **FTC & Comm Cert:** `POST /api/v1/ftc/cases`, `POST /api/v1/ftc/{id}/stage/{1..5}`, `POST /api/v1/ftc/{id}/dept-consent`, `GET /api/v1/ftc/{id}/certificate-pdf`, `CRUD /api/v1/ftc/startup-power`, `CRUD /api/v1/comm-cert/cases`
- **Outage Suite:** `POST /api/v1/shifts/open`, `/close`, `CRUD /api/v1/outage-coord/plans`, `POST /api/v1/realtime/code-requests`, `POST /api/v1/realtime/consents/{id}`, `POST /api/v1/realtime/codes/{id}/execute`, `POST /api/v1/realtime/codes/{id}/revoke`, `GET /api/v1/realtime/shift-report`
- **Availability, Protection, Alerts, SPS & MIS:** `GET/POST /api/v1/availability/monthly-sheet`, `POST /api/v1/availability/{id}/bifurcate`, `CRUD /api/v1/protection/events`, `/psc`, `POST /api/v1/alerts/send-bulk`, `CRUD /api/v1/sps/status`, `POST /api/v1/mis/reports/generate` (bi-lingual PDF/XLSX), `GET /api/v1/mis/bi-views/{view_name}`

### 5.3 Security & Compliance Middleware
- **Authentication:** OAuth2 Bearer JWT + 2FA OTP check; 5-attempt lockout; password complexity validator.
- **Protection:** `slowapi` rate limiting (DoS protection), strict CORS, security headers (CSP, HSTS, X-Frame-Options), CSRF token validation on state-changing routes, and IP-binding allowlist decorator for external integration endpoints (`NSWS`, `SCADA`, `CTUIL`).
- **Validation:** Strict Pydantic v2 input validation + MIME/extension verification on all file uploads.

---

## 6. Step 5 — Phased Build Instructions for Claude Code

Execute the build in **5 sequential milestones**. Complete and verify each milestone before starting the next.

### Milestone 1: Foundation, SQLite Database & Auth Shell
1. Initialize `backend/` (FastAPI, SQLAlchemy 2.0, `aiosqlite`, Alembic, Pydantic v2, `strawberry-graphql`, `python-jose`, `passlib`, `slowapi`, `openpyxl`, `reportlab`) and `frontend/` (Vite React-TS, Tailwind CSS, `react-router-dom`, `@tanstack/react-table`, `reactflow`, `recharts`, `i18next`, `vite-plugin-pwa`).
2. Implement all SQLAlchemy models in `backend/app/modules/*/models.py`, run `alembic revision --autogenerate` and `alembic upgrade head`, and execute `seed.py`.
3. Build `auth_rbac` (Dual Login, CAPTCHA, mock OTP console logger, 5-attempt lockout, session manager, audit middleware) and the React **App Shell** (Sidebar, Topbar, Centre Switcher, English/Hindi toggle, Module Launcher Grid).
4. **Verify:** Login as `superadmin` and as an `External RE User`; confirm unauthorized modules appear greyed-out and audit logs record login/session events.

### Milestone 2: Common Portal & Complaint Addressal System (RFP Phase A)
1. Build `portal_cms` (Notice Board, moving Flashers with file download, Pop-up Banner, Feedback form) with bi-lingual fields.
2. Build `ticketing_cas` (multi-channel ticket creation, Priority vs. Severity 1–4, background escalation job for Levels 0–3, graphical `CaseFlowchartTracker`, role-based dashboards, and quarterly SLA/AMC penalty calculator).
3. **Verify:** Create a Severity 1 ticket, escalate through Level 1 → Level 2, resolve, re-open, and export the SLA penalty report as PDF/XLSX.

### Milestone 3: Master Registry, Registration, FTC & Comm Certification
1. Build `master_registry` (Entities, Substations, 20+ Grid Element types with Unique Element ID generator and duplicate-element helper) and `dms_files` (auto-naming + versioning).
2. Build `registration` (NSWS mock intake, CTUIL/RLDC parallel checklist + joint comments, NLDC workload shifting across RLDCs, Fees & Charges Excel importer).
3. Build `ftc` (Stages 1–5 wizard for A/B/C Annexures, Format II/TR/IV generation, parallel SCADA/Metering/Protection consents, Trial-run Certificate, DOCO, Start-up Power, Post-commissioning compliance tracker).
4. Build `comm_cert` (CA1–CA5, CB1–CB4, third-party/inter-regional consent).
5. **Verify:** Run a complete RE plant lifecycle: Register via NSWS/Excel → NLDC shift & return → FTC Stage 1–5 → Verify Element ID auto-created in Master DB and auto-enabled for Real-Time Outage.

### Milestone 4: Outage Coordination, Real-Time Control Room, Availability, Protection, Alerts & SPS
1. Build `outage_coord` (OCC M+2, D-3, D-2, D-1 workflows, utility-wise sheet filtering, inter-regional NLDC routing).
2. Build `realtime_outage` (strict `Morning → Evening → Night` shift lifecycle with prior-shift auto-logout, Codebook for Planned/Forced/Emergency/Tripped/FTC/Anti-theft/Suo-Moto/RE MVAr, Consent blocking rule, 1-hour code expiry, execution-time enforcement gate, Draft → Final Shift Report, SCADA/Weather mock feed via WebSockets).
3. Build `availability_verify` (auto-generated monthly spreadsheet tabs, Accept/Object workflow, Protection verification, Outage Bifurcation tool).
4. Build `protection_tripping` (Outage-linked GD/GI Event creator, End-1/End-2 restricted FIR/DR/EL/TR uploads, SOPR indices, PSC tracker).
5. Build `message_alerts` (Contact directory, bulk SMS/Email, 15+ Violation templates, Flash reports) and `sps_status` (ON/OFF matrix + timeline).
6. **Verify:** Open Morning Shift → Approve OCC outage → Collect stakeholder consents → Issue Code → Record execution time → Close shift → Open Evening Shift → Verify monthly availability sheet and tripping event linkage.

### Milestone 5: MIS, GraphQL, Bi-Lingual Exports & Security Hardening
1. Build `mis_reporting` (NPMC report, Generation Outage & ENS statistics, dynamic non-hardcoded report builder, bi-lingual PDF with Hindi text above English, 30-chart-template explorer, Power BI/Tableau SQL views).
2. Wire unified Strawberry `/graphql` endpoint with `DataLoader` and real-time Subscriptions.
3. Run automated backend (`pytest`) and frontend (`vitest` / build) tests, verify `< 100ms` local API latency, check OWASP security headers/rate-limiting, and generate SPDX/CycloneDX SBOM.