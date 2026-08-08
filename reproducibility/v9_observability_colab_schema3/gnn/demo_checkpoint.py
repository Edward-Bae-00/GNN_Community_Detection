"""Durable, hash-verified scoring checkpoints for the V9 demo."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from types import MappingProxyType
import shutil
import tempfile

import numpy as np
import torch


SCHEMA_VERSION = "1.0"


def _canonical_json(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _sha256_file(path, *, chunk_size=1024 * 1024):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def checkpoint_node_universe_hash(node_ids):
    """Hash the exact ordered node universe used by the model."""
    values = [str(node_id) for node_id in node_ids]
    return hashlib.sha256(_canonical_json(values)).hexdigest()


def corpus_fingerprints(corpus_dir):
    """Return content fingerprints for every corpus CSV input."""
    root = Path(corpus_dir).resolve()
    files = sorted(path for path in root.rglob("*.csv") if path.is_file())
    if not files:
        raise ValueError(f"corpus contains no CSV inputs: {root}")
    return {
        path.relative_to(root).as_posix(): _sha256_file(path)
        for path in files
    }


def _score_array(value, *, name):
    array = np.array(value, copy=True, order="C", subok=False)
    if array.ndim != 1 or array.dtype.kind != "f":
        raise ValueError(f"{name} must be a one-dimensional floating array")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def _event_id_array(values, *, name):
    normalized = [str(value) for value in values]
    if any(not value for value in normalized):
        raise ValueError(f"{name} must contain nonblank event IDs")
    width = max((len(value) for value in normalized), default=1)
    return np.asarray(normalized, dtype=f"<U{width}")


def _array_manifest(arrays):
    return {
        name: {
            "shape": list(array.shape),
            "dtype": array.dtype.str,
            "content_sha256": hashlib.sha256(
                array.tobytes(order="C")
            ).hexdigest(),
        }
        for name, array in sorted(arrays.items())
    }


def _cpu_state_dict(model):
    state = model.state_dict()
    if not isinstance(state, dict) or any(
        not isinstance(value, torch.Tensor) for value in state.values()
    ):
        raise ValueError("model state_dict must contain only tensors")
    return {
        str(key): value.detach().cpu().clone()
        for key, value in state.items()
    }


def _tensor_manifest(state):
    manifest = {}
    for name, value in sorted(state.items()):
        raw = value.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes()
        manifest[name] = {
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "content_sha256": hashlib.sha256(raw).hexdigest(),
        }
    return manifest


def _logical_checkpoint_id(metadata):
    logical = json.loads(json.dumps(metadata))
    logical.pop("checkpoint_id", None)
    logical["model"]["files"] = {
        seed: {"tensors": record["tensors"]}
        for seed, record in sorted(logical["model"]["files"].items())
    }
    logical["scores"].pop("path", None)
    logical["scores"].pop("sha256", None)
    return hashlib.sha256(_canonical_json(logical)).hexdigest()


def _validated_seed_order(metadata):
    raw = metadata.get("run", {}).get("seeds")
    if not isinstance(raw, list):
        raise ValueError("checkpoint seeds must be a list")
    seed_order = tuple(int(seed) for seed in raw)
    if not seed_order or len(set(seed_order)) != len(seed_order):
        raise ValueError("checkpoint seeds must be nonempty and unique")
    return seed_order


def _verify_score_payload(path, metadata):
    scores_record = metadata.get("scores", {})
    scores_path = path / scores_record.get("path", "")
    if _sha256_file(scores_path) != scores_record.get("sha256"):
        raise ValueError("checkpoint scores SHA-256 mismatch")
    try:
        with np.load(scores_path, allow_pickle=False) as source:
            arrays = {name: np.array(source[name], copy=True) for name in source.files}
    except (OSError, ValueError, KeyError) as exc:
        raise ValueError("checkpoint scores are unreadable") from exc
    manifest = scores_record.get("arrays", {})
    if set(arrays) != set(manifest):
        raise ValueError("checkpoint score array names do not match metadata")
    for name, array in arrays.items():
        record = manifest[name]
        if list(array.shape) != record.get("shape"):
            raise ValueError(f"checkpoint score shape mismatch for {name}")
        if array.dtype.str != record.get("dtype"):
            raise ValueError(f"checkpoint score dtype mismatch for {name}")
        digest = hashlib.sha256(array.tobytes(order="C")).hexdigest()
        if digest != record.get("content_sha256"):
            raise ValueError(f"checkpoint score content hash mismatch for {name}")
    return arrays


def _verify_model_payload(path, metadata, seed_order):
    model_files = metadata.get("model", {}).get("files", {})
    if set(model_files) != {str(seed) for seed in seed_order}:
        raise ValueError("checkpoint model files do not exactly match seeds")
    states = {}
    for seed in seed_order:
        record = model_files[str(seed)]
        model_path = path / record["path"]
        if _sha256_file(model_path) != record.get("sha256"):
            raise ValueError(f"checkpoint model SHA-256 mismatch for seed {seed}")
        try:
            state = torch.load(model_path, map_location="cpu", weights_only=True)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError(f"checkpoint model state is unreadable for seed {seed}") from exc
        if not isinstance(state, dict) or any(
            not isinstance(key, str) or not isinstance(value, torch.Tensor)
            for key, value in state.items()
        ):
            raise ValueError("checkpoint model state contains unsafe values")
        actual = _tensor_manifest(state)
        expected = record.get("tensors")
        if set(actual) != set(expected or {}):
            raise ValueError(f"checkpoint model tensor names mismatch for seed {seed}")
        for name in actual:
            if actual[name]["shape"] != expected[name].get("shape"):
                raise ValueError(
                    f"checkpoint model tensor shape mismatch for seed {seed}: {name}"
                )
            if actual[name]["dtype"] != expected[name].get("dtype"):
                raise ValueError(
                    f"checkpoint model tensor dtype mismatch for seed {seed}: {name}"
                )
            if actual[name]["content_sha256"] != expected[name].get("content_sha256"):
                raise ValueError(
                    f"checkpoint model tensor content hash mismatch for seed {seed}: {name}"
                )
        states[seed] = state
    return states


def _verify_checkpoint_closure(path, metadata):
    seed_order = _validated_seed_order(metadata)
    arrays = _verify_score_payload(path, metadata)
    states = _verify_model_payload(path, metadata, seed_order)
    checkpoint_id = metadata.get("checkpoint_id")
    if _logical_checkpoint_id(metadata) != checkpoint_id or path.name != checkpoint_id:
        raise ValueError("checkpoint ID does not match verified metadata")
    return seed_order, arrays, states


@dataclass(frozen=True)
class WrittenDemoCheckpoint:
    """Paths and identity metadata for a newly written checkpoint.

    ``checkpoint_id`` names the content-derived publication and ``path`` points
    to its atomically written directory after closure checks succeed.
    """

    checkpoint_id: str
    path: Path


@dataclass(frozen=True)
class LoadedDemoCheckpoint:
    """Validated models, scores, and metadata loaded from a checkpoint.

    The record contains hash-checked metadata, model mappings, score arrays, and
    aligned validation/test event IDs reconstructed from the verified payload.
    """

    checkpoint_id: str
    path: Path
    metadata: dict
    models_by_seed: MappingProxyType
    baseline_valid: np.ndarray
    baseline_test: np.ndarray
    gnn_valid_by_seed: MappingProxyType
    gnn_test_by_seed: MappingProxyType
    validation_event_ids: np.ndarray
    test_event_ids: np.ndarray


def _write_json(path, value):
    with Path(path).open("wb") as handle:
        handle.write(_canonical_json(value))
        handle.flush()
        os.fsync(handle.fileno())


def write_demo_checkpoint(
    *,
    checkpoints_root,
    corpus_dir,
    seeds,
    epochs,
    train_bucket,
    valid_sample,
    gnn_arm,
    substrate,
    feature_schema,
    node_ids,
    relation_schema,
    fusion_weights,
    model_name,
    model_kwargs,
    models_by_seed,
    baseline_valid,
    baseline_test,
    gnn_valid_by_seed,
    gnn_test_by_seed,
    validation_event_ids,
    test_event_ids,
):
    """Atomically publish a complete scoring checkpoint."""
    seed_order = tuple(int(seed) for seed in seeds)
    if not seed_order or len(set(seed_order)) != len(seed_order):
        raise ValueError("checkpoint seeds must be nonempty and unique")
    if set(models_by_seed) != set(seed_order):
        raise ValueError("models_by_seed must exactly match checkpoint seeds")
    if set(gnn_valid_by_seed) != set(seed_order):
        raise ValueError("gnn_valid_by_seed must exactly match checkpoint seeds")
    if set(gnn_test_by_seed) != set(seed_order):
        raise ValueError("gnn_test_by_seed must exactly match checkpoint seeds")

    arrays = {
        "baseline_valid": _score_array(baseline_valid, name="baseline_valid"),
        "baseline_test": _score_array(baseline_test, name="baseline_test"),
        "validation_event_ids": _event_id_array(
            validation_event_ids, name="validation_event_ids"
        ),
        "test_event_ids": _event_id_array(test_event_ids, name="test_event_ids"),
    }
    for seed in seed_order:
        arrays[f"gnn_valid_seed_{seed}"] = _score_array(
            gnn_valid_by_seed[seed], name=f"gnn_valid_seed_{seed}"
        )
        arrays[f"gnn_test_seed_{seed}"] = _score_array(
            gnn_test_by_seed[seed], name=f"gnn_test_seed_{seed}"
        )
    if len(arrays["baseline_valid"]) != len(arrays["validation_event_ids"]):
        raise ValueError("validation scores and event IDs must align")
    if len(arrays["baseline_test"]) != len(arrays["test_event_ids"]):
        raise ValueError("test scores and event IDs must align")
    for seed in seed_order:
        if arrays[f"gnn_valid_seed_{seed}"].shape != arrays["baseline_valid"].shape:
            raise ValueError("all validation score arrays must align")
        if arrays[f"gnn_test_seed_{seed}"].shape != arrays["baseline_test"].shape:
            raise ValueError("all test score arrays must align")

    root = Path(checkpoints_root)
    root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".checkpoint.tmp-", dir=root))
    try:
        models_dir = stage / "models"
        models_dir.mkdir()
        model_records = {}
        for seed in seed_order:
            relative = Path("models") / f"seed_{seed}.pt"
            target = stage / relative
            state = _cpu_state_dict(models_by_seed[seed])
            torch.save(state, target)
            model_records[str(seed)] = {
                "path": relative.as_posix(),
                "sha256": _sha256_file(target),
                "tensors": _tensor_manifest(state),
            }

        scores_path = stage / "scores.npz"
        np.savez_compressed(scores_path, **arrays)
        metadata = {
            "schema_version": SCHEMA_VERSION,
            "corpus": {
                "identity": str(Path(corpus_dir).resolve()),
                "fingerprints": corpus_fingerprints(corpus_dir),
            },
            "run": {
                "seeds": list(seed_order),
                "epochs": int(epochs),
                "train_bucket": str(train_bucket),
                "valid_sample": None if valid_sample is None else int(valid_sample),
                "gnn_arm": str(gnn_arm),
                "substrate": str(substrate),
            },
            "feature_schema": {
                str(key): [str(value) for value in values]
                for key, values in sorted(feature_schema.items())
            },
            "node_universe": {
                "count": len(node_ids),
                "sha256": checkpoint_node_universe_hash(node_ids),
            },
            "relation_schema": {
                str(key): int(value)
                for key, value in sorted(relation_schema.items())
            },
            "fusion_weights": {
                str(key): float(value)
                for key, value in sorted(fusion_weights.items())
            },
            "model": {
                "name": str(model_name),
                "kwargs": dict(model_kwargs),
                "files": model_records,
            },
            "scores": {
                "path": "scores.npz",
                "sha256": _sha256_file(scores_path),
                "arrays": _array_manifest(arrays),
            },
        }
        checkpoint_id = _logical_checkpoint_id(metadata)
        metadata["checkpoint_id"] = checkpoint_id
        _write_json(stage / "metadata.json", metadata)
        destination = root / checkpoint_id
        if destination.exists():
            existing = read_demo_checkpoint_metadata(destination)
            _verify_checkpoint_closure(destination, existing)
            if _logical_checkpoint_id(existing) != checkpoint_id:
                raise ValueError(f"checkpoint ID collision at existing path: {destination}")
            return WrittenDemoCheckpoint(checkpoint_id, destination)
        os.replace(stage, destination)
        stage = None
        return WrittenDemoCheckpoint(checkpoint_id, destination)
    finally:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)


def read_demo_checkpoint_metadata(checkpoint_path):
    """Read checkpoint metadata without loading model tensors or score arrays.

    ``checkpoint_path`` names a checkpoint directory.  The returned mapping is
    JSON-decoded and schema/identity checked without publishing or mutating any
    files; unreadable or incompatible metadata raises ``ValueError``.
    """
    path = Path(checkpoint_path)
    try:
        metadata = json.loads((path / "metadata.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("checkpoint metadata is unreadable") from exc
    if metadata.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported checkpoint schema_version")
    if not isinstance(metadata.get("checkpoint_id"), str):
        raise ValueError("checkpoint metadata lacks checkpoint_id")
    return metadata


def _expected_value(metadata, key):
    locations = {
        "seeds": metadata["run"]["seeds"],
        "epochs": metadata["run"]["epochs"],
        "train_bucket": metadata["run"]["train_bucket"],
        "valid_sample": metadata["run"]["valid_sample"],
        "gnn_arm": metadata["run"]["gnn_arm"],
        "substrate": metadata["run"]["substrate"],
        "corpus_identity": metadata["corpus"]["identity"],
        "corpus_fingerprints": metadata["corpus"]["fingerprints"],
        "feature_schema": metadata["feature_schema"],
        "node_universe_hash": metadata["node_universe"]["sha256"],
        "relation_schema": metadata["relation_schema"],
        "fusion_weights": metadata["fusion_weights"],
    }
    if key not in locations:
        raise ValueError(f"unsupported checkpoint compatibility field: {key}")
    return locations[key]


def load_demo_checkpoint(checkpoint_path, *, model_registry, expected=None):
    """Verify a checkpoint completely, then safely reconstruct its models."""
    path = Path(checkpoint_path)
    metadata = read_demo_checkpoint_metadata(path)
    seed_order, arrays, states = _verify_checkpoint_closure(path, metadata)
    checkpoint_id = metadata["checkpoint_id"]
    for key, value in (expected or {}).items():
        if _expected_value(metadata, key) != value:
            raise ValueError(f"checkpoint is incompatible with expected {key}")

    model_record = metadata["model"]
    model_name = model_record["name"]
    if model_name not in model_registry:
        raise ValueError(f"checkpoint model is not registered: {model_name}")
    models = {}
    for seed in seed_order:
        model = model_registry[model_name](**model_record["kwargs"])
        target_state = model.state_dict()
        if set(target_state) != set(states[seed]):
            raise ValueError(f"checkpoint model keys are incompatible for seed {seed}")
        for name, value in states[seed].items():
            if target_state[name].dtype != value.dtype:
                raise ValueError(
                    f"checkpoint model tensor dtype is incompatible for seed {seed}: {name}"
                )
            if target_state[name].shape != value.shape:
                raise ValueError(
                    f"checkpoint model tensor shape is incompatible for seed {seed}: {name}"
                )
        model.load_state_dict(states[seed], strict=True)
        model.eval()
        models[seed] = model

    for name in ("baseline_valid", "baseline_test"):
        _score_array(arrays[name], name=name)
    gnn_valid = {}
    gnn_test = {}
    for seed in seed_order:
        gnn_valid[seed] = _score_array(
            arrays[f"gnn_valid_seed_{seed}"], name=f"gnn_valid_seed_{seed}"
        )
        gnn_test[seed] = _score_array(
            arrays[f"gnn_test_seed_{seed}"], name=f"gnn_test_seed_{seed}"
        )
        if gnn_valid[seed].shape != arrays["baseline_valid"].shape:
            raise ValueError("checkpoint validation score shapes are not aligned")
        if gnn_test[seed].shape != arrays["baseline_test"].shape:
            raise ValueError("checkpoint test score shapes are not aligned")
    if arrays["validation_event_ids"].dtype.kind != "U":
        raise ValueError("checkpoint validation event ID dtype is invalid")
    if arrays["test_event_ids"].dtype.kind != "U":
        raise ValueError("checkpoint test event ID dtype is invalid")
    if arrays["validation_event_ids"].shape != arrays["baseline_valid"].shape:
        raise ValueError("checkpoint validation event IDs are not aligned")
    if arrays["test_event_ids"].shape != arrays["baseline_test"].shape:
        raise ValueError("checkpoint test event IDs are not aligned")

    return LoadedDemoCheckpoint(
        checkpoint_id=checkpoint_id,
        path=path,
        metadata=metadata,
        models_by_seed=MappingProxyType(models),
        baseline_valid=arrays["baseline_valid"],
        baseline_test=arrays["baseline_test"],
        gnn_valid_by_seed=MappingProxyType(gnn_valid),
        gnn_test_by_seed=MappingProxyType(gnn_test),
        validation_event_ids=arrays["validation_event_ids"],
        test_event_ids=arrays["test_event_ids"],
    )
