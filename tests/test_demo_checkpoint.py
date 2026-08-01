import json
from pathlib import Path

import numpy as np
import pytest
import torch

from gnn.demo_checkpoint import (
    checkpoint_node_universe_hash,
    load_demo_checkpoint,
    write_demo_checkpoint,
)


class TinyModel(torch.nn.Module):
    def __init__(self, in_dim, num_relations=None):
        super().__init__()
        self.linear = torch.nn.Linear(in_dim, 1)

    def forward(self, values):
        return self.linear(values)


def _checkpoint_kwargs(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "source.csv").write_text("id,value\na,1\n")
    models = {seed: TinyModel(3, num_relations=4) for seed in (0, 1, 2)}
    return {
        "checkpoints_root": tmp_path / "checkpoints",
        "corpus_dir": corpus,
        "seeds": (0, 1, 2),
        "epochs": 18,
        "train_bucket": "Q",
        "valid_sample": 20_000,
        "gnn_arm": "sage",
        "substrate": "oracle",
        "feature_schema": {
            "baseline": ["own_history", "event_context"],
            "gnn": ["bias", "caught_before_snapshot"],
        },
        "node_ids": ["P-1", "P-2"],
        "relation_schema": {
            "COTRAVEL": 0,
            "RESIDENCE": 1,
            "SHARED_PLATE": 2,
            "SHARED_PLATE_HOT": 3,
        },
        "fusion_weights": {"deployable": 0.75, "oracle": 1.0},
        "model_name": "sage",
        "model_kwargs": {"in_dim": 3, "num_relations": 4},
        "models_by_seed": models,
        "baseline_valid": np.array([0.2, 0.4], dtype=np.float64),
        "baseline_test": np.array([0.1, 0.3, 0.5], dtype=np.float64),
        "gnn_valid_by_seed": {
            seed: np.array([seed + 0.1, seed + 0.2], dtype=np.float32)
            for seed in (0, 1, 2)
        },
        "gnn_test_by_seed": {
            seed: np.array([seed + 0.3, seed + 0.4, seed + 0.5], dtype=np.float32)
            for seed in (0, 1, 2)
        },
        "validation_event_ids": ["v1", "v2"],
        "test_event_ids": ["t1", "t2", "t3"],
    }


def test_checkpoint_round_trip_verifies_and_safely_reconstructs_models(tmp_path):
    kwargs = _checkpoint_kwargs(tmp_path)
    written = write_demo_checkpoint(**kwargs)

    loaded = load_demo_checkpoint(
        written.path,
        model_registry={"sage": TinyModel},
        expected={
            "seeds": [0, 1, 2],
            "epochs": 18,
            "train_bucket": "Q",
            "valid_sample": 20_000,
            "gnn_arm": "sage",
            "substrate": "oracle",
            "node_universe_hash": checkpoint_node_universe_hash(["P-1", "P-2"]),
        },
    )

    assert loaded.checkpoint_id == written.checkpoint_id
    assert loaded.validation_event_ids.tolist() == ["v1", "v2"]
    assert loaded.test_event_ids.tolist() == ["t1", "t2", "t3"]
    np.testing.assert_array_equal(loaded.baseline_test, kwargs["baseline_test"])
    for seed in (0, 1, 2):
        np.testing.assert_array_equal(
            loaded.gnn_test_by_seed[seed], kwargs["gnn_test_by_seed"][seed]
        )
        for key, value in kwargs["models_by_seed"][seed].state_dict().items():
            torch.testing.assert_close(loaded.models_by_seed[seed].state_dict()[key], value)


@pytest.mark.parametrize("target", ["scores", "model"])
def test_checkpoint_rejects_corrupted_payload_hashes(tmp_path, target):
    written = write_demo_checkpoint(**_checkpoint_kwargs(tmp_path))
    if target == "scores":
        payload = written.path / "scores.npz"
    else:
        payload = written.path / "models" / "seed_0.pt"
    payload.write_bytes(payload.read_bytes() + b"corrupt")

    with pytest.raises(ValueError, match="SHA-256"):
        load_demo_checkpoint(written.path, model_registry={"sage": TinyModel})


def test_checkpoint_rejects_shape_metadata_tampering_even_with_rehashed_metadata(tmp_path):
    written = write_demo_checkpoint(**_checkpoint_kwargs(tmp_path))
    metadata_path = written.path / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["scores"]["arrays"]["baseline_test"]["shape"] = [99]
    metadata_path.write_text(json.dumps(metadata, sort_keys=True))

    with pytest.raises(ValueError, match="shape"):
        load_demo_checkpoint(written.path, model_registry={"sage": TinyModel})


def test_checkpoint_rejects_incompatible_run_parameter(tmp_path):
    written = write_demo_checkpoint(**_checkpoint_kwargs(tmp_path))

    with pytest.raises(ValueError, match="epochs"):
        load_demo_checkpoint(
            written.path,
            model_registry={"sage": TinyModel},
            expected={"epochs": 30},
        )


def test_checkpoint_publication_is_atomic_and_leaves_no_staging_tree(tmp_path):
    kwargs = _checkpoint_kwargs(tmp_path)
    written = write_demo_checkpoint(**kwargs)

    assert written.path.is_dir()
    assert {path.name for path in written.path.iterdir()} == {
        "metadata.json", "models", "scores.npz"
    }
    assert not list((tmp_path / "checkpoints").glob(".*.tmp-*"))


def test_existing_checkpoint_is_fully_verified_before_reuse(tmp_path):
    kwargs = _checkpoint_kwargs(tmp_path)
    written = write_demo_checkpoint(**kwargs)
    scores = written.path / "scores.npz"
    scores.write_bytes(scores.read_bytes() + b"corrupt")

    with pytest.raises(ValueError, match="SHA-256"):
        write_demo_checkpoint(**kwargs)


def test_checkpoint_rejects_model_tensor_dtype_mismatch_before_state_load(tmp_path):
    written = write_demo_checkpoint(**_checkpoint_kwargs(tmp_path))
    model_path = written.path / "models" / "seed_0.pt"
    state = torch.load(model_path, map_location="cpu", weights_only=True)
    tensor_name = next(name for name, value in state.items() if value.is_floating_point())
    state[tensor_name] = state[tensor_name].to(torch.float64)
    torch.save(state, model_path)
    metadata_path = written.path / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    import hashlib
    metadata["model"]["files"]["0"]["sha256"] = hashlib.sha256(
        model_path.read_bytes()
    ).hexdigest()
    metadata_path.write_text(json.dumps(metadata, sort_keys=True))

    with pytest.raises(ValueError, match="tensor dtype"):
        load_demo_checkpoint(written.path, model_registry={"sage": TinyModel})


@pytest.mark.parametrize("seeds", [[], [0, 0]])
def test_checkpoint_loader_rejects_empty_or_duplicate_seed_metadata(tmp_path, seeds):
    written = write_demo_checkpoint(**_checkpoint_kwargs(tmp_path))
    metadata_path = written.path / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["run"]["seeds"] = seeds
    metadata_path.write_text(json.dumps(metadata, sort_keys=True))

    with pytest.raises(ValueError, match="nonempty and unique"):
        load_demo_checkpoint(written.path, model_registry={"sage": TinyModel})
