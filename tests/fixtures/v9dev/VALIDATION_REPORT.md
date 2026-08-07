# Validation Report (v9dev)

## Realism feedback coverage
- Person<->person edges come from co-travel (`PERSON_ASSOCIATED_WITH_PERSON`: 1,437 weighted pairs), government family records (`FAMILY_MEMBER`: 2,264 pairs, ~90% of true family links), and shared household residence. No phone-based edges exist.
- Families span multiple households: 848 families across 1,136 households (mean 1.34 households/family).
- Undetected smuggling: 421 true-contraband events, 159 caught (seizures), 262 false negatives (62.2% slipped through).
- False-positive searches (searched, no contraband): 42.
- Hidden co-offender orgs (V6/V7): 14 cross-family cells, 83 members (74 actually observable, 9 dark / truly-linked-but-unfindable). Surfaced only via co-travel/shared-vehicle/shared-carrier; org_id is golden ground truth, never a feature.
- Stopped-traveller detail: `secondary_inspections.csv` = 233 rows; seizures and arrests carry person_id.

## Row Counts
- arrests.csv: 92
- audit_attributes.csv: 2,000
- businesses.csv: 500
- communities.csv: 848
- contact_anchors.csv: 2,000
- crossing_events.csv: 4,000
- documents.csv: 2,400
- edges.csv: 40,686
- entity_resolution_pairs.csv: 1,600
- entity_resolution_truth.csv: 6,726
- event_features.csv: 4,000
- event_ground_truth.csv: 4,000
- fairness_group_rates.csv: 7
- fairness_negative_control.csv: 4,000
- golden_seed_event_ids.csv: 250
- ground_truth_community_labels.csv: 12,326
- labels.csv: 20,000
- locations.csv: 2,520
- narrative_validation_subset.jsonl: 200
- node_features.csv: 4,384
- observed_person_records.csv: 6,726
- officers_or_teams.csv: 300
- org_membership_ground_truth.csv: 83
- persons.csv: 2,000
- persons_ground_truth.csv: 2,000
- scale_profile_and_metrics.csv: 5
- secondary_inspections.csv: 233
- seizures.csv: 159
- temporal_fields_manifest.csv: 6
- train_valid_test_splits.csv: 4,000
- vehicles.csv: 1,200

## Outcome Counts
- secondary_referrals: 233
- searches: 202
- seizures: 159
- arrests: 92
- referrals: 81
- administrative_actions: 10

## Positive Rates
- secondary: 0.058250
- search: 0.050500
- seizure: 0.039750
- arrest: 0.023000

## Graph Summary
- Total edges: 40,686
- Degree nodes_with_degree: 11544
- Degree min: 1
- Degree max: 317
- Degree mean: 7.049
- Degree median: 5.0
- Degree p95: 17

## Privacy Statement
All data are synthetic. No real names, addresses, phones, emails, license plates, document numbers, officers, cases, or seizures are generated.
