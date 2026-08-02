"""EVERY CREDENTIAL: WHERE IT IS, WHAT IT POWERS, AND HOW TO SET IT SAFELY.

    docker compose -f deploy/docker-compose.yml exec api python credentials.py
    ... --find linkedin       every field whose name or purpose matches
    ... --set  FIELD_NAME     type it in with no echo, no shell history
    ... --wire linkedin       what a wire needs, and what it has

Never prints a credential, or any part of one.

WHY THIS EXISTS. Two keys were entered correctly and neither reached the wire
it was meant for.

  IMAGE_API_KEY   a name this engine invented. Anyone holding an OpenAI key
                  calls it OPENAI_API_KEY, so the engine looked in one place
                  and reported the key missing.

  LINKEDIN_API_KEY  reads as "my LinkedIn key" and feeds PROSPEO lead
                  sourcing. The actual posting token is LINKEDIN_POST_TOKEN.
                  A token put in the obvious field goes to the wrong client,
                  silently, and the poster stays dark.

Both are naming faults, not data-entry mistakes. This tool exists so the
question "where did my key go" has a command instead of an afternoon.
"""
import sys


# what each wire actually needs, and the name people reach for by mistake
WIRES = {
    "linkedin": {
        "label": "LinkedIn posting",
        "needs": ["LINKEDIN_POST_TOKEN", "LINKEDIN_AUTHOR_URN"],
        "note": ("LINKEDIN_POST_TOKEN is an OAuth token with w_member_social "
                 "or w_organization_social. LINKEDIN_AUTHOR_URN looks like "
                 "urn:li:organization:12345 or urn:li:person:abc."),
        "confused_with": {
            "LINKEDIN_API_KEY": "feeds Prospeo LEAD SOURCING, not posting",
            "LINKEDIN_PROVIDER_URL": "the Prospeo endpoint, not posting",
        },
    },
    "leads": {
        "label": "Prospeo lead sourcing",
        "needs": ["PROSPEO_API_KEY"],
        "note": "LINKEDIN_API_KEY is accepted as a legacy alias for this.",
        "confused_with": {},
    },
    "image": {
        "label": "Image generation",
        "needs": ["IMAGE_API_KEY"],
        "note": ("Must be an OpenAI key (sk-). OPENAI_API_KEY is accepted as "
                 "an alias. Anthropic has no image API."),
        "confused_with": {
            "ANTHROPIC_API_KEY": "the engine's brain — makes no pictures",
        },
    },
    "wordpress": {
        "label": "WordPress publishing",
        "needs": ["WORDPRESS_URL", "WORDPRESS_USER", "WORDPRESS_APP_PASSWORD"],
        "note": ("WORDPRESS_APP_PASSWORD legitimately contains spaces — that "
                 "is how WordPress formats application passwords."),
        "confused_with": {},
    },
    "twitter": {
        "label": "X / Twitter posting",
        "needs": ["TWITTER_BEARER_TOKEN"],
        "note": "Needs tweet.write scope.",
        "confused_with": {},
    },
}


def _bind():
    import content_engine_api as API
    import content_engine_connectors as C
    API.get_store()
    if C._SETTINGS_GET is None:
        print("!! settings store not connected — this would only see "
              "environment variables. Refusing to report.")
        sys.exit(1)
    return C


def _shape(C, name, val):
    """A description of the value. NEVER the value."""
    if not val:
        return "not set"
    bad = ""
    try:
        bad = C.credential_problem(name, val)
    except Exception:
        bad = ""
    kind = "looks like an OpenAI key" if val.startswith("sk-") and not \
        val.startswith("sk-ant-") else \
        "looks like an Anthropic key" if val.startswith("sk-ant-") else \
        "looks like a LinkedIn URN" if val.startswith("urn:li:") else \
        "looks like a URL" if val.startswith("http") else \
        f"{len(val)} chars"
    return f"SET, {kind}" + (f"  !! {bad}" if bad else "")


def show_all(C) -> int:
    print("Every credential field, by the wire it powers. No values shown.\n")
    for key, w in WIRES.items():
        have = [n for n in w["needs"] if C._env(n)]
        state = ("LIVE" if len(have) == len(w["needs"]) else
                 f"{len(have)}/{len(w['needs'])}")
        print(f"[{state:^6}] {w['label']}   (--wire {key})")
        for n in w["needs"]:
            print(f"           {n:<24} {_shape(C, n, C._env(n))}")
        for n, why in w["confused_with"].items():
            if C._env(n):
                print(f"           {n:<24} SET — but this {why}")
        print()
    total = len(C.CONNECTOR_ENV_KEYS)
    filled = len([k for k in C.CONNECTOR_ENV_KEYS if C._env(k)])
    print(f"{filled} of {total} fields have a value across the whole engine.")
    print("Run --find <word> to search every field by name.")
    return 0


def find(C, term: str) -> int:
    term = (term or "").lower()
    print(f"Every field whose name contains {term!r}. No values shown.\n")
    hits = [k for k in sorted(C.CONNECTOR_ENV_KEYS) if term in k.lower()]
    if not hits:
        print("No field by that name. Run with no arguments to see them all.")
        return 1
    for k in hits:
        v = C._env(k)
        powers = ""
        for wk, w in WIRES.items():
            if k in w["needs"]:
                powers = f"-> powers {w['label']}"
            elif k in w["confused_with"]:
                powers = f"-> {w['confused_with'][k]}"
        print(f"  {k:<26} {_shape(C, k, v):<38} {powers}")
    print()
    aliased = C.aliased()
    if aliased:
        print("Resolved from an alternative name: " +
              ", ".join(f"{a} <- {b}" for a, b in aliased.items()))
    shadow = C.shadowed()
    if shadow:
        print("Stored value IGNORED as malformed (environment used instead): " +
              ", ".join(shadow))
    return 0


def wire(C, name: str) -> int:
    w = WIRES.get((name or "").lower())
    if not w:
        print(f"Unknown wire. Known: {', '.join(WIRES)}")
        return 1
    print(f"{w['label']}\n")
    missing = []
    for n in w["needs"]:
        v = C._env(n)
        print(f"  {n:<24} {_shape(C, n, v)}")
        if not v:
            missing.append(n)
    print(f"\n{w['note']}")
    for n, why in w["confused_with"].items():
        if C._env(n):
            print(f"\n!! {n} is SET, but it {why}. If you meant to connect "
                  f"{w['label']}, the value belongs in {w['needs'][0]}.")
    if missing:
        print(f"\nNOT LIVE. Missing: {', '.join(missing)}")
        print(f"Set one with:  python credentials.py --set {missing[0]}")
        return 1
    print("\nLIVE — every field this wire needs has a value. Whether the "
          "credential is ACCEPTED is a separate question only a real call "
          "can answer.")
    return 0


def set_one(C, name: str) -> int:
    """No echo, no shell history, never printed back."""
    import getpass
    import content_engine_api as API
    if name not in C.CONNECTOR_ENV_KEYS:
        print(f"{name} is not a field this engine reads.")
        print("Run --find <word> to see the real names.")
        return 1
    store = API.get_store()
    for wk, w in WIRES.items():
        if name in w["needs"]:
            print(f"{name} powers {w['label']}.")
            print(w["note"])
            break
    print("\nPaste the value. It will NOT be shown as you type.\n")
    try:
        val = getpass.getpass(f"{name}: ").strip()
    except Exception:
        print("!! No terminal available. Re-run with a TTY attached.")
        return 1
    if not val:
        print("Nothing entered. Nothing changed.")
        return 1
    bad = C.credential_problem(name, val)
    if bad:
        print(f"\n!! That value {bad}")
        print("   Nothing was saved.")
        return 1
    store.set_setting(name, val)
    del val
    print(f"\nSaved. {name} is now {_shape(C, name, C._env(name))}.")
    print("Whether it is ACCEPTED is a separate question — only a real call "
          "can answer that, and nothing here sends one.")
    return 0


def sync_env(C, apply: bool) -> int:
    """deploy/.env -> the settings store, in one command. Names only.

    THE ONE PROCEDURE. You edit /opt/content-engine/deploy/.env, run this, and
    never paste a credential into a chat, a web form, or a shell again.

    It reads os.environ rather than the file, because docker-compose loads
    deploy/.env into the container's environment at start (env_file:, line 34)
    and the file itself may not be mounted. Reading the environment is what the
    engine does, so it is what this must do."""
    import os
    rows = []
    for k in sorted(C.CONNECTOR_ENV_KEYS):
        ev = (os.getenv(k, "") or "").strip()
        sv = ""
        try:
            sv = (str(C._SETTINGS_GET(k) or "")).strip()
        except Exception:
            sv = ""
        if not ev and not sv:
            continue
        bad_e = C.credential_problem(k, ev) if ev else ""
        bad_s = C.credential_problem(k, sv) if sv else ""
        if ev and not sv:
            verdict, act = "only in .env", "COPY to settings"
        elif sv and not ev:
            verdict, act = "only in settings", "leave"
        elif ev == sv:
            verdict, act = "identical", "leave"
        elif bad_s and not bad_e:
            verdict, act = "DIFFER — stored one is malformed", "OVERWRITE from .env"
        else:
            verdict, act = "DIFFER — settings wins today", "leave (use --set to change)"
        rows.append((k, verdict, act, bad_s or bad_e))

    print("deploy/.env vs the settings store. No values shown.\n")
    print(f"  {'field':<28}{'state':<34}action")
    todo = []
    for k, verdict, act, bad in rows:
        print(f"  {k:<28}{verdict:<34}{act}")
        if bad:
            print(f"      !! {bad}")
        if act.startswith(("COPY", "OVERWRITE")):
            todo.append(k)
    print()
    if not todo:
        print("Nothing to sync. The settings store already has everything "
              "usable that deploy/.env holds.")
        return 0
    if not apply:
        print(f"{len(todo)} field(s) would change: {', '.join(todo)}")
        print("Re-run with --sync-env --apply to write them.")
        return 0

    import content_engine_api as API
    store = API.get_store()
    for k in todo:
        store.set_setting(k, (os.getenv(k, "") or "").strip())
    print(f"Wrote {len(todo)} field(s) into the settings store: "
          f"{', '.join(todo)}")
    print("Whether each is ACCEPTED is a separate question — only a real call "
          "can answer that, and nothing here sends one.")
    return 0


def clear_one(C, name: str) -> int:
    """Empty a field. Some credentials should be DELETED, not corrected.

    GOOGLE_ACCESS_TOKEN is the example that forced this to exist. It is a
    fallback slot for a raw bearer token, used only when there is no service
    account — and Google access tokens expire in about an hour, so a value
    there is stale within the day. With GOOGLE_SERVICE_ACCOUNT_JSON set, the
    engine mints its own. The field held a malformed value that every board
    reported as a problem to fix, when the right answer was to remove it."""
    import content_engine_api as API
    if name not in C.CONNECTOR_ENV_KEYS:
        print(f"{name} is not a field this engine reads.")
        return 1
    if not C._env(name):
        print(f"{name} is already empty. Nothing to do.")
        return 0
    store = API.get_store()
    store.set_setting(name, "")
    print(f"Cleared {name} from the settings store.")
    import os
    if (os.getenv(name, "") or "").strip():
        print(f"NOTE: {name} is ALSO set in deploy/.env, and the engine will "
              f"now fall through to that value. Remove the line there too if "
              f"you want the field genuinely empty.")
    return 0


def main() -> int:
    C = _bind()
    a = sys.argv[1:]
    if "--clear" in a:
        i = a.index("--clear")
        return clear_one(C, a[i + 1] if len(a) > i + 1 else "")
    if "--sync-env" in a:
        return sync_env(C, apply="--apply" in a)
    if "--set" in a:
        i = a.index("--set")
        return set_one(C, a[i + 1] if len(a) > i + 1 else "")
    if "--find" in a:
        i = a.index("--find")
        return find(C, a[i + 1] if len(a) > i + 1 else "")
    if "--wire" in a:
        i = a.index("--wire")
        return wire(C, a[i + 1] if len(a) > i + 1 else "")
    return show_all(C)


if __name__ == "__main__":
    sys.exit(main())
