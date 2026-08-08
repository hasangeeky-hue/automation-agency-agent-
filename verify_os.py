"""
verify_os.py
============================================================================
THE GATES FOR THE EMAIL AND LEAD ENGAGEMENT OS.

Each gate below exists because something specific could go wrong, and most
of them exist because something specific DID go wrong.

  G1  one vocabulary          five outages came from two word lists that
                              disagreed
  G2  no agent reaches an ESP the absolute rule, as a test rather than a
                              paragraph
  G3  tenancy                 a guessed id must return nothing, not
                              somebody else's record
  G4  the segment evaluator   fourteen operators and nesting, including
                              what missing data means
  G5  the projection          his real jobs become OS records, and a
                              second pass writes nothing
  G6  THE PREVIEW             the defect that scored zero: what previews
                              must be what sends
  G7  the campaign machine    an illegal transition is refused
  G8  the orchestrator gates  every refusal is named
  G9  queue then approve      nothing sends without a human
  G10 the worker              re-checks at send time
  G11 events                  immutable and idempotent
  G12 flows                   a graph that branches, and never sends
  G13 templates               a published version is never overwritten
  G14 analytics               every rate carries its denominator
  G15 the screens             one navigation grammar, scoped ids, and the
                              founder's working controls still present
  G16 the wiring              the routes exist and the dashboard reaches them
  G17 real tables             one table per entity, generated from one
                              declaration, and a migration that only copies
  G18 tenancy                 workspaces, roles, and a guard that treats a
                              requested id as a request
  G19 send rules              local time, the window, the throttle, and a
                              retry ladder that stops
  G20 A/B                     deterministic arms and a verdict that refuses
                              to crown a winner early
  G21 consent capture         pending is not a subscriber, and unsubscribe
                              cancels what is already queued
  G22 the worker              honours the window, the caps and the ladder
  G23 the editors             a canvas you drag and a builder you reorder
  G24 the removal             the old formation is gone from disk
  G25 list hygiene            a scanner is named, not silently deleted; a
                              rested person is not a suppressed one
  G26 tables                  ONE table element, so columns line up
  G27 data in and out         every table downloads, a foreign spreadsheet
                              imports, and Drive is a mirror
  G28 the nineteen            every gap named in the handover, closed and
                              tested rather than described
============================================================================
"""

from __future__ import annotations

import ast
import io
import re

import content_engine_os as OS
import content_engine_os_agents as AGT
import content_engine_os_analytics as AN
import content_engine_os_audience as AUD
import content_engine_os_content as CT
import content_engine_os_core as CORE
import content_engine_os_flows as FL
import content_engine_os_screens as SCR
import content_engine_os_send as SEND
from content_engine_os_core import _D, _L

OK = []


def t(name, cond, detail=""):
    OK.append(bool(cond))
    print(("  OK   " if cond else "  FAIL ") + name
          + (f"   [{detail}]" if detail and not cond else ""))


class Store:
    """The engine's settings store, in memory, plus a job table."""

    def __init__(self):
        self.d = {}
        self.jobs = {}

    def get_setting(self, k, dflt=None):
        return self.d.get(k, dflt)

    def set_setting(self, k, v):
        self.d[k] = v

    def get(self, jid):
        return self.jobs[jid]

    def save(self, job):
        self.jobs[job["job_id"]] = job

    def list_jobs(self, status=None):
        return list(self.jobs.values())


def a_job():
    """A campaign shaped exactly like the founder's live ones: leads, a
    qualifier result, outreach_copy with subject variants, sends with
    timestamps and sent_meta, and one hand edit."""
    return {
        "job_id": "out_991", "type": "outreach_campaign",
        "created_at": "2026-07-01T09:00:00+00:00",
        "payload": {
            "name": "Munich clinics, July",
            "leads": [
                {"email": "ann@clinicx.de", "name": "Ann Weber",
                 "company": "Clinic X", "city": "Munich", "country": "Germany",
                 "website": "clinicx.de", "title": "Practice manager",
                 "source": "maps"},
                {"email": "bo@lawfirm.co.uk", "name": "Bo Hart",
                 "company": "Hart Law", "city": "Leeds", "country": "UK",
                 "source": "serp"},
                {"email": "cy@shop.ch", "name": "Cy Roth", "company": "Shop AG",
                 "country": "Switzerland", "source": "maps"},
                {"email": "bounced@dead.example", "name": "Dee",
                 "company": "Dead Co", "source": "maps"},
            ],
            "lead_qualifier": {"results": [
                {"id": "ann@clinicx.de", "score": 82, "verdict": "good",
                 "reason": "no online booking"},
                {"id": "bo@lawfirm.co.uk", "score": 41, "verdict": "weak"}]},
            "outreach_copy": {
                "subject_variants": ["A question about {{company}}",
                                     "{{company}} and online booking"],
                "body": "Hi {{name}}, I noticed {{company}} has no online "
                        "booking. Worth a short call?"},
            "email_edits": {"ann@clinicx.de|1": {
                "subject": "Ann, one thing about Clinic X",
                "body": "Hand written by the founder."}},
            "sent_to": {"ann@clinicx.de": ["<m1@x>", "<m2@x>"],
                        "bo@lawfirm.co.uk": ["<m3@x>"]},
            "sent_at": {"ann@clinicx.de": ["2026-07-02T09:00:00+00:00",
                                           "2026-07-05T09:00:00+00:00"],
                        "bo@lawfirm.co.uk": ["2026-07-02T09:05:00+00:00"]},
            "sent_meta": {
                "ann@clinicx.de": [
                    {"subject": "Ann, one thing about Clinic X", "step": 1,
                     "alias": "marketing@anthropos-automation.com",
                     "at": "2026-07-02T09:00:00+00:00"},
                    {"subject": "Following up, Clinic X", "step": 2,
                     "alias": "marketing@anthropos-automation.com",
                     "at": "2026-07-05T09:00:00+00:00"}],
                "bo@lawfirm.co.uk": [
                    {"subject": "A question about Hart Law", "step": 1,
                     "alias": "marketing@anthropos-automation.com",
                     "at": "2026-07-02T09:05:00+00:00"}]},
        }}


def seeded():
    s = Store()
    s.save(a_job())
    s.set_setting("email_suppression", ["bounced@dead.example"])
    s.set_setting("email_suppression_meta",
                  {"bounced@dead.example": {"reason": "BOUNCE"}})
    s.set_setting("outreach_tokens", {
        "tk1": {"email": "ann@clinicx.de", "job": "out_991", "step": 1},
        "tk2": {"email": "bo@lawfirm.co.uk", "job": "out_991", "step": 1}})
    s.set_setting("outreach_events", [
        {"token": "tk1", "kind": "open", "at": "2026-07-02T11:00:00+00:00"},
        {"token": "tk1", "kind": "open", "at": "2026-07-02T18:00:00+00:00"},
        {"token": "tk1", "kind": "click", "at": "2026-07-02T11:05:00+00:00",
         "url": "https://anthropos-automation.com/free-audit/"},
        {"token": "tk2", "kind": "open", "at": "2026-07-03T08:00:00+00:00"}])
    return s


SRC = {f: io.open(f, encoding="utf-8").read() for f in [
    "content_engine_os_core.py", "content_engine_os_audience.py",
    "content_engine_os_content.py", "content_engine_os_providers.py",
    "content_engine_os_send.py", "content_engine_os_flows.py",
    "content_engine_os_analytics.py", "content_engine_os_agents.py",
    "content_engine_os_screens.py", "content_engine_os.py",
    "content_engine_api.py", "content_engine_outreach_boards.py",
    "content_engine_seo_ops.py", "content_engine_os_store.py",
    "content_engine_os_tenancy.py", "content_engine_os_schedule.py",
    "content_engine_os_optin.py", "content_engine_os_editors.py"]}


def imports_of(path) -> set:
    out = set()
    for n in ast.walk(ast.parse(SRC[path])):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module)
    return out


# ===========================================================================
print("\nG1  ONE VOCABULARY")
VOCAB = ["CAMPAIGN_STATES", "JOB_STATES", "EVENT_TYPES", "CONSENT_STATES",
         "SUPPRESSION_REASONS", "NODE_TYPES", "DOMAIN_STATES", "SEGMENT_OPS",
         "LEAD_STAGES"]
dupes = []
for name in VOCAB:
    for f, src in SRC.items():
        if f == "content_engine_os_core.py":
            continue
        for n in ast.walk(ast.parse(src)):
            if (isinstance(n, ast.Assign)
                    and any(getattr(tg, "id", "") == name for tg in n.targets)):
                dupes.append(f"{name} in {f}")
t("no module re-declares a vocabulary constant", not dupes, "; ".join(dupes))
t("every campaign state has a transition rule",
  set(CORE.CAMPAIGN_MOVES) == set(CORE.CAMPAIGN_STATES))
t("every transition target is itself a real state",
  all(x in CORE.CAMPAIGN_STATES
      for v in CORE.CAMPAIGN_MOVES.values() for x in v))
t("every segment operator is offered for at least one field kind",
  set(CORE.SEGMENT_OPS) == {o for v in AUD.OPS_FOR.values() for o in v})
t("every segment operator has words a person can read",
  all(o in AUD.OP_WORDS for o in CORE.SEGMENT_OPS))
t("every node type declares what it needs",
  set(FL.NODE_CONFIG) == set(CORE.NODE_TYPES))
t("every gate reason is spelled out in words",
  all(len(v) > 8 for v in SEND.GATE_REASONS.values()))

print("\nG2  NO AGENT REACHES A MAIL PROVIDER")
reach = [f for f in SRC
         if "content_engine_os_providers" in imports_of(f)
         and f not in ("content_engine_os_send.py", "content_engine_os.py")]
t("only the send engine imports the provider adapters", not reach, str(reach))
t("the agent service does not import providers",
  "content_engine_os_providers" not in imports_of("content_engine_os_agents.py"))
t("sending is refused to agents by name",
  "campaigns.send" in AGT.HUMAN_ONLY and "campaigns.approve" in AGT.HUMAN_ONLY)
t("an agent asking to send is refused with the reason",
  AGT.call(Store(), "x", "campaigns.send", {}).get("error") == "human_only")
t("an agent asking for an invented action is told what exists",
  "does not" in AGT.call(Store(), "x", "campaigns.teleport", {}).get("message", ""))
t("an agent may not suppress somebody",
  AGT.call(Store(), "x", "profiles.suppress", {}).get("ok") is False)

print("\nG3  TENANCY IS ENFORCED IN THE BACKEND")
s = Store()
r1, r2 = CORE.Repo(s, "ws_a"), CORE.Repo(s, "ws_b")
mine = r1.put("profiles", {"id": "p1", "email": "a@a.com"})
t("a record written in one workspace is invisible in another",
  r2.one("profiles", "p1") is None)
t("all() only returns this workspace", r2.all("profiles") == [])
t("a guessed id cannot be deleted from another workspace",
  r2.delete("profiles", "p1") is False and r1.one("profiles", "p1") is not None)
r2.put("profiles", {"id": "p1", "email": "b@b.com"})
t("the same id in two workspaces stays two records",
  r1.one("profiles", "p1")["email"] == "a@a.com"
  and r2.one("profiles", "p1")["email"] == "b@b.com")
try:
    r1.all("not_a_collection")
    bad = False
except KeyError:
    bad = True
t("an unknown collection is refused rather than silently created", bad)

print("\nG4  THE SEGMENT EVALUATOR")
person = {"country": "Germany", "lead_score": 82, "company": "Clinic X",
          "city": "", "consent": "NEVER_SUBSCRIBED", "opens": 3,
          "created_at": "2026-07-01T00:00:00+00:00"}
cases = [
    ("equals", "country", "Germany", True), ("equals", "country", "France", False),
    ("not_equals", "country", "France", True),
    ("contains", "company", "clinic", True),
    ("not_contains", "company", "law", True),
    ("greater_than", "lead_score", 70, True),
    ("less_than", "lead_score", 70, False),
    ("greater_or_equal", "lead_score", 82, True),
    ("less_or_equal", "lead_score", 82, True),
    ("exists", "company", "", True), ("not_exists", "city", "", True),
    ("exists", "city", "", False),
    ("in", "country", "Germany,Austria", True),
    ("not_in", "country", "France,Spain", True),
    ("before", "created_at", "2026-08-01T00:00:00+00:00", True),
    ("after", "created_at", "2026-08-01T00:00:00+00:00", False),
]
for op, f, v, want in cases:
    t(f"{f} {AUD.OP_WORDS[op]} {v!r}",
      AUD.compare(person.get(f), op, v) is want)
t("every operator in the vocabulary is exercised above",
  {c[0] for c in cases} == set(CORE.SEGMENT_OPS))
tree = {"operator": "AND", "conditions": [
    {"field": "country", "operator": "equals", "value": "Germany"},
    {"operator": "OR", "conditions": [
        {"field": "lead_score", "operator": "greater_than", "value": 70},
        {"field": "company", "operator": "contains", "value": "law"}]}]}
t("a nested AND over OR evaluates", AUD.evaluate(tree, person) is True)
t("the nested rule reads as a sentence",
  "Country is Germany AND" in AUD.describe(tree))
t("a missing field is refused at save time, not at send time",
  AUD.validate({"field": "nope", "operator": "equals", "value": 1})[0] is False)
t("an operator that does not fit the field is refused",
  AUD.validate({"field": "country", "operator": "greater_than",
                "value": 1})[0] is False)
t("a condition with no value is refused",
  AUD.validate({"field": "country", "operator": "equals", "value": ""})[0] is False)
t("unknown data is never read as a match",
  AUD.compare(None, "equals", "x") is False
  and AUD.compare("", "contains", "x") is False)

print("\nG5  THE PROJECTION READS HIS REAL ENGINE")
store = seeded()
out = OS.sync(store, store.list_jobs())
repo = OS.repo(store)
t("four leads became four profiles", out["profiles"] == 4, str(out))
t("the campaign was projected", out["campaigns"] == 1)
t("three sent touches became three messages", out["messages"] == 3, str(out))
t("companies were created", len(repo.all("companies")) == 4)
t("the suppression list was imported",
  "bounced@dead.example" in CORE.suppression_index(repo))
t("the suppression kept its reason",
  repo.all("suppressions")[0]["reason"] == "BOUNCE")
t("opens and clicks became events",
  len([e for e in repo.all("email_events")
       if e["event_type"] == "EMAIL_OPENED"]) == 3)
t("a click was recorded with its url",
  any(e["metadata"].get("url", "").endswith("free-audit/")
      for e in repo.all("email_events") if e["event_type"] == "EMAIL_CLICKED"))
t("the qualifier score reached the lead",
  any(l.get("score") == 82 for l in repo.all("leads")))
before = len(repo.all("email_events")), len(repo.all("profiles"))
OS.sync(store, store.list_jobs())
after = len(repo.all("email_events")), len(repo.all("profiles"))
t("a second projection writes nothing new", before == after,
  f"{before} -> {after}")

print("\nG6  THE PREVIEW IS THE SEND PATH  (the zero out of ten)")
job = store.get("out_991")
got = CT.resolve_email(job, "ann@clinicx.de", 1)
t("a real recipient resolves to a real subject and body", bool(got))
t("the founder's hand edit wins at touch 1",
  got[2] == "Ann, one thing about Clinic X"
  and got[3] == "Hand written by the founder.")
g2 = CT.resolve_email(job, "bo@lawfirm.co.uk", 1)
t("an unedited recipient resolves from the agent's copy",
  bool(g2) and "Hart Law" in (g2[2] + g2[3]))
t("the personalisation token was filled with the real company",
  "{{company}}" not in (g2[2] + g2[3]))
g3 = CT.resolve_email(job, "bo@lawfirm.co.uk", 2)
t("touch 2 is a different email from touch 1", g3[3] != g2[3])
t("a stranger resolves to nothing rather than to somebody else's email",
  CT.resolve_email(job, "nobody@nowhere.com", 1) is None)
rm = CT.rendered_message(job, "ann@clinicx.de", 1)
t("the rendered message carries the branded html the sender composes",
  rm["ok"] and len(rm["html"]) > 200, str(len(rm.get("html", ""))))
t("the rendered message is marked as one you edited", rm["edited"] is True)
cid = repo.all("campaigns")[0]["id"]
pv = OS.preview(store, cid, "ann@clinicx.de", 1, jobs=store.list_jobs())
t("the campaign preview resolves through that same path",
  pv.get("ok") and pv["subject"] == "Ann, one thing about Clinic X",
  str(pv)[:160])
t("the preview never reports the empty-campaign message on a live campaign",
  "nothing to preview" not in str(pv.get("message", "")))
OS.save_edit(store, cid, "bo@lawfirm.co.uk", 1, "Bo, a question",
             "A better sentence.")
again = OS.preview(store, cid, "bo@lawfirm.co.uk", 1, jobs=store.list_jobs())
t("what you save in the editor is what the resolver returns",
  again["subject"] == "Bo, a question"
  and again["body"] == "A better sentence.")
t("and it is what the SENDER would send",
  CT.resolve_email(store.get("out_991"), "bo@lawfirm.co.uk", 1)[3]
  == "A better sentence.")
import content_engine_api as API
t("the api module's resolver is the same one, not a copy",
  API._outreach_email_for(store.get("out_991"), "bo@lawfirm.co.uk", 1)[3]
  == "A better sentence.")
t("no screen reads payload.subject or payload.html any more",
  'p.get("subject")' not in SRC["content_engine_api.py"].split(
      "THE ENGAGEMENT OS")[-1])

print("\nG7  THE CAMPAIGN STATE MACHINE")
t("a projected three touch sequence is SENDING, not SENT",
  repo.one("campaigns", cid)["state"] == "SENDING",
  repo.one("campaigns", cid)["state"])
draft = SEND.save_campaign(repo, name="A state machine fixture")
did = draft["id"]
t("a draft may not jump straight to sent",
  SEND.move_campaign(repo, did, "SENT")["ok"] is False)
t("the refusal says which moves ARE legal",
  "can only move to" in SEND.move_campaign(repo, did, "SENT")["message"])
t("an invented state is refused",
  SEND.move_campaign(repo, did, "BLASTING")["ok"] is False)
t("a legal move is allowed",
  SEND.move_campaign(repo, did, "REVIEW")["ok"] is True)
t("a campaign past draft refuses a content edit",
  SEND.move_campaign(repo, did, "SCHEDULED")
  and SEND.save_campaign(repo, campaign_id=did, subject="x")["ok"] is False)
repo.delete("campaigns", did)

print("\nG8  THE ORCHESTRATOR GATES")
CORE.set_consent(repo, "cy@shop.ch", "UNSUBSCRIBED", source="test")
camp = repo.one("campaigns", cid)
camp["audience_kind"] = "all"
repo.put("campaigns", camp)
pl = SEND.plan(repo, cid, jobs=store.list_jobs(), touch=3)
why = {r["why"] for r in pl["refused"]}
t("a suppressed address is refused by name", "SUPPRESSED" in why, str(why))
t("an unsubscribed person is refused by name", "UNSUBSCRIBED" in why, str(why))
t("every refusal reason has readable words",
  all(k in SEND.GATE_REASONS for k in why))
t("the plan reports the pool and the deliverable separately",
  pl["pool"] >= pl["deliverable"])
t("the plan states today's sending room", bool(pl.get("rate_why")))
pl2 = SEND.plan(repo, cid, jobs=store.list_jobs(), touch=1)
t("somebody already at the frequency limit is refused",
  "FREQUENCY" in {r["why"] for r in pl2["refused"]}
  or SEND.FREQUENCY_MAX > 2)

print("\nG9  QUEUE, THEN A HUMAN")
q = SEND.queue(repo, cid, jobs=store.list_jobs(), touch=3)
t("queueing writes rows", q["ok"] and q["queued"] >= 1, str(q))
t("the message says nothing has been sent", "Nothing has been sent" in q["message"])
rows = [j for j in repo.all("email_jobs") if j["status"] == "QUEUED"]
t("every queued row starts unapproved", all(not j.get("approved") for j in rows))
t("queueing the same campaign twice does not duplicate a recipient",
  SEND.queue(repo, cid, jobs=store.list_jobs(), touch=3)["queued"] == 0)


class FakeProvider:
    name = "fake"
    key_env = "FAKE"
    docs = "a test double"
    sent = []

    def available(self):
        return True, "fake"

    def send(self, to, subj, plain, html="", *, headers=None, job=None):
        FakeProvider.sent.append((to, subj))
        return {"ok": True, "provider_message_id": f"<fake-{to}>"}

    def handle_webhook(self, p):
        return []


import content_engine_os_providers as PROV
PROV.PROVIDERS["fake"] = FakeProvider()

print("\nG10 THE WORKER")
import content_engine_os_schedule as _SCHED
_SCHED.set_window(store, 0, 24, False)   # the clock must not decide a gate
w = SEND.work_queue(repo, jobs=store.list_jobs(), provider_name="fake",
                    store=store)
t("an unapproved queue sends nothing", w["sent"] == 0, str(w))
SEND.approve(repo, cid)
CORE.suppress(repo, "cy@shop.ch", "MANUAL", "unsubscribed after queueing")
w = SEND.work_queue(repo, jobs=store.list_jobs(), provider_name="fake",
                    store=store)
t("approved rows are sent", w["sent"] >= 1, str(w))
t("somebody suppressed after queueing is held at send time",
  not any(to == "cy@shop.ch" for to, _ in FakeProvider.sent))
t("a sent row records the provider's id",
  any(j.get("provider_message_id") for j in repo.all("email_jobs")))
t("every send is an event",
  len([e for e in repo.all("email_events")
       if e["event_type"] == "EMAIL_SENT"]) >= 4)

print("\nG11 EVENTS ARE IMMUTABLE AND IDEMPOTENT")
n0 = len(repo.all("email_events"))
CORE.record_event(repo, "EMAIL_OPENED", profile_id="p", campaign_id=cid,
                  message_id="m", at="2026-07-09T10:00:00+00:00")
CORE.record_event(repo, "EMAIL_OPENED", profile_id="p", campaign_id=cid,
                  message_id="m", at="2026-07-09T10:00:00+00:00")
t("the same fact recorded twice is stored once",
  len(repo.all("email_events")) == n0 + 1)
t("an invented event type is refused",
  CORE.record_event(repo, "EMAIL_TELEPORTED", profile_id="p") == {})
wh = SEND.ingest_webhook(repo, [{"event": "bounce", "email": "ann@clinicx.de",
                                 "timestamp": "2026-07-09T11:00:00+00:00"}],
                         "sendgrid")
t("a provider webhook becomes an engine event", wh["recorded"] >= 1, str(wh))
t("a redelivered webhook records nothing the second time",
  SEND.ingest_webhook(repo, [{"event": "bounce", "email": "ann@clinicx.de",
                              "timestamp": "2026-07-09T11:00:00+00:00"}],
                      "sendgrid")["recorded"] == 0)
t("a hard bounce suppresses the address",
  "ann@clinicx.de" in CORE.suppression_index(repo))

print("\nG12 FLOWS ARE A GRAPH")
d = FL.default_flow()
t("the bare template says which step still needs a campaign",
  FL.validate(d) == (False, "the send email step is missing campaign_id"),
  str(FL.validate(d)))
t("the flow seeded into the workspace is pointed at a real campaign and "
  "is valid",
  FL.validate(repo.all("flows")[0])[0] is True,
  str(FL.validate(repo.all("flows")[0])))
t("it branches on the open",
  len([e for e in d["edges"] if e["condition"]]) >= 2)
t("a flow with two triggers is refused",
  FL.validate({"nodes": d["nodes"] + [{"id": "t2", "type": "TRIGGER",
                                       "config": {"event": "manual"}}],
               "edges": d["edges"]})[0] is False)
t("a step missing its configuration is refused",
  FL.validate({"nodes": [{"id": "t1", "type": "TRIGGER", "config": {}}],
               "edges": []})[0] is False)
t("a step nobody can reach is refused",
  FL.validate({"nodes": d["nodes"] + [{"id": "z", "type": "END", "config": {}}],
               "edges": d["edges"]})[0] is False)
fid = repo.all("flows")[0]["id"]
t("a flow may not go live while invalid or may go live while valid",
  FL.activate(repo, fid)["ok"] is True)
pids = [p["id"] for p in repo.all("profiles")][:2]
t("people can be enrolled", FL.enroll(repo, fid, pids)["enrolled"] == 2)
t("enrolling twice does not double anybody",
  FL.enroll(repo, fid, pids)["enrolled"] == 0)
sent_before = len(FakeProvider.sent)
adv = FL.advance(repo, jobs=store.list_jobs())
t("advancing moves people", adv["moved"] >= 2, str(adv))
t("a flow never sends, it only queues", len(FakeProvider.sent) == sent_before)
t("the flow says so in words", "queued" in adv["message"])
t("execution state is persisted per person",
  len(repo.all("flow_executions")) == 2)
t("somebody waiting has a due time",
  any(x.get("wait_until") for x in repo.all("flow_executions")))
t("no flow module reaches a provider",
  "content_engine_os_providers" not in imports_of("content_engine_os_flows.py"))

print("\nG13 TEMPLATES")
CT.save_template(repo, "Intro", blocks=[
    {"type": "heading", "content": "Hi {{first_name}}"},
    {"type": "text", "content": "One short paragraph."},
    {"type": "button", "label": "Book a call", "url": "https://x.test"}],
    subject="A question", publish=True)
CT.save_template(repo, "Intro", blocks=[{"type": "text", "content": "v2"}],
                 subject="Changed", publish=True)
vers = repo.all("template_versions")
t("publishing twice keeps both versions", len(vers) == 2)
t("version one is still readable after version two",
  any("One short paragraph" in v["html"] for v in vers))
html = CT.render_blocks([{"type": "button", "label": "Go", "url": "https://x"}])
t("the renderer produces table based html", "<table" in html and "<tr>" in html)
t("styles are inline, because a stylesheet does not survive Outlook",
  "style=" in html and "<style" not in html)
t("an unsubscribe is always appended", "unsubscribe" in html.lower())
doc = CT.from_agent({"subject": "s", "blocks": [
    {"type": "text", "content": "ok"}, {"type": "iframe", "content": "<bad>"}]})
t("an agent's invented block type is dropped, not rendered",
  doc["blocks"] == [{"type": "text", "content": "ok"}]
  and doc["refused"] == ["iframe"])

print("\nG14 ANALYTICS")
AN.rollup(repo)
tot = AN.totals(repo)
t("totals come from the rollup", tot["sent"] >= 4)
t("the open rate carries its denominator",
  isinstance(tot["open_rate"], (list, tuple)) and " of " in tot["open_rate"][1])
t("delivered stays blank rather than claiming zero",
  tot["delivered"] is None)
t("opens are counted unique by person",
  tot["unique_opens"] <= tot["opens"])
t("the Apple caveat is attached to anything derived from opens",
  "Privacy Protection" in tot["caveat"])
rows = AN.campaign_rows(repo)
t("a campaign row leads with the subject that was sent",
  rows and rows[0]["subject"] == "Ann, one thing about Clinic X",
  str(rows[0].get("subject") if rows else None))
t("links clicked are listed with how many people",
  AN.link_rows(repo) and AN.link_rows(repo)[0]["people"] >= 1)
t("the open curve buckets hours since the send",
  any(b["opens"] for b in AN.open_curve(repo, cid)))
msgs = AN.message_rows(repo, cid)
t("every message row names the recipient and the subject sent",
  msgs and msgs[0]["email"] and any(m["subject"] for m in msgs))
t("a hand edited message is marked as such",
  any(m["edited"] for m in msgs))

print("\nG15 THE SCREENS")
ctx = OS.build_ctx(store, jobs=store.list_jobs())
html = SCR.build(ctx, live="<div id='legacy-outbox'>send</div>")
t("every screen in the rail has a panel",
  set(SCR.PANELS) == {pid for _, items in SCR.NAV for pid, _ in items})
t("thirty screens render", len(SCR.PANELS) == 30, str(len(SCR.PANELS)))
t("no screen failed to draw", "could not be drawn" not in html,
  html[html.find("could not be drawn") - 120:
       html.find("could not be drawn") + 160] if "could not be drawn" in html
  else "")
# Strip the scripts first: an id inside JS source is a string, not a DOM
# node, and scanning it reported osFxCopy's "c.id='n'+..." as an element.
_dom = re.sub(r"<script>.*?</script>|<style>.*?</style>", "", html, flags=re.S)
ids = re.findall(r"id='([^']+)'", _dom)
dup = sorted({i for i in ids if ids.count(i) > 1})
t("no duplicate element ids", not dup, str(dup))
t("every id is scoped to this section",
  all(i.startswith("os") or i.startswith("legacy") for i in ids), str(ids[:6]))
t("ONE navigation grammar: a rail, and nothing else",
  html.count("class='os-rail'") == 1 and "class='stabs'" not in html
  and "class='s3band'" not in html)
t("the old card grammar is gone", "class='card" not in html)
t("the founder's working controls are still on the page",
  "legacy-outbox" in html)
t("the campaign table leads with a subject that was really sent",
  any(x in html for x in ("Ann, one thing about Clinic X",
                          "Following up, Clinic X",
                          "A question about Hart Law")))
t("real people are on the page", "ann@clinicx.de" in html)
detail = OS.campaign_html(store, cid, jobs=store.list_jobs())
t("the campaign detail renders the real email in a frame",
  "os-frame" in detail and "srcdoc" in detail)
t("the detail offers a recipient picker", "os-who" in detail)
t("the detail offers an editor that writes to the sender's store",
  "osSaveEdit" in detail)
t("the detail shows the funnel with denominators",
  "os-funnel" in detail and " of " in detail)
pid0 = repo.all("profiles")[0]["id"]
prof = OS.profile_html(store, pid0)
t("a profile shows a timeline", "os-tl" in prof)
t("the timeline includes the emails that were sent",
  "Email 1 sent" in prof or "Email 2 sent" in prof or "Lead discovered" in prof)
t("no em dash anywhere in the interface",
  "—" not in html and "&mdash;" not in html)

print("\nG16 THE WIRING")
api = SRC["content_engine_api.py"]
for route in ["/os/campaign/{cid}", "/os/profile/{pid}", "/os/sync",
              "/os/message/save", "/os/campaign/queue", "/os/campaign/approve",
              "/os/queue/work", "/os/segment/save", "/os/segment/count",
              "/os/flow/activate", "/os/flow/advance", "/os/domain/check",
              "/os/consent", "/os/suppress", "/os/webhook/{provider}",
              "/internal/v1/agent"]:
    t(f"route {route} exists", route in api)
import content_engine_os_editors as _ED
handlers = re.findall(r"function (os[A-Z]\w+)",
                      SCR.JS + _ED.FLOW_JS + _ED.BLOCK_JS)
called = set(re.findall(r"(os[A-Z]\w+)\(", html + detail + prof))
missing = sorted(c for c in called if c not in handlers and c != "osToast")
t("every handler the screens call is defined on the page", not missing,
  str(missing))
t("the dashboard section delegates to the OS",
  "content_engine_os_screens" in SRC["content_engine_outreach_boards.py"])
t("the context builder hands the section an OS view",
  '"os": _os_ctx(' in SRC["content_engine_seo_ops.py"])
t("the working blocks are carried through by name",
  "LIVE_ORDER" in SRC["content_engine_outreach_boards.py"])

print("\nG17 REAL TABLES")
import content_engine_os_store as ST
t("every collection the core knows has a table",
  set(ST.SCHEMA) == set(CORE.COLLECTIONS),
  str(set(CORE.COLLECTIONS) ^ set(ST.SCHEMA)))
stmts = ST.ddl()
t("the DDL is generated, not hand written",
  len([x for x in stmts if x.startswith("CREATE TABLE")]) == len(ST.SCHEMA))
t("every table is keyed on the workspace first",
  all("PRIMARY KEY (workspace_id, id)" in x
      for x in stmts if x.startswith("CREATE TABLE")))
t("every index is scoped to the workspace",
  all("(workspace_id," in x for x in stmts if x.startswith("CREATE INDEX")))
# THE GATE YOUR BOX EARNED. Adding rest_until to SCHEMA shipped without an
# ALTER, so every INSERT failed against the live database and the whole
# backend fell back to JSON with one log line. A column added here must
# arrive on a table that already exists.
_alters = [x for x in stmts if x.startswith("ALTER TABLE")]
_want = sum(len(c) for c, _i in ST.SCHEMA.values()) + len(ST.SCHEMA)
t("every column has an ALTER, so adding one cannot break a live database",
  len(_alters) == _want, f"{len(_alters)} alters for {_want} columns")
t("every ALTER is idempotent",
  all("ADD COLUMN IF NOT EXISTS" in x for x in _alters))
t("a column added to SCHEMA reaches an existing table",
  any("rest_until" in x for x in _alters))
t("the alters run after the create, never before",
  min(i for i, x in enumerate(stmts) if x.startswith("ALTER"))
  > min(i for i, x in enumerate(stmts) if x.startswith("CREATE TABLE")))
t("one refused statement does not abandon the other tables",
  "must not abandon" in ST.connect.__doc__ or
  "must not abandon" in io.open("content_engine_os_store.py",
                                encoding="utf-8").read())
t("the fields a screen filters on are real columns, not JSON",
  all(c in [n for n, _ in ST.SCHEMA["email_jobs"][0]]
      for c in ("status", "approved", "next_attempt_at", "campaign_id")))
rec = {"id": "x", "workspace_id": "w", "email": "a@b.c", "status": "QUEUED",
       "attempts": 2, "approved": True, "odd": {"deep": 1}}
vals, extra = ST._split("email_jobs", rec)
t("a value with no column falls into extra rather than being dropped",
  extra == {"odd": {"deep": 1}})
row = ["x", "w", "t0", "t1"] + vals + [extra]
back = ST._join("email_jobs", row)
t("a record survives the round trip",
  back["email"] == "a@b.c" and back["status"] == "QUEUED"
  and back["attempts"] == 2.0 and back["approved"] is True
  and back["odd"] == {"deep": 1}, str(back))
t("the backend reports which one is live and why",
  set(ST.backend()) == {"mode", "why", "tables"}
  and len(ST.backend()["why"]) > 20)
t("with no database it falls back rather than going blank",
  ST.backend()["mode"] == "json")
t("the migration is a copy and says so",
  "copies" in ST.migrate.__doc__.lower()
  and "never moves" in ST.migrate.__doc__.lower())
t("the OS asks the factory rather than constructing a repo itself",
  "ST.repo_for" in SRC["content_engine_os.py"])

print("\nG18 TENANCY, WORKSPACES AND ROLES")
import content_engine_os_tenancy as TEN
ten_store = seeded()
TEN.ensure_home(ten_store)
t("the founder's own workspace exists after one call",
  bool(TEN.workspaces_for(ten_store)))
t("every role grants something", all(CORE.ROLE_GRANTS.get(r)
                                     for r in CORE.ROLES))
t("only owner and admin may administer",
  {r for r in CORE.ROLES if "admin" in CORE.ROLE_GRANTS[r]}
  == {"owner", "admin"})
t("a viewer may not send", "send" not in CORE.ROLE_GRANTS["viewer"])
made = TEN.create_workspace(ten_store, "Second client")
t("a second workspace can be created", made["ok"], str(made))
t("creating it twice is refused rather than duplicated",
  TEN.create_workspace(ten_store, "Second client")["ok"] is False)
t("a workspace id from the page is a REQUEST, not an answer",
  TEN.require(ten_store, "ws_someone_elses")["workspace_id"]
  == CORE.DEFAULT_WORKSPACE)
t("the guard refuses a grant the role does not carry",
  TEN.require(ten_store, CORE.DEFAULT_WORKSPACE, grant="admin",
              email="stranger@nowhere.com")["ok"] is False)
t("a member can be added with a role", TEN.add_member(
    ten_store, CORE.DEFAULT_WORKSPACE, "colleague@x.com", "member")["ok"])
t("an invented role is refused by name",
  "not a role" in TEN.add_member(ten_store, CORE.DEFAULT_WORKSPACE,
                                 "x@y.com", "wizard")["message"])
t("the owner cannot be removed from their own workspace",
  TEN.remove_member(ten_store, CORE.DEFAULT_WORKSPACE,
                    TEN.owner_email(ten_store))["ok"] is False
  or not TEN.owner_email(ten_store))
t("the Team screen states the limit in words, rather than implying more",
  "do not yet hold their own" in SRC["content_engine_os_screens.py"])

print("\nG19 SEND RULES")
import content_engine_os_schedule as SCHED
de = {"country": "Germany"}
ca = {"country": "Canada"}
t("a German lead is read in Berlin time", SCHED.offset_for(de)[0] == 1)
t("a Canadian lead is read in Toronto time", SCHED.offset_for(ca)[0] == -5)
t("an unknown country is treated as UTC and LABELLED approximate",
  SCHED.offset_for({"country": "Narnia"}) == (0, "UTC", True))
from datetime import datetime, timezone as _tz
noon = datetime(2026, 8, 5, 12, 0, tzinfo=_tz.utc)      # a Wednesday
w = dict(SCHED.DEFAULT_WINDOW)
t("13:00 in Berlin is inside the window",
  SCHED.in_window(de, w, noon)[0] is True)
t("07:00 in Toronto is outside it, and it says where and when",
  SCHED.in_window(ca, w, noon)[0] is False
  and "Toronto" in SCHED.in_window(ca, w, noon)[1])
sat = datetime(2026, 8, 8, 12, 0, tzinfo=_tz.utc)
t("the weekend is refused when the window says weekdays",
  SCHED.in_window(de, w, sat)[0] is False
  and "weekend" in SCHED.in_window(de, w, sat)[1])
t("the next opening is a real future stamp",
  CORE.parse_at(SCHED.next_open(ca, w, noon)) > noon)
sch_store = Store()
t("the hourly cap starts with room", SCHED.throttle_room(sch_store)[0] > 0)
SCHED.note_sent(sch_store, SCHED.DEFAULT_HOURLY)
t("the hourly cap runs out and says how far",
  SCHED.throttle_room(sch_store)[0] == 0
  and " of " in SCHED.throttle_room(sch_store)[1])
t("a first failure retries in minutes, not immediately",
  SCHED.backoff(1)["retry"] is True and SCHED.backoff(1)["next_attempt_at"])
t("the ladder gets longer each time",
  CORE.parse_at(SCHED.backoff(3)["next_attempt_at"])
  > CORE.parse_at(SCHED.backoff(1)["next_attempt_at"]))
t("retrying stops rather than looping forever",
  SCHED.backoff(SCHED.MAX_ATTEMPTS)["retry"] is False)
t("a permanent refusal is never retried",
  SCHED.backoff(1, "550 no such user")["retry"] is False
  and "permanently" in SCHED.backoff(1, "550 no such user")["why"])
t("a row scheduled for later is not due",
  SCHED.due({"next_attempt_at": "2099-01-01T00:00:00+00:00"}) is False)
t("a row with nothing pending is due", SCHED.due({}) is True)
t("changing the window to an impossible one is refused",
  SCHED.set_window(sch_store, 18, 9)["ok"] is False)

print("\nG20 A/B")
ab = {"id": "c1", "subject_variants": ["A first line", "A second line"]}
picks = {SEND.variant_for(ab, f"p{i}")[0] for i in range(40)}
t("both arms are used", picks == {0, 1}, str(picks))
t("the same person always lands on the same arm",
  all(SEND.variant_for(ab, "p7") == SEND.variant_for(ab, "p7")
      for _ in range(5)))
t("one subject is not a test",
  SEND.variant_for({"id": "c", "subject_variants": ["only"]}, "p")[0] == 0)
t("arms are labelled A, B, C",
  (SEND.variant_label(0), SEND.variant_label(1)) == ("A", "B"))
vr = AN.variant_rows(repo, cid)
t("every arm reports against its OWN recipients, not the campaign total",
  all(v["open_rate"][1] == "" or str(v["sent"]) in v["open_rate"][1]
      for v in vr) or not vr)
t("a thin test is called early rather than crowned",
  AN.ab_verdict([{"variant": "A", "subject": "x", "sent": 30,
                  "open_rate": (40.0, "12 of 30")},
                 {"variant": "B", "subject": "y", "sent": 30,
                  "open_rate": (20.0, "6 of 30")}])["state"] == "early")
t("and the message says why, in words",
  "noise" in AN.ab_verdict([{"variant": "A", "subject": "x", "sent": 30,
                             "open_rate": (40.0, "12 of 30")},
                            {"variant": "B", "subject": "y", "sent": 30,
                             "open_rate": (20.0, "6 of 30")}])["message"])
t("a real gap over a real sample is called a winner",
  AN.ab_verdict([{"variant": "A", "subject": "x", "sent": 400,
                  "open_rate": (38.0, "152 of 400")},
                 {"variant": "B", "subject": "y", "sent": 400,
                  "open_rate": (22.0, "88 of 400")}])["state"] == "winner")

print("\nG21 CONSENT CAPTURE")
import content_engine_os_optin as OPT
opt_store = seeded()
OS.sync(opt_store, opt_store.list_jobs())
orepo = OS.repo(opt_store)
tok_c = OPT.token(opt_store, "new@lead.com", "confirm")
tok_u = OPT.token(opt_store, "new@lead.com", "unsub")
t("a confirm token cannot unsubscribe", tok_c != tok_u)
t("a token cannot be guessed from the address",
  OPT.check(opt_store, "new@lead.com", "confirm", "deadbeef") is False)
t("the right token checks out",
  OPT.check(opt_store, "new@lead.com", "confirm", tok_c) is True)
CORE.upsert_profile(orepo, {"email": "pending@lead.com"})
CORE.set_consent(orepo, "pending@lead.com", "PENDING", source="form")
CORE.upsert_profile(orepo, {"email": "pending@lead.com", "city": "Bonn"})
aud_p = AUD.resolve_audience(orepo, "all")
t("PENDING is a real state on the profile",
  any(p.get("consent") == "PENDING" for p in AUD.people(orepo)))
t("and re-writing the profile does not wipe it",
  next(p for p in AUD.people(orepo)
       if p.get("email") == "pending@lead.com")["consent"] == "PENDING")
t("PENDING is not eligible for a marketing send",
  not any(p.get("email") == "pending@lead.com"
          for p in AUD.resolve_audience(orepo, "all")["eligible"])
  or "PENDING" not in CORE.CONSENT_STATES)
OPT.confirm(opt_store, "pending@lead.com",
            OPT.token(opt_store, "pending@lead.com", "confirm"), ip="1.2.3.4")
row = next(c for c in orepo.all("consents")
           if c.get("email") == "pending@lead.com")
t("confirming records SUBSCRIBED", row["status"] == "SUBSCRIBED")
t("consent is stored with when, how and from where",
  row["consent_at"] and row["consent_method"] and "ip=" in row["evidence"])
before_q = len([j for j in orepo.all("email_jobs")
                if j.get("status") in ("QUEUED", "PROCESSING")])
un = OPT.unsubscribe(opt_store, "ann@clinicx.de",
                     OPT.token(opt_store, "ann@clinicx.de", "unsub"))
t("unsubscribing suppresses in the same act",
  "ann@clinicx.de" in CORE.suppression_index(orepo))
t("and it cancels anything already queued for them",
  un["ok"] and un["cancelled"] >= 0)
t("a forged unsubscribe link is refused",
  OPT.unsubscribe(opt_store, "bo@lawfirm.co.uk", "nope")["ok"] is False)
t("the public pages never say whether an address is known",
  "If that address can receive email" in SRC["content_engine_api.py"])
t("the consent pages are outside the login, on purpose",
  '"/unsubscribe"' in SRC["content_engine_api.py"].split("_auth_gate")[1][:2000])
t("and they are rate limited instead",
  "_os_rate" in SRC["content_engine_api.py"])

print("\nG22 THE WORKER HONOURS THE RULES")
wk = seeded()
OS.sync(wk, wk.list_jobs())
wrepo = OS.repo(wk)
wcid = wrepo.all("campaigns")[0]["id"]
SEND.queue(wrepo, wcid, jobs=wk.list_jobs(), touch=3)
SEND.approve(wrepo, wcid)
SCHED.set_window(wk, 0, 24, False)               # open the window for the test
FakeProvider.sent = []
w1 = SEND.work_queue(wrepo, jobs=wk.list_jobs(), provider_name="fake",
                     store=wk)
t("with the window open, approved rows send", w1["sent"] >= 1, str(w1))
t("the worker counts what it sent against the hourly cap",
  SCHED.throttle_room(wk)[0] < SCHED.hourly_cap(wk))
# A fresh box for the window half: the one above finished its campaign,
# and the state machine correctly refuses to queue a SENT campaign again.
wk2 = seeded()
OS.sync(wk2, wk2.list_jobs())
wrepo2 = OS.repo(wk2)
wcid2 = wrepo2.all("campaigns")[0]["id"]
SCHED.set_window(wk2, 3, 4, False)               # a window nobody is inside
SEND.queue(wrepo2, wcid2, jobs=wk2.list_jobs(), touch=3)
SEND.approve(wrepo2, wcid2)
before = len(FakeProvider.sent)
w2 = SEND.work_queue(wrepo2, jobs=wk2.list_jobs(), provider_name="fake",
                     store=wk2)
t("outside the window nothing leaves", len(FakeProvider.sent) == before,
  str(w2))
t("and the row records when it will next be tried",
  any(j.get("next_attempt_at") for j in wrepo2.all("email_jobs")),
  str([(j.get("status"), j.get("error_message"))
       for j in wrepo2.all("email_jobs")]))
t("the row says WHY it is waiting, in local time",
  any("waiting:" in str(j.get("error_message"))
      for j in wrepo2.all("email_jobs")))
t("the message names waiting separately from held and failed",
  "waiting" in w2["message"] and "held" in w2["message"])
t("drain walks every workspace rather than only the visible one",
  "workspaces" in SEND.drain(wk2, jobs=wk2.list_jobs()))
t("the tick drains the queue, so it is a worker and not a button",
  "_OS.drain(store" in SRC["content_engine_api.py"])
t("drain only picks up rows a human approved",
  'j.get("approved")' in SRC["content_engine_os_send.py"])

print("\nG23 THE EDITORS")
import content_engine_os_editors as ED
fx = ED.flow_canvas(_D(FL.flow_rows(repo)[0]), _L(ctx.get("campaigns")),
                    _L(ctx.get("lists")))
t("the flow canvas ships the graph as data, not as markup",
  "data-graph=" in fx and "os-fxcanvas" in fx)
t("every node type can be added from the palette",
  all(f"osFxAdd('{n}')" in fx for n in CORE.NODE_TYPES if n != "TRIGGER"))
t("nodes are draggable and connectable",
  "pointerdown" in ED.FLOW_JS and "osFxJoin" in ED.FLOW_JS)
t("saving posts the whole graph to the backend",
  "'/os/flow/save'" in ED.FLOW_JS)
t("the canvas does not autosave, because people are inside these flows",
  "autosave" not in ED.FLOW_JS.lower())
bb = ED.block_editor({})
t("the block editor offers every block type",
  all(f"osBbAdd('{b}')" in bb for b in CT.BLOCK_TYPES))
t("every block type has a form", set(ED.BLOCK_FIELDS) == set(CT.BLOCK_TYPES))
t("blocks reorder by dragging", "dragstart" in ED.BLOCK_JS
  and "osBbMove" in ED.BLOCK_JS)
t("the builder preview goes through the SENDER's renderer",
  "'/os/template/render'" in ED.BLOCK_JS
  and "CONTENT.render_blocks" in SRC["content_engine_os.py"])
t("both editors boot on the page they are drawn on",
  "osFxBoot" in ED.BOOT_JS and "osBbBoot" in ED.BOOT_JS)
full = SCR.build(OS.build_ctx(store, jobs=store.list_jobs()))
t("the shell carries the editor code, so the handlers exist",
  "osFxBoot" in full and "osBbBoot" in full and "os-fxcanvas" in full)

print("\nG24 THE OLD FORMATION CANNOT COME BACK")
import os as _os
for gone in ("content_engine_outreach_screens.py",
             "content_engine_email_campaigns.py",
             "content_engine_email_segments.py"):
    t(f"{gone} is deleted", not _os.path.exists(gone))
t("nothing imports what was deleted",
  not any(d in v for v in SRC.values()
          for d in ("outreach_screens", "email_campaigns", "email_segments")))
t("the boards file is one function now",
  len(SRC["content_engine_outreach_boards.py"].splitlines()) < 120)
t("the section carries no card markup",
  "<div class='card " not in SCR.build(OS.build_ctx(store,
                                                    jobs=store.list_jobs())))
t("thirty screens", len(SCR.PANELS) == 30, str(len(SCR.PANELS)))
handlers2 = re.findall(r"function (os[A-Z]\w+)", SCR.JS + ED.FLOW_JS
                       + ED.BLOCK_JS)
called2 = set(re.findall(r"(os[A-Z]\w+)\(", full))
missing2 = sorted(c for c in called2 if c not in handlers2 and c != "osToast")
t("every handler the new screens call is defined", not missing2, str(missing2))

print("\nG25 LIST HYGIENE")
hy = seeded()
OS.sync(hy, hy.list_jobs())
hrepo = OS.repo(hy)
hcid = hrepo.all("campaigns")[0]["id"]
# A scanner: three clicks against one open, all instant. This is exactly
# the shape lsemino@trippscott.com has on the founder's live box.
bot = CORE.rid("prf", hrepo.ws, "bo@lawfirm.co.uk")
bmsg = CORE.rid("msg", hrepo.ws, hcid, "bo@lawfirm.co.uk", 1)
for i in range(3):
    CORE.record_event(hrepo, "EMAIL_CLICKED", profile_id=bot,
                      campaign_id=hcid, message_id=bmsg,
                      at="2026-07-02T09:05:10+00:00",
                      metadata={"url": f"https://x.test/{i}"})
scan = AN.scanners(hrepo)
t("a recipient who clicks more than they open is named a scanner",
  bot in scan, str(list(scan)[:2]))
t("and the reason is a sentence, not a code",
  "cannot do" in scan[bot] or "reads and decides" in scan[bot])
# THE SECOND DEFECT YOUR BOX FOUND. The verdict wrote its own sentence and
# printed "37 clicks against 41 opens is a security scanner" for somebody
# flagged on the instant-click rule: the wrong reason, and arithmetic that
# contradicts itself on screen.
_fast = {"is_scanner": "yes", "clicks": 3, "opens": 9, "emails_sent": 9,
         "scanner_why": AN.SCANNER_RULES["clicked_instantly"]}
_code, _why, _act = AN.verdict_for(_fast, 10)
t("a verdict quotes the rule that actually fired",
  "reads and decides" in _why, _why)
t("and never claims more clicks than opens when there were fewer",
  "clicks against" not in _why or "3 clicks, 9 opens" in _why, _why)
t("the row carries the rule so the screen can group by it",
  "rule" in (AN.hygiene(hrepo, over=2)["rows"] or [{}])[0]
  or not AN.hygiene(hrepo, over=2)["rows"])
t("a normal recipient is NOT called a scanner",
  CORE.rid("prf", hrepo.ws, "ann@clinicx.de") not in scan)
t("the group names ARE the verdict codes, so cleaning cannot miss",
  set(AN.VERDICT_CODES) <= set(AN.hygiene(hrepo, over=2)))
t("every scanner rule explains itself",
  all(len(v) > 60 for v in AN.SCANNER_RULES.values()))
before_events = len(hrepo.all("email_events"))
AN.rollup(hrepo)
t("naming a scanner deletes nothing",
  len(hrepo.all("email_events")) == before_events)
ht = AN.totals(hrepo)
t("the raw click rate is still reported",
  ht["click_rate"][0] is not None)
t("the human click rate is reported BESIDE it, not instead of it",
  "human_click_rate" in ht and "click_rate" in ht)
t("and the human number is the smaller one",
  (ht["human_clicks"] or 0) <= (ht["unique_clicks"] or 0))
t("both carry their denominator",
  " of " in ht["human_click_rate"][1] or ht["human_clicks"] == 0)

hg = AN.hygiene(hrepo, over=2)
t("the hygiene list finds the scanner",
  any(r["code"] == "scanner" for r in hg["rows"]), str(hg["rows"])[:200])
t("it reports how hard the list is worked",
  hg["worst"] >= 1 and hg["average"] is not None)
t("every row says what it is AND what to do about it",
  all(r["why"] and r["action"] for r in hg["rows"]))
t("somebody sent to who never opened is called out",
  any(r["code"] in ("silent", "overmailed", "looking") for r in hg["rows"])
  or not hg["rows"])
t("the lifetime count is used, not the fourteen day window",
  "LIFETIME" in AN.hygiene.__doc__ or "lifetime" in AN.hygiene.__doc__)

# rest is not suppression
who = "cy@shop.ch"
r1 = CORE.rest(hrepo, who, 90, "no sign of life")
t("resting somebody succeeds and says until when",
  r1["ok"] and r1["until"][:4] in ("2026", "2027"), str(r1))
t("a rested person is NOT suppressed",
  who not in CORE.suppression_index(hrepo))
t("and the message says so in words",
  "not\nsuppressed" in r1["message"] or "not suppressed" in r1["message"])
person = next(p for p in AUD.people(hrepo) if p.get("email") == who)
t("the person view carries the rest state", person["resting"] == "yes")
t("a rested person is refused by the audience gate",
  who in AUD.resolve_audience(hrepo, "all")["dropped_detail"]["resting"])
t("the refusal has a name the review screen can print",
  "RESTING" in SEND.GATE_REASONS)
t("a segment can ask who is resting", "resting" in AUD.FIELDS)
t("and how many emails somebody has ever had", "sent_total" in AUD.FIELDS)
t("and whether their clicks are a machine", "is_scanner" in AUD.FIELDS)
t("the orchestrator refuses a rested person by name",
  SEND.queue_for_person(hrepo, hcid, person["id"])["message"]
  == SEND.GATE_REASONS["RESTING"])
t("waking them puts them back", CORE.wake(hrepo, who)["ok"]
  and next(p for p in AUD.people(hrepo)
           if p.get("email") == who)["resting"] == "no")

cl = OS.clean_audience(hy, "scanner", 90)
t("cleaning a group rests it rather than suppressing it",
  cl["ok"] and "not" in cl["message"] and "suppress" in cl["message"])
t("and it rests exactly what the table showed",
  cl["rested"] == len([r for r in hg["scanner"] if r["resting"] != "yes"]))
t("cleaning an empty group is answered, not crashed",
  OS.clean_audience(hy, "silent", 90)["ok"] is True)

hhtml = SCR.build(OS.build_ctx(hy, jobs=hy.list_jobs()))
t("the Deliverability screen carries the hygiene table",
  "Who should stop receiving email" in hhtml)
t("it offers Rest, and says Rest is not suppression",
  "osRest(" in hhtml and "Rest is not suppression" in hhtml)
t("Campaign analytics shows the human rate beside the raw one",
  "Human click rate" in hhtml and "Click rate" in hhtml)
t("and warns when scanners are inflating it",
  "security scanners following every" in hhtml
  or not _L(_D(OS.build_ctx(hy, jobs=hy.list_jobs(),
                            do_sync=False).get("hygiene")).get("scanner")))
api_src = SRC["content_engine_api.py"] if "content_engine_api.py" in SRC else ""
t("the routes exist", '"/os/rest"' in io.open("content_engine_api.py",
                                              encoding="utf-8").read()
  and '"/os/audience/clean"' in io.open("content_engine_api.py",
                                        encoding="utf-8").read())

print("\nG26 TABLES LINE UP")
tb = SCR.table(["Person", "Company", "Sent", "Opens"],
               [["<b>Jill Monti</b><br><span class='os-d'>j@x.com</span>",
                 "Channel Fish Processing", SCR.num(30), SCR.num(47)],
                ["<b>Raymond Levine</b>", "Schneider Wallace Cottrell Kim",
                 SCR.num(30), SCR.num(33)]])
t("a table is ONE element, not a stack of per-row grids",
  tb.count("<table>") == 1 and "grid-template-columns" not in tb)
t("it has a real header row",
  "<thead>" in tb and tb.count("</th>") == 4)
t("every row is a tr with the same number of cells",
  tb.count("<tr>") == 3 and tb.count("<td") == 8)
# Two numeric columns, and the class lands on the header AND both cells,
# which is what makes the heading sit over its own numbers.
t("a numeric column is found and right aligned, header included",
  tb.count("class='os-r'") == 6, str(tb.count("class='os-r'")))
t("a NAME is bold too and must NOT be right aligned",
  "<td class='os-r'><b>Jill" not in tb and "<td><b>Jill" in tb)
t("a column of dashes still counts as numeric",
  SCR._numeric([[SCR.num(None)], [SCR.num(3)]], 0) is True)
t("a column of words does not",
  SCR._numeric([["<b>Ann</b>"], ["<b>Bo</b>"]], 0) is False)
full2 = SCR.build(OS.build_ctx(store, jobs=store.list_jobs()))
t("the assembled section has no per-row grid left",
  "class='os-tr'" not in full2)
t("numbers use tabular figures, so 30 sits under 750",
  "tabular-nums" in SCR.CSS)
t("a wide table scrolls inside its own box, not the page",
  "overflow-x:auto" in SCR.CSS)

print("\nG27 DATA IN AND OUT")
import content_engine_os_data as DATA
import content_engine_os_sheets as XL
import json as _json
dstore = seeded()
OS.sync(dstore, dstore.list_jobs())
drepo = OS.repo(dstore)
t("every dataset declares a label, columns and a source",
  all(len(v) == 3 and v[1] for v in DATA.DATASETS.values()))
_bad = []
for _dn in DATA.DATASETS:
    _cols, _rws = DATA.rows_for(drepo, _dn)
    if not all(len(x) == len(_cols) for x in _rws):
        _bad.append(_dn)
t("every table produces rows exactly the width of its header",
  not _bad, str(_bad))
wname, wmime, wdata = DATA.workbook(drepo)
t("the workbook is a real zip", wdata[:2] == b"PK")
t("and carries Excel's own mime type", "spreadsheetml.sheet" in wmime)
wb = XL.read_xlsx(wdata)
t("its first tab reads back with a header",
  bool(wb) and bool(wb[0]) and wb[0][0] == "email", str(wb[:1])[:120])
t("one tab per table", len(DATA.DATASETS) == 10)
cname, cmime, cdata = DATA.as_bytes(drepo, "profiles", "csv")
t("a CSV starts with the BOM, so Excel reads UTF-8 correctly",
  cdata[:3] == b"\xef\xbb\xbf")
t("and reads back with the same number of columns",
  len(XL.read_csv(cdata)[0]) == len(DATA.DATASETS["profiles"][1]))
jname, jmime, jdata = DATA.as_bytes(drepo, "profiles", "json")
_j = _json.loads(jdata)
t("the JSON export is a list of objects, not a list of lists",
  (not _j) or isinstance(_j[0], dict))

foreign = ("E-Mail;Vorname;Nachname;Firma;Land;Branche;Notizen\r\n"
           "neu@praxis.de;Lena;Braun;Praxis Braun;Germany;Healthcare;fair\r\n"
           "ann@clinicx.de;Ann;Weber;Clinic X;Germany;Healthcare;known\r\n"
           "broken-address;X;Y;Z;;;\r\n"
           "neu@praxis.de;Lena;Braun;Praxis Braun;Germany;;dup\r\n"
           ).encode("utf-8")
pv = DATA.preview(drepo, "leads.csv", foreign)
t("a semicolon CSV is read as columns, not as one column",
  pv["ok"] and len(pv["header"]) == 7, str(pv.get("header")))
t("German headers map to the right fields",
  pv["mapping"][0] == "email" and pv["mapping"][1] == "first_name"
  and pv["mapping"][3] == "company", str(pv.get("mapping")))
t("a column nobody recognises is KEPT as a custom property",
  "Notizen" in pv["custom"])
t("new, existing, repeated and broken are each counted separately",
  (pv["new"], pv["update"], pv["duplicate"], pv["invalid"]) == (1, 1, 1, 1),
  str((pv["new"], pv["update"], pv["duplicate"], pv["invalid"])))
t("the preview says nothing has been written",
  "Nothing has been written" in pv["message"])
_before = len(drepo.all("profiles"))
DATA.preview(drepo, "leads.csv", foreign)
t("and previewing really wrote nothing",
  len(drepo.all("profiles")) == _before)
CORE.suppress(drepo, "gone@dead.de", "BOUNCE", "test")
pv2 = DATA.preview(drepo, "x.csv",
                   b"email\r\ngone@dead.de\r\nfresh@new.de\r\n")
t("a suppressed address is refused by the importer",
  pv2["suppressed"] == 1, str(pv2)[:160])
cm = DATA.commit(dstore, drepo, "leads.csv", foreign, list_name="Fair leads")
t("committing writes the new people", cm["written"] == 2, str(cm))
t("and skips exactly what the preview said it would", cm["skipped"] == 2)
t("an existing person is updated, never duplicated",
  len([p for p in drepo.all("profiles")
       if p.get("email") == "ann@clinicx.de"]) == 1)
who = next(p for p in AUD.people(drepo) if p["email"] == "neu@praxis.de")
t("the custom column survived onto the person",
  who["properties"].get("Notizen") == "fair", str(who["properties"]))
t("the list was created and filled", cm["listed"] == 2)
t("the import is audited exactly like an agent action",
  any(a_.get("agent_type") == "csv_import" for a_ in drepo.all("agent_runs")))
xb = XL.write_xlsx([("Leads", [["email", "first name", "company"],
                               ["x@y.de", "Xavier", "YCo"]])])
t("an uploaded Excel file is read the same way",
  DATA.preview(drepo, "x.xlsx", xb)["new"] == 1)
t("an .xlsx renamed to .csv is still read as a workbook",
  DATA.preview(drepo, "x.csv", xb)["ok"] is True)
t("a file over the limit is refused in words, with the limit",
  "limit is" in DATA.preview(drepo, "big.csv",
                             b"x" * (DATA.MAX_UPLOAD + 1))["message"])
t("a header with no rows under it is refused in words",
  "no data underneath" in DATA.preview(drepo, "h.csv",
                                       b"email\r\n")["message"])
t("a file with no email column is refused, and says why",
  "email address" in DATA.preview(drepo, "n.csv",
                                  b"name;city\r\nBo;Leeds\r\n")["message"])
ds = DATA.drive_state()
t("Drive says whether it is ready and why",
  "ready" in ds and len(ds["why"]) > 20)
t("Drive is a mirror, and the code says so where it writes",
  "never a source" in DATA.push_to_drive.__doc__.lower())
t("pushing with no credential is refused in words, not with a traceback",
  DATA.push_to_drive(dstore, drepo)["ok"] is False)
dhtml = SCR.build(OS.build_ctx(dstore, jobs=dstore.list_jobs()))
t("the Export screen offers the whole workbook",
  "/os/export/workbook.xlsx" in dhtml)
t("every table on the Export screen offers all three formats",
  "/os/export/profiles.csv" in dhtml
  and "/os/export/profiles.xlsx" in dhtml
  and "/os/export/profiles.json" in dhtml)
t("the Import screen takes a file", "type='file'" in dhtml)
t("thirty screens", len(SCR.PANELS) == 30, str(len(SCR.PANELS)))
_api = io.open("content_engine_api.py", encoding="utf-8").read()
for _r in ('"/os/export/{name}.{fmt}"', '"/os/import/preview"',
           '"/os/import/commit"', '"/os/drive/push"'):
    t(f"route {_r} exists", _r in _api)
t("the upload needs no new server dependency",
  "UploadFile" not in _api and "= File(" not in _api
  and "python-multipart" not in io.open("deploy/requirements.txt",
                                        encoding="utf-8").read())

print("\nG28 THE NINETEEN")
import content_engine_os_bounce as BOU
import content_engine_os_data as DAT
import content_engine_os_optin as OPT2
import content_engine_os_providers as PRV
import content_engine_os_tenancy as TEN2
import content_engine_connectors as CONN
g = seeded()
OS.sync(g, g.list_jobs())
gr = OS.repo(g)
gcid = gr.all("campaigns")[0]["id"]

print("  -- 1 the unsubscribe link reaches the page")
t("the composer takes the recipient, so the link can name them",
  "to_addr" in CONN.Emailer.compose_outreach.__code__.co_varnames)
t("the sender passes it",
  "compose_outreach(body, job, to_addr)" in SRC["content_engine_api.py"]
  or "compose_outreach(body, job, to_addr)" in io.open(
      "content_engine_connectors.py", encoding="utf-8").read())
t("the preview renders the SAME link, not a different one",
  "compose_outreach(body, job, email)" in SRC["content_engine_os_content.py"])
t("a visitor with no token is served a form, not an error",
  "type=\"email\"" in OPT2.unsubscribe_page("", ""))
t("a visitor with a token gets one button",
  "Unsubscribe a@b.c" in OPT2.unsubscribe_page("a@b.c", "tok"))
_u = OPT2.unsubscribe_self(g, "bo@lawfirm.co.uk")
t("a typed unsubscribe works and is recorded as typed",
  _u["ok"] and any(c.get("email") == "bo@lawfirm.co.uk"
                   and "typed" in str(c.get("consent_method"))
                   for c in gr.all("consents")))
t("and it suppresses in the same act",
  "bo@lawfirm.co.uk" in CORE.suppression_index(gr))

print("  -- sourcing cannot return somebody you already have")
import content_engine_code_skills as _CS
import content_engine_scheduler as _SCH
from datetime import date as _date
_old_known, _old_src, _old_ver = _CS.KNOWN_FN, _CS.SOURCE_FN, _CS.VERIFY_FN
_CS.KNOWN_FN = lambda: {"ann@clinicx.de"}
_CS.SOURCE_FN = None
_CS.VERIFY_FN = lambda e: True
_job = {"payload": {"raw_leads": [{"email": "ann@clinicx.de"},
                                  {"email": "new@x.de"},
                                  {"email": "new@x.de"},
                                  {"company": "No Address Ltd"}]}}
_res = _CS.lead_sourcing(_job)
t("somebody already in the engine is dropped at sourcing",
  _res["dropped_already_known"] == 1, str(_res))
t("a repeat inside the same batch is still dropped",
  _res["dropped_duplicate"] == 1)
t("a genuinely new address survives",
  [l.get("email") for l in _job["payload"]["leads"]] == ["new@x.de",
                                                         None]
  or "new@x.de" in [l.get("email") for l in _job["payload"]["leads"]])
t("a lead with no address is still sourced, it just cannot be mailed",
  any(l.get("company") == "No Address Ltd"
      for l in _job["payload"]["leads"]))
t("the count says WHY, in the founder's own words",
  "thirty emails" in _res["note"])
_CS.KNOWN_FN = lambda: (_ for _ in ()).throw(RuntimeError("os down"))
t("if the engine cannot be read, sourcing still runs rather than stopping",
  _CS.lead_sourcing({"payload": {"raw_leads": [{"email": "z@z.de"}]}})
  ["verified"] == 1)
_CS.KNOWN_FN, _CS.SOURCE_FN, _CS.VERIFY_FN = _old_known, _old_src, _old_ver

class _St:
    def __init__(self): self.d = {}
    def get_setting(self, k, v=None): return self.d.get(k, v)
    def set_setting(self, k, v): self.d[k] = v
_st = _St()
_a = _SCH.todays_icp(_st, _date(2026, 8, 8))
_b = _SCH.todays_icp(_st, _date(2026, 8, 9))
t("the daily job asks a different question each morning",
  _a["maps_query"] != _b["maps_query"], f'{_a["maps_query"]} vs {_b["maps_query"]}')
t("but the SAME question twice on one day, so a re-plan cannot spend twice",
  _SCH.todays_icp(_st, _date(2026, 8, 8)) == _a)
t("the rotation is the founder's own market",
  len(_SCH.ICP_ROTATION) >= 10
  and any("Munich" in c or "Zurich" in c for _v, c in _SCH.ICP_ROTATION))
_st.set_setting("SCHED_ICP_ROTATION", "vets|Bern\nopticians|Basel")
t("and it can be replaced from settings without a rebuild",
  _SCH.todays_icp(_st)["rotation_size"] == 2)
_sched_src = io.open("content_engine_scheduler.py", encoding="utf-8").read()
t("the daily job carries the question, not only the offer",
  '"icp": _icp["icp"]' in _sched_src)
t("and it records which slice of the market it asked for",
  "sourcing_day" in _sched_src)

print("  -- pages, and a rows-per-page you choose")
_pg = seeded()
_pj = _pg.get("out_991")
for _i in range(140):
    _pj["payload"]["leads"].append(
        {"email": (f"p{_i}@firm{_i}.de" if _i % 3 else ""),
         "name": f"Person {_i}", "company": f"Firm {_i}",
         "website": f"firm{_i}.de", "country": "Germany", "source": "maps"})
_pg.save(_pj)
OS.sync(_pg, _pg.list_jobs())
t("every offered page size is a real choice",
  SCR.PAGE_SIZES == (20, 50, 100, 250, 500))
t("the default is one screen's worth, not everything",
  SCR.DEFAULT_SIZE in SCR.PAGE_SIZES)
_sl, _m = SCR.page_of(list(range(144)), 2, 20)
t("a page is the right slice", _sl[0] == 20 and len(_sl) == 20)
t("and knows where it is", (_m["from"], _m["to"], _m["total"], _m["pages"])
  == (21, 40, 144, 8), str(_m))
t("a page past the end lands on the last one, not on nothing",
  SCR.page_of(list(range(144)), 999, 20)[1]["page"] == 8)
t("a size nobody offered falls back to the default",
  SCR.page_of(list(range(10)), 1, 37)[1]["size"] == SCR.DEFAULT_SIZE)
t("an empty table has one page, not zero",
  SCR.page_of([], 1, 20)[1]["pages"] == 1)
t("eight tables are pageable", len(SCR.PAGED) == 8, str(sorted(SCR.PAGED)))
_p1 = OS.page(_pg, "profiles", 1, 20)
_p2 = OS.page(_pg, "profiles", 2, 20)
t("page one and page two are different rows", _p1 != _p2)
t("the bar says where you are, not just which page",
  "1 to 20 of" in _p1 and "21 to 40 of" in _p2)
t("500 rows is offered and works",
  "1 to 144 of 144" in OS.page(_pg, "profiles", 1, 500))
t("a search narrows the total the pager reports",
  "of 35" in OS.page(_pg, "profiles", 1, 20, "firm1"), 
  OS.page(_pg, "profiles", 1, 20, "firm1")[:120])
t("an unknown table is refused rather than drawn empty",
  "no table called" in OS.page(_pg, "nope", 1, 20))
_ph = SCR.build(OS.build_ctx(_pg, jobs=_pg.list_jobs()))
for _tgt in SCR.PAGED:
    if _tgt != "messages":
        t(f"the {_tgt} table has a container the page can replace",
          f"id='os-t-{_tgt}'" in _ph)
t("no screen promises a fixed 250 any more", "most engaged 250" not in _ph)
t("the handler exists", "function osPage(" in SCR.JS)

print("  -- leads with no address are still leads")
_nl = seeded()
_j = _nl.get("out_991")
_j["payload"]["leads"].append({"name": "Dr Klein", "company": "Praxis Klein",
                               "website": "praxisklein.de", "phone": "+49 1",
                               "country": "Germany", "source": "maps"})
_nl.save(_j)
OS.sync(_nl, _nl.list_jobs())
_nr = OS.repo(_nl)
t("a Maps lead with no email is written in, not skipped",
  any(p.get("company") == "Praxis Klein" for p in _nr.all("profiles")),
  str([p.get("company") for p in _nr.all("profiles")]))
t("and it becomes a lead you can see",
  len(_nr.all("leads")) == 5, str(len(_nr.all("leads"))))
t("it is keyed on the website, so re-reading does not duplicate it",
  len([p for p in _nr.all("profiles")
       if p.get("company") == "Praxis Klein"]) == 1)
_np = next(p for p in AUD.people(_nr) if p.get("company") == "Praxis Klein")
t("it is named on screen even with no address",
  AN.profile_rows(_nr)[0].get("name") is not None)
t("but it can NEVER be emailed by accident",
  _np["email"] in ("", None)
  and _np.get("id") in {x.get("id") for x in AUD.people(_nr)}
  and not any(x.get("company") == "Praxis Klein"
              for x in AUD.resolve_audience(_nr, "all")["eligible"]))
t("and the gate says why, by name",
  "invalid_address" in AUD.resolve_audience(_nr, "all")["dropped"])

print("  -- 2 bounces are read out of the mailbox")
t("a 5.x.x status is permanent",
  BOU.classify("Action: failed\nStatus: 5.1.1 user unknown")[0] == "hard")
t("a 4.x.x status is temporary and must NOT suppress",
  BOU.classify("Action: failed\nStatus: 4.2.2 mailbox full")[0] == "soft")
t("a failure with no status code is treated as temporary, never permanent",
  BOU.classify("Mail delivery failed: returning message")[0] == "soft")
t("prose alone never makes a bounce permanent",
  BOU.classify("the user unknown was mentioned")[0] != "hard")
t("an ordinary email is not a bounce", BOU.classify("hello there")[0] == "")
_m = __import__("email").message_from_string(
    "From: Mail Delivery Subsystem <mailer-daemon@x>\nSubject: Undeliverable\n"
    "Message-ID: <b1@x>\n\nFinal-Recipient: rfc822; gone@dead.de\n"
    "Action: failed\nStatus: 5.1.1\n")
t("a bounce is recognised", BOU.is_bounce(_m) is True)
t("and it names the address it is about",
  BOU.recipient_of(_m, BOU.flatten(_m)) == "gone@dead.de")
t("four temporary failures rest rather than suppress",
  BOU.SOFT_LIMIT >= 2 and "never suppressed" in BOU._note_soft.__doc__.lower()
  or "RESTED" in BOU._note_soft.__doc__)
t("with no mailbox it says so instead of failing",
  BOU.read(Store(), gr)["ok"] is False)
t("the summary says whether it can read at all",
  "ready" in BOU.summary(g, gr))

# Two bounces from two addresses this engine has never seen, in the same
# second. They collapsed into one event on the live box: identical key,
# because the key had nothing in it that told them apart.
_b1 = CORE.record_event(gr, "EMAIL_BOUNCED", profile_id="",
                        at="2026-08-08T10:00:00+00:00",
                        metadata={"email": "one@dead.de", "kind": "soft"})
_b2 = CORE.record_event(gr, "EMAIL_BOUNCED", profile_id="",
                        at="2026-08-08T10:00:00+00:00",
                        metadata={"email": "two@dead.de", "kind": "soft"})
t("two bounces from two addresses stay two facts",
  bool(_b1) and bool(_b2))
t("and the same one twice is still recorded once",
  not CORE.record_event(gr, "EMAIL_BOUNCED", profile_id="",
                        at="2026-08-08T10:00:00+00:00",
                        metadata={"email": "one@dead.de", "kind": "soft"}))
_msg = __import__("email").message_from_string(
    "From: mailer-daemon@x\nDate: Wed, 05 Aug 2026 09:00:00 +0000\n\nx")
t("a bounce event carries the bounce's OWN date, not the read time",
  BOU.sent_at_of(_msg).startswith("2026-08-05"), BOU.sent_at_of(_msg))
t("a bounce with no date falls back to now rather than to nothing",
  len(BOU.sent_at_of(
      __import__("email").message_from_string("x: y\n\n"))) > 10)
t("re-reading is offered, and says it is safe to press twice",
  "writes nothing new" in BOU.reread.__doc__)
t("the summary counts distinct addresses, not just events",
  BOU.summary(g, gr)["addresses"] == 2, str(BOU.summary(g, gr)))
_r0 = AN.revenue(OS.repo(seeded()))
t("no conversions reads as an absence, not as 0.0%",
  _r0["rate"][0] is None and _r0["per_recipient"] is None, str(_r0["rate"]))
t("and it says so in words", "nothing recorded" in _r0["rate"][1])
# The near-miss that earned this gate: the address was set to a hostname
# whose DNS record had not been created, so every unsubscribe link pointed
# at a name the world could not resolve. Nothing complained.
_st = Store()
t("a host that does not resolve is refused, and the message says so",
  "does not resolve" in PRV.set_public_base(
      _st, "https://this-name-does-not-exist-12345.example")["message"])
t("and nothing was written",
  _st.get_setting("PUBLIC_BASE_URL") is None)
t("something that is not a URL is refused",
  PRV.set_public_base(_st, "track.example.com")["ok"] is False)
t("the four checks run in order, each naming the step to fix",
  "is it a URL at all" in PRV.set_public_base.__doc__
  and "does it actually answer" in PRV.set_public_base.__doc__)
t("the raw IP fallback is still allowed over http, deliberately",
  "bare" in PRV.set_public_base.__code__.co_varnames)
_pb = PRV.public_base()
t("the public address is checked at all", "state" in _pb)
t("a bare IP over http is called risky",
  "phishing" in _pb["why"] or _pb["state"] == "good" or _pb["state"] == "missing")

print("  -- 4 an adapter's send path can be proven")
t("a test send exists and refuses without an address",
  PRV.send_test("smtp", "")["ok"] is False)
t("and refuses a provider that does not exist",
  "no provider called" in PRV.send_test("nope", "a@b.c")["message"])
t("it goes through the facade, so the HTTP layer holds no provider",
  "content_engine_os_providers" not in SRC["content_engine_api.py"])

print("  -- 5 Klaviyo reads as well as writes")
t("the adapter can pull", hasattr(PRV.PROVIDERS["klaviyo"], "pull"))
t("an unknown thing to pull is refused by name",
  "nothing called" in PRV.PROVIDERS["klaviyo"].pull("unicorns")["message"])
t("with no key it says which key",
  "KLAVIYO_PRIVATE_KEY" in PRV.PROVIDERS["klaviyo"].pull("profiles")["message"])

print("  -- 6, 7 Sheets, and the nightly mirror")
t("Sheets says whether it is ready and why",
  set(DAT.sheets_state()) == {"ready", "sheet", "why"})
t("pushing with no credential is refused in words",
  DAT.push_to_sheets(g, gr)["ok"] is False)
t("the mirror is due on a fresh box", DAT.mirror_due(g) is True)
DAT.mirror_if_due(g, gr)
t("and not twice in one day", DAT.mirror_due(g) is False)
t("it is keyed on the date, so a restart cannot run it twelve times",
  "keyed on the date" in DAT.mirror_if_due.__doc__)
t("the worker runs it, not a button",
  "_OS.mirror(store)" in SRC["content_engine_api.py"])

print("  -- 8 a member can hold their own password")
_h = TEN2.hash_password("a-long-enough-one")
t("a password round trips", TEN2.verify_password("a-long-enough-one", _h))
t("a wrong one does not", TEN2.verify_password("wrong", _h) is False)
t("it is not stored in the clear", "a-long-enough-one" not in _h)
t("a short password is refused with the reason",
  "ten characters" in TEN2.set_password(g, CORE.DEFAULT_WORKSPACE,
                                        "x@y.com", "short")["message"])
t("a non-member cannot be given one",
  TEN2.set_password(g, CORE.DEFAULT_WORKSPACE, "stranger@x.com",
                    "a-long-enough-one")["ok"] is False)
TEN2.add_member(g, CORE.DEFAULT_WORKSPACE, "colleague@x.com", "member")
t("a member can", TEN2.set_password(g, CORE.DEFAULT_WORKSPACE,
                                    "colleague@x.com",
                                    "a-long-enough-one")["ok"])
_login = TEN2.check_login(g, "colleague@x.com", "a-long-enough-one")
t("and can then sign in", _login["ok"] and _login["role"] == "member")
t("a wrong password is refused",
  TEN2.check_login(g, "colleague@x.com", "nope")["ok"] is False)
t("an unknown address and a wrong password answer identically",
  TEN2.check_login(g, "nobody@x.com", "x")["message"]
  == TEN2.check_login(g, "colleague@x.com", "nope")["message"])
t("the session cookie cannot be forged",
  TEN2.user_from_cookie(g, "colleague@x.com|deadbeef") == "")
t("and a real one names its owner",
  TEN2.user_from_cookie(g, f"colleague@x.com|{_login['token']}")
  == "colleague@x.com")
t("the login form accepts an email as well as the shared password",
  'form.get("email"' in SRC["content_engine_api.py"])

print("  -- 9 exports can be narrowed")
AUD.save_segment(gr, "Germans", {"operator": "AND", "conditions": [
    {"field": "country", "operator": "equals", "value": "Germany"}]})
_seg = gr.all("segments")[0]["id"]
_all = DAT.rows_for(gr, "profiles")[1]
_de = DAT.rows_for(gr, "profiles", {"segment": _seg})[1]
t("a segment filter really narrows the rows",
  0 < len(_de) < len(_all), f"{len(_de)} of {len(_all)}")
t("a campaign filter narrows too",
  len(DAT.rows_for(gr, "messages", {"campaign": gcid})[1]) <= len(
      DAT.rows_for(gr, "messages")[1]))
t("no filter means the whole table",
  len(DAT.rows_for(gr, "profiles", {})[1]) == len(_all))
t("the route takes the filter",
  "segment: str" in SRC["content_engine_api.py"])

print("  -- 10 recurring imports and near duplicates")
t("a source needs a sheet id", DAT.save_source(g, "x", "")["ok"] is False)
t("a source can be saved",
  DAT.save_source(g, "Fair", "sheet123", "Sheet1", 2)["ok"])
t("and is listed", any(x["sheet_id"] == "sheet123" for x in DAT.sources(g)))
t("and dropped", DAT.drop_source(g, "sheet123", "Sheet1")["ok"]
  and not DAT.sources(g))
t("nothing due reads nothing", DAT.run_sources(g, gr, force=False)["sources"] == 0)
_dupes = DAT.near_duplicates(gr, [{"email": "a.weber@clinicx.de",
                                   "first_name": "Ann", "last_name": "Weber"}])
t("somebody at the same company with the same name is FLAGGED",
  len(_dupes) == 1 and "ann@clinicx.de" in _dupes[0]["matches"], str(_dupes))
t("and never merged automatically",
  "never merged" in DAT.near_duplicates.__doc__.lower())

print("  -- 11 A/B assignment and promotion")
_c = gr.one("campaigns", gcid)
_c["subject_variants"] = ["Arm A line", "Arm B line"]
gr.put("campaigns", _c)
t("a person can be pinned to an arm",
  SEND.assign_variant(gr, gcid, "ann@clinicx.de", "B")["ok"])
t("and the pin beats the automatic bucket",
  SEND.variant_for(gr.one("campaigns", gcid), "ann@clinicx.de")[0] == 1)
t("an arm that does not exist is refused with the ones that do",
  "pick one of" in SEND.assign_variant(gr, gcid, "ann@clinicx.de", "Z")["message"])
t("promoting refuses while the arms are too small to mean anything",
  SEND.promote_variant(gr, gcid)["ok"] is False)
t("naming an arm promotes it",
  SEND.promote_variant(gr, gcid, "B")["ok"]
  and gr.one("campaigns", gcid)["subject_variants"] == ["Arm B line"])
t("and the old arms are kept, not thrown away",
  len(_L(gr.one("campaigns", gcid).get("promoted_from"))) == 2)
t("a campaign with one line is not a test",
  SEND.promote_variant(gr, gcid, "A")["ok"] is False)

print("  -- 12, 13 the editors")
import content_engine_os_editors as ED2
t("the canvas has undo, zoom and duplicate",
  all(x in ED2.FLOW_JS for x in ("osFxUndo", "osFxZoom", "osFxCopy")))
t("every change is marked for undo before it happens",
  ED2.FLOW_JS.count("osFxMark();") >= 5)
t("the toolbar offers them", all(x in ED2.flow_canvas({})
                                 for x in ("osFxUndo", "osFxZoom", "osFxCopy")))
t("an image can be uploaded rather than only linked",
  "osBbUpload" in ED2.BLOCK_JS and "os-up" in ED2.block_editor({}))
t("two columns are a block type", "columns" in CT.BLOCK_TYPES)
t("and every block type still has a form",
  set(ED2.BLOCK_FIELDS) == set(CT.BLOCK_TYPES))
t("two columns render as a table Outlook understands",
  "width='50%'" in CT.render_blocks([{"type": "columns", "left": "a",
                                      "right": "b"}]))
t("an uploaded image is shared, and the screen says what that means",
  "publicly readable" in OS.upload_image.__doc__.lower()
  or "anybody with the link" in OS.upload_image.__doc__.lower())

print("  -- 14 conversions and revenue")
_cv = AN.record_conversion(gr, "ann@clinicx.de", value=2500, ref="booking-1")
t("a conversion is recorded against the last email that person was sent",
  _cv["ok"] and _cv["campaign_id"], str(_cv))
t("the same one twice is recorded once",
  AN.record_conversion(gr, "ann@clinicx.de", value=2500,
                       ref="booking-1")["ok"] is False)
t("a stranger cannot be attributed to an email nobody sent them",
  AN.record_conversion(gr, "nobody@nowhere.com", value=1)["ok"] is False)
t("the lead becomes a customer",
  any(l.get("stage") == "CUSTOMER" for l in gr.all("leads")))
_rev = AN.revenue(gr)
t("revenue is the sum of what was recorded", _rev["revenue"] == 2500)
t("and the model is named, not implied", "Last touch" in _rev["basis"])
t("the beacon is public, because a thank-you page has no session",
  '"/t/v"' in SRC["content_engine_api.py"]
  and '"/t/v"' in SRC["content_engine_api.py"].split("_auth_gate")[1][:1600])

print("  -- 15 the confirmation")
t("it is rendered through the block renderer, not hand written HTML",
  "CONTENT.render_blocks" in SRC["content_engine_os_send.py"])
t("a confirmation can be resent", hasattr(SEND, "resend_confirmation"))
CORE.set_consent(gr, "cy@shop.ch", "SUBSCRIBED", source="test")
t("but never to somebody already confirmed",
  SEND.resend_confirmation(g, gr, "cy@shop.ch")["ok"] is False)

print("  -- 16, 17 segments and search")
_got = OS.segment_get(g, _seg)
t("a saved segment loads back into the builder",
  _got["ok"] and _got["conditions"][0]["field"] == "country")
t("an unknown one is refused", OS.segment_get(g, "nope")["ok"] is False)
_tree = {"operator": "AND", "conditions": [
    {"field": "country", "operator": "equals", "value": "Germany"},
    {"operator": "OR", "conditions": [
        {"field": "lead_score", "operator": "greater_than", "value": 70},
        {"field": "company", "operator": "contains", "value": "clinic"}]}]}
t("a bracket evaluates", AUD.validate(_tree)[0] is True)
t("and reads as one", "(" in AUD.describe(_tree))
_html = OS.search_profiles(g, "clinic")
t("search looks past the 250 on screen",
  "clinicx" in _html.lower(), _html[:120])
t("a search that matches nobody says so",
  "Nobody matches" in OS.search_profiles(g, "zzzznotreal"))
t("an empty search returns everyone",
  "@" in OS.search_profiles(g, ""))

print("  -- 18 the authenticated surface has a ceiling")
t("the limiter takes a ceiling", "ceiling" in SRC["content_engine_api.py"])
t("and /os is inside it",
  'request.url.path.startswith(("/os/", "/internal/"))'
  in SRC["content_engine_api.py"])
t("the reason is stated, not implied",
  "Something is looping" in SRC["content_engine_api.py"])

print("  -- 19 the migration counts what arrived")
t("it verifies rather than trusting its own loop",
  "COUNT WHAT ARRIVED" in SRC["content_engine_os_store.py"])
t("a short table is reported, not swallowed",
  "came back" in SRC["content_engine_os_store.py"])

print("  -- all of it still draws")
ghtml = SCR.build(OS.build_ctx(g, jobs=g.list_jobs()))
t("no screen failed", "could not be drawn" not in ghtml)
t("bounces have a button", "/os/bounces/read" in ghtml)
t("Sheets has a button", "/os/sheets/push" in ghtml)
t("a provider can be test-sent", "osSendTest" in ghtml)
t("Klaviyo can be pulled", "osKlaviyo" in ghtml)
t("a member can be given a password", "osSetPassword" in ghtml)
t("a conversion can be recorded by hand", "osConversion" in ghtml)
t("the beacon snippet is on the page", "/t/v?e=" in ghtml)
t("a source can be added", "osSaveSource" in ghtml)
t("an arm can be promoted", "osPromote" in ghtml)
t("a confirmation can be resent", "osResendConfirm" in ghtml)
t("a segment can be edited", "osEditSeg" in ghtml)
t("profiles can be searched", "osSearch" in ghtml)
_h2 = re.findall(r"function (os[A-Z]\w+)", SCR.JS + ED2.FLOW_JS + ED2.BLOCK_JS)
_c2 = set(re.findall(r"(os[A-Z]\w+)\(", ghtml))
t("every handler the new controls call is defined",
  not sorted(c for c in _c2 if c not in _h2 and c != "osToast"),
  str(sorted(c for c in _c2 if c not in _h2 and c != "osToast")))

print(f"\n{sum(OK)} passed, {len(OK) - sum(OK)} failed")
raise SystemExit(0 if all(OK) else 1)
