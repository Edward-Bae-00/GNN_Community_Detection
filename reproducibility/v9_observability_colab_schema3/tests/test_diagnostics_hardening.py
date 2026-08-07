import json
import ast
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

try:
    from gnn import explanation_narrative as narrative
except ModuleNotFoundError as exc:
    # Keep this regression module runnable with only stdlib + the project's
    # light data dependencies; production environments import the real module.
    if exc.name not in {"networkx", "torch", "torch_geometric"}:
        raise
    sage_stub = types.ModuleType("gnn.sage_explainer")
    sage_stub.validate_explanation_payload = lambda payload: None
    # observability_artifact binds json_safe at import time and calls it from
    # _detached_json_object, so it must stay callable. Whichever test module
    # installs this stub first wins for the whole session, so the stub has to
    # be usable by all of them, not just this one.
    sage_stub.json_safe = lambda value: value
    for name in (
        "CommunityScope",
        "build_flow_stages", "build_structural_community_control", "compose_case_explanation",
        "explainability_eligibility",
    ):
        setattr(sage_stub, name, object())
    # The explainer eligibility ceiling is part of the staging fingerprint, so
    # it gets serialized rather than merely passed around: it has to be a real
    # integer here, not an opaque sentinel.
    sage_stub.MAX_EXPLAINER_INPUT_NODES = 128
    sage_stub.MAX_EXPLAINER_INPUT_EDGES = 256
    # Display bounds mirror production by deriving from the explainer ceiling
    # rather than being set independently.
    sage_stub.MAX_LOCAL_EXPLANATION_NODES = sage_stub.MAX_EXPLAINER_INPUT_NODES
    sage_stub.MAX_LOCAL_EXPLANATION_EDGES = sage_stub.MAX_EXPLAINER_INPUT_EDGES
    # Attribution-shaping truncation caps, serialized into the fingerprint.
    sage_stub.MAX_LOCAL_SOURCE_ROWS_PER_EDGE = 16
    sage_stub.MAX_NODE_ATTRIBUTION_SOURCE_ROWS = 16
    sage_stub.MAX_NODE_FEATURE_MASK_STATS = 512
    sys.modules["gnn.sage_explainer"] = sage_stub
    from gnn import explanation_narrative as narrative
try:
    import scipy  # noqa: F401
except ModuleNotFoundError as exc:
    if exc.name != "scipy":
        raise
    scipy_stub = types.ModuleType("scipy")
    scipy_stats_stub = types.ModuleType("scipy.stats")
    scipy_stats_stub.rankdata = lambda values, *args, **kwargs: values
    scipy_stub.stats = scipy_stats_stub
    sys.modules["scipy"] = scipy_stub
    sys.modules["scipy.stats"] = scipy_stats_stub
from gnn import observability_artifact as artifact
from gnn.recovery_bundle import RecoveryBundleWriter


class OllamaDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        narrative._PREFLIGHT_CACHE.clear()
        narrative._CONTRACT_PREFLIGHT_CACHE.clear()

    def test_list_nonzero_includes_bounded_diagnostics(self):
        stderr = "stderr-start " + ("x" * 2000)

        def runner(*args, **kwargs):
            return subprocess.CompletedProcess(
                args[0], 17, stdout="stdout detail", stderr=stderr
            )

        with self.assertRaisesRegex(RuntimeError, r"return.?code.?17") as ctx:
            narrative.preflight_local_model(runner=runner)
        message = str(ctx.exception)
        self.assertIn("stderr-start", message)
        self.assertNotIn("x" * 1000, message)

    def test_list_timeout_includes_bytes_safe_partial_output(self):
        def runner(*args, **kwargs):
            raise subprocess.TimeoutExpired(
                args[0], kwargs["timeout"], output=b"partial stdout", stderr=b"partial stderr"
            )

        with self.assertRaises(RuntimeError) as ctx:
            narrative.preflight_local_model(runner=runner)
        message = str(ctx.exception)
        self.assertIn("partial stdout", message)
        self.assertIn("partial stderr", message)
        self.assertNotIn("b'partial", message)

    def test_run_nonzero_includes_bounded_diagnostics(self):
        stderr = "run stderr marker " + ("y" * 2000)
        completed = subprocess.CompletedProcess(
            ["ollama", "run"], 23, stdout="run output", stderr=stderr
        )
        with self.assertRaisesRegex(RuntimeError, r"return.?code.?23") as ctx:
            narrative._run_local_gemma(
                "prompt", runner=lambda *a, **k: completed, timeout_seconds=180, preflight=False
            )
        self.assertIn("run stderr marker", str(ctx.exception))
        self.assertNotIn("y" * 1000, str(ctx.exception))

    def test_run_timeout_includes_bytes_safe_partial_output(self):
        def runner(command, **kwargs):
            raise subprocess.TimeoutExpired(
                command, kwargs["timeout"], output=b"run partial stdout", stderr=b"run partial stderr"
            )

        with self.assertRaises(RuntimeError) as ctx:
            narrative._run_local_gemma(
                "prompt", runner=runner, timeout_seconds=180, preflight=False
            )
        message = str(ctx.exception)
        self.assertIn("run partial stdout", message)
        self.assertIn("run partial stderr", message)
        self.assertNotIn("b'run partial", message)

    def test_contract_final_error_retains_last_underlying_error(self):
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            if command[:2] == ["ollama", "list"]:
                return subprocess.CompletedProcess(command, 0, stdout="NAME\ngemma4:12b\n", stderr="")
            return subprocess.CompletedProcess(command, 29, stdout="run out", stderr="contract stderr")

        with self.assertRaisesRegex(RuntimeError, "contract stderr"):
            narrative.preflight_narrative_contract(runner=runner)
        self.assertEqual(sum(command[:2] == ["ollama", "run"] for command in calls), 4)

    def test_generate_final_error_retains_last_underlying_error(self):
        packet = narrative._selector_preflight_packet()

        def runner(command, **kwargs):
            if command[:2] == ["ollama", "list"]:
                return subprocess.CompletedProcess(command, 0, stdout="NAME\ngemma4:12b\n", stderr="")
            return subprocess.CompletedProcess(command, 31, stdout="run out", stderr="generation stderr")

        with self.assertRaisesRegex(RuntimeError, r"after 1 attempts:.*generation stderr"):
            narrative.generate_narrative(packet, runner=runner, max_retries=0)

    def test_nested_wrappers_preserve_stderr_when_stdout_is_long(self):
        long_stdout = "stdout-start stderr=DECOY " + ("x" * 2000)
        stderr_marker = "STDERR-MUST-SURVIVE"

        def runner(command, **kwargs):
            if command[:2] == ["ollama", "list"]:
                return subprocess.CompletedProcess(
                    command, 0, stdout="NAME\ngemma4:12b\n", stderr=""
                )
            return subprocess.CompletedProcess(
                command, 9, stdout=long_stdout, stderr=stderr_marker
            )

        with self.assertRaises(RuntimeError) as contract_error:
            narrative.preflight_narrative_contract(runner=runner)
        self.assertIn("local Gemma selector-generation contract failed:", str(contract_error.exception))
        self.assertIn(stderr_marker, str(contract_error.exception))
        self.assertLessEqual(len(str(contract_error.exception)), 1200)

        with self.assertRaises(RuntimeError) as generation_error:
            narrative.generate_narrative(
                narrative._selector_preflight_packet(), runner=runner, max_retries=0
            )
        self.assertIn("local narrative failed after", str(generation_error.exception))
        self.assertIn(stderr_marker, str(generation_error.exception))
        self.assertLessEqual(len(str(generation_error.exception)), 1200)

    def test_artifact_last_error_preserves_stderr_marker(self):
        case = mock.Mock()
        case.person_id = "P-1"
        case.anchor.event_id = "E-1"
        case.anchor.scoring_day = "2025-01-01T00:00:00Z"
        case.decision_trace_jsonable.return_value = {"trace": 1}
        explanation = {
            "case_id": "case:P-1",
            "person_id": "P-1",
            "event_id": "E-1",
            "decision_trace": {"trace": 1},
            "scoring_day": "2025-01-01T00:00:00Z",
        }
        stats = {
            "narrative_attempted": 0,
            "narrative_generated": 0,
            "narrative_fallback": 0,
            "narrative_failed": 0,
        }
        long_stdout = "stdout-start stderr=DECOY " + ("x" * 2000)
        stderr_marker = "STDERR-MUST-SURVIVE"

        with mock.patch.object(artifact, "explain_case", return_value=explanation), mock.patch.object(
            artifact, "_validate_complete_explanation"
        ), mock.patch.object(artifact, "build_fact_packet", return_value={"packet": 1}), mock.patch.object(
            artifact, "_detached_json_object", side_effect=lambda value, **kwargs: value
        ), mock.patch.object(artifact, "_validate_grounded_narrative"), mock.patch.object(
            artifact, "_as_utc_timestamp", return_value=case.anchor.scoring_day
        ), mock.patch.object(
            artifact,
            "render_template",
            return_value={
                "source": "deterministic_template",
                "model": None,
                "prompt_version": narrative.PROMPT_VERSION,
                "summary": "summary",
                "summary_source_refs": [],
                "claims": [],
                "validated": True,
            },
        ):
            artifact._explain_case_with_narrative(
                case,
                object(),
                lambda packet: (_ for _ in ()).throw(
                    RuntimeError(f"ollama run failed; stdout={long_stdout!r}; stderr={stderr_marker!r}")
                ),
                narrative_stats=stats,
            )

        self.assertIn(stderr_marker, stats["narrative_last_error"])
        self.assertLessEqual(len(stats["narrative_last_error"]), 1200)


class NarrativeStatsTests(unittest.TestCase):
    def test_per_case_generation_error_is_preserved_before_template_fallback(self):
        case = mock.Mock()
        case.person_id = "P-1"
        case.anchor.event_id = "E-1"
        case.anchor.scoring_day = "2025-01-01T00:00:00Z"
        case.decision_trace_jsonable.return_value = {"trace": 1}
        explanation = {
            "case_id": "case:P-1",
            "person_id": "P-1",
            "event_id": "E-1",
            "decision_trace": {"trace": 1},
            "scoring_day": "2025-01-01T00:00:00Z",
        }
        stats = {
            "narrative_attempted": 0,
            "narrative_generated": 0,
            "narrative_fallback": 0,
            "narrative_failed": 0,
        }

        with mock.patch.object(artifact, "explain_case", return_value=explanation), mock.patch.object(
            artifact, "_validate_complete_explanation"
        ), mock.patch.object(artifact, "build_fact_packet", return_value={"packet": 1}), mock.patch.object(
            artifact, "_detached_json_object", side_effect=lambda value, **kwargs: value
        ), mock.patch.object(
            artifact, "_validate_grounded_narrative"
        ), mock.patch.object(artifact, "_as_utc_timestamp", return_value=case.anchor.scoring_day), mock.patch.object(
            artifact, "render_template", return_value={
                "source": "deterministic_template",
                "model": None,
                "prompt_version": narrative.PROMPT_VERSION,
                "summary": "summary",
                "summary_source_refs": [],
                "claims": [],
                "validated": True,
            }
        ):
            result = artifact._explain_case_with_narrative(
                case,
                object(),
                lambda packet: (_ for _ in ()).throw(RuntimeError("actual generation detail")),
                narrative_stats=stats,
            )

        self.assertEqual(result["llm_narrative"]["source"], "deterministic_template")
        self.assertIn("actual generation detail", stats["narrative_last_error"])
        self.assertEqual(stats["narrative_fallback"], 1)


class NotebookStructureTests(unittest.TestCase):
    def test_notebook_uses_bounded_cli_probe_and_unbuffered_producer(self):
        notebook = json.loads(Path("v9_schema3_observability.ipynb").read_text())
        cell_list = notebook["cells"]
        cells = {cell.get("id"): "".join(cell.get("source", [])) for cell in cell_list}
        smoke = cells["ollama-smoke"]
        diagnostic = cells["one-case-diagnostic"]
        producer = cells["run-producer"]
        cell_ids = [cell.get("id") for cell in cell_list]
        self.assertLess(cell_ids.index("ollama-smoke"), cell_ids.index("one-case-diagnostic"))
        self.assertLess(cell_ids.index("one-case-diagnostic"), cell_ids.index("run-producer"))
        self.assertIn('    "ollama",\n    "run",\n    MODEL_TAG', smoke)
        tree = ast.parse(smoke, filename="ollama-smoke")
        command_assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "_smoke_command" for target in node.targets)
        )
        self.assertEqual(
            [
                "gemma4:12b" if isinstance(item, ast.Name) and item.id == "MODEL_TAG" else ast.literal_eval(item)
                for item in command_assignment.value.elts
            ],
            [
                "ollama", "run", "gemma4:12b", "--format", "json", "--think=false",
                "--keepalive", "10m", "--nowordwrap",
            ],
        )
        self.assertEqual(smoke.count("subprocess.run("), 1)
        self.assertIn("timeout=180", smoke)
        self.assertIn("TimeoutExpired", smoke)
        self.assertIn("capture_output=True", smoke)
        self.assertIn("_smoke_excerpt", smoke)
        self.assertIn("errors=\"replace\"", smoke)
        self.assertNotIn("urllib.request", smoke)
        self.assertIn("if not (_smoke_result.stdout or '').strip():", smoke)
        self.assertIn("empty stdout", smoke.lower())
        self.assertIn("selector-contract validation is outside this probe", smoke)
        self.assertIn("RUN_ONE_CASE_DIAGNOSTIC = False", diagnostic)
        self.assertIn("/content/v9_schema3_diag3", diagnostic)
        self.assertIn("/content/v9_schema3_diag3.log", diagnostic)
        self.assertIn("--hybrid-detail-limit", diagnostic)
        self.assertIn("'1'", diagnostic)
        self.assertIn("--baseline-control-limit", diagnostic)
        self.assertIn("'0'", diagnostic)
        self.assertIn("'--allow-shortfall'", diagnostic)
        self.assertIn("stderr=subprocess.STDOUT", diagnostic)
        self.assertIn("'python3',\n        '-u',", diagnostic)
        self.assertIn("for line in process.stdout:", diagnostic)
        self.assertIn("if return_code != 0:", diagnostic)
        self.assertIn("raise RuntimeError(", diagnostic)
        self.assertIn("sys.executable,\n    '-u',", producer)


class CompactManifestDiagnosticsTests(unittest.TestCase):
    def test_schema3_bundle_threads_narrative_diagnostics_to_finalizer(self):
        captured = {}

        class CapturingWriter:
            def __init__(self, *args, **kwargs):
                pass

            def finalize_schema3(self, **kwargs):
                captured.update(kwargs)
                return {"generation_diagnostics": kwargs["generation_diagnostics"]}

        artifact_payload = {
            "selection": {
                "selected_ids": {"hybrid_only": [], "baseline_only": []},
                "hybrid_structural_fallback_ids": [],
            },
            "cohorts": {
                "hybrid_only": [],
                "baseline_only": [],
                "recovered_by_both": [],
            },
            "policy": {},
            "coverage": {},
            "summary": {},
            "run_fingerprint": {},
            "generation_diagnostics": {
                "narrative": {
                    "narrative_preflight_error": "preflight stderr",
                    "narrative_last_error": "generation stderr",
                }
            },
        }
        # The bundle binds the engine's rank reference before fingerprinting it
        # (see tests/test_schema3_rank_reference_ordering.py). That is pure
        # setup for this test, so it is stubbed out to keep the assertions on
        # diagnostics threading alone.
        with mock.patch.object(artifact, "_validated_scope", return_value=(0, 1, 2)), mock.patch.object(
            artifact, "_resolve_schema3_limits", return_value=(1, 1)
        ), mock.patch.object(
            artifact, "_prepared_pool", return_value=(None, None)
        ), mock.patch.object(
            artifact, "build_rank_reference", return_value=None
        ), mock.patch.object(
            artifact, "_rank_row_bindings", return_value=()
        ), mock.patch.object(
            artifact, "_recovery_run_fingerprint", return_value={"policy": {}}
        ), mock.patch.object(
            artifact, "_build_schema3_artifact", return_value=artifact_payload
        ), mock.patch.object(
            artifact, "_detached_json_object", side_effect=lambda value, **kwargs: value
        ):
            artifact._build_schema3_bundle(
                pool=None,
                baseline_raw=None,
                seed0_gnn_raw=None,
                blend_weight=0.75,
                caught_times=None,
                gnn_arm="sage",
                surrounding_seeds=(0, 1, 2),
                explanation_engine=mock.Mock(),
                seed_level_unique_person_recovery=None,
                staging_root=Path("/tmp/staging"),
                final_root=Path("/tmp/final"),
                explanation_limit=None,
                hybrid_detail_limit=1,
                baseline_control_limit=1,
                inspections_per_day=5,
                narrative_builder=lambda packet: packet,
                corpus_identity="test",
                recovery_run_identity=None,
                instrumentation=None,
                narrative_preflight=None,
                writer_factory=CapturingWriter,
            )

        self.assertEqual(
            captured["generation_diagnostics"], artifact_payload["generation_diagnostics"]
        )

    def test_compact_manifest_carries_only_bounded_narrative_diagnostics(self):
        narrative_stats = {
            "narrative_preflight_failed": 1,
            "narrative_preflight_error": "RuntimeError: preflight stderr",
            "narrative_last_error": "RuntimeError: generation stderr",
            "unrelated_large_diagnostic": "x" * 10000,
        }
        with tempfile.TemporaryDirectory() as temporary:
            writer = RecoveryBundleWriter(
                Path(temporary) / "staging",
                Path(temporary) / "final",
                run_fingerprint={"fingerprint": "test"},
            )
            manifest = writer.finalize_schema3(
                selected_hybrid_case_ids=[],
                selected_baseline_case_ids=[],
                cohorts={
                    "hybrid_only": [],
                    "baseline_only": [],
                    "recovered_by_both": [],
                },
                policy={},
                coverage={},
                summary={},
                generation_diagnostics={"narrative": narrative_stats},
            )
            writer_without_diagnostics = RecoveryBundleWriter(
                Path(temporary) / "staging-without",
                Path(temporary) / "final-without",
                run_fingerprint={"fingerprint": "test"},
            )
            manifest_without_diagnostics = writer_without_diagnostics.finalize_schema3(
                selected_hybrid_case_ids=[],
                selected_baseline_case_ids=[],
                cohorts={
                    "hybrid_only": [],
                    "baseline_only": [],
                    "recovered_by_both": [],
                },
                policy={},
                coverage={},
                summary={},
            )

        diagnostics = manifest["generation_diagnostics"]
        self.assertEqual(
            diagnostics,
            {
                "narrative": {
                    "narrative_preflight_failed": 1,
                    "narrative_preflight_error": "RuntimeError: preflight stderr",
                    "narrative_last_error": "RuntimeError: generation stderr",
                }
            },
        )
        self.assertNotIn("unrelated_large_diagnostic", json.dumps(manifest))
        self.assertNotEqual(
            manifest["bundle_id"], manifest_without_diagnostics["bundle_id"]
        )

    def test_diagnostic_formatter_strictly_respects_limit(self):
        formatter = getattr(narrative, "bounded_diagnostic_text", None)
        self.assertIsNotNone(formatter)
        self.assertLessEqual(len(formatter("x" * 100, limit=10)), 10)

    def test_compact_manifest_omits_none_narrative_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            writer = RecoveryBundleWriter(
                Path(temporary) / "staging",
                Path(temporary) / "final",
                run_fingerprint={"fingerprint": "test"},
            )
            manifest = writer.finalize_schema3(
                selected_hybrid_case_ids=[],
                selected_baseline_case_ids=[],
                cohorts={
                    "hybrid_only": [],
                    "baseline_only": [],
                    "recovered_by_both": [],
                },
                policy={},
                coverage={},
                summary={},
                generation_diagnostics={
                    "narrative": {
                        "narrative_attempted": 1,
                        "narrative_generated": 1,
                        "narrative_fallback": 0,
                        "narrative_failed": 0,
                        "narrative_preflight_failed": 0,
                        "narrative_preflight_error": None,
                        "narrative_last_error": None,
                    }
                },
            )

        narrative_manifest = manifest["generation_diagnostics"]["narrative"]
        self.assertNotIn("narrative_preflight_error", narrative_manifest)
        self.assertNotIn("narrative_last_error", narrative_manifest)


class StageFailureReasonTests(unittest.TestCase):
    """A failed case must say why in the live stage stream.

    The artifact is written only after the whole run, and a schema-3 run is
    several hours long, so a ``case_published`` event that carries
    ``status: failed`` without a reason leaves an operator unable to diagnose
    a failing run until it has finished burning the session.
    """

    def test_healthy_case_reports_no_reason(self):
        self.assertIsNone(artifact._bounded_stage_failure_reason(None))

    def test_reason_is_preserved_and_bounded(self):
        self.assertEqual(
            artifact._bounded_stage_failure_reason("ValueError: boom"),
            "ValueError: boom",
        )
        bounded = artifact._bounded_stage_failure_reason("ValueError: " + "x" * 5000)
        self.assertLessEqual(len(bounded), narrative._DIAGNOSTIC_TEXT_LIMIT)

    def test_traceback_names_the_failing_line(self):
        def _inner():
            raise ValueError("boom")

        try:
            _inner()
        except ValueError as error:
            captured = artifact._bounded_stage_traceback(error)
        # The reason alone ("ValueError: boom") does not say where; the point of
        # keeping the traceback is that it does.
        self.assertIn("_inner", captured)
        self.assertIn("ValueError: boom", captured)

    def test_a_long_message_cannot_push_out_the_frames_or_the_type(self):
        # Several raises on this path interpolate whole ID lists into the
        # message. Bounding message and frames together let one such message
        # consume the entire budget, leaving neither a frame nor the exception
        # type -- which is exactly the information the reason string lacks.
        def _inner():
            raise ValueError("deep" + "!" * 20000)

        try:
            _inner()
        except ValueError as error:
            captured = artifact._bounded_stage_traceback(error)
        self.assertLessEqual(
            len(captured),
            artifact._STAGE_TRACEBACK_LIMIT + len("...<truncated>\n"),
        )
        self.assertIn("_inner", captured)
        self.assertIn("ValueError: deep", captured)

    def test_a_deep_stack_keeps_the_innermost_frames(self):
        source = "def f0():\n    raise ValueError('boom')\n"
        for index in range(1, 120):
            source += f"def f{index}():\n    f{index - 1}()\n"
        namespace = {}
        exec(compile(source, "<generated>", "exec"), namespace)

        try:
            namespace["f119"]()
        except ValueError as error:
            captured = artifact._bounded_stage_traceback(error)
        self.assertLessEqual(
            len(captured),
            artifact._STAGE_TRACEBACK_LIMIT + len("...<truncated>\n"),
        )
        self.assertTrue(captured.startswith("...<truncated>"))
        self.assertIn("ValueError: boom", captured)
        # The innermost frame names the failing statement, so it is the one
        # that must survive; the outermost frames are what get dropped.
        self.assertIn("in f0", captured)
        self.assertNotIn("in f119", captured)

    def test_healthy_case_reports_no_traceback(self):
        self.assertIsNone(artifact._bounded_stage_traceback(None))

    def test_every_case_published_event_carries_a_failure_reason(self):
        source = Path("gnn/observability_artifact.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        published_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "stage"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "case_published"
        ]
        self.assertTrue(published_calls)
        for call in published_calls:
            keywords = {keyword.arg for keyword in call.keywords}
            for field in ("failure_reason", "failure_traceback"):
                self.assertIn(
                    field,
                    keywords,
                    f"a case_published stage event must emit {field}, or a "
                    "failed case is only diagnosable from the final artifact "
                    f"-- written hours later (line {call.lineno})",
                )


if __name__ == "__main__":
    unittest.main()
