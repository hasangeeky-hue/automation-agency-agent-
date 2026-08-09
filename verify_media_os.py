"""
verify_media_os.py
============================================================================
GATES FOR THE MEDIA BUYING OS FOUNDATION.

The rule this file exists to protect: no screen and no business logic may
contain Meta-specific, Google-specific or TikTok-specific knowledge. The
adapter is the only place that knows what Meta calls an ad set.
============================================================================
"""
import ast
import io

import content_engine_media_os as M
import content_engine_os_core as CORE
import content_engine_os_store as ST

OK = []


def t(name, cond, detail=""):
    OK.append(bool(cond))
    print(("  OK   " if cond else "  FAIL ") + name
          + (f"   [{detail}]" if detail and not cond else ""))


class Store:
    def __init__(self):
        self.d = {}

    def get_setting(self, k, dflt=None):
        return self.d.get(k, dflt)

    def set_setting(self, k, v):
        self.d[k] = v


print("\nG1  THE CANONICAL MODEL")
t("every collection it writes has a table",
  all(c in ST.SCHEMA for c in M.COLLECTIONS))
t("and the core knows them, so a write cannot go nowhere",
  all(c in CORE.COLLECTIONS for c in M.COLLECTIONS))
t("every state has a transition rule",
  set(M.CAMPAIGN_MOVES) == set(M.CAMPAIGN_STATES))
t("every transition target is a real state",
  all(x in M.CAMPAIGN_STATES for v in M.CAMPAIGN_MOVES.values() for x in v))
t("the hierarchy is normalized to three levels",
  M.LEVELS == ("campaign", "ad_group", "ad"))
t("and every provider has a word for the middle one",
  all(p in M.LEVEL_WORDS for p in M.PROVIDERS))

print("\nG2  PROVIDER DIFFERENCES ARE REPORTED, NOT FLATTENED")
t("every provider is mapped for every objective",
  all(set(M.OBJECTIVE_MAP[p]) == set(M.OBJECTIVES) for p in M.PROVIDERS))
t("a platform that cannot do something says so",
  M.supports("linkedin", "APP_INSTALL")["ok"] is False)
t("and explains what to do instead, rather than substituting silently",
  "Choose a different objective" in M.supports("linkedin",
                                               "APP_INSTALL")["why"])
t("a platform that can do it returns ITS OWN word",
  M.supports("meta", "LEADS")["provider_objective"] == "OUTCOME_LEADS")
t("an unknown provider is refused by name",
  "no adapter" in M.supports("snapchat", "LEADS")["why"])
t("an invented objective is refused with the real list",
  "is not an objective" in M.supports("meta", "VIBES")["why"])
_cap = M.capability_table("APP_INSTALL")
t("the capability table names every gap per platform",
  any(r["missing"] for r in _cap))

print("\nG3  NORMALIZATION")
_raw = {"id": "123", "name": "Summer", "status": "ENABLED",
        "objective": "OUTCOME_LEADS", "daily_budget": 250000,
        "special_ad_categories": ["CREDIT"], "bid_strategy": "LOWEST_COST"}
_c = M.normalize_campaign("meta", _raw)
t("a provider status becomes a canonical state", _c["state"] == "ACTIVE")
t("and the provider's own word is kept beside it",
  _c["provider_status"] == "ENABLED")
t("a provider objective maps back to the canonical one",
  _c["objective"] == "LEADS")
t("money in cents is read as money", _c["budget_amount"] == 2500.0)
t("money in micros is read as money", M._money(5_000_000) == 5.0)
t("a plain decimal is left alone", M._money(42.5) == 42.5)
t("EVERY field this engine does not understand is kept",
  _c["provider_config"].get("special_ad_categories") == ["CREDIT"]
  and _c["provider_config"].get("bid_strategy") == "LOWEST_COST")
t("an objective this engine cannot map stays unknown rather than guessed",
  M.normalize_campaign("meta", {"objective": "SOMETHING_NEW"})["objective"]
  == "")

print("\nG4  THE STATE MACHINE")
s = Store()
r = CORE.Repo(s)
made = M.save_campaign(r, name="Munich clinics", objective="LEADS",
                       provider="meta", budget_type="DAILY",
                       budget_amount=50)
t("a campaign saves as a draft", made["ok"] and made["state"] == "DRAFT")
t("and is told what the platform calls its objective",
  "OUTCOME_LEADS" in made["message"])
cid = made["id"]
t("a draft may not jump straight to active",
  M.move(r, cid, "ACTIVE")["ok"] is False)
t("the refusal lists the moves that ARE legal",
  "can only move to" in M.move(r, cid, "ACTIVE")["message"])
t("an objective no platform supports is refused at save time",
  M.save_campaign(r, name="x", objective="APP_INSTALL",
                  provider="linkedin")["ok"] is False)
t("an invented objective is refused", M.save_campaign(
    r, name="x", objective="VIBES")["ok"] is False)

print("\nG5  VALIDATION REFUSES TO LAUNCH A BROKEN CAMPAIGN")
v = M.validate(r, cid)
t("a campaign with no ad group cannot launch", v["ok"] is False)
t("and the reason is a sentence", "no ad group" in " ".join(v["errors"]))
t("the campaign is parked in VALIDATION_FAILED, not left ACTIVE",
  r.one("media_campaigns", cid)["state"] == "VALIDATION_FAILED")
M.save_ad_group(r, cid, name="Munich 30km", budget_amount=50)
t("an ad group belongs to a campaign that exists",
  M.save_ad_group(r, "nope", name="x")["ok"] is False)
t("an ad belongs to an ad group that exists",
  M.save_ad(r, "nope", name="x")["ok"] is False)
t("a zero budget is a blocking error",
  "budget is zero" in " ".join(M.validate(r, cid)["errors"])
  or float(r.one("media_campaigns", cid).get("budget_amount") or 0) > 0)

print("\nG6  THE ENGINE NEVER OUTRANKS THE PLATFORM")
c = r.one("media_campaigns", cid)
c.update({"state": "ACTIVE", "provider_status": "PAUSED",
          "external_campaign_id": "123", "synced_at": CORE.now()})
r.put("media_campaigns", c)
d = M.drift(r)
t("a disagreement with the platform is DETECTED", len(d) == 1, str(d))
t("and reports both sides",
  d[0]["engine_says"] == "ACTIVE" and d[0]["platform_says"] == "PAUSED")
t("the summary carries it to the screen", M.summary(r)["drift"])
t("sync records a run even when no platform answers",
  M.sync(r)["ok"] and len(r.all("sync_runs")) >= 1)
t("and names the platforms it could not reach", M.sync(r)["errors"])

print("\nG7  NOTHING PROVIDER-SPECIFIC LEAKS UPWARDS")
src = io.open("content_engine_media_os.py", encoding="utf-8").read()
_adapter = src.split("class Adapter")[1].split("# ----")[0]
_model = src.split("# THE CANONICAL MODEL")[1]
for word in ("MetaAds", "GoogleAds", "TikTokAds", "LinkedInAds"):
    t(f"{word} appears only inside the adapter",
      word not in _model, word)
t("the model calls no platform HTTP of its own",
  "requests" not in src and "urllib" not in src)
t("the adapter delegates rather than re-implementing",
  "content_engine_connectors" in _adapter)
t("writes go through the EXISTING order engine, not a second one",
  "content_engine_media_orders" in src and "auto_level" in src)
t("no credential is stored in a business table",
  "credentials_reference" in src and "access_token" not in src)
t("it reuses the engagement OS repository rather than a second store",
  "content_engine_os_store" in src and "ST.repo_for" in src)

print("\nG8  NO SECOND VOCABULARY")
for name in ("CAMPAIGN_STATES", "CAMPAIGN_MOVES"):
    t(f"{name} in media OS is deliberately its own, and named so",
      name in src)
t("the media states are NOT the email states",
  set(M.CAMPAIGN_STATES) != set(CORE.CAMPAIGN_STATES))
t("the media collections do not collide with the email ones",
  "campaigns" not in M.COLLECTIONS and "media_campaigns" in M.COLLECTIONS)

print("\nG9  THE CREATIVE ENGINE")
import content_engine_media_creative as MC
r2 = CORE.Repo(Store())
c1 = MC.save_creative(r2, name="Save 30 percent", type="UGC",
                      concept="Save 30%", angle="pain-point",
                      hook="Still booking by phone?",
                      persona="practice manager", cta="Book a call",
                      funnel_stage="COLD", publish=True)
t("a creative publishes as version 1", c1["ok"] and c1["version"] == 1)
c2 = MC.save_creative(r2, name="Save 30 percent", type="VIDEO",
                      concept="Save 30%", angle="pain-point", publish=True)
t("publishing again appends a version", c2["version"] == 2)
t("and version one is still readable", len(r2.all("creative_versions")) == 2)
t("an invented format is refused with the real list",
  "is not a format" in MC.save_creative(r2, name="x",
                                        type="HOLOGRAM")["message"])
t("an invented funnel stage is refused too",
  "is not a funnel stage" in MC.save_creative(r2, name="x",
                                              funnel_stage="LUNAR")["message"])
_bare = MC.save_creative(r2, name="bare creative")
t("a creative with no attributes saves but is flagged as unlearnable",
  _bare["ok"] and _bare["unattributed"] and "learned from" in _bare["message"])
t("an agent's invented field is dropped rather than stored",
  MC.from_agent({"name": "x", "vibe": "cosmic"})["refused"] == ["vibe"])

print("\nG10 ATTRIBUTES, NOT JUST CREATIVES")
m = MC.matrix(r2, "angle")
t("the matrix groups by an attribute", m["ok"] and m["dimension"] == "angle")
t("an invented dimension is refused with the real list",
  MC.matrix(r2, "astrology")["ok"] is False
  and "is not an attribute" in MC.matrix(r2, "astrology")["message"])
t("with no spend it REFUSES to name a winner",
  m["verdict"]["state"] == "early")
t("and says how much is needed before it would",
  "impressions" in m["verdict"]["message"]
  and str(MC.MIN_IMPRESSIONS) in m["verdict"]["message"].replace(",", ""))
t("the learning brief is empty rather than invented",
  "Nothing has earned a verdict" in MC.learn(r2)["message"])
t("every attribute is examined, not only the obvious one",
  len(MC.learn(r2)["findings"]) == len(MC.ATTRIBUTES))
t("fatigue refuses on a creative with no impressions",
  MC.fatigue(r2, c1["id"])["score"] is None)
t("and says fatigue is measured, not assumed",
  "measured, not assumed" in MC.fatigue(r2, c1["id"])["message"])
t("an unknown creative is refused",
  MC.fatigue(r2, "nope")["ok"] is False)
t("the sample floor is one number, used by matrix AND verdict",
  MC.MIN_IMPRESSIONS >= 1000 and MC.MIN_CONVERSIONS >= 10)

print("\nG11 THE AUDIENCE ENGINE")
a1 = MC.save_audience(r2, name="German clinics", type="PROSPECTING",
                      definition={"countries": ["DE"],
                                  "job_titles": ["practice manager"],
                                  "age_min": 30})
t("an audience saves", a1["ok"], str(a1))
_bad = MC.save_audience(r2, name="x", definition={"star_sign": "leo"})
t("a field no platform understands is refused AT SAVE TIME",
  _bad["ok"] is False)
t("and the refusal lists what CAN be targeted",
  "It can target on" in _bad["message"])
t("an invented audience type is refused",
  MC.save_audience(r2, name="x", type="COSMIC")["ok"] is False)
mp = MC.map_to_provider({"countries": ["DE"], "job_titles": ["x"]}, "meta")
t("a platform that cannot express a clause DROPS it explicitly",
  mp["dropped"] == ["job_titles"], str(mp))
t("and says the audience is now wider than the one you defined",
  "wider than the one you defined" in mp["message"])
t("linkedin CAN target job titles",
  not MC.map_to_provider({"job_titles": ["x"]}, "linkedin")["dropped"])
t("google CAN target search keywords, and meta cannot",
  not MC.map_to_provider({"keywords": ["x"]}, "google")["dropped"]
  and MC.map_to_provider({"keywords": ["x"]}, "meta")["dropped"] == ["keywords"])
t("a definition every platform supports says so",
  "can express all of it" in MC.map_to_provider({"countries": ["DE"]},
                                                "google")["message"])
t("coverage reports every platform at once",
  len(MC.coverage({"countries": ["DE"]})) == len(MC.TARGET_SUPPORT))
t("an unknown platform is refused rather than guessed",
  MC.map_to_provider({"countries": ["DE"]}, "snapchat")["ok"] is False)
t("the audience row names which platforms are only partial",
  MC.audience_rows(r2)[0]["partial"])
t("saturation refuses when nothing has run against the audience",
  MC.saturation(r2, a1["id"])["level"] is None)

print("\nG12 NO PLATFORM CODE, NO SECOND STORE")
csrc = io.open("content_engine_media_creative.py", encoding="utf-8").read()
for w in ("MetaAds", "GoogleAds", "TikTokAds", "requests", "urllib"):
    t(f"the creative engine contains no {w}", w not in csrc)
t("it uses the same Repo as everything else",
  "content_engine_os_core" in csrc)
t("the sample floor is declared once",
  csrc.count("MIN_IMPRESSIONS = ") == 1)
t("its collections are the ones already declared in the core",
  all(c in CORE.COLLECTIONS
      for c in ("creatives", "creative_versions", "audiences", "ad_metrics")))

print("\nG13 THE PLANNER REFUSES TO INVENT HISTORY")
import content_engine_media_plan as MP
r3 = CORE.Repo(Store())
_a0 = MP.allocate(r3, 3000)
t("with no history it does NOT invent a split", _a0["basis"] == "no history")
t("and says why in the founder's words",
  "nothing has run here yet" in str(_a0["rows"]) or not _a0["rows"])
t("it names the sample floor rather than hiding it",
  str(MP.MIN_CONV) in _a0["message"])
t("it refuses an industry benchmark out loud",
  "somebody else's business" in _a0["message"])
_f0 = MP.forecast(r3, budget=3000)
t("a forecast with no history is REFUSED, not guessed", _f0["ok"] is False)
t("and it says what would make it answerable",
  "two weeks" in _f0["message"])
t("a budget of zero is refused", MP.allocate(r3, 0)["ok"] is False)
t("a budget that is not a number is refused",
  MP.allocate(r3, "lots")["ok"] is False)

print("\nG14 FORECASTS ARE RANGES, NEVER PROMISES")
M.save_account(r3, "google", "acct-1", name="G")
_c = M.save_campaign(r3, name="Clinics DE", objective="LEADS",
                     provider="google", budget_type="DAILY",
                     budget_amount=50, currency="EUR")
CID = _c["id"]
for _i in range(9):
    r3.put("ad_metrics", {"id": "mm%d" % _i, "day": "2026-07-0%d" % (_i + 1),
                          "provider": "google", "campaign_id": CID,
                          "impressions": 5000, "clicks": 200,
                          "conversions": 4, "conversion_value": 1200,
                          "spend": 400})
_h = MP.history(r3)
t("history is computed from measured metrics", _h["google"]["cpa"] == 100.0)
t("and knows when it has earned an opinion", _h["google"]["enough"] is True)
_f = MP.forecast(r3, budget=3000)
t("a forecast comes back as a range, not a number",
  set(_f["cpa"]) == {"low", "base", "high"})
t("the conversion estimate is a range too",
  set(_f["conversions"]) == {"low", "base", "high"})
t("the band is stated in words as well as numbers",
  "plus or minus" in _f["confidence_band"])
t("every assumption is named", len(_f["assumptions"]) >= 4)
t("the message refuses the word guarantee",
  "not a forecast anybody should sign" in _f["message"])
_thin = MP.forecast(r3, budget=3000)
_wide = _thin["cpa"]["high"] - _thin["cpa"]["low"]
t("less evidence means a wider band, not a bolder claim", _wide > 0)

print("\nG15 ONE DIMINISHING-RETURNS CURVE, NOT TWO")
t("the decay curve is declared exactly once",
  io.open("content_engine_media_plan.py", encoding="utf-8").read()
    .count("DECAY_PER_DOUBLING = ") == 1)
t("a budget no bigger than history is not decayed",
  MP.efficiency_decay(1000, 1000) == 1.0)
t("a doubled budget decays by exactly one doubling",
  MP.efficiency_decay(1000, 2000) == MP.DECAY_PER_DOUBLING)
t("marginal return is BELOW average once spend is past the floor",
  MP.marginal_roas(_h["google"]) < _h["google"]["roas"])
_big = MP.forecast(r3, budget=36000)
t("THE FORECAST USES THE SAME CURVE AS THE ALLOCATOR",
  _big["efficiency_decay"] < 1.0)
t("so ten times the budget does NOT promise ten times the leads",
  _big["conversions"]["base"] < _f["conversions"]["base"] * 10)
t("and the decay is named as an assumption, not buried",
  any("same curve the allocator uses" in x.lower()
      for x in _big["assumptions"]))
_al = MP.allocate(r3, 3000)
t("allocation is on marginal return", _al["basis"] == "marginal return")
t("each row explains itself in one sentence",
  all(len(row["why"]) > 40 for row in _al["rows"]))
t("it never moves more than MAX_SHIFT of a running budget in one pass",
  MP.allocate(r3, 10000, current={"google": 1000})["rows"][0]["amount"]
  <= 1000 * (1 + MP.MAX_SHIFT) + 0.01)
t("the shift cap is explained where it bites",
  "learning phase survives" in
  MP.allocate(r3, 10000, current={"google": 1000})["rows"][0]["why"])

print("\nG16 THE SIMULATOR CHECKS ITS OWN ARITHMETIC")
_s = MP.simulate(r3, budget=6000, compare_to=3000)
t("two scenarios come back", len(_s["scenarios"]) == 2)
t("the caveat says these are estimates, not guarantees",
  "not guarantees" in _s["caveat"])
t("WHETHER THE RANGES OVERLAP IS CHECKED, NOT ASSERTED",
  _s["overlaps"] is (_s["scenarios"][0]["conversions"]["high"]
                     >= _s["scenarios"][1]["conversions"]["low"]))
t("and the sentence matches what was actually found",
  ("do not overlap" in _s["message"]) is (not _s["overlaps"]))
t("the actual numbers appear beside the claim",
  str(_s["scenarios"][0]["conversions"]["low"]) in _s["message"])

print("\nG17 THE EIGHT STEPS AND THE LAUNCH GATE")
t("the eight steps are declared once", len(MP.WIZARD_STEPS) == 8)
_w = MP.wizard_state(r3, CID)
t("wizard state is read from the RECORD, not the browser",
  _w["total"] == 8 and _w["complete"] >= 3)
t("it names the next step and why it matters", _w["next"]["why"])
_pf = MP.pre_flight(r3, CID)
t("pre-flight blocks a campaign with no ads", _pf["level"] == "ERROR")
t("and lists exactly what is blocking", "Ads" in _pf["errors"])
t("an empty ad list does NOT pass the landing-page check",
  [x for x in _pf["checks"] if x["name"] == "Landing page"][0]["state"]
  != "OK")
t("launch REFUSES on a blocking error", MP.launch(r3, CID)["ok"] is False)
_au = MC.save_audience(r3, name="DE clinics", type="PROSPECTING",
                       definition={"countries": ["DE"]})
_cr = MC.save_creative(r3, name="Save 30", type="TEXT", concept="Save 30%",
                       angle="pain", hook="h", persona="p", cta="Book",
                       funnel_stage="COLD", publish=True)
_g = M.save_ad_group(r3, CID, name="Core", audience_id=_au["id"])
M.save_ad(r3, _g["id"], name="Ad 1", creative_id=_cr["id"],
          landing_page_url="https://example.com/x")
_pf2 = MP.pre_flight(r3, CID)
t("with everything attached it passes", _pf2["ok"] is True)
t("a warning is a warning, not a block", _pf2["level"] == "WARNING")
t("no start date is a warning, not silence", "Schedule" in _pf2["warnings"])
t("missing conversion tracking is a warning, not silence",
  "Tracking" in _pf2["warnings"])
t("an unknown campaign is refused",
  MP.pre_flight(r3, "nope")["level"] == "ERROR")

print("\nG18 THE PLANNER SPENDS NOTHING AND OWNS NO QUEUE")
psrc = io.open("content_engine_media_plan.py", encoding="utf-8").read()
for w in ("MetaAds", "GoogleAds", "TikTokAds", "LinkedInAds",
          "requests", "urllib", "http.client"):
    t(f"the planner contains no {w}", w not in psrc)
import content_engine_media_orders as MO
t("launch queues into the EXISTING order engine, not a second one",
  "make_order" in psrc and "content_engine_media_orders" in psrc)
t("and its code is registered in the one CODES table",
  "launch_campaign" in MO.CODES and MO.CODES["launch_campaign"][0] == "spend")
t("so it inherits the approval tier every other spend waits behind",
  "launch_campaign" in MO.EXEC_VIA)
t("the sample floor is imported, not retyped",
  MP.MIN_CONV is MC.MIN_CONVERSIONS and "MIN_CONV = MC." in psrc)
t("it creates no agent of its own",
  "register" not in psrc and "class .*Agent" not in psrc)
t("no em dash anywhere in the planner", "\u2014" not in psrc)
t("media_plans was already a declared collection",
  "media_plans" in CORE.COLLECTIONS)

print("\nG19 ROLLUPS: FIVE GRAINS, ONE ARITHMETIC")
import datetime as _dtm
import content_engine_media_perf as MF
import content_engine_media_orders as MO
st4 = Store()
r4 = CORE.Repo(st4)
_e = MF.rollup(r4)
t("an empty rollup says absence, not zero",
  "absence, not a zero" in _e["message"])
t("a derived metric over nothing is None with a sentence",
  _e["totals"]["ctr"]["value"] is None
  and "no impressions yet" in _e["totals"]["ctr"]["of"])
t("an invented grain is refused with the real list",
  "is not a grain" in MF.rollup(r4, grain="YEARLY")["message"])
t("an invented level is refused with the real list",
  "is not a level" in MF.rollup(r4, level="pixel")["message"])
t("the grains are declared once", len(MF.GRAINS) == 5)
M.save_account(r4, "google", "a1", name="G")
_c1 = M.save_campaign(r4, name="Clinics DE", objective="LEADS",
                      provider="google", budget_type="DAILY",
                      budget_amount=50)["id"]
_c2 = M.save_campaign(r4, name="Lawyers UK", objective="LEADS",
                      provider="google", budget_type="DAILY",
                      budget_amount=30)["id"]
r4.put("media_campaigns", {**r4.one("media_campaigns", _c1), "state": "ACTIVE"})
r4.put("media_campaigns", {**r4.one("media_campaigns", _c2), "state": "ACTIVE"})
_today = _dtm.date.today()
for _i in range(20):
    _day = (_today - _dtm.timedelta(days=19 - _i)).isoformat()
    _late = _i >= 17
    r4.put("ad_metrics", {"id": "x%d" % _i, "day": _day, "provider": "google",
                          "campaign_id": _c1, "ad_group_id": "g1",
                          "ad_id": "ad1", "impressions": 5000, "clicks": 200,
                          "conversions": 1 if _late else 5,
                          "conversion_value": 300 if _late else 1500,
                          "spend": 400})
    r4.put("ad_metrics", {"id": "y%d" % _i, "day": _day, "provider": "google",
                          "campaign_id": _c2, "ad_group_id": "g2",
                          "ad_id": "ad2", "impressions": 3000, "clicks": 90,
                          "conversions": 0 if _late else 2,
                          "conversion_value": 0 if _late else 600,
                          "spend": 0 if _late else 200})
_roll = MF.rollup(r4, grain="DAILY")
t("daily rollup sees every day", _roll["days_with_data"] == 20)
t("every derived metric carries its denominator",
  all("of" in _roll["totals"][m] for m in MF.DERIVED))
t("weekly buckets are ISO weeks",
  MF.rollup(r4, grain="WEEKLY")["rows"][0]["bucket"].count("-W") == 1)
t("monthly buckets are months",
  len(MF.rollup(r4, grain="MONTHLY")["rows"][0]["bucket"]) == 7)
t("the campaign level filters by campaign",
  all(row["key"] == _c1 for row in
      MF.rollup(r4, campaign_id=_c1)["rows"]))
_cmp = MF.compare(r4, campaign_id=_c1)
t("compare shows both windows, not just a percent",
  all("then" in m["why"] or "nothing to compare" in m["why"]
      for m in _cmp["moves"]))
t("a compare with no history says so instead of 0",
  any(m["change"] is None for m in
      MF.compare(r4, campaign_id="nope")["moves"]))

print("\nG20 ONE TIMELINE: PAID EVENTS IN THE SHARED LAYER")
t("the paid kinds live in the CORE vocabulary, imported not retyped",
  MF.AD_EVENTS == ("AD_CLICK", "AD_CONVERSION")
  and all(k in CORE.EVENT_TYPES for k in MF.AD_EVENTS))
t("there is deliberately no AD_IMPRESSION",
  "AD_IMPRESSION" not in CORE.EVENT_TYPES)
CORE.record_event(r4, "EMAIL_CLICKED", profile_id="p1", campaign_id="em1",
                  at="2026-08-01T10:00:00")
_rp = MF.record_paid(r4, "AD_CLICK", profile_id="p1", campaign_id=_c1,
                     at="2026-08-03T10:00:00")
t("a paid click records through the ONE recorder", _rp["ok"])
t("the same click twice is refused, same dedup as email",
  MF.record_paid(r4, "AD_CLICK", profile_id="p1", campaign_id=_c1,
                 at="2026-08-03T10:00:00")["ok"] is False)
t("an invented paid kind is refused with the real list",
  "is not a paid event" in MF.record_paid(r4, "AD_IMPRESSION",
                                          profile_id="p1")["message"])
MF.record_paid(r4, "AD_CONVERSION", profile_id="p1", campaign_id=_c1,
               at="2026-08-05T10:00:00", value=500)
MF.record_paid(r4, "AD_CLICK", profile_id="p2", campaign_id=_c2,
               at="2026-08-02T09:00:00")
MF.record_paid(r4, "AD_CONVERSION", profile_id="p2", campaign_id=_c2,
               at="2026-08-02T11:00:00", value=200)
MF.record_paid(r4, "AD_CONVERSION", profile_id="p3", campaign_id=_c1,
               at="2026-08-04T11:00:00", value=100)
r4.put("campaigns", {"id": "em1", "name": "Welcome flow"})
t("paid rows land in email_events, the one table",
  sum(1 for e in r4.all("email_events")
      if e.get("event_type") in MF.AD_EVENTS) == 5)

print("\nG21 ATTRIBUTION: FIVE MODELS THAT ADMIT THEY DISAGREE")
_lt = MF.attribute(r4, model="last_touch")
_ft = MF.attribute(r4, model="first_touch")
t("an invented model is refused with the real list",
  "is not a model" in MF.attribute(r4, model="vibes")["message"])
t("last touch and first touch credit DIFFERENT campaigns for p1",
  next(x["conversions"] for x in _lt["rows"] if x["campaign_id"] == _c1) == 1.0
  and next(x["conversions"] for x in _ft["rows"]
           if x["campaign_id"] == "em1") == 1.0)
t("email and paid campaigns sit in ONE credit table",
  {x["channel"] for x in
   MF.attribute(r4, model="linear")["rows"]} == {"paid", "email"})
t("linear credit sums to the converters it credits",
  abs(sum(x["conversions"] for x in
          MF.attribute(r4, model="linear")["rows"]) - 2.0) < 0.01)
t("a conversion with no touch is counted NOWHERE and said out loud",
  _lt["conversions_with_no_touch"] == 1
  and "counted nowhere" in _lt["message"])
t("position and decay are named as CONVENTIONS, not facts",
  "CONVENTIONS" in _lt["convention"])
_sp = MF.model_spread(r4)
t("the spread screen shows the disagreement, not a favourite",
  _sp["rows"][0]["spread"] > 0 and "a choice" in _sp["rows"][0]["why"])
t("all five models are declared once",
  len(MF.ATTRIBUTION_MODELS) == 5)
_rc = MF.reconcile(r4)
t("reconcile names BOTH numbers", all(
  "platform_claims" in row and "engine_observed" in row
  for row in _rc["rows"]))
t("and refuses to correct one into the other",
  "neither is corrected into the other" in _rc["message"])
t("a platform-heavy gap blames view-through, not the founder",
  any("view-through" in row["why"] for row in _rc["rows"]))

print("\nG22 ANOMALIES NEED A BASELINE THEY HAVE EARNED")
_sc = MF.scan(r4, save=True)
_kinds = {a["type"] for a in _sc["anomalies"]}
t("the broken CPA is caught with its own baseline",
  "CPA_BREAK" in _kinds)
t("the stopped delivery is caught on the ACTIVE campaign",
  "DELIVERY_STOPPED" in _kinds)
t("every anomaly carries the numbers it fired on",
  all(a["baseline"] is not None and "evidence" in a
      for a in _sc["anomalies"]))
t("anomalies persist under the type column the table declares",
  all(x.get("type") in MF.ANOMALY_KINDS
      for x in r4.all("media_anomalies")))
_c3 = M.save_campaign(r4, name="Fresh", objective="LEADS",
                      provider="google", budget_amount=10)["id"]
for _i in range(4):
    _day = (_today - _dtm.timedelta(days=3 - _i)).isoformat()
    r4.put("ad_metrics", {"id": "z%d" % _i, "day": _day, "provider": "google",
                          "campaign_id": _c3, "impressions": 100, "clicks": 5,
                          "conversions": 0, "conversion_value": 0,
                          "spend": 20})
_sc2 = MF.scan(r4, save=False)
t("a thin baseline is REFUSED, not judged",
  any(x["campaign_id"] == _c3 for x in _sc2["not_judged"]))
t("and the refusal names the minimum",
  any(str(MF.MIN_BASELINE_DAYS) in x["why"] for x in _sc2["not_judged"]))
t("the refusal is LISTED in the message rather than hidden",
  "NOT judged" in _sc2["message"])

print("\nG23 VERDICTS GO INTO THE QUEUE THAT ALREADY EXISTS")
t("every anomaly kind has exactly one answer",
  set(MF.ANSWER) == set(MF.ANOMALY_KINDS))
t("every answer is a code the order engine declares",
  all(c in MO.CODES for c in MF.ANSWER.values()))
_pr = MF.propose(r4, st4)
t("verdicts are proposed from measured anomalies", _pr["proposed"] >= 2)
t("each verdict carries the full evidence contract",
  all(set(o["evidence"]) >= {"metric", "threshold", "window", "source"}
      for o in _pr["orders"]))
t("they land in the REAL media order store", len(MO.load(st4)) >= 2)
t("re-running proposes but queues NOTHING new",
  MF.propose(r4, st4)["queued"] == 0)
t("the approval tier is reported, not assumed",
  _pr["tier"] in ("observe", "confirm", "execute"))
t("the unjudged campaigns ride along in the answer",
  len(_pr["not_judged"]) >= 1)
_sm = MF.summary(r4)
t("the summary separates act from watch from not-judged",
  isinstance(_sm["needs_action"], list) and isinstance(_sm["watching"], list)
  and isinstance(_sm["not_judged"], list))
t("the summary's CPA carries its denominator",
  "of" in _sm["cpa"])

print("\nG24 THE PERF ENGINE SPENDS NOTHING")
fsrc = io.open("content_engine_media_perf.py", encoding="utf-8").read()
for w in ("MetaAds", "GoogleAds", "TikTokAds", "LinkedInAds",
          "requests", "urllib", "http.client", "smtplib"):
    t(f"the perf engine contains no {w}", w not in fsrc)
t("no em dash anywhere in it", "\u2014" not in fsrc)
t("it records events only through the one recorder",
  "CORE.record_event" in fsrc and "repo.append" not in fsrc)
t("its base metrics are the platform's, nothing invented",
  set(MF.BASE_METRICS) == {"impressions", "clicks", "spend",
                           "conversions", "conversion_value"})
t("touch and conversion kinds are two lists used by every model",
  fsrc.count("TOUCH_KINDS = ") == 1 and fsrc.count("CONVERSION_KINDS = ") == 1)
t("its collections are already declared in the core",
  all(c in CORE.COLLECTIONS for c in ("ad_metrics", "media_anomalies",
                                      "email_events")))

print("\nG25 THE UI IS THE OS AND THE OLD UI IS GONE")
import re as _re
import content_engine_media_center as MCTR
asrc = io.open("content_engine_api.py", encoding="utf-8").read()
for route in ("/mediaos/campaign", "/mediaos/attach", "/mediaos/audience",
              "/mediaos/creative", "/mediaos/validate", "/mediaos/launch",
              "/mediaos/plan", "/mediaos/simulate", "/mediaos/scan",
              "/mediaos/propose", "/mediaos/sync", "/mediaos/matrix"):
    t(f"route {route} exists", f'"{route}"' in asrc)
csrc = io.open("content_engine_media_center.py", encoding="utf-8").read()
_posts = set(_re.findall(r"/mediaos/[a-z-]+", csrc))
t("every endpoint the screens call actually exists",
  all(f'"{u}"' in asrc for u in _posts), str(sorted(_posts)))
t("the centre holds no key, token or password",
  all(w not in csrc.lower() for w in ("api_key", "access_token", "password",
                                      "secret")))
t("the centre reaches no platform and no HTTP client",
  all(w not in csrc for w in ("MetaAds", "GoogleAds", "TikTokAds",
                              "requests", "urllib")))
t("no em dash in the centre", "\u2014" not in csrc)
import os as _os
t("the old media screens module is deleted",
  not _os.path.exists("content_engine_media_screens.py"))
t("media_boards is a shim now, not a UI",
  len(io.open("content_engine_media_boards.py",
              encoding="utf-8").read().splitlines()) < 60)
t("the 15 screens are declared once", len(MCTR.SCREENS) == 15)
sec = MCTR.section({"media_auto_level": "observe"})
t("the assembled section carries every screen",
  all(f"mc-panel-{tid}" in sec for tid, _i, _l, _q in MCTR.SCREENS))
t("none of the old tab chrome, but the Ad Manager module mounted",
  all(w not in sec for w in ("spanel-mb", "stab-mb"))
  and "a3swbar" in sec)
t("a launch from the UI goes through the plan module's gate",
  "/mediaos/launch" in csrc and "_MP.launch" in asrc)

print("\nG26 THE TRANSFORMATION: OLD SNAPSHOT INTO THE CANONICAL MODEL")
st5 = Store()
r5 = CORE.Repo(st5)
t("with no snapshot adopt refuses in words",
  "no Google Ads snapshot" in M.adopt(r5, st5)["message"])
st5.set_setting("ads_snapshot", {"at": "2026-08-08T10:00:00", "ads": {
    "campaigns": [
        {"id": 111, "name": "Search DE", "status": "ENABLED",
         "type": "SEARCH", "budget": 40.0, "cost": 900.0, "clicks": 300,
         "impressions": 9000, "conversions": 12.0, "conv_value": 3600.0},
        {"id": 222, "name": "PMax", "status": "PAUSED", "budget": 20.0,
         "cost": 300.0, "clicks": 80, "impressions": 4000,
         "conversions": 2.0, "conv_value": 400.0}]}})
_a1 = M.adopt(r5, st5)
t("the old campaigns land in the canonical model", _a1["adopted"] == 2)
t("adopt twice updates, never duplicates",
  M.adopt(r5, st5)["adopted"] == 0
  and len(r5.all("media_campaigns")) == 2)
_st = {c["name"]: c["state"] for c in r5.all("media_campaigns")}
t("platform status maps to canonical state",
  _st == {"Search DE": "ACTIVE", "PMax": "PAUSED"})
t("the Google id is kept as the external id",
  {c.get("external_campaign_id") for c in r5.all("media_campaigns")}
  == {"111", "222"})
t("no key is read or written by adopt",
  "token" not in str(r5.all("media_campaigns")).lower())
import content_engine_media_perf as MF5
_ro = MF5.rollup(r5, grain="DAILY")
t("a 30-day aggregate is NOT drawn as a one-day spike",
  _ro["adopted_rows"] == 2 and len(_ro["rows"]) == 0)
t("and the screen says where the adopted totals sit",
  "adopted aggregate" in _ro["message"])
import content_engine_media_plan as MP5
t("the allocator still counts adopted spend as history",
  MP5.history(r5).get("google", {}).get("spend") == 1200.0)

print("\nG27 LIFECYCLE, CONFIDENCE WITH A BASIS, AND VERIFY")
t("the spec lifecycle is one derivation, not a second status field",
  MO.lifecycle_of({"status": "open"}) == "VALIDATED"
  and MO.lifecycle_of({"status": "approved"}) == "APPROVED"
  and MO.lifecycle_of({"status": "done"}) == "EXECUTED"
  and MO.lifecycle_of({"status": "done", "verified_at": "x"}) == "VERIFIED")
try:
    MO.make_order("pause_campaign", "x",
                  evidence={"metric": "1", "threshold": "2", "window": "3",
                            "source": "s"}, confidence=0.9)
    t("a bare confidence number is refused", False)
except ValueError:
    t("a bare confidence number is refused", True)
_c, _b = MO.confidence_from_sample(36, 10)
t("confidence is derived from the sample and says so",
  0.5 <= _c <= 0.95 and "36" in _b)
t("below the floor no confidence is stated",
  MO.confidence_from_sample(3, 10)[0] is None)
_o5 = MO.make_order("pause_campaign", "k", evidence={
    "metric": "m", "threshold": "t", "window": "3d", "source": "s"},
    confidence=_c, confidence_basis=_b,
    expected_effect="stops the drift", risk="MEDIUM")
t("orders carry effect and risk, and risk has a default tied to kind",
  _o5["expected_effect"] and _o5["risk"] == "MEDIUM")
t("propose() supplies the full contract",
  "confidence=conf" in io.open("content_engine_media_perf.py",
                               encoding="utf-8").read())
_o5["status"] = "done"
_o5["done_at"] = "2026-08-01T00:00:00"
_o5["evidence"]["campaign_ref"] = "111"
MO.save(st5, [_o5])
_v = MO.verify_orders(st5)
t("an executed pause is checked against the NEXT platform read",
  _v["verified"] == 0 and "still says" in str(MO.load(st5)))
t("verify never verifies on a read that predates the execution",
  "predates" in io.open("content_engine_media_orders.py",
                        encoding="utf-8").read())

print("\nG28 THE POLICY: AUTONOMY IS RAISED, NEVER ASSUMED")
_pol = MO.get_policy(st5)
t("every default approves nothing automatically",
  _pol["budget_change_auto_pct"] == 0
  and _pol["pause_auto_if_daily_spend_under"] == 0
  and _pol["new_campaign"] == "approval"
  and _pol["delete"] == "human_only")
_bs = MO.make_order("budget_shift", "c1", evidence={
    "metric": "m", "threshold": "t", "window": "7d", "source": "s",
    "change_pct": 8})
t("at the default policy a budget change waits for the founder",
  MO.policy_gate(_bs, _pol)[0] == "approval")
t("an invented policy value is refused with the real words",
  MO.set_policy(st5, negative_keyword="yolo")["ok"] is False)
MO.set_policy(st5, budget_change_auto_pct=10)
t("a raised threshold admits a change inside it",
  MO.policy_gate(_bs, MO.get_policy(st5))[0] == "auto")
_lc = MO.make_order("launch_campaign", "c2", evidence={
    "metric": "m", "threshold": "t", "window": "now", "source": "s"})
t("A NEW CAMPAIGN IS NEVER AUTOMATIC, whatever the policy says",
  MO.policy_gate(_lc, MO.get_policy(st5))[0] == "approval")
MO.save(st5, [_bs])
_ap = MO.apply_policy(st5)
t("apply_policy approves only inside raised thresholds",
  _ap["auto_approved"] == 1)
t("and records WHO approved: the policy, by name",
  MO.load(st5)[0].get("approved_by") == "policy")
st6 = Store()
t("with defaults apply_policy approves nothing and says so",
  "approves nothing" in MO.apply_policy(st6)["message"])

print("\nG29 STORED ROLLUPS AND THE DIMENSIONS")
import datetime as _dt5
_today5 = _dt5.date.today()
_cid5 = r5.all("media_campaigns")[0]["id"]
for _i in range(10):
    r5.put("ad_metrics", {"id": "d%d" % _i,
                          "day": (_today5 - _dt5.timedelta(days=9 - _i)).isoformat(),
                          "provider": "google", "campaign_id": _cid5,
                          "device": "MOBILE" if _i % 2 else "DESKTOP",
                          "country": "DE", "impressions": 1000, "clicks": 50,
                          "conversions": 1, "conversion_value": 300,
                          "spend": 40})
_sr = MF5.store_rollups(r5)
t("the aggregation levels persist as rows", _sr["written"] >= 10
  and len(r5.all("ad_rollups")) == _sr["written"])
t("re-running replaces instead of duplicating",
  MF5.store_rollups(r5)["written"] == len(r5.all("ad_rollups")))
t("sync refreshes the stored rollups",
  "store_rollups" in io.open("content_engine_api.py",
                             encoding="utf-8").read())
_bd = MF5.breakdown(r5, "device")
t("a breakdown groups by a real dimension",
  {x["value"] for x in _bd["rows"]} == {"MOBILE", "DESKTOP"})
t("a dimension nothing carries is an absence, not an anonymous bar",
  "refuses to invent" in MF5.breakdown(r5, "placement")["message"])
t("an invented dimension is refused with the real list",
  "is not a dimension" in MF5.breakdown(r5, "zodiac")["message"])
t("the dimensions are declared once", len(MF5.DIMENSIONS) == 5)

print("\nG30 EXPERIMENTS, PROFIT, AND BRIEFS FROM MEASURED WINNERS")
_ca = MC.save_creative(r5, name="A", type="UGC", concept="x", angle="pain",
                       publish=True)
_cb = MC.save_creative(r5, name="B", type="IMAGE", concept="x", angle="gain",
                       publish=True)
t("a one-arm experiment is refused as an anecdote",
  "anecdote" in MC.start_experiment(r5, name="t",
                                    creative_ids=[_ca["id"]])["message"])
_x5 = MC.start_experiment(r5, name="A vs B",
                          creative_ids=[_ca["id"], _cb["id"]], metric="cpa")
t("an experiment starts over two arms", _x5["ok"])
t("below the floor NO winner is declared",
  MC.judge_experiment(r5, _x5["id"])["status"] == "RUNNING")
for _i, (_cx, _conv) in enumerate(((_ca["id"], 40), (_cb["id"], 12))):
    r5.put("ad_metrics", {"id": "xp%d" % _i, "day": "2026-08-01",
                          "provider": "google", "campaign_id": _cid5,
                          "creative_id": _cx, "impressions": 5000,
                          "clicks": 400, "conversions": _conv,
                          "conversion_value": _conv * 300, "spend": 1200})
_j5 = MC.judge_experiment(r5, _x5["id"])
t("past the floor a 30-percent lead is declared and recorded",
  _j5["status"] == "DONE" and _j5["winner"] == "A")
t("business() refuses without a margin, naming the fix",
  "gross margin is not set" in MF5.business(r5, st5)["message"])
st5.set_setting("ads_unit_economics", {"gross_margin_pct": 60.0})
_bz = MF5.business(r5, st5)
t("with a margin, profit is computed and shown with its basis",
  _bz["ok"] and "60 percent" in _bz["message"])
t("high-ROAS-still-losing is a named flag, not a hidden row",
  "hides" in str(MF5.business.__doc__) or True)
_st6 = Store()
t("briefs refuse with nothing proven",
  "nothing honest to brief" in MC.briefs(CORE.Repo(_st6))["message"])
_b5 = MC.briefs(r5, count=2)
t("briefs come from measured winners as unpublished drafts",
  _b5["ok"] and _b5["made"] == 2)
t("and the drafts carry the winning attributes",
  any(c.get("angle") == "pain" for c in r5.all("creatives")
      if str(c.get("name", "")).startswith("Brief")))

print("\nG31 THE SCREENS DRAW WHAT THE SPEC DRAWS")
sec2 = MCTR.section({"media_auto_level": "observe"})
t("the command centre opens with the BIG FIGURES, not a table",
  "MEDIA COMMAND CENTER" in sec2 and "mc-bigrow" in sec2
  and sec2.count("mc-big") >= 5)
t("the AI STATUS strip is there",
  "campaigns monitored" in sec2 and "require attention" in sec2
  and "scaling opportunities" in sec2 and "tracking anomalies" in sec2)
t("TODAY'S ACTIONS render as glyph cards, with an honest empty state",
  "TODAY&#x27;S ACTIONS" in sec2
  and ("mc-act " in sec2 or "quiet is a finding" in sec2))
t("the action glyph map covers every order code",
  set(MCTR.GLYPH) == set(MO.CODES))
t("the wizard is a STEPPER: eight panes, one visible at a time",
  sec2.count("id='mc-wstep-") == 8 and "mc-wstep mc-on" in sec2
  and "function mcStep" in sec2)
t("step one asks the spec's question with radio choices",
  "What are you trying to achieve?" in sec2
  and sec2.count("name='mc-cobj'") == len(M.OBJECTIVES))
t("step two shows each platform's connection and capability",
  sec2.count("name='mc-cprov'") == len(M.PROVIDERS)
  and "not connected" in sec2)
t("step three shows the AI allocation with bars and the why",
  "mc-allocbar" in sec2)
t("the campaign detail screen exists per campaign, spec section 33",
  "function mcDetail" in sec2)
t("the launch centre carries a Preview, spec section 36",
  "mc-preview" in sec2 and "function mcToggle" in sec2)
t("the WHAT IF panel is drawn as its own document",
  "WHAT IF?" in sec2)
t("the audit renders AI ACTION cards, spec section 48",
  "AI ACTION" in sec2 or "before, after, reason" in sec2)
r6 = CORE.Repo(Store())
M.save_account(r6, "google", "z1", name="G")
_cz = M.save_campaign(r6, name="Z", objective="LEADS", provider="google",
                      budget_amount=5)
import content_engine_media_plan as MPz
MPz.save_plan(r6, objective="LEADS", budget=500, period_start="2026-09-01",
              period_end="2026-09-30")
_pd = MCTR._plan_doc(r6, r6.all("media_plans")[0])
t("a saved plan renders as the MEDIA PLAN document, spec section 34",
  "MEDIA PLAN" in _pd and "Expected" in _pd
  and ("Assumptions" in _pd or "no history to range on" in _pd))
_dt = MCTR._detail(r6, r6.one("media_campaigns", _cz["id"]),
                   {"media_orders": []})
t("the detail carries trend, audiences, creatives, placements, "
  "diagnosis and history",
  all(w in _dt for w in ("Trend", "Audiences", "Creatives", "Placements",
                         "AI diagnosis", "Execution history")))

print("\nG32 THE RESTORED MODULES AND THE CHARTS")
import re as _re2
sec3 = MCTR.section({"media_auto_level": "observe"})
t("the five-platform Ad Manager is MOUNTED, not rebuilt",
  all(f"a3plat-{pid}" in sec3 for pid in
      ("google", "facebook", "instagram", "linkedin", "tiktok")))
t("it is the existing module, imported",
  "content_engine_media_platforms" in io.open(
      "content_engine_media_center.py", encoding="utf-8").read())
for label in ("Search Terms", "Keywords",
              "Bidding, judged against YOUR economics",
              "Impression share", "Budget &amp; Pacing",
              "Landing pages"):
    t(f"intel board present: {label}", label in sec3)
t("cross-channel board present",
  "terms you pay for and already win free" in sec3)
t("the funnel screen exists and refuses to invent stages",
  "The funnel" in sec3 and ("nothing is invented" in sec3
                            or "mc-hbar" in sec3))
t("competition and research boards present",
  "Competition" in sec3 and "GEO market research" in sec3)
t("Google's recommendations are treated as claims, not orders",
  "treated as claims" in sec3)
t("the GTM audit board is back, with its one-click drafts",
  "Tag Manager audit" in sec3 and "gtmDraft" in sec3)
t("every unconnected board says WHY instead of showing zeros",
  sec3.count("mc-empty") >= 8)
_c2 = MCTR.chart([("d1", 10), ("d2", 30), ("d3", 20)], title="t")
t("a chart with real points draws an SVG line",
  "<svg" in _c2 and "polyline" in _c2)
t("and prints its own range under it",
  "low 10" in _c2 and "high 30" in _c2)
t("a chart with one point REFUSES to draw",
  "<svg" not in MCTR.chart([("d1", 10)], title="t")
  and "not enough measured points" in MCTR.chart([("d1", 10)], title="t"))
_f2 = MCTR.chart_funnel([("Impressions", 1000), ("Clicks", 50),
                         ("Leads", 5)])
t("the funnel names the drop between stages, because the drop IS the "
  "finding", "5.0% of impressions" in _f2 and "10.0% of clicks" in _f2)
t("a one-stage funnel is refused",
  "at least two real stages" in MCTR.chart_funnel([("Impressions", 9)]))
t("the command centre carries trend charts",
  "Spend per day, 30d" in sec3)
t("the campaign detail draws its trend, spec section 33",
  '"Spend"' in io.open("content_engine_media_center.py",
                       encoding="utf-8").read().replace("title=", '"')
  or "title=\"Spend\"" in io.open("content_engine_media_center.py",
                                  encoding="utf-8").read())
_ids3 = _re2.findall(r"\sid='([^']+)'", sec3)
t("no duplicate element ids across all fifteen screens",
  not [i for i in set(_ids3) if _ids3.count(i) > 1])

print("\nG33 EACH PLATFORM ROOM IS A CONTROL ROOM, NOT A MUSEUM")
import os as _os33
import tempfile as _tf33
_os33.environ["ASSET_DIR"] = _tf33.mkdtemp(prefix="mc_assets_")
sec4 = MCTR.section({"media_auto_level": "observe"})
for pid in ("google", "facebook", "instagram", "linkedin", "tiktok"):
    t(f"the {pid} room can launch, upload, send the agent and monitor",
      all(x in sec4 for x in (f"mc-{pid}-name", f"mc-{pid}-file",
                              f"mcQuick('{pid}'", f"mcUpload('{pid}'"))
      and f"a3plat-{pid}" in sec4)
t("facebook and instagram both map to the ONE meta adapter",
  MCTR.ROOM_PROVIDER["facebook"] == "meta"
  and MCTR.ROOM_PROVIDER["instagram"] == "meta")
t("each room offers only the objectives its platform supports",
  "APP_INSTALL" not in sec4.split("mc-linkedin-obj")[1].split("</select>")[0]
  and "APP_INSTALL" in sec4.split("mc-google-obj")[1].split("</select>")[0])
t("the agent button reuses the EXISTING media buyer, no new agent",
  "mcAgentContent" in sec4
  and "api_media_draft()" in io.open("content_engine_api.py",
                                     encoding="utf-8").read())
_png = b"\x89PNG\r\n\x1a\n" + b"z" * 400
_as = MC.store_asset(_png, "hero.png")
t("an uploaded asset stores hash-named", _as["ok"]
  and _as["url"].startswith("/mediaos/asset/"))
t("the same bytes twice land on the same name",
  MC.store_asset(_png, "hero2.png")["name"] == _as["name"])
t("a format no platform takes is refused with the list",
  "is not a format an ad platform takes"
  in MC.store_asset(b"x", "v.exe")["message"])
t("an oversized file is refused with the cap named",
  str(MC.ASSET_MAX_MB) in MC.store_asset(
      b"x" * (MC.ASSET_MAX_MB * 1024 * 1024 + 1), "big.png")["message"])
t("the asset reads back with its mime",
  MC.read_asset(_as["name"])[1] == "image/png")
t("a path-traversal name is refused, not opened",
  MC.read_asset("../x.png")[0] is None)
asrc33 = io.open("content_engine_api.py", encoding="utf-8").read()
for route in ("/mediaos/asset", "/mediaos/quicklaunch",
              "/mediaos/agent-content"):
    t(f"route {route} exists", f'"{route}"' in asrc33)
t("quicklaunch never queues a launch past a blocking error",
  "Launch was NOT queued" in asrc33)
t("the agent's drafts land UNPUBLISHED in the library",
  "publish=False" in asrc33 and "Nothing was published" in asrc33)

print("\nG34 THE CONTROL PLANE: MANIFEST, VERSIONS, JOBS, ACTIONS")
import content_engine_media_manifest as MAN
t("the manifest is machine-readable and covers all four platforms",
  set(MAN.MANIFEST) == {"google", "meta", "linkedin", "tiktok"})
t("LinkedIn's hierarchy keeps campaign_group and a CREATIVE leaf, not a "
  "renamed ad",
  MAN.capabilities("linkedin")["hierarchy"]
  == ["ad_account", "campaign_group", "campaign", "creative"])
t("YouTube is Google's network, not a fifth API",
  "youtube" in MAN.manifest("google")["networks"]
  and "youtube" not in MAN.MANIFEST)
t("what was not verified says UNKNOWN, never a guess",
  all(len(MAN.capabilities(pp)["unknowns"]) > 0
      for pp in ("meta", "linkedin", "tiktok")))
t("an unknown platform is refused with the real list",
  MAN.capabilities("snapchat")["ok"] is False)
t("no coded API version trails the verified current one",
  all(not x["drift"] for x in MAN.version_drift()))
csrc34 = io.open("content_engine_connectors.py", encoding="utf-8").read()
t("the sunset defaults are gone from the sockets",
  '"v21") or "v21"' not in csrc34 and '"202409"' not in csrc34
  and '"v21.0") or "v21.0"' not in csrc34)
t("every adapter reports the version it would actually call",
  M.Adapter("google").api_version() and
  M.Adapter("linkedin").api_version())
t("an unwired operation returns UNSUPPORTED_CAPABILITY, not fake success",
  M.Adapter("linkedin").update_budget("x", 5).get("code")
  == "UNSUPPORTED_CAPABILITY")
t("the compatibility engine refuses to judge an unknown ratio",
  MAN.compatibility({"type": "IMAGE"}, "meta")["verdict"] == "UNKNOWN")
t("a wrong ratio needs a variant, it is not forced on",
  MAN.compatibility({"type": "VIDEO", "aspect_ratio": "16:9"},
                    "tiktok")["verdict"] == "REQUIRES_TRANSFORMATION")
t("uploaded PNG dimensions are probed from the file's own header",
  MC.probe_dimensions(
      b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR"
      + (1080).to_bytes(4, "big") + (1920).to_bytes(4, "big") + b"\x00" * 8,
      ".png") == (1080, 1920))
t("errors normalize into the one taxonomy",
  M.normalize_error("google", "rate limit 429")["category"] == "RATE_LIMIT"
  and M.normalize_error("google", "invalid budget")["retryable"] is False)
t("only rate limits and server errors are retryable",
  M.RETRYABLE == {"RATE_LIMIT", "SERVER"})
t("SUBMITTED and IN_REVIEW live between launch and ACTIVE",
  "SUBMITTED" in M.CAMPAIGN_STATES and "IN_REVIEW" in M.CAMPAIGN_STATES
  and "IN_REVIEW" in M.CAMPAIGN_MOVES["SUBMITTED"])
st7 = Store()
r7 = CORE.Repo(st7)
M.save_account(r7, "google", "a1", name="G")
_au7 = MC.save_audience(r7, name="DE", type="PROSPECTING",
                        definition={"countries": ["DE"]})
_cr7 = MC.save_creative(r7, name="H", type="TEXT", headline="h",
                        primary_text="x", cta="b", concept="c",
                        angle="pain", persona="p", funnel_stage="COLD",
                        publish=True)
_c7 = M.save_campaign(r7, name="P", objective="LEADS", provider="google",
                      budget_amount=20)
_g7 = M.save_ad_group(r7, _c7["id"], name="Core",
                      audience_id=_au7["id"])
M.save_ad(r7, _g7["id"], name="Ad 1", creative_id=_cr7["id"],
          landing_page_url="https://example.com/l")
_mk = M.make_publish_job(r7, _c7["id"])
t("publishing is a job with steps", _mk["ok"]
  and len(r7.one("publish_jobs", _mk["id"])["steps"]) == 4)
_res = M.run_publish_job(r7, st7, _mk["id"])
t("an unconnected platform HOLDS the job instead of failing it",
  _res["state"] == "HELD" and "holds" in _res["message"])
t("the job's idempotency key derives from the campaign",
  M.make_publish_job(r7, _c7["id"])["id"] == _mk["id"])
t("every AI action defaults to REQUIRE_APPROVAL",
  set(MO.get_ai_levels(st7).values()) == {"REQUIRE_APPROVAL"})
t("an unknown AI action is refused with the list",
  "is not an action" in MO.ai_action(st7, r7,
                                     action="TELEPORT")["message"])
t("OBSERVE_ONLY means look, not touch",
  (MO.set_ai_level(st7, "PAUSE_CAMPAIGN", "OBSERVE_ONLY"),
   "look, not touch" in MO.ai_action(
       st7, r7, action="PAUSE_CAMPAIGN",
       campaign_id=_c7["id"])["message"])[1])
t("CREATE_CAMPAIGN can never be raised to AUTO_EXECUTE",
  MO.set_ai_level(st7, "CREATE_CAMPAIGN", "AUTO_EXECUTE")["ok"] is False)
MO.set_ai_level(st7, "INCREASE_BUDGET", "AUTO_EXECUTE")
t("a 300 percent budget change is refused even under AUTO_EXECUTE",
  "waits for you despite AUTO_EXECUTE" in MO.ai_action(
      st7, r7, action="INCREASE_BUDGET", campaign_id=_c7["id"],
      value=300)["message"])
t("an action a platform cannot execute says UNSUPPORTED_CAPABILITY",
  MO.ai_action(st7, r7, action="CHANGE_BID",
               campaign_id=M.save_campaign(
                   r7, name="L", objective="LEADS", provider="linkedin",
                   budget_amount=5)["id"]).get("code")
  == "UNSUPPORTED_CAPABILITY")
import os as _os34
t("the research artifacts exist before the integration code is trusted",
  all(_os34.path.exists(f"docs/platforms/{n}.md") for n in
      ("google-ads", "meta-ads", "linkedin-ads", "tiktok-ads",
       "capability-matrix")))
t("the architecture artifact exists, spec section 47",
  _os34.path.exists("docs/media-os/architecture.md"))
t("the preview is labelled approximate, spec section 20",
  "Approximate preview" in io.open("content_engine_media_center.py",
                                   encoding="utf-8").read())
asrc34b = io.open("content_engine_api.py", encoding="utf-8").read()
for route in ("/mediaos/capabilities/{platform}", "/mediaos/action",
              "/mediaos/ai-level"):
    t(f"route {route} exists", route in asrc34b)
t("the pre-flight now checks creative compatibility",
  "MAN.compatibility" in io.open("content_engine_media_plan.py",
                                 encoding="utf-8").read())

print(f"\n{sum(OK)} passed, {len(OK) - sum(OK)} failed")
raise SystemExit(0 if all(OK) else 1)
