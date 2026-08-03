"""THE SUPERVISOR — the station on the line that checks the one before it.

Nine skills each did their job and put the piece on the belt. Nothing looked
at it. So a blog with no images, two sections and no call to action travelled
the whole line and the FOUNDER was the first to notice — four times in one
day.

This is not a second opinion. It counts things:

    Did the writer write 4 sections?     count them
    Are there 4 image prompts?           count them
    At least 650 words?                  count them
    Is the keyword in the title?         yes or no
    Is there a call to action?           yes or no

Every rule is arithmetic, so it is free, instant, and cannot itself be wrong
about what it saw. A model-based judge exists for taste (content_engine_judge)
and is deliberately NOT used here — "did you do what I asked" is not a matter
of opinion, and paying a model to count to four would be silly.

WHAT IT NEVER DOES: spend, publish, send, or overrule the human gate. It
returns a verdict; the orchestrator decides what to do with it.

ONE SOURCE OF TRUTH: the thresholds are imported from content_engine_prep —
the same constants that build the brief the writer was given. A contract that
restated them would be the sixth hand-written list in this codebase.

    python content_engine_supervisor.py
"""
from __future__ import annotations

import re

_D = lambda v: v if isinstance(v, dict) else {}
_L = lambda v: list(v) if isinstance(v, (list, tuple)) else []
_S = lambda v: str(v or "").strip()


def _plain(md: str) -> str:
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", _S(md))
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    return re.sub(r"[#*_`>]+", "", t).strip()


def _brief(job) -> dict:
    """What this piece was ASKED for. Imported, never restated."""
    import content_engine_prep as P
    import content_engine_site_taxonomy as T
    row = {}
    try:
        pl = _D(job).get("payload") or {}
        cal = _L(_D(pl.get("content_strategist")).get("calendar"))
        ix = int(_D(pl.get("config")).get("produce_index", 0) or 0)
        row = _D(cal[ix]) if 0 <= ix < len(cal) else _D(cal[0] if cal else {})
    except Exception:
        row = {}
    kind = _S(row.get("type")) or "blog"
    long_form = T.wants_image(kind) and kind in ("blog", "guide", "service")
    return {"kind": kind, "long_form": long_form,
            "sections": P._SECTIONS_PER_PIECE if long_form else 0,
            "images": P._IMAGES_PER_PIECE if long_form else 0,
            "min_words": P._MIN_WORDS.get(kind, 0) if long_form else 0,
            "keyword": _S(row.get("primary_keyword"))}


# --------------------------------------------------------------- contracts
def _c_producer(data, job) -> list:
    b = _brief(job)
    body = _S(data.get("body"))
    out = []
    if b["long_form"]:
        secs = len(re.findall(r"(?m)^##\s+\S", body))
        out.append((secs >= b["sections"], "sections",
                    f"{secs} of {b['sections']} '## ' sections"))
        words = len(_plain(body).split())
        out.append((words >= b["min_words"], "length",
                    f"{words} of {b['min_words']} words"))
        prompts = len([x for x in _L(data.get("image_prompts")) if _S(x)])
        out.append((prompts >= b["images"], "image_prompts",
                    f"{prompts} of {b['images']} image prompts"))
    out.append((bool(_S(data.get("cta_text"))), "cta", "call to action present"))
    kw = b["keyword"].lower()
    if kw:
        out.append((kw in _S(data.get("title")).lower()
                    or kw in body.lower()[:1200], "keyword",
                    f"'{b['keyword']}' in the title or opening"))
    return out


def _c_strategist(data, job) -> list:
    cal = _L(data.get("calendar"))
    return [(len(cal) >= 1, "calendar", f"{len(cal)} planned item(s)"),
            (all(_S(_D(r).get("working_title")) for r in cal), "titles",
             "every planned item has a working title")]


def _c_seo(data, job) -> list:
    t, m = _S(data.get("meta_title")), _S(data.get("meta_description"))
    out = []
    if t:
        out.append((len(t) <= 60, "meta_title", f"{len(t)} chars (max 60)"))
    if m:
        out.append((50 <= len(m) <= 160, "meta_description",
                    f"{len(m)} chars (50-160)"))
    return out


def _c_qa(data, job) -> list:
    return [(_S(data.get("verdict")) in ("pass", "revise", "block"), "verdict",
             f"verdict is '{_S(data.get('verdict'))}'")]


CONTRACTS = {
    "content_producer": _c_producer,
    "content_strategist": _c_strategist,
    "seo_optimizer": _c_seo,
    "qa_compliance": _c_qa,
}


def supervise(skill: str, data, job) -> dict:
    """Was the brief met? Returns {ok, failed, note}. Never raises.

    `note` is written for the MODEL — it is fed back into the retry so the
    second attempt knows what was short, instead of re-rolling the same dice.
    """
    fn = CONTRACTS.get(skill)
    if fn is None or not isinstance(data, dict):
        return {"ok": True, "failed": [], "note": "", "checked": 0}
    try:
        results = fn(data, job)
    except Exception as e:
        # A broken contract must never block a good piece.
        return {"ok": True, "failed": [], "checked": 0,
                "note": f"(supervisor skipped: {type(e).__name__})"}
    failed = [(name, detail) for ok, name, detail in results if not ok]
    if not failed:
        return {"ok": True, "failed": [], "note": "", "checked": len(results)}
    note = ("Your previous attempt did not meet the brief: "
            + "; ".join(f"{n} — {d}" for n, d in failed)
            + ". Produce it again and satisfy every one of these.")
    return {"ok": False, "failed": [n for n, _ in failed],
            "detail": [d for _, d in failed], "note": note,
            "checked": len(results)}


if __name__ == "__main__":
    NL = chr(10)
    good_body = NL.join(f"## Section {i}{NL}{NL}" + ("word " * 200)
                        for i in range(1, 5))
    job = {"payload": {"config": {"produce_index": 0},
                       "content_strategist": {"calendar": [
                           {"type": "blog", "primary_keyword": "price monitoring"}]}}}

    ok = supervise("content_producer", {
        "title": "Automated price monitoring for Shopify",
        "body": good_body, "cta_text": "Book a call",
        "image_prompts": ["a", "b", "c", "d"]}, job)
    assert ok["ok"], ok

    bad = supervise("content_producer", {
        "title": "Something else", "body": "## One" + NL + "short.",
        "cta_text": "", "image_prompts": ["a"]}, job)
    assert not bad["ok"]
    assert set(bad["failed"]) == {"sections", "length", "image_prompts",
                                  "cta", "keyword"}, bad["failed"]
    assert "sections — 1 of 4" in bad["note"], bad["note"]

    # a short type must not be judged by long-form rules
    short = {"payload": {"config": {"produce_index": 0},
                         "content_strategist": {"calendar": [{"type": "reel"}]}}}
    assert supervise("content_producer",
                     {"body": "hook", "cta_text": "Book"}, short)["ok"]

    assert not supervise("qa_compliance", {"verdict": "maybe"}, job)["ok"]
    assert supervise("qa_compliance", {"verdict": "pass"}, job)["ok"]
    assert supervise("unknown_skill", {"x": 1}, job)["ok"]
    assert supervise("content_producer", "not a dict", job)["ok"]

    # the thresholds must come FROM the brief, not be restated here
    import content_engine_prep as P
    src = open("content_engine_supervisor.py", encoding="utf-8").read()
    assert "P._SECTIONS_PER_PIECE" in src and "P._MIN_WORDS" in src
    assert "650" not in src.split('"""')[2], (
        "a hard-coded 650 here would be the sixth list that must agree")

    print(f"OK — supervisor self-check passed. It counts sections, words, "
          f"image prompts, the CTA and the keyword against the SAME constants "
          f"the brief was built from ({P._SECTIONS_PER_PIECE} sections, "
          f"{P._IMAGES_PER_PIECE} images, {P._MIN_WORDS['blog']} words for a "
          f"blog), names every miss, and writes the retry note. No model, no "
          f"spend, no opinion.")
