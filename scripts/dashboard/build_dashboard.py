#!/usr/bin/env python3
"""
build_dashboard.py  --  Generate a standalone HTML dashboard for a synthetic CBP graph corpus.

Usage:
    python -m scripts.dashboard.build_dashboard <corpus_dir>

Reads the corpus CSVs, computes the aggregations the v2 dashboard's 8 analytics tabs expect,
plus a new `explorer` block (sampled person-person graph with smuggling-role / connection /
community / attribute metadata), and writes <corpus_dir>/dashboard_standalone.html.

The HTML is produced by reusing the v2 dashboard as a template (the 8 analytics tabs stay
byte-identical) and splicing in the embedded DATA plus the new Community Explorer tab.
"""
import csv, json, os, sys, re, math, random, collections, datetime

from gnn.paths import REPO_ROOT

csv.field_size_limit(10 ** 8)
random.seed(13)

# ---------------------------------------------------------------------------
# Geographic centroids  (lon, lat)  -- used to place ports/origins on the map.
# ---------------------------------------------------------------------------
STATE_CENTROIDS = {
    "AL": (-86.8, 32.8), "AK": (-152.0, 64.0), "AZ": (-111.7, 34.3), "AR": (-92.4, 34.8),
    "CA": (-119.7, 37.2), "CO": (-105.5, 39.0), "CT": (-72.7, 41.6), "DE": (-75.5, 39.0),
    "DC": (-77.0, 38.9), "FL": (-81.7, 28.6), "GA": (-83.4, 32.6), "HI": (-157.5, 21.1),
    "ID": (-114.4, 44.4), "IL": (-89.2, 40.0), "IN": (-86.3, 39.9), "IA": (-93.5, 42.0),
    "KS": (-98.4, 38.5), "KY": (-84.9, 37.5), "LA": (-92.0, 31.0), "ME": (-69.2, 45.4),
    "MD": (-76.7, 39.0), "MA": (-71.8, 42.3), "MI": (-85.4, 44.3), "MN": (-94.3, 46.3),
    "MS": (-89.7, 32.7), "MO": (-92.5, 38.4), "MT": (-109.6, 47.0), "NE": (-99.8, 41.5),
    "NV": (-116.9, 39.3), "NH": (-71.6, 43.7), "NJ": (-74.7, 40.2), "NM": (-106.1, 34.4),
    "NY": (-75.5, 42.9), "NC": (-79.4, 35.6), "ND": (-100.3, 47.5), "OH": (-82.8, 40.3),
    "OK": (-97.5, 35.6), "OR": (-120.6, 43.9), "PA": (-77.8, 40.9), "RI": (-71.5, 41.7),
    "SC": (-80.9, 33.9), "SD": (-100.2, 44.4), "TN": (-86.4, 35.9), "TX": (-99.3, 31.5),
    "UT": (-111.7, 39.3), "VT": (-72.7, 44.1), "VA": (-78.8, 37.5), "WA": (-120.4, 47.4),
    "WV": (-80.6, 38.6), "WI": (-89.6, 44.6), "WY": (-107.6, 43.0),
    "PR": (-66.4, 18.2), "GU": (144.8, 13.4), "VI": (-64.8, 18.0), "AS": (-170.7, -14.3),
    "MP": (145.7, 15.2),
}
COUNTRY_CENTROIDS = {
    "United States": (-98.5, 39.0), "Mexico": (-102.5, 23.6), "Canada": (-106.3, 56.1),
    "Guatemala": (-90.2, 15.7), "Honduras": (-86.6, 15.2), "El Salvador": (-88.9, 13.8),
    "Colombia": (-74.3, 4.6), "Brazil": (-51.9, -14.2), "China": (104.2, 35.9),
    "India": (78.9, 20.6), "United Kingdom": (-1.5, 52.4), "Dominican Republic": (-70.2, 18.7),
    "Nicaragua": (-85.2, 12.9), "Peru": (-75.0, -9.2), "Ecuador": (-78.2, -1.8),
    "Venezuela": (-66.6, 6.4), "Cuba": (-79.0, 21.5), "Haiti": (-72.3, 19.0),
    "Jamaica": (-77.3, 18.1), "Philippines": (122.9, 12.9), "South Korea": (127.8, 36.5),
    "Japan": (138.3, 36.2), "Germany": (10.5, 51.2), "France": (2.2, 46.2),
    "Spain": (-3.7, 40.5), "Italy": (12.6, 41.9), "Nigeria": (8.7, 9.1),
    "Ireland": (-8.2, 53.4), "The Bahamas": (-77.4, 25.0), "Bermuda": (-64.8, 32.3),
    "Aruba": (-69.9, 12.5), "Costa Rica": (-84.1, 9.7), "Panama": (-80.1, 8.4),
    "Argentina": (-65.0, -38.4), "Australia": (133.8, -25.3), "Other": (-30.0, 25.0),
}

COMMUNITY_TYPE_LABELS = {
    "synthetic_interdiction_linked_cluster": "Interdiction-linked",
    "family_travel_cluster": "Family travel",
    "routine_commuter_cluster": "Routine commuter",
    "airport_passenger_cluster": "Airport passenger",
    "low_frequency_one_time_travelers": "Low-frequency / one-time",
    "high_frequency_benign_crossers": "High-frequency benign",
    "commercial_trucking_fleet_family": "Commercial trucking",
    "seasonal_worker_cluster": "Seasonal worker",
    "rental_reliant_cluster": "Rental-reliant",
    "prior_stops_no_seizures_cluster": "Prior stops, no seizures",
    "administrative_document_issue_cluster": "Admin document issue",
}

# Role bitmask
R_CARRIED, R_INTERDICT, R_SEIZED, R_ARRESTED = 1, 2, 4, 8
# Tie bitmask
T_ASSOC, T_FAMILY, T_ADDR, T_VEHICLE, T_BUSINESS, T_EVENT = 1, 2, 4, 8, 16, 32
TIE_TYPES = ["associated", "family", "co_address", "co_vehicle", "co_business", "co_event"]

# Sampling parameters
ROLE_SAMPLE_CAP = 3400        # cap on latent-smuggler role nodes (keeps the graph legible at v4 scale)
NEIGHBOR_PER_SEED = 5         # 1-hop neighbors pulled in per role person
NEIGHBOR_TOTAL_CAP = 1200
CONTEXT_TARGET = 4200         # final node target (role + neighbors + benign context)
MAX_NODES = 8000              # hard cap on rendered nodes (raised for community completeness)
DEGREE_CAP = 8                # max emitted links per node (strongest kept)
CLIQUE_CAP = 12               # skip co-* groups larger than this when forming clique ties


def p(*a):
    print(*a, flush=True)


ENTITY_RESOLUTION_CSS = r"""
.er-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:14px 0 18px}
@media(max-width:900px){.er-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.er-grid{grid-template-columns:1fr}}
.er-kpi{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px}
.er-kpi span{display:block;font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:.06em}
.er-kpi b{display:block;font-family:var(--font-mono);font-size:22px;color:var(--text1);margin-top:6px}
.er-story{color:var(--text2);line-height:1.55;max-width:980px}
.er-bars{display:grid;gap:8px;margin-top:12px;max-width:680px}
.er-bar{display:grid;grid-template-columns:180px 1fr 54px;gap:10px;align-items:center;font-size:12px;color:var(--text2)}
.er-track{height:8px;background:var(--elevated);border:1px solid var(--border);border-radius:999px;overflow:hidden}
.er-fill{height:100%;background:var(--accent)}
"""


ENTITY_RESOLUTION_JS = r"""entityResolution:{rendered:false,render(){
  const el=document.getElementById('tab-entityResolution');
  const ER=D.entity_resolution;
  if(!ER){el.innerHTML='<p style="color:var(--text3);padding:40px">No V7 entity-resolution summary available for this corpus.</p>';return;}
  const pct=v=>((Number(v||0)*100).toFixed(1)+'%');
  const n=v=>Number(v||0).toLocaleString();
  const section=makeSection(el,'Entity Resolution');
  makeNote(section,'V7 shows how identity fragmentation changes the graph layer. Deterministic ER uses exact same-document or same-event evidence; weak-link pairs are an oracle coverage slice defined from observable evidence only. No learned ER-GNN result has been produced yet, and truth columns remain evaluation labels rather than operational features.');
  const grid=document.createElement('div');grid.className='er-grid';section.appendChild(grid);
  [
    ['Observed records',n(ER.observed_records)],
    ['Canonical people',n(ER.canonical_persons)],
    ['Candidate links',n(ER.candidate_pairs)],
    ['True same-person links',n(ER.true_pairs)],
    ['Deterministic recall',pct(ER.deterministic_pair_recall)],
    ['Deterministic + weak-link oracle coverage',pct(ER.deterministic_plus_weak_link_oracle_pair_recall)],
    ['Weak-link true links',n(ER.weak_link_true_pairs)],
    ['Oracle true links',n(ER.oracle_true_pairs)],
  ].forEach(([label,value])=>{const box=document.createElement('div');box.className='er-kpi';box.innerHTML='<span>'+esc(label)+'</span><b>'+esc(value)+'</b>';grid.appendChild(box);});
  const story=document.createElement('p');story.className='er-story';story.textContent=ER.downstream_story||'';section.appendChild(story);
  const frag=ER.fragmentation_tiers||{};const total=Object.values(frag).reduce((a,b)=>a+Number(b||0),0)||1;
  const bars=document.createElement('div');bars.className='er-bars';section.appendChild(bars);
  Object.entries(frag).sort((a,b)=>Number(b[1])-Number(a[1])).forEach(([label,count])=>{
    const row=document.createElement('div');row.className='er-bar';
    const w=Math.max(2,Math.round(Number(count||0)/total*100));
    row.innerHTML='<span>'+esc(label.replaceAll("_"," "))+'</span><div class="er-track"><div class="er-fill" style="width:'+w+'%"></div></div><b>'+n(count)+'</b>';
    bars.appendChild(row);
  });
}}, 
"""


def load_entity_resolution_summary(corpus_dir):
    path = os.path.join(corpus_dir, "v7_er_recoverability_summary.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ===========================================================================
def main(corpus_dir):
    files = lambda n: os.path.join(corpus_dir, n)
    name = os.path.basename(os.path.normpath(corpus_dir))
    p(f"[build] corpus = {name}")

    # -------------------------------------------------------------------
    # 1. persons.csv  -> base attributes + person index
    # -------------------------------------------------------------------
    pid2idx = {}
    age = []; cit = []; reg = []; crossings = []; resloc = []
    air_x = []; land_x = []
    with open(files("persons.csv")) as f:
        for row in csv.DictReader(f):
            pid = row["person_id"]
            pid2idx[pid] = len(pid2idx)
            age.append(row.get("synthetic_age_bucket", "-") or "-")
            cit.append(row.get("citizenship_country", "-") or "-")
            reg.append(row.get("primary_border_region", "-") or "-")
            crossings.append(int(row.get("total_crossings") or 0))
            resloc.append(row.get("residence_location_id", "") or "")
    N = len(pid2idx)
    p(f"[build] persons = {N:,}")

    # -------------------------------------------------------------------
    # 2. persons_ground_truth.csv -> family / community / segment / roles
    # -------------------------------------------------------------------
    family = [""] * N; comm = [""] * N; ctype = [""] * N; seg = [""] * N
    role = [0] * N
    gt_path = files("persons_ground_truth.csv")
    if os.path.exists(gt_path):
        gt_file = gt_path
    else:
        # v2 corpus: ground truth columns are in persons.csv itself
        gt_file = files("persons.csv")
        p("[build] persons_ground_truth.csv not found — falling back to persons.csv")
    with open(gt_file) as f:
        for row in csv.DictReader(f):
            i = pid2idx.get(row["person_id"])
            if i is None:
                continue
            family[i] = row.get("family_id", "")
            comm[i] = row.get("ground_truth_community_id", "")
            ctype[i] = row.get("community_type", "")
            seg[i] = row.get("synthetic_traveler_segment", "-") or "-"
            if (row.get("ever_carried_contraband_flag", "").lower() == "true"):
                role[i] |= R_CARRIED
            if (row.get("is_member_of_interdiction_cluster", "").lower() == "true"):
                role[i] |= R_INTERDICT

    # -------------------------------------------------------------------
    # 3. arrests.csv + seizures.csv  -> roles + seizure/arrest aggregations
    # -------------------------------------------------------------------
    sa = {
        "drug_types": collections.Counter(), "detection_methods": collections.Counter(),
        "conveyance": collections.Counter(), "arrest_reasons": collections.Counter(),
        "arrest_charges": collections.Counter(), "arrest_dispositions": collections.Counter(),
        "monthly_seiz": collections.Counter(), "monthly_arr": collections.Counter(),
        "qty": [],
    }
    n_seized = 0
    with open(files("seizures.csv")) as f:
        for row in csv.DictReader(f):
            i = pid2idx.get(row.get("primary_person_id", ""))
            if i is not None and not (role[i] & R_SEIZED):
                role[i] |= R_SEIZED
            sa["drug_types"][row.get("drug_type", "Unknown")] += 1
            sa["detection_methods"][row.get("detection_context", "unknown")] += 1
            sa["conveyance"][row.get("conveyance_context", "unknown")] += 1
            try:
                sa["qty"].append(float(row.get("quantity_lbs") or 0))
            except ValueError:
                pass
            ts = row.get("event_timestamp_utc", "")
            if len(ts) >= 7:
                sa["monthly_seiz"][ts[:7]] += 1
    n_seized = sum(1 for r in role if r & R_SEIZED)
    n_arrested_rows = 0
    with open(files("arrests.csv")) as f:
        for row in csv.DictReader(f):
            i = pid2idx.get(row.get("person_id", ""))
            if i is not None:
                role[i] |= R_ARRESTED
            sa["arrest_reasons"][row.get("arrest_reason_category", "unknown")] += 1
            sa["arrest_charges"][row.get("charge_category_synthetic", "unknown")] += 1
            sa["arrest_dispositions"][row.get("disposition_status", "unknown")] += 1
            ts = row.get("event_timestamp_utc", "")
            if len(ts) >= 7:
                sa["monthly_arr"][ts[:7]] += 1
            n_arrested_rows += 1
    n_arrested = sum(1 for r in role if r & R_ARRESTED)
    n_carried = sum(1 for r in role if r & R_CARRIED)
    n_interdict = sum(1 for r in role if r & R_INTERDICT)
    p(f"[build] roles: carried={n_carried} interdiction={n_interdict} arrested={n_arrested} seized={n_seized}")

    # -------------------------------------------------------------------
    # 4. communities.csv  -> catalog + type aggregations
    # -------------------------------------------------------------------
    comm_meta = {}            # comm_id -> dict
    type_distribution = collections.Counter()
    sizes = []
    score_by_type = collections.defaultdict(list)
    with open(files("communities.csv")) as f:
        for row in csv.DictReader(f):
            cid = row["ground_truth_community_id"]
            t = row.get("community_type", "")
            try:
                sz = int(row.get("member_count") or 0)
            except ValueError:
                sz = 0
            try:
                score = float(row.get("latent_contraband_propensity") or 0)
            except ValueError:
                score = 0.0
            comm_meta[cid] = {
                "type": t, "region": row.get("home_region", "-"),
                "size": sz, "score": score,
                "eval": (row.get("is_positive_interdiction_eval_cluster", "").lower() == "true"),
            }
            type_distribution[t] += 1
            sizes.append(sz)
            score_by_type[t].append(score)

    # -------------------------------------------------------------------
    # 5. Stream edges.csv  -> type counts, node degree, person-person ties
    # -------------------------------------------------------------------
    edge_type_counts = collections.Counter()
    conn_pairs = collections.Counter()          # (src_type, tgt_type) -> count
    degree = collections.Counter()              # node_id -> degree
    assoc_pairs = []                            # list[(idx, idx)]
    family_edge_pairs = []                      # FAMILY_MEMBER edges from edges.csv
    biz_members = collections.defaultdict(list)  # business_id -> [idx]
    total_edges = 0
    with open(files("edges.csv")) as f:
        r = csv.reader(f)
        header = next(r)
        ix = {c: k for k, c in enumerate(header)}
        c_st, c_tt = ix["source_node_type"], ix["target_node_type"]
        c_s, c_t, c_et = ix["source_node_id"], ix["target_node_id"], ix["edge_type"]
        for row in r:
            total_edges += 1
            et = row[c_et]
            edge_type_counts[et] += 1
            s, t = row[c_s], row[c_t]
            degree[s] += 1
            degree[t] += 1
            conn_pairs[(row[c_st], row[c_tt])] += 1
            if et == "PERSON_ASSOCIATED_WITH_PERSON":
                a, b = pid2idx.get(s), pid2idx.get(t)
                if a is not None and b is not None and a != b:
                    assoc_pairs.append((a, b))
            elif et == "FAMILY_MEMBER":
                a, b = pid2idx.get(s), pid2idx.get(t)
                if a is not None and b is not None and a != b:
                    family_edge_pairs.append((a, b))
            elif et == "PERSON_LINKED_TO_BUSINESS":
                a = pid2idx.get(s)
                if a is not None:
                    biz_members[t].append(a)
    p(f"[build] edges = {total_edges:,}")

    # -------------------------------------------------------------------
    # 6. Stream crossing_events.csv  -> temporal / geo / outcomes + ties + flows
    # -------------------------------------------------------------------
    OUTCOME_KEYS = ["secondary", "search", "seizure", "arrest", "prosecution", "admin_action"]
    FLAG_COL = {
        "secondary": "secondary_referral_flag", "search": "search_flag",
        "seizure": "seizure_flag", "arrest": "arrest_flag",
        "prosecution": "prosecution_referral_flag", "admin_action": "administrative_action_flag",
    }
    monthly = collections.defaultdict(lambda: collections.Counter())
    by_fy = collections.Counter()
    by_dow = collections.Counter()
    by_hour = collections.Counter()
    dow_hour = collections.Counter()
    fy_region = collections.defaultdict(lambda: collections.Counter())
    split_counts = collections.Counter()
    outcome_counts = collections.Counter()

    def newcell():
        return {"total": 0, "secondary": 0, "search": 0, "seizure": 0, "arrest": 0}

    by_region = collections.defaultdict(newcell)
    by_office = collections.defaultdict(newcell)
    by_port = collections.defaultdict(lambda: {"name": "", "region": "", "office": "",
                                               "state": "", "total": 0, "secondary": 0, "seizure": 0})
    by_segment = collections.defaultdict(newcell)
    by_mode = collections.defaultdict(newcell)
    by_category = collections.defaultdict(newcell)
    by_citizenship = collections.defaultdict(newcell)
    by_direction = collections.defaultdict(newcell)
    by_ctype_out = collections.defaultdict(lambda: newcell())
    risk_hist = collections.Counter()
    port_state_volume = collections.Counter()
    dest_state_volume = collections.Counter()
    origin_state = collections.Counter()         # (origin, state)
    origin_port = collections.Counter()          # (origin, port_code)
    origin_port_mode = collections.Counter()     # (origin, port_code, mode)
    routes = collections.Counter()               # (origin, dest_state)
    port_routes = collections.Counter()          # (port_code, dest_state)
    port_info = {}                               # port_code -> (name, state, region, office)

    vehicle_members = collections.defaultdict(set)   # vehicle_id -> set(idx)
    event_ties = collections.Counter()              # (a,b) -> count  (co-event)
    comm_crossing_state = collections.defaultdict(lambda: collections.Counter())  # comm_id -> {state: count}
    comm_crossing_fo = collections.defaultdict(lambda: collections.Counter())     # comm_id -> {field_office: count}
    state_unique_travelers = collections.defaultdict(set)   # state -> set(person_idx)
    state_outcomes = collections.defaultdict(lambda: {"total": 0, "secondary": 0, "seizure": 0, "arrest": 0})
    state_citizenships = collections.defaultdict(lambda: collections.Counter())  # state -> {citizenship: count}
    state_dest_travelers = collections.defaultdict(set)  # dest_state -> set(person_idx)
    state_modes = collections.defaultdict(lambda: collections.Counter())  # state -> {mode: count}
    total_events = 0

    with open(files("crossing_events.csv")) as f:
        r = csv.reader(f)
        header = next(r)
        ix = {c: k for k, c in enumerate(header)}

        def g(row, col):
            k = ix.get(col)
            return row[k] if k is not None and k < len(row) else ""

        for row in r:
            total_events += 1
            ts = g(row, "event_timestamp_utc")
            month = ts[:7] if len(ts) >= 7 else "?"
            region = g(row, "region")
            office = g(row, "field_office")
            state = g(row, "state")
            pcode = g(row, "port_code")
            pname = g(row, "port_of_entry")
            mode = g(row, "mode_of_transportation")
            cat = g(row, "travel_category")
            direction = g(row, "direction")
            dow = g(row, "day_of_week")
            fy = g(row, "fiscal_year")
            hour = g(row, "hour_of_day")
            citc = g(row, "citizenship_country")
            origin = g(row, "origin_country")
            dest = g(row, "destination_state")
            split = g(row, "data_split")
            disp = g(row, "synthetic_risk_score_pre_outcome")
            ppid = g(row, "primary_person_id")
            vid = g(row, "vehicle_id")

            flags = {k: (g(row, FLAG_COL[k]).lower() == "true") for k in OUTCOME_KEYS}
            for k in OUTCOME_KEYS:
                if flags[k]:
                    outcome_counts[k] += 1
            mrow = monthly[month]
            mrow["total"] += 1
            for k in ("secondary", "search", "seizure", "arrest"):
                if flags[k]:
                    mrow[k] += 1
            if fy:
                by_fy[fy] += 1
                if region:
                    fy_region[fy][region] += 1
            if dow:
                by_dow[dow] += 1
            if hour != "":
                try:
                    hh = int(hour)
                    by_hour[hh] += 1
                    if dow:
                        dow_hour[(dow, hh)] += 1
                except ValueError:
                    pass
            if split:
                split_counts[split] += 1

            def addcell(d):
                d["total"] += 1
                for k in ("secondary", "search", "seizure", "arrest"):
                    if flags[k]:
                        d[k] += 1

            if region:
                addcell(by_region[region])
            if office:
                addcell(by_office[office])
            if cat:
                addcell(by_category[cat])
            if mode:
                addcell(by_mode[mode])
            if citc:
                addcell(by_citizenship[citc])
            if direction:
                addcell(by_direction[direction])
            # segment + community-type via primary person
            pi = pid2idx.get(ppid)
            if pi is not None:
                if seg[pi]:
                    addcell(by_segment[seg[pi]])
                if ctype[pi]:
                    addcell(by_ctype_out[ctype[pi]])
                # community → geographic location tracking
                c_id = comm[pi]
                if c_id:
                    if state:
                        comm_crossing_state[c_id][state] += 1
                    if office:
                        comm_crossing_fo[c_id][office] += 1
            if pcode:
                pr = by_port[pcode]
                pr["name"] = pname or pr["name"]
                pr["region"] = region or pr["region"]
                pr["office"] = office or pr["office"]
                pr["state"] = state or pr["state"]
                pr["total"] += 1
                if flags["secondary"]:
                    pr["secondary"] += 1
                if flags["seizure"]:
                    pr["seizure"] += 1
                port_info[pcode] = (pname, state, region, office)
            # risk histogram
            try:
                rs = float(disp)
                b = min(11, int(rs * 12))
                risk_hist[b] += 1
            except (ValueError, TypeError):
                pass
            if state:
                port_state_volume[state] += 1
                so = state_outcomes[state]
                so["total"] += 1
                if flags["secondary"]: so["secondary"] += 1
                if flags["seizure"]: so["seizure"] += 1
                if flags["arrest"]: so["arrest"] += 1
                if pi is not None:
                    state_unique_travelers[state].add(pi)
                if citc:
                    state_citizenships[state][citc] += 1
                if mode:
                    state_modes[state][mode] += 1
            if dest:
                dest_state_volume[dest] += 1
                if pi is not None:
                    state_dest_travelers[dest].add(pi)
            if origin and state:
                origin_state[(origin, state)] += 1
            if origin and pcode:
                origin_port[(origin, pcode)] += 1
                if mode:
                    origin_port_mode[(origin, pcode, mode)] += 1
            if origin and dest:
                routes[(origin, dest)] += 1
            if pcode and dest:
                port_routes[(pcode, dest)] += 1

            # ---- ties: co-vehicle, co-event ----
            party = []
            if pi is not None:
                party.append(pi)
            cot = g(row, "co_traveler_person_ids")
            if cot:
                for tok in cot.split(";"):
                    j = pid2idx.get(tok.strip())
                    if j is not None:
                        party.append(j)
            if vid and pi is not None:
                vehicle_members[vid].add(pi)
                for j in party:
                    if j != pi:
                        vehicle_members[vid].add(j)
            if len(party) > 1:
                party = party[:CLIQUE_CAP]
                for a in range(len(party)):
                    for b in range(a + 1, len(party)):
                        x, y = party[a], party[b]
                        if x != y:
                            event_ties[(min(x, y), max(x, y))] += 1
    p(f"[build] events = {total_events:,}")

    # -------------------------------------------------------------------
    # 6a. Location→state map + resident counts per state
    # -------------------------------------------------------------------
    loc_state = {}
    with open(files("locations.csv")) as f:
        for row in csv.DictReader(f):
            lid = row.get("location_id", "")
            st = row.get("state", "")
            if lid and st:
                loc_state[lid] = st
    residents_per_state = collections.Counter()
    resident_smugglers_per_state = collections.Counter()
    resident_arrested_per_state = collections.Counter()
    for i in range(N):
        st = loc_state.get(resloc[i], "")
        if st:
            residents_per_state[st] += 1
            if role[i] & R_CARRIED:
                resident_smugglers_per_state[st] += 1
            if role[i] & R_ARRESTED:
                resident_arrested_per_state[st] += 1
    p(f"[build] location→state map: {len(loc_state):,} locations, residents in {len(residents_per_state)} states")

    # -------------------------------------------------------------------
    # 6b. Build community_map block (community → geographic locations)
    # -------------------------------------------------------------------
    FIELD_OFFICE_REGIONS = {
        "SAN DIEGO": "Southern Border", "LAREDO": "Southern Border",
        "EL PASO": "Southern Border", "TUCSON": "Southern Border",
        "HOUSTON": "Coastal/Interior", "NEW YORK": "Coastal/Interior",
        "MIAMI": "Coastal/Interior", "LOS ANGELES": "Coastal/Interior",
        "SAN FRANCISCO": "Coastal/Interior", "CHICAGO": "Coastal/Interior",
        "ATLANTA": "Coastal/Interior", "BALTIMORE": "Coastal/Interior",
        "TAMPA": "Coastal/Interior", "SAN JUAN": "Coastal/Interior",
        "NEW ORLEANS": "Coastal/Interior",
        "BUFFALO": "Northern Border", "DETROIT": "Northern Border",
        "BOSTON": "Northern Border", "SEATTLE": "Northern Border",
        "PORTLAND": "Northern Border",
        "PRECLEARANCE": "Preclearance",
    }

    # Determine home_region for each state (dominant region of its events)
    state_region_votes = collections.defaultdict(lambda: collections.Counter())
    for pc, info in port_info.items():
        pname, pstate, pregion, poffice = info
        if pstate and pregion:
            state_region_votes[pstate][pregion] += by_port.get(pc, {}).get("total", 0)
    state_home_region = {}
    for st, votes in state_region_votes.items():
        state_home_region[st] = votes.most_common(1)[0][0] if votes else "Coastal/Interior"

    # by_state: aggregate communities seen in each state
    cm_by_state = {}
    all_sts = set(s for cid_states in comm_crossing_state.values() for s in cid_states)
    all_sts.update(residents_per_state.keys())
    all_sts.update(state_outcomes.keys())
    if "" in all_sts:
        all_sts.remove("")
    for st in sorted(all_sts):
        comms_in_state = []
        type_dist = collections.Counter()
        scores = []
        fo_set = set()
        for cid, st_counts in comm_crossing_state.items():
            if st not in st_counts:
                continue
            meta = comm_meta.get(cid, {})
            t = meta.get("type", "")
            sc = meta.get("score", 0.0)
            sz = meta.get("size", 0)
            if t:
                type_dist[t] += 1
            scores.append(sc)
            comms_in_state.append({"id": cid, "type": t, "size": sz, "score": round(sc, 4)})
            # track field offices for this state
            for fo_name in comm_crossing_fo.get(cid, {}):
                fo_set.add(fo_name)
        comms_in_state.sort(key=lambda c: -c["score"])
        coords = STATE_CENTROIDS.get(st)
        so = state_outcomes.get(st, {"total": 0, "secondary": 0, "seizure": 0, "arrest": 0})
        n_unique = len(state_unique_travelers.get(st, set()))
        n_residents = residents_per_state.get(st, 0)
        n_dest = len(state_dest_travelers.get(st, set()))
        top_cit = state_citizenships.get(st, collections.Counter()).most_common(5)
        top_modes = state_modes.get(st, collections.Counter()).most_common(5)
        state_ports = [(pc, v) for pc, v in by_port.items() if v.get("state") == st]
        state_ports.sort(key=lambda x: -x[1]["total"])
        cm_by_state[st] = {
            "community_count": len(comms_in_state),
            "type_distribution": dict(type_dist),
            "avg_risk_score": round(sum(scores) / (len(scores) or 1), 4),
            "top_communities": comms_in_state[:25],
            "home_region": state_home_region.get(st, "Coastal/Interior"),
            "field_offices": sorted(fo_set),
            "lat": coords[1] if coords else None,
            "lon": coords[0] if coords else None,
            "total_crossings": so["total"],
            "unique_travelers": n_unique,
            "resident_count": n_residents,
            "resident_smugglers": resident_smugglers_per_state.get(st, 0),
            "resident_arrested": resident_arrested_per_state.get(st, 0),
            "visitor_count": max(0, n_unique - n_residents),
            "destination_travelers": n_dest,
            "secondary_count": so["secondary"],
            "seizure_count": so["seizure"],
            "arrest_count": so["arrest"],
            "top_citizenships": [{"name": c, "count": n} for c, n in top_cit],
            "top_modes": [{"name": m, "count": n} for m, n in top_modes],
            "top_ports": [{"code": pc, "name": v["name"], "total": v["total"],
                           "seizure_rate": round(v.get("seizure", 0) / (v["total"] or 1), 4)}
                          for pc, v in state_ports[:5]],
        }

    # by_region: aggregate
    cm_by_region = {}
    region_comms = collections.defaultdict(set)
    for cid, meta in comm_meta.items():
        hr = meta.get("region", "")
        if hr:
            region_comms[hr].add(cid)
    for rg, cids in region_comms.items():
        type_dist = collections.Counter()
        for cid in cids:
            t = comm_meta[cid].get("type", "")
            if t:
                type_dist[t] += 1
        cm_by_region[rg] = {"community_count": len(cids), "type_distribution": dict(type_dist)}

    # by_field_office
    cm_by_fo = {}
    for fo_name in sorted(set(fo for cid_fos in comm_crossing_fo.values() for fo in cid_fos)):
        type_dist = collections.Counter()
        cids_in_fo = set()
        for cid, fo_counts in comm_crossing_fo.items():
            if fo_name in fo_counts:
                cids_in_fo.add(cid)
                t = comm_meta.get(cid, {}).get("type", "")
                if t:
                    type_dist[t] += 1
        cm_by_fo[fo_name] = {"community_count": len(cids_in_fo), "type_distribution": dict(type_dist)}

    community_map = {
        "by_state": cm_by_state,
        "by_region": cm_by_region,
        "by_field_office": cm_by_fo,
        "all_community_types": sorted(type_distribution.keys()),
        "state_centroids": {k: list(v) for k, v in STATE_CENTROIDS.items()},
    }
    p(f"[build] community_map: {len(cm_by_state)} states, {len(cm_by_fo)} field offices")

    # -------------------------------------------------------------------
    # 7. Entity files -> counts and node-type totals
    # -------------------------------------------------------------------
    def count_rows(fn):
        with open(files(fn)) as f:
            return sum(1 for _ in f) - 1

    def col_counter(fn, col, top=None):
        c = collections.Counter()
        with open(files(fn)) as f:
            for row in csv.DictReader(f):
                c[row.get(col, "-") or "-"] += 1
        return c

    vehicle_types = col_counter("vehicles.csv", "vehicle_type")
    document_types = col_counter("documents.csv", "document_type")
    n_vehicles = sum(vehicle_types.values())
    n_documents = sum(document_types.values())
    n_locations = count_rows("locations.csv")
    n_business = count_rows("businesses.csv")
    n_officers = count_rows("officers_or_teams.csv")
    n_communities = len(comm_meta)

    age_buckets = col_counter("persons.csv", "synthetic_age_bucket")
    citizen_counts = collections.Counter(cit)
    segment_counts = collections.Counter(s for s in seg if s)

    node_type_counts = {
        "person": N, "event": total_events, "document": n_documents, "location": n_locations,
        "officer_team": n_officers, "vehicle": n_vehicles, "business": n_business,
        "arrest": n_arrested_rows, "seizure": int(sum(sa["drug_types"].values())),
    }

    # ===================================================================
    #  Build person-person tie graph
    # ===================================================================
    p("[build] assembling person-person ties...")
    ties = {}   # (a,b) -> [bits, weight]

    def add_tie(a, b, bit, w=1.0):
        if a == b:
            return
        k = (a, b) if a < b else (b, a)
        e = ties.get(k)
        if e is None:
            ties[k] = [bit, w]
        else:
            e[0] |= bit
            e[1] += w

    for a, b in assoc_pairs:
        add_tie(a, b, T_ASSOC, 2.0)
    for a, b in family_edge_pairs:
        add_tie(a, b, T_FAMILY, 2.0)

    def clique(members, bit, w=1.0):
        m = list(dict.fromkeys(members))
        if len(m) < 2 or len(m) > CLIQUE_CAP:
            return
        for i in range(len(m)):
            for j in range(i + 1, len(m)):
                add_tie(m[i], m[j], bit, w)

    fam_groups = collections.defaultdict(list)
    for i in range(N):
        if family[i]:
            fam_groups[family[i]].append(i)
    for members in fam_groups.values():
        clique(members, T_FAMILY, 1.5)

    addr_groups = collections.defaultdict(list)
    for i in range(N):
        if resloc[i]:
            addr_groups[resloc[i]].append(i)
    for members in addr_groups.values():
        clique(members, T_ADDR, 1.0)

    for members in vehicle_members.values():
        clique(list(members), T_VEHICLE, 1.0)
    for members in biz_members.values():
        clique(members, T_BUSINESS, 0.8)
    for (a, b), c in event_ties.items():
        add_tie(a, b, T_EVENT, float(c))

    p(f"[build] raw person-person ties = {len(ties):,}")

    # adjacency (full, for accurate neighbor flags + sampling)
    adj = collections.defaultdict(list)
    for (a, b), (bits, w) in ties.items():
        adj[a].append((b, w))
        adj[b].append((a, w))

    # neighbor-of-smuggler / neighbor-of-arrested over full graph
    is_smug = [bool(role[i] & (R_CARRIED | R_INTERDICT)) for i in range(N)]
    is_arr = [bool(role[i] & R_ARRESTED) for i in range(N)]
    nb_smug = [False] * N
    nb_arr = [False] * N
    for a in adj:
        for (b, _w) in adj[a]:
            if is_smug[b]:
                nb_smug[a] = True
            if is_arr[b]:
                nb_arr[a] = True

    # ===================================================================
    #  Sample node set:  role people + capped neighbors + benign context
    # ===================================================================
    # Always show every detected case (arrests + seizures); sample the latent smugglers.
    detected = set(i for i in range(N) if role[i] & (R_SEIZED | R_ARRESTED))
    node_set = set(detected)
    smug = [i for i in range(N) if (role[i] & (R_CARRIED | R_INTERDICT)) and i not in node_set]
    random.shuffle(smug)
    for i in smug[:ROLE_SAMPLE_CAP]:
        node_set.add(i)
    role_nodes = list(node_set)

    # 1-hop neighbors of role people
    neigh_added = 0
    for s in role_nodes:
        if neigh_added >= NEIGHBOR_TOTAL_CAP or len(node_set) >= MAX_NODES:
            break
        for (b, _w) in sorted(adj.get(s, []), key=lambda x: -x[1])[:NEIGHBOR_PER_SEED]:
            if b not in node_set:
                node_set.add(b)
                neigh_added += 1
                if neigh_added >= NEIGHBOR_TOTAL_CAP or len(node_set) >= MAX_NODES:
                    break

    # benign context: stratified by community type
    target = min(CONTEXT_TARGET, MAX_NODES)
    if len(node_set) < target:
        pool = [i for i in range(N) if i not in node_set]
        random.shuffle(pool)
        by_type_pool = collections.defaultdict(list)
        for i in pool:
            by_type_pool[ctype[i]].append(i)
        need = target - len(node_set)
        types = [t for t in by_type_pool if t]
        ti = 0
        while need > 0 and types:
            t = types[ti % len(types)]
            if by_type_pool[t]:
                node_set.add(by_type_pool[t].pop())
                need -= 1
            else:
                types.remove(t)
                continue
            ti += 1
    # Community-complete expansion: if any member of a community is sampled,
    # include ALL members so focus mode shows the full community.
    comm_groups = collections.defaultdict(list)
    for i in range(N):
        if comm[i]:
            comm_groups[comm[i]].append(i)
    sampled_comms = set()
    for i in node_set:
        if comm[i]:
            sampled_comms.add(comm[i])
    pre_complete = len(node_set)
    for c in sampled_comms:
        for i in comm_groups[c]:
            node_set.add(i)
    p(f"[build] explorer nodes = {len(node_set):,} ({len(node_set) - pre_complete:,} added for community completeness)")

    # index spaces for compact encoding
    ct_list = sorted(type_distribution, key=lambda t: -type_distribution[t])
    ct_idx = {t: k for k, t in enumerate(ct_list)}
    reg_list = sorted(set(reg[i] for i in node_set if reg[i]))
    reg_idx = {x: k for k, x in enumerate(reg_list)}
    seg_list = sorted(set(seg[i] for i in node_set if seg[i]))
    seg_idx = {x: k for k, x in enumerate(seg_list)}
    cit_top = [c for c, _ in citizen_counts.most_common(15)]
    cit_set = set(cit_top)
    cit_list = cit_top + ["Other"]
    cit_idx = {x: k for k, x in enumerate(cit_top)}
    other_cit = len(cit_top)
    age_list = sorted(set(age[i] for i in node_set if age[i]))
    age_idx = {x: k for k, x in enumerate(age_list)}

    GNN_FACTOR_LABELS = [
        "Community risk score",
        "Neighbor risk proximity",
        "Connection density",
        "Crossing history",
        "Community archetype",
    ]
    GNN_STATUS_LABELS = ["Caught by GNN", "Missed by GNN", "False positive", "Not predicted"]
    GNN_THRESHOLD = 0.62
    GNN_TYPE_FACTOR = {
        "synthetic_interdiction_linked_cluster": 0.90,
        "prior_stops_no_seizures_cluster": 0.74,
        "rental_reliant_cluster": 0.58,
        "commercial_trucking_fleet_family": 0.52,
        "family_travel_cluster": 0.34,
        "routine_commuter_cluster": 0.24,
        "high_frequency_benign_crossers": 0.21,
        "airport_passenger_cluster": 0.18,
        "seasonal_worker_cluster": 0.16,
        "administrative_document_issue_cluster": 0.14,
        "low_frequency_one_time_travelers": 0.10,
    }

    def gnn_features(i):
        meta = comm_meta.get(comm[i], {})
        comm_score = float(meta.get("score", 0.0) or 0.0)
        neighbor_score = (0.65 if nb_smug[i] else 0.0) + (0.35 if nb_arr[i] else 0.0)
        neighbor_score = min(1.0, neighbor_score)
        density_score = min(1.0, len(adj.get(i, [])) / 12.0)
        crossing_score = min(1.0, crossings[i] / 18.0)
        type_score = GNN_TYPE_FACTOR.get(ctype[i], 0.20)
        jitter = (((i * 1103515245 + 12345) & 0x7fffffff) % 101 - 50) / 1000.0
        raw = (
            -1.05
            + 2.25 * comm_score
            + 0.82 * neighbor_score
            + 0.45 * density_score
            + 0.32 * crossing_score
            + 0.92 * type_score
            + jitter
        )
        prob = 1.0 / (1.0 + math.exp(-raw))
        factors = [
            round(comm_score, 3),
            round(neighbor_score, 3),
            round(density_score, 3),
            round(crossing_score, 3),
            round(type_score, 3),
        ]
        return prob, factors

    def gnn_explanation(i, prob, factors):
        strongest = sorted(zip(GNN_FACTOR_LABELS, factors), key=lambda x: -x[1])[:3]
        pieces = [f"{label.lower()} {value:.2f}" for label, value in strongest if value > 0]
        if not pieces:
            pieces = ["no strong graph risk factors"]
        return (
            f"Predicted stop probability {prob:.2f}. The synthetic GNN is driven most by "
            + ", ".join(pieces)
            + ". This means the person sits in a graph neighborhood whose community pattern, nearby risky ties, "
              "and observed crossing history resemble stopped or interdiction-linked synthetic examples."
        )

    idx2pid = [None] * N
    for pid, i in pid2idx.items():
        idx2pid[i] = pid

    node_order = sorted(node_set)
    node_pos = {i: k for k, i in enumerate(node_order)}   # person idx -> node array position
    enodes = []
    gnn_summary = collections.Counter()
    gnn_top_people = []
    for i in node_order:
        prob, factors = gnn_features(i)
        predicted = prob >= GNN_THRESHOLD
        target = bool(role[i] & (R_CARRIED | R_INTERDICT))
        if target and predicted:
            status = 0
            gnn_summary["gnn_caught"] += 1
        elif target and not predicted:
            status = 1
            gnn_summary["missed_by_gnn"] += 1
        elif (not target) and predicted:
            status = 2
            gnn_summary["false_positive"] += 1
        else:
            status = 3
            gnn_summary["not_predicted"] += 1
        if predicted:
            gnn_summary["predicted_stop"] += 1
            gnn_top_people.append((prob, len(enodes), idx2pid[i], status))
        enodes.append({
            "id": idx2pid[i],
            "ct": ct_idx.get(ctype[i], 0),
            "rg": reg_idx.get(reg[i], 0),
            "sg": seg_idx.get(seg[i], 0),
            "ci": cit_idx.get(cit[i], other_cit),
            "ag": age_idx.get(age[i], 0),
            "cr": crossings[i],
            "r": role[i],
            "ns": 1 if nb_smug[i] else 0,
            "na": 1 if nb_arr[i] else 0,
            "cm": comm[i],
            "d": len(adj.get(i, [])),
            "g": 1 if predicted else 0,
            "gp": round(prob, 3),
            "gk": status,
            "gx": factors,
            "ge": gnn_explanation(i, prob, factors) if predicted else "",
        })

    # emit links restricted to node set, degree-capped (strongest kept)
    cand = []
    for (a, b), (bits, w) in ties.items():
        if a in node_pos and b in node_pos:
            cand.append((w, node_pos[a], node_pos[b], bits))
    cand.sort(reverse=True)
    deg_used = collections.Counter()
    elinks = []
    for (w, s, t, bits) in cand:
        if deg_used[s] >= DEGREE_CAP or deg_used[t] >= DEGREE_CAP:
            continue
        elinks.append([s, t, bits, round(w, 2)])
        deg_used[s] += 1
        deg_used[t] += 1

    # community catalog (only communities present among sampled nodes, ranked)
    comm_present = collections.defaultdict(lambda: {"size": 0, "carried": 0, "arrested": 0, "seized": 0})
    for i in sorted(node_set):
        c = comm[i]
        if not c:
            continue
        cp = comm_present[c]
        cp["size"] += 1
        if role[i] & (R_CARRIED | R_INTERDICT):
            cp["carried"] += 1
        if role[i] & R_ARRESTED:
            cp["arrested"] += 1
        if role[i] & R_SEIZED:
            cp["seized"] += 1
    comm_catalog = []
    for c, v in comm_present.items():
        meta = comm_meta.get(c, {})
        comm_catalog.append({
            "id": c, "ct": ct_idx.get(meta.get("type", ""), 0),
            "rg": reg_idx.get(meta.get("region", ""), 0) if meta.get("region", "") in reg_idx else 0,
            "size": v["size"], "carried": v["carried"], "arrested": v["arrested"], "seized": v["seized"],
            "score": round(meta.get("score", 0.0), 3),
        })
    comm_catalog.sort(key=lambda x: (-(x["carried"] + x["arrested"] + x["seized"]), -x["size"]))

    gnn_top_people.sort(reverse=True)
    explorer = {
        "meta": {
            "total_people": N, "sampled_nodes": len(enodes), "total_links": len(elinks),
            "n_carried": n_carried, "n_interdiction": n_interdict,
            "n_arrested": n_arrested, "n_seized": n_seized,
            "n_undetected": sum(1 for i in range(N) if (role[i] & R_CARRIED) and not (role[i] & (R_SEIZED | R_ARRESTED))),
            "n_neighbor_smug": sum(1 for x in nb_smug if x),
            "n_neighbor_arr": sum(1 for x in nb_arr if x),
        },
        "community_types": [{"code": t, "label": COMMUNITY_TYPE_LABELS.get(t, t.replace("_", " ")),
                             "count": type_distribution[t]} for t in ct_list],
        "regions": reg_list, "segments": seg_list, "citizenships": cit_list, "age_buckets": age_list,
        "tie_types": TIE_TYPES,
        "nodes": enodes, "links": elinks,
        "communities": comm_catalog[:400],
        "gnn": {
            "model": "Synthetic GraphSAGE stop-risk demo",
            "target": "Predicted stop / secondary-inspection referral for synthetic people",
            "threshold": GNN_THRESHOLD,
            "factor_labels": GNN_FACTOR_LABELS,
            "status_labels": GNN_STATUS_LABELS,
            "summary": {
                "predicted_stop": gnn_summary["predicted_stop"],
                "gnn_caught": gnn_summary["gnn_caught"],
                "missed_by_gnn": gnn_summary["missed_by_gnn"],
                "false_positive": gnn_summary["false_positive"],
                "not_predicted": gnn_summary["not_predicted"],
            },
            "top_people": [
                {"idx": pos, "id": pid, "probability": round(prob, 3), "status": status}
                for prob, pos, pid, status in gnn_top_people[:50]
            ],
            "explanation_note": (
                "GNNExplainer-style factors are normalized synthetic feature contributions. "
                "LLM text is generated from those factors and is not based on real people or real enforcement data."
            ),
        },
    }

    # ===================================================================
    #  Assemble the analytics DATA (v2 schema)
    # ===================================================================
    def rate(d):
        out = dict(d)
        tot = d["total"] or 1
        for k in ("secondary", "search", "seizure", "arrest"):
            out[f"{k}_rate"] = round(d[k] / tot, 4)
        return out

    months_sorted = sorted(m for m in monthly if m != "?")
    monthly_series = [{"month": m, "total": monthly[m]["total"], "secondary": monthly[m]["secondary"],
                       "search": monthly[m]["search"], "seizure": monthly[m]["seizure"],
                       "arrest": monthly[m]["arrest"]} for m in months_sorted]

    # actual port-of-entry coordinates [lon, lat]
    PORT_COORDINATES = {
        "0104":(-70.26,45.63),"0106":(-67.84,46.13),"0109":(-68.33,47.36),"0115":(-67.28,45.19),
        "0209":(-72.10,44.98),"0212":(-73.10,44.98),"0417":(-71.02,42.37),
        "0701":(-75.49,44.69),"0704":(-74.89,44.93),"0708":(-75.92,44.33),"0712":(-73.36,44.99),
        "0901":(-79.05,43.10),"1108":(-75.24,39.87),"1512":(-80.94,35.21),"1704":(-84.43,33.64),
        "1808":(-81.31,28.43),
        "2301":(-97.50,25.91),"2302":(-100.90,29.37),"2303":(-100.50,28.71),"2304":(-99.50,27.50),
        "2305":(-98.26,26.10),"2307":(-98.82,26.38),"2309":(-97.96,26.06),"2310":(-99.01,26.41),
        "2401":(-106.32,31.69),"2402":(-106.49,31.76),"2403":(-104.35,29.56),"2404":(-106.09,31.44),
        "2406":(-107.64,31.83),"2408":(-106.64,31.87),
        "2502":(-114.70,32.72),"2503":(-115.50,32.68),"2504":(-117.03,32.54),"2505":(-116.63,32.57),
        "2506":(-117.05,32.57),"2507":(-115.42,32.67),"2582":(-117.04,32.55),
        "2601":(-109.55,31.34),"2602":(-112.82,31.88),"2603":(-109.95,31.33),"2604":(-110.94,31.34),
        "2605":(-112.01,33.44),"2608":(-114.78,32.49),
        "2720":(-118.41,33.94),"2801":(-122.38,37.62),"2904":(-122.60,45.59),
        "3004":(-122.75,48.99),"3009":(-122.26,49.00),"3017":(-123.07,48.98),"3023":(-118.15,48.70),
        "3029":(-122.31,47.45),"3205":(-157.92,21.33),
        "3302":(-116.18,48.99),"3307":(-104.67,39.85),"3310":(-111.97,48.99),"3318":(-115.06,48.99),
        "3401":(-97.24,48.97),"3501":(-93.22,44.88),"3604":(-93.41,48.60),"3613":(-89.69,47.96),
        "3801":(-83.04,42.31),"3802":(-82.42,42.97),"3803":(-84.35,46.50),"3807":(-83.35,42.21),
        "3901":(-87.91,41.97),
        "4601":(-74.17,40.69),"4701":(-73.78,40.64),"5206":(-80.28,25.80),"5210":(-80.15,26.07),
        "5309":(-95.34,29.99),"5401":(-77.45,38.95),"5501":(-97.04,32.90),
        "7423":(-77.47,25.04),"7424":(-70.01,12.50),"7541":(-6.27,53.42),
        "7922":(-123.18,49.19),"7923":(-114.01,51.13),"7925":(-73.74,45.47),"7926":(-79.63,43.68),
    }
    def port_coords(port_code, state):
        pc = PORT_COORDINATES.get(port_code)
        if pc:
            return pc[1], pc[0]
        c = STATE_CENTROIDS.get(state)
        if not c:
            return None, None
        return c[1] + random.uniform(-0.25, 0.25), c[0] + random.uniform(-0.25, 0.25)

    top_ports = []
    for pc, v in sorted(by_port.items(), key=lambda kv: -kv[1]["total"])[:50]:
        lat, lon = port_coords(pc, v["state"])
        top_ports.append({
            "port_code": pc, "name": v["name"], "region": v["region"], "field_office": v["office"],
            "state": v["state"], "total": v["total"],
            "secondary_rate": round(v["secondary"] / (v["total"] or 1), 4),
            "seizure_rate": round(v["seizure"] / (v["total"] or 1), 4),
            "lat": lat, "lon": lon,
        })

    # origin->port->mode flows with coords (for the map)
    flows = []
    for (origin, pc, mode), c in origin_port_mode.most_common(500):
        info = port_info.get(pc, ("", "", "", ""))
        pname, pstate, pregion, poffice = info
        oc = COUNTRY_CENTROIDS.get(origin)
        sc = STATE_CENTROIDS.get(pstate)
        if not oc or not sc:
            continue
        plat, plon = port_coords(pc, pstate)
        if plat is None:
            plat, plon = sc[1], sc[0]
        flows.append({
            "origin": origin, "port_code": pc, "port_name": pname, "state": pstate,
            "region": pregion, "field_office": poffice, "mode": mode, "count": c,
            "origin_lon": oc[0], "origin_lat": oc[1],
            "port_lon": plon, "port_lat": plat,
        })

    origin_to_port_state = [{"origin": o, "state": s, "count": c}
                            for (o, s), c in origin_state.most_common(100)]
    origin_to_port = []
    for (o, pc), c in origin_port.most_common(200):
        info = port_info.get(pc, ("", "", "", ""))
        origin_to_port.append({"origin": o, "port_code": pc, "port_name": info[0], "state": info[1],
                               "region": info[2], "field_office": info[3], "count": c})
    routes_list = [{"from": o, "to": d, "count": c} for (o, d), c in routes.most_common(200)]
    port_routes_list = []
    for (pc, d), c in port_routes.most_common(250):
        info = port_info.get(pc, ("", "", "", ""))
        lat, lon = port_coords(pc, info[1])
        port_routes_list.append({"from_port_code": pc, "from_port_name": info[0], "from_state": info[1],
                                 "to_state": d, "count": c, "lat": lat, "lon": lon})

    # communities aggregations
    def size_bucket(s):
        if s <= 4:
            return "1-4"
        if s <= 9:
            return "5-9"
        if s <= 19:
            return "10-19"
        if s <= 49:
            return "20-49"
        if s <= 99:
            return "50-99"
        return "100+"
    size_hist = collections.Counter()
    for s in sizes:
        size_hist[size_bucket(s)] += 1
    avg_size = round(sum(sizes) / (len(sizes) or 1), 1)

    def stats(vals):
        if not vals:
            return {"min": 0, "max": 0, "mean": 0, "median": 0, "values": []}
        sv = sorted(vals)
        n = len(sv)
        med = sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2
        return {"min": round(sv[0], 4), "max": round(sv[-1], 4),
                "mean": round(sum(sv) / n, 4), "median": round(med, 4),
                "values": [round(x, 4) for x in sv[:200]]}
    score_by_type_out = {t: stats(v) for t, v in score_by_type.items()}
    type_outcomes = {t: {**{"events": d["total"], "secondary": d["secondary"], "search": d["search"],
                            "seizure": d["seizure"], "arrest": d["arrest"]},
                         **{f"{k}_rate": round(d[k] / (d["total"] or 1), 4)
                            for k in ("secondary", "search", "seizure", "arrest")}}
                     for t, d in by_ctype_out.items()}
    top_comm = []
    for c, m in sorted(comm_meta.items(), key=lambda kv: -kv[1]["score"])[:30]:
        top_comm.append({"id": c, "type": m["type"], "score": round(m["score"], 4),
                         "port": m["region"], "size": m["size"]})

    # graph structure
    deg_vals = list(degree.values())
    deg_dist = collections.Counter(deg_vals)
    degree_distribution = [{"degree": d, "count": c} for d, c in sorted(deg_dist.items())]

    def pct(vals, q):
        if not vals:
            return 0
        sv = sorted(vals)
        return sv[min(len(sv) - 1, int(q * len(sv)))]
    degree_stats = {"min": min(deg_vals or [0]), "max": max(deg_vals or [0]),
                    "mean": round(sum(deg_vals) / (len(deg_vals) or 1), 2),
                    "median": pct(deg_vals, 0.5), "p95": pct(deg_vals, 0.95)}
    STRUCTURAL = {"PERSON_CROSSED_EVENT", "DOCUMENT_PRESENTED_IN_EVENT", "VEHICLE_USED_IN_EVENT",
                  "EVENT_OCCURRED_AT_PORT", "EVENT_PROCESSED_BY_TEAM", "BUSINESS_LINKED_TO_EVENT",
                  "PERSON_USED_DOCUMENT", "PERSON_USED_VEHICLE"}
    OUTCOME_E = {"EVENT_RESULTED_IN_SECONDARY", "EVENT_RESULTED_IN_SEARCH", "EVENT_RESULTED_IN_SEIZURE",
                 "EVENT_RESULTED_IN_ARREST", "EVENT_LINKED_TO_ADMIN_ACTION", "EVENT_LINKED_TO_SEIZURE"}
    edge_categories = {"structural": {}, "outcome": {}, "social": {}}
    for et, c in edge_type_counts.items():
        if et in STRUCTURAL:
            edge_categories["structural"][et] = c
        elif et in OUTCOME_E:
            edge_categories["outcome"][et] = c
        else:
            edge_categories["social"][et] = c
    connectivity = [{"source": s, "target": t, "count": c}
                    for (s, t), c in conn_pairs.most_common(15)]

    DATA = {
        "meta": {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 "corpus": name, "total_nodes": sum(node_type_counts.values()),
                 "total_edges": total_edges, "total_events": total_events,
                 "total_communities": n_communities},
        "overview": {
            "node_type_counts": node_type_counts, "edge_type_counts": dict(edge_type_counts),
            "outcome_counts": {k: outcome_counts.get(k, 0) for k in OUTCOME_KEYS},
            "outcome_rates": {k: round(outcome_counts.get(k, 0) / (total_events or 1), 4) for k in OUTCOME_KEYS},
            "split_counts": dict(split_counts),
        },
        "temporal": {
            "monthly_series": monthly_series, "by_fiscal_year": dict(by_fy),
            "by_day_of_week": {d: by_dow.get(d, 0) for d in
                               ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]},
            "by_hour": {str(h): by_hour.get(h, 0) for h in range(24)},
            "dow_hour_heatmap": [{"dow": d, "hour": h, "count": dow_hour.get((d, h), 0)}
                                 for d in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                                 for h in range(24)],
            "fy_region": {fy: dict(v) for fy, v in fy_region.items()},
        },
        "geographic": {
            "by_region": {k: {kk: v[kk] for kk in ("total", "secondary", "search", "seizure", "arrest")}
                          for k, v in by_region.items()},
            "by_field_office": {k: {kk: v[kk] for kk in ("total", "secondary", "search", "seizure", "arrest")}
                                for k, v in sorted(by_office.items(), key=lambda kv: -kv[1]["total"])},
            "top_ports": top_ports, "routes": routes_list, "port_routes": port_routes_list,
            "origin_to_port_state": origin_to_port_state, "origin_to_port": origin_to_port,
            "origin_port_mode_flows": flows,
            "port_state_volume": dict(port_state_volume.most_common(55)),
            "dest_state_volume": dict(dest_state_volume.most_common(55)),
        },
        "communities": {
            "total_communities": n_communities, "type_distribution": dict(type_distribution),
            "size_histogram": {k: size_hist.get(k, 0) for k in ["1-4", "5-9", "10-19", "20-49", "50-99", "100+"]},
            "avg_size": avg_size, "score_by_type": score_by_type_out, "type_outcomes": type_outcomes,
            "top_communities": top_comm,
        },
        "outcomes": {
            "risk_score_histogram": [{"bin": round(b / 12, 2), "count": risk_hist.get(b, 0)} for b in range(12)],
            "by_segment": {k: {kk: v[kk] for kk in ("total", "secondary", "search", "seizure", "arrest")}
                           for k, v in by_segment.items()},
            "by_mode": {k: {kk: v[kk] for kk in ("total", "secondary", "search", "seizure", "arrest")}
                        for k, v in by_mode.items()},
            "by_category": {k: {kk: v[kk] for kk in ("total", "secondary", "search", "seizure", "arrest")}
                            for k, v in by_category.items()},
            "by_citizenship_top15": {k: {kk: v[kk] for kk in ("total", "secondary", "search", "seizure", "arrest")}
                                     for k, v in sorted(by_citizenship.items(), key=lambda kv: -kv[1]["total"])[:15]},
            "by_direction": {k: {kk: v[kk] for kk in ("total", "secondary", "search", "seizure", "arrest")}
                             for k, v in by_direction.items()},
        },
        "graph_structure": {
            "node_type_counts": node_type_counts, "edge_type_counts": dict(edge_type_counts),
            "degree_distribution": degree_distribution, "degree_stats": degree_stats,
            "edge_categories": edge_categories, "connectivity": connectivity,
        },
        "seizures_arrests": {
            "total_seizures": int(sum(sa["drug_types"].values())), "total_arrests": n_arrested_rows,
            "drug_types": dict(sa["drug_types"]), "detection_methods": dict(sa["detection_methods"]),
            "conveyance": dict(sa["conveyance"]),
            "monthly": [{"month": m, "seizures": sa["monthly_seiz"].get(m, 0), "arrests": sa["monthly_arr"].get(m, 0)}
                        for m in sorted(set(sa["monthly_seiz"]) | set(sa["monthly_arr"]))],
            "quantity_stats": {"total": round(sum(sa["qty"]), 1), "min": round(min(sa["qty"] or [0]), 2),
                               "max": round(max(sa["qty"] or [0]), 2),
                               "mean": round(sum(sa["qty"]) / (len(sa["qty"]) or 1), 2)},
            "unique_drug_types": len(sa["drug_types"]),
            "arrest_reasons": dict(sa["arrest_reasons"]), "arrest_charges": dict(sa["arrest_charges"]),
            "arrest_dispositions": dict(sa["arrest_dispositions"]),
        },
        "community_map": community_map,
        "entities": {
            "person_age_buckets": dict(age_buckets.most_common()),
            "person_citizenships_top15": dict(citizen_counts.most_common(15)),
            "person_traveler_segments": dict(segment_counts.most_common()),
            "vehicle_types": dict(vehicle_types.most_common(10)),
            "document_types": dict(document_types.most_common()),
        },
        "explorer": explorer,
    }
    er_summary = load_entity_resolution_summary(corpus_dir)
    if er_summary is not None:
        DATA["entity_resolution"] = er_summary

    # Embed the combined-detector flagged export for V8 (single copy path via
    # dashboard_data.json; the unified builder only copies that file per corpus).
    if name.endswith("_v8"):
        flagged_path = os.path.join(REPO_ROOT, "gnn", "diagnostics",
                                    "model_flagged_v8.json")
        if os.path.exists(flagged_path):
            with open(flagged_path) as ff:
                DATA["modelFlagged"] = json.load(ff)
            p(f"[build] embedded modelFlagged ({len(DATA['modelFlagged'].get('rows', []))} rows)")
        else:
            p(f"[build] note: {flagged_path} absent — Flagged tab will stay hidden")

        # Detection Arms tab: five arms with uncertainty + seed spread + ceiling.
        arms_path = os.path.join(REPO_ROOT, "gnn", "diagnostics",
                                 "detection_arms_v8.json")
        if os.path.exists(arms_path):
            with open(arms_path) as af:
                DATA["detectionArms"] = json.load(af)
            p(f"[build] embedded detectionArms ({len(DATA['detectionArms'].get('arms', []))} arms)")
        else:
            p(f"[build] note: {arms_path} absent — Detection Arms tab will stay hidden")

    # V9 positive-control result blob for the V9-specific dashboard.
    if name.endswith("_v9"):
        demo_path = os.path.join(REPO_ROOT, "gnn", "diagnostics",
                                 "demo_comparison_v9.json")
        if os.path.exists(demo_path):
            with open(demo_path) as df:
                DATA["v9Demo"] = json.load(df)
            p("[build] embedded v9Demo comparison result")
        else:
            p(f"[build] note: {demo_path} absent — V9 Results tab will show corpus-only data")

    # Also write JSON for the unified dashboard
    json_path = files("dashboard_data.json")
    with open(json_path, "w") as jf:
        json.dump(DATA, jf, separators=(",", ":"))
    p(f"[build] wrote {json_path}  ({os.path.getsize(json_path)/1e6:.2f} MB)")

    # ===================================================================
    #  Render HTML
    # ===================================================================
    try:
        out_html = render_html(DATA, name, corpus_dir)
    except FileNotFoundError as exc:
        p(f"[build] skipped standalone HTML: template missing ({exc.filename})")
    else:
        out_path = files("dashboard_standalone.html")
        with open(out_path, "w") as f:
            f.write(out_html)
        p(f"[build] wrote {out_path}  ({os.path.getsize(out_path)/1e6:.2f} MB)")


def render_html(DATA, name, corpus_dir):
    """Splice data and the explorer into the corpus's standalone template."""
    tmpl_path = os.path.join(corpus_dir, "dashboard_standalone.html")
    with open(tmpl_path, encoding="utf-8") as tmpl_file:
        html = tmpl_file.read()

    data_json = json.dumps(DATA, separators=(",", ":"))

    # 1. replace embedded DATA blob (up to the IIFE start)
    anchor = "\n(async function(){"
    start = html.index("const DATA = ")
    iife = html.index(anchor, start)
    html = html[:start] + "const DATA = " + data_json + ";\n" + html[iife + 1:]

    # 2. swap People Network tab -> Community Explorer (Tabs entry)
    #    Handle both fresh templates (people:...) and already-transformed ones (explorer:...) 
    if "people:{rendered:false,render(){" in html:
        s1 = html.index("people:{rendered:false,render(){")
        s2 = html.index("seizures:{rendered:false,render(){")
        html = html[:s1] + EXPLORER_JS + html[s2:]
    elif "explorer:{rendered:false,render(){" in html:
        s1 = html.index("explorer:{rendered:false,render(){")
        s2 = html.index("seizures:{rendered:false,render(){")
        html = html[:s1] + EXPLORER_JS + html[s2:]

    # 3. nav button + section id (handle both fresh and already-transformed)
    html = html.replace('<button data-tab="people">People Network</button>',
                        '<button data-tab="explorer">Community Explorer</button>')
    html = html.replace('<section id="tab-people" class="tab-content"></section>',
                        '<section id="tab-explorer" class="tab-content"></section>')

    if DATA.get("entity_resolution"):
        html = html.replace(
            '<button data-tab="explorer">Community Explorer</button>',
            '<button data-tab="entityResolution">Entity Resolution</button>\n'
            '  <button data-tab="explorer">Community Explorer</button>',
            1,
        )
        html = html.replace(
            '<section id="tab-explorer" class="tab-content"></section>',
            '<section id="tab-entityResolution" class="tab-content"></section>\n'
            '  <section id="tab-explorer" class="tab-content"></section>',
            1,
        )
        html = html.replace(
            "explorer:{rendered:false,render(){",
            ENTITY_RESOLUTION_JS + "explorer:{rendered:false,render(){",
            1,
        )

    # 4. explorer CSS before </style>
    html = html.replace("</style>", EXPLORER_CSS + ENTITY_RESOLUTION_CSS + "\n</style>", 1)

    # 5. title / header label
    label = name.replace("synthetic_cbp_graph_corpus_", "").upper()
    html = re.sub(r"<title>[^<]*</title>",
                  f"<title>CBP Graph Corpus Explorer — {label}</title>", html, count=1)
    html = re.sub(r"(<h1>)([^<]*)(</h1>)", rf"\g<1>CBP Graph Corpus Explorer · {label}\g<3>", html, count=1)
    return html


# Explorer CSS + JS are defined in a sibling module to keep this file readable.
from scripts.dashboard.explorer_ui import EXPLORER_CSS, EXPLORER_JS  # noqa: E402


if __name__ == "__main__":
    if len(sys.argv) != 2:
        p("usage: python -m scripts.dashboard.build_dashboard <corpus_dir>")
        sys.exit(1)
    main(sys.argv[1])
