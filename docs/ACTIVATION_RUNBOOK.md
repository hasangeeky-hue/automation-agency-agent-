# ACTIVATION RUNBOOK — stages E and F

The engine is built and gated. These two stages are the founder's
switches, in the founder's hands. Nothing in the codebase flips them.

The doctrine's curve applies from the day Stage 2 starts: rough on
day 3, sharp by day 30. Do not quit at the dip.

---

## Stage 1 — OPEN THE EYES (observe mode, one week)

What it is: the clock runs, collectors fill every screen with real
numbers, and NOTHING publishes, sends, spends, or prices.

Preconditions (check on the dashboard, Web & Data Core, 17a and 13i):

- the census ran and showed what you expect
      docker compose -f deploy/docker-compose.yml exec -T api python collect_inventory.py
- the feed ran and real rows landed
      docker compose -f deploy/docker-compose.yml exec -T api python feed_data.py

The switch: press **START, supervised** in the topbar. That is the whole
action. It sets `paused = false`. Autonomy stays OFF (it is a separate
deliberate act; the start button never grants it).

What runs: the free cadence tasks only, cheapest first. Crawl, index
inspection, speed, Search Console, GA4, orders, bookings, social
snapshots, the integrations check, the risk check, the daily briefing.

What to do for a week: read the Cockpit each morning. FINISHED /
COULDN'T / NEED FROM YOU. Correct nothing yet. You are learning what
normal looks like so that abnormal is visible later.

Abort: press **STOP the whole system**. One click, everything queues
nothing new.

---

## Stage 2 — ONE LANE TO ITS GATE (content, weeks 2 to 5)

What it is: the content pipeline runs end to end and STOPS at the
Approval Room (9c). Your ten minutes a day.

For each waiting piece, three choices:

- **Approve**: it publishes.
- **Send back** with a note: the writer redoes THAT piece using your
  note (`revision_note` rides into the rewrite).
- **Save a standing rule** (the box on 9c): the correction applies to
  EVERY future piece in the lane, injected into every prompt until you
  remove it. This is the compounding; use it every time you type the
  same complaint twice.

The daily cost cap and per-job caps are live throughout. The five
permanent gates (SPEND, PUBLISH, SEND, DEPLOY, CROSS-MODULE) do not
open in any stage.

Stage 3 (add outreach) repeats this pattern at 12f. Stage 4 (narrow
autonomy) is a separate decision for week 10+, and spend, publish,
send and price stay gated forever regardless.
