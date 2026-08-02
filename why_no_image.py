"""WHY DOES THIS PIECE HAVE NO PICTURE — read the live jobs and say.

Run on the VPS:
    docker compose -f deploy/docker-compose.yml exec api python why_no_image.py

Reads only. Spends nothing. Publishes nothing.

For every content piece in the store it prints the type the strategist ACTUALLY
chose, whether a hero image is attached, and — when there is none — the reason
the engine recorded. That last column is the one that did not exist: a piece
without a picture used to look exactly like a piece whose image failed, and the
previews showed the same silent blank for both.
"""
import sys


def main() -> int:
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
