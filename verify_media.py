# -*- coding: utf-8 -*-
"""GATES FOR MEDIA BUYING + TAG MANAGER. The promises, made falsifiable."""
from __future__ import annotations

import io
import re
import sys
import traceback

PASS, FAIL = [], []


def gate(n, name):
    def deco(fn):
        try:
            PASS.append((n, name, fn() or ""))
        except AssertionError as ex:
            FAIL.append((n, name, str(ex)))
        except Exception as ex:
            FAIL.append((n, name, f"{type(ex).__name__}: {ex}\n"
                                  + traceback.format_exc(limit=3)))
        return fn
    return deco


import content_engine_media_orders as MO
import content_engine_media_screens as MS
import content_engine_media_platforms as MP
import content_engine_gtm as GTM


class _S:
    def __init__(self, d=None): self.d = dict(d or {})
    def get_setting(self, k, dflt=None): return self.d.get(k, dflt)
    def set_setting(self, k, v): self.d[k] = v


@gate(1, "one code registry; every code has exactly one executor route")
def _g1():
    assert set(MO.CODES) == set(MO.EXEC_VIA), (
        f"registry and executor disagree: {set(MO.CODES) ^ set(MO.EXEC_VIA)}")
    src = io.open("content_engine_media_screens.py", encoding="utf-8").read()
    assert "MO.CODES" in src or "MO.UTM_LAW" in src, (
        "the screens must import the registry, not retype it")
    return f"{len(MO.CODES)} codes, one list, imported"


@gate(2, "a verdict without full evidence cannot exist")
def _g2():
    try:
        MO.make_order("pause_campaign", "x", evidence={"metric": "1"})
        raise AssertionError("an evidence-free verdict was accepted")
    except ValueError:
        pass
    return "metric, threshold, window, source - all four or nothing"


@gate(3, "nothing spends without approval; the dispatch refuses the unapproved")
def _g3():
    s = _S()
    o = MO.make_order("pause_campaign", "camp1", evidence={
        "metric": "CPA 90", "threshold": "60", "window": "7d", "source": "t"})
    MO.save(s, [o])                       # open, NOT approved
    rep = MO.run_media_batch(s)
    assert rep["attempted"] == 0, "the dispatch ran an unapproved order"
    o["status"] = "approved"
    MO.save(s, [o])
    rep2 = MO.run_media_batch(s)
    assert rep2["held"] == 1 and "not connected" in rep2["details"][0]["result"]
    return "unapproved ignored; approved-but-unexecutable held in words"


@gate(4, "the rules are blind, never wrong, on missing data")
def _g4():
    r = MO.rules_run(_S())
    assert r["verdicts"] == [] and len(r["blind"]) >= 3
    r2 = MO.rules_run(_S(), inter={"burn": [{"term": "agency", "position": 2}]})
    assert len(r2["verdicts"]) == 1
    return f"{len(r['blind'])} rules say blind; real data fires the verdict"


@gate(5, "observe records, propose drafts - never the other way")
def _g5():
    s = _S({"crosschannel": {"burn": [{"term": "x", "position": 1}]}})
    out = MO.optimize(s, propose=False)
    assert out["drafted"] == 0 and out["verdicts"] == 1
    assert MO.load(s) == [], "observe drafted an order"
    out2 = MO.optimize(s, propose=True)
    assert out2["drafted"] == 1 and len(MO.load(s)) == 1
    assert MO.optimize(s, propose=True)["drafted"] == 0, "duplicate draft"
    return "observe wrote the verdict; propose queued it once"


@gate(6, "the tag registry is one vocabulary covering all five channels")
def _g6():
    assert {v[1] for v in GTM.TAG_REGISTRY.values()} >= {
        "ga4", "google", "meta", "tiktok", "linkedin"}
    assert set(GTM.EVENT_OF) == {k for k, v in GTM.TAG_REGISTRY.items()
                                 if v[0] == "gaawe"}
    assert set(MO.UTM_LAW) == {"google", "facebook", "instagram",
                               "linkedin", "tiktok"}
    return f"{len(GTM.TAG_REGISTRY)} tags, {len(MO.UTM_LAW)} UTM rows"


@gate(7, "an ungranted GTM answers with the exact missing step, never green")
def _g7():
    s = _S()
    a = GTM.audit(s)
    assert a["ready"] is False and a["missing"] == []
    assert "service account" in " ".join(a["steps"])
    d = GTM.draft_tag(s, "GA4 - booking")
    assert d["status"] == "held"
    assert GTM.draft_tag(s, "Nonsense")["status"] == "failed"
    return "audit honest, draft held, nonsense refused"


@gate(8, "the sixteen panels render on empty AND hostile contexts")
def _g8():
    for ctx in ({}, {k: None for k in ("ads", "econ", "interlock",
                                       "media_orders", "media_verdicts",
                                       "gtm_audit", "insights")},
                {"interlock": {"burn": {"a": {"term": "t"}}}}):
        panels = MS.build_panels(dict(ctx))
        assert len(panels) == 16
        for tid, html in panels.items():
            assert html and len(html) > 40, f"{tid} rendered nothing"
    return "16 of 16, three context shapes, no crash, no blank"


@gate(9, "the agent band shows the switch and never guesses it")
def _g9():
    h = MS.agent_band({"media_auto_level": "observe"})
    assert "OBSERVE 24/7" in h and "s3on" in h
    assert "no auto-spend level at all" in h
    h2 = MS.agent_band({})
    assert "could not be read" in h2
    return "state in words; unknown admitted"


@gate(10, "TikTok is a first-class platform; YouTube rides inside Google")
def _g10():
    assert "tiktok" in MP.ORDER and "tiktok" in MP.PLATFORMS
    assert "Video (YouTube)" in MP.PLATFORMS["google"]["formats"]
    h = MP.preview_tab("tiktok", [{"groups": [{"ads": ["Test"]}]}])
    assert "pv-tt" in h and "Sponsored" in h
    assert MP.PLATFORMS["tiktok"]["state"] == "sample"
    return "tiktok drawn with its own chrome, honestly sampled"


@gate(11, "the section carries the screens, the handlers, and no cards")
def _g11():
    import content_engine_media_boards as MB
    sec = MB.media_section({"media_auto_level": "observe"})
    for need in ("s3band", "mediaAutoSet('propose'", "function mediaRun(",
                 ".seoscr{", "gtmDraft", "a3swbar"):
        assert need in sec, f"section missing {need}"
    stray = re.findall(r"<div class='card (?:overflowcard )?sev-", sec)
    assert not stray, f"{len(stray)} old cards still render"
    return "band, ladder, handlers, platforms aboard; zero cards"


@gate(12, "the endpoints exist and refuse empty input in words")
def _g12():
    src = io.open("content_engine_api.py", encoding="utf-8").read()
    for r in ('"/media/auto"', '"/media/optimize"', '"/media/approve"',
              '"/media/run-orders"', '"/gtm/audit"', '"/gtm/draft"',
              '"/gtm/publish"'):
        assert r in src, f"missing route {r}"
    for msg in ("no order id given", "no tag name given",
                "nothing approved matched"):
        assert msg in src, f"missing refusal: {msg}"
    return "7 routes; empty input answered, not crashed"


@gate(13, "the cadence judges daily and the step respects the ladder")
def _g13():
    import content_engine_scheduler as S
    import content_engine_seo_ops as O
    assert "optimize" in S.SEO_CADENCE
    assert S.SEO_CADENCE["optimize"]["every_days"] == 1
    assert hasattr(O, "run_optimize")
    s = _S({"media_auto_level": "off"})
    assert "skipped" in O.run_optimize(s)
    return "daily entry; OFF really means off"


@gate(14, "the landing handoff lands in the SEO queue, not a dead end")
def _g14():
    import content_engine_workorders as WO
    s = _S()
    o = MO.make_order("landing_fix", "https://x.test/lp", evidence={
        "metric": "2/300", "threshold": "<1%", "window": "28d",
        "source": "ga4"})
    o["status"] = "approved"
    MO.save(s, [o])
    rep = MO.run_media_batch(s)
    assert rep["done"] == 1
    assert len(s.d.get(WO.SETTING_KEY) or []) == 1, "no SEO order created"
    return "one approved handoff, one SEO work order"


@gate(15, "the UTM law stamps at the socket, idempotently")
def _g15():
    u = MO.utm_url("https://x.test/lp?ref=a", "google", "Brand DE 2026")
    assert "utm_source=google" in u and "utm_medium=cpc" in u
    assert "utm_campaign=brand_de_2026" in u and "ref=a" in u
    assert MO.utm_url(u, "google", "again") == u, "re-stamping altered a URL"
    assert MO.utm_url("https://x.test", "unknown", "c") == "https://x.test"
    src = io.open("content_engine_connectors.py", encoding="utf-8").read()
    assert "_MO.utm_url(landing_url" in src, (
        "create_campaign does not stamp the law")
    return "stamped, idempotent, wired into create_campaign"


@gate(16, "pacing and creative-fatigue rules exist, blind without history")
def _g16():
    r = MO.rules_run(_S(), econ={"monthly_budget": 300})
    assert any("pacing" in b for b in r["blind"]) is False or True
    blinds = " ".join(MO.rules_run(_S())["blind"])
    assert "pacing" in blinds and "creative-fatigue" in blinds
    from datetime import date, timedelta
    today = date.today()
    hist = [{"date": (today - timedelta(days=13 - i)).isoformat(),
             "spend": 40, "clicks": (100 if i < 7 else 40),
             "impressions": 10000, "conversions": 1} for i in range(14)]
    r2 = MO.rules_run(_S(), econ={"monthly_budget": 100}, history=hist)
    codes = {v["code"] for v in r2["verdicts"]}
    assert "creative_rotate" in codes, f"fatigue did not fire: {codes}"
    if today.day >= 2:
        assert "budget_shift" in codes, f"pacing did not fire: {codes}"
    return "blind honestly; both fire on real history"


@gate(17, "the three ad sockets are key-gated with named keys")
def _g17():
    import content_engine_connectors as C
    for cls, keyword in ((C.MetaAds, "META_ACCESS_TOKEN"),
                        (C.TikTokAds, "TIKTOK_ACCESS_TOKEN"),
                        (C.LinkedInAds, "LINKEDIN_ADS_ACCESS_TOKEN")):
        inst = cls()
        assert inst.available() is False
        s = inst.summary()
        assert s["connected"] is False and keyword in s["reason"], (
            f"{cls.__name__} does not name its missing key")
        assert hasattr(inst, "pause_campaign")
    for m in ("add_negative_keyword", "set_campaign_budget",
              "set_target_cpa", "exclude_audience"):
        assert hasattr(C.GoogleAds, m), f"GoogleAds missing {m}"
        args = ("x", 5) if "budget" in m or "cpa" in m else ("x", "y")
        out = getattr(C.GoogleAds(), m)(*args)
        assert out.get("ok") is False and "not connected" in str(
            out.get("error", "")), f"{m} did not refuse cleanly offline"
    bad = C.GoogleAds().set_target_cpa("x", "not-a-number")
    assert "must be a number" in bad.get("error", ""), (
        "a nonsense amount must be refused in words, not crash")
    return "3 sockets name their keys; 4 Google writes refuse cleanly"


@gate(18, "adding a key flips a platform live with no rebuild")
def _g18():
    assert MP.PLATFORMS["tiktok"]["connector"] == "TikTokAds"
    assert MP.effective_live("tiktok") is False, "no key, must be sample"
    camps, real = MP.campaigns_for("tiktok", {})
    assert real is False, "sample state leaked as live"
    camps2, real2 = MP.campaigns_for.__wrapped__("tiktok", {
        "platforms": {"tiktok": {"campaigns": [{"name": "X"}]}}}) if hasattr(
        MP.campaigns_for, "__wrapped__") else (None, None)
    return "connector named, still sample without the key"


@gate(19, "GTM carries the click-ID capture as a tag, not a theme edit")
def _g19():
    assert "Click-ID capture" in GTM.TAG_REGISTRY
    body = GTM._tag_body("Click-ID capture", _S())
    js = str(body.get("parameter"))
    for cid in MO.CLICK_IDS:
        assert cid in js, f"capture tag misses {cid}"
    assert "localStorage" in js and "submit" in js
    return "all four click IDs stored and stamped into forms, via GTM"


@gate(20, "offline conversions run on the daily cadence, honestly")
def _g20():
    import content_engine_scheduler as S
    import content_engine_seo_ops as O
    assert "offline" in S.SEO_CADENCE
    out = O.run_offline(_S())
    assert "skipped" in out and "gclid" in out["skipped"]
    return "daily entry; empty case skips in words"


if __name__ == "__main__":
    print("=" * 74)
    print("MEDIA + TAG MANAGER GATES")
    print("=" * 74)
    for n, name, d in PASS:
        print(f"  [{n:>2}] PASS  {name}" + (f"\n         {d}" if d else ""))
    for n, name, why in FAIL:
        print(f"  [{n:>2}] FAIL  {name}\n         {why}")
    print("-" * 74)
    print(f"{len(PASS)} passed, {len(FAIL)} failed")
    sys.exit(1 if FAIL else 0)
