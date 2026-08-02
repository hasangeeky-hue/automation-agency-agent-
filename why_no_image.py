"""WHY DOES THIS PIECE HAVE NO PICTURE — read the live jobs and say.

Run on the VPS:
    docker compose -f deploy/docker-compose.yml exec api python why_no_image.py
    ... --test    makes ONE real image call and prints what the provider said

Reads only. Spends nothing. Publishes nothing.

For every content piece in the store it prints the type the strategist ACTUALLY
chose, whether a hero image is attached, and — when there is none — the reason
the engine recorded. That last column is the one that did not exist: a piece
without a picture used to look exactly like a piece whose image failed, and the
previews showed the same silent blank for both.
"""
import sys


def live_test() -> int:
    """ONE real call to the image provider, and the provider's own answer.

    Costs about EUR 0.04 if it succeeds and nothing if it fails. It publishes
    nothing. This exists because every failure on this box reported "the image
    provider returned nothing" - my phrase, not the provider's - while the real
    message sat in a discarded HTTP body."""
    import content_engine_connectors as C
    import content_engine_site_taxonomy as T

    # BIND THE SETTINGS STORE FIRST, exactly as the api and worker do.
    # _env() reads Postgres settings, THEN os.environ. Nothing binds that
    # reader automatically - api.py:90 and main.py:119 each call
    # set_settings_provider at startup. The first version of this test
    # returned before importing the api module, so the reader stayed None,
    # _env fell through to os.environ, and it reported a key entered on the
    # Connect board as NOT SET. The key was always fine. The test was not.
    import content_engine_api as API
    try:
        API.get_store()
    except Exception as e:
        print(f"!! could not reach the settings store: {type(e).__name__}: {e}")
        print("   Everything below reads OS environment only, so a key saved "
              "on the Connect board will look missing when it is not.")
    bound = C._SETTINGS_GET is not None

    key = C._env("IMAGE_API_KEY") or ""
    src = ""
    if key:
        if "IMAGE_API_KEY" in C.shadowed():
            src = ("the ENVIRONMENT — the Connect board value was ignored "
                   f"because it {C.shadowed()['IMAGE_API_KEY']}")
        elif bound and (C._SETTINGS_GET("IMAGE_API_KEY") or ""):
            src = "the Connect board (database)"
        else:
            src = "an environment variable"
    print(f"settings : {'connected' if bound else 'NOT CONNECTED — env only'}")
    print(f"provider : {C._env('IMAGE_PROVIDER', 'openai')}")
    print(f"model    : {C._env('IMAGE_MODEL', 'gpt-image-1')}  "
          f"(unset means gpt-image-1)")
    print(f"key      : {'set, ' + str(len(key)) + ' chars, starts ' + key[:7] + ', from ' + src if key else 'NOT SET'}")
    # CHECK THE VALUES BEFORE SPENDING A CALL ON THEM. IMAGE_PROVIDER was
    # saved as "open ai" with a space, which matched no branch, so the engine
    # made no request at all and then reported that a provider had answered.
    problems = []
    for fld in ("IMAGE_PROVIDER", "IMAGE_API_KEY", "IMAGE_MODEL"):
        bad = C.credential_problem(fld, C._env(fld))
        if bad:
            problems.append(f"{fld} {bad}")
    raw_prov = C._env("IMAGE_PROVIDER", "openai")
    if raw_prov and C._norm_provider(raw_prov) != raw_prov.strip().lower():
        print(f"note     : IMAGE_PROVIDER is stored as {raw_prov!r}; the engine "
              f"now reads that as '{C._norm_provider(raw_prov)}'. Before this "
              f"fix a stray space here silently sent zero requests.")
    if problems:
        print()
        print("!! Fix these on the Connect board before testing:")
        for pr in problems:
            print(f"   - {pr}")
        return 1
    if not key:
        print()
        if not bound:
            print("!! The settings store is not connected, so this only "
                  "checked OS environment variables. A key saved on the "
                  "Connect board lives in Postgres and would not show here. "
                  "That is a fault in this test, not in your key.")
        else:
            print("!! The settings store IS connected and holds no "
                  "IMAGE_API_KEY. Add it on the Connect board — it must be an "
                  "OpenAI key; Anthropic has no image API.")
        return 1

    print()
    print("calling the provider once ...", flush=True)
    url = C.generate_image(T.image_prompt("Automation for small firms"))
    if url:
        print()
        print(f"WORKS. {url}")
        print("The image is hosted in your WordPress media library, so the URL "
              "will not expire. Produce a new piece and it will carry one.")
        return 0
    print()
    print("FAILED — the provider said:")
    print()
    print(f"    {C.last_image_error()}")
    print()
    why = C.last_image_error().lower()
    if "verif" in why:
        print("gpt-image-1 needs your OpenAI ORGANISATION verified. Either "
              "verify it at platform.openai.com/settings/organization/general, "
              "or set IMAGE_MODEL=dall-e-3 on the Connect board — dall-e-3 "
              "needs no verification and this code already handles its "
              "URL-shaped response.")
    elif "401" in why or "invalid" in why or "incorrect" in why:
        print("The key is being rejected. Check it is an OpenAI key with the "
              "images scope, and that it has not been revoked.")
    elif "quota" in why or "billing" in why or "429" in why:
        print("The key works but the OpenAI account will not bill. Add credit "
              "or raise the rate limit.")
    return 1


def audit_all() -> int:
    """Every stored credential, checked. Never prints a value.

    The image key was found by staring at one failure for an hour. There are
    85 of these fields and any of them can hold a paste accident, so none of
    them should need an hour."""
    import content_engine_api as API
    import content_engine_connectors as C
    API.get_store()                       # bind settings BEFORE reading them
    if C._SETTINGS_GET is None:
        print("!! settings store not connected — this would only check "
              "environment variables. Not reporting.")
        return 1
    total = len(C.CONNECTOR_ENV_KEYS)
    filled = [k for k in C.CONNECTOR_ENV_KEYS if C._env(k)]
    bad = C.credential_audit()
    print(f"{len(filled)} of {total} credential fields have a value.")
    print()
    if not bad:
        print("None of them look wrong. (This checks the SHAPE of a value — "
              "a well-formed key can still be revoked or out of quota.)")
        return 0
    print(f"{len(bad)} look wrong. They are SET, so every wire reads green, "
          f"and they cannot work:")
    print()
    import os
    for r in bad:
        print(f"  {r['key']}")
        print(f"      {r['problem']}")
        # DID YOU ALREADY PUT A GOOD ONE IN deploy/.env? Say so. The stored
        # value used to shadow it silently, which is how a correct key can be
        # present on the box and unreachable by the engine.
        ev = (os.getenv(r["key"], "") or "").strip()
        if ev and not C.credential_problem(r["key"], ev):
            print("      -> the ENVIRONMENT holds a well-formed value for this "
                  "field, and the engine now uses it. Clean up the Connect "
                  "board entry when convenient; nothing is blocked.")
        elif ev:
            print("      -> deploy/.env also has a value for this field, and it "
                  "has the same problem.")
        else:
            print("      -> nothing usable in deploy/.env either, so this field "
                  "is genuinely blocked until you fix it.")
    print()
    print("No value is printed above, by design.")
    return 1


def find_key() -> int:
    """WHERE IS THE OPENAI KEY. Scans every setting and every environment
    variable for an OpenAI-shaped value and reports the NAMES it found them
    under. Never prints a value, or any part of one.

    "I already added it properly" is usually true. IMAGE_API_KEY is a name
    this engine invented; anyone holding an OpenAI key calls it
    OPENAI_API_KEY. Looking under one name and declaring the key missing was
    my error, not a data-entry mistake."""
    import os
    import content_engine_api as API
    import content_engine_connectors as C
    API.get_store()

    def openai_shaped(v):
        v = (v or "").strip()
        return v.startswith("sk-") and " " not in v and len(v) > 20

    hits = []
    for k in sorted(set(C.CONNECTOR_ENV_KEYS)):
        try:
            if C._SETTINGS_GET and openai_shaped(str(C._SETTINGS_GET(k) or "")):
                hits.append((k, "the Connect board (database)"))
        except Exception:
            pass
    for k, v in sorted(os.environ.items()):
        if openai_shaped(v):
            hits.append((k, "the environment (deploy/.env)"))

    print("Scanning every setting and every environment variable for a value "
          "shaped like an OpenAI key (starts sk-, no spaces).")
    print()
    if not hits:
        print("NOT FOUND. There is no OpenAI-shaped value anywhere the engine "
              "can see — not under IMAGE_API_KEY, not under OPENAI_API_KEY, "
              "not under any other name, in either the database or "
              "deploy/.env.")
        print()
        print("That means the key has not reached this container. If you saved "
              "it on the Connect board, check it landed in the IMAGE_API_KEY "
              "field and not another one. If you put it in deploy/.env, the "
              "container needs `up -d` to pick the file up.")
        return 1
    print(f"FOUND {len(hits)}:")
    for name, where in hits:
        used = " <- the image generator uses this" if name in (
            "IMAGE_API_KEY", "OPENAI_API_KEY", "OPENAI_KEY") else ""
        print(f"  {name:<28} in {where}{used}")
    print()
    usable = [h for h in hits if h[0] in ("IMAGE_API_KEY", "OPENAI_API_KEY",
                                          "OPENAI_KEY")]
    if usable:
        print("The engine can reach one. Run --test to make a real call.")
        return 0
    print("None of these are in a name the image generator reads. Copy the "
          "value from one of the fields above into IMAGE_API_KEY on the "
          "Connect board, or rename it in deploy/.env.")
    return 1


def set_key() -> int:
    """Type the key in, invisibly, and store it. Then test it immediately.

    Every route this key could have taken was a bad one: pasted into a web
    form that silently accepted a shell command, typed into a shell where it
    lands in ~/.bash_history, or sent into a chat where it becomes public and
    has to be revoked.

    getpass reads it with no echo. It never appears on screen, never enters
    shell history, and is never printed back. It goes straight to the settings
    store the engine reads."""
    import getpass
    import content_engine_api as API
    import content_engine_connectors as C
    store = API.get_store()

    print("Paste your OpenAI key. It will NOT be shown as you type.")
    print("(Get one at platform.openai.com/api-keys - it starts 'sk-'.)")
    print()
    try:
        key = getpass.getpass("OPENAI KEY: ").strip()
    except Exception:
        print("!! No terminal available. Re-run with a TTY attached.")
        return 1
    if not key:
        print("Nothing entered. Nothing changed.")
        return 1

    bad = C.credential_problem("IMAGE_API_KEY", key)
    if bad:
        print()
        print(f"!! That value {bad}")
        print("   Nothing was saved. Try again.")
        return 1

    store.set_setting("IMAGE_API_KEY", key)
    store.set_setting("IMAGE_PROVIDER", "openai")
    del key                                   # do not keep it in this frame
    print()
    print("Saved, and IMAGE_PROVIDER set to 'openai'.")
    print("Testing it now with one real call ...")
    print()
    return live_test()


def main() -> int:
    if "--set-key" in sys.argv:
        return set_key()
    if "--test" in sys.argv:
        return live_test()
    if "--audit" in sys.argv:
        return audit_all()
    if "--find" in sys.argv:
        return find_key()
    import content_engine_api as API

    store = API.get_store()
    try:
        jobs = store.list_jobs()
    except Exception:
        jobs = store.all() if hasattr(store, "all") else []
    pieces = [j for j in jobs if (j or {}).get("type") == "content_piece"]
    pieces.sort(key=lambda j: j.get("created_at") or "", reverse=True)

    if not pieces:
        print("No content pieces in the store yet. Run probe_one_job.py first.")
        return 0

    import content_engine_site_taxonomy as T

    print(f"{len(pieces)} content piece(s), newest first\n")
    print(f"{'job':<24}{'status':<19}{'type':<17}{'image':<8}why")
    print("-" * 100)

    counts = {"has": 0, "skipped": 0, "failed": 0, "silent": 0}
    for j in pieces[:40]:
        pl = j.get("payload") or {}
        piece = pl.get("content_producer") or {}
        cal = ((pl.get("content_strategist") or {}).get("calendar") or [])
        try:
            ix = int((pl.get("config") or {}).get("produce_index", 0) or 0)
            row = cal[ix] if 0 <= ix < len(cal) else (cal[0] if cal else {})
        except Exception:
            row = {}
        ptype = (row or {}).get("type") or (pl.get("config") or {}).get("type") or "?"
        url = piece.get("image_url") or pl.get("image_url") or ""

        if url:
            mark, why, k = "YES", url[:48], "has"
        elif pl.get("image_skipped"):
            mark, why, k = "no", str(pl["image_skipped"]), "skipped"
        elif pl.get("image_error"):
            mark, why, k = "FAIL", str(pl["image_error"]), "failed"
        elif not piece:
            mark, why, k = "-", "the piece was never produced", "silent"
        else:
            mark, why, k = "no", ("produced before the engine explained itself "
                                  "— re-run it for a reason"), "silent"
        counts[k] += 1
        print(f"{str(j.get('job_id'))[:23]:<24}{str(j.get('status'))[:18]:<19}"
              f"{str(ptype)[:16]:<17}{mark:<8}{why[:52]}")

    print("\n" + "=" * 100)
    print(f"with an image: {counts['has']}   deliberately skipped: {counts['skipped']}"
          f"   FAILED: {counts['failed']}   no reason recorded: {counts['silent']}")

    types = {(( (j.get('payload') or {}).get('content_strategist') or {})
              .get('calendar') or [{}])[0].get('type')
             for j in pieces if j.get('payload')}
    types = {t for t in types if t}
    unknown = [t for t in types if t not in T.CONTENT_TYPES]
    print(f"\ntypes the strategist actually chose: {sorted(types) or '(none yet)'}")
    if unknown:
        print(f"!! {unknown} are NOT in the one vocabulary — that is the bug class "
              f"that silently removed every non-blog image. Run "
              f"verify_vocabulary.py.")
    else:
        print("all of them are in the one vocabulary "
              f"({', '.join(T.CONTENT_TYPES)}).")

    if counts["failed"]:
        print("\nA FAILED image means the call was made and did not come back with "
              "a URL. The reason column above says which — almost always "
              "IMAGE_API_KEY missing, or an Anthropic key in the image slot "
              "(Anthropic has no image API).")
    if counts["silent"]:
        print("\nPieces with no reason were produced before this fix. Their "
              "previews will stay blank; produce a new one to see the reason "
              "flow through to the preview box.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
