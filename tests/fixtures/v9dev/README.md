# Synthetic CBP-Style Entity-Centric Crossing Event Graph Corpus (v9dev)

Fully synthetic. No row represents a real person, vehicle, document, officer/team, case, event, seizure, arrest, address, phone, email, license plate, or name. The uploaded aggregate CBP-style CSVs were used only to calibrate FY/month/region/field-office/port/mode/category and drug-type distributions. Do not use for real enforcement decisions.

## What changed in this rework (realism)

1. **Connectivity = what the government observes.** Person-to-person links arise from co-travel, family records (customs declarations, immigration petitions, travel-party linkage), shared household residence, shared vehicles, vehicle registration, shared employer, and repeated routes. The population-wide phone/address "social web" from earlier versions is gone.
2. **Phone is a data point, not an edge.** Each person has a `synthetic_phone_token`; no two people are ever linked because of a phone number.
3. **Family connections are government-observable.** `FAMILY_MEMBER` edges represent family relationships discoverable from customs declarations, immigration petitions (I-130), travel-party records, and shared-document addresses. ~90% of true family pairs are captured; ~10% remain hidden due to data-entry gaps or separate immigration files — a realistic GNN prediction target.
4. **Undetected smuggling.** `event_ground_truth.csv` records who was actually carrying contraband, independent of whether they were caught. Most smuggling events are never stopped.
5. **Stopped-traveller data.** `secondary_inspections.csv` captures the richer record collected during secondary inspection; seizures/arrests carry person_id.
6. **Demographics on the person record** (document-derived), with the fairness audit grouping kept separate in `audit_attributes.csv` and smuggling generated independent of demographics.

## Files
- `arrests.csv`: 92 rows
- `audit_attributes.csv`: 2,000 rows
- `businesses.csv`: 500 rows
- `communities.csv`: 848 rows
- `contact_anchors.csv`: 2,000 rows
- `crossing_events.csv`: 4,000 rows
- `documents.csv`: 2,400 rows
- `edges.csv`: 40,686 rows
- `entity_resolution_pairs.csv`: 1,600 rows
- `entity_resolution_truth.csv`: 6,726 rows
- `event_features.csv`: 4,000 rows
- `event_ground_truth.csv`: 4,000 rows
- `fairness_group_rates.csv`: 7 rows
- `fairness_negative_control.csv`: 4,000 rows
- `golden_seed_event_ids.csv`: 250 rows
- `ground_truth_community_labels.csv`: 12,326 rows
- `labels.csv`: 20,000 rows
- `locations.csv`: 2,520 rows
- `narrative_validation_subset.jsonl`: 200 rows
- `node_features.csv`: 4,384 rows
- `observed_person_records.csv`: 6,726 rows
- `officers_or_teams.csv`: 300 rows
- `org_membership_ground_truth.csv`: 83 rows
- `persons.csv`: 2,000 rows
- `persons_ground_truth.csv`: 2,000 rows
- `scale_profile_and_metrics.csv`: 5 rows
- `secondary_inspections.csv`: 233 rows
- `seizures.csv`: 159 rows
- `temporal_fields_manifest.csv`: 6 rows
- `train_valid_test_splits.csv`: 4,000 rows
- `vehicles.csv`: 1,200 rows
