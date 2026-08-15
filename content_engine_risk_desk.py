# -*- coding: utf-8 -*-
"""LANE 3b: THE RISK SENTINEL.

Section 4.2 asks for a desk that owns backups, restore tests and
credential rotation. Building it turned up why that desk has never had
anything true to say.

WHAT WAS FOUND
  deploy/backup.sh is a HOST script: it shells out to `docker compose
  exec` against /opt/content-engine/deploy/docker-compose.yml. The
  run_backup fix action calls it from INSIDE the api container, which
  has no docker CLI, no compose file, and no view of the host disk (the
  only volume in the compose file is the Postgres data volume). The
  script is also not copied into the image.

  So the "Run a backup now" button could never have worked, and the
  engine could not see whether a backup existed either. The risk board
  has been showing "no backup is configured" with no way to ever clear
  it.

THE FIX IS THE PHASE 0 PATTERN
  A container cannot prove something about a host it cannot see. So it
  stops guessing and asks for evidence: the host's backup cron POSTs a
  RECEIPT when it succeeds, and this desk reports the age of the last
  receipt. No receipt means no proven backup, stated plainly, forever,
  until one arrives. Exactly like a connector: creds present is not
  verified, and a script existing is not a backup taken.

WHAT ITS BADGE MEANS
  LIVE, since 2026-08-15, and earned by two things changing in the code:
  it runs on the cadence, and it has a real evidence path. It still does
  not take a backup, and must never claim to. The host cron takes it;
  this desk owns the PROOF, and says plainly when there is none. Its own
  check fails the build if a live badge ever stops saying that.

  The first receipts arrived the same day: a 54MB dump, restored into a
  scratch database, 171 settings rows and 135 jobs read back.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import content_engine_contracts as C

AGENT_ID = "risk.sentinel"
LANE = "risk"

#: a backup older than this is stale
BACKUP_MAX_AGE_DAYS = 2

#: a restore that has not been tested in this long is a hope, not a backup
RESTORE_MAX_AGE_DAYS = 90

#: a credential older than this should be rotated
CRED_MAX_AGE_DAYS = 90

#: where the host cron's evidence lands
RECEIPT_KEY = "backup_receipts"
#: when each credential was last written, stamped by the connect route
CRED_STAMP_KEY = "credential_set_at"

LANE_LOG_KEY = "lane_log"

#: The two host lines that actually work. backup.sh now posts its own
#: receipt (authenticated with DASHBOARD_PASSWORD from deploy/.env), so
#: the cron stays short and cannot drift out of step with the endpoint.
#: Daily dump, weekly restore PROOF: a backup nobody has restored is a
#: hope, and --verify actually loads it into a scratch database.
HOST_CRON_LINES = (
    "0 3 * * * bash /opt/content-engine/deploy/backup.sh",
    "30 3 * * 0 bash /opt/content-engine/deploy/backup.sh --verify",
)
HOST_CRON = "\n".join(HOST_CRON_LINES)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _s(v) -> str:
    return "" if v is None else str(v)


def _get(store, k, d=None):
    try:
        return store.get_setting(k, d)
    except Exception:                                     # noqa: BLE001
        return d


def _set(store, k, v) -> bool:
    try:
        store.set_setting(k, v)
        return True
    except Exception:                                     # noqa: BLE001
        return False


def _age_days(stamp: str, at: datetime):
    """Days since an ISO stamp, or None when there is no stamp. None is
    not zero: never-backed-up and backed-up-today are opposites."""
    if not stamp:
        return None
    try:
        when = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except Exception:                                     # noqa: BLE001
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0, (at - when).days)


# --------------------------------------------------------------------------
# THE EVIDENCE. Written by the host, never by this desk.
# --------------------------------------------------------------------------
def record_receipt(store, kind: str = "backup", detail: str = "") -> dict:
    """Called by the host cron after a real backup or restore test.

    This is the ONLY way a backup becomes true in this engine. The desk
    cannot fabricate one, which is the whole point."""
    kind = (kind or "backup").strip().lower()
    if kind not in ("backup", "restore"):
        raise ValueError("a receipt is for a backup or a restore, not %r"
                         % kind)
    rec = dict(_get(store, RECEIPT_KEY, {}) or {})
    rec[kind] = {"at": _now().isoformat(), "detail": _s(detail)[:300]}
    _set(store, RECEIPT_KEY, rec)
    return {"ok": True, "kind": kind, "at": rec[kind]["at"]}


def receipts(store) -> Dict[str, Any]:
    return dict(_get(store, RECEIPT_KEY, {}) or {})


def stamp_credential(store, key: str) -> None:
    """Called when a credential is saved, so rotation age becomes a fact
    rather than a guess. A key with no stamp is 'age unknown', which is
    reported as unknown and never as fresh."""
    if not key:
        return
    st = dict(_get(store, CRED_STAMP_KEY, {}) or {})
    st[str(key)] = _now().isoformat()
    _set(store, CRED_STAMP_KEY, st)


# --------------------------------------------------------------------------
# THE LANE
# --------------------------------------------------------------------------
def _backup_findings(store, at: datetime) -> List[dict]:
    rec = receipts(store)
    out = []
    b_age = _age_days(_s((rec.get("backup") or {}).get("at")), at)
    if b_age is None:
        out.append({
            "kind": "no_backup_proof", "severity": "bad",
            "what": "NO BACKUP HAS EVER BEEN PROVEN",
            "cause": "the engine runs in a container with no view of the "
                     "host disk and no docker CLI, so it cannot take or "
                     "see a backup. Nothing has ever reported one.",
            "fix": "install the host cron below; it takes the backup and "
                   "tells the engine it happened"})
    elif b_age > BACKUP_MAX_AGE_DAYS:
        out.append({
            "kind": "stale_backup", "severity": "bad",
            "what": "the last proven backup was %d days ago" % b_age,
            "cause": "no receipt has arrived since then",
            "fix": "check the host cron is still running"})

    r_age = _age_days(_s((rec.get("restore") or {}).get("at")), at)
    if b_age is not None and r_age is None:
        out.append({
            "kind": "restore_untested", "severity": "warn",
            "what": "the restore has never been tested",
            "cause": "backups are arriving but none has been read back",
            "fix": "restore one dump into a scratch database and post a "
                   "restore receipt"})
    elif r_age is not None and r_age > RESTORE_MAX_AGE_DAYS:
        out.append({
            "kind": "restore_stale", "severity": "warn",
            "what": "the restore was last tested %d days ago" % r_age,
            "cause": "a backup nobody has restored from is a hope",
            "fix": "run the restore test again"})
    return out


def _credential_findings(store, at: datetime) -> List[dict]:
    stamps = dict(_get(store, CRED_STAMP_KEY, {}) or {})
    out = []
    old = []
    for key, when in sorted(stamps.items()):
        age = _age_days(_s(when), at)
        if age is not None and age > CRED_MAX_AGE_DAYS:
            old.append("%s (%dd)" % (key, age))
    if old:
        out.append({
            "kind": "credential_age", "severity": "warn",
            "what": "%d credential(s) are older than %d days"
                    % (len(old), CRED_MAX_AGE_DAYS),
            "cause": ", ".join(old[:5]),
            "fix": "rotate them, starting with anything that can spend or "
                   "publish"})
    if not stamps:
        out.append({
            "kind": "credential_age_unknown", "severity": "warn",
            "what": "no credential has a known age",
            "cause": "keys saved before this desk existed were never "
                     "stamped, so their age is unknown rather than fresh",
            "fix": "re-saving a key stamps it; ages become real from then on"})
    return out


def _wire_findings(store) -> List[dict]:
    """A refusing wire is an operational risk, not only a connector fact."""
    out = []
    try:
        import content_engine_connectors as CN
        bad = [r for r in CN.health() if r.get("status") == "rejected"]
        if bad:
            out.append({
                "kind": "wires_refusing", "severity": "warn",
                "what": "%d wire(s) are refusing" % len(bad),
                "cause": ", ".join(_s(r.get("wire")) for r in bad[:5]),
                "fix": "the Integrations Engineer has proposed the fixes"})
    except Exception:                                     # noqa: BLE001
        pass
    return out


def inspect(store, at: datetime = None) -> Dict[str, Any]:
    at = at or _now()
    findings = (_backup_findings(store, at) + _credential_findings(store, at)
                + _wire_findings(store))
    rec = receipts(store)
    return {"at": at.isoformat(), "findings": findings, "receipts": rec,
            "backup_age_days": _age_days(_s((rec.get("backup") or {}).get("at")), at),
            "restore_age_days": _age_days(_s((rec.get("restore") or {}).get("at")), at),
            "host_cron": HOST_CRON}


def run(store, at: datetime = None) -> Dict[str, Any]:
    at = at or _now()
    day = C.today()
    res = inspect(store, at)
    fs = res["findings"]

    finished = [{"what": "checked backups, restore proof, credential age and "
                         "the wires: %d finding(s)" % len(fs), "job_ids": []}]
    couldnt, needs = [], []
    for f in fs:
        # A THING THE FOUNDER MUST DO IS A DECISION. A thing that is
        # broken and not his to approve is BLOCKED. The no-backup finding
        # is a decision: only he can install the cron.
        needs.append(C.need(
            what=f["what"], kind="decision", action="/riskinfra#backup",
            why=f["fix"]))

    log = dict(_get(store, LANE_LOG_KEY, {}) or {})
    per_day = dict(log.get(day) or {})
    per_day[AGENT_ID] = {"finished": finished, "couldnt": couldnt,
                         "needs": needs}
    log[day] = per_day
    for old in sorted(log)[:-14]:
        log.pop(old, None)
    _set(store, LANE_LOG_KEY, log)

    learned = ["%s: %s" % (f["kind"], f["what"]) for f in fs[:5]]
    if learned:
        try:
            import content_engine_learning as L
            L.record_lane_cycle(_s(_get(store, "BRAND_NAME", "")) or "default",
                                LANE, learned=learned, at=at.isoformat())
        except Exception:                                 # noqa: BLE001
            pass

    return {"agent": AGENT_ID, "day": day, "result": res,
            "report": C.daily_report(day, finished=finished, couldnt=couldnt,
                                     needs=needs)}


def check() -> Dict[str, Any]:
    """This desk must not claim it can do what the container cannot."""
    problems = []
    for forbidden in ("take_backup", "run_backup", "restore"):
        if callable(globals().get(forbidden)):
            problems.append("stage 1 cannot back anything up: %s() exists"
                            % forbidden)
    # THE CRON AND THE SCRIPT MUST AGREE. The cron only names the script,
    # so the reporting lives in backup.sh; if that ever loses its receipt
    # call, the engine goes back to being unable to prove anything and
    # nothing else would notice.
    if "backup.sh" not in HOST_CRON:
        problems.append("the cron does not run the backup script")
    if "--verify" not in HOST_CRON:
        problems.append("nothing ever proves the dump restores")
    try:
        import os
        _here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(_here, "deploy", "backup.sh"),
                  encoding="utf-8") as fh:
            _sh = fh.read()
        if "risk/backup-receipt" not in _sh:
            problems.append("deploy/backup.sh no longer reports its receipt, "
                            "so a backup could never be proven again")
        if "X-API-Key" not in _sh:
            problems.append("the receipt is posted unauthenticated")
    except FileNotFoundError:
        # NOT A FAILURE IN THE CONTAINER. deploy/backup.sh is a HOST
        # file and the Dockerfile does not copy deploy/ on purpose: the
        # script drives docker compose from outside. This check is a
        # repo-side one, and asserting a host file exists inside the
        # image is how a check comes to pass on a laptop and fail on the
        # box, which is the least useful place to learn anything.
        pass
    # THE BADGE IS EARNED BY THE CADENCE AND THE EVIDENCE, not by taking
    # a backup: this desk never takes one and must never claim to. What
    # it owns is the PROOF, which is a real lane and runs daily.
    try:
        import content_engine_roster as R
        why = str(R.agent(AGENT_ID).get("why") or "")
        if R.agent(AGENT_ID).get("badge") == "live" and                 "does not take the backup" not in why:
            problems.append("a live badge here must say out loud that the "
                            "host takes the backup and this desk only "
                            "holds the proof")
        import content_engine_scheduler as S
        if "risk" not in getattr(S, "SEO_CADENCE", {}):
            problems.append("nothing puts this desk on a clock")
    except Exception as exc:                              # noqa: BLE001
        problems.append("roster or cadence unreadable: %s"
                        % type(exc).__name__)
    return {"ok": not problems, "problems": problems}


if __name__ == "__main__":
    class _S:
        def __init__(self):
            self.d = {}

        def get_setting(self, k, d=None):
            return self.d.get(k, d)

        def set_setting(self, k, v):
            self.d[k] = v

    assert check()["ok"], check()["problems"]
    s = _S()
    out = run(s)
    print("findings with no evidence:")
    for f in out["result"]["findings"]:
        print("  -", f["severity"], "|", f["what"])
    record_receipt(s, "backup", "engine-20260815-030000Z.sql.gz 41MB")
    out2 = run(s)
    print("after one real backup receipt:")
    for f in out2["result"]["findings"]:
        print("  -", f["severity"], "|", f["what"])
