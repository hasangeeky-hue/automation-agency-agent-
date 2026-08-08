"""
content_engine_os_data.py
============================================================================
EXPORT, IMPORT, AND THE GOOGLE DRIVE MIRROR.

ONE DATASET REGISTRY
  DATASETS below declares every table this OS will hand you: its columns,
  its label, and the function that produces its rows. The CSV writer, the
  Excel writer, the JSON writer, the download menu and the Drive mirror all
  read that one declaration. Adding a dataset is one entry, not five edits
  in five places that will eventually disagree.

IMPORT IS A PREVIEW FIRST, ALWAYS
  A lead list arrives as somebody else's spreadsheet with somebody else's
  column names. preview() reads it, guesses the mapping from a table of
  aliases, and reports what WOULD happen: how many new people, how many
  updates, how many rows have no usable address, how many are already
  suppressed. Nothing is written until you press the second button. An
  importer that writes on upload is how four hundred duplicate profiles
  appear and nobody can say which run made them.

  The commit goes through the audited agent service layer, so a list you
  uploaded by hand is recorded exactly like one an agent wrote.

THE DRIVE MIRROR IS A MIRROR
  Postgres stays the source of truth. push_to_drive() writes a workbook and
  a JSON file into the folder the service account already has, and records
  what it wrote. It never reads back, so Drive cannot become a second
  truth that disagrees with the engine.
============================================================================
"""

from __future__ import annotations

import logging

import content_engine_os_analytics as AN
import content_engine_os_audience as AUD
import content_engine_os_core as CORE
import content_engine_os_sheets as XL
from content_engine_os_core import _D, _L, norm_email, now
import json as _json

log = logging.getLogger("content_engine.os.data")

MAX_UPLOAD = 8 * 1024 * 1024          # 8 MB, stated on the screen


def _people(repo):
    return AN.profile_rows(repo, limit=100000)


def _messages(repo):
    camps = {c.get("id"): c for c in repo.all("campaigns")}
    ev = {}
    for e_ in repo.all("email_events"):
        ev.setdefault(e_.get("message_id"), []).append(e_.get("event_type"))
    profs = {p.get("id"): p for p in repo.all("profiles")}
    out = []
    for m in repo.all("campaign_messages"):
        p = profs.get(m.get("profile_id")) or {}
        k = ev.get(m.get("id"), [])
        out.append({
            "email": m.get("email"),
            "name": " ".join(x for x in [p.get("first_name"),
                                         p.get("last_name")] if x),
            "company": p.get("company", ""),
            "campaign": _D(camps.get(m.get("campaign_id"))).get("name", ""),
            "touch": m.get("touch"), "variant": m.get("variant", ""),
            "subject": m.get("subject", ""), "state": m.get("state", ""),
            "sent_at": m.get("sent_at", ""),
            "edited_by_you": "yes" if m.get("edited") else "no",
            "opened": k.count("EMAIL_OPENED"),
            "clicked": k.count("EMAIL_CLICKED"),
            "bounced": "yes" if "EMAIL_BOUNCED" in k else "no"})
    return sorted(out, key=lambda r: str(r.get("sent_at")), reverse=True)


def _events(repo):
    profs = {p.get("id"): p.get("email") for p in repo.all("profiles")}
    camps = {c.get("id"): c.get("name") for c in repo.all("campaigns")}
    return [{"at": e_.get("timestamp"), "event": e_.get("event_type"),
             "email": profs.get(e_.get("profile_id"), ""),
             "campaign": camps.get(e_.get("campaign_id"), ""),
             "url": _D(e_.get("metadata")).get("url", ""),
             "message_id": e_.get("message_id", "")}
            for e_ in sorted(repo.all("email_events"),
                             key=lambda x: str(x.get("timestamp")),
                             reverse=True)]


def _consent(repo):
    supp = {s.get("email"): s for s in repo.all("suppressions")}
    out = []
    for c in repo.all("consents"):
        em = c.get("email")
        s = supp.get(em) or {}
        out.append({"email": em, "status": c.get("status"),
                    "consent_source": c.get("consent_source", ""),
                    "consent_method": c.get("consent_method", ""),
                    "consent_at": c.get("consent_at", ""),
                    "unsubscribed_at": c.get("unsubscribed_at", ""),
                    "evidence": c.get("evidence", ""),
                    "suppressed_reason": s.get("reason", ""),
                    "suppressed_at": s.get("suppressed_at", "")})
    for em, s in supp.items():
        if not any(r["email"] == em for r in out):
            out.append({"email": em, "status": "SUPPRESSED",
                        "consent_source": "", "consent_method": "",
                        "consent_at": "", "unsubscribed_at": "",
                        "evidence": "", "suppressed_reason": s.get("reason"),
                        "suppressed_at": s.get("suppressed_at")})
    return out


#: name -> (label, columns, rows_fn). The one declaration.
DATASETS = {
    "profiles": ("People", ["email", "first_name", "last_name", "company",
                            "job_title", "country", "city", "website",
                            "phone", "source", "consent", "lead_stage",
                            "lead_score", "priority", "pain_point", "offer",
                            "business", "why", "collected_at",
                            "emails_sent", "opens", "clicks",
                            "is_scanner", "resting", "rest_until",
                            "last_activity_at", "created_at"], _people),
    "leads": ("Leads", ["primary_profile_id", "stage", "score",
                        "qualification_status", "source", "source_url",
                        "assigned_agent", "created_at", "updated_at"],
              lambda r: r.all("leads")),
    "companies": ("Companies", ["name", "website", "country", "created_at"],
                  lambda r: r.all("companies")),
    "campaigns": ("Campaigns", ["name", "subject", "state", "recipients",
                                "messages", "sent", "opens", "clicks",
                                "edited", "variants", "created_at"],
                  lambda r: AN.campaign_rows(r)),
    "messages": ("Emails sent", ["email", "name", "company", "campaign",
                                 "touch", "variant", "subject", "state",
                                 "sent_at", "edited_by_you", "opened",
                                 "clicked", "bounced"], _messages),
    "events": ("Events", ["at", "event", "email", "campaign", "url",
                          "message_id"], _events),
    "consent": ("Consent and suppression",
                ["email", "status", "consent_source", "consent_method",
                 "consent_at", "unsubscribed_at", "evidence",
                 "suppressed_reason", "suppressed_at"], _consent),
    "queue": ("Queue", ["email", "campaign", "status", "approved", "attempts",
                        "provider", "scheduled_at", "sent_at", "error"],
              lambda r: __import__("content_engine_os_send").queue_rows(r)),
    "hygiene": ("List hygiene", ["email", "company", "sent", "opens",
                                 "clicks", "code", "why", "action",
                                 "resting", "rest_until"],
                lambda r: AN.hygiene(r)["rows"]),
    "daily": ("By day", ["day", "sent", "opens", "clicks", "unique_opens",
                         "unique_clicks", "human_opens", "human_clicks",
                         "unsubscribes", "complaints"],
              lambda r: AN.by_day(r, days=400)),
}


def _filtered(repo, name, rows, cols, flt) -> list:
    """ITEM 9. Narrow an export to a segment, a list or one campaign.

    Exports used to be whole tables only, which is useless the moment you
    want to hand somebody the two hundred people in one segment rather
    than everyone you have ever met."""
    flt = _D(flt)
    if not flt:
        return rows
    i_email = cols.index("email") if "email" in cols else -1
    i_camp = cols.index("campaign") if "campaign" in cols else -1
    keep = None
    if flt.get("segment"):
        seg = repo.one("segments", flt["segment"]) or {}
        keep = {p.get("email") for p in AUD.members(repo, seg)}
    elif flt.get("list"):
        ids = {m.get("profile_id")
               for m in repo.find("list_members", list_id=flt["list"])}
        keep = {p.get("email") for p in repo.all("profiles")
                if p.get("id") in ids}
    elif flt.get("campaign"):
        c = repo.one("campaigns", flt["campaign"]) or {}
        if i_camp >= 0:
            return [r for r in rows if r[i_camp] == c.get("name")]
        keep = {m.get("email")
                for m in repo.find("campaign_messages",
                                   campaign_id=flt["campaign"])}
    elif flt.get("code"):
        keep = {r.get("email") for r in _L(AN.hygiene(repo).get(flt["code"]))}
    if keep is None or i_email < 0:
        return rows
    return [r for r in rows if r[i_email] in keep]


def rows_for(repo, name, flt=None) -> tuple:
    """(header, rows). Missing columns come back empty rather than raising:
    a dataset that half-exists must still download."""
    label, cols, fn = DATASETS[name]
    try:
        data = _L(fn(repo))
    except Exception as ex:
        log.warning("dataset %s failed: %s", name, ex)
        data = []
    rows = [[_D(r).get(c, "") for c in cols] for r in data]
    return cols, _filtered(repo, name, rows, cols, flt)


def as_bytes(repo, name, fmt, flt=None) -> tuple:
    """(filename, mime, bytes) for one dataset, optionally narrowed."""
    label, cols, _fn = DATASETS[name]
    cols, rows = rows_for(repo, name, flt)
    stamp = now()[:10]
    if fmt == "csv":
        return (f"{name}-{stamp}.csv", "text/csv; charset=utf-8",
                XL.write_csv([cols] + rows))
    if fmt == "json":
        return (f"{name}-{stamp}.json", "application/json",
                XL.write_json([dict(zip(cols, r)) for r in rows]))
    return (f"{name}-{stamp}.xlsx",
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet",
            XL.write_xlsx([(label, [cols] + rows)]))


def workbook(repo) -> tuple:
    """Everything, one workbook, one tab per dataset. This is the file the
    founder actually wants: open it and every table is there."""
    sheets = []
    for name, (label, _c, _f) in DATASETS.items():
        cols, rows = rows_for(repo, name)
        sheets.append((label, [cols] + rows))
    return (f"engagement-os-{now()[:10]}.xlsx",
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet", XL.write_xlsx(sheets))


def everything_json(repo) -> tuple:
    out = {"exported_at": now(), "workspace": repo.ws}
    for name in DATASETS:
        cols, rows = rows_for(repo, name)
        out[name] = [dict(zip(cols, r)) for r in rows]
    return (f"engagement-os-{now()[:10]}.json", "application/json",
            XL.write_json(out))


def catalogue(repo) -> list:
    """What the Export screen draws: every dataset and how big it is."""
    out = []
    for name, (label, cols, _fn) in DATASETS.items():
        _c, rows = rows_for(repo, name)
        out.append({"name": name, "label": label, "columns": len(cols),
                    "rows": len(rows)})
    return out


# ---------------------------------------------------------------------------
# GOOGLE DRIVE
# ---------------------------------------------------------------------------
def drive_state() -> dict:
    try:
        import content_engine_connectors as C
        d = C.GoogleDrive()
        return {"ready": bool(d.available()), "folder": d.folder_id or "",
                "why": ("writing into the folder the service account was "
                        "given" if d.available() else
                        "set GOOGLE_SERVICE_ACCOUNT_JSON and GDRIVE_FOLDER_ID "
                        "on the System Map; both already exist for GSC and "
                        "GA4, so this turns on without a rebuild")}
    except Exception as ex:
        return {"ready": False, "folder": "",
                "why": f"the Drive connector is unavailable: {ex}"}


def push_to_drive(store, repo) -> dict:
    """Mirror the workbook and the JSON into Drive.

    A MIRROR, NEVER A SOURCE. Nothing is ever read back from Drive. If it
    were, Drive and Postgres would eventually disagree and there would be
    no way to say which was right."""
    st = drive_state()
    if not st["ready"]:
        return {"ok": False, "message": st["why"]}
    import content_engine_connectors as C
    drive = C.GoogleDrive()
    written, failed = [], []
    name, _mime, data = workbook(repo)
    ref = save_file(drive, name, data,
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet")
    (written if ref else failed).append(name)
    jname, _m, jdata = everything_json(repo)
    jref = save_file(drive, jname, jdata, "application/json")
    (written if jref else failed).append(jname)
    stamp = {"at": now(), "files": written, "failed": failed,
             "workbook": ref, "json": jref}
    try:
        store.set_setting("os_drive_last", stamp)
    except Exception:
        pass
    return {"ok": bool(written), "written": written, "failed": failed,
            "link": ref or jref,
            "message": (f"{len(written)} file(s) written to Drive"
                        + (f", {len(failed)} refused" if failed else "")
                        + ". Drive is a mirror: nothing is ever read back "
                          "from it.")}


def save_file(drive, name, data, mime) -> str:
    """Upload arbitrary bytes. The connector only knew how to write JSON,
    and a spreadsheet is not JSON."""
    try:
        import content_engine_connectors as C
        token = C._google_token([C._GDRIVE_SCOPE])
        rq = C._requests()
        if not token or not rq:
            return ""
        import json as _json
        b = "aa_os_boundary"
        meta = _json.dumps({"name": name, "parents": [drive.folder_id],
                            "mimeType": mime})
        head = (f"--{b}\r\nContent-Type: application/json; charset=UTF-8"
                f"\r\n\r\n{meta}\r\n--{b}\r\nContent-Type: {mime}\r\n"
                f"Content-Transfer-Encoding: binary\r\n\r\n").encode("utf-8")
        tail = f"\r\n--{b}--".encode("utf-8")
        r = rq.post("https://www.googleapis.com/upload/drive/v3/files"
                    "?uploadType=multipart&fields=id,webViewLink",
                    headers={"Authorization": f"Bearer {token}",
                             "Content-Type":
                                 f"multipart/related; boundary={b}"},
                    data=head + data + tail, timeout=90)
        r.raise_for_status()
        j = r.json()
        return j.get("webViewLink") or ("drive:" + str(j.get("id", "")))
    except Exception as ex:
        log.warning("Drive upload of %s failed: %s", name, ex)
        return ""


def drive_last(store) -> dict:
    try:
        return _D(store.get_setting("os_drive_last", {}))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# IMPORT
# ---------------------------------------------------------------------------
#: Header aliases. Real lead lists arrive from Apollo, Sales Navigator,
#: Google Maps exports and clients' own spreadsheets, and none of them
#: agree on what a column is called.
ALIASES = {
    "email": ("email", "e-mail", "mail", "email address", "work email",
              "business email", "emailaddress", "contact email", "e mail"),
    "first_name": ("first name", "firstname", "first", "given name",
                   "vorname"),
    "last_name": ("last name", "lastname", "surname", "family name",
                  "nachname"),
    "name": ("name", "full name", "fullname", "contact", "contact name",
             "person"),
    "company": ("company", "company name", "organisation", "organization",
                "account", "employer", "firma", "business", "business name"),
    "job_title": ("title", "job title", "role", "position", "jobtitle"),
    "website": ("website", "url", "domain", "site", "web", "company website"),
    "phone": ("phone", "telephone", "mobile", "phone number", "tel"),
    "country": ("country", "land", "location country"),
    "city": ("city", "town", "location", "stadt"),
    "linkedin_url": ("linkedin", "linkedin url", "linkedin profile"),
    "industry": ("industry", "sector", "vertical", "branche"),
    "company_size": ("company size", "employees", "size", "headcount"),
    "lead_score": ("score", "lead score", "rating"),
    "source": ("source", "lead source", "origin"),
}

#: Anything mapped here becomes a custom property rather than being lost.
CUSTOM = "properties"


def guess_mapping(header) -> dict:
    """{column index: field}. Unmatched columns are kept as custom
    properties rather than dropped: a column somebody bothered to include
    is usually a column that matters to them."""
    out = {}
    taken = set()
    for i, h in enumerate(header):
        key = str(h or "").strip().lower().replace("_", " ")
        if not key:
            continue
        hit = ""
        for field, names in ALIASES.items():
            if field in taken:
                continue
            if key in names:
                hit = field
                break
        if not hit:
            for field, names in ALIASES.items():
                if field in taken:
                    continue
                if any(n in key or key in n for n in names):
                    hit = field
                    break
        if hit:
            out[i] = hit
            taken.add(hit)
        else:
            out[i] = f"{CUSTOM}.{str(h).strip()[:40]}"
    return out


def _row_to_person(row, mapping) -> dict:
    rec, props = {}, {}
    for i, field in mapping.items():
        if i >= len(row):
            continue
        v = str(row[i] or "").strip()
        if not v:
            continue
        if field.startswith(CUSTOM + "."):
            props[field.split(".", 1)[1]] = v
        else:
            rec[field] = v
    if not rec.get("first_name") and rec.get("name"):
        rec["first_name"], rec["last_name"] = CORE.split_name(rec.pop("name"))
    rec.pop("name", None)
    if props:
        rec["properties"] = props
    return rec


def preview(repo, filename, data, mapping=None) -> dict:
    """Read the file and report what WOULD happen. Writes nothing."""
    if len(data) > MAX_UPLOAD:
        return {"ok": False,
                "message": f"that file is {len(data)//1024//1024} MB; the "
                           f"limit is {MAX_UPLOAD//1024//1024} MB. Split it "
                           f"or send a CSV instead of a workbook."}
    try:
        rows, kind = XL.read_any(filename, data)
    except Exception as ex:
        return {"ok": False,
                "message": f"that file could not be read as a spreadsheet: "
                           f"{type(ex).__name__}"}
    rows = [r for r in rows if any(str(c or "").strip() for c in r)]
    if len(rows) < 2:
        return {"ok": False,
                "message": "there is a header but no data underneath it"}
    header, body = rows[0], rows[1:]
    mapping = ({int(k): v for k, v in _D(mapping).items()} if mapping
               else guess_mapping(header))
    if "email" not in mapping.values():
        return {"ok": False, "header": header, "mapping": mapping,
                "message": "no column in that file looks like an email "
                           "address, and a person with no address cannot be "
                           "emailed or de-duplicated"}
    known = {p.get("email") for p in repo.all("profiles")}
    supp = CORE.suppression_index(repo)
    new, update, invalid, dupe, suppressed = [], [], [], [], []
    seen = set()
    sample = []
    for r in body:
        rec = _row_to_person(r, mapping)
        em = norm_email(rec.get("email"))
        rec["email"] = em
        if len(sample) < 8:
            sample.append(rec)
        if not CORE.valid_email(em):
            invalid.append(rec)
            continue
        if em in seen:
            dupe.append(rec)
            continue
        seen.add(em)
        if em in supp:
            suppressed.append(rec)
            continue
        (update if em in known else new).append(rec)
    return {"ok": True, "kind": kind, "header": header, "mapping": mapping,
            "fields": sorted(set(ALIASES) | {"skip"}),
            "rows": len(body), "sample": sample,
            "new": len(new), "update": len(update), "invalid": len(invalid),
            "duplicate": len(dupe), "suppressed": len(suppressed),
            "custom": sorted({v.split(".", 1)[1] for v in mapping.values()
                              if v.startswith(CUSTOM + ".")}),
            "message": (f"{len(new)} new, {len(update)} already here, "
                        f"{len(dupe)} repeated inside the file, "
                        f"{len(invalid)} with no usable address, "
                        f"{len(suppressed)} on the suppression list and "
                        f"therefore skipped. Nothing has been written.")}


def commit(store, repo, filename, data, mapping=None, *, list_name="",
           source="upload") -> dict:
    """Write the file in. Goes through the audited agent service layer, so a
    list uploaded by hand is recorded exactly like one an agent wrote."""
    pv = preview(repo, filename, data, mapping)
    if not pv.get("ok"):
        return pv
    import content_engine_os_agents as AGT
    rows, _kind = XL.read_any(filename, data)
    rows = [r for r in rows if any(str(c or "").strip() for c in r)]
    mapping = {int(k): v for k, v in _D(pv.get("mapping")).items()}
    supp = CORE.suppression_index(repo)
    written, skipped, ids = 0, 0, []
    seen = set()
    for r in rows[1:]:
        rec = _row_to_person(r, mapping)
        em = norm_email(rec.get("email"))
        if not CORE.valid_email(em) or em in seen or em in supp:
            skipped += 1
            continue
        seen.add(em)
        rec["email"] = em
        rec["source"] = rec.get("source") or source
        out = AGT.call(store, "csv_import", "leads.upsert", rec,
                       workspace_id=repo.ws)
        if out.get("ok"):
            written += 1
            if out.get("profile_id"):
                ids.append(out["profile_id"])
        else:
            skipped += 1
    listed = 0
    if list_name and ids:
        made = AUD.save_list(repo, list_name,
                             f"imported from {filename} on {now()[:10]}")
        if made.get("ok"):
            listed = AUD.add_to_list(repo, made["id"], ids,
                                     source="upload").get("added", 0)
    CORE.audit(repo, "founder", "list_imported", filename,
               f"{written} written, {skipped} skipped")
    return {"ok": True, "written": written, "skipped": skipped,
            "listed": listed,
            "message": (f"{written} person(s) written"
                        + (f", added to the list {list_name!r}" if listed
                           else "")
                        + f". {skipped} row(s) skipped: no usable address, a "
                          f"repeat, or already suppressed.")}


# ---------------------------------------------------------------------------
# ITEM 6: GOOGLE SHEETS
# ---------------------------------------------------------------------------
def sheets_state() -> dict:
    try:
        import content_engine_connectors as C
        sh = C.GoogleSheets()
        return {"ready": bool(sh.available()), "sheet": sh.sheet_id or "",
                "why": ("writing tabs into the sheet the service account was "
                        "given" if sh.available() else
                        "set GOOGLE_SHEETS_ID on the System Map; the key is "
                        "the same one GSC, GA4 and Drive already use")}
    except Exception as ex:
        return {"ready": False, "sheet": "", "why": f"unavailable: {ex}"}


def _sheet_write(sheet_id, token, tab, rows) -> bool:
    """Replace a tab's contents. Clear then write, never append.

    Appending would double every row on the second run, which is how a
    mirror becomes a pile."""
    import urllib.parse
    try:
        import content_engine_connectors as C
        rq = C._requests()
        if not rq:
            return False
        head = {"Authorization": f"Bearer {token}"}
        base = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
        # A tab that does not exist yet has to be made before it is written.
        rq.post(f"{base}:batchUpdate", headers=head, timeout=30, json={
            "requests": [{"addSheet": {"properties": {"title": tab}}}]})
        rng = urllib.parse.quote(f"{tab}!A1:ZZ", safe="")
        rq.post(f"{base}/values/{rng}:clear", headers=head, timeout=30,
                json={})
        r = rq.put(f"{base}/values/{rng}?valueInputOption=RAW", headers=head,
                   timeout=90,
                   json={"values": [["" if v is None else str(v)[:400]
                                     for v in row] for row in rows]})
        return r.status_code < 300
    except Exception as ex:
        log.warning("sheet write %s failed: %s", tab, ex)
        return False


def push_to_sheets(store, repo, tabs=None) -> dict:
    """Mirror every table into the Google Sheet, one tab each. Write only."""
    st = sheets_state()
    if not st["ready"]:
        return {"ok": False, "message": st["why"]}
    import content_engine_connectors as C
    token = C._google_token([C._GSHEETS_SCOPE])
    if not token:
        return {"ok": False, "message": "the Google key was refused"}
    sheet_id = C.GoogleSheets().sheet_id
    want = tabs or list(DATASETS)
    done, failed = [], []
    for name in want:
        if name not in DATASETS:
            continue
        label, _c, _f = DATASETS[name]
        cols, rows = rows_for(repo, name)
        # A sheet cell tops out; big tables are truncated and SAY SO rather
        # than failing the whole mirror.
        capped = rows[:5000]
        note = ([[f"showing the first 5000 of {len(rows)} rows; the full "
                  f"table is in the Excel export"]] if len(rows) > 5000
                else [])
        (done if _sheet_write(sheet_id, token, label,
                              [cols] + capped + note) else failed).append(label)
    stamp = {"at": now(), "tabs": done, "failed": failed}
    try:
        store.set_setting("os_sheets_last", stamp)
    except Exception:
        pass
    return {"ok": bool(done), "tabs": done, "failed": failed,
            "message": (f"{len(done)} tab(s) written into the sheet"
                        + (f", {len(failed)} refused" if failed else "")
                        + ". Like Drive, this only ever writes.")}


def sheets_last(store) -> dict:
    try:
        return _D(store.get_setting("os_sheets_last", {}))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# ITEM 7: THE NIGHTLY MIRROR
# ---------------------------------------------------------------------------
MIRROR_KEY = "os_mirror_last_day"


def mirror_due(store) -> bool:
    try:
        return str(store.get_setting(MIRROR_KEY, "")) != now()[:10]
    except Exception:
        return False


def mirror_if_due(store, repo) -> dict:
    """Called from the worker tick. Writes Drive and Sheets once a day.

    Once a DAY, keyed on the date rather than on a timer, so a container
    restart cannot make it run twelve times and a missed night is caught
    the next morning rather than skipped."""
    if not mirror_due(store):
        return {"ok": True, "skipped": True, "message": "already mirrored today"}
    out = {"drive": push_to_drive(store, repo),
           "sheets": push_to_sheets(store, repo)}
    try:
        store.set_setting(MIRROR_KEY, now()[:10])
    except Exception:
        pass
    return {"ok": True, "skipped": False, **out,
            "message": (str(_D(out["drive"]).get("message", ""))[:90] + " | "
                        + str(_D(out["sheets"]).get("message", ""))[:90])}


# ---------------------------------------------------------------------------
# ITEM 10: A RECURRING IMPORT, AND DE-DUPLICATION BEYOND THE ADDRESS
# ---------------------------------------------------------------------------
SOURCE_KEY = "os_import_sources"


def sources(store) -> list:
    try:
        return _L(store.get_setting(SOURCE_KEY, []))
    except Exception:
        return []


def save_source(store, name, sheet_id, tab="Sheet1", every_days=1) -> dict:
    """A Google Sheet somebody keeps adding leads to, read on a schedule."""
    if not str(sheet_id or "").strip():
        return {"ok": False, "message": "paste the sheet id from its URL"}
    rows = [r for r in sources(store)
            if r.get("sheet_id") != sheet_id or r.get("tab") != tab]
    rows.append({"name": name or tab, "sheet_id": sheet_id.strip(),
                 "tab": tab or "Sheet1", "every_days": int(every_days or 1),
                 "last_at": "", "added_at": now()})
    store.set_setting(SOURCE_KEY, rows[:20])
    return {"ok": True,
            "message": f"{name or tab!r} will be read every "
                       f"{int(every_days or 1)} day(s). Share the sheet with "
                       f"the service account or it cannot be opened."}


def drop_source(store, sheet_id, tab) -> dict:
    rows = [r for r in sources(store)
            if not (r.get("sheet_id") == sheet_id and r.get("tab") == tab)]
    store.set_setting(SOURCE_KEY, rows)
    return {"ok": True, "message": "that source will not be read again"}


def read_sheet(sheet_id, tab) -> list:
    import urllib.parse
    try:
        import content_engine_connectors as C
        token = C._google_token([C._GSHEETS_SCOPE])
        rq = C._requests()
        if not (token and rq):
            return []
        rng = urllib.parse.quote(f"{tab}!A1:ZZ20000", safe="")
        r = rq.get(f"https://sheets.googleapis.com/v4/spreadsheets/"
                   f"{sheet_id}/values/{rng}",
                   headers={"Authorization": f"Bearer {token}"}, timeout=60)
        r.raise_for_status()
        return _L(r.json().get("values"))
    except Exception as ex:
        log.warning("sheet read failed: %s", ex)
        return []


def run_sources(store, repo, *, force=False) -> dict:
    """Read every due sheet and import it. Same preview rules, same audit."""
    from datetime import datetime, timezone, timedelta
    rows, ran, wrote = sources(store), [], 0
    for src in rows:
        last = CORE.parse_at(src.get("last_at"))
        due = force or not last or (
            datetime.now(timezone.utc) - last
            >= timedelta(days=int(src.get("every_days") or 1)))
        if not due:
            continue
        values = read_sheet(src.get("sheet_id"), src.get("tab"))
        if len(values) < 2:
            src["last_at"] = now()
            src["last_result"] = "nothing to read"
            continue
        data = XL.write_csv(values)
        out = commit(store, repo, f"{src.get('name')}.csv", data,
                     source=f"sheet:{src.get('name')}")
        src["last_at"] = now()
        src["last_result"] = out.get("message", "")
        wrote += int(out.get("written") or 0)
        ran.append(src.get("name"))
    try:
        store.set_setting(SOURCE_KEY, rows)
    except Exception:
        pass
    return {"ok": True, "sources": len(ran), "written": wrote,
            "message": (f"{len(ran)} source(s) read, {wrote} person(s) written"
                        if ran else "no source was due")}


def _domain(email_addr) -> str:
    return norm_email(email_addr).rsplit("@", 1)[-1]


def near_duplicates(repo, rows) -> list:
    """ITEM 10, second half. People who are probably already here under a
    different address: same company domain AND same name.

    Reported, never merged. Two people at one firm can share a surname, and
    a merge you cannot undo is worse than a list you have to look at."""
    known = {}
    for p in repo.all("profiles"):
        key = (_domain(p.get("email")),
               str(p.get("first_name") or "").lower().strip(),
               str(p.get("last_name") or "").lower().strip())
        if key[0] and (key[1] or key[2]):
            known.setdefault(key, []).append(p.get("email"))
    out = []
    for r in _L(rows):
        r = _D(r)
        key = (_domain(r.get("email")),
               str(r.get("first_name") or "").lower().strip(),
               str(r.get("last_name") or "").lower().strip())
        hits = [x for x in known.get(key, []) if x != norm_email(r.get("email"))]
        if hits:
            out.append({"email": r.get("email"), "matches": hits[:3],
                        "why": f"same name at {key[0]}"})
    return out
