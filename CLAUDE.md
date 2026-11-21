# Picnic Portal

Online service for the **Picnic/Recreational Journey Permit**, Transport Department, Government of Assam.
A group leader applies for approval of a picnic journey by road. The application passes three offices
(DTO → origin police station → DC office). On approval the system issues a QR-coded permit.

The service implements the Transport Department SOP "Picnic Journeys by Road: Picnic Season".

- **Portal name (shown to the public):** Picnic Portal
- **Project and repository name:** `picnic-permit`
- **Database name:** `picnic_permit`
- **Docker Compose project name:** `picnic-permit`

## Source documents (read before designing anything)

| File | What it is |
| --- | --- |
| `docs/PRD.md` | Product requirements. **The source of truth.** If this file and the PRD disagree, the PRD wins: tell me. |
| `docs/SOP.pdf` | The Transport Department SOP the portal implements |
| `docs/masters/District_Master.csv` | 35 districts with District ID and a Short Name used in user IDs |
| `docs/masters/Police_Stations_master.csv` | 306 police stations with District ID |
| `docs/masters/DTO_Office_Master.csv` | Draft: one DTO office per district |
| `docs/masters/User_ID_List.csv` | The 376 officer user IDs to create at first load (35 DTO, 35 DC office, 306 police station) |

Do not invent requirements. If the PRD is silent or unclear, ask me before building.

## Tech stack

Use the latest stable release of each, and pin exact versions in lock files.

- **Backend:** Python 3.14, FastAPI, Uvicorn, Pydantic v2, pydantic-settings
- **Database:** PostgreSQL 18 (Docker image only, never installed on the host)
- **ORM:** SQLAlchemy 2.x (typed `Mapped[...]` models), Alembic migrations, psycopg 3
- **Frontend:** Next.js 16 (App Router), React 19, TypeScript (strict), Tailwind CSS 4, shadcn/ui,
  React Hook Form + Zod
- **Tooling:** uv (Python packages), Ruff (lint + format), pytest; pnpm, ESLint, Prettier
- **Other:** Argon2 password hashing, segno (QR), WeasyPrint (permit PDF), openpyxl (Excel)
- **Runtime:** Docker Compose for development and production

## Repository layout

```
backend/
  app/
    api/          route handlers, one module per area
    core/         settings, security, dependencies
    models/       SQLAlchemy models
    schemas/      Pydantic request/response models
    services/     business logic (workflow, duplicates, QR, SMS, OTP)
    seeds/        master data loaders
  alembic/        migrations
  tests/
frontend/
  src/app/        routes: (public) landing, apply, status, verify, incident; (officer) dashboard
  src/components/
  src/lib/        API client, validation schemas
docker/           nginx config, backup script
docs/             PRD, SOP, masters
compose.yaml      development
compose.prod.yaml production
```

## Commands

Everything runs in Docker. Do not ask me to install Python, Node or PostgreSQL on the host.

```
docker compose up --build                 # start db, backend, frontend
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision --autogenerate -m "message"
docker compose exec backend python -m app.seeds.load_masters
docker compose exec backend pytest
docker compose exec backend ruff check . && ruff format .
docker compose exec frontend pnpm lint
docker compose exec frontend pnpm build
```

- Frontend: http://localhost:3000
- API: http://localhost:8000, interactive docs at http://localhost:8000/docs

## Core rules of the domain

These come from the SOP and the PRD. Enforce them in the backend. The frontend repeats them only for
convenience.

**Applicant side**

- No applicant login, no accounts, no saved drafts. Form state lives in the browser until submission.
- The group leader's mobile is verified by OTP at submission (the SOP's undertaking).
- Status search by application number is open. Status search by mobile number needs OTP.
- Correcting a returned application, uploading the inspection certificate, viewing full details and
  downloading the permit need OTP to the group leader's mobile.
- English only. Citizen pages are mobile-first.

**Form validations (hard blocks)**

- Travel date at least 7 days and not more than 90 days after the submission date, and inside the
  picnic season when the State Admin has set one.
- Group leader at least 18 years old. Driving licence valid on the travel date.
- Departure not before 07:00. Return not after 18:00, and after departure.
- People travelling (group leader + members + driver + handyman) must not exceed the registered seating
  capacity.
- Driving time is a choice of "up to 60 minutes" or "60 to 90 minutes". The second flags the
  application for the DC's specific approval. Over 90 minutes cannot be applied for.
- One destination only. Vehicle type list excludes goods vehicles, trucks, tractors and trailers.
- The group leader is always passenger 1 and cannot be removed.

Keep 7 days, 90 days, 07:00, 18:00, the leader's minimum age and the child-counting rule as settings
in the database, not constants.

**Duplicates**

- Block a submission when an active application exists for the same vehicle registration number on the
  same travel date, or the same driving licence number on the same travel date.
- Compare after removing spaces and hyphens and upper-casing.
- Active = any status except Rejected, Cancelled, Expired.
- A blocked applicant can raise a claim. Their application is stored as "On hold: duplicate claim" and
  the DTO resolves it (PRD Section 10.1).

**Workflow**

Statuses: `PENDING_DTO`, `ON_HOLD_DUPLICATE_CLAIM`, `PENDING_POLICE`, `PENDING_DC`,
`RETURNED_TO_APPLICANT`, `REJECTED`, `APPROVED`, `CANCELLED`, `EXPIRED`.

- Submission routes to the DTO office of the origin district.
- DTO, police station and DC office can each: forward (DC: approve), return to applicant, correct data
  or documents themselves, set a working status, reject with a reason.
- A returned application, once resubmitted, goes back to the office that returned it.
- If the vehicle or driver is changed after the DTO stage, the application goes back to the DTO.
- A police station can transfer an application to another police station of the same district.
- The origin police station must enter the destination police station before forwarding.
- DC approval generates the permit and QR. Permits expire at the end of the travel date.
- Implement the workflow as one state machine in `services/workflow.py`. No status changes anywhere else.
- Every action and every data change writes an immutable audit log row: who, when, old value, new value.
- Every status change sends an SMS to the group leader.

**QR permit**

- The QR holds plain text readable offline (permit number, travel date and hours, vehicle number, driver
  name and licence number, number of people, origin, destination, group leader's mobile) plus a short
  verification URL. Keep the text short.
- The verification page is public and shows Valid, Cancelled or Expired.
- The permit prints with the QR at no less than 10 cm × 10 cm.

**Officers**

- Officer login is user ID + password. Passwords are auto-generated, must be changed at first login,
  and are reset only by a State User Management Admin. There are several such admins.
- Bulk user creation from Excel or CSV.
- User ID naming. Lowercase letters, digits and dots only. Login is not case-sensitive.
  - DTO: `dto.<district short name>`, e.g. `dto.tinsukia`, `dto.kamrupm`
  - DC office: `dc.<district short name>`, e.g. `dc.tinsukia`, `dc.salmara`
  - Police station: `ps.<station name without spaces or the trailing "PS">`, e.g. `ps.margherita`
  - If a new police station's name clashes, append the district short name: `ps.lakhipur.cachar`
  - A second user in the same office gets a number: `dto.tinsukia.2`
  - Others: `admin.1`, `sp.<district short name>`, `transport.state.1`
  - The district Short Name is a column in the district master and is editable by the admin.
  - Link users to offices by internal ID, never by the user ID string, so a user ID can be renamed.
  - Seed the initial officers from `docs/masters/User_ID_List.csv`. Passwords are generated by the
    portal, never stored in that file.
- Roles: `STATE_ADMIN`, `DTO`, `POLICE_STATION`, `DC_OFFICE`, `VIEWER`. Every officer has a
  jurisdiction (state, district or police station) and sees only data inside it.
- Enforcement (cancelling a permit) uses one access code per office (DTO office, police station, DC
  office) plus the official's own mobile verified by OTP. Enforcement officials may be from the
  Transport Department, the Police, or notified by the DC. No enforcement login and no individual
  enforcement accounts. A reason is mandatory. See PRD Section 9.1.
- Admins can add, modify and deactivate districts, police stations and DTO offices. Never hard-delete
  a master row that an application refers to.

## Engineering conventions

- Business logic lives in `services/`. Route handlers stay thin.
- All schema changes go through Alembic migrations. Never edit the database by hand.
- Authorisation is checked in the backend on every request, including jurisdiction. Never trust the UI.
- SMS and OTP go through an interface (`services/sms.py`). In development, log the message and OTP to
  the console instead of sending. The real gateway is not decided yet.
- Uploaded files: PDF, JPG, PNG only, size-limited, stored on a Docker volume under a random name,
  served only through an authorised endpoint.
- Secrets and settings come from environment variables. Commit `.env.example`, never `.env`.
- Rate-limit OTP requests and public search. Add a captcha to public forms.
- Write tests for: every validation rule, the duplicate check, every workflow transition and its
  permissions, and QR content.
- Timezone is Asia/Kolkata for all rules and displays. Store timestamps in UTC.

## Build order

Build one phase at a time. At the end of each phase, run the tests, tell me what to check in the
browser, and wait for my go-ahead.

1. **Foundation:** repo layout, Docker Compose (db, backend, frontend), settings, health check,
   Alembic, lint and test setup.
2. **Masters and officers:** district, police station and DTO office models; seed from the CSV files;
   officer accounts, roles, jurisdiction, login, forced password change, admin reset, bulk creation.
3. **Application form:** data model, six-step mobile form, validations, uploads, OTP undertaking,
   duplicate check, submission.
4. **Landing page and status:** landing page, status search, OTP-gated correction and uploads.
5. **Officer workflow:** queues and actions for DTO, police station and DC office; inspection;
   transfers; working status; audit timeline; duplicate claims.
6. **Permit:** QR generation, permit PDF, public verification page, expiry job.
7. **Enforcement and incidents:** access codes, violation recording, cancellation and restore, open
   incident report form.
8. **Dashboards and reports:** counts, reports, exports, daily list of approved journeys, incoming
   journeys for destination police stations.
9. **Production:** production images, Nginx, backups, security review, load test.

## Working with me

- Before writing code for a phase, show me a short plan and wait for approval.
- Make small commits with clear messages. Do not push or deploy unless I ask.
- If something in the PRD cannot be built as written, stop and explain instead of working around it.
- Do not add features that are out of scope in PRD Section 2 (VAHAN, SARATHI and eChallan integration,
  checkpoint mobile app, Assamese language, picnic spot master, map or route capture).
- When you finish a task, say plainly what works, what is untested, and what is still missing.
