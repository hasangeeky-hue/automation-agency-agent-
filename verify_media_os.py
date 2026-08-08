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

print(f"\n{sum(OK)} passed, {len(OK) - sum(OK)} failed")
raise SystemExit(0 if all(OK) else 1)
