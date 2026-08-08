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
                            "lead_score", "emails_sent", "opens", "clicks",
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


def rows_for(repo, name) -> tuple:
    """(header, rows). Missing columns come back empty rather than raising:
    a dataset that half-exists must still download."""
    label, cols, fn = DATASETS[name]
    try:
        data = _L(fn(repo))
    except Exception as ex:
        log.warning("dataset %s failed: %s", name, ex)
        data = []
    return cols, [[_D(r).get(c, "") for c in cols] for r in data]


def as_bytes(repo, name, fmt) -> tuple:
    """(filename, mime, bytes) for one dataset."""
    label, cols, _fn = DATASETS[name]
    cols, rows = rows_for(repo, name)
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
