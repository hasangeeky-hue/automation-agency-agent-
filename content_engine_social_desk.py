# -*- coding: utf-8 -*-
"""LANE 3d: THE SOCIAL DISTRIBUTOR.

Section 4.4: the content lane already WRITES social posts. Nothing puts
them out. This desk owns that step.

WHAT IT FOUND ON DAY ONE
  All five social wires are EMPTY. Not rejected, not stale: no
  credential has ever been saved for LinkedIn, X, Facebook, Instagram or
  TikTok, and every poster reports available() == False. So the queue of
  written posts has nowhere to go, and the honest output of this desk
  today is the queue plus the exact credential each channel wants.

THE THREE CONDITIONS, AND WHY THEY ARE SEPARATE
  A post goes out only when all three hold:
    1. the piece is APPROVED by a human (the permanent PUBLISH gate)
    2. the channel is VERIFIED, not merely configured
    3. that piece has not already been posted to that channel
  They are checked separately and reported separately, because "nothing
  posted today" has three completely different meanings and a founder
  needs to know which one he is looking at.

  Condition 2 is deliberately VERIFIED and not available(). A saved
  credential is not a working one, and posting to a live audience is not
  the place to find that out.

IDEMPOTENCE IS THE WHOLE SAFETY STORY
  Posting twice is not a retry, it is a second post to real people. The
  desk writes payload.published_refs[channel] the moment a post
  succeeds, and refuses any piece that already carries a ref for that
  channel. The same list read twice cannot post twice.
"""
from __future__ import annotations

from typing import Any, Dict, List

import content_engine_contracts as C

AGENT_ID = "sga.distributor"
LANE = "sga"

#: channel -> (poster class name on connectors, the wire it needs)
CHANNELS = {
    "linkedin": ("LinkedInPoster", "social_linkedin"),
    "twitter": ("TwitterPoster", "social_twitter"),
    "facebook": ("MetaPoster", "social_facebook"),
    "instagram": ("InstagramPoster", "social_instagram"),
    "tiktok": ("TikTokPoster", "social_tiktok"),
}

#: what each channel wants, so an empty board is actionable
CHANNEL_NEEDS = {
    "linkedin": "a LinkedIn access token with w_member_social",
    "twitter": "X API keys with write scope",
    "facebook": "a Meta page token with pages_manage_posts",
    "instagram": "a Meta token plus the Instagram business account id",
    "tiktok": "TikTok content posting credentials",
}

LANE_LOG_KEY = "lane_log"
#: the daily ceiling, so one bad plan cannot flood a feed
MAX_PER_RUN = 4


def _s(v) -> str:
    return "" if v is None else str(v)


def _d(v) -> dict:
    return dict(v) if isinstance(v, dict) else {}


def _l(v) -> list:
    return list(v) if isinstance(v, (list, tuple)) else []


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


# --------------------------------------------------------------------------
# RUNG 1 - CONTEXT
# --------------------------------------------------------------------------
def channel_state(store=None) -> Dict[str, Dict[str, Any]]:
    """Per channel: is it VERIFIED, and can its poster even load.

    Verified comes from the connector health store, which only says yes
    after a real accepted call. available() is reported alongside so the
    difference between 'a key is saved' and 'the provider accepted us'
    stays visible rather than being collapsed into one green dot."""
    health = {}
    try:
        import content_engine_connectors as CN
        health = {r["wire"]: r for r in CN.health()}
    except Exception:                                     # noqa: BLE001
        CN = None
    out = {}
    for ch, (cls_name, wire) in CHANNELS.items():
        row = _d(health.get(wire))
        avail = False
        try:
            import content_engine_connectors as _CN
            cls = getattr(_CN, cls_name, None)
            avail = bool(cls().available()) if cls else False
        except Exception:                                 # noqa: BLE001
            avail = False
        out[ch] = {"channel": ch, "wire": wire,
                   "status": _s(row.get("status")) or "empty",
                   "verified": _s(row.get("status")) == "verified",
                   "available": avail,
                   "reason": _s(row.get("reason")),
                   "needs": CHANNEL_NEEDS.get(ch, "")}
    return out


def _social_pieces(jobs) -> List[dict]:
    """Written social posts, with the channels each still owes."""
    out = []
    for j in _l(jobs):
        d = _d(j)
        payload = _d(d.get("payload"))
        text = _s(payload.get("social_text") or payload.get("post_text"))
        chans = [_s(c).lower() for c in _l(payload.get("channels"))
                 if _s(c).lower() in CHANNELS]
        if not chans:
            continue
        refs = _d(payload.get("published_refs"))
        pending = [c for c in chans if not _s(refs.get(c))]
        out.append({"job_id": _s(d.get("job_id")),
                    "approved": d.get("approved") is True,
                    "status": _s(d.get("status")),
                    "text": text, "channels": chans, "pending": pending,
                    "posted": [c for c in chans if _s(refs.get(c))]})
    return out


def queue(store, jobs=None) -> Dict[str, Any]:
    """What is written and still owed, split by WHY it has not gone out."""
    if jobs is None:
        try:
            jobs = store.list_jobs(status=None)
        except Exception:                                 # noqa: BLE001
            jobs = []
    pieces = _social_pieces(jobs)
    chans = channel_state(store)
    ready, waiting_approval, blocked = [], [], []
    for p in pieces:
        if not p["pending"]:
            continue
        if not p["approved"]:
            waiting_approval.append(p)
            continue
        can = [c for c in p["pending"] if chans.get(c, {}).get("verified")]
        if can:
            ready.append(dict(p, can_post=can))
        else:
            blocked.append(dict(p, why=", ".join(
                "%s is %s" % (c, chans.get(c, {}).get("status", "empty"))
                for c in p["pending"])))
    return {"pieces": len(pieces), "ready": ready,
            "waiting_approval": waiting_approval, "blocked": blocked,
            "channels": chans}


# --------------------------------------------------------------------------
# RUNG 3 + 6 - THE LANE AND ITS GUARDRAILS
# --------------------------------------------------------------------------
def post_one(store, piece: Dict[str, Any], channel: str) -> Dict[str, Any]:
    """Put ONE approved piece on ONE verified channel.

    Every refusal below is a separate named reason. A single boolean
    would make "we did not post" unreadable, and this is the one lane
    where the failure mode is visible to strangers."""
    piece = _d(piece)
    channel = _s(channel).lower()
    if channel not in CHANNELS:
        return {"ok": False, "why": "%r is not a channel this engine knows"
                                    % channel}
    if piece.get("approved") is not True:
        return {"ok": False, "why": "the piece is not approved; publishing "
                                    "is a permanent gate"}
    if channel in _l(piece.get("posted")):
        return {"ok": False, "why": "already posted to %s; posting twice is "
                                    "not a retry, it is a second post"
                                    % channel}
    st = channel_state(store).get(channel) or {}
    if not st.get("verified"):
        return {"ok": False, "why": "%s is %s, not verified. A saved "
                                    "credential is not a working one."
                                    % (channel, st.get("status", "empty"))}
    text = _s(piece.get("text")).strip()
    if not text:
        return {"ok": False, "why": "there is no text to post"}
    try:
        import content_engine_connectors as CN
        cls = getattr(CN, CHANNELS[channel][0], None)
        if cls is None:
            return {"ok": False, "why": "no poster exists for %s" % channel}
        ref = cls().post(text)
    except Exception as exc:                              # noqa: BLE001
        return {"ok": False, "why": "%s refused: %s"
                                    % (channel, type(exc).__name__)}
    if not ref:
        return {"ok": False, "why": "%s accepted nothing back, so there is "
                                    "no proof it posted" % channel}
    return {"ok": True, "channel": channel, "ref": _s(ref)}


def _record(store, job_id: str, channel: str, ref: str) -> None:
    """Write the ref onto the job so the same piece can never post twice."""
    try:
        job = store.get(job_id)
        if not job:
            return
        payload = _d(job.get("payload"))
        refs = _d(payload.get("published_refs"))
        refs[channel] = ref
        payload["published_refs"] = refs
        job["payload"] = payload
        store.save(job)
    except Exception:                                     # noqa: BLE001
        pass


def run(store, jobs=None) -> Dict[str, Any]:
    """One working day for the Social Distributor."""
    day = C.today()
    q = queue(store, jobs)
    posted, skipped = [], []
    budget = MAX_PER_RUN
    for p in q["ready"]:
        for ch in p.get("can_post", []):
            if budget <= 0:
                skipped.append({"job_id": p["job_id"], "channel": ch,
                                "why": "the daily ceiling of %d was reached"
                                       % MAX_PER_RUN})
                continue
            r = post_one(store, p, ch)
            if r.get("ok"):
                _record(store, p["job_id"], ch, r["ref"])
                posted.append({"job_id": p["job_id"], "channel": ch,
                               "ref": r["ref"]})
                budget -= 1
            else:
                skipped.append({"job_id": p["job_id"], "channel": ch,
                                "why": r.get("why", "no reason given")})

    finished, couldnt, needs = [], [], []
    if posted:
        finished.append({"what": "posted %d" % len(posted),
                         "job_ids": [x["job_id"] for x in posted]})
    live = [c for c, s in q["channels"].items() if s["verified"]]
    if not live:
        # THE HEADLINE FINDING while nothing is wired. Blocked, not a
        # decision: no approval of his would make a post go out.
        needs.append(C.need(
            what="no social channel is verified, so %d written post(s) "
                 "cannot go anywhere" % len(q["blocked"]),
            kind="blocked", action="/connect#social_linkedin",
            why="; ".join("%s needs %s" % (c, s["needs"])
                          for c, s in sorted(q["channels"].items()))[:400]))
    for p in q["waiting_approval"][:5]:
        needs.append(C.need(
            what="approve the social post on " + p["job_id"], kind="decision",
            action="/jobs/%s/approve" % p["job_id"],
            why="it is written and waiting; nothing posts until you say so"))
    for sk in skipped[:5]:
        couldnt.append({"what": "%s on %s" % (sk["job_id"], sk["channel"]),
                        "cause": sk["why"]})
    if not finished and not couldnt and not needs:
        finished.append({"what": "nothing was owed to any channel today",
                         "job_ids": []})

    log = dict(_get(store, LANE_LOG_KEY, {}) or {})
    per_day = dict(log.get(day) or {})
    per_day[AGENT_ID] = {"finished": finished, "couldnt": couldnt,
                         "needs": needs}
    log[day] = per_day
    for old in sorted(log)[:-14]:
        log.pop(old, None)
    _set(store, LANE_LOG_KEY, log)

    learned = ["posted to %s" % x["channel"] for x in posted[:3]]
    learned += ["could not post: %s" % sk["why"] for sk in skipped[:2]]
    if learned:
        try:
            import content_engine_learning as L
            L.record_lane_cycle(_s(_get(store, "BRAND_NAME", "")) or "default",
                                LANE, learned=learned)
        except Exception:                                 # noqa: BLE001
            pass

    return {"agent": AGENT_ID, "day": day, "posted": posted,
            "skipped": skipped, "queue": q,
            "report": C.daily_report(day, finished=finished, couldnt=couldnt,
                                     needs=needs)}


def check() -> Dict[str, Any]:
    """The two rules this lane cannot be allowed to lose."""
    problems = []
    import inspect as _i
    src = _i.getsource(post_one)
    if "approved" not in src or "permanent gate" not in src:
        problems.append("post_one no longer refuses an unapproved piece")
    if "verified" not in src:
        problems.append("post_one no longer requires a VERIFIED channel")
    if "already posted" not in src:
        problems.append("post_one no longer refuses a second post")
    if set(CHANNELS) != set(CHANNEL_NEEDS):
        problems.append("a channel has no stated credential need: %s"
                        % sorted(set(CHANNELS) ^ set(CHANNEL_NEEDS)))
    try:
        import content_engine_connectors as CN
        for ch, (cls_name, wire) in CHANNELS.items():
            if getattr(CN, cls_name, None) is None:
                problems.append("%s names a poster that does not exist: %s"
                                % (ch, cls_name))
            if wire not in {r["wire"] for r in CN.health()}:
                problems.append("%s names a wire that does not exist: %s"
                                % (ch, wire))
    except Exception as exc:                              # noqa: BLE001
        problems.append("connectors unreadable: %s" % type(exc).__name__)
    return {"ok": not problems, "problems": problems}


if __name__ == "__main__":
    class _S:
        def __init__(self):
            self.d, self.j = {}, {}

        def get_setting(self, k, d=None):
            return self.d.get(k, d)

        def set_setting(self, k, v):
            self.d[k] = v

        def list_jobs(self, status=None):
            return list(self.j.values())

        def get(self, jid):
            return self.j.get(jid)

        def save(self, job):
            self.j[job["job_id"]] = job

    assert check()["ok"], check()["problems"]
    s = _S()
    s.save({"job_id": "p1", "approved": True, "status": "approved",
            "payload": {"social_text": "hello", "channels": ["linkedin"]}})
    s.save({"job_id": "p2", "approved": False, "status": "AWAITING_APPROVAL",
            "payload": {"social_text": "draft", "channels": ["linkedin"]}})
    out = run(s)
    print("posted:", out["posted"])
    for n in out["report"]["needs"]:
        print(" ", n["kind"], "|", n["what"][:70])
