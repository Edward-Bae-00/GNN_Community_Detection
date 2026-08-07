"""Summary-page assets extracted from the V9 dashboard redesign.

This module deliberately contains only the Overview/Summary route. The rest of
the redesign branch remains out of the main dashboard build.
"""

from __future__ import annotations


SUMMARY_PAGE_RUNTIME_JS = r"""
function summaryDashboardRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function summaryDashboardNonNegativeSafeInteger(value) {
  return Number.isSafeInteger(value) && value >= 0;
}

function summaryDashboardPositiveSafeInteger(value) {
  return Number.isSafeInteger(value) && value > 0;
}

function summaryDashboardSafeText(value, fallback) {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function summaryDashboardSortedCounts(value) {
  if (!summaryDashboardRecord(value)) return [];
  return Object.keys(value).map(function(label) {
    return {label: label, count: value[label]};
  }).filter(function(item) {
    return summaryDashboardNonNegativeSafeInteger(item.count);
  }).sort(function(left, right) {
    return right.count - left.count || left.label.localeCompare(right.label);
  });
}

function summaryBuildDatasetSnapshot(meta, overview, demo) {
  var metadata = summaryDashboardRecord(meta) ? meta : {};
  var totals = {
    nodes: summaryDashboardNonNegativeSafeInteger(metadata.total_nodes)
      ? metadata.total_nodes : null,
    edges: summaryDashboardNonNegativeSafeInteger(metadata.total_edges)
      ? metadata.total_edges : null,
    events: summaryDashboardNonNegativeSafeInteger(metadata.total_events)
      ? metadata.total_events : null,
    communities: summaryDashboardNonNegativeSafeInteger(metadata.total_communities)
      ? metadata.total_communities : null
  };
  var totalsAvailable = Object.keys(totals).every(function(key) {
    return totals[key] !== null;
  });
  var dataOverview = summaryDashboardRecord(overview) ? overview : {};
  var dataDemo = summaryDashboardRecord(demo) ? demo : {};
  var arms = summaryDashboardRecord(dataDemo.model_arms) ? dataDemo.model_arms : {};
  var models = {};
  var baselineArm = summaryDashboardRecord(arms.baseline) ? arms.baseline : null;
  var hybridArm = summaryDashboardRecord(arms.hybrid) ? arms.hybrid : null;
  var oracleArm = summaryDashboardRecord(arms.hybrid_oracle) ? arms.hybrid_oracle : null;
  if (baselineArm) {
    models.baseline = {
      label: summaryDashboardSafeText(baselineArm.label, 'HGB tabular baseline'),
      description: summaryDashboardSafeText(baselineArm.looks_for, 'Leak-safe tabular model using own history and event context.'),
      featureCount: Array.isArray(dataDemo.features) ? dataDemo.features.length : null
    };
  }
  if (hybridArm) {
    var seeds = Array.isArray(dataDemo.gnn_seeds)
      && dataDemo.gnn_seeds.every(function(seed) { return summaryDashboardNonNegativeSafeInteger(seed); })
      ? dataDemo.gnn_seeds.length : null;
    models.hybrid = {
      label: summaryDashboardSafeText(hybridArm.label, 'Baseline + GraphSAGE rank-fusion Hybrid'),
      description: summaryDashboardSafeText(hybridArm.looks_for, 'Deployable score fusion of the tabular baseline and as-of GNN risk score.'),
      gnnArm: dataDemo.gnn_arm === 'sage' ? 'GraphSAGE' : summaryDashboardSafeText(dataDemo.gnn_arm, null),
      seeds: seeds,
      fusionWeight: typeof dataDemo.hybrid_fusion_w_gnn === 'number'
        && Number.isFinite(dataDemo.hybrid_fusion_w_gnn)
        && dataDemo.hybrid_fusion_w_gnn >= 0
        && dataDemo.hybrid_fusion_w_gnn <= 1
        ? dataDemo.hybrid_fusion_w_gnn : null,
      trainBucket: summaryDashboardSafeText(dataDemo.train_bucket, null),
      epochs: summaryDashboardPositiveSafeInteger(dataDemo.epochs) ? dataDemo.epochs : null
    };
  }
  if (oracleArm) {
    models.oracle = {
      label: summaryDashboardSafeText(oracleArm.label, 'Oracle Hybrid ceiling'),
      description: summaryDashboardSafeText(oracleArm.looks_for, 'Synthetic-only oracle ceiling; not deployable.')
    };
  }
  return {
    available: totalsAvailable,
    corpus: summaryDashboardSafeText(metadata.corpus, null),
    generatedAt: summaryDashboardSafeText(metadata.generated_at, null),
    totals: totals,
    nodeTypes: summaryDashboardSortedCounts(dataOverview.node_type_counts),
    edgeTypes: summaryDashboardSortedCounts(dataOverview.edge_type_counts),
    models: models
  };
}

function summaryBuildResearchSummary(demo, recovery) {
  var canonicalUnavailable = {
    available: false,
    reason: 'Canonical three-seed operational fields are not embedded.'
  };
  var canonicalOperational = canonicalUnavailable;
  var canonical = summaryDashboardRecord(demo)
    ? demo.operational_unique_person_recovery
    : null;
  if (summaryDashboardRecord(canonical)
      && canonical.scope === 'three-seed'
      && Object.prototype.hasOwnProperty.call(canonical, 'inspections_per_day')
      && summaryDashboardPositiveSafeInteger(canonical.inspections_per_day)
      && ['baseline_people', 'hybrid_people'].every(function(field) {
        return Object.prototype.hasOwnProperty.call(canonical, field)
          && summaryDashboardNonNegativeSafeInteger(canonical[field]);
      })
      && Object.prototype.hasOwnProperty.call(canonical, 'net_people')
      && Number.isSafeInteger(canonical.net_people)
      && canonical.net_people === canonical.hybrid_people - canonical.baseline_people) {
    canonicalOperational = {
      available: true,
      scope: canonical.scope,
      inspectionsPerDay: canonical.inspections_per_day,
      baselinePeople: canonical.baseline_people,
      hybridPeople: canonical.hybrid_people,
      netPeople: canonical.net_people
    };
  }

  var observability = {
    available: false,
    reason: 'Single-seed observability summary is not embedded.'
  };
  var recoveryRecord = summaryDashboardRecord(recovery);
  var policy = recoveryRecord ? recovery.policy : null;
  var hasSchemaMetadata = recoveryRecord
    && Object.prototype.hasOwnProperty.call(recovery, 'schema_version');
  var hasPolicyMetadata = recoveryRecord
    && Object.prototype.hasOwnProperty.call(recovery, 'policy');
  var explicitProvenance = hasSchemaMetadata || hasPolicyMetadata;
  var validProvenance = !explicitProvenance || (
    (recovery.schema_version === '1.0' || recovery.schema_version === '2.0')
    && summaryDashboardRecord(policy)
    && policy.observability_seed === 0
  );
  var recoverySummary = recoveryRecord && validProvenance
    ? recovery.summary : null;
  if (summaryDashboardRecord(recoverySummary)
      && ['baseline_recovered', 'hybrid_total'].every(function(field) {
        return Object.prototype.hasOwnProperty.call(recoverySummary, field)
          && summaryDashboardNonNegativeSafeInteger(recoverySummary[field]);
      })
      && Object.prototype.hasOwnProperty.call(recoverySummary, 'net_gain')
      && Number.isSafeInteger(recoverySummary.net_gain)
      && recoverySummary.net_gain === recoverySummary.hybrid_total - recoverySummary.baseline_recovered) {
    observability = {
      available: true,
      scope: 'single-seed',
      baselinePeople: recoverySummary.baseline_recovered,
      hybridPeople: recoverySummary.hybrid_total,
      netPeople: recoverySummary.net_gain
    };
  }

  return {
    canonicalOperational: canonicalOperational,
    observability: observability
  };
}

var DashboardRuntime = (typeof DashboardRuntime === 'object' && DashboardRuntime)
  ? DashboardRuntime : {};
DashboardRuntime.buildResearchSummary = summaryBuildResearchSummary;
DashboardRuntime.buildDatasetSnapshot = summaryBuildDatasetSnapshot;
"""


SUMMARY_PAGE_CSS = r"""
/* V9 summary page */
.overview-layout{display:grid;grid-template-columns:minmax(240px,.72fr) minmax(0,1.28fr);gap:28px;align-items:start}
.research-brief{position:sticky;top:24px;padding:4px 28px 24px 0;border-right:1px solid var(--border);min-width:0}
.research-brief .brief-kicker{color:var(--accent);font-size:11px;font-weight:700;letter-spacing:.1em;text-transform:uppercase}
.research-brief h2{margin:16px 0 14px;font-size:clamp(30px,4vw,52px);line-height:1.02;letter-spacing:-.045em;font-weight:650;max-width:11ch}
.research-brief p{color:var(--text2);font-size:14px;line-height:1.65;max-width:52ch}
.evidence-console{display:grid;gap:28px;min-width:0}
.evidence-block{padding-top:24px;border-top:1px solid var(--border)}
.evidence-block:first-child{padding-top:0;border-top:0}
.evidence-block h3{font-size:14px;letter-spacing:-.01em;color:var(--text1);margin-bottom:8px}
.evidence-block>p{color:var(--text2);font-size:13px;line-height:1.55;max-width:72ch}
.evidence-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-top:18px}
.evidence-metric{min-width:0}
.evidence-metric .metric-label{display:block;color:var(--text2);font-size:10px;line-height:1.35;letter-spacing:.06em;text-transform:uppercase}
.evidence-metric .metric-value{display:block;margin-top:5px;color:var(--text1);font:600 20px/1.2 var(--font-mono);overflow-wrap:anywhere}
.evidence-metric .metric-note{display:block;margin-top:4px;color:var(--text2);font-size:11px;line-height:1.35}
.evidence-status{color:var(--text2);font-size:13px;line-height:1.55}
.mechanism-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:18px}
.mechanism-item{padding-top:12px;border-top:1px solid var(--border)}
.mechanism-item .mechanism-label{display:block;color:var(--text1);font-size:13px}
.mechanism-item .mechanism-value{display:block;margin-top:4px;color:var(--text2);font:500 17px/1.2 var(--font-mono)}
.mechanism-item .mechanism-note{display:block;margin-top:4px;color:var(--text2);font-size:11px;line-height:1.35}
.limits-list{display:grid;gap:8px;margin-top:14px;color:var(--text2);font-size:13px;line-height:1.5}
.limits-list p{margin:0}
.metric-semantics{margin-top:24px;padding-top:18px;border-top:1px solid var(--border)}
.metric-semantics summary{cursor:pointer;color:var(--text1);font-size:13px;font-weight:600}
.metric-semantics dl{display:grid;grid-template-columns:minmax(150px,.35fr) minmax(0,1fr);gap:9px 18px;margin-top:14px;color:var(--text2);font-size:12px;line-height:1.5}
.metric-semantics dt{color:var(--text1);font-weight:600}
.metric-semantics dd{margin:0}
.dataset-snapshot{display:grid;gap:18px;margin-top:18px}
.dataset-total-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}
.dataset-total{min-width:0;padding:14px;border:1px solid var(--border);background:var(--elevated)}
.dataset-total .metric-value{font-size:18px}
.dataset-breakdown-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.dataset-breakdown{min-width:0;padding:14px;border:1px solid var(--border);background:var(--surface)}
.dataset-breakdown h4{margin:0 0 10px;color:var(--text1);font-size:12px;font-weight:600}
.dataset-breakdown ul{display:grid;gap:7px;margin:0;padding:0;list-style:none}
.dataset-breakdown li{display:flex;justify-content:space-between;gap:12px;color:var(--text2);font-size:12px;line-height:1.35}
.dataset-breakdown li span:first-child{min-width:0;overflow-wrap:anywhere}
.dataset-breakdown li b{flex:none;color:var(--text1);font:500 12px/1.35 var(--font-mono)}
.dataset-model-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.dataset-model-card{min-width:0;padding:16px;border:1px solid var(--border-strong);background:var(--surface)}
.dataset-model-card h4{margin:0;color:var(--text1);font-size:13px;font-weight:600}
.dataset-model-card p{margin:7px 0 0;color:var(--text2);font-size:12px;line-height:1.5}
.dataset-model-meta{display:flex;flex-wrap:wrap;gap:6px 12px;margin-top:12px;color:var(--text2);font-size:11px}
.dataset-model-meta b{color:var(--text1);font-family:var(--font-mono);font-weight:500}
.dataset-unavailable{color:var(--text2);font-size:13px;line-height:1.5}
@media(max-width:768px){.overview-layout{grid-template-columns:1fr;gap:24px}.research-brief{position:static;padding:0 0 24px;border-right:0;border-bottom:1px solid var(--border)}.research-brief h2{max-width:none}.evidence-console{gap:24px}.evidence-metrics,.mechanism-list{grid-template-columns:1fr}.metric-semantics dl{grid-template-columns:1fr;gap:4px 0}.metric-semantics dd{margin-bottom:9px}}
@media(max-width:768px){.dataset-total-grid,.dataset-breakdown-grid,.dataset-model-grid{grid-template-columns:1fr}}
"""


SUMMARY_PAGE_RENDERER_JS = r'''overview:{rendered:false,render(){
  const el=document.getElementById('tab-overview');
  if(!el||typeof DashboardRuntime!=='object'||typeof DashboardRuntime.buildResearchSummary!=='function')return;
  if(typeof el.replaceChildren==='function')el.replaceChildren();else while(el.firstChild)el.removeChild(el.firstChild);
  const summary=DashboardRuntime.buildResearchSummary(D.v9Demo,D.v9RecoveryExplainer);
  const demo=D.v9Demo&&typeof D.v9Demo==='object'?D.v9Demo:null;
  const text=(parent,value,className)=>{const node=document.createElement('span');if(className)node.className=className;node.textContent=String(value);parent.appendChild(node);return node;};
  const para=(parent,value,className)=>{const node=document.createElement('p');if(className)node.className=className;node.textContent=String(value);parent.appendChild(node);return node;};
  const heading=(parent,tag,value)=>{const node=document.createElement(tag);node.textContent=value;parent.appendChild(node);return node;};
  const metric=(parent,label,value,note)=>{const node=document.createElement('div');node.className='evidence-metric';text(node,label,'metric-label');text(node,value,'metric-value');if(note)text(node,note,'metric-note');parent.appendChild(node);};
  const block=(parent,className,title)=>{const node=document.createElement('section');node.className='evidence-block '+className;heading(node,'h3',title);parent.appendChild(node);return node;};
  const safeCount=value=>Number.isSafeInteger(value)&&value>=0;

  const layout=document.createElement('div');layout.className='overview-layout';el.appendChild(layout);
  const brief=document.createElement('aside');brief.className='research-brief';layout.appendChild(brief);
  text(brief,'V9 designed positive control','brief-kicker');
  heading(brief,'h2','A graph helps recover more people at operational depth.');
  para(brief,'V9 is a deliberately connected synthetic positive control. It asks whether an as-of graph signal can help a deployable Hybrid recover people that a strong tabular baseline misses.');

  const console=document.createElement('div');console.className='evidence-console';layout.appendChild(console);
  const snapshot=DashboardRuntime.buildDatasetSnapshot(D.meta,D.overview,D.v9Demo);
  const mechanism=block(console,'mechanism-evidence','Why the graph can help');
  const hidden=demo&&demo.stratum_hidden&&typeof demo.stratum_hidden==='object'?demo.stratum_hidden:null;
  if(hidden&&safeCount(hidden.observable)&&safeCount(hidden.dark)&&safeCount(hidden.lone)){
    para(mechanism,'The positive-control signal propagates through co-travel, shared plate, and residence links. The model may use only graph edges and caught labels available strictly before each event time T.');
    const mechanisms=document.createElement('div');mechanisms.className='mechanism-list';mechanism.appendChild(mechanisms);
    [['Observable population',hidden.observable,'visible relational context'],['Dark population',hidden.dark,'limited observed context'],['Lone population',hidden.lone,'no connected propagation path']].forEach(item=>{const node=document.createElement('div');node.className='mechanism-item';text(node,item[0],'mechanism-label');text(node,item[1],'mechanism-value');text(node,item[2],'mechanism-note');mechanisms.appendChild(node);});
  }else para(mechanism,'Artifact stratum_hidden counts are unavailable or malformed.','evidence-status');

  const obs=summary&&summary.observability;
  const dataset=block(console,'dataset-model-evidence','Dataset and models');
  para(dataset,snapshot&&snapshot.available
    ? 'Synthetic V9 corpus snapshot and the deployable comparison arms used in this positive-control demonstration.'
    : 'Dataset and model metadata is unavailable or failed validation.','dataset-unavailable');
  const totals=snapshot&&snapshot.totals?snapshot.totals:{};
  const totalValue=value=>value===null||value===undefined?'—':Number(value).toLocaleString();
  const totalGrid=document.createElement('div');totalGrid.className='dataset-total-grid dataset-snapshot';dataset.appendChild(totalGrid);
  metric(totalGrid,'Total nodes',totalValue(totals.nodes),'heterogeneous corpus nodes');
  metric(totalGrid,'Total edges',totalValue(totals.edges),'heterogeneous corpus edges');
  metric(totalGrid,'Total events',totalValue(totals.events),'crossing events');
  metric(totalGrid,'Total communities',totalValue(totals.communities),'connected components');
  totalGrid.querySelectorAll('.evidence-metric').forEach(function(node){node.classList.add('dataset-total');});
  const breakdownGrid=document.createElement('div');breakdownGrid.className='dataset-breakdown-grid';dataset.appendChild(breakdownGrid);
  const breakdown=function(parent,title,items,className){
    const panel=document.createElement('div');panel.className='dataset-breakdown '+className;
    heading(panel,'h4',title);
    const list=document.createElement('ul');panel.appendChild(list);
    (items||[]).slice(0,6).forEach(function(item){const row=document.createElement('li');text(row,item.label);const count=document.createElement('b');count.textContent=Number(item.count).toLocaleString();row.appendChild(count);list.appendChild(row);});
    if(!(items||[]).length) para(panel,'Breakdown unavailable.','dataset-unavailable');
    parent.appendChild(panel);
  };
  breakdown(breakdownGrid,'Node types',snapshot&&snapshot.nodeTypes,'node-type-breakdown');
  breakdown(breakdownGrid,'Edge types',snapshot&&snapshot.edgeTypes,'edge-type-breakdown');
  const modelGrid=document.createElement('div');modelGrid.className='dataset-model-grid';dataset.appendChild(modelGrid);
  const modelCard=function(id,fallbackLabel,fallbackDescription){
    const model=snapshot&&snapshot.models&&snapshot.models[id]?snapshot.models[id]:{};
    const card=document.createElement('article');card.className='dataset-model-card';
    heading(card,'h4',model.label||fallbackLabel);
    para(card,model.description||fallbackDescription);
    const metaLine=document.createElement('div');metaLine.className='dataset-model-meta';card.appendChild(metaLine);
    const addMeta=function(label,value){if(value===null||value===undefined)return;const item=document.createElement('span');item.textContent=label+': ';const strong=document.createElement('b');strong.textContent=String(value);item.appendChild(strong);metaLine.appendChild(item);};
    if(id==='baseline') addMeta('Features',model.featureCount);
    if(id==='hybrid'){addMeta('GNN',model.gnnArm);addMeta('Seeds',model.seeds);addMeta('GNN weight',model.fusionWeight===null?null:Number(model.fusionWeight).toFixed(2));addMeta('Train bucket',model.trainBucket);addMeta('Epochs',model.epochs);}
    modelGrid.appendChild(card);
  };
  modelCard('baseline','HGB tabular baseline','Leak-safe tabular model using own history, observed demographics, and event context.');
  modelCard('hybrid','Baseline + GraphSAGE rank-fusion Hybrid','Deployable late fusion of the baseline and an as-of GraphSAGE risk score.');
  if(snapshot&&snapshot.models&&snapshot.models.oracle){
    const oracle=document.createElement('p');oracle.className='dataset-unavailable';oracle.textContent=snapshot.models.oracle.label+' is synthetic-only and not deployable.';dataset.appendChild(oracle);
  }

  if(obs&&obs.available){
    const diagnostic=block(console,'observability-evidence','Single-seed observability diagnostic');
    para(diagnostic,'Seed-0 diagnostic only; values below are unique-person recovery and are separate from event hits.');
    const metrics=document.createElement('div');metrics.className='evidence-metrics';diagnostic.appendChild(metrics);
    metric(metrics,'Baseline unique-person recovery',obs.baselinePeople,'unique people');metric(metrics,'Hybrid unique-person recovery',obs.hybridPeople,'unique people');metric(metrics,'Net unique-person recovery',obs.netPeople,'unique people');
  }

  const semantics=document.createElement('details');semantics.className='metric-semantics';console.appendChild(semantics);heading(semantics,'summary','Metric semantics');
  const definitions=[['Event hit','A hidden-positive event included in a model ranking at a stated K.'],['Unique-person recovery','The number of distinct people represented by recovered hidden-positive events.'],['Observable population','Hidden-positive events in the connected, findable stratum with usable relational context.'],['As-of propagation','Graph edges and caught labels available strictly before the row event time T.']];
  const dl=document.createElement('dl');semantics.appendChild(dl);definitions.forEach(item=>{const dt=document.createElement('dt');dt.textContent=item[0];dl.appendChild(dt);const dd=document.createElement('dd');dd.textContent=item[1];dl.appendChild(dd);});
}},
'''
