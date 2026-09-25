"""Build a self-contained interactive explorer (single HTML) from sweep.csv."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

COLS = ["architecture", "alt_km", "solar", "intake_area_m2", "accommodation", "comp_ratio", "active_ratio",
        "vd_V", "mdot_air_mgps", "p_in_Pa", "eta_u_air", "T_air_mN", "Isp_air_s", "T_over_D_air",
        "P_total_air_W", "P_total_peak_W", "m_total_kg", "xe_total_kg", "ic_total", "ic_thruster",
        "life_margin", "O_survival", "feasible", "rfp_compliant", "abep_closed", "technical_compliant", "technical_closed", "chk_thrust_air_ge_req", "chk_power_air", "chk_power_peak", "chk_mass",
        "chk_life", "chk_ic_total", "chk_ic_thruster"]

TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>ABEP design-space explorer — DTDF/06/13516</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{--bg:#f7f7f5;--fg:#1a1a1a;--mut:#666;--card:#fff;--line:#ddd;--acc:#4259A1;--ok:#1CAB98;--bad:#c0392b;
box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
html{scroll-padding-top:env(safe-area-inset-top,0px)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#111;--fg:#eee;--mut:#999;--card:#1c1c1c;--line:#333}}
:root[data-theme="dark"]{--bg:#111;--fg:#eee;--mut:#999;--card:#1c1c1c;--line:#333}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{padding:14px 18px;border-bottom:1px solid var(--line)} h1{font-size:18px;margin:0} .sub{color:var(--mut);font-size:12px}
main{display:grid;grid-template-columns:280px 1fr;gap:14px;padding:14px}
@media (max-width:900px){main{grid-template-columns:1fr}}
.panel{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
fieldset{border:0;padding:0;margin:0 0 10px} legend{font-weight:600;font-size:12px;color:var(--mut);margin-bottom:4px}
label.chk{display:block;font-size:13px} select,input{width:100%;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:4px;padding:4px}
.row{display:flex;gap:8px} .row>*{flex:1}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin:8px 0} .stat{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:6px 10px;font-size:12px}
.stat b{display:block;font-size:16px}
canvas{max-width:100%}
.tbl{overflow-x:auto;margin-top:12px} table{border-collapse:collapse;font-size:12px;min-width:900px} th,td{padding:4px 6px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap} th:first-child,td:first-child{text-align:left}
.ok{color:var(--ok)} .bad{color:var(--bad)}
.note{font-size:12px;color:var(--mut);margin-top:8px}
</style></head><body>
<header><h1>ABEP design-space explorer</h1><div class="sub">__N__ configurations · DRDO TDF DTDF/06/13516 · 12–25 mN · &lt;1.5 kW · &lt;40 kg · 180–230 km · N₂ + O · Xe · &gt;15,000 h · IC ≥ 75 %. Priors, not test data.</div></header>
<main>
<aside class="panel">
<fieldset><legend>Architecture</legend><div id="archs"></div></fieldset>
<fieldset><legend>Altitude</legend><div id="alts" class="row"></div></fieldset>
<fieldset><legend>Solar</legend><div id="solars" class="row"></div></fieldset>
<fieldset><legend>Compressor total ratio</legend><div id="crs" class="row"></div></fieldset>
<fieldset><legend>Discharge voltage</legend><div id="vds" class="row"></div></fieldset>
<fieldset><legend>Intake surface</legend><div id="accs" class="row"></div></fieldset>
<fieldset><legend>Show</legend>
<label class="chk"><input type="checkbox" id="feasOnly"> RFP-compliant only (incl. 12 mN sustained on air)</label>
<label class="chk"><input type="checkbox" id="closeOnly"> ABEP-closed only (RFP-compliant AND T &gt; D on air)</label>
<label class="chk"><input type="checkbox" id="ignoreIC"> technical only (ignore both IC checks)</label></fieldset>
<fieldset><legend>Axes</legend><div class="row"><select id="xsel"></select><select id="ysel"></select></div></fieldset>
<fieldset><legend>Rank table by</legend><select id="rank"></select></fieldset>
</aside>
<section class="panel">
<div class="stats" id="stats"></div>
<canvas id="chart" height="420"></canvas>
<div class="note">Green band = RFP thrust window; red line = RFP limit on that axis. Each point is one closed configuration. Hover for details.</div>
<div class="tbl"><table id="tbl"></table></div>
</section></main>
<script>
const DATA=__DATA__;
const NUM=["intake_area_m2","comp_ratio","active_ratio","vd_V","mdot_air_mgps","p_in_Pa","eta_u_air","T_air_mN","Isp_air_s","T_over_D_air","P_total_air_W","P_total_peak_W","m_total_kg","xe_total_kg","ic_total","ic_thruster","life_margin","O_survival"];
const LIM={T_air_mN:[12,25],P_total_air_W:[null,1500],P_total_peak_W:[null,1500],m_total_kg:[null,40],T_over_D_air:[1,null],ic_total:[0.75,null],ic_thruster:[0.80,null],life_margin:[1,null]};
const uniq=(k)=>[...new Set(DATA.map(d=>d[k]))].sort((a,b)=>a-b||String(a).localeCompare(String(b)));
const COLORS=["#4259A1","#1CAB98","#e67e22","#8e44ad","#c0392b","#2c3e50","#7f8c8d"];
function mkChecks(id,key,all=true){const el=document.getElementById(id);uniq(key).forEach(v=>{const l=document.createElement('label');l.className='chk';l.innerHTML=`<input type="checkbox" data-k="${key}" value="${v}" ${all?'checked':''}> ${v}`;el.appendChild(l)})}
mkChecks('archs','architecture');mkChecks('alts','alt_km');mkChecks('solars','solar');mkChecks('crs','comp_ratio');mkChecks('vds','vd_V');mkChecks('accs','accommodation');
for(const id of ['xsel','ysel','rank']){const s=document.getElementById(id);NUM.forEach(n=>{const o=document.createElement('option');o.value=n;o.textContent=n;s.appendChild(o)})}
document.getElementById('xsel').value='P_total_air_W';document.getElementById('ysel').value='T_air_mN';document.getElementById('rank').value='T_over_D_air';
function sel(key){return [...document.querySelectorAll(`input[data-k="${key}"]:checked`)].map(i=>i.value)}
function filt(){const a=sel('architecture'),al=sel('alt_km'),so=sel('solar'),cr=sel('comp_ratio'),vd=sel('vd_V'),ac=sel('accommodation');
const fo=feasOnly.checked,co=closeOnly.checked,ig=ignoreIC.checked;
return DATA.filter(d=>a.includes(d.architecture)&&al.includes(String(d.alt_km))&&so.includes(d.solar)&&cr.includes(String(d.comp_ratio))&&vd.includes(String(d.vd_V))&&ac.includes(String(d.accommodation))
&&(!fo||(ig?d.technical_compliant:d.rfp_compliant))&&(!co||(ig?d.technical_closed:d.abep_closed)))}
let chart;
function draw(){const rows=filt();const xk=xsel.value,yk=ysel.value;
const groups={};rows.forEach(r=>{(groups[r.architecture]??=[]).push({x:r[xk],y:r[yk],r})});
const ds=Object.keys(groups).sort().map((k,i)=>({label:k,data:groups[k],backgroundColor:COLORS[i%COLORS.length]+'99',pointRadius:3}));
const ann=[];const lx=LIM[xk],ly=LIM[yk];
if(chart)chart.destroy();
chart=new Chart(document.getElementById('chart'),{type:'scatter',data:{datasets:ds},options:{responsive:true,animation:false,
scales:{x:{title:{display:true,text:xk},type:xk==='p_in_Pa'||xk==='O_survival'?'logarithmic':'linear'},y:{title:{display:true,text:yk},type:yk==='p_in_Pa'||yk==='O_survival'?'logarithmic':'linear'}},
plugins:{tooltip:{callbacks:{label:c=>{const r=c.raw.r;return `${r.architecture} ${r.alt_km}km ${r.solar} A=${r.intake_area_m2}m² CR=${r.comp_ratio} Vd=${r.vd_V}V | T=${r.T_air_mN.toFixed(1)}mN Isp=${r.Isp_air_s.toFixed(0)}s P=${r.P_total_air_W.toFixed(0)}W m=${r.m_total_kg.toFixed(1)}kg T/D=${r.T_over_D_air.toFixed(2)} Xe=${r.xe_total_kg.toFixed(1)}kg IC=${r.ic_total.toFixed(2)}`}}},
legend:{position:'bottom'}}},
plugins:[{id:'lims',afterDraw(ch){const {ctx,chartArea:ca,scales:{x,y}}=ch;ctx.save();
if(ly&&ly[0]!=null&&ly[1]!=null){ctx.fillStyle='rgba(28,171,152,0.10)';const y1=y.getPixelForValue(ly[1]),y0=y.getPixelForValue(ly[0]);ctx.fillRect(ca.left,y1,ca.width,y0-y1)}
ctx.strokeStyle='#c0392b';ctx.setLineDash([5,4]);
for(const [L,ax,vert] of [[lx,x,true],[ly,y,false]]){if(!L)continue;for(const v of L){if(v==null)continue;const p=ax.getPixelForValue(v);ctx.beginPath();if(vert){ctx.moveTo(p,ca.top);ctx.lineTo(p,ca.bottom)}else{ctx.moveTo(ca.left,p);ctx.lineTo(ca.right,p)}ctx.stroke()}}
ctx.restore()}}]});
const feas=rows.filter(r=>r.rfp_compliant).length,tc=rows.filter(r=>r.technical_compliant).length,both=rows.filter(r=>r.abep_closed).length,tcl=rows.filter(r=>r.technical_closed).length;
stats.innerHTML=`<div class="stat">shown<b>${rows.length}</b></div><div class="stat">RFP-compliant<b>${feas}</b></div><div class="stat">technical-compliant (no IC)<b>${tc}</b></div><div class="stat">ABEP-closed<b>${both}</b></div><div class="stat">technical-closed<b>${tcl}</b></div>`;
const rk=rank.value;const top=[...rows].sort((a,b)=>b[rk]-a[rk]).slice(0,25);
const cols=["architecture","alt_km","solar","intake_area_m2","accommodation","comp_ratio","vd_V","mdot_air_mgps","p_in_Pa","eta_u_air","T_air_mN","Isp_air_s","T_over_D_air","P_total_air_W","P_total_peak_W","m_total_kg","xe_total_kg","ic_total","life_margin","rfp_compliant","abep_closed","technical_closed"];
const fmt=(k,v)=>typeof v==='number'?(k==='p_in_Pa'||k==='O_survival'?v.toExponential(2):(Math.abs(v)>=100?v.toFixed(0):v.toFixed(2))):(typeof v==='boolean'?`<span class="${v?'ok':'bad'}">${v?'yes':'no'}</span>`:v);
tbl.innerHTML='<tr>'+cols.map(c=>`<th>${c}</th>`).join('')+'</tr>'+top.map(r=>'<tr>'+cols.map(c=>`<td>${fmt(c,r[c])}</td>`).join('')+'</tr>').join('')}
document.querySelectorAll('input,select').forEach(e=>e.addEventListener('change',draw));draw();
</script></body></html>"""


def build(csv_path: str, out_html: str):
    df = pd.read_csv(csv_path)
    keep = [c for c in COLS if c in df.columns]
    recs = df[keep].round(6).to_dict(orient="records")
    html = TEMPLATE.replace("__DATA__", json.dumps(recs, separators=(",", ":"))).replace("__N__", str(len(df)))
    Path(out_html).write_text(html)
    return out_html


if __name__ == "__main__":
    import sys
    build(sys.argv[1], sys.argv[2])
