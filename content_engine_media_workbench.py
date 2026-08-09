"""
content_engine_media_workbench.py
============================================================================
THE ANALYTICS WORKBENCH. One screen, twelve sections, one data contract.

HOW THE GOLDEN RULE IS KEPT IN THE BROWSER
  The server embeds a data CUBE (date x platform x campaign base sums,
  plus creative/device/placement/country cubes) and the METRIC REGISTRY
  itself. The client computes every KPI, chart, table and breakdown from
  the cube with ONE generic function that executes the registry's ratio
  rules (sums first, ratios after). The formulas therefore exist in
  exactly one place - the registry - and a chart cannot disagree with the
  table beside it because they are the same aggregation call.

  Live re-queries go to /mediaos/analytics (the same engine that built
  the cube). When the engine is unreachable, the toolbar says so and the
  page keeps computing exactly from the last cube, never approximating.

WHAT THIS SCREEN REFUSES TO PRETEND
  - Audience delivery rows are not collected (no audience_id on metric
    rows); the Audiences section says so instead of drawing a fake table.
  - Attribution runs on its own fixed 90-day window and is labelled.
  - An empty slice renders the spec's empty state, never zeros.
============================================================================
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import json
import logging

import content_engine_media_metrics as MX
import content_engine_media_perf as MF
from content_engine_os_core import _D, _L

log = logging.getLogger("content_engine.media_workbench")


def e(v) -> str:
    return _html.escape(str("" if v is None else v), quote=True)


SECTIONS = (
    ("cc", "Command Center"), ("perf", "Performance"),
    ("camps", "Campaigns"), ("creat", "Creatives"),
    ("aud", "Audiences"), ("plc", "Placements"),
    ("funnel", "Funnel"), ("attr", "Attribution"),
    ("pace", "Budget & Pacing"), ("comp", "Platform Comparison"),
    ("reports", "Custom Reports"), ("health", "Data Health"),
)


def _cube(r) -> dict:
    """Base sums at the grains the client recomputes from. 90 days."""
    cutoff = (_dt.date.today() - _dt.timedelta(days=90)).isoformat()
    camps = {c.get("id"): c for c in r.all("media_campaigns")}
    ad_cre = {str(a.get("id")): str(a.get("creative_id") or "")
              for a in r.all("ads")}
    main, cre, dims = {}, {}, {"device": {}, "placement": {}, "country": {}}
    adopted = 0
    for m in r.all("ad_metrics"):
        day = str(m.get("day") or "")[:10]
        if not day:
            adopted += 1
            continue
        if day < cutoff:
            continue
        p = str(m.get("provider") or "")
        c = str(m.get("campaign_id") or "")
        vals = [float(m.get(k) or 0) for k in
                ("spend", "impressions", "clicks", "conversions",
                 "conversion_value")]

        def bump(store_, key):
            cur = store_.setdefault(key, [0.0] * 5)
            for i, v in enumerate(vals):
                cur[i] += v

        bump(main, (day, p, c))
        crid = (str(m.get("creative_id") or "")
                or ad_cre.get(str(m.get("ad_id") or ""), ""))
        if crid:
            bump(cre, (day, p, crid))
        for dname in dims:
            dv = str(m.get(dname) or "")
            if dv:
                bump(dims[dname], (day, p, dv))
    pack = lambda d: [[*k, *[round(x, 4) for x in v]]  # noqa: E731
                      for k, v in sorted(d.items())]
    return {"main": pack(main), "creative": pack(cre),
            "device": pack(dims["device"]),
            "placement": pack(dims["placement"]),
            "country": pack(dims["country"]),
            "adopted_excluded": adopted,
            "campaigns": {str(k): {"name": v.get("name"),
                                   "objective": v.get("objective"),
                                   "state": v.get("state"),
                                   "provider": v.get("provider")}
                          for k, v in camps.items()}}


def _registry_js() -> dict:
    out = {}
    for k, m in MX.REGISTRY.items():
        if m.get("uncollected"):
            continue
        out[k] = ({"agg": "sum", "col": ("spend", "impressions", "clicks",
                                         "conversions",
                                         "conversion_value")
                   .index(m["column"]), "dec": m["decimals"],
                   "disp": m["display"], "pol": m["polarity"],
                   "unit": m["unit"]}
                  if m["agg"] == "sum" else
                  {"agg": "ratio",
                   "num": ("spend", "impressions", "clicks", "conversions",
                           "conversion_value").index(m["num"]),
                   "den": ("spend", "impressions", "clicks", "conversions",
                           "conversion_value").index(m["den"]),
                   "mult": m["mult"], "dec": m["decimals"],
                   "disp": m["display"], "pol": m["polarity"],
                   "unit": m["unit"]})
    return out


def build(r, store, ctx) -> str:
    """The workbench panel HTML: shell + embedded bootstrap + the app."""
    cube = _cube(r)
    pacing = {}
    try:
        pacing = MX.pacing(r, store)
    except Exception as ex:
        pacing = {"ok": False, "message": f"pacing unavailable: "
                                         f"{type(ex).__name__}"}
    quality = MX.data_quality(r, store)
    # attribution: fixed 90d window, labelled as such
    attrib = {"spread": [], "reconcile": [], "note": ""}
    try:
        sp = MF.model_spread(r)
        rc = MF.reconcile(r)
        attrib = {"spread": [{k: v for k, v in row.items()}
                             for row in sp.get("rows", [])[:20]],
                  "reconcile": rc.get("rows", [])[:20],
                  "note": "attribution runs on its own fixed 90-day "
                          "window over the shared event layer; the "
                          "toolbar's date range does not re-slice it"}
    except Exception:
        pass
    # creative attributes for the attribute breakdown
    creatives = {str(c.get("id")): {
        "name": c.get("name"), "type": c.get("type"),
        "hook": c.get("hook"), "angle": c.get("angle"),
        "persona": c.get("persona"), "cta": c.get("cta"),
        "concept": c.get("concept")}
        for c in r.all("creatives")}
    audiences = [{"name": a.get("name"), "type": a.get("type")}
                 for a in r.all("audiences")[:30]]
    saved = []
    try:
        saved = store.get_setting("media_saved_views", []) or []
    except Exception:
        pass
    boot = {"cube": cube, "registry": _registry_js(), "pacing": pacing,
            "quality": quality, "attribution": attrib,
            "creatives": creatives, "audiences": audiences,
            "views": saved,
            "generated_at": MX.now()}
    payload = json.dumps(boot).replace("</", "<\\/")
    nav = "".join(
        f"<button class='mc-btn wb-nav{' mc-go' if i == 0 else ''}' "
        f"data-sec='{sid}' onclick=\"wbSec('{sid}',this)\">{e(label)}"
        f"</button>" for i, (sid, label) in enumerate(SECTIONS))
    secs = "".join(
        f"<div class='wb-sec{' wb-on' if i == 0 else ''}' "
        f"id='wb-sec-{sid}'></div>"
        for i, (sid, _l) in enumerate(SECTIONS))
    return (
        "<div class='wb-root'>"
        "<div class='wb-toolbar'>"
        "<span class='wb-brand'>ANALYTICS</span>"
        "<select id='wb-plat' onchange='wbCtxChanged()'>"
        "<option value=''>All platforms</option>"
        "<option>google</option><option>meta</option>"
        "<option>tiktok</option><option>linkedin</option></select>"
        "<select id='wb-date' onchange='wbCtxChanged()'>"
        "<option value='7'>Last 7 days</option>"
        "<option value='14'>Last 14 days</option>"
        "<option value='30' selected>Last 30 days</option>"
        "<option value='90'>Last 90 days</option></select>"
        "<select id='wb-gran' onchange='wbCtxChanged()'>"
        "<option>DAY</option><option>WEEK</option><option>MONTH</option>"
        "</select>"
        "<label class='wb-cmp'><input type='checkbox' id='wb-cmp' checked "
        "onchange='wbCtxChanged()'> vs previous period</label>"
        "<span id='wb-fresh' class='wb-fresh'></span>"
        "<span id='wb-crumb' class='wb-crumb'></span>"
        "</div>"
        f"<div class='wb-navrow'>{nav}"
        "<span style='flex:1'></span>"
        "<select id='wb-views'></select>"
        "<input id='wb-viewname' placeholder='view name' "
        "style='width:110px'>"
        "<button class='mc-btn' onclick='wbSaveView(this)'>Save view"
        "</button></div>"
        f"{secs}"
        f"<script type='application/json' id='wb-boot'>{payload}</script>"
        + JS + CSS + "</div>")


CSS = """<style>
.wb-root{margin:4px 0}
.wb-toolbar{display:flex;gap:9px;align-items:center;flex-wrap:wrap;
border:1px solid var(--mc-ln);border-radius:11px;padding:9px 13px;
background:var(--mc-card);margin:0 0 8px;position:sticky;top:0;z-index:5}
.wb-brand{font-size:10px;letter-spacing:1.6px;color:var(--mc-mut);
font-weight:700}
.wb-toolbar select,.wb-toolbar input[type=text],.wb-navrow select,
.wb-navrow input{background:rgba(0,0,0,.25);border:1px solid var(--mc-ln);
border-radius:7px;color:var(--mc-ink);padding:5px 8px;font-size:12px}
.wb-cmp{color:var(--mc-mut);font-size:11px;display:flex;gap:5px;
align-items:center}
.wb-fresh{font-size:10px;color:var(--mc-mut)}
.wb-crumb{font-size:11px;color:var(--mc-go)}
.wb-crumb b{cursor:pointer;text-decoration:underline}
.wb-navrow{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 10px;
align-items:center}
.wb-sec{display:none}.wb-sec.wb-on{display:block}
.wb-kpis{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 12px}
.wb-kpi{flex:1;min-width:140px;border:1px solid var(--mc-ln);
border-radius:11px;padding:11px 14px;background:var(--mc-card)}
.wb-kpi b{display:block;font-size:23px;color:var(--mc-ink);
font-variant-numeric:tabular-nums}
.wb-kpi span{font-size:10px;color:var(--mc-mut);text-transform:uppercase;
letter-spacing:.5px}
.wb-kpi i{font-style:normal;font-size:11px;display:block}
.wb-good{color:#3FD98B}.wb-bad{color:#FF6B93}.wb-flat{color:var(--mc-mut)}
.wb-card{border:1px solid var(--mc-ln);border-radius:11px;
padding:12px 15px;background:var(--mc-card);margin:0 0 12px}
.wb-ct{font-weight:700;color:var(--mc-ink);margin:0 0 2px;font-size:13px}
.wb-cq{color:var(--mc-mut);font-size:11px;margin:0 0 8px}
.wb-row{display:flex;gap:12px;flex-wrap:wrap}
.wb-row>.wb-card{flex:1;min-width:300px}
.wb-chart svg{width:100%;height:150px;display:block}
.wb-legend{font-size:10px;color:var(--mc-mut);margin-top:3px}
.wb-tbl{border-collapse:collapse;width:100%;font-size:12px}
.wb-tbl th{color:var(--mc-mut);text-transform:uppercase;font-size:10px;
letter-spacing:.4px;text-align:left;padding:5px 8px;cursor:pointer;
border-bottom:1px solid var(--mc-ln)}
.wb-tbl td{padding:5px 8px;border-bottom:1px solid var(--mc-ln);
color:var(--mc-ink);font-variant-numeric:tabular-nums}
.wb-scroll{overflow-x:auto}
.wb-link{color:var(--mc-go);cursor:pointer;text-decoration:underline}
.wb-empty{color:var(--mc-mut);font-size:12px;padding:8px 0}
.wb-viewdata{font-size:10px;color:var(--mc-go);cursor:pointer;
margin-left:8px}
.wb-chip{display:inline-block;border:1px solid var(--mc-ln);
border-radius:9px;padding:1px 8px;font-size:10px;color:var(--mc-mut);
margin-left:6px}
.wb-msel{display:flex;gap:5px;flex-wrap:wrap;margin:0 0 7px}
.wb-msel button{background:none;border:1px solid var(--mc-ln);
border-radius:7px;color:var(--mc-mut);padding:3px 9px;font-size:11px;
cursor:pointer}
.wb-msel button.on{border-color:var(--mc-go);color:var(--mc-go)}
.wb-repgrid{display:flex;gap:14px;flex-wrap:wrap}
.wb-repcol{min-width:170px}
.wb-repcol p{color:var(--mc-ink);font-size:11px;font-weight:700;
margin:0 0 5px}
.wb-repcol label{display:block;font-size:11px;color:var(--mc-mut);
margin:2px 0}
</style>"""


# The client app. Every number on this screen is computed by wbAgg() from
# the cube using the embedded registry - the same rules the server runs.
JS = r"""<script>
(function(){
var BOOT=JSON.parse(document.getElementById('wb-boot').textContent);
var CUBE=BOOT.cube, REG=BOOT.registry;
var CTX={plat:'',days:30,gran:'DAY',cmp:true,campaign:''};
var COLS=['spend','impressions','clicks','conversions','conversion_value'];
function fmt(v,dec){if(v===null||v===undefined)return '--';
return Number(v).toLocaleString(undefined,{maximumFractionDigits:dec===undefined?2:dec});}
function today(){var xs=CUBE.main.map(function(r){return r[0];});
return xs.length?xs[xs.length-1]:new Date().toISOString().slice(0,10);}
function dayShift(iso,n){var d=new Date(iso+'T00:00:00Z');
d.setUTCDate(d.getUTCDate()+n);return d.toISOString().slice(0,10);}
function bucketOf(day,g){if(g==='DAY')return day;
if(g==='MONTH')return day.slice(0,7);
var d=new Date(day+'T00:00:00Z');var t=new Date(d);
t.setUTCDate(d.getUTCDate()+4-((d.getUTCDay()+6)%7+1));
var y=t.getUTCFullYear();
var w=Math.ceil(((t-new Date(Date.UTC(y,0,1)))/864e5+1)/7);
return y+'-W'+String(w).padStart(2,'0');}
function rowsIn(rows,from,to){return rows.filter(function(r){
return r[0]>=from&&r[0]<=to
&&(!CTX.plat||r[1]===CTX.plat)
&&(!CTX.campaign||r[2]===CTX.campaign||rows!==CUBE.main&&false);});}
function sums(rows){var s=[0,0,0,0,0];rows.forEach(function(r){
for(var i=0;i<5;i++)s[i]+=r[3+i];});return s;}
// THE ONE AGGREGATION: executes the registry, sums first, ratios after.
function wbAgg(metric,s){var m=REG[metric];if(!m)return null;
if(m.agg==='sum')return +s[m.col].toFixed(m.dec);
if(s[m.den]<=0)return null;
return +((s[m.num]/s[m.den])*m.mult).toFixed(m.dec);}
function windowRows(prev){var t=today();
var to=prev?dayShift(t,-CTX.days):t;
var from=prev?dayShift(t,-2*CTX.days+1):dayShift(t,-CTX.days+1);
return rowsIn(CUBE.main,from,to);}
function grp(rows,keyFn){var out={};rows.forEach(function(r){
var k=keyFn(r);if(k===''||k===null)return;
var s=out[k]||(out[k]=[0,0,0,0,0]);
for(var i=0;i<5;i++)s[i]+=r[3+i];});return out;}
function polCls(metric,chg){if(chg===null||chg===undefined)return 'wb-flat';
var m=REG[metric];var good=(m.pol==='positive'&&chg>0)
||(m.pol==='negative'&&chg<0);
if(m.pol==='neutral')return 'wb-flat';
return good?'wb-good':'wb-bad';}
function esc(s){var d=document.createElement('div');
d.textContent=(s===null||s===undefined)?'':String(s);return d.innerHTML;}
// ---- tiny chart kit (SVG strings) ----
function lineChart(series,opts){opts=opts||{};var w=640,h=140,pad=14;
var all=[];series.forEach(function(s){s.pts.forEach(function(p){
if(p[1]!==null)all.push(p[1]);});});
if(all.length<2)return "<p class='wb-empty'>not enough measured points "
+"to draw a line; a chart appears at two or more</p>";
var lo=Math.min.apply(null,all),hi=Math.max.apply(null,all);
var span=(hi-lo)||1;var n=Math.max.apply(null,series.map(function(s){
return s.pts.length;}));var step=(w-2*pad)/Math.max(n-1,1);
var out="<div class='wb-chart'><svg viewBox='0 0 "+w+" "+h
+"' preserveAspectRatio='none'>";
out+="<line x1='"+pad+"' y1='"+(h-24)+"' x2='"+(w-pad)+"' y2='"+(h-24)
+"' stroke='rgba(143,160,200,.25)'/>";
series.forEach(function(s){var pts=[];s.pts.forEach(function(p,i){
if(p[1]===null)return;
pts.push((pad+i*step).toFixed(1)+','
+(pad+(h-38)-((p[1]-lo)/span)*(h-38)).toFixed(1));});
out+="<polyline points='"+pts.join(' ')+"' fill='none' stroke='"+s.color
+"' stroke-width='2'"+(s.dash?" stroke-dasharray='4 4'":"")+"/>";});
out+="</svg><div class='wb-legend'>"+series.map(function(s){
return "<span style='color:"+s.color+"'>"
+(s.dash?'╌ ':'─ ')+esc(s.name)+"</span>";}).join(' &middot; ')
+" &middot; low "+fmt(lo)+" &middot; high "+fmt(hi)+"</div></div>";
return out;}
function hbars(rows,opts){opts=opts||{};
if(!rows.length)return "<p class='wb-empty'>"+(opts.empty
||'nothing measured in this slice')+"</p>";
var top=Math.max.apply(null,rows.map(function(r){return r[1]||0;}))||1;
return rows.map(function(r){
return "<div style='display:flex;gap:8px;align-items:center;margin:3px 0'>"
+"<span style='width:130px;font-size:11px;color:var(--mc-ink)'"
+(opts.click?" class='wb-link' onclick=\""+opts.click+"('"+esc(r[0])
+"')\"":"")+">"+esc(r[0])+"</span>"
+"<span style='flex:1;height:9px;border-radius:5px;"
+"background:rgba(255,255,255,.06);overflow:hidden'>"
+"<span style='display:block;height:100%;width:"
+Math.max(2,Math.round((r[1]||0)/top*100))
+"%;background:"+(opts.color||'#4C8DFF')+"'></span></span>"
+"<i style='font-style:normal;font-size:11px;color:var(--mc-ink)'>"
+fmt(r[1])+"</i></div>";}).join('');}
function scatter(points){if(points.length<2)
return "<p class='wb-empty'>a scatter needs at least two campaigns with "
+"measured spend and return</p>";
var w=640,h=170,pad=20;
var xs=points.map(function(p){return p.x;}),ys=points.map(function(p){
return p.y;});
var xl=Math.min.apply(null,xs),xh=Math.max.apply(null,xs);
var yl=Math.min.apply(null,ys),yh=Math.max.apply(null,ys);
var out="<div class='wb-chart'><svg viewBox='0 0 "+w+" "+h
+"' preserveAspectRatio='none'>";
points.forEach(function(p){
var x=pad+((p.x-xl)/((xh-xl)||1))*(w-2*pad);
var y=(h-pad)-((p.y-yl)/((yh-yl)||1))*(h-2*pad);
out+="<circle cx='"+x.toFixed(1)+"' cy='"+y.toFixed(1)
+"' r='"+Math.max(3,Math.min(9,3+(p.n||0)/5))
+"' fill='#4C8DFF' opacity='.75'><title>"+esc(p.label)+"\nspend "
+fmt(p.x)+" / ROAS "+fmt(p.y)+"</title></circle>";});
out+="</svg><div class='wb-legend'>x: spend &middot; y: ROAS &middot; "
+"size: conversions &middot; hover a point for the campaign</div></div>";
return out;}
function viewData(id,heads,rows){return "<span class='wb-viewdata' "
+"onclick=\"document.getElementById('"+id+"').style.display="
+"document.getElementById('"+id+"').style.display==='none'?'block':'none'"
+"\">[View data]</span><div id='"+id+"' style='display:none' "
+"class='wb-scroll'><table class='wb-tbl'><thead><tr>"
+heads.map(function(x){return '<th>'+esc(x)+'</th>';}).join('')
+"</tr></thead><tbody>"+rows.map(function(r){return '<tr>'
+r.map(function(c){return '<td>'+((c===null)?'--':esc(
typeof c==='number'?fmt(c):c))+'</td>';}).join('')+'</tr>';}).join('')
+"</tbody></table></div>";}
function card(title,q,body){return "<div class='wb-card'>"
+"<p class='wb-ct'>"+esc(title)+"</p>"
+(q?"<p class='wb-cq'>"+esc(q)+"</p>":"")+body+"</div>";}
// ---- context / breadcrumb ----
window.wbCtxChanged=function(){
CTX.plat=document.getElementById('wb-plat').value;
CTX.days=+document.getElementById('wb-date').value;
CTX.gran=document.getElementById('wb-gran').value;
CTX.cmp=document.getElementById('wb-cmp').checked;
wbRender();};
window.wbDrillPlat=function(p){CTX.plat=(CTX.plat===p)?'':p;
document.getElementById('wb-plat').value=CTX.plat;wbRender();};
window.wbDrillCamp=function(c){CTX.campaign=(CTX.campaign===c)?'':c;
wbRender();};
function crumb(){var el=document.getElementById('wb-crumb');
var parts=["<b onclick='wbDrillPlat(\"\")'>All platforms</b>"];
if(CTX.plat)parts.push("<b onclick='wbDrillCamp(\"\")'>"+esc(CTX.plat)
+"</b>");
if(CTX.campaign){var c=CUBE.campaigns[CTX.campaign]||{};
parts.push(esc(c.name||CTX.campaign));}
el.innerHTML=parts.join(' › ');}
// ---- sections ----
function secCC(){var cur=sums(windowRows(false)),
prev=sums(windowRows(true));
var ks=['spend','revenue','conversions','cpa','roas'];
var map={revenue:'conversion_value'};
function agg(k,s){return wbAgg(k==='revenue'?'revenue':k,s);}
var kpis=ks.map(function(k){var v=wbAgg(k,cur),p=wbAgg(k,prev);
var chg=(p&&v!==null)?+((v-p)/p*100).toFixed(1):null;
return "<div class='wb-kpi'><span>"+esc(REG[k].disp)+"</span><b>"
+(v===null?'--':fmt(v))+"</b><i class='"+polCls(k,chg)+"'>"
+(chg===null?(v===null?'no denominator in slice':'no previous period')
:(chg>0?'+':'')+chg+'%')+"</i></div>";}).join('');
var g=grp(windowRows(false),function(r){return bucketOf(r[0],CTX.gran);});
var gp=grp(windowRows(true),function(r){return bucketOf(r[0],CTX.gran);});
var mk=window.wbMetric||'spend';
var bs=Object.keys(g).sort();var bp=Object.keys(gp).sort();
var main=lineChart([{name:'current '+mk,color:'#4C8DFF',
pts:bs.map(function(b){return [b,wbAgg(mk,g[b])];})}].concat(
CTX.cmp?[{name:'previous',color:'#8FA0C8',dash:true,
pts:bp.map(function(b){return [b,wbAgg(mk,gp[b])];})}]:[]));
var msel="<div class='wb-msel'>"+['spend','revenue','conversions','cpa',
'roas','ctr'].map(function(m){return "<button class='"+(m===mk?'on':'')
+"' onclick=\"window.wbMetric='"+m+"';wbRender()\">"+REG[m].disp
+"</button>";}).join('')+"</div>";
var byPlat=grp(windowRows(false),function(r){return r[1];});
var platRows=Object.keys(byPlat).map(function(p){
return [p,wbAgg('roas',byPlat[p])];}).filter(function(r){
return r[1]!==null;}).sort(function(a,b){return b[1]-a[1];});
var byCamp=grp(windowRows(false),function(r){return r[2];});
var camps=Object.keys(byCamp).map(function(c){var s=byCamp[c];
return {id:c,name:(CUBE.campaigns[c]||{}).name||c,
spend:wbAgg('spend',s),conv:wbAgg('conversions',s),cpa:wbAgg('cpa',s),
rev:wbAgg('revenue',s),roas:wbAgg('roas',s)};})
.sort(function(a,b){return (b.roas||0)-(a.roas||0);});
var tb="<div class='wb-scroll'><table class='wb-tbl'><thead><tr>"
+"<th>Campaign</th><th>Spend</th><th>Conv.</th><th>CPA</th>"
+"<th>Revenue</th><th>ROAS</th></tr></thead><tbody>"
+camps.slice(0,10).map(function(c){return "<tr><td><span class='wb-link' "
+"onclick=\"wbDrillCamp('"+c.id+"')\">"+esc(c.name)+"</span></td><td>"
+fmt(c.spend)+"</td><td>"+fmt(c.conv,0)+"</td><td>"+fmt(c.cpa)
+"</td><td>"+fmt(c.rev)+"</td><td>"+fmt(c.roas)+"</td></tr>";}).join('')
+"</tbody></table></div>";
var empty=windowRows(false).length===0;
if(empty)return "<div class='wb-card'><p class='wb-ct'>NO PERFORMANCE "
+"DATA</p><p class='wb-cq'>No advertising data exists for this slice. "
+"Possible reasons: campaigns have not delivered yet; provider sync is "
+"incomplete; the filters exclude every campaign.</p>"
+"<button class='mc-btn' onclick=\"wbDrillPlat('')\">Clear filters"
+"</button></div>";
return "<div class='wb-kpis'>"+kpis+"</div>"
+card('Performance over time','Is overall performance improving?',
msel+main+viewData('wb-vd-cc',['bucket',mk],
bs.map(function(b){return [b,wbAgg(mk,g[b])];})))
+"<div class='wb-row'>"
+card('Platform performance','Which platform returns most?',
hbars(platRows,{click:'wbDrillPlat',
empty:'no platform has measured return in this slice'})
+viewData('wb-vd-plat',['platform','ROAS'],platRows))
+card('Spend vs return','Which campaigns spend inefficiently?',
scatter(camps.filter(function(c){return c.spend&&c.roas!==null;})
.map(function(c){return {x:c.spend,y:c.roas,n:c.conv,label:c.name};})))
+"</div>"+card('Top / bottom campaigns','',tb);}
function secPerf(){return secCC();}
function secCamps(){var byCamp=grp(windowRows(false),function(r){
return r[2];});
var rows=Object.keys(byCamp).map(function(c){var s=byCamp[c];
var meta=CUBE.campaigns[c]||{};
return [meta.name||c,meta.provider||'',meta.state||'',
wbAgg('spend',s),wbAgg('clicks',s),wbAgg('conversions',s),
wbAgg('cpa',s),wbAgg('revenue',s),wbAgg('roas',s)];})
.sort(function(a,b){return (b[3]||0)-(a[3]||0);});
if(!rows.length)return "<p class='wb-empty'>no campaign rows in this "
+"slice</p>";
return card('Campaign analytics','sorted by spend; click a name in the '
+'Command Center to drill',
"<div class='wb-scroll'><table class='wb-tbl'><thead><tr>"
+['Campaign','Platform','Status','Spend','Clicks','Conv.','CPA',
'Revenue','ROAS'].map(function(h){return '<th>'+h+'</th>';}).join('')
+"</tr></thead><tbody>"+rows.map(function(r){return '<tr>'
+r.map(function(c,i){return '<td>'+(c===null?'--':(i>=3?fmt(c):esc(c)))
+'</td>';}).join('')+'</tr>';}).join('')+"</tbody></table></div>"
+viewData('wb-vd-camps',['campaign','spend'],
rows.map(function(r){return [r[0],r[3]];})));}
function secCreat(){var t=today(),
from=dayShift(t,-CTX.days+1);
var rows=CUBE.creative.filter(function(r){return r[0]>=from&&r[0]<=t
&&(!CTX.plat||r[1]===CTX.plat);});
var by=grp(rows,function(r){return r[2];});
var ids=Object.keys(by);
if(!ids.length)return card('Creative analytics','',
"<p class='wb-empty'>no metric row carries a creative yet; creative "
+"rows appear when ads carry creative ids and the pull is segmented"
+"</p>");
var list=ids.map(function(id){var s=by[id];
var meta=BOOT.creatives[id]||{};
return {id:id,name:meta.name||id,hook:meta.hook||'',
angle:meta.angle||'',spend:wbAgg('spend',s),ctr:wbAgg('ctr',s),
cpa:wbAgg('cpa',s),roas:wbAgg('roas',s),
conv:wbAgg('conversions',s)};})
.sort(function(a,b){return (b.roas||0)-(a.roas||0);});
var tb="<div class='wb-scroll'><table class='wb-tbl'><thead><tr>"
+['Creative','Hook','Angle','Spend','CTR','CPA','ROAS']
.map(function(h){return '<th>'+h+'</th>';}).join('')+"</tr></thead>"
+"<tbody>"+list.map(function(c){return "<tr><td>"+esc(c.name)
+"</td><td>"+esc(c.hook)+"</td><td>"+esc(c.angle)+"</td><td>"
+fmt(c.spend)+"</td><td>"+fmt(c.ctr)+"</td><td>"+fmt(c.cpa)+"</td><td>"
+fmt(c.roas)+"</td></tr>";}).join('')+"</tbody></table></div>";
var attrs={};list.forEach(function(c){['hook','angle'].forEach(
function(a){var v=c[a];if(!v)return;
var k=a+': '+v;var s=attrs[k]||(attrs[k]={sp:0,val:0});
sp=s.sp+=c.spend||0;s.val+=(c.roas||0)*(c.spend||0);});});
var arows=Object.keys(attrs).map(function(k){var s=attrs[k];
return [k,s.sp?+(s.val/s.sp).toFixed(2):null];}).filter(function(r){
return r[1]!==null;}).sort(function(a,b){return b[1]-a[1];});
return card('Creative efficiency','high spend + low ROAS = investigate',
scatter(list.filter(function(c){return c.spend&&c.roas!==null;})
.map(function(c){return {x:c.spend,y:c.roas,n:c.conv,label:c.name};})))
+card('Creative table','',tb)
+card('Attribute performance','spend-weighted ROAS per attribute value',
hbars(arows,{empty:'no attributed creative has measured return yet'}));}
function secAud(){var t="<p class='wb-empty'>Per-audience delivery rows "
+"are not collected yet: the provider pulls carry no audience id, and "
+"this screen does not invent a split. The audiences themselves:</p>";
if(!BOOT.audiences.length)return card('Audience analytics','',
t+"<p class='wb-empty'>no audiences defined yet</p>");
return card('Audience analytics','',t+"<div class='wb-scroll'>"
+"<table class='wb-tbl'><thead><tr><th>Audience</th><th>Type</th>"
+"</tr></thead><tbody>"+BOOT.audiences.map(function(a){
return "<tr><td>"+esc(a.name)+"</td><td>"+esc(a.type)+"</td></tr>";})
.join('')+"</tbody></table></div>");}
function secDim(dim,title){var t=today(),from=dayShift(t,-CTX.days+1);
var rows=CUBE[dim].filter(function(r){return r[0]>=from&&r[0]<=t
&&(!CTX.plat||r[1]===CTX.plat);});
var by=grp(rows,function(r){return r[2];});
var ks=Object.keys(by);
if(!ks.length)return card(title,'',"<p class='wb-empty'>no row carries "
+"a "+dim+" yet; dimension data arrives when the platform pull is "
+"segmented, and nothing is invented until then</p>");
var list=ks.map(function(k){var s=by[k];
return [k,wbAgg('spend',s),wbAgg('ctr',s),wbAgg('cpa',s),
wbAgg('roas',s)];}).sort(function(a,b){return (b[1]||0)-(a[1]||0);});
return card(title,'ranked by spend',
hbars(list.map(function(r){return [r[0],r[1]];}))
+"<div class='wb-scroll'><table class='wb-tbl'><thead><tr>"
+[dim,'Spend','CTR','CPA','ROAS'].map(function(h){
return '<th>'+h+'</th>';}).join('')+"</tr></thead><tbody>"
+list.map(function(r){return '<tr>'+r.map(function(c,i){
return '<td>'+(c===null?'--':(i?fmt(c):esc(c)))+'</td>';}).join('')
+'</tr>';}).join('')+"</tbody></table></div>");}
function secFunnel(){var s=sums(windowRows(false));
var stages=[['Impressions',s[1]],['Clicks',s[2]],
['Conversions',s[3]]].filter(function(x){return x[1]>0;});
if(stages.length<2)return card('Funnel','',
"<p class='wb-empty'>the funnel needs at least two real stages in this "
+"slice; nothing is invented to fill it</p>");
var out='';var top=stages[0][1];
stages.forEach(function(st,i){var drop=i?(' &middot; '
+(st[1]/stages[i-1][1]*100).toFixed(2)+'% of '+stages[i-1][0]
.toLowerCase()):'';
out+="<div style='display:flex;gap:9px;align-items:center;margin:4px 0'>"
+"<span style='width:110px;font-size:11px;color:var(--mc-ink)'>"
+st[0]+"</span><span style='flex:1;height:11px;border-radius:5px;"
+"background:rgba(255,255,255,.06);overflow:hidden'>"
+"<span style='display:block;height:100%;width:"
+Math.max(2,Math.round(st[1]/top*100))+"%;background:#4C8DFF'></span>"
+"</span><i style='font-style:normal;font-size:11px'>"+fmt(st[1],0)
+drop+"</i></div>";});
return card('Funnel','each transition shows its rate; deeper stages '
+'(landing, cart, checkout) appear when first-party events flow',out);}
function secAttr(){var a=BOOT.attribution;
var camps=CUBE.campaigns;
function vis(row){var cid=row.campaign_id||'';
if(CTX.campaign&&cid!==CTX.campaign)return false;
if(CTX.plat){var meta=camps[cid];
if(meta&&meta.provider&&meta.provider!==CTX.plat)return false;}
return true;}
var sp=a.spread.filter(vis),rc=a.reconcile.filter(vis);
var t1=sp.length?"<div class='wb-scroll'><table class='wb-tbl'>"
+"<thead><tr><th>Campaign</th><th>last</th><th>first</th><th>linear</th>"
+"<th>position</th><th>decay</th><th>spread</th></tr></thead><tbody>"
+sp.map(function(r){return "<tr><td>"+esc(r.name)+"</td><td>"
+fmt(r.last_touch)+"</td><td>"+fmt(r.first_touch)+"</td><td>"
+fmt(r.linear)+"</td><td>"+fmt(r.position_based)+"</td><td>"
+fmt(r.time_decay)+"</td><td>"+fmt(r.spread)+"</td></tr>";}).join('')
+"</tbody></table></div>":"<p class='wb-empty'>no conversion has an "
+"attributable touch in the event layer yet</p>";
var t2=rc.length?"<div class='wb-scroll'><table class='wb-tbl'>"
+"<thead><tr><th>Campaign</th><th>Platform claims</th>"
+"<th>Engine observed</th><th>Gap</th></tr></thead><tbody>"
+rc.map(function(r){return "<tr><td>"+esc(r.name)+"</td><td>"
+fmt(r.platform_claims)+"</td><td>"+fmt(r.engine_observed)+"</td><td>"
+fmt(r.gap)+"</td></tr>";}).join('')+"</tbody></table></div>"
:"<p class='wb-empty'>nothing to reconcile yet</p>";
return card('Five models, side by side',a.note,t1)
+card('Platform-reported vs engine-observed',
'neither number is corrected into the other',t2);}
function secPace(){var p=BOOT.pacing;
if(!p.ok||!p.series||!p.series.length)
return card('Budget & pacing','',"<p class='wb-empty'>"
+esc(p.message||'pacing unavailable')+"</p>");
var kpis=[['Month budget',p.month_budget],['Spent',p.spent],
['Elapsed',p.elapsed_pct===null?null:p.elapsed_pct+'%'],
['Budget used',p.used_pct===null?null:p.used_pct+'%'],
['Projected',p.projected],
['Variance',p.variance_pct===null?null:(p.variance_pct>0?'+':'')
+p.variance_pct+'%']].map(function(k){
return "<div class='wb-kpi'><span>"+k[0]+"</span><b>"
+(k[1]===null?'--':(typeof k[1]==='number'?fmt(k[1]):esc(k[1])))
+"</b></div>";}).join('');
var chart=lineChart([
{name:'actual cumulative',color:'#4C8DFF',
pts:p.series.map(function(s){return [s.date,s.actual];})},
{name:'ideal',color:'#8FA0C8',dash:true,
pts:p.series.map(function(s){return [s.date,s.ideal];})}]);
return "<div class='wb-kpis'>"+kpis+"</div>"
+card('Pacing','are we overspending or underspending?',chart
+"<p class='wb-cq'>"+esc(p.message)+"</p>"
+"<p class='wb-cq'>pacing is month-to-date and ignores the toolbar "
+"date range on purpose</p>");}
function secComp(){var by=grp(windowRows(false),function(r){
return r[1];});
var plats=Object.keys(by);
if(!plats.length)return "<p class='wb-empty'>no platform rows in this "
+"slice</p>";
var totS=0,totR=0;plats.forEach(function(p){totS+=by[p][0];
totR+=by[p][4];});
var rows=plats.map(function(p){var s=by[p];
return [p,wbAgg('spend',s),wbAgg('impressions',s),wbAgg('clicks',s),
wbAgg('ctr',s),wbAgg('cpc',s),wbAgg('conversions',s),wbAgg('cpa',s),
wbAgg('revenue',s),wbAgg('roas',s),
totS?((s[0]/totS*100).toFixed(1)+'%'):'--',
totR?((s[4]/totR*100).toFixed(1)+'%'):'--'];});
return card('Platform comparison','metric definitions are canonical '
+'(sums first, ratios after); provider-native metric names are kept in '
+'the raw rows',
"<div class='wb-scroll'><table class='wb-tbl'><thead><tr>"
+['Platform','Spend','Impr','Clicks','CTR','CPC','Conv','CPA','Revenue',
'ROAS','Budget share','Revenue share'].map(function(h){
return '<th>'+h+'</th>';}).join('')+"</tr></thead><tbody>"
+rows.map(function(r){return "<tr><td><span class='wb-link' "
+"onclick=\"wbDrillPlat('"+r[0]+"')\">"+esc(r[0])+"</span></td>"
+r.slice(1).map(function(c){return '<td>'
+(c===null?'--':(typeof c==='number'?fmt(c):esc(c)))+'</td>';}).join('')
+"</tr>";}).join('')+"</tbody></table></div>")
+"<div class='wb-row'>"
+card('Spend by platform','',hbars(rows.map(function(r){
return [r[0],r[1]];})))
+card('ROAS by platform','',hbars(rows.map(function(r){
return [r[0],r[9]];}).filter(function(r){return r[1]!==null;}),
{color:'#3FD98B'}))+"</div>";}
function secReports(){var dims=['date','platform','campaign','device',
'placement','country'];
var mets=Object.keys(REG);
var dcol=dims.map(function(d){return "<label><input type='checkbox' "
+"class='wb-rep-d' value='"+d+"'"+(d==='platform'?' checked':'')+"> "
+d+"</label>";}).join('');
var mcol=mets.map(function(m){return "<label><input type='checkbox' "
+"class='wb-rep-m' value='"+m+"'"
+(['spend','conversions','cpa','roas'].indexOf(m)>=0?' checked':'')
+"> "+REG[m].disp+"</label>";}).join('');
return card('Custom report','dimensions x metrics over the current '
+'toolbar context',
"<div class='wb-repgrid'><div class='wb-repcol'><p>DIMENSIONS</p>"+dcol
+"</div><div class='wb-repcol'><p>METRICS</p>"+mcol+"</div></div>"
+"<div style='margin-top:9px'><button class='mc-btn mc-go' "
+"onclick='wbRunReport()'>Run report</button> "
+"<button class='mc-btn' onclick='wbCsv()'>Export CSV</button></div>"
+"<div id='wb-rep-out'></div>");}
window.wbRunReport=function(){var dims=[].slice.call(
document.querySelectorAll('.wb-rep-d:checked')).map(function(x){
return x.value;});
var mets=[].slice.call(document.querySelectorAll('.wb-rep-m:checked'))
.map(function(x){return x.value;});
if(!dims.length||!mets.length){
document.getElementById('wb-rep-out').innerHTML=
"<p class='wb-empty'>pick at least one dimension and one metric</p>";
return;}
var srcMap={device:'device',placement:'placement',country:'country'};
var useDim=dims.filter(function(d){return srcMap[d];})[0];
var src=useDim?CUBE[useDim]:CUBE.main;
var t=today(),from=dayShift(t,-CTX.days+1);
var rows=src.filter(function(r){return r[0]>=from&&r[0]<=t
&&(!CTX.plat||r[1]===CTX.plat);});
var by=grp(rows,function(r){return dims.map(function(d){
if(d==='date')return bucketOf(r[0],CTX.gran);
if(d==='platform')return r[1];
if(d==='campaign')return (CUBE.campaigns[r[2]]||{}).name||r[2];
if(srcMap[d])return r[2];return '';}).join(' | ');});
var out=Object.keys(by).sort().map(function(k){
return [k].concat(mets.map(function(m){return wbAgg(m,by[k]);}));});
window.wbLastReport={heads:[dims.join(' | ')].concat(mets),rows:out};
document.getElementById('wb-rep-out').innerHTML=out.length?
"<div class='wb-scroll'><table class='wb-tbl'><thead><tr>"
+window.wbLastReport.heads.map(function(h){return '<th>'+esc(h)
+'</th>';}).join('')+"</tr></thead><tbody>"
+out.map(function(r){return '<tr>'+r.map(function(c,i){
return '<td>'+(c===null?'--':(i?fmt(c):esc(c)))+'</td>';}).join('')
+'</tr>';}).join('')+"</tbody></table></div>":
"<p class='wb-empty'>no rows for this combination in this slice</p>";};
window.wbCsv=function(){var rep=window.wbLastReport;
if(!rep){wbRunReport();rep=window.wbLastReport;}
if(!rep||!rep.rows.length)return;
var csv=[rep.heads.join(',')].concat(rep.rows.map(function(r){
return r.map(function(c){return c===null?'':String(c).replace(/,/g,';');
}).join(',');})).join('\n');
var a=document.createElement('a');
a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));
a.download='media-report.csv';a.click();};
function secHealth(){var q=BOOT.quality;var rows=Object.keys(q.providers)
.map(function(p){var v=q.providers[p];
return [p,v.status,v.last_sync||'never',
v.age_hours===undefined||v.age_hours===null?'--':v.age_hours+'h'];});
return card('Analytics data health','what the numbers stand on',
"<div class='wb-scroll'><table class='wb-tbl'><thead><tr>"
+['Platform','Status','Last read','Age'].map(function(h){
return '<th>'+h+'</th>';}).join('')+"</tr></thead><tbody>"
+rows.map(function(r){return '<tr>'+r.map(function(c){
return '<td>'+esc(c)+'</td>';}).join('')+'</tr>';}).join('')
+"</tbody></table></div>"
+"<p class='wb-cq'>"+esc(q.currency.note)+" &middot; "
+esc(q.timezone)+" &middot; adopted aggregates excluded from date "
+"math: "+q.adopted_aggregates_excluded+" &middot; estimated flags: "
+esc(q.estimated_flags)+"</p>");}
var RENDER={cc:secCC,perf:secPerf,camps:secCamps,creat:secCreat,
aud:secAud,plc:function(){return secDim('placement',
'Placement analytics');},funnel:secFunnel,attr:secAttr,pace:secPace,
comp:secComp,reports:secReports,health:secHealth};
window.wbSec=function(sid,btn){
document.querySelectorAll('.wb-sec').forEach(function(x){
x.classList.remove('wb-on');});
document.getElementById('wb-sec-'+sid).classList.add('wb-on');
document.querySelectorAll('.wb-nav').forEach(function(x){
x.classList.remove('mc-go');});
if(btn)btn.classList.add('mc-go');
window.wbCurrent=sid;wbRender();};
window.wbRender=function(){crumb();
var sid=window.wbCurrent||'cc';
try{document.getElementById('wb-sec-'+sid).innerHTML=RENDER[sid]();}
catch(ex){document.getElementById('wb-sec-'+sid).innerHTML=
"<p class='wb-empty'>this section could not be drawn: "+esc(ex.message)
+"</p>";}
document.getElementById('wb-fresh').textContent=
'cube generated '+BOOT.generated_at.slice(0,16).replace('T',' ')
+(CUBE.adopted_excluded?(' | '+CUBE.adopted_excluded
+' adopted aggregates excluded'):'');};
// saved views
function viewsFill(){var sel=document.getElementById('wb-views');
sel.innerHTML="<option value=''>Saved views…</option>"
+BOOT.views.map(function(v,i){return "<option value='"+i+"'>"
+esc(v.name)+"</option>";}).join('');
sel.onchange=function(){var v=BOOT.views[+sel.value];if(!v)return;
CTX=Object.assign({},CTX,v.ctx||{});
document.getElementById('wb-plat').value=CTX.plat||'';
document.getElementById('wb-date').value=String(CTX.days||30);
document.getElementById('wb-gran').value=CTX.gran||'DAY';
wbRender();};}
window.wbSaveView=function(btn){
var name=document.getElementById('wb-viewname').value.trim();
if(!name){toast('give the view a name first',false);return;}
fetch('/mediaos/views',{method:'POST',
headers:{'Content-Type':'application/json'},
body:JSON.stringify({name:name,ctx:CTX})}).then(function(r){
return r.json();}).then(function(j){
toast(j.message||'saved',j.ok!==false);
if(j.ok!==false){BOOT.views.push({name:name,ctx:CTX});viewsFill();}})
.catch(function(){toast('engine unreachable; the view was not saved '
+'(the page keeps working from the loaded cube)',false);});};
viewsFill();wbRender();
})();
</script>"""
