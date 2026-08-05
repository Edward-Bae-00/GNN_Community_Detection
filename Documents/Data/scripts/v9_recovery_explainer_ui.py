"""Pure state contracts for the V9 seed-0 recovery evidence explorer."""


V9_RECOVERY_EXPLAINER_CSS = r"""
#tab-v9Results .v9-recovery { margin: 30px 0; padding: 24px 0; border-top: 1px solid var(--border-strong); border-bottom: 1px solid var(--border-strong); }
#tab-v9Results .v9-recovery-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; margin-bottom: 18px; }
#tab-v9Results .v9-recovery-eyebrow { color: var(--accent-hover); font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
#tab-v9Results .v9-recovery-title { margin: 6px 0; color: var(--text1); font-size: 20px; font-weight: 700; letter-spacing: -.02em; }
#tab-v9Results .v9-recovery-intro { max-width: 720px; margin: 0; color: var(--text2); font-size: 12px; line-height: 1.55; }
#tab-v9Results .v9-recovery-scope { flex: 0 0 auto; max-width: 270px; padding: 10px 12px; border: 1px solid rgba(52,211,153,.32); border-radius: 999px; background: var(--accent-soft); color: var(--accent-hover); font-size: 10px; font-weight: 700; line-height: 1.4; text-align: center; }
#tab-v9Results .v9-recovery-scope small { display: block; margin-top: 2px; color: var(--text2); font-size: 9px; font-weight: 500; }
#tab-v9Results .v9-recovery-summary { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 8px; }
#tab-v9Results .v9-recovery-stat { min-width: 0; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); }
#tab-v9Results .v9-recovery-stat b { display: block; color: var(--text1); font-family: var(--font-mono); font-size: 18px; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-recovery-stat span { display: block; margin-top: 4px; color: var(--text2); font-size: 9px; line-height: 1.3; letter-spacing: .045em; text-transform: uppercase; }
#tab-v9Results .v9-recovery-stat.is-warning { border-color: rgba(245,158,11,.5); background: rgba(245,158,11,.08); }
#tab-v9Results .v9-recovery-stat.is-warning b, #tab-v9Results .v9-recovery-stat.is-warning span { color: #fbbf24; }
#tab-v9Results .v9-recovery-containment, #tab-v9Results .v9-recovery-warning, #tab-v9Results .v9-recovery-status { margin-top: 9px; padding: 9px 11px; border-left: 3px solid var(--accent); background: var(--accent-soft); color: var(--text2); font-size: 11px; line-height: 1.45; }
#tab-v9Results .v9-recovery-warning { border-left-color: #f59e0b; background: rgba(245,158,11,.08); color: #fbbf24; }
#tab-v9Results .v9-recovery-status { border-left-color: var(--border-strong); background: var(--elevated); color: var(--text2); }
#tab-v9Results .v9-recovery-coverage { display: flex; flex-wrap: wrap; gap: 8px 18px; margin: 10px 0 18px; color: var(--text2); font-size: 10px; }
#tab-v9Results .v9-recovery-workspace { display: grid; grid-template-columns: minmax(220px, 290px) minmax(0, 1fr); min-height: 620px; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; background: var(--surface); }
#tab-v9Results .v9-recovery-rail { min-width: 0; padding: 14px; border-right: 1px solid var(--border); background: var(--sunk); }
#tab-v9Results .v9-recovery-filter-grid { display: grid; gap: 8px; }
#tab-v9Results .v9-recovery-field { display: grid; gap: 4px; color: var(--text2); font-size: 9px; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; }
#tab-v9Results .v9-recovery-select, #tab-v9Results .v9-recovery-search { width: 100%; min-width: 0; box-sizing: border-box; border: 1px solid var(--border-strong); border-radius: 6px; background: var(--surface); color: var(--text1); padding: 7px 8px; font: inherit; font-size: 11px; }
#tab-v9Results .v9-recovery-case-count { margin: 12px 0 7px; color: var(--text2); font-size: 10px; }
#tab-v9Results .v9-recovery-case-list { display: grid; gap: 6px; max-height: 470px; overflow: auto; }
#tab-v9Results .v9-recovery-case { width: 100%; padding: 10px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text2); text-align: left; cursor: pointer; }
#tab-v9Results .v9-recovery-case:hover { border-color: var(--border-strong); color: var(--text1); }
#tab-v9Results .v9-recovery-case[aria-current="true"] { border-color: rgba(52,211,153,.5); box-shadow: inset 3px 0 0 var(--accent); background: var(--accent-soft); }
#tab-v9Results .v9-recovery-case-top { display: flex; justify-content: space-between; gap: 8px; color: var(--text1); font-size: 11px; font-weight: 700; }
#tab-v9Results .v9-recovery-case-ranks { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 4px; margin-top: 8px; font-family: var(--font-mono); font-size: 9px; }
#tab-v9Results .v9-recovery-case-meta { margin-top: 7px; color: var(--text2); font-size: 9px; line-height: 1.35; }
#tab-v9Results .v9-recovery-case-evidence { margin-top: 4px; color: var(--accent-hover); font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
#tab-v9Results .v9-recovery-detail { min-width: 0; padding: 18px; }
#tab-v9Results .v9-recovery-case-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 14px; }
#tab-v9Results .v9-recovery-case-header h4 { margin: 0 0 4px; color: var(--text1); font-size: 15px; }
#tab-v9Results .v9-recovery-case-header p { margin: 0; color: var(--text2); font-size: 10px; }
#tab-v9Results .v9-recovery-ranks { display: grid; grid-template-columns: repeat(3, minmax(90px, 1fr)); gap: 6px; }
#tab-v9Results .v9-recovery-rank { padding: 8px; border-left: 2px solid var(--border-strong); background: var(--elevated); }
#tab-v9Results .v9-recovery-rank b { display: block; color: var(--text1); font-family: var(--font-mono); font-size: 13px; }
#tab-v9Results .v9-recovery-rank span { display: block; margin-top: 2px; color: var(--text2); font-size: 8px; letter-spacing: .04em; text-transform: uppercase; }
#tab-v9Results .v9-recovery-evidence-grid { display: grid; grid-template-columns: minmax(190px, .62fr) minmax(0, 1.38fr); gap: 12px; }
#tab-v9Results .v9-recovery-panel { min-width: 0; border: 1px solid var(--border); border-radius: 9px; background: var(--elevated); }
#tab-v9Results .v9-recovery-panel-head { padding: 11px 12px; border-bottom: 1px solid var(--border); }
#tab-v9Results .v9-recovery-panel-head h5 { margin: 0; color: var(--text1); font-size: 11px; }
#tab-v9Results .v9-recovery-panel-head p { margin: 4px 0 0; color: var(--text2); font-size: 9px; line-height: 1.4; }
#tab-v9Results .v9-recovery-factor-list { display: grid; gap: 1px; background: var(--border); }
#tab-v9Results .v9-recovery-factor { width: 100%; padding: 10px 12px; border: 0; background: var(--surface); color: var(--text2); text-align: left; cursor: pointer; }
#tab-v9Results .v9-recovery-factor[aria-pressed="true"] { box-shadow: inset 3px 0 0 var(--accent); background: var(--accent-soft); }
#tab-v9Results .v9-recovery-factor strong { display: block; color: var(--text1); font-size: 10px; line-height: 1.35; }
#tab-v9Results .v9-recovery-factor span { display: block; margin-top: 4px; color: var(--text2); font-family: var(--font-mono); font-size: 9px; }
#tab-v9Results .v9-recovery-narrative { margin-top: 12px; padding: 13px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); }
#tab-v9Results .v9-recovery-narrative h5 { margin: 0 0 8px; color: var(--text1); font-size: 11px; }
#tab-v9Results .v9-recovery-narrative p { margin: 6px 0; color: var(--text2); font-size: 11px; line-height: 1.55; }
#tab-v9Results .v9-attribution-panel { margin-top: 12px; padding: 13px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); }
#tab-v9Results .v9-attribution-panel h5 { margin: 0 0 4px; color: var(--text1); font-size: 11px; }
#tab-v9Results .v9-attribution-caveat { margin: 0 0 10px; color: var(--text2); font-size: 10px; line-height: 1.45; }
#tab-v9Results .v9-attribution-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
#tab-v9Results .v9-attribution-section { min-width: 0; padding: 10px; border: 1px solid var(--border); border-radius: 7px; background: var(--elevated); }
#tab-v9Results .v9-attribution-section h6 { margin: 0 0 8px; color: var(--text1); font-size: 10px; letter-spacing: .04em; text-transform: uppercase; }
#tab-v9Results .v9-attribution-row { display: grid; gap: 5px; padding: 7px 0; border-top: 1px solid var(--border); color: var(--text2); font-size: 10px; }
#tab-v9Results .v9-attribution-row:first-of-type { border-top: 0; padding-top: 0; }
#tab-v9Results .v9-attribution-row-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
#tab-v9Results .v9-attribution-rank { color: var(--accent-hover); font-family: var(--font-mono); font-size: 9px; font-weight: 700; }
#tab-v9Results .v9-attribution-id { min-width: 0; overflow-wrap: anywhere; color: var(--text1); font-family: var(--font-mono); }
#tab-v9Results .v9-attribution-connection { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; min-width: 0; }
#tab-v9Results .v9-attribution-relation { padding: 2px 5px; border: 1px solid var(--border-strong); border-radius: 999px; color: var(--accent-hover); font-size: 8px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
#tab-v9Results .v9-attribution-weight { color: var(--text1); font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-attribution-bar { height: 6px; overflow: hidden; border-radius: 999px; background: var(--sunk); }
#tab-v9Results .v9-attribution-bar-fill { display: block; height: 100%; border-radius: inherit; background: var(--accent); }
#tab-v9Results .v9-recovery-source-row { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
#tab-v9Results .v9-recovery-source { padding: 2px 5px; border: 1px solid var(--border); border-radius: 999px; color: var(--text2); font-family: var(--font-mono); font-size: 8px; }
#tab-v9Results .v9-recovery-toolbar { display: flex; flex-wrap: wrap; gap: 6px; padding: 9px; border-bottom: 1px solid var(--border); }
#tab-v9Results .v9-recovery-toolgroup { display: inline-flex; align-items: center; gap: 3px; }
#tab-v9Results .v9-recovery-button { min-height: 29px; padding: 5px 8px; border: 1px solid var(--border-strong); border-radius: 6px; background: var(--surface); color: var(--text2); font: inherit; font-size: 9px; cursor: pointer; }
#tab-v9Results .v9-recovery-button:hover { color: var(--text1); border-color: var(--text2); }
#tab-v9Results .v9-recovery-button[aria-pressed="true"] { border-color: var(--accent); background: var(--accent-soft); color: var(--accent-hover); }
#tab-v9Results .v9-recovery-search { width: 118px; min-height: 29px; padding: 5px 7px; font-size: 9px; }
#tab-v9Results .v9-recovery-toolbar .v9-recovery-select { width: auto; min-height: 29px; padding: 5px 7px; font-size: 9px; }
#tab-v9Results .v9-recovery-canvas-note { padding: 8px 10px; border-bottom: 1px solid var(--border); color: var(--text2); font-size: 9px; line-height: 1.4; }
#tab-v9Results .v9-recovery-canvas-wrap { position: relative; height: 410px; min-height: 300px; background: var(--sunk); }
#tab-v9Results .v9-recovery-canvas { display: block; width: 100%; height: 100%; touch-action: none; cursor: grab; }
#tab-v9Results .v9-recovery-canvas:active { cursor: grabbing; }
#tab-v9Results .v9-recovery-case:focus-visible, #tab-v9Results .v9-recovery-factor:focus-visible, #tab-v9Results .v9-recovery-button:focus-visible, #tab-v9Results .v9-recovery-select:focus-visible, #tab-v9Results .v9-recovery-search:focus-visible, #tab-v9Results .v9-recovery-canvas:focus-visible { outline: 2px solid var(--accent-hover); outline-offset: 2px; }
#tab-v9Results .v9-recovery-empty { padding: 28px; border: 1px dashed var(--border-strong); border-radius: 9px; color: var(--text2); font-size: 12px; line-height: 1.55; text-align: center; }
#tab-v9Results .v9-recovery-cohorts { display: inline-flex; gap: 4px; padding: 4px; margin: 12px 0; border: 1px solid var(--border); border-radius: 8px; background: var(--elevated); }
#tab-v9Results .v9-recovery-cohorts button { border: 0; border-radius: 5px; padding: 8px 12px; background: transparent; color: var(--text2); cursor: pointer; }
#tab-v9Results .v9-recovery-cohorts button[aria-pressed="true"] { background: var(--surface); color: var(--text1); box-shadow: 0 1px 2px rgba(15,23,42,.12); }
#tab-v9Results .v9-recovery-v2-grid { display: grid; grid-template-columns: minmax(220px,.4fr) minmax(0,1fr); gap: 16px; }
#tab-v9Results .v9-recovery-v2-list, #tab-v9Results .v9-recovery-v2-detail { display: grid; gap: 8px; align-content: start; min-width: 0; }
#tab-v9Results .v9-recovery-v2-panels { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px; }
#tab-v9Results .v9-recovery-v2-panel { padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); }
#tab-v9Results .v9-recovery-v2-panel h5 { margin: 0 0 7px; color: var(--text1); }
#tab-v9Results .v9-recovery-v2-panel pre { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--text2); font: 9px/1.5 var(--font-mono); }
#tab-v9Results .v9-recovery-progress { color: var(--text2); font: 9px/1.5 var(--font-mono); }
#tab-v9Results .v9-recovery-legend { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
#tab-v9Results .v9-recovery-legend-item { display: inline-flex; align-items: center; gap: 6px; min-height: 26px; padding: 4px 8px; border: 1px solid var(--border); border-radius: 999px; color: var(--text2); font-size: 10px; line-height: 1.25; }
#tab-v9Results .v9-recovery-legend-swatch { display: inline-block; flex: 0 0 auto; width: 18px; height: 8px; border-radius: 999px; background: #7f8798; box-shadow: 0 0 0 1px rgba(255,255,255,.2); }
#tab-v9Results .v9-recovery-legend-swatch.is-context { opacity: .45; }
#tab-v9Results .v9-recovery-legend-swatch.is-evidence { height: 10px; background: #fbbf24; box-shadow: 0 0 8px rgba(251,191,36,.55); }
#tab-v9Results .v9-recovery-legend-swatch.is-target { width: 10px; height: 10px; border: 2px solid #34d399; border-radius: 50%; background: transparent; }
#tab-v9Results .v9-recovery-legend-swatch.is-caught { width: 10px; height: 10px; border-radius: 50%; background: #60a5fa; }
#tab-v9Results .v9-recovery-legend-swatch.is-weight { background: linear-gradient(90deg, rgba(251,191,36,.35), #fbbf24); }
#tab-v9Results .v9-recovery-sampled { display: inline-block; margin: 8px 9px 0; padding: 4px 8px; border: 1px solid rgba(251,191,36,.42); border-radius: 999px; background: rgba(251,191,36,.1); color: #fbbf24; font-size: 9px; font-weight: 700; line-height: 1.35; }
#tab-v9Results .v9-recovery-v3 .v9-recovery-canvas-wrap { height: 470px; min-height: 360px; background: radial-gradient(circle at 18% 0%, rgba(52,211,153,.16), transparent 42%), radial-gradient(circle at 84% 100%, rgba(96,165,250,.12), transparent 48%), linear-gradient(145deg, #071018, #0b1019 58%, #111827); }
#tab-v9Results .v9-recovery-v3 .v9-recovery-canvas { background: transparent; }
#tab-v9Results .v9-recovery-v3 .v9-recovery-legend { padding: 4px 9px; border-top: 1px solid rgba(255,255,255,.08); border-bottom: 1px solid rgba(255,255,255,.08); background: rgba(5,10,16,.62); }
#tab-v9Results .v9-recovery-v3 .v9-recovery-legend-item { border-color: rgba(255,255,255,.16); background: rgba(255,255,255,.05); color: #d5d9e2; }
#tab-v9Results .v9-recovery-v3 button:focus:not(:focus-visible), #tab-v9Results .v9-recovery-v3 input:focus:not(:focus-visible), #tab-v9Results .v9-recovery-v3 select:focus:not(:focus-visible), #tab-v9Results .v9-recovery-v3 canvas:focus:not(:focus-visible) { outline: none; }
#tab-v9Results .v9-recovery-table-wrap { margin-top: 12px; overflow-x: auto; }
#tab-v9Results .v9-recovery-table-wrap h6 { margin: 0 0 4px; color: var(--text1); font-size: 11px; }
#tab-v9Results .v9-recovery-table { width: 100%; border-collapse: collapse; color: var(--text2); font-size: 10px; }
#tab-v9Results .v9-recovery-table th, #tab-v9Results .v9-recovery-table td { padding: 5px 8px; border-bottom: 1px solid var(--border); text-align: left; white-space: nowrap; }
#tab-v9Results .v9-recovery-table th { color: var(--text1); font-weight: 600; }
#tab-v9Results .v9-recovery-pager { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 8px 0 14px; color: var(--text2); font-size: 10px; }
#tab-v9Results .v9-recovery-pager .v9-recovery-button { min-height: 44px; }
@media(max-width:900px){
  #tab-v9Results .v9-recovery-summary { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  #tab-v9Results .v9-recovery-workspace { grid-template-columns: 1fr; }
  #tab-v9Results .v9-recovery-rail { border-right: 0; border-bottom: 1px solid var(--border); }
  #tab-v9Results .v9-recovery-filter-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  #tab-v9Results .v9-recovery-case-list { grid-template-columns: repeat(2, minmax(0, 1fr)); max-height: 260px; }
  #tab-v9Results .v9-recovery-v2-grid, #tab-v9Results .v9-recovery-v2-panels { grid-template-columns: 1fr; }
}
@media(max-width:700px){
  #tab-v9Results .v9-recovery { margin: 24px 0; padding: 20px 0; }
  #tab-v9Results .v9-recovery-header, #tab-v9Results .v9-recovery-case-header { display: block; }
  #tab-v9Results .v9-recovery-scope { max-width: none; margin-top: 12px; }
  #tab-v9Results .v9-recovery-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  #tab-v9Results .v9-recovery-filter-grid, #tab-v9Results .v9-recovery-case-list, #tab-v9Results .v9-recovery-evidence-grid, #tab-v9Results .v9-attribution-grid { grid-template-columns: 1fr; }
  #tab-v9Results .v9-recovery-detail { padding: 12px; }
  #tab-v9Results .v9-recovery-ranks { margin-top: 12px; grid-template-columns: repeat(3, minmax(0, 1fr)); }
  #tab-v9Results .v9-recovery-toolbar { flex-wrap: nowrap; overflow-x: auto; -webkit-overflow-scrolling: touch; }
  #tab-v9Results .v9-recovery-toolgroup { flex: 0 0 auto; }
  #tab-v9Results .v9-recovery-button, #tab-v9Results .v9-recovery-toolbar .v9-recovery-select, #tab-v9Results .v9-recovery-search { min-height: 44px; }
  #tab-v9Results .v9-recovery-canvas-wrap { height: 340px; }
  #tab-v9Results .v9-recovery-v3 .v9-recovery-canvas-wrap { height: 340px; min-height: 300px; }
}
@media(prefers-reduced-motion: reduce){
  #tab-v9Results .v9-recovery-v3 *, #tab-v9Results .v9-recovery-v3 *::before, #tab-v9Results .v9-recovery-v3 *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; }
}
"""


V9_RECOVERY_EXPLAINER_JS = r"""
function recoveryIsRecord(value){
  return value!==null&&typeof value==='object'&&!Array.isArray(value);
}

function recoveryNonBlankString(value){
  return typeof value==='string'&&value.trim().length>0;
}

function recoveryUniqueStrings(value){
  return Array.isArray(value)&&value.every(recoveryNonBlankString)
    &&new Set(value).size===value.length;
}

function recoverySourceRefs(value){
  return recoveryUniqueStrings(value)&&value.length>0;
}

function recoveryAllowedSourceRef(value){
  return recoveryNonBlankString(value)&&[
    /^scope\.observability_seed$/,
    /^ranks\.(?:baseline|seed0_gnn|seed0_hybrid)$/,
    /^factors_by_id\.[^.]+\.(?:label|stability|counterfactual\.(?:original_hybrid_rank|ablated_hybrid_rank))$/,
    /^visible_paths\.(?:0|[1-9][0-9]*)\.(?:relation|u|v)$/,
    /^caveats\.[12]$/
  ].some(pattern=>pattern.test(value));
}

function recoveryCompareId(left,right){
  return left<right?-1:(left>right?1:0);
}

function recoverySafeInteger(value,allowNegative){
  return typeof value==='number'&&Number.isSafeInteger(value)
    &&(allowNegative===true||value>=0);
}

function recoveryUnavailable(reason){
  return {available:false,reason};
}

function recoveryValidCase(item){
  if(!recoveryIsRecord(item)) return false;
  const positiveRanks=['baseline_rank','seed0_gnn_rank','seed0_hybrid_rank'];
  const finiteMetrics=['hybrid_rank_uplift','gnn_percentile_uplift'];
  return ['case_id','person_id','event_id','scoring_day']
      .every(key=>recoveryNonBlankString(item[key]))
    &&positiveRanks.every(key=>recoverySafeInteger(item[key],false)&&item[key]>0)
    &&finiteMetrics.every(key=>typeof item[key]==='number'&&Number.isFinite(item[key]))
    &&recoveryUniqueStrings(item.relationship_categories)
    &&['stable','unstable','not_explained'].includes(item.stable_factor_status);
}

function buildRecoveryEvidenceViewModel(artifact){
  if(!recoveryIsRecord(artifact)||artifact.schema_version!=='1.0'){
    return recoveryUnavailable('unsupported-or-missing-artifact');
  }
  const policy=artifact.policy;
  const validScope=recoveryIsRecord(policy)
    &&policy.observability_seed===0
    &&policy.gnn_arm==='sage'
    &&policy.inspections_per_day===25
    &&Array.isArray(policy.surrounding_results_seeds)
    &&policy.surrounding_results_seeds.length===3
    &&policy.surrounding_results_seeds.every((seed,index)=>seed===index)
    &&recoveryNonBlankString(policy.percentile_reference_id);
  if(!validScope) return recoveryUnavailable('invalid-observability-scope');

  if(!Array.isArray(artifact.hybrid_only_cases)
      ||!Array.isArray(artifact.explanations)){
    return recoveryUnavailable('invalid-case-collections');
  }
  const cases=artifact.hybrid_only_cases;
  const explanations=artifact.explanations;
  if(!cases.every(recoveryValidCase)
      ||!explanations.every(item=>recoveryIsRecord(item)
        &&recoveryNonBlankString(item.case_id)
        &&recoveryNonBlankString(item.person_id))){
    return recoveryUnavailable('invalid-case-records');
  }
  const caseIds=cases.map(item=>item.case_id);
  const explanationIds=explanations.map(item=>item.case_id);
  if(new Set(caseIds).size!==caseIds.length
      ||new Set(explanationIds).size!==explanationIds.length){
    return recoveryUnavailable('duplicate-case-id');
  }
  const caseById=new Map(cases.map(item=>[item.case_id,item]));
  if(explanations.some(item=>!caseById.has(item.case_id)
      ||caseById.get(item.case_id).person_id!==item.person_id)){
    return recoveryUnavailable('invalid-case-records');
  }

  const summary=artifact.summary;
  let summaryView;
  if(!recoveryIsRecord(summary)||summary.overlap_ids_available!==true){
    summaryView={unavailable:true,reason:'overlap-ids-unavailable'};
  }else{
    const required=[
      'baseline_recovered','recovered_by_both','hybrid_only_recovered',
      'baseline_only_recovered','hybrid_total','net_gain'
    ];
    const numericTypes=required.every(key=>recoverySafeInteger(
      summary[key],key==='net_gain'
    ));
    const values=Object.fromEntries(required.map(key=>[key,summary[key]]));
    const validAlgebra=numericTypes
      &&values.baseline_recovered===values.recovered_by_both
        +values.baseline_only_recovered
      &&values.hybrid_total===values.recovered_by_both
        +values.hybrid_only_recovered
      &&values.net_gain===values.hybrid_total-values.baseline_recovered;
    if(!validAlgebra){
      summaryView={unavailable:true,reason:'invalid-set-algebra'};
    }else{
      const containment=values.baseline_only_recovered===0;
      summaryView={
        values,
        containment,
        tone:containment?'success':'warning'
      };
      if(!containment){
        summaryView.warning='Baseline-only recoveries are present; containment is not claimed.';
      }
    }
  }

  return {
    available:true,
    scope:{
      seed:policy.observability_seed,
      arm:policy.gnn_arm,
      inspectionsPerDay:policy.inspections_per_day,
      surroundingResultsSeeds:policy.surrounding_results_seeds.slice()
    },
    summary:summaryView,
    coverage:recoveryIsRecord(artifact.coverage)?{...artifact.coverage}:{},
    cases:cases.slice(),
    explanations:new Map(explanations.map(item=>[item.case_id,item]))
  };
}

function validateRecoveryNarrative(narrative){
  if(!recoveryIsRecord(narrative)||narrative.validated!==true){
    return {visible:false,reason:'unvalidated'};
  }
  if(!recoveryNonBlankString(narrative.summary)
      ||!recoverySourceRefs(narrative.summary_source_refs)
      ||!narrative.summary_source_refs.every(recoveryAllowedSourceRef)){
    return {visible:false,reason:'missing-summary-sources'};
  }
  if(!Array.isArray(narrative.claims)){
    return {visible:false,reason:'invalid-claims'};
  }
  const validClaims=narrative.claims.every(claim=>recoveryIsRecord(claim)
    &&recoveryNonBlankString(claim.text)
    &&recoverySourceRefs(claim.source_refs)
    &&claim.source_refs.every(recoveryAllowedSourceRef));
  if(!validClaims){
    return {visible:false,reason:'missing-claim-sources'};
  }
  const validProvenance=narrative.prompt_version==='v1'
    &&((narrative.source==='llm'&&narrative.model==='gemma4:12b')
      ||(narrative.source==='deterministic_template'&&narrative.model===null));
  if(!validProvenance){
    return {visible:false,reason:'invalid-narrative-metadata'};
  }
  return {
    visible:true,
    summary:narrative.summary,
    summarySourceRefs:narrative.summary_source_refs.slice(),
    claims:narrative.claims.map(claim=>({
      text:claim.text,
      source_refs:claim.source_refs.slice()
    })),
    source:narrative.source,
    model:narrative.model||null
  };
}

function recoveryAttributionRank(value){
  return Number.isSafeInteger(value)&&value>0?value:null;
}

function recoveryAttributionRows(records,kind){
  if(records===undefined) return [];
  if(!Array.isArray(records)) return null;
  const rows=[];
  for(const record of records){
    if(!recoveryIsRecord(record)||!recoveryFiniteUnit(record.explainer_median)){
      continue;
    }
    const rank=recoveryAttributionRank(record.rank);
    if(kind==='node'){
      if(!recoveryNonBlankString(record.node_id)) continue;
      rows.push({
        rank,
        id:record.node_id.trim(),
        weight:record.explainer_median
      });
    }else{
      const relation=recoveryNonBlankString(record.relation)
        ?record.relation.trim():recoveryNonBlankString(record.edge_type)
          ?record.edge_type.trim():null;
      if(!recoveryNonBlankString(record.edge_id)
          ||!recoveryNonBlankString(record.u)
          ||!recoveryNonBlankString(record.v)
          ||!relation) continue;
      rows.push({
        rank,
        id:record.edge_id.trim(),
        u:record.u.trim(),
        v:record.v.trim(),
        relation,
        weight:record.explainer_median
      });
    }
  }
  const useRanks=rows.length>0&&rows.every(row=>row.rank!==null)
    &&new Set(rows.map(row=>row.rank)).size===rows.length;
  rows.sort((left,right)=>useRanks
    ?left.rank-right.rank||recoveryCompareId(left.id,right.id)
    :right.weight-left.weight||recoveryCompareId(left.id,right.id));
  return rows.slice(0,3).map((row,index)=>kind==='node'?{
    rank:index+1,
    nodeId:row.id,
    weight:row.weight
  }:{
    rank:index+1,
    edgeId:row.id,
    u:row.u,
    v:row.v,
    relation:row.relation,
    weight:row.weight
  });
}

function buildHighestAttributionViewModel(explanation){
  const attributions=recoveryIsRecord(explanation)?explanation.attributions:null;
  if(!recoveryIsRecord(attributions)){
    return recoveryUnavailable('no-valid-attribution-ranking');
  }
  const nodes=recoveryAttributionRows(attributions.top_local_nodes,'node');
  const connections=recoveryAttributionRows(attributions.top_edges,'edge');
  if(nodes===null||connections===null){
    return recoveryUnavailable('no-valid-attribution-ranking');
  }
  if(nodes.length===0&&connections.length===0){
    return recoveryUnavailable('no-valid-attribution-ranking');
  }
  return {available:true,nodes,connections};
}

function recoveryAttributionBar(doc,weight,label){
  const bar=recoveryElement(doc,'div','v9-attribution-bar');
  bar.setAttribute('role','progressbar');
  bar.setAttribute('aria-label',label);
  bar.setAttribute('aria-valuemin','0');
  bar.setAttribute('aria-valuemax','1');
  bar.setAttribute('aria-valuenow',String(weight));
  const fill=recoveryElement(doc,'span','v9-attribution-bar-fill');
  fill.style.width=String(weight*100)+'%';
  bar.appendChild(fill);
  return bar;
}

function renderHighestAttributionPanel(doc,explanation){
  const panel=recoveryElement(doc,'section','v9-attribution-panel');
  panel.setAttribute('aria-label','Highest-attribution evidence');
  panel.appendChild(recoveryElement(doc,'h5','', 'Highest-attribution evidence'));
  panel.appendChild(recoveryElement(doc,'p','v9-attribution-caveat',
    'Unsigned median attribution weights show salience across deterministic explainer restarts, not causal direction.'));
  const view=buildHighestAttributionViewModel(explanation);
  if(!view.available){
    panel.appendChild(recoveryElement(doc,'div','v9-recovery-status',
      'Attribution ranking unavailable in this artifact.'));
    return panel;
  }
  const grid=recoveryElement(doc,'div','v9-attribution-grid');
  const sections=[['Nodes',view.nodes],['Connections',view.connections]];
  for(const [title,rows] of sections){
    const section=recoveryElement(doc,'section','v9-attribution-section');
    section.appendChild(recoveryElement(doc,'h6','',title));
    if(!rows.length){
      section.appendChild(recoveryElement(doc,'div','v9-recovery-status',
        'No valid ranked data is available.'));
    }
    for(const row of rows){
      const item=recoveryElement(doc,'div','v9-attribution-row');
      const head=recoveryElement(doc,'div','v9-attribution-row-head');
      const label=title==='Nodes'?row.nodeId:row.u+' ↔ '+row.v;
      const identifier=recoveryElement(doc,'div','v9-attribution-connection');
      identifier.appendChild(recoveryElement(doc,'span','v9-attribution-rank','#'+row.rank));
      identifier.appendChild(recoveryElement(doc,'span','v9-attribution-id',label));
      if(title==='Connections'){
        identifier.appendChild(recoveryElement(doc,'span','v9-attribution-relation',row.relation));
        identifier.appendChild(recoveryElement(doc,'span','v9-attribution-id','edge '+row.edgeId));
      }
      head.appendChild(identifier);
      head.appendChild(recoveryElement(doc,'span','v9-attribution-weight',row.weight.toFixed(3)));
      item.appendChild(head);
      item.appendChild(recoveryAttributionBar(doc,row.weight,
        title==='Nodes'
          ?'Nodes attribution weight for '+label
          :'Connections attribution weight for '+label+' relation '+row.relation
            +' edge '+row.edgeId));
      section.appendChild(item);
    }
    grid.appendChild(section);
  }
  panel.appendChild(grid);
  return panel;
}

function validateRecoveryEvidenceBoundary(explanation,scoringDay){
  const boundary=recoveryIsRecord(explanation)
    ?explanation.evidence_boundary:null;
  const valid=recoveryIsRecord(boundary)
    &&boundary.snapshot===scoringDay
    &&boundary.edge_rule==='available_time < snapshot'
    &&boundary.caught_rule==='label_available_time_utc < snapshot';
  if(!valid) return recoveryUnavailable('invalid-evidence-boundary');
  return {
    available:true,
    snapshot:boundary.snapshot,
    edgeRule:boundary.edge_rule,
    caughtRule:boundary.caught_rule
  };
}

function filterAndSortRecoveryCases(cases,options){
  if(!Array.isArray(cases)) return [];
  const settings=recoveryIsRecord(options)?options:{};
  const stable=recoveryNonBlankString(settings.stableStatus)
    ?settings.stableStatus:'all';
  const relation=recoveryNonBlankString(settings.relationshipCategory)
    ?settings.relationshipCategory:'all';
  const allowedSorts=['hybrid_rank_uplift','gnn_percentile_uplift'];
  const sortBy=allowedSorts.includes(settings.sortBy)
    ?settings.sortBy:'hybrid_rank_uplift';
  const explainedIds=Array.isArray(settings.explainedIds)
    ?new Set(settings.explainedIds.filter(recoveryNonBlankString)):null;
  const evidence=settings.evidence==='explained'&&explainedIds?'explained':'all';
  return cases.filter(item=>recoveryValidCase(item)
      &&(stable==='all'||item.stable_factor_status===stable)
      &&(relation==='all'||item.relationship_categories.includes(relation))
      &&(evidence==='all'||explainedIds.has(item.case_id)))
    .slice()
    .sort((left,right)=>
      (explainedIds?Number(explainedIds.has(right.case_id))
        -Number(explainedIds.has(left.case_id)):0)
      ||right[sortBy]-left[sortBy]
      ||right.hybrid_rank_uplift-left.hybrid_rank_uplift
      ||recoveryCompareId(left.person_id,right.person_id)
      ||recoveryCompareId(left.case_id,right.case_id));
}

function buildCommunityStageView(explanation,options){
  if(!recoveryIsRecord(explanation)
      ||!recoveryNonBlankString(explanation.person_id)
      ||!recoveryIsRecord(explanation.community)
      ||explanation.community.complete!==true){
    return recoveryUnavailable('incomplete-community');
  }
  const settings=recoveryIsRecord(options)?options:{};
  const validModes=['all','flow'];
  const validStages=['first_hop','second_hop','component_pool','rank_fusion'];
  if(!validModes.includes(settings.mode)||!validStages.includes(settings.stageId)){
    return recoveryUnavailable('invalid-view-options');
  }
  const community=explanation.community;
  if(!Array.isArray(community.nodes)||!Array.isArray(community.edges)){
    return recoveryUnavailable('invalid-community-membership');
  }
  const validNodes=community.nodes.every(node=>recoveryIsRecord(node)
    &&recoveryNonBlankString(node.node_id));
  const validEdges=community.edges.every(edge=>recoveryIsRecord(edge)
    &&recoveryNonBlankString(edge.edge_id)
    &&recoveryNonBlankString(edge.u)
    &&recoveryNonBlankString(edge.v));
  if(!validNodes||!validEdges){
    return recoveryUnavailable('invalid-community-membership');
  }
  const nodeIds=community.nodes.map(node=>node.node_id);
  const edgeIds=community.edges.map(edge=>edge.edge_id);
  const nodeSet=new Set(nodeIds);
  if(nodeIds.length===0||!nodeSet.has(explanation.person_id)
      ||nodeSet.size!==nodeIds.length||new Set(edgeIds).size!==edgeIds.length
      ||community.edges.some(edge=>!nodeSet.has(edge.u)||!nodeSet.has(edge.v))){
    return recoveryUnavailable('invalid-community-membership');
  }
  return {
    available:true,
    nodeIds:nodeIds.slice().sort(),
    edgeIds:edgeIds.slice().sort(),
    mode:settings.mode,
    stageId:settings.stageId,
    selectedFactorId:recoveryNonBlankString(settings.selectedFactorId)
      ?settings.selectedFactorId:null,
    query:typeof settings.query==='string'?settings.query:''
  };
}

function recoveryFiniteUnit(value){
  return typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=1;
}

function recoverySameIds(values,expected){
  return recoveryUniqueStrings(values)
    &&values.slice().sort().join('\u0000')===expected.slice().sort().join('\u0000');
}

function recoveryValidStageRule(stage,nodeIds,edgeIds){
  if(!recoveryIsRecord(stage.edge_rule)){
    return recoverySameIds(stage.node_ids,nodeIds)
      &&recoverySameIds(stage.edge_ids,edgeIds)
      &&recoveryUniqueStrings(stage.emphasized_edge_ids)
      &&stage.emphasized_edge_ids.every(id=>edgeIds.includes(id));
  }
  if(stage.node_ids!==undefined||stage.edge_ids!==undefined
      ||stage.emphasized_edge_ids!==undefined) return false;
  const rule=stage.edge_rule;
  if(stage.stage_id==='first_hop') return rule.max_message_hop===1;
  if(stage.stage_id==='second_hop') return rule.max_message_hop===2;
  if(stage.stage_id==='component_pool') return rule.edge_type==='COTRAVEL'
    &&rule.both_pooled_members===true;
  return stage.stage_id==='rank_fusion'&&rule.match_none===true;
}

function recoveryStageEmphasizes(stage,edge,nodesById){
  if(Array.isArray(stage.emphasized_edge_ids)){
    return stage.emphasized_edge_ids.includes(edge.edge_id);
  }
  const rule=stage.edge_rule;
  if(rule.match_none===true) return false;
  if(Number.isSafeInteger(rule.max_message_hop)){
    return Number.isSafeInteger(edge.message_hop)
      &&edge.message_hop<=rule.max_message_hop;
  }
  if(rule.edge_type==='COTRAVEL'&&rule.both_pooled_members===true){
    const left=nodesById.get(edge.u);
    const right=nodesById.get(edge.v);
    return String(edge.edge_type||'').toUpperCase()==='COTRAVEL'
      &&left&&right&&left.pooled_member===true&&right.pooled_member===true;
  }
  return false;
}

function buildRecoveryGraphSlice(fullNodes,fullEdges,personId){
  const tableNodes=Array.isArray(fullNodes)?fullNodes.slice():[];
  const tableEdges=Array.isArray(fullEdges)?fullEdges.slice():[];
  const nodeId=row=>recoveryNonBlankString(row&&row.node_id)
    ?row.node_id:recoveryNonBlankString(row&&row.id)?row.id:null;
  const edgeId=row=>recoveryNonBlankString(row&&row.edge_id)
    ?row.edge_id:recoveryNonBlankString(row&&row.id)?row.id:null;
  const endpoint=row=>recoveryNonBlankString(row)?row:null;
  const sortedNodes=tableNodes.slice().sort((left,right)=>
    recoveryCompareId(String(nodeId(left)||''),String(nodeId(right)||'')));
  const sortedEdges=tableEdges.slice().sort((left,right)=>
    recoveryCompareId(String(edgeId(left)||''),String(edgeId(right)||'')));
  const selectedNodeIds=new Set();
  const attributedNodeIds=new Set();
  for(const node of tableNodes){
    const id=nodeId(node);
    if(!id)continue;
    if(id===personId)selectedNodeIds.add(id);
    if(node&&node.attributed===true){
      attributedNodeIds.add(id);selectedNodeIds.add(id);
    }
  }
  const attributedEdgeIds=new Set();
  for(const edge of tableEdges){
    if(!edge||edge.attributed!==true)continue;
    const id=edgeId(edge);
    if(id)attributedEdgeIds.add(id);
    const left=endpoint(edge.u);const right=endpoint(edge.v);
    if(left)selectedNodeIds.add(left);
    if(right)selectedNodeIds.add(right);
  }
  const sampled=tableNodes.length>RECOVERY_GRAPH_NODE_LIMIT
    ||tableEdges.length>RECOVERY_GRAPH_EDGE_LIMIT;
  if(selectedNodeIds.size>RECOVERY_GRAPH_NODE_LIMIT){
    return {
      available:false,
      reason:'mandatory-evidence-node-limit-exceeded',
      sampled,
      fullNodeCount:tableNodes.length,
      fullEdgeCount:tableEdges.length,
      nodes:[],
      edges:[],
      tableNodes,
      tableEdges
    };
  }
  for(const node of sortedNodes){
    if(selectedNodeIds.size>=RECOVERY_GRAPH_NODE_LIMIT)break;
    const id=nodeId(node);
    if(id)selectedNodeIds.add(id);
  }
  const visibleNodes=sortedNodes.filter(node=>selectedNodeIds.has(nodeId(node)));
  const visibleNodeIds=new Set(visibleNodes.map(node=>nodeId(node)));
  const selectedEdgeIds=new Set();
  for(const edge of sortedEdges){
    const id=edgeId(edge);
    if(!id)continue;
    const attributed=attributedEdgeIds.has(id);
    if(attributed&&visibleNodeIds.has(edge.u)&&visibleNodeIds.has(edge.v)
        &&selectedEdgeIds.size<RECOVERY_GRAPH_EDGE_LIMIT){
      selectedEdgeIds.add(id);
    }
  }
  for(const edge of sortedEdges){
    if(selectedEdgeIds.size>=RECOVERY_GRAPH_EDGE_LIMIT)break;
    const id=edgeId(edge);
    if(!id||attributedEdgeIds.has(id)
        ||!visibleNodeIds.has(edge&&edge.u)
        ||!visibleNodeIds.has(edge&&edge.v))continue;
    selectedEdgeIds.add(id);
  }
  const visibleEdges=sortedEdges.filter(edge=>selectedEdgeIds.has(edgeId(edge)));
  return {
    available:true,
    sampled,
    fullNodeCount:tableNodes.length,
    fullEdgeCount:tableEdges.length,
    nodes:visibleNodes,
    edges:visibleEdges,
    tableNodes,
    tableEdges
  };
}

function buildCommunityDrawCommands(explanation,options){
  const stageView=buildCommunityStageView(explanation,options);
  if(!stageView.available) return stageView;
  const community=explanation.community;
  if(!community.nodes.every(node=>recoveryFiniteUnit(node.x)
      &&recoveryFiniteUnit(node.y))){
    return recoveryUnavailable('invalid-community-coordinates');
  }
  const requiredStages=['first_hop','second_hop','component_pool','rank_fusion'];
  if(!Array.isArray(explanation.flow_stages)
      ||explanation.flow_stages.length!==requiredStages.length){
    return recoveryUnavailable('invalid-flow-stages');
  }
  const stagesById=new Map();
  for(const stage of explanation.flow_stages){
    if(!recoveryIsRecord(stage)||!requiredStages.includes(stage.stage_id)
        ||stagesById.has(stage.stage_id)
        ||!recoveryValidStageRule(stage,stageView.nodeIds,stageView.edgeIds)){
      return recoveryUnavailable('invalid-flow-stages');
    }
    stagesById.set(stage.stage_id,stage);
  }
  if(requiredStages.some(id=>!stagesById.has(id))){
    return recoveryUnavailable('invalid-flow-stages');
  }
  const selectedStage=stagesById.get(stageView.stageId);
  const nodesById=new Map(community.nodes.map(node=>[node.node_id,node]));
  const overlayNodes=Array.isArray(explanation.overlayNodes)
    ?explanation.overlayNodes:[];
  const overlayEdges=Array.isArray(explanation.overlayEdges)
    ?explanation.overlayEdges:[];
  const overlayNodesById=new Map(overlayNodes.map(node=>[
    node&&node.node_id,node
  ]));
  const overlayEdgesById=new Map(overlayEdges.map(edge=>[
    edge&&edge.edge_id,edge
  ]));
  const query=stageView.query.trim().toLowerCase();
  const importanceFor=row=>recoveryFiniteUnit(row&&row.importance)
    ?row.importance:recoveryFiniteUnit(row&&row.explainer_median)
      ?row.explainer_median:0;
  const nodes=community.nodes.map(node=>{
    const overlay=overlayNodesById.get(node.node_id);
    return {
      node_id:node.node_id,
      id:node.node_id,
      x:node.x,
      y:node.y,
      target:node.node_id===explanation.person_id,
      pooledMember:node.pooled_member===true,
      caughtBeforeSnapshot:node.caught_before_snapshot===true,
      importance:importanceFor(overlay||node),
      attributed:overlay?overlay.attributed===true:node.attributed===true,
      rank:overlay&&Number.isSafeInteger(overlay.rank)?overlay.rank
        :(Number.isSafeInteger(node.rank)?node.rank:null),
      matched:query.length>0&&node.node_id.toLowerCase().includes(query)
    };
  });
  const edges=community.edges.map(edge=>{
    const overlay=overlayEdgesById.get(edge.edge_id);
    const attributed=overlay?overlay.attributed===true:edge.attributed===true;
    return {
      edge_id:edge.edge_id,
      id:edge.edge_id,
      u:edge.u,
      v:edge.v,
      relation:recoveryNonBlankString(edge.edge_type)?edge.edge_type:'RELATION',
      importance:importanceFor(overlay||edge),
      attributed,
      rank:overlay&&Number.isSafeInteger(overlay.rank)?overlay.rank
        :(Number.isSafeInteger(edge.rank)?edge.rank:null),
      emphasized:stageView.mode==='all'||attributed
        ||recoveryStageEmphasizes(selectedStage,edge,nodesById)
    };
  });
  const slice=buildRecoveryGraphSlice(nodes,edges,explanation.person_id);
  if(!slice.available) return slice;

  const provenanceNodes=[];
  const provenanceEdges=[];
  if(stageView.selectedFactorId!==null){
    if(!Array.isArray(explanation.factors)){
      return recoveryUnavailable('invalid-selected-factor');
    }
    const factor=explanation.factors.find(item=>recoveryIsRecord(item)
      &&item.factor_id===stageView.selectedFactorId);
    if(!factor||!recoveryUniqueStrings(factor.provenance_expansion_ids)){
      return recoveryUnavailable('invalid-selected-factor');
    }
    if(!Array.isArray(community.provenance_expansions)){
      return recoveryUnavailable('invalid-provenance-expansion');
    }
    const expansionsById=new Map();
    for(const expansion of community.provenance_expansions){
      if(!recoveryIsRecord(expansion)
          ||!recoveryNonBlankString(expansion.expansion_id)
          ||expansionsById.has(expansion.expansion_id)){
        return recoveryUnavailable('invalid-provenance-expansion');
      }
      expansionsById.set(expansion.expansion_id,expansion);
    }
    const selectedExpansions=[];
    for(const expansionId of factor.provenance_expansion_ids){
      const expansion=expansionsById.get(expansionId);
      if(!expansion) return recoveryUnavailable('invalid-provenance-expansion');
      selectedExpansions.push(expansion);
    }
    const baseIds=new Set(nodes.map(node=>node.id));
    const availableIds=new Set(baseIds);
    const outsideById=new Map();
    for(const expansion of selectedExpansions){
      if(expansion.label!=='outside message community'
          ||!Array.isArray(expansion.nodes)||!Array.isArray(expansion.edges)){
        return recoveryUnavailable('invalid-provenance-expansion');
      }
      const localIds=new Set();
      for(const node of expansion.nodes){
        if(!recoveryIsRecord(node)||!recoveryNonBlankString(node.node_id)
            ||localIds.has(node.node_id)||!recoveryFiniteUnit(node.x)
            ||!recoveryFiniteUnit(node.y)){
          return recoveryUnavailable('invalid-provenance-expansion');
        }
        localIds.add(node.node_id);
        availableIds.add(node.node_id);
        if(!baseIds.has(node.node_id)){
          const existing=outsideById.get(node.node_id);
          if(existing&&(existing.x!==node.x||existing.y!==node.y)){
            return recoveryUnavailable('invalid-provenance-expansion');
          }
          outsideById.set(node.node_id,{id:node.node_id,x:node.x,y:node.y});
        }
      }
    }
    const provenanceEdgeIds=new Set();
    for(const expansion of selectedExpansions){
      for(const edge of expansion.edges){
        if(!recoveryIsRecord(edge)||!recoveryNonBlankString(edge.edge_id)
            ||!recoveryNonBlankString(edge.u)||!recoveryNonBlankString(edge.v)
            ||provenanceEdgeIds.has(edge.edge_id)
            ||!availableIds.has(edge.u)||!availableIds.has(edge.v)){
          return recoveryUnavailable('invalid-provenance-expansion');
        }
        provenanceEdgeIds.add(edge.edge_id);
        provenanceEdges.push({
          id:edge.edge_id,
          u:edge.u,
          v:edge.v,
          relation:recoveryNonBlankString(edge.edge_type)
            ?edge.edge_type:'RELATION',
          label:'outside message community',
          dashed:true
        });
      }
    }
    provenanceNodes.push(...Array.from(outsideById.values()).sort((a,b)=>
      recoveryCompareId(a.id,b.id)));
    provenanceEdges.sort((a,b)=>recoveryCompareId(a.id,b.id));
  }
  return {
    available:true,
    mode:stageView.mode,
    stageId:stageView.stageId,
    nodes:slice.nodes,
    edges:slice.edges,
    tableNodes:slice.tableNodes,
    tableEdges:slice.tableEdges,
    sampled:slice.sampled,
    fullNodeCount:slice.fullNodeCount,
    fullEdgeCount:slice.fullEdgeCount,
    provenanceNodes,
    provenanceEdges
  };
}

function graphPoint(point,viewport){
  const width=Number(viewport.width);
  const height=Number(viewport.height);
  const padding=Number(viewport.padding);
  const scale=Number(viewport.scale);
  const offsetX=Number(viewport.offsetX);
  const offsetY=Number(viewport.offsetY);
  const baseX=padding+point.x*Math.max(0,width-padding*2);
  const baseY=padding+point.y*Math.max(0,height-padding*2);
  return {
    x:(baseX-width/2)*scale+width/2+offsetX,
    y:(baseY-height/2)*scale+height/2+offsetY
  };
}

function recoveryVisibleText(value){
  return String(value===null||value===undefined?'':value)
    .replace(/[\u2013\u2014]/g,'-').replace(/\u00b7/g,' / ');
}

function recoveryElement(doc,tag,className,text){
  const element=doc.createElement(tag);
  if(className) element.className=className;
  if(text!==undefined) element.textContent=recoveryVisibleText(text);
  return element;
}

function recoverySetData(element,action,value){
  element.dataset.recoveryAction=action;
  if(value!==undefined) element.dataset.recoveryValue=String(value);
  return element;
}

function recoveryRestoreFocus(root,datasetKey,action,value){
  const selector=datasetKey==='recoveryAction'
    ?'[data-recovery-action]':'[data-recovery-change]';
  const expectedValue=value===undefined?null:String(value);
  for(const control of root.querySelectorAll(selector)){
    const matchesAction=control.dataset
      &&control.dataset[datasetKey]===action;
    const matchesValue=expectedValue===null
      ||control.dataset.recoveryValue===expectedValue;
    if(matchesAction&&matchesValue){
      control.focus();
      return true;
    }
  }
  return false;
}

function recoverySelect(doc,labelText,action,options,value){
  const label=recoveryElement(doc,'label','v9-recovery-field',labelText);
  const select=recoveryElement(doc,'select','v9-recovery-select');
  select.dataset.recoveryChange=action;
  for(const option of options){
    const node=recoveryElement(doc,'option','',option.label);
    node.value=option.value;
    select.appendChild(node);
  }
  select.value=value;
  label.appendChild(select);
  return label;
}

function recoveryAppendSources(doc,parent,refs){
  const row=recoveryElement(doc,'div','v9-recovery-source-row');
  for(const ref of refs){
    row.appendChild(recoveryElement(doc,'span','v9-recovery-source',ref));
  }
  parent.appendChild(row);
}

function recoveryRelationColor(relation){
  const key=String(relation||'').toUpperCase();
  if(key==='COTRAVEL') return '#34d399';
  if(key==='RESIDENCE') return '#60a5fa';
  if(key==='SHARED_PLATE') return '#a78bfa';
  return '#8b8b96';
}

function recoveryDrawArrow(context,from,to,color){
  const angle=Math.atan2(to.y-from.y,to.x-from.x);
  const x=from.x+(to.x-from.x)*.62;
  const y=from.y+(to.y-from.y)*.62;
  context.beginPath();
  context.moveTo(x,y);
  context.lineTo(x-7*Math.cos(angle-Math.PI/6),y-7*Math.sin(angle-Math.PI/6));
  context.lineTo(x-7*Math.cos(angle+Math.PI/6),y-7*Math.sin(angle+Math.PI/6));
  context.closePath();
  context.fillStyle=color;
  context.fill();
}

function recoveryEdgeStyle(edge){
  const importance=typeof edge.importance==='number'
    &&Number.isFinite(edge.importance)
    ?Math.max(0,Math.min(1,edge.importance)):0;
  if(edge.attributed===true){
    return {
      alpha:0.45+0.5*importance,
      lineWidth:1.5+3*importance,
      color:'#fbbf24'
    };
  }
  return edge.emphasized
    ?{alpha:0.45+0.5*importance,lineWidth:1.5+3*importance}
    :{alpha:0.18+0.12*importance,lineWidth:0.85+0.65*importance};
}

function bindRecoveryCanvas(canvas,commands,state){
  const view=canvas.ownerDocument&&canvas.ownerDocument.defaultView;
  const context=canvas.getContext('2d');
  if(!context) return function(){};
  const pointers=new Map();
  let lastPoint=null;
  let lastPinchDistance=null;
  let observer=null;
  const positionById=new Map();

  function draw(){
    const rect=canvas.getBoundingClientRect();
    const width=Math.max(1,Math.round(rect.width||canvas.clientWidth||640));
    const height=Math.max(1,Math.round(rect.height||canvas.clientHeight||410));
    const dpr=Math.max(1,Number(view&&view.devicePixelRatio)||1);
    canvas.width=Math.round(width*dpr);
    canvas.height=Math.round(height*dpr);
    context.setTransform(dpr,0,0,dpr,0,0);
    context.clearRect(0,0,width,height);
    const viewport={
      width,
      height,
      padding:42,
      scale:state.scale,
      offsetX:state.offsetX,
      offsetY:state.offsetY
    };
    positionById.clear();
    for(const node of commands.nodes.concat(commands.provenanceNodes)){
      positionById.set(node.id,graphPoint(node,viewport));
    }
    context.lineCap='round';
    for(const edge of commands.edges){
      const from=positionById.get(edge.u);
      const to=positionById.get(edge.v);
      if(!from||!to)continue;
      const color=recoveryRelationColor(edge.relation);
      const style=recoveryEdgeStyle(edge);
      context.beginPath();
      context.setLineDash([]);
      context.moveTo(from.x,from.y);
      context.lineTo(to.x,to.y);
      context.strokeStyle=style.color||color;
      context.globalAlpha=style.alpha;
      context.lineWidth=style.lineWidth;
      context.stroke();
      if(commands.mode==='flow'&&edge.emphasized){
        context.globalAlpha=.95;
        recoveryDrawArrow(context,from,to,style.color||color);
      }
    }
    for(const edge of commands.provenanceEdges){
      const from=positionById.get(edge.u);
      const to=positionById.get(edge.v);
      if(!from||!to)continue;
      context.beginPath();
      context.setLineDash([6,5]);
      context.moveTo(from.x,from.y);
      context.lineTo(to.x,to.y);
      context.strokeStyle='#f59e0b';
      context.globalAlpha=.9;
      context.lineWidth=1.5;
      context.stroke();
      context.setLineDash([]);
      context.fillStyle='#fbbf24';
      context.font='9px JetBrains Mono, monospace';
      context.fillText(edge.label,(from.x+to.x)/2+5,(from.y+to.y)/2-5);
    }
    context.globalAlpha=1;
    for(const node of commands.provenanceNodes){
      const point=positionById.get(node.id);
      context.beginPath();
      context.arc(point.x,point.y,5,0,Math.PI*2);
      context.fillStyle='#f59e0b';
      context.fill();
    }
    const emphasizedNodes=new Set(commands.edges.filter(edge=>edge.emphasized)
      .flatMap(edge=>[edge.u,edge.v]));
    for(const node of commands.nodes){
      const point=positionById.get(node.id);
      if(!point)continue;
      const radius=node.target?8:(node.pooledMember?6:4.5);
      if(node.attributed){
        context.beginPath();
        context.arc(point.x,point.y,radius+3+2*node.importance,0,Math.PI*2);
        context.strokeStyle='#fbbf24';
        context.globalAlpha=.65+.3*node.importance;
        context.lineWidth=2+node.importance;
        context.stroke();
      }
      context.beginPath();
      context.arc(point.x,point.y,radius,0,Math.PI*2);
      context.globalAlpha=1;
      context.fillStyle=node.target?'#34d399':(node.caughtBeforeSnapshot?'#60a5fa':'#8b8b96');
      context.fill();
      if(node.target){
        context.beginPath();
        context.arc(point.x,point.y,radius+5,0,Math.PI*2);
        context.strokeStyle='#34d399';
        context.lineWidth=2.5;
        context.stroke();
      }else if(node.matched){
        context.beginPath();
        context.arc(point.x,point.y,radius+4,0,Math.PI*2);
        context.strokeStyle='#fbbf24';
        context.lineWidth=2;
        context.stroke();
      }
      const showLabel=state.labelDensity==='all'
        ||(state.labelDensity==='auto'
          &&(node.target||node.matched||emphasizedNodes.has(node.id)));
      if(showLabel){
        context.fillStyle='#e8e8ec';
        context.font='10px JetBrains Mono, monospace';
        context.fillText(recoveryVisibleText(node.id),point.x+radius+4,point.y+3);
      }
    }
    context.globalAlpha=1;
  }

  function pointerDistance(){
    const values=Array.from(pointers.values());
    if(values.length<2) return null;
    return Math.hypot(values[0].x-values[1].x,values[0].y-values[1].y);
  }
  function onPointerDown(event){
    pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
    if(canvas.setPointerCapture) canvas.setPointerCapture(event.pointerId);
    lastPoint={x:event.clientX,y:event.clientY};
    lastPinchDistance=pointerDistance();
  }
  function onPointerMove(event){
    if(!pointers.has(event.pointerId)) return;
    pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
    const distance=pointerDistance();
    if(distance!==null&&lastPinchDistance!==null&&lastPinchDistance>0){
      state.scale=Math.max(.5,Math.min(4,state.scale*distance/lastPinchDistance));
      lastPinchDistance=distance;
    }else if(pointers.size===1&&lastPoint){
      state.offsetX+=event.clientX-lastPoint.x;
      state.offsetY+=event.clientY-lastPoint.y;
      lastPoint={x:event.clientX,y:event.clientY};
    }
    draw();
  }
  function onPointerUp(event){
    pointers.delete(event.pointerId);
    lastPoint=null;
    lastPinchDistance=pointerDistance();
  }
  function onWheel(event){
    event.preventDefault();
    state.scale=Math.max(.5,Math.min(4,state.scale*(event.deltaY<0?1.12:.89)));
    draw();
  }
  canvas.addEventListener('pointerdown',onPointerDown);
  canvas.addEventListener('pointermove',onPointerMove);
  canvas.addEventListener('pointerup',onPointerUp);
  canvas.addEventListener('pointercancel',onPointerUp);
  canvas.addEventListener('wheel',onWheel,{passive:false});
  const ResizeObserver=view&&view.ResizeObserver;
  if(ResizeObserver){
    observer=new ResizeObserver(draw);
    observer.observe(canvas);
  }else if(view){
    view.addEventListener('resize',draw);
  }
  draw();
  return function(){
    canvas.removeEventListener('pointerdown',onPointerDown);
    canvas.removeEventListener('pointermove',onPointerMove);
    canvas.removeEventListener('pointerup',onPointerUp);
    canvas.removeEventListener('pointercancel',onPointerUp);
    canvas.removeEventListener('wheel',onWheel);
    if(observer) observer.disconnect();
    if(!observer&&view) view.removeEventListener('resize',draw);
  };
}

function recoveryValidFactor(factor){
  const counterfactual=recoveryIsRecord(factor)&&factor.counterfactual;
  return recoveryIsRecord(factor)&&recoveryNonBlankString(factor.factor_id)
    &&recoveryNonBlankString(factor.label)
    &&['stable','unstable','countervailing'].includes(factor.stability)
    &&recoveryIsRecord(counterfactual)
    &&recoverySafeInteger(counterfactual.original_hybrid_rank,false)
    &&counterfactual.original_hybrid_rank>0
    &&recoverySafeInteger(counterfactual.ablated_hybrid_rank,false)
    &&counterfactual.ablated_hybrid_rank>0;
}

function recoverySigned(value){
  return (value>0?'+':'')+String(value);
}

function buildRecoveryManifestViewModel(artifact){
  if(!recoveryIsRecord(artifact)||artifact.schema_version!=='2.0'){
    return recoveryUnavailable('unsupported-or-missing-manifest');
  }
  const policy=artifact.policy;
  const coverage=artifact.coverage;
  const cohorts=artifact.cohorts;
  const bundleId=artifact.bundle_id;
  const sidecarBase=artifact.sidecar_base;
  if(!recoveryIsRecord(policy)||policy.observability_seed!==0
      ||policy.inspections_per_day!==5||policy.gnn_arm!=='sage'
      ||JSON.stringify(policy.surrounding_results_seeds)!=='[0,1,2]'
      ||!recoveryIsRecord(coverage)
      ||coverage.complete!==true||!recoveryIsRecord(cohorts)
      ||!Array.isArray(cohorts.hybrid_only)||!Array.isArray(cohorts.baseline_only)
      ||!recoveryIsRecord(artifact.case_index)
      ||!recoveryIsRecord(artifact.community_index)
      ||typeof bundleId!=='string'||!/^[0-9a-f]{24}$/.test(bundleId)
      ||sidecarBase!=='recovery/bundles/'+bundleId+'/'){
    return recoveryUnavailable('invalid-manifest-contract');
  }
  const counts=['hybrid_only_count','baseline_only_count','explained_count',
    'llm_validated_count','failed_count'];
  if(!counts.every(key=>recoverySafeInteger(coverage[key],false))
      ||coverage.hybrid_only_count!==cohorts.hybrid_only.length
      ||coverage.baseline_only_count!==cohorts.baseline_only.length
      ||coverage.explained_count!==coverage.hybrid_only_count
      ||coverage.llm_validated_count!==coverage.hybrid_only_count
      ||coverage.failed_count!==0){
    return recoveryUnavailable('incomplete-coverage');
  }
  const cases=[...cohorts.hybrid_only,...cohorts.baseline_only];
  const hybridIds=cohorts.hybrid_only.map(item=>item&&item.case_id);
  const baselineIds=cohorts.baseline_only.map(item=>item&&item.case_id);
  const allIds=[...hybridIds,...baselineIds];
  if(!cases.every(item=>recoveryIsRecord(item)
      &&recoveryNonBlankString(item.case_id)
      &&recoveryNonBlankString(item.person_id)
      &&recoveryNonBlankString(item.community_key)
      &&recoveryIsRecord(artifact.case_index[item.case_id]))
      ||new Set(allIds).size!==allIds.length
      ||Object.keys(artifact.case_index).length!==allIds.length
      ||!Object.keys(artifact.case_index).every(caseId=>allIds.includes(caseId))){
    return recoveryUnavailable('invalid-case-index');
  }
  for(const [cohortName,items] of Object.entries({
    hybrid_only:cohorts.hybrid_only,baseline_only:cohorts.baseline_only})){
    for(const item of items){
      const record=artifact.case_index[item.case_id];
      if(record.cohort!==cohortName||record.community_key!==item.community_key
          ||!recoveryIsRecord(artifact.community_index[item.community_key])){
        return recoveryUnavailable('case-index-identity-mismatch');
      }
    }
  }
  const defaultCohort=cohorts.hybrid_only.length?'hybrid_only':'baseline_only';
  const summary=recoveryIsRecord(artifact.summary)?{...artifact.summary}:{};
  const overlapFields=['baseline_recovered','recovered_by_both',
    'hybrid_only_recovered','baseline_only_recovered','hybrid_total','net_gain'];
  if(!overlapFields.every(key=>recoverySafeInteger(summary[key],true))
      ||overlapFields.slice(0,-1).some(key=>summary[key]<0)
      ||summary.hybrid_only_recovered!==cohorts.hybrid_only.length
      ||summary.baseline_only_recovered!==cohorts.baseline_only.length
      ||summary.baseline_recovered!==summary.recovered_by_both+summary.baseline_only_recovered
      ||summary.hybrid_total!==summary.recovered_by_both+summary.hybrid_only_recovered
      ||summary.net_gain!==summary.hybrid_total-summary.baseline_recovered){
    return recoveryUnavailable('invalid-overlap-algebra');
  }
  const seedLevelRecovery=recoveryIsRecord(
    summary.seed_level_unique_person_recovery
  )?summary.seed_level_unique_person_recovery:null;
  return {
    available:true,
    policy:{...policy},
    summary,
    seedLevelRecovery,
    coverage:{...coverage},
    coverageComplete:true,
    cohorts:{
      hybrid_only:cohorts.hybrid_only.slice(),
      baseline_only:cohorts.baseline_only.slice()
    },
    caseIndex:artifact.case_index,
    communityIndex:artifact.community_index,
    catalogIndex:recoveryIsRecord(artifact.catalog_index)?artifact.catalog_index:{},
    sidecarBase,
    defaultCohort,
    defaultCaseId:(cohorts[defaultCohort][0]||{}).case_id||null
  };
}

function recoverySidecarUrl(view,path){
  if(!recoverySafeSidecarPath(path))throw new Error('Unsafe sidecar path');
  const base=view.sidecarBase.endsWith('/')?view.sidecarBase:view.sidecarBase+'/';
  return base+path;
}

function recoverySafeSidecarPath(value){
  if(!recoveryNonBlankString(value)||value!==value.trim()
      ||value.startsWith('/')||value.includes('\\'))return false;
  const segments=value.split('/');
  return segments.length>0&&segments.every(segment=>
    segment.length>0&&segment!=='.'&&segment!=='..'
      &&/^[A-Za-z0-9._-]+$/.test(segment));
}

function recoverySchema3Reference(value){
  return recoveryIsRecord(value)&&recoverySafeSidecarPath(value.path)
    &&typeof value.sha256==='string'&&/^[0-9a-f]{64}$/.test(value.sha256);
}

function recoverySchema3Community(value,key){
  if(!recoveryIsRecord(value)||value.schema_version!=='1.0'
      ||value.complete!==true||value.community_key!==key
      ||!recoverySafeInteger(value.node_count,false)
      ||!recoverySafeInteger(value.edge_count,false)
      ||!recoverySafeInteger(value.provenance_observation_count,false)){
    return false;
  }
  return recoveryValidateChunkOwner(value);
}

function recoverySchema3SummaryRecord(item,cohort){
  const statuses=['not_selected','selected','available','community_only',
    'unavailable','failed'];
  const kinds=['gnn_explanation','community_control',null];
  const scoreFields=['baseline_raw','baseline_percentile',
    'seed0_gnn_probability','seed0_gnn_percentile','seed0_hybrid_score'];
  const rankFields=['baseline_rank','seed0_gnn_rank','seed0_hybrid_rank'];
  const detailKindAllowed=recoveryIsRecord(item)
    &&(item.detail_kind===null
      ||(item.detail_kind==='gnn_explanation'&&cohort==='hybrid_only')
      ||(item.detail_kind==='community_control'
        &&(cohort==='baseline_only'||cohort==='hybrid_only')));
  return recoveryIsRecord(item)&&item.cohort===cohort
    &&recoveryNonBlankString(item.case_id)
    &&recoveryNonBlankString(item.person_id)
    &&recoveryNonBlankString(item.event_id)
    &&recoveryNonBlankString(item.scoring_day)
    &&statuses.includes(item.detail_status)&&kinds.includes(item.detail_kind)
    &&detailKindAllowed
    &&scoreFields.every(key=>recoveryFiniteUnit(item[key]))
    &&rankFields.every(key=>recoverySafeInteger(item[key],false)&&item[key]>0)
    &&item.hybrid_score_semantics==='percentile_fusion_not_probability';
}

function buildRecoverySchema3ViewModel(artifact){
  if(!recoveryIsRecord(artifact)||artifact.schema_version!=='3.0'){
    return recoveryUnavailable('unsupported-or-missing-schema3-artifact');
  }
  const policy=artifact.policy;
  const validPolicy=recoveryIsRecord(policy)
    &&policy.observability_seed===0&&policy.gnn_arm==='sage'
    &&policy.inspections_per_day===5;
  const bundleId=artifact.bundle_id;
  const sidecarBase=artifact.sidecar_base;
  if(!validPolicy||typeof bundleId!=='string'||!/^[0-9a-f]{24}$/.test(bundleId)
      ||sidecarBase!=='recovery/bundles/'+bundleId+'/'){
    return recoveryUnavailable('invalid-schema3-manifest-contract');
  }
  const cohorts=artifact.cohorts;
  const cohortNames=['hybrid_only','baseline_only','recovered_by_both'];
  if(!recoveryIsRecord(cohorts)
      ||!cohortNames.every(name=>Array.isArray(cohorts[name]))){
    return recoveryUnavailable('invalid-schema3-cohorts');
  }
  const allCases=[];const caseIds=new Set();
  for(const cohort of cohortNames){
    for(const item of cohorts[cohort]){
      if(!recoverySchema3SummaryRecord(item,cohort)
          ||caseIds.has(item.case_id)){
        return recoveryUnavailable('invalid-schema3-case-records');
      }
      caseIds.add(item.case_id);allCases.push(item);
    }
  }
  const summary=artifact.summary;
  const summaryFields=['baseline_recovered','recovered_by_both',
    'hybrid_only_recovered','baseline_only_recovered','hybrid_total','net_gain'];
  if(!recoveryIsRecord(summary)
      ||!summaryFields.every(key=>recoverySafeInteger(summary[key],true))
      ||summaryFields.slice(0,-1).some(key=>summary[key]<0)
      ||summary.hybrid_only_recovered!==cohorts.hybrid_only.length
      ||summary.baseline_only_recovered!==cohorts.baseline_only.length
      ||summary.baseline_recovered!==summary.recovered_by_both
        +summary.baseline_only_recovered
      ||summary.hybrid_total!==summary.recovered_by_both
        +summary.hybrid_only_recovered
      ||summary.net_gain!==summary.hybrid_total-summary.baseline_recovered){
    return recoveryUnavailable('invalid-schema3-overlap-algebra');
  }
  const selection=artifact.selection;
  const selected=selection&&selection.selected_ids;
  if(!recoveryIsRecord(selection)||!recoveryIsRecord(selected)
      ||!cohortNames.every(name=>Array.isArray(selected[name]))
      ||selected.recovered_by_both.length!==0){
    return recoveryUnavailable('invalid-schema3-selection');
  }
  const selectedSets={};
  const cohortByCaseId=new Map(allCases.map(item=>[item.case_id,item.cohort]));
  for(const cohort of cohortNames){
    const values=selected[cohort];
    if(new Set(values).size!==values.length
        ||values.some(caseId=>!caseIds.has(caseId)
          ||cohortByCaseId.get(caseId)!==cohort)){
      return recoveryUnavailable('invalid-schema3-selection');
    }
    selectedSets[cohort]=new Set(values);
  }
  const detailIndex=artifact.detail_index;
  const communityIndex=artifact.community_index;
  const communitySidecarIndex=artifact.community_sidecar_index;
  const fallbackValues=selection.hybrid_structural_fallback_ids||[];
  if(!Array.isArray(fallbackValues)
      ||new Set(fallbackValues).size!==fallbackValues.length
      ||fallbackValues.some(caseId=>!caseIds.has(caseId)
        ||cohortByCaseId.get(caseId)!=='hybrid_only')){
    return recoveryUnavailable('invalid-schema3-selection');
  }
  const fallbackSet=new Set(fallbackValues);
  if(!recoveryIsRecord(detailIndex)||!recoveryIsRecord(communityIndex)
      ||!recoveryIsRecord(communitySidecarIndex)
      ||Object.entries(detailIndex).some(([caseId,ref])=>
        !selectedSets.hybrid_only.has(caseId)||!recoverySchema3Reference(ref))
      ||Object.entries(communityIndex).some(([caseId,ref])=>
        !(selectedSets.baseline_only.has(caseId)||fallbackSet.has(caseId))
          ||!recoverySchema3Reference(ref))
      ||Object.entries(communitySidecarIndex).some(([key,ref])=>
        !recoveryNonBlankString(key)||!recoverySchema3Reference(ref))){
    return recoveryUnavailable('invalid-schema3-sidecar-index');
  }
  const coverage=artifact.coverage;
  const coverageFields=['hybrid_requested','baseline_requested',
    'hybrid_selected','baseline_selected','hybrid_explained',
    'baseline_community','hybrid_shortfall','baseline_shortfall','shortfall'];
  if(!recoveryIsRecord(coverage)
      ||!coverageFields.every(key=>recoverySafeInteger(coverage[key],false))
      ||!Array.isArray(coverage.shortfall_reasons)
      ||coverage.hybrid_selected!==selected.hybrid_only.length
      ||coverage.baseline_selected!==selected.baseline_only.length
      ||coverage.hybrid_explained!==Object.keys(detailIndex).length
      ||coverage.baseline_community!==Object.keys(communityIndex).filter(caseId=>
        selectedSets.baseline_only.has(caseId)).length
      ||(coverage.hybrid_structural_fallback!==undefined
        &&coverage.hybrid_structural_fallback!==Object.keys(communityIndex).filter(
          caseId=>fallbackSet.has(caseId)).length)
      ||coverage.shortfall!==coverage.hybrid_shortfall+coverage.baseline_shortfall
      ||(coverage.shortfall>0&&!coverage.shortfall_reasons.length)){
    return recoveryUnavailable('invalid-schema3-coverage');
  }
  const defaultCohort=cohorts.hybrid_only.length?'hybrid_only':
    (cohorts.baseline_only.length?'baseline_only':'recovered_by_both');
  const caseIndex={};
  for(const item of allCases){
    caseIndex[item.case_id]={
      ...item,
      caseId:item.case_id,
      personId:item.person_id,
      detailStatus:item.detail_status,
      detailKind:item.detail_kind===undefined?null:item.detail_kind,
      selectionReason:recoveryNonBlankString(item.selection_reason)
        ?item.selection_reason:'not_selected',
      failureReason:recoveryNonBlankString(item.failure_reason)
        ?item.failure_reason:null,
      explanationUnavailableReason:recoveryNonBlankString(
        item.explanation_unavailable_reason)?item.explanation_unavailable_reason:null
    };
  }
  return {
    available:true,
    schemaVersion:'3.0',
    policy:{...policy},summary:{...summary},coverage:{...coverage},
    cohorts:{
      hybrid_only:cohorts.hybrid_only.map(item=>caseIndex[item.case_id]),
      baseline_only:cohorts.baseline_only.map(item=>caseIndex[item.case_id]),
      recovered_by_both:cohorts.recovered_by_both.map(item=>caseIndex[item.case_id])
    },
    caseIndex,
    selection:{...selection,selected_ids:{...selected}},
    detailIndex:{...detailIndex},communityIndex:{...communityIndex},
    communitySidecarIndex:{...communitySidecarIndex},
    catalogIndex:recoveryIsRecord(artifact.catalog_index)?artifact.catalog_index:{},
    sidecarBase,defaultCohort,
    defaultCaseId:Object.keys(detailIndex)[0]
      ||(cohorts[defaultCohort][0]||{}).case_id||null
  };
}

const RECOVERY_SCHEMA3_FILTERS=['all','hybrid_only','baseline_only',
  'recovered_by_both','gnn_explanation','community_control','all_detail'];

function filterRecoverySchema3Cases(view,filter){
  if(!recoveryIsRecord(view)||view.available!==true)return [];
  const selected=RECOVERY_SCHEMA3_FILTERS.includes(filter)?filter:'all';
  const cohortNames=['hybrid_only','baseline_only','recovered_by_both'];
  const rows=[];
  for(const cohort of cohortNames){
    for(const record of view.cohorts[cohort])rows.push(record);
  }
  if(cohortNames.includes(selected)){
    return rows.filter(record=>record.cohort===selected);
  }
  if(selected==='all_detail'){
    return rows.filter(record=>record.detailKind!==null);
  }
  if(selected==='all')return rows;
  return rows.filter(record=>record.detailKind===selected);
}

const RECOVERY_STRUCTURAL_STAGES=['first_hop','second_hop','component_pool'];
const RECOVERY_GRAPH_NODE_LIMIT=1500;
const RECOVERY_GRAPH_EDGE_LIMIT=4000;

function buildStructuralDrawCommands(control,options){
  if(!recoveryIsRecord(control)||!recoveryNonBlankString(control.person_id)
      ||!recoveryIsRecord(control.community)
      ||control.community.complete!==true){
    return recoveryUnavailable('incomplete-community');
  }
  const settings=recoveryIsRecord(options)?options:{};
  if(!['all','flow'].includes(settings.mode)
      ||!RECOVERY_STRUCTURAL_STAGES.includes(settings.stageId)){
    return recoveryUnavailable('invalid-view-options');
  }
  const community=control.community;
  if(!Array.isArray(community.nodes)||!Array.isArray(community.edges)){
    return recoveryUnavailable('invalid-community-membership');
  }
  const nodeIds=community.nodes.map(node=>recoveryIsRecord(node)?node.node_id:null);
  const nodeSet=new Set(nodeIds);
  if(!community.nodes.every(node=>recoveryIsRecord(node)
        &&recoveryNonBlankString(node.node_id))
      ||nodeIds.length===0||nodeSet.size!==nodeIds.length
      ||!nodeSet.has(control.person_id)){
    return recoveryUnavailable('invalid-community-membership');
  }
  const edgeIds=community.edges.map(edge=>recoveryIsRecord(edge)?edge.edge_id:null);
  if(!community.edges.every(edge=>recoveryIsRecord(edge)
        &&recoveryNonBlankString(edge.edge_id)
        &&recoveryNonBlankString(edge.u)&&recoveryNonBlankString(edge.v)
        &&nodeSet.has(edge.u)&&nodeSet.has(edge.v))
      ||new Set(edgeIds).size!==edgeIds.length){
    return recoveryUnavailable('invalid-community-membership');
  }
  if(!community.nodes.every(node=>recoveryFiniteUnit(node.x)
      &&recoveryFiniteUnit(node.y))){
    return recoveryUnavailable('invalid-community-coordinates');
  }
  const stages=control.structural_stages;
  if(!Array.isArray(stages)||stages.length!==RECOVERY_STRUCTURAL_STAGES.length){
    return recoveryUnavailable('invalid-structural-stages');
  }
  const stagesById=new Map();
  for(const stage of stages){
    if(!recoveryIsRecord(stage)
        ||!RECOVERY_STRUCTURAL_STAGES.includes(stage.stage_id)
        ||stagesById.has(stage.stage_id)
        ||!recoveryIsRecord(stage.edge_rule)
        ||!recoveryValidStageRule(stage,nodeIds,edgeIds)){
      return recoveryUnavailable('invalid-structural-stages');
    }
    stagesById.set(stage.stage_id,stage);
  }
  if(RECOVERY_STRUCTURAL_STAGES.some(id=>!stagesById.has(id))){
    return recoveryUnavailable('invalid-structural-stages');
  }
  const nodesById=new Map(community.nodes.map(node=>[node.node_id,node]));
  const selectedStage=stagesById.get(settings.stageId);
  const query=(typeof settings.query==='string'?settings.query:'')
    .trim().toLowerCase();
  const nodes=community.nodes.slice().sort((a,b)=>
    recoveryCompareId(a.node_id,b.node_id)).map(node=>({
      node_id:node.node_id,
      id:node.node_id,
      x:node.x,
      y:node.y,
      target:node.node_id===control.person_id,
      pooledMember:node.pooled_member===true,
      caughtBeforeSnapshot:node.caught_before_snapshot===true,
      importance:0,
      attributed:false,
      rank:null,
      matched:query.length>0&&node.node_id.toLowerCase().includes(query)
    }));
  const edges=community.edges.slice().sort((a,b)=>
    recoveryCompareId(a.edge_id,b.edge_id)).map(edge=>({
      edge_id:edge.edge_id,
      id:edge.edge_id,
      u:edge.u,
      v:edge.v,
      relation:recoveryNonBlankString(edge.edge_type)?edge.edge_type:'RELATION',
      // A control has no explainer mask, so every edge keeps neutral weight.
      importance:0,
      attributed:false,
      rank:null,
      emphasized:settings.mode==='all'
        ||recoveryStageEmphasizes(selectedStage,edge,nodesById)
    }));
  const slice=buildRecoveryGraphSlice(nodes,edges,control.person_id);
  return {
    available:true,
    mode:settings.mode,
    stageId:settings.stageId,
    nodes:slice.nodes,
    edges:slice.edges,
    tableNodes:slice.tableNodes,
    tableEdges:slice.tableEdges,
    sampled:slice.sampled,
    fullNodeCount:slice.fullNodeCount,
    fullEdgeCount:slice.fullEdgeCount,
    provenanceNodes:[],
    provenanceEdges:[]
  };
}

function assembleRecoverySchema3Community(manifest,nodeRows,edgeRows){
  if(!recoveryIsRecord(manifest))return recoveryUnavailable('missing-community');
  if(!Array.isArray(nodeRows)||!Array.isArray(edgeRows)){
    return recoveryUnavailable('community-not-loaded');
  }
  if(nodeRows.length!==manifest.node_count
      ||edgeRows.length!==manifest.edge_count){
    return recoveryUnavailable('community-partially-loaded');
  }
  return {
    available:true,
    community:{
      complete:true,
      community_key:manifest.community_key,
      node_count:manifest.node_count,
      edge_count:manifest.edge_count,
      nodes:nodeRows,
      edges:edgeRows,
      provenance_expansions:[]
    }
  };
}

function mergeRecoverySchema3Overlay(community,overlayNodes,overlayEdges){
  if(!recoveryIsRecord(community)
      ||community.complete!==true
      ||!recoverySafeInteger(community.node_count,false)
      ||!recoverySafeInteger(community.edge_count,false)
      ||!Array.isArray(community.nodes)||!Array.isArray(community.edges)
      ||community.node_count!==community.nodes.length
      ||community.edge_count!==community.edges.length
      ||!Array.isArray(overlayNodes)||!Array.isArray(overlayEdges)){
    return recoveryUnavailable('invalid-overlay-identity');
  }
  const baseNodesById=new Map();
  for(const node of community.nodes){
    if(!recoveryIsRecord(node)||!recoveryNonBlankString(node.node_id)){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    const nodeId=node.node_id.trim();
    if(baseNodesById.has(nodeId)){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    baseNodesById.set(nodeId,node);
  }
  const baseEdgesById=new Map();
  for(const edge of community.edges){
    if(!recoveryIsRecord(edge)||!recoveryNonBlankString(edge.edge_id)
        ||!recoveryNonBlankString(edge.u)||!recoveryNonBlankString(edge.v)
        ||!recoveryNonBlankString(edge.edge_type)){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    const edgeId=edge.edge_id.trim();
    if(baseEdgesById.has(edgeId)
        ||!baseNodesById.has(edge.u.trim())||!baseNodesById.has(edge.v.trim())){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    if(edge.relation!==undefined
        &&(!recoveryNonBlankString(edge.relation)
          ||edge.relation.trim()!==edge.edge_type.trim())){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    baseEdgesById.set(edgeId,edge);
  }

  const overlayNodeById=new Map();
  for(const node of overlayNodes){
    if(!recoveryIsRecord(node)||!recoveryNonBlankString(node.node_id)
        ||!recoveryFiniteUnit(node.explainer_median)
        ||!recoverySafeInteger(node.rank,false)||node.rank<1){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    const nodeId=node.node_id.trim();
    if(overlayNodeById.has(nodeId)){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    if(!baseNodesById.has(nodeId)){
      return recoveryUnavailable('invalid-overlay-membership');
    }
    overlayNodeById.set(nodeId,node);
  }

  const overlayEdgeById=new Map();
  for(const edge of overlayEdges){
    if(!recoveryIsRecord(edge)||!recoveryNonBlankString(edge.edge_id)
        ||!recoveryNonBlankString(edge.u)||!recoveryNonBlankString(edge.v)
        ||!recoveryNonBlankString(edge.edge_type)
        ||!recoveryFiniteUnit(edge.explainer_median)
        ||!recoverySafeInteger(edge.rank,false)||edge.rank<1){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    const edgeId=edge.edge_id.trim();
    if(overlayEdgeById.has(edgeId)){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    const baseEdge=baseEdgesById.get(edgeId);
    if(!baseEdge)return recoveryUnavailable('invalid-overlay-membership');
    for(const field of ['u','v']){
      if(edge[field].trim()!==baseEdge[field].trim()){
        return recoveryUnavailable('invalid-overlay-membership');
      }
    }
    if(edge.edge_type.trim()!==baseEdge.edge_type.trim()
        ||(edge.relation!==undefined
          &&(!recoveryNonBlankString(edge.relation)
            ||edge.relation.trim()!==edge.edge_type.trim()))){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    overlayEdgeById.set(edgeId,edge);
  }

  function normalizedRow(base,row,isEdge){
    const result={...base,importance:0,attributed:false,rank:null};
    const identityFields=isEdge
      ?['edge_id','u','v','edge_type','relation']:['node_id'];
    const overlayFields=isEdge
      ?['edge_id','u','v','edge_type','relation',
        'explainer_median','importance','attributed','rank']
      :['node_id','explainer_median','importance','attributed','rank'];
    function trimIdentityFields(){
      for(const field of identityFields){
        if(recoveryNonBlankString(result[field]))result[field]=result[field].trim();
      }
    }
    trimIdentityFields();
    if(isEdge){
      result.relation=recoveryNonBlankString(base.relation)
        ?base.relation.trim():result.edge_type;
    }
    if(row){
      for(const key of overlayFields){
        if(Object.prototype.hasOwnProperty.call(row,key))result[key]=row[key];
      }
      trimIdentityFields();
      result.importance=Math.max(0,Math.min(1,row.explainer_median));
      result.attributed=true;
      result.rank=row.rank;
      if(isEdge){
        result.relation=recoveryNonBlankString(row.relation)
          ?row.relation.trim():result.edge_type;
      }
    }
    return result;
  }
  return {
    available:true,
    nodes:community.nodes.map(node=>normalizedRow(
      node,overlayNodeById.get(node.node_id.trim()),false)),
    edges:community.edges.map(edge=>normalizedRow(
      edge,overlayEdgeById.get(edge.edge_id.trim()),true))
  };
}

function buildRecoverySchema3Detail(record,payload,communityView,overlayRows){
  if(!recoveryIsRecord(record))return recoveryUnavailable('missing-case');
  const kind=record.detailKind;
  if(kind!=='gnn_explanation'&&kind!=='community_control'){
    return recoveryUnavailable('no-detail-selected');
  }
  if(!recoveryIsRecord(payload))return recoveryUnavailable('sidecar-unavailable');
  if(!recoveryIsRecord(communityView)||communityView.available!==true){
    return {available:false,kind,
      reason:recoveryIsRecord(communityView)&&communityView.reason
        ?communityView.reason:'community-unavailable'};
  }
  const detail=payload.detail;
  const explanation=kind==='gnn_explanation'
    ?(payload.explanation||(recoveryIsRecord(detail)?detail.explanation:null))
    :null;
  if(kind==='gnn_explanation'&&!recoveryIsRecord(explanation)){
    return {available:false,kind,reason:'explanation-unavailable'};
  }
  if(kind==='community_control'&&!recoveryIsRecord(detail)){
    return {available:false,kind,reason:'structural-detail-unavailable'};
  }
  const boundarySource=kind==='gnn_explanation'?explanation:detail;
  const evidenceBoundary=recoveryIsRecord(boundarySource)
    ?boundarySource.evidence_boundary:null;
  if(!validateRecoveryEvidenceBoundary(
    {evidence_boundary:evidenceBoundary},record.scoring_day).available){
    return {available:false,kind,reason:'invalid-evidence-boundary'};
  }
  let explanationPresentation=null;
  if(kind==='gnn_explanation'){
    let presentationOverlay=overlayRows;
    if(presentationOverlay===undefined||presentationOverlay===null){
      presentationOverlay={
        available:true,
        nodes:communityView.community.nodes.map(node=>
          ({...node,importance:0,attributed:false})),
        edges:communityView.community.edges.map(edge=>
          ({...edge,importance:0,attributed:false}))
      };
    }else if(!recoveryIsRecord(presentationOverlay)
        ||presentationOverlay.available!==true
        ||!Array.isArray(presentationOverlay.nodes)
        ||!Array.isArray(presentationOverlay.edges)){
      return {available:false,kind,
        reason:recoveryIsRecord(presentationOverlay)&&presentationOverlay.reason
          ?presentationOverlay.reason:'invalid-overlay-presentation'};
    }
    explanationPresentation={...explanation,person_id:record.personId,
      community:communityView.community,
      overlayNodes:presentationOverlay.nodes,
      overlayEdges:presentationOverlay.edges};
  }
  return {
    available:true,
    kind,
    personId:record.personId,
    explanation:explanationPresentation,
    control:kind==='community_control'
      ?{person_id:record.personId,community:communityView.community,
        structural_stages:detail.structural_stages}
      :null,
    evidenceBoundary,
    nodeCount:communityView.community.nodes.length,
    edgeCount:communityView.community.edges.length,
    canvasAvailable:kind==='gnn_explanation'||(
      communityView.community.nodes.length<=RECOVERY_GRAPH_NODE_LIMIT
      &&communityView.community.edges.length<=RECOVERY_GRAPH_EDGE_LIMIT)
  };
}

const recoveryCatalogChunkCache=new Map();

async function recoveryFetchJson(url,expectedHash){
  if(typeof expectedHash!=='string'||!/^[0-9a-f]{64}$/.test(expectedHash)){
    throw new Error('Sidecar reference requires a 64-character lowercase SHA-256 hash');
  }
  if(!globalThis.crypto||!globalThis.crypto.subtle){
    throw new Error('WebCrypto SHA-256 is required to verify recovery sidecars');
  }
  const response=await fetch(url,{cache:'no-store'});
  if(!response.ok) throw new Error('HTTP '+response.status+' for '+url);
  const bytes=await response.arrayBuffer();
  const digest=await globalThis.crypto.subtle.digest('SHA-256',bytes);
  const actual=Array.from(new Uint8Array(digest))
    .map(value=>value.toString(16).padStart(2,'0')).join('');
  if(actual!==expectedHash) throw new Error('SHA-256 mismatch for '+url);
  return JSON.parse(new TextDecoder().decode(bytes));
}

function recoveryServerHelp(error){
  return 'Sidecars require local HTTP. From the repository root run: '
    +'python -m http.server 8000 --directory Documents/Data/v9_dashboard, '
    +'then open http://localhost:8000/index.html. Fetch error: '
    +String(error&&error.message||error);
}

function recoveryPage(rows,page,size){
  const values=Array.isArray(rows)?rows:[];
  const pageSize=Math.max(1,Number(size)||25);
  const totalPages=Math.max(1,Math.ceil(values.length/pageSize));
  const selected=Math.max(0,Math.min(totalPages-1,Number(page)||0));
  return {rows:values.slice(selected*pageSize,(selected+1)*pageSize),page:selected,totalPages};
}

function recoveryClusterNodes(nodes,query){
  const needle=String(query||'').trim().toLowerCase();
  const groups=new Map();
  for(const node of Array.isArray(nodes)?nodes:[]){
    const nodeId=String(node&&node.node_id||'');
    if(needle&&!nodeId.toLowerCase().includes(needle)) continue;
    const cluster=String(node.cluster_id||node.kind||'community');
    if(!groups.has(cluster)) groups.set(cluster,[]);
    groups.get(cluster).push(nodeId);
  }
  return Array.from(groups.entries()).sort((a,b)=>recoveryCompareId(a[0],b[0]))
    .map(([cluster,nodeIds])=>({cluster,node_ids:nodeIds.sort(recoveryCompareId)}));
}

function recoveryValidateChunkOwner(owner){
  if(!recoveryIsRecord(owner)||owner.complete!==true
      ||owner.nodes!==undefined||owner.edges!==undefined)return false;
  const specs=[
    ['node_chunks','node_count'],['edge_chunks','edge_count'],
    ['provenance_chunks','provenance_observation_count'],
    ['provenance_expansion_membership_chunks',null]
  ];
  for(const [field,countField] of specs){
    const refs=owner[field];
    if(!Array.isArray(refs))return false;
    let expectedOffset=0;
    for(const ref of refs){
      if(!recoveryIsRecord(ref)||!recoverySafeSidecarPath(ref.path)
          ||!recoveryNonBlankString(ref.sha256)
          ||ref.offset!==expectedOffset||!recoverySafeInteger(ref.count,false))return false;
      expectedOffset+=ref.count;
    }
    if(countField&&owner[countField]!==expectedOffset)return false;
  }
  if(owner.day_view!==undefined){
    if(!recoveryIsRecord(owner.day_view))return false;
    const daySpecs=[
      ['node_status_chunks','node_count'],
      ['edge_membership_chunks','edge_count']
    ];
    for(const [field,countField] of daySpecs){
      const refs=owner.day_view[field];
      if(!Array.isArray(refs))return false;
      let expectedOffset=0;
      for(const ref of refs){
        if(!recoveryIsRecord(ref)||!recoverySafeSidecarPath(ref.path)
            ||!recoveryNonBlankString(ref.sha256)
            ||ref.offset!==expectedOffset||!recoverySafeInteger(ref.count,false))return false;
        expectedOffset+=ref.count;
      }
      if(owner[countField]!==expectedOffset)return false;
    }
  }
  return true;
}

function recoveryValidatedChunkRows(payload,ref,rowField){
  if(!recoveryIsRecord(payload)||!recoveryIsRecord(ref)
      ||!Array.isArray(payload[rowField])
      ||payload.offset!==ref.offset||payload.count!==ref.count
      ||payload.count!==payload[rowField].length)return null;
  return payload[rowField];
}

function recoveryV2Panel(doc,title,value){
  const panel=recoveryElement(doc,'section','v9-recovery-v2-panel');
  panel.appendChild(recoveryElement(doc,'h5','',title));
  panel.appendChild(recoveryElement(doc,'pre','',JSON.stringify(value||null,null,2)));
  return panel;
}

async function recoveryResolveCatalogRows(view,rows,kind){
  const catalog=view.catalogIndex&&view.catalogIndex[kind];
  if(!recoveryIsRecord(catalog)||!Array.isArray(catalog.chunks)){
    throw new Error('Normalized catalog index is missing');
  }
  const needed=new Map();
  for(const row of rows){
    const catalogId=row&&row.catalog_id;
    const chunk=catalog.chunks.find(
      candidate=>candidate.first_id<=catalogId&&catalogId<=candidate.last_id);
    if(!chunk)throw new Error('Normalized catalog record is not indexed');
    needed.set(chunk.path,chunk);
  }
  const recordsById=new Map();
  await Promise.all(Array.from(needed.values()).map(async chunk=>{
    const cacheKey=recoverySidecarUrl(view,chunk.path)+'|'+chunk.sha256;
    let records=recoveryCatalogChunkCache.get(cacheKey);
    if(!records){
      const catalogPayload=await recoveryFetchJson(
        recoverySidecarUrl(view,chunk.path),chunk.sha256);
      records=recoveryValidatedChunkRows(catalogPayload,chunk,'records');
      if(records===null)throw new Error('Normalized catalog chunk is invalid');
      recoveryCatalogChunkCache.set(cacheKey,records);
    }
    for(const entry of records){
      if(!recoveryIsRecord(entry)||!recoveryNonBlankString(entry.record_id)
          ||!recoveryIsRecord(entry.record)){
        throw new Error('Normalized catalog chunk is invalid');
      }
      recordsById.set(entry.record_id,entry.record);
    }
  }));
  for(const row of rows){
    if(!recoveryIsRecord(row)||!recoveryNonBlankString(row.catalog_id)
        ||!recordsById.has(row.catalog_id)){
      throw new Error('Normalized catalog record is missing');
    }
    const identityField=kind==='nodes'?'node_id'
      :(kind==='edges'?'edge_id':'source_row_id');
    const catalogRecord=recordsById.get(row.catalog_id);
    if(!recoveryNonBlankString(row[identityField])
        ||!recoveryNonBlankString(catalogRecord[identityField])
        ||row[identityField]!==catalogRecord[identityField]){
      throw new Error('Normalized catalog identity contract is invalid');
    }
  }
  return rows.map(row=>{
    const detached={...row};delete detached.catalog_id;
    return {...(recordsById.get(row.catalog_id)||{}),...detached};
  });
}

async function recoveryApplyDayView(view,owner,normalized,index,resolvedRows){
  const dayConfig=normalized==='node'
    ?['node_status_chunks','node_statuses','node_id']
    :['edge_membership_chunks','edge_memberships','edge_id'];
  const dayRefs=owner.day_view[dayConfig[0]];
  if(!Array.isArray(dayRefs)||!dayRefs[index]){
    throw new Error('Normalized day-view chunk is missing');
  }
  const dayRef=dayRefs[index];
  const dayPayload=await recoveryFetchJson(
    recoverySidecarUrl(view,dayRef.path),dayRef.sha256);
  const dayRows=recoveryValidatedChunkRows(dayPayload,dayRef,dayConfig[1]);
  if(dayRows===null)throw new Error('Day-view chunk offset or count contract is invalid');
  const dayIds=dayRows.map(row=>recoveryIsRecord(row)?row[dayConfig[2]]:null);
  const resolvedIds=resolvedRows.map(row=>recoveryIsRecord(row)
    ?row[dayConfig[2]]:null);
  if(!recoverySameIds(dayIds,resolvedIds)){
    throw new Error('Normalized day-view identity contract is invalid');
  }
  const stateById=new Map(dayRows.map(row=>[row[dayConfig[2]],row]));
  return resolvedRows.map(
    row=>({...row,...(stateById.get(row[dayConfig[2]])||{})}));
}

function mountRecoveryExplorerV2(root,artifact,tools){
  const doc=root.ownerDocument;
  const view=buildRecoveryManifestViewModel(artifact);
  const fmt=recoveryIsRecord(tools)&&typeof tools.fmt==='function'
    ?tools.fmt:value=>Number(value||0).toLocaleString();
  const state={cohort:view.available?view.defaultCohort:'hybrid_only',
    caseId:view.available?view.defaultCaseId:null,caseData:null,community:null,
    nodePages:{},edgePages:{},provenancePages:{},membershipPages:{},
    overlayNodePages:{},overlayEdgePages:{},overlayProvenancePages:{},
    overlayMembershipPages:{},
    loadedNodeCount:0,loadedEdgeCount:0,loadedProvenanceCount:0,
    loadedMembershipCount:0,loadedOverlayNodeCount:0,loadedOverlayEdgeCount:0,
    loadedOverlayProvenanceCount:0,loadedOverlayMembershipCount:0,
    loading:false,error:null,nodeQuery:'',relation:'all',nodePage:0,edgePage:0,
    provenancePage:0,membershipPage:0,overlayNodePage:0,overlayEdgePage:0,
    overlayProvenancePage:0,overlayMembershipPage:0};
  let recoveryRequestToken=0;
  let disposed=false;
  const rows=()=>view.available?view.cohorts[state.cohort]:[];

  function renderV2Detail(detail){
    if(state.error){
      detail.appendChild(recoveryElement(doc,'div','v9-recovery-empty',recoveryServerHelp(state.error)));
      return;
    }
    if(state.loading&&!state.caseData){
      detail.appendChild(recoveryElement(doc,'div','v9-recovery-status','Loading selected case...'));
      return;
    }
    if(!state.caseData) return;
    const data=state.caseData;
    detail.appendChild(recoveryV2Panel(doc,'Selected anchor-event ranks',{
      baseline_rank:data.case.baseline_rank,seed0_gnn_rank:data.case.seed0_gnn_rank,
      seed0_hybrid_rank:data.case.seed0_hybrid_rank}));
    detail.appendChild(recoveryElement(doc,'p','v9-recovery-intro',
      'B / G / H values are anchor-event ranks among daily candidate events; cohort recovery remains unique-person.'));
    const panels=recoveryElement(doc,'div','v9-recovery-v2-panels');
    if(state.cohort==='hybrid_only'){
      const explanation=data.explanation||{};
      detail.appendChild(renderHighestAttributionPanel(doc,explanation));
      const narrative=explanation.llm_narrative||{};
      const attributions=explanation.attributions||{};
      const ledger=explanation.decision_ledger||{};
      const componentPooling=ledger.component_pooling||{};
      panels.appendChild(recoveryV2Panel(doc,'Validated local Gemma narrative',
        narrative.validated===true&&narrative.source==='llm'?narrative:{status:'unavailable'}));
      panels.appendChild(recoveryV2Panel(doc,'attributions.top_edges',attributions.top_edges));
      panels.appendChild(recoveryV2Panel(doc,'attributions.top_local_nodes',attributions.top_local_nodes));
      panels.appendChild(recoveryV2Panel(doc,'attributions.top_features',attributions.top_features));
      panels.appendChild(recoveryV2Panel(doc,
        'decision_ledger.component_pooling.top_members_by_absolute_contribution',
        componentPooling.top_members_by_absolute_contribution));
      panels.appendChild(recoveryV2Panel(doc,'decision_ledger.rank_fusion',ledger.rank_fusion));
      panels.appendChild(recoveryV2Panel(doc,'Local GNNExplainer overlay',{
        edge_importance:attributions.top_edges||[],
        node_importance:attributions.top_local_nodes||[],
        feature_importance:attributions.top_features||[]
      }));
    }else{
      panels.appendChild(recoveryV2Panel(doc,
        'No GNN explanation is generated for Baseline-only cases by policy.',
        {policy:data.explanation_policy}));
    }
    detail.appendChild(panels);
    if(!state.community) return;
    const membershipTotal=(state.community.provenance_expansion_membership_chunks||[])
      .reduce((sum,ref)=>sum+Number(ref.count||0),0);
    const complete=state.loadedNodeCount===state.community.node_count
      &&state.loadedEdgeCount===state.community.edge_count
      &&state.loadedProvenanceCount===state.community.provenance_observation_count
      &&state.loadedMembershipCount===membershipTotal;
    const communityPanel=recoveryElement(doc,'section','v9-recovery-v2-panel');
    communityPanel.appendChild(recoveryElement(doc,'h5','',complete
      ?'Complete community':'Community loading'));
    communityPanel.appendChild(recoveryElement(doc,'div','v9-recovery-progress',
      'Nodes '+state.loadedNodeCount+' loaded / '+state.community.node_count
        +' total; edges '+state.loadedEdgeCount+' loaded / '+state.community.edge_count
        +' total; provenance '+state.loadedProvenanceCount+' loaded / '
        +state.community.provenance_observation_count+' total; expansion memberships '
        +state.loadedMembershipCount+' loaded / '+membershipTotal+' total.'));
    const search=recoveryElement(doc,'input','v9-recovery-search');
    search.type='search';search.placeholder='Node search (current node page)';
    search.value=state.nodeQuery;search.dataset.v2Input='node';
    search.setAttribute('aria-label','Node search, current node page only');
    communityPanel.appendChild(search);
    const relation=recoveryElement(doc,'select','v9-recovery-select');
    relation.dataset.v2Change='relation';relation.setAttribute('aria-label','Relation filter');
    const loadedEdges=Object.values(state.edgePages).flat();
    for(const value of ['all',...new Set(loadedEdges.map(edge=>edge.edge_type||'RELATION'))]){
      const option=recoveryElement(doc,'option','',value==='all'?'Relation filter: all':value);
      option.value=value;relation.appendChild(option);
    }
    relation.value=state.relation;communityPanel.appendChild(relation);
    const pageNodes=state.nodePages[state.nodePage]||[];
    communityPanel.appendChild(recoveryV2Panel(doc,
      'Clustered nodes (search scope: current node page)',
      recoveryClusterNodes(pageNodes,state.nodeQuery)));
    const pageEdges=state.edgePages[state.edgePage]||[];
    const edges=state.relation==='all'?pageEdges:pageEdges.filter(
      edge=>(edge.edge_type||'RELATION')===state.relation);
    const provenanceRows=state.provenancePages[state.provenancePage]||[];
    const membershipRows=state.membershipPages[state.membershipPage]||[];
    const nodePageCount=Math.max(1,(state.community.node_chunks||[]).length);
    const edgePageCount=Math.max(1,(state.community.edge_chunks||[]).length);
    const provenancePageCount=Math.max(1,(state.community.provenance_chunks||[]).length);
    const membershipPageCount=Math.max(1,
      (state.community.provenance_expansion_membership_chunks||[]).length);
    communityPanel.appendChild(recoveryV2Panel(doc,
      'Node page (base community) '+(state.nodePage+1)+' / '+nodePageCount,pageNodes));
    communityPanel.appendChild(recoveryV2Panel(doc,
      'Edge page (base community) '+(state.edgePage+1)+' / '+edgePageCount,edges));
    communityPanel.appendChild(recoveryV2Panel(doc,
      'Provenance page (base community) '+(state.provenancePage+1)+' / '+provenancePageCount,
      provenanceRows));
    communityPanel.appendChild(recoveryV2Panel(doc,
      'Expansion membership page (base community) '+(state.membershipPage+1)+' / '
        +membershipPageCount,membershipRows));
    const overlay=data.overlay_evidence;
    let overlayPageCounts=null;
    if(overlay){
      overlayPageCounts={
        node:Math.max(1,overlay.node_chunks.length),
        edge:Math.max(1,overlay.edge_chunks.length),
        provenance:Math.max(1,overlay.provenance_chunks.length),
        membership:Math.max(1,overlay.provenance_expansion_membership_chunks.length)
      };
      communityPanel.appendChild(recoveryElement(doc,'div','v9-recovery-progress',
        'Case attribution overlay: nodes '+state.loadedOverlayNodeCount+' loaded / '
          +overlay.node_count+' total; edges '+state.loadedOverlayEdgeCount+' loaded / '
          +overlay.edge_count+' total; provenance '+state.loadedOverlayProvenanceCount
          +' loaded / '+overlay.provenance_observation_count+' total.'));
      communityPanel.appendChild(recoveryV2Panel(doc,
        'Case attribution overlay node page '+(state.overlayNodePage+1)+' / '
          +overlayPageCounts.node,state.overlayNodePages[state.overlayNodePage]||[]));
      communityPanel.appendChild(recoveryV2Panel(doc,
        'Case attribution overlay edge page '+(state.overlayEdgePage+1)+' / '
          +overlayPageCounts.edge,state.overlayEdgePages[state.overlayEdgePage]||[]));
      communityPanel.appendChild(recoveryV2Panel(doc,
        'Case attribution overlay provenance page '+(state.overlayProvenancePage+1)
          +' / '+overlayPageCounts.provenance,
        state.overlayProvenancePages[state.overlayProvenancePage]||[]));
      communityPanel.appendChild(recoveryV2Panel(doc,
        'Case attribution overlay expansion membership page '
          +(state.overlayMembershipPage+1)+' / '+overlayPageCounts.membership,
        state.overlayMembershipPages[state.overlayMembershipPage]||[]));
    }
    const pages=recoveryElement(doc,'div','v9-recovery-toolgroup');
    const pageButtons=[
      ['Previous node page','node-prev',state.nodePage===0],
      ['Next node page','node-next',state.nodePage+1>=nodePageCount],
      ['Previous edge page','edge-prev',state.edgePage===0],
      ['Next edge page','edge-next',state.edgePage+1>=edgePageCount],
      ['Previous provenance page','provenance-prev',state.provenancePage===0],
      ['Next provenance page','provenance-next',state.provenancePage+1>=provenancePageCount],
      ['Previous expansion membership page','membership-prev',state.membershipPage===0],
      ['Next expansion membership page','membership-next',
        state.membershipPage+1>=membershipPageCount]
    ];
    if(overlayPageCounts)pageButtons.push(
      ['Previous overlay node page','overlay-node-prev',state.overlayNodePage===0],
      ['Next overlay node page','overlay-node-next',
        state.overlayNodePage+1>=overlayPageCounts.node],
      ['Previous overlay edge page','overlay-edge-prev',state.overlayEdgePage===0],
      ['Next overlay edge page','overlay-edge-next',
        state.overlayEdgePage+1>=overlayPageCounts.edge],
      ['Previous overlay provenance page','overlay-provenance-prev',
        state.overlayProvenancePage===0],
      ['Next overlay provenance page','overlay-provenance-next',
        state.overlayProvenancePage+1>=overlayPageCounts.provenance],
      ['Previous overlay membership page','overlay-membership-prev',
        state.overlayMembershipPage===0],
      ['Next overlay membership page','overlay-membership-next',
        state.overlayMembershipPage+1>=overlayPageCounts.membership]
    );
    for(const [label,value,disabled] of pageButtons){
      const button=recoveryElement(doc,'button','v9-recovery-button',label);
      button.type='button';button.disabled=disabled;
      button.setAttribute('data-v2-page',value);pages.appendChild(button);
    }
    communityPanel.appendChild(pages);
    detail.appendChild(communityPanel);
  }

  function renderV2(){
    const fragment=doc.createDocumentFragment();
    const title=recoveryElement(doc,'h3','v9-recovery-title','Why Hybrid recovered different people');
    title.id='v9-recovery-title';fragment.appendChild(title);
    fragment.appendChild(recoveryElement(doc,'p','v9-recovery-intro',
      'Seed-0, K=5 unique-person evidence. Main panels preserve distinct seed, ensemble, event and person semantics.'));
    if(!view.available){fragment.appendChild(recoveryElement(doc,'div','v9-recovery-empty',view.reason));root.replaceChildren(fragment);return;}
    fragment.appendChild(recoveryElement(doc,'div','v9-recovery-coverage',
      fmt(view.coverage.hybrid_only_count)+' Hybrid-only / '
        +fmt(view.coverage.baseline_only_count)+' Baseline-only / complete validated coverage'));
    const seedLevel=view.seedLevelRecovery||{};
    const semantics=recoveryElement(doc,'div','v9-recovery-v2-panels');
    semantics.appendChild(recoveryV2Panel(doc,'Per-seed unique-person recovery',
      seedLevel.seeds||null));
    semantics.appendChild(recoveryV2Panel(doc,
      'Per-seed mean / Population SD / common_validation_tuned_fusion_weight',{
        mean:seedLevel.mean,population_sd:seedLevel.population_sd,
        common_validation_tuned_fusion_weight:seedLevel.common_validation_tuned_fusion_weight
      }));
    semantics.appendChild(recoveryV2Panel(doc,
      'score_averaged_ensemble / separate ensemble ranking',
      seedLevel.score_averaged_ensemble||null));
    semantics.appendChild(recoveryV2Panel(doc,'Ensemble ranking / event-level metrics',
      {semantics:'Main V9 found@K panels count event hits; they do not count unique people.'}));
    semantics.appendChild(recoveryV2Panel(doc,'Individual unique-person overlap',
      view.summary));
    fragment.appendChild(semantics);
    const cohorts=recoveryElement(doc,'div','v9-recovery-cohorts');
    for(const [value,label] of [['hybrid_only','Hybrid-only'],['baseline_only','Baseline-only']]){
      const button=recoveryElement(doc,'button','',label);button.type='button';
      button.dataset.v2Cohort=value;button.setAttribute('aria-pressed',String(state.cohort===value));
      cohorts.appendChild(button);
    }
    fragment.appendChild(cohorts);
    const grid=recoveryElement(doc,'div','v9-recovery-v2-grid');
    const list=recoveryElement(doc,'aside','v9-recovery-v2-list');
    for(const item of rows()){
      const button=recoveryElement(doc,'button','v9-recovery-case');button.type='button';
      button.dataset.v2Case=item.case_id;button.setAttribute('aria-current',String(item.case_id===state.caseId));
      button.appendChild(recoveryElement(doc,'strong','',item.person_id));
      button.appendChild(recoveryElement(doc,'div','v9-recovery-case-meta',
        'B '+fmt(item.baseline_rank)+' / G '+fmt(item.seed0_gnn_rank)+' / H '+fmt(item.seed0_hybrid_rank)));
      list.appendChild(button);
    }
    grid.appendChild(list);const detail=recoveryElement(doc,'div','v9-recovery-v2-detail');
    renderV2Detail(detail);grid.appendChild(detail);fragment.appendChild(grid);root.replaceChildren(fragment);
  }

  async function loadSelected(){
    const requestToken=++recoveryRequestToken;
    state.loading=true;state.error=null;state.caseData=null;state.community=null;
    state.nodePages={};state.edgePages={};state.provenancePages={};
    state.membershipPages={};state.overlayNodePages={};state.overlayEdgePages={};
    state.overlayProvenancePages={};state.overlayMembershipPages={};
    state.loadedNodeCount=0;state.loadedEdgeCount=0;
    state.loadedProvenanceCount=0;state.loadedMembershipCount=0;
    state.loadedOverlayNodeCount=0;state.loadedOverlayEdgeCount=0;
    state.loadedOverlayProvenanceCount=0;state.loadedOverlayMembershipCount=0;
    state.nodePage=0;state.edgePage=0;state.provenancePage=0;
    state.membershipPage=0;state.overlayNodePage=0;state.overlayEdgePage=0;
    state.overlayProvenancePage=0;state.overlayMembershipPage=0;renderV2();
    try{
      const caseRecord=view.caseIndex[state.caseId];
      const caseRef=caseRecord.ref||caseRecord;
      const caseData=await recoveryFetchJson(recoverySidecarUrl(view,caseRef.path),caseRef.sha256);
      if(disposed||requestToken!==recoveryRequestToken)return;
      if(!recoveryIsRecord(caseData)||!recoveryIsRecord(caseData.case)
          ||caseData.case.case_id!==state.caseId||caseData.cohort!==state.cohort
          ||caseData.cohort!==caseRecord.cohort
          ||caseData.community_key!==caseRecord.community_key
          ||caseData.case.community_key!==caseRecord.community_key
          ||(caseData.overlay_evidence!==null&&caseData.overlay_evidence!==undefined
            &&!recoveryValidateChunkOwner(caseData.overlay_evidence))){
        throw new Error('Case sidecar identity or chunk contract is invalid');
      }
      const communityRef=view.communityIndex[caseData.community_key];
      const community=await recoveryFetchJson(
        recoverySidecarUrl(view,communityRef.path),communityRef.sha256);
      if(disposed||requestToken!==recoveryRequestToken)return;
      if(!recoveryValidateChunkOwner(community)
          ||community.community_key!==caseData.community_key){
        throw new Error('Community sidecar identity or chunk contract is invalid');
      }
      state.caseData=caseData;state.community=community;
      renderV2();
      await loadRecoveryChunkPage('node',0,requestToken);
      await loadRecoveryChunkPage('edge',0,requestToken);
      await loadRecoveryChunkPage('provenance',0,requestToken);
      await loadRecoveryChunkPage('membership',0,requestToken);
      if(caseData.overlay_evidence){
        await loadRecoveryChunkPage('overlay-node',0,requestToken);
        await loadRecoveryChunkPage('overlay-edge',0,requestToken);
        await loadRecoveryChunkPage('overlay-provenance',0,requestToken);
        await loadRecoveryChunkPage('overlay-membership',0,requestToken);
      }
    }catch(error){if(requestToken===recoveryRequestToken)state.error=error;}
    if(requestToken===recoveryRequestToken){
      state.loading=false;if(!disposed)renderV2();
    }
  }
  async function loadRecoveryChunkPage(kind,index,requestToken=recoveryRequestToken){
    if(!state.community||requestToken!==recoveryRequestToken)return;
    const overlay=kind.startsWith('overlay-');
    const normalized=overlay?kind.slice(8):kind;
    const owner=overlay?state.caseData&&state.caseData.overlay_evidence:state.community;
    const config=(overlay?{
      node:['node_chunks',state.overlayNodePages,'nodes'],
      edge:['edge_chunks',state.overlayEdgePages,'edges'],
      provenance:['provenance_chunks',state.overlayProvenancePages,'observations'],
      membership:['provenance_expansion_membership_chunks',
        state.overlayMembershipPages,'memberships']
    }:{
      node:['node_chunks',state.nodePages,'nodes'],
      edge:['edge_chunks',state.edgePages,'edges'],
      provenance:['provenance_chunks',state.provenancePages,'observations'],
      membership:['provenance_expansion_membership_chunks',state.membershipPages,
        'memberships']
    })[normalized];
    if(!config)return;
    const refs=owner&&owner[config[0]];
    const cache=config[1];
    if(!Array.isArray(refs)||!refs[index]||cache[index])return;
    const ref=refs[index];
    const payload=await recoveryFetchJson(recoverySidecarUrl(view,ref.path),ref.sha256);
    if(disposed||requestToken!==recoveryRequestToken)return;
    const rows=recoveryValidatedChunkRows(payload,ref,config[2]);
    if(rows===null)throw new Error('Chunk offset or count contract is invalid');
    let resolvedRows=rows;
    if(!overlay&&['node','edge','provenance'].includes(normalized)){
      resolvedRows=await recoveryResolveCatalogRows(view,rows,
        normalized==='node'?'nodes':normalized==='edge'?'edges':'provenance');
      if(disposed||requestToken!==recoveryRequestToken)return;
    }
    if(!overlay&&recoveryIsRecord(owner.day_view)
        &&(normalized==='node'||normalized==='edge')){
      resolvedRows=await recoveryApplyDayView(
        view,owner,normalized,index,resolvedRows);
      if(disposed||requestToken!==recoveryRequestToken)return;
    }
    cache[index]=resolvedRows;
    state.loadedNodeCount=Object.values(state.nodePages).reduce((sum,rows)=>sum+rows.length,0);
    state.loadedEdgeCount=Object.values(state.edgePages).reduce((sum,rows)=>sum+rows.length,0);
    state.loadedProvenanceCount=Object.values(state.provenancePages).reduce((sum,rows)=>sum+rows.length,0);
    state.loadedMembershipCount=Object.values(state.membershipPages)
      .reduce((sum,rows)=>sum+rows.length,0);
    state.loadedOverlayNodeCount=Object.values(state.overlayNodePages)
      .reduce((sum,rows)=>sum+rows.length,0);
    state.loadedOverlayEdgeCount=Object.values(state.overlayEdgePages)
      .reduce((sum,rows)=>sum+rows.length,0);
    state.loadedOverlayProvenanceCount=Object.values(state.overlayProvenancePages)
      .reduce((sum,rows)=>sum+rows.length,0);
    state.loadedOverlayMembershipCount=Object.values(state.overlayMembershipPages)
      .reduce((sum,rows)=>sum+rows.length,0);
    if(!disposed)renderV2();
  }
  async function onV2Click(event){
    const target=event.target.closest&&event.target.closest('[data-v2-cohort],[data-v2-case],[data-v2-page]');
    if(!target||!root.contains(target))return;
    if(target.dataset.v2Page){
      const direction=target.dataset.v2Page.endsWith('next')?1:-1;
      if(target.dataset.v2Page.startsWith('overlay-node')){
        state.overlayNodePage+=direction;
        await loadRecoveryChunkPage('overlay-node',state.overlayNodePage);
      }else if(target.dataset.v2Page.startsWith('overlay-edge')){
        state.overlayEdgePage+=direction;
        await loadRecoveryChunkPage('overlay-edge',state.overlayEdgePage);
      }else if(target.dataset.v2Page.startsWith('overlay-provenance')){
        state.overlayProvenancePage+=direction;
        await loadRecoveryChunkPage('overlay-provenance',state.overlayProvenancePage);
      }else if(target.dataset.v2Page.startsWith('overlay-membership')){
        state.overlayMembershipPage+=direction;
        await loadRecoveryChunkPage('overlay-membership',state.overlayMembershipPage);
      }else if(target.dataset.v2Page.startsWith('node')){
        state.nodePage+=direction;await loadRecoveryChunkPage('node',state.nodePage);
      }else if(target.dataset.v2Page.startsWith('edge')){
        state.edgePage+=direction;await loadRecoveryChunkPage('edge',state.edgePage);
      }else if(target.dataset.v2Page.startsWith('provenance')){
        state.provenancePage+=direction;
        await loadRecoveryChunkPage('provenance',state.provenancePage);
      }else{
        state.membershipPage+=direction;
        await loadRecoveryChunkPage('membership',state.membershipPage);
      }
      renderV2();return;
    }else if(target.dataset.v2Cohort){state.cohort=target.dataset.v2Cohort;
      state.caseId=(view.cohorts[state.cohort][0]||{}).case_id||null;}
    else state.caseId=target.dataset.v2Case;
    if(state.caseId)loadSelected();else renderV2();
  }
  function onV2Input(event){if(event.target.dataset.v2Input==='node'){state.nodeQuery=event.target.value;renderV2();}}
  function onV2Change(event){if(event.target.dataset.v2Change==='relation'){state.relation=event.target.value;state.edgePage=0;renderV2();}}
  root.addEventListener('click',onV2Click);root.addEventListener('input',onV2Input);root.addEventListener('change',onV2Change);
  renderV2();if(state.caseId)loadSelected();
  return function(){disposed=true;recoveryRequestToken++;
    root.removeEventListener('click',onV2Click);root.removeEventListener('input',onV2Input);
    root.removeEventListener('change',onV2Change);};
}

function mountRecoveryExplorerV3(root,artifact,tools){
  const doc=root.ownerDocument;
  const view=buildRecoverySchema3ViewModel(artifact);
  const fmt=recoveryIsRecord(tools)&&typeof tools.fmt==='function'
    ?tools.fmt:value=>Number(value||0).toLocaleString();
  const firstPublishedCaseId=view.available
    ?Object.keys(view.detailIndex||{})[0]||null:null;
  const state={filter:'gnn_explanation',
    caseId:firstPublishedCaseId,caseData:null,community:null,
    nodeRows:null,edgeRows:null,overlayNodeRows:null,overlayEdgeRows:null,
    loading:false,error:null,
    mode:'flow',stageId:'first_hop',selectedFactorId:null,query:'',
    scale:1,offsetX:0,offsetY:0,labelDensity:'auto',
    nodeTablePage:0,edgeTablePage:0};
  let requestToken=0;let disposed=false;
  let canvasCleanup=function(){};let pendingCanvas=null;

  function restoreV3Focus(attribute,datasetKey,value){
    for(const control of root.querySelectorAll('['+attribute+']')){
      if(control.dataset&&control.dataset[datasetKey]===String(value)){
        control.focus();return true;
      }
    }
    return false;
  }
  function visibleRows(){return filterRecoverySchema3Cases(view,state.filter);}
  function currentRecord(){
    return visibleRows().find(item=>item.caseId===state.caseId)||null;
  }
  function stageIdsFor(kind){
    return kind==='community_control'
      ?RECOVERY_STRUCTURAL_STAGES
      :['first_hop','second_hop','component_pool','rank_fusion'];
  }
  function activeStageId(kind){
    const allowed=stageIdsFor(kind);
    return allowed.includes(state.stageId)?state.stageId:'first_hop';
  }
  function addText(parent,tag,className,text){
    parent.appendChild(recoveryElement(doc,tag,className,text));
  }
  function renderHeader(fragment){
    const header=recoveryElement(doc,'header','v9-recovery-header');
    addText(header,'div','v9-recovery-eyebrow','Balanced recovery evidence');
    addText(header,'h3','v9-recovery-title','Why Hybrid recovered more cases');
    addText(header,'p','v9-recovery-intro',
      'Retrospective seed-0 evaluation cohorts with selected technical detail and structural controls.');
    addText(header,'div','v9-recovery-scope',
      'Single-seed observability · GraphSAGE seed 0 · Hybrid score is percentile fusion, not probability.');
    fragment.appendChild(header);
  }
  function renderSummary(fragment){
    if(!view.available)return;
    const grid=recoveryElement(doc,'div','v9-recovery-summary');
    grid.setAttribute('aria-label','Schema-3 recovery overlap summary');
    for(const [key,label] of [
      ['baseline_recovered','Baseline recovered'],
      ['recovered_by_both','Recovered by both'],
      ['hybrid_only_recovered','Hybrid-only recovered'],
      ['baseline_only_recovered','Baseline-only recovered'],
      ['hybrid_total','Hybrid total'],['net_gain','Net gain']]){
      const card=recoveryElement(doc,'article','v9-recovery-stat');
      addText(card,'b','',fmt(view.summary[key]));addText(card,'span','',label);
      grid.appendChild(card);
    }
    fragment.appendChild(grid);
    const coverage=recoveryElement(doc,'div','v9-recovery-coverage');
    addText(coverage,'span','',
      'Hybrid technical detail '+fmt(view.coverage.hybrid_explained)+' / '
        +fmt(view.coverage.hybrid_requested));
    addText(coverage,'span','',
      'Baseline community context '+fmt(view.coverage.baseline_community)+' / '
        +fmt(view.coverage.baseline_requested));
    if(view.coverage.hybrid_structural_fallback){
      addText(coverage,'span','',
        'Hybrid structural fallback '+fmt(view.coverage.hybrid_structural_fallback));
    }
    fragment.appendChild(coverage);
    if(view.coverage.shortfall){
      addText(fragment,'div','v9-recovery-warning',
        'Partial coverage: '+fmt(view.coverage.shortfall)
          +' of the requested detail cases have no published evidence. Reasons: '
          +(view.coverage.shortfall_reasons.join(', ')||'not recorded')+'.');
    }
  }
  function renderFilters(fragment){
    const status=recoveryElement(doc,'div','v9-recovery-status',
      'Showing GNN explanations only');
    status.setAttribute('role','status');
    status.setAttribute('aria-label','Showing GNN explanations only');
    fragment.appendChild(status);
  }
  function renderRecordStatus(detail,record){
    const copy={
      not_selected:'This case was retained in the cohort summary but was not selected for detail.',
      selected:'Selected detail is not available in the published bundle.',
      unavailable:'Detail is unavailable; no evidence is inferred.',
      failed:'Detail generation failed; no replacement case was selected.'
    }[record.detailStatus||'not_selected'];
    if(copy)addText(detail,'div','v9-recovery-status',copy);
    if(record.failureReason)addText(detail,'p','v9-recovery-intro',
      'Recorded reason: '+String(record.failureReason));
    if(record.explanationUnavailableReason)addText(detail,'p','v9-recovery-intro',
      'GNNExplainer was not run for this case: '
        +String(record.explanationUnavailableReason)
        +'. The exact two-hop input exceeded the explainer limits, so structural community context is published instead.');
  }
  function renderRanks(detail,record){
    const panel=recoveryElement(doc,'section','v9-recovery-v2-panel');
    addText(panel,'h5','',
      record.detailKind==='gnn_explanation'
        ?'Hybrid percentile-fusion score and ranks':'Recorded ranks and structural context');
    const values=[['Baseline rank',record.baseline_rank],
      ['Seed-0 GNN rank',record.seed0_gnn_rank],
      ['Seed-0 Hybrid rank',record.seed0_hybrid_rank]];
    for(const [label,value] of values)addText(panel,'div','',label+': '+fmt(value));
    if(typeof record.baseline_raw==='number')addText(panel,'div','',
      'Baseline score: '+String(record.baseline_raw));
    if(typeof record.baseline_percentile==='number')addText(panel,'div','',
      'Baseline percentile: '+String(record.baseline_percentile));
    if(typeof record.seed0_gnn_percentile==='number')addText(panel,'div','',
      'Seed-0 GNN percentile: '+String(record.seed0_gnn_percentile));
    if(typeof record.seed0_gnn_probability==='number')addText(panel,'div','',
      'Seed-0 GNN probability: '+String(record.seed0_gnn_probability));
    if(typeof record.seed0_hybrid_score==='number')addText(panel,'div','',
      'Hybrid percentile-fusion score: '+String(record.seed0_hybrid_score)
        +' (percentile fusion, not probability)');
    detail.appendChild(panel);
  }
  function renderEvidenceBoundary(detail,boundary){
    if(!recoveryIsRecord(boundary)
        ||!recoveryNonBlankString(boundary.snapshot)
        ||!recoveryNonBlankString(boundary.edge_rule)
        ||!recoveryNonBlankString(boundary.caught_rule)){
      addText(detail,'div','v9-recovery-empty',
        'Strict as-of evidence boundary unavailable. Evidence details are not rendered.');
      return false;
    }
    addText(detail,'div','v9-recovery-status',
      'Strict as-of evidence boundary: snapshot '+boundary.snapshot
        +'. Edges: '+boundary.edge_rule+'. Caught labels: '+boundary.caught_rule+'.');
    return true;
  }
  function renderNarrative(column,explanation){
    const panel=recoveryElement(doc,'section','v9-recovery-narrative');
    addText(panel,'h5','','Grounded narrative');
    const narrative=validateRecoveryNarrative(explanation.llm_narrative);
    if(!narrative.visible){
      addText(panel,'p','',
        'Validated narrative unavailable. Measured factors remain authoritative.');
    }else{
      addText(panel,'p','',narrative.source==='llm'
        ?'Validated local Gemma: '+narrative.model
        :'Deterministic evidence summary. Local Gemma output was unavailable or rejected.');
      addText(panel,'p','',narrative.summary);
      recoveryAppendSources(doc,panel,narrative.summarySourceRefs);
      for(const claim of narrative.claims){
        addText(panel,'p','',claim.text);
        recoveryAppendSources(doc,panel,claim.source_refs);
      }
    }
    column.appendChild(panel);
  }
  function renderFactors(column,explanation){
    const panel=recoveryElement(doc,'section','v9-recovery-panel');
    const head=recoveryElement(doc,'div','v9-recovery-panel-head');
    addText(head,'h5','','Salient counterfactual factors');
    addText(head,'p','',
      'Signed effect is ablated rank minus original rank. Positive values mean removal worsened rank.');
    panel.appendChild(head);
    const factors=Array.isArray(explanation.factors)
      ?explanation.factors.filter(recoveryValidFactor).slice():[];
    factors.sort((left,right)=>
      Number(right.stability==='stable')-Number(left.stability==='stable')
      ||Math.abs(right.counterfactual.ablated_hybrid_rank-right.counterfactual.original_hybrid_rank)
        -Math.abs(left.counterfactual.ablated_hybrid_rank-left.counterfactual.original_hybrid_rank)
      ||recoveryCompareId(left.factor_id,right.factor_id));
    if(!factors.some(factor=>factor.stability==='stable')){
      addText(panel,'div','v9-recovery-status',
        'No stable factor found; inspect measured effects below.');
    }
    if(!factors.length){
      addText(panel,'div','v9-recovery-status',
        'No measured factors are available for this explanation.');
    }else{
      const list=recoveryElement(doc,'div','v9-recovery-factor-list');
      for(const factor of factors){
        const button=recoveryElement(doc,'button','v9-recovery-factor');
        button.type='button';button.dataset.v3Factor=factor.factor_id;
        button.setAttribute('aria-pressed',
          String(state.selectedFactorId===factor.factor_id));
        button.setAttribute('aria-label',
          'Show measured effect for '+recoveryVisibleText(factor.label));
        addText(button,'strong','',factor.label+' / '+factor.stability);
        const effect=factor.counterfactual.ablated_hybrid_rank
          -factor.counterfactual.original_hybrid_rank;
        addText(button,'span','',
          recoverySigned(effect)+' ranks / Ablated minus original');
        list.appendChild(button);
      }
      panel.appendChild(list);
      addText(panel,'p','v9-recovery-canvas-note',
        'Per-factor provenance is published as separate attribution overlay evidence and is not drawn on the community graph in this view.');
    }
    column.appendChild(panel);
  }
  function renderStabilityAndFaithfulness(column,explanation){
    const panel=recoveryElement(doc,'section','v9-recovery-panel');
    const head=recoveryElement(doc,'div','v9-recovery-panel-head');
    addText(head,'h5','','Restart stability and removal faithfulness');
    panel.appendChild(head);
    const stability=explanation.stability;
    if(recoveryIsRecord(stability)
        &&recoverySafeInteger(stability.stable_factor_count,false)){
      addText(panel,'div','',
        'Stable factors across deterministic restarts: '
          +fmt(stability.stable_factor_count));
      if(recoveryNonBlankString(stability.signed_effect_source)){
        addText(panel,'div','',
          'Signed effect source: '+stability.signed_effect_source);
      }
    }else{
      addText(panel,'div','v9-recovery-status',
        'Restart stability is unavailable in this artifact.');
    }
    const faithfulness=explanation.faithfulness;
    const points=recoveryIsRecord(faithfulness)?faithfulness.points:null;
    if(!recoveryIsRecord(faithfulness)||!Array.isArray(points)||!points.length
        ||!recoveryFiniteUnit(faithfulness.original_probability)){
      addText(panel,'div','v9-recovery-status',
        'Edge-removal faithfulness is unavailable in this artifact.');
      column.appendChild(panel);return;
    }
    addText(panel,'p','',
      'Removing the highest-attribution edges is compared against a matched random control. A larger top-edge drop than its matched control is evidence the attribution tracked the score.');
    addText(panel,'div','',
      'Seed-0 probability before removal: '
        +String(faithfulness.original_probability));
    const table=recoveryElement(doc,'table','v9-recovery-table');
    table.setAttribute('aria-label','Edge removal faithfulness by removed fraction');
    const header=recoveryElement(doc,'tr');
    for(const label of ['Removed fraction','Top-edge drop','Matched random drop',
      'Unmatched controls']){
      header.appendChild(recoveryElement(doc,'th','',label));
    }
    table.appendChild(header);
    for(const point of points){
      if(!recoveryIsRecord(point))continue;
      const row=recoveryElement(doc,'tr');
      const matched=typeof point.matched_random_probability_drop==='number'
        ?String(point.matched_random_probability_drop)
        :'not measured';
      for(const value of [String(point.fraction),
        String(point.top_edge_probability_drop),matched,
        String(point.unmatched_control_count)]){
        row.appendChild(recoveryElement(doc,'td','',value));
      }
      table.appendChild(row);
    }
    panel.appendChild(table);
    column.appendChild(panel);
  }
  function graphButton(label,action,value,pressed,ariaLabel){
    const button=recoveryElement(doc,'button','v9-recovery-button',label);
    button.type='button';button.dataset[action]=value;
    if(pressed!==null)button.setAttribute('aria-pressed',String(pressed));
    button.setAttribute('aria-label',ariaLabel||label);
    return button;
  }
  function renderGraphTable(panel,commands,record){
    const wrap=recoveryElement(doc,'div','v9-recovery-table-wrap');
    addText(wrap,'h6','','Community data table');
    addText(wrap,'p','v9-recovery-canvas-note',
      'Non-canvas equivalent of the graph above. Emphasis matches the selected stage.');
    const tableNodes=Array.isArray(commands.tableNodes)
      ?commands.tableNodes:commands.nodes;
    const tableEdges=Array.isArray(commands.tableEdges)
      ?commands.tableEdges:commands.edges;
    const nodePages=Math.max(1,Math.ceil(tableNodes.length/25));
    const edgePages=Math.max(1,Math.ceil(tableEdges.length/25));
    const nodePage=Math.min(Math.max(0,state.nodeTablePage),nodePages-1);
    const edgePage=Math.min(Math.max(0,state.edgeTablePage),edgePages-1);
    const nodeTable=recoveryElement(doc,'table','v9-recovery-table');
    nodeTable.setAttribute('aria-label',
      'Community members for '+recoveryVisibleText(record.personId));
    const nodeHead=recoveryElement(doc,'tr');
    for(const label of ['Member','Focal','Pooled member','Caught before snapshot',
      'Evidence weight','Evidence rank']){
      nodeHead.appendChild(recoveryElement(doc,'th','',label));
    }
    nodeTable.appendChild(nodeHead);
    for(const node of tableNodes.slice(nodePage*25,nodePage*25+25)){
      const row=recoveryElement(doc,'tr');
      const nodeId=node.id===undefined?node.node_id:node.id;
      const weight=typeof node.importance==='number'
        ?node.importance.toFixed(3):'none';
      const rank=Number.isSafeInteger(node.rank)?String(node.rank):'none';
      for(const value of [nodeId,node.target?'yes':'no',
        node.pooledMember?'yes':'no',node.caughtBeforeSnapshot?'yes':'no',
        weight,rank]){
        row.appendChild(recoveryElement(doc,'td','',String(value)));
      }
      nodeTable.appendChild(row);
    }
    wrap.appendChild(nodeTable);
    const nodeNav=recoveryElement(doc,'div','v9-recovery-pager');
    nodeNav.appendChild(graphButton('Previous members','v3Page','node-prev',null,
      'Previous page of community members'));
    addText(nodeNav,'span','','Members page '+(nodePage+1)+' / '+nodePages);
    nodeNav.appendChild(graphButton('Next members','v3Page','node-next',null,
      'Next page of community members'));
    wrap.appendChild(nodeNav);
    const edgeTable=recoveryElement(doc,'table','v9-recovery-table');
    edgeTable.setAttribute('aria-label',
      'Community relationships for '+recoveryVisibleText(record.personId));
    const edgeHead=recoveryElement(doc,'tr');
    for(const label of ['Relationship','Relation','From','To','Emphasized',
      'Evidence weight','Evidence rank']){
      edgeHead.appendChild(recoveryElement(doc,'th','',label));
    }
    edgeTable.appendChild(edgeHead);
    for(const edge of tableEdges.slice(edgePage*25,edgePage*25+25)){
      const row=recoveryElement(doc,'tr');
      const edgeId=edge.id===undefined?edge.edge_id:edge.id;
      const weight=typeof edge.importance==='number'
        ?edge.importance.toFixed(3):'none';
      const rank=Number.isSafeInteger(edge.rank)?String(edge.rank):'none';
      for(const value of [edgeId,edge.relation,edge.u,edge.v,
        edge.emphasized?'yes':'no',weight,rank]){
        row.appendChild(recoveryElement(doc,'td','',String(value)));
      }
      edgeTable.appendChild(row);
    }
    wrap.appendChild(edgeTable);
    const edgeNav=recoveryElement(doc,'div','v9-recovery-pager');
    edgeNav.appendChild(graphButton('Previous relationships','v3Page','edge-prev',
      null,'Previous page of community relationships'));
    addText(edgeNav,'span','','Relationships page '+(edgePage+1)+' / '+edgePages);
    edgeNav.appendChild(graphButton('Next relationships','v3Page','edge-next',null,
      'Next page of community relationships'));
    wrap.appendChild(edgeNav);
    panel.appendChild(wrap);
  }
  function renderGraph(column,detailView,record){
    const control=detailView.kind==='community_control';
    const stageId=activeStageId(detailView.kind);
    const panel=recoveryElement(doc,'section','v9-recovery-panel');
    const head=recoveryElement(doc,'div','v9-recovery-panel-head');
    addText(head,'h5','','As-of community context + explanation evidence');
    addText(head,'p','',control
      ?'Muted context remains visible. This control has no explanation evidence or attribution mask.'
      :'Muted context remains visible. Explanation evidence width and brightness follow the unsigned explainer median. This is not a causal claim.');
    panel.appendChild(head);
    const toolbar=recoveryElement(doc,'div','v9-recovery-toolbar');
    toolbar.setAttribute('role','toolbar');
    toolbar.setAttribute('aria-label','Community graph controls');
    const modes=recoveryElement(doc,'div','v9-recovery-toolgroup');
    modes.appendChild(graphButton('All','v3Mode','all',state.mode==='all',
      'Show all relationships'));
    modes.appendChild(graphButton('Flow','v3Mode','flow',state.mode==='flow',
      'Show influence flow emphasis'));
    toolbar.appendChild(modes);
    const stages=recoveryElement(doc,'div','v9-recovery-toolgroup');
    const stageLabels={first_hop:'First hop',second_hop:'Second hop',
      component_pool:'Component pool',rank_fusion:'Rank fusion'};
    for(const value of stageIdsFor(detailView.kind)){
      stages.appendChild(graphButton(stageLabels[value],'v3Stage',value,
        stageId===value,'Show '+stageLabels[value].toLowerCase()+' stage'));
    }
    toolbar.appendChild(stages);
    const zoom=recoveryElement(doc,'div','v9-recovery-toolgroup');
    zoom.appendChild(graphButton('+','v3Zoom','in',null,'Zoom in'));
    zoom.appendChild(graphButton('-','v3Zoom','out',null,'Zoom out'));
    zoom.appendChild(graphButton('Reset','v3Zoom','reset',null,'Reset zoom'));
    zoom.appendChild(graphButton('Fit','v3Zoom','fit',null,'Fit to community'));
    toolbar.appendChild(zoom);
    const search=recoveryElement(doc,'input','v9-recovery-search');
    search.type='search';search.value=state.query;search.placeholder='Find node';
    search.dataset.v3Input='search';
    search.setAttribute('aria-label','Search node identifiers');
    toolbar.appendChild(search);
    const density=recoveryElement(doc,'select','v9-recovery-select');
    density.dataset.v3Change='density';
    density.setAttribute('aria-label','Node label density');
    for(const pair of [['auto','Labels: auto'],['all','Labels: all'],
      ['none','Labels: none']]){
      const option=recoveryElement(doc,'option','',pair[1]);
      option.value=pair[0];density.appendChild(option);
    }
    density.value=state.labelDensity;toolbar.appendChild(density);
    panel.appendChild(toolbar);
    const description=recoveryElement(doc,'p','v9-recovery-canvas-note',control
      ?'Relation colors show observable context, not relation-specific GraphSAGE parameters. No attribution mask is drawn for a community control.'
      :'Relation colors show observable context, not relation-specific GraphSAGE parameters. Mask values are unsigned evidence weights, not causal claims.');
    description.id='v9-recovery-v3-canvas-description';
    panel.appendChild(description);
    const options={mode:state.mode,stageId,
      selectedFactorId:null,query:state.query};
    const commands=control
      ?buildStructuralDrawCommands(detailView.control,options)
      :buildCommunityDrawCommands(detailView.explanation,options);
    if(!commands.available){
      addText(panel,'div','v9-recovery-empty',
        'Strict-bound unavailable: complete community unavailable ('
          +commands.reason+'). The complete data table is not rendered because the graph command failed closed.');
      column.appendChild(panel);return;
    }
    const legend=recoveryElement(doc,'div','v9-recovery-legend');
    legend.setAttribute('role','list');
    legend.setAttribute('aria-label','Graph legend');
    function legendItem(label,swatchClass,description){
      const item=recoveryElement(doc,'div','v9-recovery-legend-item');
      item.setAttribute('role','listitem');
      item.setAttribute('aria-label',label+(description?': '+description:''));
      const swatch=recoveryElement(doc,'span','v9-recovery-legend-swatch '+swatchClass);
      swatch.setAttribute('aria-hidden','true');
      item.appendChild(swatch);
      addText(item,'span','',label+(description?' - '+description:''));
      legend.appendChild(item);
    }
    legendItem('Context relations','is-context','muted');
    legendItem('Explanation evidence','is-evidence','width and brightness follow unsigned explainer median');
    legendItem('Target','is-target','selected person');
    legendItem('Caught before snapshot','is-caught','label available before T');
    legendItem('Weight range','is-weight','0.00 to 1.00');
    panel.appendChild(legend);
    if(commands.sampled){
      addText(panel,'div','v9-recovery-sampled',
        'Sampled context: showing '+fmt(commands.nodes.length)+' of '
          +fmt(commands.fullNodeCount)+' nodes and '+fmt(commands.edges.length)
          +' of '+fmt(commands.fullEdgeCount)
          +' relationships for canvas performance; complete tables remain available.');
    }
    if(detailView.canvasAvailable){
      const wrap=recoveryElement(doc,'div','v9-recovery-canvas-wrap');
      const canvas=recoveryElement(doc,'canvas','v9-recovery-canvas');
      canvas.tabIndex=0;canvas.setAttribute('role','img');
      canvas.setAttribute('aria-label',
        (control
          ?'Community context graph for '
            +(record.cohort==='baseline_only'
              ?'baseline control ':'Hybrid structural fallback ')
          :'Community graph for Hybrid case ')
          +recoveryVisibleText(record.personId)+', '+stageLabels[stageId]
          +' stage, '+(state.mode==='all'?'all relationships':'flow emphasis')
          +', '+commands.nodes.length+' members and '+commands.edges.length
          +' relationships.');
      canvas.setAttribute('aria-describedby','v9-recovery-v3-canvas-description');
      canvas.textContent='Interactive community graph. Use the toolbar for keyboard controls.';
      wrap.appendChild(canvas);panel.appendChild(wrap);
      pendingCanvas={canvas,commands};
    }else{
      addText(panel,'div','v9-recovery-status',
        'Strict-bound unavailable: community graph is not drawn: '
          +fmt(detailView.nodeCount)+' members and '
          +fmt(detailView.edgeCount)
          +' relationships exceed the interactive rendering bound. The complete data table below carries the same evidence.');
    }
    renderGraphTable(panel,commands,record);
    column.appendChild(panel);
  }
  function renderSelectedEvidence(detail,record){
    if(state.error){
      addText(detail,'div','v9-recovery-empty',recoveryServerHelp(state.error));
      return;
    }
    if(state.loading){
      addText(detail,'div','v9-recovery-status','Loading selected evidence...');
      return;
    }
    if(record.detailKind===null){
      renderRecordStatus(detail,record);return;
    }
    const communityView=assembleRecoverySchema3Community(
      state.community,state.nodeRows,state.edgeRows);
    const overlayRows=record.detailKind==='gnn_explanation'
      ?mergeRecoverySchema3Overlay(communityView.community,
        state.overlayNodeRows,state.overlayEdgeRows)
      :null;
    const detailView=buildRecoverySchema3Detail(
      record,state.caseData,communityView,overlayRows);
    if(!detailView.available){
      addText(detail,'div','v9-recovery-empty',
        'Selected evidence unavailable. '+detailView.reason+'.');
      renderRecordStatus(detail,record);return;
    }
    if(detailView.kind==='community_control'){
      addText(detail,'div','v9-recovery-status',
        record.cohort==='baseline_only'
          ?'Community context only: GNNExplainer was not run for this baseline control.'
          :'Community context only: GNNExplainer was not run for this Hybrid structural fallback.');
      addText(detail,'p','v9-recovery-intro',
        'No GNN explanation, mask, or attribution is generated for this control.');
    }else{
      addText(detail,'div','v9-recovery-status','Hybrid technical detail');
    }
    if(!renderEvidenceBoundary(detail,detailView.evidenceBoundary)){
      renderRecordStatus(detail,record);return;
    }
    const evidence=recoveryElement(doc,'div','v9-recovery-evidence-grid');
    const left=recoveryElement(doc,'div');
    const right=recoveryElement(doc,'div');
    if(detailView.kind==='gnn_explanation'){
      renderFactors(left,detailView.explanation);
      renderStabilityAndFaithfulness(left,detailView.explanation);
      renderNarrative(left,detailView.explanation);
      left.appendChild(renderHighestAttributionPanel(doc,detailView.explanation));
    }else{
      const note=recoveryElement(doc,'section','v9-recovery-panel');
      addText(note,'h5','','Structural evidence only');
      addText(note,'p','',
        'Community membership is observable context, not an attribution claim. Attribution, counterfactual factor, stability, and faithfulness panels are suppressed for a control.');
      left.appendChild(note);
    }
    renderGraph(right,detailView,record);
    evidence.appendChild(left);evidence.appendChild(right);
    detail.appendChild(evidence);
    renderRecordStatus(detail,record);
  }
  function render(){
    canvasCleanup();canvasCleanup=function(){};pendingCanvas=null;
    const fragment=doc.createDocumentFragment();renderHeader(fragment);
    if(!view.available){
      addText(fragment,'div','v9-recovery-empty',
        'Case evidence unavailable. '+view.reason+'.');
      root.replaceChildren(fragment);return;
    }
    renderSummary(fragment);renderFilters(fragment);
    const grid=recoveryElement(doc,'div','v9-recovery-v2-grid');
    const list=recoveryElement(doc,'aside','v9-recovery-v2-list');
    list.setAttribute('aria-label','Recovery cases');
    const rows=visibleRows();
    if(!rows.length){
      addText(list,'div','v9-recovery-empty','No cases match the current filter.');
    }
    for(const record of rows){
      const button=recoveryElement(doc,'button','v9-recovery-case');
      button.type='button';button.dataset.v3Case=record.caseId;
      button.setAttribute('aria-current',String(record.caseId===state.caseId));
      button.setAttribute('aria-label','Inspect recovery case '+record.personId);
      addText(button,'strong','',record.personId);
      addText(button,'div','v9-recovery-case-meta',
        record.cohort+' · '+(record.detailStatus||'not_selected')
          +' · B '+fmt(record.baseline_rank)
          +' / H '+fmt(record.seed0_hybrid_rank));
      list.appendChild(button);
    }
    grid.appendChild(list);
    const detail=recoveryElement(doc,'div','v9-recovery-v2-detail');
    const record=currentRecord();
    if(!record){
      addText(detail,'div','v9-recovery-empty',
        'Select a case to inspect its published evidence.');
    }else{
      const header=recoveryElement(doc,'header','v9-recovery-case-header');
      addText(header,'h4','','Case '+record.personId);
      addText(header,'p','','Event '+record.event_id+' / scoring day '
        +record.scoring_day+' / selection: '+record.selectionReason+'.');
      detail.appendChild(header);
      renderRanks(detail,record);
      renderSelectedEvidence(detail,record);
    }
    grid.appendChild(detail);fragment.appendChild(grid);
    root.replaceChildren(fragment);
    if(pendingCanvas){
      canvasCleanup=bindRecoveryCanvas(
        pendingCanvas.canvas,pendingCanvas.commands,state);
    }
  }
  async function loadSelected(){
    const token=++requestToken;
    const record=currentRecord();
    state.caseData=null;state.community=null;state.nodeRows=null;
    state.edgeRows=null;state.overlayNodeRows=null;state.overlayEdgeRows=null;
    state.error=null;state.loading=false;
    state.selectedFactorId=null;state.nodeTablePage=0;state.edgeTablePage=0;
    if(!record||record.detailKind===null){render();return;}
    const caseRef=view.detailIndex[state.caseId]||view.communityIndex[state.caseId];
    if(!caseRef){
      state.error=new Error('Published sidecar reference is missing for this case');
      render();return;
    }
    state.loading=true;render();
    try{
      const payload=await recoveryFetchJson(
        recoverySidecarUrl(view,caseRef.path),caseRef.sha256);
      if(disposed||token!==requestToken)return;
      if(!recoveryIsRecord(payload)
          ||!['1.0','3.0'].includes(payload.schema_version)
          ||!recoveryIsRecord(payload.case)||payload.case.case_id!==state.caseId
          ||payload.cohort!==record.cohort
          ||payload.community_key!==record.community_key){
        throw new Error('Schema-3 case sidecar identity is invalid');
      }
      if(record.cohort==='hybrid_only'
          &&record.detailKind==='gnn_explanation'
          &&!recoveryValidateChunkOwner(payload.overlay_evidence)){
        throw new Error('Schema-3 explanation overlay owner is invalid');
      }
      const communityRef=view.communitySidecarIndex[payload.community_key];
      if(!recoverySchema3Reference(communityRef))
        throw new Error('Schema-3 community sidecar reference is missing');
      const community=await recoveryFetchJson(
        recoverySidecarUrl(view,communityRef.path),communityRef.sha256);
      if(disposed||token!==requestToken)return;
      if(!recoverySchema3Community(community,payload.community_key))
        throw new Error('Schema-3 community sidecar identity is invalid');
      const detail=payload.detail||(
        payload.explanation
          ?{...payload.case,explanation:payload.explanation}
          :null
      );
      state.caseData={...payload,detail};state.community=community;
      render();
      const nodeRows=await loadCommunityRows(community,'node',token);
      if(disposed||token!==requestToken)return;
      const edgeRows=await loadCommunityRows(community,'edge',token);
      if(disposed||token!==requestToken)return;
      state.nodeRows=nodeRows;state.edgeRows=edgeRows;
      if(record.cohort==='hybrid_only'
          &&record.detailKind==='gnn_explanation'){
        const overlayNodeRows=await loadRecoverySchema3OverlayRows(
          view,payload.overlay_evidence,'node',token);
        if(disposed||token!==requestToken)return;
        const overlayEdgeRows=await loadRecoverySchema3OverlayRows(
          view,payload.overlay_evidence,'edge',token);
        if(disposed||token!==requestToken)return;
        const communityView=assembleRecoverySchema3Community(
          community,nodeRows,edgeRows);
        if(!communityView.available){
          throw new Error('Schema-3 community rows are invalid');
        }
        const overlayRows=mergeRecoverySchema3Overlay(
          communityView.community,overlayNodeRows,overlayEdgeRows);
        if(!overlayRows.available){
          throw new Error('Schema-3 overlay presentation is invalid: '
            +overlayRows.reason);
        }
        state.overlayNodeRows=overlayNodeRows;
        state.overlayEdgeRows=overlayEdgeRows;
      }
    }catch(error){if(token===requestToken)state.error=error;}
    if(token===requestToken){state.loading=false;if(!disposed)render();}
  }
  async function loadCommunityRows(community,normalized,token){
    const refs=community[normalized==='node'?'node_chunks':'edge_chunks'];
    if(!Array.isArray(refs))throw new Error('Community chunk index is missing');
    const collected=[];
    for(let index=0;index<refs.length;index+=1){
      const ref=refs[index];
      const payload=await recoveryFetchJson(
        recoverySidecarUrl(view,ref.path),ref.sha256);
      if(disposed||token!==requestToken)return collected;
      const rows=recoveryValidatedChunkRows(
        payload,ref,normalized==='node'?'nodes':'edges');
      if(rows===null)throw new Error('Chunk offset or count contract is invalid');
      let resolved=await recoveryResolveCatalogRows(view,rows,
        normalized==='node'?'nodes':'edges');
      if(disposed||token!==requestToken)return collected;
      if(recoveryIsRecord(community.day_view)){
        resolved=await recoveryApplyDayView(
          view,community,normalized,index,resolved);
        if(disposed||token!==requestToken)return collected;
      }
      collected.push(...resolved);
    }
    return collected;
  }
  async function loadRecoverySchema3OverlayRows(view,owner,normalized,token){
    if(!recoveryValidateChunkOwner(owner)){
      throw new Error('Overlay chunk owner is invalid');
    }
    if(normalized!=='node'&&normalized!=='edge'){
      throw new Error('Overlay row kind is invalid');
    }
    const refs=owner[normalized==='node'?'node_chunks':'edge_chunks'];
    if(!Array.isArray(refs))throw new Error('Overlay chunk index is missing');
    const collected=[];
    for(const ref of refs){
      const payload=await recoveryFetchJson(
        recoverySidecarUrl(view,ref.path),ref.sha256);
      if(disposed||token!==requestToken)return collected;
      const rows=recoveryValidatedChunkRows(
        payload,ref,normalized==='node'?'nodes':'edges');
      if(rows===null)throw new Error('Chunk offset or count contract is invalid');
      collected.push(...rows);
    }
    return collected;
  }
  function onV3Click(event){
    const target=event.target.closest&&event.target.closest(
      '[data-v3-filter],[data-v3-case],[data-v3-mode],[data-v3-stage],'
        +'[data-v3-zoom],[data-v3-factor],[data-v3-page]');
    if(!target||!root.contains(target))return;
    const data=target.dataset;
    if(data.v3Filter){
      state.filter=data.v3Filter;
      const rows=filterRecoverySchema3Cases(view,state.filter);
      if(!rows.some(item=>item.caseId===state.caseId)){
        state.caseId=(rows[0]||{}).caseId||null;
        loadSelected();return;
      }
      render();
      restoreV3Focus('data-v3-filter','v3Filter',data.v3Filter);return;
    }
    if(data.v3Case){
      if(data.v3Case===state.caseId){render();return;}
      state.caseId=data.v3Case;loadSelected();return;
    }
    if(data.v3Mode){
      state.mode=data.v3Mode;render();
      restoreV3Focus('data-v3-mode','v3Mode',data.v3Mode);return;
    }
    if(data.v3Stage){
      state.stageId=data.v3Stage;render();
      restoreV3Focus('data-v3-stage','v3Stage',data.v3Stage);return;
    }
    if(data.v3Factor){
      state.selectedFactorId=state.selectedFactorId===data.v3Factor
        ?null:data.v3Factor;
      render();return;
    }
    if(data.v3Page){
      const direction=data.v3Page.endsWith('next')?1:-1;
      if(data.v3Page.startsWith('node')){
        state.nodeTablePage=Math.max(0,state.nodeTablePage+direction);
      }else{
        state.edgeTablePage=Math.max(0,state.edgeTablePage+direction);
      }
      render();
      restoreV3Focus('data-v3-page','v3Page',data.v3Page);return;
    }
    if(data.v3Zoom==='in')state.scale=Math.min(6,state.scale*1.25);
    else if(data.v3Zoom==='out')state.scale=Math.max(.25,state.scale/1.25);
    else{state.scale=1;state.offsetX=0;state.offsetY=0;}
    render();
    restoreV3Focus('data-v3-zoom','v3Zoom',data.v3Zoom);
  }
  function onV3Input(event){
    if(event.target.dataset.v3Input==='search'){
      state.query=event.target.value;render();
      if(restoreV3Focus('data-v3-input','v3Input','search')){
        const control=root.querySelector('[data-v3-input="search"]');
        if(control&&typeof control.setSelectionRange==='function'){
          control.setSelectionRange(control.value.length,control.value.length);
        }
      }
    }
  }
  function onV3Change(event){
    if(event.target.dataset.v3Change==='density'){
      state.labelDensity=event.target.value;render();
      restoreV3Focus('data-v3-change','v3Change','density');
    }
  }
  root.addEventListener('click',onV3Click);root.addEventListener('input',onV3Input);
  root.addEventListener('change',onV3Change);
  root.classList.add('v9-recovery','v9-recovery-v3');render();
  if(state.caseId)loadSelected();
  return function(){disposed=true;requestToken++;canvasCleanup();
    if(root.classList&&typeof root.classList.remove==='function'){
      root.classList.remove('v9-recovery-v3');
    }
    root.removeEventListener('click',onV3Click);
    root.removeEventListener('input',onV3Input);
    root.removeEventListener('change',onV3Change);};
}

const recoveryMounts=new WeakMap();

function mountV9RecoveryExplainer(root,artifact,tools){
  if(!root||!root.ownerDocument||!root.classList) return;
  const prior=recoveryMounts.get(root);
  if(prior) prior();
  if(recoveryIsRecord(artifact)&&artifact.schema_version==='3.0'){
    root.classList.add('v9-recovery');
    const cleanup=mountRecoveryExplorerV3(root,artifact,tools);
    recoveryMounts.set(root,cleanup);
    return;
  }
  if(recoveryIsRecord(artifact)&&artifact.schema_version==='2.0'){
    root.classList.add('v9-recovery');
    const cleanup=mountRecoveryExplorerV2(root,artifact,tools);
    recoveryMounts.set(root,cleanup);
    return;
  }
  const doc=root.ownerDocument;
  const helpers=recoveryIsRecord(tools)?tools:{};
  const fmt=typeof helpers.fmt==='function'?helpers.fmt:
    value=>Number(value||0).toLocaleString();
  const view=buildRecoveryEvidenceViewModel(artifact);
  const state={
    caseId:null,
    sortBy:'hybrid_rank_uplift',
    stableStatus:'all',
    relationshipCategory:'all',
    evidence:'all',
    mode:'flow',
    stageId:'first_hop',
    selectedFactorId:null,
    query:'',
    scale:1,
    offsetX:0,
    offsetY:0,
    labelDensity:'auto'
  };
  let canvasCleanup=function(){};
  let pendingCanvas=null;
  root.classList.add('v9-recovery');

  function addHeader(fragment){
    const header=recoveryElement(doc,'header','v9-recovery-header');
    const copy=recoveryElement(doc,'div');
    copy.appendChild(recoveryElement(doc,'div','v9-recovery-eyebrow','Seed-0 evidence audit'));
    const title=recoveryElement(doc,'h3','v9-recovery-title','Why Hybrid recovered more cases');
    title.id='v9-recovery-title';
    copy.appendChild(title);
    copy.appendChild(recoveryElement(
      doc,'p','v9-recovery-intro',
      'Inspect measured rank changes, complete message communities, and validated narrative evidence for Hybrid-only recoveries.'
    ));
    header.appendChild(copy);
    const scope=recoveryElement(doc,'div','v9-recovery-scope');
    scope.textContent='Single-seed observability \u00b7 GraphSAGE seed 0';
    scope.appendChild(recoveryElement(
      doc,'small','',
      'Main results remain three-seed'
    ));
    header.appendChild(scope);
    fragment.appendChild(header);
  }

  function addSummary(fragment){
    if(view.summary.unavailable){
      fragment.appendChild(recoveryElement(
        doc,'div','v9-recovery-status',
        'Overlap unavailable; no values are inferred.'
      ));
    }else{
      const labels=[
        ['baseline_recovered','Baseline recovered'],
        ['recovered_by_both','Recovered by both'],
        ['hybrid_only_recovered','Hybrid-only recovered'],
        ['baseline_only_recovered','Baseline-only recovered'],
        ['hybrid_total','Hybrid total'],
        ['net_gain','Net gain']
      ];
      const grid=recoveryElement(doc,'div','v9-recovery-summary');
      grid.setAttribute('aria-label','Seed-0 recovery overlap summary');
      for(const pair of labels){
        const card=recoveryElement(doc,'article','v9-recovery-stat');
        if(pair[0]==='baseline_only_recovered'&&!view.summary.containment){
          card.classList.add('is-warning');
        }
        card.appendChild(recoveryElement(doc,'b','',fmt(view.summary.values[pair[0]])));
        card.appendChild(recoveryElement(doc,'span','',pair[1]));
        grid.appendChild(card);
      }
      fragment.appendChild(grid);
      fragment.appendChild(recoveryElement(
        doc,'div',view.summary.containment
          ?'v9-recovery-containment':'v9-recovery-warning',
        view.summary.containment
          ?'Observed containment: every baseline recovery also appears in Hybrid for this seed-0 run.'
          :view.summary.warning
      ));
    }
    const coverage=view.coverage;
    const validCoverage=recoveryIsRecord(coverage)
      &&['hybrid_only_count','explanation_limit','attempted_count','explained_count','failed_count']
        .every(key=>recoverySafeInteger(coverage[key],false));
    const coverageRow=recoveryElement(doc,'div','v9-recovery-coverage');
    coverageRow.appendChild(recoveryElement(
      doc,'span','',validCoverage
        ?fmt(coverage.explained_count)+' of '+fmt(coverage.hybrid_only_count)
          +' Hybrid-only cases explained; '+fmt(coverage.attempted_count)
          +' attempted under limit '+fmt(coverage.explanation_limit)+'.'
        :'Coverage unavailable; artifact fields failed validation.'
    ));
    coverageRow.appendChild(recoveryElement(
      doc,'span','',validCoverage
        ?fmt(coverage.failed_count)+' explanation attempts failed validation.'
        :'Failure count unavailable.'
    ));
    fragment.appendChild(coverageRow);
  }

  function renderCaseRail(workspace,filtered){
    const rail=recoveryElement(doc,'aside','v9-recovery-rail');
    rail.setAttribute('aria-label','Recovery case filters and cases');
    const filters=recoveryElement(doc,'div','v9-recovery-filter-grid');
    filters.appendChild(recoverySelect(doc,'Sort','sort',[
      {value:'hybrid_rank_uplift',label:'Hybrid rank uplift'},
      {value:'gnn_percentile_uplift',label:'GNN percentile uplift'}
    ],state.sortBy));
    filters.appendChild(recoverySelect(doc,'Stable factor','stable',[
      {value:'all',label:'All statuses'},
      {value:'stable',label:'Stable'},
      {value:'unstable',label:'Unstable'},
      {value:'not_explained',label:'Not explained'}
    ],state.stableStatus));
    const relations=Array.from(new Set(view.cases.flatMap(item=>
      item.relationship_categories))).sort();
    filters.appendChild(recoverySelect(doc,'Relationship','relation',[
      {value:'all',label:'All relationships'},
      ...relations.map(value=>({value,label:recoveryVisibleText(value)}))
    ],state.relationshipCategory));
    filters.appendChild(recoverySelect(doc,'Evidence','evidence',[
      {value:'all',label:'All cases'},
      {value:'explained',label:'Validated evidence only'}
    ],state.evidence));
    rail.appendChild(filters);
    rail.appendChild(recoveryElement(
      doc,'div','v9-recovery-case-count',
      fmt(filtered.length)+' of '+fmt(view.cases.length)+' cases'
    ));
    const list=recoveryElement(doc,'div','v9-recovery-case-list');
    for(const item of filtered){
      const button=recoverySetData(
        recoveryElement(doc,'button','v9-recovery-case'),'case',item.case_id
      );
      button.type='button';
      button.setAttribute('aria-current',String(item.case_id===state.caseId));
      button.setAttribute('aria-label','Inspect recovery case '+item.person_id);
      const top=recoveryElement(doc,'div','v9-recovery-case-top');
      top.appendChild(recoveryElement(doc,'span','',item.person_id));
      top.appendChild(recoveryElement(
        doc,'span','',recoverySigned(item.hybrid_rank_uplift)+' ranks'
      ));
      button.appendChild(top);
      const ranks=recoveryElement(doc,'div','v9-recovery-case-ranks');
      ranks.appendChild(recoveryElement(doc,'span','','B '+fmt(item.baseline_rank)));
      ranks.appendChild(recoveryElement(doc,'span','','G '+fmt(item.seed0_gnn_rank)));
      ranks.appendChild(recoveryElement(doc,'span','','H '+fmt(item.seed0_hybrid_rank)));
      button.appendChild(ranks);
      button.appendChild(recoveryElement(
        doc,'div','v9-recovery-case-meta',
        item.stable_factor_status+' / '+item.relationship_categories.join(' / ')
      ));
      if(view.explanations.has(item.case_id)){
        button.appendChild(recoveryElement(
          doc,'div','v9-recovery-case-evidence','✓ evidence'
        ));
      }
      list.appendChild(button);
    }
    rail.appendChild(list);
    workspace.appendChild(rail);
  }

  function renderNarrative(detail,explanation){
    const panel=recoveryElement(doc,'section','v9-recovery-narrative');
    panel.appendChild(recoveryElement(doc,'h5','','Grounded narrative'));
    const narrative=validateRecoveryNarrative(explanation.llm_narrative);
    if(!narrative.visible){
      panel.appendChild(recoveryElement(
        doc,'p','',
        'Validated narrative unavailable. Measured factors remain authoritative.'
      ));
    }else{
      panel.appendChild(recoveryElement(
        doc,'p','',narrative.source==='llm'
          ?'Validated local Gemma: '+narrative.model
          :'Deterministic evidence summary. Local Gemma output was unavailable or rejected.'
      ));
      panel.appendChild(recoveryElement(doc,'p','',narrative.summary));
      recoveryAppendSources(doc,panel,narrative.summarySourceRefs);
      for(const claim of narrative.claims){
        panel.appendChild(recoveryElement(doc,'p','',claim.text));
        recoveryAppendSources(doc,panel,claim.source_refs);
      }
    }
    detail.appendChild(panel);
  }

  function renderFactors(column,explanation){
    const panel=recoveryElement(doc,'section','v9-recovery-panel');
    const head=recoveryElement(doc,'div','v9-recovery-panel-head');
    head.appendChild(recoveryElement(doc,'h5','','Salient counterfactual factors'));
    head.appendChild(recoveryElement(
      doc,'p','',
      'Signed effect is ablated rank minus original rank. Positive values mean removal worsened rank.'
    ));
    panel.appendChild(head);
    const factors=Array.isArray(explanation.factors)
      ?explanation.factors.filter(recoveryValidFactor).slice():[];
    factors.sort((left,right)=>
      Number(right.stability==='stable')-Number(left.stability==='stable')
      ||Math.abs(right.counterfactual.ablated_hybrid_rank-right.counterfactual.original_hybrid_rank)
        -Math.abs(left.counterfactual.ablated_hybrid_rank-left.counterfactual.original_hybrid_rank)
      ||recoveryCompareId(left.factor_id,right.factor_id));
    if(!factors.some(factor=>factor.stability==='stable')){
      panel.appendChild(recoveryElement(
        doc,'div','v9-recovery-status',
        'No stable factor found; inspect measured effects below.'
      ));
    }
    if(!factors.length){
      panel.appendChild(recoveryElement(
        doc,'div','v9-recovery-status',
        'No measured factors are available for this explanation.'
      ));
    }else{
      const list=recoveryElement(doc,'div','v9-recovery-factor-list');
      for(const factor of factors){
        const button=recoverySetData(
          recoveryElement(doc,'button','v9-recovery-factor'),
          'factor',factor.factor_id
        );
        button.type='button';
        button.setAttribute('aria-pressed',String(
          state.selectedFactorId===factor.factor_id
        ));
        button.setAttribute('aria-label','Show provenance for '+recoveryVisibleText(factor.label));
        button.appendChild(recoveryElement(
          doc,'strong','',factor.label+' / '+factor.stability
        ));
        const effect=factor.counterfactual.ablated_hybrid_rank
          -factor.counterfactual.original_hybrid_rank;
        button.appendChild(recoveryElement(
          doc,'span','',
          recoverySigned(effect)+' ranks / Ablated minus original'
        ));
        list.appendChild(button);
      }
      panel.appendChild(list);
    }
    column.appendChild(panel);
  }

  function graphButton(label,action,value,pressed,ariaLabel){
    const button=recoverySetData(
      recoveryElement(doc,'button','v9-recovery-button',label),action,value
    );
    button.type='button';
    if(pressed!==null) button.setAttribute('aria-pressed',String(pressed));
    button.setAttribute('aria-label',ariaLabel||label);
    return button;
  }

  function renderGraph(column,explanation){
    const panel=recoveryElement(doc,'section','v9-recovery-panel');
    const head=recoveryElement(doc,'div','v9-recovery-panel-head');
    head.appendChild(recoveryElement(doc,'h5','','Complete as-of message community'));
    head.appendChild(recoveryElement(
      doc,'p','',
      'Base nodes and edges remain visible in every mode. Flow changes emphasis only.'
    ));
    panel.appendChild(head);
    const toolbar=recoveryElement(doc,'div','v9-recovery-toolbar');
    toolbar.setAttribute('role','toolbar');
    toolbar.setAttribute('aria-label','Community graph controls');
    const modes=recoveryElement(doc,'div','v9-recovery-toolgroup');
    modes.appendChild(graphButton('All','mode','all',state.mode==='all','Show all relationships'));
    modes.appendChild(graphButton('Flow','mode','flow',state.mode==='flow','Show influence flow emphasis'));
    toolbar.appendChild(modes);
    const stages=recoveryElement(doc,'div','v9-recovery-toolgroup');
    const stageLabels={
      first_hop:'First hop',
      second_hop:'Second hop',
      component_pool:'Component pool',
      rank_fusion:'Rank fusion'
    };
    for(const stageId of Object.keys(stageLabels)){
      stages.appendChild(graphButton(
        stageLabels[stageId],'stage',stageId,state.stageId===stageId,
        'Show '+stageLabels[stageId].toLowerCase()+' stage'
      ));
    }
    toolbar.appendChild(stages);
    const zoom=recoveryElement(doc,'div','v9-recovery-toolgroup');
    zoom.appendChild(graphButton('+','zoom','in',null,'Zoom in'));
    zoom.appendChild(graphButton('-','zoom','out',null,'Zoom out'));
    zoom.appendChild(graphButton('Reset','zoom','reset',null,'Reset zoom'));
    zoom.appendChild(graphButton('Fit','zoom','fit',null,'Fit to community'));
    toolbar.appendChild(zoom);
    const search=recoveryElement(doc,'input','v9-recovery-search');
    search.type='search';
    search.value=state.query;
    search.placeholder='Find node';
    search.dataset.recoveryInput='search';
    search.setAttribute('aria-label','Search node identifiers');
    toolbar.appendChild(search);
    const density=recoveryElement(doc,'select','v9-recovery-select');
    density.dataset.recoveryChange='density';
    density.setAttribute('aria-label','Node label density');
    for(const pair of [['auto','Labels: auto'],['all','Labels: all'],['none','Labels: none']]){
      const option=recoveryElement(doc,'option','',pair[1]);
      option.value=pair[0];
      density.appendChild(option);
    }
    density.value=state.labelDensity;
    toolbar.appendChild(density);
    panel.appendChild(toolbar);
    const description=recoveryElement(
      doc,'p','v9-recovery-canvas-note',
      'Relation colors show observable context, not relation-specific GraphSAGE parameters. Dashed amber links are selected factor provenance outside the message community.'
    );
    description.id='v9-recovery-canvas-description';
    panel.appendChild(description);
    const commands=buildCommunityDrawCommands(explanation,{
      mode:state.mode,
      stageId:state.stageId,
      selectedFactorId:state.selectedFactorId,
      query:state.query
    });
    if(!commands.available){
      panel.appendChild(recoveryElement(
        doc,'div','v9-recovery-empty',
        'Complete community unavailable. '+commands.reason+'.'
      ));
    }else{
      const wrap=recoveryElement(doc,'div','v9-recovery-canvas-wrap');
      const canvas=recoveryElement(doc,'canvas','v9-recovery-canvas');
      canvas.tabIndex=0;
      canvas.setAttribute('role','img');
      canvas.setAttribute('aria-label','Interactive complete community for the selected seed-0 recovery case');
      canvas.setAttribute('aria-describedby','v9-recovery-canvas-description');
      canvas.textContent='Interactive community graph. Use the toolbar for keyboard controls.';
      wrap.appendChild(canvas);
      panel.appendChild(wrap);
      pendingCanvas={canvas,commands};
    }
    column.appendChild(panel);
  }

  function renderDetail(workspace,selected){
    const detail=recoveryElement(doc,'div','v9-recovery-detail');
    if(!selected){
      detail.appendChild(recoveryElement(
        doc,'div','v9-recovery-empty','No cases match the current filters.'
      ));
      workspace.appendChild(detail);
      return;
    }
    const header=recoveryElement(doc,'header','v9-recovery-case-header');
    const identity=recoveryElement(doc,'div');
    identity.appendChild(recoveryElement(doc,'h4','','Case '+selected.person_id));
    identity.appendChild(recoveryElement(
      doc,'p','',
      'Event '+selected.event_id+' / scoring day '+selected.scoring_day
        +' / Selected at 25 inspections/day.'
    ));
    header.appendChild(identity);
    const ranks=recoveryElement(doc,'div','v9-recovery-ranks');
    for(const item of [
      ['Baseline',selected.baseline_rank],
      ['GraphSAGE seed 0',selected.seed0_gnn_rank],
      ['Hybrid seed 0',selected.seed0_hybrid_rank]
    ]){
      const rank=recoveryElement(doc,'div','v9-recovery-rank');
      rank.appendChild(recoveryElement(doc,'b','',fmt(item[1])));
      rank.appendChild(recoveryElement(doc,'span','',item[0]+' rank'));
      ranks.appendChild(rank);
    }
    header.appendChild(ranks);
    detail.appendChild(header);
    const explanation=view.explanations.get(selected.case_id);
    if(!explanation){
      detail.appendChild(recoveryElement(
        doc,'div','v9-recovery-empty',
        'No validated explanation is available for this case.'
      ));
      workspace.appendChild(detail);
      return;
    }
    const boundaryView=validateRecoveryEvidenceBoundary(
      explanation,selected.scoring_day
    );
    if(!boundaryView.available){
      detail.appendChild(recoveryElement(
        doc,'div','v9-recovery-empty',
        'Strict as-of evidence boundary unavailable. Evidence details are not rendered.'
      ));
      workspace.appendChild(detail);
      return;
    }
    detail.appendChild(recoveryElement(
      doc,'div','v9-recovery-status',
      'Strict as-of evidence boundary: snapshot '+boundaryView.snapshot
        +'. Edges: '+boundaryView.edgeRule+'. Caught labels: '
        +boundaryView.caughtRule+'.'
    ));
    const evidence=recoveryElement(doc,'div','v9-recovery-evidence-grid');
    const left=recoveryElement(doc,'div');
    const right=recoveryElement(doc,'div');
    renderFactors(left,explanation);
    renderNarrative(left,explanation);
    left.appendChild(renderHighestAttributionPanel(doc,explanation));
    renderGraph(right,explanation);
    evidence.appendChild(left);
    evidence.appendChild(right);
    detail.appendChild(evidence);
    workspace.appendChild(detail);
  }

  function render(){
    canvasCleanup();
    canvasCleanup=function(){};
    pendingCanvas=null;
    const fragment=doc.createDocumentFragment();
    addHeader(fragment);
    if(!view.available){
      fragment.appendChild(recoveryElement(
        doc,'div','v9-recovery-empty',
        'Case evidence unavailable. '+view.reason+'.'
      ));
      root.replaceChildren(fragment);
      return;
    }
    addSummary(fragment);
    if(view.cases.length===0){
      fragment.appendChild(recoveryElement(
        doc,'div','v9-recovery-empty',
        'No Hybrid-only recoveries in this seed-0 run.'
      ));
      root.replaceChildren(fragment);
      return;
    }
    const filtered=filterAndSortRecoveryCases(view.cases,{
      sortBy:state.sortBy,
      stableStatus:state.stableStatus,
      relationshipCategory:state.relationshipCategory,
      explainedIds:Array.from(view.explanations.keys()),
      evidence:state.evidence
    });
    if(!filtered.some(item=>item.case_id===state.caseId)){
      state.caseId=filtered.length?filtered[0].case_id:null;
      state.selectedFactorId=null;
      state.scale=1;
      state.offsetX=0;
      state.offsetY=0;
    }
    const selected=filtered.find(item=>item.case_id===state.caseId)||null;
    const workspace=recoveryElement(doc,'div','v9-recovery-workspace');
    renderCaseRail(workspace,filtered);
    renderDetail(workspace,selected);
    fragment.appendChild(workspace);
    root.replaceChildren(fragment);
    if(pendingCanvas){
      canvasCleanup=bindRecoveryCanvas(
        pendingCanvas.canvas,pendingCanvas.commands,state
      );
    }
  }

  function onClick(event){
    const target=event.target;
    if(!target||typeof target.closest!=='function') return;
    const control=target.closest('[data-recovery-action]');
    if(!control||!root.contains(control)) return;
    const action=control.dataset.recoveryAction;
    const value=control.dataset.recoveryValue;
    if(action==='case'){
      state.caseId=value;
      state.selectedFactorId=null;
      state.scale=1;
      state.offsetX=0;
      state.offsetY=0;
    }else if(action==='factor'){
      state.selectedFactorId=state.selectedFactorId===value?null:value;
    }else if(action==='mode'){
      state.mode=value;
    }else if(action==='stage'){
      state.stageId=value;
    }else if(action==='zoom'){
      if(value==='in') state.scale=Math.min(4,state.scale*1.2);
      if(value==='out') state.scale=Math.max(.5,state.scale/1.2);
      if(value==='reset'){
        state.scale=1;
        state.offsetX=0;
        state.offsetY=0;
      }
      if(value==='fit'){
        state.scale=1;
        state.offsetX=0;
        state.offsetY=0;
      }
    }
    render();
    recoveryRestoreFocus(root,'recoveryAction',action,value);
  }
  function onChange(event){
    const control=event.target;
    if(!control||!control.dataset) return;
    const action=control.dataset.recoveryChange;
    if(action==='sort') state.sortBy=control.value;
    if(action==='stable') state.stableStatus=control.value;
    if(action==='relation') state.relationshipCategory=control.value;
    if(action==='evidence') state.evidence=control.value;
    if(action==='density') state.labelDensity=control.value;
    if(action){
      render();
      recoveryRestoreFocus(root,'recoveryChange',action);
    }
  }
  function onInput(event){
    const control=event.target;
    if(!control||!control.dataset||control.dataset.recoveryInput!=='search') return;
    state.query=control.value;
    render();
    const replacement=root.querySelector('[data-recovery-input="search"]');
    if(replacement){
      replacement.focus();
      replacement.setSelectionRange(state.query.length,state.query.length);
    }
  }
  root.addEventListener('click',onClick);
  root.addEventListener('change',onChange);
  root.addEventListener('input',onInput);
  const cleanup=function(){
    canvasCleanup();
    root.removeEventListener('click',onClick);
    root.removeEventListener('change',onChange);
    root.removeEventListener('input',onInput);
    recoveryMounts.delete(root);
  };
  recoveryMounts.set(root,cleanup);
  render();
}
"""
