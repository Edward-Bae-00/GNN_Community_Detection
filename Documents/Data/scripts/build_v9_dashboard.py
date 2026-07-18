#!/usr/bin/env python3
"""Build a V9-only dashboard from the V9 standalone shell.

Run after `build_dashboard.py Documents/Data/synthetic_cbp_graph_corpus_v9`
has produced `dashboard_data.json`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import csv
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path


HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(DATA_DIR))
V9_CORPUS = os.path.join(DATA_DIR, "synthetic_cbp_graph_corpus_v9")
V9_DATA = os.path.join(V9_CORPUS, "dashboard_data.json")
V9_DEMO = os.path.join(REPO_ROOT, "gnn", "diagnostics", "demo_comparison_v9.json")
V9_RECOVERY_EXPLANATIONS = os.path.join(
    REPO_ROOT,
    "gnn",
    "diagnostics",
    "hybrid_recovery_explanations_v9.json",
)
OUT_DIR = os.path.join(DATA_DIR, "v9_dashboard")


def p(*args):
    print(*args, flush=True)


def _normalize_v9_template(html: str) -> str:
    """Remove stale V7 renderers and duplicate Explorer CSS from the template."""
    html = re.sub(
        r"(?ms)^[ \t]*entityResolution:\{rendered:false,render\(\)\{.*?^\}\},[ \t]*\n",
        "",
        html,
    )

    style_start = html.find("<style")
    style_end = html.find("</style>", style_start)
    marker = "/* ---- Community Explorer ---- */"
    if style_start < 0 or style_end < 0:
        return html

    style = html[style_start:style_end]
    markers = list(re.finditer(re.escape(marker), style))
    if len(markers) > 1:
        style = style[:markers[0].start()] + style[markers[-1].start():]
        html = html[:style_start] + style + html[style_end:]
    return html


def _daily_crossing_series(corpus_dir):
    """Return actual crossing-event volume for each V9 test-window day."""
    split_path = os.path.join(corpus_dir, "train_valid_test_splits.csv")
    events_path = os.path.join(corpus_dir, "crossing_events.csv")
    test_ids = set()
    with open(split_path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("split") == "test":
                test_ids.add(row.get("entity_id"))

    counts = Counter()
    with open(events_path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("event_id") not in test_ids:
                continue
            timestamp = row.get("event_timestamp_utc", "")
            if not timestamp:
                continue
            try:
                day = datetime.fromisoformat(
                    timestamp.replace("Z", "+00:00")
                ).date().isoformat()
            except ValueError:
                day = timestamp[:10]
            counts[day] += 1
    return [
        {"date": day, "crossings": counts[day]}
        for day in sorted(counts)
    ]


def _is_compatible_v9_demo(demo):
    """Return whether demo satisfies the fields dereferenced by V9 Results."""
    if not isinstance(demo, dict):
        return False
    for section in ("overall", "overall_daily", "stratified"):
        value = demo.get(section)
        if not isinstance(value, dict):
            return False
        for arm in ("baseline", "hybrid"):
            if not isinstance(value.get(arm), dict):
                return False
    for arm in ("baseline", "hybrid"):
        if not isinstance(demo["stratified"][arm].get("observable"), dict):
            return False
    return (
        isinstance(demo.get("stratum_hidden"), dict)
        and "hidden_total" in demo
    )


def _load_recovery_artifact(path, output_dir=None):
    if not os.path.exists(path):
        p(f"[v9-dashboard] WARNING: {path} not found; case evidence unavailable.")
        return None
    try:
        with open(path) as handle:
            artifact = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        p(f"[v9-dashboard] WARNING: invalid recovery artifact: {error}")
        return None
    if not isinstance(artifact, dict):
        p("[v9-dashboard] WARNING: unsupported recovery artifact schema.")
        return None
    if artifact.get("schema_version") == "2.0":
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        from v9_recovery_sidecars import publish_prepackaged_manifest

        try:
            dashboard_output = OUT_DIR if output_dir is None else output_dir
            if (
                isinstance(artifact.get("case_index"), dict)
                and isinstance(artifact.get("community_index"), dict)
                and isinstance(artifact.get("bundle_id"), str)
            ):
                return publish_prepackaged_manifest(
                    artifact,
                    path,
                    os.path.join(dashboard_output, "recovery"),
                )
            raise ValueError(
                "schema-2 recovery requires a prepackaged producer bundle"
            )
        except ValueError as error:
            raise ValueError(
                f"invalid schema-2 recovery artifact: {error}"
            ) from error
    if artifact.get("schema_version") != "1.0":
        p("[v9-dashboard] WARNING: unsupported recovery artifact schema.")
        return None
    return artifact


def _load_v9_data(output_dir=None) -> dict:
    if not os.path.exists(V9_DATA):
        p(f"[v9-dashboard] ERROR: {V9_DATA} not found.")
        p("[v9-dashboard] Run: .venv/bin/python Documents/Data/scripts/build_dashboard.py "
          "Documents/Data/synthetic_cbp_graph_corpus_v9")
        sys.exit(1)
    with open(V9_DATA) as f:
        data = json.load(f)
    data["v9DailyCrossings"] = _daily_crossing_series(V9_CORPUS)
    candidate_demo = data.get("v9Demo")
    if os.path.exists(V9_DEMO):
        with open(V9_DEMO) as f:
            candidate_demo = json.load(f)
    else:
        p(f"[v9-dashboard] WARNING: {V9_DEMO} not found; V9 Results tab will be sparse.")
    if _is_compatible_v9_demo(candidate_demo):
        data["v9Demo"] = candidate_demo
    else:
        data.pop("v9Demo", None)
        if candidate_demo is not None:
            p("[v9-dashboard] WARNING: discarded incompatible V9 demo payload.")

    data.pop("v9RecoveryExplainer", None)
    recovery_artifact = _load_recovery_artifact(
        V9_RECOVERY_EXPLANATIONS, output_dir=output_dir
    )
    if recovery_artifact is not None:
        data["v9RecoveryExplainer"] = recovery_artifact

    return data


def _embed_dashboard_data(html: str, data: dict) -> str:
    """Replace the template data blob with a self-contained V9 data blob."""
    data_start = html.find("const DATA = ")
    iife_start = html.find("\n(async function(){", data_start)
    if data_start < 0 or iife_start < 0:
        raise ValueError("dashboard template is missing its DATA/IIFE boundary")
    blob = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    # Prevent a data string from prematurely closing the surrounding script.
    blob = blob.replace("<", "\\u003c")
    return (
        html[:data_start]
        + "\nlet DATA = " + blob + ";\nlet D = DATA;\n"
        + html[iife_start:]
    )


def _make_d3_optional(html: str) -> str:
    """Keep V9 tab bootstrapping alive when the optional D3 CDN is unavailable."""
    old = """const tip=d3.select('body').append('div').attr('class','tooltip');
function showTip(e,html){
  tip.html(html).style('opacity',1);
  const b=tip.node().getBoundingClientRect();
  let x=e.clientX+14,y=e.clientY-12;
  if(x+b.width>window.innerWidth-10)x=e.clientX-b.width-14;
  if(y+b.height>window.innerHeight-10)y=e.clientY-b.height-10;
  if(y<6)y=6;
  tip.style('left',x+'px').style('top',y+'px');
}
function hideTip(){tip.style('opacity',0)}"""
    new = """const tip=document.createElement('div');
tip.className='tooltip';
document.body.appendChild(tip);
function showTip(e,html){
  tip.innerHTML=html;
  tip.style.opacity='1';
  const b=tip.getBoundingClientRect();
  let x=e.clientX+14,y=e.clientY-12;
  if(x+b.width>window.innerWidth-10)x=e.clientX-b.width-14;
  if(y+b.height>window.innerHeight-10)y=e.clientY-b.height-10;
  if(y<6)y=6;
  tip.style.left=x+'px';
  tip.style.top=y+'px';
}
function hideTip(){tip.style.opacity='0'}"""
    if old not in html:
        raise ValueError("dashboard template is missing its tooltip bootstrap")
    return html.replace(old, new, 1)


def _inject_dashboard_tab_scripts(html, helper_js, renderer_js):
    """Place helpers before ``Tabs`` and renderers inside its object literal."""
    tabs_marker = "const Tabs={"
    explorer_marker = "explorer:{rendered:false,render(){"
    if tabs_marker not in html or explorer_marker not in html:
        raise ValueError("dashboard template is missing its tab registry markers")
    html = html.replace(tabs_marker, helper_js + "\n" + tabs_marker, 1)
    return html.replace(explorer_marker, renderer_js + explorer_marker, 1)


def _inject_recovery_assets(html, css, js):
    """Idempotently place recovery explorer behavior and styles in the shell."""
    if not isinstance(css, str) or not css or not isinstance(js, str) or not js:
        raise ValueError("recovery assets must be non-empty strings")
    if html.count(css) > 1 or html.count(js) > 1:
        raise ValueError("dashboard contains duplicate recovery assets")

    style_start = html.find("<style")
    style_end = html.find("</style>", style_start)
    if style_start < 0 or style_end < 0:
        raise ValueError("dashboard template is missing its style boundary")
    css_index = html.find(css)
    if css_index >= 0 and not (
        style_start < css_index and css_index + len(css) <= style_end
    ):
        raise ValueError("recovery asset CSS is outside the style boundary")

    tabs_marker = "const Tabs={"
    tabs_index = html.find(tabs_marker)
    if tabs_index < 0:
        raise ValueError("dashboard template is missing its tab registry marker")
    js_index = html.find(js)
    if js_index >= tabs_index:
        raise ValueError("recovery asset JavaScript must precede the tab registry")

    if css not in html:
        html = html.replace("</style>", css + "\n</style>", 1)
    if js not in html:
        html = html.replace(tabs_marker, js + "\n" + tabs_marker, 1)
    return html


def _validate_recovery_explorer_mount(html):
    """Fail closed if the local artifact explorer mount is missing or ambiguous."""
    exact_once = (
        'href="#v9-case-evidence"',
        'id="v9-case-evidence"',
        "DATA.v9RecoveryExplainer",
    )
    if any(html.count(token) != 1 for token in exact_once):
        raise ValueError("dashboard recovery explorer mount is invalid")
    return html


def _publish_staged_dashboard(staged_dir, destination_dir):
    """Swap a complete staged dashboard into place, restoring the prior tree on failure."""
    staged = Path(staged_dir)
    destination = Path(destination_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.backup-", dir=destination.parent
    ))
    backup.rmdir()
    prior_moved = False
    try:
        if destination.exists():
            os.replace(destination, backup)
            prior_moved = True
        os.replace(staged, destination)
    except Exception:
        if prior_moved and not destination.exists() and backup.exists():
            os.replace(backup, destination)
        raise
    if prior_moved:
        shutil.rmtree(backup)


def _build_staged_dashboard(staged_output, destination, tmpl_path):
    data = _load_v9_data(output_dir=staged_output)
    out_data = staged_output / "data_v9.json"
    with open(out_data, "w") as f:
        json.dump(data, f, separators=(",", ":"))

    with open(tmpl_path) as f:
        html = f.read()
    html = _normalize_v9_template(html)

    # 1. Embed the data while retaining data_v9.json for inspection. Schema-2
    # sidecars still require HTTP because browsers block file:// fetches.
    html = _embed_dashboard_data(html, data)

    # 2. Replace the fetch block in IIFE
    iife_cleanup = re.search(
        r'\(async function\(\)\{.*?if\(!D\)\s*return;\s*\n',
        html, re.DOTALL
    )
    if iife_cleanup:
        html = html[:iife_cleanup.start()] + "(async function(){\n" + html[iife_cleanup.end():]
    else:
        # Fallback
        old_iife_body = re.search(
            r'\(async function\(\)\{.*?const D = DATA \|\| await fetch.*?\n',
            html, re.DOTALL
        )
        if old_iife_body:
            html = html.replace(old_iife_body.group(0), "(async function(){\n")

    # 3. Inject the V9 Results tab
    sys.path.insert(0, HERE)
    from v9_dashboard_ui import (
        V9_RESULTS_CSS,
        V9_RESULTS_JS,
        V9_RESULTS_NAV_BTN,
        V9_RESULTS_SECTION,
    )
    from v9_recovery_explainer_ui import (
        V9_RECOVERY_EXPLAINER_CSS,
        V9_RECOVERY_EXPLAINER_JS,
    )

    html = html.replace(
        '    <!-- V9_NAV_TABS -->\n',
        '    ' + V9_RESULTS_NAV_BTN,
    )
    html = html.replace(
        '  <!-- V9_TAB_SECTIONS -->\n',
        V9_RESULTS_SECTION,
    )
    html = _inject_recovery_assets(
        html,
        V9_RECOVERY_EXPLAINER_CSS,
        V9_RECOVERY_EXPLAINER_JS,
    )
    html = _inject_dashboard_tab_scripts(html, "", V9_RESULTS_JS)
    html = _validate_recovery_explorer_mount(html)
    html = html.replace("</style>", V9_RESULTS_CSS + "\n</style>", 1)
    html = _make_d3_optional(html)

    # 4. Remove Entity Resolution if present
    html = html.replace('  <button data-tab="entityResolution">Entity Resolution</button>\n', '')
    html = html.replace('  <section id="tab-entityResolution" class="tab-content"></section>\n', '')

    # 5. Update titles
    html = re.sub(r"<title>[^<]*</title>", "<title>CBP Graph Corpus Explorer - V9</title>", html, count=1)
    html = re.sub(r"<h1>[^<]*</h1>", "<h1>CBP Graph Corpus Explorer &middot; V9</h1>", html, count=1)

    # 5. DATA is already embedded above; no local fetch is needed.
    out_html = staged_output / "index.html"
    with open(out_html, "w") as f:
        f.write(html)
    _publish_staged_dashboard(staged_output, destination)
    final_data = destination / "data_v9.json"
    final_html = destination / "index.html"
    p(f"[v9-dashboard] wrote {final_data} ({os.path.getsize(final_data)/1e6:.2f} MB)")
    p(f"[v9-dashboard] wrote {final_html} ({os.path.getsize(final_html)/1e6:.2f} MB)")
    p("[v9-dashboard] run: python -m http.server 8000 --directory Documents/Data/v9_dashboard")
    p("[v9-dashboard] then open http://localhost:8000/index.html")


def main():
    tmpl_path = os.path.join(V9_CORPUS, "dashboard_standalone.html")
    if not os.path.exists(tmpl_path):
        p(f"[v9-dashboard] ERROR: {tmpl_path} not found.")
        sys.exit(1)

    destination = Path(OUT_DIR)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged_output = Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.stage-", dir=destination.parent
    ))
    try:
        _build_staged_dashboard(staged_output, destination, tmpl_path)
    except Exception:
        if staged_output.exists():
            shutil.rmtree(staged_output)
        raise


if __name__ == "__main__":
    main()
