# Pan-Grid-India OMS: Development Instructions

This file collects every instruction given for building the Grid-India Operations Management System (OMS) proof of concept, so any future session can pick up the work from here.

- **Project:** GeM bid GEM/2026/B/8083674, Grid Controller of India Ltd (Grid-India)
- **Repository:** https://github.com/dattajayraj-lab/pan-india-oms-poc (branch `main`)
- **Code folder:** `D:\PwC Work\Opportunities\OMS GRID-INDIA Operations Management System\OMS-POC`
- **Last updated:** 20-11-2026

---

## 1. Instructions given so far (in order)

| # | Instruction | Outcome |
|---|---|---|
| 1 | Read the scope of work document `scope-of-work-1791363725.pdf` and the development plan `pan_grid_india_oms_development_plan.md`. Before coding, write a functional requirements document and save it in `D:\PwC Work\Opportunities\OMS GRID-INDIA Operations Management System`. Then build the application in `OMS-POC` from milestone 1 to the end, and keep working without stopping. | `OMS_GridIndia_FRD.md` written; milestones M1 to M5 built (FastAPI backend, React frontend, all 11 modules) |
| 2 | "continue your work" | Build continued through to M5 |
| 3 | Turn the FRS into a Word version. | `OMS_GridIndia_FRD.docx` (37 pages) |
| 4 | Create a start-up script that runs in PowerShell and starts the whole application. | `start-oms.ps1` and `stop-oms.ps1` in `OMS-POC` |
| 5 | Use Claude Design to improve the design and layout. | UI redesigned directly in code. The Claude Design tool available could only sync design-system libraries, so it could not restyle the app. |
| 6 | Push the changes to the GitHub repo `https://github.com/dattajayraj-lab/pan-india-oms-poc.git`. | Pushed to `main`. Secrets, `.env` files, databases, `node_modules`, the venv and build output are kept out by `.gitignore`. |
| 7 | Summarise all the instructions for developing the application and save them in a Markdown file. | This file |

---

## 2. Standard development workflow (as instructed)

### Phases (work through in order)

1. **Development plan:** goals, tech stack, architecture, milestones
2. **FRS** (functional requirements specification)
3. **Database:** schema design, migrations, seed data
4. **API:** endpoints, validation, error handling
5. **UI:** build all screens and connect them to the API
6. **Design:** use Claude Design to create improved versions of the main screens, show them to the user, and once the user picks a direction, apply it to the UI code
7. **Startup script:** one command (for example `./start.sh`) that installs dependencies, sets up the database and starts the backend and frontend together
8. **Test** that the whole app starts and works using only that script
9. **Commit and push** to the connected git repo (branch: `main` or a feature branch)

### Logging rules

- Create `docs/BUILD_LOG.md` before starting, and update it after **every** step.
- For each step record:
  - date and time
  - phase
  - what was done
  - files created or changed
  - commands run
  - decisions made and why
  - problems hit and how they were fixed
- Keep a checklist at the top of the file showing which phases are done, in progress and pending, so the work can be resumed from that file alone.
- Commit `BUILD_LOG.md` with the code.

### Asking for input

- Before starting each phase, ask the user if anything important is unclear (tech choices, features, design preferences, credentials, repo or branch).
- Never guess passwords, API keys or secrets. Ask the user, and keep them out of git (use `.env` and add it to `.gitignore`).
- Ask before anything that can't be undone, such as force-pushing or deleting data.
- Otherwise, keep going without waiting for approval.

### Resuming

If work stops partway (for example because of a usage limit), the next session should read `docs/BUILD_LOG.md` first and continue from the first unchecked step.

---

## 3. Where this project stands against the workflow

The workflow in section 2 was given after the build was done, so this table maps the existing work onto it.

| Phase | Status | Where it lives / notes |
|---|---|---|
| 1. Development plan | Done | `Docs/pan_grid_india_oms_development_plan.md` |
| 2. FRS | Done | `OMS_GridIndia_FRD.md` and `.docx` (in the parent folder) |
| 3. Database | Done | SQLAlchemy models, Alembic migration in `backend/alembic/versions/`, seed data in `backend/app/db/seed_modules.py` and `backend/scripts/demo_data.py` |
| 4. API | Done | FastAPI routers in `backend/app/modules/*`, GraphQL in `backend/app/graphql/`; 46 backend tests pass |
| 5. UI | Done | React + TypeScript + Tailwind in `frontend/src/pages/*`; frontend tests and production build pass |
| 6. Design | Partly done | The redesign was applied directly in code. Mock-ups were not shown for a choice of direction first, because Claude Design could not generate them here. |
| 7. Startup script | Done (PowerShell) | `start-oms.ps1` (`-Reset`, `-Demo`, `-NoBrowser`, `-ApiPort`, `-WebPort`) and `stop-oms.ps1`, in place of `./start.sh` because the target machine is Windows |
| 8. End-to-end test with the script only | Done | App started with `start-oms.ps1`, then login, home, FTC and control-room screens checked in the browser |
| 9. Commit and push | Done | `main` on `dattajayraj-lab/pan-india-oms-poc` |
| Build log | Not started | `docs/BUILD_LOG.md` does not exist yet; the history so far is summarised in section 1 above |

### Useful facts for a new session

- **Python:** use `py -3.13` or `backend\.venv\Scripts\python.exe`.
- **Demo logins:** demo password `Grid@2026`. In dev mode the one-time password is shown on screen.
- **Database:** SQLite (`backend/oms_dev.db`). Stop the API before reseeding, because SQLite locks the file.
- **JWT secret:** the value in `backend/app/core/config.py` is a placeholder. Supply a real one through an environment variable before any real deployment.
