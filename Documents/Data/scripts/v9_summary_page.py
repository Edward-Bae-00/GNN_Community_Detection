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

  var eventDepth = {
    available: false,
    reason: 'No mutually available event depth is embedded.'
  };
  var overall = summaryDashboardRecord(demo) ? demo.overall : null;
  var baseline = summaryDashboardRecord(overall) && summaryDashboardRecord(overall.baseline)
    ? overall.baseline : null;
  var hybrid = summaryDashboardRecord(overall) && summaryDashboardRecord(overall.hybrid)
    ? overall.hybrid : null;
  [2000, 5000, 1000, 500, 200, 100, 50].some(function(k) {
    var key = 'found@' + k;
    if (!baseline || !hybrid
        || !summaryDashboardNonNegativeSafeInteger(baseline[key])
        || baseline[key] > k
        || !summaryDashboardNonNegativeSafeInteger(hybrid[key])
        || hybrid[key] > k) {
      return false;
    }
    eventDepth = {
      available: true,
      k: k,
      baselineEventHits: baseline[key],
      hybridEventHits: hybrid[key],
      netEventHits: hybrid[key] - baseline[key]
    };
    return true;
  });

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
    eventDepth: eventDepth,
    observability: observability
  };
}

var DashboardRuntime = (typeof DashboardRuntime === 'object' && DashboardRuntime)
  ? DashboardRuntime : {};
DashboardRuntime.buildResearchSummary = summaryBuildResearchSummary;
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
@media(max-width:768px){.overview-layout{grid-template-columns:1fr;gap:24px}.research-brief{position:static;padding:0 0 24px;border-right:0;border-bottom:1px solid var(--border)}.research-brief h2{max-width:none}.evidence-console{gap:24px}.evidence-metrics,.mechanism-list{grid-template-columns:1fr}.metric-semantics dl{grid-template-columns:1fr;gap:4px 0}.metric-semantics dd{margin-bottom:9px}}
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
  heading(brief,'h2','Relational signal changes recovery at depth.');
  para(brief,'V9 is a designed positive control: relational signal is injected through connected co-travel, shared plate, and residence structure so caught labels can propagate through a connected population. Scores and labels obey strict as-of semantics: only evidence available before each event time is used. This does not replace the V8 honest track, where graph signal is intentionally thin.');

  const console=document.createElement('div');console.className='evidence-console';layout.appendChild(console);
  const operational=block(console,'operational-evidence','Operational evidence');
  const canonical=summary&&summary.canonicalOperational;
  if(canonical&&canonical.available){
    para(operational,'Canonical three-seed operational comparison; values are unique-person recovery.');
    const metrics=document.createElement('div');metrics.className='evidence-metrics';operational.appendChild(metrics);
    metric(metrics,'Inspections per day',canonical.inspectionsPerDay,'operational depth');metric(metrics,'Baseline unique-person recovery',canonical.baselinePeople,'unique people');metric(metrics,'Hybrid unique-person recovery',canonical.hybridPeople,'unique people');metric(metrics,'Net unique-person recovery',canonical.netPeople,'hybrid minus baseline');
  }else{
    para(operational,'Canonical operational comparison unavailable.');
    para(operational,canonical&&canonical.reason?canonical.reason:'Canonical operational fields are unavailable.','evidence-status');
    if(summary&&summary.eventDepth&&summary.eventDepth.available)para(operational,'Artifact-supported event-depth evidence is available in the Event depth section below.','evidence-status');
  }

  const depthBlock=block(console,'event-depth-evidence','Event depth');
  const depth=summary&&summary.eventDepth;
  if(depth&&depth.available){
    para(depthBlock,'Artifact-supported ranking depth; every value below is event hits.');
    const metrics=document.createElement('div');metrics.className='evidence-metrics';depthBlock.appendChild(metrics);
    metric(metrics,'K',depth.k,'event depth');metric(metrics,'Baseline event hits',depth.baselineEventHits,'event hits');metric(metrics,'Hybrid event hits',depth.hybridEventHits,'event hits');metric(metrics,'Net event hits',depth.netEventHits,'event hits');
  }else para(depthBlock,depth&&depth.reason?depth.reason:'Event-depth comparison unavailable.','evidence-status');

  const mechanism=block(console,'mechanism-evidence','Mechanism and ceiling');
  const hidden=demo&&demo.stratum_hidden&&typeof demo.stratum_hidden==='object'?demo.stratum_hidden:null;
  if(hidden&&safeCount(hidden.observable)&&safeCount(hidden.dark)&&safeCount(hidden.lone)){
    para(mechanism,'The designed signal propagates through co-travel, shared plate, and residence links. These strata describe the ceiling imposed by observability, not a forecast.');
    const mechanisms=document.createElement('div');mechanisms.className='mechanism-list';mechanism.appendChild(mechanisms);
    [['Observable population',hidden.observable,'visible relational context'],['Dark population',hidden.dark,'limited observed context'],['Lone population',hidden.lone,'no connected propagation path']].forEach(item=>{const node=document.createElement('div');node.className='mechanism-item';text(node,item[0],'mechanism-label');text(node,item[1],'mechanism-value');text(node,item[2],'mechanism-note');mechanisms.appendChild(node);});
  }else para(mechanism,'Artifact stratum_hidden counts are unavailable or malformed.','evidence-status');

  const limits=block(console,'limits-evidence','Limits and provenance');
  const list=document.createElement('div');list.className='limits-list';limits.appendChild(list);
  para(list,'Positive-control status: V9 is deliberately engineered to contain relational signal; interpret it as a capability check, not a claim about the V8 honest track.');
  para(list,'Connected-population dependence and top-K wash limit recovery when people are dark or isolated.');
  para(list,'As-of evidence is required: graph edges and caught labels must precede each row time T.');
  const provenance=[];
  if(canonical&&canonical.available)provenance.push('canonical operational artifact available');else provenance.push('canonical operational artifact unavailable');
  if(depth&&depth.available)provenance.push('event-depth artifact available');else provenance.push('event-depth artifact unavailable');
  const obs=summary&&summary.observability;
  if(obs&&obs.available)provenance.push('single-seed artifact available');else provenance.push('single-seed artifact unavailable');
  para(list,'Seeds and artifact availability: '+provenance.join('; ')+'.');
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
