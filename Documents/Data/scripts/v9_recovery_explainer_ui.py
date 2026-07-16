"""Pure state contracts for the V9 seed-0 recovery evidence explorer."""


V9_RECOVERY_EXPLAINER_CSS = r"""
#tab-v9Results .v9-recovery-warning { color: #b45309; }
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
  return cases.filter(item=>recoveryValidCase(item)
      &&(stable==='all'||item.stable_factor_status===stable)
      &&(relation==='all'||item.relationship_categories.includes(relation)))
    .slice()
    .sort((left,right)=>
      right[sortBy]-left[sortBy]
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
"""
