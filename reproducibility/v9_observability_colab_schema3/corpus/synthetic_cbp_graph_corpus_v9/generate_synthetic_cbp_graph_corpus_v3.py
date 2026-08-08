#!/usr/bin/env python3
"""Synthetic CBP-style entity-centric crossing-event graph corpus generator, v3/v4.

Rewritten from v2 to address realism feedback:

1. CONNECTIVITY = WHAT THE GOVERNMENT ACTUALLY OBSERVES.
   - Removed the population-wide phone/contact and address "social web".
   - Phone number is now a per-person *data point* (a column), it creates NO edges.
   - Person<->person links arise only from observable behaviour:
       * co-travel (people who actually crossed together in the same event/vehicle),
       * shared household residence (same address on file),
       * shared vehicles over time, vehicle registration, shared employer/business,
       * repeated routes.
   - Net effect: person<->person edge density drops ~10x vs v2.

2. FAMILIES != ADDRESSES.
   - Kinship is modelled with a hidden `family_id` that can span MULTIPLE households.
   - Some relatives live at different addresses but still co-travel, so families are
     only partially recoverable from the address graph (a realistic ER/community
     detection challenge). `ADDRESS_SHARED_BY_PERSONS` only links co-residents.

3. UNDETECTED SMUGGLING.
   - A latent `true_contraband_present` is generated per event, INDEPENDENT of whether
     enforcement caught it. Detection probability is < 1 at every stage, so many real
     smuggling events are never stopped (false negatives) and repeat carriers slip
     through on some trips and get caught on others. Seizures occur only when
     contraband is actually present AND found. Hidden truth lives in
     `event_ground_truth.csv` (evaluation-only, quarantined from features).

4. DATA ON PEOPLE WHO WERE STOPPED.
   - `secondary_inspections.csv` captures the richer record collected DURING secondary
     inspection (flagged available_after_secondary). Seizures/arrests carry person_id.
   - Every stopped person has a complete demographic + travel-history record.

5. DEMOGRAPHICS ARE ON THE INDIVIDUAL RECORD (document-derived: DOB, sex, nationality,
   residence) because the government realistically holds them. The fairness design is
   preserved as *methodology*: the synthetic audit grouping lives in audit_attributes.csv,
   and the latent smuggling propensity is generated INDEPENDENT of demographics, so a
   demographics-only model stays at chance (negative control).

All data are fully synthetic. The uploaded aggregate CBP-style CSVs are used only to
calibrate FY/month/region/field-office/port/mode/category and drug-type distributions.
No row represents a real person, vehicle, document, officer, case, event, or seizure.

Usage:  python generate_synthetic_cbp_graph_corpus_v3.py v3   # 50k events / 30k persons
        python generate_synthetic_cbp_graph_corpus_v3.py v4   # 150k events / 90k persons
        python generate_synthetic_cbp_graph_corpus_v3.py v5   # 200k events / 120k persons
        python generate_synthetic_cbp_graph_corpus_v3.py v6   # v5 + hidden co-offender orgs
        python generate_synthetic_cbp_graph_corpus_v3.py v7   # v6 + ER recoverability layer
        python generate_synthetic_cbp_graph_corpus_v3.py v8   # v7 + observed record per co-traveler
        python generate_synthetic_cbp_graph_corpus_v3.py both # v3+v4
        python generate_synthetic_cbp_graph_corpus_v3.py all  # v3+v4+v5+v6+v7+v8
"""
import csv, json, math, os, random, statistics, sys, re
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

SEED = 20260613
BASE = Path('/Users/edward/Desktop/GNN_Community_Detection/Documents/Data')
CALIB = BASE / 'RealWorld_Data'
TRAVELERS = CALIB / 'travelers-conveyances-fy22-fy25.csv'
NATIONWIDE = CALIB / 'nationwide-drugs-fy22-fy25.csv'
AMO = CALIB / 'amo-drug-seizures-fy22-fy25.csv'

SCALES = {
    'v3': dict(events=50_000,  persons=30_000),
    'v4': dict(events=150_000, persons=90_000),
    'v5': dict(events=200_000, persons=120_000),
    # v6 == v5 scale plus the hidden co-offender org layer (see ENABLE_ORGS below).
    'v6': dict(events=200_000, persons=120_000),
    # v7 == v6 plus entity-resolution fragmentation/recoverability artifacts.
    'v7': dict(events=200_000, persons=120_000),
    # v8 == v7 PLUS an observed record for every co-traveler (not just the event
    # primary), so co-travel is observable at the record level. Same base draw as
    # v7 (same seed offset); co-traveler records are generated from dedicated RNGs
    # so all non-observed-record files stay byte-identical to v7.
    'v8': dict(events=200_000, persons=120_000),
    # v9 == designed positive-control DEMO: v8 scale + amplified relational signal
    # (denser co-offender co-travel, ~4% measured catch rate (initial target: ~10%), shared plates, more connectivity;
    # see docs/research/changes_3.md). v9dev is a tiny scale for fast tests/iteration.
    'v9':    dict(events=200_000, persons=120_000),
    'v9mid': dict(events=50_000,  persons=30_000),   # fast iteration scale for the demo
    'v9dev': dict(events=4_000,   persons=2_000),
}

MONTHS = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']
MONTH_NUM = {m:i+1 for i,m in enumerate(MONTHS)}
DAYS = {1:31,2:28,3:31,4:30,5:31,6:30,7:31,8:31,9:30,10:31,11:30,12:31}

# Citizenship conditioned on the border region a traveller primarily uses. This is what
# makes the population representative of WHO crosses WHERE (e.g. Mexican nationals at SW
# land ports, Canadians on the northern border, diverse air arrivals incl. returning US
# citizens). These are synthetic modelling choices, not data copied from the source files.
REGION_CITIZENSHIP = {
    'Southern Border': {'Mexico':.52,'United States':.31,'Guatemala':.04,'Honduras':.03,
                        'El Salvador':.03,'Colombia':.01,'Other':.06},
    'Northern Border': {'United States':.54,'Canada':.40,'India':.01,'United Kingdom':.01,'Other':.04},
    'Coastal/Interior': {'United States':.44,'Mexico':.07,'Canada':.05,'China':.06,'India':.06,
                         'United Kingdom':.04,'Brazil':.03,'Colombia':.03,'Dominican Republic':.03,
                         'Philippines':.02,'Japan':.02,'South Korea':.02,'Germany':.02,'Other':.09},
    'Preclearance': {'United States':.49,'Canada':.21,'United Kingdom':.07,'Ireland':.05,
                     'The Bahamas':.04,'Bermuda':.02,'Aruba':.02,'Other':.10},
}
REGION_W = {'Coastal/Interior':.40,'Southern Border':.39,'Northern Border':.105,'Preclearance':.105}

AGE_BUCKETS = ['0-17','18-24','25-34','35-44','45-54','55-64','65+']; AGE_W=[.08,.12,.24,.22,.17,.10,.07]
AGE_TO_DOB = {'0-17':'YOB_2010s','18-24':'YOB_2000s','25-34':'YOB_1990s','35-44':'YOB_1980s',
              '45-54':'YOB_1970s','55-64':'YOB_1960s','65+':'YOB_1950s'}
SEX_MARKERS = ['F','M','X']; SEX_W=[.49,.49,.02]
AUDIT_GROUPS = ['AUD_GRP_A','AUD_GRP_B','AUD_GRP_C','AUD_GRP_D','AUD_GRP_E','AUD_GRP_F','AUD_GRP_G']
AUDIT_W = [.20,.18,.16,.15,.13,.10,.08]
LANGS = ['not_collected','English','Spanish','French','Mandarin','Other']; LANG_W=[.40,.30,.20,.03,.03,.04]

# Family / community archetypes (the hidden ground-truth community is the family).
FAM_TYPES = ['low_frequency_one_time_travelers','family_travel_cluster','routine_commuter_cluster',
             'airport_passenger_cluster','high_frequency_benign_crossers','seasonal_worker_cluster',
             'commercial_trucking_fleet_family','rental_reliant_cluster','administrative_document_issue_cluster',
             'prior_stops_no_seizures_cluster','synthetic_interdiction_linked_cluster']
FAM_W = [.305,.18,.12,.11,.05,.05,.04,.035,.025,.025,.06]
FAM_SIZE = [1,2,3,4,5,6,7,8]; FAM_SIZE_W=[.40,.24,.15,.09,.06,.03,.02,.01]

SEGMENTS_BY_FAM = {
    'low_frequency_one_time_travelers':'occasional_traveler','family_travel_cluster':'family_traveler',
    'routine_commuter_cluster':'routine_commuter','airport_passenger_cluster':'airport_traveler',
    'high_frequency_benign_crossers':'routine_commuter','seasonal_worker_cluster':'seasonal_worker',
    'commercial_trucking_fleet_family':'commercial_driver','rental_reliant_cluster':'rental_car_user',
    'administrative_document_issue_cluster':'admin_issue_test','prior_stops_no_seizures_cluster':'occasional_traveler',
    'synthetic_interdiction_linked_cluster':'interdiction_linked_synthetic',
}
ACTIVITY = {'routine_commuter':7.5,'commercial_driver':9.5,'family_traveler':2.4,'airport_traveler':1.8,
            'rental_car_user':2.0,'seasonal_worker':3.2,'occasional_traveler':.8,
            'interdiction_linked_synthetic':4.5,'admin_issue_test':1.8,'leakage_control_test':1.4}

VEH_TYPES = ['sedan','suv','pickup','van','semi_truck','box_truck','bus','motorcycle','rental_passenger_vehicle','commercial_tractor']
VEH_W = [.25,.23,.18,.10,.08,.05,.02,.02,.04,.03]
DOC_TYPES = ['passport','passport_card','border_crossing_card','permanent_resident_card','enhanced_driver_license','visa_document','commercial_crew_document','other_travel_document']
DOC_W = [.42,.13,.16,.08,.09,.08,.02,.02]
BUS_TYPES = ['carrier','shipper','broker','rental_agency','consignee','employer','warehouse_operator','tour_operator','other_logistics']
BUS_W = [.24,.16,.12,.10,.12,.10,.08,.04,.04]
NAME_STYLES = ['TOKEN_GIVEN_FAMILY','TOKEN_FAMILY_GIVEN','TOKEN_DOUBLE_SURNAME','TOKEN_PATRONYMIC','TOKEN_MONONYM','TOKEN_TRANSLITERATED','TOKEN_COMPOUND','TOKEN_INITIALIZED']
NAME_STYLE_W = [.26,.18,.15,.10,.05,.12,.10,.04]
VARIANT_TYPES = ['canonical_token','spacing_variant','hyphenation_variant','order_swap_variant','truncation_variant','transliteration_variant','initial_variant','data_entry_typo_variant']
VARIANT_W = [.56,.10,.08,.08,.05,.06,.04,.03]

# ---- V7: latent invented names (letters-only, no digits) -----------------------
# `observed_name_token` used to embed the raw person index (SYNNAME-<style>-<idx>-<var>),
# which made name-string similarity a perfect same-person oracle for ER. Instead every
# person gets a LATENT invented (given, surname) pair drawn from small pools; different
# people can and do collide on the same latent name (realistic hard negatives), and each
# observed record renders that latent name under a NAME_STYLE + VARIANT_TYPE with
# deterministic per-record noise -- name similarity becomes a real, noisy ER signal
# rather than an oracle. Pools are built once (module import time) from a dedicated RNG
# stream (SEED+41) that is entirely independent of the main corpus-generation `rng`, so
# building/using these pools never perturbs edges.csv / ground truth determinism.
def _pseudoword(r, min_syl=2, max_syl=3):
    """Invented Title-case pseudo-word: consonant+vowel syllables, letters only."""
    cons = 'bcdfgjklmnprstvzhw'
    vow = 'aeiou'
    n = r.randint(min_syl, max_syl)
    word = ''.join(r.choice(cons) + r.choice(vow) for _ in range(n))
    return word[0].upper() + word[1:]


_NAME_POOL_RNG = random.Random(SEED + 41)
GIVEN_M = [_pseudoword(_NAME_POOL_RNG) for _ in range(250)]
GIVEN_F = [_pseudoword(_NAME_POOL_RNG) for _ in range(250)]
SURNAMES = [_pseudoword(_NAME_POOL_RNG, 2, 3) for _ in range(600)]

_TRANSLIT_SUBS = [('ph', 'f'), ('ll', 'l'), ('k', 'c'), ('y', 'i')]


def render_name(given, surname, style, variant, noise_rng):
    """Render a latent (given, surname) pair under a name style + variant.

    `noise_rng` supplies the randomness for `data_entry_typo_variant` only; every other
    variant is a deterministic function of (given, surname, style, variant). Output never
    contains digits.
    """
    if style == 'TOKEN_FAMILY_GIVEN':
        base = f'{surname} {given}'
    elif style == 'TOKEN_MONONYM':
        base = surname
    elif style == 'TOKEN_INITIALIZED':
        base = f'{given[0]} {surname}'
    else:
        # TOKEN_GIVEN_FAMILY, TOKEN_DOUBLE_SURNAME, TOKEN_PATRONYMIC,
        # TOKEN_TRANSLITERATED, TOKEN_COMPOUND all render as "Given Surname".
        base = f'{given} {surname}'

    if variant == 'canonical_token':
        out = base
    elif variant == 'spacing_variant':
        if ' ' in base:
            out = base.replace(' ', '')
        else:
            mid = max(1, len(base) // 2)
            out = base[:mid] + ' ' + base[mid:]
    elif variant == 'hyphenation_variant':
        if ' ' in base:
            out = base.replace(' ', '-')
        else:
            mid = max(1, len(base) // 2)
            out = base[:mid] + '-' + base[mid:]
    elif variant == 'order_swap_variant':
        parts = base.split(' ')
        out = f'{parts[-1]}, {" ".join(parts[:-1])}' if len(parts) >= 2 else base
    elif variant == 'truncation_variant':
        parts = base.split(' ')
        li = max(range(len(parts)), key=lambda idx: len(parts[idx]))
        tok = parts[li]
        parts[li] = tok[:max(1, len(tok) - 3)]
        out = ' '.join(parts)
    elif variant == 'transliteration_variant':
        low = base.lower()
        for a, b in _TRANSLIT_SUBS:
            low = low.replace(a, b)
        out = ' '.join(w[:1].upper() + w[1:] if w else w for w in low.split(' '))
    elif variant == 'initial_variant':
        parts = base.split(' ')
        parts[0] = parts[0][0]
        out = ' '.join(parts)
    elif variant == 'data_entry_typo_variant':
        chars = list(base)
        for _ in range(noise_rng.randint(1, 2)):
            if len(chars) < 2:
                break
            idx = noise_rng.randrange(len(chars) - 1)
            if chars[idx] == ' ' or chars[idx + 1] == ' ':
                continue
            if noise_rng.choice(['swap', 'drop']) == 'swap':
                chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]
            else:
                del chars[idx]
        out = ''.join(chars)
    else:
        out = base
    return out

# ---- V6 hidden co-offender org layer (only active when scale_key == 'v6') ----
# A second hidden grouping, INDEPENDENT of family_id, modelling smuggling cells.
# It mirrors how family surfaces only through observable records: orgs become
# visible ONLY via cross-family co-travel / shared vehicle / shared carrier.
# `is_dark` members are truly in the cell but leave no observable trail
# (operational security: burner phones, recruiting strangers, never co-travelling)
# -> findable only in the golden ground truth, never in the graph. The gap between
# true-org and observable reachability is the realistic "unfindable" fraction,
# the structural analog of undetected smuggling.
ORG_SIZE = [3, 4, 5, 6, 7, 8]
ORG_SIZE_W = [.30, .28, .20, .12, .06, .04]
ORG_MODE_W = {'passenger_vehicle': .40, 'pedestrian': .25, 'air': .20, 'truck': .15}
ORG_DARK_RATE = 0.30           # fraction of members that are truly-linked-but-unfindable
ORG_OBSERVABILITY = (0.45, 0.85)  # per-org P(a relationship leaves an observable trail)
ORG_CANDIDATE_LAT = 0.15       # only meaningfully-involved persons are recruited into a cell


def main(scale_key):
    cfg = SCALES[scale_key]
    N_EVENTS = cfg['events']; N_PERSONS = cfg['persons']
    N_VEHICLES = int(N_PERSONS * 0.60)
    N_DOCS = int(N_PERSONS * 1.20)
    N_BUSINESSES = max(500, int(N_PERSONS / 15))
    N_OFFICERS = max(300, int(N_EVENTS / 100))
    N_ROUTE_LOCS = max(500, int(N_PERSONS / 30))
    N_NARRATIVES = 200
    N_ER_PAIRS = int(N_PERSONS * 0.8)
    ENABLE_ORGS = scale_key in ('v6', 'v7', 'v8', 'v9', 'v9mid', 'v9dev')   # hidden co-offender cells in v6+
    N_ORGS = max(20, int(N_PERSONS / 500))  # calibration knob for FN->anchor reachability

    # --- V9 designed-signal knobs (docs/research/changes_3.md). Locals so the
    # v6/v7/v8 paths (module-level constants) stay untouched and byte-identical. ---
    IS_V9 = scale_key in ('v9', 'v9mid', 'v9dev')
    org_size, org_size_w = ORG_SIZE, ORG_SIZE_W
    org_dark_rate, org_observability = ORG_DARK_RATE, ORG_OBSERVABILITY
    if IS_V9:
        N_ORGS = max(20, int(N_PERSONS / 150))        # ~800 cells at 120k (org-candidate-pool limited)
        org_size   = [4, 5, 6, 7, 8, 10, 12]
        org_size_w = [.22, .22, .18, .14, .10, .09, .05]
        org_dark_rate = 0.10                          # more findable (was .30)
        org_observability = (0.80, 0.99)              # more observable trails
        # V9 carry + ROLE-BASED catch knobs. KEY DESIGN: each cell splits into
        # ANCHORS (caught, esp. in train -> the graph signal) and CLEAN carriers
        # (carry but never caught, no enforcement trail -> FN targets findable ONLY
        # via the graph). Keeps the tabular baseline weak and lets the GNN's caught-
        # propagation win. (An earlier universal-carry/blanket-catch design made
        # carriers trivially identifiable by own history -> baseline crushed the GNN.)
        V9_CARRY_MULT = 12.0     # non-org elevated-lat carry multiplier (lone tail)
        V9_ORG_CARRY = 0.60      # org members are active smugglers (carry most trips)
        V9_ACTIVITY_ORG = 2.5    # org members cross more -> timely co-travel/plate edges form
                                 # BEFORE their test FN crossing, and cells span train+test.
                                 # (prior_crossings is kept OUT of the baseline's leak surface
                                 # by dense per-crossing connectivity, not by low activity.)
        V9_ANCHOR_FRAC = 0.55    # fraction of a cell's non-dark members that are catchable anchors
        V9_ANCHOR_SEIZE_TRAIN = 0.95  # anchor catch prob (carrying crossing, train window)
        V9_ANCHOR_SEIZE_TEST = 0.90   # anchor catch prob (test too) -> anchors rarely enter the FN
                                      # pool, so it's ~pure CLEAN carriers (no enforcement history
                                      # for the baseline to exploit at top-K)
        V9_LONE_SEIZE = 0.20     # lone (non-org) carriers MOSTLY PASS (uncaught -> lone tail).
                                 # Catching lots of lone carriers pollutes the RGCN (propagation
                                 # from lone catches to benign co-travelers) and breaks the win,
                                 # so catches stay concentrated in cells; the lone tail is uncaught.
        V9_LONE_FLOOR = 0.03     # modest baseline carry for NON-org people -> a real lone-smuggler tail
    OUT = BASE / f'synthetic_cbp_graph_corpus_{scale_key}'
    # v8 reuses v7's exact seed offset so the base draw (persons/families/events/orgs/...)
    # is byte-identical to v7; co-traveler observed records are generated below using
    # dedicated per-record RNGs (ct_rng) that never touch `rng`, so they cannot desync it.
    rng = random.Random(SEED + {'v3': 0, 'v4': 1, 'v5': 2, 'v6': 3, 'v7': 4, 'v8': 4, 'v9': 6, 'v9dev': 7, 'v9mid': 8}.get(scale_key, 0))
    res_rng = random.Random(SEED + 40)  # V7: independent stream for observed-residence noise; keeps rest of corpus byte-identical
    name_rng = random.Random(SEED + 41)  # V7: independent stream for latent name pool draws; keeps rest of corpus byte-identical

    def fid(prefix, i, width=8): return f'{prefix}{i:0{width}d}'
    def choice(items, w=None): return rng.choices(items, weights=w, k=1)[0]
    def wchoice(d):
        ks = list(d); return rng.choices(ks, weights=[d[k] for k in ks], k=1)[0]
    def parse_port_code(port):
        m = re.search(r'\((\d{4})\)\s*$', port or ''); return m.group(1) if m else f'{rng.randint(9000,9999)}'
    def fy_cal_year(fy, mon): return fy-1 if MONTH_NUM[mon] >= 10 else fy
    def rand_dt(fy, mon, mode):
        m = MONTH_NUM[mon]; y = fy_cal_year(fy, mon); d = rng.randint(1, DAYS[m])
        hour = int(min(23, max(0, rng.gauss(14 if mode == 'Air' else 11, 5 if mode == 'Air' else 6))))
        return datetime(y, m, d, hour, rng.randint(0, 59), rng.randint(0, 59))
    def make_cum(weights):
        cum = []; t = 0.0
        for w in weights: t += float(w); cum.append(t)
        return cum, t
    def sample_cum(cum, total): return bisect_left(cum, rng.random()*total)
    def set_minmax(first, last, idx, date):
        if not first[idx] or date < first[idx]: first[idx] = date
        if not last[idx] or date > last[idx]: last[idx] = date

    # ---- Calibration ---------------------------------------------------------
    calib = []; ports = {}
    region_slots = defaultdict(list)  # region -> list of (calib_index, weight)
    with open(TRAVELERS, newline='', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if r['Measure Name'] != 'Travelers':
                continue
            cnt = int(r['Count']) if r['Count'] else 0
            if cnt <= 0:
                continue
            pc = parse_port_code(r['Port of Entry'])
            meta = {'region': r['Region'], 'field_office': r['Field Office'], 'state': r['State'],
                    'port_of_entry': r['Port of Entry'], 'port_code': pc,
                    'mode': r['Mode of Transportation'], 'category': r['Category']}
            idx = len(calib); calib.append((int(r['FY']), r['Month (abbv)'], meta, cnt))
            region_slots[r['Region']].append((idx, cnt)); ports[pc] = meta
    weights = [c[3] for c in calib]; cum, total = make_cum(weights)
    region_cum = {}
    for reg, slots in region_slots.items():
        idxs = [s[0] for s in slots]; cc, tt = make_cum([s[1] for s in slots]); region_cum[reg] = (idxs, cc, tt)
    port_codes = sorted(ports); states = sorted({m['state'] for m in ports.values() if m['state']})
    field_offices = [m['field_office'] for m in ports.values()]

    drug_counts = Counter(); drug_qty = defaultdict(float)
    for p in [NATIONWIDE, AMO]:
        with open(p, newline='', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                drug = r['Drug Type'].replace('Khat (Catha Edulis)', 'Khat').replace('Lsd', 'LSD').replace('Other Drugs**', 'Other Drugs')
                c = int(float(r.get('Count of Event') or 0)); q = float(r.get('Sum Qty (lbs)') or 0)
                if c > 0: drug_counts[drug] += c; drug_qty[drug] += q
    drugs = list(drug_counts); drug_w = [drug_counts[d] for d in drugs]
    avg_qty = {d: max(.05, drug_qty[d]/max(1, drug_counts[d])) for d in drugs}

    def sample_region_slot(reg):
        idxs, cc, tt = region_cum.get(reg, (None, None, None))
        if not idxs: return sample_cum(cum, total)
        return idxs[bisect_left(cc, rng.random()*tt)]

    # ---- Businesses (generated first; persons may reference an employer) ------
    b_type = [choice(BUS_TYPES, BUS_W) for _ in range(N_BUSINESSES)]
    rental_biz = [i for i, t in enumerate(b_type) if t == 'rental_agency'] or list(range(N_BUSINESSES))
    employer_biz = [i for i, t in enumerate(b_type) if t in ('carrier', 'employer', 'warehouse_operator', 'shipper')] or list(range(N_BUSINESSES))
    b_country = [choice(['United States','Mexico','Canada','Other'], [.60,.22,.12,.06]) for _ in range(N_BUSINESSES)]
    b_state = [rng.choice(states) for _ in range(N_BUSINESSES)]

    # ---- Families -> households -> persons -----------------------------------
    p_family = []; p_hh = []; p_country = []; p_res = []; p_age = []; p_dob = []
    p_sex = []; p_audit = []; p_lang = []; p_seg = []; p_lat = []; p_style = []; p_phone = []; p_employer = []
    p_name = []  # V7: latent (given, surname) pair per person, drawn from name_rng only
    fam_type = []; fam_region = []; fam_lat = []; fam_eval_pos = []
    fam_members = defaultdict(list); hh_members = defaultdict(list); hh_res_loc = []  # global household -> residence loc int
    P_NEW_HH = 0.22
    fam = 0
    while len(p_family) < N_PERSONS:
        k = min(choice(FAM_SIZE, FAM_SIZE_W), N_PERSONS - len(p_family))
        reg = wchoice(REGION_W); ft = choice(FAM_TYPES, FAM_W)
        if ft == 'synthetic_interdiction_linked_cluster':
            lat = min(1.0, rng.betavariate(2, 5) + .18); pos = True
        elif ft in ('prior_stops_no_seizures_cluster', 'administrative_document_issue_cluster'):
            lat = rng.betavariate(2, 16); pos = False
        else:
            lat = rng.betavariate(1, 220); pos = False
        fam_type.append(ft); fam_region.append(reg); fam_lat.append(lat); fam_eval_pos.append(pos)
        hh_in_fam = []
        for m in range(k):
            if m == 0 or rng.random() < P_NEW_HH:
                ghh = len(hh_res_loc); hh_res_loc.append(len(hh_res_loc)); hh_in_fam.append(ghh)
            ghh = rng.choices(hh_in_fam, weights=[3] + [1]*(len(hh_in_fam)-1))[0]
            i = len(p_family)
            citizenship = wchoice(REGION_CITIZENSHIP[reg]); p_country.append(citizenship)
            p_res.append(citizenship if rng.random() < .85 else wchoice(REGION_CITIZENSHIP[reg]))
            age = choice(AGE_BUCKETS, AGE_W); p_age.append(age); p_dob.append(AGE_TO_DOB[age])
            p_sex.append(choice(SEX_MARKERS, SEX_W)); p_audit.append(choice(AUDIT_GROUPS, AUDIT_W))
            p_lang.append(choice(LANGS, LANG_W)); p_style.append(choice(NAME_STYLES, NAME_STYLE_W))
            p_name.append((name_rng.choice(GIVEN_F if p_sex[-1] == 'F' else GIVEN_M), name_rng.choice(SURNAMES)))
            seg = SEGMENTS_BY_FAM[ft]
            if seg == 'occasional_traveler' and rng.random() < .12: seg = 'routine_commuter'
            p_seg.append(seg)
            # Member-level smuggling involvement: even in an interdiction family, only a
            # subset is actually involved (mix of benign + non-benign within a cluster).
            if lat > 0.05 and rng.random() < 0.65:
                pl = min(1.0, lat * (0.6 + 0.8 * rng.random()))
            else:
                pl = rng.betavariate(1, 400)
            p_lat.append(pl)
            p_phone.append(f'SYN-PHN-{scale_key.upper()}-{i+1:08d}')  # data point only; never an edge
            emp = ''
            if seg in ('commercial_driver', 'seasonal_worker'):
                emp = rng.choice(employer_biz)
            elif rng.random() < .03:
                emp = rng.choice(employer_biz)
            p_employer.append(emp)
            p_family.append(fam); p_hh.append(ghh)
            fam_members[fam].append(i); hh_members[ghh].append(i)
            if len(p_family) >= N_PERSONS: break
        fam += 1
    N_FAMILIES = fam; N_HOUSEHOLDS = len(hh_res_loc)

    # ---- Vehicles + ownership/fleet pools ------------------------------------
    v_type = [choice(VEH_TYPES, VEH_W) for _ in range(N_VEHICLES)]
    v_owner_p = ['']*N_VEHICLES; v_owner_b = ['']*N_VEHICLES; v_rental = [False]*N_VEHICLES; v_commercial = [False]*N_VEHICLES
    household_vehicles = defaultdict(list); business_vehicles = defaultdict(list); rental_vehicles = []
    for v, t in enumerate(v_type):
        if 'truck' in t or 'tractor' in t or t == 'bus':
            v_commercial[v] = True; b = rng.choice(employer_biz); v_owner_b[v] = b; business_vehicles[b].append(v)
        elif 'rental' in t or rng.random() < .05:
            v_rental[v] = True; b = rng.choice(rental_biz); v_owner_b[v] = b; rental_vehicles.append(v)
        else:
            owner = rng.randrange(N_PERSONS); v_owner_p[v] = owner; household_vehicles[p_hh[owner]].append(v)
    if not rental_vehicles: rental_vehicles = [v for v in range(N_VEHICLES) if v_rental[v]] or [0]

    # ---- Hidden co-offender orgs (V6 only) -----------------------------------
    # Built AFTER families/vehicles so cells can span families and reuse vehicles.
    # No person's latent propensity is changed here -> contraband prevalence is
    # preserved; orgs add only cross-family CONNECTIVITY among existing carriers.
    p_org = [-1] * N_PERSONS
    org_anchor = [False] * N_PERSONS   # v9: catchable anchors (vs clean carriers) within a cell
    org_members = defaultdict(list)
    org_obs = {}; org_mode = {}; org_families = {}
    org_vehicle = {}; org_carrier = {}
    org_dark = [False] * N_PERSONS; p_role = {}
    org_observable_members = set()
    N_ORGS_MADE = 0
    if ENABLE_ORGS:
        cand = [i for i in range(N_PERSONS) if p_lat[i] > ORG_CANDIDATE_LAT]
        rng.shuffle(cand)
        free_pv = [v for v in range(N_VEHICLES) if not v_commercial[v] and not v_rental[v] and v_owner_p[v] == '']
        free_tr = [v for v in range(N_VEHICLES) if v_commercial[v]]
        rng.shuffle(free_pv); rng.shuffle(free_tr)
        ci = pv_ptr = tr_ptr = oid = 0
        while ci < len(cand) and oid < N_ORGS:
            size = choice(org_size, org_size_w)
            members = []; fams = set(); tries = 0
            while len(members) < size and ci < len(cand) and tries < size * 6:
                m = cand[ci]; ci += 1; tries += 1
                if p_org[m] != -1:
                    continue
                members.append(m); fams.add(p_family[m])
            # A cell must be cross-family (>=2 families) and >=3 members to be meaningful.
            if len(members) < 3 or len(fams) < 2:
                continue
            mode = ('passenger_vehicle' if IS_V9 else wchoice(ORG_MODE_W))  # v9: all cells share a plate + co-travel by car
            obs = rng.uniform(*org_observability)
            for idx, m in enumerate(members):
                p_org[m] = oid; org_members[oid].append(m)
                org_dark[m] = rng.random() < org_dark_rate
                p_role[m] = 'coordinator' if idx == 0 else choice(
                    ['carrier', 'courier', 'recruiter', 'associate'], [.50, .25, .12, .13])
                # v9: designate catchable ANCHORS (coordinator + ~V9_ANCHOR_FRAC of the
                # rest, non-dark only). Anchors get caught and become the graph signal;
                # every other cell member is a CLEAN carrier (the FN target).
                if IS_V9 and not org_dark[m]:
                    org_anchor[m] = (idx == 0) or (rng.random() < V9_ANCHOR_FRAC)
            org_obs[oid] = obs; org_mode[oid] = mode; org_families[oid] = fams
            # One small shared asset per cell (specificity: rare shared entity).
            if mode == 'passenger_vehicle' and pv_ptr < len(free_pv):
                v = free_pv[pv_ptr]; pv_ptr += 1; org_vehicle[oid] = v
                v_owner_p[v] = members[0]; household_vehicles[p_hh[members[0]]].append(v)
            elif mode == 'truck' and tr_ptr < len(free_tr):
                org_vehicle[oid] = free_tr[tr_ptr]; tr_ptr += 1
            if mode in ('air', 'truck'):
                org_carrier[oid] = rng.choice(employer_biz)
            oid += 1
        N_ORGS_MADE = oid
        print(f'  v6 orgs built: {N_ORGS_MADE:,} cells, '
              f'{sum(len(m) for m in org_members.values()):,} members '
              f'({sum(org_dark):,} dark)', flush=True)

    # ---- Officers ------------------------------------------------------------
    o_port = [rng.choice(port_codes) for _ in range(N_OFFICERS)]
    o_role = [choice(['primary_inspection_team','secondary_inspection_team','cargo_inspection_team','air_processing_team','supervisory_review_team','canine_support_team'], [.45,.20,.12,.10,.08,.05]) for _ in range(N_OFFICERS)]
    o_shift = [choice(['day','evening','overnight','rotating','weekend-heavy'], [.42,.24,.14,.14,.06]) for _ in range(N_OFFICERS)]

    # ---- Documents -----------------------------------------------------------
    doc_person = [0]*N_DOCS; p_docs = [[] for _ in range(N_PERSONS)]
    for i in range(N_PERSONS): doc_person[i] = i; p_docs[i].append(i)
    for d in range(N_PERSONS, N_DOCS):
        p = rng.randrange(N_PERSONS); doc_person[d] = p; p_docs[p].append(d)

    # ---- Stat accumulators ---------------------------------------------------
    pstat = [[0]*10 for _ in range(N_PERSONS)]  # total air land ped passveh truck sec search seiz arrest
    pfirst = ['']*N_PERSONS; plast = ['']*N_PERSONS; pveh = [set() for _ in range(N_PERSONS)]
    p_port_ct = [Counter() for _ in range(N_PERSONS)]
    vstat = [[0]*4 for _ in range(N_VEHICLES)]; vpers = [set() for _ in range(N_VEHICLES)]
    vports = [set() for _ in range(N_VEHICLES)]; vfirst = ['']*N_VEHICLES; vlast = ['']*N_VEHICLES
    v_port_ct = [Counter() for _ in range(N_VEHICLES)]
    dstat = [0]*N_DOCS; dfirst = ['']*N_DOCS; dlast = ['']*N_DOCS; dmismatch = [False]*N_DOCS
    bstat = [[0]*4 for _ in range(N_BUSINESSES)]; bpers = [set() for _ in range(N_BUSINESSES)]
    bveh = [set() for _ in range(N_BUSINESSES)]; bfirst = ['']*N_BUSINESSES; blast = ['']*N_BUSINESSES
    ostat = [[0]*5 for _ in range(N_OFFICERS)]; ofirst = ['']*N_OFFICERS; olast = ['']*N_OFFICERS
    p_counter = defaultdict(int); v_counter = defaultdict(int); d_counter = defaultdict(int)
    cotravel = Counter()
    p_train_anchor = [False] * N_PERSONS  # caught (seizure) in the train window -> graph anchor
    p_test_fn = [False] * N_PERSONS       # carried but not caught in the test window (golden FN)

    # ---- Output writers ------------------------------------------------------
    if OUT.exists():
        import shutil; shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    headers = {
        'crossing_events.csv': ['event_id','event_timestamp_utc','crossing_datetime_local','fiscal_year','fiscal_month','calendar_month','day_of_week','hour_of_day','region','field_office','state','port_of_entry','port_code','mode_of_transportation','travel_category','direction','primary_person_id','observed_person_record_id','party_size','co_traveler_person_ids','vehicle_id','document_id','carrier_id','officer_team_id','inspection_lane_or_processing_context','declared_trip_purpose','origin_country','citizenship_country','residence_country','destination_state','repeat_crossing_count_prior_365d','same_vehicle_crossing_count_prior_365d','same_document_crossing_count_prior_365d','secondary_referral_flag','search_flag','seizure_flag','arrest_flag','prosecution_referral_flag','administrative_action_flag','final_disposition','synthetic_risk_score_pre_outcome','data_split','label_available_time_utc','feature_available_time_utc'],
        'event_features.csv': ['event_id','feature_available_time_utc','feature_window_start_utc','feature_window_end_utc','pre_event_features_json','at_primary_features_json','pre_secondary_features_json','target_secondary','target_search','target_seizure','target_arrest','target_referral','leakage_safe_flag','excluded_leakage_columns'],
        'event_ground_truth.csv': ['event_id','event_timestamp_utc','primary_person_id','true_contraband_present','true_drug_type','true_quantity_lbs','contraband_outcome_path','detected_flag','false_negative_flag','false_positive_search_flag','label_class','notes_on_leakage_risk'],
        'seizures.csv': ['seizure_id','event_id','primary_person_id','event_timestamp_utc','seizure_timestamp_utc','drug_type','quantity_lbs','package_count','conveyance_context','seizure_location_context','detection_context','component','lab_confirmation_status','post_event_label_available_time_utc'],
        'arrests.csv': ['arrest_id','event_id','person_id','event_timestamp_utc','arrest_timestamp_utc','arrest_reason_category','related_seizure_id','charge_category_synthetic','disposition_status','referred_agency_category','post_event_label_available_time_utc'],
        'secondary_inspections.csv': ['secondary_inspection_id','event_id','person_id','event_timestamp_utc','secondary_start_timestamp_utc','referral_reason_category','exam_type','declared_items_category','document_reverification_result','search_conducted_flag','result_category','officer_team_id','availability_class','post_secondary_available_time_utc'],
        'labels.csv': ['entity_id','label_type','label_value','event_timestamp_utc','label_time_utc','label_source','train_valid_test_allowed_flag','notes_on_leakage_risk'],
        'train_valid_test_splits.csv': ['entity_id','entity_type','split','split_strategy','temporal_cutoff','group_leakage_prevention_id','notes'],
        'edges.csv': ['edge_id','source_node_id','source_node_type','target_node_id','target_node_type','edge_type','event_id','edge_timestamp_utc','first_seen_timestamp_utc','last_seen_timestamp_utc','weight','confidence','evidence_source','temporal_valid_from_utc','temporal_valid_to_utc','feature_available_time_utc','leakage_safe_flag'],
        'observed_person_records.csv': ['observed_person_record_id','event_id','event_timestamp_utc','canonical_person_id','observed_name_token','name_convention_style','name_variant_type','observed_dob_year_bucket','observed_sex_marker','observed_document_id','observed_document_token','issuing_country_observed','transliteration_noise_flag','tokenization_noise_flag','document_mismatch_noise_flag','source_system','raw_record_available_time_utc','observed_residence_location_id'],
        'entity_resolution_truth.csv': ['observed_person_record_id','canonical_person_id','true_resolution_cluster_id','family_id','event_id','event_timestamp_utc','truth_label_available_time_utc','truth_label_type','notes'],
    }
    files = {}; w = {}
    for name, h in headers.items():
        f = open(OUT/name, 'w', newline='', encoding='utf-8'); wr = csv.writer(f); wr.writerow(h); files[name] = f; w[name] = wr
    ew = w['edges.csv']
    edge_count = [0]; degree = Counter()

    def edge(src, st, tgt, tt, etype, eid, ts, ftime, leak=True, conf=1.0, weight=1, evsrc='synthetic_generator'):
        edge_count[0] += 1
        ew.writerow([fid('EDGE', edge_count[0], 10), src, st, tgt, tt, etype, eid, ts, ts, ts, weight, conf, evsrc, ts, '', ftime, str(leak).lower()])
        degree[src] += 1; degree[tgt] += 1

    purposes = ['commute','tourism','family_visit','business','commercial_transport','shopping','education','medical','crew','other']
    origins = {'Southern Border':['Mexico','United States','Guatemala','Honduras','El Salvador'],
               'Northern Border':['Canada','United States'],
               'Coastal/Interior':list({c for d in REGION_CITIZENSHIP.values() for c in d}),
               'Preclearance':['Canada','Ireland','United Arab Emirates','The Bahamas','Bermuda','Aruba','Other']}
    detect = ['inspection','canine alert','x-ray anomaly','document inconsistency','behavioral referral','routine exam','investigative referral','non-intrusive inspection anomaly','cargo manifest inconsistency']
    components = ['Office of Field Operations','U.S. Border Patrol','Air and Marine Operations']

    # ---- Person event ordering: every person crosses at least once -----------
    p_order = list(range(N_PERSONS)); rng.shuffle(p_order)
    p_weights = [ACTIVITY.get(p_seg[i], 1.0) * (0.5 + rng.random())
                 * (V9_ACTIVITY_ORG if (IS_V9 and p_org[i] != -1) else 1.0)
                 for i in range(N_PERSONS)]
    p_cum, p_total_w = make_cum(p_weights)

    obs_by_person = defaultdict(list); obs_event_map = []
    audit_event_rows = []; narratives = []; narrative_idxs = set(rng.sample(range(1, N_EVENTS+1), N_NARRATIVES))
    sec_n = search_n = seiz_n = arr_n = ref_n = admin_n = 0
    contraband_n = caught_n = fn_n = fp_n = 0

    cw = w['crossing_events.csv']; efw = w['event_features.csv']; egw = w['event_ground_truth.csv']
    sw = w['seizures.csv']; aw = w['arrests.csv']; siw = w['secondary_inspections.csv']
    lw = w['labels.csv']; spw = w['train_valid_test_splits.csv']
    ow = w['observed_person_records.csv']; erw = w['entity_resolution_truth.csv']

    def pick_vehicle(p, cat):
        if cat == 'Trucks':
            emp = p_employer[p]
            if emp != '' and business_vehicles.get(emp): return rng.choice(business_vehicles[emp])
            allc = [v for v in range(N_VEHICLES) if v_commercial[v]]
            return rng.choice(allc) if allc else rng.randrange(N_VEHICLES)
        hhv = household_vehicles.get(p_hh[p])
        if hhv and rng.random() < .80: return rng.choice(hhv)
        if rng.random() < .12: return rng.choice(rental_vehicles)
        nv = rng.randrange(N_VEHICLES)
        if v_owner_p[nv] == '' and not v_commercial[nv]:
            v_owner_p[nv] = p; household_vehicles[p_hh[p]].append(nv)
        return nv

    for ev in range(1, N_EVENTS+1):
        p = p_order[ev-1] if ev <= N_PERSONS else sample_cum(p_cum, p_total_w)
        # Concentrate a person's crossings in their home region (representativeness),
        # otherwise sample globally from the calibrated traveller distribution.
        cidx = sample_region_slot(fam_region[p_family[p]]) if rng.random() < 0.72 else sample_cum(cum, total)
        fy, mon, meta, _ = calib[cidx]; meta = dict(meta)
        dt = rand_dt(fy, mon, meta['mode']); ets = dt.isoformat()+'Z'; date = dt.date().isoformat()
        eid = fid('E', ev); pid = fid('P', p+1); mode = meta['mode']; cat = meta['category']

        # V6: is this an observable op for a co-offender cell member?
        oid = p_org[p] if ENABLE_ORGS else -1
        org_active = oid >= 0 and not org_dark[p] and rng.random() < org_obs[oid]

        # Vehicle / carrier
        veh = ''; vidx = None; biz = ''; bidx = None
        if cat in ('Passenger Vehicles', 'Trucks'):
            if org_active and oid in org_vehicle and (
                    (cat == 'Passenger Vehicles' and org_mode[oid] == 'passenger_vehicle') or
                    (cat == 'Trucks' and org_mode[oid] == 'truck')):
                vidx = org_vehicle[oid]  # cell members share one vehicle (specificity signal)
            else:
                vidx = pick_vehicle(p, cat)
            veh = fid('V', vidx+1)
            if v_owner_b[vidx] != '':
                bidx = v_owner_b[vidx]; biz = fid('BIZ', bidx+1, 6)
            elif cat == 'Trucks' and org_active and oid in org_carrier and org_mode[oid] == 'truck':
                bidx = org_carrier[oid]; biz = fid('BIZ', bidx+1, 6)  # shared small broker/carrier
            elif cat == 'Trucks' and rng.random() < .6:
                bidx = rng.choice(employer_biz); biz = fid('BIZ', bidx+1, 6)
        elif mode == 'Air' and org_active and oid in org_carrier and org_mode[oid] == 'air':
            bidx = org_carrier[oid]; biz = fid('BIZ', bidx+1, 6)  # shared carrier / booking source
        elif mode == 'Air' and rng.random() < .92:
            bidx = rng.randrange(N_BUSINESSES); biz = fid('BIZ', bidx+1, 6)

        # Co-travel party drawn from FAMILY (can span households)
        party = choice([1,2,3,4,5,6], [.55,.25,.09,.06,.03,.02])
        if cat == 'Trucks' or mode == 'Air' and rng.random() < .6:
            party = 1 if cat == 'Trucks' else choice([1,2], [.7,.3])
        fam_pool = [m for m in fam_members[p_family[p]] if m != p]
        cotravelers = rng.sample(fam_pool, min(party-1, len(fam_pool))) if party > 1 and fam_pool else []
        # V6: cross-family org co-travel (time-correlated by construction: same event).
        # Truck cells move freight solo, so their signal is the shared truck/broker, not co-travel.
        if org_active and org_mode[oid] != 'truck' and cat != 'Trucks':
            org_pool = [m for m in org_members[oid] if m != p and not org_dark[m]]
            if org_pool:
                if IS_V9:                       # v9: DENSE co-travel, biased to include ANCHORS
                    k = min(len(org_pool), rng.choice([3, 4, 5]))
                    anc = [m for m in org_pool if org_anchor[m]]
                    oth = [m for m in org_pool if not org_anchor[m]]
                    rng.shuffle(anc); rng.shuffle(oth)
                    picks = (anc + oth)[:k]      # anchors first -> clean carriers link to a caught anchor
                    for assoc in picks:
                        if assoc not in cotravelers:
                            cotravelers.append(assoc)
                else:
                    assoc = rng.choice(org_pool)
                    if assoc not in cotravelers:
                        cotravelers.append(assoc)
        party = 1 + len(cotravelers)

        # Document + entity-resolution noise (primary person)
        docidx = rng.choice(p_docs[p]); doc_exc = False
        if (p_seg[p] == 'admin_issue_test' and rng.random() < .03) or rng.random() < .0015:
            doc_exc = True
            if rng.random() < .35:
                docidx = rng.randrange(N_DOCS); dmismatch[docidx] = True
        doc = fid('DOC', docidx+1, 8)
        obs_id = fid('OBS', ev, 9)
        variant = choice(VARIANT_TYPES, VARIANT_W) if p_counter[p] > 0 else 'canonical_token'
        style = p_style[p]
        noise_rng = random.Random(int(obs_id[3:]))  # stable per-record seed (obs_id = 'OBS'+digits); independent of PYTHONHASHSEED and main rng
        obs_name = render_name(p_name[p][0], p_name[p][1], style, variant, noise_rng)
        translit = variant == 'transliteration_variant' or style == 'TOKEN_TRANSLITERATED'
        token_noise = variant in ['spacing_variant','hyphenation_variant','order_swap_variant','truncation_variant','initial_variant','data_entry_typo_variant']
        obs_doc_token = f'SYN-OBS-DOC-{docidx+1:08d}-{variant[:3].upper()}'
        src_sys = choice(['primary_inspection_system','carrier_manifest_feed','secondary_review_note','document_scan_record','manual_entry_log'], [.52,.18,.12,.12,.06])
        # V7: noisy observed residence — a real observable ER signal derived from the
        # person's latent residence with independent noise (dedicated res_rng).
        _rr = res_rng.random()
        if _rr < 0.15:
            obs_res = ''                                                   # missing on this record
        elif _rr < 0.25:
            obs_res = fid('LOC', hh_res_loc[res_rng.randrange(len(hh_res_loc))] + 1, 8)  # wrong address on file
        else:
            obs_res = fid('LOC', hh_res_loc[p_hh[p]] + 1, 8)              # true residence
        ow.writerow([obs_id, eid, ets, pid, obs_name, style, variant, p_dob[p], p_sex[p], doc, obs_doc_token, p_country[doc_person[docidx]], str(translit).lower(), str(token_noise).lower(), str(doc_exc).lower(), src_sys, ets, obs_res])
        erw.writerow([obs_id, pid, fid('RESCL', p+1, 8), fid('C', p_family[p]+1, 7), eid, ets, (dt+timedelta(days=30)).isoformat()+'Z', 'canonical_person_truth', 'Entity-resolution training truth only; not an operational feature.'])
        obs_by_person[p].append(obs_id); obs_event_map.append((obs_id, p, eid, ets, style, variant))

        # V8/V9: every co-traveler on this event also gets an observed_person_records.csv
        # row (v7 only recorded the primary). This is strictly additive: it must never
        # touch the main `rng` (that would desync the base draw and break v7 byte-
        # identity), so all randomness here comes from `ct_rng`, a per-(event, slot)
        # deterministic stream seeded independently of every other RNG in this module.
        # V9 REQUIRES this: the demo RGCN derives COTRAVEL from >=2 identities sharing an
        # event_id, so without co-traveler records the co-travel rail is structurally empty
        # (edges.csv co-travel is NOT read by build_anchor_graph). See changes_3.md.
        if IS_V9 or scale_key == 'v8':
            for k, c in enumerate(cotravelers, start=1):
                ct_rng = random.Random(int(ev) * 100 + k)
                ct_obs_id = f'{obs_id}-{k}'
                ct_variant = ct_rng.choices(VARIANT_TYPES, weights=VARIANT_W, k=1)[0]
                ct_style = p_style[c]
                ct_docidx = ct_rng.choice(p_docs[c])
                ct_doc = fid('DOC', ct_docidx + 1, 8)
                ct_obs_doc_token = f'SYN-OBS-DOC-{ct_docidx+1:08d}-{ct_variant[:3].upper()}'
                ct_noise_rng = random.Random(ct_rng.randrange(2**31))
                ct_obs_name = render_name(p_name[c][0], p_name[c][1], ct_style, ct_variant, ct_noise_rng)
                ct_translit = ct_variant == 'transliteration_variant' or ct_style == 'TOKEN_TRANSLITERATED'
                ct_token_noise = ct_variant in ['spacing_variant','hyphenation_variant','order_swap_variant','truncation_variant','initial_variant','data_entry_typo_variant']
                ct_src_sys = ct_rng.choices(['primary_inspection_system','carrier_manifest_feed','secondary_review_note','document_scan_record','manual_entry_log'], weights=[.52,.18,.12,.12,.06], k=1)[0]
                _ct_rr = ct_rng.random()
                if _ct_rr < 0.15:
                    ct_obs_res = ''                                                        # missing on this record
                elif _ct_rr < 0.25:
                    ct_obs_res = fid('LOC', hh_res_loc[ct_rng.randrange(len(hh_res_loc))] + 1, 8)  # wrong address on file
                else:
                    ct_obs_res = fid('LOC', hh_res_loc[p_hh[c]] + 1, 8)                    # true residence
                ct_pid = fid('P', c + 1)
                ow.writerow([ct_obs_id, eid, ets, ct_pid, ct_obs_name, ct_style, ct_variant, p_dob[c], p_sex[c], ct_doc, ct_obs_doc_token, p_country[doc_person[ct_docidx]], str(ct_translit).lower(), str(ct_token_noise).lower(), 'false', ct_src_sys, ets, ct_obs_res])
                erw.writerow([ct_obs_id, ct_pid, fid('RESCL', c + 1, 8), fid('C', p_family[c] + 1, 7), eid, ets, (dt+timedelta(days=30)).isoformat()+'Z', 'canonical_person_truth', 'Entity-resolution training truth only; not an operational feature.'])
                obs_by_person[c].append(ct_obs_id); obs_event_map.append((ct_obs_id, c, eid, ets, ct_style, ct_variant))

        # --- Latent smuggling truth (independent of detection) ---------------
        if IS_V9:
            if p_org[p] >= 0 and not org_dark[p]:
                per_trip_carry = V9_ORG_CARRY                 # active cell smuggler
            else:
                per_trip_carry = min(0.9, p_lat[p] * 0.72 * V9_CARRY_MULT + V9_LONE_FLOOR)  # lone tail
        else:
            per_trip_carry = p_lat[p] * 0.72
        contraband = rng.random() < per_trip_carry
        true_drug = choice(drugs, drug_w) if contraband else ''
        true_qty = round(min(25000, max(.01, rng.lognormvariate(math.log(max(avg_qty.get(true_drug, 1), .05)), 1.15))), 4) if contraband else 0.0

        # --- Observable, leakage-safe risk proxy (NOT a function of contraband
        #     truth or demographics) -------------------------------------------
        repeat = p_counter[p]; veh_prior = v_counter[vidx] if vidx is not None else 0; doc_prior = d_counter[docidx]
        risk = max(.001, min(.95, .02 + .05*min(1, repeat/120) + (.012 if meta['region'] in ('Southern Border',) else 0)
                              + (.02 if doc_exc else 0) + (min(.04, veh_prior/400) if vidx is not None else 0)
                              + (.01 if vidx is not None and v_rental[vidx] else 0) + rng.uniform(-.012, .012)))
        # Contraband carriers are only somewhat more referable; most still slip through.
        carry_referral_boost = 0.16 if contraband else 0.0
        p_sec = min(.45, .022 + .10*risk + carry_referral_boost + (.015 if doc_exc else 0)
                    + (.01 if p_seg[p] == 'commercial_driver' and cat == 'Trucks' else 0))
        secondary = rng.random() < p_sec
        if secondary:
            search = rng.random() < min(.82, .40 + .30*risk + (.14 if contraband else 0))
        else:
            search = rng.random() < min(.015, .002 + .015*risk)  # random / canine exams
        # Seizure only when contraband is truly present AND found during a search.
        if contraband and search:
            seizure = rng.random() < 0.82
        elif contraband and not search and rng.random() < 0.01:
            seizure = True  # rare plain-view discovery
        else:
            seizure = False
        if IS_V9:                                    # role-based catch (see knobs above)
            if p_org[p] >= 0 and not org_dark[p] and not org_anchor[p]:
                secondary = search = seizure = False       # CLEAN cell carrier: no enforcement trail -> FN target
            elif org_anchor[p] and contraband:
                pc = V9_ANCHOR_SEIZE_TRAIN if dt < datetime(2024, 1, 1) else V9_ANCHOR_SEIZE_TEST
                if rng.random() < pc:
                    secondary = search = seizure = True    # ANCHOR caught (esp. train) -> graph signal
            elif p_org[p] < 0 and contraband and not seizure and rng.random() < V9_LONE_SEIZE:
                search = seizure = True                    # lone carrier: some caught (partial FN tail)
        arrest = (rng.random() < .55) if seizure else (rng.random() < (.0016 + (.002 if doc_exc else 0)))  # non-drug arrests too
        referral = (rng.random() < .72) if arrest else (rng.random() < .20 if seizure else rng.random() < .015 if secondary else False)
        admin = doc_exc or (rng.random() < .002 and secondary)

        # Outcome path on the hidden truth
        if contraband:
            contraband_n += 1
            if seizure: path = 'seized'; caught_n += 1
            elif search: path = 'searched_not_found'
            elif secondary: path = 'secondary_no_search'
            else: path = 'passed_primary_clean'
            if not seizure: fn_n += 1
        else:
            path = 'no_contraband'
        fp_search = search and not contraband
        if fp_search: fp_n += 1
        sec_n += secondary; search_n += search; seiz_n += seizure; arr_n += arrest; ref_n += referral; admin_n += admin

        if arrest: disp = 'arrest_event_recorded'
        elif seizure: disp = 'seizure_no_arrest'
        elif referral: disp = 'referred_for_investigation'
        elif admin: disp = choice(['administrative_action','denied_or_withdrawn'], [.82,.18])
        elif search: disp = 'released_after_search_no_finding'
        elif secondary: disp = 'released_after_secondary'
        else: disp = 'admitted_or_released'
        split = 'train' if dt < datetime(2024,1,1) else 'validation' if dt < datetime(2025,1,1) else 'test'
        if ENABLE_ORGS:
            if seizure and split == 'train': p_train_anchor[p] = True
            if contraband and not seizure and split == 'test': p_test_fn[p] = True
        label_time = (dt + timedelta(days=rng.randint(1,28) if (seizure or arrest or referral) else rng.randint(0,2))).isoformat()+'Z'
        lane = choice(['standard_primary_lane','trusted_traveler_lane','commercial_cargo_lane','pedestrian_processing','air_arrival_processing','secondary_review_area'], [.46,.08,.08,.10,.22,.06])
        if cat == 'Trucks': lane = choice(['commercial_cargo_lane','commercial_secondary_review','standard_primary_lane'], [.75,.15,.10])
        if mode == 'Air': lane = choice(['air_arrival_processing','air_connection_processing','air_secondary_review'], [.77,.17,.06])
        purpose = choice(purposes, [.18,.16,.15,.10,.09,.12,.03,.03,.02,.12])
        if p_seg[p] == 'commercial_driver': purpose = 'commercial_transport'
        elif p_seg[p] == 'routine_commuter': purpose = choice(['commute','shopping','business'], [.72,.18,.10])
        elif p_seg[p] == 'seasonal_worker': purpose = choice(['business','commute','family_visit'], [.5,.3,.2])
        origin = choice(origins.get(meta['region'], ['United States'])); dest = rng.choice(states)
        co_ids = ';'.join(fid('P', c+1) for c in cotravelers)
        oi = rng.randrange(N_OFFICERS); team = fid('TEAM', oi+1, 5)

        cw.writerow([eid, ets, ets, fy, mon, MONTHS[dt.month-1], dt.strftime('%A'), dt.hour, meta['region'], meta['field_office'], meta['state'], meta['port_of_entry'], meta['port_code'], mode, cat, choice(['inbound','outbound'], [.67,.33]), pid, obs_id, party, co_ids, veh, doc, biz, team, lane, purpose, origin, p_country[p], p_res[p], dest, min(repeat,365), min(veh_prior,365), min(doc_prior,365), str(secondary).lower(), str(search).lower(), str(seizure).lower(), str(arrest).lower(), str(referral).lower(), str(admin).lower(), disp, f'{risk:.4f}', split, label_time, ets])
        efw.writerow([eid, ets, (dt-timedelta(days=365)).isoformat()+'Z', ets,
                      json.dumps({'prior_person_crossings':min(repeat,365),'prior_vehicle_crossings':min(veh_prior,365),'prior_document_crossings':min(doc_prior,365),'port_code':meta['port_code'],'mode':mode,'category':cat,'hour':dt.hour,'day_of_week':dt.strftime('%A'),'declared_trip_purpose':purpose,'party_size':party}, sort_keys=True),
                      json.dumps({'lane_context':lane,'document_exception_at_primary':doc_exc,'synthetic_risk_score_pre_outcome':round(risk,4)}, sort_keys=True),
                      json.dumps({'secondary_referral_flag':secondary}, sort_keys=True),
                      str(secondary).lower(), str(search).lower(), str(seizure).lower(), str(arrest).lower(), str(referral).lower(), 'true', 'search_flag,seizure_flag,arrest_flag,prosecution_referral_flag,final_disposition,label_available_time_utc are post-outcome'])
        egw.writerow([eid, ets, pid, str(contraband).lower(), true_drug, f'{true_qty:.4f}' if contraband else '', path, str(seizure).lower(), str(contraband and not seizure).lower(), str(fp_search).lower(), 'hidden_ground_truth_evaluation_only', 'Hidden latent label; never use as a feature. Observable tables show only caught cases.'])
        spw.writerow([eid, 'event', split, 'temporal_by_event_timestamp plus family leakage group', 'train<2024-01-01; validation<2025-01-01; test>=2025-01-01', fid('C', p_family[p]+1, 7), 'Use family/community id to prevent strongly-linked leakage across splits.'])
        for lt, val, src, note in [('secondary',secondary,'primary_or_supervisory_review','available after referral decision'),('search',search,'secondary_or_exam_record','post-secondary for seizure target'),('seizure',seizure,'seizure_record','post-search outcome label'),('arrest',arrest,'custodial_event_record','post-arrest label'),('referral',referral,'investigative_or_prosecution_referral','delayed post-event label')]:
            lw.writerow([eid, lt, str(val).lower(), ets, label_time, src, 'true', note])

        # Stats (primary + co-travelers experience the crossing)
        party_members = [p] + cotravelers
        for m in party_members:
            ps = pstat[m]; ps[0] += 1; ps[1] += mode == 'Air'; ps[2] += mode != 'Air'
            ps[3] += cat == 'Pedestrians'; ps[4] += cat == 'Passenger Vehicles'; ps[5] += cat == 'Trucks'
            ps[6] += secondary; ps[7] += search
            set_minmax(pfirst, plast, m, date); p_counter[m] += 1; p_port_ct[m][meta['port_code']] += 1
        pstat[p][8] += seizure; pstat[p][9] += arrest  # contraband/arrest attributed to carrier
        dstat[docidx] += 1; set_minmax(dfirst, dlast, docidx, date); d_counter[docidx] += 1
        if vidx is not None:
            vs = vstat[vidx]; vs[0] += 1; vs[1] += secondary; vs[2] += search; vs[3] += seizure
            for m in party_members: vpers[vidx].add(m); pveh[m].add(vidx)
            vports[vidx].add(meta['port_code']); v_port_ct[vidx][meta['port_code']] += 1
            set_minmax(vfirst, vlast, vidx, date); v_counter[vidx] += 1
        if bidx is not None:
            bs = bstat[bidx]; bs[0] += 1; bs[1] += secondary; bs[2] += search; bs[3] += seizure
            bpers[bidx].add(p); set_minmax(bfirst, blast, bidx, date)
            if vidx is not None: bveh[bidx].add(vidx)
        os_ = ostat[oi]; os_[0] += 1; os_[1] += secondary; os_[2] += search; os_[3] += seizure; os_[4] += arrest
        set_minmax(ofirst, olast, oi, date)

        # --- Observable graph edges ------------------------------------------
        edge(pid,'person',eid,'event','PERSON_CROSSED_EVENT',eid,ets,ets,True)
        edge(doc,'document',eid,'event','DOCUMENT_PRESENTED_IN_EVENT',eid,ets,ets,True)
        edge(pid,'person',doc,'document','PERSON_USED_DOCUMENT',eid,ets,ets,True)
        edge(eid,'event',fid('PORT',int(meta['port_code']),4),'location','EVENT_OCCURRED_AT_PORT',eid,ets,ets,True)
        edge(eid,'event',team,'officer_team','EVENT_PROCESSED_BY_TEAM',eid,ets,ets,True)
        if veh:
            edge(veh,'vehicle',eid,'event','VEHICLE_USED_IN_EVENT',eid,ets,ets,True)
            edge(pid,'person',veh,'vehicle','PERSON_USED_VEHICLE',eid,ets,ets,True)
        if biz:
            edge(biz,'business',eid,'event','BUSINESS_LINKED_TO_EVENT',eid,ets,ets,True)
        for c in cotravelers:
            cpid = fid('P', c+1); cdoc = fid('DOC', rng.choice(p_docs[c])+1, 8)
            edge(cpid,'person',eid,'event','PERSON_CROSSED_EVENT',eid,ets,ets,True,conf=.95,evsrc='co_travel_manifest')
            edge(cdoc,'document',eid,'event','DOCUMENT_PRESENTED_IN_EVENT',eid,ets,ets,True,conf=.9,evsrc='co_travel_manifest')
            if veh: edge(cpid,'person',veh,'vehicle','PERSON_USED_VEHICLE',eid,ets,ets,True,conf=.9,evsrc='co_travel_manifest')
            cotravel[tuple(sorted((p, c)))] += 1
        if secondary:
            sec_id = fid('SEC', sec_n, 8)
            siw.writerow([sec_id, eid, pid, ets, (dt+timedelta(minutes=rng.randint(2,90))).isoformat()+'Z',
                          choice(['random_or_systematic','behavioral_referral','document_inconsistency','canine_or_tech_alert','manifest_discrepancy','watchlist_or_lookout'], [.30,.18,.16,.16,.12,.08]),
                          choice(['document_review','vehicle_exam','baggage_exam','cargo_exam','interview_only','non_intrusive_imaging'], [.24,.22,.20,.12,.14,.08]),
                          choice(['none_declared','personal_goods','commercial_goods','agricultural_items','currency_reportable','other'], [.46,.24,.12,.08,.04,.06]),
                          choice(['verified_ok','minor_discrepancy','unresolved','not_applicable'], [.78,.12,.04,.06]),
                          str(search).lower(),
                          'enforcement_action' if (seizure or arrest) else 'released_no_action' if not search else 'searched_no_finding',
                          team, 'available_after_secondary', (dt+timedelta(hours=rng.randint(1,12))).isoformat()+'Z'])
            edge(eid,'event','LBL_SECONDARY_TRUE','label','EVENT_RESULTED_IN_SECONDARY',eid,ets,label_time,False)
        if search:
            edge(eid,'event','LBL_SEARCH_TRUE','label','EVENT_RESULTED_IN_SEARCH',eid,ets,label_time,False)
        seizure_id = ''
        if seizure:
            seizure_id = fid('SZ', seiz_n, 7)
            edge(eid,'event',seizure_id,'seizure','EVENT_RESULTED_IN_SEIZURE',eid,ets,label_time,False)
            edge(eid,'event',seizure_id,'seizure','EVENT_LINKED_TO_SEIZURE',eid,ets,label_time,False)
            pkg = max(1, int(round(true_qty / max(.1, rng.uniform(.4,8)))))
            sw.writerow([seizure_id, eid, pid, ets, (dt+timedelta(minutes=rng.randint(5,240))).isoformat()+'Z', true_drug, f'{true_qty:.4f}', pkg, cat,
                         choice(['primary inspection area','secondary inspection area','cargo exam area','air processing context','marine or air support context'], [.18,.52,.18,.08,.04]),
                         choice(detect, [.22,.14,.16,.12,.11,.13,.06,.04,.02]), choice(components, [.68,.26,.06]),
                         choice(['pending','presumptive_positive','confirmed','not_submitted'], [.20,.22,.50,.08]),
                         (dt+timedelta(days=rng.randint(1,45))).isoformat()+'Z'])
        if arrest:
            ar = fid('AR', arr_n, 7)
            aw.writerow([ar, eid, pid, ets, (dt+timedelta(minutes=rng.randint(20,360))).isoformat()+'Z',
                         choice(['drug-related-enforcement-event','active-lookout-or-warrant','document-fraud-referral','administrative-custody-event','other-law-enforcement-referral'], [.46 if seizure else .14,.14,.12,.18,.10]),
                         seizure_id, choice(['controlled-substance-related','warrant-or-lookout-related','immigration-administrative','fraudulent-document-related','other-synthetic'], [.48 if seizure else .10,.16,.12,.12,.12]),
                         choice(['pending_review','referred','released','declined','administrative_resolution'], [.26,.34,.18,.08,.14]),
                         choice(['federal_partner','state_or_local_partner','internal_investigations','prosecutorial_review','administrative_review'], [.34,.24,.12,.20,.10]),
                         (dt+timedelta(days=rng.randint(0,30))).isoformat()+'Z'])
            edge(eid,'event',ar,'arrest','EVENT_RESULTED_IN_ARREST',eid,ets,label_time,False)
        if admin:
            edge(eid,'event','LBL_ADMIN_ACTION_TRUE','label','EVENT_LINKED_TO_ADMIN_ACTION',eid,ets,label_time,False)

        audit_event_rows.append([eid, ets, str(secondary).lower(), str(search).lower(), str(seizure).lower(), str(arrest).lower(), p_audit[p], p_age[p], p_sex[p], 'synthetic_audit_group;synthetic_age_bucket;sex_marker', 'ROC_AUC should be in [0.45,0.55]; PR_AUC near base prevalence'])
        if ev in narrative_idxs:
            narratives.append({'event_id':eid,'person_id':pid,'obs_id':obs_id,'vehicle_id':veh,'document_id':doc,'business_id':biz,'port':meta['port_of_entry'],'datetime':ets,'party_size':party,'co_ids':co_ids,'secondary':secondary,'search':search,'seizure':seizure,'arrest':arrest,'disposition':disp,'category':cat,'officer_team_id':team,'doc_exception':doc_exc,'name_token':obs_name})

    # ---- Static relationship edges (sparse, government-observable only) -------
    # Household co-residence (only links people who actually share an address).
    for h in range(N_HOUSEHOLDS):
        loc = fid('LOC', hh_res_loc[h]+1, 8)
        for m in hh_members[h]:
            ts = (pfirst[m]+'T00:00:00Z') if pfirst[m] else ''
            edge(fid('P', m+1),'person',loc,'location','ADDRESS_SHARED_BY_PERSONS','',ts,ts,True,conf=.85,evsrc='shared_residence_on_record')
    # Employer / work links.
    for i in range(N_PERSONS):
        if p_employer[i] != '':
            ts = (pfirst[i]+'T00:00:00Z') if pfirst[i] else ''
            edge(fid('P', i+1),'person',fid('BIZ', p_employer[i]+1, 6),'business','PERSON_LINKED_TO_BUSINESS','',ts,ts,True,conf=.8,evsrc='employment_or_manifest')
    # Co-travel person<->person (derived from actual shared crossings; weighted).
    for (a, b), cnt in cotravel.items():
        ts = (pfirst[a]+'T00:00:00Z') if pfirst[a] else ''
        edge(fid('P', a+1),'person',fid('P', b+1),'person','PERSON_ASSOCIATED_WITH_PERSON','',ts,ts,True,conf=min(.95,.5+.05*cnt),weight=cnt,evsrc='co_travel_observation')
    # Family member linkage (government-observable: customs declarations, immigration
    # petitions, travel-party records, shared-document addresses). ~90% of true family
    # pairs are captured; ~10% remain hidden (data-entry gaps, separate immigration files).
    FAMILY_EVIDENCE = [('customs_declaration', .40), ('immigration_petition', .25),
                       ('travel_party_linkage', .20), ('shared_document_address', .15)]
    _fam_ev_codes, _fam_ev_w = zip(*FAMILY_EVIDENCE)
    pp_family = 0
    for fam_id, members in fam_members.items():
        if len(members) < 2:
            continue
        for mi in range(len(members)):
            for mj in range(mi + 1, len(members)):
                if rng.random() > 0.90:
                    continue
                a, b = members[mi], members[mj]
                ts = (pfirst[a] + 'T00:00:00Z') if pfirst[a] else ''
                evsrc = rng.choices(_fam_ev_codes, weights=_fam_ev_w)[0]
                edge(fid('P', a+1), 'person', fid('P', b+1), 'person',
                     'FAMILY_MEMBER', '', ts, ts, True, conf=0.92, evsrc=evsrc)
                pp_family += 1
    print(f'  family edges emitted: {pp_family:,}', flush=True)
    # Vehicle registration.
    for v in range(N_VEHICLES):
        ts = (vfirst[v]+'T00:00:00Z') if vfirst[v] else ''
        if v_owner_p[v] != '':
            edge(fid('V', v+1),'vehicle',fid('P', v_owner_p[v]+1),'person','VEHICLE_REGISTERED_TO_PERSON','',ts,ts,True,conf=.9,evsrc='synthetic_registration')
        if v_owner_b[v] != '':
            edge(fid('V', v+1),'vehicle',fid('BIZ', v_owner_b[v]+1, 6),'business','VEHICLE_REGISTERED_TO_BUSINESS','',ts,ts,True,conf=.9,evsrc='synthetic_registration')
            edge(fid('V', v+1),'vehicle',fid('BIZ', v_owner_b[v]+1, 6),'business','VEHICLE_LINKED_TO_BUSINESS','',ts,ts,True,conf=.86,evsrc='synthetic_operational_link')
    # Repeated routes (only when genuinely repeated -> sparse).
    for i in range(N_PERSONS):
        for pc, c in p_port_ct[i].items():
            if c >= 3:
                edge(fid('P', i+1),'person',fid('PORT', int(pc), 4),'location','ROUTE_REPEATED_BY_PERSON','', (pfirst[i]+'T00:00:00Z') if pfirst[i] else '', (plast[i]+'T23:59:59Z') if plast[i] else '', True, conf=.8, weight=c, evsrc='repeated_route_observation')
    for v in range(N_VEHICLES):
        for pc, c in v_port_ct[v].items():
            if c >= 3:
                edge(fid('V', v+1),'vehicle',fid('PORT', int(pc), 4),'location','ROUTE_REPEATED_BY_VEHICLE','', (vfirst[v]+'T00:00:00Z') if vfirst[v] else '', (vlast[v]+'T23:59:59Z') if vlast[v] else '', True, conf=.8, weight=c, evsrc='repeated_route_observation')

    for f in files.values(): f.close()

    def write_csv(name, header, rows):
        with open(OUT/name, 'w', newline='', encoding='utf-8') as f:
            wr = csv.writer(f); wr.writerow(header); wr.writerows(rows)

    # ---- Entity tables -------------------------------------------------------
    write_csv('persons.csv',
        ['person_id','canonical_synthetic_name_token','synthetic_dob_year_bucket','synthetic_age_bucket','sex_marker','citizenship_country','residence_country','primary_border_region','synthetic_phone_token','household_id','residence_location_id','work_location_id','employer_business_id','document_count','known_vehicle_count','first_seen_timestamp_utc','last_seen_timestamp_utc','total_crossings','air_crossings','land_crossings','pedestrian_crossings','passenger_vehicle_crossings','truck_crossings','prior_secondary_count','prior_search_count','prior_seizure_count','prior_arrest_count'],
        ([fid('P', i+1), render_name(p_name[i][0], p_name[i][1], p_style[i], 'canonical_token', random.Random(0)), p_dob[i], p_age[i], p_sex[i], p_country[i], p_res[i], fam_region[p_family[i]], p_phone[i], fid('HH', p_hh[i]+1, 8), fid('LOC', hh_res_loc[p_hh[i]]+1, 8), (fid('BLOC', p_employer[i]+1, 7) if p_employer[i] != '' else ''), (fid('BIZ', p_employer[i]+1, 6) if p_employer[i] != '' else ''), len(p_docs[i]), len(pveh[i]), (pfirst[i]+'T00:00:00Z') if pfirst[i] else '', (plast[i]+'T23:59:59Z') if plast[i] else '', *pstat[i]] for i in range(N_PERSONS)))

    write_csv('persons_ground_truth.csv',
        ['person_id','family_id','ground_truth_community_id','community_type','synthetic_traveler_segment','latent_contraband_propensity','is_member_of_interdiction_cluster','ever_carried_contraband_flag','household_id','notes'],
        ([fid('P', i+1), fid('FAM', p_family[i]+1, 7), fid('C', p_family[i]+1, 7), fam_type[p_family[i]], p_seg[i], round(p_lat[i], 4), str(fam_eval_pos[p_family[i]]).lower(), str(pstat[i][8] > 0 or p_lat[i] > 0.05).lower(), fid('HH', p_hh[i]+1, 8), 'Latent generator truth for community/anomaly evaluation only; never an operational feature.'] for i in range(N_PERSONS)))

    # Hidden co-offender org membership (V6) -- the GOLDEN dataset. Holds the FULL
    # cell membership, including `is_dark` members who are truly linked but leave no
    # observable trail. `org_id` must NEVER appear on persons.csv / node_features.csv /
    # event_features.csv; it is evaluation-only, exactly like family_id.
    if ENABLE_ORGS and N_ORGS_MADE:
        # Non-dark members are eligible to surface, but `is_observable` means
        # a same-org tie actually appeared in observable co-travel, vehicle, or
        # carrier/broker records.
        for (a, b), _cnt in cotravel.items():
            if p_org[a] >= 0 and p_org[a] == p_org[b] and not org_dark[a] and not org_dark[b]:
                org_observable_members.add(a)
                org_observable_members.add(b)
        for people in vpers:
            by_org = defaultdict(list)
            for m in people:
                if p_org[m] >= 0 and not org_dark[m]:
                    by_org[p_org[m]].append(m)
            for members in by_org.values():
                if len(members) >= 2:
                    org_observable_members.update(members)
        for people in bpers:
            by_org = defaultdict(list)
            for m in people:
                if p_org[m] >= 0 and not org_dark[m]:
                    by_org[p_org[m]].append(m)
            for members in by_org.values():
                if len(members) >= 2:
                    org_observable_members.update(members)

        org_anchor = {o: any(p_train_anchor[m] for m in mem) for o, mem in org_members.items()}
        org_fn = {o: any(p_test_fn[m] for m in mem) for o, mem in org_members.items()}
        org_rows = []
        for o in range(N_ORGS_MADE):
            mem = org_members[o]
            srcfam = ';'.join(fid('FAM', f+1, 7) for f in sorted(org_families[o]))
            for m in mem:
                org_rows.append([fid('ORG', o+1, 6), fid('P', m+1), p_role.get(m, 'associate'),
                                 org_mode[o], str(m in org_observable_members).lower(), str(org_dark[m]).lower(),
                                 str(org_anchor[o]).lower(), str(org_fn[o]).lower(), round(org_obs[o], 3),
                                 srcfam,
                                 'Hidden co-offender cell; evaluation only, never an operational feature. '
                                 'Dark members are truly linked but unfindable in observable data.'])
        write_csv('org_membership_ground_truth.csv',
            ['org_id','person_id','org_role','org_mode_affinity','is_observable','is_dark',
             'org_contains_train_detected_anchor','org_contains_test_false_negative',
             'org_observability','source_family_ids','notes'], org_rows)

    write_csv('vehicles.csv',
        ['vehicle_id','synthetic_plate_token','plate_state_or_country','vehicle_type','make_bucket','model_bucket','model_year_bucket','color','registration_status','owner_person_id','owner_business_id','rental_flag','commercial_flag','first_seen_timestamp_utc','last_seen_timestamp_utc','total_crossings','unique_person_count','unique_port_count','prior_secondary_count','prior_search_count','prior_seizure_count'],
        ([fid('V', v+1), f'SYN-PLT-{v+1:07d}', rng.choice(states+['MX','CAN','SYN']), v_type[v], choice(['domestic_common','import_common','commercial_heavy','rental_fleet','older_mixed','other_synthetic'], [.28,.27,.12,.08,.18,.07]), choice(['compact','midsize','fullsize','utility','cargo','tractor','unknown']), choice(['pre_2000','2000_2009','2010_2014','2015_2019','2020_2025','unknown'], [.04,.12,.20,.34,.26,.04]), choice(['white','black','silver','gray','blue','red','green','brown','yellow','unknown']), choice(['current','expired','temporary','unknown','exception_review'], [.86,.05,.03,.05,.01]), (fid('P', v_owner_p[v]+1) if v_owner_p[v] != '' else ''), (fid('BIZ', v_owner_b[v]+1, 6) if v_owner_b[v] != '' else ''), str(v_rental[v]).lower(), str(v_commercial[v]).lower(), (vfirst[v]+'T00:00:00Z') if vfirst[v] else '', (vlast[v]+'T23:59:59Z') if vlast[v] else '', vstat[v][0], len(vpers[v]), len(vports[v]), vstat[v][1], vstat[v][2], vstat[v][3]] for v in range(N_VEHICLES)))

    write_csv('documents.csv',
        ['document_id','document_type','issuing_country','synthetic_document_token','person_id','issue_year_bucket','expiration_year_bucket','first_seen_timestamp_utc','last_seen_timestamp_utc','total_crossings','mismatch_or_exception_flag','document_validity_status'],
        ([fid('DOC', d+1, 8), choice(DOC_TYPES, DOC_W), p_country[doc_person[d]], f'SYN-DOC-{d+1:08d}', fid('P', doc_person[d]+1), choice(['pre_2010','2010_2014','2015_2019','2020_2025','unknown'], [.08,.18,.28,.42,.04]), choice(['2022_2024','2025_2027','2028_2030','2031_plus','unknown'], [.14,.36,.31,.15,.04]), (dfirst[d]+'T00:00:00Z') if dfirst[d] else '', (dlast[d]+'T23:59:59Z') if dlast[d] else '', dstat[d], str(dmismatch[d]).lower(), 'exception_review' if dmismatch[d] else choice(['valid','expired','unknown'], [.94,.035,.025])] for d in range(N_DOCS)))

    write_csv('businesses.csv',
        ['business_id','business_type','synthetic_business_name_token','country','state_or_region','business_location_id','first_seen_timestamp_utc','last_seen_timestamp_utc','total_crossings_linked','total_vehicles_linked','total_persons_linked','prior_secondary_count','prior_search_count','prior_seizure_count'],
        ([fid('BIZ', b+1, 6), b_type[b], f'SYN-BIZNAME-{b+1:06d}', b_country[b], b_state[b], fid('BLOC', b+1, 7), (bfirst[b]+'T00:00:00Z') if bfirst[b] else '', (blast[b]+'T23:59:59Z') if blast[b] else '', bstat[b][0], len(bveh[b]), len(bpers[b]), bstat[b][1], bstat[b][2], bstat[b][3]] for b in range(N_BUSINESSES)))

    # Locations: ports + household residences + business sites + route anchors.
    loc_rows = []
    for pc, m in ports.items():
        loc_rows.append([fid('PORT', int(pc), 4), 'port_of_entry', m['port_of_entry'], 'United States', m['state'], m['region'], m['field_office'], 'GRID_PORT_'+pc, 'GRID_PORT_'+pc, 'true', pc])
    for h in range(N_HOUSEHOLDS):
        reg = fam_region[p_family[hh_members[h][0]]] if hh_members[h] else 'Coastal/Interior'
        loc_rows.append([fid('LOC', hh_res_loc[h]+1, 8), 'synthetic_residence_anchor', f'SYN-RES-{hh_res_loc[h]+1:08d}', choice(['United States','Mexico','Canada','Other'], [.70,.18,.08,.04]), rng.choice(states), reg, rng.choice(field_offices), f'GRID_SYN_{rng.randint(1,999):03d}', f'GRID_SYN_{rng.randint(1,999):03d}', 'false', ''])
    for b in range(N_BUSINESSES):
        loc_rows.append([fid('BLOC', b+1, 7), 'synthetic_business_anchor', f'SYN-BIZLOC-{b+1:07d}', b_country[b], b_state[b], choice(['Coastal/Interior','Northern Border','Southern Border','Preclearance'], [.42,.20,.32,.06]), rng.choice(field_offices), f'GRID_SYN_{rng.randint(1,999):03d}', f'GRID_SYN_{rng.randint(1,999):03d}', 'false', ''])
    for i in range(1, N_ROUTE_LOCS+1):
        loc_rows.append([fid('RLOC', i, 7), choice(['synthetic_warehouse_anchor','synthetic_route_anchor'], [.5,.5]), f'SYN-ROUTE-{i:07d}', choice(['United States','Mexico','Canada','Other'], [.62,.24,.10,.04]), rng.choice(states), choice(['Coastal/Interior','Northern Border','Southern Border','Preclearance'], [.42,.20,.32,.06]), rng.choice(field_offices), f'GRID_SYN_{rng.randint(1,999):03d}', f'GRID_SYN_{rng.randint(1,999):03d}', 'false', ''])
    write_csv('locations.csv', ['location_id','location_type','synthetic_location_token','country','state','region','field_office','latitude_bucket_or_synthetic_grid_id','longitude_bucket_or_synthetic_grid_id','port_of_entry_flag','port_code'], loc_rows)

    write_csv('officers_or_teams.csv', ['officer_team_id','field_office','port_of_entry','shift_pattern','inspection_role','first_seen_timestamp_utc','last_seen_timestamp_utc','total_events_processed','secondary_referrals_made','searches_participated','seizures_participated','arrests_participated'], ([fid('TEAM', o+1, 5), ports[o_port[o]]['field_office'], ports[o_port[o]]['port_of_entry'], o_shift[o], o_role[o], (ofirst[o]+'T00:00:00Z') if ofirst[o] else '', (olast[o]+'T23:59:59Z') if olast[o] else '', ostat[o][0], ostat[o][1], ostat[o][2], ostat[o][3], ostat[o][4]] for o in range(N_OFFICERS)))

    write_csv('audit_attributes.csv', ['person_id','synthetic_audit_group','synthetic_age_bucket','sex_marker','citizenship_country','residence_country','language_preference_synthetic','audit_only_flag','usage_note'], ([fid('P', i+1), p_audit[i], p_age[i], p_sex[i], p_country[i], p_res[i], p_lang[i], 'true', 'Audit-only. Do NOT use as a predictive feature. Smuggling propensity is generated independent of these attributes.'] for i in range(N_PERSONS)))

    # Phone tokens listed for completeness; they create NO person<->person edges.
    write_csv('contact_anchors.csv', ['contact_anchor_id','contact_anchor_type','synthetic_contact_token','linked_person_id','creates_person_links','audit_note'], ([f'CON{i+1:08d}', 'synthetic_phone_token', p_phone[i], fid('P', i+1), 'false', 'Phone is a stored data point per person. By design it creates no person-to-person edges.'] for i in range(N_PERSONS)))

    write_csv('communities.csv', ['ground_truth_community_id','family_id','community_type','home_region','latent_contraband_propensity','member_count','is_positive_interdiction_eval_cluster','documentation_note'], ([fid('C', f+1, 7), fid('FAM', f+1, 7), fam_type[f], fam_region[f], round(fam_lat[f], 4), len(fam_members[f]), str(fam_eval_pos[f]).lower(), 'Ground-truth family/affinity community for NMI/ARI; not a real case group.'] for f in range(N_FAMILIES)))

    # Ground-truth community labels (the family is the community).
    def membership_rows():
        for i in range(N_PERSONS):
            f = p_family[i]; yield [fid('P', i+1), 'person', fid('C', f+1, 7), fam_type[f], 'canonical_entity', 1.0, (pfirst[i]+'T00:00:00Z') if pfirst[i] else '', (plast[i]+'T23:59:59Z') if plast[i] else '', str(fam_eval_pos[f]).lower(), 'nmi_ari_node_eval', 'Ground-truth family community label.']
        for v in range(N_VEHICLES):
            f = p_family[v_owner_p[v]] if v_owner_p[v] != '' else None
            cid = fid('C', f+1, 7) if f is not None else (fid('BIZFLEET', v_owner_b[v]+1, 6) if v_owner_b[v] != '' else 'C0000000')
            ct = fam_type[f] if f is not None else 'commercial_or_rental_fleet'
            yield [fid('V', v+1), 'vehicle', cid, ct, 'canonical_entity', 1.0, (vfirst[v]+'T00:00:00Z') if vfirst[v] else '', (vlast[v]+'T23:59:59Z') if vlast[v] else '', str(fam_eval_pos[f]).lower() if f is not None else 'false', 'nmi_ari_node_eval', 'Vehicle community via owner family or fleet.']
        for d in range(N_DOCS):
            f = p_family[doc_person[d]]; yield [fid('DOC', d+1, 8), 'document', fid('C', f+1, 7), fam_type[f], 'canonical_entity', 1.0, (dfirst[d]+'T00:00:00Z') if dfirst[d] else '', (dlast[d]+'T23:59:59Z') if dlast[d] else '', str(fam_eval_pos[f]).lower(), 'nmi_ari_node_eval', 'Document community via canonical holder family.']
        for obs_id, p, eid, ts, style, variant in obs_event_map:
            f = p_family[p]; yield [obs_id, 'observed_person_record', fid('C', f+1, 7), fam_type[f], 'unresolved_observation', .75, ts, ts, str(fam_eval_pos[f]).lower(), 'raw_graph_nmi_ari_eval_after_resolution', 'Observed noisy node maps to canonical family ground truth.']
    write_csv('ground_truth_community_labels.csv', ['entity_id','entity_type','ground_truth_community_id','community_type','membership_source','membership_strength','valid_from_utc','valid_to_utc','is_positive_interdiction_eval_cluster','evaluation_use','notes'], membership_rows())

    # Entity-resolution pairs.
    er_pairs = []; seen = set(); multi = [p for p, obs in obs_by_person.items() if len(obs) > 1]
    if multi:
        for _ in range(N_ER_PAIRS//2):
            p = rng.choice(multi); a, b = rng.sample(obs_by_person[p], 2); key = tuple(sorted((a, b)))
            if key in seen: continue
            seen.add(key); er_pairs.append([fid('ERPAIR', len(er_pairs)+1, 7), a, b, 'true', fid('P', p+1), fid('P', p+1), 'same_canonical_person', choice(['easy','medium','hard'], [.30,.45,.25]), choice(['train','validation','test'], [.65,.15,.20]), 'Entity-resolution / name-matching evaluation.'])
    guard = 0
    while len(er_pairs) < N_ER_PAIRS and guard < N_ER_PAIRS*20:
        guard += 1; p1, p2 = rng.sample(range(N_PERSONS), 2)
        if p1 == p2 or not obs_by_person[p1] or not obs_by_person[p2]: continue
        if rng.random() < .45 and p_family[p1] != p_family[p2]: continue
        a = rng.choice(obs_by_person[p1]); b = rng.choice(obs_by_person[p2]); key = tuple(sorted((a, b)))
        if key in seen: continue
        seen.add(key); er_pairs.append([fid('ERPAIR', len(er_pairs)+1, 7), a, b, 'false', fid('P', p1+1), fid('P', p2+1), 'different_canonical_person', choice(['easy','medium','hard'], [.25,.45,.30]), choice(['train','validation','test'], [.65,.15,.20]), 'Hard negatives may share style/family.'])
    write_csv('entity_resolution_pairs.csv', ['pair_id','observed_person_record_id_a','observed_person_record_id_b','true_same_person','canonical_person_id_a','canonical_person_id_b','truth_relation','match_difficulty','data_split','notes'], er_pairs)

    # Node features.
    def node_rows():
        for i in range(N_PERSONS): yield [fid('P', i+1), 'person', json.dumps({'age_bucket':p_age[i],'citizenship_country':p_country[i],'primary_border_region':fam_region[p_family[i]]}), json.dumps({'first_seen':pfirst[i],'last_seen':plast[i]}), json.dumps({'total_crossings':pstat[i][0],'prior_secondary_count':pstat[i][6],'prior_search_count':pstat[i][7],'known_vehicle_count':len(pveh[i])}), json.dumps({'segment':p_seg[i]}), (pfirst[i]+'T00:00:00Z') if pfirst[i] else '', (plast[i]+'T23:59:59Z') if plast[i] else '', (plast[i]+'T23:59:59Z') if plast[i] else '', 'conditional_by_target_time', 'false']
        for v in range(N_VEHICLES): yield [fid('V', v+1), 'vehicle', json.dumps({'vehicle_type':v_type[v],'commercial_flag':v_commercial[v],'rental_flag':v_rental[v]}), json.dumps({'first_seen':vfirst[v],'last_seen':vlast[v]}), json.dumps({'total_crossings':vstat[v][0],'unique_person_count':len(vpers[v])}), '{}', (vfirst[v]+'T00:00:00Z') if vfirst[v] else '', (vlast[v]+'T23:59:59Z') if vlast[v] else '', (vlast[v]+'T23:59:59Z') if vlast[v] else '', 'conditional_by_target_time', 'false']
        for b in range(N_BUSINESSES): yield [fid('BIZ', b+1, 6), 'business', json.dumps({'business_type':b_type[b]}), json.dumps({'first_seen':bfirst[b],'last_seen':blast[b]}), json.dumps({'total_crossings_linked':bstat[b][0],'total_vehicles_linked':len(bveh[b])}), '{}', (bfirst[b]+'T00:00:00Z') if bfirst[b] else '', (blast[b]+'T23:59:59Z') if blast[b] else '', (blast[b]+'T23:59:59Z') if blast[b] else '', 'conditional_by_target_time', 'false']
        for pc, m in ports.items(): yield [fid('PORT', int(pc), 4), 'location', json.dumps({'location_type':'port_of_entry','state':m['state'],'field_office':m['field_office'],'region':m['region']}), '{}', '{}', '{}', '', '', '', 'true', 'false']
        for o in range(N_OFFICERS): yield [fid('TEAM', o+1, 5), 'officer_team', json.dumps({'field_office':ports[o_port[o]]['field_office'],'role':o_role[o]}), json.dumps({'first_seen':ofirst[o],'last_seen':olast[o]}), json.dumps({'events':ostat[o][0],'secondary':ostat[o][1],'searches':ostat[o][2]}), json.dumps({'shift':o_shift[o]}), (ofirst[o]+'T00:00:00Z') if ofirst[o] else '', (olast[o]+'T23:59:59Z') if olast[o] else '', (olast[o]+'T23:59:59Z') if olast[o] else '', 'conditional_by_target_time', 'false']
    write_csv('node_features.csv', ['node_id','node_type','static_features','temporal_features','count_features','categorical_features_encoded','feature_window_start_utc','feature_window_end_utc','feature_available_time_utc','leakage_safe_flag','audit_only_flag'], node_rows())

    # Narrative validation subset.
    with open(OUT/'narrative_validation_subset.jsonl', 'w', encoding='utf-8') as f:
        for r in narratives:
            parts = [f"At {r['datetime']}, observed synthetic identity token {r['name_token']} ({r['obs_id']}) was processed at {r['port']} for a {r['category']} crossing in a party of {r['party_size']}."]
            if r['vehicle_id']: parts.append(f"The observed record was associated with synthetic vehicle {r['vehicle_id']}.")
            if r['business_id']: parts.append(f"Synthetic carrier or business entity {r['business_id']} was linked to the crossing context.")
            parts.append(f"Synthetic document {r['document_id']} was presented.")
            if r['doc_exception']: parts.append('A document exception was recorded for administrative review.')
            if r['secondary']: parts.append('The event was referred for secondary inspection.')
            if r['search']: parts.append('A search or examination record was created.')
            if r['seizure']: parts.append('A seizure event was recorded in the structured seizure table.')
            if r['arrest']: parts.append('An arrest event was recorded and linked to the crossing event.')
            parts.append(f"The final synthetic disposition was {r['disposition']}.")
            ents = [{'text':r['obs_id'],'label':'OBSERVED_PERSON_RECORD_ID'},{'text':r['name_token'],'label':'SYNTHETIC_NAME_TOKEN'},{'text':r['person_id'],'label':'CANONICAL_PERSON_ID'},{'text':r['document_id'],'label':'DOCUMENT_ID'},{'text':r['port'],'label':'PORT_OF_ENTRY'},{'text':r['officer_team_id'],'label':'OFFICER_TEAM_ID'}]
            if r['vehicle_id']: ents.append({'text':r['vehicle_id'],'label':'VEHICLE_ID'})
            if r['business_id']: ents.append({'text':r['business_id'],'label':'BUSINESS_ID'})
            f.write(json.dumps({'event_id':r['event_id'],'narrative_text':' '.join(parts),'expected_entities':ents,'expected_relations':['PERSON_CROSSED_EVENT','DOCUMENT_PRESENTED_IN_EVENT']+(['VEHICLE_USED_IN_EVENT'] if r['vehicle_id'] else []),'linked_table_rows':{'crossing_events':r['event_id'],'observed_person_records':r['obs_id'],'persons':r['person_id'],'vehicles':r['vehicle_id'],'documents':r['document_id'],'businesses':r['business_id']},'redaction_status':'fully_synthetic_no_real_pii_artificial_name_tokens_only','ner_gold_labels':ents}, sort_keys=True)+'\n')

    # Fairness negative control.
    write_csv('fairness_negative_control.csv', ['event_id','event_timestamp_utc','target_secondary','target_search','target_seizure','target_arrest','synthetic_audit_group','synthetic_age_bucket','sex_marker','allowed_demographic_only_features','expected_result'], audit_event_rows)
    gc = defaultdict(lambda: [0,0,0,0,0])
    for r in audit_event_rows:
        g = r[6]; gc[g][0] += 1; gc[g][1] += r[2] == 'true'; gc[g][2] += r[3] == 'true'; gc[g][3] += r[4] == 'true'; gc[g][4] += r[5] == 'true'
    write_csv('fairness_group_rates.csv', ['synthetic_audit_group','event_count','secondary_rate','search_rate','seizure_rate','arrest_rate','negative_control_interpretation'], ([g, c[0], round(c[1]/c[0], 5), round(c[2]/c[0], 5), round(c[3]/c[0], 5), round(c[4]/c[0], 5), 'Rates should vary only by noise; demographics-only model expected near chance.'] for g, c in sorted(gc.items())))
    base_prev = {'secondary':sec_n/N_EVENTS,'search':search_n/N_EVENTS,'seizure':seiz_n/N_EVENTS,'arrest':arr_n/N_EVENTS}
    with open(OUT/'fairness_negative_control_spec.json', 'w', encoding='utf-8') as f:
        json.dump({'task':'Train using only synthetic_audit_group, synthetic_age_bucket, sex_marker. Performance should be at chance.','expected_roc_auc_range':[0.45,0.55],'expected_pr_auc_baseline_by_target':base_prev,'demographic_features_allowed':['synthetic_audit_group','synthetic_age_bucket','sex_marker'],'forbidden_features':['port_code','prior crossings','risk score','document exception','search/seizure/arrest labels','community_id','latent_contraband_propensity'],'falsification_rule':'Flag the dataset if demographics-only ROC-AUC exceeds 0.55.'}, f, indent=2, sort_keys=True)

    # Golden seed + scale profile.
    golden = set(rng.sample([fid('E', e) for e in range(1, N_EVENTS+1)], 250))
    write_csv('golden_seed_event_ids.csv', ['event_id','subset_name','target_size','positive_inclusion_rule','notes'], ([eid, 'golden_seed_250', 250, 'random sample for hand verification', 'Small hand-verifiable subset; do not train only on this.'] for eid in sorted(golden)))
    scale_rows = []
    for n in [250, 5_000, 10_000, 25_000, N_EVENTS]:
        scale_rows.append([n, round(base_prev['secondary'], 6), round(n*base_prev['secondary'], 2), round(base_prev['search'], 6), round(n*base_prev['search'], 2), round(base_prev['seizure'], 6), round(n*base_prev['seizure'], 2), round(base_prev['arrest'], 6), round(n*base_prev['arrest'], 2), 'Evaluate imbalanced targets with PR-AUC, recall@k, precision@k, calibration; accuracy is insufficient.'])
    write_csv('scale_profile_and_metrics.csv', ['event_count','secondary_rate','expected_secondary_positives','search_rate','expected_search_positives','seizure_rate','expected_seizure_positives','arrest_rate','expected_arrest_positives','required_metrics'], scale_rows)

    write_csv('temporal_fields_manifest.csv', ['table_name','primary_time_column','additional_time_columns','time_zone_or_basis','pre_outcome_use'], [
        ['crossing_events.csv','event_timestamp_utc','label_available_time_utc;feature_available_time_utc','UTC-like synthetic ISO-8601','feature_available_time_utc is safe for pre-outcome features'],
        ['edges.csv','edge_timestamp_utc','first_seen_timestamp_utc;last_seen_timestamp_utc;temporal_valid_from_utc;feature_available_time_utc','UTC-like synthetic ISO-8601','use leakage_safe_flag and feature_available_time_utc'],
        ['labels.csv','label_time_utc','event_timestamp_utc','UTC-like synthetic ISO-8601','labels are not pre-outcome features'],
        ['secondary_inspections.csv','secondary_start_timestamp_utc','post_secondary_available_time_utc','UTC-like synthetic ISO-8601','available_after_secondary only'],
        ['event_ground_truth.csv','event_timestamp_utc','','UTC-like synthetic ISO-8601','hidden truth; evaluation only, never a feature'],
        ['observed_person_records.csv','event_timestamp_utc','raw_record_available_time_utc','UTC-like synthetic ISO-8601','raw identity observations are pre-resolution inputs'],
    ])

    if scale_key in ('v7', 'v8'):
        try:
            from v7_er import build_v7_er_layer
        except ImportError:
            from Documents.Data.scripts.v7_er import build_v7_er_layer
        build_v7_er_layer(OUT, seed=SEED + 4, max_pair_rows=N_ER_PAIRS * 2)

    # Schema, config, docs, validation.
    table_counts = {}; schema = {}
    for p in sorted(OUT.glob('*.csv')):
        with open(p, encoding='utf-8') as f:
            reader = csv.reader(f); header = next(reader); schema[p.name] = {'format':'csv','columns':header}; table_counts[p.name] = sum(1 for _ in reader)
    table_counts['narrative_validation_subset.jsonl'] = sum(1 for _ in open(OUT/'narrative_validation_subset.jsonl', encoding='utf-8'))
    schema['narrative_validation_subset.jsonl'] = {'format':'jsonl','columns_or_keys':['event_id','narrative_text','expected_entities','expected_relations','linked_table_rows','redaction_status','ner_gold_labels']}
    with open(OUT/'SCHEMA.json', 'w', encoding='utf-8') as f: json.dump(schema, f, indent=2, sort_keys=True)

    # person<->person edge accounting for the validation report.
    pp_assoc = len(cotravel)
    with open(OUT/'GENERATION_CONFIG.json', 'w', encoding='utf-8') as f:
        _org_changes = (['hidden non-family co-offender orgs (org_membership_ground_truth.csv): '
                         'cross-family cells surfacing only via co-travel/shared-vehicle/shared-carrier, '
                         'with dark members truly-linked-but-unfindable'] if ENABLE_ORGS else [])
        json.dump({'seed':SEED,'scale_key':scale_key,'version':'v3_realism_rework','counts':{'events':N_EVENTS,'persons':N_PERSONS,'families':N_FAMILIES,'households':N_HOUSEHOLDS,'vehicles':N_VEHICLES,'documents':N_DOCS,'businesses':N_BUSINESSES,'officer_teams':N_OFFICERS,'orgs':N_ORGS_MADE},'design_changes':['phone is a data point with no edges','household-only address edges','family spans multiple households','co-travel parties create person links','undetected smuggling via hidden event_ground_truth','secondary_inspections table for stopped travellers','citizenship conditioned on border region','demographics on the person record with audit methodology preserved']+_org_changes,'source_files':[TRAVELERS.name,NATIONWIDE.name,AMO.name],'privacy':'fully synthetic; aggregate source files used only for calibration'}, f, indent=2, sort_keys=True)

    with open(OUT/'DATA_DICTIONARY.md', 'w', encoding='utf-8') as f:
        f.write('# Data Dictionary\n\nAll identifiers and PII-like values are synthetic. Outcome fields and ground-truth labels are evaluation-only unless explicitly part of a training-label task.\n\n')
        f.write('## Key modelling notes\n')
        f.write('- `synthetic_phone_token` (persons.csv / contact_anchors.csv) is a stored data point. It creates **no** person-to-person edges.\n')
        f.write('- `family_id` (persons_ground_truth.csv) is the hidden kinship community; it can span multiple `household_id`/`residence_location_id` values. `ADDRESS_SHARED_BY_PERSONS` links only co-residents.\n')
        f.write('- `event_ground_truth.csv` holds the hidden `true_contraband_present` label, independent of enforcement outcome. Observable tables show only caught cases.\n')
        f.write('- Demographics live on `persons.csv` (document-derived). `audit_attributes.csv` is audit-only and must not be used as a predictive feature.\n\n')
        if ENABLE_ORGS and N_ORGS_MADE:
            f.write('- `org_membership_ground_truth.csv` is evaluation-only. `is_dark` means deliberately unfindable; `is_observable` means the member actually surfaced through same-org co-travel, shared vehicle, or shared carrier/broker records.\n\n')
        for t, s in sorted(schema.items()):
            f.write(f'## {t}\n')
            for col in s.get('columns', s.get('columns_or_keys', [])): f.write(f'- `{col}`\n')
            f.write('\n')

    dv = list(degree.values())
    deg = {'nodes_with_degree':len(dv),'min':min(dv) if dv else 0,'max':max(dv) if dv else 0,'mean':round(statistics.mean(dv),3) if dv else 0,'median':statistics.median(dv) if dv else 0,'p95':sorted(dv)[int(.95*len(dv))] if dv else 0}
    with open(OUT/'VALIDATION_REPORT.md', 'w', encoding='utf-8') as f:
        f.write(f'# Validation Report ({scale_key})\n\n')
        f.write('## Realism feedback coverage\n')
        f.write(f'- Person<->person edges come from co-travel (`PERSON_ASSOCIATED_WITH_PERSON`: {pp_assoc:,} weighted pairs), government family records (`FAMILY_MEMBER`: {pp_family:,} pairs, ~90% of true family links), and shared household residence. No phone-based edges exist.\n')
        f.write(f'- Families span multiple households: {N_FAMILIES:,} families across {N_HOUSEHOLDS:,} households (mean {N_HOUSEHOLDS/max(1,N_FAMILIES):.2f} households/family).\n')
        f.write(f'- Undetected smuggling: {contraband_n:,} true-contraband events, {caught_n:,} caught (seizures), {fn_n:,} false negatives ({(fn_n/contraband_n*100) if contraband_n else 0:.1f}% slipped through).\n')
        f.write(f'- False-positive searches (searched, no contraband): {fp_n:,}.\n')
        if ENABLE_ORGS and N_ORGS_MADE:
            _org_mem = sum(len(m) for m in org_members.values())
            f.write(f'- Hidden co-offender orgs (V6/V7): {N_ORGS_MADE:,} cross-family cells, {_org_mem:,} members '
                    f'({len(org_observable_members):,} actually observable, {sum(org_dark):,} dark / truly-linked-but-unfindable). '
                    f'Surfaced only via co-travel/shared-vehicle/shared-carrier; org_id is golden ground truth, never a feature.\n')
        if scale_key in ('v7', 'v8'):
            f.write('- V7 entity-resolution layer: observed identity records are summarized into deterministic baseline clusters, oracle clusters, and weak-link recoverability evidence for GNN ER experiments.\n')
        if scale_key == 'v8':
            f.write('- V8: every co-traveler on an event also gets an observed_person_records.csv row (not just the primary), so co-travel is observable at the record level; co-traveler records use ids `<primary_obs_id>-<k>` and are generated from RNGs independent of the main corpus draw, so v8 is v7 plus these additional rows.\n')
        f.write(f'- Stopped-traveller detail: `secondary_inspections.csv` = {table_counts.get("secondary_inspections.csv",0):,} rows; seizures and arrests carry person_id.\n\n')
        f.write('## Row Counts\n')
        for k, v in sorted(table_counts.items()): f.write(f'- {k}: {v:,}\n')
        f.write('\n## Outcome Counts\n')
        for k, v in {'secondary_referrals':sec_n,'searches':search_n,'seizures':seiz_n,'arrests':arr_n,'referrals':ref_n,'administrative_actions':admin_n}.items(): f.write(f'- {k}: {v:,}\n')
        f.write('\n## Positive Rates\n')
        for k, v in base_prev.items(): f.write(f'- {k}: {v:.6f}\n')
        f.write('\n## Graph Summary\n')
        f.write(f'- Total edges: {edge_count[0]:,}\n')
        for k, v in deg.items(): f.write(f'- Degree {k}: {v}\n')
        f.write('\n## Privacy Statement\nAll data are synthetic. No real names, addresses, phones, emails, license plates, document numbers, officers, cases, or seizures are generated.\n')

    with open(OUT/'README.md', 'w', encoding='utf-8') as f:
        f.write(f'# Synthetic CBP-Style Entity-Centric Crossing Event Graph Corpus ({scale_key})\n\n')
        f.write('Fully synthetic. No row represents a real person, vehicle, document, officer/team, case, event, seizure, arrest, address, phone, email, license plate, or name. The uploaded aggregate CBP-style CSVs were used only to calibrate FY/month/region/field-office/port/mode/category and drug-type distributions. Do not use for real enforcement decisions.\n\n')
        f.write('## What changed in this rework (realism)\n\n')
        f.write('1. **Connectivity = what the government observes.** Person-to-person links arise from co-travel, family records (customs declarations, immigration petitions, travel-party linkage), shared household residence, shared vehicles, vehicle registration, shared employer, and repeated routes. The population-wide phone/address "social web" from earlier versions is gone.\n')
        f.write('2. **Phone is a data point, not an edge.** Each person has a `synthetic_phone_token`; no two people are ever linked because of a phone number.\n')
        f.write('3. **Family connections are government-observable.** `FAMILY_MEMBER` edges represent family relationships discoverable from customs declarations, immigration petitions (I-130), travel-party records, and shared-document addresses. ~90% of true family pairs are captured; ~10% remain hidden due to data-entry gaps or separate immigration files — a realistic GNN prediction target.\n')
        f.write('4. **Undetected smuggling.** `event_ground_truth.csv` records who was actually carrying contraband, independent of whether they were caught. Most smuggling events are never stopped.\n')
        f.write('5. **Stopped-traveller data.** `secondary_inspections.csv` captures the richer record collected during secondary inspection; seizures/arrests carry person_id.\n')
        f.write('6. **Demographics on the person record** (document-derived), with the fairness audit grouping kept separate in `audit_attributes.csv` and smuggling generated independent of demographics.\n\n')
        f.write('## Files\n')
        for k, v in sorted(table_counts.items()): f.write(f'- `{k}`: {v:,} rows\n')

    import shutil as _sh; _sh.copy(__file__, OUT/'generate_synthetic_cbp_graph_corpus_v3.py')
    print(json.dumps({'scale':scale_key,'out':str(OUT),'events':N_EVENTS,'persons':N_PERSONS,'families':N_FAMILIES,'households':N_HOUSEHOLDS,'edges':edge_count[0],'cotravel_pairs':pp_assoc,'family_pairs':pp_family,'outcomes':{'secondary':sec_n,'search':search_n,'seizure':seiz_n,'arrest':arr_n},'contraband':contraband_n,'caught':caught_n,'false_negatives':fn_n}, indent=2))


if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'v3'
    if which == 'both':
        targets = ['v3', 'v4']
    elif which == 'all':
        targets = ['v3', 'v4', 'v5', 'v6', 'v7', 'v8']
    else:
        targets = [which]
    for t in targets:
        main(t)
