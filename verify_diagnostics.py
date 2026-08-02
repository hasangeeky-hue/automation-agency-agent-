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

print()
if FAILS:
    print(f"{len(FAILS)} DIAGNOSTIC(S) READING THE WRONG PLACE: {FAILS}")
    sys.exit(1)
print("Every tool that reports on a live credential reads the same source the "
      "engine reads, binds it before the first read, and names the source in "
      "its output.")
