# Hostinger VPS setup + which accounts to connect

Two parts: (1) the accounts your agents need, and (2) the exact VPS steps.

Be clear on the honest state of the build:
- **Built and tested:** the agent brains (Claude), the orchestrator, both
  pipelines, gates, budgets, and the learning loop. These run on the Anthropic
  key alone.
- **Stubbed on purpose (needs a connector):** the external data hooks that pull
  real numbers and publish/send. Connecting an account means (a) getting its
  credentials AND (b) filling one small connector function. Those are marked
  "connector" below. I can build them one at a time once you have the account.

=============================================================================
## PART 1 - ACCOUNTS TO CONNECT
=============================================================================

### A. CORE - needed to run the agents at all
| Account | What it powers | Cost | Status |
|---|---|---|---|
| **Anthropic (Claude) API** — console.anthropic.com -> API key | Every LLM agent (the brain). Fallback is also Claude. | usage-based | **credentials only (wired)** |
| **Hostinger VPS** | Runs everything | you have it | done |
| **Postgres** | Job blackboard + learning store | free (Docker on the VPS) | wired |
| **n8n** | Orchestration + human-gate + cron | free (self-hosted) | wired |

> With just the Anthropic key you can already run the API and "taste" each
> agent in isolation. Everything below makes the pipeline pull REAL data.

### B. CONTENT PIPELINE - connect to produce, publish, and LEARN
| Account | What it powers (skill) | Cost | Status |
|---|---|---|---|
| **WordPress** (your own site) — Application Password | Publisher posts drafts via REST (Skill 8) | free | connector |
| **Google Search Console** — GCP service account + Search Console API | Site Intelligence: your real queries/positions (Skill 1) | free | connector |
| **Google Analytics 4** — GCP service account + Analytics Data API | Analytics + Optimizer: the real numbers the learning loop uses (Skill 9/10) | free | connector |
| **PageSpeed Insights API** — GCP API key | Core Web Vitals for Site Intelligence (Skill 1) | free | connector |
| **Ahrefs OR Semrush** — API key (Jurek likely has one) | Backlinks (Skill 2) + keyword opportunities feeding the Strategist | paid | connector |

### C. CONTENT PIPELINE - optional, defer until web content works
| Account | Powers | Status |
|---|---|---|
| **Meta (FB/IG) + LinkedIn** APIs | Auto-publish social posts (Skill 8) | connector, later |
| **Image generation API** | Hero/social images (Skill 5) | connector, later |

### D. OUTREACH PIPELINE (Pipeline B) - only if you do cold email
| Account | Powers | Cost | Status |
|---|---|---|---|
| **Email sender** — Brevo / SendGrid / Amazon SES: API key + verified sending domain (SPF/DKIM/DMARC) + physical mailing address + unsubscribe | Sends cold emails; the QA gate enforces CAN-SPAM (Skill 14) | free tier+ | connector |
| **Lead source** (optional) — Apollo/similar + an email verifier | Lead sourcing + verify (Skill 12/13) | paid | connector |

### E. NOTIFICATIONS
| Account | Powers | Status |
|---|---|---|
| **Slack** — Incoming Webhook URL | Approval pings from n8n | **wired** (optional; email works too) |

### Minimum to go live with CONTENT
Anthropic + WordPress + Google Search Console + GA4 (+ ahrefs/Semrush if you
want backlink/keyword depth). That set makes Pipeline A produce real, measured,
self-improving content. Outreach (Part D) is a separate switch-on.

=============================================================================
## PART 2 - HOSTINGER VPS SETUP
=============================================================================

### 1. Get into the VPS
- hPanel -> VPS -> your server -> **SSH access** (note the IP + root password, or
  add your SSH key). You can also use hPanel's **Browser terminal**.
  ```bash
  ssh root@YOUR_VPS_IP
  ```

### 2. Docker
- If you used Hostinger's **n8n VPS template**, Docker + n8n are already there:
  ```bash
  docker ps          # you should see the n8n container
  ```
- If it's a plain Ubuntu VPS:
  ```bash
  curl -fsSL https://get.docker.com | sh
  docker compose version
  ```

### 3. Put the engine on the box
```bash
cd /opt
git clone https://github.com/hasangeeky-hue/automation-agency.git content-engine
# ^ use the repo that actually holds the content_engine_*.py files.
cd content-engine
cp deploy/.env.example deploy/.env
nano deploy/.env      # set POSTGRES_PASSWORD + ANTHROPIC_API_KEY
```

### 4. Start it
```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
docker compose -f deploy/docker-compose.yml ps          # db, api, worker running/healthy
```

### 5. Taste it (health + one agent)
```bash
curl -s http://127.0.0.1:8000/health | python3 -m json.tool     # "healthy": true
curl -s -X POST http://127.0.0.1:8000/skills/site_intelligence/taste \
  -H 'content-type: application/json' \
  -d '{"input":{"site_url":"https://anthropos-automation.com","pages_indexed":40,
       "crawl_errors":0,"core_web_vitals":{"lcp_ms":2100,"cls":0.05,"inp_ms":150},
       "mobile_friendly":true},"brand":{"brand_name":"Anthropos"}}' | python3 -m json.tool
```

### 6. Connect n8n to the engine
- If n8n is a separate compose (Hostinger template), attach it to the engine
  network (see the note at the bottom of `deploy/docker-compose.yml`), then set
  in n8n's environment:
  ```
  ENGINE_URL=http://api:8000
  SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
  APPROVE_WEBHOOK_URL=https://<your-n8n-domain>/webhook/content-approve
  ```
- Import the 3 workflows from `n8n/`, set the vars, activate.

### 7. Firewall (hPanel -> VPS -> Firewall)
- Open ONLY: 22 (SSH), 443/80 (n8n's public webhooks behind its proxy).
- **Do NOT open 8000.** The engine API is localhost-only; only n8n reaches it
  over the docker network. It has no auth by design.

### 8. Wire your site
- Point your website's form / lead webhook at n8n's public webhook
  (`https://<your-n8n-domain>/webhook/content-intake`).

### 9. Connect the data accounts (Part 1B) - one at a time
For each account you enable, I fill its connector (the stubbed hook) with your
credentials, so the agent pulls/publishes real data. Start with WordPress
(publish) + Search Console/GA4 (measure) - that closes the learn loop.

### Keep it running
- `restart: unless-stopped` is set (survives reboots).
- Logs: `docker compose -f deploy/docker-compose.yml logs -f api worker`
- Backup: `docker compose -f deploy/docker-compose.yml exec db pg_dump -U engine engine > backup.sql`
