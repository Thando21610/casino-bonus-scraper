# Production plan: 200 casinos, updated daily

The screening task proves the pipeline on 3 casinos. This is how I would
run the same shape of system for 200 casinos, refreshed once per day, with
the operator able to see what ran, what changed, and what failed.

## Where it runs

A single **Hetzner CX22 VPS** (2 vCPU, 4 GB RAM, ~€4.50/month) in Nuremberg,
Germany. Why Hetzner over AWS or GCP: flat monthly pricing, no egress
surprises, no per-request billing, and enough compute for a scraper fleet
plus a tiny API. If traffic grows I can resize to CX32 (4 vCPU, 8 GB) without
changing the architecture.

The VPS runs **Docker Compose** with three containers:

- **`scraper`** — the Python job. Runs on a systemd timer, exits when done.
- **`api`** — a small FastAPI service that serves the latest JSON payload
  and a small `/health` endpoint.
- **`caddy`** — reverse proxy, terminates TLS, gets certificates from
  Let's Encrypt automatically.

Why containers: reproducible builds, one file (`docker-compose.yml`) to
describe the whole stack, and the ability to run the same scraper locally
during development without touching production.

## Database

**PostgreSQL 16** on the same VPS. Two tables:

- `casinos(id, name, source_url, created_at)`
- `bonus_snapshots(id, casino_id, welcome_bonus, wagering_requirement,
  minimum_deposit, scraped_at, run_id)`

Snapshots mean we keep history and can show "changed since yesterday" on
the front end — useful when a promotion flips. 200 rows/day is trivial for
Postgres; the table will hold ~73k rows/year, well inside a single small
instance.

**Backups:**

- Nightly `pg_dump` piped to `rclone` and uploaded to **Backblaze B2**
  (free tier covers this volume comfortably).
- Weekly automated restore test to a scratch database, to prove the dumps
  are actually usable — an untested backup isn't a backup.
- Backblaze B2 keeps 30-day version history so a bad night can be rolled
  back without losing the previous good state.

**If the project grows** beyond a few million rows or needs multi-region
reads, move the database to **Neon** or **Supabase** (~$19/month) so
backups, failover, and read replicas are managed.

## Domain, DNS, HTTPS

- Domain registered at **Cloudflare Registrar** (at-cost pricing,
  ~$10/year for a `.com`).
- DNS hosted on **Cloudflare's free tier**. The apex and `www` are proxied
  through Cloudflare so I get their DDoS protection and edge caching for
  free.
- HTTPS handled by **Caddy** on the VPS, using automatic ACME
  (Let's Encrypt). Certificate renewal is fully automatic — no cron job,
  no manual step, no expiry surprises.

## Scheduling the daily run

A **systemd timer** on the VPS:

```ini
[Unit]
Description=Daily casino bonus scraper
After=network-online.target

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target