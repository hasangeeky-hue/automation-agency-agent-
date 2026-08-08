"""
content_engine_os_editors.py
============================================================================
THE TWO EDITORS YOU DRAG: THE FLOW CANVAS AND THE EMAIL BUILDER.

WHY THEY LIVE IN THEIR OWN FILE
  Both are mostly JavaScript, and mixing four hundred lines of it into the
  screens module makes the screens unreadable. Nothing here holds data or
  makes a decision: each editor loads a graph or a block list, lets you
  move it around, and posts it back. The backend is the truth.

THE FLOW CANVAS
  Drag a node and it moves. Press Connect on one node and click another to
  draw an arrow. Click a node to configure it. Save posts the whole graph
  to /os/flow/save, which validates it and refuses to activate a shape that
  strands people.

  Deliberately NOT a live-saving canvas: an autosaving editor on a flow
  that real people are moving through is how somebody ends up mid-sequence
  in a step that no longer exists. You press Save, the backend validates,
  and it tells you what it did.

THE EMAIL BUILDER
  Nine block types, add, remove, reorder by dragging, edit in place, and a
  preview that renders through the SAME renderer the sender uses. A preview
  drawn by different code from the one that sends is a decoration.
============================================================================
"""

from __future__ import annotations

import html as _html
import json

from content_engine_os_content import BLOCK_TYPES
from content_engine_os_core import NODE_TYPES, _D, _L

from content_engine_os_flows import NODE_CONFIG, TRIGGERS


def e(v) -> str:
    return _html.escape(str(v if v is not None else ""), quote=True)


def j(v) -> str:
    """A python value into a JS literal, safely embedded in HTML."""
    return _html.escape(json.dumps(v, default=str), quote=True)


# ---------------------------------------------------------------------------
# THE FLOW CANVAS
# ---------------------------------------------------------------------------
def flow_canvas(flow, campaigns=None, lists=None) -> str:
    """One editable flow. The graph travels to the browser as data, not as
    markup, so what you drag and what gets saved are the same object."""
    flow = _D(flow)
    graph = _D(flow.get("graph")) or {"nodes": _L(flow.get("nodes")),
                                      "edges": _L(flow.get("edges"))}
    opts = {
        "campaign_id": [{"v": _D(c).get("id"),
                         "l": _D(c).get("subject") or _D(c).get("name")}
                        for c in _L(campaigns)],
        "list_id": [{"v": _D(l).get("id"), "l": _D(l).get("name")}
                    for l in _L(lists)],
        "event": [{"v": t, "l": t.replace("_", " ")} for t in TRIGGERS],
    }
    palette = "".join(
        f"<button class='os-mini' onclick=\"osFxAdd('{t}')\">"
        f"+ {e(t.replace('_', ' ').title())}</button>" for t in NODE_TYPES
        if t != "TRIGGER")
    return (
        "<div class='os-fx' data-flow='" + e(flow.get("id")) + "' "
        "data-graph='" + j(graph) + "' data-opts='" + j(opts) + "' "
        "data-config='" + j({k: list(v) for k, v in NODE_CONFIG.items()}) + "'>"
        "<div class='os-brow os-fxbar'>"
        + palette +
        "<button class='os-mini' onclick='osFxLink()' id='os-fxlink'>"
        "Connect</button>"
        "<button class='os-mini' onclick='osFxCopy()'>Duplicate</button>"
        "<button class='os-mini' onclick='osFxDrop()'>Delete step</button>"
        "<button class='os-mini' onclick='osFxUndo()' id='os-fxundo'>"
        "Undo</button>"
        "<button class='os-mini' onclick='osFxZoom(-1)'>-</button>"
        "<button class='os-mini' onclick='osFxZoom(0)'>Fit</button>"
        "<button class='os-mini' onclick='osFxZoom(1)'>+</button>"
        "<button class='cta' onclick='osFxSave()'>Save the flow</button>"
        "</div>"
        "<div class='os-fxwrap'><div class='os-fxcanvas' id='os-fxcanvas'>"
        "<svg class='os-fxedges' id='os-fxedges'></svg></div></div>"
        "<div class='os-fxform' id='os-fxform'>"
        "<p class='os-note'>Click a step to configure it. Drag it to move "
        "it. Press Connect, then click the step it should lead to.</p>"
        "</div></div>")


FLOW_JS = ("<script>"
           "var OSFX={id:'',g:{nodes:[],edges:[]},sel:'',link:false,opts:{},"
           "cfg:{},drag:null,undo:[],zoom:1};"

           # Every change pushes the WHOLE graph. A flow has a few dozen
           # nodes, so a full snapshot costs nothing and cannot get the
           # partial-undo bugs a diff-based stack collects.
           "function osFxMark(){OSFX.undo.push(JSON.stringify(OSFX.g));"
           "if(OSFX.undo.length>40)OSFX.undo.shift();"
           "var b=document.getElementById('os-fxundo');"
           "if(b)b.textContent='Undo ('+OSFX.undo.length+')';}"
           "function osFxUndo(){if(!OSFX.undo.length){osToast({ok:false,"
           "message:'nothing to undo'});return;}"
           "OSFX.g=JSON.parse(OSFX.undo.pop());OSFX.sel='';osFxDraw();"
           "osFxForm();var b=document.getElementById('os-fxundo');"
           "if(b)b.textContent=OSFX.undo.length?'Undo ('+OSFX.undo.length+')'"
           ":'Undo';}"

           "function osFxZoom(d){var c=document.getElementById('os-fxcanvas');"
           "if(!c)return;"
           "if(d===0){OSFX.zoom=1;}else{OSFX.zoom=Math.min(1.6,Math.max(0.4,"
           "OSFX.zoom+d*0.15));}"
           "c.style.transform='scale('+OSFX.zoom+')';"
           "c.style.transformOrigin='0 0';}"

           "function osFxCopy(){if(!OSFX.sel){osToast({ok:false,message:"
           "'click a step first'});return;}osFxMark();"
           "var n=OSFX.g.nodes.filter(function(x){return x.id===OSFX.sel;})[0];"
           "if(!n)return;var c=JSON.parse(JSON.stringify(n));"
           "c.id='node'+(OSFX.g.nodes.length+1)+'_'+OSFX.g.nodes.length;"
           "c.position_x=(n.position_x||0)+40;c.position_y=(n.position_y||0)+60;"
           "OSFX.g.nodes.push(c);OSFX.sel=c.id;osFxDraw();osFxForm();}"

           "function osFxBoot(){var r=document.querySelector('.os-fx');"
           "if(!r)return;OSFX.id=r.dataset.flow;"
           "try{OSFX.g=JSON.parse(r.dataset.graph)||{nodes:[],edges:[]};"
           "OSFX.opts=JSON.parse(r.dataset.opts)||{};"
           "OSFX.cfg=JSON.parse(r.dataset.config)||{};}catch(e){}"
           "OSFX.g.nodes=OSFX.g.nodes||[];OSFX.g.edges=OSFX.g.edges||[];"
           "osFxDraw();}"

           "function osFxDraw(){var c=document.getElementById('os-fxcanvas');"
           "if(!c)return;"
           "var svg=document.getElementById('os-fxedges');"
           "c.querySelectorAll('.os-fxnode').forEach(function(n){n.remove();});"
           "var maxx=600,maxy=400;"
           "OSFX.g.nodes.forEach(function(n){"
           "var d=document.createElement('div');"
           "d.className='os-fxnode'+(OSFX.sel===n.id?' sel':'');"
           "d.style.left=(n.position_x||0)+'px';d.style.top=(n.position_y||0)+'px';"
           "d.dataset.id=n.id;"
           "var det=Object.keys(n.config||{}).map(function(k){"
           "return k+': '+(n.config[k]===''?'not set':n.config[k]);}).join(', ');"
           "d.innerHTML=\"<b>\"+n.type.replace(/_/g,' ')+\"</b><span>\"+"
           "(det||'no settings')+\"</span>\";"
           "d.addEventListener('pointerdown',osFxDown);"
           "c.appendChild(d);"
           "maxx=Math.max(maxx,(n.position_x||0)+240);"
           "maxy=Math.max(maxy,(n.position_y||0)+120);});"
           "c.style.width=maxx+'px';c.style.height=maxy+'px';"
           "svg.setAttribute('viewBox','0 0 '+maxx+' '+maxy);"
           "svg.setAttribute('width',maxx);svg.setAttribute('height',maxy);"
           "var pos={};OSFX.g.nodes.forEach(function(n){"
           "pos[n.id]=[(n.position_x||0)+90,(n.position_y||0)];});"
           "svg.innerHTML=OSFX.g.edges.map(function(ed){"
           "var a=pos[ed.source_node_id],b=pos[ed.target_node_id];"
           "if(!a||!b)return '';"
           "var p=\"M\"+a[0]+\",\"+(a[1]+46)+\" C\"+a[0]+\",\"+(a[1]+90)+\" \"+"
           "b[0]+\",\"+(b[1]-40)+\" \"+b[0]+\",\"+b[1];"
           "var t=ed.condition?(\"<text x='\"+((a[0]+b[0])/2+6)+\"' y='\"+"
           "((a[1]+b[1])/2+30)+\"' class='os-bl'>\"+ed.condition+\"</text>\"):'';"
           "return \"<path d='\"+p+\"' class='os-edge'/>\"+t;}).join('');}"

           "function osFxDown(ev){osFxMark();var el=ev.currentTarget;"
           "var id=el.dataset.id;"
           "if(OSFX.link&&OSFX.sel&&OSFX.sel!==id){osFxJoin(OSFX.sel,id);return;}"
           "OSFX.sel=id;osFxForm();"
           "OSFX.drag={el:el,id:id,x:ev.clientX,y:ev.clientY,"
           "ox:parseInt(el.style.left)||0,oy:parseInt(el.style.top)||0};"
           "el.setPointerCapture(ev.pointerId);"
           "el.addEventListener('pointermove',osFxMove);"
           "el.addEventListener('pointerup',osFxUp);osFxDraw();}"

           "function osFxMove(ev){var d=OSFX.drag;if(!d)return;"
           "var nx=Math.max(0,d.ox+ev.clientX-d.x),"
           "ny=Math.max(0,d.oy+ev.clientY-d.y);"
           "d.el.style.left=nx+'px';d.el.style.top=ny+'px';"
           "var n=OSFX.g.nodes.filter(function(n){return n.id===d.id;})[0];"
           "if(n){n.position_x=nx;n.position_y=ny;}}"

           "function osFxUp(ev){var d=OSFX.drag;if(d){"
           "d.el.removeEventListener('pointermove',osFxMove);"
           "d.el.removeEventListener('pointerup',osFxUp);}"
           "OSFX.drag=null;osFxDraw();}"

           "function osFxLink(){OSFX.link=!OSFX.link;"
           "var b=document.getElementById('os-fxlink');"
           "if(b)b.textContent=OSFX.link?'Connect: pick the next step':'Connect';}"

           "function osFxJoin(a,b){osFxMark();var cond='';"
           "var src=OSFX.g.nodes.filter(function(n){return n.id===a;})[0];"
           "if(src&&src.type==='CONDITION')cond=prompt("
           "'Which branch does this arrow carry? yes or no','yes')||'';"
           "if(src&&src.type==='SPLIT')cond=prompt("
           "'Which arm does this arrow carry? a or b','a')||'';"
           "OSFX.g.edges.push({id:'e'+Date.now(),source_node_id:a,"
           "target_node_id:b,condition:cond});"
           "OSFX.link=false;osFxLink();osFxLink();osFxDraw();}"

           "function osFxAdd(type){osFxMark();var n={id:'n'+Date.now(),type:type,"
           "config:{},position_x:40,position_y:40+OSFX.g.nodes.length*70};"
           "(OSFX.cfg[type]||[]).forEach(function(k){n.config[k]='';});"
           "OSFX.g.nodes.push(n);OSFX.sel=n.id;osFxDraw();osFxForm();}"

           "function osFxDrop(){osFxMark();if(!OSFX.sel){osToast({ok:false,message:"
           "'click a step first'});return;}"
           "OSFX.g.nodes=OSFX.g.nodes.filter(function(n){return n.id!==OSFX.sel;});"
           "OSFX.g.edges=OSFX.g.edges.filter(function(e){"
           "return e.source_node_id!==OSFX.sel&&e.target_node_id!==OSFX.sel;});"
           "OSFX.sel='';osFxDraw();osFxForm();}"

           "function osFxForm(){var f=document.getElementById('os-fxform');"
           "if(!f)return;"
           "var n=OSFX.g.nodes.filter(function(x){return x.id===OSFX.sel;})[0];"
           "if(!n){f.innerHTML=\"<p class='os-note'>Click a step to configure \"+"
           "\"it. Drag it to move it. Press Connect, then click the step it \"+"
           "\"should lead to.</p>\";return;}"
           "var keys=OSFX.cfg[n.type]||[];"
           "var rows=keys.map(function(k){"
           "var o=OSFX.opts[k];"
           "if(o&&o.length){return \"<label>\"+k+\"</label><select \"+"
           "\"onchange=\\\"osFxSet('\"+k+\"',this.value)\\\" class='os-in'>\"+"
           "\"<option value=''>choose</option>\"+o.map(function(x){"
           "return \"<option value='\"+x.v+\"'\"+(n.config[k]===x.v?' selected':'')+"
           "\">\"+x.l+\"</option>\";}).join('')+\"</select>\";}"
           "return \"<label>\"+k+\"</label><input class='os-in' value='\"+"
           "(n.config[k]||'')+\"' oninput=\\\"osFxSet('\"+k+\"',this.value)\\\">\";"
           "}).join('');"
           "f.innerHTML=\"<p class='os-st'>\"+n.type.replace(/_/g,' ')+\"</p>\"+"
           "(rows||\"<p class='os-note'>this step needs no settings</p>\");}"

           "function osFxSet(k,v){var n=OSFX.g.nodes.filter(function(x){"
           "return x.id===OSFX.sel;})[0];if(n){n.config[k]=v;osFxDraw();}}"

           "async function osFxSave(){var j=await osAct('/os/flow/save',"
           "{id:OSFX.id,nodes:OSFX.g.nodes,edges:OSFX.g.edges});"
           "if(j&&j.ok)osToast(j,'saved');}"
           "</script>")


# ---------------------------------------------------------------------------
# THE EMAIL BUILDER
# ---------------------------------------------------------------------------
#: Which fields each block asks for. One declaration; the form and the
#: renderer read the same list.
BLOCK_FIELDS = {
    "columns": ("left", "right"),
    "heading": ("content", "level"),
    "text": ("content",),
    "image": ("url", "alt"),
    "button": ("label", "url", "color"),
    "divider": (),
    "spacer": ("height",),
    "social": (),
    "product": ("title", "description", "price"),
    "footer": ("content",),
}

_MISSING = [b for b in BLOCK_TYPES if b not in BLOCK_FIELDS]
assert not _MISSING, f"block types with no form: {_MISSING}"


def block_editor(template=None) -> str:
    t = _D(template)
    blocks = _L(t.get("blocks")) or [
        {"type": "heading", "content": "Hi {{first_name}}", "level": 2},
        {"type": "text", "content": "One short paragraph that says why you "
                                    "wrote, in their words."},
        {"type": "button", "label": "Book a call",
         "url": "https://anthropos-automation.com/free-audit/"},
    ]
    palette = "".join(
        f"<button class='os-mini' onclick=\"osBbAdd('{b}')\">+ {e(b)}</button>"
        for b in BLOCK_TYPES)
    # An image in an email must live at a URL a mail client can fetch.
    # Uploading here puts it in Drive and returns that URL, so the
    # founder does not have to host a picture somewhere first.
    palette += ("<label class='os-mini os-up'>+ upload an image"
                "<input type='file' accept='image/*' hidden "
                "onchange='osBbUpload(this)'></label>")
    return (
        "<div class='os-bb' data-id='" + e(t.get("id")) + "' "
        "data-blocks='" + j(blocks) + "' "
        "data-fields='" + j({k: list(v) for k, v in BLOCK_FIELDS.items()}) + "'>"
        "<div class='os-form'>"
        "<input class='os-in' id='os-bbname' placeholder='Template name' "
        "value='" + e(t.get("name")) + "'>"
        "<input class='os-in' id='os-bbsubj' placeholder='Subject line' "
        "value='" + e(t.get("subject")) + "'>"
        "<button class='os-mini' onclick='osBbSave(false)'>Save draft</button>"
        "<button class='cta' onclick='osBbSave(true)'>Publish a version"
        "</button></div>"
        "<div class='os-brow'>" + palette + "</div>"
        "<div class='os-two'>"
        "<div class='os-col'><div id='os-bblist' class='os-bblist'></div></div>"
        "<div class='os-col'><p class='os-st'>Preview</p>"
        "<div class='os-render'><iframe class='os-frame' id='os-bbframe' "
        "sandbox=''></iframe></div>"
        "<p class='os-note'>The preview is drawn by the same renderer the "
        "sender uses. A preview built by different code from the one that "
        "sends is a decoration.</p></div></div></div>")


BLOCK_JS = ("<script>"
            "var OSBB={id:'',blocks:[],fields:{},drag:-1};"

            "function osBbBoot(){var r=document.querySelector('.os-bb');"
            "if(!r)return;OSBB.id=r.dataset.id;"
            "try{OSBB.blocks=JSON.parse(r.dataset.blocks)||[];"
            "OSBB.fields=JSON.parse(r.dataset.fields)||{};}catch(e){}"
            "osBbDraw();}"

            "function osBbDraw(){var l=document.getElementById('os-bblist');"
            "if(!l)return;"
            "l.innerHTML=OSBB.blocks.map(function(b,i){"
            "var keys=OSBB.fields[b.type]||[];"
            "var rows=keys.map(function(k){"
            "var v=(b[k]===undefined?'':b[k]);"
            "if(k==='content')return \"<textarea class='os-ta' rows='3' \"+"
            "\"oninput=\\\"osBbSet(\"+i+\",'\"+k+\"',this.value)\\\">\"+v+\"</textarea>\";"
            "return \"<input class='os-in' placeholder='\"+k+\"' value='\"+v+\"' \"+"
            "\"oninput=\\\"osBbSet(\"+i+\",'\"+k+\"',this.value)\\\">\";}).join('');"
            "return \"<div class='os-bbi' draggable='true' data-i='\"+i+\"'>\"+"
            "\"<div class='os-bbh'><span class='os-grip'>drag</span><b>\"+b.type+"
            "\"</b><button class='os-mini' onclick='osBbDrop(\"+i+\")'>remove\"+"
            "\"</button></div>\"+(rows||\"<span class='os-d'>nothing to set</span>\")+"
            "\"</div>\";}).join('');"
            "l.querySelectorAll('.os-bbi').forEach(function(el){"
            "el.addEventListener('dragstart',function(){OSBB.drag=+el.dataset.i;});"
            "el.addEventListener('dragover',function(ev){ev.preventDefault();"
            "el.classList.add('over');});"
            "el.addEventListener('dragleave',function(){el.classList.remove('over');});"
            "el.addEventListener('drop',function(ev){ev.preventDefault();"
            "el.classList.remove('over');osBbMove(OSBB.drag,+el.dataset.i);});});"
            "osBbPreview();}"

            "function osBbSet(i,k,v){if(!OSBB.blocks[i])return;"
            "OSBB.blocks[i][k]=v;clearTimeout(OSBB.t);"
            "OSBB.t=setTimeout(osBbPreview,400);}"
            "function osBbAdd(type){OSBB.blocks.push({type:type});osBbDraw();}"

            "async function osBbUpload(el){"
            "var f=el.files&&el.files[0];if(!f)return;"
            "if(f.size>4194304){osToast({ok:false,message:"
            "'images must be under 4 MB; mail clients will not load more'});"
            "return;}"
            "osToast({ok:true,message:'uploading '+f.name+'...'});"
            "var b64=await osFileB64(f);"
            "var j=await osAct('/os/upload/image',{filename:f.name,b64:b64});"
            "if(j&&j.ok&&j.url){OSBB.blocks.push({type:'image',url:j.url,"
            "alt:f.name});osBbDraw();}el.value='';}"

            "async function osBbUpload(el){"
            "var f=el.files&&el.files[0];if(!f)return;"
            "if(f.size>4194304){osToast({ok:false,message:"
            "'images must be under 4 MB; email clients will not load more'});"
            "return;}"
            "osToast({ok:true,message:'uploading '+f.name+'...'});"
            "var b64=await osFileB64(f);"
            "var j=await osAct('/os/upload/image',{filename:f.name,b64:b64});"
            "if(j&&j.ok&&j.url){OSBB.blocks.push({type:'image',url:j.url,"
            "alt:f.name});osBbDraw();}el.value='';}"
            "function osBbDrop(i){OSBB.blocks.splice(i,1);osBbDraw();}"
            "function osBbMove(from,to){if(from<0||from===to)return;"
            "var b=OSBB.blocks.splice(from,1)[0];OSBB.blocks.splice(to,0,b);"
            "OSBB.drag=-1;osBbDraw();}"

            "async function osBbPreview(){try{"
            "var r=await fetch('/os/template/render',{method:'POST',"
            "headers:{'Content-Type':'application/json'},"
            "body:JSON.stringify({blocks:OSBB.blocks})});"
            "var j=await r.json();var f=document.getElementById('os-bbframe');"
            "if(f&&j&&j.html)f.srcdoc=j.html;}catch(e){}}"

            "async function osBbSave(publish){"
            "var n=document.getElementById('os-bbname');"
            "var s=document.getElementById('os-bbsubj');"
            "await osAct('/os/template/save',{id:OSBB.id,name:n?n.value:'',"
            "subject:s?s.value:'',blocks:OSBB.blocks,publish:!!publish});}"
            "</script>")

BOOT_JS = ("<script>"
           "(function(){function go(){try{osFxBoot();}catch(e){}"
           "try{osBbBoot();}catch(e){}}"
           "if(document.readyState!=='loading'){setTimeout(go,0);}"
           "else{document.addEventListener('DOMContentLoaded',go);}})();"
           "</script>")

CSS = """
.os-fxwrap{overflow:auto;background:var(--osbg);border:1px solid var(--osln);
 border-radius:8px;max-height:520px}
.os-fxcanvas{position:relative;min-width:640px;min-height:400px}
.os-fxedges{position:absolute;inset:0;pointer-events:none}
.os-fxnode{position:absolute;width:180px;padding:8px 10px;border-radius:6px;
 background:var(--os2);border:1px solid var(--osln);cursor:grab;
 touch-action:none;user-select:none}
.os-fxnode.sel{border-color:var(--osac);box-shadow:0 0 0 2px rgba(76,141,255,.2)}
.os-fxnode b{display:block;font-size:12px;text-transform:capitalize}
.os-fxnode span{display:block;font-size:10.5px;color:var(--osdim);
 margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.os-fxform{margin:12px 0 0;background:var(--os2);border:1px solid var(--osln);
 border-radius:8px;padding:12px}
.os-fxform label{display:block;font-size:11px;color:var(--osdim);
 margin:8px 0 3px;text-transform:uppercase;letter-spacing:.06em}
.os-fxform .os-in{width:100%}
.os-bblist{display:flex;flex-direction:column;gap:8px}
.os-bbi{background:var(--os2);border:1px solid var(--osln);border-radius:8px;
 padding:10px;cursor:grab}
.os-bbi.over{border-color:var(--osac)}
.os-bbh{display:flex;gap:8px;align-items:center;margin:0 0 6px}
.os-bbh b{font-size:12px;text-transform:capitalize;flex:1}
.os-grip{font-size:10px;color:var(--osdim);text-transform:uppercase;
 letter-spacing:.08em}
.os-bbi .os-in,.os-bbi .os-ta{width:100%;margin:0 0 6px}
"""
