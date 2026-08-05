"""Community Explorer — CSS + JS spliced into the dashboard template by build_dashboard.py.

EXPLORER_JS replaces the v2 `people:{...}` Tabs entry, so it must begin with
`explorer:{rendered:false,render(){` and end with `}},` (followed by the seizures entry).
It runs inside the dashboard IIFE and may use: D, C, F, esc, showTip, hideTip, getW,
makeMetrics, makeSection, makeNote, d3.
"""

EXPLORER_CSS = r"""
/* ---- Community Explorer ---- */
.xp-shell{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:18px;align-items:start}
@media(max-width:1024px){.xp-shell{grid-template-columns:1fr}}
.xp-tools{display:flex;flex-wrap:wrap;gap:18px;background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 18px;margin:14px 0}
.xp-group{display:flex;flex-direction:column;gap:7px;min-width:0}
.xp-group>.xp-label{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--text3);font-weight:600}
.xp-chips{display:flex;flex-wrap:wrap;gap:6px}
.xp-chip{display:inline-flex;align-items:center;gap:6px;font-size:11px;padding:5px 10px;border-radius:999px;border:1px solid var(--border-strong);background:var(--elevated);color:var(--text2);cursor:pointer;user-select:none;transition:all 120ms;white-space:nowrap}
.xp-chip:hover{color:var(--text1);border-color:var(--text3)}
.xp-chip.on{background:var(--accent-soft);border-color:var(--accent);color:var(--accent-hover)}
.xp-chip .xp-dot{width:8px;height:8px;border-radius:50%;flex:none}
.xp-chip.role.on{background:rgba(245,158,11,.1);border-color:var(--orange);color:var(--orange)}
.xp-select{background:var(--elevated);border:1px solid var(--border-strong);color:var(--text1);font-family:var(--font-body);font-size:12px;border-radius:8px;padding:7px 9px;min-width:130px;cursor:pointer}
.xp-seg{display:inline-flex;border:1px solid var(--border-strong);border-radius:8px;overflow:hidden}
.xp-seg button{background:var(--elevated);border:none;color:var(--text2);font-family:var(--font-body);font-size:11px;padding:7px 12px;cursor:pointer}
.xp-seg button.on{background:var(--accent);color:#06281d;font-weight:600}
.xp-reset{align-self:flex-end;background:var(--elevated);border:1px solid var(--border-strong);color:var(--text2);border-radius:8px;padding:8px 14px;font-family:var(--font-body);font-size:12px;cursor:pointer}
.xp-reset:hover{color:var(--text1);border-color:var(--text3)}
.xp-canvas{position:relative;min-height:720px;height:720px;background:var(--sunk);border:1px solid var(--border);border-radius:12px;overflow:hidden}
.xp-canvas svg{display:block;width:100%;height:100%}
.xp-link{stroke-linecap:round}
.xp-node{cursor:pointer}
.xp-nlabel{font-family:var(--font-mono);font-size:9px;fill:var(--text2);pointer-events:none;text-anchor:middle}
.xp-legend{position:absolute;left:14px;bottom:14px;background:rgba(10,10,12,.82);border:1px solid var(--border);border-radius:10px;padding:10px 12px;max-width:260px;backdrop-filter:blur(6px)}
.xp-legend .xp-lrow{display:flex;align-items:center;gap:7px;font-size:10px;color:var(--text2);margin:2px 0}
.xp-legend .xp-lrow span.sw{width:9px;height:9px;border-radius:50%;flex:none}
.xp-legend .xp-ltitle{font-size:9px;text-transform:uppercase;letter-spacing:.06em;color:var(--text3);font-weight:600;margin:6px 0 3px}
.xp-status{position:absolute;right:14px;top:12px;font-family:var(--font-mono);font-size:10px;color:var(--text3);text-align:right;background:rgba(10,10,12,.7);padding:5px 9px;border-radius:8px;border:1px solid var(--border)}
.xp-zoom{position:absolute;right:14px;bottom:14px;display:flex;flex-direction:column;gap:5px}
.xp-zoom button{width:30px;height:30px;background:var(--elevated);border:1px solid var(--border-strong);color:var(--text2);border-radius:7px;cursor:pointer;font-size:15px;line-height:1}
.xp-side{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px;position:sticky;top:18px}
.xp-empty{color:var(--text3);font-size:12px;line-height:1.6;padding:30px 6px;text-align:center}
.xp-pid{font-family:var(--font-mono);font-size:16px;font-weight:600;color:var(--text1);margin-top:2px}
.xp-badges{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}
.xp-badge{font-size:10px;font-weight:600;padding:3px 8px;border-radius:6px;letter-spacing:.02em}
.xp-dgrid{display:flex;flex-direction:column;gap:1px;margin-top:8px}
.xp-drow{display:flex;justify-content:space-between;gap:10px;font-size:12px;padding:6px 0;border-bottom:1px solid var(--border)}
.xp-drow span:first-child{color:var(--text3)}
.xp-drow span:last-child{color:var(--text1);font-family:var(--font-mono);text-align:right}
.xp-btn{width:100%;margin-top:12px;background:var(--accent-soft);border:1px solid var(--accent);color:var(--accent-hover);border-radius:8px;padding:9px;font-family:var(--font-body);font-size:12px;font-weight:500;cursor:pointer}
.xp-btn:hover{background:var(--accent-glow)}
.xp-btn.ghost{background:var(--elevated);border-color:var(--border-strong);color:var(--text2)}
.xp-conn{margin-top:14px}
.xp-conn .xp-ctitle{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--text3);font-weight:600;margin-bottom:6px}
.xp-citem{display:flex;justify-content:space-between;font-size:11px;color:var(--text2);padding:3px 0}
.xp-citem span:last-child{font-family:var(--font-mono);color:var(--text3)}
.xp-bars{display:flex;flex-direction:column;gap:8px}
.xp-barrow{display:grid;grid-template-columns:118px minmax(0,1fr) 44px;gap:8px;align-items:center;font-size:11px;color:var(--text2)}
.xp-bartrack{height:9px;background:var(--sunk);border-radius:999px;overflow:hidden;border:1px solid var(--border)}
.xp-barfill{height:100%;border-radius:999px}
.xp-factor{margin-top:12px}
.xp-factor-row{display:grid;grid-template-columns:130px minmax(0,1fr) 38px;gap:8px;align-items:center;font-size:11px;color:var(--text2);margin:6px 0}
.xp-explain{margin-top:12px;background:var(--sunk);border:1px solid var(--border);border-radius:10px;padding:12px;font-size:12px;line-height:1.55;color:var(--text2)}
"""

EXPLORER_JS = r"""explorer:{rendered:false,render(){
  const el=document.getElementById('tab-explorer');
  const E=D.explorer;
  if(!E||!E.nodes||!E.nodes.length){el.innerHTML='<p style="color:var(--text3);padding:40px">No explorer data available.</p>';return;}

  const TYPE_COLORS=['#10b981','#3b82f6','#f59e0b','#8b5cf6','#f43f5e','#0ea5e9','#a3e635','#e879f9','#22d3ee','#fb923c','#94a3b8','#facc15'];
  const tc=i=>TYPE_COLORS[i%TYPE_COLORS.length];
  const ROLE={CARRIED:1,INTERDICT:2,SEIZED:4,ARRESTED:8};
  const ROLE_RING=n=> (n.r&ROLE.ARRESTED)?'#ef4444' : (n.r&ROLE.SEIZED)?'#f59e0b' : (n.r&(ROLE.CARRIED|ROLE.INTERDICT))?'#fb923c' : null;

  // ---- metrics + framing note ----
  makeMetrics(el,[
    {l:'People shown',v:F.n(E.meta.sampled_nodes),s:'of '+F.k(E.meta.total_people)+': role holders, their neighbors, and complete communities'},
    {l:'Contraband carriers',v:F.n(E.meta.n_carried),s:F.n(E.meta.n_undetected)+' never caught'},
    {l:'Arrested',v:F.n(E.meta.n_arrested),s:F.n(E.meta.n_seized)+' seizures'},
    {l:'Linked to a smuggler',v:F.n(E.meta.n_neighbor_smug)},
    {l:'Linked to an arrest',v:F.n(E.meta.n_neighbor_arr)},
  ]);
  const intro=makeSection(el,'Community Explorer');
  makeNote(intro,'Each node is a person; links are real associations, shared family, address, vehicle, business, or co-travel. Phones are deliberately excluded. Colour = community type. Rings mark role. Use the filters to isolate smugglers (including those never caught), the people who were arrested or had seizures, and everyone connected to them. Click a node to inspect it and drill into its community.');

  // ---- toolbar ----
  const tools=document.createElement('div');tools.className='xp-tools';intro.appendChild(tools);
  function group(label){const g=document.createElement('div');g.className='xp-group';g.innerHTML='<div class="xp-label">'+label+'</div>';tools.appendChild(g);return g;}
  function chip(parent,text,cls,dot){const c=document.createElement('span');c.className='xp-chip'+(cls?(' '+cls):'');if(dot)c.innerHTML='<span class="xp-dot" style="background:'+dot+'"></span>';c.appendChild(document.createTextNode(text));parent.appendChild(c);return c;}

  // category chips (role + connection)  -- OR within group
  const catG=group('Show people who are…');const catWrap=document.createElement('div');catWrap.className='xp-chips';catG.appendChild(catWrap);
  const CATS=[
    {k:'carried',t:'Carrying contraband',d:'#fb923c'},
    {k:'seized',t:'Caught (seizure)',d:'#f59e0b'},
    {k:'arrested',t:'Arrested',d:'#ef4444'},
    {k:'interdict',t:'Interdiction member',d:'#f43f5e'},
    {k:'nbsmug',t:'Linked to a smuggler',d:'#a78bfa'},
    {k:'nbarr',t:'Linked to an arrest',d:'#22d3ee'},
  ];
  const catChips={};CATS.forEach(c=>{const ch=chip(catWrap,c.t,'role',c.d);catChips[c.k]=ch;ch.addEventListener('click',()=>{ch.classList.toggle('on');apply();});});

  // community type chips
  const typeG=group('Community type');const typeWrap=document.createElement('div');typeWrap.className='xp-chips';typeG.appendChild(typeWrap);
  const typeChips=[];E.community_types.forEach((t,i)=>{const ch=chip(typeWrap,t.label,'',tc(i));typeChips.push(ch);ch.addEventListener('click',()=>{ch.classList.toggle('on');apply();});});

  // attribute selects
  function selGroup(label,opts,allLabel){const g=group(label);const s=document.createElement('select');s.className='xp-select';s.innerHTML='<option value="">'+allLabel+'</option>'+opts.map((o,i)=>'<option value="'+i+'">'+esc(o)+'</option>').join('');g.appendChild(s);s.addEventListener('change',apply);return s;}
  const regSel=selGroup('Region',E.regions,'All regions');
  const segSel=selGroup('Traveler segment',E.segments,'All segments');
  const citSel=selGroup('Citizenship',E.citizenships,'All');
  const ageSel=selGroup('Age',E.age_buckets,'All ages');

  // specific community — drillCommId is the source of truth (works for
  // communities not in the dropdown, e.g. when the drill button is clicked).
  let drillCommId='';
  const commG=group('Jump to community');const commSel=document.createElement('select');commSel.className='xp-select';
  commSel.innerHTML='<option value="">Pick a community</option>'+E.communities.map(c=>{const lbl=c.id+'  ('+c.size+'p'+(c.carried?', '+c.carried+'⚠':'')+(c.arrested?', '+c.arrested+'×':'')+')';return '<option value="'+esc(c.id)+'">'+esc(lbl)+'</option>';}).join('');
  commG.appendChild(commSel);commSel.addEventListener('change',()=>{drillCommId=commSel.value;selectedNode=null;apply();});
  const drillLabel=document.createElement('div');drillLabel.className='xp-label';drillLabel.style.cssText='font-size:10px;color:var(--accent);margin-top:4px;display:none';commG.appendChild(drillLabel);

  // tie types
  const tieG=group('Connection types');const tieWrap=document.createElement('div');tieWrap.className='xp-chips';tieG.appendChild(tieWrap);
  const TIE_LABELS={associated:'Associated',family:'Family',co_address:'Co-address',co_vehicle:'Co-vehicle',co_business:'Co-business',co_event:'Co-travel'};
  const tieChips=[];E.tie_types.forEach((t,i)=>{const ch=chip(tieWrap,TIE_LABELS[t]||t,'',null);ch.classList.add('on');tieChips.push(ch);ch.addEventListener('click',()=>{ch.classList.toggle('on');apply();});});

  // color-by + mode
  const colorG=group('Colour by');const colorSeg=document.createElement('div');colorSeg.className='xp-seg';colorSeg.innerHTML='<button class="on" data-v="type">Community</button><button data-v="role">Role</button>';colorG.appendChild(colorSeg);
  let colorBy='type';colorSeg.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{colorSeg.querySelectorAll('button').forEach(x=>x.classList.remove('on'));b.classList.add('on');colorBy=b.dataset.v;apply();}));
  const modeG=group('Filter mode');const modeSeg=document.createElement('div');modeSeg.className='xp-seg';modeSeg.innerHTML='<button class="on" data-v="highlight">Highlight</button><button data-v="focus">Focus</button>';modeG.appendChild(modeSeg);
  let mode='highlight';modeSeg.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{modeSeg.querySelectorAll('button').forEach(x=>x.classList.remove('on'));b.classList.add('on');mode=b.dataset.v;apply();}));

  const resetBtn=document.createElement('button');resetBtn.className='xp-reset';resetBtn.textContent='Reset';tools.appendChild(resetBtn);

  // ---- shell: canvas + side ----
  const shell=document.createElement('div');shell.className='xp-shell';el.appendChild(shell);
  const canvas=document.createElement('div');canvas.className='xp-canvas';shell.appendChild(canvas);
  const side=document.createElement('div');side.className='xp-side';shell.appendChild(side);
  side.innerHTML='<div class="xp-empty">Click any person to inspect their roles, community, and connections, then drill into the community around them.</div>';

  const status=document.createElement('div');status.className='xp-status';canvas.appendChild(status);

  // legend
  const legend=document.createElement('div');legend.className='xp-legend';canvas.appendChild(legend);
  function drawLegend(){
    if(colorBy==='type'){
      legend.innerHTML='<div class="xp-ltitle">Community type</div>'+E.community_types.map((t,i)=>'<div class="xp-lrow"><span class="sw" style="background:'+tc(i)+'"></span>'+esc(t.label)+'</div>').join('')+
        '<div class="xp-ltitle">Role ring</div><div class="xp-lrow"><span class="sw" style="background:#fb923c"></span>Smuggler</div><div class="xp-lrow"><span class="sw" style="background:#ef4444"></span>Arrested</div><div class="xp-lrow"><span class="sw" style="background:#f59e0b"></span>Seizure</div>';
    } else {
      legend.innerHTML='<div class="xp-ltitle">Role</div>'+
        '<div class="xp-lrow"><span class="sw" style="background:#fb923c"></span>Contraband carrier</div>'+
        '<div class="xp-lrow"><span class="sw" style="background:#f43f5e"></span>Interdiction member</div>'+
        '<div class="xp-lrow"><span class="sw" style="background:#ef4444"></span>Arrested</div>'+
        '<div class="xp-lrow"><span class="sw" style="background:#f59e0b"></span>Seizure</div>'+
        '<div class="xp-lrow"><span class="sw" style="background:#3a3a42"></span>No recorded role</div>';
    }
  }

  // ---- data + layout ----
  const W=getW(canvas)||900, H=720;
  const nodes=E.nodes.map((n,i)=>Object.assign({},n,{idx:i}));
  const links=E.links.map(l=>({source:l[0],target:l[1],ty:l[2],w:l[3]}));
  const neighbors=nodes.map(()=>[]);
  links.forEach(l=>{neighbors[l.source].push(l.target);neighbors[l.target].push(l.source);});

  const maxDeg=d3.max(nodes,d=>d.d)||1;
  const rscale=d3.scaleSqrt().domain([0,maxDeg]).range([3,12]);
  function radius(d){let r=rscale(d.d);if(d.r&(ROLE.ARRESTED|ROLE.SEIZED))r+=1.5;return r;}
  const sim=d3.forceSimulation(nodes)
    .force('charge',d3.forceManyBody().strength(-45).theta(0.9).distanceMax(400))
    .force('link',d3.forceLink(links).id(d=>d.idx).distance(d=>40+(d.ty&1?0:10)).strength(0.32))
    .force('x',d3.forceX(W/2).strength(0.045))
    .force('y',d3.forceY(H/2).strength(0.055))
    .force('collide',d3.forceCollide(d=>radius(d)+4))
    .stop();
  for(let i=0;i<240;i++)sim.tick();

  const svg=d3.select(canvas).append('svg').attr('viewBox',[0,0,W,H]);
  const root=svg.append('g');
  const linkG=root.append('g').attr('stroke','#3a3a44');
  const nodeG=root.append('g');
  const labelG=root.append('g');
  const zoom=d3.zoom().scaleExtent([0.25,8]).on('zoom',e=>root.attr('transform',e.transform));
  svg.call(zoom);

  function linkTipHtml(d){
    const types=[];
    E.tie_types.forEach((t,i)=>{
      if(d.ty&(1<<i)){
        let lbl=TIE_LABELS[t]||t;
        if(t==='co_event')lbl+=' ('+Math.floor(d.w)+'x)';
        types.push(lbl);
      }
    });
    return '<div class="tt-label">Connection</div>'+
      '<div class="tt-row"><span>People</span><span class="tt-value" style="font-family:var(--font-mono)">'+esc(d.source.id)+' &leftrightarrow; '+esc(d.target.id)+'</span></div>'+
      '<div class="tt-row"><span>Types</span><span class="tt-value">'+types.join(', ')+'</span></div>';
  }

  const link=linkG.selectAll('line').data(links).join('line').attr('class','xp-link')
    .attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y)
    .attr('stroke-width',d=>Math.min(2.4,0.5+Math.sqrt(d.w)*0.35))
    .style('cursor','pointer')
    .on('mouseover',(e,d)=>showTip(e,linkTipHtml(d)))
    .on('mousemove',e=>showTip(e,tip.html()))
    .on('mouseout',hideTip);

  const node=nodeG.selectAll('circle').data(nodes).join('circle').attr('class','xp-node')
    .attr('cx',d=>d.x).attr('cy',d=>d.y).attr('r',radius)
    .on('mouseover',(e,d)=>showTip(e,tipHtml(d))).on('mousemove',e=>showTip(e,tip.html())).on('mouseout',hideTip)
    .on('click',(e,d)=>{selectedNode=d;apply();renderSide(d);})
    .call(d3.drag().on('start',(e,d)=>{d.fx=d.x;d.fy=d.y;}).on('drag',(e,d)=>{d.fx=e.x;d.fy=e.y;d.x=e.x;d.y=e.y;node.filter(n=>n===d).attr('cx',e.x).attr('cy',e.y);labelG.selectAll('text').filter(n=>n===d).attr('x',e.x).attr('y',e.y-radius(d)-3);link.filter(l=>l.source===d||l.target===d).attr('x1',l=>l.source.x).attr('y1',l=>l.source.y).attr('x2',l=>l.target.x).attr('y2',l=>l.target.y);}).on('end',(e,d)=>{d.fx=null;d.fy=null;}));

  function tipHtml(d){
    const roled=[];if(d.r&ROLE.CARRIED)roled.push('carrier');if(d.r&ROLE.INTERDICT)roled.push('interdiction');if(d.r&ROLE.SEIZED)roled.push('seizure');if(d.r&ROLE.ARRESTED)roled.push('arrested');
    return '<div class="tt-label">'+esc(d.id)+'</div>'+
      '<div class="tt-row"><span>Community type</span><span class="tt-value">'+esc(E.community_types[d.ct].label)+'</span></div>'+
      '<div class="tt-row"><span>Degree</span><span class="tt-value">'+F.n(d.d)+'</span></div>'+
      (roled.length?'<div class="tt-row"><span>Role</span><span class="tt-value">'+roled.join(', ')+'</span></div>':(d.ns||d.na?'<div class="tt-row"><span>Linked to</span><span class="tt-value">'+[d.ns?'smuggler':null,d.na?'arrest':null].filter(Boolean).join(', ')+'</span></div>':''));
  }

  // ---- filtering ----
  let selectedNode=null;
  function activeCats(){const s=new Set();Object.keys(catChips).forEach(k=>{if(catChips[k].classList.contains('on'))s.add(k);});return s;}
  function activeTypes(){const s=new Set();typeChips.forEach((ch,i)=>{if(ch.classList.contains('on'))s.add(i);});return s;}
  function tieMask(){let m=0;tieChips.forEach((ch,i)=>{if(ch.classList.contains('on'))m|=(1<<i);});return m;}
  function catMatch(d,cats){
    if(cats.size===0)return true;
    if(cats.has('carried')&&(d.r&ROLE.CARRIED))return true;
    if(cats.has('seized')&&(d.r&ROLE.SEIZED))return true;
    if(cats.has('arrested')&&(d.r&ROLE.ARRESTED))return true;
    if(cats.has('interdict')&&(d.r&ROLE.INTERDICT))return true;
    if(cats.has('nbsmug')&&d.ns)return true;
    if(cats.has('nbarr')&&d.na)return true;
    return false;
  }
  function apply(){
    const cats=activeCats();const tset=activeTypes();
    const reg=regSel.value,sg=segSel.value,ci=citSel.value,ag=ageSel.value;
    const tm=tieMask();
    const commId=drillCommId;
    // show/hide drill indicator
    if(commId){drillLabel.textContent='Drilling: '+commId;drillLabel.style.display='block';}else{drillLabel.style.display='none';}
    // community drill: members + their link-neighbors
    let drillMembers=null,drillSet=null;
    if(commId){
      drillMembers=new Set();nodes.forEach(n=>{if(n.cm===commId)drillMembers.add(n.idx);});
      drillSet=new Set(drillMembers);drillMembers.forEach(i=>neighbors[i].forEach(j=>drillSet.add(j)));
    }
    function base(d){
      if(!catMatch(d,cats))return false;
      if(tset.size&&!tset.has(d.ct))return false;
      if(reg!==''&&d.rg!=+reg)return false;
      if(sg!==''&&d.sg!=+sg)return false;
      if(ci!==''&&d.ci!=+ci)return false;
      if(ag!==''&&d.ag!=+ag)return false;
      return true;
    }
    let nMatch=0,nSmug=0,nArr=0;
    nodes.forEach(d=>{
      let m=base(d);
      if(drillSet&&!drillSet.has(d.idx))m=false;
      d._m=m;d._core=m&&(!drillMembers||drillMembers.has(d.idx));
      if(m){nMatch++;if(d.r&(ROLE.CARRIED|ROLE.INTERDICT))nSmug++;if(d.r&ROLE.ARRESTED)nArr++;}
    });
    // link visibility: enabled tie + endpoint matching
    link.each(function(l){const tieOk=(l.ty&tm)!==0;const bothM=l.source._m&&l.target._m;l._show=tieOk&&(mode==='focus'?bothM:true);l._strong=tieOk&&bothM;});
    // selection ego
    const selId=selectedNode?selectedNode.idx:-1;
    const ego=new Set();if(selId>=0){ego.add(selId);neighbors[selId].forEach(j=>ego.add(j));}

    node.attr('display',d=> (mode==='focus'&&!d._m)?'none':null)
      .attr('fill',d=>{
        if(!d._m)return colorBy==='role'?'#2a2a30':'#26262c';
        if(colorBy==='role')return (d.r&ROLE.ARRESTED)?'#ef4444':(d.r&ROLE.SEIZED)?'#f59e0b':(d.r&ROLE.CARRIED)?'#fb923c':(d.r&ROLE.INTERDICT)?'#f43f5e':'#3a3a42';
        return tc(d.ct);
      })
      .attr('fill-opacity',d=>d._m?(mode==='highlight'?0.95:0.95):0.16)
      .attr('stroke',d=>{if(selId>=0&&d.idx===selId)return '#fff';const ring=ROLE_RING(d);return d._m&&ring?ring:'var(--bg)';})
      .attr('stroke-width',d=>{if(selId>=0&&d.idx===selId)return 2.4;return (d._m&&ROLE_RING(d))?1.8:0.6;})
      .attr('stroke-opacity',d=>d._m?1:0.25);

    link.attr('display',l=>l._show?null:'none')
      .attr('stroke',l=>l._strong?'#5a5a68':'#33333c')
      .attr('stroke-opacity',l=>{if(selId>=0)return (l.source.idx===selId||l.target.idx===selId)?0.85:(l._strong?0.16:0.07);return l._strong?0.5:0.14;});

    // labels: only for matched role nodes when set is small enough, or selection ego
    const labelData=nodes.filter(d=>d._m&&((d.r&(ROLE.ARRESTED|ROLE.SEIZED))||(selId>=0&&ego.has(d.idx))));
    const lab=labelG.selectAll('text').data(labelData.length<=160?labelData:[],d=>d.idx).join('text')
      .attr('class','xp-nlabel').attr('x',d=>d.x).attr('y',d=>d.y-radius(d)-3).text(d=>d.id);

    status.innerHTML=F.n(nMatch)+' people · '+F.n(nSmug)+' smugglers · '+F.n(nArr)+' arrested'+(commId?'<br>community '+esc(commId):'');
    drawLegend();
  }

  function renderSide(d){
    if(!d){side.innerHTML='<div class="xp-empty">Click any person to inspect them.</div>';return;}
    const roles=[];
    if(d.r&ROLE.CARRIED)roles.push(['Contraband carrier','#fb923c','rgba(251,146,60,.14)']);
    if(d.r&ROLE.INTERDICT)roles.push(['Interdiction member','#f43f5e','rgba(244,63,94,.14)']);
    if(d.r&ROLE.SEIZED)roles.push(['Seizure','#f59e0b','rgba(245,158,11,.14)']);
    if(d.r&ROLE.ARRESTED)roles.push(['Arrested','#ef4444','rgba(239,68,68,.16)']);
    if(!roles.length&&d.ns)roles.push(['Linked to smuggler','#a78bfa','rgba(167,139,250,.14)']);
    if(!roles.length&&d.na)roles.push(['Linked to arrest','#22d3ee','rgba(34,211,238,.14)']);
    if(!roles.length)roles.push(['No recorded role','#6b7280','rgba(107,114,128,.12)']);
    // connection breakdown by tie type among visible links
    const byTie={};let nConn=0;
    links.forEach(l=>{if(l.source.idx===d.idx||l.target.idx===d.idx){nConn++;E.tie_types.forEach((t,i)=>{if(l.ty&(1<<i))byTie[t]=(byTie[t]||0)+1;});}});
    const conn=Object.entries(byTie).sort((a,b)=>b[1]-a[1]);
    side.innerHTML=
      '<div class="xp-label" style="font-size:10px;color:var(--text3)">Selected person</div>'+
      '<div class="xp-pid">'+esc(d.id)+'</div>'+
      '<div class="xp-badges">'+roles.map(r=>'<span class="xp-badge" style="color:'+r[1]+';background:'+r[2]+'">'+r[0]+'</span>').join('')+'</div>'+
      '<div class="xp-dgrid">'+
      '<div class="xp-drow"><span>Community</span><span>'+esc(d.cm||'—')+'</span></div>'+
      '<div class="xp-drow"><span>Community type</span><span>'+esc(E.community_types[d.ct].label)+'</span></div>'+
      '<div class="xp-drow"><span>Region</span><span>'+esc(E.regions[d.rg]||'—')+'</span></div>'+
      '<div class="xp-drow"><span>Segment</span><span>'+esc(E.segments[d.sg]||'—')+'</span></div>'+
      '<div class="xp-drow"><span>Citizenship</span><span>'+esc(E.citizenships[d.ci]||'—')+'</span></div>'+
      '<div class="xp-drow"><span>Age</span><span>'+esc(E.age_buckets[d.ag]||'—')+'</span></div>'+
      '<div class="xp-drow"><span>Crossings</span><span>'+F.n(d.cr)+'</span></div>'+
      '<div class="xp-drow"><span>Total connections</span><span>'+F.n(d.d)+'</span></div>'+
      '<div class="xp-drow"><span>Linked to smuggler</span><span>'+(d.ns?'yes':'no')+'</span></div>'+
      '<div class="xp-drow"><span>Linked to arrest</span><span>'+(d.na?'yes':'no')+'</span></div>'+
      '</div>'+
      (conn.length?'<div class="xp-conn"><div class="xp-ctitle">Visible connections</div>'+conn.map(c=>'<div class="xp-citem"><span>'+(TIE_LABELS[c[0]]||c[0])+'</span><span>'+c[1]+'</span></div>').join('')+'</div>':'')+
      '<button class="xp-btn" id="xp-drill">Drill into community '+esc(d.cm||'')+'</button>'+
      '<button class="xp-btn ghost" id="xp-clear">Clear selection</button>';
    const drill=side.querySelector('#xp-drill');if(drill)drill.addEventListener('click',()=>{doDrill(d.cm||'');});
    const clr=side.querySelector('#xp-clear');if(clr)clr.addEventListener('click',()=>{selectedNode=null;apply();renderSide(null);});
  }

  function clearFilters(){
    Object.values(catChips).forEach(c=>c.classList.remove('on'));
    typeChips.forEach(c=>c.classList.remove('on'));
    tieChips.forEach(c=>c.classList.add('on'));
    regSel.value='';segSel.value='';citSel.value='';ageSel.value='';
  }

  function doDrill(cid){
    clearFilters();
    drillCommId=cid;
    if(commSel.querySelector('option[value="'+cid+'"]'))commSel.value=cid;else commSel.value='';
    selectedNode=null;
    mode='focus';modeSeg.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x.dataset.v==='focus'));
    apply();
  }

  resetBtn.addEventListener('click',()=>{
    clearFilters();
    commSel.value='';drillCommId='';
    selectedNode=null;mode='highlight';modeSeg.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x.dataset.v==='highlight'));
    colorBy='type';colorSeg.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x.dataset.v==='type'));
    apply();renderSide(null);
  });

  // Cross-tab drill: Community Map -> Explorer
  window.addEventListener('drillCommunity', e => {
    const cid = e.detail && e.detail.communityId;
    if (!cid) return;
    doDrill(cid);
  });

  // Cross-tab focus: Detection Arms -> Explorer (select a specific person by id).
  // No-op if the person is not in the sampled explorer graph.
  window.explorerFocus = pid => {
    if (!pid) return false;
    const n = nodes.find(x => x.id === pid);
    if (!n) return false;
    clearFilters();
    selectedNode = n;
    apply();
    renderSide(n);
    return true;
  };

  apply();
}},
  """
