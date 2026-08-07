#!/usr/bin/env python3
"""Run the fixed V9 schema-3 observability producer in Colab.

The checkpoint records the original absolute corpus path as part of its
identity.  Colab therefore receives a local copy at that exact path before
the normal checkpoint loader is called.  Hot files stay on local scratch;
``--export-dir`` is only touched after the final artifact validates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path


CHECKPOINT_ID = (
    "17d5ee9fe23234ab33b0ba33e36800ab21bd25101b32ff51bb787b259e4f3c52"
)
RECORDED_CORPUS = Path(
    "/Users/edward/Desktop/GNN_Community_Detection/Documents/Data/"
    "synthetic_cbp_graph_corpus_v9"
)


def _package_root() -> Path:
    return Path(__file__).resolve().parent


def _atomic_json(path: Path, payload: object) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, sort_keys=True, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _ensure_recorded_corpus(source: Path, target: Path) -> Path:
    source = Path(source).resolve()
    target = Path(target)
    if not source.is_dir():
        raise FileNotFoundError(f"package corpus is missing: {source}")
    if target.exists():
        if not target.is_dir():
            raise ValueError(f"recorded corpus path is not a directory: {target}")
        return target.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return target.resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _export_file(source: Path, export_dir: Path) -> Path:
    source = Path(source).resolve()
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    destination = export_dir / source.name
    temporary = export_dir / f".{source.name}.{os.getpid()}.tmp"
    try:
        shutil.copy2(source, temporary)
        if _sha256(source) != _sha256(temporary):
            raise ValueError("exported artifact hash does not match source")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def _sha256_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _iter_bundle_references(node):
    """Yield every ``{path, sha256, bytes}`` reference dict found anywhere
    inside ``node`` (a schema-3 manifest sub-field such as ``detail_index``,
    ``community_index``, ``catalog_index``, or ``community_sidecar_index``).

    These indexes nest references at different depths (``catalog_index``
    wraps chunk refs inside per-kind ``chunks`` lists, while
    ``detail_index``/``community_index`` entries are refs merged with extra
    ``cohort``/``community_key`` fields), so a generic recursive scan for any
    dict carrying the ``path``/``sha256``/``bytes`` triple is used instead of
    hard-coding the shape.
    """
    if isinstance(node, dict):
        if (
            isinstance(node.get("path"), str)
            and isinstance(node.get("sha256"), str)
            and isinstance(node.get("bytes"), int)
        ):
            yield node
        for value in node.values():
            yield from _iter_bundle_references(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_bundle_references(item)


def _collect_bundle_references(manifest: dict) -> list[dict]:
    refs: list[dict] = []
    for field in (
        "detail_index",
        "community_index",
        "catalog_index",
        "community_sidecar_index",
    ):
        if field in manifest:
            refs.extend(_iter_bundle_references(manifest[field]))
    return refs


def _export_bundle(output: Path, export_dir: Path) -> dict:
    """Publish the schema-3 pointer manifest JSON together with its full
    ``recovery/`` evidence tree into ``export_dir``.

    The written JSON is only a compact pointer manifest -- the real
    evidence lives in the sibling ``recovery/`` tree written by
    ``RecoveryBundleWriter``.  ``publish_prepackaged_schema3_manifest``
    resolves sidecar references relative to
    ``Path(artifact_json_path).parent / manifest["sidecar_base"]``, i.e.
    ``export_dir/recovery/bundles/<bundle_id>/<path>`` -- confirmed from
    ``RecoveryBundleWriter._object_path``/``_read_verified_ref`` and
    ``finalize_schema3`` in gnn/recovery_bundle.py, where every sidecar ref's
    ``path`` is resolved against ``self.staging_root`` and, once published,
    against ``final_bundle = self.final_root / bundle_path`` (i.e.
    ``recovery/bundles/<bundle_id>``).

    Crash-safety ordering: the recovery/ tree is staged into a temp
    directory inside ``export_dir`` (same filesystem, so the final swap is a
    single ``os.replace``), fully verified from the staged copy, and
    published *before* the JSON is copied. A partially exported directory
    must never contain a JSON that points at missing or corrupt sidecars, so
    the JSON copy (which already has its own sha256-verified copy path via
    ``_export_file``) only happens after the recovery tree is safely in
    place. Any verification failure raises and leaves no trace in
    ``export_dir``.
    """
    output = Path(output).resolve()
    export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(output.read_text(encoding="utf-8"))
    bundle_id = manifest.get("bundle_id")
    bundle_path = manifest.get("bundle_path")
    if not isinstance(bundle_id, str) or not bundle_id:
        raise ValueError("artifact manifest is missing bundle_id")
    if bundle_path != f"bundles/{bundle_id}":
        raise ValueError("artifact manifest bundle_path is not canonical")

    source_recovery = output.parent / "recovery"
    if not source_recovery.is_dir():
        raise FileNotFoundError(
            f"recovery evidence tree is missing: {source_recovery}"
        )
    source_bundle_dir = source_recovery / bundle_path
    source_manifest = source_bundle_dir / "manifest.json"
    if not source_manifest.is_file():
        raise FileNotFoundError(
            f"recovery bundle manifest is missing: {source_manifest}"
        )

    references = _collect_bundle_references(manifest)

    stage_dir = Path(tempfile.mkdtemp(dir=export_dir, prefix=".recovery-stage-"))
    target = export_dir / "recovery"
    try:
        shutil.copytree(
            source_recovery, stage_dir, copy_function=shutil.copy2, dirs_exist_ok=True
        )

        staged_bundle_dir = stage_dir / bundle_path
        try:
            staged_bundle_dir.resolve().relative_to(stage_dir.resolve())
        except ValueError as exc:
            raise ValueError("bundle_path escapes recovery export root") from exc

        staged_manifest = staged_bundle_dir / "manifest.json"
        if not staged_manifest.is_file():
            raise FileNotFoundError(
                f"exported recovery bundle manifest is missing: {staged_manifest}"
            )
        if staged_manifest.read_bytes() != source_manifest.read_bytes():
            raise ValueError(
                "exported recovery bundle manifest does not match source"
            )
        if not (stage_dir / "current.json").is_file():
            raise FileNotFoundError("exported recovery tree is missing current.json")

        # Copy fidelity for the WHOLE tree, not just the objects the manifest
        # names directly.  The manifest indexes reference only top-level
        # objects; the chunk/catalog objects those payloads point into are
        # reachable solely by following refs *inside* the sidecars (which is
        # what the downstream validator does).  In a real bundle that is the
        # large majority of files, so verifying references alone would let a
        # chunk corrupted during the Drive write sail through here and fail
        # only at dashboard-build time -- days later, with the source VM long
        # gone.  Comparing every staged file against its source closes that
        # window and also catches truncated writes.
        source_files = sorted(
            path for path in source_recovery.rglob("*") if path.is_file()
        )
        for source_file in source_files:
            relative = source_file.relative_to(source_recovery)
            staged_file = stage_dir / relative
            if not staged_file.is_file():
                raise FileNotFoundError(
                    f"exported recovery file is missing: {relative.as_posix()}"
                )
            if _sha256_and_size(staged_file) != _sha256_and_size(source_file):
                raise ValueError(
                    "exported recovery file failed verification: "
                    f"{relative.as_posix()}"
                )
        staged_count = sum(1 for path in stage_dir.rglob("*") if path.is_file())
        if staged_count != len(source_files):
            raise ValueError(
                f"exported recovery tree has {staged_count} files, "
                f"expected {len(source_files)}"
            )

        # The reference pass is a different assertion from copy fidelity: it
        # checks that the manifest's recorded sha256/bytes actually describe
        # the objects on disk, so a manifest that disagrees with its own
        # bundle is rejected before publication rather than downstream.
        for ref in references:
            relative = Path(ref["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"sidecar reference path is unsafe: {ref['path']!r}")
            destination = staged_bundle_dir / relative
            try:
                destination.resolve().relative_to(staged_bundle_dir.resolve())
            except ValueError as exc:
                raise ValueError(
                    f"sidecar reference escapes bundle: {ref['path']!r}"
                ) from exc
            if not destination.is_file():
                raise FileNotFoundError(
                    f"exported sidecar object is missing: {destination}"
                )
            digest, size = _sha256_and_size(destination)
            if digest != ref["sha256"] or size != ref["bytes"]:
                raise ValueError(
                    f"exported sidecar object failed verification: {ref['path']!r}"
                )

        old_aside = export_dir / f".recovery.old.{os.getpid()}.tmp"
        moved_old_aside = False
        if target.exists():
            # os.replace() cannot atomically replace a non-empty directory,
            # so move the existing export aside first, swap the new one in,
            # then delete the old one.
            os.replace(target, old_aside)
            moved_old_aside = True
        try:
            os.replace(stage_dir, target)
        except Exception:
            if moved_old_aside:
                os.replace(old_aside, target)
            raise
        if moved_old_aside:
            shutil.rmtree(old_aside, ignore_errors=True)
    except Exception:
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)
        raise

    exported_json = _export_file(output, export_dir)
    return {
        "exported_artifact": str(exported_json),
        "exported_recovery_dir": str(target),
        "bundle_id": bundle_id,
    }


_COVERAGE_GATE_FIELDS = (
    "narrative_preflight_failed",
    "failed_count",
    "narrative_fallback",
    "hybrid_explained",
    "hybrid_attribution_complete",
    "hybrid_structural_fallback",
    "hybrid_available",
    "hybrid_eligible",
    "baseline_available",
    "baseline_community",
)


def _evaluate_coverage_gate(
    coverage: dict, *, hybrid_detail_limit: int, baseline_control_limit: int
) -> list[str]:
    """Return a list of human-readable reasons the coverage gate failed.

    An empty list means the run looks healthy. Semantics verified against
    gnn/observability_artifact.py's schema-3 coverage dict.

    The Hybrid budget must be filled by ``hybrid_explained`` alone.
    ``hybrid_structural_fallback`` counts candidates too large for GNNExplainer
    that were downgraded to community-only evidence; that is different evidence,
    not a substitute, so any of it fails the gate. Treating the two as
    interchangeable is what allowed a 10-explained run to exit successfully
    against a 20-case budget.

    ``hybrid_available``/``baseline_available`` are candidate-pool sizes, so a
    pool smaller than the requested limit remains a legitimate shortfall rather
    than a gate failure. ``hybrid_eligible`` is the count that passed explainer
    preflight, and it is reported when it -- rather than case failures -- is
    what kept the budget from being filled.
    """
    missing = [field for field in _COVERAGE_GATE_FIELDS if field not in coverage]
    if missing:
        return [f"coverage is missing required field(s): {', '.join(sorted(missing))}"]

    reasons = []
    if coverage["narrative_preflight_failed"] != 0:
        reasons.append(
            "narrative_preflight_failed="
            f"{coverage['narrative_preflight_failed']} (expected 0) -- "
            "Ollama/model narrative preflight failed"
        )
    if coverage["failed_count"] != 0:
        reasons.append(
            f"failed_count={coverage['failed_count']} (expected 0) -- "
            "one or more cases failed write_case validation"
        )
    if coverage["narrative_fallback"] != 0:
        reasons.append(
            f"narrative_fallback={coverage['narrative_fallback']} (expected 0) -- "
            "deterministic-template narratives were used instead of "
            "validated LLM narratives"
        )
    if coverage["hybrid_structural_fallback"] != 0:
        reasons.append(
            "hybrid_structural_fallback="
            f"{coverage['hybrid_structural_fallback']} (expected 0) -- "
            "community-only evidence was published in place of GNNExplainer "
            "explanations, so the Hybrid budget is not all exact"
        )
    ceiling_hint = ""
    if coverage["hybrid_eligible"] < hybrid_detail_limit:
        # Distinguish "the ceiling admitted too few candidates" from "cases
        # failed", because only the first is fixed by changing the ceiling.
        ceiling_hint = (
            f"; only hybrid_eligible={coverage['hybrid_eligible']} candidates "
            "passed explainer preflight -- raise MAX_EXPLAINER_INPUT_NODES/EDGES "
            "in gnn/sage_explainer.py (use --preflight-only to size it from "
            "measured candidates)"
        )
    if coverage["hybrid_explained"] <= 0:
        reasons.append(
            f"hybrid_explained={coverage['hybrid_explained']} (expected > 0) -- "
            "no Hybrid case was successfully GNNExplainer-explained"
            + ceiling_hint
        )
    elif (
        coverage["hybrid_available"] >= hybrid_detail_limit
        and coverage["hybrid_explained"] != hybrid_detail_limit
    ):
        reasons.append(
            f"hybrid budget not fully explained: hybrid_explained="
            f"{coverage['hybrid_explained']} != hybrid_detail_limit="
            f"{hybrid_detail_limit} (hybrid_available="
            f"{coverage['hybrid_available']} >= limit)"
            + ceiling_hint
        )
    elif coverage["hybrid_attribution_complete"] != coverage["hybrid_explained"]:
        # Only reported once the budget itself is sound, so a short run is not
        # described as two separate problems.
        reasons.append(
            "hybrid_attribution_complete="
            f"{coverage['hybrid_attribution_complete']} != hybrid_explained="
            f"{coverage['hybrid_explained']} -- some published explanations "
            "omitted mask records, so their top_local_nodes/top_edges rank over "
            "part of the input and must not be reported as exact attribution"
        )
    if coverage["baseline_available"] >= baseline_control_limit:
        if coverage["baseline_community"] != baseline_control_limit:
            reasons.append(
                f"baseline budget not filled: baseline_community="
                f"{coverage['baseline_community']} != baseline_control_limit="
                f"{baseline_control_limit} (baseline_available="
                f"{coverage['baseline_available']} >= limit)"
            )
    return reasons


class _PreflightOnlyComplete(Exception):
    """Signals that a ``--preflight-only`` run has collected what it needs.

    Preflight sits in the middle of the artifact build, so stopping there means
    unwinding the build.  Raising from the instrumentation callback does that
    without giving the library a special half-run mode to maintain.
    """

    def __init__(self, summary_path: Path):
        super().__init__(f"preflight-only run stopped after preflight: {summary_path}")
        self.summary_path = summary_path


def _progress_callback(progress_path: Path, *, preflight_only_out: Path | None = None):
    def on_stage(stage: str, payload: dict[str, object]) -> None:
        record = {
            "stage": stage,
            "updated_at_epoch": time.time(),
            "payload": payload,
        }
        _atomic_json(progress_path, record)
        print(json.dumps(record, sort_keys=True, default=str), flush=True)
        if preflight_only_out is not None and stage == "preflight_complete":
            _atomic_json(preflight_only_out, payload)
            raise _PreflightOnlyComplete(preflight_only_out)

    return on_stage


def _report_preflight_only(summary_path: Path) -> None:
    """Print the measured candidate sizes and what each ceiling would admit."""
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    summary = payload.get("size_summary", {})
    print(f"\npreflight distribution written to {summary_path}", flush=True)
    print(
        f"candidates={summary.get('candidates')} "
        f"eligible_at_current_ceiling={payload.get('eligible_hybrid')} "
        f"(max_nodes={payload.get('max_nodes')}, max_edges={payload.get('max_edges')})",
        flush=True,
    )
    percentiles = summary.get("percentiles", {})
    for field in ("node_count", "edge_count"):
        values = percentiles.get(field)
        if values:
            rendered = " ".join(
                f"{name}={value}" for name, value in sorted(values.items())
            )
            print(f"{field}: {rendered}", flush=True)
    grid = summary.get("ceiling_grid", [])
    if grid:
        print("\nceiling -> eligible candidates", flush=True)
        for row in grid:
            print(
                f"  max_nodes={row['max_nodes']:>5} "
                f"max_edges={row['max_edges']:>6} -> {row['eligible']}",
                flush=True,
            )
    print(
        "\nSet MAX_EXPLAINER_INPUT_NODES/EDGES in gnn/sage_explainer.py to the "
        "smallest row that admits the number of Hybrid cases you need, then "
        "re-run without --preflight-only.",
        flush=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=None,
        help="handoff root; defaults to the directory containing this script",
    )
    parser.add_argument(
        "--work-root",
        type=Path,
        default=Path("/content/v9_schema3_run"),
        help="local Colab scratch root, never a Drive FUSE path",
    )
    parser.add_argument(
        "--recorded-corpus",
        type=Path,
        default=RECORDED_CORPUS,
        help="must remain the absolute path recorded by the checkpoint",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=None,
        help="optional Drive directory receiving the validated JSON",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help=(
            "stop once explainer preflight has measured every Hybrid "
            "candidate, writing preflight_distribution.json to the work root. "
            "Use it to choose the eligibility ceiling from measured sizes "
            "before committing to a full run"
        ),
    )
    parser.add_argument(
        "--hybrid-detail-limit", type=int, default=20
    )
    parser.add_argument(
        "--baseline-control-limit", type=int, default=10
    )
    parser.add_argument(
        "--allow-shortfall",
        action="store_true",
        help=(
            "downgrade the post-run coverage gate to a printed warning and "
            "proceed with the export instead of failing on a degraded run "
            "(e.g. narrative preflight failures, failed cases, a Hybrid budget "
            "not filled by exact explanations, or any structural fallback "
            "published in place of one)"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    package_root = (
        Path(args.package_root).resolve()
        if args.package_root is not None
        else _package_root()
    )
    work_root = Path(args.work_root).resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(package_root))

    checkpoint = (
        package_root / "checkpoint" / CHECKPOINT_ID
    ).resolve()
    source_corpus = (
        package_root / "corpus" / "synthetic_cbp_graph_corpus_v9"
    ).resolve()
    if checkpoint.name != CHECKPOINT_ID or not checkpoint.is_dir():
        raise FileNotFoundError(f"verified checkpoint is missing: {checkpoint}")
    recorded_corpus = _ensure_recorded_corpus(source_corpus, args.recorded_corpus)

    output = work_root / "hybrid_recovery_explanations_v9.json"
    progress = work_root / "progress.json"
    _atomic_json(
        progress,
        {
            "stage": "inputs_ready",
            "checkpoint": str(checkpoint),
            "recorded_corpus": str(recorded_corpus),
            "hybrid_detail_limit": args.hybrid_detail_limit,
            "baseline_control_limit": args.baseline_control_limit,
        },
    )
    print(f"checkpoint={checkpoint}", flush=True)
    print(f"recorded_corpus={recorded_corpus}", flush=True)
    print(f"output={output}", flush=True)

    from gnn.run_demo import resume_observability

    preflight_distribution = work_root / "preflight_distribution.json"
    try:
        artifact = resume_observability(
            checkpoint,
            corpus_dir=recorded_corpus,
            observability_out_name=output,
            schema_version="3.0",
            hybrid_detail_limit=args.hybrid_detail_limit,
            baseline_control_limit=args.baseline_control_limit,
            observability_instrumentation={
                "on_stage": _progress_callback(
                    progress,
                    preflight_only_out=(
                        preflight_distribution if args.preflight_only else None
                    ),
                ),
            },
        )
    except _PreflightOnlyComplete as stopped:
        _report_preflight_only(stopped.summary_path)
        return 0
    coverage = artifact.get("coverage", {})
    gate_reasons = _evaluate_coverage_gate(
        coverage,
        hybrid_detail_limit=args.hybrid_detail_limit,
        baseline_control_limit=args.baseline_control_limit,
    )
    gate_passed = not gate_reasons
    result = {
        "schema_version": artifact.get("schema_version"),
        "coverage": coverage,
        "artifact": str(output),
        "sha256": _sha256(output),
        "coverage_gate_passed": gate_passed,
    }
    if not gate_passed:
        result["coverage_gate_failed_reasons"] = gate_reasons
        result["coverage_gate_shortfall_allowed"] = bool(args.allow_shortfall)
    _atomic_json(work_root / "result.json", result)
    print(json.dumps(result, sort_keys=True, indent=2), flush=True)

    if not gate_passed:
        print("=" * 72, flush=True)
        print(
            "COVERAGE GATE FAILED -- this looks like a degraded run "
            "(e.g. Ollama/gemma unavailable), not a healthy artifact:",
            flush=True,
        )
        for reason in gate_reasons:
            print(f"  - {reason}", flush=True)
        print(
            f"coverage.shortfall_reasons={coverage.get('shortfall_reasons')}",
            flush=True,
        )
        narrative_diagnostics = artifact.get("generation_diagnostics", {}).get(
            "narrative"
        )
        if narrative_diagnostics:
            print(
                "generation_diagnostics.narrative="
                + json.dumps(narrative_diagnostics, sort_keys=True, default=str),
                flush=True,
            )
        print("=" * 72, flush=True)
        if not args.allow_shortfall:
            print(
                "exiting non-zero and skipping export "
                "(pass --allow-shortfall to override)",
                flush=True,
            )
            return 1
        print(
            "--allow-shortfall set: proceeding with export despite the "
            "coverage gate failure above",
            flush=True,
        )

    if args.export_dir is not None:
        exported = _export_bundle(output, Path(args.export_dir))
        result.update(exported)
        _atomic_json(work_root / "result.json", result)
        print(f"exported_artifact={exported['exported_artifact']}", flush=True)
        print(
            f"exported_recovery_dir={exported['exported_recovery_dir']}", flush=True
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
