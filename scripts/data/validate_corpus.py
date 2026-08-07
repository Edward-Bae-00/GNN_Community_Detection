#!/usr/bin/env python3
"""Validation harness for the v3/v4 synthetic CBP graph corpus.

Checks referential integrity, the connectivity-realism claims (no phone edges,
person<->person only from co-travel/household), label-leakage controls,
hidden-smuggling consistency, outcome logic, and representativeness.
Exits non-zero if any hard check fails.
"""
import csv, json, sys
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10**9)
DIR = None
FAIL = []
WARN = []
INFO = []


def col(name, key):
    out = []
    with open(DIR/name, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            out.append(r[key])
    return out


def ids(name, key):
    s = set()
    with open(DIR/name, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            s.add(r[key])
    return s


def check(cond, msg):
    (INFO if cond else FAIL).append(("PASS" if cond else "FAIL") + ": " + msg)


def _run_validation() -> int:
    print(f"== Validating {DIR.name} ==")

    persons = ids('persons.csv', 'person_id')
    vehicles = ids('vehicles.csv', 'vehicle_id')
    documents = ids('documents.csv', 'document_id')
    businesses = ids('businesses.csv', 'business_id')
    officers = ids('officers_or_teams.csv', 'officer_team_id')
    locations = ids('locations.csv', 'location_id')

    events = set(); ev_person = {}
    with open(DIR/'crossing_events.csv', newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            events.add(r['event_id']); ev_person[r['event_id']] = r['primary_person_id']

    # --- Referential integrity ------------------------------------------------
    with open(DIR/'crossing_events.csv', newline='', encoding='utf-8') as f:
        bad_p = bad_v = bad_d = bad_b = bad_o = 0
        for r in csv.DictReader(f):
            if r['primary_person_id'] not in persons: bad_p += 1
            if r['vehicle_id'] and r['vehicle_id'] not in vehicles: bad_v += 1
            if r['document_id'] and r['document_id'] not in documents: bad_d += 1
            if r['carrier_id'] and r['carrier_id'] not in businesses: bad_b += 1
            if r['officer_team_id'] not in officers: bad_o += 1
    check(bad_p == 0, f"crossing_events.primary_person_id all valid ({bad_p} bad)")
    check(bad_v == 0, f"crossing_events.vehicle_id all valid/null ({bad_v} bad)")
    check(bad_d == 0, f"crossing_events.document_id all valid ({bad_d} bad)")
    check(bad_b == 0, f"crossing_events.carrier_id all valid/null ({bad_b} bad)")
    check(bad_o == 0, f"crossing_events.officer_team_id all valid ({bad_o} bad)")

    for tbl, ekey, pkey in [('seizures.csv','event_id','primary_person_id'),('arrests.csv','event_id','person_id'),('secondary_inspections.csv','event_id','person_id')]:
        be = bp = 0
        with open(DIR/tbl, newline='', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if r[ekey] not in events: be += 1
                if r[pkey] not in persons: bp += 1
        check(be == 0, f"{tbl}.{ekey} all in crossing_events ({be} bad)")
        check(bp == 0, f"{tbl}.{pkey} all in persons ({bp} bad)")

    # every document.person_id valid; every vehicle owner valid
    bd = sum(1 for x in col('documents.csv','person_id') if x not in persons)
    check(bd == 0, f"documents.person_id all valid ({bd} bad)")

    # --- Edge integrity + connectivity realism --------------------------------
    node_sets = {'person':persons,'vehicle':vehicles,'document':documents,'business':businesses,
                 'officer_team':officers,'location':locations,'event':events}
    etype_ct = Counter(); pp_edges = 0; pp_assoc_via_cotravel = 0; bad_edge = 0; bad_leak = 0
    phone_edges = 0; addr_edges = 0; assoc_endpoints_ok = True; assoc_evsrc = Counter()
    outcome_types = {'EVENT_RESULTED_IN_SECONDARY','EVENT_RESULTED_IN_SEARCH','EVENT_RESULTED_IN_SEIZURE',
                     'EVENT_RESULTED_IN_ARREST','EVENT_LINKED_TO_SEIZURE','EVENT_LINKED_TO_ADMIN_ACTION'}
    with open(DIR/'edges.csv', newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            et = r['edge_type']; etype_ct[et] += 1
            s, st, t, tt = r['source_node_id'], r['source_node_type'], r['target_node_id'], r['target_node_type']
            # label endpoints are synthetic sentinels; skip those targets
            if tt in node_sets and not (tt == 'label'):
                if t not in node_sets[tt] and tt not in ('seizure','arrest'):
                    bad_edge += 1
            if st in node_sets and s not in node_sets[st] and st not in ('seizure','arrest'):
                bad_edge += 1
            if 'PHONE' in et or 'CONTACT' in et:
                phone_edges += 1
            if et == 'ADDRESS_SHARED_BY_PERSONS':
                addr_edges += 1
            if et == 'PERSON_ASSOCIATED_WITH_PERSON':
                pp_edges += 1; assoc_evsrc[r['evidence_source']] += 1
                if st != 'person' or tt != 'person': assoc_endpoints_ok = False
                if r['evidence_source'] == 'co_travel_observation': pp_assoc_via_cotravel += 1
            if et in outcome_types and r['leakage_safe_flag'] != 'false':
                bad_leak += 1

    check(phone_edges == 0, f"NO phone/contact person-link edges exist ({phone_edges} found)")
    check(assoc_endpoints_ok, "PERSON_ASSOCIATED_WITH_PERSON endpoints are both persons")
    check(pp_edges == pp_assoc_via_cotravel, f"all person<->person association edges are co-travel-derived ({pp_assoc_via_cotravel}/{pp_edges})")
    check(bad_edge == 0, f"all edge endpoints resolve to node tables ({bad_edge} bad)")
    check(bad_leak == 0, f"all outcome edges flagged leakage_safe=false ({bad_leak} violations)")
    INFO.append(f"INFO: person<->person association edges = {pp_edges:,}; per-person assoc degree ~ {2*pp_edges/len(persons):.3f}")
    INFO.append(f"INFO: household address edges = {addr_edges:,}")

    # --- Family spans multiple households -------------------------------------
    fam_hh = defaultdict(set)
    with open(DIR/'persons_ground_truth.csv', newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            fam_hh[r['family_id']].add(r['household_id'])
    multi = sum(1 for hs in fam_hh.values() if len(hs) > 1)
    check(multi > 0, f"families spanning multiple households exist ({multi:,} of {len(fam_hh):,})")

    # --- Hidden co-offender orgs (V6 only; conditional on file presence) -------
    org_path = DIR / 'org_membership_ground_truth.csv'
    if org_path.exists():
        org_fam = defaultdict(set); org_dark_ct = Counter(); org_size = Counter()
        org_rows_by_person = {}
        p_org = {}
        bad_org_p = 0; person_fam = {}
        with open(DIR/'persons_ground_truth.csv', newline='', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                person_fam[r['person_id']] = r['family_id']
        with open(org_path, newline='', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                oid = r['org_id']
                org_rows_by_person[r['person_id']] = r
                p_org[r['person_id']] = oid
                if r['person_id'] not in persons: bad_org_p += 1
                org_fam[oid].add(person_fam.get(r['person_id'], r['person_id']))
                org_size[oid] += 1
                if r['is_dark'] == 'true': org_dark_ct[oid] += 1
        cross_family = sum(1 for fs in org_fam.values() if len(fs) >= 2)
        total_dark = sum(org_dark_ct.values())
        check(bad_org_p == 0, f"org_membership.person_id all valid ({bad_org_p} bad)")
        check(len(org_fam) > 0, f"hidden co-offender orgs exist ({len(org_fam):,} cells)")
        check(cross_family == len(org_fam),
              f"every org spans >=2 families ({cross_family}/{len(org_fam)})")
        check(total_dark > 0,
              f"dark (truly-linked-but-unfindable) members exist ({total_dark:,})")
        observable_people = set()
        vehicle_people = defaultdict(set)
        carrier_people = defaultdict(set)
        with open(DIR/'crossing_events.csv', newline='', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                primary = r['primary_person_id']
                oid = p_org.get(primary)
                if not oid:
                    continue
                for cotraveler in filter(None, (r.get('co_traveler_person_ids') or '').split(';')):
                    if p_org.get(cotraveler) == oid:
                        observable_people.add(primary)
                        observable_people.add(cotraveler)
                if r.get('vehicle_id'):
                    vehicle_people[(oid, r['vehicle_id'])].add(primary)
                if r.get('carrier_id'):
                    carrier_people[(oid, r['carrier_id'])].add(primary)
        for grouped_people in list(vehicle_people.values()) + list(carrier_people.values()):
            if len(grouped_people) >= 2:
                observable_people.update(grouped_people)
        bad_observable = sum(
            1
            for pid, r in org_rows_by_person.items()
            if (r['is_observable'] == 'true') != (pid in observable_people)
        )
        check(
            bad_observable == 0,
            f"org_membership.is_observable matches actual same-org observable evidence ({bad_observable} mismatches)",
        )
        # org_id must NOT leak into any feature/operational table, including JSON payloads.
        leak_tables = []
        for tbl in ['persons.csv', 'node_features.csv', 'event_features.csv', 'crossing_events.csv']:
            p = DIR / tbl
            if not p.exists():
                continue
            with open(p, newline='', encoding='utf-8') as f:
                for line in f:
                    lowered = line.lower()
                    if 'org_id' in lowered or 'org_' in lowered:
                        leak_tables.append(tbl)
                        break
        check(not leak_tables, f"org_id/org_* absent from feature/operational table content (leaks: {leak_tables})")
        INFO.append(f"INFO: orgs = {len(org_fam):,} cells; members = {sum(org_size.values()):,}; dark = {total_dark:,}")

    # --- V7 entity-resolution layer (conditional on file presence) -------------
    er_evidence_path = DIR / 'record_link_evidence.csv'
    if er_evidence_path.exists():
        observed_ids = set()
        truth_person_by_obs = {}
        with open(DIR/'observed_person_records.csv', newline='', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                observed_ids.add(r['observed_person_record_id'])
                truth_person_by_obs[r['observed_person_record_id']] = r.get('canonical_person_id', '')
        if (DIR/'entity_resolution_truth.csv').exists():
            with open(DIR/'entity_resolution_truth.csv', newline='', encoding='utf-8') as f:
                for r in csv.DictReader(f):
                    truth_person_by_obs[r['observed_person_record_id']] = r.get('canonical_person_id', '')

        bad_pair_obs = bad_pair_truth = 0
        pair_ct = true_pair_ct = deterministic_true_ct = weak_link_positive_ct = 0
        pair_missing_fields = set()
        with open(er_evidence_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            required_pair_fields = {
                'relational_evidence_score',
                'weak_link_candidate_flag',
                'weak_link_positive_flag',
            }
            pair_missing_fields = required_pair_fields - set(reader.fieldnames or [])
            for r in reader:
                pair_ct += 1
                a = r['observed_person_record_id_a']; b = r['observed_person_record_id_b']
                if a not in observed_ids or b not in observed_ids:
                    bad_pair_obs += 1
                    continue
                expected_same = truth_person_by_obs.get(a, '') == truth_person_by_obs.get(b, '')
                actual_same = r.get('true_same_person') == 'true'
                if expected_same != actual_same:
                    bad_pair_truth += 1
                if actual_same:
                    true_pair_ct += 1
                    deterministic_true_ct += r.get('deterministic_match_flag') == 'true'
                    weak_link_positive_ct += r.get('weak_link_positive_flag') == 'true'
        check(bad_pair_obs == 0, f"record_link_evidence observed record ids resolve ({bad_pair_obs} bad)")
        check(bad_pair_truth == 0, f"record_link_evidence true_same_person matches ER truth ({bad_pair_truth} bad)")
        check(pair_ct > 0, f"record_link_evidence has candidate pairs ({pair_ct:,})")
        check(true_pair_ct > 0, f"record_link_evidence has true same-person pairs ({true_pair_ct:,})")
        check(deterministic_true_ct > 0, f"record_link_evidence has deterministic true pairs ({deterministic_true_ct:,})")
        check(not pair_missing_fields, f"record_link_evidence has weak-link schema fields (missing={sorted(pair_missing_fields)})")
        check(weak_link_positive_ct > 0, f"record_link_evidence has weak-link positive true pairs ({weak_link_positive_ct:,})")

        for tbl, key in [
            ('baseline_er_clusters.csv', 'observed_person_record_id'),
            ('oracle_er_clusters.csv', 'observed_person_record_id'),
        ]:
            bad_cluster_obs = 0
            with open(DIR/tbl, newline='', encoding='utf-8') as f:
                for r in csv.DictReader(f):
                    if r[key] not in observed_ids:
                        bad_cluster_obs += 1
            check(bad_cluster_obs == 0, f"{tbl}.{key} all valid ({bad_cluster_obs} bad)")

        summary_path = DIR / 'v7_er_recoverability_summary.json'
        if summary_path.exists():
            summary = json.load(open(summary_path, encoding='utf-8'))
            required = {'observed_records', 'candidate_pairs', 'true_pairs',
                        'deterministic_true_pairs', 'weak_link_true_pairs',
                        'deterministic_pair_recall',
                        'deterministic_plus_weak_link_oracle_pair_recall'}
            missing = sorted(required - set(summary))
            check(not missing, f"v7_er_recoverability_summary.json has required keys (missing={missing})")
            check(summary.get('observed_records') == len(observed_ids),
                  f"v7 ER summary observed_records matches observed_person_records ({summary.get('observed_records')} vs {len(observed_ids)})")
            check(summary.get('candidate_pairs') == pair_ct,
                  f"v7 ER summary candidate_pairs matches record_link_evidence ({summary.get('candidate_pairs')} vs {pair_ct})")
        else:
            check(False, "v7_er_recoverability_summary.json exists when record_link_evidence.csv exists")

    # --- Hidden smuggling consistency -----------------------------------------
    egt = {}
    with open(DIR/'event_ground_truth.csv', newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            egt[r['event_id']] = r
    seizure_events = set(col('seizures.csv','event_id'))
    contraband_events = {e for e, r in egt.items() if r['true_contraband_present'] == 'true'}
    seiz_without_contraband = sum(1 for e in seizure_events if egt.get(e,{}).get('true_contraband_present') != 'true')
    fn = sum(1 for e in contraband_events if egt[e]['detected_flag'] != 'true')
    check(seiz_without_contraband == 0, f"every seizure has true_contraband_present ({seiz_without_contraband} violations)")
    check(len(seizure_events) < len(contraband_events), f"undetected smuggling exists: {len(seizure_events)} seized of {len(contraband_events)} true ({fn} slipped through)")

    # --- Outcome logic --------------------------------------------------------
    ev_flags = {}
    with open(DIR/'crossing_events.csv', newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            ev_flags[r['event_id']] = (r['secondary_referral_flag'], r['search_flag'], r['seizure_flag'], r['arrest_flag'])
    n_sec = sum(1 for v in ev_flags.values() if v[0]=='true')
    n_sch = sum(1 for v in ev_flags.values() if v[1]=='true')
    n_sz = sum(1 for v in ev_flags.values() if v[2]=='true')
    n_ar = sum(1 for v in ev_flags.values() if v[3]=='true')
    sz_no_ar = sum(1 for v in ev_flags.values() if v[2]=='true' and v[3]=='false')
    sch_no_sz = sum(1 for v in ev_flags.values() if v[1]=='true' and v[2]=='false')
    check(n_sec > n_sch > n_sz, f"funnel secondary({n_sec}) > search({n_sch}) > seizure({n_sz})")
    check(sz_no_ar > 0, f"seizures without arrest exist ({sz_no_ar})")
    check(sch_no_sz > 0, f"searches without seizure exist ({sch_no_sz})")

    # --- Demographics on record, audit separated ------------------------------
    with open(DIR/'persons.csv', newline='', encoding='utf-8') as f:
        ph = next(csv.reader(f))
    for c in ['sex_marker','citizenship_country','synthetic_dob_year_bucket','synthetic_phone_token']:
        check(c in ph, f"persons.csv has demographic/data-point column '{c}'")
    check('audit_demographic_group_id' not in ph, "persons.csv does NOT carry the audit grouping (kept separate)")

    # --- Representativeness: citizenship by border region ---------------------
    reg_cit = defaultdict(Counter)
    with open(DIR/'crossing_events.csv', newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            reg_cit[r['region']][r['citizenship_country']] += 1
    for reg in ['Southern Border','Northern Border']:
        if reg in reg_cit:
            top = reg_cit[reg].most_common(3)
            INFO.append(f"INFO: {reg} top citizenships: " + ", ".join(f"{k} {v}" for k,v in top))

    # --- Privacy spot-check ---------------------------------------------------
    sample_tokens = col('persons.csv','synthetic_phone_token')[:5] + col('vehicles.csv','synthetic_plate_token')[:5]
    all_syn = all(t.startswith('SYN') for t in sample_tokens)
    check(all_syn, "sampled PII-like tokens are clearly synthetic (SYN prefix)")

    # --- Report ---------------------------------------------------------------
    print("\n".join(INFO))
    print("\n--- edge_type counts ---")
    for et, c in etype_ct.most_common():
        print(f"  {et}: {c:,}")
    if WARN:
        print("\n".join(WARN))
    print("\n" + "\n".join(FAIL) if FAIL else "\nALL HARD CHECKS PASSED")
    return 1 if FAIL else 0

def main(argv=None) -> int:
    """Validate exactly one corpus directory and return a process status."""
    global DIR, FAIL, WARN, INFO
    args = sys.argv[1:] if argv is None else list(argv)
    if len(args) != 1:
        print("usage: python -m scripts.data.validate_corpus <corpus_dir>", file=sys.stderr)
        return 2
    DIR = Path(args[0])
    FAIL = []
    WARN = []
    INFO = []
    return _run_validation()

if __name__ == "__main__":
    raise SystemExit(main())
