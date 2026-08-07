"""Contract tests for the V9 dashboard design system layer."""

import os
import re

import pytest

from scripts.dashboard import v9_design_system as ds


# --- contrast helpers -------------------------------------------------------


def _srgb(channel):
    c = channel / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _srgb(r) + 0.7152 * _srgb(g) + 0.0722 * _srgb(b)


def _contrast(fg, bg):
    a, b = _luminance(fg), _luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


SURFACES = ("#0c1117", "#141c24", "#1d2832", "#070b10")


def _token(css, name):
    match = re.search(rf"{re.escape(name)}\s*:\s*(#[0-9a-fA-F]{{6}})", css)
    assert match, f"token {name} not found"
    return match.group(1)


def _strip_comments(css):
    """Comments document what was retired; only rendered CSS is under test."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


# --- approved token contract ------------------------------------------------


APPROVED_TOKENS = {
    "--bg": "#0c1117",
    "--surface": "#141c24",
    "--elevated": "#1d2832",
    "--sunk": "#070b10",
    "--text1": "#f4f7fa",
    "--text2": "#c0cbd5",
    "--text3": "#93a1ad",
    "--text-dim": "#71808c",
    "--accent": "#5eead4",
    "--accent-hover": "#99f6e4",
    "--accent-soft": "rgba(94,234,212,.12)",
    "--accent-glow": "rgba(94,234,212,.18)",
    "--positive": "#5eead4",
    "--warning": "#fbbf24",
    "--negative": "#fb7185",
    "--negative-soft": "rgba(251,113,133,.14)",
    "--data-baseline": "#e2e8f0",
    "--data-hybrid": "#5eead4",
    "--data-gnn": "#60a5fa",
    "--data-context": "#93a1ad",
    "--fs-micro": "11px",
    "--fs-xs": "12px",
    "--fs-sm": "13px",
    "--fs-base": "14px",
    "--fs-md": "15px",
    "--fs-lg": "19px",
    "--fs-xl": "26px",
}


def test_approved_deep_slate_tokens_are_exact():
    css = ds.build_design_system_css()
    mismatches = {}
    for token, expected in APPROVED_TOKENS.items():
        match = re.search(rf"{re.escape(token)}\s*:\s*([^;}}]+)", css)
        actual = match.group(1).strip() if match else "<missing>"
        if actual != expected:
            mismatches[token] = {"expected": expected, "actual": actual}
    assert not mismatches, f"approved token mismatches: {mismatches}"


# --- contrast ---------------------------------------------------------------


@pytest.mark.parametrize("token", ["--text1", "--text2", "--text3"])
def test_text_ramp_passes_aa_on_every_surface(token):
    """The inherited --text3 scored 2.55:1 while carrying every small label."""
    css = ds.build_design_system_css()
    color = _token(css, token)
    for surface in SURFACES:
        ratio = _contrast(color, surface)
        assert ratio >= 4.5, f"{token} {color} on {surface} = {ratio:.2f}:1"


def test_text_ramp_keeps_three_distinguishable_steps():
    css = ds.build_design_system_css()
    steps = [_luminance(_token(css, t)) for t in ("--text1", "--text2", "--text3")]
    assert steps[0] > steps[1] > steps[2], "ramp must stay monotonic"
    for brighter, dimmer in zip(steps, steps[1:]):
        assert (brighter + 0.05) / (dimmer + 0.05) >= 1.25, "steps too close to read"


def test_dim_token_is_documented_as_decoration_only():
    """--text-dim is below AA on purpose; the comment must say so."""
    css = ds.build_design_system_css()
    assert _contrast(_token(css, "--text-dim"), "#141c24") < 4.5
    assert "non-essential decoration" in css


def test_dim_token_is_not_used_for_reader_facing_text():
    """--text-dim is sub-AA, so it may tint graphics but never label copy."""
    css = _strip_comments(ds.build_design_system_css())
    screen = css.split("@media print", 1)[0]
    for rule in re.findall(r"([^{}]+)\{([^{}]*)\}", screen):
        selector, body = rule
        if "color:var(--text-dim)" not in body.replace(" ", ""):
            continue
        pytest.fail(f"--text-dim used as text color in: {selector.strip()}")


@pytest.mark.parametrize("token", ["--accent", "--positive", "--warning", "--negative"])
def test_semantic_colors_pass_aa_on_every_surface(token):
    css = ds.build_design_system_css()
    color = _token(css, token)
    for surface in SURFACES:
        assert _contrast(color, surface) >= 4.5


@pytest.mark.parametrize(
    "token", ["--data-baseline", "--data-hybrid", "--data-gnn"]
)
def test_series_colors_meet_graphical_contrast(token):
    """WCAG 1.4.11 requires 3:1 for meaningful non-text graphics."""
    css = ds.build_design_system_css()
    color = _token(css, token)
    for surface in SURFACES:
        assert _contrast(color, surface) >= 3.0


# --- redundant encoding -----------------------------------------------------


def test_each_series_line_carries_a_distinct_dash_signature():
    """Colour alone cannot separate three series on a dark background."""
    css = ds.build_design_system_css()
    signatures = {}
    for arm in ("baseline", "hybrid", "gnn"):
        match = re.search(
            rf"\.v9-found-chart-line\.{arm}\{{[^}}]*stroke-dasharray:([^;}}]+)", css
        )
        assert match, f"{arm} line has no dash signature"
        signatures[arm] = match.group(1).strip()
    assert len(set(signatures.values())) == 3, f"dashes not distinct: {signatures}"


def test_legend_keys_carry_distinct_shapes():
    css = ds.build_design_system_css()
    assert "clip-path:polygon" in css, "gnn key needs a non-circular shape"
    assert re.search(r"\.v9-chart-key\.baseline\{border-radius:2px\}", css)


# --- palette unification ----------------------------------------------------


BANNED_HEXES = (
    "#16a34a",  # second green, competed with the accent
    "#059669",  # third green, failed AA as pill text
    "#4f7890",  # story-block palette, unrelated to the rest
    "#c97848",
    "#6a8f6b",
    "#d28b57",
    "#dc2626",  # light-mode red
    "#64748b",  # light-mode slate used as body text
)


@pytest.mark.parametrize("banned", BANNED_HEXES)
def test_layer_does_not_reintroduce_retired_hexes(banned):
    css = _strip_comments(ds.build_design_system_css())
    assert banned.lower() not in css.lower()


def test_outcome_pills_are_restated_for_a_dark_surface():
    css = ds.build_design_system_css()
    for variant in ("win", "tie", "loss"):
        assert re.search(rf"\.v9-pill\.{variant}\{{[^}}]*var\(--", css)


# --- type, shape, motion ----------------------------------------------------


def test_no_font_size_below_the_eleven_pixel_floor():
    """Covers both the scale tokens and any literal font-size in the layer."""
    css = _strip_comments(ds.build_design_system_css())
    sizes = [int(v) for v in re.findall(r"--fs-[a-z]+:\s*(\d+)px", css)]
    sizes += [int(v) for v in re.findall(r"font-size:\s*(\d+)px", css)]
    assert sizes, "expected explicit sizes in the type scale"
    assert min(sizes) >= 11, f"sub-11px type present: {sorted(set(sizes))}"


def test_this_layer_does_not_restyle_recovery_explorer_type():
    """This sheet is injected after V9_RECOVERY_EXPLAINER_CSS at equal
    specificity, so a font-size on a `.v9-recovery-*` selector here beats the
    panel's own rule and makes that panel unfixable at source. It owns its type;
    change sizes in v9_recovery_explainer_ui.py instead of reinstating them here.
    """
    css = _strip_comments(ds.build_design_system_css())
    offenders = [
        block.strip()
        for block in css.split("}")
        if "v9-recovery" in block and "font-size" in block
    ]

    assert not offenders, f"recovery type overridden from the design system: {offenders}"


def test_type_scale_is_bounded():
    css = ds.build_design_system_css()
    scale = re.search(r"--fs-micro:(\d+)px", css)
    assert scale and scale.group(1) == "11"


def test_radius_scale_collapses_to_three_values():
    css = ds.build_design_system_css()
    declared = set(re.findall(r"--r-(?:sm|md|full):\s*([0-9]+px)", css))
    assert declared == {"6px", "10px", "999px"}


def test_reduced_motion_is_honoured():
    css = ds.build_design_system_css()
    assert "prefers-reduced-motion: reduce" in css
    assert "animation-iteration-count:1!important" in css


def test_global_focus_visible_covers_interactive_elements():
    css = ds.build_design_system_css()
    assert ":focus-visible" in css
    for element in ("button", "select", "input", "a"):
        assert re.search(rf"\b{element}\b[^{{]*:focus-visible", css) or element in (
            css.split(":focus-visible")[0][-200:]
        )


def test_dashboard_shell_uses_readable_shell_rhythm():
    css = ds.build_design_system_css()

    assert ".metric-label,.metric-sub{color:var(--text2)" in css
    assert ".section-head{font-size:var(--fs-md);color:var(--text1)" in css
    assert ".chart-title{color:var(--text2)" in css
    assert ".axis .tick text{fill:var(--text2);font-size:12px" in css
    assert ".grid line{stroke:var(--border-strong);opacity:.72}" in css
    assert "nav.tabs{background:var(--sunk);border-bottom-color:var(--border-strong)" in css
    assert "nav.tabs button{color:var(--text2);font-size:13px;padding:15px 18px}" in css
    assert (
        "nav.tabs button.active{color:var(--accent-hover);border-bottom-color:var(--accent)}"
        in css
    )
    panel_rule = (
        r"\.chart-panel,\s*\.map-container,\s*\.filter-panel,\s*"
        r"\.network-canvas,\s*\.network-side,\s*\.xp-canvas,\s*"
        r"\.xp-side,\s*\.xp-tools,\s*\.uad-card,\s*\.uad-figure,\s*"
        r"#tab-v9Results \.v9-card,\s*#tab-v9Results "
        r"\.v9-recovery-workspace\s*\{\s*"
        r"background:var\(--surface\);\s*"
        r"border-color:var\(--border-strong\)"
    )
    assert re.search(panel_rule, css)
    assert "header{background:var(--surface);border-bottom-color:var(--border-strong)" in css
    assert ".section-note{color:var(--text2)}" in css


def test_dashboard_shell_allows_results_children_to_shrink():
    css = ds.build_design_system_css()

    assert re.search(r":where\(main,[^)]*\)\{[^}]*min-width:\s*0", css)
    assert re.search(
        r":where\([^)]*#tab-v9Results[^)]*\)\{[^}]*min-width:\s*0",
        css,
    )


def test_crossing_context_line_is_solid_and_muted():
    css = ds.build_design_system_css()

    assert re.search(
        r"\.v9-volume-line\{[^}]*stroke-dasharray:\s*none[^}]*opacity:",
        css,
    )


def test_neon_glow_is_removed():
    css = ds.build_design_system_css()
    assert re.search(r"\.header-mark\{box-shadow:none\}", css)


def test_invisible_light_mode_shadows_are_replaced():
    css = ds.build_design_system_css()
    assert "rgba(0,0,0,0.02)" not in css
    assert "rgba(15,23,42,.12)" not in css
    assert "--shadow-1:0 1px 2px rgba(0,0,0,.45)" in css


def test_layer_is_well_formed_css():
    """A malformed layer would silently break every rule after it."""
    css = _strip_comments(ds.build_design_system_css())
    assert css.count("{") == css.count("}"), "unbalanced braces"
    assert css.count("/*") == 0 and css.count("*/") == 0
    # @font-face payloads are base64 data URIs containing ';', so they cannot
    # be split on declaration boundaries; they are covered by the font tests.
    css = re.sub(r"@font-face\{[^}]*\}", "", css)
    # every declaration block should terminate its declarations
    for selector, body in re.findall(r"([^{}]+)\{([^{}@]*)\}", css):
        decls = [d for d in body.split(";") if d.strip()]
        for decl in decls:
            assert ":" in decl, f"malformed declaration {decl!r} in {selector.strip()}"


def test_print_stylesheet_inverts_to_paper():
    css = ds.build_design_system_css()
    assert "@media print" in css
    assert re.search(r"@media print\{[^@]*--bg:#fff", css, re.S)


# --- fonts ------------------------------------------------------------------


def test_every_declared_face_is_embedded():
    css = ds.build_font_face_css()
    assert css.count("@font-face") == len(ds.FONT_FACES)
    assert css.count("data:font/woff2;base64,") == len(ds.FONT_FACES)
    assert "https://" not in css, "faces must not reach the network"


def test_font_payloads_are_real_woff2():
    for _family, _weight, filename in ds.FONT_FACES:
        path = os.path.join(ds.FONT_DIR, filename)
        with open(path, "rb") as fh:
            assert fh.read(4) == b"wOF2", f"{filename} is not woff2"


def test_google_fonts_import_is_stripped():
    html = (
        "<style>\n"
        "@import url('https://fonts.googleapis.com/css2?family=Outfit&display=swap');\n"
        "body{color:red}\n"
        "</style>"
    )
    out = ds.strip_google_fonts_import(html)
    assert "fonts.googleapis.com" not in out
    assert "body{color:red}" in out


def test_stripping_import_is_a_no_op_when_absent():
    html = "<style>body{color:red}</style>"
    assert ds.strip_google_fonts_import(html) == html


# --- provenance -------------------------------------------------------------


def test_provenance_renders_supplied_fields():
    markup = ds.build_provenance_markup(
        {"corpus": "v9", "generated": "2026-07-28", "records": "12,041"}
    )
    assert "header-meta" in markup
    for value in ("v9", "2026-07-28", "12,041"):
        assert value in markup


def test_provenance_skips_missing_fields_without_empty_labels():
    markup = ds.build_provenance_markup({"corpus": "v9", "generated": None})
    assert "Corpus" in markup
    assert "Built" not in markup


def test_provenance_is_empty_when_nothing_is_known():
    assert ds.build_provenance_markup({}) == ""
    assert ds.build_provenance_markup(None) == ""


def test_provenance_injection_is_idempotent():
    html = "<header>\n  <div class='header-left'></div>\n</header>"
    meta = {"corpus": "v9"}
    once = ds.inject_provenance(html, meta)
    twice = ds.inject_provenance(once, meta)
    assert once == twice
    assert once.count('class="header-meta"') == 1


def test_provenance_from_meta_maps_the_real_artifact_shape():
    fields = ds.provenance_from_meta(
        {
            "generated_at": "2026-07-21T03:19:59.527072+00:00",
            "corpus": "synthetic_cbp_graph_corpus_v9",
            "total_nodes": 636606,
            "total_edges": 2090447,
        }
    )
    assert fields["corpus"] == "V9"
    assert fields["generated"] == "2026-07-21"
    assert fields["records"] == "636,606 nodes / 2,090,447 edges"


@pytest.mark.parametrize(
    "meta",
    [
        {},
        None,
        {"corpus": "", "generated_at": None, "total_nodes": "many"},
        {"total_nodes": 5},  # edges missing, so the pair is unusable
    ],
)
def test_provenance_from_meta_drops_unusable_values(meta):
    fields = ds.provenance_from_meta(meta)
    assert all(v for v in fields.values()), f"blank value survived: {fields}"
    assert "records" not in fields


def test_provenance_injection_requires_a_header():
    with pytest.raises(ValueError, match="header"):
        ds.inject_provenance("<body></body>", {"corpus": "v9"})
