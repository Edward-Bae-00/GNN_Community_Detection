"""V9 positive-control tab for the V9-only dashboard."""

V9_RESULTS_NAV_BTN = '  <button data-tab="v9Results" aria-controls="tab-v9Results" aria-selected="false">V9 results</button>\n'
V9_RESULTS_SECTION = '  <section id="tab-v9Results" class="tab-content"></section>\n'

V9_RESULTS_CSS = r"""
#tab-v9Results { padding: 32px 24px; max-width: 1200px; font-family: var(--font-body); color: var(--text1); }
#tab-v9Results h2 { font-size: 24px; font-weight: 700; margin: 0 0 8px 0; letter-spacing: -0.02em; }
#tab-v9Results .v9-sub { color: var(--text2); font-size: 14px; margin-bottom: 32px; max-width: 720px; line-height: 1.6; }
#tab-v9Results .v9-summary { display: grid; grid-template-columns: minmax(0, 1.3fr) repeat(3, minmax(120px, .7fr)); gap: 12px; margin: 0 0 24px; }
#tab-v9Results .v9-summary-lead { background: linear-gradient(135deg, rgba(16,185,129,.16), rgba(16,185,129,.04)); border: 1px solid rgba(52,211,153,.35); border-radius: 12px; padding: 20px; min-width: 0; }
#tab-v9Results .v9-summary-kicker { color: var(--accent-hover); font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
#tab-v9Results .v9-summary-title { margin-top: 7px; color: var(--text1); font-size: 18px; font-weight: 700; letter-spacing: -.02em; line-height: 1.2; }
#tab-v9Results .v9-summary-copy { margin-top: 7px; color: var(--text2); font-size: 12px; line-height: 1.5; }
#tab-v9Results .v9-summary-link { display: inline-flex; margin-top: 14px; color: var(--accent-hover); font-size: 12px; font-weight: 600; text-decoration: none; }
#tab-v9Results .v9-summary-link:hover { text-decoration: underline; }
#tab-v9Results .v9-summary-stat { display: flex; flex-direction: column; justify-content: center; gap: 5px; background: var(--elevated); border: 1px solid var(--border); border-radius: 12px; padding: 16px; }
#tab-v9Results .v9-summary-stat b { color: var(--text1); font-family: var(--font-mono); font-size: 22px; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-summary-stat span { color: var(--text3); font-size: 10px; letter-spacing: .05em; text-transform: uppercase; }
#tab-v9Results .v9-story { margin: 24px 0; padding: 22px; border: 1px solid var(--border); border-radius: 12px; background: linear-gradient(135deg, rgba(79,120,144,.08), rgba(255,255,255,.02)); }
#tab-v9Results .v9-story-header { display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; margin-bottom: 18px; }
#tab-v9Results .v9-story-kicker { color: #4f7890; font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
#tab-v9Results .v9-story-title { margin: 6px 0 6px; color: var(--text1); font-size: 18px; font-weight: 700; letter-spacing: -.02em; line-height: 1.2; }
#tab-v9Results .v9-story-intro { max-width: 760px; margin: 0; color: var(--text2); font-size: 12px; line-height: 1.55; }
#tab-v9Results .v9-story-note { max-width: 230px; padding: 11px 13px; border-left: 3px solid #d28b57; color: var(--text2); font-size: 11px; line-height: 1.45; }
#tab-v9Results .v9-story-note b { display: block; margin-bottom: 4px; color: var(--text1); font-size: 12px; }
#tab-v9Results .v9-lens-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
#tab-v9Results .v9-lens { min-width: 0; padding: 15px; border: 1px solid var(--border); border-left: 3px solid #4f7890; border-radius: 9px; background: var(--surface); }
#tab-v9Results .v9-lens:nth-child(2) { border-left-color: #c97848; }
#tab-v9Results .v9-lens:nth-child(3) { border-left-color: #6a8f6b; }
#tab-v9Results .v9-lens h4 { margin: 0 0 7px; color: var(--text1); font-size: 13px; font-weight: 700; }
#tab-v9Results .v9-lens p { min-height: 58px; margin: 0; color: var(--text2); font-size: 12px; line-height: 1.5; }
#tab-v9Results .v9-lens-stat { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border); }
#tab-v9Results .v9-lens-stat b { display: block; color: var(--text1); font-family: var(--font-mono); font-size: 16px; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-lens-stat span { display: block; margin-top: 3px; color: var(--text3); font-size: 10px; line-height: 1.35; }
#tab-v9Results .v9-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; min-width: 0; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.02); }
#tab-v9Results .v9-card h3 { margin: 0 0 6px; font-size: 14px; font-weight: 600; color: var(--text1); letter-spacing: -0.01em; }
#tab-v9Results .v9-hint { font-size: 12px; color: var(--text3); margin-bottom: 20px; line-height: 1.5; }
#tab-v9Results .v9-seg { display: inline-flex; background: var(--elevated); border: 1px solid var(--border); border-radius: 8px; padding: 4px; margin: 12px 0 24px; }
#tab-v9Results .v9-seg button { background: transparent; color: var(--text2); border: 0; border-radius: 6px; font-weight: 500; font-size: 13px; padding: 6px 14px; cursor: pointer; transition: all 0.2s ease; }
#tab-v9Results .v9-seg button.on { background: var(--surface); color: var(--text1); box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
#tab-v9Results .v9-table-wrap { max-width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
#tab-v9Results table { border-collapse: collapse; width: 100%; font-size: 13px; font-variant-numeric: tabular-nums; }
#tab-v9Results th, #tab-v9Results td { border-bottom: 1px solid var(--border); padding: 12px 8px; text-align: right; white-space: nowrap; }
#tab-v9Results th:first-child, #tab-v9Results td:first-child { text-align: left; }
#tab-v9Results thead th { color: var(--text3); font-weight: 500; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; padding-bottom: 16px; border-bottom: 1px solid var(--border-strong); }
#tab-v9Results td.best { color: #10b981; font-weight: 600; }
#tab-v9Results td.bad { color: #ef4444; }
#tab-v9Results .v9-bars { display: grid; gap: 12px; }
#tab-v9Results .v9-bar-row { display: grid; grid-template-columns: 60px 1fr 70px; gap: 12px; align-items: center; font-size: 12px; color: var(--text2); font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-track { height: 6px; background: var(--elevated); border-radius: 999px; overflow: hidden; }
#tab-v9Results .v9-fill { height: 100%; background: #3b82f6; border-radius: 999px; }
#tab-v9Results .v9-fill.base { background: #94a3b8; }
#tab-v9Results .v9-pill { display: inline-flex; align-items: center; justify-content: center; border-radius: 999px; padding: 2px 8px; font-size: 10px; font-weight: 600; letter-spacing: 0.02em; text-transform: uppercase; }
#tab-v9Results .v9-pill.win { background: rgba(16,185,129,0.1); color: #059669; }
#tab-v9Results .v9-pill.tie { background: rgba(148,163,184,0.1); color: #64748b; }
#tab-v9Results .v9-pill.loss { background: rgba(239,68,68,0.1); color: #dc2626; }
#tab-v9Results .v9-model-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-top: 16px; }
#tab-v9Results .v9-model-note { border: 1px solid var(--border); border-radius: 8px; padding: 16px; background: var(--elevated); }
#tab-v9Results .v9-model-note b { display: flex; justify-content: space-between; align-items: center; font-size: 13px; color: var(--text1); margin-bottom: 8px; }
#tab-v9Results .v9-model-note p { font-size: 13px; line-height: 1.5; color: var(--text2); margin: 0; }
#tab-v9Results .v9-capacity { display: grid; gap: 16px; }
#tab-v9Results .v9-capacity-group { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
#tab-v9Results .v9-capacity-budget { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; padding: 12px 16px; background: var(--elevated); border-bottom: 1px solid var(--border); }
#tab-v9Results .v9-capacity-budget strong { font-size: 13px; color: var(--text1); }
#tab-v9Results .v9-capacity-budget span { font-size: 11px; color: var(--text3); }
#tab-v9Results .v9-capacity-rows { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; background: var(--border); }
#tab-v9Results .v9-capacity-row { min-width: 0; padding: 16px; background: var(--surface); }
#tab-v9Results .v9-capacity-row.is-best { box-shadow: inset 3px 0 0 #10b981; }
#tab-v9Results .v9-capacity-arm { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 14px; color: var(--text1); font-size: 13px; font-weight: 600; }
#tab-v9Results .v9-capacity-found { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-capacity-found small { display: block; margin-top: 2px; color: var(--text3); font-size: 10px; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; }
#tab-v9Results .v9-capacity-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
#tab-v9Results .v9-capacity-metric { padding-left: 9px; border-left: 1px solid var(--border-strong); }
#tab-v9Results .v9-capacity-metric b { display: block; color: var(--text1); font-size: 13px; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-capacity-metric span { display: block; margin-top: 3px; color: var(--text3); font-size: 10px; text-transform: uppercase; letter-spacing: .04em; }
#tab-v9Results .v9-volume-summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 18px 0 20px; }
#tab-v9Results .v9-chart-stack { display: grid; gap: 18px; margin-top: 16px; }
#tab-v9Results .v9-chart-block { min-width: 0; overflow: hidden; padding: 16px; border: 1px solid var(--border); border-radius: 10px; background: var(--elevated); }
#tab-v9Results .v9-chart-block h4 { margin: 0 0 6px; color: var(--text1); font-size: 13px; font-weight: 600; }
#tab-v9Results .v9-volume-stat { padding: 12px 14px; border: 1px solid var(--border); border-radius: 8px; background: var(--elevated); }
#tab-v9Results .v9-volume-stat b { display: block; color: var(--text1); font-size: 18px; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-volume-stat span { display: block; margin-top: 4px; color: var(--text3); font-size: 10px; text-transform: uppercase; letter-spacing: .05em; }
#tab-v9Results .v9-volume-chart, #tab-v9Results .v9-combined-chart { display: block; width: 100%; height: auto; overflow: visible; }
#tab-v9Results .v9-volume-chart text, #tab-v9Results .v9-combined-chart text { fill: var(--text3); font-family: inherit; font-size: 11px; }
#tab-v9Results .v9-volume-area { fill: rgba(148,163,184,.16); }
#tab-v9Results .v9-volume-line { fill: none; stroke: #94a3b8; stroke-linecap: round; stroke-linejoin: round; stroke-width: 2.5; }
#tab-v9Results .v9-volume-rule { stroke: var(--border-strong); stroke-dasharray: 4 5; stroke-width: 1; }
#tab-v9Results .v9-hover-guide { stroke: var(--text3); stroke-dasharray: 3 4; stroke-width: 1; opacity: 0; pointer-events: none; }
#tab-v9Results .v9-hover-target { fill: transparent; pointer-events: all; cursor: crosshair; }
#tab-v9Results .v9-hover-point { fill: var(--surface); stroke-width: 2; opacity: 0; pointer-events: none; }
#tab-v9Results .v9-daily-found-header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px 16px; margin: 24px 0 10px; }
#tab-v9Results .v9-daily-found-header h4 { margin: 0; color: var(--text1); font-size: 13px; font-weight: 600; }
#tab-v9Results .v9-daily-found-select { background: var(--surface); color: var(--text1); border: 1px solid var(--border-strong); border-radius: 6px; padding: 6px 9px; font: inherit; font-size: 12px; }
#tab-v9Results .v9-daily-found-select:focus-visible, #tab-v9Results .v9-chart-toggle:focus-visible { outline: 2px solid #16a34a; outline-offset: 2px; }
#tab-v9Results .v9-chart-legend { display: flex; flex-wrap: wrap; gap: 14px; margin: 0 0 8px; color: var(--text2); font-size: 12px; }
#tab-v9Results .v9-chart-toggle { display: inline-flex; align-items: center; gap: 6px; padding: 3px 7px; border: 1px solid transparent; border-radius: 6px; background: transparent; color: var(--text2); font: inherit; font-size: 12px; cursor: pointer; }
#tab-v9Results .v9-chart-toggle:hover { border-color: var(--border-strong); color: var(--text1); }
#tab-v9Results .v9-chart-toggle[aria-pressed="false"] { opacity: .38; }
#tab-v9Results .v9-chart-key { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
#tab-v9Results .v9-chart-key.baseline { background: #64748b; }
#tab-v9Results .v9-chart-key.hybrid { background: #16a34a; }
#tab-v9Results .v9-chart-key.gnn { background: #3b82f6; }
#tab-v9Results .v9-chart-key.crossings { background: #94a3b8; }
#tab-v9Results .v9-chart-key.hidden-carriers { background: #3b82f6; }
#tab-v9Results .v9-found-chart { display: block; width: 100%; height: auto; overflow: visible; }
#tab-v9Results .v9-found-chart text { fill: var(--text3); font-family: inherit; font-size: 11px; }
#tab-v9Results .v9-found-chart-rule { stroke: var(--border); stroke-width: 1; }
#tab-v9Results .v9-found-chart-line { fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-width: 2.5; }
#tab-v9Results .v9-found-chart-line.baseline { stroke: #64748b; }
#tab-v9Results .v9-found-chart-line.hybrid { stroke: #16a34a; }
#tab-v9Results .v9-found-chart-line.gnn { stroke: #3b82f6; }
#tab-v9Results .v9-simulated-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 16px 0 18px; }
#tab-v9Results .v9-simulated-card { min-width: 0; padding: 14px; border: 1px solid var(--border); border-left: 3px solid #64748b; border-radius: 8px; background: var(--surface); }
#tab-v9Results .v9-simulated-card.hybrid { border-left-color: #16a34a; }
#tab-v9Results .v9-simulated-card h5 { margin: 0 0 11px; color: var(--text1); font-size: 12px; font-weight: 600; }
#tab-v9Results .v9-simulated-metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px 12px; }
#tab-v9Results .v9-simulated-metric { min-width: 0; padding-left: 8px; border-left: 1px solid var(--border-strong); }
#tab-v9Results .v9-simulated-metric b { display: block; color: var(--text1); font-size: 14px; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-simulated-metric span { display: block; margin-top: 3px; color: var(--text2); font-size: 11px; line-height: 1.35; letter-spacing: .02em; }
#tab-v9Results .v9-simulated-chart-scroll { max-width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
#tab-v9Results .v9-simulated-chart-scroll:focus-visible { outline: 2px solid #16a34a; outline-offset: 2px; }
#tab-v9Results .v9-simulated-chart { min-width: 720px; }
#tab-v9Results .v9-simulated-chart text { fill: var(--text2); font-size: 12px; }
#tab-v9Results .v9-sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
#tab-v9Results table.v9-sr-only { display: block; }
@media(max-width:700px){
  #tab-v9Results { padding: 24px 16px; }
  #tab-v9Results .v9-summary { grid-template-columns: 1fr 1fr; }
  #tab-v9Results .v9-model-list { grid-template-columns: minmax(0, 1fr); }
  #tab-v9Results .v9-summary-lead { grid-column: 1 / -1; }
  #tab-v9Results .v9-capacity-rows { grid-template-columns: 1fr; }
  #tab-v9Results .v9-capacity-row.is-best { box-shadow: inset 3px 0 0 #10b981; }
  #tab-v9Results .v9-volume-summary { grid-template-columns: 1fr; gap: 8px; }
  #tab-v9Results .v9-story-header { display: block; }
  #tab-v9Results .v9-story-note { max-width: none; margin-top: 14px; }
  #tab-v9Results .v9-lens-grid { grid-template-columns: 1fr; }
  #tab-v9Results .v9-lens p { min-height: 0; }
  #tab-v9Results .v9-simulated-summary { grid-template-columns: 1fr; }
}
"""

SIMULATED_CATCH_VIEW_MODEL_JS = r"""
  function buildSimulatedCatchViewModel(sim,requestedBudget){
    const arms=['baseline','hybrid'];
    const metricPrefixes=['daily_people_found','daily_budget','daily_precision','daily_recall','daily_f1','later_candidate_events_removed','later_hidden_events_removed'];
    const seriesPrefix='daily_found_by_day';
    const unavailable=()=>({available:false,budgets:[]});
    if(!sim||!sim.arms||!arms.every(a=>sim.arms[a]&&typeof sim.arms[a]==='object')) return unavailable();
    const owns=(obj,key)=>Object.prototype.hasOwnProperty.call(obj,key);
    const validSeries=rows=>Array.isArray(rows)&&rows.length>0
      &&rows.every(row=>row&&typeof row.date==='string'&&row.date&&Number.isFinite(row.found))
      &&new Set(rows.map(row=>row.date)).size===rows.length;
    const validBudget=(arm,k)=>{
      const metrics=sim.arms[arm];
      return metricPrefixes.every(prefix=>owns(metrics,prefix+'@'+k)&&Number.isFinite(metrics[prefix+'@'+k]))
        &&owns(metrics,seriesPrefix+'@'+k)&&validSeries(metrics[seriesPrefix+'@'+k]);
    };
    const matchingDateSets=k=>{
      const baselineDates=new Set(sim.arms.baseline[seriesPrefix+'@'+k].map(row=>row.date));
      return arms.slice(1).every(a=>{
        const dates=new Set(sim.arms[a][seriesPrefix+'@'+k].map(row=>row.date));
        return dates.size===baselineDates.size&&Array.from(baselineDates).every(date=>dates.has(date));
      });
    };
    const budgets=Object.keys(sim.arms.baseline).map(key=>{const match=key.match(/^daily_people_found@(\d+)$/);return match?Number(match[1]):null;})
      .filter(k=>k!==null&&arms.every(a=>validBudget(a,k))&&matchingDateSets(k)).sort((a,b)=>a-b);
    if(!budgets.length) return unavailable();
    const selected=budgets.includes(requestedBudget)?requestedBudget:(budgets.includes(25)?25:budgets[0]);
    const dates=sim.arms.baseline[seriesPrefix+'@'+selected].map(row=>row.date).sort();
    const valuesByArm=Object.fromEntries(arms.map(a=>{
      const byDate=Object.fromEntries(sim.arms[a][seriesPrefix+'@'+selected].map(row=>[row.date,row.found]));
      return [a,dates.map(date=>byDate[date])];
    }));
    const metricsByArm=Object.fromEntries(arms.map(a=>[a,{
      peopleFound:sim.arms[a]['daily_people_found@'+selected],
      inspections:sim.arms[a]['daily_budget@'+selected],
      precision:sim.arms[a]['daily_precision@'+selected],
      recall:sim.arms[a]['daily_recall@'+selected],
      f1:sim.arms[a]['daily_f1@'+selected],
      laterHiddenEventsRemoved:sim.arms[a]['later_hidden_events_removed@'+selected]
    }]));
    const foundMax=Math.max(1,...arms.flatMap(a=>valuesByArm[a]));
    const foundMaxY=Math.max(1,Math.ceil(foundMax));
    const yTicks=Array.from(new Set(Array.from({length:4},(_,i)=>Math.round(foundMaxY*i/3))));
    const tickCount=Math.min(6,dates.length);
    const dateTickIndexes=Array.from(new Set(Array.from({length:tickCount},(_,i)=>Math.round(i*(dates.length-1)/Math.max(1,tickCount-1)))));
    return {available:true,budgets,selected,dates,valuesByArm,metricsByArm,foundMaxY,yTicks,dateTickIndexes};
  }
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
  const hidden=pop=>pop==='observable'?demo.stratum_hidden.observable:demo.hidden_total;
  const win=pop=>pop==='observable'?demo.win_hybrid_observable:demo.win_hybrid_whole_pool;
  const winKey=(pop,k)=>pop==='observable'?'hybrid_vs_baseline_obs@'+k:'hybrid_vs_baseline@'+k;
  const seizureRate=DATA.overview&&DATA.overview.outcome_rates?DATA.overview.outcome_rates.seizure:null;
  const preferredArms=['baseline','hybrid','gnn'];
  const armOrder=preferredArms.filter(a=>demo.overall&&demo.overall[a]);
  const armMeta=demo.model_arms||{};
  const armLabel=a=>a==='baseline'?'Baseline':(a==='hybrid'?'Deployable Hybrid':'GNN');
  const runLabel=(demo.gnn_seeds?demo.gnn_seeds.length:0)+' seed(s), '+(demo.epochs||'-')+' epochs'+(demo.gnn_arm?', '+demo.gnn_arm+' arm':'');
  const wDeploy=demo.hybrid_fusion_w_gnn;
  const headlineK=ks.includes(2000)?2000:ks[ks.length-1];
  const headlineBaseline=found('pool','baseline',headlineK);
  const headlineHybrid=found('pool','hybrid',headlineK);
  const headlineGnn=demo.overall&&demo.overall.gnn?found('pool','gnn',headlineK):null;
  const headlineDelta=headlineHybrid-headlineBaseline;
  const headlineLift=headlineBaseline?headlineDelta/headlineBaseline:null;
  const wholeHybridAt2000=Number((demo.overall.hybrid||{})['found@2000']||0);
  const wholeBaselineAt2000=Number((demo.overall.baseline||{})['found@2000']||0);
  const dailyBaseline25=Number((demo.overall_daily.baseline||{})['daily_found@25']||0);
  const dailyHybrid25=Number((demo.overall_daily.hybrid||{})['daily_found@25']||0);
  const dailyBudget25=Number((demo.overall_daily.baseline||{})['daily_budget@25']||0);
  const dailyDays=Number((demo.overall_daily.baseline||{}).n_days||0);
  let pop='observable';
  const modelVisibility={baseline:true,hybrid:true,gnn:true};
  const layerVisibility={crossings:true,'hidden-carriers':true};

  sec.innerHTML='<h2>V9 Positive Control</h2>'
    +'<div class="v9-sub">Leak-safe baselines use row-level history and context. GNN arms add as-of relational signals.</div>'
    +'<div id="v9-summary" class="v9-summary" aria-label="V9 result summary">'
    +'<div class="v9-summary-lead"><div class="v9-summary-kicker">Operational headline</div><div class="v9-summary-title">Deployable Hybrid records '+fmt(headlineDelta)+' more hidden-positive event hits at K='+fmt(headlineK)+'.</div><div class="v9-summary-copy">'+fmt(headlineHybrid)+' event hits vs '+fmt(headlineBaseline)+' for the baseline ('+(headlineLift==null?'n/a':pct(headlineLift))+' lift). GNN event-hit ceiling: '+(headlineGnn==null?'n/a':fmt(headlineGnn))+'. These found@K metrics count events, not unique people.</div><a class="v9-summary-link" href="#v9-case-evidence">Inspect seed-0 unique-person recovery evidence →</a></div>'
    +'<div class="v9-summary-stat"><b>'+fmt(headlineHybrid)+'</b><span>Hybrid event hits</span></div>'
    +'<div class="v9-summary-stat"><b>'+fmt(headlineBaseline)+'</b><span>Baseline event hits</span></div>'
    +'<div class="v9-summary-stat"><b>'+(headlineGnn==null?'n/a':fmt(headlineGnn))+'</b><span>GNN event-hit ceiling</span></div>'
    +'</div>'
    +'<div id="v9-metrics"></div>'
    +'<div class="v9-card" style="margin-top:18px"><h3>What the models look for</h3><div class="v9-hint">Baselines use the target row; GNN arms add graph evidence available before scoring.</div><div id="v9-model-notes"></div></div>'
    +'<section class="v9-story" aria-labelledby="v9-story-title"><div class="v9-story-header"><div><div class="v9-story-kicker">How to read this tab</div><h3 id="v9-story-title" class="v9-story-title">Read the V9 result through three lenses</h3><p class="v9-story-intro">The main rankings count event hits; the recovery explorer separately counts unique people.</p></div><div class="v9-story-note"><b>The short version</b>The graph advantage appears at operational depth.</div></div><div class="v9-lens-grid"><article class="v9-lens"><h4>1. Global event ranking</h4><p>One whole-pool top-K list, with all hidden-positive events in the recall denominator.</p><div class="v9-lens-stat"><b>'+fmt(wholeHybridAt2000)+' vs '+fmt(wholeBaselineAt2000)+'</b><span>Whole-pool hidden-positive event hits at K=2,000</span></div></article><article class="v9-lens"><h4>2. Findable event depth</h4><p>Defaults to the '+fmt(demo.stratum_hidden.observable)+'-event observable slice. Toggle for the whole pool.</p><div class="v9-lens-stat"><b>'+fmt(headlineHybrid)+' vs '+fmt(headlineBaseline)+'</b><span>Hybrid vs baseline event hits at K='+fmt(headlineK)+'</span></div></article><article class="v9-lens"><h4>3. Daily event operations</h4><p>Each of '+fmt(dailyDays)+' test days gets its own quota; 25/day equals '+fmt(dailyBudget25)+' inspections.</p><div class="v9-lens-stat"><b>'+fmt(dailyHybrid25)+' vs '+fmt(dailyBaseline25)+'</b><span>Hybrid vs baseline event hits at 25 inspections/day</span></div></article></div></section>'
    +'<section id="v9-case-evidence" aria-labelledby="v9-recovery-title"></section>'
    +'<h3 style="margin: 32px 0 12px; font-size: 20px; font-weight: 700; color: var(--text1); letter-spacing: -0.01em;">Baseline vs Hybrid vs GNN</h3>'
    +'<div class="v9-seg" id="v9-pop" role="group" aria-label="Population scope"><button data-v="observable" class="on" aria-pressed="true">Observable slice</button><button data-v="pool" aria-pressed="false">Whole pool</button></div>'
    +'<div class="v9-card"><h3>Depth event recall</h3><div class="v9-hint">Share of hidden-positive events hit in the selected population.</div><div id="v9-bars"></div></div>'
    +'<div class="v9-card" style="margin-top:18px"><h3>Daily capacity view</h3><div class="v9-hint">Found, precision, recall, and F1 under fixed per-day inspection budgets.</div><div id="v9-daily"></div></div>'
    +'<div class="v9-card" style="margin-top:18px"><h3>Daily Crossing Volume</h3><div class="v9-hint">Daily test-window crossing volume and hidden-positive event hits by each model.</div><div class="v9-chart-stack"><section class="v9-chart-block"><div class="v9-daily-found-header"><h4>Crossing events and hidden-positive event hits per day</h4><label><span class="v9-sr-only">Daily inspection budget</span><select id="v9-daily-found-k" class="v9-daily-found-select"></select></label></div><div class="v9-hint">Daily top-k event hits only. Toggle a model to show or hide its line.</div><div id="v9-volume"></div></section><section id="v9-simulated-catches" class="v9-chart-block" aria-labelledby="v9-simulated-title"><div class="v9-daily-found-header"><h4 id="v9-simulated-title">Simulated catches - first-time unique-person recoveries</h4><label><span class="v9-sr-only">Simulated daily inspection budget</span><select id="v9-simulated-k" class="v9-daily-found-select"></select></label></div><div class="v9-hint">New people recovered each day after earlier simulated catches leave the candidate pool.</div><div id="v9-simulated-summary" class="v9-simulated-summary"></div><div id="v9-simulated-volume"></div></section></div></div>'
    +'<div class="v9-card" style="margin-top:18px"><h3>Bootstrap verdicts</h3><div class="v9-hint">Paired event-bootstrap results for Hybrid minus baseline, using global and daily budgets.</div><div class="v9-table-wrap" id="v9-sig"></div></div>';

  mountV9RecoveryExplainer(
    document.getElementById('v9-case-evidence'),
    (typeof DATA!=='undefined'&&DATA)?DATA.v9RecoveryExplainer:null,
    {fmt,pct,esc}
  );

  makeMetrics(document.getElementById('v9-metrics'),[
    {l:'test pool',v:fmt(demo.pool_size),s:'detected events excluded'},
    {l:'hidden-positive events',v:fmt(demo.hidden_total),s:'false-negative test events'},
    {l:'observable hidden-positive events',v:fmt(demo.stratum_hidden.observable),s:'findable cell slice'},
    {l:'seizure rate',v:seizureRate==null?'-':pct(seizureRate),s:'corpus outcome rate'},
    {l:'fusion weight',v:wDeploy==null?'-':wDeploy,s:'deployable caught-tuned GNN blend'},
    {l:'GNN run',v:runLabel,s:'settings recorded in JSON'},
  ]);

  function drawModelNotes(){
    const groups = { 'GNN Models': [], 'Base Models': [], 'Hybrid Models': [] };
    armOrder.forEach(a=>{
      const meta=armMeta[a]||{};
      const kind=meta.kind||((a.indexOf('gnn')===0)?'gnn':'baseline');
      const group = (kind==='hybrid' || a.includes('hybrid')) ? 'Hybrid Models' : ((kind==='gnn' || a.indexOf('gnn')===0) ? 'GNN Models' : 'Base Models');
      groups[group].push(a);
    });

    let h='';
    for (const [gName, arms] of Object.entries(groups)) {
      if (!arms.length) continue;
      h += '<h4 style="margin: 16px 0 12px; font-size: 13px; font-weight: 600; color: var(--text1); padding-bottom: 4px; border-bottom: 1px solid var(--border);">' + gName + '</h4>';
      h += '<div class="v9-model-list" style="margin-top: 0; margin-bottom: 24px;">'+arms.map(a=>{
        const meta=armMeta[a]||{};
        const kind=meta.kind||((a.indexOf('gnn')===0)?'gnn':'baseline');
        const label=meta.label||a;
        const text=meta.looks_for||'No model description provided.';
        const pCls=kind==='gnn'?'win':(kind==='hybrid'?'tie':'tie');
        return '<div class="v9-model-note"><b><span>'+esc(armLabel(a))+'</span><span class="v9-pill '+pCls+'">'+esc(kind)+'</span></b><p>'+esc(text)+'</p></div>';
      }).join('')+'</div>';
    }
    document.getElementById('v9-model-notes').innerHTML = h;
  }

  document.getElementById('v9-pop').addEventListener('click',e=>{
    const b=e.target.closest('button'); if(!b) return;
    pop=b.dataset.v;
    sec.querySelectorAll('#v9-pop button').forEach(x=>{const active=x===b;x.classList.toggle('on',active);x.setAttribute('aria-pressed',String(active));});
    draw();
  });

  function pill(summary){
    if(!summary) return '<span class="v9-pill tie">n/a</span>';
    const lo=Number(summary.ci[0]), hi=Number(summary.ci[1]);
    if(lo>0) return '<span class="v9-pill win">Hybrid win</span>';
    if(hi<0) return '<span class="v9-pill loss">baseline win</span>';
    return '<span class="v9-pill tie">wash</span>';
  }

  const hasGnn=()=>!!(demo.overall&&demo.overall.gnn);
  function drawBars(){
    const k=ks.includes(5000)?5000:ks[ks.length-1];
    const total=hidden(pop)||1;
    const vals=[['baseline',found(pop,'baseline',k),'base'],['Hybrid',found(pop,'hybrid',k),'']];
    if(hasGnn()) vals.push(['GNN',found(pop,'gnn',k),'']);
    document.getElementById('v9-bars').innerHTML='<div class="v9-bars">'+vals.map(([label,val,cls])=>{
      const w=Math.max(2,Math.round(val/total*100));
      return '<div class="v9-bar-row"><span>'+label+'</span><div class="v9-track"><div class="v9-fill '+cls+'" style="width:'+w+'%"></div></div><b>'+fmt(val)+' / '+fmt(total)+'</b></div>';
    }).join('')+'</div>';
  }

  function drawDaily(){
    const el=document.getElementById('v9-daily'); if(!el) return;
    const od=demo.overall_daily;
    if(!od){el.innerHTML='<div class="v9-hint">No daily-capacity metric in this result (re-run the demo to populate it).</div>';return;}
    const dks=(demo.daily_ks||[]).slice().sort((a,b)=>a-b);
    const arms=['baseline','hybrid','gnn'].filter(a=>od[a]);
    const nDays=(od.baseline&&od.baseline.n_days)||null;
    let h='<div class="v9-capacity">';
    dks.forEach(k=>{
      const cells=arms.map(a=>({
        a,
        f:Number(od[a]['daily_found@'+k]||0),
        p:Number(od[a]['daily_precision@'+k]||0),
        r:Number(od[a]['daily_recall@'+k]||0),
        f1:Number(od[a]['daily_f1@'+k]||0)
      }));
      const best=Math.max.apply(null,cells.map(c=>c.f));
      h+='<section class="v9-capacity-group"><div class="v9-capacity-budget"><strong>'+fmt(k)+' inspections / day</strong><span>summed operating budget: '+fmt(Number(od.baseline['daily_budget@'+k]||k))+'</span></div><div class="v9-capacity-rows">'+cells.map(c=>'<article class="v9-capacity-row'+(c.f===best&&c.f>0?' is-best':'')+'"><div class="v9-capacity-arm"><span>'+esc(armLabel(c.a))+'</span><span class="v9-capacity-found">'+fmt(c.f)+'<small>found</small></span></div><div class="v9-capacity-metrics"><div class="v9-capacity-metric"><b>'+pct(c.p)+'</b><span>Precision</span></div><div class="v9-capacity-metric"><b>'+pct(c.r)+'</b><span>Recall</span></div><div class="v9-capacity-metric"><b>'+pct(c.f1)+'</b><span>F1</span></div></div></article>').join('')+'</div></section>';
    });
    h+='</div>'+(nDays?'<div class="v9-hint" style="margin-top:10px">Summed over '+fmt(nDays)+' test days.</div>':'');
    el.innerHTML=h;
  }

  function drawCombined(){
    const el=document.getElementById('v9-volume'); if(!el) return;
    const points=(typeof DATA!=='undefined'&&Array.isArray(DATA.v9DailyCrossings)?DATA.v9DailyCrossings:[]).map(d=>({date:String(d.date||''),value:Number(d.crossings||0)})).filter(d=>d.date&&Number.isFinite(d.value));
    if(!points.length){el.innerHTML='<div class="v9-hint">No daily crossing-volume series is embedded in this dashboard.</div>';return;}
    const select=document.getElementById('v9-daily-found-k');
    const od=demo.overall_daily||{}, arms=['baseline','hybrid','gnn'].filter(a=>od[a]);
    const dks=(demo.daily_ks||[]).map(Number).filter(k=>[5,10,25,50].includes(k)).sort((a,b)=>a-b);
    if(!select||!arms.length||!dks.length){el.innerHTML='<div class="v9-hint">No daily model catch series is embedded in this dashboard.</div>';return;}
    const current=Number(select.value), selected=dks.includes(current)?current:(dks.includes(25)?25:dks[0]);
    select.innerHTML=dks.map(k=>'<option value="'+k+'">'+fmt(k)+' / day</option>').join('');
    select.value=selected;
    select.onchange=()=>drawCombined();
    const byArm=arms.map(a=>({a,values:(od[a]['daily_found_by_day@'+selected]||[]).map(d=>({date:String(d.date||''),value:Number(d.found||0)}))}));
    const dates=points.map(d=>d.date), width=720, height=280, left=58, right=58, top=24, bottom=42, chartW=width-left-right, chartH=height-top-bottom;
    const crossingMax=Math.max.apply(null,points.map(d=>d.value)), crossingMaxY=Math.max(1,Math.ceil(crossingMax/10)*10);
    const foundMax=Math.max(1,...byArm.flatMap(series=>series.values.map(d=>d.value))), foundMaxY=Math.max(1,Math.ceil(foundMax));
    const x=i=>left+(dates.length===1?chartW/2:i*chartW/(dates.length-1)), yLeft=v=>top+chartH-(v/crossingMaxY)*chartH, yRight=v=>top+chartH-(v/foundMaxY)*chartH;
    const tickCount=Math.min(6,dates.length), tickIndexes=Array.from({length:tickCount},(_,i)=>Math.round(i*(dates.length-1)/Math.max(1,tickCount-1)));
    const ticks=tickIndexes.map(i=>'<text x="'+x(i).toFixed(1)+'" y="'+(height-14)+'" text-anchor="'+(i===0?'start':i===dates.length-1?'end':'middle')+'">'+esc(dates[i])+'</text>').join('');
    const leftTicks=Array.from({length:4},(_,i)=>Math.round(crossingMaxY*i/3)), rightTicks=Array.from({length:4},(_,i)=>Math.round(foundMaxY*i/3));
    const rules=leftTicks.map(v=>'<line class="v9-volume-rule" x1="'+left+'" x2="'+(width-right)+'" y1="'+yLeft(v).toFixed(1)+'" y2="'+yLeft(v).toFixed(1)+'"/><text x="'+(left-8)+'" y="'+(yLeft(v)+4).toFixed(1)+'" text-anchor="end">'+fmt(v)+'</text>').join('');
    const rightLabels=rightTicks.map(v=>'<text x="'+(width-right+8)+'" y="'+(yRight(v)+4).toFixed(1)+'">'+fmt(v)+'</text>').join('');
    const volumeLine=points.map((d,i)=>(i?'L':'M')+x(i).toFixed(1)+' '+yLeft(d.value).toFixed(1)).join(' '), volumeArea=volumeLine+' L '+x(points.length-1).toFixed(1)+' '+(top+chartH)+' L '+x(0).toFixed(1)+' '+(top+chartH)+' Z';
    const valuesByArm=Object.fromEntries(byArm.map(series=>[series.a,dates.map(date=>{const row=series.values.find(d=>d.date===date);return row?row.value:0;})]));
    const modelLines=byArm.map(series=>{const values=valuesByArm[series.a];const path=values.map((value,i)=>(i?'L':'M')+x(i).toFixed(1)+' '+yRight(value).toFixed(1)).join(' ');return '<path class="v9-found-chart-line '+series.a+'" d="'+path+'"/>';}).join('');
    const total=points.reduce((sum,d)=>sum+d.value,0), average=total/points.length, peak=Math.max.apply(null,points.map(d=>d.value));
    const volumePoints=points.map((d,i)=>'<circle class="v9-hover-point v9-volume-point" data-layer="crossings" data-index="'+i+'" cx="'+x(i).toFixed(1)+'" cy="'+yLeft(d.value).toFixed(1)+'" r="5" stroke="#94a3b8"/>').join('');
    const modelPoints=byArm.map(series=>valuesByArm[series.a].map((value,i)=>'<circle class="v9-hover-point '+series.a+'" data-layer="hidden-carriers" data-arm="'+series.a+'" data-index="'+i+'" cx="'+x(i).toFixed(1)+'" cy="'+yRight(value).toFixed(1)+'" r="4" stroke="'+(series.a==='baseline'?'#64748b':series.a==='hybrid'?'#16a34a':'#3b82f6')+'"/>').join('')).join('');
    const legend='<button type="button" class="v9-chart-toggle" data-layer="crossings" aria-pressed="true"><i class="v9-chart-key crossings"></i>Crossing events</button><button type="button" class="v9-chart-toggle" data-layer="hidden-carriers" aria-pressed="true"><i class="v9-chart-key hidden-carriers"></i>Hidden-positive event hits</button>'+arms.map(a=>'<button type="button" class="v9-chart-toggle" data-arm="'+a+'" aria-pressed="true"><i class="v9-chart-key '+a+'"></i>'+esc(armLabel(a))+'</button>').join('');
    el.innerHTML='<div class="v9-volume-summary"><div class="v9-volume-stat"><b>'+fmt(points.length)+'</b><span>Days</span></div><div class="v9-volume-stat"><b>'+average.toFixed(1)+'</b><span>Average crossings / day</span></div><div class="v9-volume-stat"><b>'+fmt(peak)+'</b><span>Peak crossings / day</span></div></div><div class="v9-chart-legend" aria-label="Model and data-layer legend">'+legend+'</div><svg class="v9-combined-chart" viewBox="0 0 '+width+' '+height+'" role="img" aria-label="Daily crossing events and hidden-positive event hits"><text x="'+left+'" y="12">crossing events / day</text><text x="'+(width-right)+'" y="12" text-anchor="end">hidden-positive event hits / day</text>'+rules+rightLabels+'<g class="v9-crossings-layer" data-layer="crossings"><path class="v9-volume-area" d="'+volumeArea+'"/><path class="v9-volume-line" d="'+volumeLine+'"/>'+volumePoints+'</g><line class="v9-hover-guide" x1="'+left+'" x2="'+left+'" y1="'+top+'" y2="'+(top+chartH)+'"/><g class="v9-hidden-carriers-layer" data-layer="hidden-carriers">'+modelLines+modelPoints+'</g>'+ticks+'<rect class="v9-hover-target" x="'+left+'" y="'+top+'" width="'+chartW+'" height="'+chartH+'"/></svg>';
    const svg=el.querySelector('svg'), guide=svg.querySelector('.v9-hover-guide'), target=svg.querySelector('.v9-hover-target'), hoverPoints=svg.querySelectorAll('.v9-hover-point');
    const indexAt=e=>{const p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;const local=p.matrixTransform(svg.getScreenCTM().inverse());return Math.max(0,Math.min(dates.length-1,Math.round((local.x-left)/Math.max(1,chartW/(dates.length-1)))));};
    const toggles=el.querySelectorAll('.v9-chart-toggle');
    const updateVisibility=()=>{const crossingsVisible=layerVisibility.crossings!==false;const carriersVisible=layerVisibility['hidden-carriers']!==false;svg.querySelector('.v9-crossings-layer').style.display=crossingsVisible?'':'none';svg.querySelector('.v9-hidden-carriers-layer').style.display=carriersVisible?'':'none';arms.forEach(a=>{const visible=carriersVisible&&modelVisibility[a]!==false;svg.querySelectorAll('.v9-found-chart-line.'+a).forEach(node=>node.style.display=visible?'':'none');svg.querySelectorAll('.v9-hover-point.'+a).forEach(node=>node.style.display=visible?'':'none');});toggles.forEach(button=>{const visible=button.dataset.layer?layerVisibility[button.dataset.layer]!==false:modelVisibility[button.dataset.arm]!==false;button.setAttribute('aria-pressed',String(visible));});};
    toggles.forEach(button=>button.addEventListener('click',()=>{if(button.dataset.layer){const layer=button.dataset.layer;layerVisibility[layer]=layerVisibility[layer]===false;}else{const arm=button.dataset.arm;modelVisibility[arm]=modelVisibility[arm]===false;}updateVisibility();}));
    updateVisibility();
    target.addEventListener('pointermove',e=>{const i=indexAt(e),d=points[i],crossingsVisible=layerVisibility.crossings!==false,carriersVisible=layerVisibility['hidden-carriers']!==false;guide.setAttribute('x1',x(i).toFixed(1));guide.setAttribute('x2',x(i).toFixed(1));guide.style.opacity='1';hoverPoints.forEach(point=>point.style.opacity=Number(point.dataset.index)===i&&(!point.dataset.arm||modelVisibility[point.dataset.arm]!==false)&&(!point.dataset.layer||layerVisibility[point.dataset.layer]!==false)?'1':'0');const counts=arms.filter(a=>carriersVisible&&modelVisibility[a]!==false).map(a=>esc(armLabel(a))+': '+fmt(valuesByArm[a][i])).join('<br>');const tooltipParts=['<b>'+esc(d.date)+'</b>'];if(crossingsVisible) tooltipParts.push(fmt(d.value)+' crossings');tooltipParts.push(fmt(selected)+' inspections / day');if(counts) tooltipParts.push(counts);showTip(e,tooltipParts.join('<br>'));});
    target.addEventListener('pointerleave',()=>{guide.style.opacity='0';hoverPoints.forEach(point=>point.style.opacity='0');hideTip();});
  }
""" + SIMULATED_CATCH_VIEW_MODEL_JS + r"""
  function drawSimulatedCatches(){
    const section=document.getElementById('v9-simulated-catches');
    const simSelect=document.getElementById('v9-simulated-k');
    const summaryEl=document.getElementById('v9-simulated-summary');
    const chartEl=document.getElementById('v9-simulated-volume');
    if(!section||!simSelect||!summaryEl||!chartEl) return;
    const arms=['baseline','hybrid'];
    const view=buildSimulatedCatchViewModel(demo.simulated_catch_daily,Number(simSelect.value));
    if(!view.available){
      simSelect.innerHTML='';
      simSelect.disabled=true;
      summaryEl.innerHTML='';
      chartEl.innerHTML='<div class="v9-hint">No simulated-catch series is embedded in this dashboard.</div>';
      return;
    }
    simSelect.disabled=false;
    const selected=view.selected;
    simSelect.innerHTML=view.budgets.map(k=>'<option value="'+k+'">'+fmt(k)+' / day</option>').join('');
    simSelect.value=selected;
    simSelect.onchange=()=>drawSimulatedCatches();
    summaryEl.innerHTML=arms.map(a=>{
      const metrics=view.metricsByArm[a];
      return '<article class="v9-simulated-card '+a+'"><h5>'+esc(armLabel(a))+'</h5><div class="v9-simulated-metrics">'
        +'<div class="v9-simulated-metric"><b>'+fmt(metrics.peopleFound)+'</b><span>Unique people found</span></div>'
        +'<div class="v9-simulated-metric"><b>'+fmt(metrics.inspections)+'</b><span>Inspections</span></div>'
        +'<div class="v9-simulated-metric"><b>'+pct(metrics.precision)+'</b><span>Precision</span></div>'
        +'<div class="v9-simulated-metric"><b>'+pct(metrics.recall)+'</b><span>Recall</span></div>'
        +'<div class="v9-simulated-metric"><b>'+pct(metrics.f1)+'</b><span>F1</span></div>'
        +'<div class="v9-simulated-metric"><b>'+fmt(metrics.laterHiddenEventsRemoved)+'</b><span>Later hidden-positive events removed</span></div>'
        +'</div></article>';
    }).join('');
    const dates=view.dates, valuesByArm=view.valuesByArm;
    const width=720, height=240, left=48, right=20, top=24, bottom=42, chartW=width-left-right, chartH=height-top-bottom;
    const foundMaxY=view.foundMaxY;
    const x=i=>left+(dates.length===1?chartW/2:i*chartW/(dates.length-1)), y=v=>top+chartH-(v/foundMaxY)*chartH;
    const ticks=view.dateTickIndexes.map(i=>'<text x="'+x(i).toFixed(1)+'" y="'+(height-14)+'" text-anchor="'+(i===0?'start':i===dates.length-1?'end':'middle')+'">'+esc(dates[i])+'</text>').join('');
    const rules=view.yTicks.map(v=>'<line class="v9-found-chart-rule" x1="'+left+'" x2="'+(width-right)+'" y1="'+y(v).toFixed(1)+'" y2="'+y(v).toFixed(1)+'"/><text x="'+(left-8)+'" y="'+(y(v)+4).toFixed(1)+'" text-anchor="end">'+fmt(v)+'</text>').join('');
    const lines=arms.map(a=>'<path class="v9-found-chart-line '+a+'" d="'+valuesByArm[a].map((value,i)=>(i?'L':'M')+x(i).toFixed(1)+' '+y(value).toFixed(1)).join(' ')+'"/>').join('');
    const points=arms.map(a=>valuesByArm[a].map((value,i)=>'<circle class="v9-hover-point '+a+'" data-arm="'+a+'" data-index="'+i+'" cx="'+x(i).toFixed(1)+'" cy="'+y(value).toFixed(1)+'" r="4" stroke="'+(a==='baseline'?'#64748b':'#16a34a')+'"/>').join('')).join('');
    const accessibleName='Simulated first-time recoveries at '+fmt(selected)+' inspections per day: Baseline and Deployable Hybrid daily new unique people caught';
    const accessibleRows=dates.map((date,i)=>'<tr><td>'+esc(date)+'</td><td>'+fmt(valuesByArm.baseline[i])+'</td><td>'+fmt(valuesByArm.hybrid[i])+'</td></tr>').join('');
    chartEl.innerHTML='<div class="v9-chart-legend" aria-label="Simulated-catch model legend"><span><i class="v9-chart-key baseline"></i> Baseline</span><span><i class="v9-chart-key hybrid"></i> Deployable Hybrid</span></div><div class="v9-simulated-chart-scroll" tabindex="0" role="region" aria-label="'+esc(accessibleName)+' chart"><svg class="v9-found-chart v9-simulated-chart" viewBox="0 0 '+width+' '+height+'" role="img" aria-label="'+esc(accessibleName)+'" aria-describedby="v9-simulated-data-'+selected+'"><text x="'+left+'" y="12">new unique people / day</text>'+rules+lines+points+'<line class="v9-hover-guide" x1="'+left+'" x2="'+left+'" y1="'+top+'" y2="'+(top+chartH)+'"/>'+ticks+'<rect class="v9-hover-target" x="'+left+'" y="'+top+'" width="'+chartW+'" height="'+chartH+'"/></svg></div><table id="v9-simulated-data-'+selected+'" class="v9-sr-only"><caption>'+esc(accessibleName)+'</caption><thead><tr><th>Date</th><th>Baseline</th><th>Deployable Hybrid</th></tr></thead><tbody>'+accessibleRows+'</tbody></table>';
    const svg=chartEl.querySelector('svg'), guide=svg.querySelector('.v9-hover-guide'), target=svg.querySelector('.v9-hover-target'), hoverPoints=svg.querySelectorAll('.v9-hover-point');
    const indexAt=e=>{const p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;const local=p.matrixTransform(svg.getScreenCTM().inverse());return Math.max(0,Math.min(dates.length-1,Math.round((local.x-left)/Math.max(1,chartW/Math.max(1,dates.length-1)))));};
    target.addEventListener('pointermove',e=>{const i=indexAt(e);guide.setAttribute('x1',x(i).toFixed(1));guide.setAttribute('x2',x(i).toFixed(1));guide.style.opacity='1';hoverPoints.forEach(point=>point.style.opacity=Number(point.dataset.index)===i?'1':'0');showTip(e,'<b>'+esc(dates[i])+'</b><br>'+fmt(selected)+' inspections / day<br>'+arms.map(a=>esc(armLabel(a))+': '+fmt(valuesByArm[a][i])).join('<br>'));});
    target.addEventListener('pointerleave',()=>{guide.style.opacity='0';hoverPoints.forEach(point=>point.style.opacity='0');hideTip();});
  }

  function drawSig(){
    const wins=win(pop)||{};
    let h='<h4 style="margin: 4px 0 12px; font-size: 13px; font-weight: 600; color: var(--text1);">Whole-window bootstrap</h4>';
    h+='<table><thead><tr><th>K</th><th>mean diff</th><th>95% CI</th><th>p(Hybrid&lt;=base)</th><th>verdict</th></tr></thead><tbody>';
    ks.forEach(k=>{
      const s=wins[winKey(pop,k)];
      if(!s) return;
      h+='<tr><td>'+fmt(k)+'</td><td class="'+(s.mean_diff<0?'bad':'best')+'">'+(s.mean_diff>0?'+':'')+s.mean_diff+'</td>'
        +'<td>['+s.ci[0]+', '+s.ci[1]+']</td><td>'+s.p_enh_le_base+'</td><td>'+pill(s)+'</td></tr>';
    });
    h+='</tbody></table>';
    const dailyWins=demo.win_hybrid_daily||{};
    const dailyBaseline=demo.overall_daily&&demo.overall_daily.baseline||{};
    h+='<h4 style="margin: 24px 0 12px; font-size: 13px; font-weight: 600; color: var(--text1);">Daily-capacity bootstrap</h4>';
    h+='<table><thead><tr><th>per-day budget</th><th>mean diff</th><th>95% CI</th><th>p(Hybrid&lt;=base)</th><th>verdict</th></tr></thead><tbody>';
    (demo.daily_ks||[]).slice().sort((a,b)=>a-b).forEach(k=>{
      const s=dailyWins['hybrid_vs_baseline_daily@'+k];
      if(!s) return;
      h+='<tr><td>'+fmt(dailyBaseline['daily_budget@'+k]||k)+' total ('+fmt(k)+'/day)</td><td class="'+(s.mean_diff<0?'bad':'best')+'">'+(s.mean_diff>0?'+':'')+s.mean_diff+'</td>'
        +'<td>['+s.ci[0]+', '+s.ci[1]+']</td><td>'+s.p_enh_le_base+'</td><td>'+pill(s)+'</td></tr>';
    });
    h+='</tbody></table>';
    document.getElementById('v9-sig').innerHTML=h;
  }

  drawModelNotes();
  function draw(){drawBars();drawDaily();drawCombined();drawSig();}
  draw();
  drawSimulatedCatches();
}},
"""
