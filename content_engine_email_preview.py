"""
content_engine_email_preview.py
============================================================================
THE EMAIL PREVIEW. See exactly what lands in their inbox, before it does.

WHAT IT ANSWERS, IN ORDER OF HOW MUCH IT COSTS TO GET WRONG
  1. Does a personalisation token render EMPTY?   "Hi ," sent to 400 people
  2. Where does every link actually go?           a tracked link to nowhere
  3. Will it look like spam?                      a campaign nobody sees
  4. What does it look like?                      desktop, mobile, plain text

THE HARD RULE
  render() returns blocking=True when a token would render empty. The send
  path asks this question first and refuses while it is True. A preview that
  merely WARNS is a preview people click past.

RENDERER AND CHECKER ONLY. Nothing here sends, stores or fetches.
============================================================================
"""

from __future__ import annotations

import html as _html
import re

# Spam words that actually move filters, kept short and honest. A long list
# of scary words produces a screen nobody believes; these are the ones that
# reliably correlate with a spam verdict in cold B2B mail.
SPAM_WORDS = ("free", "guarantee", "act now", "limited time", "click here",
              "risk-free", "no obligation", "winner", "cash", "urgent",
              "100%", "buy now", "cheap", "credit", "income", "investment")

TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")
LINK_RE = re.compile(r'href=["\'](https?://[^"\']+)["\']', re.I)


def e(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


def _text_of(html) -> str:
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", str(html or ""),
               flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def resolve(text, lead) -> tuple:
    """Fill every {{token}} from the lead. Returns (filled, empties).

    An empty token is the defect this whole screen exists to catch: it is
    invisible in the editor, obvious to the recipient, and unrecoverable
    once sent."""
    lead = lead if isinstance(lead, dict) else {}
    empties = []

    def sub(m):
        key = m.group(1)
        val = lead
        for part in key.split("."):
            val = (val or {}).get(part) if isinstance(val, dict) else None
        s = "" if val is None else str(val).strip()
        if not s:
            empties.append(key)
        return s

    return TOKEN_RE.sub(sub, str(text or "")), empties


def links(html, base="") -> list:
    """Every link, with what a click will really do once tracking wraps it."""
    out = []
    for u in LINK_RE.findall(str(html or "")):
        wrapped = (f"{base.rstrip('/')}/t/c/<token>?u={u}" if base else
                   "not wrapped: PUBLIC_BASE_URL is not set, so clicks "
                   "cannot be counted")
        out.append({"url": u, "tracked_as": wrapped,
                    "https": u.lower().startswith("https://")})
    return out


def spam_signals(subject, html, *, has_text_part=True,
                 has_unsubscribe=None) -> list:
    """Each signal with a verdict and WHY it matters. Never a bare score:
    a number with no reason cannot be acted on."""
    subject = str(subject or "")
    body = _text_of(html)
    letters = [c for c in subject if c.isalpha()]
    caps = (sum(1 for c in letters if c.isupper()) / len(letters)
            if letters else 0.0)
    imgs = len(re.findall(r"<img", str(html or ""), re.I))
    words = len(body.split())
    found = sorted({w for w in SPAM_WORDS
                    if w in (subject + " " + body).lower()})
    subj_hits = sorted({w for w in SPAM_WORDS if w in subject.lower()})
    if has_unsubscribe is None:
        has_unsubscribe = ("unsubscribe" in str(html or "").lower()
                           or "{{unsubscribe" in str(html or "").lower())
    sig = [
        {"name": "Subject length", "ok": 20 <= len(subject) <= 60,
         "value": f"{len(subject)} characters",
         "why": "Under 20 reads as thin; over 60 is cut off on a phone."},
        {"name": "Shouting", "ok": caps < 0.35,
         "value": f"{caps * 100:.0f}% capitals",
         "why": "A subject in capitals is the oldest spam signal there is."},
        {"name": "Exclamation marks", "ok": subject.count("!") <= 1,
         "value": f"{subject.count('!')} in the subject",
         "why": "More than one reads as a shout to a filter and a person."},
        {"name": "Words in the body", "ok": words >= 40,
         "value": f"{words} words",
         "why": "A body of almost nothing around a link is what a filter "
                "expects from a bad actor."},
        {"name": "Image to text", "ok": not (imgs and words < 60),
         "value": f"{imgs} image(s), {words} words",
         "why": "Images carrying the message with no text is a classic "
                "filter trip."},
        {"name": "Unsubscribe present", "ok": bool(has_unsubscribe),
         "value": "yes" if has_unsubscribe else "no",
         "why": "Legally required for cold mail in the EU, and its absence "
                "is a direct spam signal."},
        {"name": "Plain-text part", "ok": bool(has_text_part),
         "value": "yes" if has_text_part else "no",
         "why": "HTML-only mail is scored worse by every major filter."},
        # A spam word in the SUBJECT is worth several in the body: the
        # subject is what the filter scores hardest and the only part a
        # person reads before deciding. Counting them together let
        # "FREE!! ACT NOW!!" pass, which is the exact thing this checks for.
        {"name": "Spam words", "ok": not subj_hits and len(found) <= 2,
         "value": (", ".join(found) or "none")
                  + (f" ({len(subj_hits)} in the subject)" if subj_hits
                     else ""),
         "why": "A couple in the body is fine. Any in the subject line is "
                "a verdict on its own."},
    ]
    return sig


def render(subject, html, lead=None, *, base="", text_part=True,
           preheader="", from_name="") -> dict:
    """The whole preview, as one object the screen draws.

    blocking=True when a token would render empty. The send endpoint asks
    for this and refuses while it is True, because a warning is something
    people click past and this mistake cannot be taken back."""
    s_filled, s_empty = resolve(subject, lead)
    h_filled, h_empty = resolve(html, lead)
    p_filled, p_empty = resolve(preheader, lead)
    empties = sorted(set(s_empty) | set(h_empty) | set(p_empty))
    sig = spam_signals(s_filled, h_filled, has_text_part=text_part)
    lk = links(h_filled, base)
    return {
        "subject": s_filled, "html": h_filled, "preheader": p_filled,
        "from_name": from_name or "",
        "text": _text_of(h_filled),
        "empty_tokens": empties,
        "blocking": bool(empties),
        "block_reason": (
            "This would send with " + ", ".join("{{" + t + "}}"
                                                for t in empties[:4])
            + " empty. Fill the field on those leads, or remove the token."
            if empties else ""),
        "links": lk,
        "insecure_links": [x["url"] for x in lk if not x["https"]],
        "untracked": bool(lk) and not base,
        "signals": sig,
        "failing": [s["name"] for s in sig if not s["ok"]],
        "words": len(_text_of(h_filled).split()),
    }


def inbox_line(prev) -> dict:
    """From-name, subject and preheader, as a crowded inbox shows them."""
    prev = prev if isinstance(prev, dict) else {}
    set_by_you = str(prev.get("preheader") or "").strip()
    derived = str(prev.get("text") or "")[:90]
    return {"from": prev.get("from_name") or "(no from-name set)",
            "subject": prev.get("subject") or "(no subject)",
            "preheader": set_by_you or derived or "(nothing to show)",
            # WHERE the preheader came from matters: a derived one is the
            # mail client picking your first line for you, and the founder
            # should know that is what is happening rather than assume he
            # wrote it.
            "preheader_derived": not set_by_you,
            "preheader_note": ("" if set_by_you else
                               "no preheader set, so the client will use "
                               "the first line of the body")}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ok = []

    def t(n, c):
        ok.append(bool(c))
        print(("  OK   " if c else "  FAIL ") + n)

    lead = {"name": "Ann", "company": "Clinic X", "city": ""}
    html = ('<p>Hi {{name}}, I noticed {{company}} in {{city}}.</p>'
            '<p>Would a short call help? '
            '<a href="https://anthropos-automation.com/book">Book here</a> '
            'or reply. ' + "word " * 50 + '</p>'
            '<p><a href="http://old.example.com/x">old link</a></p>')

    filled, empty = resolve("Hi {{name}} at {{company}}", lead)
    t("tokens fill from the lead", filled == "Hi Ann at Clinic X")
    t("a present token is not reported empty", empty == [])
    _, e2 = resolve("in {{city}}", lead)
    t("an EMPTY field is caught", e2 == ["city"])
    _, e3 = resolve("{{nope}}", lead)
    t("a missing field is caught", e3 == ["nope"])

    p = render("A short question about Clinic X", html, lead,
               base="https://engine.test", from_name="Murtuja")
    t("the preview blocks on an empty token", p["blocking"] is True)
    t("the block names the token and what to do",
      "{{city}}" in p["block_reason"] and "Fill the field" in p["block_reason"])
    good = render("A short question about your clinic scheduling",
                  html.replace("{{city}}", "Munich"), lead,
                  base="https://engine.test")
    t("a clean email does not block", good["blocking"] is False)
    t("every link is listed", len(good["links"]) == 2)
    t("links show what a click really does",
      "/t/c/<token>?u=" in good["links"][0]["tracked_as"])
    t("an http link is flagged as insecure",
      good["insecure_links"] == ["http://old.example.com/x"])
    nb = render("s", html.replace("{{city}}", "M"), lead, base="")
    t("no base url means clicks cannot be counted, and it says so",
      nb["untracked"] is True and "cannot be counted" in nb["links"][0]["tracked_as"])

    sig = spam_signals("FREE!! ACT NOW!!", "<p>hi</p>", has_text_part=False)
    names = {s["name"]: s["ok"] for s in sig}
    t("shouting is caught", names["Shouting"] is False)
    t("exclamation marks are caught", names["Exclamation marks"] is False)
    t("a thin body is caught", names["Words in the body"] is False)
    t("a missing plain-text part is caught", names["Plain-text part"] is False)
    t("a missing unsubscribe is caught", names["Unsubscribe present"] is False)
    t("spam words are caught", names["Spam words"] is False)
    t("every signal explains WHY it matters",
      all(len(s["why"]) > 30 for s in sig))
    clean = spam_signals("A short question about your scheduling",
                         "<p>" + "word " * 60 + "unsubscribe</p>")
    t("a good email passes every signal",
      all(s["ok"] for s in clean))

    il = inbox_line(good)
    t("the inbox line is what a person actually sees",
      il["subject"].startswith("A short question"))
    il2 = inbox_line(render("s", "<p>x</p>", {}, preheader=""))
    t("a derived preheader is shown AND labelled as derived",
      il2["preheader"] == "x" and il2["preheader_derived"] is True
      and "first line of the body" in il2["preheader_note"])
    il3 = inbox_line(render("s", "<p>x</p>", {}, preheader="Mine"))
    t("a preheader you set is not labelled derived",
      il3["preheader"] == "Mine" and il3["preheader_derived"] is False)
    t("plain text is derived from the html",
      "Would a short call help" in good["text"])
    print(f"\n{sum(ok)} passed, {len(ok) - sum(ok)} failed")
    raise SystemExit(0 if all(ok) else 1)
