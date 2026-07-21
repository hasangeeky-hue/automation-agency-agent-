# Deploying the Content Engine agents on your VPS

The engine runs as 3 containers: **Postgres** (the job blackboard + learning
store), the **API** (what n8n calls), and a **worker** (advances jobs on a
loop). n8n stays where it is and talks to the API over a shared docker network.

```
 site/form ──▶ n8n (public webhooks) ──▶  API :8000  ──▶  Postgres
                     ▲                       ▲
                     └── Slack approve ──────┘   worker (drains jobs, incl. measurement)
```

---

## 0. Prerequisites on the VPS
- Docker + Docker Compose plugin:
  ```bash
  curl -fsSL https://get.docker.com | sh
  docker compose version   # confirm it prints a version
  ```

## 1. Get the code onto the VPS
Put the engine files (all `content_engine_*.py`, `main.py`, and the `deploy/`
folder) on the box. Easiest is git:
```bash
cd /opt
git clone https://github.com/hasangeeky-hue/automation-agency.git content-engine
# ^ or whichever repo holds the engine .py files; if they live in a different
#   repo/folder than the WP theme, clone that one.
cd content-engine
```
> The engine `.py` files must sit at the repo root (that's what the Dockerfile
> copies). If they're in a subfolder, run the commands from that folder.

## 2. Configure secrets
```bash
cp deploy/.env.example deploy/.env
nano deploy/.env          # set POSTGRES_PASSWORD, ANTHROPIC_API_KEY, etc.
```
Also fill the OpenAI prices in `content_engine_providers.py` (the `PRICING`
dict) **if** you plan to use the GPT fallback; otherwise leave it.

## 3. Build and start
```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
docker compose -f deploy/docker-compose.yml ps        # all three "running/healthy"
```

## 4. Health-check every connection ("taste it")
```bash
# from the VPS shell:
curl -s http://127.0.0.1:8000/health | python3 -m json.tool
```
Expect `"healthy": true` with `anthropic: ok` and `postgres: ok`. If a row says
`fail`, fix that credential and `docker compose ... up -d` again.

Test a single agent in isolation (no job needed):
```bash
curl -s -X POST http://127.0.0.1:8000/skills/site_intelligence/taste \
  -H 'content-type: application/json' \
  -d '{"input":{"site_url":"https://x.com","pages_indexed":42,"crawl_errors":0,
       "core_web_vitals":{"lcp_ms":2100,"cls":0.05,"inp_ms":150},"mobile_friendly":true},
       "brand":{"brand_name":"Anthropos"}}' | python3 -m json.tool
```
You should get the agent's JSON output + token cost. (Set `USE_FIXTURES=1` first
if you want to rehearse with zero API spend.)

## 5. Connect n8n
- If n8n runs in its **own** compose, attach it to the shared network (see the
  note at the bottom of `docker-compose.yml`), then set in n8n's env:
  ```
  ENGINE_URL=http://api:8000
  SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
  APPROVE_WEBHOOK_URL=https://<your-n8n>/webhook/content-approve
  ```
- Import the 3 workflows from the `n8n/` folder, set those env vars, activate.
- Fire a test job (see `n8n/README.md`) and watch it reach the Slack approval.

## 6. Make it durable
- `restart: unless-stopped` is already set, so containers survive reboots.
- Postgres data persists in the `engine_db` volume (survives rebuilds).
- Logs: `docker compose -f deploy/docker-compose.yml logs -f api worker`

---

## Updating after a code change
```bash
cd /opt/content-engine
git pull
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

## Backups (do this)
```bash
docker compose -f deploy/docker-compose.yml exec db \
  pg_dump -U engine engine > engine-backup-$(date +%F).sql
```

## Security notes
- The API is bound to `127.0.0.1:8000` and has **no auth** — keep it that way.
  Never map port 8000 to `0.0.0.0` / the public internet. Only n8n (same docker
  network) should reach it. Public traffic hits n8n's webhooks, not the API.
- Secrets live in `deploy/.env` (git-ignored) and in n8n credentials — never in
  the code or the WP theme.
- If you ever must expose the API, put it behind a reverse proxy (Caddy/nginx)
  with a bearer token, and add an auth check in `content_engine_api.py`.

## Bare-metal alternative (no Docker)
If you'd rather run without Docker:
```bash
python3 -m venv venv && . venv/bin/activate
pip install -r deploy/requirements.txt
export STORE=pg DATABASE_URL=postgresql://... ANTHROPIC_API_KEY=... MEASURE_AFTER_DAYS=7
# API (systemd service or tmux):
uvicorn content_engine_api:app --host 127.0.0.1 --port 8000
# worker (second service):
python main.py
```
Wrap each in a `systemd` unit with `Restart=always` so they come back on reboot.
