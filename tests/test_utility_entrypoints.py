"""Behavioral contracts for packaged utility entry points."""

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.dashboard import build_dashboard


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def _run_python(args, *, cwd=ROOT):
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    return subprocess.run(
        [PYTHON, *args],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
    )


def test_validate_corpus_import_is_silent_and_argument_free():
    result = _run_python(["-c", "import scripts.data.validate_corpus"])

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_validate_corpus_main_resets_state_between_successful_calls(monkeypatch, tmp_path):
    from scripts.data import validate_corpus

    calls = []

    def fake_run_validation():
        calls.append(
            (
                validate_corpus.DIR,
                id(validate_corpus.FAIL),
                id(validate_corpus.WARN),
                id(validate_corpus.INFO),
                list(validate_corpus.FAIL),
                list(validate_corpus.WARN),
                list(validate_corpus.INFO),
            )
        )
        validate_corpus.FAIL.append("sentinel")
        validate_corpus.WARN.append("sentinel")
        validate_corpus.INFO.append("sentinel")
        return 0

    monkeypatch.setattr(validate_corpus, "_run_validation", fake_run_validation)
    first = tmp_path / "first-corpus"
    second = tmp_path / "second-corpus"

    assert validate_corpus.main([str(first)]) == 0
    assert validate_corpus.main([str(second)]) == 0

    assert [call[0] for call in calls] == [first, second]
    assert calls[0][1:4] != calls[1][1:4]
    assert calls[0][4:] == ([], [], [])
    assert calls[1][4:] == ([], [], [])


def test_direct_build_dashboard_script_reaches_usage_handling():
    result = _run_python(["scripts/dashboard/build_dashboard.py"])

    assert result.returncode == 1
    assert "usage:" in result.stdout
    assert "ModuleNotFoundError" not in result.stderr


def test_direct_build_v9_loading_bootstraps_from_outside_repo(tmp_path):
    script = ROOT / "scripts/dashboard/build_v9_dashboard.py"
    code = (
        "import runpy; "
        f"module = runpy.run_path({str(script)!r}, run_name='direct_probe'); "
        "assert module['V9_CORPUS_NAME'] == 'synthetic_cbp_graph_corpus_v9'; "
        "print('DIRECT_BOOTSTRAP_OK')"
    )
    result = _run_python(["-c", code], cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "DIRECT_BOOTSTRAP_OK"


def test_render_html_reads_template_from_supplied_corpus(tmp_path):
    template = """<html><head><title>old</title><style></style></head><body>
<h1>old</h1><script>
const DATA = {"old":true};
(async function(){
const Tabs={people:{rendered:false,render(){}},seizures:{rendered:false,render(){}}};
</script></body></html>
"""
    (tmp_path / "dashboard_standalone.html").write_text(template)

    rendered = build_dashboard.render_html(
        {"marker": "supplied-data"}, "synthetic_test", tmp_path
    )

    assert "supplied-data" in rendered
    assert '"old":true' not in rendered
    assert "CBP Graph Corpus Explorer — SYNTHETIC_TEST" in rendered


def test_optional_diagnostics_embed_from_supplied_repo_root(tmp_path):
    diagnostics = tmp_path / "gnn" / "diagnostics"
    diagnostics.mkdir(parents=True)
    payloads = {
        "model_flagged_v8.json": {"rows": [{"id": "v8"}]},
        "detection_arms_v8.json": {"arms": [{"id": "arm"}]},
        "demo_comparison_v9.json": {"overall": {"hybrid": {"found": 1}}},
    }
    for filename, payload in payloads.items():
        (diagnostics / filename).write_text(json.dumps(payload))

    v8_data = build_dashboard._embed_optional_diagnostics(
        {}, "synthetic_cbp_graph_corpus_v8", tmp_path
    )
    v9_data = build_dashboard._embed_optional_diagnostics(
        {}, "synthetic_cbp_graph_corpus_v9", tmp_path
    )

    assert v8_data["modelFlagged"] == payloads["model_flagged_v8.json"]
    assert v8_data["detectionArms"] == payloads["detection_arms_v8.json"]
    assert v9_data["v9Demo"] == payloads["demo_comparison_v9.json"]


def test_optional_diagnostics_missing_files_preserve_fallback_behavior(tmp_path):
    assert build_dashboard._embed_optional_diagnostics(
        {}, "synthetic_cbp_graph_corpus_v9", tmp_path
    ) == {}


def test_importing_build_dashboard_does_not_change_global_random_state():
    code = """
import random
random.seed(918273)
before = random.getstate()
import scripts.dashboard.build_dashboard
assert random.getstate() == before
print('RNG_STATE_PRESERVED')
"""
    result = _run_python(["-c", code])

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "RNG_STATE_PRESERVED"
