"""
content_engine_os_tenancy.py
============================================================================
WORKSPACES, USERS, MEMBERSHIPS AND ROLES.

WHAT THIS IS AND IS NOT
  It IS a real membership layer: workspaces you can create, users, roles
  with grants, and a resolver that turns "the person on this session, and
  the workspace they asked for" into a workspace id the backend trusts.
  Every OS route runs through require() before it touches data.

  It is NOT a second login. The dashboard's existing session is still the
  only way into the building, and whoever holds it is the OWNER. Users and
  members below the owner scope data and record who did what; they do not
  yet hold their own passwords. That line is stated on the Team screen in
  those words rather than implied by a screen that looks like more than it
  is.

THE RULE THAT MATTERS
  A workspace id from the frontend is a REQUEST, never an answer. require()
  checks membership and falls back to the owner's workspace. Guessing an id
  gets you your own data, not somebody else's.
============================================================================
"""

from __future__ import annotations

import hashlib
import hmac
import os as _os

import content_engine_os_core as CORE
from content_engine_os_core import (DEFAULT_WORKSPACE, ROLE_GRANTS, ROLES, _D,
                                    _L, norm_email, now, rid)

#: The cookie the dashboard sets when you switch workspace. Read only as a
#: request; require() decides whether it is honoured.
WS_COOKIE = "ce_ws"

OWNER_KEY = "os_owner_email"


def owner_email(store) -> str:
    """Who holds the session. Falls back to the sending address, because a
    single founder engine should not need a settings screen before the
    Team page can say anything true."""
    try:
        v = store.get_setting(OWNER_KEY, "")
    except Exception:
        v = ""
    if v:
        return norm_email(v)
    try:
        import content_engine_connectors as C
        return norm_email(C._env("EMAIL_FROM", "") or C._env("SMTP_USER", ""))
    except Exception:
        return ""


def ensure_home(store) -> dict:
    """Create the founder's own workspace, once. Idempotent."""
    import content_engine_os_store as ST
    repo = ST.repo_for(store, DEFAULT_WORKSPACE)
    ws = repo.one("workspaces", DEFAULT_WORKSPACE)
    em = owner_email(store)
    if not ws:
        ws = repo.put("workspaces", {
            "id": DEFAULT_WORKSPACE, "name": "Anthropos Automation",
            "plan": "founder", "owner_email": em})
    if em:
        u = repo.put("users", {"id": rid("usr", em), "email": em,
                               "name": "Founder", "last_seen_at": now()})
        if not repo.find("workspace_members", user_email=em):
            repo.put("workspace_members", {
                "id": rid("wm", DEFAULT_WORKSPACE, em), "user_id": u["id"],
                "user_email": em, "role": "owner", "invited_at": now(),
                "accepted_at": now()})
    return ws


def workspaces_for(store, email="") -> list:
    """Every workspace this person belongs to, newest first.

    Membership rows live inside each workspace, so this walks the home
    workspace's list of workspaces and asks each one. Small by construction:
    a founder has one, an agency has a handful."""
    import content_engine_os_store as ST
    em = norm_email(email) or owner_email(store)
    home = ST.repo_for(store, DEFAULT_WORKSPACE)
    out = []
    for w in home.all("workspaces") or []:
        wid = w.get("id")
        r = ST.repo_for(store, wid)
        mine = [m for m in r.find("workspace_members", user_email=em)]
        if mine or w.get("owner_email") == em or wid == DEFAULT_WORKSPACE:
            out.append({"id": wid, "name": w.get("name"),
                        "plan": w.get("plan", ""),
                        "role": (mine[0].get("role") if mine
                                 else "owner" if w.get("owner_email") == em
                                 else "owner"),
                        "members": len(r.all("workspace_members")),
                        "created_at": w.get("created_at", "")})
    return sorted(out, key=lambda w: str(w.get("created_at")), reverse=True)


def create_workspace(store, name, owner="") -> dict:
    """A new workspace, owned by whoever asked. Its id is derived from the
    name so creating it twice returns the same one."""
    import content_engine_os_store as ST
    nm = str(name or "").strip()
    if not nm:
        return {"ok": False, "message": "a workspace needs a name"}
    em = norm_email(owner) or owner_email(store)
    wid = rid("ws", nm.lower())
    home = ST.repo_for(store, DEFAULT_WORKSPACE)
    if home.one("workspaces", wid):
        return {"ok": False, "message": f"{nm!r} already exists"}
    home.put("workspaces", {"id": wid, "name": nm, "plan": "standard",
                            "owner_email": em})
    r = ST.repo_for(store, wid)
    r.put("workspaces", {"id": wid, "name": nm, "plan": "standard",
                         "owner_email": em})
    r.put("workspace_members", {"id": rid("wm", wid, em), "user_email": em,
                                "user_id": rid("usr", em), "role": "owner",
                                "invited_at": now(), "accepted_at": now()})
    CORE.audit(home, em or "founder", "workspace_created", wid, nm)
    return {"ok": True, "id": wid,
            "message": f"{nm!r} created. Switch to it from the Team screen; "
                       f"it starts empty, because data never crosses a "
                       f"workspace boundary."}


def add_member(store, workspace_id, email, role="member") -> dict:
    import content_engine_os_store as ST
    em = norm_email(email)
    if not CORE.valid_email(em):
        return {"ok": False, "message": "that is not a valid email address"}
    if role not in ROLES:
        return {"ok": False,
                "message": f"{role!r} is not a role. They are: "
                           + ", ".join(ROLES)}
    r = ST.repo_for(store, workspace_id)
    r.put("users", {"id": rid("usr", em), "email": em})
    r.put("workspace_members", {"id": rid("wm", workspace_id, em),
                                "user_id": rid("usr", em), "user_email": em,
                                "role": role, "invited_at": now(),
                                "accepted_at": ""})
    CORE.audit(r, owner_email(store) or "founder", "member_added", em, role)
    return {"ok": True,
            "message": f"{em} recorded as {role}. They can see this "
                       f"workspace's data through the API; they do not yet "
                       f"have their own dashboard password."}


def remove_member(store, workspace_id, email) -> dict:
    import content_engine_os_store as ST
    em = norm_email(email)
    r = ST.repo_for(store, workspace_id)
    row = next((m for m in r.find("workspace_members", user_email=em)), None)
    if row and row.get("role") == "owner":
        return {"ok": False,
                "message": "the owner cannot be removed from their own "
                           "workspace"}
    ok = r.delete("workspace_members", rid("wm", workspace_id, em))
    return {"ok": ok, "message": f"{em} removed" if ok else "not a member"}


def members(store, workspace_id) -> list:
    import content_engine_os_store as ST
    r = ST.repo_for(store, workspace_id)
    return [{"email": m.get("user_email"), "role": m.get("role"),
             "grants": ", ".join(ROLE_GRANTS.get(m.get("role"), ())),
             "invited_at": str(m.get("invited_at"))[:10],
             "accepted": bool(m.get("accepted_at"))}
            for m in r.all("workspace_members")]


def role_of(store, workspace_id, email="") -> str:
    import content_engine_os_store as ST
    em = norm_email(email) or owner_email(store)
    r = ST.repo_for(store, workspace_id)
    row = next((m for m in r.find("workspace_members", user_email=em)), None)
    if row:
        return row.get("role") or "viewer"
    ws = r.one("workspaces", workspace_id) or {}
    if em and ws.get("owner_email") == em:
        return "owner"
    # The home workspace grants ownership to whoever holds the session ONLY
    # while nobody has been named yet. Once members exist, membership is the
    # answer; otherwise adding a viewer would still leave every stranger an
    # owner of the founder's own data, which is the opposite of the point.
    if (workspace_id == DEFAULT_WORKSPACE
            and not r.all("workspace_members")
            and (not em or em == owner_email(store))):
        return "owner"
    return ""


def may(store, workspace_id, grant, email="") -> bool:
    return grant in ROLE_GRANTS.get(role_of(store, workspace_id, email), ())


def require(store, requested="", *, grant="read", email="") -> dict:
    """THE GUARD. Turns a requested workspace into one the backend trusts.

    Returns {ok, workspace_id, role, message}. A workspace the caller is
    not a member of is not an error page, it is their own workspace: the
    id is a request, and the answer is what they are entitled to."""
    ensure_home(store)
    em = norm_email(email) or owner_email(store)
    wid = str(requested or "").strip() or DEFAULT_WORKSPACE
    role = role_of(store, wid, em)
    if not role:
        wid, role = DEFAULT_WORKSPACE, role_of(store, DEFAULT_WORKSPACE, em)
    if grant not in ROLE_GRANTS.get(role, ()):
        return {"ok": False, "workspace_id": wid, "role": role,
                "message": f"a {role or 'guest'} may not {grant} here"}
    return {"ok": True, "workspace_id": wid, "role": role, "email": em,
            "message": ""}


# ---------------------------------------------------------------------------
# ITEM 8: A MEMBER CAN HOLD THEIR OWN PASSWORD
# ---------------------------------------------------------------------------
#: PBKDF2 with a per-user salt. Not bcrypt, because that is a wheel this
#: image does not carry and a hashed password is not the place to add a
#: dependency on the day you need it. 200k rounds of SHA-256 is well past
#: what a stolen settings row is worth.
ROUNDS = 200_000
SESSION_KEY = "os_session_secret"


def _session_secret(store) -> bytes:
    try:
        v = store.get_setting(SESSION_KEY, "")
    except Exception:
        v = ""
    if not v:
        v = hashlib.sha256(_os.urandom(32)).hexdigest()
        try:
            store.set_setting(SESSION_KEY, v)
        except Exception:
            pass
    return str(v).encode()


def hash_password(password, salt="") -> str:
    salt = salt or hashlib.sha256(_os.urandom(16)).hexdigest()[:16]
    dk = hashlib.pbkdf2_hmac("sha256", str(password).encode(), salt.encode(),
                             ROUNDS)
    return f"pbkdf2${ROUNDS}${salt}${dk.hex()}"


def verify_password(password, stored) -> bool:
    try:
        kind, rounds, salt, want = str(stored or "").split("$", 3)
        if kind != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", str(password).encode(),
                                 salt.encode(), int(rounds))
        return hmac.compare_digest(dk.hex(), want)
    except Exception:
        return False


def set_password(store, workspace_id, email, password) -> dict:
    """Give a member their own way in.

    The dashboard password still works and still means owner. This adds a
    second door for the people already listed under Team, so an assistant
    can be given read or write without being handed the founder's key."""
    import content_engine_os_store as ST
    em = norm_email(email)
    if len(str(password or "")) < 10:
        return {"ok": False,
                "message": "use at least ten characters; this account can "
                           "see every lead in the workspace"}
    r = ST.repo_for(store, workspace_id)
    if not r.find("workspace_members", user_email=em):
        return {"ok": False,
                "message": f"{em} is not a member of this workspace; add "
                           f"them first"}
    u = r.one("users", rid("usr", em)) or {"id": rid("usr", em), "email": em}
    u["password_hash"] = hash_password(password)
    u["password_set_at"] = now()
    r.put("users", u)
    CORE.audit(r, owner_email(store) or "founder", "password_set", em, "")
    return {"ok": True,
            "message": f"{em} can now sign in with their own password. The "
                       f"dashboard password still works and still means "
                       f"owner."}


def clear_password(store, workspace_id, email) -> dict:
    import content_engine_os_store as ST
    em = norm_email(email)
    r = ST.repo_for(store, workspace_id)
    u = r.one("users", rid("usr", em))
    if not u:
        return {"ok": False, "message": f"{em} has no account"}
    u["password_hash"] = ""
    r.put("users", u)
    return {"ok": True, "message": f"{em} can no longer sign in on their own"}


def check_login(store, email, password) -> dict:
    """(ok, workspace, role). Walks the workspaces this person belongs to.

    A wrong password and an unknown address answer identically: a login
    form that distinguishes them is a way of finding out who has an
    account here."""
    import content_engine_os_store as ST
    em = norm_email(email)
    if not em or not password:
        return {"ok": False, "message": "email and password, please"}
    ensure_home(store)
    home = ST.repo_for(store, DEFAULT_WORKSPACE)
    for w in home.all("workspaces") or []:
        wid = w.get("id")
        r = ST.repo_for(store, wid)
        if not r.find("workspace_members", user_email=em):
            continue
        u = r.one("users", rid("usr", em)) or {}
        if u.get("password_hash") and verify_password(password,
                                                      u["password_hash"]):
            u["last_seen_at"] = now()
            r.put("users", u)
            return {"ok": True, "email": em, "workspace_id": wid,
                    "role": role_of(store, wid, em),
                    "token": user_token(store, em)}
    return {"ok": False, "message": "that email and password do not match"}


def user_token(store, email) -> str:
    return hmac.new(_session_secret(store),
                    f"user|{norm_email(email)}".encode(),
                    hashlib.sha256).hexdigest()


def user_from_cookie(store, cookie) -> str:
    """Which member a session cookie belongs to, or "" if none.

    The cookie is "email|signature", so the address is readable and the
    signature is not forgeable without the server secret."""
    raw = str(cookie or "")
    if "|" not in raw:
        return ""
    em, sig = raw.rsplit("|", 1)
    return em if hmac.compare_digest(user_token(store, em), sig) else ""


def people_with_logins(store, workspace_id) -> dict:
    import content_engine_os_store as ST
    r = ST.repo_for(store, workspace_id)
    return {u.get("email"): bool(u.get("password_hash"))
            for u in r.all("users")}
