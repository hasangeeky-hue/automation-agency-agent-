# -*- coding: utf-8 -*-
"""COMMERCE AND CMS: the section that replaces SGA.

SGA answered "how are the social channels doing". That question belongs
to the systems that own those channels, and it is answered there. THIS
section answers the question nothing else could: what does this site
sell, and therefore what should the machine be making?

Three screens, because there are three honest states: what is
connected, what was read, and what follows from it.
"""
from __future__ import annotations

from typing import Any, Dict

import content_engine_commerce as CM


def e(x) -> str:
    return (str("" if x is None else x).replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return list(x) if isinstance(x, (list, tuple)) else []


def _s(x) -> str:
    return "" if x is None else str(x)


CSS = """<style>
.cms-root{background:#F7F8FA;border-radius:12px;padding:14px;
color:#111827;font-size:13px}
.cms-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));
gap:12px}
.cms-card{background:#FFFFFF;border:1px solid #E5E7EB;border-radius:10px;
padding:14px 16px}
.cms-h1{font-size:20px;font-weight:600;margin:0 0 4px}
.cms-h2{font-size:13px;font-weight:600;margin:16px 0 6px}
.cms-meta{font-size:11px;color:#6B7280}
.cms-note{font-size:12px;color:#4B5563;line-height:1.55;max-width:76ch}
.cms-big{font-size:26px;font-weight:650;letter-spacing:-.01em}
.cms-pill{display:inline-block;font-size:10px;font-weight:600;
border-radius:20px;padding:2px 9px;border:1px solid #E5E7EB;color:#4B5563}
.cms-ok{border-color:#16A34A;color:#16A34A}
.cms-wa{border-color:#D97706;color:#D97706}
.cms-off{border-color:#E5E7EB;color:#9CA3AF}
.cms-btn{background:#2563EB;border:1px solid #2563EB;color:#fff;
border-radius:8px;padding:7px 13px;font:inherit;font-size:12px;
font-weight:600;cursor:pointer}
.cms-btn.ghost{background:#fff;color:#111827;border-color:#E5E7EB}
.cms-row{display:flex;gap:10px;justify-content:space-between;
align-items:baseline;padding:8px 0;border-bottom:1px solid #E5E7EB}
.cms-row:last-child{border-bottom:0}
.cms-key{font-family:ui-monospace,Menlo,monospace;font-size:11px;
background:#F3F4F6;border-radius:4px;padding:1px 6px}
</style>"""

JS = """<script>
function cmsRefresh(btn){
  if(!confirm('Read the connected shop or site now? It only READS: it '
    + 'cannot change a product, a price or a page.'))return;
  var b=btn;var old=b?b.textContent:'';
  if(b){b.disabled=true;b.textContent='Reading…';}
  fetch('/cms/refresh',{method:'POST'})
    .then(function(r){return r.json();})
    .then(function(j){
      if(window.toast)toast(j.message||(j.error?('Failed: '+j.error):'Done.'));
      if(!j.error&&window.keepPlace)keepPlace();
      else if(b){b.disabled=false;b.textContent=old;}})
    .catch(function(err){if(window.toast)toast('Failed: '+err);
      if(b){b.disabled=false;b.textContent=old;}});
}
</script>"""


def _connect_card(pid: str, st: dict) -> str:
    d = _d(st)
    on = bool(d.get("connected"))
    pill = ("<span class='cms-pill cms-ok'>connected</span>" if on else
            "<span class='cms-pill cms-off'>"
            + str(d.get("have") or 0) + " of " + str(d.get("needs") or 0)
            + " keys</span>")
    missing = _l(d.get("missing"))
    return ("<div class='cms-card'><div class='cms-row'><b>"
            + e(d.get("label") or pid) + "</b>" + pill + "</div>"
            + "<p class='cms-note'>Reads " + e(d.get("reads")) + ".</p>"
            + ("<p class='cms-note'>Still needs: "
               + " ".join("<span class='cms-key'>" + e(k) + "</span>"
                          for k in missing)
               + "<br><span class='cms-meta'>Where to get it: "
               + e(d.get("where")) + ". Paste it on the Connections board "
               "in System and Wiring; it is stored like every other "
               "credential and never read back out.</span></p>"
               if missing else
               "<p class='cms-meta'>Every key this platform needs is "
               "saved.</p>")
            + "</div>")


def section(ctx=None) -> str:
    """The whole section: connect, read, decide."""
    c = _d(ctx)
    st = _d(c.get("cms_platforms")) or {}
    verdict = _d(c.get("business_type"))
    policy = _d(c.get("content_policy"))
    cat = _d(c.get("cms_catalogue"))

    out = [CSS, JS, "<div class='cms-root'>",
           "<p class='cms-h1'>Commerce and CMS</p>",
           "<p class='cms-note'>Connect the shop or the site, and this "
           "works out what kind of business it is from what is actually "
           "there. Every content agent then writes for THAT business "
           "instead of writing blog posts at everyone forever. It only "
           "reads: it cannot change a product, a price or a page.</p>"]

    # 1. what is connected
    out.append("<p class='cms-h2'>01 &middot; What is connected</p>"
               "<div class='cms-grid'>")
    for pid in ("shopify", "woocommerce", "wordpress"):
        out.append(_connect_card(pid, st.get(pid)))
    out.append("</div>")

    # 2. the verdict
    t = _s(verdict.get("type")) or "UNKNOWN"
    conf = _s(verdict.get("confidence")) or "NONE"
    tone = ("cms-ok" if t in ("ECOMMERCE", "SERVICE") and conf == "HIGH"
            else "cms-wa" if t in ("ECOMMERCE", "SERVICE") else "cms-off")
    ev = _d(verdict.get("evidence"))
    out.append(
        "<p class='cms-h2'>02 &middot; What kind of business is this?</p>"
        "<div class='cms-card'>"
        "<div class='cms-row'><span class='cms-big'>" + e(t) + "</span>"
        "<span class='cms-pill " + tone + "'>" + e(conf)
        + " confidence</span></div>"
        "<p class='cms-note'>" + e(verdict.get("why") or
                                   "nothing has been read yet")
        + "</p>")
    if ev:
        out.append("<p class='cms-meta'>Evidence: "
                   + e(str(ev.get("products_found"))) + " product(s), "
                   + e(str(ev.get("pages_found"))) + " page(s), "
                   + e(str(ev.get("queries_read"))) + " search quer(ies) "
                     "read &middot; buying intent "
                   + e(str(ev.get("buying_intent_queries")))
                   + ", hiring intent "
                   + e(str(ev.get("hiring_intent_queries"))) + "</p>")
    out.append("<div class='cms-row'><span>"
               "<button class='cms-btn' onclick='cmsRefresh(this)'>"
               "Read the CMS and decide</button></span>"
               "<span class='cms-meta'>"
               + (e("last read " + _s(cat.get("at"))[:16])
                  if cat.get("at") else "never read")
               + "</span></div></div>")

    # 3. what follows
    types = _l(policy.get("types"))
    out.append("<p class='cms-h2'>03 &middot; What the agents should "
               "make</p><div class='cms-card'>")
    if types:
        out.append("<p class='cms-note'>" + e(policy.get("why")) + "</p>")
        for x in types:
            out.append("<div class='cms-row'><span>" + e(x) + "</span>"
                       "<span class='cms-meta'>call to action: "
                       + e(policy.get("cta")) + "</span></div>")
        for x in _l(policy.get("avoid")):
            out.append("<p class='cms-note'>Avoid: " + e(x) + "</p>")
    else:
        out.append("<p class='cms-note'>" + e(policy.get("why") or
                   "the business type is not established, so no content "
                   "type is recommended") + "</p>")
    out.append("</div></div>")
    return "".join(out)


def check() -> Dict[str, Any]:
    """The section renders in all three states without a store."""
    problems = []
    for label, ctx in (
            ("empty", {}),
            ("shop", {"business_type": {"type": "ECOMMERCE",
                                        "confidence": "HIGH",
                                        "why": "12 products"},
                      "content_policy": CM.CONTENT_POLICY["ECOMMERCE"]}),
            ("service", {"business_type": {"type": "SERVICE",
                                           "confidence": "HIGH",
                                           "why": "no products"},
                         "content_policy": CM.CONTENT_POLICY["SERVICE"]})):
        try:
            html = section(ctx)
            if "cms-root" not in html:
                problems.append(label + ": did not render")
        except Exception as exc:                      # noqa: BLE001
            problems.append(f"{label}: {type(exc).__name__}: {exc}")
    return {"ok": not problems, "problems": problems}


if __name__ == "__main__":
    r = check()
    assert r["ok"], r["problems"]
    h = section({"business_type": {"type": "UNKNOWN", "confidence": "NONE",
                                   "why": "nothing read"},
                 "content_policy": CM.CONTENT_POLICY["UNKNOWN"]})
    assert "UNKNOWN" in h and "no content type is recommended" in h
    print("OK - cms screen renders connected, unknown and decided states")
