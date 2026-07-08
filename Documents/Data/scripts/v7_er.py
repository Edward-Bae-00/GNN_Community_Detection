#!/usr/bin/env python3
"""V7 entity-resolution helper layer for synthetic CBP corpora."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path


csv.field_size_limit(10**9)

SUMMARY_NAME = "v7_er_recoverability_summary.json"


def _truthy(value: str | None) -> bool:
    return str(value).lower() == "true"


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_rows(path: Path, headers: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            serialized = {}
            for key in headers:
                value = row.get(key, "")
                if isinstance(value, bool):
                    serialized[key] = "true" if value else "false"
                elif value is None:
                    serialized[key] = ""
                else:
                    serialized[key] = value
            writer.writerow(serialized)


def _parse_timestamp(value: str | None) -> datetime:
    text = (value or "").strip()
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def load_v7_er_summary(corpus_dir: str | Path) -> dict | None:
    """Load the V7 ER summary if it exists."""

    path = Path(corpus_dir) / SUMMARY_NAME
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_v7_er_layer(corpus_dir, seed: int = 20260617, max_pair_rows: int | None = None):
    """Build the V7 ER artifact layer from an existing generated corpus."""

    del seed  # sampling is deterministic from sorted corpus state

    corpus_path = Path(corpus_dir)

    observed_path = corpus_path / "observed_person_records.csv"
    truth_path = corpus_path / "entity_resolution_truth.csv"
    events_path = corpus_path / "crossing_events.csv"

    observed_rows = _read_rows(observed_path)
    truth_rows = _read_rows(truth_path) if truth_path.exists() else []
    event_rows = _read_rows(events_path) if events_path.exists() else []

    truth_by_record = {row["observed_person_record_id"]: row for row in truth_rows}
    truth_by_person = defaultdict(list)
    for row in truth_rows:
        truth_by_person[row.get("canonical_person_id", "")].append(row)
    event_by_id = {}
    for row in event_rows:
        event_id = row.get("event_id", "")
        if not event_id:
            continue
        event_by_id[event_id] = row
    split_counts = Counter((row.get("data_split", "unknown") or "unknown") for row in event_by_id.values())

    records_by_id = {row["observed_person_record_id"]: row for row in observed_rows}
    records_by_person = defaultdict(list)
    for row in observed_rows:
        records_by_person[row["canonical_person_id"]].append(row)
    for rows in records_by_person.values():
        rows.sort(key=lambda row: (row.get("event_timestamp_utc", ""), row["observed_person_record_id"]))

    def observed_residence(record: dict[str, str]) -> str:
        return (record.get("observed_residence_location_id") or "").strip()

    def pair_metrics(record_a: dict[str, str], record_b: dict[str, str]) -> dict[str, object]:
        event_a = event_by_id.get(record_a.get("event_id", ""), {})
        event_b = event_by_id.get(record_b.get("event_id", ""), {})
        person_a = record_a.get("canonical_person_id", "")
        person_b = record_b.get("canonical_person_id", "")
        residence_a = observed_residence(record_a)
        residence_b = observed_residence(record_b)

        same_document_flag = bool(record_a.get("observed_document_id")) and record_a.get("observed_document_id") == record_b.get("observed_document_id")
        same_dob_bucket_flag = bool(record_a.get("observed_dob_year_bucket")) and record_a.get("observed_dob_year_bucket") == record_b.get("observed_dob_year_bucket")
        same_sex_marker_flag = bool(record_a.get("observed_sex_marker")) and record_a.get("observed_sex_marker") == record_b.get("observed_sex_marker")
        same_source_system_flag = bool(record_a.get("source_system")) and record_a.get("source_system") == record_b.get("source_system")
        same_event_flag = bool(record_a.get("event_id")) and record_a.get("event_id") == record_b.get("event_id")
        shared_vehicle_flag = bool(event_a.get("vehicle_id")) and event_a.get("vehicle_id") == event_b.get("vehicle_id")
        shared_carrier_flag = bool(event_a.get("carrier_id")) and event_a.get("carrier_id") == event_b.get("carrier_id")
        shared_residence_flag = bool(residence_a) and residence_a == residence_b
        deterministic_match_flag = same_document_flag or same_event_flag
        relational_evidence_score = sum(
            int(flag)
            for flag in (
                shared_vehicle_flag,
                shared_carrier_flag,
                shared_residence_flag,
            )
        )
        evidence_score = sum(
            int(flag)
            for flag in (
                same_dob_bucket_flag,
                same_sex_marker_flag,
                same_source_system_flag,
                shared_vehicle_flag,
                shared_carrier_flag,
                shared_residence_flag,
            )
        )
        true_same_person = person_a == person_b
        weak_link_candidate_flag = (
            not deterministic_match_flag and evidence_score >= 2 and relational_evidence_score >= 1
        )
        weak_link_positive_flag = true_same_person and weak_link_candidate_flag
        if true_same_person and deterministic_match_flag:
            match_difficulty = "deterministic"
            notes = "Same person resolved by deterministic same-document or same-event evidence."
        elif weak_link_positive_flag:
            match_difficulty = "weak_link_positive"
            notes = "Same person falls inside the oracle weak-link coverage set."
        elif true_same_person:
            match_difficulty = "hard_same_person"
            notes = "Same person is not in the oracle weak-link coverage set."
        elif deterministic_match_flag:
            match_difficulty = "hard_negative"
            notes = "Different people share deterministic-looking evidence."
        else:
            match_difficulty = "hard_negative"
            notes = "Different people selected as a hard negative."

        split_a = event_a.get("data_split", "") or ""
        split_b = event_b.get("data_split", "") or ""
        if split_a and split_a == split_b:
            data_split = split_a
        elif split_a and not split_b:
            data_split = split_a
        elif split_b and not split_a:
            data_split = split_b
        elif split_a and split_b and split_a != split_b:
            data_split = "mixed"
        else:
            data_split = "unknown"

        return {
            "same_document_flag": same_document_flag,
            "same_dob_bucket_flag": same_dob_bucket_flag,
            "same_sex_marker_flag": same_sex_marker_flag,
            "same_source_system_flag": same_source_system_flag,
            "same_event_flag": same_event_flag,
            "shared_vehicle_flag": shared_vehicle_flag,
            "shared_carrier_flag": shared_carrier_flag,
            "shared_residence_flag": shared_residence_flag,
            "deterministic_match_flag": deterministic_match_flag,
            "relational_evidence_score": relational_evidence_score,
            "weak_link_candidate_flag": weak_link_candidate_flag,
            "weak_link_positive_flag": weak_link_positive_flag,
            "evidence_score": evidence_score,
            "data_split": data_split,
            "match_difficulty": match_difficulty,
            "notes": notes,
            "true_same_person": true_same_person,
        }

    fragmentation_profile_rows = []
    deterministic_pair_count = 0
    weak_link_true_pair_count = 0
    true_pair_count = 0
    oracle_pair_count = 0

    for canonical_person_id in sorted(records_by_person):
        rows = records_by_person[canonical_person_id]
        truth_rows_for_person = truth_by_person.get(canonical_person_id, [])
        cluster_ids = sorted({row.get("true_resolution_cluster_id", "") for row in truth_rows_for_person if row.get("true_resolution_cluster_id")})
        canonical_cluster = cluster_ids[0] if cluster_ids else canonical_person_id
        observed_count = len(rows)
        document_count = len({row.get("observed_document_id", "") for row in rows if row.get("observed_document_id")})
        variant_count = len({row.get("name_variant_type", "") for row in rows if row.get("name_variant_type")})
        first_seen = min(_parse_timestamp(row.get("event_timestamp_utc")) for row in rows)
        last_seen = max(_parse_timestamp(row.get("event_timestamp_utc")) for row in rows)
        if observed_count == 1:
            fragmentation_tier = "single_record"
        elif observed_count == 2:
            fragmentation_tier = "light_fragmentation"
        elif observed_count <= 4:
            fragmentation_tier = "moderate_fragmentation"
        else:
            fragmentation_tier = "heavy_fragmentation"
        fragmentation_profile_rows.append(
            {
                "canonical_person_id": canonical_person_id,
                "true_resolution_cluster_id": canonical_cluster,
                "observed_record_count": observed_count,
                "distinct_document_count": document_count,
                "distinct_name_variant_count": variant_count,
                "first_seen_timestamp_utc": _format_timestamp(first_seen),
                "last_seen_timestamp_utc": _format_timestamp(last_seen),
                "fragmentation_tier": fragmentation_tier,
            }
        )

    # Full same-person pair universe for summary statistics.
    for rows in records_by_person.values():
        for record_a, record_b in combinations(rows, 2):
            metrics = pair_metrics(record_a, record_b)
            true_pair_count += 1
            oracle_pair_count += 1
            if metrics["deterministic_match_flag"]:
                deterministic_pair_count += 1
            if metrics["weak_link_positive_flag"]:
                weak_link_true_pair_count += 1

    # Candidate evidence rows: same-person positives first, then hard negatives.
    candidate_rows: list[dict[str, object]] = []
    seen_pairs: set[tuple[str, str]] = set()

    def add_pair(record_id_a: str, record_id_b: str) -> None:
        if record_id_a == record_id_b:
            return
        pair_key = tuple(sorted((record_id_a, record_id_b)))
        if pair_key in seen_pairs:
            return
        seen_pairs.add(pair_key)
        record_a = records_by_id[pair_key[0]]
        record_b = records_by_id[pair_key[1]]
        metrics = pair_metrics(record_a, record_b)
        candidate_rows.append(
            {
                "pair_id": f"PAIR{len(candidate_rows) + 1:05d}",
                "observed_person_record_id_a": pair_key[0],
                "observed_person_record_id_b": pair_key[1],
                "true_same_person": metrics["true_same_person"],
                "canonical_person_id_a": record_a.get("canonical_person_id", ""),
                "canonical_person_id_b": record_b.get("canonical_person_id", ""),
                "data_split": metrics["data_split"],
                "same_document_flag": metrics["same_document_flag"],
                "same_dob_bucket_flag": metrics["same_dob_bucket_flag"],
                "same_sex_marker_flag": metrics["same_sex_marker_flag"],
                "same_source_system_flag": metrics["same_source_system_flag"],
                "same_event_flag": metrics["same_event_flag"],
                "shared_vehicle_flag": metrics["shared_vehicle_flag"],
                "shared_carrier_flag": metrics["shared_carrier_flag"],
                "shared_residence_flag": metrics["shared_residence_flag"],
                "deterministic_match_flag": metrics["deterministic_match_flag"],
                "relational_evidence_score": metrics["relational_evidence_score"],
                "weak_link_candidate_flag": metrics["weak_link_candidate_flag"],
                "weak_link_positive_flag": metrics["weak_link_positive_flag"],
                "evidence_score": metrics["evidence_score"],
                "match_difficulty": metrics["match_difficulty"],
                "notes": metrics["notes"],
            }
        )

    for canonical_person_id in sorted(records_by_person):
        rows = records_by_person[canonical_person_id]
        for record_a, record_b in combinations(rows, 2):
            add_pair(record_a["observed_person_record_id"], record_b["observed_person_record_id"])

    if max_pair_rows is None or max_pair_rows > len(candidate_rows):
        negative_candidates = []
        hard_buckets = defaultdict(set)
        for row in observed_rows:
            record_id = row["observed_person_record_id"]
            event = event_by_id.get(row.get("event_id", ""), {})
            residence = observed_residence(row)
            if row.get("event_id"):
                hard_buckets[("event", row["event_id"])].add(record_id)
            if row.get("observed_document_id"):
                hard_buckets[("doc", row["observed_document_id"])].add(record_id)
            if event.get("vehicle_id"):
                hard_buckets[("vehicle", event["vehicle_id"])].add(record_id)
            if event.get("carrier_id"):
                hard_buckets[("carrier", event["carrier_id"])].add(record_id)
            if residence:
                hard_buckets[("residence", residence)].add(record_id)
            demo_source = "|".join(
                [
                    row.get("observed_dob_year_bucket", ""),
                    row.get("observed_sex_marker", ""),
                    row.get("source_system", ""),
                ]
            )
            if demo_source.strip("|"):
                hard_buckets[("demo_source", demo_source)].add(record_id)

        def bounded_pairs(record_ids):
            ordered_ids = sorted(record_ids)
            if len(ordered_ids) <= 60:
                yield from combinations(ordered_ids, 2)
                return
            # Large demographic buckets can be huge. Adjacent windows keep the
            # candidate set deterministic without turning V7 generation into an
            # all-pairs job.
            emitted = 0
            for offset in (1, 2, 5, 13):
                for idx, record_id_a in enumerate(ordered_ids[:-offset]):
                    yield record_id_a, ordered_ids[idx + offset]
                    emitted += 1
                    if emitted >= 250:
                        return

        for record_ids in hard_buckets.values():
            for record_id_a, record_id_b in bounded_pairs(record_ids):
                if records_by_id[record_id_a].get("canonical_person_id") == records_by_id[record_id_b].get("canonical_person_id"):
                    continue
                pair_key = tuple(sorted((record_id_a, record_id_b)))
                if pair_key in seen_pairs:
                    continue
                metrics = pair_metrics(records_by_id[pair_key[0]], records_by_id[pair_key[1]])
                if not (
                    metrics["same_event_flag"]
                    or metrics["same_document_flag"]
                    or metrics["evidence_score"] >= 2
                ):
                    continue
                negative_candidates.append(
                    {
                        "pair_key": pair_key,
                        "metrics": metrics,
                        "hardness": (
                            int(metrics["same_event_flag"]) * 4
                            + int(metrics["same_document_flag"]) * 4
                            + int(metrics["evidence_score"])
                        ),
                    }
                )

        negative_candidates.sort(
            key=lambda item: (
                -item["hardness"],
                item["pair_key"][0],
                item["pair_key"][1],
            )
        )
        for item in negative_candidates:
            if max_pair_rows is not None and len(candidate_rows) >= max_pair_rows:
                break
            pair_key = item["pair_key"]
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            record_a = records_by_id[pair_key[0]]
            record_b = records_by_id[pair_key[1]]
            metrics = item["metrics"]
            candidate_rows.append(
                {
                    "pair_id": f"PAIR{len(candidate_rows) + 1:05d}",
                    "observed_person_record_id_a": pair_key[0],
                    "observed_person_record_id_b": pair_key[1],
                    "true_same_person": False,
                    "canonical_person_id_a": record_a.get("canonical_person_id", ""),
                    "canonical_person_id_b": record_b.get("canonical_person_id", ""),
                    "data_split": metrics["data_split"],
                    "same_document_flag": metrics["same_document_flag"],
                    "same_dob_bucket_flag": metrics["same_dob_bucket_flag"],
                    "same_sex_marker_flag": metrics["same_sex_marker_flag"],
                    "same_source_system_flag": metrics["same_source_system_flag"],
                    "same_event_flag": metrics["same_event_flag"],
                    "shared_vehicle_flag": metrics["shared_vehicle_flag"],
                    "shared_carrier_flag": metrics["shared_carrier_flag"],
                    "shared_residence_flag": metrics["shared_residence_flag"],
                    "deterministic_match_flag": metrics["deterministic_match_flag"],
                    "relational_evidence_score": metrics["relational_evidence_score"],
                    "weak_link_candidate_flag": metrics["weak_link_candidate_flag"],
                    "weak_link_positive_flag": False,
                    "evidence_score": metrics["evidence_score"],
                    "match_difficulty": metrics["match_difficulty"],
                    "notes": metrics["notes"],
                }
            )

        # --- Name-token blocking: hard negatives from shared name tokens ---
        # Records sharing at least one lowercased name token (≥2 chars) form
        # a name-blocking bucket.  Different-person pairs from these buckets
        # become "name_collision_negative" candidates — the regime where
        # pairwise name features are ambiguous and graph signal could help.
        name_token_buckets = defaultdict(set)
        for row in observed_rows:
            record_id = row["observed_person_record_id"]
            name = (row.get("observed_name_token") or "").lower()
            for token in name.split():
                if len(token) >= 2:
                    name_token_buckets[token].add(record_id)

        name_neg_count = 0
        for token_key in sorted(name_token_buckets):
            bucket_ids = name_token_buckets[token_key]
            if len(bucket_ids) < 2:
                continue
            for record_id_a, record_id_b in bounded_pairs(bucket_ids):
                if max_pair_rows is not None and len(candidate_rows) >= max_pair_rows:
                    break
                if records_by_id[record_id_a].get("canonical_person_id") == records_by_id[record_id_b].get("canonical_person_id"):
                    continue
                pair_key = tuple(sorted((record_id_a, record_id_b)))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                record_a = records_by_id[pair_key[0]]
                record_b = records_by_id[pair_key[1]]
                metrics = pair_metrics(record_a, record_b)
                candidate_rows.append(
                    {
                        "pair_id": f"PAIR{len(candidate_rows) + 1:05d}",
                        "observed_person_record_id_a": pair_key[0],
                        "observed_person_record_id_b": pair_key[1],
                        "true_same_person": False,
                        "canonical_person_id_a": record_a.get("canonical_person_id", ""),
                        "canonical_person_id_b": record_b.get("canonical_person_id", ""),
                        "data_split": metrics["data_split"],
                        "same_document_flag": metrics["same_document_flag"],
                        "same_dob_bucket_flag": metrics["same_dob_bucket_flag"],
                        "same_sex_marker_flag": metrics["same_sex_marker_flag"],
                        "same_source_system_flag": metrics["same_source_system_flag"],
                        "same_event_flag": metrics["same_event_flag"],
                        "shared_vehicle_flag": metrics["shared_vehicle_flag"],
                        "shared_carrier_flag": metrics["shared_carrier_flag"],
                        "shared_residence_flag": metrics["shared_residence_flag"],
                        "deterministic_match_flag": metrics["deterministic_match_flag"],
                        "relational_evidence_score": metrics["relational_evidence_score"],
                        "weak_link_candidate_flag": metrics["weak_link_candidate_flag"],
                        "weak_link_positive_flag": False,
                        "evidence_score": metrics["evidence_score"],
                        "match_difficulty": "name_collision_negative",
                        "notes": "Different people sharing a name token (name-blocked hard negative).",
                    }
                )
                name_neg_count += 1

    if max_pair_rows is not None:
        candidate_rows = candidate_rows[:max_pair_rows]

    # Re-number pair ids after any truncation.
    for index, row in enumerate(candidate_rows, start=1):
        row["pair_id"] = f"PAIR{index:05d}"

    # Baseline clusters: deterministic connected components.
    parent = {record_id: record_id for record_id in records_by_id}

    def find(record_id: str) -> str:
        while parent[record_id] != record_id:
            parent[record_id] = parent[parent[record_id]]
            record_id = parent[record_id]
        return record_id

    def union(record_id_a: str, record_id_b: str) -> None:
        root_a = find(record_id_a)
        root_b = find(record_id_b)
        if root_a != root_b:
            if root_a < root_b:
                parent[root_b] = root_a
            else:
                parent[root_a] = root_b

    doc_groups = defaultdict(list)
    event_groups = defaultdict(list)
    for record in observed_rows:
        if record.get("observed_document_id"):
            doc_groups[record["observed_document_id"]].append(record["observed_person_record_id"])
        if record.get("event_id"):
            event_groups[record["event_id"]].append(record["observed_person_record_id"])

    for group in doc_groups.values():
        ordered = sorted(group)
        for record_id_a, record_id_b in combinations(ordered, 2):
            union(record_id_a, record_id_b)
    for group in event_groups.values():
        ordered = sorted(group)
        for record_id_a, record_id_b in combinations(ordered, 2):
            union(record_id_a, record_id_b)

    components = defaultdict(list)
    for record_id in sorted(records_by_id):
        components[find(record_id)].append(record_id)

    baseline_cluster_rows = []
    for index, root in enumerate(sorted(components, key=lambda item: components[item][0]), start=1):
        members = components[root]
        has_document = any(
            records_by_id[a].get("observed_document_id")
            and records_by_id[a].get("observed_document_id") == records_by_id[b].get("observed_document_id")
            for a, b in combinations(members, 2)
        )
        confidence = 0.95 if has_document else (0.80 if len(members) > 1 else 0.50)
        cluster_id = f"BASECL{index:05d}"
        for record_id in members:
            baseline_cluster_rows.append(
                {
                    "observed_person_record_id": record_id,
                    "baseline_cluster_id": cluster_id,
                    "cluster_method": "deterministic_same_document_or_event",
                    "confidence": f"{confidence:.2f}",
                }
            )

    baseline_cluster_rows.sort(key=lambda row: row["observed_person_record_id"])

    oracle_cluster_rows = []
    for record_id in sorted(records_by_id):
        row = records_by_id[record_id]
        truth_row = truth_by_record.get(record_id, {})
        oracle_cluster_rows.append(
            {
                "observed_person_record_id": record_id,
                "oracle_cluster_id": truth_row.get("true_resolution_cluster_id", row.get("canonical_person_id", "")),
                "canonical_person_id": row.get("canonical_person_id", ""),
                "truth_label_type": truth_row.get("truth_label_type", "canonical_person_truth"),
            }
        )

    fragmentation_profile_rows.sort(key=lambda row: row["canonical_person_id"])
    candidate_rows.sort(key=lambda row: row["pair_id"])

    _write_rows(
        corpus_path / "identity_fragmentation_profile.csv",
        [
            "canonical_person_id",
            "true_resolution_cluster_id",
            "observed_record_count",
            "distinct_document_count",
            "distinct_name_variant_count",
            "first_seen_timestamp_utc",
            "last_seen_timestamp_utc",
            "fragmentation_tier",
        ],
        fragmentation_profile_rows,
    )
    _write_rows(
        corpus_path / "record_link_evidence.csv",
        [
            "pair_id",
            "observed_person_record_id_a",
            "observed_person_record_id_b",
            "true_same_person",
            "canonical_person_id_a",
            "canonical_person_id_b",
            "data_split",
            "same_document_flag",
            "same_dob_bucket_flag",
            "same_sex_marker_flag",
            "same_source_system_flag",
            "same_event_flag",
            "shared_vehicle_flag",
            "shared_carrier_flag",
            "shared_residence_flag",
            "deterministic_match_flag",
            "relational_evidence_score",
            "weak_link_candidate_flag",
            "weak_link_positive_flag",
            "evidence_score",
            "match_difficulty",
            "notes",
        ],
        candidate_rows,
    )
    _write_rows(
        corpus_path / "baseline_er_clusters.csv",
        ["observed_person_record_id", "baseline_cluster_id", "cluster_method", "confidence"],
        baseline_cluster_rows,
    )
    _write_rows(
        corpus_path / "oracle_er_clusters.csv",
        ["observed_person_record_id", "oracle_cluster_id", "canonical_person_id", "truth_label_type"],
        oracle_cluster_rows,
    )

    fragmentation_counter = Counter(row["fragmentation_tier"] for row in fragmentation_profile_rows)
    candidate_pair_count = len(candidate_rows)
    summary = {
        "version": "v7_er",
        "generated_at": _format_timestamp(datetime.now(timezone.utc)),
        "observed_records": len(observed_rows),
        "canonical_persons": len(records_by_person),
        "candidate_pairs": candidate_pair_count,
        "true_pairs": true_pair_count,
        "deterministic_true_pairs": deterministic_pair_count,
        "weak_link_true_pairs": weak_link_true_pair_count,
        "oracle_true_pairs": oracle_pair_count,
        "deterministic_pair_recall": (deterministic_pair_count / true_pair_count) if true_pair_count else 0.0,
        "deterministic_plus_weak_link_oracle_pair_recall": (
            (deterministic_pair_count + weak_link_true_pair_count) / true_pair_count if true_pair_count else 0.0
        ),
        "fragmentation_tiers": dict(sorted(fragmentation_counter.items())),
        "data_split_counts": dict(sorted(split_counts.items())),
        "downstream_story": (
            "Deterministic same-document or same-event links recover "
            f"{deterministic_pair_count} of {true_pair_count} true same-person pairs; "
            f"the oracle weak-link coverage set raises deterministic_plus_weak_link_oracle_pair_recall to "
            f"{((deterministic_pair_count + weak_link_true_pair_count) / true_pair_count) if true_pair_count else 0.0:.3f}. "
            "No learned ER-GNN result has been produced yet; this layer remains an oracle calibration artifact."
        ),
    }

    with (corpus_path / SUMMARY_NAME).open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    return summary
