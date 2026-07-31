"""What is ACTUALLY wired on this VPS right now.

Run inside the api container. Reports PRESENCE ONLY — it never prints a
credential value, so the output is safe to paste anywhere:

    docker compose -f deploy/docker-compose.yml exec api python audit_live.py

Answers the three questions the dashboard cannot answer from source alone:
  1. which of the 85 allow-listed keys have a value in Postgres
  2. which wires that makes live, and which loops that closes
  3. what is in the job store, so "the engine has learned nothing yet" can be
     distinguished from "the engine has learned from zeros"
"""
import os
import sys


def main() -> int:
    import content_engine_connectors as C
    import content_engine_api as API

    store = API.get_store()
    get = getattr(store, "get_setting", None)
    if not callable(get):
        print("this store cannot read settings")
        return 1

    def has(k):
        """A key counts as set only if it has a non-blank value. Disconnect
        writes a blank rather than deleting the row, so 'present' is not
        the same as 'set'."""
        try:
            if str(get(k, "") or "").strip():
                return "db"
        except Exception:
            pass
        return "env" if str(os.getenv(k, "") or "").strip() else ""

    keys = list(C.CONNECTOR_ENV_KEYS)
    state = {k: has(k) for k in keys}
    n_db = sum(1 for v in state.values() if v == "db")
    n_env = sum(1 for v in state.values() if v == "env")

    print("=" * 66)
    print("1. CREDENTIALS  (presence only - no value is ever printed)")
    print("=" * 66)
    print(f"   in Postgres (set from the browser) : {n_db}")
    print(f"   in the environment only            : {n_env}")
    print(f"   not set anywhere                   : {len(keys) - n_db - n_env}")
    print(f"   allow-list total                   : {len(keys)}")
    print("\n   NOT SET:")
    missing = [k for k, v in state.items() if not v]
    for i in range(0, len(missing), 3):
        print("     " + "  ".join(f"{k:<30}" for k in missing[i:i + 3]))

    print("\n" + "=" * 66)
    print("2. WIRES  (what the engine reports it can actually do)")
    print("=" * 66)
    try:
        st = C.status()
        for k in sorted(st):
            print(f"   {'LIVE' if st[k] else '    '}  {k}")
        print(f"\n   {sum(1 for v in st.values() if v)} of {len(st)} live")
    except Exception as e:
        print("   could not read connector status:", e)

    try:
        reasons = C.auth_reasons()
        if reasons:
            print("\n   REJECTED - a key is saved but the provider refused it:")
            for k, why in reasons.items():
                print(f"     {k}: {str(why)[:90]}")
    except Exception:
        pass

    print("\n" + "=" * 66)
    print("3. THE JOB STORE  (has anything actually run?)")
    print("=" * 66)
    try:
        jobs = store.list_jobs() if hasattr(store, "list_jobs") else []
        by_status, measured_on_zeros = {}, 0
        for j in jobs:
            by_status[j.get("status", "?")] = by_status.get(j.get("status", "?"), 0) + 1
            a = (j.get("payload", {}) or {}).get("analytics") or {}
            if j.get("status") in ("measured", "tracked", "learned", "optimized") \
                    and not a:
                measured_on_zeros += 1
        print(f"   jobs total: {len(jobs)}")
        for s, n in sorted(by_status.items(), key=lambda t: -t[1]):
            print(f"     {n:>5}  {s}")
        print(f"\n   jobs that reached a LEARNING state with EMPTY analytics: "
              f"{measured_on_zeros}")
        if measured_on_zeros:
            print("   ^ every one of these wrote a playbook entry derived from zeros.")
    except Exception as e:
        print("   could not read jobs:", e)

    print("\n" + "=" * 66)
    print("4. WHAT THE LOOP NEEDS  (the Tier-1 checks, on live data)")
    print("=" * 66)
    checks = [
        ("GA4 reachable (closes the content loop)",
         lambda: bool(C.collect_analytics())),
        ("Google connector available",
         lambda: C.Google().available() if hasattr(C, "Google") else False),
    ]
    for label, fn in checks:
        try:
            ok = fn()
        except Exception as e:
            ok = f"error: {str(e)[:60]}"
        print(f"   {str(ok):<8} {label}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
