# -*- coding: utf-8 -*-
"""PHASE 0 GATE: the connector health is honest, and it survives a restart.

Definition of done (Section 6, P0):
  - /connectors/health truthful after restart
  - a rejected wire shows rejected WITH its reason
  - zero green-without-timestamp

Arithmetic and behaviour only. No LLM, no network, no paid probe.
"""
from __future__ import annotations

import subprocess
import sys

import content_engine_connectors as CN
import content_engine_contracts as C

PASS, FAIL = [], []


def t(label, ok, detail=""):
    (PASS if ok else FAIL).append(label)
    print(("  OK   " if ok else "  FAIL ") + label
          + (("   " + str(detail)) if detail and not ok else ""))


print("=" * 74)
print("PHASE 0 - HONEST CONNECTOR HEALTH")
print("=" * 74)

# ---- the contract itself refuses false green -----------------------------
print("\nA. THE CONTRACT REFUSES A LIE")
try:
    C.connector_health("x", status="verified")
    t("green without a timestamp is refused", False, "it was allowed")
except ValueError:
    t("green without a timestamp is refused", True)
t("and green WITH a timestamp is allowed",
  C.connector_health("x", status="verified",
                     last_verified="2026-08-15T09:00:00Z")["status"]
  == "verified")

# ---- the four states, and nothing else -----------------------------------
print("\nB. FOUR STATES, NO FIFTH")
rows = CN.health()
t("health() returns rows", bool(rows), str(len(rows)))
bad = sorted({r["status"] for r in rows} - set(C.CONNECTOR_STATES))
t("every row is one of verified|present|rejected|empty", not bad, str(bad))
green_no_stamp = [r["wire"] for r in rows
                  if r["status"] == "verified" and not r["last_verified"]]
t("ZERO GREEN WITHOUT A TIMESTAMP", not green_no_stamp, str(green_no_stamp))
present = [r for r in rows if r["status"] == "present"]
t("creds-present reads amber 'present', never verified",
  all(r["last_verified"] is None for r in present))
t("and it says why it is not green",
  all("no call has verified it" in (r["reason"] or "") for r in present))

# ---- a rejection is recorded with the provider's own reason --------------
print("\nC. A REFUSAL IS RECORDED, WITH ITS REASON")
_mem = {}
CN.set_settings_writer(lambda k, v: _mem.__setitem__(k, v))
CN.set_settings_reader(lambda k, d=None: _mem.get(k, d))
CN.note_auth("probe_wire", False, 401,
             "the provider refused: invalid_client")
saved = dict(_mem.get("connector_health") or {})
t("the verdict was written to the store", "probe_wire" in saved)
t("it is stored as rejected",
  saved.get("probe_wire", {}).get("status") == "rejected")
t("with the provider's own words",
  "invalid_client" in (saved.get("probe_wire", {}).get("reason") or ""))
t("and stamped when it was checked",
  bool(saved.get("probe_wire", {}).get("checked_at")))

# ---- THE RESTART TEST: a fresh process must still know ------------------
print("\nD. IT SURVIVES A RESTART (the whole point)")
code = (
    "import json,sys\n"
    "import content_engine_connectors as CN\n"
    "store = json.loads(sys.argv[1])\n"
    "CN.set_settings_reader(lambda k, d=None: store.get(k, d))\n"
    "CN.set_settings_writer(lambda k, v: None)\n"
    "rows = {r['wire']: r for r in CN.health()}\n"
    "r = rows.get('probe_wire') or {}\n"
    "print(r.get('status'), '|', (r.get('reason') or '')[:40])\n"
)
import json
res = subprocess.run([sys.executable, "-c", code, json.dumps(_mem)],
                     capture_output=True, text=True, timeout=180)
out = (res.stdout or "").strip()
t("a NEW process still reports the rejection",
  out.startswith("rejected"), out or (res.stderr or "")[-200:])
t("and still carries the reason", "invalid_client" in out, out)

# ---- a verified call turns it green, with a stamp ------------------------
print("\nE. A REAL ACCEPTED CALL IS WHAT TURNS IT GREEN")
CN.note_auth("probe_wire", True, 0, "")
saved2 = dict(_mem.get("connector_health") or {})
t("an accepted call records verified",
  saved2.get("probe_wire", {}).get("status") == "verified")
t("and writes the timestamp that green requires",
  bool(saved2.get("probe_wire", {}).get("last_verified")))

print("\n" + "=" * 74)
print(f"{len(PASS)} passed, {len(FAIL)} failed")
for f in FAIL:
    print("  FAILED: " + f)
print("=" * 74)
sys.exit(1 if FAIL else 0)
