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

print()
if FAILS:
    print(f"{len(FAILS)} VOCABULARY BREAK(S): {FAILS}")
    sys.exit(1)
print("ONE VOCABULARY — the strategist, the image gate, the factory, the length "
      "table and the WordPress routing all mean the same thing by a type, and a "
      "missing picture states its reason all the way to the preview.")
