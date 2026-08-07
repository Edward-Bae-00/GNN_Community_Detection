# V9 Evidence-First Explanation Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the V9 explanation graph evidence-first by default, preserve all existing explanation stages, separate relationship identity from model evidence weight, simplify graph controls, and replace empty grounded narratives with deterministic highest-attribution evidence.

**Architecture:** Keep the existing schema-3 loader, draw-command builders, canvas limits, and complete tables authoritative. Add small pure JavaScript presentation helpers for relationship styles, canvas-only filtering, evidence label selection, and evidence framing; use those helpers inside the existing Canvas 2D renderer and V3 mount. Keep narrative validation unchanged and reuse the existing highest-attribution renderer as the fail-closed fallback.

**Tech Stack:** Python 3.14 string-hosted vanilla JavaScript and CSS, Canvas 2D, Node.js syntax/runtime checks, pytest, existing V9 dashboard builder.

---

## Execution constraints

- Work in the current Merget workspace because the active schema-3 dashboard rewrite and its artifacts are uncommitted here. Do not create a clean Git worktree that would omit this state.
- Do not manually edit generated recovery sidecars, the schema-3 ZIP, model code, scores, or evaluation artifacts.
- Do not run `git commit`. Use focused `merget diff` checkpoints and leave recording to the Merget historian unless the user explicitly requests a commit.
- Read `Documents/Data/changes_3.md` before production edits and preserve strict as-of failure behavior.

## File map

- Modify `Documents/Data/scripts/v9_recovery_explainer_ui.py`: pure presentation helpers, grouped graph controls, Canvas 2D edge/label rendering, evidence framing, and grounded-narrative fallback.
- Modify `tests/test_v9_recovery_explainer_ui.py`: pure-helper, DOM-rendering, accessibility, fallback, and regression tests.
- Modify `tests/test_v9_dashboard_builder.py`: one integration assertion that the generated V9 injection contains the approved graph language without duplicating the recovery mount.
- Modify `DESIGN.md`: record the dual-channel relationship/evidence encoding and grouped graph-control rules.
- Modify `Documents/Data/changes_3.md`: add the dated presentation-only change note after verification.
- Modify `PROJECT_MEMORY.md`: record the durable graph semantics and narrative fallback after verification.
- Rebuild `Documents/Data/v9_dashboard/index.html` only through `Documents/Data/scripts/build_v9_dashboard.py`; never hand-edit the generated HTML.

### Task 1: Add the graph presentation model

**Files:**
- Modify: `tests/test_v9_recovery_explainer_ui.py:585-1028,1125-1180`
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py:840-903`

- [ ] **Step 1: Write failing relationship-style and evidence-style tests**

Add these tests beside the current `recoveryEdgeStyle` coverage:

```python
def test_relationship_presentation_uses_color_pattern_and_plain_labels():
    observed = {
        relation: _run_ui("recoveryRelationPresentation", relation)
        for relation in ("COTRAVEL", "RESIDENCE", "SHARED_PLATE", "OTHER_LINK")
    }

    assert observed == {
        "COTRAVEL": {
            "key": "COTRAVEL",
            "label": "Co-travel",
            "color": "#34d399",
            "dash": [],
        },
        "RESIDENCE": {
            "key": "RESIDENCE",
            "label": "Residence",
            "color": "#60a5fa",
            "dash": [9, 5],
        },
        "SHARED_PLATE": {
            "key": "SHARED_PLATE",
            "label": "Shared plate",
            "color": "#a78bfa",
            "dash": [2, 5],
        },
        "OTHER_LINK": {
            "key": "OTHER_LINK",
            "label": "Other link",
            "color": "#8b8b96",
            "dash": [12, 6],
        },
    }


def test_edge_style_separates_relationship_core_from_model_evidence_underlay():
    low = _run_ui(
        "recoveryEdgeStyle",
        {"importance": 0.0, "emphasized": True, "attributed": True},
    )
    high = _run_ui(
        "recoveryEdgeStyle",
        {"importance": 1.0, "emphasized": True, "attributed": True},
    )
    context = _run_ui(
        "recoveryEdgeStyle",
        {"importance": 0.0, "emphasized": False, "attributed": False},
    )

    assert low == {
        "alpha": 0.9,
        "lineWidth": 1.75,
        "evidenceAlpha": 0.22,
        "evidenceLineWidth": 5,
    }
    assert high == {
        "alpha": 0.95,
        "lineWidth": 3,
        "evidenceAlpha": 0.57,
        "evidenceLineWidth": 10,
    }
    assert context == {
        "alpha": 0.14,
        "lineWidth": 0.75,
        "evidenceAlpha": 0,
        "evidenceLineWidth": 0,
    }
```

- [ ] **Step 2: Run the new tests and confirm the expected failures**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_relationship_presentation_uses_color_pattern_and_plain_labels \
  tests/test_v9_recovery_explainer_ui.py::test_edge_style_separates_relationship_core_from_model_evidence_underlay
```

Expected: FAIL because `recoveryRelationPresentation` is undefined and the existing edge-style object does not expose separate evidence-underlay fields.

- [ ] **Step 3: Implement the pure relationship and edge-style helpers**

Replace `recoveryRelationColor` with this presentation helper and keep a compatibility wrapper for existing callers:

```javascript
function recoveryRelationPresentation(relation){
  const key=String(relation||'RELATION').trim().toUpperCase()||'RELATION';
  const known={
    COTRAVEL:{label:'Co-travel',color:'#34d399',dash:[]},
    RESIDENCE:{label:'Residence',color:'#60a5fa',dash:[9,5]},
    SHARED_PLATE:{label:'Shared plate',color:'#a78bfa',dash:[2,5]}
  }[key];
  if(known)return {key,label:known.label,color:known.color,dash:known.dash.slice()};
  const label=key.toLowerCase().split('_')
    .map((part,index)=>index===0
      ?part.charAt(0).toUpperCase()+part.slice(1):part).join(' ');
  return {key,label,color:'#8b8b96',dash:[12,6]};
}

function recoveryRelationColor(relation){
  return recoveryRelationPresentation(relation).color;
}

function recoveryEdgeStyle(edge){
  const importance=typeof edge.importance==='number'
    &&Number.isFinite(edge.importance)
    ?Math.max(0,Math.min(1,edge.importance)):0;
  if(edge.attributed===true){
    return {
      alpha:0.9+0.05*importance,
      lineWidth:1.75+1.25*importance,
      evidenceAlpha:0.22+0.35*importance,
      evidenceLineWidth:5+5*importance
    };
  }
  if(edge.emphasized){
    return {
      alpha:0.5,
      lineWidth:1.35,
      evidenceAlpha:0,
      evidenceLineWidth:0
    };
  }
  return {
    alpha:0.14,
    lineWidth:0.75,
    evidenceAlpha:0,
    evidenceLineWidth:0
  };
}
```

Update the old edge-style test expectations instead of retaining contradictory legacy assertions.

- [ ] **Step 4: Add failing canvas-only relationship-filter tests**

Add this test near the draw-command tests:

```python
def test_relationship_filter_changes_canvas_rows_but_preserves_complete_tables():
    commands = {
        "available": True,
        "nodes": [
            {"id": "target", "target": True},
            {"id": "n2", "target": False},
            {"id": "n3", "target": False},
        ],
        "edges": [
            {"id": "e1", "u": "target", "v": "n2", "relation": "COTRAVEL"},
            {"id": "e2", "u": "target", "v": "n3", "relation": "RESIDENCE"},
        ],
        "tableNodes": [{"id": "target"}, {"id": "n2"}, {"id": "n3"}],
        "tableEdges": [{"id": "e1"}, {"id": "e2"}],
        "provenanceNodes": [],
        "provenanceEdges": [],
    }

    filtered = _run_ui("filterRecoveryGraphCommands", commands, "RESIDENCE")

    assert [edge["id"] for edge in filtered["edges"]] == ["e2"]
    assert [node["id"] for node in filtered["nodes"]] == ["target", "n3"]
    assert [edge["id"] for edge in filtered["tableEdges"]] == ["e1", "e2"]
    assert filtered["relationshipOptions"] == [
        {"key": "all", "label": "All types"},
        {"key": "COTRAVEL", "label": "Co-travel"},
        {"key": "RESIDENCE", "label": "Residence"},
    ]
```

- [ ] **Step 5: Run the filter test and confirm it fails**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_relationship_filter_changes_canvas_rows_but_preserves_complete_tables
```

Expected: FAIL because `filterRecoveryGraphCommands` is undefined.

- [ ] **Step 6: Implement non-mutating canvas filtering**

Add these helpers after `recoveryEdgeStyle`:

```javascript
function recoveryGraphRelationshipOptions(edges){
  const seen=new Map();
  for(const edge of Array.isArray(edges)?edges:[]){
    const presentation=recoveryRelationPresentation(edge&&edge.relation);
    if(!seen.has(presentation.key))seen.set(presentation.key,presentation.label);
  }
  const preferred=['COTRAVEL','RESIDENCE','SHARED_PLATE'];
  const keys=Array.from(seen.keys()).sort((left,right)=>{
    const leftIndex=preferred.indexOf(left);
    const rightIndex=preferred.indexOf(right);
    if(leftIndex!==-1||rightIndex!==-1){
      if(leftIndex===-1)return 1;
      if(rightIndex===-1)return -1;
      return leftIndex-rightIndex;
    }
    return recoveryCompareId(left,right);
  });
  return [{key:'all',label:'All types'},
    ...keys.map(key=>({key,label:seen.get(key)}))];
}

function filterRecoveryGraphCommands(commands,relationship){
  const source=recoveryIsRecord(commands)?commands:{};
  const relationshipOptions=recoveryGraphRelationshipOptions(source.edges);
  const allowed=new Set(relationshipOptions.map(option=>option.key));
  const selected=allowed.has(relationship)?relationship:'all';
  if(selected==='all'){
    return {...source,
      nodes:Array.isArray(source.nodes)?source.nodes.slice():[],
      edges:Array.isArray(source.edges)?source.edges.slice():[],
      tableNodes:Array.isArray(source.tableNodes)?source.tableNodes.slice():[],
      tableEdges:Array.isArray(source.tableEdges)?source.tableEdges.slice():[],
      provenanceNodes:Array.isArray(source.provenanceNodes)
        ?source.provenanceNodes.slice():[],
      provenanceEdges:Array.isArray(source.provenanceEdges)
        ?source.provenanceEdges.slice():[],
      relationship:selected,relationshipOptions};
  }
  const edges=(Array.isArray(source.edges)?source.edges:[]).filter(edge=>
    recoveryRelationPresentation(edge&&edge.relation).key===selected);
  const nodeIds=new Set(edges.flatMap(edge=>[edge.u,edge.v]));
  for(const node of Array.isArray(source.nodes)?source.nodes:[]){
    if(node&&node.target===true)nodeIds.add(node.id);
  }
  return {...source,
    nodes:(Array.isArray(source.nodes)?source.nodes:[])
      .filter(node=>nodeIds.has(node&&node.id)),
    edges,
    tableNodes:Array.isArray(source.tableNodes)?source.tableNodes.slice():[],
    tableEdges:Array.isArray(source.tableEdges)?source.tableEdges.slice():[],
    provenanceNodes:[],provenanceEdges:[],
    relationship:selected,relationshipOptions};
}
```

- [ ] **Step 7: Run Task 1 tests and inspect the focused diff**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py -k \
  'relationship_presentation or edge_style or relationship_filter'
rtk merget diff -- Documents/Data/scripts/v9_recovery_explainer_ui.py \
  tests/test_v9_recovery_explainer_ui.py
```

Expected: selected tests PASS. The diff contains only pure presentation helpers and their tests.

### Task 2: Render dual-channel edges, strongest-edge labels, and evidence framing

**Files:**
- Modify: `tests/test_v9_recovery_explainer_ui.py:1450-1535,1517-1605,2260-2310`
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py:905-1046`

- [ ] **Step 1: Write failing evidence-label and bounds tests**

Add:

```python
def test_evidence_edge_selection_is_rank_first_stable_and_bounded():
    edges = [
        {"id": "e3", "rank": 3, "importance": 0.95, "attributed": True},
        {"id": "e1", "rank": 1, "importance": 0.7, "attributed": True},
        {"id": "e2", "rank": 2, "importance": 0.8, "attributed": True},
        {"id": "e4", "rank": 4, "importance": 1.0, "attributed": True},
        {"id": "context", "rank": None, "importance": 1.0, "attributed": False},
    ]

    selected = _run_ui("selectRecoveryEvidenceEdges", edges, 3)

    assert [edge["id"] for edge in selected] == ["e1", "e2", "e3"]


def test_evidence_bounds_fit_target_and_attributed_endpoints_only():
    commands = {
        "nodes": [
            {"id": "target", "x": 0.4, "y": 0.4, "target": True},
            {"id": "evidence", "x": 0.6, "y": 0.7, "target": False},
            {"id": "context", "x": 0.99, "y": 0.01, "target": False},
        ],
        "edges": [
            {
                "id": "e1",
                "u": "target",
                "v": "evidence",
                "attributed": True,
            }
        ],
    }

    bounds = _run_ui("recoveryEvidenceBounds", commands)

    assert bounds == {"minX": 0.32, "minY": 0.32, "maxX": 0.68, "maxY": 0.78}
```

Add a source-contract assertion to the existing graph accessibility test:

```python
    for token in (
        "Model evidence weight",
        "selectRecoveryEvidenceEdges",
        "recoveryEvidenceBounds",
        "recoveryDrawEvidenceLabels",
        "style.evidenceLineWidth",
        "relation.dash",
    ):
        assert token in mount
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_evidence_edge_selection_is_rank_first_stable_and_bounded \
  tests/test_v9_recovery_explainer_ui.py::test_evidence_bounds_fit_target_and_attributed_endpoints_only \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_graph_exposes_accessible_names_and_a_table_fallback
```

Expected: FAIL because the label-selection, evidence-bounds, and dual-channel draw hooks do not exist.

- [ ] **Step 3: Implement stable evidence selection and evidence bounds**

Add before `graphPoint`:

```javascript
function selectRecoveryEvidenceEdges(edges,limit){
  const rows=(Array.isArray(edges)?edges:[]).filter(edge=>
    edge&&edge.attributed===true&&recoveryFiniteUnit(edge.importance));
  const ranked=rows.length>0&&rows.every(edge=>
    Number.isSafeInteger(edge.rank)&&edge.rank>0)
    &&new Set(rows.map(edge=>edge.rank)).size===rows.length;
  rows.sort((left,right)=>ranked
    ?left.rank-right.rank||recoveryCompareId(left.id,right.id)
    :right.importance-left.importance||recoveryCompareId(left.id,right.id));
  return rows.slice(0,Math.max(0,Number.isSafeInteger(limit)?limit:3));
}

function recoveryEvidenceBounds(commands){
  const nodes=Array.isArray(commands&&commands.nodes)?commands.nodes:[];
  const byId=new Map(nodes.map(node=>[node.id,node]));
  const ids=new Set(nodes.filter(node=>node.target===true).map(node=>node.id));
  for(const edge of Array.isArray(commands&&commands.edges)?commands.edges:[]){
    if(edge&&edge.attributed===true){ids.add(edge.u);ids.add(edge.v);}
  }
  let points=Array.from(ids).map(id=>byId.get(id)).filter(Boolean);
  if(points.length<2)points=nodes.slice();
  if(!points.length)return {minX:0,minY:0,maxX:1,maxY:1};
  const minX=Math.min(...points.map(point=>point.x));
  const maxX=Math.max(...points.map(point=>point.x));
  const minY=Math.min(...points.map(point=>point.y));
  const maxY=Math.max(...points.map(point=>point.y));
  return {
    minX:Math.max(0,Number((minX-0.08).toFixed(6))),
    minY:Math.max(0,Number((minY-0.08).toFixed(6))),
    maxX:Math.min(1,Number((maxX+0.08).toFixed(6))),
    maxY:Math.min(1,Number((maxY+0.08).toFixed(6)))
  };
}
```

Extend `graphPoint` to normalize against `viewport.bounds`, protecting spans
smaller than `0.12`:

```javascript
  const bounds=recoveryIsRecord(viewport.bounds)
    ?viewport.bounds:{minX:0,minY:0,maxX:1,maxY:1};
  const spanX=Math.max(0.12,bounds.maxX-bounds.minX);
  const spanY=Math.max(0.12,bounds.maxY-bounds.minY);
  const normalizedX=(point.x-bounds.minX)/spanX;
  const normalizedY=(point.y-bounds.minY)/spanY;
  const baseX=padding+normalizedX*Math.max(0,width-padding*2);
  const baseY=padding+normalizedY*Math.max(0,height-padding*2);
```

- [ ] **Step 4: Implement the dual-stroke canvas path**

Add a focused edge renderer before `bindRecoveryCanvas`:

```javascript
function recoveryStrokeGraphEdge(context,from,to,edge){
  const relation=recoveryRelationPresentation(edge.relation);
  const style=recoveryEdgeStyle(edge);
  context.lineCap='round';
  if(style.evidenceLineWidth>0){
    context.beginPath();context.setLineDash([]);
    context.moveTo(from.x,from.y);context.lineTo(to.x,to.y);
    context.strokeStyle='#fbbf24';context.globalAlpha=style.evidenceAlpha;
    context.lineWidth=style.evidenceLineWidth;context.stroke();
  }
  context.beginPath();context.setLineDash(relation.dash);
  context.moveTo(from.x,from.y);context.lineTo(to.x,to.y);
  context.strokeStyle=relation.color;context.globalAlpha=style.alpha;
  context.lineWidth=style.lineWidth;context.stroke();
  context.setLineDash([]);context.globalAlpha=1;
  return relation;
}
```

Replace the current per-edge stroke block with
`recoveryStrokeGraphEdge(context,from,to,edge)`. Keep flow arrows, but color
them with `recoveryRelationPresentation(edge.relation).color` so relationship
identity remains visible.

- [ ] **Step 5: Implement collision-aware labels for the three strongest evidence edges**

Add:

```javascript
function recoveryRectOverlaps(left,right){
  return left.x<right.x+right.width&&left.x+left.width>right.x
    &&left.y<right.y+right.height&&left.y+left.height>right.y;
}

function recoveryDrawEvidenceLabels(context,edges,positionById,nodeBoxes){
  const occupied=(Array.isArray(nodeBoxes)?nodeBoxes:[]).slice();
  context.font='700 9px JetBrains Mono, monospace';
  for(const edge of selectRecoveryEvidenceEdges(edges,3)){
    const from=positionById.get(edge.u);const to=positionById.get(edge.v);
    if(!from||!to)continue;
    const relation=recoveryRelationPresentation(edge.relation);
    const rank=Number.isSafeInteger(edge.rank)?'#'+edge.rank:'Evidence';
    const text=rank+' '+relation.label+' '
      +recoveryFormatNumber(edge.importance);
    const width=Math.ceil(context.measureText(text).width)+14;
    const midpoint={x:(from.x+to.x)/2,y:(from.y+to.y)/2};
    const box={x:midpoint.x+8,y:midpoint.y-23,width,height:18};
    if(occupied.some(other=>recoveryRectOverlaps(box,other)))continue;
    context.beginPath();context.moveTo(midpoint.x,midpoint.y);
    context.lineTo(box.x,box.y+box.height/2);
    context.strokeStyle=relation.color;context.globalAlpha=.8;
    context.lineWidth=1;context.stroke();context.globalAlpha=1;
    context.fillStyle='#171c24';context.fillRect(box.x,box.y,box.width,box.height);
    context.strokeStyle='#4a5260';context.strokeRect(box.x,box.y,box.width,box.height);
    context.fillStyle='#eef2f8';context.fillText(text,box.x+7,box.y+12);
    occupied.push(box);
  }
}
```

Before the node pass, create `const nodeBoxes=[];`. After each node radius is
resolved, record its marker box, then expand the occupied region when a node
label is drawn:

```javascript
      nodeBoxes.push({x:point.x-radius-5,y:point.y-radius-5,
        width:(radius+5)*2,height:(radius+5)*2});
      const showLabel=state.labelDensity==='all'
        ||(state.labelDensity==='key'
          &&(node.target||node.matched||emphasizedNodes.has(node.id)));
      if(showLabel){
        const text=recoveryVisibleText(node.id);
        context.fillStyle='#e8e8ec';
        context.font='10px JetBrains Mono, monospace';
        context.fillText(text,point.x+radius+4,point.y+3);
        nodeBoxes.push({x:point.x+radius+2,y:point.y-8,
          width:Math.ceil(context.measureText(text).width)+4,height:14});
      }
```

Call `recoveryDrawEvidenceLabels(context,commands.edges,positionById,nodeBoxes)`
after the node pass so evidence labels remain readable while collision checks
prevent them from covering node markers and key node labels.

- [ ] **Step 6: Wire evidence framing into the draw viewport**

Inside `draw()`, set:

```javascript
    const bounds=state.mode==='flow'
      ?recoveryEvidenceBounds(commands)
      :{minX:0,minY:0,maxX:1,maxY:1};
    const viewport={
      width,height,padding:42,scale:state.scale,
      offsetX:state.offsetX,offsetY:state.offsetY,bounds
    };
```

Keep pan, wheel zoom, resize cleanup, and device-pixel-ratio behavior unchanged.

- [ ] **Step 7: Run Task 2 tests and the JavaScript lifecycle slice**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py -k \
  'evidence_edge_selection or evidence_bounds or canvas or graph_exposes_accessible'
```

Expected: PASS, including the existing cleanup and missing-endpoint checks.

### Task 3: Replace the confusing toolbar with grouped evidence controls

**Files:**
- Modify: `tests/test_v9_recovery_explainer_ui.py:1000-1045,2180-2310,3180-3275`
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py:85-188,1833-1870,2293-2410,2640-2710`
- Modify: `tests/test_v9_dashboard_builder.py:2586-2645`

- [ ] **Step 1: Write failing rendered-control and accessibility tests**

Add:

```python
def test_schema3_graph_groups_evidence_stage_relationship_and_navigation_controls():
    rendered = _mount_schema3("h1")
    text = " | ".join(rendered["text"])
    labels = rendered["labels"]

    for visible in (
        "Evidence first",
        "Full community",
        "First hop",
        "Second hop",
        "Component pool",
        "Rank fusion",
        "All types",
        "Co-travel",
        "Key labels",
        "Reset view",
        "Model evidence weight",
    ):
        assert visible in text
    for accessible in (
        "Graph view",
        "Explanation stage",
        "Relationship type",
        "Node labels",
        "Graph navigation",
    ):
        assert accessible in labels
    assert "Flow" not in text
    assert "Labels: auto" not in text
    assert "Fit" not in text


def test_v9_results_injection_contains_evidence_first_graph_language_once():
    from Documents.Data.scripts import v9_recovery_explainer_ui as recovery_ui

    recovery = recovery_ui.V9_RECOVERY_EXPLAINER_JS
    assert recovery.count("Evidence first") == 1
    assert recovery.count("Model evidence weight") >= 1
    assert "data-v3-relation" in recovery
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_graph_groups_evidence_stage_relationship_and_navigation_controls \
  tests/test_v9_dashboard_builder.py::test_v9_results_injection_contains_evidence_first_graph_language_once
```

Expected: FAIL because the old toolbar still renders All, Flow, Fit, and the
ungrouped label-density select.

- [ ] **Step 3: Add labeled toolbar-group and stage-description helpers**

Inside `mountRecoveryExplorerV3`, add:

```javascript
  function graphControlGroup(label){
    const group=recoveryElement(doc,'div','v9-recovery-control-group');
    group.setAttribute('role','group');group.setAttribute('aria-label',label);
    addText(group,'span','v9-recovery-control-label',label);
    const controls=recoveryElement(doc,'div','v9-recovery-control-items');
    group.appendChild(controls);return {group,controls};
  }
  function stageDescription(stageId){
    return {
      first_hop:'Immediate message-passing relationships around the target.',
      second_hop:'Relationships available within two message-passing hops.',
      component_pool:'Co-travel links between members included in component pooling.',
      rank_fusion:'Attributed explanation evidence at the final rank-fusion stage.'
    }[stageId]||'Published explanation stage.';
  }
```

Add `relationship:'all'` to the V3 state. Keep internal mode values `flow` and
`all` so the validated draw-command contracts do not change. Change the label
density default from `auto` to `key` and update the canvas label condition to
recognize `key`.

- [ ] **Step 4: Build commands before rendering controls and filter only the canvas**

In `renderGraph`, compute and validate the authoritative commands before the
toolbar. Then derive:

```javascript
    const canvasCommands=filterRecoveryGraphCommands(commands,state.relationship);
    if(canvasCommands.relationship!==state.relationship){
      state.relationship=canvasCommands.relationship;
    }
```

Use `canvasCommands` for `pendingCanvas`, visible canvas counts, relationship
options, and empty relationship feedback. Continue returning the original
`commands` so `renderGraphTable` receives complete rows.

- [ ] **Step 5: Render the grouped toolbar with approved copy**

Replace the current toolbar body with five groups:

```javascript
    const viewGroup=graphControlGroup('Graph view');
    viewGroup.controls.appendChild(graphButton('Evidence first','v3Mode','flow',
      state.mode==='flow','Show evidence-first graph view'));
    viewGroup.controls.appendChild(graphButton('Full community','v3Mode','all',
      state.mode==='all','Show full community graph view'));
    toolbar.appendChild(viewGroup.group);

    const stageGroup=graphControlGroup('Explanation stage');
    for(const value of stageIdsFor(detailView.kind)){
      stageGroup.controls.appendChild(graphButton(stageLabels[value],
        'v3Stage',value,stageId===value,
        'Show '+stageLabels[value].toLowerCase()+' explanation stage'));
    }
    toolbar.appendChild(stageGroup.group);

    const relationGroup=graphControlGroup('Relationship type');
    for(const option of canvasCommands.relationshipOptions){
      relationGroup.controls.appendChild(graphButton(option.label,
        'v3Relation',option.key,state.relationship===option.key,
        'Show '+option.label.toLowerCase()+' relationships'));
    }
    toolbar.appendChild(relationGroup.group);

    const labelGroup=graphControlGroup('Node labels');
    const density=recoveryElement(doc,'select','v9-recovery-select');
    density.dataset.v3Change='density';density.setAttribute('aria-label','Node labels');
    for(const pair of [['key','Key labels'],['all','All labels'],['none','No labels']]){
      const option=recoveryElement(doc,'option','',pair[1]);
      option.value=pair[0];density.appendChild(option);
    }
    density.value=state.labelDensity;labelGroup.controls.appendChild(density);
    toolbar.appendChild(labelGroup.group);

    const navigationGroup=graphControlGroup('Graph navigation');
    navigationGroup.controls.appendChild(graphButton('+','v3Zoom','in',null,'Zoom in'));
    navigationGroup.controls.appendChild(graphButton('-','v3Zoom','out',null,'Zoom out'));
    navigationGroup.controls.appendChild(graphButton('Reset view','v3Zoom','reset',
      null,'Reset graph view'));
    toolbar.appendChild(navigationGroup.group);
```

Keep node search after the groups with its existing accessible label. Add the
stage description immediately after the toolbar and include the approved
sentence: `Gold underlay shows model evidence weight. Inner color and pattern
show the observable relationship type.`

- [ ] **Step 6: Handle relationship, view, stage, and reset state clearly**

Add `[data-v3-relation]` to the delegated click selector and add:

```javascript
    if(data.v3Relation){
      state.relationship=data.v3Relation;
      state.scale=1;state.offsetX=0;state.offsetY=0;render();
      restoreV3Focus('data-v3-relation','v3Relation',data.v3Relation);return;
    }
```

When view or stage changes, also reset `scale`, `offsetX`, and `offsetY` before
rendering. When a new case loads, reset `relationship` to `all` so stale edge
types cannot produce an empty next case. Retain the existing delegated listener
count and focus restoration.

- [ ] **Step 7: Expand the legend and canvas accessible description**

Render one legend item for every relationship option except All types with:

```javascript
    const relationLegendClasses={
      COTRAVEL:'is-cotravel',
      RESIDENCE:'is-residence',
      SHARED_PLATE:'is-shared-plate'
    };
    for(const option of canvasCommands.relationshipOptions){
      if(option.key==='all')continue;
      const swatchClass=relationLegendClasses[option.key]||'is-other-relation';
      legendItem(option.label,swatchClass,'observable relationship type');
    }
```

Retain Target and Caught before snapshot. Replace the generic evidence legend
with these two calls:

```javascript
    legendItem('Model evidence weight','is-evidence',
      'gold underlay width and brightness follow unsigned GNNExplainer attribution');
    legendItem('Attributed node','is-attributed-node',
      'gold ring shows ranked model evidence');
```

Include view, stage, selected relationship, filtered node/edge counts, and the
non-causal evidence meaning in the canvas `aria-label` with:

```javascript
      const relationLabel=(canvasCommands.relationshipOptions.find(option=>
        option.key===canvasCommands.relationship)||{label:'All types'}).label;
      canvas.setAttribute('aria-label',
        (control?'Community context graph for ':'Community graph for Hybrid case ')
          +recoveryVisibleText(record.personId)+', '
          +(state.mode==='flow'?'Evidence first':'Full community')+' view, '
          +stageLabels[stageId]+' stage, '+relationLabel+' relationships, '
          +fmt(canvasCommands.nodes.length)+' members and '
          +fmt(canvasCommands.edges.length)+' relationships. Model evidence weight '
          +'is unsigned GNNExplainer salience, not a causal claim.');
```

- [ ] **Step 8: Add scoped responsive CSS for the grouped toolbar and patterns**

Add to `V9_RECOVERY_EXPLAINER_CSS`:

```css
#tab-v9Results .v9-recovery-toolbar { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; padding:12px; }
#tab-v9Results .v9-recovery-control-group { display:grid; gap:6px; align-content:start; min-width:0; }
#tab-v9Results .v9-recovery-control-label { color:var(--text2); font-size:10px; font-weight:700; letter-spacing:.04em; }
#tab-v9Results .v9-recovery-control-items { display:flex; flex-wrap:wrap; gap:4px; min-width:0; }
#tab-v9Results .v9-recovery-control-items .v9-recovery-button { min-height:36px; }
#tab-v9Results .v9-recovery-legend-swatch.is-cotravel { height:3px; background:#34d399; box-shadow:none; }
#tab-v9Results .v9-recovery-legend-swatch.is-residence { height:3px; background:repeating-linear-gradient(90deg,#60a5fa 0 8px,transparent 8px 13px); box-shadow:none; }
#tab-v9Results .v9-recovery-legend-swatch.is-shared-plate { height:3px; background:repeating-linear-gradient(90deg,#a78bfa 0 3px,transparent 3px 8px); box-shadow:none; }
#tab-v9Results .v9-recovery-legend-swatch.is-other-relation { height:3px; background:repeating-linear-gradient(90deg,#8b8b96 0 11px,transparent 11px 17px); box-shadow:none; }
#tab-v9Results .v9-recovery-legend-swatch.is-evidence { height:9px; background:#fbbf24; box-shadow:none; opacity:.72; }
#tab-v9Results .v9-recovery-legend-swatch.is-attributed-node { width:10px; height:10px; border:2px solid #fbbf24; border-radius:50%; background:transparent; box-shadow:none; }
```

At `max-width:700px`, set the toolbar to one column, make each control item
expand to the available width, and preserve the existing 44-pixel minimum touch
target. Remove the old mobile rules that assume anonymous `.v9-recovery-toolgroup`
rows.

- [ ] **Step 9: Run Task 3 tests**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py -k \
  'groups_evidence_stage or graph_copy or graph_exposes or css_polish or mobile' \
  tests/test_v9_dashboard_builder.py::test_v9_results_injection_contains_evidence_first_graph_language_once
```

Expected: PASS. Existing single-listener, focus, canvas, and responsive
contracts remain green.

### Task 4: Put highest-attribution evidence into empty grounded narratives

**Files:**
- Modify: `tests/test_v9_recovery_explainer_ui.py:640-940,3180-3275,3400-3470`
- Modify: `Documents/Data/scripts/v9_recovery_explainer_ui.py:390-438,2091-2110,2440-2480`

- [ ] **Step 1: Add a test helper that safely replaces a served sidecar**

Add `import hashlib` at the top of the test file and add:

```python
def _replace_served_detail(artifact, files, mutate):
    reference = artifact["detail_index"]["h1"]
    url = artifact["sidecar_base"] + reference["path"]
    payload = json.loads(files[url])
    mutate(payload)
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    files[url] = body
    reference["sha256"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
```

- [ ] **Step 2: Write failing fallback and no-duplication tests**

Add:

```python
def test_schema3_invalid_narrative_uses_highest_attribution_in_grounded_panel():
    artifact, files = _schema3_served_bundle()

    def mutate(payload):
        payload["explanation"]["llm_narrative"] = {}
        payload["explanation"]["attributions"] = {
            "top_local_nodes": [
                {"rank": 1, "node_id": "p2", "explainer_median": 0.9}
            ],
            "top_edges": [
                {
                    "rank": 1,
                    "edge_id": "e1",
                    "u": "p1",
                    "v": "p2",
                    "edge_type": "COTRAVEL",
                    "explainer_median": 0.8,
                }
            ],
        }

    _replace_served_detail(artifact, files, mutate)
    rendered = _mount_schema3("h1", (artifact, files))
    text = " | ".join(rendered["text"])
    disclosures = [
        node["dataset"].get("v3Disclosure")
        for node in rendered["nodes"]
        if node["tag"] == "details"
    ]

    assert "Grounded narrative" in text
    assert "Validated narrative unavailable. Showing ranked model evidence" in text
    assert text.count("Highest-attribution evidence") == 1
    assert "COTRAVEL" in text
    assert "attribution" not in disclosures


def test_schema3_valid_narrative_keeps_attribution_in_technical_disclosure():
    artifact, files = _schema3_served_bundle()

    def mutate(payload):
        payload["explanation"]["llm_narrative"] = {
            "validated": True,
            "prompt_version": "v1",
            "source": "deterministic_template",
            "model": None,
            "summary": "The published ranks identify this case.",
            "summary_source_refs": ["ranks.seed0_hybrid"],
            "claims": [],
        }

    _replace_served_detail(artifact, files, mutate)
    rendered = _mount_schema3("h1", (artifact, files))
    text = " | ".join(rendered["text"])
    disclosures = [
        node["dataset"].get("v3Disclosure")
        for node in rendered["nodes"]
        if node["tag"] == "details"
    ]

    assert "The published ranks identify this case." in text
    assert "attribution" in disclosures
```

- [ ] **Step 3: Run the fallback tests and confirm they fail**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_invalid_narrative_uses_highest_attribution_in_grounded_panel \
  tests/test_v9_recovery_explainer_ui.py::test_schema3_valid_narrative_keeps_attribution_in_technical_disclosure
```

Expected: the invalid-narrative test FAILS because the panel still shows only
the generic unavailable sentence and the separate attribution disclosure.

- [ ] **Step 4: Make `renderNarrative` report whether it consumed attribution**

Replace the invalid branch and return a structured result:

```javascript
  function renderNarrative(column,explanation){
    const panel=recoveryElement(doc,'section','v9-recovery-narrative');
    addText(panel,'h5','','Grounded narrative');
    const narrative=validateRecoveryNarrative(explanation.llm_narrative);
    if(!narrative.visible){
      addText(panel,'p','',
        'Validated narrative unavailable. Showing ranked model evidence from deterministic explainer restarts.');
      panel.appendChild(renderHighestAttributionPanel(doc,explanation));
      column.appendChild(panel);
      return {attributionRendered:true};
    }
    addText(panel,'p','',narrative.source==='llm'
      ?'Validated local Gemma: '+narrative.model
      :'Deterministic evidence summary. Local Gemma output was unavailable or rejected.');
    addText(panel,'p','',narrative.summary);
    recoveryAppendSources(doc,panel,narrative.summarySourceRefs);
    for(const claim of narrative.claims){
      addText(panel,'p','',claim.text);
      recoveryAppendSources(doc,panel,claim.source_refs);
    }
    column.appendChild(panel);
    return {attributionRendered:false};
  }
```

Do not change `validateRecoveryNarrative` or its allowlist.

- [ ] **Step 5: Omit only the duplicate attribution disclosure**

Capture the return value in `renderSelectedEvidence`:

```javascript
    let narrativeResult={attributionRendered:false};
    if(detailView.kind==='gnn_explanation'){
      narrativeResult=renderNarrative(explanationRow,detailView.explanation);
      renderFactors(explanationRow,detailView.explanation);
    }
```

Guard the existing disclosure:

```javascript
    if(detailView.kind==='gnn_explanation'
        &&narrativeResult.attributionRendered!==true){
      renderDisclosure(disclosures,'attribution',
        'Highest-attribution nodes and relationships',body=>
          body.appendChild(renderHighestAttributionPanel(doc,detailView.explanation)));
    }
```

Keep stability, tables, and cohort disclosures unchanged.

- [ ] **Step 6: Run narrative and end-to-end mount tests**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py -k \
  'narrative or highest_attribution or technical_evidence_end_to_end or graph_first_case_workspace'
```

Expected: PASS. Invalid narratives show deterministic ranked evidence once;
valid narratives retain the technical attribution disclosure.

### Task 5: Synchronize design documentation and run full verification

**Files:**
- Modify: `DESIGN.md:34-76`
- Modify: `Documents/Data/changes_3.md:8-30`
- Modify: `PROJECT_MEMORY.md:421-455`
- Generated by command: `Documents/Data/v9_dashboard/index.html`

- [ ] **Step 1: Update the visual source of truth**

Add this paragraph under the graph/evidence component rules in `DESIGN.md`:

```markdown
- **Explanation graph:** default to Evidence first at First hop. Attributed
  relationships use a gold model-evidence-weight underlay beneath a narrower
  relationship stroke: solid green for co-travel, dashed blue for residence,
  and dotted violet for shared plate. The strongest three attributed edges may
  carry direct labels. Group View, Stage, Relationship, Labels, and Navigation
  controls explicitly; do not make one color carry both relationship and
  evidence semantics.
```

Replace the stale layout-order sentence in `DESIGN.md` with:

```markdown
The reading order is: selected case context, rank comparison, interactive
evidence graph, grounded narrative with measured factors, then the technical
disclosures and complete tables.
```

Do not rewrite unrelated design-system sections.

- [ ] **Step 2: Run the complete focused test suites**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_v9_recovery_explainer_ui.py \
  tests/test_v9_dashboard_builder.py
```

Expected: all tests PASS with no skips newly introduced by this work.

- [ ] **Step 3: Compile the Python-hosted UI and builder**

Run:

```bash
rtk .venv/bin/python -m py_compile \
  Documents/Data/scripts/v9_recovery_explainer_ui.py \
  Documents/Data/scripts/build_v9_dashboard.py
```

Expected: exit code 0 and no output.

- [ ] **Step 4: Rebuild the generated V9 dashboard**

Run:

```bash
rtk env PYTHONPATH=. .venv/bin/python Documents/Data/scripts/build_v9_dashboard.py
```

Expected: the builder completes successfully, preserves the single recovery
mount, and publishes the existing verified schema-3 recovery bundle into
`Documents/Data/v9_dashboard/`.

- [ ] **Step 5: Verify generated-language and mount invariants**

Run:

```bash
rtk rg -n "Evidence first|Model evidence weight|Relationship type|Grounded narrative" \
  Documents/Data/v9_dashboard/index.html
rtk env PYTHONPATH=. .venv/bin/python -m pytest -q \
  tests/test_v9_dashboard_builder.py -k \
  'v9_results or recovery or injection'
```

Expected: each approved graph label is present in the generated dashboard and
all selected builder integration tests PASS.

- [ ] **Step 6: Perform visual QA where tooling is available**

Inspect one published explanation at desktop width and below 700 pixels.
Confirm:

- Evidence first and First hop are selected initially.
- Gold underlays remain visually distinct from relationship cores.
- Solid, dashed, and dotted relationship styles match the legend.
- At most three evidence-edge labels appear and do not cover node markers.
- Relationship selection changes only the canvas.
- Full community remains available.
- Empty grounded narratives show Highest-attribution evidence once.
- Controls wrap without page-level horizontal overflow.
- Browser console contains no new errors.

If the in-app browser remains unavailable, record that limitation and rely on
the executable DOM/canvas contracts plus the generated dashboard inspection;
do not claim visual verification occurred.

- [ ] **Step 7: Record the verified change**

Add a dated entry near the top of `Documents/Data/changes_3.md`:

```markdown
## 2026-08-06: evidence-first explanation graph

The V9 explanation graph now defaults to an evidence-first first-hop view,
separates unsigned model evidence weight from observable relationship type with
dual-channel edges, groups graph controls by purpose, and labels the strongest
published connections directly. When the strict narrative validator rejects or
lacks a narrative, the Grounded narrative section shows deterministic
highest-attribution evidence instead of empty prose. Model outputs, sidecars,
strict as-of rules, graph limits, and complete tables are unchanged.
```

Add the same durable rule, in shorter form, to `PROJECT_MEMORY.md` under a new
`2026-08-06` heading.

- [ ] **Step 8: Run final hygiene and review the exact task diff**

Run:

```bash
rtk git diff --check
rtk merget diff -- \
  Documents/Data/scripts/v9_recovery_explainer_ui.py \
  tests/test_v9_recovery_explainer_ui.py \
  tests/test_v9_dashboard_builder.py \
  DESIGN.md \
  Documents/Data/changes_3.md \
  PROJECT_MEMORY.md \
  docs/superpowers/specs/2026-08-06-v9-evidence-first-graph-design.md \
  docs/superpowers/plans/2026-08-06-v9-evidence-first-graph.md
```

Expected: `git diff --check` exits 0. The focused Merget diff contains only the
approved graph presentation, tests, generated build result, and synchronized
documentation, with no model or artifact-schema changes.

- [ ] **Step 9: Hand off to the Merget historian**

Do not create a manual Git commit. Report the verified test commands, generated
dashboard status, any browser-availability limitation, and the exact files
changed so the Merget historian can record the completed work.
