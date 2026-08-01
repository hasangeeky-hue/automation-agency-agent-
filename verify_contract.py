"""THE ENGINE <-> WEBSITE CONTRACT.

Two repos, two languages, no shared code, no import between them. Everything
they agree on is agreed by convention — a taxonomy name here, a category name
there — and a convention with nothing checking it is a bug waiting for a
quiet week.

That is exactly how ao_type survived: the theme filtered its two main listings
on a taxonomy the engine never set, both halves were individually correct, and
every post the engine published was live and invisible.

    python verify_contract.py

Reads the THEME source directly. If anthropos-design/ is not present (a clone
that only has the engine) it skips rather than failing — a missing repo is not
a broken contract.
"""
import re
import sys
from pathlib import Path

THEME = Path("anthropos-design")
FAILS, NOTES = [], []


def chk(ok, label, detail=""):
    print(("  OK   " if ok else "  FAIL ") + label + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


def read(rel):
    p = THEME / rel
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


if not THEME.exists():
    print("anthropos-design/ not present — skipping the contract check.")
    print("(Clone it beside the engine to check the engine<->website contract.)")
    sys.exit(0)

php = "\n".join(read(p.relative_to(THEME))
                for p in THEME.rglob("*.php") if ".git" not in p.parts)

print("== 1. every taxonomy the SITE filters on must be one the ENGINE sets ==")
# what the theme actually filters its listings by
filtered = set(re.findall(r"'taxonomy'\s*=>\s*'([a-z_]+)'", php))
chk(bool(filtered), "the theme filters on at least one taxonomy",
    ", ".join(sorted(filtered)))

import content_engine_connectors as C

pub = C.WordPress.publish.__doc__ or ""
src = Path("content_engine_connectors.py").read_text(encoding="utf-8")
body = src[src.index("    def publish(self, job: dict, piece: dict) -> str:"):][:4000]
sent = set(re.findall(r'data\["([a-z_]+)"\]', body))
sent |= set(re.findall(r'"([a-z_]+)":', body[:600]))   # the initial dict literal
for tax in sorted(filtered):
    if tax == "category":
        chk("categories" in sent, "engine sets: category")
        continue
    chk(tax in sent, f"engine sets: {tax}",
        "the site filters on this and the engine never sends it — posts would "
        "publish live and stay invisible" if tax not in sent else "")

print("\n== 2. a custom taxonomy must be REST-visible or WordPress drops it ==")
for tax in sorted(t for t in filtered if t not in ("category", "post_tag")):
    m = re.search(r"register_taxonomy\(\s*'%s'.*?\);" % re.escape(tax), php, re.S)
    chk(bool(m), f"{tax}: registered in the theme")
    if m:
        chk("'show_in_rest' => true" in m.group(0),
            f"{tax}: show_in_rest is true",
            "without it WordPress SILENTLY DROPS the field the engine sends — "
            "no error, no warning")

print("\n== 3. segments must mean the same thing on both sides ==")
import content_engine_site_taxonomy as T

seg_php = read("inc/segments.php")
theme_segs = {}
if seg_php and "function anthropos_segments" in seg_php:
    b = seg_php[seg_php.index("function anthropos_segments"):]
    for slug, lab in re.findall(
            r"^\t\t'([a-z0-9-]+)' => array\(\s*\n\s*'label' => '([^']+)'", b, re.M):
        # the seeder stores wp_specialchars_decode(label), so compare decoded
        theme_segs[slug] = lab.replace("&amp;", "&").replace("&#039;", "'")
chk(bool(theme_segs), f"theme defines segments ({len(theme_segs)})")

eng_segs = {s["name"] for s in T.SEGMENTS}
missing_in_engine = set(theme_segs.values()) - eng_segs
missing_in_theme = eng_segs - set(theme_segs.values())
chk(not missing_in_engine, "every site segment is one the engine can assign",
    f"the site has {sorted(missing_in_engine)} but the engine never routes "
    f"content to it" if missing_in_engine else "")
chk(not missing_in_theme, "every engine segment exists on the site",
    f"the engine would CREATE {sorted(missing_in_theme)} as a new category "
    f"rather than reusing the seeded one" if missing_in_theme else "")

print("\n== 4. the engine matches categories by NAME, so names must match ==")
# _category_ids searches WP by name; the theme seeds with a decoded label. If
# either side changes its wording the engine silently creates a duplicate
# category instead of reusing the seeded one.
seeder = re.search(r"wp_insert_term\(\s*([^,]+),\s*'category'", php)
chk(bool(seeder), "the theme seeds segment categories")
if seeder:
    chk("wp_specialchars_decode" in seeder.group(1),
        "the theme decodes entities before seeding",
        "without it the stored name is 'X &amp; Y' and the engine's search for "
        "'X & Y' misses, creating a duplicate")
chk('params={"search": name}' in src,
    "the engine looks categories up by name")

print("\n== 5. what the engine PUBLISHES must be blocks the theme can style ==")
import content_engine_connectors as _C

_md = ("## Heading\n\nBody with **bold**.\n\n![Hero](https://x/h.png)\n\n"
       "- one\n- two\n\n> quoted\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n")
_html = _C.md_to_html(_md)
for _blk in ("wp:heading", "wp:paragraph", "wp:image", "wp:list",
             "wp:quote", "wp:table"):
    chk(_blk in _html, f"publishes a real {_blk} block",
        "" if _blk in _html else
        "classic HTML renders as ONE unstyled Classic block in the editor")
chk("<p><img" not in _html,
    "a hero image is a FIGURE block, never an <img> inside a paragraph")
chk('class="wp-block-heading"' in _html,
    "headings carry the class the editor expects")

_cta = _C.cta_block("Talk to us about automating this.",
                    "https://cal.com/anthropos")
chk("art-cta" in _cta, "the CTA uses the theme's own .art-cta band",
    "the theme styles .art-cta - it styles nothing named wp-block-*")
chk("btn btn-cta" in _cta, "and the theme's .btn.btn-cta button")
chk("cal.com" in _cta, "pointing at the booking link")
chk(_C.cta_block("", "https://x") == "", "no CTA text means no empty band")

_src = Path("content_engine_connectors.py").read_text(encoding="utf-8")
_pub = _src[_src.index("    def publish(self, job: dict, piece: dict) -> str:"):][:2600]
chk("cta_block(" in _pub, "publish() actually appends the CTA",
    "cta_text was written by the agent, compliance-checked by QA, and then "
    "dropped right here")
chk("EMAIL_BOOKING_URL" in _pub, "using the booking URL")

print("\n== 6. the section names the engine files under must exist on the site ==")
kinds = set(T.KIND_CATEGORY.values())
for k in sorted(kinds):
    present = (f"'{k}'" in php) or (f'"{k}"' in php) or (k.lower() in php.lower())
    if not present:
        NOTES.append(f"section '{k}' is not named anywhere in the theme")
chk(True, f"engine files content under {sorted(kinds)}",
    "; ".join(NOTES) if NOTES else "all named in the theme")

print()
if FAILS:
    print(f"{len(FAILS)} CONTRACT BREAK(S): {FAILS}")
    sys.exit(1)
print("CONTRACT HOLDS — every taxonomy the site filters on is one the engine "
      "sets and WordPress will accept, and both sides mean the same thing by "
      "a segment.")
if NOTES:
    print("notes: " + "; ".join(NOTES))
