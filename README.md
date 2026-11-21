# Picnic Portal

Online service for the **Picnic/Recreational Journey Permit**, Transport Department, Government of Assam.

- Requirements: [docs/PRD.md](docs/PRD.md) (the source of truth) and [docs/SOP.pdf](docs/SOP.pdf)
- Build rules and conventions: [CLAUDE.md](CLAUDE.md)

**Status: Phase 5 (Officer workflow).** DTO, police station and
DC office users have a work queue and a list of every application in their jurisdiction. The office
that holds an application can forward it (the DC office approves), return it to the applicant,
correct it, set a working status, or reject it. Each action records the officer's name and
designation and shows in the application's timeline. The State Admin can edit the working statuses
and the ready reasons for return and rejection.
Each office also records its own work. The DTO records the VAHAN, challan and SARATHI findings,
checks each document, schedules and records the vehicle inspection, and confirms the inspection
certificate; it cannot forward until the inspection is passed or a certificate is confirmed. The
DTO resolves duplicate claims and can flag the mobile number behind a fake application; the State
Admin can block a flagged number. The police station enters the destination police station (needed
before forwarding), confirms the driving time, and can transfer the application to another station
of the district. The DC office gives a specific approval remark for a 60 to 90 minute journey.
The permit and its QR code come in Phase 6.
The landing page, status search, OTP access to the
full application, inspection certificate upload and correction of a returned application work.
The public six-step application form works: rules, uploads,
OTP undertaking, duplicate check and submission.
Districts, police stations, DTO offices and officer
accounts are in place, with login, forced password change and the State Admin screens. The public
application form comes in Phase 3.

Everything runs in Docker. Nothing else is installed on the computer: no Python, Node or PostgreSQL.

| Part | Technology |
| --- | --- |
| Backend | Python 3.14, FastAPI, SQLAlchemy 2, Alembic, psycopg 3 |
| Database | PostgreSQL 18 |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui |
| Entry point (production) | Nginx |

## Development (Windows 11, Docker Desktop with WSL 2)

Run every command from the project folder, in PowerShell.

### Start

```
docker compose up --build
```

Leave this window open: it shows the logs. Add `-d` to run in the background instead.

| What | Address |
| --- | --- |
| API health check | http://localhost:8000/api/health |
| API docs | http://localhost:8000/docs |
| Landing page | http://localhost:3000 |
| Application form | http://localhost:3000/apply |
| Status search | http://localhost:3000/status |
| System health | http://localhost:3000/health |
| Officer login | http://localhost:3000/login |

Edits under `backend/` and `frontend/` show within a second or two, without a rebuild.
Rebuild (`docker compose up --build`) only after changing dependencies or a Dockerfile.

Two things to know about pages on Windows:

- Do not name a route folder with square brackets (for example `[number]`). The development
  server then rebuilds without end and pages never settle. Pass the value in the address instead,
  as `/status/application?n=...` does.
- A brand-new page folder under `frontend/src/app/` is not noticed until
the frontend is restarted:

```
docker compose restart frontend
```

### First-time setup of the database

Run these three once, after the first start (and again after a database reset).

Create the tables:

```
docker compose exec backend alembic upgrade head
```

Load the 35 districts, 306 police stations, 35 DTO offices and 376 officer accounts from
`docs/masters/`. It is safe to run again; rows already present are skipped:

```
docker compose exec backend python -m app.seeds.load_masters
```

Create the first State Admin. The command prints the user ID (`admin.1`) and a password, once:

```
docker compose exec backend python -m app.seeds.create_admin
```

Then log in at http://localhost:3000/login, change the password when asked, and go to
**Users → Generate first passwords**. The portal gives one Excel file with the user IDs and
passwords of the 376 officer accounts. The seeded accounts cannot log in before this.

In development no SMS is sent. The application form shows the OTP in a "Development only" box
under the OTP field. Every SMS, including each OTP, is also written to the backend log
instead, and so is the answer of each captcha, for
convenience (`docker compose logs backend`). This never happens in production.

### Trying the officer workflow

Log in as the State Admin and give passwords to the offices of one district (Users page), for
example `dto.tinsukia`, `ps.margherita` and `dc.tinsukia`. Submit an application for that district
and police station from the public form. Then log in as each office in turn: the application is in
the work queue of the office that holds it. Returning it lets the group leader correct and resubmit
it from the status page.

To try a duplicate claim, submit a second application with the same vehicle and date from another
mobile number, and choose "raise a claim" when the form reports the clash. The DTO then finds it
under "Duplicate claims" on the work queue page.

Development needs no `.env` file. To change a port or password, copy `.env.example` to `.env`
and edit it.

### Stop

```
docker compose down
```

The database and uploaded files are kept. Press `Ctrl+C` first if the logs window is open.

### Migrations

In development, migrations are run by hand.

```
docker compose exec backend alembic upgrade head
```

```
docker compose exec backend alembic revision --autogenerate -m "describe the change"
```

```
docker compose exec backend alembic current
```

### Tests and lint

```
docker compose exec backend pytest
```

The tests use their own database, `picnic_permit_test`, which is created and removed by the test
run. They never touch the development data.

```
docker compose exec backend sh -c "ruff check . && ruff format --check ."
```

```
docker compose exec frontend pnpm lint
```

To fix formatting automatically:

```
docker compose exec backend sh -c "ruff check --fix . && ruff format ."
```

```
docker compose exec frontend pnpm format
```

### Logs

```
docker compose logs -f
```

```
docker compose logs -f backend
```

Replace `backend` with `frontend` or `db` as needed.

### Database shell

```
docker compose exec db psql -U picnic -d picnic_permit
```

### Reset the development database

This deletes all development data, including uploaded files.

```
docker compose down --volumes
```

```
docker compose up --build
```

Then repeat the three commands of "First-time setup of the database".

### Adding a dependency

Lock files are updated inside the containers, then the image is rebuilt.

```
docker compose exec backend uv add <package>
```

```
docker compose exec frontend pnpm add <package>
```

```
docker compose up --build -d
```

## Production (Linux server)

### First start

1. Install Docker Engine with the Compose plugin on the server.
2. Copy the project to the server.
3. Create the settings file. Set a strong `POSTGRES_PASSWORD`, and set `PUBLIC_BASE_URL` to the
   address of the site as the public will reach it:

   ```
   cp .env.example .env
   ```

4. Build and start:

   ```
   docker compose -f compose.prod.yaml up -d --build
   ```

5. Load the masters and officer accounts (the tables are created automatically at start):

   ```
   docker compose -f compose.prod.yaml exec backend python -m app.seeds.load_masters
   ```

6. Create the first State Admin. Note the password it prints; it is shown once:

   ```
   docker compose -f compose.prod.yaml exec backend python -m app.seeds.create_admin
   ```

7. Log in at `/login`, change the password, and use **Users → Generate first passwords** to get
   the Excel file of officer passwords for distribution.

The site is served at `http://<server>/` (port `HTTP_PORT`, default 80). The API is under `/api`.

Set `SESSION_COOKIE_SECURE=true` in `.env` as soon as the site is served over HTTPS, so the login
cookie is never sent over plain HTTP.

What production mode does:

- Nginx is the single entry point. It serves the frontend at `/` and passes `/api` to the backend.
- Only Nginx publishes a port. The database, backend and frontend are reachable only inside Docker.
- Database migrations run automatically every time the backend starts.
- The backend runs without reload. The frontend runs the built Next.js output.
- Every container runs as a non-root user, has a health check, and restarts unless stopped by hand.
- API docs (`/docs`) are switched off.
- HTTPS is not configured yet. It will be added in Phase 9, or handled by a load balancer in front.
- **No SMS gateway is connected yet.** In production an OTP is created but not delivered, and it is
  never written to the log, so the application form cannot be submitted on a production server
  until the gateway is added in `backend/app/services/sms.py`.

### Everyday commands

```
docker compose -f compose.prod.yaml ps
```

```
docker compose -f compose.prod.yaml logs -f
```

```
docker compose -f compose.prod.yaml down
```

`down` keeps the database and uploaded files. Never add `--volumes` in production: it deletes them.

### Update to a new version

```
docker compose -f compose.prod.yaml up -d --build
```

### Check health

```
curl http://localhost/api/health
```

A healthy answer is `{"status":"ok","database":"ok",...}` with HTTP 200. If the API cannot reach the
database, the answer is HTTP 503 with `"database":"unreachable"`.

## Backup and restore (production)

### Back up the database

```
sh docker/backup.sh
```

This writes `backups/picnic_permit_<UTC date and time>.dump` and deletes dumps older than 14 days.

| Setting | Default | Meaning |
| --- | --- | --- |
| `BACKUP_DIR` | `./backups` | Folder for the dump files |
| `BACKUP_KEEP_DAYS` | `14` | Dumps older than this are deleted |

Daily backup at 01:30, with cron (`crontab -e`). Replace the path with the project's folder:

```
30 1 * * * cd /opt/picnic-permit && sh docker/backup.sh >> backups/backup.log 2>&1
```

Copy the dump files to another machine regularly. A backup on the same server does not survive the
loss of that server.

### Restore the database

This replaces everything in the database with the contents of the dump.

```
sh docker/restore.sh backups/picnic_permit_20261119_183000Z.dump
```

The script asks for confirmation, stops the backend, restores inside one transaction, and starts the
backend again. To restore on a new server, start the stack once (First start, above), then run the
same command.

### Uploaded files

Uploaded files live on the `picnic-permit_uploads` volume and are not part of the database dump.

Back up:

```
docker run --rm -v picnic-permit_uploads:/data:ro -v "$(pwd)/backups:/backup" debian:trixie-slim tar czf /backup/uploads_$(date -u +%Y%m%d).tar.gz -C /data .
```

Restore (replace the file name):

```
docker run --rm -v picnic-permit_uploads:/data -v "$(pwd)/backups:/backup" debian:trixie-slim tar xzf /backup/uploads_20261119.tar.gz -C /data
```

## Settings

All settings are environment variables. `.env.example` lists and explains every one. `.env` is never
committed.

## Layout

```
backend/            FastAPI application
  app/api/          route handlers
  app/core/         settings, database
  app/models/       SQLAlchemy models
  app/schemas/      request and response models
  app/services/     business logic
  app/seeds/        master data loaders
  alembic/          migrations
  tests/
frontend/           Next.js application
  src/app/          pages
  src/components/   components (ui/ is generated by shadcn)
  src/lib/          API client, utilities
docker/             Nginx config, backup and restore scripts
docs/               PRD, SOP, master data
compose.yaml        development
compose.prod.yaml   production
```

## Pinned versions

Base images are pinned to exact tags in the Dockerfiles and Compose files. Dependencies are pinned in
`backend/uv.lock` and `frontend/pnpm-lock.yaml`, and builds fail if a lock file is out of date.
