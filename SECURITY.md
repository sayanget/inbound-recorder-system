# Security notes (delivery branch)

This branch is prepared for **handover**: no hardcoded API tokens, no fixed default admin password in source, and secrets are expected from the environment.

## Secrets

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Flask session signing. Set a stable random value in production. |
| `INITIAL_ADMIN_PASSWORD` | Optional. First-time `admin` password on empty DB. If omitted, a random password is printed once at initialization. |
| `GOFO_ADMIN_TOKEN` | Optional seed for `gofo_admin_token` in `system_config` on new databases. Prefer configuring via your admin UI after deploy. |
| `MONITOR_SECRET` | Required for `app_monitor.py` control endpoints (`POST /restart`, `/stop`, `/start`). Without it, those actions return HTTP 503; `GET /status` still works. |

## Docker

1. Copy `.env.example` to `.env` and set at least `SECRET_KEY`.
2. `docker compose up` loads `.env` via `env_file` and uses `${SECRET_KEY:?…}` so Compose fails fast if `SECRET_KEY` is missing.

## Operational hygiene

- Rotate any credentials that ever appeared in old commits or shared builds.
- Prefer HTTPS in production and set `SESSION_COOKIE_SECURE` appropriately when terminating TLS.
- Keep dependencies updated (`pip list` / lockfile if you add one).

## Reporting

Report security issues to the repository maintainers privately (do not open a public issue for undisclosed vulnerabilities).
