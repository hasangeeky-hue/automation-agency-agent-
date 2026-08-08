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
import content_engine_os_bounce as BOUNCE
import content_engine_os_data as DATA
import content_engine_os_flows as FLOWS
import content_engine_os_optin as OPTIN
import content_engine_os_providers as PROV
import content_engine_os_schedule as SCHED
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


def repo(store, workspace_id=CORE.DEFAULT_WORKSPACE):
    """THE factory. Returns the table-backed repository when Postgres is
    reachable and the settings-backed one when it is not, with the same six
    methods either way. Every OS caller goes through here, so switching
    backends is one function rather than forty call sites."""
    import content_engine_os_store as ST
    return ST.repo_for(store, workspace_id)


def sync(store, jobs=None, reply_drafts=None,
         workspace_id=CORE.DEFAULT_WORKSPACE) -> dict:
    """Project the engine into the OS, then rebuild the daily rollup."""
    import content_engine_os_tenancy as TEN
    TEN.ensure_home(store)
    out = CORE.project(store, jobs, workspace_id=workspace_id,
                       reply_drafts=reply_drafts, repo=repo(store, workspace_id))
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
    """Everything the twenty seven screens read. One assembly, one pass."""
    import content_engine_os_store as ST
    import content_engine_os_tenancy as TEN
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
        "public_base": safe(PROV.public_base, {}),
        # -- the second pass: rules, people, storage, replies -------------
        "replies": _L(reply_drafts),
        "schedule": safe(lambda: SCHED.describe(store), {}),
        "workspaces": safe(lambda: TEN.workspaces_for(store), []),
        "members": safe(lambda: TEN.members(store, workspace_id), []),
        "backend": safe(lambda: ST.backend(), {}),
        "table_counts": safe(lambda: ST.counts(workspace_id), {}),
        "connectors": safe(_connector_state, {}),
        "hygiene": safe(lambda: AN.hygiene(r), {}),
        "datasets": safe(lambda: DATA.catalogue(r), []),
        "drive": safe(DATA.drive_state, {}),
        "drive_last": safe(lambda: DATA.drive_last(store), {}),
        "sheets": safe(DATA.sheets_state, {}),
        "sheets_last": safe(lambda: DATA.sheets_last(store), {}),
        "sources": safe(lambda: DATA.sources(store), []),
        "bounces": safe(lambda: BOUNCE.summary(store, r), {}),
        "revenue": safe(lambda: AN.revenue(r), {}),
        "logins": safe(lambda: TEN.people_with_logins(store, workspace_id), {}),
    }


def _connector_state() -> dict:
    """Which outside services are reachable, asked rather than remembered."""
    try:
        import content_engine_connectors as C
        return {"serper": bool(C._env("SERPER_API_KEY")),
                "prospeo": bool(C._env("PROSPEO_API_KEY")),
                "public_base": bool(C._env("PUBLIC_BASE_URL")
                                    or C._env("ENGINE_PUBLIC_URL"))}
    except Exception:
        return {}


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
    variants = AN.variant_rows(r, cid)
    ctx = {"campaigns": AN.campaign_rows(r),
           "messages": AN.message_rows(r, cid),
           "detail_totals": AN.totals(r, cid),
           "detail_links": AN.link_rows(r, cid),
           "detail_curve": AN.open_curve(r, cid),
           "detail_variants": variants,
           "detail_verdict": AN.ab_verdict(variants)}
    who = str(email or "").strip().lower()
    if not who and ctx["messages"]:
        who = ctx["messages"][0].get("email")
        touch = ctx["messages"][0].get("touch") or 1
    ctx["detail_preview"] = preview(store, cid, who, touch, jobs=jobs)
    ctx["detail_checks"] = preflight(ctx["detail_preview"])
    return SCR.campaign_detail(ctx, cid)


def preflight(prev) -> dict:
    """The link audit and the spam signals, for the email actually resolved.

    These checks existed before and had nothing real to read: they were
    pointed at a preview that never resolved. They now run on the exact
    bytes the transport is handed."""
    prev = _D(prev)
    if not prev.get("ok"):
        return {}
    try:
        import content_engine_email_preview as EP
        import content_engine_connectors as C
        base = (C._env("PUBLIC_BASE_URL") or C._env("ENGINE_PUBLIC_URL") or "")
        sig = EP.spam_signals(prev.get("subject"), prev.get("html"))
        links = EP.links(prev.get("html"), base)
        empties = EP.resolve(prev.get("subject", "") + " "
                             + str(prev.get("body", "")), prev.get("lead"))[1]
        return {"signals": sig, "links": links,
                "failing": [x["name"] for x in sig if not x["ok"]],
                "blocking": bool(empties),
                "block_reason": ("This would send with "
                                 + ", ".join("{{" + t + "}}" for t in empties[:4])
                                 + " empty. Fill the field on those leads, or "
                                   "remove the token." if empties else "")}
    except Exception as ex:
        log.warning("preflight unavailable: %s", ex)
        return {}


def template_html(store, tid) -> str:
    """One template, in the drag editor."""
    r = repo(store)
    return SCR.ED.block_editor(r.one("templates", tid) or {"id": tid})


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


# ---------------------------------------------------------------------------
# THE REST OF THE ACTIONS
# ---------------------------------------------------------------------------
def save_rules(store, from_hour, to_hour, weekdays_only, hourly) -> dict:
    a = SCHED.set_window(store, from_hour, to_hour, weekdays_only)
    if not a.get("ok"):
        return a
    b = SCHED.set_hourly_cap(store, hourly)
    return {"ok": bool(b.get("ok")),
            "message": a["message"] + ", and " + str(b.get("message"))}


def render_blocks(blocks) -> dict:
    """The preview inside the email builder, drawn by the SAME renderer the
    sender uses. A preview built by different code is a decoration."""
    return {"ok": True, "html": CONTENT.render_blocks(blocks)}


def migrate(store, workspace_id=CORE.DEFAULT_WORKSPACE) -> dict:
    import content_engine_os_store as ST
    return ST.migrate(store, workspace_id)


def drain(store, jobs=None) -> dict:
    """The worker's entry point into the OS queue."""
    return SEND.drain(store, jobs=jobs)


def public(store, action, params=None, *, ip="") -> dict:
    """The opt-in surface, kept behind one function so the HTTP layer never
    reaches into the consent module directly."""
    p = _D(params)
    if action == "signup":
        return OPTIN.signup(store, p.get("email"), source=p.get("source", ""),
                            ip=ip, name=p.get("name", ""),
                            company=p.get("company", ""))
    if action == "confirm":
        return OPTIN.confirm(store, p.get("email"), p.get("t"), ip=ip)
    if action == "unsubscribe":
        if p.get("t"):
            return OPTIN.unsubscribe(store, p.get("email"), p.get("t"), ip=ip)
        # No token: an older email, whose link never named anybody.
        return OPTIN.unsubscribe_self(store, p.get("email"), ip=ip)
    return {"ok": False, "message": f"no public action called {action!r}"}


def test_provider(name) -> dict:
    """Prove a provider's key. Routed through the facade so the HTTP layer
    never imports the provider module, which a gate enforces."""
    return PROV.test_provider(name)


def send_test(name, to_addr) -> dict:
    """One real email through one adapter. Through the facade, so the HTTP
    layer never imports a provider, which a gate enforces."""
    return PROV.send_test(name, to_addr)


def register_webhook(name) -> dict:
    return PROV.register_provider_webhook(name)


# ---------------------------------------------------------------------------
# LIST HYGIENE ACTIONS
# ---------------------------------------------------------------------------
def rest_person(store, email, days=90, wake=False,
                workspace_id=CORE.DEFAULT_WORKSPACE) -> dict:
    r = repo(store, workspace_id)
    return CORE.wake(r, email) if wake else CORE.rest(r, email, days,
                                                      "rested by hand")


def clean_audience(store, kind="silent", days=90,
                   workspace_id=CORE.DEFAULT_WORKSPACE) -> dict:
    """Rest a whole group at once. Never suppresses, never deletes.

    The groups come from AN.hygiene, so what this rests is exactly what the
    table above the button was showing: there is no second definition of
    "silent" hiding in here."""
    r = repo(store, workspace_id)
    h = AN.hygiene(r)
    group = _L(h.get(kind))
    if not group:
        return {"ok": True, "rested": 0,
                "message": f"nobody is in the {kind} group right now"}
    n = 0
    for row in group:
        if row.get("resting") == "yes":
            continue
        if CORE.rest(r, row.get("email"), days, row.get("why", "")).get("ok"):
            n += 1
    return {"ok": True, "rested": n,
            "message": (f"{n} person(s) rested for {days} days. They are not "
                        f"suppressed: they stay in every count and you can "
                        f"wake any of them from this table.")}


# ---------------------------------------------------------------------------
# DATA IN AND OUT
# ---------------------------------------------------------------------------
def export(store, name, fmt, workspace_id=CORE.DEFAULT_WORKSPACE,
           flt=None) -> tuple:
    """(filename, mime, bytes). One door for every download."""
    r = repo(store, workspace_id)
    if name == "workbook":
        return DATA.workbook(r)
    if name == "everything":
        return DATA.everything_json(r)
    if name not in DATA.DATASETS:
        raise KeyError(name)
    return DATA.as_bytes(r, name, fmt if fmt in ("csv", "json") else "xlsx",
                         flt)


def import_preview(store, filename, data, mapping=None,
                   workspace_id=CORE.DEFAULT_WORKSPACE) -> dict:
    return DATA.preview(repo(store, workspace_id), filename, data, mapping)


def import_commit(store, filename, data, mapping=None, list_name="",
                  workspace_id=CORE.DEFAULT_WORKSPACE) -> dict:
    return DATA.commit(store, repo(store, workspace_id), filename, data,
                       mapping, list_name=list_name)


def drive_push(store, workspace_id=CORE.DEFAULT_WORKSPACE) -> dict:
    return DATA.push_to_drive(store, repo(store, workspace_id))


def import_preview_html(pv) -> dict:
    """The preview, as the fragment the Import screen injects."""
    return SCR.import_preview(pv)


# ---------------------------------------------------------------------------
# THE REMAINING ACTIONS
# ---------------------------------------------------------------------------
def read_bounces(store, workspace_id=CORE.DEFAULT_WORKSPACE) -> dict:
    return BOUNCE.read(store, repo(store, workspace_id))


def sheets_push(store, workspace_id=CORE.DEFAULT_WORKSPACE) -> dict:
    return DATA.push_to_sheets(store, repo(store, workspace_id))


def mirror(store, workspace_id=CORE.DEFAULT_WORKSPACE) -> dict:
    """Once a day, from the worker. Drive and Sheets together."""
    return DATA.mirror_if_due(store, repo(store, workspace_id))


def source_save(store, name, sheet_id, tab, every_days) -> dict:
    return DATA.save_source(store, name, sheet_id, tab, every_days)


def source_drop(store, sheet_id, tab) -> dict:
    return DATA.drop_source(store, sheet_id, tab)


def source_run(store, workspace_id=CORE.DEFAULT_WORKSPACE, force=True) -> dict:
    return DATA.run_sources(store, repo(store, workspace_id), force=force)


def klaviyo_pull(store, what="profiles",
                 workspace_id=CORE.DEFAULT_WORKSPACE) -> dict:
    """Read out of a connected Klaviyo account. Profiles are imported;
    anything else is reported so you can see what is there before this
    engine starts copying it."""
    out = PROV.PROVIDERS["klaviyo"].pull(what)
    if not out.get("ok") or what != "profiles":
        return out
    import content_engine_os_agents as AGT
    n = 0
    for row in _L(out.get("rows")):
        if not CORE.valid_email(_D(row).get("email")):
            continue
        got = AGT.call(store, "klaviyo_import", "leads.upsert",
                       {"email": row.get("email"),
                        "first_name": row.get("first_name"),
                        "last_name": row.get("last_name"),
                        "company": row.get("organization"),
                        "job_title": row.get("title"),
                        "phone": row.get("phone_number"),
                        "source": "klaviyo"}, workspace_id=workspace_id)
        n += 1 if got.get("ok") else 0
    out["imported"] = n
    out["message"] = f"{len(_L(out.get('rows')))} read from Klaviyo, {n} written"
    return out


def upload_image(store, filename, data) -> dict:
    """Put an image where a mail client can fetch it.

    Drive, with link sharing, because an image in an email MUST be
    publicly readable to render at all. That is stated rather than done
    quietly: anybody with the link can see this picture."""
    st = DATA.drive_state()
    if not st["ready"]:
        return {"ok": False, "message": st["why"]}
    if len(data) > 4 * 1024 * 1024:
        return {"ok": False, "message": "images must be under 4 MB"}
    import content_engine_connectors as C
    kind = ("image/png" if str(filename).lower().endswith(".png")
            else "image/gif" if str(filename).lower().endswith(".gif")
            else "image/jpeg")
    ref = DATA.save_file(C.GoogleDrive(), filename, data, kind)
    if not ref:
        return {"ok": False, "message": "Drive refused the upload"}
    fid = ref.rsplit("/d/", 1)[-1].split("/")[0] if "/d/" in ref else \
        ref.replace("drive:", "")
    try:
        token = C._google_token([C._GDRIVE_SCOPE])
        rq = C._requests()
        rq.post(f"https://www.googleapis.com/drive/v3/files/{fid}/permissions",
                headers={"Authorization": f"Bearer {token}"}, timeout=30,
                json={"role": "reader", "type": "anyone"})
    except Exception as ex:
        log.warning("could not share the image: %s", ex)
    return {"ok": True, "url": f"https://drive.google.com/uc?export=view&id={fid}",
            "message": "uploaded. Anyone with the link can see this image, "
                       "which is what makes it render in an inbox."}


def search_profiles(store, q, workspace_id=CORE.DEFAULT_WORKSPACE) -> str:
    """ITEM 17. Search every profile, not only the ones on screen."""
    import content_engine_os_audience as _AUD
    q = str(q or "").strip().lower()
    rows = AN.profile_rows(repo(store, workspace_id), limit=100000)
    if q:
        rows = [r for r in rows
                if q in " ".join(str(r.get(k) or "").lower() for k in
                                 ("email", "first_name", "last_name",
                                  "company", "country", "city", "industry",
                                  "job_title"))]
    for r in rows:
        r["name"] = " ".join(x for x in [r.get("first_name"),
                                         r.get("last_name")] if x) or r.get("email")
    return SCR.profile_table(rows[:250])


def segment_get(store, seg_id, workspace_id=CORE.DEFAULT_WORKSPACE) -> dict:
    """ITEM 16. Load a saved segment back into the builder."""
    seg = repo(store, workspace_id).one("segments", seg_id)
    if not seg:
        return {"ok": False, "message": "no such segment"}
    tree = _D(seg.get("tree"))
    return {"ok": True, "id": seg_id, "name": seg.get("name"),
            "match": tree.get("operator", "AND"),
            "conditions": _L(tree.get("conditions")),
            "described": seg.get("described", "")}
