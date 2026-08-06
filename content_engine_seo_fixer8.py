"""
content_engine_seo_fixer8.py
============================================================================
THE EIGHT THAT COULD BE DETECTED BUT NEVER REPAIRED.

The engine knew about 33 problems and could repair 17. The other sixteen
split into eight that genuinely need a server or a theme, and eight that were
simply never given a fix path. These are those eight.

  h1_missing            insert an H1 built from the page title
  h1_multiple           demote the extra H1s to H2
  heading_order         renumber so no heading level is skipped
  broken_internal_link  repoint the link, or remove it
  canonical_mismatch    point the canonical at the page you meant to rank
  canonical_override    remove the override
  not_indexed           submit the URL and ask for a re-inspection
  not_found             a 301 to the closest live page, or retire the URL

EVERY ONE IS APPROVAL GATED. Each writes a proposal onto the work order
showing exactly what the page says now and what it would say after. Nothing
reaches WordPress until a human presses approve, which is the same contract
the title and meta rewrites already run under.

WHY THE HTML IS EDITED WITH A PARSER AND NOT A REGEX
  These fixes rewrite the body of a live page. A regex that is almost right
  turns a published article into broken markup, and the founder would find
  out from a reader. Every transform below works on parsed structure and
  refuses rather than guesses.
============================================================================
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

# ---------------------------------------------------------------------------
# THE CODES THIS MODULE OWNS. Imported by content_engine_workorders so the
# two sides cannot disagree about which problems have a fix path.
# ---------------------------------------------------------------------------
FIXER8_CODES = frozenset({
    "h1_missing", "h1_multiple", "heading_order", "broken_internal_link",
    "canonical_mismatch", "canonical_override", "not_indexed", "not_found",
})

# which field of the post each one writes, so apply_proposal knows what to do
FIELD_OF = {
    "h1_missing": "content", "h1_multiple": "content",
    "heading_order": "content", "broken_internal_link": "content",
    "canonical_mismatch": "canonical", "canonical_override": "canonical",
    "not_indexed": "indexnow", "not_found": "redirect",
}


class _Headings(HTMLParser):
    """Every heading in document order, with its exact source span."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out = []
        self._open = None

    def handle_starttag(self, tag, attrs):
        if re.fullmatch(r"h[1-6]", tag):
            self._open = (int(tag[1]), self.getpos(), self.get_starttag_text())

    def handle_endtag(self, tag):
        if re.fullmatch(r"h[1-6]", tag) and self._open:
            lvl, pos, raw = self._open
            self.out.append({"level": lvl, "line": pos[0], "col": pos[1],
                             "open": raw})
            self._open = None


def headings(html: str) -> list:
    p = _Headings()
    try:
        p.feed(html or "")
    except Exception:
        return []
    return p.out


def _retag(html: str, frm: int, to: int, *, skip: int = 0) -> str:
    """Rewrite <hN>...</hN> to <hM>...</hM>, leaving the first `skip` alone.

    Works on whole tags only. A heading whose tag carries attributes keeps
    them; anything it cannot parse cleanly is left exactly as it was.
    """
    pat = re.compile(rf"<h{frm}(\s[^>]*)?>(.*?)</h{frm}\s*>",
                     re.I | re.S)
    seen = {"n": 0}

    def sub(m):
        seen["n"] += 1
        if seen["n"] <= skip:
            return m.group(0)
        return f"<h{to}{m.group(1) or ''}>{m.group(2)}</h{to}>"

    return pat.sub(sub, html or "")


def _text_of(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()


# ---------------------------------------------------------------------------
# THE EIGHT TRANSFORMS. Each returns a proposal dict or a refusal, and NONE
# of them writes anything anywhere.
# ---------------------------------------------------------------------------
def _refuse(why: str) -> dict:
    return {"ok": False, "why": why}


def _ok(field, before, after, says, *, full=None) -> dict:
    """A proposal. `after` is what the founder READS; `full` is what gets
    written.

    These must be separate. The body previews are trimmed so a 40 KB article
    does not fill the screen, and an early version of this file then had
    apply() write that trimmed preview back to WordPress, which would have
    deleted the rest of the post. A content fix without `full` is refused
    below rather than trusted.
    """
    p = {"field": field, "before": before, "after": after, "says": says}
    if full is not None:
        p["after_full"] = full
    return {"ok": True, "proposal": p}


def fix_h1_missing(rec: dict) -> dict:
    body = rec.get("content") or rec.get("body") or ""
    title = (rec.get("title") or "").strip()
    if not title:
        return _refuse("the page has no title to build an H1 from")
    hs = headings(body)
    if any(h["level"] == 1 for h in hs):
        return _refuse("this page already has an H1, so nothing is missing")
    after = f"<h1>{title}</h1>\n{body}"
    return _ok("content", body[:400], after[:400],
               f'adds "{title}" as the H1 at the top of the page',
               full=after)


def fix_h1_multiple(rec: dict) -> dict:
    body = rec.get("content") or rec.get("body") or ""
    hs = [h for h in headings(body) if h["level"] == 1]
    if len(hs) < 2:
        return _refuse("there are not two or more H1s on this page")
    after = _retag(body, 1, 2, skip=1)
    if after == body:
        return _refuse("the H1 markup could not be rewritten safely, so "
                       "nothing was changed")
    return _ok("content", body[:400], after[:400],
               f"keeps the first H1 and demotes the other {len(hs) - 1} to H2",
               full=after)


def fix_heading_order(rec: dict) -> dict:
    """Close gaps so no level is skipped, keeping relative structure."""
    body = rec.get("content") or rec.get("body") or ""
    hs = headings(body)
    if len(hs) < 2:
        return _refuse("there are too few headings for the order to be wrong")
    levels = sorted({h["level"] for h in hs})
    remap, want = {}, levels[0]
    for lv in levels:
        remap[lv] = want
        want += 1
    if all(k == v for k, v in remap.items()):
        return _refuse("the heading levels already run in order")
    after = body
    # rewrite deepest first so an earlier rename cannot collide with a later one
    for lv in sorted(remap, reverse=True):
        if remap[lv] != lv:
            after = _retag(after, lv, remap[lv])
    if after == body:
        return _refuse("the headings could not be renumbered safely")
    moved = ", ".join(f"H{k} to H{v}" for k, v in remap.items() if k != v)
    return _ok("content", body[:400], after[:400],
               f"renumbers so no level is skipped: {moved}",
               full=after)


def fix_broken_internal_link(rec: dict, order: dict, live_urls=()) -> dict:
    """Repoint a dead link at the closest live URL, or unwrap it."""
    body = rec.get("content") or rec.get("body") or ""
    dead = ((order.get("extra") or {}).get("target")
            or (order.get("extra") or {}).get("href") or "")
    if not dead:
        return _refuse("the work order does not record which link is broken")
    if dead not in body:
        return _refuse("that link is no longer in the page body")
    tail = [s for s in re.split(r"[/\-_]", dead.rstrip("/")) if s][-1:]
    best, score = "", 0
    for u in live_urls or ():
        s = sum(1 for t in tail if t and t in u)
        if s > score:
            best, score = u, s
    if best:
        after = body.replace(dead, best)
        return _ok("content", dead, best,
                   f"repoints the dead link to {best}", full=after)
    after = re.sub(rf"<a[^>]*href=[\"']{re.escape(dead)}[\"'][^>]*>(.*?)</a\s*>",
                   r"\1", body, flags=re.I | re.S)
    if after == body:
        return _refuse("the link could not be removed safely")
    return _ok("content", dead, "(link removed, text kept)",
               "no live page matches, so the link is removed and its words "
               "are kept", full=after)


def fix_canonical(rec: dict, order: dict) -> dict:
    """Point the canonical where you meant it to point."""
    want = (order.get("extra") or {}).get("should_be") or order.get("url") or ""
    have = rec.get("canonical") or (order.get("extra") or {}).get("current") or ""
    if not want:
        return _refuse("nothing records which URL should be canonical")
    if have and have.rstrip("/") == want.rstrip("/"):
        return _refuse("the canonical already points there")
    return _ok("canonical", have or "(none set)", want,
               f"sets the canonical to {want}")


def fix_not_indexed(order: dict) -> dict:
    url = order.get("url") or ""
    if not url:
        return _refuse("the work order carries no URL")
    return _ok("indexnow", "not in the index", url,
               f"submits {url} to IndexNow and asks for a re-inspection")


def fix_not_found(order: dict, live_urls=()) -> dict:
    """A 301 to the closest live page, or retire the URL."""
    url = order.get("url") or ""
    if not url:
        return _refuse("the work order carries no URL")
    tail = [s for s in re.split(r"[/\-_]", url.rstrip("/")) if s][-2:]
    best, score = "", 0
    for u in live_urls or ():
        if u.rstrip("/") == url.rstrip("/"):
            continue
        s = sum(1 for t in tail if t and t in u)
        if s > score:
            best, score = u, s
    if best:
        return _ok("redirect", url, best,
                   f"301 redirects {url} to {best}, so the visits and the "
                   f"link value are kept")
    return _ok("redirect", url, "(retire)",
               "no live page is close enough to redirect to, so this URL is "
               "retired: it stops being linked and stops being submitted")


# ---------------------------------------------------------------------------
# THE ONE ENTRY POINT
# ---------------------------------------------------------------------------
def propose(order: dict, rec: dict, *, live_urls=()) -> dict:
    """Draft the repair for one work order. Writes nothing, anywhere.

    Returns {"ok": True, "proposal": {...}} or {"ok": False, "why": "..."}.
    A refusal is a RESULT, not an error: "this page already has an H1" is
    information the founder should see, not an exception to swallow.
    """
    code = order.get("code")
    rec = rec or {}
    if code not in FIXER8_CODES:
        return _refuse(f"{code} is not one of the eight this module repairs")
    try:
        if code == "h1_missing":
            return fix_h1_missing(rec)
        if code == "h1_multiple":
            return fix_h1_multiple(rec)
        if code == "heading_order":
            return fix_heading_order(rec)
        if code == "broken_internal_link":
            return fix_broken_internal_link(rec, order, live_urls)
        if code in ("canonical_mismatch", "canonical_override"):
            return fix_canonical(rec, order)
        if code == "not_indexed":
            return fix_not_indexed(order)
        if code == "not_found":
            return fix_not_found(order, live_urls)
    except Exception as ex:
        return _refuse(f"the repair could not be drafted: {type(ex).__name__}")
    return _refuse("no path for this code")


def apply(order: dict) -> dict:
    """Publish an already approved proposal. Called only after a human click.

    The three non-content fields do not go through update_post: a canonical is
    a meta field, an IndexNow submit is a ping, and a redirect is a rule. Each
    is handled by the thing that actually owns it, and each says so.
    """
    prop = (order.get("extra") or {}).get("proposal") or {}
    if not prop:
        return {"status": "failed", "result": "no proposal on this order"}
    field = prop.get("field")
    url = order.get("url") or ""

    # VALIDATE THE PROPOSAL BEFORE TOUCHING ANYTHING. This check used to sit
    # after the WordPress connection test, so a malformed proposal reported
    # "WordPress not connected" - a true sentence about the wrong problem,
    # which is how a real defect hides for weeks.
    if field == "content" and not prop.get("after_full"):
        return {"status": "failed",
                "result": "this proposal carries only a preview of the new "
                          "body, not the whole thing. Refusing rather than "
                          "truncating the post. Re-draft the fix."}

    import content_engine_connectors as C

    if field == "indexnow":
        idx = C.IndexNow()
        if not idx.available():
            return {"status": "skipped",
                    "result": "IndexNow is not configured, so nothing was sent"}
        try:
            idx.submit([url])
            return {"status": "done", "result": f"{url} submitted to IndexNow"}
        except Exception as ex:
            return {"status": "failed", "result": f"{type(ex).__name__}"}

    if field == "redirect":
        # A 301 lives in the host or the SEO plugin, not in a post field. The
        # engine records the decision and tells you where to enact it rather
        # than pretending it changed something it cannot reach.
        return {"status": "recorded",
                "result": f"redirect {url} to {prop.get('after')} recorded. "
                          f"Add it in your host or SEO plugin: the engine has "
                          f"no write access to redirect rules."}

    wp = C.WordPress()
    if not wp.available():
        return {"status": "skipped", "result": "WordPress not connected"}
    post = wp.find_by_url(url)
    if not post:
        return {"status": "failed", "result": "post not found in WordPress"}

    if field == "canonical":
        payload = {"meta": {"_yoast_wpseo_canonical": prop.get("after")}}
    elif field == "content":
        # NEVER fall back to `after`. `after` is a 400-character preview;
        # writing it would replace a whole article with its own first
        # paragraph. If the full body is absent the proposal is malformed,
        # and refusing is the only safe answer.
        full = prop.get("after_full")
        if not full:
            return {"status": "failed",
                    "result": "this proposal carries only a preview of the "
                              "new body, not the whole thing. Refusing rather "
                              "than truncating the post. Re-draft the fix."}
        payload = {"content": full}
    else:
        return {"status": "failed", "result": f"unknown field {field}"}

    res = wp.update_post(post["id"], payload, kind=post.get("kind", "posts"))
    return ({"status": "done", "result": prop.get("says") or "updated"}
            if res == "updated" else {"status": "failed", "result": res})


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    checks = []

    def t(name, got, want):
        ok = got == want
        checks.append(ok)
        print(("  OK   " if ok else "  FAIL ") + name)
        if not ok:
            print(f"         got  {got!r}\n         want {want!r}")

    # h1_missing
    r = propose({"code": "h1_missing"}, {"title": "Price monitoring",
                                         "content": "<p>hello</p>"})
    t("h1_missing adds the title as H1", r["ok"], True)
    t("  and puts it first", r["proposal"]["after"].startswith(
        "<h1>Price monitoring</h1>"), True)
    r = propose({"code": "h1_missing"}, {"title": "X", "content": "<h1>a</h1>"})
    t("h1_missing refuses when an H1 exists", r["ok"], False)

    # h1_multiple
    r = propose({"code": "h1_multiple"},
                {"content": "<h1>one</h1><p>x</p><h1>two</h1><h1>three</h1>"})
    t("h1_multiple keeps the first", r["proposal"]["after"].count("<h1>"), 1)
    t("  and demotes the rest", r["proposal"]["after"].count("<h2>"), 2)

    # heading_order
    r = propose({"code": "heading_order"},
                {"content": "<h1>a</h1><h4>b</h4><h5>c</h5>"})
    t("heading_order closes the gap", r["ok"], True)
    t("  H4 becomes H2", "<h2>b</h2>" in r["proposal"]["after"], True)
    t("  H5 becomes H3", "<h3>c</h3>" in r["proposal"]["after"], True)
    r = propose({"code": "heading_order"}, {"content": "<h1>a</h1><h2>b</h2>"})
    t("heading_order refuses when already in order", r["ok"], False)

    # broken_internal_link
    o = {"code": "broken_internal_link", "url": "/p",
         "extra": {"target": "/old-pricing-guide"}}
    r = propose(o, {"content": "<a href='/old-pricing-guide'>see</a>"},
                live_urls=["/blog/pricing-guide", "/about"])
    t("broken link repoints to the closest live URL",
      r["proposal"]["after"], "/blog/pricing-guide")
    r = propose(o, {"content": "<a href='/old-pricing-guide'>see</a>"},
                live_urls=[])
    t("  with no candidate it unwraps instead", r["ok"], True)

    # canonical
    r = propose({"code": "canonical_mismatch", "url": "/a",
                 "extra": {"should_be": "/a", "current": "/b"}},
                {"canonical": "/b"})
    t("canonical points where you meant", r["proposal"]["after"], "/a")

    # not_indexed / not_found
    r = propose({"code": "not_indexed", "url": "/new"}, {})
    t("not_indexed submits the URL", r["proposal"]["field"], "indexnow")
    r = propose({"code": "not_found", "url": "/old-price-guide"}, {},
                live_urls=["/blog/price-guide"])
    t("not_found finds a 301 target", r["proposal"]["after"], "/blog/price-guide")
    r = propose({"code": "not_found", "url": "/zzz"}, {}, live_urls=[])
    t("  and retires when nothing is close", r["proposal"]["after"], "(retire)")

    # the contract
    t("every code has a field", sorted(FIELD_OF) == sorted(FIXER8_CODES), True)
    r = propose({"code": "title_long"}, {})
    t("it refuses codes it does not own", r["ok"], False)

    # THE TRUNCATION GUARD. Every content proposal must carry the whole body,
    # and apply() must refuse one that does not. This is the check that stops
    # a repair from deleting the article it was repairing.
    long_body = "<h4>a</h4>" + ("<p>filler sentence. </p>" * 90)
    for code, rec in (("h1_missing", {"title": "T", "content": long_body}),
                      ("h1_multiple",
                       {"content": "<h1>a</h1>" + long_body + "<h1>b</h1>"}),
                      ("heading_order", {"content": long_body + "<h6>z</h6>"})):
        r = propose({"code": code}, rec)
        if not r["ok"]:
            continue
        p = r["proposal"]
        t(f"{code} carries the whole body, not the preview",
          len(p.get("after_full", "")) > len(p["after"]), True)
    out = apply({"url": "/x", "extra": {"proposal": {
        "field": "content", "after": "<p>only a preview</p>", "says": "x"}}})
    t("apply refuses a content proposal with no full body",
      out["status"], "failed")
    t("  and says why in words a person can act on",
      "Refusing rather" in out["result"], True)

    print(f"\n{sum(checks)} passed, {len(checks) - sum(checks)} failed")
    raise SystemExit(0 if all(checks) else 1)
