# Content Engine - n8n workflows

Three import-ready workflows that drive the Content Engine over its REST API.
They cover the full human-in-the-loop content lifecycle:

```
form/webhook -> POST /jobs -> drive to gate -> Slack approval link
             -> click -> POST /approve -> drive to published/sent
daily cron   -> flip ready_to_measure -> drive to analytics -> optimizer -> LEARN
```

| File | Trigger | What it does |
|------|---------|--------------|
| `content-engine-1-intake.json` | Webhook `POST /webhook/content-intake` | Creates a job, drives it to the human approval gate, posts a Slack approval link |
| `content-engine-2-approve.json` | Webhook `GET /webhook/content-approve?job_id=...` | Approves the job, drives it to published/sent, notifies Slack, responds OK |
| `content-engine-3-measure-cron.json` | Schedule (every 6h) | Drains the engine: ticks every runnable job, including measurement-ready ones |

**Each workflow is a trigger + one Code node.** The orchestration logic (create,
poll, notify) lives in the Code node's JavaScript, which calls the engine with
`this.helpers.httpRequest`. This is deliberate: Code nodes barely change across
n8n versions, so there is almost no parameter-shape to break on import (unlike a
long chain of HTTP/IF/Wait nodes). The JS has been syntax-checked.

> **Code-node env access:** the Code nodes read `$env.ENGINE_URL` etc. n8n allows
> this by default; if your instance sets `N8N_BLOCK_ENV_ACCESS_IN_NODE=true`,
> either unset it, or replace `$env.X` with the literal URLs in the three Code
> nodes.

## Prerequisites

1. **Run the engine API** (the thing these workflows call):
   ```bash
   pip install fastapi uvicorn "psycopg[binary]" anthropic openai jsonschema
   export ANTHROPIC_API_KEY=...        # + OPENAI_API_KEY for the fallback
   export STORE=pg DATABASE_URL=postgres://...   # or omit STORE for in-memory
   export MEASURE_AFTER_DAYS=7         # days a piece collects traffic before measurement
   uvicorn content_engine_api:app --host 0.0.0.0 --port 8000
   ```
   Confirm it is healthy: `GET http://localhost:8000/health`.

2. **Import the workflows**: in n8n, *Workflows -> Import from File*, once per JSON file.

3. **Set n8n environment variables** (Settings -> Variables, or host env for
   `$env`). The workflows read these:

   | Variable | Example | Used by |
   |----------|---------|---------|
   | `ENGINE_URL` | `http://content-engine:8000` | all |
   | `SLACK_WEBHOOK_URL` | `https://hooks.slack.com/services/...` | 1, 2 |
   | `APPROVE_WEBHOOK_URL` | `https://your-n8n/webhook/content-approve` | 1 |

   `APPROVE_WEBHOOK_URL` must be workflow 2's **production** webhook URL (copy it
   from the Approve Webhook node after activating workflow 2).

4. **Activate** all three workflows.

## Try it (taste before launch)

Kick off a content job:
```bash
curl -X POST https://your-n8n/webhook/content-intake \
  -H 'content-type: application/json' \
  -d '{
        "type": "content_piece",
        "brand": {"brand_name": "Anthropos", "offer": "AI automation"},
        "payload": {
          "config": {"business_goal": "awareness", "cta": "Book a consultation", "produce_index": 0},
          "audit": {"site_url": "https://anthropos-automation.com", "existing_topics": ["automation"]},
          "competitors": [{"name": "RivalCo", "external_content": "..."}]
        }
      }'
```
You get a Slack message with an approval link. Click it -> the piece publishes.
The next daily cron opens measurement, runs analytics + optimizer, and folds the
result into the client playbook - so the following cycle is smarter.

**Test one agent in isolation** (no job needed):
```bash
curl -X POST http://localhost:8000/skills/site_intelligence/taste \
  -H 'content-type: application/json' \
  -d '{"input": {"site_url":"https://x.com","pages_indexed":42,"crawl_errors":0,
                 "core_web_vitals":{"lcp_ms":2100,"cls":0.05,"inp_ms":150},
                 "mobile_friendly":true}, "brand": {"brand_name":"Anthropos"}}'
```

## Notes

- **"Wait N days" is real, and lives in the ENGINE, not the cron.** When a piece
  is published (or a campaign sent), the engine stamps `measure_at = now +
  MEASURE_AFTER_DAYS`. The measurement gate stays shut until that time actually
  passes. So you can tick as often as you like (every 6h here) with zero risk of
  measuring on day 1. To change the window, set `MEASURE_AFTER_DAYS` on the API;
  the cron interval only controls how promptly a due job gets picked up.
  (`POST /jobs/{id}/ready_to_measure` still exists as a manual force-measure.)
- **Ticks are idempotent.** Each `POST /tick` advances one runnable job or
  returns `{"advanced": false}`. The drain loops call it until nothing advances.
- **Human gate holds.** Nothing publishes or sends until the approval webhook
  fires. Nothing measures until `ready_to_measure` is flipped.
- **Zero-cost testing.** Start the API with `USE_FIXTURES=1` (after a
  `RECORD_FIXTURES=1` capture) to exercise the whole flow without spending on the
  model APIs.
- **Outreach (Pipeline B):** send `"type": "outreach_campaign"` with the outreach
  payload (`raw_leads`, `buckets`, `lead`, `category`, `config`). Same three
  workflows drive it; the QA gate runs the CAN-SPAM checks.
