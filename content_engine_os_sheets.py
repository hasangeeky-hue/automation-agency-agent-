"""
content_engine_os_sheets.py
============================================================================
SPREADSHEETS, WITHOUT A DEPENDENCY.

WHY THIS IS HAND WRITTEN
  An .xlsx is a zip of XML. openpyxl is the obvious answer and it is not
  installed on this box, and adding it means a new wheel in the image on a
  machine that is currently sending live email. Ninety lines of stdlib buy
  the same file and no rebuild risk. If openpyxl ever arrives, read_xlsx
  will still work and this file can be deleted.

WHAT IT DOES
  write_xlsx(sheets)  a workbook, one tab per dataset, from lists of rows
  read_xlsx(data)     the first sheet of an uploaded workbook, as rows
  write_csv(rows)     a CSV with a BOM, so Excel opens UTF-8 correctly
  read_csv(data)      a CSV whatever its delimiter or encoding

THE TWO DETAILS THAT ACTUALLY MATTER
  1. The BOM. Without it Excel reads a UTF-8 CSV as Latin-1 and a German
     company name arrives as mojibake. One three-byte prefix.
  2. Inline strings. Using them instead of a shared-string table makes the
     writer half the length and the file opens identically in Excel,
     Numbers and Google Sheets.

NO NETWORK, NO STORE. Bytes in, bytes out.
============================================================================
"""

from __future__ import annotations

import csv
import io
import re
import zipfile

BOM = "﻿"

_ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}
_NUM = re.compile(r"^-?\d+(\.\d+)?$")
_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _x(v) -> str:
    s = "" if v is None else str(v)
    s = _ILLEGAL.sub("", s)
    return "".join(_ESC.get(c, c) for c in s)


def _col(i: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    out = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        out = chr(65 + r) + out
    return out


def _safe_tab(name, used) -> str:
    """Excel refuses / \\ ? * [ ] : in a tab name and caps it at 31 chars."""
    s = re.sub(r"[\\/?*\[\]:]", " ", str(name or "Sheet")).strip()[:31] or "Sheet"
    base, n = s, 2
    while s.lower() in used:
        s = f"{base[:28]}~{n}"
        n += 1
    used.add(s.lower())
    return s


# ---------------------------------------------------------------------------
# WRITE
# ---------------------------------------------------------------------------
def _sheet_xml(rows) -> str:
    out = ["<?xml version='1.0' encoding='UTF-8'?>",
           "<worksheet xmlns='http://schemas.openxmlformats.org/"
           "spreadsheetml/2006/main'><sheetData>"]
    for r, row in enumerate(rows, start=1):
        out.append(f"<row r='{r}'>")
        for c, val in enumerate(row):
            ref = f"{_col(c)}{r}"
            s = "" if val is None else str(val)
            if _NUM.match(s.strip()) and len(s.strip()) < 15:
                out.append(f"<c r='{ref}'><v>{_x(s.strip())}</v></c>")
            else:
                out.append(f"<c r='{ref}' t='inlineStr'><is><t xml:space="
                           f"'preserve'>{_x(s)}</t></is></c>")
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def write_xlsx(sheets) -> bytes:
    """sheets: [(tab_name, [row, row, ...]), ...] -> the workbook, as bytes.

    Row one of each tab is treated as its header by every reader; the
    caller supplies it. Nothing is styled: a spreadsheet somebody is about
    to filter and pivot does not need this engine's opinion about fonts."""
    sheets = [(n, list(rows)) for n, rows in sheets] or [("Empty", [["no data"]])]
    used = set()
    names = [_safe_tab(n, used) for n, _ in sheets]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        types = ["<?xml version='1.0' encoding='UTF-8'?>",
                 "<Types xmlns='http://schemas.openxmlformats.org/package/"
                 "2006/content-types'>",
                 "<Default Extension='rels' ContentType='application/"
                 "vnd.openxmlformats-package.relationships+xml'/>",
                 "<Default Extension='xml' ContentType='application/xml'/>",
                 "<Override PartName='/xl/workbook.xml' ContentType='"
                 "application/vnd.openxmlformats-officedocument."
                 "spreadsheetml.sheet.main+xml'/>"]
        for i in range(len(sheets)):
            types.append(f"<Override PartName='/xl/worksheets/sheet{i+1}.xml' "
                         f"ContentType='application/vnd.openxmlformats-"
                         f"officedocument.spreadsheetml.worksheet+xml'/>")
        types.append("</Types>")
        z.writestr("[Content_Types].xml", "".join(types))
        z.writestr("_rels/.rels",
                   "<?xml version='1.0' encoding='UTF-8'?><Relationships "
                   "xmlns='http://schemas.openxmlformats.org/package/2006/"
                   "relationships'><Relationship Id='rId1' Type='http://"
                   "schemas.openxmlformats.org/officeDocument/2006/"
                   "relationships/officeDocument' Target='xl/workbook.xml'/>"
                   "</Relationships>")
        wb = ["<?xml version='1.0' encoding='UTF-8'?><workbook xmlns='http://"
              "schemas.openxmlformats.org/spreadsheetml/2006/main' "
              "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/"
              "relationships'><sheets>"]
        rels = ["<?xml version='1.0' encoding='UTF-8'?><Relationships xmlns="
                "'http://schemas.openxmlformats.org/package/2006/"
                "relationships'>"]
        for i, name in enumerate(names):
            wb.append(f"<sheet name='{_x(name)}' sheetId='{i+1}' "
                      f"r:id='rId{i+1}'/>")
            rels.append(f"<Relationship Id='rId{i+1}' Type='http://schemas."
                        f"openxmlformats.org/officeDocument/2006/"
                        f"relationships/worksheet' Target='worksheets/"
                        f"sheet{i+1}.xml'/>")
        wb.append("</sheets></workbook>")
        rels.append("</Relationships>")
        z.writestr("xl/workbook.xml", "".join(wb))
        z.writestr("xl/_rels/workbook.xml.rels", "".join(rels))
        for i, (_n, rows) in enumerate(sheets):
            z.writestr(f"xl/worksheets/sheet{i+1}.xml", _sheet_xml(rows))
    return buf.getvalue()


def write_csv(rows) -> bytes:
    """A CSV Excel opens correctly. The BOM is the whole trick: without it
    Excel reads UTF-8 as Latin-1 and every German name arrives broken."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return (BOM + out.getvalue()).encode("utf-8")


def write_json(obj) -> bytes:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2,
                      default=str).encode("utf-8")


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------
def _text_of(el) -> str:
    return "".join(el.itertext())


def read_xlsx(data) -> list:
    """The FIRST sheet of a workbook, as a list of rows.

    Reads both shared strings and inline strings, because Excel writes the
    first and this engine writes the second, and an importer that only
    understood its own output would be useless for the file a client sends
    you."""
    import xml.etree.ElementTree as ET
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = [_text_of(si) for si in root.findall(f"{ns}si")]
        names = [n for n in z.namelist()
                 if n.startswith("xl/worksheets/sheet")]
        if not names:
            return []
        root = ET.fromstring(z.read(sorted(names)[0]))
        rows = []
        for row in root.iter(f"{ns}row"):
            cells = {}
            for c in row.findall(f"{ns}c"):
                ref = c.get("r") or ""
                letters = "".join(ch for ch in ref if ch.isalpha())
                idx = 0
                for ch in letters:
                    idx = idx * 26 + (ord(ch.upper()) - 64)
                idx -= 1
                t = c.get("t")
                if t == "s":
                    v = c.find(f"{ns}v")
                    n = int(v.text) if v is not None and v.text else 0
                    val = shared[n] if n < len(shared) else ""
                elif t == "inlineStr":
                    el = c.find(f"{ns}is")
                    val = _text_of(el) if el is not None else ""
                else:
                    v = c.find(f"{ns}v")
                    val = (v.text or "") if v is not None else ""
                cells[max(0, idx)] = val
            if cells:
                width = max(cells) + 1
                rows.append([cells.get(i, "") for i in range(width)])
            else:
                rows.append([])
    return rows


def read_csv(data) -> list:
    """A CSV whatever its encoding or delimiter.

    Comma, semicolon and tab all appear in real exports: a German Excel
    writes semicolons by default, which is the single most common reason a
    lead list imports as one column."""
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = data.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        return []
    head = text[:4000]
    try:
        delim = csv.Sniffer().sniff(head, delimiters=",;\t|").delimiter
    except Exception:
        delim = max(",;\t|", key=lambda d: head.count(d))
    return [r for r in csv.reader(io.StringIO(text), delimiter=delim)]


def read_any(filename, data) -> tuple:
    """(rows, kind). One door, so the caller never sniffs a file itself."""
    name = str(filename or "").lower()
    if name.endswith((".xlsx", ".xlsm")):
        return read_xlsx(data), "xlsx"
    if name.endswith(".json"):
        import json
        obj = json.loads(data.decode("utf-8", "replace"))
        rows = obj if isinstance(obj, list) else obj.get("rows") or []
        if rows and isinstance(rows[0], dict):
            keys = list(rows[0].keys())
            return [keys] + [[r.get(k, "") for k in keys] for r in rows], "json"
        return rows, "json"
    if data[:2] == b"PK":
        # An .xlsx renamed to .csv is a zip whatever the extension says.
        return read_xlsx(data), "xlsx"
    return read_csv(data), "csv"
