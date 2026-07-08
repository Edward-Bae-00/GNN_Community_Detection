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


HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(DATA_DIR))
V9_CORPUS = os.path.join(DATA_DIR, "synthetic_cbp_graph_corpus_v9")
V9_DATA = os.path.join(V9_CORPUS, "dashboard_data.json")
V9_DEMO = os.path.join(REPO_ROOT, "gnn", "diagnostics", "demo_comparison_v9.json")
OUT_DIR = os.path.join(DATA_DIR, "v9_dashboard")


def p(*args):
    print(*args, flush=True)


def _load_v9_data() -> dict:
    if not os.path.exists(V9_DATA):
        p(f"[v9-dashboard] ERROR: {V9_DATA} not found.")
        p("[v9-dashboard] Run: .venv/bin/python Documents/Data/scripts/build_dashboard.py "
          "Documents/Data/synthetic_cbp_graph_corpus_v9")
        sys.exit(1)
    with open(V9_DATA) as f:
        data = json.load(f)
    if os.path.exists(V9_DEMO):
        with open(V9_DEMO) as f:
            data["v9Demo"] = json.load(f)
    else:
        p(f"[v9-dashboard] WARNING: {V9_DEMO} not found; V9 Results tab will be sparse.")
    return data


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

    # 1. Strip inline DATA blob
    data_start = html.find("const DATA = ")
    iife_start = html.find("\n(async function(){", data_start)
    html = html[:data_start] + "\nlet DATA = null;\nlet D = null;\n" + html[iife_start:]

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
        '  <button data-tab="explorer">Community Explorer</button>\n',
        '  <button data-tab="explorer">Community Explorer</button>\n' + V9_RESULTS_NAV_BTN
    )
    html = html.replace(
        '  <section id="tab-explorer" class="tab-content"></section>\n',
        '  <section id="tab-explorer" class="tab-content"></section>\n' + V9_RESULTS_SECTION
    )
    html = html.replace(
        "explorer:{rendered:false,render(){",
        V9_RESULTS_JS + "explorer:{rendered:false,render(){"
    )
    html = html.replace("</style>", V9_RESULTS_CSS + "\n</style>", 1)

    # 4. Update titles
    html = re.sub(r"<title>[^<]*</title>", "<title>CBP Graph Corpus Explorer - V9</title>", html, count=1)
    html = re.sub(r"<h1>[^<]*</h1>", "<h1>CBP Graph Corpus Explorer &middot; V9</h1>", html, count=1)

    # 5. Inject new fetch loader
    loader_idx = html.find("(async function(){\n") + 19
    loader_js = """
  try {
    const resp = await fetch('data_v9.json');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    DATA = await resp.json();
    D = DATA;
  } catch (e) {
    console.error('Failed to load V9 dashboard data', e);
    return;
  }
"""
    html = html[:loader_idx] + loader_js + html[loader_idx:]

    out_html = os.path.join(OUT_DIR, "index.html")
    with open(out_html, "w") as f:
        f.write(html)
    p(f"[v9-dashboard] wrote {out_html} ({os.path.getsize(out_html)/1e6:.2f} MB)")
    p("[v9-dashboard] open v9_dashboard/index.html through a local HTTP server.")


if __name__ == "__main__":
    main()
