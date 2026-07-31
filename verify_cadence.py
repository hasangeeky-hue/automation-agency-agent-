"""The cadence must run the work — and must never send anything.

SEO_CADENCE has declared "crawl every 7 days, ranks every 1 day" since it was
written and nothing ever called it. plan_today() could queue a day's work and
nothing ever called that either. This proves the caller now exists, and — more
importantly — proves the boundaries it must never cross.

    python verify_cadence.py
"""
import sys
from datetime import datetime, timedelta, timezone

import content_engine_scheduler as S

FAILS = []


def chk(ok, label, detail=""):
    print(("  OK   " if ok else "  FAIL ") + label + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


class Store:
    def __init__(self, **settings):
        self.s = dict(settings)
        self.jobs = {}
        self.sent = []

    def get_setting(self, k, d=None):
        return self.s.get(k, d)

    def set_setting(self, k, v):
        self.s[k] = v

    def save(self, job):
        self.jobs[job["job_id"]] = job

    def list_jobs(self, status=None):
        return [j for j in self.jobs.values()
                if status is None or j.get("status") == status]

    def get(self, jid):
        return self.jobs[jid]


NOW = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)

# Stub the two tasks that reach the network. This file tests the CADENCE — when
# things fire and what they are allowed to do — not the SEO engines themselves.
SEO_CALLS, REPLY_CALLS = [], []
S.run_seo_due = lambda store, **kw: (SEO_CALLS.append(kw), {"ran": []})[1]
import content_engine_reply_agent as RA
RA.answer_replies = lambda **kw: (REPLY_CALLS.append(kw), {"drafts": []})[1]

print("== the switches that must stop it ==")
chk(S.run_due_work(Store(), NOW).get("skipped") == "cadence off",
    "a fresh install does NOTHING until you start it")
chk(S.run_due_work(Store(cadence_on=True, paused=True), NOW).get("skipped") == "paused",
    "PAUSED means paused — the cadence does not run behind a stop")

print("\n== it queues the day's work ==")
st = Store(cadence_on=True)
r = S.run_due_work(st, NOW)
chk(r.get("ran") == "plan", "first call queues today's batch", str(r.get("ran")))
chk(len(st.jobs) > 0, f"{len(st.jobs)} jobs created")
chk(all(j["status"] == "created" for j in st.jobs.values()),
    "every one starts at 'created' — none skips ahead")

print("\n== it does ONE thing per call and then throttles ==")
r2 = S.run_due_work(st, NOW)
chk(r2.get("ran") != "plan", "it does not re-plan on the very next loop",
    str(r2.get("ran")))
n_before = len(st.jobs)
for _ in range(50):
    S.run_due_work(st, NOW)
chk(len(st.jobs) == n_before, "50 more loops create nothing new — no runaway",
    f"{len(st.jobs)} jobs")

print("\n== the interval is real ==")
state = S.cadence_state(st)
chk(bool(state.get("plan")), "the last-run time is recorded")
later = NOW + timedelta(seconds=S.CADENCE["plan"] + 60)
chk(S._due(state, "plan", later), "it becomes due again after its interval")
chk(not S._due(state, "plan", NOW + timedelta(seconds=60)),
    "and is NOT due a minute later")

print("\n== IT MUST NEVER SEND ==")
REPLY_CALLS.clear()
st2 = Store(cadence_on=True)
st2.set_setting(S.CADENCE_KEY, {"plan": NOW.isoformat(), "seo": NOW.isoformat()})
S.run_due_work(st2, NOW)
chk(len(REPLY_CALLS) == 1, "the reply agent was invoked", str(len(REPLY_CALLS)))
chk(REPLY_CALLS and REPLY_CALLS[0].get("auto_send") is False,
    "auto_send=False is passed EXPLICITLY, so a stray REPLY_AUTO_SEND=1 in the "
    "environment cannot turn a scheduled draft into a scheduled send",
    str(REPLY_CALLS[0] if REPLY_CALLS else ""))
chk(all(c.get("dry_run") is False for c in REPLY_CALLS),
    "drafts are really written (dry_run False) — they land in your queue")

src = open("content_engine_scheduler.py", encoding="utf-8").read()
block = src[src.index("def run_due_work("):src.index("def cadence_view(")]
for forbidden in ("outreach_send", "send_all", "publish(", "approve"):
    chk(forbidden not in block,
        f"the cadence never calls anything named '{forbidden}'")

print("\n== a broken task cannot spin the worker ==")
st3 = Store(cadence_on=True)
boom = S.plan_today
S.plan_today = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
try:
    r = S.run_due_work(st3, NOW)
    chk("error" in r, "the failure is reported, not raised", str(r)[:70])
    chk(bool(S.cadence_state(st3).get("plan")),
        "and it is STAMPED, so a permanently broken task retries on its "
        "interval instead of every loop")
finally:
    S.plan_today = boom

print("\n== the dashboard can see it ==")
v = S.cadence_view(Store(cadence_on=True))
chk(v["on"] is True and len(v["rows"]) == 3, "cadence_view reports all 3 tasks")
chk(S.cadence_view(Store())["note"].startswith("The cadence is OFF"),
    "and says plainly when it is off")

print()
if FAILS:
    print(f"{len(FAILS)} FAILURES: {FAILS}")
    sys.exit(1)
print("THE CADENCE RUNS — and it queues, crawls and drafts without ever being "
      "able to publish, send, or approve on your behalf.")
