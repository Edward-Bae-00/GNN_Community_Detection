#!/usr/bin/env python3
"""Build a V9-only dashboard from the V9 standalone shell.

Run after `build_dashboard.py Documents/Data/synthetic_cbp_graph_corpus_v9`
has produced `dashboard_data.json`.
"""
from __future__ import annotations

import json
import os
import re
import sys
import csv
from collections import Counter
from datetime import datetime


HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(DATA_DIR))
V9_CORPUS = os.path.join(DATA_DIR, "synthetic_cbp_graph_corpus_v9")
V9_DATA = os.path.join(V9_CORPUS, "dashboard_data.json")
V9_DEMO = os.path.join(REPO_ROOT, "gnn", "diagnostics", "demo_comparison_v9.json")
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


def _load_v9_data() -> dict:
    if not os.path.exists(V9_DATA):
        p(f"[v9-dashboard] ERROR: {V9_DATA} not found.")
        p("[v9-dashboard] Run: .venv/bin/python Documents/Data/scripts/build_dashboard.py "
          "Documents/Data/synthetic_cbp_graph_corpus_v9")
        sys.exit(1)
    with open(V9_DATA) as f:
        data = json.load(f)
    data["v9DailyCrossings"] = _daily_crossing_series(V9_CORPUS)
    if os.path.exists(V9_DEMO):
        with open(V9_DEMO) as f:
            data["v9Demo"] = json.load(f)
    else:
        p(f"[v9-dashboard] WARNING: {V9_DEMO} not found; V9 Results tab will be sparse.")

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


def main():
    tmpl_path = os.path.join(V9_CORPUS, "dashboard_standalone.html")
    if not os.path.exists(tmpl_path):
        p(f"[v9-dashboard] ERROR: {tmpl_path} not found.")
        sys.exit(1)

    data = _load_v9_data()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_data = os.path.join(OUT_DIR, "data_v9.json")
    with open(out_data, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    p(f"[v9-dashboard] wrote {out_data} ({os.path.getsize(out_data)/1e6:.2f} MB)")

    with open(tmpl_path) as f:
        html = f.read()
    html = _normalize_v9_template(html)

    # 1. Keep the generated dashboard self-contained so it also works when
    # opened directly as a file, while retaining data_v9.json for inspection.
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

    html = html.replace(
        '    <!-- V9_NAV_TABS -->\n',
        '    ' + V9_RESULTS_NAV_BTN,
    )
    html = html.replace(
        '  <!-- V9_TAB_SECTIONS -->\n',
        V9_RESULTS_SECTION,
    )
    html = _inject_dashboard_tab_scripts(html, "", V9_RESULTS_JS)
    html = html.replace("</style>", V9_RESULTS_CSS + "\n</style>", 1)
    html = _make_d3_optional(html)

    # 4. Remove Entity Resolution if present
    html = html.replace('  <button data-tab="entityResolution">Entity Resolution</button>\n', '')
    html = html.replace('  <section id="tab-entityResolution" class="tab-content"></section>\n', '')

    # 5. Update titles
    html = re.sub(r"<title>[^<]*</title>", "<title>CBP Graph Corpus Explorer - V9</title>", html, count=1)
    html = re.sub(r"<h1>[^<]*</h1>", "<h1>CBP Graph Corpus Explorer &middot; V9</h1>", html, count=1)

    # 5. DATA is already embedded above; no local fetch is needed.
    out_html = os.path.join(OUT_DIR, "index.html")
    with open(out_html, "w") as f:
        f.write(html)
    p(f"[v9-dashboard] wrote {out_html} ({os.path.getsize(out_html)/1e6:.2f} MB)")
    p("[v9-dashboard] open v9_dashboard/index.html directly or through a local HTTP server.")


if __name__ == "__main__":
    main()
