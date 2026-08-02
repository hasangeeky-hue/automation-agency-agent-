"""A DIAGNOSTIC THAT READS THE WRONG PLACE IS WORSE THAN NO DIAGNOSTIC.

why_no_image.py --test reported a key entered on the Connect board as
"NOT SET". The key was fine. The test was not.

_env() reads Postgres settings first and os.environ second, but only after
something calls connectors.set_settings_provider(store.get_setting). The api
does it at content_engine_api.py:90; the worker does it at main.py:119.
Nothing does it automatically. A standalone script that touches _env() without
binding that reader sees ONLY environment variables — so every credential the
dashboard saved looks missing, and the tool confidently blames the user for
something it never looked at.

That is the whole failure: a tool ran a path the engine does not use, and was
believed because it printed a definite answer.

    python verify_diagnostics.py
"""
import re
import sys
from pathlib import Path

# tools that offer to exercise a LIVE credential — these must bind the store
LIVE_TOOLS = ["why_no_image.py", "probe_one_job.py", "audit_live.py",
              "audit_gaps.py"]

FAILS = []


def chk(ok, label, detail=""):
    print(("  OK   " if ok else "  FAIL ") + label + (f" — {detail}" if detail else ""))
    if not ok:
        FAILS.append(label)


print("== every live-credential tool must bind the settings store ==")
for name in LIVE_TOOLS:
    p = Path(name)
    if not p.exists():
        print(f"  --   {name} not present, skipping")
        continue
    s = p.read_text(encoding="utf-8", errors="ignore")
    touches = bool(re.search(r"\b_env\(|generate_image\(|last_image_error", s))
    binds = ("get_store()" in s or "set_settings_provider" in s)
    if not touches:
        print(f"  --   {name} reads no credentials")
        continue
    chk(binds, f"{name} binds the settings store",
        "it reads credentials but never calls get_store(), so it sees "
        "environment variables only and will report saved keys as missing"
        if not binds else "")

print("\n== and must bind it BEFORE the first credential read ==")
# the ordering matters: binding after the read is the same bug wearing a hat
p = Path("why_no_image.py")
if p.exists():
    s = p.read_text(encoding="utf-8", errors="ignore")
    i_bind = s.find("get_store()")
    i_read = s.find('_env("IMAGE_API_KEY")')
    chk(i_bind != -1 and (i_read == -1 or i_bind < i_read),
        "why_no_image.py binds the store before reading IMAGE_API_KEY",
        f"binds at char {i_bind}, reads at char {i_read}"
        if not (i_bind != -1 and (i_read == -1 or i_bind < i_read)) else "")
    chk("settings :" in s or "NOT CONNECTED" in s,
        "and SAYS which source the value came from",
        "a credential tool that will not name its source cannot be trusted "
        "when it says a key is missing")

print("\n== the binder still exists and is still called ==")
src_c = Path("content_engine_connectors.py").read_text(encoding="utf-8")
chk("def set_settings_provider" in src_c, "connectors exposes set_settings_provider")
callers = [f.name for f in Path(".").glob("*.py")
           if "set_settings_provider(" in f.read_text(encoding="utf-8", errors="ignore")
           and f.name != "content_engine_connectors.py"
           and f.name != "verify_diagnostics.py"]
chk(len(callers) >= 2, f"the api and the worker both bind it ({len(callers)})",
    ", ".join(callers))

print("== a credential that is SET but WRONG must be visible without looking ==")
import content_engine_connectors as _C
chk(hasattr(_C, "credential_audit"), "connectors can sweep every stored value")
chk(hasattr(_C, "credential_problem"), "and describe the fault in one sentence")
_probe = _C.credential_problem("IMAGE_API_KEY", "cd /opt && docker compose up")
chk(bool(_probe), "a pasted shell command is caught", _probe)
chk("cd /opt" not in _probe and "docker" not in _probe,
    "and the value itself is never echoed back",
    "a credential report that quotes the credential is a leak")
chk(_C._norm_provider("open ai") == "openai",
    "a provider name with a stray space still routes",
    "one space here sent zero HTTP requests for days")
_ops = Path("content_engine_seo_ops.py").read_text(encoding="utf-8")
chk("credential_audit()" in _ops, "the system context sweeps on every render")
_sb = Path("content_engine_system_boards.py").read_text(encoding="utf-8")
chk("cred_problems" in _sb, "and a CARD shows the result",
    "status() only asks whether a field is non-empty, so a wrong value "
    "reads green everywhere else")

print("== there must be a way to enter a key that leaks nowhere ==")
_w = Path("why_no_image.py").read_text(encoding="utf-8")
chk("getpass" in _w, "--set-key reads the key with no echo",
    "a key typed into a shell lands in ~/.bash_history forever")
chk("--set-key" in _w, "and is reachable from the command line")
chk("credential_problem" in _w, "and refuses to save a malformed value")
chk("print(key" not in _w and "{key}" not in _w,
    "and never prints the key back")
chk("OPENAI_API_KEY" in _C.KEY_ALIASES.get("IMAGE_API_KEY", ()),
    "IMAGE_API_KEY accepts the name everyone actually uses",
    "IMAGE_API_KEY is an invention of this engine; OPENAI_API_KEY is not")

print("== a slow job must not inherit a fast job's timeout ==")
chk(_C._IMAGE_TIMEOUT > _C._HTTP_TIMEOUT,
    f"image generation gets its own budget ({_C._IMAGE_TIMEOUT:.0f}s vs "
    f"{_C._HTTP_TIMEOUT:.0f}s for lookups)",
    "one number for a status check and for drawing a picture is a claim "
    "about duration that is simply false")
chk(_C._IMAGE_TIMEOUT >= 60,
    "and it is long enough for gpt-image-1 (30-90s typical)",
    f"{_C._IMAGE_TIMEOUT:.0f}s would fail on every successful generation")
_src = Path("content_engine_connectors.py").read_text(encoding="utf-8")
_gi = _src[_src.index("def generate_image"):][:3000]
chk("_IMAGE_TIMEOUT" in _gi, "generate_image actually uses it",
    "defining a longer timeout and not passing it is the same as not "
    "having one")

print()
if FAILS:
    print(f"{len(FAILS)} DIAGNOSTIC(S) READING THE WRONG PLACE: {FAILS}")
    sys.exit(1)
print("Every tool that reports on a live credential reads the same source the "
      "engine reads, binds it before the first read, and names the source in "
      "its output.")
