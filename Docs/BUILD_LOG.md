# Build Log: Pan-Grid-India OMS POC

Read this file first when resuming. Continue from the first unchecked item. The workflow rules are in `Docs/DEVELOPMENT_INSTRUCTIONS.md`.

## Status checklist

- [x] 1. Development plan (`Docs/pan_grid_india_oms_development_plan.md`)
- [x] 2. FRS (`OMS_GridIndia_FRD.md` / `.docx`, in the parent folder)
- [x] 3. Database: schema, Alembic migration, seed and demo data
- [x] 4. API: FastAPI REST and GraphQL, validation, error handling (46 backend tests)
- [x] 5. UI: all module screens connected to the API (6 frontend tests, production build)
- [ ] 6. Design: applied directly in code. Pending: show design options and let the user pick a direction (see note below)
- [x] 7. Startup script: `start-oms.ps1` / `stop-oms.ps1` (PowerShell, Windows target)
- [x] 8. App started and checked with the script only
- [x] 9. Commit and push to `main` (https://github.com/dattajayraj-lab/pan-india-oms-poc)
- [x] 10. User manuals in PDF with menu navigation and screenshots (`Docs/User_Manuals/`)

Note on phase 6: the Claude Design tool available in the session only syncs design-system libraries, so it could not
produce mock-ups of the app. The redesign was applied directly to the UI code without a choice of directions.

---

## Log

### 2026-11-20 (before this log existed): phases 1 to 9, summarised
This log was created after phases 1 to 9 were done, so they are recorded here in summary.
- **What was done:** read the SOW and the development plan; wrote the FRD (Markdown and a 37-page Word version);
  built milestones M1 to M5 (FastAPI + SQLite + Alembic backend, React + TypeScript + Tailwind frontend, all 11 modules);
  wrote `start-oms.ps1` / `stop-oms.ps1`; redesigned the UI; pushed to GitHub.
- **Decisions:** FastAPI rather than the plan's original framework, for speed of building a POC; SQLite with WAL for a
  zero-install demo; PowerShell start-up script because the target machine is Windows.
- **Problems and fixes:** passlib replaced by bcrypt; the SQLite lock means the API must be stopped before reseeding;
  the Vite port check needed IPv6 (`::1`); the demo-data script must set the rate limit before importing the app.

### 2026-11-20 12:20 to 12:45 IST: user manuals (PDF)
- **Phase:** documentation (user request: run the application and prepare user manuals in PDF with menu navigation and screenshots, saved under the Docs folder).
- **What was done:**
  - Started the app with `start-oms.ps1 -NoBrowser` (existing demo database).
  - Added 4 demo complaints through the API as `re_dev` (CAS/NRLDC/202611/00002 to 00005), so the Complaints screens show data. The demo database had only one, closed, ticket.
  - Captured 75 screenshots at 1440x900 with headless Edge (playwright-core), signing in as 9 demo roles:
    superadmin, nr_coord, nr_shiftic, nr_outage, nr_protection, nr_alerts, re_dev, tpcomm_user, pg_user.
  - Wrote the manual text and generated 4 PDFs with ReportLab: a cover page, a clickable table of contents and PDF bookmarks,
    a "MENU" path box and page address for every screen, numbered steps, and figures.
- **Files created:**
  - `Docs/User_Manuals/OMS_User_Manual_01_Getting_Started.pdf` (14 pages)
  - `Docs/User_Manuals/OMS_User_Manual_02_Grid-India_Internal_Users.pdf` (37 pages)
  - `Docs/User_Manuals/OMS_User_Manual_03_External_Stakeholders.pdf` (13 pages)
  - `Docs/User_Manuals/OMS_User_Manual_04_Administrators.pdf` (9 pages)
  - `Docs/User_Manuals/_build/` (capture.js, manual_content.py, build_manuals.py, README.md for regeneration)
  - `Docs/BUILD_LOG.md` (this file)
- **Commands:** `node capture.js .\png [role]`; `backend\.venv\Scripts\python.exe Docs\User_Manuals\_build\build_manuals.py <png> Docs\User_Manuals`.
- **Decisions:**
  - One manual per audience (all users, internal, external, admin) rather than one large file, so each reader gets only what applies to them.
  - Screenshots for external modules use the external user who is authorised for them: `re_dev` is not authorised for Communication Certification, Outage or Availability, so `tpcomm_user` and `pg_user` were used for those.
  - Screenshots are not committed (they are embedded in the PDFs); they can be regenerated with `_build/capture.js`.
- **Problems and fixes:**
  - Screenshots were pushed away from their text, leaving half-empty pages. Fixed by keeping each section together and scaling screenshots to 74% of the text width.
  - The PDF page renderer wrote no files when called with `-File`. Fixed by calling it with `-Command`.

### 2026-11-20 12:45 IST: commit check
- **Phase:** 9 (commit and push), at the user's request "commit to github repo".
- **What was done:** checked `git status` and compared with `origin/main`. Everything was already committed and pushed (last commit b662790). Added this entry and pushed it.
- **Note:** the 4 sample complaints added for the manuals live only in the local demo database (`backend/oms_dev.db`), which is excluded from git by design. Running `start-oms.ps1 -Reset -Demo` rebuilds the demo data without them.
