"""HOW MANY OF YOUR PROBLEMS CAN THE ENGINE FIX ITSELF?

    docker compose -f deploy/docker-compose.yml exec api python classify_problems.py

Read-only. No LLM calls. No spend. Writes nothing, publishes nothing.

WHY THIS EXISTS
    I reported "775 problem cards" in a proposal, an artifact and a plan. That
    number came from rendering the dashboard with an EMPTY context on my own
    machine. Measured properly, 84% of those cards were red only because I had
    given them no data - Media 99%, Business Intel 93%, Outreach 93%. A card
    reading "Checks passed: 0" goes red correctly when you show it nothing.
    That was a fault in my measurement, not in your engine.

    The question - how much of the fixing can be automated - depends entirely
    on live state: which jobs failed, which pages lack metas, which wires are
    down. It cannot be answered anywhere but on the box.

WHAT IT DOES
    Renders the dashboard through api_dashboard_html() - the SAME function the
    browser calls, with the same real contexts - then sorts every problem card
    into three piles:

      GREEN   the engine could fix this   -> how many more buttons to build
      AMBER   needs something from you    -> no button will ever help
      GREY    a decision, not a fault     -> already correct as it is

    Classification is by evidence on the card, and every rule is printed so you
    can see what it decided on. Where a card is ambiguous it says UNSURE rather
    than guessing - an inflated green pile would send us building the wrong
    things.
"""
import re
import sys
from collections import Counter, defaultdict

W = 78
CARD = re.compile(r"(?=<div class='card (?:overflowcard )?sev-)")
SEV = re.compile(r"<div class='card (?:overflowcard )?sev-([a-z]+)")
BAD = ("critical", "warn", "bad", "pink", "amber")

# A card whose headline number is zero/blank is almost always a card with no
# data behind it rather than a fault. Counted separately, never as a problem.
EMPTYVAL = re.compile(r"^(0|0/0|0%|0\.0|-|–|—|n/a|none|never|\?)$", re.I)

# Signals, in priority order. First match wins, and the winner is reported.
RULES = [
    ("GREEN", "already has a one-click fix", re.compile(r"/fix/")),
    ("AMBER", "names a credential you must supply",
     re.compile(r"\b[A-Z][A-Z0-9_]{5,}(KEY|TOKEN|SECRET|PASSWORD|ID|URL)\b")),
    ("AMBER", "says a key is missing or not set",
     re.compile(r"not set|no key|missing key|paste|needs? (a|your) key", re.I)),
    ("GREY", "is a decision you make, not a defect",
     re.compile(r"your decision|approve|decline|choose|you steer|budget|cap\b", re.I)),
]

# WHAT THE GREEN RULE USED TO BE, AND WHY IT IS GONE.
#
#     ("GREEN", "has an action the engine can already run", onclick="act(")
#
# act() posts to seven GLOBAL endpoints - /health, /tick, /selftest and four
# more. So a card titled "Idle" or "Postgres holds everything" was marked
# fixable because it happened to sit beside a /tick button. On live data that
# rule produced 45 of 46 greens and every one of them was wrong.
#
# There is no signal on a card that says "the engine could repair this". It is
# not written anywhere, and no amount of HTML parsing will find it. It has to
# be DECLARED by whoever wrote the card - which is what the fix registry is
# for. So GREEN now means exactly one thing: the card already carries a
# registered fix. That number starts near zero and grows as descriptors are
# added, which is honest: it measures work done, not work possible.
GLOBAL_ONLY = re.compile(r"onclick=\"act\('/(?!fix/)")


def rule(title=""):
    print()
    print(("== " + title + " ").ljust(W, "=") if title else "=" * W)


def main() -> int:
    import content_engine_api as API

    print("PROBLEM CLASSIFICATION".center(W))
    print("live data, read-only, nothing changed".center(W))

    try:
        html = API.api_dashboard_html()
    except Exception as e:
        print(f"\ncould not render the dashboard: {type(e).__name__}: {e}")
        print("This must run inside the api container so it can reach the store.")
        return 1
    print(f"\nrendered {len(html):,} chars through api_dashboard_html() - the "
          f"same function\nthe browser calls, so this sees exactly what you see.")

    blocks = CARD.split(html)[1:]
    cards, empties = [], 0
    for b in blocks:
        cut = b.find("<div class='card ", 4)
        b = b[:cut] if cut > 0 else b[:4000]
        m = SEV.match(b)
        if not m or m.group(1) not in BAD:
            continue
        val = (re.search(r"class='tnum'>([^<]{0,18})", b)
               or re.search(r"font-weight:800[^>]*>([^<]{0,18})", b))
        val = (val.group(1).strip() if val else "")
        if EMPTYVAL.match(val):
            empties += 1
            continue                      # no data behind it - not a fault
        title = re.search(r"class='ct'[^>]*>([^<]{0,70})", b)
        sec = re.search(r"id='card-([a-z0-9]+)-", b)
        cards.append({"title": (title.group(1).strip() if title else "?"),
                      "sec": (sec.group(1) if sec else "?"),
                      "val": val, "html": b})

    rule("1. what got counted")
    print(f"  cards flagged as a problem     : {len(cards) + empties}")
    print(f"  of those, EMPTY (no data yet)  : {empties}")
    print(f"  REAL problems to classify      : {len(cards)}")
    if not cards:
        print("\n  Nothing to classify. Either the engine is healthy or the "
              "boards have no live context.")
        return 0

    rule("2. the three piles")
    piles, why = defaultdict(list), Counter()
    for c in cards:
        for pile, reason, pat in RULES:
            if pat.search(c["html"]):
                piles[pile].append(c)
                why[f"{pile}: {reason}"] += 1
                break
        else:
            piles["UNSURE"].append(c)
            why["UNSURE: no signal on the card"] += 1

    labels = {"GREEN": "the engine could fix this",
              "AMBER": "needs something from you",
              "GREY": "a decision, not a defect",
              "UNSURE": "cannot tell from the card"}
    for k in ("GREEN", "AMBER", "GREY", "UNSURE"):
        n = len(piles[k])
        # PROPORTIONAL, not capped. The first version capped at 40 chars, so
        # 46 and 273 drew the same bar - a chart that hid the only number that
        # mattered.
        bar = "#" * max(1, round(40 * n / max(1, max(len(v) for v in piles.values()))))
        print(f"  {k:<8}{n:>5}  {100 * n / len(cards):>5.1f}%  "
              f"{labels[k]:<28}{bar}")

    rule("3. what each decision was based on")
    for k, n in why.most_common():
        print(f"  {n:>5}  {k}")

    rule("4. by section")
    bysec = defaultdict(Counter)
    for k, rows in piles.items():
        for c in rows:
            bysec[c["sec"]][k] += 1
    print(f"  {'section':<14}{'green':>7}{'amber':>7}{'grey':>7}{'unsure':>8}")
    for s in sorted(bysec, key=lambda x: -sum(bysec[x].values())):
        c = bysec[s]
        print(f"  {s[:13]:<14}{c['GREEN']:>7}{c['AMBER']:>7}{c['GREY']:>7}"
              f"{c['UNSURE']:>8}")

    rule("5. the green pile - what to build next")
    t = Counter(c["title"] for c in piles["GREEN"])
    print(f"  {len(piles['GREEN'])} card(s), {len(t)} distinct problem(s).")
    print("  A repeated title means ONE fix covers many cards.\n")
    for title, n in t.most_common(18):
        print(f"   x{n:<4} {title[:58]}")

    rule("6. the amber pile - only you can clear these")
    ta = Counter(c["title"] for c in piles["AMBER"])
    for title, n in ta.most_common(10):
        print(f"   x{n:<4} {title[:58]}")

    if piles["UNSURE"]:
        rule("7. unsure - deliberately not guessed")
        print("  These carry no signal I trust. Counting them as fixable would "
              "inflate\n  the work list; counting them as decisions would hide "
              "real faults.\n")
        for title, n in Counter(c["title"] for c in piles["UNSURE"]).most_common(10):
            print(f"   x{n:<4} {title[:58]}")

    rule()
    g, a, gy, u = (len(piles[k]) for k in ("GREEN", "AMBER", "GREY", "UNSURE"))
    print("WHAT THIS CAN AND CANNOT TELL YOU")
    print()
    print(f"  CAN: {len(cards)} cards report a real problem. The other "
          f"{empties} are empty of data, not faulty.")
    print(f"       {a} need a credential only you can supply.")
    print(f"       {gy} are decisions rather than defects.")
    print()
    print(f"  CANNOT: how many of the remaining {u} are automatable.")
    print("          There is no signal on a card that says so. The first")
    print("          version guessed by looking for an act() button and was")
    print("          wrong 45 times out of 46 - act() posts to seven GLOBAL")
    print("          endpoints, so a card beside a /tick button looked fixable.")
    print()
    print(f"  So GREEN counts one thing: cards carrying a DECLARED fix. {g} today.")
    print("  A coverage meter, not an estimate. It rises only when a fix")
    print("  descriptor is actually attached to a card.")
    print()
    print(f"  COVERAGE: {g} of {len(cards)} real problems have a fix "
          f"attached ({100 * g / max(1, len(cards)):.0f}%).")
    print()
    print("Read-only. Nothing was changed, published or spent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
