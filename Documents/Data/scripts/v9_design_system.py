"""V9 dashboard design system: tokens, contrast fixes, and consistency layer.

The base stylesheet for the dashboard lives in ``dashboard_standalone.html``
inside the corpus directory, which is generated and gitignored. Editing it
directly is not durable, because the next ``build_dashboard.py`` run discards
the change. This module is the tracked seam instead: it emits a stylesheet that
``build_v9_dashboard.py`` appends as the last block inside ``<style>``, so it
wins the cascade without touching the generated template.

What the layer corrects, all measured rather than eyeballed:

* Contrast. The inherited ``--text3`` scored 2.55:1 on ``--surface`` while
  carrying every 10-11px label in the dashboard. The ramp below is verified at
  >= 4.5:1 against all four background tokens.
* Palette sprawl. The template accumulated 28 hard-coded hexes, including three
  different greens and a second muted palette. Everything routes through tokens.
* Light-mode leftovers. Several shadows were authored for white backgrounds
  (``rgba(0,0,0,0.02)``) and are invisible on a near-black surface.
* Series encoding. On a dark background the >= 3:1 requirement compresses
  luminance so far that no three-colour ramp stays separable under simulated
  deuteranopia, protanopia and tritanopia. The best worst-case separation across
  125 candidate palettes was 1.59. Colour is therefore paired with dash and
  marker redundancy rather than carrying the distinction alone.
"""

import base64
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "assets", "fonts")

# (family, weight, filename) for the latin subset of each face actually used.
FONT_FACES = (
    ("Outfit", 400, "Outfit-400.woff2"),
    ("Outfit", 500, "Outfit-500.woff2"),
    ("Outfit", 600, "Outfit-600.woff2"),
    ("Outfit", 700, "Outfit-700.woff2"),
    ("JetBrains Mono", 400, "JetBrainsMono-400.woff2"),
    ("JetBrains Mono", 500, "JetBrainsMono-500.woff2"),
    ("JetBrains Mono", 600, "JetBrainsMono-600.woff2"),
    ("JetBrains Mono", 700, "JetBrainsMono-700.woff2"),
)

# Google Fonts @import in the base template. Render-blocking, and it silently
# degrades to system-ui with no network, which is exactly the demo setting that
# matters most. Removed in favour of the embedded faces below.
GOOGLE_FONTS_IMPORT_PREFIX = "@import url('https://fonts.googleapis.com/css2?"


def _font_face_rule(family: str, weight: int, filename: str) -> str:
    path = os.path.join(FONT_DIR, filename)
    with open(path, "rb") as fh:
        payload = base64.b64encode(fh.read()).decode("ascii")
    return (
        "@font-face{"
        f"font-family:'{family}';"
        "font-style:normal;"
        f"font-weight:{weight};"
        "font-display:swap;"
        f"src:url(data:font/woff2;base64,{payload}) format('woff2');"
        "unicode-range:U+0000-00FF;"
        "}"
    )


def build_font_face_css() -> str:
    """Return @font-face rules with the woff2 payloads inlined."""
    return "\n".join(_font_face_rule(*face) for face in FONT_FACES)


def strip_google_fonts_import(html: str) -> str:
    """Drop the render-blocking Google Fonts @import from the base template."""
    start = html.find(GOOGLE_FONTS_IMPORT_PREFIX)
    if start < 0:
        return html
    end = html.find("\n", start)
    if end < 0:
        raise ValueError("unterminated Google Fonts @import in dashboard template")
    return html[:start] + html[end + 1 :]


# Layer 1: tokens. Every neutral is verified >= 4.5:1 against --bg (#0a0a0c),
# --surface (#131316), --elevated (#1a1a1f) and --sunk (#08080a).
_TOKENS = """
:root{
  /* Neutral ramp. Minimum contrast across all four surface tokens:
     text1 14.19:1, text2 6.77:1, text3 4.69:1. --text-dim is 3.44:1 and is
     reserved for non-essential decoration, never for label or body copy. */
  --text1:#e8e8ec;--text2:#a1a1ab;--text3:#84848f;--text-dim:#6e6e78;

  /* One accent for the whole dashboard. 9.02:1 on --bg. */
  --accent:#34d399;--accent-hover:#6ee7b7;
  --accent-soft:rgba(52,211,153,.10);--accent-glow:rgba(52,211,153,.16);

  /* Semantic. Replaces the 600-level values that were authored for light
     backgrounds and failed AA on this shell. */
  --positive:#34d399;--warning:#fbbf24;
  --negative:#f87171;--negative-soft:rgba(248,113,113,.10);

  /* Series colours. Paired with dash and marker redundancy below, because
     colour alone cannot separate three series on a dark background. */
  --data-baseline:#cbd5e1;--data-hybrid:#34d399;--data-gnn:#60a5fa;
  --data-context:#6e6e78;

  /* Type scale, replacing 13 ad-hoc sizes. 10px is the floor. */
  --fs-micro:10px;--fs-xs:11px;--fs-sm:12px;--fs-base:13px;
  --fs-md:14px;--fs-lg:18px;--fs-xl:24px;

  /* Radius scale, replacing 9 ad-hoc values. */
  --r-sm:6px;--r-md:10px;--r-full:999px;

  /* Elevation that is actually visible against a near-black surface. */
  --shadow-1:0 1px 2px rgba(0,0,0,.45);
  --shadow-2:0 10px 30px rgba(0,0,0,.55);

  /* Spacing rhythm. */
  --sp-1:4px;--sp-2:8px;--sp-3:12px;--sp-4:16px;
  --sp-5:24px;--sp-6:32px;--sp-7:40px;
}
"""

# Layer 2: retire hard-coded hexes in favour of the tokens above.
_PALETTE_UNIFICATION = """
/* Outcome pills were slate/emerald/red 600s over a white background. */
#tab-v9Results .v9-pill.win{background:rgba(52,211,153,.14);color:var(--positive)}
#tab-v9Results .v9-pill.tie{background:rgba(148,163,184,.14);color:var(--text2)}
#tab-v9Results .v9-pill.loss{background:rgba(248,113,113,.14);color:var(--negative)}
#tab-v9Results td.best{color:var(--positive)}
#tab-v9Results td.bad{color:var(--negative)}

/* Series keys and lines. #16a34a was a second green competing with the accent. */
#tab-v9Results .v9-chart-key.baseline{background:var(--data-baseline)}
#tab-v9Results .v9-chart-key.hybrid{background:var(--data-hybrid)}
#tab-v9Results .v9-chart-key.gnn{background:var(--data-gnn)}
#tab-v9Results .v9-chart-key.crossings{background:var(--data-context)}
#tab-v9Results .v9-chart-key.hidden-carriers{background:var(--data-gnn)}
#tab-v9Results .v9-found-chart-line.baseline{stroke:var(--data-baseline)}
#tab-v9Results .v9-found-chart-line.hybrid{stroke:var(--data-hybrid)}
#tab-v9Results .v9-found-chart-line.gnn{stroke:var(--data-gnn)}
#tab-v9Results .v9-fill{background:var(--data-gnn)}
#tab-v9Results .v9-fill.base{background:var(--data-baseline)}
#tab-v9Results .v9-volume-line{stroke:var(--data-context)}
#tab-v9Results .v9-volume-area{fill:rgba(110,110,120,.18)}
#tab-v9Results .v9-simulated-card{border-left-color:var(--data-baseline)}
#tab-v9Results .v9-simulated-card.hybrid{border-left-color:var(--data-hybrid)}
#tab-v9Results .v9-capacity-row.is-best{box-shadow:inset 3px 0 0 var(--accent)}

/* The story block carried its own muted palette (#4f7890/#c97848/#6a8f6b
   /#d28b57) unrelated to the rest of the dashboard. */
#tab-v9Results .v9-story-kicker{color:var(--data-gnn)}
#tab-v9Results .v9-story{background:var(--surface)}
#tab-v9Results .v9-story-note{border-left-color:var(--warning)}
#tab-v9Results .v9-lens{border-left-color:var(--data-gnn)}
#tab-v9Results .v9-lens:nth-child(2){border-left-color:var(--warning)}
#tab-v9Results .v9-lens:nth-child(3){border-left-color:var(--positive)}
#tab-v9Results .v9-explain{border-left-color:var(--data-gnn)}
#tab-v9Results .v9-summary-lead{
  background:linear-gradient(135deg,rgba(52,211,153,.14),rgba(52,211,153,.03));
  border-color:rgba(52,211,153,.30)}

/* Anomaly-ranking metrics. */
.uad-metric-val.best{color:var(--positive)}
.uad-metric-val.f1{color:var(--data-gnn)}

/* Recovery explorer warning state. */
#tab-v9Results .v9-recovery-stat.is-warning{
  border-color:rgba(251,191,36,.45);background:rgba(251,191,36,.08)}
#tab-v9Results .v9-recovery-stat.is-warning b,
#tab-v9Results .v9-recovery-stat.is-warning span{color:var(--warning)}
#tab-v9Results .v9-recovery-warning{
  border-left-color:var(--warning);background:rgba(251,191,36,.08);color:var(--warning)}
#tab-v9Results .v9-recovery-scope{border-color:rgba(52,211,153,.30)}
#tab-v9Results .v9-recovery-case[aria-current="true"]{border-color:rgba(52,211,153,.45)}
"""

# Layer 3: redundant encoding. Colour alone cannot separate three series on a
# dark background, so each line also carries a distinct dash signature and each
# legend key a distinct shape.
_SERIES_REDUNDANCY = """
#tab-v9Results .v9-found-chart-line.baseline{stroke-dasharray:7 4}
#tab-v9Results .v9-found-chart-line.gnn{stroke-dasharray:2 3}
#tab-v9Results .v9-found-chart-line.hybrid{stroke-dasharray:none}
#tab-v9Results .v9-volume-line{stroke-dasharray:1 4}
#tab-v9Results .v9-chart-key{position:relative}
#tab-v9Results .v9-chart-key.baseline{border-radius:2px}
#tab-v9Results .v9-chart-key.gnn{
  border-radius:0;clip-path:polygon(50% 0,100% 100%,0 100%)}
#tab-v9Results .v9-chart-key.hybrid{border-radius:var(--r-full)}
"""

# Layer 4: type floor. 8px and 9px are not readable at arm's length on a
# projector, which is where this dashboard gets shown.
#
# The recovery explorer used to be patched from here, but this sheet is injected
# after V9_RECOVERY_EXPLAINER_CSS at equal specificity, so every rule below
# silently beat the panel's own type and the panel could not be fixed at source.
# That panel now owns its sizes in v9_recovery_explainer_ui.py. Do not reinstate
# `#tab-v9Results .v9-recovery-*` font-size rules here; edit them there instead.
_TYPE_SCALE = """
.xp-nlabel,
.xp-legend .xp-ltitle{font-size:var(--fs-micro)}
"""

# Layer 5: shape and elevation consistency.
_SHAPE_AND_ELEVATION = """
.chart-panel,.map-container,.filter-panel,.network-canvas,.network-side,
.xp-canvas,.xp-side,.xp-tools,.uad-card,.uad-figure,
#tab-v9Results .v9-card,#tab-v9Results .v9-recovery-workspace{
  border-radius:var(--r-md)}

.mode-chip,.xp-chip,.v9-pill,#tab-v9Results .v9-recovery-source,
#tab-v9Results .v9-recovery-scope,.uad-badge{border-radius:var(--r-full)}

.filter-field select,.network-toolbar select,.xp-select,.xp-seg,.xp-reset,
.reset-btn,.map-controls button,.xp-zoom button,.xp-btn,
.uad-metric,.er-kpi,
#tab-v9Results .v9-seg,#tab-v9Results .v9-recovery-case,
#tab-v9Results .v9-recovery-panel,#tab-v9Results .v9-recovery-button,
#tab-v9Results .v9-recovery-select,#tab-v9Results .v9-recovery-search,
#tab-v9Results .v9-chart-block,#tab-v9Results .v9-volume-stat,
#tab-v9Results .v9-simulated-card,#tab-v9Results .v9-model-note{
  border-radius:var(--r-sm)}

/* These shadows were authored for a white background and render as nothing. */
#tab-v9Results .v9-card,.uad-card{box-shadow:var(--shadow-1)}
#tab-v9Results .v9-seg button.on,
#tab-v9Results .v9-recovery-cohorts button[aria-pressed="true"]{
  box-shadow:var(--shadow-1)}
.tooltip{box-shadow:var(--shadow-2);border-radius:var(--r-sm)}

/* Neon outer glow is an AI tell and adds nothing at 7px. */
.header-mark{box-shadow:none}
"""

# Layer 6: focus, motion and other interaction guarantees. The base sheet only
# defined focus-visible inside the newest section, leaving global navigation,
# legends and map controls with no keyboard affordance at all.
_INTERACTION = """
:where(button,a,select,input,textarea,summary,[tabindex]):focus-visible{
  outline:2px solid var(--accent-hover);outline-offset:2px}
nav.tabs button:focus-visible{outline-offset:-2px}
.legend-item:focus-visible,.mode-chip:focus-visible,.xp-chip:focus-visible{
  outline:2px solid var(--accent-hover);outline-offset:2px}

nav.tabs button{color:var(--text3)}
nav.tabs button:hover{color:var(--text1)}
nav.tabs button.active{color:var(--accent);border-bottom-color:var(--accent)}

@media (prefers-reduced-motion: reduce){
  *,*::before,*::after{
    animation-duration:.01ms!important;
    animation-iteration-count:1!important;
    transition-duration:.01ms!important;
    scroll-behavior:auto!important}
}
"""

# Layer 7: provenance header. For a research dashboard the run it came from is
# the credibility signal, so it belongs on screen rather than in a filename.
_PROVENANCE = """
header{align-items:center;gap:var(--sp-5)}
.header-left h1{font-size:var(--fs-md)}
.header-meta{
  display:flex;flex-wrap:wrap;align-items:center;gap:var(--sp-2) var(--sp-5);
  margin-left:auto;font-family:var(--font-mono);font-size:var(--fs-xs);
  color:var(--text3);text-align:right}
.header-meta-item{display:flex;align-items:baseline;gap:var(--sp-2);min-width:0}
.header-meta-label{
  font-family:var(--font-body);font-size:var(--fs-micro);font-weight:600;
  letter-spacing:.06em;text-transform:uppercase;color:var(--text3)}
.header-meta-value{color:var(--text2);font-variant-numeric:tabular-nums}
@media(max-width:900px){
  header{flex-wrap:wrap;align-items:flex-start}
  .header-meta{margin-left:0;width:100%;text-align:left;gap:var(--sp-1) var(--sp-4)}
}
"""

# Layer 8: density rhythm. The metric row used a 32px gutter that read as
# unrelated columns rather than one instrument cluster.
_RHYTHM = """
.metrics{gap:var(--sp-5) var(--sp-6);margin-bottom:var(--sp-6)}
.metric-value{font-size:var(--fs-xl);font-variant-numeric:tabular-nums}
.metric-label{color:var(--text3)}
.metric-sub{color:var(--text3)}
.section{padding-top:var(--sp-6);margin-top:var(--sp-6)}
.section-head{font-size:var(--fs-base);color:var(--text1)}
.section-note{color:var(--text2)}
.chart-title{color:var(--text3)}
main{padding:var(--sp-7) var(--sp-7) var(--sp-6)}
@media(max-width:900px){main{padding:var(--sp-5) var(--sp-4)}}
"""

# Layer 9: print. This dashboard gets screenshotted into decks and papers.
_PRINT = """
@media print{
  :root{--bg:#fff;--surface:#fff;--elevated:#fff;--sunk:#fff;
        --border:#d4d4d8;--border-strong:#a1a1aa;
        --text1:#18181b;--text2:#3f3f46;--text3:#52525b;--text-dim:#71717a}
  html{background:#fff;color:#18181b}
  nav.tabs,.map-controls,.xp-zoom,.reset-btn,.xp-reset{display:none}
  .tab-content{display:block!important;break-inside:avoid}
  .chart-panel,#tab-v9Results .v9-card,.uad-card{
    box-shadow:none;border:1px solid #d4d4d8;break-inside:avoid}
  header{border-bottom:1px solid #d4d4d8}
}
"""


def build_design_system_css() -> str:
    """Return the full override stylesheet, fonts first."""
    return "\n".join(
        [
            "/* ===== V9 design system layer (v9_design_system.py) ===== */",
            build_font_face_css(),
            _TOKENS,
            _PALETTE_UNIFICATION,
            _SERIES_REDUNDANCY,
            _TYPE_SCALE,
            _SHAPE_AND_ELEVATION,
            _INTERACTION,
            _PROVENANCE,
            _RHYTHM,
            _PRINT,
            "/* ===== end V9 design system layer ===== */",
        ]
    )


def provenance_from_meta(meta: dict) -> dict:
    """Map a dashboard artifact's ``meta`` block onto provenance fields.

    Missing or malformed values are dropped rather than rendered as blanks, so
    a partial artifact still produces a clean header.
    """
    meta = meta or {}
    out = {}

    corpus = meta.get("corpus")
    if isinstance(corpus, str) and corpus.strip():
        # "synthetic_cbp_graph_corpus_v9" carries no information the reader of
        # a V9 dashboard does not already have; the version does.
        out["corpus"] = corpus.strip().rsplit("_", 1)[-1].upper()

    generated = meta.get("generated_at")
    if isinstance(generated, str) and len(generated) >= 10:
        out["generated"] = generated[:10]

    nodes = meta.get("total_nodes")
    edges = meta.get("total_edges")
    if isinstance(nodes, int) and isinstance(edges, int):
        out["records"] = f"{nodes:,} nodes / {edges:,} edges"

    return out


def build_provenance_markup(meta: dict) -> str:
    """Return the header provenance strip for ``meta``.

    Only keys with a usable value are rendered, so a partial artifact degrades
    to fewer items rather than to empty labels.
    """
    fields = (
        ("corpus", "Corpus"),
        ("generated", "Built"),
        ("records", "Records"),
    )
    items = []
    for key, label in fields:
        value = (meta or {}).get(key)
        if value in (None, "", []):
            continue
        items.append(
            '<span class="header-meta-item">'
            f'<span class="header-meta-label">{label}</span>'
            f'<span class="header-meta-value">{value}</span>'
            "</span>"
        )
    if not items:
        return ""
    return '<div class="header-meta">' + "".join(items) + "</div>"


def inject_provenance(html: str, meta: dict) -> str:
    """Place the provenance strip in the header, idempotently."""
    markup = build_provenance_markup(meta)
    if not markup or 'class="header-meta"' in html:
        return html
    anchor = "</header>"
    if anchor not in html:
        raise ValueError("dashboard template is missing its header")
    return html.replace(anchor, markup + "\n" + anchor, 1)
