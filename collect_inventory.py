# -*- coding: utf-8 -*-
"""THE CENSUS: everything this engine holds, before anything is switched on.

    docker compose -f deploy/docker-compose.yml exec -T api \
        python collect_inventory.py

WHAT IT IS FOR

Stage 1 of collecting the old OS into the new one. There is no migration to
run: the old dashboard and the new Agent OS are the same process over the
same Postgres, so every credential and every row is already where it always
was. What is missing is a RECEIPT - a single page that says what is actually
held, so the next stage is decided from evidence instead of memory.

WHAT IT WILL NOT DO

It runs nothing. No job is planned, no wire is called, no credential is
tested, no agent is woken. Every number below comes from a value already in
the store or a file already on disk. A census that spends money or sends a
message is not a census.

It also never prints a credential, or any part of one. A field is described
- "SET, 51 chars", "SET, looks like an OpenAI key" - and that is all. This
file's output is meant to be safe to paste into a chat window.

THE THREE QUESTIONS IT ANSWERS

  1. CREDENTIALS  which of the 94 fields have a value, where that value came
                  from (Postgres, the environment, or a differently-named
                  twin), and which are malformed.
  2. WIRES        which of the 33 wires have what they need, which are being
                  refused by the far end, and which can prove themselves for
                  free when we get to that stage.
  3. DATA         every store key the code defines, how much it holds, how
                  old it is, and - the important one - whether anything
                  still READS it.

WHY THE DATA KEYS ARE FOUND BY PARSING, NOT BY A LIST

A hand-typed list of store keys is the same bug this project has hit three
times: two lists that must agree, and only one of them gets updated. So the
keys are read out of the source with the ast module. Add a new
SOMETHING_KEY = "something" anywhere and it appears here on the next run
with no edit to this file. Nothing is imported to do it, so scanning has no
side effects and cannot start work.

ORPHANS ARE THE POINT

Removing the old dashboard removed PAGES, not data. If a key is written by
its own module and referenced by no other file, then something is filling it
every day and no screen shows it. That is data you own and cannot see, and
it is the actual work of stage 2.
"""
from __future__ import annotations

import ast
import os
import sys
from typing import Any, Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))

# A key constant is one whose NAME says so. Matching on the VALUE instead
# would sweep up SECTION = "blog" and MODULE = "commerce", which are not
# store keys at all, and the report would then invent orphans.
_KEY_NAME_OK = ("_KEY",)
_KEY_NAME_EXACT = ("KEY",)


# ==========================================================================
# small helpers
# ==========================================================================
def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _rule(title: str) -> None:
    print("")
    print("=" * 74)
    print(title)
    print("=" * 74)


def _py_files() -> List[str]:
    return sorted(f for f in os.listdir(HERE)
                  if f.endswith(".py") and not f.startswith("."))


def _read(path: str) -> str:
    try:
        with open(os.path.join(HERE, path), "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception:                                      # noqa: BLE001
        return ""


# ==========================================================================
# 1 - CREDENTIALS
# ==========================================================================
def _bind():
    """Attach to the running engine's store, or refuse.

    Without the settings provider this would see environment variables only
    and would report perfectly good keys as missing - a false empty, which
    is worse than no report because it sends you to fix what is not broken.
    credentials.py refuses for the same reason; so does this."""
    import content_engine_api as API
    import content_engine_connectors as C
    API.get_store()
    if C._SETTINGS_GET is None:
        print("!! settings store not connected. This would see environment "
              "variables only and would call stored keys missing.")
        print("   Run it inside the api container, not on the host.")
        sys.exit(1)
    return C


def _shape(C, name: str, val: str) -> str:
    """A description of a value. Never the value."""
    if not val:
        return "not set"
    try:
        bad = C.credential_problem(name, val)
    except Exception:                                      # noqa: BLE001
        bad = ""
    if val.startswith("sk-ant-"):
        kind = "looks like an Anthropic key"
    elif val.startswith("sk-"):
        kind = "looks like an OpenAI key"
    elif val.startswith("urn:li:"):
        kind = "looks like a LinkedIn URN"
    elif val.startswith("http"):
        kind = "looks like a URL"
    else:
        kind = "%d chars" % len(val)
    return "SET, " + kind + ("   !! " + bad if bad else "")


def _source(C, name: str) -> str:
    """Postgres, the environment, or a twin. This is the answer to 'I put it
    in the .env, why is it not live' - if it says settings, the browser value
    is the one in force and the file is being ignored, exactly as designed."""
    try:
        sv = C._SETTINGS_GET(name)
    except Exception:                                      # noqa: BLE001
        sv = None
    sv = (str(sv) if sv is not None else "").strip()
    ev = (os.getenv(name, "") or "").strip()
    alias = _d(C.aliased()).get(name)
    if alias:
        return "alias <- " + str(alias)
    if sv and ev:
        return "settings (env also set)"
    if sv:
        return "settings"
    if ev:
        return ".env"
    return ""


def credentials(C) -> Dict[str, Any]:
    _rule("1  CREDENTIALS   what is held, and where it came from")
    keys = list(C.CONNECTOR_ENV_KEYS)
    rows: List[Tuple[str, str, str]] = []
    for k in sorted(keys):
        v = C._env(k)
        rows.append((k, _shape(C, k, v), _source(C, k)))

    have = [r for r in rows if r[1] != "not set"]
    miss = [r for r in rows if r[1] == "not set"]
    bad = [r for r in rows if "!!" in r[1]]

    print("%d of %d fields have a value.\n" % (len(have), len(rows)))
    for k, shape, src in have:
        print("  %-30s %-38s %s" % (k, shape, src))

    if miss:
        print("\nNo value anywhere (%d):" % len(miss))
        # names only, wrapped - an empty field needs no description
        line = "   "
        for k, _s, _x in miss:
            if len(line) + len(k) > 72:
                print(line)
                line = "   "
            line += " " + k
        if line.strip():
            print(line)

    shadow = _d(C.shadowed())
    if shadow:
        print("\n!! STORED VALUE IGNORED as malformed, environment used "
              "instead (%d):" % len(shadow))
        for k, why in sorted(shadow.items()):
            print("   %-30s %s" % (k, why))
        print("   The .env value is doing the work. The Postgres value still "
              "needs clearing in the browser.")

    alias = _d(C.aliased())
    if alias:
        print("\nResolved from a differently-named twin (%d):" % len(alias))
        for k, a in sorted(alias.items()):
            print("   %-30s found as %s" % (k, a))

    if bad:
        print("\n!! MALFORMED and in force (%d): %s"
              % (len(bad), ", ".join(r[0] for r in bad)))

    # Which fields the .env template never had a line for. If one of these
    # is set, it came from the browser; if it is empty, the file was never
    # the reason, so editing the file will not fix it.
    tmpl = _read(os.path.join("deploy", ".env.example"))
    if tmpl:
        named = {ln.split("=", 1)[0].strip()
                 for ln in tmpl.splitlines()
                 if "=" in ln and not ln.strip().startswith("#")}
        absent = sorted(k for k in keys if k not in named)
        if absent:
            print("\n%d field(s) the .env template never mentions, so they "
                  "can only come from the browser:" % len(absent))
            line = "   "
            for k in absent:
                if len(line) + len(k) > 72:
                    print(line)
                    line = "   "
                line += " " + k
            if line.strip():
                print(line)

    return {"total": len(rows), "set": len(have), "missing": len(miss),
            "shadowed": len(shadow), "aliased": len(alias), "malformed": len(bad)}


# ==========================================================================
# 2 - WIRES
# ==========================================================================
def wires(C) -> Dict[str, Any]:
    _rule("2  WIRES   what has what it needs, and who is refusing")
    st = _d(C.status())
    reasons = _d(C.auth_reasons())
    verifiable = set(getattr(C, "VERIFIABLE", ()))

    live, refusing, off = [], [], []
    for w in sorted(st):
        ok = bool(st[w])
        why = str(reasons.get(w) or "")
        if why and not ok:
            refusing.append((w, why))
        elif ok:
            live.append(w)
        else:
            off.append(w)

    print("%d live | %d refused by the far end | %d not configured\n"
          % (len(live), len(refusing), len(off)))

    print("LIVE (%d)" % len(live))
    for w in live:
        mark = "  (provable for free)" if w in verifiable else ""
        print("   %-26s%s" % (w, mark))

    if refusing:
        print("\nREFUSED - the credential is present and the far end says no "
              "(%d)" % len(refusing))
        for w, why in refusing:
            print("   %-26s %s" % (w, why))

    if off:
        print("\nNOT CONFIGURED (%d)" % len(off))
        line = "   "
        for w in off:
            if len(line) + len(w) > 72:
                print(line)
                line = "   "
            line += " " + w
        if line.strip():
            print(line)

    untested = sorted(w for w in verifiable if w in st)
    if untested:
        print("\nThese %d can prove themselves at zero cost when you say go. "
              "A proof reads; it never posts, sends or spends." % len(untested))
        print("   " + ", ".join(untested))

    return {"total": len(st), "live": len(live), "refusing": len(refusing),
            "off": len(off)}


# ==========================================================================
# 3 - DATA
# ==========================================================================
_SRC: Dict[str, str] = {}

#: Files that PROVE things rather than SHOW them. A verifier reading a key
#: does not put it on a screen, so counting it as a reader would report
#: "you can see this" about data no page renders. This census counts as a
#: tool too - its own docstring names three keys as examples, and without
#: this it would list itself as the reader that saves them.
_TOOL_PREFIX = ("verify_", "audit_", "why_", "check_")
_TOOL_EXACT = ("collect_inventory.py", "credentials.py", "live_test.py",
               "main.py", "worker.py")


def _is_tool(fname: str) -> bool:
    return fname.startswith(_TOOL_PREFIX) or fname in _TOOL_EXACT


def _sources() -> Dict[str, str]:
    """Every file read once. Re-reading 141 files per key turned a census
    into a minute of disk for no new information."""
    if not _SRC:
        for f in _py_files():
            _SRC[f] = _read(f)
    return _SRC


def _key_constants() -> Dict[str, List[Tuple[str, str]]]:
    """Every store key the code defines, found by parsing, not by a list.

    ast, not import: a census must not be able to start work, and importing
    141 modules to read a string would give every one of them a chance to.

    Returns key -> [(file, CONSTANT_NAME)], a LIST because three different
    desks define lane_log and each of them is a real owner."""
    found: Dict[str, List[Tuple[str, str]]] = {}
    for fname, src in _sources().items():
        if not src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in tree.body:               # module level only
            if not isinstance(node, ast.Assign):
                continue
            if not isinstance(node.value, ast.Constant):
                continue
            if not isinstance(node.value.value, str):
                continue
            for tgt in node.targets:
                if not isinstance(tgt, ast.Name):
                    continue
                nm = tgt.id
                if nm.endswith(_KEY_NAME_OK) or nm in _KEY_NAME_EXACT:
                    val = node.value.value
                    if val and val.islower():
                        found.setdefault(val, []).append((fname, nm))
    return found


def _readers(key: str, owners: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    """Which files can actually reach this key, by two separate routes.

    A LITERAL SEARCH IS NOT ENOUGH, and getting this wrong is the whole
    reason to be careful here. Two ways it lies, both already caught:

    1. BY CONSTANT. content_engine_orders.py reads the deals list every run
       and writes BI.DEALS_KEY - the constant, never the string. Searching
       for "bi_deals" finds nothing and reports an orphan over a working
       pipeline.

    2. BY FUNCTION. Nothing anywhere names risk_register, because screens
       call content_engine_risk's own reader function and never touch the
       key. The data is on a page; the key looks stranded.

    So this reports both routes and lets the caller judge:
      direct  - the file names the key or the owning module's constant
      via     - the file imports an owning module at all, so it can reach
                whatever that module chooses to expose

    A key is only truly stranded when BOTH are empty. Verifiers and this
    census are excluded from both: proving a value exists is not showing
    it to anyone."""
    needles = ('"%s"' % key, "'%s'" % key)
    owner_files = {f for f, _c in owners}
    direct: List[str] = []
    via: List[str] = []
    for fname, src in _sources().items():
        if fname in owner_files or not src or _is_tool(fname):
            continue
        hit = any(n in src for n in needles)
        if not hit:
            for ofile, const in owners:
                # the import check matters because CONSTANT names collide:
                # LANE_LOG_KEY is declared in five files, so a bare name
                # search would make every desk a reader of every other
                # desk's log.
                if ("import " + ofile[:-3]) in src and const in src:
                    hit = True
                    break
        if hit:
            direct.append(fname)
            continue
        if any(("import " + f[:-3]) in src for f in owner_files):
            via.append(fname)
    return {"direct": direct, "via": via}


def _size(val) -> str:
    if val is None:
        return "empty"
    if isinstance(val, list):
        return "%d row(s)" % len(val)
    if isinstance(val, dict):
        return "%d field(s)" % len(val)
    s = str(val)
    return "%d chars" % len(s) if len(s) > 20 else repr(s)


def _newest(val, depth: int = 0) -> str:
    """The most recent ISO-looking date anywhere inside. Age is the thing
    that separates a live key from one that stopped being written months
    ago, and neither looks different from the outside."""
    if depth > 4:
        return ""
    best = ""
    if isinstance(val, str):
        s = val.strip()
        if len(s) >= 10 and s[4] == "-" and s[7] == "-" and s[:4].isdigit():
            return s[:19]
        return ""
    if isinstance(val, dict):
        for v in val.values():
            got = _newest(v, depth + 1)
            if got > best:
                best = got
    elif isinstance(val, list):
        for v in val[:200]:
            got = _newest(v, depth + 1)
            if got > best:
                best = got
    return best


def data(store) -> Dict[str, Any]:
    _rule("3  DATA   every store key, how much it holds, and who reads it")
    consts = _key_constants()
    print("%d store key(s) defined across the code.\n" % len(consts))

    held, empty, orphans = [], [], []
    for key in sorted(consts):
        owners = consts[key]
        try:
            val = store.get_setting(key, None)
        except Exception:                                  # noqa: BLE001
            val = None
        r = _readers(key, owners)
        row = (key, owners[0][0], _size(val), _newest(val),
               len(r["direct"]), len(r["via"]))
        if val is None or val == [] or val == {}:
            empty.append(row)
        else:
            held.append(row)
            if not r["direct"] and not r["via"]:
                orphans.append(row)

    print("HOLDING DATA (%d)" % len(held))
    print("   %-28s %-15s %-19s %6s %6s"
          % ("key", "size", "newest", "reads", "reach"))
    for key, owner, size, newest, ndir, nvia in held:
        print("   %-28s %-15s %-19s %6d %6d"
              % (key, size, newest or "no date", ndir, nvia))
    print("   reads = files that name the key. reach = files that import "
          "the owning module and can get at it through its own functions.")

    if orphans:
        print("\n!! STRANDED - holding data, and no engine file reaches it "
              "by either route (%d)" % len(orphans))
        for key, owner, size, newest, _a, _b in orphans:
            print("   %-28s %-15s written by %s" % (key, size, owner))
        print("   This is data you own and cannot see. It is the work of "
              "stage 2.")

    if empty:
        print("\nDEFINED BUT EMPTY (%d) - nothing has ever written these:"
              % len(empty))
        line = "   "
        for key, _o, _s, _n, _a, _b in empty:
            if len(line) + len(key) > 72:
                print(line)
                line = "   "
            line += " " + key
        if line.strip():
            print(line)

    return {"defined": len(consts), "holding": len(held),
            "empty": len(empty), "orphans": len(orphans)}


# ==========================================================================
# 4 - JOBS AND SPEND
# ==========================================================================
def jobs(store) -> Dict[str, Any]:
    _rule("4  JOBS AND SPEND")
    counts: Dict[str, int] = {}
    total = 0
    try:
        for j in _l(store.list_jobs()):
            s = str(_d(j).get("status") or "unknown")
            counts[s] = counts.get(s, 0) + 1
            total += 1
    except Exception as exc:                               # noqa: BLE001
        print("could not read jobs: %s" % type(exc).__name__)

    print("%d job(s) in the store." % total)
    for s in sorted(counts):
        print("   %-18s %d" % (s, counts[s]))

    for label, fn in (("today", "daily_cost"), ("this month", "monthly_cost")):
        try:
            print("spend %-11s $%.4f" % (label, float(getattr(store, fn)())))
        except Exception:                                  # noqa: BLE001
            print("spend %-11s NOT MEASURED" % label)

    return {"jobs": total, "by_status": counts}


# ==========================================================================
def main() -> int:
    print("ENGINE CENSUS - read only. Nothing here runs, calls, sends or "
          "spends.")
    C = _bind()
    import content_engine_api as API
    store = API.get_store()

    cred = credentials(C)
    wire = wires(C)
    dat = data(store)
    job = jobs(store)

    _rule("SUMMARY")
    print("credentials   %d of %d set   %d malformed   %d shadowed   %d aliased"
          % (cred["set"], cred["total"], cred["malformed"],
             cred["shadowed"], cred["aliased"]))
    print("wires         %d live of %d   %d refusing   %d not configured"
          % (wire["live"], wire["total"], wire["refusing"], wire["off"]))
    print("data          %d keys defined   %d holding data   %d ORPHANED"
          % (dat["defined"], dat["holding"], dat["orphans"]))
    print("jobs          %d in the store" % job["jobs"])
    print("")
    print("Nothing was started. Nothing was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
