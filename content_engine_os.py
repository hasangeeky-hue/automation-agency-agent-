"""
content_engine_os.py
============================================================================
THE FACADE. One import for the dashboard and one for the HTTP layer.

Everything above this line is domain logic with no idea a web page exists.
Everything below it is a screen with no idea how a database works. This
file is the only place the two meet: it projects the live engine into the
OS, assembles the context the screens read, and hands back HTML.

WHY THE PROJECTION RUNS ON RENDER
  The founder's real campaigns live in job payloads written by the older
  outreach code, which is still the code that sends. Rather than migrate
  (and own two truths), the OS re-reads those jobs every time the page is
  drawn. Ids are content derived and events are keyed, so the second pass
  writes nothing new. The result is an OS that opens full of his own data
  and cannot drift from the engine that produced it.
============================================================================
"""

from __future__ import annotations

import logging

import content_engine_os_analytics as AN
import content_engine_os_audience as AUD
import content_engine_os_content as CONTENT
import content_engine_os_core as CORE
import content_engine_os_flows as FLOWS
import content_engine_os_providers as PROV
import content_engine_os_screens as SCR
import content_engine_os_send as SEND
from content_engine_os_core import _D, _L, Repo

log = logging.getLogger("content_engine.os")

#: Fields whose absence makes a personalisation token render empty, with
#: the consequence spelled out. The Enrichment screen reads this.
FIELD_GAPS = {
    "first_name": "a missing first name renders \"Hi ,\" to a real person",
    "company": "a missing company empties the most common token in your copy",
    "job_title": "without a role the opening line cannot be specific",
    "country": "without a country nothing can be scheduled to their morning",
    "website": "without a site the research agent has nothing to read",
}


def repo(store, workspace_id=CORE.DEFAULT_WORKSPACE) -> Repo:
    return Repo(store, workspace_id)


def sync(store, jobs=None, reply_drafts=None,
         workspace_id=CORE.DEFAULT_WORKSPACE) -> dict:
    """Project the engine into the OS, then rebuild the daily rollup."""
    out = CORE.project(store, jobs, workspace_id=workspace_id,
                       reply_drafts=reply_drafts)
    r = repo(store, workspace_id)
    FLOWS.ensure_default(r)
    roll = AN.rollup(r)
    out["rollup_rows"] = roll.get("rows")
    out["message"] = (f"{out['profiles']} profile(s), {out['campaigns']} "
                      f"campaign(s), {out['messages']} message(s) and "
                      f"{out['events']} new event(s) read from the engine")
    return out


def build_ctx(store, *, jobs=None, reply_drafts=None,
              workspace_id=CORE.DEFAULT_WORKSPACE, do_sync=True) -> dict:
    """Everything the twenty two screens read. One assembly, one pass."""
    r = repo(store, workspace_id)
    if do_sync:
        try:
            sync(store, jobs, reply_drafts, workspace_id)
        except Exception as ex:
            log.warning("os sync skipped: %s", ex)

    def safe(fn, dflt):
        try:
            return fn()
        except Exception as ex:
            log.warning("os ctx piece failed (%s): %s", getattr(fn, "__name__", "?"), ex)
            return dflt

    profiles = safe(lambda: AN.profile_rows(r), [])
    companies = {}
    for p in profiles:
        nm = p.get("company")
        if nm:
            c = companies.setdefault(nm, {"name": nm, "people": 0,
                                          "website": p.get("website"),
                                          "country": p.get("country")})
            c["people"] += 1
    gaps = {}
    for f, why in FIELD_GAPS.items():
        gaps[f] = {"missing": len([p for p in profiles if not p.get(f)]),
                   "why": why}
    return {
        "workspace_id": workspace_id,
        "summary": safe(lambda: CORE.summary(r), {}),
        "acquisition": safe(lambda: AN.acquisition(r), {}),
        "campaigns": safe(lambda: AN.campaign_rows(r), []),
        "totals": safe(lambda: AN.totals(r), {}),
        "by_day": safe(lambda: AN.by_day(r), []),
        "links": safe(lambda: AN.link_rows(r), []),
        "open_curve": safe(lambda: AN.open_curve(r), []),
        "profiles": profiles,
        "companies": sorted(companies.values(), key=lambda c: -c["people"]),
        "field_gaps": gaps,
        "segments": safe(lambda: AUD.segment_rows(r), []),
        "lists": safe(lambda: AUD.list_rows(r), []),
        "templates": safe(lambda: CONTENT.template_rows(r), []),
        "flows": safe(lambda: FLOWS.flow_rows(r), []),
        "queue_rows": safe(lambda: SEND.queue_rows(r), []),
        "queue_counts": safe(lambda: SEND.queue_counts(r), {}),
        "deliverability": safe(lambda: AN.deliverability(r), {}),
        "agent_runs": safe(lambda: AN.agent_rows(r), []),
        "providers": safe(lambda: PROV.provider_rows(), []),
        "domains": safe(lambda: PROV.domain_rows(r), []),
        "sender_why": safe(lambda: PROV.sending_allowed(r)[1], ""),
    }


def section(store, *, jobs=None, reply_drafts=None, live=None,
            legacy_ctx=None) -> str:
    """The whole Leads and Outreach section, for the old dashboard."""
    ctx = build_ctx(store, jobs=jobs, reply_drafts=reply_drafts)
    ctx["attribution"] = _D(_D(legacy_ctx).get("attribution"))
    return SCR.build(ctx, live=live)


# ---------------------------------------------------------------------------
# DETAIL VIEWS
# ---------------------------------------------------------------------------
def campaign_html(store, cid, *, jobs=None, email="", touch=1) -> str:
    r = repo(store)
    ctx = {"campaigns": AN.campaign_rows(r),
           "messages": AN.message_rows(r, cid),
           "detail_totals": AN.totals(r, cid),
           "detail_links": AN.link_rows(r, cid),
           "detail_curve": AN.open_curve(r, cid)}
    who = str(email or "").strip().lower()
    if not who and ctx["messages"]:
        who = ctx["messages"][0].get("email")
        touch = ctx["messages"][0].get("touch") or 1
    ctx["detail_preview"] = preview(store, cid, who, touch, jobs=jobs)
    return SCR.campaign_detail(ctx, cid)


def preview(store, cid, email, touch=1, *, jobs=None) -> dict:
    """THE RESOLUTION THE LAST BUILD GOT WRONG.

    It reads through content_engine_os_content.resolve_email, which is the
    engine's own send path: the founder's manual edit if there is one, the
    agent's copy otherwise, rendered by the same compose_outreach the
    transport uses. Not a field guessed off a payload."""
    r = repo(store)
    c = r.one("campaigns", cid) or {}
    who = str(email or "").strip().lower()
    if not who:
        return {"ok": False, "message": "pick a recipient first"}
    jid = c.get("job_id")
    if jid:
        job = None
        for j in _L(jobs):
            if str(_D(j).get("job_id")) == str(jid):
                job = j
                break
        if job is None:
            try:
                job = store.get(jid)
            except Exception:
                job = None
        if job:
            out = CONTENT.rendered_message(job, who, int(touch or 1))
            if out.get("ok"):
                out["email"] = who
                out["from_name"] = _from_name()
                return out
            return {"ok": False, "email": who,
                    "message": out.get("error") or "that lead is not on this "
                                                   "campaign any more"}
    person = next((p for p in AUD.people(r)
                   if p.get("email") == who), {})
    out = SEND.message_for(r, c, person, int(touch or 1), jobs=jobs)
    out["email"] = who
    out["from_name"] = _from_name()
    if not out.get("ok"):
        out["message"] = ("this campaign has no copy on it yet, so there is "
                          "nothing to render for anyone")
    return out


def _from_name() -> str:
    try:
        import content_engine_connectors as C
        return C._env("EMAIL_FROM_NAME", "") or C._env("EMAIL_FROM", "")
    except Exception:
        return ""


def profile_html(store, pid) -> str:
    r = repo(store)
    person = next((p for p in AUD.people(r) if p.get("id") == pid), None)
    ctx = {"detail_profile": person or {},
           "detail_timeline": CORE.timeline(r, pid) if person else [],
           "detail_props": CORE.properties_of(r, pid) if person else {}}
    return SCR.profile_detail(ctx, pid)


# ---------------------------------------------------------------------------
# WRITE ACTIONS, one per button. Thin: the rules live in the engines.
# ---------------------------------------------------------------------------
def check_domain(store, domain, selector="") -> dict:
    """Read a sender domain's DNS. Routed through the facade on purpose:
    the HTTP layer must not import the provider module at all, and a gate
    in verify_os.py fails the build if it does."""
    return PROV.save_domain(repo(store), domain, selector)


def save_edit(store, cid, email, touch, subject, body) -> dict:
    """Write the founder's correction where the SENDER reads it.

    Not a new store: payload.email_edits is the record resolve_email()
    consults first, so saving here changes what leaves the building."""
    r = repo(store)
    c = r.one("campaigns", cid) or {}
    jid = c.get("job_id")
    if not jid:
        c["subject"] = subject
        c["body"] = body
        r.put("campaigns", c)
        return {"ok": True, "message": "saved on the campaign"}
    import content_engine_api as A
    out = A.api_outreach_edit(jid, email, subject, body, int(touch or 1),
                              store=store)
    if out.get("ok"):
        out["message"] = (f"saved. {email} now receives exactly this at step "
                          f"{int(touch or 1)}, and so does the preview.")
    return out
