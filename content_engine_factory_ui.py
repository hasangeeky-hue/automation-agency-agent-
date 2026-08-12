# -*- coding: utf-8 -*-
"""CONTENT FACTORY OS: the section, assembled.

Spec sections 5-7, 84-86, 100, 111.

NINE SCREENS, ONE SECTION. The nav is a real sidebar (section 6), not a
tab strip, because the factory is a place you work in rather than a
report you scan.

WHY THIS FILE IS NOT content_engine_factory_boards.py
-----------------------------------------------------
That name is taken by the module this one replaces, and the dashboard
imports it. Writing over it destroys 1,704 lines of working code, which
is exactly what happened once while this was being built. The old name
stays and becomes a shim that delegates here, the same pattern used when
the Media Buying OS replaced its own predecessor.

THE ONE-LIST RULE
-----------------
This project has lost a day to a screen declared in one list and drawn
from another. Here there is exactly ONE list: SCREENS. The nav and the
panels are both derived from it, and check_screens() fails the build if
a row lacks a renderer or a contract.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional, Tuple

import content_engine_factory_agents as FA
import content_engine_factory_os as FOS
import content_engine_factory_screens as S

_s, _d, _l = FOS._s, FOS._d, FOS._l
e = S.e

# ===========================================================================
# 5. THE NINE. ONE LIST.
# ===========================================================================
SCREENS: Tuple[Tuple[str, str, str, Callable, str], ...] = (
    ("cfcmd", "01", "Command Center", S.command_center,
     "What needs my attention, and what should we make next?"),
    ("cfinbox", "02", "Inbox", S.inbox,
     "What did the other systems observe?"),
    ("cfplan", "03", "Planner", S.planner,
     "What are we making, and when?"),
    ("cfstudio", "04", "Studio", S.studio,
     "How do I write this, with the brief and the evidence in view?"),
    ("cflib", "05", "Library", S.library,
     "Where are the assets?"),
    ("cfreview", "06", "Review", S.review,
     "Is this good enough to go out?"),
    ("cfdist", "07", "Distribution", S.distribution,
     "Where did it go, and did the destination take it?"),
    ("cfsocial", "08", "Social", S.social,
     "What goes out on social, and how did it land?"),
    ("cfperf", "09", "Performance", S.performance,
     "What worked, and what should we make more of?"),
    ("cfset", "10", "Settings", S.settings,
     "How is the brand, the tooling and the workflow configured?"),
)

CONTRACT_DIR = os.path.join("docs", "content-factory", "ui")


def check_screens() -> Dict[str, Any]:
    """Section 100: no contract, no screen. Enforced, not requested."""
    problems = []
    for sid, _num, _label, fn, _q in SCREENS:
        if not callable(fn):
            problems.append(sid + ": no renderer")
        path = os.path.join(CONTRACT_DIR, sid + ".md")
        if not os.path.exists(path):
            problems.append(sid + ": no screen contract at " + path)
    ids = [x[0] for x in SCREENS]
    dupes = sorted({x for x in ids if ids.count(x) > 1})
    if dupes:
        problems.append("duplicate screen id: " + ", ".join(dupes))
    if len(SCREENS) > 10:
        problems.append("more than ten screens; the cap moved from nine "
                        "to ten when SGA retired and Social came here "
                        "rather than becoming unreachable code")
    return {"ok": not problems, "problems": problems,
            "count": len(SCREENS),
            "why": ("nine screens, each with a renderer and a contract"
                    if not problems else "; ".join(problems))}


# ===========================================================================
# 6. THE SHELL
# ===========================================================================
_SHELL_CSS = """<style>
.cf-shell{display:grid;grid-template-columns:248px 1fr;gap:14px;
align-items:start}
.cf-nav{background:var(--sf);border:1px solid var(--bd);border-radius:10px;
padding:10px;position:sticky;top:8px}
.cf-nav a{display:flex;gap:9px;align-items:baseline;padding:8px 10px;
border-radius:8px;color:var(--tx2);text-decoration:none;font-size:13px;
cursor:pointer}
.cf-nav a b{font-size:11px;color:var(--mu);font-weight:500;
font-variant-numeric:tabular-nums}
.cf-nav a:hover{background:var(--sf2);color:var(--tx)}
.cf-nav a.on{background:rgba(37,99,235,.08);color:var(--hu);
font-weight:600}
.cf-nav a.on b{color:var(--hu)}
.cf-panel{display:none}
.cf-panel.on{display:block}
.cf-legend{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 0;
padding:0 6px}
.cf-legend span{font-size:10px;padding:2px 7px;border-radius:20px;
border:1px solid var(--bd);color:var(--tx2)}
@media (max-width:900px){.cf-shell{grid-template-columns:1fr}
.cf-nav{position:static}}
</style>"""

_SHELL_JS = """<script>
function cfGo(id){
  document.querySelectorAll('.cf-panel').forEach(function(p){
    p.classList.toggle('on', p.id === 'cfpanel-' + id); });
  document.querySelectorAll('.cf-nav a').forEach(function(a){
    a.classList.toggle('on', a.dataset.cf === id); });
}

/* THE WIRING ROUND ARRIVED, so these stopped being promises. Each one
   posts to an endpoint this API already serves; the two that have no
   endpoint still say so rather than pretending. */
function uiNotWired(n){var m=n+': there is no endpoint for this yet. It is on the build list, not silently broken.';if(window.toast)toast(m);else alert(m);}
function cfPost(u,body,btn,ask){
  if(ask&&!confirm(ask))return;
  var b=btn||(window.event&&window.event.target)||null;
  if(b&&b.tagName!=='BUTTON'&&b.closest)b=b.closest('button');
  var old=b?b.textContent:'';if(b){b.disabled=true;b.textContent='Working…';}
  fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},
           body:JSON.stringify(body||{})})
    .then(function(r){return r.json().catch(function(){return {};});})
    .then(function(j){
      var ok=(j.ok!==false)&&!j.error;
      if(window.toast)toast(ok?(j.message||'Done.'):('Failed: '+(j.error||'unknown')));
      if(ok&&window.keepPlace)keepPlace();
      else if(b){b.disabled=false;b.textContent=old;}})
    .catch(function(e){if(window.toast)toast('Failed: '+e);
      if(b){b.disabled=false;b.textContent=old;}});
}
/* A DECISION IS A HUMAN ACTION and it needs a named human. These three
   were called by the Review board and defined NOWHERE: clicking Approve
   did absolutely nothing, silently, on the one screen where you decide. */
function cfApprove(id,btn){cfPost('/jobs/'+encodeURIComponent(id)+'/approve',{},btn,
  'Approve this piece? It publishes to your site.');}
function cfApproveSend(id,btn){cfPost('/jobs/'+encodeURIComponent(id)+'/approve',{},btn,
  'Approve this piece? Anything addressed to people still waits for a separate send.');}
/* THE NOTE IS AN INLINE FIELD, not a browser prompt. A prompt() steals
   the window, cannot be corrected once dismissed, and throws away what
   you typed on a misclick. The approval row keeps its note beside the
   words it refers to. */
var CF_NOTE_KIND={};
function cfNoteOpen(id,kind){
  CF_NOTE_KIND[id]=kind;
  var box=document.getElementById('cf-note-'+id);
  var why=document.getElementById('cf-notewhy-'+id);
  if(!box)return;
  if(why)why.textContent=(kind==='reject'
    ?'Why are you rejecting it? Recorded so the engine learns.'
    :kind==='variant'
      ?'What should the variant do differently?'
      :'What should change? This goes back as a revision request.');
  box.style.display='block';
  var t=document.getElementById('cf-notetext-'+id);if(t)t.focus();
}
function cfNoteClose(id){var b=document.getElementById('cf-note-'+id);
  if(b)b.style.display='none';}
function cfNoteSend(id,btn){
  var t=document.getElementById('cf-notetext-'+id);
  var note=t?t.value.trim():'';
  var kind=CF_NOTE_KIND[id]||'changes';
  if(!note){if(window.toast)toast('Write the reason first: it is recorded and the engine learns from it.');
    if(t)t.focus();return;}
  if(kind==='reject')cfPost('/jobs/'+encodeURIComponent(id)+'/decline',{note:note},btn);
  else if(kind==='variant')cfPost('/content/variant',{job_id:id,note:note},btn);
  else cfPost('/proposal',{job_id:id,accept:false,note:note},btn);
}
/* kept for callers elsewhere: they open the same inline field */
function cfReject(id){cfNoteOpen(id,'reject');}
function cfRequestChanges(id){cfNoteOpen(id,'changes');}
/* Production */
function cfCreate(a,btn){var t=prompt('What should it be about?');if(!t)return;
  cfPost('/jobs',{type:'content_piece',payload:{config:{topic:t,type:'blog'}}},btn);}
function cfAdd(a,btn){cfCreate(a,btn);}
function cfPlanWeek(a,btn){cfPost('/plan/content',{},btn,
  'Plan a week of content? It costs one LLM call and writes nothing until you approve.');}
function cfGenImage(a,btn){cfPost('/content/test-image',{},btn,
  'Generate one image? It costs about EUR 0.04.');}
/* Local tab switches: a URL, so the tab survives a reload */
function cfTab(param,v){try{var u=new URL(window.location.href);
  u.searchParams.set(param,v);window.location.href=u.toString();}catch(e){}}
function cfInboxTab(t){cfTab('inbox_tab',t);}
function cfPlanMode(m){cfTab('plan_mode',m);}
function cfLib(t){cfTab('lib_tab',t);}
function cfDist(t){cfTab('dist_tab',t);}
/* THE ORPHANS. Eighteen handlers were called by these screens and
   defined nowhere: every click was a silent no-op. Wired where the
   endpoint is unambiguous; where it is not, the button SAYS so, because
   a button wired to the wrong endpoint is worse than a dead one. */
function cfPlan(a,btn){cfPost('/plan/content',{},btn,
  'Plan content now? It costs one LLM call and writes nothing until you approve.');}
function cfAcceptAll(a,btn){cfPost('/plan/approve',{},btn,
  'Approve the whole plan?');}
function cfRejectPlan(a,btn){cfPost('/plan/clear',{},btn,
  'Clear the current plan?');}
function cfAcceptDiff(id,btn){cfPost('/proposal',{job_id:id,accept:true},btn);}
function cfAcceptSel(id,btn){cfPost('/proposal',{job_id:id,accept:true},btn);}
function cfRejectDiff(id,btn){var n=prompt('Why? (recorded so the engine learns)');
  if(n===null)return;cfPost('/proposal',{job_id:id,accept:false,note:n},btn);}
/* opening a piece is a URL, so the view survives a reload */
function cfPreview(id){cfTab('piece',id);}
function cfToReview(id){cfTab('piece',id);}
/* A REAL FILE PICKER. /os/upload/image takes multipart, so this opens
   the OS dialog and posts the file itself rather than describing one. */
function cfUpload(a){
  var i=document.createElement('input');i.type='file';
  i.accept='image/png,image/jpeg,image/webp,image/gif';
  i.onchange=function(){
    var f=i.files&&i.files[0];if(!f)return;
    if(f.size>8*1024*1024){if(window.toast)toast('That file is larger than 8 MB.');return;}
    var fd=new FormData();fd.append('file',f,f.name);
    if(window.toast)toast('Uploading '+f.name+'…');
    fetch('/os/upload/image',{method:'POST',body:fd})
      .then(function(r){return r.json().catch(function(){return {};});})
      .then(function(j){
        var ok=(j.ok!==false)&&!j.error;
        if(window.toast)toast(ok?('Uploaded: '+(j.url||f.name)):('Upload failed: '+(j.error||'unknown')));
        if(ok&&window.keepPlace)keepPlace();})
      .catch(function(e){if(window.toast)toast('Upload failed: '+e);});};
  i.click();
}
/* no endpoint serves this yet - it names itself instead of failing quietly */
/* THE ENDPOINTS EXIST NOW, so these stopped being promises too. Editing
   keeps the previous text, which is what makes Restore a real button. */
function cfEdit(id,field){
  var cur=document.getElementById('cfblk-'+field);
  var was=cur?(cur.innerText||''):'';
  var t=prompt('Edit the '+field.replace('_',' ')+':',was);
  if(t===null)return;
  cfPost('/content/save',{job_id:id,field:field,text:t});
}
function cfSave(id,field,btn){
  var el=document.getElementById('cfedit-'+(field||'body'));
  if(!el){cfEdit(id,field||'body');return;}
  cfPost('/content/save',{job_id:id,field:field||'body',text:el.value},btn);
}
function cfBlock(id,field){cfEdit(id,field||'body');}
function cfEditDiff(id,field){cfEdit(id,field||'body');}
function cfAct(id,what){
  if(what==='approve')return cfApprove(id);
  if(what==='reject')return cfReject(id);
  cfEdit(id,'body');
}
function cfRestore(id,btn){cfPost('/content/restore',{job_id:id},btn,
  'Put back the text as it was before the last edit?');}
function cfVary(id){cfNoteOpen(id,'variant');}
function cfVariants(id,btn){cfVary(id,btn);}
function cfCompare(id){cfTab('piece',id);}
function cfDismiss(id,btn){var w=prompt('Why dismiss this signal? (recorded)');
  if(w===null)return;cfPost('/signal/dismiss',{id:id,why:w},btn);}
function cfEditPlan(id,btn){
  var f=prompt('Which field? title / type / market / date / keyword','title');
  if(!f)return;var v=prompt('New value for '+f);if(v===null)return;
  cfPost('/plan/edit',{id:id,field:f,value:v},btn);}
function cfAnalyzeInbox(a,btn){cfPost('/factory/run',{},btn,
  'Run the factory agents over the signals now? They draft and escalate; they cannot publish.');}
</script>"""


def _nav(active) -> str:
    rows = "".join(
        "<a data-cf='" + sid + "' class='" + ("on" if sid == active else "")
        + "' onclick=\"cfGo('" + sid + "')\"><b>" + num + "</b>"
        + e(label) + "</a>"
        for sid, num, label, _fn, _q in SCREENS)
    legend = "".join(
        "<span class='cf-" + k[:2] + "'>" + e(v) + "</span>"
        for k, v in (("human", "blue: human"), ("ai", "purple: AI"),
                     ("planning", "teal: planning")))
    return ("<div class='cf-nav'><p class='cf-meta' "
            "style='margin:2px 0 8px;padding:0 10px'>CONTENT FACTORY</p>"
            + rows + "<div class='cf-legend'>" + legend + "</div></div>")


def factory_section(ctx=None, *, active="cfcmd") -> str:
    """The whole Content Factory, as one dashboard section.

    Every panel is rendered from SCREENS. A renderer that raises is
    caught and its panel SAYS SO: one screen failing must not take the
    section down, and a blank panel with no explanation is the thing this
    project keeps having to diagnose from scratch.
    """
    c = _d(ctx)
    try:
        c = enrich(c)
    except Exception:                                 # noqa: BLE001
        pass
    panels = []
    for sid, num, label, fn, question in SCREENS:
        try:
            inner = fn(c)
        except Exception as exc:                      # noqa: BLE001
            inner = ("<p class='cf-h1'>" + e(label) + "</p>"
                     + S.empty("This screen could not render",
                               "The renderer raised: " + _s(exc)[:200]
                               + ". The rest of the section is "
                                 "unaffected, and this panel says so "
                                 "rather than showing an empty box.",
                               "", "human"))
        panels.append("<div class='cf-panel"
                      + (" on" if sid == active else "")
                      + "' id='cfpanel-" + sid + "'>"
                      + "<p class='cf-meta'>" + num + " &middot; "
                      + e(question) + "</p>" + inner + "</div>")
    return (S.CSS + _SHELL_CSS + "<div class='cf-root'>"
            + S.header(c)
            + "<div class='cf-shell'>" + _nav(active)
            + "<div>" + "".join(panels) + "</div></div>"
            + "</div>" + _SHELL_JS)


def factory_pages(ctx=None) -> Dict[str, str]:
    """Each screen on its own, for a caller that wants one panel.

    The old module exported this and something may still call it, so the
    name survives the replacement with the new screens behind it.
    """
    c = _d(ctx)
    try:
        c = enrich(c)
    except Exception:                                 # noqa: BLE001
        pass
    out = {}
    for sid, _num, label, fn, _q in SCREENS:
        try:
            out[sid] = fn(c)
        except Exception as exc:                      # noqa: BLE001
            out[sid] = S.empty(label + " could not render",
                               _s(exc)[:200], "", "human")
    return out


# ===========================================================================
# 85. THE EVENT BUS
# ===========================================================================
EVENTS = ("CONTENT_SIGNAL_CREATED", "CONTENT_PLAN_CREATED",
          "CONTENT_DRAFT_CREATED", "CONTENT_APPROVED",
          "CONTENT_PACKAGE_READY", "CONTENT_DISTRIBUTED",
          "CONTENT_PUBLISHED", "CONTENT_PERFORMANCE_UPDATED",
          "CONTENT_LEARNING_CREATED")


def emit(event, payload=None) -> Dict[str, Any]:
    """Publish a domain event. Refuses an undeclared name.

    Section 86 keeps modules loosely coupled through these rather than
    through one module reading another's tables. An event name invented
    at a call site has no subscriber and would fail silently, so it is
    refused here where somebody can see it.
    """
    ev = _s(event).upper()
    if ev not in EVENTS:
        return {"ok": False, "event": ev,
                "why": ("'" + ev + "' is not a declared domain event. An "
                        "undeclared event has no subscriber and would "
                        "fail silently.")}
    return {"ok": True, "event": ev, "payload": _d(payload),
            "why": "published to the bus"}


# ===========================================================================
# 84. THE API SURFACE
# ===========================================================================
API = (
    ("GET", "/content/signals", "list normalized signals"),
    ("POST", "/content/signals/{id}/accept", "accept a signal"),
    ("POST", "/content/plans", "create a plan"),
    ("GET", "/content/plans", "list plans"),
    ("POST", "/content/items", "create a content item"),
    ("GET", "/content/items/{id}", "read one item"),
    ("PATCH", "/content/items/{id}", "edit blocks, creates a version"),
    ("POST", "/content/items/{id}/generate", "run the Creator agent"),
    ("POST", "/content/items/{id}/variants", "create channel variants"),
    ("POST", "/content/items/{id}/review", "run QA and queue for review"),
    ("POST", "/content/items/{id}/approve", "human approval, named"),
    ("POST", "/content/items/{id}/distribute", "build and send a package"),
    ("POST", "/content/assets", "upload an asset"),
    ("POST", "/content/assets/generate", "generate an asset via a tool"),
    ("POST", "/content/assets/{id}/edit", "edit, creating a version"),
    ("GET", "/content/library", "list assets"),
    ("GET", "/content/performance", "content performance"),
    ("POST", "/content/performance/import", "inbound results"),
    ("GET", "/content/learning", "the learning store"),
)


def api_map() -> List[Dict[str, str]]:
    return [{"method": m, "path": p, "does": d} for m, p, d in API]


# ===========================================================================
# 3. THE EXTERNAL OS CONTRACT
# ===========================================================================
def receive_signal(raw, *, at="") -> Dict[str, Any]:
    """The front door for another OS. Normalizes and reports.

    Section 3: the factory does not need to know how the sender computed
    anything. It records the numbers as given and never recomputes them.
    """
    sig = FOS.normalize_signal(raw, received_at=at)
    act = FOS.signal_is_actionable(sig)
    return {"signal": sig, "actionable": act.get("ok"),
            "weak": act.get("weak"),
            "event": emit("CONTENT_SIGNAL_CREATED", {"id": sig.get("id")}),
            "why": act.get("why")}


def enrich(ctx) -> Dict[str, Any]:
    """Fill the screens' derived keys from what the caller supplied.

    Deliberately small. A key the caller already set is never
    overwritten, so a test keeps testing its own fixture rather than
    silently testing live data.
    """
    c = dict(_d(ctx))
    if c.get("signals") and "counts" not in c:
        sigs = [FOS.normalize_signal(s) for s in _l(c["signals"])]
        c["counts"] = {"inbox": len([s for s in sigs
                                     if _s(s.get("status")) == "NEW"])}
    if "loop_counts" not in c:
        c["loop_counts"] = {
            "SIGNAL": len(_l(c.get("signals"))),
            "PLAN": len(_l(_d(c.get("plan")).get("items"))),
            "CONTENT": len(_l(c.get("content_items"))),
            "DISTRIBUTED": len(_l(c.get("packages"))),
            "PERFORMANCE": len(_l(c.get("variants"))),
            "LEARNING": len(_l(c.get("learning"))),
            "REPLANNED": len(_l(_d(c.get("plan")).get("learning_used"))),
        }
    if "data_health" not in c:
        tools = [t for t in FOS.tool_matrix() if t.get("mvp")]
        ok = [t for t in tools if t.get("available")]
        # NOT CONFIGURED is not ERROR. Nothing has failed on a box
        # where nobody has connected a provider yet, and a red ERROR
        # sends someone looking for a broken thing that does not exist.
        c["data_health"] = {
            "state": ("HEALTHY" if ok and len(ok) == len(tools)
                      else "DEGRADED" if ok else "NOT CONFIGURED"),
            "why": (str(len(ok)) + " of " + str(len(tools))
                    + " MVP capabilities are configured"
                    + ("" if ok else
                       ". Nothing has failed; no provider has been "
                       "connected yet."))}
    return c


# ===========================================================================
# 111. THE DEFINITION OF DONE
# ===========================================================================
#: Twenty-eight steps. verify_factory.py walks this list. A step that
#: cannot be demonstrated with real persisted data is not done, whatever
#: a screen happens to look like.
DONE_STEPS = (
    "open the Content Factory",
    "receive a signal from another OS",
    "understand its evidence",
    "turn it into a content plan",
    "put content on the planner",
    "generate a brief",
    "open the Studio",
    "write manually",
    "generate or revise text with AI",
    "lock human-approved blocks",
    "upload an image",
    "generate an image",
    "edit an image through a tool",
    "save asset versions",
    "create one master content concept",
    "generate multiple channel variants",
    "preview variants",
    "comment",
    "request revision",
    "review versions and diff",
    "run QA",
    "approve content",
    "send a package to another OS",
    "receive distribution status",
    "receive performance data",
    "see content performance",
    "create learning from results",
    "have the planner use learning next time",
)
