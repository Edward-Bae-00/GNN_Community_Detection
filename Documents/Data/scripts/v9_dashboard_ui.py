"""V9 positive-control tab for the V9-only dashboard."""

V9_RESULTS_NAV_BTN = '  <button data-tab="v9Results" aria-controls="tab-v9Results" aria-selected="false">V9 results</button>\n'
V9_RESULTS_SECTION = '  <section id="tab-v9Results" class="tab-content"></section>\n'

V9_RESULTS_CSS = r"""
#tab-v9Results { box-sizing: border-box; width: 100%; min-width: 0; overflow-x: clip; padding: clamp(28px, 4vw, 48px) clamp(20px, 4vw, 48px); max-width: 1320px; font-family: var(--font-body); color: var(--text1); }
#tab-v9Results h2 { font-size: var(--fs-xl); font-weight: 700; margin: 0 0 8px 0; letter-spacing: -0.03em; }
#tab-v9Results .v9-sub { color: var(--text2); font-size: 13px; margin-bottom: 36px; max-width: 64ch; line-height: 1.65; }
#tab-v9Results .v9-summary { display: grid; grid-template-columns: minmax(0, 1.5fr) repeat(3, minmax(130px, .7fr)); gap: 14px; margin: 0 0 32px; min-width: 0; }
#tab-v9Results .v9-summary-lead { background: linear-gradient(135deg, var(--sunk), var(--surface)); border: 1px solid var(--accent); border-radius: 12px; padding: 24px; min-width: 0; }
#tab-v9Results .v9-summary-kicker { color: var(--accent-hover); font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
#tab-v9Results .v9-summary-title { margin-top: 8px; color: var(--text1); font-size: var(--fs-lg); font-weight: 700; letter-spacing: -.025em; line-height: 1.25; overflow-wrap: anywhere; }
#tab-v9Results .v9-summary-copy { margin-top: 9px; color: var(--text2); font-size: 13px; line-height: 1.55; }
#tab-v9Results .v9-summary-link { display: inline-flex; margin-top: 14px; color: var(--accent-hover); font-size: 12px; font-weight: 600; text-decoration: none; }
#tab-v9Results .v9-summary-link:hover { text-decoration: underline; }
#tab-v9Results .v9-summary-stat { display: flex; flex-direction: column; justify-content: center; gap: 7px; min-width: 0; min-height: 132px; background: var(--elevated); border: 1px solid var(--border-strong); border-radius: 12px; padding: 20px; }
#tab-v9Results .v9-summary-stat b { color: var(--text1); font-family: var(--font-mono); font-size: var(--fs-xl); font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
#tab-v9Results .v9-summary-stat span { color: var(--text2); font-size: 11px; line-height: 1.35; letter-spacing: .05em; text-transform: uppercase; overflow-wrap: anywhere; }
#tab-v9Results .v9-story { margin: 32px 0; padding: 28px; border: 1px solid var(--border-strong); border-radius: 12px; background: var(--surface); min-width: 0; }
#tab-v9Results .v9-story-header { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 24px; align-items: flex-start; margin-bottom: 18px; }
#tab-v9Results .v9-story-header > div { min-width: 0; }
#tab-v9Results .v9-story-kicker { color: var(--data-gnn); font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
#tab-v9Results .v9-story-title { margin: 6px 0 7px; color: var(--text1); font-size: var(--fs-lg); font-weight: 700; letter-spacing: -.025em; line-height: 1.25; overflow-wrap: anywhere; }
#tab-v9Results .v9-story-intro { max-width: 760px; margin: 0; color: var(--text2); font-size: var(--fs-base); line-height: 1.6; }
#tab-v9Results .v9-story-note { max-width: 260px; padding: 13px 15px; border-left: 3px solid var(--warning); color: var(--text2); font-size: var(--fs-base); line-height: 1.5; }
#tab-v9Results .v9-story-note b { display: block; margin-bottom: 4px; color: var(--text1); font-size: 12px; }
#tab-v9Results .v9-lens-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
#tab-v9Results .v9-lens { min-width: 0; padding: 18px; border: 1px solid var(--border-strong); border-left: 3px solid var(--data-gnn); border-radius: 9px; background: var(--surface); }
#tab-v9Results .v9-lens:nth-child(2) { border-left-color: var(--warning); }
#tab-v9Results .v9-lens:nth-child(3) { border-left-color: var(--positive); }
#tab-v9Results .v9-lens h4 { margin: 0 0 7px; color: var(--text1); font-size: 13px; font-weight: 700; }
#tab-v9Results .v9-lens p { min-height: 0; max-width: 70ch; margin: 0; color: var(--text2); font-size: 13px; line-height: 1.55; }
#tab-v9Results .v9-lens-stat { margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--border); }
#tab-v9Results .v9-lens-stat b { display: block; color: var(--text1); font-family: var(--font-mono); font-size: 16px; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-lens-stat span { display: block; margin-top: 3px; color: var(--text2); font-size: var(--fs-xs); line-height: 1.35; }
#tab-v9Results .v9-card { background: var(--surface); border: 1px solid var(--border-strong); border-radius: 12px; padding: 28px; min-width: 0; overflow: hidden; box-shadow: var(--shadow-1); }
#tab-v9Results .v9-card-spaced { margin-top: 20px; }
#tab-v9Results .v9-card h3 { margin: 0 0 7px; font-size: 16px; font-weight: 600; color: var(--text1); letter-spacing: -0.015em; }
#tab-v9Results .v9-hint { max-width: 76ch; font-size: var(--fs-base); color: var(--text2); margin-bottom: 22px; line-height: 1.6; }
#tab-v9Results .v9-seg { display: inline-flex; flex-wrap: wrap; max-width: 100%; background: var(--elevated); border: 1px solid var(--border-strong); border-radius: 8px; padding: 4px; margin: 12px 0 24px; }
#tab-v9Results .v9-seg button { min-width: 0; background: transparent; color: var(--text2); border: 0; border-radius: 6px; font-weight: 500; font-size: 13px; padding: 6px 14px; cursor: pointer; transition: all 0.2s ease; }
#tab-v9Results .v9-seg button:hover { background: var(--accent-soft); color: var(--accent-hover); }
#tab-v9Results .v9-seg button.on { background: var(--accent-soft); color: var(--accent-hover); box-shadow: inset 0 0 0 1px var(--accent-glow); }
#tab-v9Results .v9-table-wrap { max-width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; }
#tab-v9Results table { border-collapse: collapse; width: 100%; font-size: 13px; font-variant-numeric: tabular-nums; }
#tab-v9Results th, #tab-v9Results td { border-bottom: 1px solid var(--border); padding: 14px 12px; text-align: right; white-space: nowrap; color: var(--text2); }
#tab-v9Results th:first-child, #tab-v9Results td:first-child { text-align: left; }
#tab-v9Results thead th { color: var(--text1); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; padding-bottom: 16px; border-bottom: 1px solid var(--border-strong); }
#tab-v9Results td.best { color: var(--positive); font-weight: 600; }
#tab-v9Results td.bad { color: var(--negative); }
#tab-v9Results .v9-pill { display: inline-flex; align-items: center; justify-content: center; border-radius: 999px; padding: 2px 8px; font-size: 10px; font-weight: 600; letter-spacing: 0.02em; text-transform: uppercase; }
#tab-v9Results .v9-pill.win { background: var(--accent-soft); color: var(--positive); }
#tab-v9Results .v9-pill.tie { background: var(--elevated); color: var(--text2); }
#tab-v9Results .v9-pill.loss { background: var(--negative-soft); color: var(--negative); }
#tab-v9Results .v9-capacity { display: grid; gap: 18px; }
#tab-v9Results .v9-capacity-group { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; }
#tab-v9Results .v9-capacity-budget { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; padding: 12px 16px; background: var(--elevated); border-bottom: 1px solid var(--border); }
#tab-v9Results .v9-capacity-budget strong { font-size: 13px; color: var(--text1); }
#tab-v9Results .v9-capacity-budget span { font-size: 11px; color: var(--text2); }
#tab-v9Results .v9-capacity-rows { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; background: var(--border); }
#tab-v9Results .v9-capacity-row { min-width: 0; padding: 20px; background: var(--surface); }
#tab-v9Results .v9-capacity-row.is-best { box-shadow: inset 3px 0 0 var(--positive); }
#tab-v9Results .v9-capacity-arm { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 14px; color: var(--text1); font-size: 13px; font-weight: 600; }
#tab-v9Results .v9-capacity-found { font-size: 24px; font-weight: 700; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-capacity-found small { display: block; margin-top: 2px; color: var(--text2); font-size: var(--fs-xs); font-weight: 600; letter-spacing: .05em; text-transform: uppercase; }
#tab-v9Results .v9-capacity-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
#tab-v9Results .v9-capacity-metric { padding-left: 9px; border-left: 1px solid var(--border-strong); }
#tab-v9Results .v9-capacity-metric b { display: block; color: var(--text1); font-size: 13px; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-capacity-metric span { display: block; margin-top: 3px; color: var(--text2); font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }
#tab-v9Results .v9-volume-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin: 22px 0 24px; min-width: 0; }
#tab-v9Results .v9-chart-stack { display: grid; gap: 20px; margin-top: 20px; min-width: 0; }
#tab-v9Results .v9-chart-block { min-width: 0; overflow: hidden; padding: 24px; border: 1px solid var(--border-strong); border-radius: 10px; background: var(--elevated); }
#tab-v9Results .v9-chart-block h4 { margin: 0 0 7px; color: var(--text1); font-size: 15px; font-weight: 600; }
#tab-v9Results .v9-volume-stat { min-width: 0; padding: 16px; border: 1px solid var(--border-strong); border-radius: 8px; background: var(--elevated); }
#tab-v9Results .v9-volume-stat b { display: block; color: var(--text1); font-size: 20px; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-volume-stat span { display: block; margin-top: 5px; color: var(--text2); font-size: 11px; line-height: 1.35; text-transform: uppercase; letter-spacing: .05em; overflow-wrap: anywhere; }
#tab-v9Results .v9-volume-chart, #tab-v9Results .v9-combined-chart { display: block; width: 100%; height: auto; overflow: visible; }
#tab-v9Results #v9-volume { width: 100%; min-width: 0; max-width: 100%; overflow-x: auto; overflow-y: hidden; -webkit-overflow-scrolling: touch; }
#tab-v9Results #v9-volume .v9-combined-chart { min-width: 720px; }
#tab-v9Results .v9-volume-chart text, #tab-v9Results .v9-combined-chart text { fill: var(--text2); font-family: inherit; font-size: var(--fs-xs); }
#tab-v9Results .v9-volume-area { fill: var(--accent-soft); }
#tab-v9Results .v9-volume-line { fill: none; stroke: var(--data-context); stroke-linecap: round; stroke-linejoin: round; stroke-width: 2.5; }
#tab-v9Results .v9-volume-rule { stroke: var(--border-strong); stroke-dasharray: 4 5; stroke-width: 1; opacity: .75; }
#tab-v9Results .v9-hover-guide { stroke: var(--text3); stroke-dasharray: 3 4; stroke-width: 1; opacity: 0; pointer-events: none; }
#tab-v9Results .v9-hover-target { fill: transparent; pointer-events: all; cursor: crosshair; }
#tab-v9Results .v9-hover-point { fill: var(--surface); stroke-width: 2; opacity: 0; pointer-events: none; }
#tab-v9Results .v9-daily-found-header { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px 16px; margin: 24px 0 10px; }
#tab-v9Results .v9-daily-found-header h4 { margin: 0; color: var(--text1); font-size: 13px; font-weight: 600; }
#tab-v9Results .v9-daily-found-select { background: var(--surface); color: var(--text1); border: 1px solid var(--border-strong); border-radius: 6px; padding: 6px 9px; font: inherit; font-size: 12px; }
#tab-v9Results .v9-daily-found-select:focus-visible, #tab-v9Results .v9-chart-toggle:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
#tab-v9Results .v9-chart-legend { display: flex; flex-wrap: wrap; gap: 10px 18px; margin: 0 0 12px; color: var(--text2); font-size: var(--fs-xs); }
#tab-v9Results .v9-chart-toggle { display: inline-flex; align-items: center; gap: 6px; padding: 3px 7px; border: 1px solid transparent; border-radius: 6px; background: transparent; color: var(--text2); font: inherit; font-size: 12px; cursor: pointer; }
#tab-v9Results .v9-chart-toggle:hover { border-color: var(--border-strong); color: var(--text1); }
#tab-v9Results .v9-chart-toggle[aria-pressed="false"] { opacity: .38; }
#tab-v9Results .v9-chart-key { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
#tab-v9Results .v9-chart-key.baseline { background: var(--data-baseline); }
#tab-v9Results .v9-chart-key.hybrid { background: var(--data-hybrid); }
#tab-v9Results .v9-chart-key.gnn { background: var(--data-gnn); }
#tab-v9Results .v9-chart-key.crossings { background: var(--data-context); }
#tab-v9Results .v9-chart-key.hidden-carriers { background: var(--data-gnn); }
#tab-v9Results .v9-found-chart { display: block; width: 100%; height: auto; overflow: visible; }
#tab-v9Results .v9-found-chart text { fill: var(--text2); font-family: inherit; font-size: var(--fs-xs); }
#tab-v9Results .v9-found-chart-rule { stroke: var(--border-strong); stroke-width: 1; opacity: .75; }
#tab-v9Results .v9-found-chart-line { fill: none; stroke-linecap: round; stroke-linejoin: round; stroke-width: 2.5; }
#tab-v9Results .v9-found-chart-line.baseline { stroke: var(--data-baseline); }
#tab-v9Results .v9-found-chart-line.hybrid { stroke: var(--data-hybrid); }
#tab-v9Results .v9-found-chart-line.gnn { stroke: var(--data-gnn); }
#tab-v9Results .v9-simulated-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 16px 0 18px; }
#tab-v9Results .v9-simulated-card { min-width: 0; padding: 14px; border: 1px solid var(--border-strong); border-left: 3px solid var(--data-baseline); border-radius: 8px; background: var(--surface); }
#tab-v9Results .v9-simulated-card.hybrid { border-left-color: var(--data-hybrid); }
#tab-v9Results .v9-simulated-card h5 { margin: 0 0 11px; color: var(--text1); font-size: 12px; font-weight: 600; }
#tab-v9Results .v9-simulated-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 9px 12px; }
#tab-v9Results .v9-simulated-metric { min-width: 0; padding-left: 8px; border-left: 1px solid var(--border-strong); }
#tab-v9Results .v9-simulated-metric b { display: block; color: var(--text1); font-size: 14px; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-simulated-metric span { display: block; margin-top: 3px; color: var(--text2); font-size: 11px; line-height: 1.35; letter-spacing: .02em; }
#tab-v9Results .v9-simulated-chart-scroll { width: 100%; min-width: 0; max-width: 100%; overflow-x: auto; overflow-y: hidden; -webkit-overflow-scrolling: touch; }
#tab-v9Results .v9-simulated-chart-scroll:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
#tab-v9Results .v9-simulated-chart { min-width: 720px; }
#tab-v9Results .v9-seg-small { margin: 0; padding: 3px; }
#tab-v9Results .v9-seg-small button { padding: 4px 10px; font-size: 12px; }
#tab-v9Results .v9-simulated-chart text { fill: var(--text2); font-size: 12px; }
#tab-v9Results .v9-explain { margin: -6px 0 22px; padding: 16px 18px; border: 1px solid var(--border-strong); border-left: 3px solid var(--data-gnn); border-radius: 9px; background: var(--elevated); }
#tab-v9Results .v9-explain-lead { margin: 0; color: var(--text2); font-size: 12px; line-height: 1.55; max-width: 780px; }
#tab-v9Results .v9-explain-lead b { color: var(--text1); }
#tab-v9Results .v9-explain-terms { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 10px 20px; margin: 14px 0 0; }
#tab-v9Results .v9-explain-terms > div { min-width: 0; }
#tab-v9Results .v9-explain-terms dt { color: var(--text1); font-family: var(--font-mono); font-size: 11px; font-weight: 600; letter-spacing: .01em; }
#tab-v9Results .v9-explain-terms dd { margin: 4px 0 0; color: var(--text2); font-size: 11px; line-height: 1.45; }
#tab-v9Results .v9-explain-terms dd .v9-pill { margin-right: 3px; vertical-align: baseline; }
#tab-v9Results .v9-explain-sep { color: var(--text3); padding: 0 3px; }
#tab-v9Results .v9-sig-note { margin: 0 0 12px; color: var(--text3); font-size: 11px; line-height: 1.45; max-width: 780px; }
#tab-v9Results .v9-explain-foot { margin: 14px 0 0; padding-top: 12px; border-top: 1px solid var(--border); color: var(--text3); font-size: 11px; line-height: 1.45; max-width: 780px; }
#tab-v9Results .v9-methods { margin-top: 28px; }
#tab-v9Results .v9-methods > h3 { margin: 0 0 12px; color: var(--text1); font-size: 20px; font-weight: 700; letter-spacing: -0.01em; }
#tab-v9Results .v9-methods > #v9-gnn-architecture-comparison { margin-top: 18px; }
#tab-v9Results .v9-sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
#tab-v9Results table.v9-sr-only { display: block; }
@media(max-width:700px){
  #tab-v9Results { padding: 28px 16px 40px; }
  #tab-v9Results .v9-sub { margin-bottom: 28px; }
  #tab-v9Results .v9-summary { grid-template-columns: 1fr 1fr; }
  #tab-v9Results .v9-summary-lead { grid-column: 1 / -1; }
  #tab-v9Results .v9-summary-stat { min-height: 104px; padding: 16px; }
  #tab-v9Results .v9-capacity-rows { grid-template-columns: 1fr; }
  #tab-v9Results .v9-capacity-row.is-best { box-shadow: inset 3px 0 0 var(--positive); }
  #tab-v9Results .v9-volume-summary { grid-template-columns: 1fr; gap: 8px; }
  #tab-v9Results .v9-story-header { display: block; }
  #tab-v9Results .v9-story-note { max-width: none; margin-top: 14px; }
  #tab-v9Results .v9-story { padding: 20px; }
  #tab-v9Results .v9-lens-grid { grid-template-columns: 1fr; }
  #tab-v9Results .v9-lens p { min-height: 0; }
  #tab-v9Results .v9-simulated-summary { grid-template-columns: 1fr; }
  #tab-v9Results .v9-daily-found-header { align-items: stretch; }
  #tab-v9Results .v9-daily-found-select { width: 100%; }
  #tab-v9Results .v9-capacity-budget { align-items: flex-start; flex-direction: column; }
  #tab-v9Results .v9-capacity-budget span { text-align: left; }
  #tab-v9Results .v9-capacity-arm { flex-wrap: wrap; }
  #tab-v9Results .v9-capacity-found { margin-left: auto; }
  #tab-v9Results .v9-summary-title, #tab-v9Results .v9-story-title, #tab-v9Results .v9-hint, #tab-v9Results .v9-sub { overflow-wrap: anywhere; }
  #tab-v9Results .v9-chart-block, #tab-v9Results .v9-card { padding: 20px; }
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
    const selected=budgets.includes(requestedBudget)?requestedBudget:(budgets.includes(5)?5:budgets[0]);
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
    const cumulativeByArm=Object.fromEntries(arms.map(a=>{
      let total=0;
      return [a,valuesByArm[a].map(value=>(total+=value))];
    }));
    const cumulativeMax=Math.max(1,...arms.map(a=>cumulativeByArm[a][cumulativeByArm[a].length-1]||0));
    const cumulativeMaxY=Math.max(1,Math.ceil(cumulativeMax));
    const cumulativeTicks=Array.from(new Set(Array.from({length:4},(_,i)=>Math.round(cumulativeMaxY*i/3))));
    return {available:true,budgets,selected,dates,valuesByArm,metricsByArm,foundMaxY,yTicks,dateTickIndexes,cumulativeByArm,cumulativeMaxY,cumulativeTicks};
}
"""

DAILY_CROSSING_SELECTION_JS = r"""
function selectDailyCrossingBudget(dks,current){
  const budgets=(Array.isArray(dks)?dks:[]).map(Number)
    .filter(Number.isFinite).sort((a,b)=>a-b);
  if(!budgets.length) return null;
  const requested=Number(current);
  return budgets.includes(requested)?requested:(budgets.includes(10)?10:budgets[0]);
}
"""

V9_RESULTS_JS = r"""v9Results:{rendered:false,render(){
  if(this.rendered) return; this.rendered=true;
  const sec=document.getElementById('tab-v9Results');
""" + DAILY_CROSSING_SELECTION_JS + r"""
  const demo=(typeof DATA!=='undefined'&&DATA)?DATA.v9Demo:null;
  if(!demo){sec.innerHTML='<div class="v9-card">No V9 demo result is embedded in data_v9.json.</div>';return;}

  const fmt=n=>Number(n||0).toLocaleString();
  const pct=v=>(Number(v||0)*100).toFixed(1)+'%';
  const preferredArms=['baseline','hybrid','gnn'];
  const armLabel=a=>a==='baseline'?'Baseline':(a==='hybrid'?'Deployable Hybrid':'GNN');
  const supportedDailyKs=[5,10,25];
  const publishedDailyKs=(demo.daily_ks||[]).map(Number).filter(k=>supportedDailyKs.includes(k)).sort((a,b)=>a-b);
  const headlineDailyK=publishedDailyKs.includes(25)?25:(publishedDailyKs[publishedDailyKs.length-1]||5);
  const headlineBaseline=Number((demo.overall_daily.baseline||{})['daily_found@'+headlineDailyK]||0);
  const headlineHybrid=Number((demo.overall_daily.hybrid||{})['daily_found@'+headlineDailyK]||0);
  const headlineGnn=demo.overall_daily&&demo.overall_daily.gnn?Number((demo.overall_daily.gnn||{})['daily_found@'+headlineDailyK]||0):null;
  const headlineDelta=headlineHybrid-headlineBaseline;
  const headlineLift=headlineBaseline?headlineDelta/headlineBaseline:null;
  const dailyBaselineAtK=headlineBaseline;
  const dailyHybridAtK=headlineHybrid;
  const dailyBudgetAtK=Number((demo.overall_daily.baseline||{})['daily_budget@'+headlineDailyK]||0);
  const dailyDays=Number((demo.overall_daily.baseline||{}).n_days||0);
  let simMode='cumulative';
  const modelVisibility={baseline:true,hybrid:true,gnn:true};
  const layerVisibility={crossings:true,'hidden-carriers':true};

  sec.innerHTML='<h2>V9 Positive Control</h2>'
    +'<div class="v9-sub">Leak-safe baselines use row-level history and context. GNN arms add as-of relational signals.</div>'
    +'<div id="v9-summary" class="v9-summary" aria-label="V9 result summary">'
    +'<div class="v9-summary-lead"><div class="v9-summary-kicker">Operational headline</div><div class="v9-summary-title">Deployable Hybrid records '+fmt(headlineDelta)+' more hidden-positive event hits at '+fmt(headlineDailyK)+'/day.</div><div class="v9-summary-copy">'+fmt(headlineHybrid)+' event hits vs '+fmt(headlineBaseline)+' for the baseline ('+(headlineLift==null?'n/a':pct(headlineLift))+' lift). GNN event-hit ceiling: '+(headlineGnn==null?'n/a':fmt(headlineGnn))+'. Daily metrics count events, not unique people.</div><a class="v9-summary-link" href="#v9-case-evidence">Inspect seed-0 unique-person recovery evidence →</a></div>'
    +'<div class="v9-summary-stat"><b>'+fmt(headlineHybrid)+'</b><span>Hybrid event hits</span></div>'
    +'<div class="v9-summary-stat"><b>'+fmt(headlineBaseline)+'</b><span>Baseline event hits</span></div>'
    +'<div class="v9-summary-stat"><b>'+(headlineGnn==null?'n/a':fmt(headlineGnn))+'</b><span>GNN event-hit ceiling</span></div>'
    +'</div>'
    +'<section class="v9-story" aria-labelledby="v9-story-title"><div class="v9-story-header"><div><div class="v9-story-kicker">How to read this tab</div><h3 id="v9-story-title" class="v9-story-title">Read the V9 result as a daily operating view</h3><p class="v9-story-intro">Every result uses a fixed daily inspection budget. The recovery explorer separately counts unique people.</p></div><div class="v9-story-note"><b>The short version</b>The graph advantage appears at operational depth.</div></div><div class="v9-lens-grid"><article class="v9-lens"><h4>Daily event operations</h4><p>Each of '+fmt(dailyDays)+' test days gets its own '+fmt(headlineDailyK)+'/day quota, or '+fmt(dailyBudgetAtK)+' inspections in total.</p><div class="v9-lens-stat"><b>'+fmt(dailyHybridAtK)+' vs '+fmt(dailyBaselineAtK)+'</b><span>Hybrid vs baseline event hits at '+fmt(headlineDailyK)+'/day</span></div></article></div></section>'
    +'<div class="v9-chart-stack">'
    +'<section class="v9-chart-block" aria-labelledby="v9-crossing-volume-title"><div class="v9-daily-found-header"><h4 id="v9-crossing-volume-title">Daily Crossing Volume</h4><label><span class="v9-sr-only">Daily inspection budget</span><select id="v9-daily-found-k" class="v9-daily-found-select"></select></label></div><div class="v9-hint">Daily crossing volume and hidden-positive event hits by model. Toggle a model to show or hide its line.</div><div id="v9-volume"></div></section>'
    +'<div class="v9-card v9-card-spaced"><h3>Daily capacity view</h3><div class="v9-hint">Found, precision, recall, and F1 under fixed per-day inspection budgets.</div><div id="v9-daily"></div></div>'
    +'<section id="v9-simulated-catches" class="v9-chart-block" aria-labelledby="v9-simulated-title"><div class="v9-daily-found-header"><h4 id="v9-simulated-title">Simulated catches</h4><div class="v9-seg v9-seg-small" id="v9-simulated-mode" role="group" aria-label="Simulated chart mode"><button data-v="cumulative" class="on" aria-pressed="true">Cumulative</button><button data-v="daily" aria-pressed="false">Daily</button></div><label><span class="v9-sr-only">Simulated daily inspection budget</span><select id="v9-simulated-k" class="v9-daily-found-select"></select></label></div><div class="v9-hint">Unique people caught for the first time. A caught person leaves the pool.</div><div id="v9-simulated-summary" class="v9-simulated-summary"></div><div id="v9-simulated-volume"></div></section>'
    +'</div>'
    +'<section id="v9-case-evidence" aria-labelledby="v9-recovery-title"></section>'
    +'<div class="v9-card v9-card-spaced"><h3>Daily bootstrap verdicts</h3><div class="v9-hint">Does the Hybrid event-hit lead persist when we re-draw the test events many times and keep the same daily inspection quota?</div>'
    +'<div class="v9-explain"><p class="v9-explain-lead">Each replicate samples test events with replacement. Both rankers score the same sample, rank within each day, and use the same quota. The table shows the Hybrid-minus-baseline gap in hidden-positive event hits across re-draws.</p>'
    +'<dl class="v9-explain-terms">'
    +'<div><dt>What is re-sampled?</dt><dd>Test events are sampled with replacement, then ranked within each day under the same quota.</dd></div>'
    +'<div><dt>What is measured?</dt><dd>The Hybrid-minus-baseline gap in hidden-positive event hits.</dd></div>'
    +'<div><dt>What does 95% CI mean here?</dt><dd>The middle 95% of re-drawn gaps. This shows resampling variability—not the probability that the true gap lies inside.</dd></div>'
    +'<div><dt>How should it be read?</dt><dd><span class="v9-pill win">Hybrid win</span> if above zero <span class="v9-explain-sep">/</span> <span class="v9-pill tie">wash</span> if it crosses zero <span class="v9-explain-sep">/</span> <span class="v9-pill loss">baseline win</span> if below zero</dd></div>'
    +'</dl>'
    +'<p class="v9-explain-foot">Each day uses a fixed quota. Rows count event hits, not unique people; use the recovery explorer for unique-person recovery.</p></div>'
    +'<div class="v9-table-wrap" id="v9-sig"></div></div>'
    +'<section class="v9-methods" aria-labelledby="v9-methods-title"><h3 id="v9-methods-title">Methods</h3>'
    +'<section id="v9-gnn-architecture-comparison" aria-labelledby="v9-gnn-architecture-title"></section></section>';

  mountV9RecoveryExplainer(
    document.getElementById('v9-case-evidence'),
    (typeof DATA!=='undefined'&&DATA)?DATA.v9RecoveryExplainer:null,
    {fmt,pct,esc}
  );
  mountV9GNNArchitectureComparison(document.getElementById('v9-gnn-architecture-comparison'), (typeof DATA!=='undefined'&&DATA)?DATA.v9GNNArchitectureComparison:null, {fmt,pct,esc}, (typeof DATA!=='undefined'&&DATA)?DATA.demoComparison:null);
  function pill(summary){
    if(!summary) return '<span class="v9-pill tie">n/a</span>';
    const lo=Number(summary.ci[0]), hi=Number(summary.ci[1]);
    if(lo>0) return '<span class="v9-pill win">Hybrid win</span>';
    if(hi<0) return '<span class="v9-pill loss">baseline win</span>';
    return '<span class="v9-pill tie">wash</span>';
  }

  function drawDaily(){
    const el=document.getElementById('v9-daily'); if(!el) return;
    const od=demo.overall_daily;
    if(!od){el.innerHTML='<div class="v9-hint">No daily-capacity metric in this result (re-run the demo to populate it).</div>';return;}
    const dks=(demo.daily_ks||[]).map(Number).filter(k=>supportedDailyKs.includes(k)).sort((a,b)=>a-b);
    const arms=['baseline','hybrid'].filter(a=>od[a]);
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
    const od=demo.overall_daily||{}, arms=['baseline','hybrid'].filter(a=>od[a]);
    const dks=(demo.daily_ks||[]).map(Number).filter(k=>supportedDailyKs.includes(k)).sort((a,b)=>a-b);
    if(!select||!arms.length||!dks.length){el.innerHTML='<div class="v9-hint">No daily model catch series is embedded in this dashboard.</div>';return;}
    const selected=selectDailyCrossingBudget(dks,select.value);
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
    const modeSeg=document.getElementById('v9-simulated-mode');
    if(modeSeg&&!modeSeg.dataset.wired){
      modeSeg.dataset.wired='1';
      modeSeg.addEventListener('click',e=>{
        const b=e.target.closest('button'); if(!b) return;
        simMode=b.dataset.v;
        modeSeg.querySelectorAll('button').forEach(x=>{const on=x===b;x.classList.toggle('on',on);x.setAttribute('aria-pressed',String(on));});
        drawSimulatedCatches();
      });
    }
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
    const dates=view.dates;
    const plotByArm=simMode==='cumulative'?view.cumulativeByArm:view.valuesByArm;
    const plotMaxY=simMode==='cumulative'?view.cumulativeMaxY:view.foundMaxY;
    const plotTicks=simMode==='cumulative'?view.cumulativeTicks:view.yTicks;
    const yAxisTitle=simMode==='cumulative'?'total unique people caught':'new unique people / day';
    const width=720, height=240, left=48, right=20, top=24, bottom=42, chartW=width-left-right, chartH=height-top-bottom;
    const x=i=>left+(dates.length===1?chartW/2:i*chartW/(dates.length-1)), y=v=>top+chartH-(v/plotMaxY)*chartH;
    const ticks=view.dateTickIndexes.map(i=>'<text x="'+x(i).toFixed(1)+'" y="'+(height-14)+'" text-anchor="'+(i===0?'start':i===dates.length-1?'end':'middle')+'">'+esc(dates[i])+'</text>').join('');
    const rules=plotTicks.map(v=>'<line class="v9-found-chart-rule" x1="'+left+'" x2="'+(width-right)+'" y1="'+y(v).toFixed(1)+'" y2="'+y(v).toFixed(1)+'"/><text x="'+(left-8)+'" y="'+(y(v)+4).toFixed(1)+'" text-anchor="end">'+fmt(v)+'</text>').join('');
    const lines=arms.map(a=>'<path class="v9-found-chart-line '+a+'" d="'+plotByArm[a].map((value,i)=>(i?'L':'M')+x(i).toFixed(1)+' '+y(value).toFixed(1)).join(' ')+'"/>').join('');
    const points=arms.map(a=>plotByArm[a].map((value,i)=>'<circle class="v9-hover-point '+a+'" data-arm="'+a+'" data-index="'+i+'" cx="'+x(i).toFixed(1)+'" cy="'+y(value).toFixed(1)+'" r="4" stroke="'+(a==='baseline'?'#64748b':'#16a34a')+'"/>').join('')).join('');
    const accessibleName='Simulated first-time recoveries at '+fmt(selected)+' inspections per day: Baseline and Deployable Hybrid '+(simMode==='cumulative'?'cumulative unique people caught':'daily new unique people caught');
    const accessibleRows=dates.map((date,i)=>'<tr><td>'+esc(date)+'</td><td>'+fmt(plotByArm.baseline[i])+'</td><td>'+fmt(plotByArm.hybrid[i])+'</td></tr>').join('');
    chartEl.innerHTML='<div class="v9-chart-legend" aria-label="Simulated-catch model legend"><span><i class="v9-chart-key baseline"></i> Baseline</span><span><i class="v9-chart-key hybrid"></i> Deployable Hybrid</span></div><div class="v9-simulated-chart-scroll" tabindex="0" role="region" aria-label="'+esc(accessibleName)+' chart"><svg class="v9-found-chart v9-simulated-chart" viewBox="0 0 '+width+' '+height+'" role="img" aria-label="'+esc(accessibleName)+'" aria-describedby="v9-simulated-data-'+selected+'"><text x="'+left+'" y="12">'+esc(yAxisTitle)+'</text>'+rules+lines+points+'<line class="v9-hover-guide" x1="'+left+'" x2="'+left+'" y1="'+top+'" y2="'+(top+chartH)+'"/>'+ticks+'<rect class="v9-hover-target" x="'+left+'" y="'+top+'" width="'+chartW+'" height="'+chartH+'"/></svg></div><table id="v9-simulated-data-'+selected+'" class="v9-sr-only"><caption>'+esc(accessibleName)+'</caption><thead><tr><th>Date</th><th>Baseline</th><th>Deployable Hybrid</th></tr></thead><tbody>'+accessibleRows+'</tbody></table>';
    const svg=chartEl.querySelector('svg'), guide=svg.querySelector('.v9-hover-guide'), target=svg.querySelector('.v9-hover-target'), hoverPoints=svg.querySelectorAll('.v9-hover-point');
    const indexAt=e=>{const p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;const local=p.matrixTransform(svg.getScreenCTM().inverse());return Math.max(0,Math.min(dates.length-1,Math.round((local.x-left)/Math.max(1,chartW/Math.max(1,dates.length-1)))));};
    target.addEventListener('pointermove',e=>{const i=indexAt(e);guide.setAttribute('x1',x(i).toFixed(1));guide.setAttribute('x2',x(i).toFixed(1));guide.style.opacity='1';hoverPoints.forEach(point=>point.style.opacity=Number(point.dataset.index)===i?'1':'0');showTip(e,'<b>'+esc(dates[i])+'</b><br>'+fmt(selected)+' inspections / day<br>'+arms.map(a=>esc(armLabel(a))+': '+fmt(plotByArm[a][i])).join('<br>'));});
    target.addEventListener('pointerleave',()=>{guide.style.opacity='0';hoverPoints.forEach(point=>point.style.opacity='0');hideTip();});
  }

  function drawSig(){
    const dailyWins=demo.win_hybrid_daily||{};
    const dailyBaseline=demo.overall_daily&&demo.overall_daily.baseline||{};
    let h='<h4 style="margin: 4px 0 4px; font-size: 13px; font-weight: 600; color: var(--text1);">Daily-capacity bootstrap</h4>';
    h+='<div class="v9-sig-note">Every one of the '+fmt(dailyDays)+' test days gets the same quota, so the total is what fixed staffing would actually inspect. Whole-pool events.</div>';
    h+='<table><thead><tr><th>per-day budget</th><th>mean diff</th><th>95% CI</th><th>p(Hybrid&lt;=base)</th><th>verdict</th></tr></thead><tbody>';
    publishedDailyKs.forEach(k=>{
      const s=dailyWins['hybrid_vs_baseline_daily@'+k];
      if(!s) return;
      h+='<tr><td>'+fmt(dailyBaseline['daily_budget@'+k]||k)+' total ('+fmt(k)+'/day)</td><td class="'+(s.mean_diff<0?'bad':'best')+'">'+(s.mean_diff>0?'+':'')+s.mean_diff+'</td>'
        +'<td>['+s.ci[0]+', '+s.ci[1]+']</td><td>'+s.p_enh_le_base+'</td><td>'+pill(s)+'</td></tr>';
    });
    h+='</tbody></table>';
    document.getElementById('v9-sig').innerHTML=h;
  }

  function draw(){drawDaily();drawCombined();drawSig();}
  draw();
  drawSimulatedCatches();
}},
"""

UNSUP_AD_CSS = r"""
#tab-unsupervisedAD {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  overflow-x: clip;
  padding: 32px 24px;
  max-width: 1200px;
  font-family: var(--font-body);
  color: var(--text1);
}
.uad-header { margin-bottom: 40px; }
.uad-header h2 {
  font-size: var(--fs-xl);
  font-weight: 700;
  color: var(--text1);
  margin: 0 0 12px 0;
  letter-spacing: -0.02em;
}
.uad-header p {
  color: var(--text2);
  font-size: var(--fs-base);
  line-height: 1.6;
  max-width: 750px;
  margin: 0;
}
.uad-mode-heading {
  margin: 32px 0 14px;
  color: var(--text1);
  font-size: var(--fs-lg);
  font-weight: 700;
}
.uad-note {
  color: var(--text2);
  font-size: var(--fs-base);
  line-height: 1.5;
}
.uad-note { max-width: 850px; margin: 0 0 20px; }
.uad-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(360px, 100%), 1fr));
  gap: 28px;
}
.uad-card {
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  padding: 24px;
  position: relative;
  overflow: hidden;
  box-shadow: var(--shadow-1);
}
.uad-region-name {
  font-size: var(--fs-lg);
  font-weight: 600;
  color: var(--text1);
  margin: 0 0 24px 0;
  display: flex;
  align-items: center;
}
.uad-arm { margin: 0 0 30px; }
.uad-arm-header {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 14px;
  margin: 0 0 12px;
}
.uad-arm-header h4 { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--text1); font-size: var(--fs-base); }
.uad-arm-key { width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex: none; }
.uad-arm-header span { color: var(--text2); font-size: var(--fs-xs); }
.uad-region-table { width: 100%; min-width: 0; border-collapse: collapse; font-size: var(--fs-xs); }
.uad-region-table th, .uad-region-table td {
  padding: 12px 10px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  vertical-align: top;
  white-space: normal;
  color: var(--text2);
}
.uad-region-table th { width: 48%; color: var(--text1); font-weight: 600; }
.uad-region-table td { color: var(--text2); font-variant-numeric: tabular-nums; }
.uad-skipped {
  padding: 12px 14px;
  border: 1px dashed var(--border-strong);
  border-radius: 8px;
  color: var(--text2);
  font-size: var(--fs-base);
}
.uad-appendix {
  margin-top: 36px;
  padding-top: 24px;
  border-top: 1px solid var(--border-strong);
}
.uad-empty { color: var(--text2); font-size: var(--fs-base); }
.uad-figures {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  margin: 0 0 28px;
}
.uad-figure {
  min-width: 0;
  width: 100%;
  max-width: 820px;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 20px;
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  background: var(--surface);
}
.uad-figure h4 {
  margin: 0 0 5px;
  color: var(--text1);
  font-size: var(--fs-md);
  font-weight: 600;
}
.uad-figure-sub {
  margin: 0 0 12px;
  color: var(--text2);
  font-size: var(--fs-xs);
  line-height: 1.45;
}
.uad-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  margin: 0 0 10px;
  color: var(--text2);
  font-size: var(--fs-xs);
}
.uad-legend span { display: inline-flex; align-items: center; gap: 6px; }
.uad-legend i {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  display: inline-block;
  flex: none;
}
.uad-legend svg { display: block; overflow: visible; flex: none; }
.uad-legend-shape { fill: var(--text2); }
.uad-legend i.uad-legend-rule { width: 14px; height: 0; border-radius: 0; border-top: 1px solid var(--border-strong); }
.uad-chart { display: block; width: 100%; min-width: 720px; height: auto; overflow: visible; }
.uad-chart text { fill: var(--text2); font-family: inherit; font-size: var(--fs-xs); }
.uad-chart text.uad-axis-title { fill: var(--text2); font-size: var(--fs-xs); letter-spacing: .04em; text-transform: uppercase; }
.uad-chart text.uad-value { fill: var(--text1); font-size: var(--fs-xs); font-variant-numeric: tabular-nums; }
.uad-chart text.uad-ref { fill: var(--text2); font-size: var(--fs-xs); }
.uad-chart .uad-rule { stroke: var(--border-strong); stroke-width: 1; opacity: .72; }
.uad-chart .uad-baseline { stroke: var(--border-strong); stroke-width: 1; }
.uad-chart .uad-ref-rule { stroke: var(--border-strong); stroke-width: 1; }
.uad-chart .uad-dot { stroke: var(--surface); stroke-width: 2; }
.uad-chart .uad-track { fill: none; stroke: var(--border-strong); stroke-width: 1; stroke-linejoin: round; }
.uad-chart .uad-hit { fill: transparent; pointer-events: all; cursor: pointer; }
.uad-strata { margin: -6px 0 16px; display: grid; gap: 7px; }
.uad-strata-row {
  display: grid;
  grid-template-columns: minmax(0, 126px) 1fr 46px;
  gap: 10px;
  align-items: center;
  color: var(--text2);
  font-size: var(--fs-xs);
}
.uad-strata-row > span { min-width: 0; overflow-wrap: anywhere; white-space: normal; }
.uad-strata-row > b { color: var(--text1); font-size: var(--fs-xs); font-variant-numeric: tabular-nums; text-align: right; }
.uad-strata-track { height: 6px; border-radius: 999px; background: var(--elevated); overflow: hidden; }
.uad-strata-fill { height: 100%; border-radius: 999px; }
.uad-strata-scale { margin-top: 2px; color: var(--text3); font-size: 10px; }
.uad-sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
table.uad-sr-only { display: block; }
@media(max-width:700px){
  #tab-unsupervisedAD { padding: 28px 16px 40px; }
  .uad-grid { grid-template-columns: minmax(0, 1fr); }
  .uad-card, .uad-figure { padding: 20px; }
  .uad-figure { max-width: none; }
  .uad-strata-row { grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr) 44px; }
}
"""

UNSUP_AD_NAV_BTN = '  <button data-tab="unsupervisedAD" aria-controls="tab-unsupervisedAD" aria-selected="false">Anomaly ranking</button>\n'
UNSUP_AD_SECTION = '  <section id="tab-unsupervisedAD" class="tab-content"></section>\n'

UNSUP_AD_VIEW_MODEL_JS = r"""
function buildUnsupervisedADViewModel(ad){
  const PRIMARY_IDS=new Set([
    'tabular_unlabeled',
    'relational_unlabeled',
    'relational_caught_supervised'
  ]);
  const ABLATION_IDS=new Set(['tabular_caught_supervised']);
  const arms=ad&&ad.arms&&typeof ad.arms==='object'?ad.arms:{};
  const metadata=ad&&ad.arm_metadata&&typeof ad.arm_metadata==='object'
    ?ad.arm_metadata:{};
  const orderedIds=(order, allowed)=>{
    const seen=new Set();
    return (Array.isArray(order)?order:[]).filter(id=>{
      if(!allowed.has(id)||seen.has(id)) return false;
      seen.add(id);
      return true;
    });
  };
  const read=(obj, key)=>obj&&obj[key]!==undefined?obj[key]:null;
  const normalizeRegion=(region, raw)=>{
    raw=raw&&typeof raw==='object'?raw:{};
    if(raw.status==='skipped') return {
      region,
      status:'skipped',
      skipReason:String(raw.skip_reason||'No reason recorded')
    };
    const threshold=raw.threshold_metadata||{};
    const scoredTest=raw.scored_test||{};
    const labels=raw.label_metadata||{};
    const evaluation=raw.evaluation_only||{};
    const allCarrier=evaluation.all_carrier_events||{};
    const missed=evaluation.missed_at_event||{};
    const noPrior=evaluation.no_prior_catch_missed_events||{};
    const neverCaught=evaluation.lifetime_never_caught_people||{};
    const observed=evaluation.observed_catch_enrichment||{};
    return {
      region,
      status:String(raw.status||'completed'),
      metrics:{
        featureCount:read(raw,'feature_count'),
        thresholdSource:read(threshold,'threshold_source'),
        frozenThreshold:read(scoredTest,'threshold'),
        thresholdQuantile:read(threshold,'threshold_quantile'),
        thresholdComparator:read(threshold,'threshold_comparator'),
        realizedTestAlertRate:read(raw,'realized_test_alert_rate')
          ??read(threshold,'realized_test_alert_rate'),
        caughtPositiveCount:read(labels,'caught_positive_count'),
        immatureLabelCount:read(labels,'immature_label_count'),
        fitSignal:read(labels,'fit_signal'),
        allCarrierRecall:read(allCarrier,'recall'),
        allCarrierPrecision:read(allCarrier,'precision'),
        missedRecall:read(missed,'recall'),
        missedPrecision:read(missed,'precision'),
        noPriorMissedRecall:read(noPrior,'recall'),
        lifetimeNeverCaughtRecall:read(neverCaught,'recall'),
        lifetimeNeverCaughtFound:read(neverCaught,'found'),
        observedCatchPrecision:read(observed,'precision'),
        observedCatchLift:read(observed,'lift_over_prevalence')
      }
    };
  };
  const normalizeArm=id=>({
    id,
    metadata:metadata[id]||{},
    regions:Object.entries(arms[id]||{}).map(
      ([region, raw])=>normalizeRegion(region, raw)
    )
  });
  const primaryArmIds=orderedIds(ad&&ad.primary_arm_order, PRIMARY_IDS);
  const ablationArmIds=orderedIds(ad&&ad.ablation_arm_order, ABLATION_IDS);
  return {
    primaryArmIds,
    ablationArmIds,
    primary:primaryArmIds.map(normalizeArm),
    ablation:ablationArmIds.map(normalizeArm)
  };
}
"""

# Categorical slots 1-4 of the validated dark-surface palette, in the fixed
# progression order. Assignment follows the arm identity, never its rank, so a
# missing arm never repaints the others.
UNSUP_AD_CHART_JS = r"""
const UAD_ARM_COLORS={
  tabular_unlabeled:'#3987e5',
  relational_unlabeled:'#d95926',
  relational_caught_supervised:'#199e70',
  tabular_caught_supervised:'#c98500'
};
const UAD_REGION_SHAPES=['circle','square','triangle','diamond'];

function buildUnsupervisedADChartModel(view){
  const toSeries=arms=>(Array.isArray(arms)?arms:[]).map(arm=>{
    const byRegion={};
    (arm&&arm.regions?arm.regions:[]).forEach(region=>{
      if(region&&region.status!=='skipped'&&region.metrics) byRegion[region.region]=region.metrics;
    });
    return {
      id:arm.id,
      label:(arm.metadata&&arm.metadata.label)||arm.id,
      color:UAD_ARM_COLORS[arm.id]||UAD_ARM_COLORS.tabular_unlabeled,
      byRegion
    };
  }).filter(series=>Object.keys(series.byRegion).length>0);
  const primary=toSeries(view&&view.primary);
  const ablation=toSeries(view&&view.ablation);
  const regions=[];
  primary.concat(ablation).forEach(series=>Object.keys(series.byRegion).forEach(region=>{
    if(regions.indexOf(region)<0) regions.push(region);
  }));
  return {available:primary.length>0&&regions.length>0,regions,primary,ablation};
}

function uadMetric(series,region,key){
  const metrics=series&&series.byRegion?series.byRegion[region]:null;
  const value=metrics?metrics[key]:null;
  return typeof value==='number'&&isFinite(value)?value:null;
}

function uadNiceMax(values,step,floor){
  const finite=(values||[]).filter(value=>typeof value==='number'&&isFinite(value));
  const peak=Math.max(finite.length?Math.max.apply(null,finite):0,floor||0);
  const size=step>0?step:1;
  return Math.max(size,Math.ceil((peak-1e-9)/size)*size);
}

/* Grow the tick step through the 1-2-5 ladder until the axis tops out in at
   most maxTicks intervals, so every printed tick stays a round number. */
function uadAxis(values,step,floor,maxTicks){
  const ladder=[1,2,5];
  const limit=Math.max(2,maxTicks||5);
  let size=step>0?step:1;
  let guard=0;
  let max=uadNiceMax(values,size,floor);
  while(Math.round(max/size)>limit&&guard<24){
    const decade=Math.pow(10,Math.floor(Math.log10(size)+1e-9));
    const index=ladder.indexOf(Math.round(size/decade));
    size=index<0||index===ladder.length-1?decade*10:decade*ladder[index+1];
    max=uadNiceMax(values,size,floor);
    guard+=1;
  }
  const ticks=[];
  for(let value=0;value<=max+size/2;value+=size) ticks.push(Number(value.toFixed(10)));
  return {max,step:size,ticks};
}

function uadTicks(max,count){
  const steps=Math.max(1,count||4);
  const out=[];
  for(let i=0;i<=steps;i++) out.push(max*i/steps);
  return out;
}

function uadBarPath(x,y,w,h,r){
  const radius=Math.max(0,Math.min(r,w/2,h));
  return 'M'+x.toFixed(1)+' '+(y+h).toFixed(1)
    +' V'+(y+radius).toFixed(1)
    +' Q'+x.toFixed(1)+' '+y.toFixed(1)+' '+(x+radius).toFixed(1)+' '+y.toFixed(1)
    +' H'+(x+w-radius).toFixed(1)
    +' Q'+(x+w).toFixed(1)+' '+y.toFixed(1)+' '+(x+w).toFixed(1)+' '+(y+radius).toFixed(1)
    +' V'+(y+h).toFixed(1)+' Z';
}

function uadShapeMark(shape,cx,cy,size,attrs){
  const extra=attrs||'';
  const points=list=>list.map(p=>p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ');
  if(shape==='square') return '<rect'+extra+' x="'+(cx-size).toFixed(1)+'" y="'+(cy-size).toFixed(1)
    +'" width="'+(size*2).toFixed(1)+'" height="'+(size*2).toFixed(1)+'" rx="1.5"/>';
  if(shape==='triangle') return '<polygon'+extra+' points="'
    +points([[cx,cy-size*1.2],[cx+size*1.15,cy+size*0.85],[cx-size*1.15,cy+size*0.85]])+'"/>';
  if(shape==='diamond') return '<polygon'+extra+' points="'
    +points([[cx,cy-size*1.3],[cx+size*1.3,cy],[cx,cy+size*1.3],[cx-size*1.3,cy]])+'"/>';
  return '<circle'+extra+' cx="'+cx.toFixed(1)+'" cy="'+cy.toFixed(1)+'" r="'+size.toFixed(1)+'"/>';
}

function uadColorLegend(series,extra){
  return '<div class="uad-legend">'+series.map(item=>'<span><i style="background:'+item.color+'"></i>'
    +esc(item.label)+'</span>').join('')
    +(extra?'<span><i class="uad-legend-rule"></i>'+esc(extra)+'</span>':'')+'</div>';
}

function uadShapeLegend(groups){
  return '<div class="uad-legend">'+groups.map((group,index)=>'<span><svg width="12" height="12" '
    +'viewBox="-6 -6 12 12" aria-hidden="true">'
    +uadShapeMark(UAD_REGION_SHAPES[index%UAD_REGION_SHAPES.length],0,0,4,' class="uad-legend-shape"')
    +'</svg>'+esc(group)+'</span>').join('')+'</div>';
}

function uadDataTable(id,caption,rowHeader,groups,series,cell){
  return '<table id="'+id+'" class="uad-sr-only"><caption>'+esc(caption)+'</caption><thead><tr><th>'
    +esc(rowHeader)+'</th>'+series.map(item=>'<th>'+esc(item.label)+'</th>').join('')
    +'</tr></thead><tbody>'+groups.map(group=>'<tr><td>'+esc(group)+'</td>'
    +series.map(item=>'<td>'+esc(cell(item,group))+'</td>').join('')+'</tr>').join('')
    +'</tbody></table>';
}

function uadColumnChart(spec){
  const groups=spec.groups||[], series=spec.series||[];
  if(!groups.length||!series.length||!(spec.max>0)) return '';
  const W=680, H=280, padL=54, padR=18, padT=34, padB=56;
  const chartW=W-padL-padR, chartH=H-padT-padB;
  const band=chartW/groups.length;
  const gap=2, innerPad=Math.min(34,band*0.26);
  const barW=Math.max(4,Math.min(24,(band-innerPad-gap*(series.length-1))/series.length));
  const groupW=barW*series.length+gap*(series.length-1);
  const scale=value=>padT+chartH-(Math.max(0,Math.min(value,spec.max))/spec.max)*chartH;
  const ticks=spec.ticks||uadTicks(spec.max,4);
  let body=ticks.map(tick=>'<line class="uad-rule" x1="'+padL+'" x2="'+(W-padR)+'" y1="'+scale(tick).toFixed(1)
    +'" y2="'+scale(tick).toFixed(1)+'"/><text x="'+(padL-9)+'" y="'+(scale(tick)+4).toFixed(1)
    +'" text-anchor="end">'+esc(spec.tickLabel(tick))+'</text>').join('');
  if(spec.reference&&spec.reference.value>0&&spec.reference.value<spec.max){
    const refY=scale(spec.reference.value);
    body+='<line class="uad-ref-rule" x1="'+padL+'" x2="'+(W-padR)+'" y1="'+refY.toFixed(1)
      +'" y2="'+refY.toFixed(1)+'"/>';
  }
  body+='<line class="uad-baseline" x1="'+padL+'" x2="'+(W-padR)+'" y1="'+scale(0).toFixed(1)
    +'" y2="'+scale(0).toFixed(1)+'"/>';
  groups.forEach((group,groupIndex)=>{
    const left=padL+groupIndex*band+(band-groupW)/2;
    const values=series.map(item=>spec.value(item,group));
    const best=values.reduce((acc,value)=>value===null?acc:(acc===null||value>acc?value:acc),null);
    let labelled=false;
    series.forEach((item,seriesIndex)=>{
      const value=values[seriesIndex];
      const x=left+seriesIndex*(barW+gap);
      if(value!==null){
        const top=scale(value), height=scale(0)-top;
        if(height>0.5) body+='<path fill="'+item.color+'" d="'+uadBarPath(x,top,barW,height,4)+'"/>';
        if(!labelled&&best!==null&&value===best&&value>0){
          labelled=true;
          body+='<text class="uad-value" x="'+(x+barW/2).toFixed(1)+'" y="'+(top-7).toFixed(1)
            +'" text-anchor="middle">'+esc(spec.valueLabel(value))+'</text>';
        }
      }
      body+='<rect class="uad-hit" x="'+(x-gap).toFixed(1)+'" y="'+padT+'" width="'+(barW+gap*2).toFixed(1)
        +'" height="'+chartH+'" data-tip="'+esc('<b>'+group+'</b><br>'+item.label+': '
        +(value===null?'not reported':spec.valueLabel(value)))+'"/>';
    });
    body+='<text x="'+(padL+groupIndex*band+band/2).toFixed(1)+'" y="'+(H-30)
      +'" text-anchor="middle">'+esc(group)+'</text>';
  });
  const table=uadDataTable(spec.id+'-data',spec.title,spec.groupHeader||'Region',groups,series,
    (item,group)=>{const value=spec.value(item,group);return value===null?'not reported':spec.valueLabel(value);});
  return uadColorLegend(series,spec.reference?spec.reference.label:null)
    +'<svg class="uad-chart" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+esc(spec.title)
    +'" aria-describedby="'+spec.id+'-data"><text class="uad-axis-title" x="'+padL+'" y="11">'
    +esc(spec.axisTitle)+'</text>'+body+'</svg>'+table;
}

function uadScatterChart(spec){
  const groups=spec.groups||[], series=spec.series||[];
  if(!groups.length||!series.length||!(spec.xMax>0)||!(spec.yMax>0)) return '';
  const W=680, H=300, padL=56, padR=22, padT=22, padB=54;
  const chartW=W-padL-padR, chartH=H-padT-padB;
  const xScale=value=>padL+(Math.max(0,Math.min(value,spec.xMax))/spec.xMax)*chartW;
  const yScale=value=>padT+chartH-(Math.max(0,Math.min(value,spec.yMax))/spec.yMax)*chartH;
  const xTicks=spec.xTicks||uadTicks(spec.xMax,4), yTicks=spec.yTicks||uadTicks(spec.yMax,4);
  let body=yTicks.map(tick=>'<line class="uad-rule" x1="'+padL+'" x2="'+(W-padR)+'" y1="'+yScale(tick).toFixed(1)
    +'" y2="'+yScale(tick).toFixed(1)+'"/><text x="'+(padL-9)+'" y="'+(yScale(tick)+4).toFixed(1)
    +'" text-anchor="end">'+esc(spec.tickLabel(tick))+'</text>').join('');
  body+=xTicks.map(tick=>'<text x="'+xScale(tick).toFixed(1)+'" y="'+(H-32)+'" text-anchor="middle">'
    +esc(spec.tickLabel(tick))+'</text>').join('');
  body+='<line class="uad-baseline" x1="'+padL+'" x2="'+(W-padR)+'" y1="'+yScale(0).toFixed(1)
    +'" y2="'+yScale(0).toFixed(1)+'"/>';
  // One connector per group traces the progression through the arms in order,
  // so the shape of the trade-off reads without a label on every mark.
  groups.forEach(group=>{
    const path=series.map(item=>{
      const xValue=spec.x(item,group), yValue=spec.y(item,group);
      return xValue===null||yValue===null?null:[xScale(xValue),yScale(yValue)];
    }).filter(point=>point!==null);
    if(path.length>1) body+='<path class="uad-track" d="'
      +path.map((point,index)=>(index?'L':'M')+point[0].toFixed(1)+' '+point[1].toFixed(1)).join(' ')+'"/>';
  });
  series.forEach(item=>{
    groups.forEach((group,groupIndex)=>{
      const xValue=spec.x(item,group), yValue=spec.y(item,group);
      if(xValue===null||yValue===null) return;
      const cx=xScale(xValue), cy=yScale(yValue);
      body+=uadShapeMark(UAD_REGION_SHAPES[groupIndex%UAD_REGION_SHAPES.length],cx,cy,5,
        ' class="uad-dot" fill="'+item.color+'"');
      body+='<circle class="uad-hit" cx="'+cx.toFixed(1)+'" cy="'+cy.toFixed(1)+'" r="11" data-tip="'
        +esc('<b>'+group+'</b><br>'+item.label+'<br>'+spec.xLabel+': '+spec.valueLabel(xValue)
        +'<br>'+spec.yLabel+': '+spec.valueLabel(yValue))+'"/>';
    });
  });
  const table='<table id="'+spec.id+'-data" class="uad-sr-only"><caption>'+esc(spec.title)
    +'</caption><thead><tr><th>Region</th><th>Arm</th><th>'+esc(spec.xLabel)+'</th><th>'+esc(spec.yLabel)
    +'</th></tr></thead><tbody>'+groups.map(group=>series.map(item=>{
      const xValue=spec.x(item,group), yValue=spec.y(item,group);
      return '<tr><td>'+esc(group)+'</td><td>'+esc(item.label)+'</td><td>'
        +esc(xValue===null?'not reported':spec.valueLabel(xValue))+'</td><td>'
        +esc(yValue===null?'not reported':spec.valueLabel(yValue))+'</td></tr>';
    }).join('')).join('')+'</tbody></table>';
  return uadColorLegend(series)+uadShapeLegend(groups)
    +'<svg class="uad-chart" viewBox="0 0 '+W+' '+H+'" role="img" aria-label="'+esc(spec.title)
    +'" aria-describedby="'+spec.id+'-data"><text class="uad-axis-title" x="'+padL+'" y="11">'
    +esc(spec.yLabel)+'</text>'+body+'<text class="uad-axis-title" x="'+(W-padR)+'" y="'+(H-12)
    +'" text-anchor="end">'+esc(spec.xLabel)+'</text></svg>'+table;
}

function uadStrataBars(metrics,color,max,formatValue){
  const rows=[
    ['All carrier events','allCarrierRecall'],
    ['Missed at event','missedRecall'],
    ['No prior catch','noPriorMissedRecall'],
    ['Never-caught people','lifetimeNeverCaughtRecall']
  ];
  const ceiling=max>0?max:1;
  return '<div class="uad-strata" role="group" aria-label="Recall across evaluation strata">'
    +rows.map(([label,key])=>{
      const value=metrics&&typeof metrics[key]==='number'&&isFinite(metrics[key])?metrics[key]:null;
      const width=value===null?0:Math.max(1,Math.round(Math.min(value,ceiling)/ceiling*100));
      return '<div class="uad-strata-row"><span title="'+esc(label)+'">'+esc(label)+'</span>'
        +'<div class="uad-strata-track"><div class="uad-strata-fill" style="width:'+width
        +'%;background:'+color+'"></div></div><b>'+esc(value===null?'—':formatValue(value))+'</b></div>';
    }).join('')
    +'</div><div class="uad-strata-scale">recall, shared 0 to '+esc(formatValue(ceiling))+' scale</div>';
}

function wireUnsupervisedADTooltips(root){
  if(!root||typeof root.querySelectorAll!=='function') return;
  if(typeof showTip!=='function'||typeof hideTip!=='function') return;
  root.querySelectorAll('[data-tip]').forEach(node=>{
    const html=node.getAttribute('data-tip');
    node.addEventListener('pointermove',event=>showTip(event,html));
    node.addEventListener('pointerleave',hideTip);
  });
}
"""

UNSUP_AD_JS = r"""unsupervisedAD:{rendered:false,render(){
  if(this.rendered) return; this.rendered=true;
  const sec=document.getElementById('tab-unsupervisedAD');
  const ad=(typeof DATA!=='undefined'&&DATA)?DATA.unsupervisedAD:null;
  if(!ad){sec.innerHTML='<div class="v9-card">No anomaly-ranking result embedded.</div>';return;}

  const fmt=n=>n===null||n===undefined?'—':Number(n).toLocaleString();
  const pct=v=>v===null||v===undefined?'—':(Number(v)*100).toFixed(1)+'%';
  const metricText=metric=>metric===null||metric===undefined?'—':esc(String(metric));
  const pair=(left,right,formatter)=>formatter(left)+' / '+formatter(right);

  const renderRegion=(region,color,strataMax)=>{
    if(region.status==='skipped') return '<div class="uad-skipped"><b>'+esc(region.region)+'</b> · skipped — '+esc(region.skipReason)+'</div>';
    const m=region.metrics;
    return '<div class="uad-card">'
      +'<div class="uad-region-name">'+esc(region.region)+'</div>'
      +uadStrataBars(m,color,strataMax,pct)
      +'<table class="uad-region-table"><tbody>'
      +'<tr><th>Fit signal</th><td>'+metricText(m.fitSignal)+'</td></tr>'
      +'<tr><th>Feature count</th><td>'+fmt(m.featureCount)+'</td></tr>'
      +'<tr><th>Threshold source</th><td>'+metricText(m.thresholdSource)+'</td></tr>'
      +'<tr><th>Frozen threshold</th><td>'+metricText(m.frozenThreshold)+'</td></tr>'
      +'<tr><th>Validation quantile</th><td>'+metricText(m.thresholdQuantile)+'</td></tr>'
      +'<tr><th>Comparator</th><td>'+metricText(m.thresholdComparator)+'</td></tr>'
      +'<tr><th>Realized test alert rate</th><td>'+pct(m.realizedTestAlertRate)+'</td></tr>'
      +'<tr><th>Caught positives / immature</th><td>'+pair(m.caughtPositiveCount,m.immatureLabelCount,fmt)+'</td></tr>'
      +'<tr><th>All-carrier recall / precision</th><td>'+pair(m.allCarrierRecall,m.allCarrierPrecision,pct)+'</td></tr>'
      +'<tr><th>Missed-at-event recall / precision</th><td>'+pair(m.missedRecall,m.missedPrecision,pct)+'</td></tr>'
      +'<tr><th>No-prior-catch missed recall</th><td>'+pct(m.noPriorMissedRecall)+'</td></tr>'
      +'<tr><th>Lifetime-never-caught person recall / found</th><td>'+pct(m.lifetimeNeverCaughtRecall)+' / '+fmt(m.lifetimeNeverCaughtFound)+'</td></tr>'
      +'<tr><th>Observed-catch enrichment precision / lift</th><td>'+pct(m.observedCatchPrecision)+' / '+(m.observedCatchLift===null?'—':Number(m.observedCatchLift).toFixed(2)+'×')+'</td></tr>'
      +'</tbody></table></div>';
  };
  const renderArm=(arm,strataMax)=>{
    const meta=arm.metadata||{};
    const color=UAD_ARM_COLORS[arm.id]||UAD_ARM_COLORS.tabular_unlabeled;
    let out='<div class="uad-arm"><div class="uad-arm-header"><h4>'
      +'<i class="uad-arm-key" style="background:'+color+'"></i>'+esc(meta.label||arm.id)+'</h4>';
    out+='<span>'+esc(arm.id)+'</span><span>'+fmt(meta.feature_count)+' features</span></div>';
    if(!arm.regions.length) out+='<div class="uad-empty">No regional results embedded.</div>';
    else out+='<div class="uad-grid">'+arm.regions.map(
      region=>renderRegion(region,color,strataMax)
    ).join('')+'</div>';
    return out+'</div>';
  };

  if(Number(ad.schema_version)!==3){
    sec.innerHTML='<div class="uad-card"><h3>Anomaly ranking unavailable</h3>'
      +'<p class="uad-note">Unsupported anomaly artifact schema. This dashboard requires schema 3.</p></div>';
    return;
  }

  const view=buildUnsupervisedADViewModel(ad);
  let h='<div class="uad-header"><h2>Unsupervised and caught-supervised anomaly ranking</h2>';
  h+='<p>This <strong>V9 designed positive control</strong> follows the primary progression from tabular and relational unlabeled detection to a relational <strong>caught-supervised</strong> ranker. The caught-supervised arm is a <strong>naive PU</strong> historical-enforcement ranker with <strong>no SCAR ranking guarantee</strong>. The label-free validation quantile is an <strong>operating-point policy</strong>, not probability calibration.</p>';
  h+='<p class="uad-note">Label and threshold semantics are deployable <strong>conditional on resolved identity</strong>. Oracle evaluation is unavailable in production and appears here only as retrospective synthetic evaluation after scores and thresholds are frozen. Day-to-day monitoring can use observed-catch enrichment.</p></div>';
  const chart=buildUnsupervisedADChartModel(view);
  const recallKeys=['allCarrierRecall','missedRecall','noPriorMissedRecall','lifetimeNeverCaughtRecall'];
  const sample=(series,key)=>series.reduce(
    (out,item)=>out.concat(chart.regions.map(region=>uadMetric(item,region,key))),[]
  );
  const strataCeiling=uadNiceMax(
    recallKeys.reduce((out,key)=>out.concat(sample(chart.primary.concat(chart.ablation),key)),[]),
    0.1, 0.1
  );
  const tickPct=value=>(Number(value)*100).toFixed(0)+'%';
  const valuePct=value=>(Number(value)*100).toFixed(1)+'%';
  const valueLift=value=>Number(value).toFixed(1)+'×';

  function renderFigures(){
    if(!chart.available) return '';
    const series=chart.primary;
    const recallAxis=uadAxis(sample(series,'missedRecall'),0.05,0.1,5);
    const precisionAxis=uadAxis(sample(series,'missedPrecision'),0.05,0.05,5);
    const liftAxis=uadAxis(sample(series,'observedCatchLift'),1,2,5);
    const figure=(title,subtitle,body)=>'<figure class="uad-figure"><h4>'+esc(title)
      +'</h4><figcaption class="uad-figure-sub">'+esc(subtitle)+'</figcaption>'+body+'</figure>';
    let out='<div class="uad-figures">';
    out+=figure(
      'Missed carrier events found, by region',
      'Share of the carrier events that enforcement had not caught at the time and that this ranker still put above its alert threshold. Higher is better.',
      uadColumnChart({
        id:'uad-missed-recall', title:'Missed-at-event recall by region and arm',
        axisTitle:'missed-at-event recall', groups:chart.regions, series,
        value:(item,region)=>uadMetric(item,region,'missedRecall'),
        max:recallAxis.max, ticks:recallAxis.ticks, tickLabel:tickPct, valueLabel:valuePct
      })
    );
    out+=figure(
      'Observed-catch enrichment lift',
      'The one signal a real deployment can watch without oracle labels: how much richer the alerted slice is in observed catches than the region base rate.',
      uadColumnChart({
        id:'uad-lift', title:'Observed-catch enrichment lift by region and arm',
        axisTitle:'lift over prevalence', groups:chart.regions, series,
        value:(item,region)=>uadMetric(item,region,'observedCatchLift'),
        max:liftAxis.max, ticks:liftAxis.ticks,
        tickLabel:value=>Number(value).toFixed(0)+'×', valueLabel:valueLift,
        reference:{value:1,label:'1× = no enrichment'}
      })
    );
    out+=figure(
      'What each arm trades away',
      'Every mark is one arm in one region, and the connector traces that region through the progression. Moving right means reaching more of the missed carriers; moving up means wasting fewer alerts.',
      uadScatterChart({
        id:'uad-tradeoff', title:'Missed-at-event precision against recall, by arm and region',
        groups:chart.regions, series,
        x:(item,region)=>uadMetric(item,region,'missedRecall'),
        y:(item,region)=>uadMetric(item,region,'missedPrecision'),
        xLabel:'missed-at-event recall', yLabel:'missed-at-event precision',
        xMax:recallAxis.max, yMax:precisionAxis.max,
        xTicks:recallAxis.ticks, yTicks:precisionAxis.ticks,
        tickLabel:tickPct, valueLabel:valuePct
      })
    );
    return out+'</div>';
  }

  h+='<h3 class="uad-mode-heading">Ranking quality at a glance</h3>';
  h+='<p class="uad-note">Charts read the same frozen artifact as the tables below. All three are retrospective synthetic evaluation: the scores and thresholds were fixed before any oracle label was consulted.</p>';
  h+=renderFigures();
  h+='<h3 class="uad-mode-heading">Primary deployability progression</h3>';
  if(view.primary.length!==3) h+='<div class="uad-skipped">Primary artifact contract incomplete: expected the three named deployability arms.</div>';
  h+=view.primary.map(arm=>renderArm(arm,strataCeiling)).join('');

  h+='<div class="uad-appendix"><h3 class="uad-mode-heading">Ablation appendix</h3>';
  h+='<p class="uad-note">The 14-feature caught-supervised arm completes the 2×2 diagnostic and is not part of the primary lineup.</p>';
  if(chart.ablation.length){
    const ablationSeries=chart.primary
      .filter(item=>item.id==='relational_caught_supervised')
      .concat(chart.ablation);
    h+='<div class="uad-figures"><figure class="uad-figure"><h4>Does the relational feature set earn its place under caught supervision?</h4>'
      +'<figcaption class="uad-figure-sub">Same supervision signal, same operating-point policy; only the feature scope differs.</figcaption>'
      +uadColumnChart({
        id:'uad-ablation', title:'Missed-at-event recall, relational against tabular caught-supervised',
        axisTitle:'missed-at-event recall', groups:chart.regions, series:ablationSeries,
        value:(item,region)=>uadMetric(item,region,'missedRecall'),
        max:uadAxis(sample(ablationSeries,'missedRecall'),0.05,0.1,5).max,
        ticks:uadAxis(sample(ablationSeries,'missedRecall'),0.05,0.1,5).ticks,
        tickLabel:tickPct, valueLabel:valuePct
      })
      +'</figure></div>';
  }
  h+=view.ablation.map(arm=>renderArm(arm,strataCeiling)).join('');
  h+='</div>';
  sec.innerHTML=h;
  wireUnsupervisedADTooltips(sec);
}},
"""
