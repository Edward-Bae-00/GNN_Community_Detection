# Validation Report (v9)

## Realism feedback coverage
- Person<->person edges come from co-travel (`PERSON_ASSOCIATED_WITH_PERSON`: 78,613 weighted pairs), government family records (`FAMILY_MEMBER`: 135,280 pairs, ~90% of true family links), and shared household residence. No phone-based edges exist.
- Families span multiple households: 50,052 families across 65,470 households (mean 1.31 households/family).
- Undetected smuggling: 21,469 true-contraband events, 8,013 caught (seizures), 13,456 false negatives (62.7% slipped through).
- False-positive searches (searched, no contraband): 2,208.
- Hidden co-offender orgs (V6/V7): 800 cross-family cells, 5,043 members (4,527 actually observable, 507 dark / truly-linked-but-unfindable). Surfaced only via co-travel/shared-vehicle/shared-carrier; org_id is golden ground truth, never a feature.
- Stopped-traveller detail: `secondary_inspections.csv` = 11,529 rows; seizures and arrests carry person_id.

## Row Counts
- arrests.csv: 4,739
- audit_attributes.csv: 120,000
- businesses.csv: 8,000
- communities.csv: 50,052
- contact_anchors.csv: 120,000
- crossing_events.csv: 200,000
- documents.csv: 144,000
- edges.csv: 2,090,447
- entity_resolution_pairs.csv: 96,000
- entity_resolution_truth.csv: 333,640
- event_features.csv: 200,000
- event_ground_truth.csv: 200,000
- fairness_group_rates.csv: 7
- fairness_negative_control.csv: 200,000
- golden_seed_event_ids.csv: 250
- ground_truth_community_labels.csv: 669,640
- labels.csv: 1,000,000
- locations.csv: 77,854
- narrative_validation_subset.jsonl: 200
- node_features.csv: 202,384
- observed_person_records.csv: 333,640
- officers_or_teams.csv: 2,000
- org_membership_ground_truth.csv: 5,043
- persons.csv: 120,000
- persons_ground_truth.csv: 120,000
- scale_profile_and_metrics.csv: 5
- secondary_inspections.csv: 11,529
- seizures.csv: 8,013
- temporal_fields_manifest.csv: 6
- train_valid_test_splits.csv: 200,000
- vehicles.csv: 72,000

## Outcome Counts
- secondary_referrals: 11,529
- searches: 10,309
- seizures: 8,013
- arrests: 4,739
- referrals: 4,194
- administrative_actions: 472

## Positive Rates
- secondary: 0.057645
- search: 0.051545
- seizure: 0.040065
- arrest: 0.023695

## Graph Summary
- Total edges: 2,090,447
- Degree nodes_with_degree: 602106
- Degree min: 1
- Degree max: 16015
- Degree mean: 6.944
- Degree median: 5.0
- Degree p95: 16

## Privacy Statement
All data are synthetic. No real names, addresses, phones, emails, license plates, document numbers, officers, cases, or seizures are generated.
