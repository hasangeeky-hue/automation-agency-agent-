# -*- coding: utf-8 -*-
"""Every button, what it calls, and whether that thing exists.

THE CLASS: a button that looks alive and does nothing. Three ways it
happens, and they need different fixes:

  STUB     the handler exists only to say "not wired yet" (uiNotWired).
           Honest, but it is a promise, and 227 endpoints are already
           running - most of these have a real one waiting.
  BROKEN   the handler POSTs to an endpoint that does not exist. This
           is the dangerous one: it looks wired, fails at runtime, and
           only the browser console ever knows.
  LOCAL    no network call: it opens a tab or toggles a panel. Fine.
  WIRED    it calls an endpoint this API actually serves.

  python audit_buttons.py           # the map
  python audit_buttons.py --gate    # exit 1 if anything is BROKEN
"""
from __future__ import annotations

import io
import re
import sys

JS_SOURCES = [
    "content_engine_dashboard.py",
    "content_engine_seo_screens.py",
    "content_engine_factory_ui.py",
    "content_engine_media_center.py",
    "content_engine_media_workbench.py",
    "content_engine_os_screens.py",
    "content_engine_search_screens.py",
]
MARKUP_SOURCES = JS_SOURCES + [
    "content_engine_factory_screens.py",
    "content_engine_control_screens.py",
    "content_engine_bi_screens.py",
    "content_engine_command_ui.py",
    "content_engine_seo_boards.py",
    "content_engine_media_platforms.py",
    "content_engine_sga_screens.py",
]


def _read(p):
    try:
        return io.open(p, encoding="utf-8").read()
    except OSError:
        return ""


def routes() -> set:
    s = _read("content_engine_api.py")
    out = set()
    for _m, p in re.findall(r'@app\.(get|post)\("([^"]+)"', s):
        out.add(p)
    return out


def _serves(path: str, known: set) -> bool:
    """A path matches a route, including {param} segments.

    JS builds most paths by concatenation - fetch('/media/abort/' + id -
    so what is extractable is a PREFIX, not the whole path. Treating the
    prefix as the literal path reported twenty live buttons as broken.
    A prefix that any real route starts with is served."""
    if path in known:
        return True
    parts = path.strip("/").split("/")
    for r in known:
        rp = r.strip("/").split("/")
        if len(rp) == len(parts) and all(
                b.startswith("{") or b == a for a, b in zip(parts, rp)):
            return True
        # the extracted text is a prefix of a real route
        if r.startswith(path) or path.startswith(r + "/"):
            return True
    return False


def handlers() -> dict:
    """{function name -> its body}, from every module that ships JS.

    A screen module can ship its own <script>; scanning only the seven
    obvious ones reported 68 live handlers as missing."""
    out = {}
    for p in set(JS_SOURCES) | set(MARKUP_SOURCES):
        s = _read(p)
        def _body(start):
            """Stop at the NEXT function. Reading blindly ahead made a
            one-line handler inherit its neighbour's stub message, and
            three wired buttons were reported as still stubbed."""
            chunk = s[start:start + 1400]
            nxt = chunk.find("function ")
            return chunk[:nxt] if nxt > 0 else chunk

        for m in re.finditer(r"function\s+([A-Za-z_]\w*)\s*\(", s):
            out[m.group(1)] = _body(m.end())
        # window.wbRefresh = function(){...} and wbRefresh = async function
        # are exactly as alive in a browser as a declaration. Missing them
        # reported the whole media workbench toolbar as undefined.
        for m in re.finditer(
                r"(?:window\.)?([A-Za-z_]\w*)\s*=\s*(?:async\s+)?function", s):
            out.setdefault(m.group(1), _body(m.end()))
    return out


def called() -> dict:
    """{handler name -> the boards that call it}."""
    out = {}
    for p in MARKUP_SOURCES:
        s = _read(p)
        for name in re.findall(r"onclick=[\"'\\]*([A-Za-z_]\w*)\(", s):
            # a language keyword or a python escape helper is not a handler
            if name in ("function", "if", "for", "while", "return", "typeof",
                        "new", "catch", "switch", "_D", "_d", "_s", "_l", "e"):
                continue
            out.setdefault(name, set()).add(p.replace("content_engine_", "")
                                            .replace(".py", ""))
    return out


def main() -> int:
    known, hs, cs = routes(), handlers(), called()
    print("=" * 74)
    print("BUTTON AUDIT - what each one calls, and whether it exists")
    print("=" * 74)
    print(f"\n{len(known)} routes served | {len(cs)} handler(s) called from "
          f"the boards\n")

    stub, broken, wired, local, unknown = [], [], [], [], []
    for name in sorted(cs):
        body = hs.get(name)
        where = ", ".join(sorted(cs[name]))
        if body is None:
            unknown.append((name, where, ""))
            continue
        if "uiNotWired" in body[:200]:
            stub.append((name, where, ""))
            continue
        paths = re.findall(r"""fetch\(\s*['"]([^'"?]+)""", body)
        paths += re.findall(r"""\b(?:act|post|seoRun|mcPost)\(\s*['"]([^'"?]+)""",
                            body)
        paths = [p for p in paths if p.startswith("/")]
        if not paths:
            local.append((name, where, ""))
            continue
        miss = [p for p in paths if not _serves(p, known)]
        if miss:
            broken.append((name, where, ", ".join(sorted(set(miss)))))
        else:
            wired.append((name, where, ", ".join(sorted(set(paths))[:2])))

    for label, rows in (("BROKEN - calls an endpoint that does not exist",
                         broken),
                        ("STUB - says 'not wired yet'", stub),
                        ("UNKNOWN - no handler found in any shipped script",
                         unknown)):
        print(f"--- {label}: {len(rows)} ---")
        for n, where, extra in rows:
            print(f"    {n:20} [{where}]" + (f"  -> {extra}" if extra else ""))
        print()
    print(f"--- WIRED to a real endpoint: {len(wired)} ---")
    print(f"--- LOCAL (opens a tab, no network): {len(local)} ---")
    print("=" * 74)
    print(f"{len(broken)} broken, {len(stub)} stubbed, {len(unknown)} "
          f"unknown, {len(wired)} wired, {len(local)} local")
    print("=" * 74)

    if "--gate" in sys.argv and (broken or unknown):
        print("GATE FAILED: a button that calls nothing real is worse than "
              "a button that admits it")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
