"""V9 positive-control tab for the V9-only dashboard."""

V9_RESULTS_NAV_BTN = '  <button data-tab="v9Results">V9 Results</button>\n'
V9_RESULTS_SECTION = '  <section id="tab-v9Results" class="tab-content"></section>\n'

V9_RESULTS_CSS = r"""
#tab-v9Results{padding:16px;max-width:1120px}
#tab-v9Results h2{margin:0 0 6px;font-size:18px;color:var(--text1)}
#tab-v9Results .v9-sub{color:var(--text3);font-size:12px;margin-bottom:18px;max-width:860px;line-height:1.55}
#tab-v9Results .v9-grid{display:grid;grid-template-columns:1.15fr .85fr;gap:18px;margin-top:18px}
@media(max-width:900px){#tab-v9Results .v9-grid{grid-template-columns:1fr}}
#tab-v9Results .v9-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;min-width:0;overflow:hidden}
#tab-v9Results .v9-card h3{margin:0 0 4px;font-size:12px;color:var(--text1)}
#tab-v9Results .v9-hint{font-size:10px;color:var(--text3);margin-bottom:10px}
#tab-v9Results .v9-seg{display:inline-flex;border:1px solid var(--border-strong);border-radius:8px;overflow:hidden;margin:8px 0 14px}
#tab-v9Results .v9-seg button{background:var(--surface);color:var(--text2);border:0;border-right:1px solid var(--border-strong);font:inherit;font-size:11px;padding:7px 10px;cursor:pointer}
#tab-v9Results .v9-seg button:last-child{border-right:0}
#tab-v9Results .v9-seg button.on{background:var(--accent-soft);color:var(--accent)}
#tab-v9Results table{border-collapse:collapse;width:100%;font-size:12px}
#tab-v9Results th,#tab-v9Results td{border-bottom:1px solid var(--border);padding:8px 7px;text-align:right;white-space:nowrap}
#tab-v9Results th:first-child,#tab-v9Results td:first-child{text-align:left}
#tab-v9Results thead th{color:var(--text3);font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:.04em}
#tab-v9Results td.best{color:var(--accent);font-weight:700}
#tab-v9Results td.bad{color:#e77}
#tab-v9Results .v9-bars{display:grid;gap:9px}
#tab-v9Results .v9-bar-row{display:grid;grid-template-columns:52px 1fr 68px;gap:10px;align-items:center;font-size:11px;color:var(--text2)}
#tab-v9Results .v9-track{height:9px;background:var(--elevated);border:1px solid var(--border);border-radius:999px;overflow:hidden}
#tab-v9Results .v9-fill{height:100%;background:var(--accent)}
#tab-v9Results .v9-fill.base{background:#64748b}
#tab-v9Results .v9-pill{display:inline-block;border-radius:999px;padding:2px 8px;font-size:10px;font-weight:600}
#tab-v9Results .v9-pill.win{background:rgba(16,185,129,.14);color:var(--accent)}
#tab-v9Results .v9-pill.tie{background:rgba(139,139,150,.18);color:var(--text2)}
#tab-v9Results .v9-pill.loss{background:rgba(239,68,68,.16);color:#e77}
#tab-v9Results .v9-model-list{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
@media(max-width:900px){#tab-v9Results .v9-model-list{grid-template-columns:1fr}}
#tab-v9Results .v9-model-note{border:1px solid var(--border);border-radius:8px;padding:10px;background:var(--elevated)}
#tab-v9Results .v9-model-note b{display:block;font-size:12px;color:var(--text1);margin-bottom:5px}
#tab-v9Results .v9-model-note p{font-size:11px;line-height:1.45;color:var(--text2);margin:6px 0 0}
"""

V9_RESULTS_JS = r"""v9Results:{rendered:false,render(){
  if(this.rendered) return; this.rendered=true;
  const sec=document.getElementById('tab-v9Results');
  const demo=(typeof DATA!=='undefined'&&DATA)?DATA.v9Demo:null;
  if(!demo){sec.innerHTML='<div class="v9-card">No V9 demo result is embedded in data_v9.json.</div>';return;}

  const ks=Object.keys(demo.overall.baseline)
    .filter(k=>k.startsWith('found@')).map(k=>Number(k.slice(6))).sort((a,b)=>a-b);
  const fmt=n=>Number(n||0).toLocaleString();
  const pct=v=>(Number(v||0)*100).toFixed(1)+'%';
  const found=(pop,arm,k)=>{
    const src=pop==='observable'?demo.stratified[arm].observable:demo.overall[arm];
    return Number(src['found@'+k]||0);
  };
  const recall=(pop,arm,k)=>{
    const src=pop==='observable'?demo.stratified[arm].observable:demo.overall[arm];
    return Number(src['recall@'+k]||0);
  };
  const precision=(arm,k)=>Number((demo.overall[arm]||{})['precision@'+k]||0);
  const f1=(arm,k)=>Number((demo.overall[arm]||{})['f1@'+k]||0);
  const hidden=pop=>pop==='observable'?demo.stratum_hidden.observable:demo.hidden_total;
  const win=pop=>pop==='observable'?demo.win_observable:demo.win_whole_pool;
  const winKey=(pop,k)=>pop==='observable'?'gnn_vs_baseline_obs@'+k:'gnn_vs_baseline@'+k;
  const seizureRate=DATA.overview&&DATA.overview.outcome_rates?DATA.overview.outcome_rates.seizure:null;
  const preferredArms=['baseline','baseline_logistic','baseline_history','gnn_cotravel_only','gnn_rgcn_2rel','gnn'];
  const armOrder=preferredArms.filter(a=>demo.overall&&demo.overall[a]);
  const armMeta=demo.model_arms||{};
  const compareKs=[500,2000].filter(k=>ks.includes(k));
  if(!compareKs.length&&ks.length) compareKs.push(ks[ks.length-1]);
  const runLabel=(demo.gnn_seeds?demo.gnn_seeds.length:0)+' seed(s), '+(demo.epochs||'-')+' epochs, bucket '+(demo.train_bucket||'-');
  let pop='observable';

  sec.innerHTML='<h2>V9 Positive Control</h2>'
    +'<div class="v9-sub">V9 detection positive-control result. The baselines use leak-safe own-history and context features; the GNN arms add as-of caught-propagation over graph relations such as COTRAVEL, RESIDENCE, SHARED_PLATE, and SHARED_PLATE_HOT.</div>'
    +'<div id="v9-metrics"></div>'
    +'<div class="v9-card" style="margin-top:18px"><h3>What The Models Look For</h3><div class="v9-hint">Baselines only see the target person/event row. GNN arms pass messages over as-of graph edges before the scored event date.</div><div id="v9-model-notes"></div></div>'
    +'<div class="v9-card" style="margin-top:18px"><h3>Model Comparison</h3><div class="v9-hint">Top-K precision, recall, and F1 on the same V9 hidden-carrier test pool.</div><div id="v9-model-table"></div></div>'
    +'<div class="v9-seg" id="v9-pop"><button data-v="observable" class="on">Observable slice</button><button data-v="pool">Whole pool</button></div>'
    +'<div class="v9-grid">'
    +'<div class="v9-card"><h3>Found@K</h3><div class="v9-hint">Hidden carriers recovered in the global top-K ranking.</div><div id="v9-table"></div></div>'
    +'<div class="v9-card"><h3>Depth Recall</h3><div class="v9-hint">Baseline versus GNN as share of hidden carriers in the selected population.</div><div id="v9-bars"></div></div>'
    +'</div>'
    +'<div class="v9-card" style="margin-top:18px"><h3>Bootstrap Verdicts</h3><div class="v9-hint">Paired event-bootstrap difference: GNN found@K minus baseline found@K.</div><div id="v9-sig"></div></div>';

  makeMetrics(document.getElementById('v9-metrics'),[
    {l:'test pool',v:fmt(demo.pool_size),s:'detected events excluded'},
    {l:'hidden carriers',v:fmt(demo.hidden_total),s:'false-negative test events'},
    {l:'observable carriers',v:fmt(demo.stratum_hidden.observable),s:'findable cell slice'},
    {l:'seizure rate',v:seizureRate==null?'-':pct(seizureRate),s:'corpus outcome rate'},
    {l:'GNN run',v:runLabel,s:'settings recorded in JSON'},
  ]);

  function drawModelNotes(){
    document.getElementById('v9-model-notes').innerHTML='<div class="v9-model-list">'+armOrder.map(a=>{
      const meta=armMeta[a]||{};
      const kind=meta.kind||((a.indexOf('gnn')===0)?'gnn':'baseline');
      const label=meta.label||a;
      const text=meta.looks_for||'No model description provided.';
      return '<div class="v9-model-note"><b>'+esc(label)+'</b><span class="v9-pill '+(kind==='gnn'?'win':'tie')+'">'+esc(kind)+'</span><p>'+esc(text)+'</p></div>';
    }).join('')+'</div>';
  }

  function drawModelTable(){
    let h='<table><thead><tr><th>model</th><th>kind</th>';
    compareKs.forEach(k=>{h+='<th>P@'+fmt(k)+'</th><th>R@'+fmt(k)+'</th><th>F1@'+fmt(k)+'</th>';});
    h+='</tr></thead><tbody>';
    armOrder.forEach(a=>{
      const meta=armMeta[a]||{};
      const kind=meta.kind||((a.indexOf('gnn')===0)?'gnn':'baseline');
      h+='<tr><td>'+esc(meta.label||a)+'</td><td>'+esc(kind)+'</td>';
      compareKs.forEach(k=>{
        h+='<td>'+pct(precision(a,k))+'</td><td>'+pct(recall('pool',a,k))+'</td><td>'+pct(f1(a,k))+'</td>';
      });
      h+='</tr>';
    });
    h+='</tbody></table>';
    document.getElementById('v9-model-table').innerHTML=h;
  }

  document.getElementById('v9-pop').addEventListener('click',e=>{
    const b=e.target.closest('button'); if(!b) return;
    pop=b.dataset.v;
    sec.querySelectorAll('#v9-pop button').forEach(x=>x.classList.toggle('on',x===b));
    draw();
  });

  function pill(summary){
    if(!summary) return '<span class="v9-pill tie">n/a</span>';
    const lo=Number(summary.ci[0]), hi=Number(summary.ci[1]);
    if(lo>0) return '<span class="v9-pill win">GNN win</span>';
    if(hi<0) return '<span class="v9-pill loss">baseline win</span>';
    return '<span class="v9-pill tie">wash</span>';
  }

  function drawTable(){
    let h='<table><thead><tr><th>K</th><th>baseline</th><th>GNN</th><th>delta</th><th>GNN recall</th></tr></thead><tbody>';
    ks.forEach(k=>{
      const b=found(pop,'baseline',k), g=found(pop,'gnn',k), d=g-b;
      h+='<tr><td>'+fmt(k)+'</td><td>'+(b===Math.max(b,g)?'<span class="best">'+fmt(b)+'</span>':fmt(b))+'</td>'
        +'<td>'+(g===Math.max(b,g)?'<span class="best">'+fmt(g)+'</span>':fmt(g))+'</td>'
        +'<td class="'+(d<0?'bad':'best')+'">'+(d>0?'+':'')+fmt(d)+'</td>'
        +'<td>'+pct(recall(pop,'gnn',k))+'</td></tr>';
    });
    h+='</tbody></table>';
    document.getElementById('v9-table').innerHTML=h;
  }

  function drawBars(){
    const k=ks.includes(5000)?5000:ks[ks.length-1];
    const total=hidden(pop)||1;
    const vals=[['baseline',found(pop,'baseline',k),'base'],['GNN',found(pop,'gnn',k),'']];
    document.getElementById('v9-bars').innerHTML='<div class="v9-bars">'+vals.map(([label,val,cls])=>{
      const w=Math.max(2,Math.round(val/total*100));
      return '<div class="v9-bar-row"><span>'+label+'</span><div class="v9-track"><div class="v9-fill '+cls+'" style="width:'+w+'%"></div></div><b>'+fmt(val)+' / '+fmt(total)+'</b></div>';
    }).join('')+'</div>';
  }

  function drawSig(){
    const wins=win(pop)||{};
    let h='<table><thead><tr><th>K</th><th>mean diff</th><th>95% CI</th><th>p(GNN&lt;=base)</th><th>verdict</th></tr></thead><tbody>';
    ks.forEach(k=>{
      const s=wins[winKey(pop,k)];
      if(!s) return;
      h+='<tr><td>'+fmt(k)+'</td><td class="'+(s.mean_diff<0?'bad':'best')+'">'+(s.mean_diff>0?'+':'')+s.mean_diff+'</td>'
        +'<td>['+s.ci[0]+', '+s.ci[1]+']</td><td>'+s.p_enh_le_base+'</td><td>'+pill(s)+'</td></tr>';
    });
    h+='</tbody></table>';
    document.getElementById('v9-sig').innerHTML=h;
  }

  drawModelNotes();
  drawModelTable();
  function draw(){drawTable();drawBars();drawSig();}
  draw();
}},
"""
