"""ONE CONTENT VOCABULARY — the guard.

There were FIVE lists of content types across four files and only the word
"blog" appeared in all of them. The strategist wrote the type; the image gate
read it; their lists shared one word. So every piece that was not a blog got
no hero image — no error, no card, nothing. The WordPress and LinkedIn
previews then honestly showed a picture-less piece and said nothing at all.

Every unit test passed the whole time, because the fixtures said type="blog"
and I wrote the fixtures. A test that supplies both sides of an agreement
cannot detect a disagreement.

This file supplies neither side. It reads the real modules and asserts they
agree.

    python verify_vocabulary.py
"""
import sys

import content_engine_site_taxonomy as T
import content_engine_prep as P
import content_engine_factory as F
import content_engine_schemas as S

FAILS = []


def chk(ok, label, detail=""):
    print(("  OK   " if ok else "  FAIL ") + label + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


print("== 1. nobody re-types the list ==")
src_prep = open("content_engine_prep.py", encoding="utf-8").read()
src_fact = open("content_engine_factory.py", encoding="utf-8").read()
for name, src in (("prep", src_prep), ("factory", src_fact)):
    chk('"case_study"' not in src and "'case_study'" not in src,
        f"{name} no longer carries its own copy of the type list",
        "a second hand-written list is how this broke the first time")
chk("wants_image" in src_prep, "the image gate asks the vocabulary")

# THE CHECK I SHOULD HAVE WRITTEN FIRST. Scoping the guard to the image gate
# let an identical bug survive four lines away: _ensure_linkedin_post compared
# against a hard-coded ("blog", "guide") and dropped every carousel and reel.
# Scan for ANY type comparison written as a literal.
print("== 1b. nobody compares against a hand-written list of types ==")
import re as _re
_KNOWN = set(T.CONTENT_TYPES) | {"social", "post", "article", "case_study"}
for _f in ("content_engine_prep.py", "content_engine_factory.py",
           "content_engine_orchestrator.py"):
    _s = open(_f, encoding="utf-8").read()
    _hits = []
    for _m in _re.finditer(r"(?:not\s+in|in)\s*\(([^()]*)\)", _s):
        _lits = _re.findall(r"[\"']([a-z_]+)[\"']", _m.group(1))
        if len([x for x in _lits if x in _KNOWN]) >= 2:
            _hits.append(_m.group(0)[:58])
    chk(not _hits, f"{_f} compares no hand-written type list",
        "; ".join(_hits) + " - ask the vocabulary instead" if _hits else "")


print("\n== 2. every type the strategist may PLAN is a real content type ==")
raw = getattr(S.SCHEMAS["content_strategist"], "schema", S.SCHEMAS["content_strategist"])
enum = raw["properties"]["calendar"]["items"]["properties"]["type"]["enum"]
chk(bool(enum), f"the strategist enum is populated ({len(enum)})", ", ".join(enum))
stray = [t for t in enum if t not in T.CONTENT_TYPES]
chk(not stray, "every plannable type is in CONTENT_TYPES",
    f"the strategist can emit {stray} and nothing downstream knows the word"
    if stray else "")
chk(set(enum) == set(T.PLANNABLE_TYPES),
    "the enum IS PLANNABLE_TYPES, not a copy that drifted")

print("\n== 3. every type the strategist writes reaches the image gate ==")
for t in T.PLANNABLE_TYPES:
    decided = T.wants_image(t)
    chk(isinstance(decided, bool), f"{t}: the gate has an answer",
        "yes, gets an image" if decided else "deliberately no image")
# the real bug, stated as a test: a non-blog piece must not silently lose its
# picture just because two files disagreed about a word.
for t in ("social_carousel", "reel", "guide"):
    chk(T.wants_image(t), f"{t} gets a hero image",
        "this is the exact case that silently failed" if not T.wants_image(t) else "")

print("\n== 4. an UNKNOWN type gets a picture, it does not lose one ==")
chk(T.wants_image("some_type_invented_next_year"),
    "an unrecognised type still gets an image",
    "opt-out, not opt-in — a new type must not vanish from the previews")
chk(not T.wants_image("email"), "email is the deliberate exception")

print("\n== 5. factory.IMAGE_TYPES is derived, and agrees ==")
chk(set(F.IMAGE_TYPES) == {t for t in T.CONTENT_TYPES if T.wants_image(t)},
    "IMAGE_TYPES matches the vocabulary exactly", str(F.IMAGE_TYPES))

print("\n== 6. every plannable type has a writing length ==")
for t in T.PLANNABLE_TYPES:
    chk(t in P._LENGTH_BY_TYPE, f"{t}: has a length brief",
        "" if t in P._LENGTH_BY_TYPE else
        "it would silently be written at blog length")

print("\n== 7. every content type routes to a WordPress section ==")
for t in T.CONTENT_TYPES:
    chk(t in T.KIND_CATEGORY, f"{t}: routes to {T.KIND_CATEGORY.get(t, '(nowhere)')}")

print("\n== 8. a missing image must state a REASON, never stay silent ==")
chk("image_error" in src_prep and "image_skipped" in src_prep,
    "the gate records why an image is missing")
src_ops = open("content_engine_seo_ops.py", encoding="utf-8").read()
chk("image_state" in src_ops, "the factory context reads that reason back out",
    "a diagnostic nobody renders is not a diagnostic")
src_brd = open("content_engine_factory_boards.py", encoding="utf-8").read()
chk('ctx.get("image_state")' in src_brd,
    "and a CARD on the Creative & image board shows it")
chk("image_reason" in src_fact,
    "the empty preview box prints the reason too")

# the render must actually contain it — not just the code path existing
box = F._img_box.__wrapped__ if hasattr(F._img_box, "__wrapped__") else F._img_box
F.previews({"title": "t", "body": "b"}, ["wordpress"], image_reason="BECAUSE-X")
html = F.previews({"title": "t", "body": "b"}, ["wordpress"],
                  image_reason="BECAUSE-X")["by_platform"]["website"]["html"]
chk("BECAUSE-X" in html, "the reason survives all the way into the HTML",
    "this is the assertion that would have caught the whole bug")

print("\n== 9. the publisher and the boards mean the same thing by a CHANNEL ==")
import content_engine_code_skills as CS

chk(all(k in T.CHANNELS for k in F.PLATFORMS),
    "every PLATFORMS key is a canonical channel", ", ".join(F.PLATFORMS))
chk(T.channel("wordpress") == "website" and T.channel("website") == "website",
    "'wordpress' and 'website' are the same channel",
    "these two lists shared NOTHING: a job saying 'website' was handed to the "
    "social poster as if it were a social network")
chk(CS._target_channels({}) == ["website"],
    "the publisher's default is a canonical channel",
    str(CS._target_channels({})))
src_cs = open("content_engine_code_skills.py", encoding="utf-8").read()
chk('"cms", "web", "blog"' not in src_cs,
    "the publisher no longer carries its own CMS name list",
    "a second hand-written list is how this broke")
chk("is_website" in src_cs, "it asks the vocabulary instead")

# the behaviour, not just the wiring: every alias must reach the CMS branch
_saved = (CS.PUBLISH_FN, CS.SOCIAL_FN)
CS.PUBLISH_FN = lambda job, piece: "WP"
CS.SOCIAL_FN = lambda job, piece, ch: "SOC-" + ch
try:
    for _alias in ("website", "wordpress", "wp", "cms", "blog"):
        _j = {"job_id": "v", "payload": {"config": {"deploy_channels": [_alias]},
                                         "content_producer": {"title": "t"}}}
        _r = CS.publisher(_j)
        chk(_r["channels"].get("website") == "WP",
            f"deploy_channels=['{_alias}'] publishes to the SITE",
            f"went to {_r['channels']} instead" if _r["channels"].get("website")
            != "WP" else "")
    _j = {"job_id": "v2", "payload": {"config": {"deploy_channels": ["X", "ig"]},
                                      "content_producer": {"title": "t"}}}
    _r = CS.publisher(_j)
    chk(set(_r["channels"]) == {"twitter", "instagram"},
        "social aliases route to the social poster", str(_r["channels"]))
finally:
    CS.PUBLISH_FN, CS.SOCIAL_FN = _saved

print()
if FAILS:
    print(f"{len(FAILS)} VOCABULARY BREAK(S): {FAILS}")
    sys.exit(1)
print("ONE VOCABULARY — the strategist, the image gate, the factory, the length "
      "table and the WordPress routing all mean the same thing by a type, and a "
      "missing picture states its reason all the way to the preview.")


print("\n== 10. a long piece carries SECTION images, not one hero ==")
import content_engine_connectors as _CC
import content_engine_factory as _FA

chk("image_prompts" in getattr(S.SCHEMAS["content_producer"], "schema",
                               {}).get("properties", {}),
    "content_producer may return image_prompts",
    "additionalProperties is false, so without the field the writer's prompts "
    "are REJECTED, not ignored")
_in = P._in_content_producer({"payload": {"config": {"produce_index": 0},
    "content_strategist": {"calendar": [{"type": "blog"}]}}})
chk(bool(_in.get("structure")), "the brief asks for a structure, not just a length",
    str(_in.get("structure", {}).get("images")) + " images, "
    + str(_in.get("structure", {}).get("sections")) + " sections, min "
    + str(_in.get("structure", {}).get("min_words")) + " words")
chk(_in.get("structure", {}).get("images", 0) >= 4,
    "at least 4 images are requested")

# the behaviour: 4 prompts must become 4 images, each AFTER its own section
_orig = _CC.generate_image
_n = [0]
_CC.generate_image = lambda pr, size="1024x1024": (
    _n.__setitem__(0, _n[0] + 1) or f"https://cdn/s{_n[0]}.png")
try:
    _nl = chr(10)
    _body = _nl.join(f"## Section {i}{_nl}{_nl}Text {i}.{_nl}" for i in range(1, 5))
    _job = {"job_id": "v", "payload": {"config": {"produce_index": 0},
        "content_strategist": {"calendar": [{"type": "blog"}]},
        "content_producer": {"title": "T", "body": _body,
                             "image_prompts": ["a", "b", "c", "d"]}}}
    P._ensure_hero_image(_job)
    _pc = _job["payload"]["content_producer"]
    chk(_job["payload"].get("section_images") == 4,
        f"4 prompts produced {_job['payload'].get('section_images')} section images")
    chk(_pc["body"].count("![") == 5, "hero + 4 section images in the body",
        f"{_pc['body'].count('![')} found")
    _before = _pc["body"]
    P._ensure_hero_image(_job)
    chk(_job["payload"]["content_producer"]["body"] == _before,
        "re-running does NOT duplicate images")
    # and the preview must SHOW them — it used to `continue` past every inline
    # image, so four generated pictures would have previewed as none
    _html = _FA.preview_website({"title": "T", "body": _pc["body"],
                                 "image_url": _pc.get("image_url")})["html"]
    chk(_html.count("<img ") == 5, "all 5 reach the PREVIEW",
        f"{_html.count('<img ')} rendered — the preview used to drop inline images")
finally:
    _CC.generate_image = _orig


print("\n== 11. every plannable type gets a ceiling it can actually write in ==")
import content_engine_providers as PROV

for t in T.PLANNABLE_TYPES:
    _len = P._LENGTH_BY_TYPE.get(t, "")
    _cap = PROV._max_tokens_for("content_producer", {"type": t, "length": _len})
    _words = [int(x) for x in _re.findall(r"(\d{3,5})", _len)]
    _need = int(max(_words) * 2.0) if _words else 0
    chk(_cap >= max(900, _need),
        f"{t}: {_cap} tokens for '{_len}'",
        f"needs about {_need} to write {max(_words) if _words else '?'} words")

# the exact production failure, as a test: a guide used to get 400 because the
# rule was `2600 if type == "blog" else 400` - one word in a list.
chk(PROV._max_tokens_for("content_producer",
                         {"type": "guide",
                          "length": P._LENGTH_BY_TYPE["guide"]}) > 4000,
    "a guide is not sized like a tweet",
    "it got 400 tokens in production and died before writing a sentence")
chk(PROV._max_tokens_for("content_producer", {"structure": {"sections": 4}}) >= 4000,
    "a long-form piece with no parsable length still gets room")
