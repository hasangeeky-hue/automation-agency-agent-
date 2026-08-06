"""
content_engine_media_screens.py
============================================================================
THE MEDIA BUYING SCREENS. Sixteen panels replacing 296 cards: the agent
band, four real ad-platform managers, the Tag Manager and tracking layer,
and the queues - every verdict with its evidence, every push behind you.

RENDERER ONLY. This module draws. It does not fetch, spend, publish or
write. The buttons land on endpoints; the endpoints land on the one
dispatch; the dispatch refuses what is not approved.

It reuses the SEO screens' CSS grammar (s2*/s3* classes) so the two
sections wear the same clothes, and content_engine_media_platforms for the
platform managers. All element ids are scoped "mm-" because the old
dashboard renders every panel at once - the 66-duplicate-id lesson,
pre-applied.
============================================================================
"""

from __future__ import annotations

import html as _html

import content_engine_media_orders as MO
import content_engine_media_platforms as MP
import content_engine_gtm as GTM


def e(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


def _n(v, unit=""):
    if v in (None, ""):
        return "<b class='s2nonebig' style='font-size:20px'>--</b>"
    try:
        f = float(v)
        s = f"{f:,.0f}" if abs(f) >= 100 or f == int(f) else f"{f:,.2f}"
    except Exception:
        s = str(v)
    return f"<b>{e(s)}</b>" + (f"<span class='s3d'>{e(unit)}</span>" if unit else "")


def _open_orders(ctx):
    return [o for o in (ctx.get("media_orders") or ()) if o.get("status") == "open"]


# ---------------------------------------------------------------------------
# THE AGENT BAND
# ---------------------------------------------------------------------------
def agent_band(ctx: dict) -> str:
    level = str(ctx.get("media_auto_level") or "unknown").lower()
    verd = ctx.get("media_verdicts") or {}
    n_v = len(verd.get("verdicts") or ())
    blind = verd.get("blind") or []
    orders = _open_orders(ctx)
    word = {"off": "OFF - pulls run, the agent stays silent",
            "observe": "OBSERVE 24/7 - judging, writing verdicts, drafting nothing",
            "propose": "PROPOSE - verdicts become drafts in the queue",
            }.get(level, "switch state could not be read")

    def _lvl(lv, lab):
        on = " s3on" if level == lv else ""
        return (f"<button class='s3lvl{on}' "
                f"onclick=\"mediaAutoSet('{lv}',this)\">{lab}</button>")

    return (
        "<div class='s3band'>"
        "<div class='s3who'><p class='s3k'>Your media buying agent</p>"
        f"<p class='s3state'><b>{e(word)}</b>"
        + (f" &middot; last verdicts {e(str(verd.get('at'))[:16])}"
           if verd.get("at") else " &middot; no verdict run recorded yet")
        + "</p>"
        f"<p class='s3sub'>{n_v} verdict(s) standing &middot; "
        f"{len(orders)} draft(s) waiting for your approval"
        + (f" &middot; blind on {len(blind)} rule(s): "
           + "; ".join(e(b) for b in blind[:2]) if blind else "")
        + ". Nothing spends without your click; there is no auto-spend "
          "level at all.</p></div>"
        "<div class='s3cmds'>"
        "<button class='cta s3go' onclick=\"act('/ads/pull')\">Pull "
        "platforms now</button>"
        "<button class='cta' onclick=\"act('/ads/interlock')\">Rebuild "
        "interlock</button>"
        "<button class='cta a2draft' onclick=\"mediaOptimize(this)\">Run the "
        "rules now</button>"
        "</div>"
        "<div class='s3ladder' role='group' aria-label='media agent level'>"
        + _lvl("off", "OFF") + _lvl("observe", "OBSERVE")
        + _lvl("propose", "PROPOSE") + "</div></div>")


def _verdict_rows(ctx, limit=5) -> str:
    verd = (ctx.get("media_verdicts") or {}).get("verdicts") or []
    if not verd:
        return ("<p class='s2empty'>No verdicts standing. Either every rule "
                "is satisfied or the agent has not run; the band above says "
                "which, and which rules are blind.</p>")
    rows = []
    for v in verd[:limit]:
        ev = v.get("evidence") or {}
        rows.append(
            f"<div class='s3fx'><span class='s2sev s2bad'>"
            f"{e(v.get('code', '').replace('_', ' '))[:16]}</span>"
            f"<span class='s3fxn'>{e(v.get('say'))[:80]}</span>"
            f"<span class='s3fxw'>{e(ev.get('metric'))} vs "
            f"{e(ev.get('threshold'))} over {e(ev.get('window'))} "
            f"[{e(ev.get('source'))}]</span></div>")
    more = len(verd) - limit
    return ("".join(rows)
            + (f"<p class='s2more'>and {more} more in Work Orders</p>"
               if more > 0 else ""))


# ---------------------------------------------------------------------------
# THE SIXTEEN PANELS
# ---------------------------------------------------------------------------
def cmd_screen(ctx) -> str:
    ads = (ctx.get("ads") or {})
    econ = ctx.get("econ") or {}
    spend = ads.get("spend")
    conv = ads.get("conversions")
    cpa = (float(spend) / float(conv)) if spend and conv else None
    tiles = (
        "<div class='s3stats'>"
        "<div class='s3stat'><span class='s3k'>Spend &middot; 30d</span>"
        + _n(spend, "&euro;") + "</div>"
        "<div class='s3stat'><span class='s3k'>Conversions</span>"
        + _n(conv) + "</div>"
        "<div class='s3stat'><span class='s3k'>Blended CPA</span>"
        + _n(round(cpa, 2) if cpa else None, "&euro;") + "</div>"
        "<div class='s3stat'><span class='s3k'>CPA target</span>"
        + _n((ctx.get("targets") or {}).get("target_cpa_lead")
             or econ.get("target_cpa"), "&euro;") + "</div></div>")
    why = ""
    if ads.get("reason"):
        why = (f"<div class='s3banner'>{e(ads['reason'])[:220]}</div>")
    return (agent_band(ctx) + why + tiles
            + "<p class='s3k' style='margin-top:14px'>The agent's standing "
              "verdicts</p>" + _verdict_rows(ctx))


def health_screen(ctx) -> str:
    rows = []
    for pid in MP.ORDER:
        p = MP.PLATFORMS[pid]
        live = MP.is_connected(pid)
        col = "var(--okc)" if live else "var(--ft)"
        word = "connected" if live else ("ads API not wired" if not p["connector"]
                                         else "not authorised")
        rows.append(f"<div class='s3fx'><span class='s3fxn'><b>{e(p['name'])}"
                    f"</b></span><span class='s3fxw'>{word}</span>"
                    f"<span class='shp-state' style='color:{col}'>"
                    f"<i style='background:{col};width:8px;height:8px;"
                    f"border-radius:50%;display:inline-block'></i></span></div>")
    g = ctx.get("gtm_audit") or {}
    gtm_word = ("granted, audited " + str(g.get("at"))[:16] if g.get("ready")
                else "not granted yet - steps on the Tracking tab")
    rows.append(f"<div class='s3fx'><span class='s3fxn'><b>Google Tag "
                f"Manager</b></span><span class='s3fxw'>{e(gtm_word)}</span>"
                f"</div>")
    rows.append("<div class='s3fx'><span class='s3fxn'><b>GA4 + Search "
                "Console</b></span><span class='s3fxw'>the agent's eyes; "
                "live via your service account</span>"
                "<span class='shp-state' style='color:var(--okc)'>"
                "<i style='background:var(--okc);width:8px;height:8px;"
                "border-radius:50%;display:inline-block'></i></span></div>")
    snap_at = (ctx.get("at") or "")
    return ("<p class='s3k'>Every wire, tested rather than assumed</p>"
            + "".join(rows)
            + f"<p class='s2empty'>Last platform pull: "
              f"{e(snap_at) or 'none on record'}. "
              f"<button class='cta' onclick=\"act('/ads/test')\">Test the "
              f"Google wire</button></p>")


def platform_screen_for(pid, ctx) -> str:
    return MP.platform_screen(pid, {"campaigns": (ctx.get("ads") or {}).get("campaigns") or []})


def meta_screen(ctx) -> str:
    return (platform_screen_for("facebook", ctx)
            + "<div style='height:18px'></div>"
            + platform_screen_for("instagram", ctx))


def tracking_screen(ctx) -> str:
    """Tag Manager + the tracking law: the measurement floor, honest."""
    g = ctx.get("gtm_audit") or {}
    parts = []
    if not g.get("ready"):
        steps = "".join(f"<div class='s3chk'><i class='q'>{i + 1}</i>{e(s)}"
                        f"</div>"
                        for i, s in enumerate((g.get("steps") or
                                               GTM.readiness_steps())[:3]))
        parts.append("<div class='s3banner'>Tag Manager is not granted yet. "
                     "Until it is, the engine cannot see or create tags, and "
                     "says so instead of guessing.</div>"
                     "<div class='s3panel'><p class='s3k'>The one-time steps"
                     f"</p>{steps}"
                     "<button class='cta' style='margin-top:8px' "
                     "onclick=\"act('/gtm/audit')\">Re-check now</button>"
                     "</div>")
    else:
        def dot(state, word):
            col = {"ok": "var(--okc)", "bad": "var(--bad)",
                   "warn": "var(--warnc)"}[state]
            return (f"<span class='shp-state' style='color:{col}'>"
                    f"<i style='background:{col};width:7px;height:7px;"
                    f"border-radius:50%;display:inline-block'></i>{word}</span>")
        rows = []
        present = {p["tag"] for p in g.get("present") or []}
        missing = {m["tag"] for m in g.get("missing") or []}
        silent = {s["tag"] for s in g.get("silent") or []}
        for name, (_t, channel, why) in GTM.TAG_REGISTRY.items():
            if name in missing:
                st = dot("bad", "missing")
                act_btn = (f"<button class='cta a2draft' "
                           f"onclick=\"gtmDraft('{e(name)}',this)\">Draft it"
                           f"</button>")
            elif name in silent:
                st = dot("warn", "silent 7d")
                act_btn = ""
            elif name in present:
                st = dot("ok", "live")
                act_btn = ""
            else:
                st = dot("warn", "paused")
                act_btn = ""
            rows.append(f"<div class='s3fx'><span class='s3fxn'><b>{e(name)}"
                        f"</b> <i class='s3prop'>{e(channel)}</i></span>"
                        f"<span class='s3fxw'>{e(why)}</span>{st}"
                        f"<span class='s2act'>{act_btn}</span></div>")
        parts.append(f"<p class='s3k'>The container vs the registry &middot; "
                     f"audited {e(str(g.get('at'))[:16])}</p>" + "".join(rows))
        parts.append("<div class='s2bulk'><p>Drafted tags publish only when "
                     "you approve; a publish is one version, reversible in "
                     "GTM's history.</p>"
                     "<button class='cta a2draft' "
                     "onclick=\"act('/gtm/publish')\">Publish approved "
                     "drafts</button>"
                     "<button class='cta' onclick=\"act('/gtm/audit')\">"
                     "Re-audit</button></div>")
    # THE BASE SNIPPET, ready to paste. The one thing the API cannot do is
    # put its own loader into the theme; this box removes every other step.
    pub = str(ctx.get("gtm_public_id") or "")
    if pub:
        sn = ("&lt;script&gt;(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({"
              "'gtm.start':new Date().getTime(),event:'gtm.js'});var f=d."
              "getElementsByTagName(s)[0],j=d.createElement(s);j.async=true;"
              "j.src='https://www.googletagmanager.com/gtm.js?id='+i;"
              "f.parentNode.insertBefore(j,f);})(window,document,'script',"
              f"'dataLayer','{e(pub)}');&lt;/script&gt;")
        parts.append("<div class='s3panel'><p class='s3k'>The base snippet "
                     "&middot; paste once into the theme header</p>"
                     f"<div class='code' style='font-family:ui-monospace,"
                     f"monospace;font-size:10.5px;white-space:pre-wrap;"
                     f"word-break:break-all'>{sn}</div></div>")
    else:
        parts.append("<p class='s2empty'>Save your public container id "
                     "(GTM-XXXXXXX) as GTM_PUBLIC_ID on Connect and the "
                     "paste-ready base snippet renders here.</p>")
    # the UTM law, from the single table
    law = "".join(
        f"<div class='s3fx'><span class='s3fxn mono'>{e(pid)}</span>"
        f"<span class='s3fxw mono'>utm_source={e(v['utm_source'])} &middot; "
        f"utm_medium={e(v['utm_medium'])} &middot; utm_campaign=&lt;name&gt;"
        f"</span></div>"
        for pid, v in MO.UTM_LAW.items())
    parts.append("<p class='s3k' style='margin-top:14px'>The UTM law &middot; "
                 "one table, enforced on every campaign the engine creates"
                 "</p>" + law)
    parts.append("<p class='s2empty'>Click IDs captured on the lead record: "
                 + ", ".join(MO.CLICK_IDS)
                 + ". Closed deals feed Google back through offline "
                   "conversions. "
                   "<button class='cta' "
                   "onclick=\"act('/ads/offline-conversions')\">Send offline "
                   "conversions</button></p>")
    return "".join(parts)


def _burn_list(inter) -> list:
    """The interlock's burn/overlap has been a list AND a dict across engine
    versions. Read either; a shape mismatch here blanked a board once."""
    v = (inter or {}).get("burn") or (inter or {}).get("overlap") or []
    if isinstance(v, dict):
        v = list(v.values())
    return [x for x in v if isinstance(x, (dict, str))]


def terms_screen(ctx) -> str:
    inter = ctx.get("interlock") or {}
    burn = _burn_list(inter)
    terms = (ctx.get("terms") or {})
    parts = []
    if burn:
        rows = []
        for t in burn[:20]:
            term = t.get("term") if isinstance(t, dict) else str(t)
            rows.append(f"<div class='s3fx'><span class='s3fxn'>{e(term)}"
                        f"</span><span class='s3fxw'>you already rank &le;3 "
                        f"organically; paying for it is burn</span>"
                        f"<span class='s2act'><button class='cta a2draft' "
                        f"onclick=\"mediaOptimize(this)\">Draft negative"
                        f"</button></span></div>")
        parts.append(f"<p class='s3k'>Money burned on terms you already win "
                     f"&middot; {len(burn)}</p>" + "".join(rows))
    else:
        parts.append("<p class='s2empty'>No burn detected"
                     + ("" if inter else " - the interlock has not run yet")
                     + ". <button class='cta' "
                       "onclick=\"act('/ads/interlock')\">Run the interlock"
                       "</button></p>")
    if terms.get("reason"):
        parts.append(f"<p class='s2empty'>Search terms: "
                     f"{e(terms['reason'])[:160]}</p>")
    return "".join(parts)


def budget_screen(ctx) -> str:
    econ = ctx.get("econ") or {}
    ads = ctx.get("ads") or {}
    rows = [("Monthly ad cap", econ.get("monthly_budget"), "&euro;"),
            ("Spend so far", ads.get("spend"), "&euro;"),
            ("CPA target", econ.get("target_cpa"), "&euro;"),
            ("LTV", econ.get("ltv"), "&euro;")]
    tiles = "".join(f"<div class='s3stat'><span class='s3k'>{k}</span>"
                    + _n(v, u) + "</div>" for k, v, u in rows)
    return ("<div class='s3stats'>" + tiles + "</div>"
            "<p class='s2empty'>Caps live in Economics; the agent's pacing "
            "rule fires against them daily. "
            "<button class='cta' onclick=\"openEcon()\">Set unit economics"
            "</button></p>")


def work_screen(ctx) -> str:
    orders = ctx.get("media_orders") or []
    st = MO.stats(orders)
    rows = []
    for o in [x for x in orders if x.get("status") in ("open", "approved",
                                                       "held")][:30]:
        ev = o.get("evidence") or {}
        btn = ""
        if o.get("status") == "open":
            btn = (f"<button class='cta a2draft' "
                   f"onclick=\"mediaApprove('{e(o['id'])}',this)\">Approve"
                   f"</button>")
        elif o.get("status") == "approved":
            btn = (f"<button class='cta s3go' "
                   f"onclick=\"mediaRun('{e(o['id'])}',this)\">Execute now"
                   f"</button>")
        state = {"open": "s2warn", "approved": "s2bad", "held": "s2none"}[
            o["status"]]
        rows.append(
            f"<div class='s3fx'><span class='s2sev {state}'>"
            f"{e(o['status'])}</span>"
            f"<span class='s3fxn'>{e(o.get('say'))[:70]}</span>"
            f"<span class='s3fxw'>{e(ev.get('metric'))} vs "
            f"{e(ev.get('threshold'))} [{e(ev.get('source'))}]"
            + (f" &middot; {e(o.get('result'))[:60]}" if o.get("result")
               else "") + "</span>"
            f"<span class='s2act'>{btn}</span></div>")
    return (agent_band(ctx)
            + f"<div class='s2sum'><span class='s2big s2bad'>{st['open']}"
              f"</span><span class='s2lb'>waiting on you</span>"
              f"<span class='s2big'>{st['held']}</span>"
              f"<span class='s2lb'>held for a platform</span>"
              f"<span class='s2big'>{st['done']}</span>"
              f"<span class='s2lb'>executed</span></div>"
            + ("".join(rows) or "<p class='s2empty'>The queue is empty. The "
                                "agent's next verdict run fills it.</p>"))


def table_screen(title, obj, *, reason_key, rows_keys, empty) -> str:
    """A defensive table over whatever a pull really returned: list-of-dicts
    become rows, a stated reason is shown, and nothing is invented."""
    if isinstance(obj, dict) and obj.get(reason_key):
        return simple_screen(title, f"<p class='s2empty'>"
                                    f"{e(obj[reason_key])[:220]}</p>")
    rows = []
    if isinstance(obj, dict):
        for k in rows_keys:
            v = obj.get(k)
            if isinstance(v, list) and v:
                rows = [r for r in v if isinstance(r, dict)][:25]
                break
    elif isinstance(obj, list):
        rows = [r for r in obj if isinstance(r, dict)][:25]
    if not rows:
        return simple_screen(title, f"<p class='s2empty'>{e(empty)}</p>")
    cols = [k for k in rows[0].keys()][:5]
    head = "".join(f"<span class='s3fxw'><b>{e(c)}</b></span>" for c in cols)
    body = "".join(
        "<div class='s3fx'>" + "".join(
            f"<span class='s3fxw'>{e(r.get(c))[:38]}</span>" for c in cols)
        + "</div>" for r in rows)
    return simple_screen(title, f"<div class='s3fx'>{head}</div>{body}")


def comp_screen(ctx) -> str:
    """Who advertises on which of your queries - real SERP observation."""
    ci = ctx.get("competitor_intel") or {}
    serp = ci.get("serp_ads") or {}
    if not isinstance(serp, dict) or not serp:
        return simple_screen("Competition", "<p class='s2empty'>No SERP "
                             "advertiser observations yet; the competitor "
                             "engine fills this. Auction insights need the "
                             "Google key.</p>")
    rows = "".join(
        f"<div class='s3fx'><span class='s3fxn'>{e(q)[:46]}</span>"
        f"<span class='s3fxw'>{e(', '.join(map(str, ds[:4])) if isinstance(ds, list) else ds)[:70]}"
        f"</span></div>"
        for q, ds in list(serp.items())[:20])
    return simple_screen("Who advertises on your queries", rows
                         + "<p class='s2empty'>True auction insights need "
                           "the Google Ads key; this is live SERP "
                           "observation meanwhile.</p>")


def simple_screen(title, body) -> str:
    return f"<p class='s3k'>{e(title)}</p>{body}"


def bid_screen(ctx) -> str:
    rows = []
    for pid in MP.ORDER:
        p = MP.PLATFORMS[pid]
        strat = " &middot; ".join(e(n) for n, _w in p["bidding"][:4])
        rows.append(f"<div class='s3fx'><span class='s3fxn'><b>"
                    f"{e(p['name'])}</b></span>"
                    f"<span class='s3fxw'>{strat}</span></div>")
    return simple_screen(
        "Each platform's real bidding vocabulary",
        "".join(rows) + "<p class='s2empty'>Bid changes are drafted by the "
        "agent's rules and executed only after your approval; there is no "
        "hand-tuning surface here by design.</p>")


def land_screen(ctx) -> str:
    ga4 = (ctx.get("insights") or {}).get("ga4") or {}
    pages = ga4.get("pages") or []
    if not pages:
        return ("<p class='s2empty'>No GA4 page rows on record yet. The "
                "landing rule runs on real sessions and conversions; the "
                "daily pull fills this.</p>")
    rows = []
    for p in pages[:15]:
        sess = p.get("sessions")
        conv = p.get("conversions")
        rows.append(f"<div class='s3fx'><span class='s3fxn mono'>"
                    f"{e(p.get('path') or p.get('page'))[:50]}</span>"
                    f"<span class='s3fxw'>{e(sess)} sessions &middot; "
                    f"{e(conv)} conversions</span></div>")
    return simple_screen("Landing pages, from GA4", "".join(rows))


def build_panels(ctx, *, legacy_campaigns: str = "",
                 legacy_tracking: str = "") -> dict:
    """tab id -> screen html. THE one mapping, imported by media_section."""
    return {
        "mbcmd": cmd_screen(ctx),
        "mbhealth": health_screen(ctx),
        # The Google manager, then the AI media buyer's own drafting flow -
        # draft a campaign, read its reasoning, chat, deploy. That flow is
        # real function, so it moved in here rather than being deleted with
        # the card wall it used to sit under.
        "mbtypes": (platform_screen_for("google", ctx)
                    + (("<p class='s3k' style='margin-top:18px'>Campaign drafts &middot; your AI media buyer</p>"
                        + legacy_campaigns)
                       if legacy_campaigns else "")),
        "mbaud": meta_screen(ctx),
        "mbtarget": platform_screen_for("linkedin", ctx),
        "mbads": platform_screen_for("tiktok", ctx),
        "mbconv": (tracking_screen(ctx)
                   + (("<p class='s3k' style='margin-top:18px'>What GA4 and Search Console actually recorded</p>"
                       + legacy_tracking)
                      if legacy_tracking else "")),
        "mbterms": terms_screen(ctx),
        "mbkw": table_screen(
            "Paid keywords & quality score",
            (ctx.get("kw") or {}),
            reason_key="reason",
            rows_keys=("keywords", "rows"),
            empty="Fills from the Google pull; quality score needs the Google Ads key."),
        "mbbid": bid_screen(ctx),
        "mbbudget": budget_screen(ctx),
        "mbland": land_screen(ctx),
        "mbcomp": comp_screen(ctx),
        "mbresearch": table_screen(
            "Keyword research",
            (ctx.get("kw_ideas") or {}),
            reason_key="reason",
            rows_keys=("ideas", "keywords", "rows"),
            empty="Search volumes need the Google Ads key; free research runs on the SEO side."),
        "mblink": terms_screen(ctx),
        "mbwork": work_screen(ctx),
    }


JS = ("<script>"
      "async function mediaAutoSet(level,btn){"
      "try{var r=await fetch('/media/auto',{method:'POST',"
      "headers:{'Content-Type':'application/json'},"
      "body:JSON.stringify({level:level})});var j=await r.json();"
      "toast((j&&(j.message||j.error))||('level '+level),j&&j.ok!==false);"
      # EVERY ladder on the page follows, not just the one clicked. The
      # band renders on Command AND Work Orders, so updating only the
      # pressed one left the other screen showing a level that was no
      # longer true - the same silence the founder objected to when an
      # approval told him nothing.
      "if(j&&j.ok!==false){document.querySelectorAll('.s3lvl').forEach("
      "function(x){x.classList.remove('s3on');if(x.textContent.toLowerCase()"
      ".indexOf(level)===0)x.classList.add('s3on');});}}"
      "catch(e){toast('could not reach the engine \\u2014 the switch is "
      "unchanged',false);}}"
      "async function mediaOptimize(btn){"
      "var lab=btn?btn.textContent:'';"
      "if(btn){btn.disabled=true;btn.textContent='Judging\\u2026';}"
      "try{var r=await fetch('/media/optimize',{method:'POST'});"
      "var j=await r.json();toast((j&&j.message)||'ran',j&&j.ok!==false);}"
      "catch(e){toast('could not reach the engine',false);}"
      "if(btn){btn.disabled=false;btn.textContent=lab;}}"
      "async function mediaApprove(id,btn){"
      "try{var r=await fetch('/media/approve',{method:'POST',"
      "headers:{'Content-Type':'application/json'},"
      "body:JSON.stringify({id:id})});var j=await r.json();"
      "toast((j&&j.message)||'approved',j&&j.ok!==false);"
      "if(btn)btn.textContent='Approved';}catch(e){"
      "toast('could not reach the engine',false);}}"
      "async function mediaRun(id,btn){"
      "var lab=btn?btn.textContent:'';"
      "if(btn){btn.disabled=true;btn.textContent='Executing\\u2026';}"
      "try{var r=await fetch('/media/run-orders',{method:'POST',"
      "headers:{'Content-Type':'application/json'},"
      "body:JSON.stringify({ids:[id]})});var j=await r.json();"
      "toast((j&&j.message)||'ran',j&&j.ok!==false);}catch(e){"
      "toast('could not reach the engine',false);}"
      "if(btn){btn.disabled=false;btn.textContent=lab;}}"
      "async function gtmDraft(name,btn){"
      "var lab=btn?btn.textContent:'';"
      "if(btn){btn.disabled=true;btn.textContent='Drafting\\u2026';}"
      "try{var r=await fetch('/gtm/draft',{method:'POST',"
      "headers:{'Content-Type':'application/json'},"
      "body:JSON.stringify({name:name})});var j=await r.json();"
      "toast((j&&(j.result||j.message))||'drafted',j&&j.ok!==false);}"
      "catch(e){toast('could not reach the engine',false);}"
      "if(btn){btn.disabled=false;btn.textContent=lab;}}"
      "</script>")
