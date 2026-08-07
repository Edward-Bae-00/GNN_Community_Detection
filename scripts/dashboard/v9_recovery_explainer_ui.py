"""Pure state contracts for the V9 seed-0 recovery evidence explorer."""


V9_RECOVERY_EXPLAINER_CSS = r"""
#tab-v9Results .v9-recovery { margin: 30px 0; padding: 24px 0 32px; border-top: 1px solid var(--border-strong); border-bottom: 1px solid var(--border-strong); }
#tab-v9Results .v9-recovery-header { display: grid; grid-template-columns: minmax(0,1fr) auto; align-items: start; gap: 24px; margin-bottom: 18px; padding: 22px 24px; border: 1px solid var(--border); border-radius: 12px 12px 0 0; background: var(--surface); }
#tab-v9Results .v9-recovery-header-copy { min-width: 0; }
#tab-v9Results .v9-recovery-eyebrow { color: var(--accent-hover); font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
#tab-v9Results .v9-recovery-title { margin: 6px 0; color: var(--text1); font-size: clamp(22px, 2.5vw, 30px); font-weight: 700; letter-spacing: -.02em; text-wrap: balance; }
#tab-v9Results .v9-recovery-intro { max-width: 68ch; margin: 0; color: var(--text2); font-size: 12px; line-height: 1.55; }
#tab-v9Results .v9-recovery-scope { flex: 0 0 auto; max-width: 280px; padding: 10px 12px; border: 1px solid rgba(52,211,153,.32); border-radius: 999px; background: var(--accent-soft); color: var(--accent-hover); font-size: 10px; font-weight: 700; line-height: 1.4; text-align: right; }
#tab-v9Results .v9-recovery-scope small { display: block; margin-top: 2px; color: var(--text2); font-size: 10px; font-weight: 500; }
#tab-v9Results .v9-recovery-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
#tab-v9Results .v9-recovery-stat { min-width: 0; padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); }
#tab-v9Results .v9-recovery-stat b { display: block; color: var(--text1); font-family: var(--font-mono); font-size: 18px; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-recovery-stat span { display: block; margin-top: 4px; color: var(--text2); font-size: 10px; line-height: 1.3; letter-spacing: .045em; text-transform: uppercase; }
#tab-v9Results .v9-recovery-stat.is-warning { border-color: rgba(245,158,11,.5); background: rgba(245,158,11,.08); }
#tab-v9Results .v9-recovery-stat.is-warning b, #tab-v9Results .v9-recovery-stat.is-warning span { color: #fbbf24; }
#tab-v9Results .v9-recovery-status { margin-top: 9px; padding: 9px 11px; border-left: 3px solid var(--accent); background: var(--accent-soft); color: var(--text2); font-size: 11px; line-height: 1.45; }
#tab-v9Results .v9-recovery-status { border-left-color: var(--border-strong); background: var(--elevated); color: var(--text2); }
#tab-v9Results .v9-recovery-coverage { display: flex; flex-wrap: wrap; gap: 8px 18px; margin: 10px 0 18px; color: var(--text2); font-size: 10px; }
#tab-v9Results .v9-recovery-select, #tab-v9Results .v9-recovery-search { width: 100%; min-width: 0; box-sizing: border-box; border: 1px solid var(--border-strong); border-radius: 6px; background: var(--surface); color: var(--text1); padding: 7px 8px; font: inherit; font-size: 11px; }
#tab-v9Results .v9-recovery-case { width: 100%; padding: 10px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text2); text-align: left; cursor: pointer; }
#tab-v9Results .v9-recovery-case:hover { border-color: var(--border-strong); color: var(--text1); }
#tab-v9Results .v9-recovery-case[aria-current="true"] { border-color: rgba(52,211,153,.5); box-shadow: inset 3px 0 0 var(--accent); background: var(--accent-soft); }
#tab-v9Results .v9-recovery-case-meta { margin-top: 7px; color: var(--text2); font-size: 10px; line-height: 1.35; }
#tab-v9Results .v9-recovery-case-evidence { margin-top: 4px; color: var(--accent-hover); font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
#tab-v9Results .v9-recovery-case-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 14px; }
#tab-v9Results .v9-recovery-case-header h4 { margin: 0 0 4px; color: var(--text1); font-size: 15px; }
#tab-v9Results .v9-recovery-case-header p { margin: 0; color: var(--text2); font-size: 10px; }
#tab-v9Results .v9-recovery-ranks { display: grid; grid-template-columns: repeat(2, minmax(90px, 1fr)); gap: 1px; border: 1px solid var(--border); border-top: 0; background: var(--border); }
#tab-v9Results .v9-recovery-rank { padding: 8px; border-left: 2px solid var(--border-strong); background: var(--elevated); }
#tab-v9Results .v9-recovery-rank.is-primary { border-left-color: var(--accent); background: var(--accent-soft); }
#tab-v9Results .v9-recovery-rank b { display: block; color: var(--text1); font-family: var(--font-mono); font-size: 21px; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-recovery-rank span { display: block; margin-top: 2px; color: var(--text2); font-size: 10px; letter-spacing: .04em; text-transform: uppercase; }
#tab-v9Results .v9-recovery-rank-delta { grid-column: 1 / -1; color: var(--text2); font-size: 10px; line-height: 1.35; }
#tab-v9Results .v9-recovery-header-copy,
#tab-v9Results .v9-recovery-title,
#tab-v9Results .v9-recovery-intro,
#tab-v9Results .v9-recovery-narrative { font-family: Outfit, var(--font-sans), sans-serif; }
#tab-v9Results .v9-recovery-rank,
#tab-v9Results .v9-recovery-rank b,
#tab-v9Results .v9-attribution-weight,
#tab-v9Results .v9-recovery-table { font-family: 'JetBrains Mono', var(--font-mono), monospace; }
#tab-v9Results .v9-recovery-rank { min-height: 78px; padding: 12px; border-top: 2px solid var(--border-strong); border-left: 0; }
#tab-v9Results .v9-recovery-rank.is-primary { border-top-color: var(--accent); background: var(--accent-soft); }
#tab-v9Results .v9-recovery-rank-delta { color: var(--accent-hover); font-size: 12px; }
#tab-v9Results .v9-recovery-narrative { padding: 18px; border-radius: 10px; }
#tab-v9Results .v9-recovery-narrative p { font-size: 13px; line-height: 1.6; }
#tab-v9Results .v9-recovery-button,
#tab-v9Results .v9-recovery-case,
#tab-v9Results .v9-recovery-factor { min-height: 44px; }
#tab-v9Results .v9-recovery-evidence-grid { display: grid; grid-template-columns: minmax(190px, .62fr) minmax(0, 1.38fr); gap: 12px; }
#tab-v9Results .v9-recovery-evidence-grid > * { width: 100%; min-width: 0; }
#tab-v9Results .v9-recovery-panel { min-width: 0; border: 1px solid var(--border); border-radius: 9px; background: var(--elevated); }
#tab-v9Results .v9-recovery-v3 .v9-recovery-panel { overflow: hidden; border-radius: 10px; background: var(--surface); }
#tab-v9Results .v9-recovery-panel-head { padding: 11px 12px; border-bottom: 1px solid var(--border); }
#tab-v9Results .v9-recovery-panel-head h5 { margin: 0; color: var(--text1); font-size: 11px; }
#tab-v9Results .v9-recovery-panel-head p { margin: 4px 0 0; color: var(--text2); font-size: 10px; line-height: 1.4; }
#tab-v9Results .v9-recovery-factor-list { display: grid; gap: 1px; background: var(--border); }
#tab-v9Results .v9-recovery-factor { width: 100%; min-width: 0; padding: 10px 12px; border: 0; background: var(--surface); color: var(--text2); text-align: left; cursor: pointer; }
#tab-v9Results .v9-recovery-factor[aria-pressed="true"] { box-shadow: inset 3px 0 0 var(--accent); background: var(--accent-soft); }
#tab-v9Results .v9-recovery-factor strong { display: block; min-width: 0; color: var(--text1); font-size: 10px; line-height: 1.35; overflow-wrap: anywhere; word-break: break-word; }
#tab-v9Results .v9-recovery-factor span { display: block; margin-top: 4px; color: var(--text2); font-family: var(--font-mono); font-size: 10px; }
#tab-v9Results .v9-recovery-narrative { margin-top: 12px; padding: 13px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); }
#tab-v9Results .v9-recovery-narrative h5 { margin: 0 0 8px; color: var(--text1); font-size: 11px; }
#tab-v9Results .v9-recovery-narrative p { margin: 6px 0; color: var(--text2); font-size: 11px; line-height: 1.55; }
#tab-v9Results .v9-attribution-panel { margin-top: 12px; padding: 13px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); }
#tab-v9Results .v9-attribution-panel h5 { margin: 0 0 4px; color: var(--text1); font-size: 11px; }
#tab-v9Results .v9-attribution-caveat { margin: 0 0 10px; color: var(--text2); font-size: 10px; line-height: 1.45; }
#tab-v9Results .v9-attribution-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
#tab-v9Results .v9-attribution-section { min-width: 0; padding: 10px; border: 1px solid var(--border); border-radius: 7px; background: var(--elevated); }
#tab-v9Results .v9-attribution-section h6 { margin: 0 0 8px; color: var(--text1); font-size: 10px; letter-spacing: .04em; text-transform: uppercase; }
#tab-v9Results .v9-attribution-row { display: grid; gap: 5px; padding: 7px 0; border-top: 1px solid var(--border); color: var(--text2); font-size: 10px; }
#tab-v9Results .v9-attribution-row:first-of-type { border-top: 0; padding-top: 0; }
#tab-v9Results .v9-attribution-row-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
#tab-v9Results .v9-attribution-rank { color: var(--accent-hover); font-family: var(--font-mono); font-size: 10px; font-weight: 700; }
#tab-v9Results .v9-attribution-id { min-width: 0; overflow-wrap: anywhere; color: var(--text1); font-family: var(--font-mono); }
#tab-v9Results .v9-attribution-connection { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; min-width: 0; }
#tab-v9Results .v9-attribution-relation { padding: 2px 5px; border: 1px solid var(--border-strong); border-radius: 999px; color: var(--accent-hover); font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
#tab-v9Results .v9-attribution-weight { color: var(--text1); font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-attribution-bar { height: 6px; overflow: hidden; border-radius: 999px; background: var(--sunk); }
#tab-v9Results .v9-attribution-bar-fill { display: block; height: 100%; border-radius: inherit; background: var(--accent); }
#tab-v9Results .v9-recovery-source-row { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
#tab-v9Results .v9-recovery-source { padding: 2px 5px; border: 1px solid var(--border); border-radius: 999px; color: var(--text2); font-family: var(--font-mono); font-size: 10px; }
#tab-v9Results .v9-recovery-toolbar { display:grid; grid-template-columns:repeat(auto-fit,minmax(178px,1fr)); gap:12px 14px; padding:13px 14px; border-bottom: 1px solid var(--border); background: var(--sunk); }
#tab-v9Results .v9-recovery-control-group { display:grid; gap:6px; align-content:start; min-width:0; }
#tab-v9Results .v9-recovery-control-label { color:var(--text2); font-size:9px; font-weight:700; letter-spacing:.09em; text-transform:uppercase; }
#tab-v9Results .v9-recovery-control-items { display:flex; flex-wrap:wrap; gap:4px; min-width:0; }
#tab-v9Results .v9-recovery-control-items .v9-recovery-button { min-height:36px; }
#tab-v9Results .v9-recovery-button { display:inline-flex; align-items:center; gap:6px; min-height: 29px; padding: 5px 9px; border: 1px solid var(--border-strong); border-radius: 6px; background: var(--surface); color: var(--text2); font: inherit; font-size: 10px; cursor: pointer; transition: background .14s ease, border-color .14s ease, color .14s ease; }
#tab-v9Results .v9-recovery-button:hover { color: var(--text1); border-color: var(--text2); background: var(--elevated); }
#tab-v9Results .v9-recovery-button[aria-pressed="true"] { border-color: var(--accent); background: var(--accent-soft); color: var(--accent-hover); box-shadow: inset 0 -2px 0 var(--accent); }
#tab-v9Results .v9-recovery-button-count { padding: 1px 5px; border-radius: 999px; background: rgba(255,255,255,.08); color: var(--text2); font-family: var(--font-mono); font-size: 9px; font-variant-numeric: tabular-nums; }
#tab-v9Results .v9-recovery-button[aria-pressed="true"] .v9-recovery-button-count { background: rgba(52,211,153,.2); color: var(--accent-hover); }
#tab-v9Results .v9-recovery-search { width: 100%; min-height: 36px; padding: 5px 8px; font-size: 10px; }
#tab-v9Results .v9-recovery-toolbar .v9-recovery-select { width: 100%; min-height: 36px; padding: 5px 8px; font-size: 10px; }
#tab-v9Results .v9-recovery-canvas-note { padding: 8px 12px; border-bottom: 1px solid var(--border); color: var(--text2); font-size: 10px; line-height: 1.4; }
#tab-v9Results .v9-recovery-canvas-note.is-fine-print { border-bottom: 0; border-top: 1px solid var(--border); color: var(--text2); font-size: 9px; opacity: .78; }
#tab-v9Results .v9-recovery-canvas-wrap { position: relative; height: 410px; min-height: 300px; background: var(--sunk); }
#tab-v9Results .v9-recovery-canvas { display: block; width: 100%; height: 100%; touch-action: none; cursor: grab; }
#tab-v9Results .v9-recovery-canvas:active { cursor: grabbing; }
#tab-v9Results .v9-recovery-case:focus-visible, #tab-v9Results .v9-recovery-factor:focus-visible, #tab-v9Results .v9-recovery-button:focus-visible, #tab-v9Results .v9-recovery-select:focus-visible, #tab-v9Results .v9-recovery-search:focus-visible, #tab-v9Results .v9-recovery-canvas:focus-visible { outline: 2px solid var(--accent-hover); outline-offset: 2px; }
#tab-v9Results .v9-recovery-empty { padding: 28px; border: 1px dashed var(--border-strong); border-radius: 9px; color: var(--text2); font-size: 12px; line-height: 1.55; text-align: center; }
#tab-v9Results .v9-recovery-loading { display: grid; gap: 12px; min-height: 520px; padding: 14px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }
#tab-v9Results .v9-recovery-skeleton { border-radius: 7px; background: var(--elevated); animation: v9-recovery-pulse 1.4s ease-in-out infinite; }
#tab-v9Results .v9-recovery-skeleton.is-graph { min-height: 390px; }
#tab-v9Results .v9-recovery-skeleton.is-copy { min-height: 54px; }
#tab-v9Results .v9-recovery-skeleton.is-copy.is-short { width: 64%; }
#tab-v9Results .v9-recovery-error, #tab-v9Results .v9-recovery-empty-state { padding: 24px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); color: var(--text2); }
#tab-v9Results .v9-recovery-error h4, #tab-v9Results .v9-recovery-empty-state h4 { margin: 0; color: var(--text1); font-size: 15px; }
#tab-v9Results .v9-recovery-error p, #tab-v9Results .v9-recovery-empty-state p { margin: 8px 0 0; color: var(--text2); font-size: 12px; line-height: 1.55; }
#tab-v9Results .v9-recovery-retry { margin-top: 12px; }
#tab-v9Results .v9-recovery-sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@keyframes v9-recovery-pulse { 0%, 100% { opacity: 1; } 50% { opacity: .55; } }
#tab-v9Results .v9-recovery-v3-grid { display: grid; grid-template-columns: 214px minmax(0, 1fr); gap: 16px; align-items: start; margin-top: 16px; }
#tab-v9Results .v9-recovery-v3-list { position: sticky; top: 16px; max-height: min(70vh, 720px); overflow-y: auto; display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; align-content: start; min-width: 0; padding: 12px; border: 1px solid var(--border); border-radius: 9px; background: var(--sunk); scrollbar-gutter: stable; }
#tab-v9Results .v9-recovery-v3-picker { display: none; width: 100%; min-height: 44px; box-sizing: border-box; border: 1px solid var(--border-strong); border-radius: 8px; background: var(--surface); color: var(--text1); padding: 9px 10px; font: inherit; }
#tab-v9Results .v9-recovery-v3-detail { display: grid; grid-template-columns: minmax(0, 1fr); gap: 8px; align-content: start; min-width: 0; }
#tab-v9Results .v9-recovery-v3-panel { padding: 12px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); }
#tab-v9Results .v9-recovery-v3-panel h5 { margin: 0 0 7px; color: var(--text1); }
#tab-v9Results .v9-recovery-graph-panel { min-width: 0; overflow: hidden; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); }
#tab-v9Results .v9-recovery-legend { display: flex; flex-wrap: wrap; gap: 5px; margin: 8px 0; }
#tab-v9Results .v9-recovery-legend-item { display: inline-flex; align-items: center; gap: 6px; min-height: 24px; padding: 3px 9px 3px 7px; border: 1px solid var(--border); border-radius: 999px; color: var(--text2); font-size: 10px; line-height: 1.25; white-space: nowrap; }
#tab-v9Results .v9-recovery-legend-swatch { display: inline-block; flex: 0 0 auto; width: 18px; height: 8px; border-radius: 999px; background: #7f8798; box-shadow: 0 0 0 1px rgba(255,255,255,.2); }
#tab-v9Results .v9-recovery-legend-swatch.is-cotravel { height:3px; background:#34d399; box-shadow:none; }
#tab-v9Results .v9-recovery-legend-swatch.is-residence { height:3px; background:repeating-linear-gradient(90deg,#60a5fa 0 8px,transparent 8px 13px); box-shadow:none; }
#tab-v9Results .v9-recovery-legend-swatch.is-shared-plate { height:3px; background:repeating-linear-gradient(90deg,#a78bfa 0 3px,transparent 3px 8px); box-shadow:none; }
#tab-v9Results .v9-recovery-legend-swatch.is-other-relation { height:3px; background:repeating-linear-gradient(90deg,#8b8b96 0 11px,transparent 11px 17px); box-shadow:none; }
#tab-v9Results .v9-recovery-legend-swatch.is-attributed-node { width:10px; height:10px; border:2px solid #fbbf24; border-radius:50%; background:transparent; box-shadow:none; }
#tab-v9Results .v9-recovery-legend-swatch.is-evidence { height:9px; background:#fbbf24; box-shadow:none; opacity:.72; }
#tab-v9Results .v9-recovery-legend-swatch.is-target { width: 10px; height: 10px; border: 2px solid #34d399; border-radius: 50%; background: transparent; }
#tab-v9Results .v9-recovery-legend-swatch.is-caught { width: 10px; height: 10px; border-radius: 50%; background: #60a5fa; }
#tab-v9Results .v9-recovery-sampled { display: inline-block; margin: 8px 9px 0; padding: 4px 8px; border: 1px solid rgba(251,191,36,.42); border-radius: 999px; background: rgba(251,191,36,.1); color: #fbbf24; font-size: 10px; font-weight: 700; line-height: 1.35; }
#tab-v9Results .v9-recovery-v3 .v9-recovery-canvas-wrap { height: clamp(460px, 58vh, 640px); min-height: 460px; background-color: #080d14; background-image: linear-gradient(rgba(255,255,255,.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.03) 1px, transparent 1px), linear-gradient(155deg, #0b131d, #070c13 60%, #0d1420); background-size: 34px 34px, 34px 34px, auto; box-shadow: inset 0 1px 0 rgba(255,255,255,.06), inset 0 0 90px rgba(0,0,0,.5); }
#tab-v9Results .v9-recovery-v3 .v9-recovery-canvas { background: transparent; }
#tab-v9Results .v9-recovery-v3 .v9-recovery-legend { padding: 6px 11px; margin: 0; border-top: 1px solid rgba(255,255,255,.08); border-bottom: 1px solid rgba(255,255,255,.08); background: rgba(5,10,16,.62); }
#tab-v9Results .v9-recovery-v3 .v9-recovery-legend-item { border-color: rgba(255,255,255,.16); background: rgba(255,255,255,.05); color: #d5d9e2; }
#tab-v9Results .v9-recovery-explanation-row { display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; margin-top: 14px; }
#tab-v9Results .v9-recovery-explanation-row > * { min-width: 0; }
#tab-v9Results .v9-recovery-disclosures { display: grid; gap: 8px; margin-top: 14px; }
#tab-v9Results .v9-recovery-disclosure { overflow: hidden; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); }
#tab-v9Results .v9-recovery-disclosure-summary { display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 44px; padding: 11px 14px; color: var(--text1); font-size: 11px; font-weight: 600; cursor: pointer; list-style: none; transition: background .16s ease, color .16s ease, transform .08s ease; }
#tab-v9Results .v9-recovery-disclosure-summary::-webkit-details-marker { display: none; }
#tab-v9Results .v9-recovery-disclosure-summary::marker { content: ''; }
#tab-v9Results .v9-recovery-disclosure-summary::after { content: '+'; color: var(--accent); font-family: var(--font-mono); font-size: 16px; line-height: 1; }
#tab-v9Results .v9-recovery-disclosure[open] .v9-recovery-disclosure-summary::after { content: '-'; }
#tab-v9Results .v9-recovery-disclosure-summary:hover { background: var(--accent-soft); color: var(--accent-hover); }
#tab-v9Results .v9-recovery-disclosure-summary:active { transform: translateY(1px); }
#tab-v9Results .v9-recovery-disclosure-summary:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
#tab-v9Results .v9-recovery-disclosure-body { padding: 0 14px 14px; }
#tab-v9Results .v9-recovery-v3 button:focus:not(:focus-visible), #tab-v9Results .v9-recovery-v3 input:focus:not(:focus-visible), #tab-v9Results .v9-recovery-v3 select:focus:not(:focus-visible), #tab-v9Results .v9-recovery-v3 canvas:focus:not(:focus-visible) { outline: none; }
#tab-v9Results .v9-recovery-table-wrap { margin-top: 12px; overflow-x: auto; }
#tab-v9Results .v9-recovery-table-wrap h6 { margin: 0 0 4px; color: var(--text1); font-size: 11px; }
#tab-v9Results .v9-recovery-table { width: 100%; border-collapse: collapse; color: var(--text2); font-size: 10px; }
#tab-v9Results .v9-recovery-table th, #tab-v9Results .v9-recovery-table td { padding: 5px 8px; border-bottom: 1px solid var(--border); text-align: left; white-space: nowrap; }
#tab-v9Results .v9-recovery-table th { color: var(--text1); font-weight: 600; }
#tab-v9Results .v9-recovery-pager { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 8px 0 14px; color: var(--text2); font-size: 10px; }
#tab-v9Results .v9-recovery-pager .v9-recovery-button { min-height: 44px; }
@media(max-width:900px){
  #tab-v9Results .v9-recovery-header { grid-template-columns: 1fr; }
  #tab-v9Results .v9-recovery-scope { max-width: none; text-align: left; }
  #tab-v9Results .v9-recovery-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  #tab-v9Results .v9-recovery-v3-grid { grid-template-columns: 1fr; }
  #tab-v9Results .v9-recovery-v3-list { display: none; }
  #tab-v9Results .v9-recovery-v3-picker { display: block; margin-bottom: 12px; }
  #tab-v9Results .v9-recovery-v3 .v9-recovery-canvas-wrap { height: clamp(360px, 48vh, 470px); min-height: 360px; }
  #tab-v9Results .v9-recovery-evidence-grid { grid-template-columns: minmax(0, 1fr); }
}
@media(max-width:700px){
  #tab-v9Results .v9-recovery { margin: 24px 0; padding: 20px 0 24px; }
  #tab-v9Results .v9-recovery-header { padding: 18px; }
  #tab-v9Results .v9-recovery-header, #tab-v9Results .v9-recovery-case-header { display: block; }
  #tab-v9Results .v9-recovery-scope { max-width: none; margin-top: 12px; }
  #tab-v9Results .v9-recovery-summary { grid-template-columns: 1fr; }
  #tab-v9Results .v9-recovery-evidence-grid, #tab-v9Results .v9-attribution-grid { grid-template-columns: 1fr; }
  #tab-v9Results .v9-recovery-ranks { margin-top: 12px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  #tab-v9Results .v9-recovery-rank { min-height: 68px; padding: 11px 12px; }
  #tab-v9Results .v9-recovery-explanation-row { grid-template-columns: 1fr; }
  #tab-v9Results .v9-recovery-toolbar { grid-template-columns: 1fr; }
  #tab-v9Results .v9-recovery-control-items { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); }
  #tab-v9Results .v9-recovery-control-items > * { width:100%; min-width:0; }
  #tab-v9Results .v9-recovery-control-items .v9-recovery-button { min-height:44px; }
  #tab-v9Results .v9-recovery-toolbar > .v9-recovery-search, #tab-v9Results .v9-recovery-toolbar .v9-recovery-select { width:100%; min-width:0; }
  #tab-v9Results .v9-recovery-button, #tab-v9Results .v9-recovery-toolbar .v9-recovery-select, #tab-v9Results .v9-recovery-search { min-height: 44px; }
  #tab-v9Results .v9-recovery-canvas-wrap { height: 340px; }
  #tab-v9Results .v9-recovery-v3 .v9-recovery-canvas-wrap { height: 340px; min-height: 300px; }
}
@media(max-width:700px){
  #tab-v9Results .v9-recovery-v3 .v9-recovery-canvas-wrap { height: 340px; min-height: 300px; }
}
@media(max-width:359px){
  #tab-v9Results .v9-recovery-ranks { grid-template-columns: 1fr; }
  #tab-v9Results .v9-recovery-rank-delta { grid-column: 1; }
}
@media(prefers-reduced-motion: reduce){
  #tab-v9Results .v9-recovery-skeleton { animation: none; }
  #tab-v9Results .v9-recovery-v3 *, #tab-v9Results .v9-recovery-v3 *::before, #tab-v9Results .v9-recovery-v3 *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; }
}
"""


V9_RECOVERY_EXPLAINER_JS = r"""
function recoveryFormatNumber(value){
  if(value===null||value===undefined||value==='')return 'not available';
  const number=Number(value);
  if(!Number.isFinite(number))return 'not available';
  if(Object.is(number,-0))return '0';
  return new Intl.NumberFormat('en-US',{
    maximumFractionDigits:3,
    useGrouping:true
  }).format(number);
}

function recoveryFormatSigned(value){
  if(value===null||value===undefined||value==='')return 'not available';
  const number=Number(value);
  if(!Number.isFinite(number))return 'not available';
  return (number>0?'+':'')+recoveryFormatNumber(number);
}

function recoveryFormatDateOnly(value){
  if(!recoveryNonBlankString(value))return 'not available';
  const trimmed=value.trim();
  return /^\d{4}-\d{2}-\d{2}(?:$|T)/.test(trimmed)
    ?trimmed.slice(0,10):'not available';
}

function recoveryCompactIdentifier(value){
  const identifier=recoveryNonBlankString(value)?value.trim():'';
  return identifier.length<=18
    ?identifier:identifier.slice(0,9)+'…'+identifier.slice(-6);
}

function recoveryRankDelta(record){
  return recoverySafeInteger(record&&record.baseline_rank,false)
    &&recoverySafeInteger(record&&record.seed0_hybrid_rank,false)
    ?record.baseline_rank-record.seed0_hybrid_rank:null;
}

function recoveryIsRecord(value){
  return value!==null&&typeof value==='object'&&!Array.isArray(value);
}

function recoveryNonBlankString(value){
  return typeof value==='string'&&value.trim().length>0;
}

function recoveryNormalizeCaseId(value){
  return recoveryNonBlankString(value)?value.trim():null;
}

function recoveryCanonicalCaseId(value){
  return recoveryNonBlankString(value)&&value===value.trim()?value:null;
}

function recoveryUniqueStrings(value){
  return Array.isArray(value)&&value.every(recoveryNonBlankString)
    &&new Set(value).size===value.length;
}

function recoverySourceRefs(value){
  return recoveryUniqueStrings(value)&&value.length>0;
}

function recoveryAllowedSourceRef(value){
  return recoveryNonBlankString(value)&&[
    /^scope\.observability_seed$/,
    /^ranks\.(?:baseline|seed0_gnn|seed0_hybrid)$/,
    /^attributions\.(?:top_local_nodes\.0\.(?:node_id|explainer_median)|top_edges\.0\.(?:edge_id|explainer_median)|top_features\.0\.(?:feature_name|node_id|explainer_median))$/,
    /^component_pooling\.top_members_by_absolute_contribution\.0\.(?:person_id|pooled_logit_contribution)$/,
    /^rank_fusion\.(?:blend_weight|baseline_weighted_term|seed0_gnn_weighted_term|hybrid_score|daily_budget)$/,
    /^factors_by_id\.[^.]+\.(?:label|stability|counterfactual\.(?:original_hybrid_rank|ablated_hybrid_rank))$/,
    /^visible_paths\.(?:0|[1-9][0-9]*)\.(?:relation|u|v)$/,
    /^caveats\.[12]$/
  ].some(pattern=>pattern.test(value));
}

function recoveryCompareId(left,right){
  return left<right?-1:(left>right?1:0);
}

function recoverySafeInteger(value,allowNegative){
  return typeof value==='number'&&Number.isSafeInteger(value)
    &&(allowNegative===true||value>=0);
}

function recoveryUnavailable(reason){
  return {available:false,reason};
}

function validateRecoveryNarrative(narrative){
  if(!recoveryIsRecord(narrative)||narrative.validated!==true){
    return {visible:false,reason:'unvalidated'};
  }
  if(!recoveryNonBlankString(narrative.summary)
      ||!recoverySourceRefs(narrative.summary_source_refs)
      ||!narrative.summary_source_refs.every(recoveryAllowedSourceRef)){
    return {visible:false,reason:'missing-summary-sources'};
  }
  if(!Array.isArray(narrative.claims)){
    return {visible:false,reason:'invalid-claims'};
  }
  const validClaims=narrative.claims.every(claim=>recoveryIsRecord(claim)
    &&recoveryNonBlankString(claim.text)
    &&recoverySourceRefs(claim.source_refs)
    &&claim.source_refs.every(recoveryAllowedSourceRef));
  if(!validClaims){
    return {visible:false,reason:'missing-claim-sources'};
  }
  const validProvenance=(narrative.source==='llm'
      &&narrative.model==='gemma4:12b'
      &&narrative.prompt_version==='v4')
    ||(narrative.source==='deterministic_template'
      &&narrative.model===null
      &&narrative.prompt_version==='v1');
  if(!validProvenance){
    return {visible:false,reason:'invalid-narrative-metadata'};
  }
  return {
    visible:true,
    summary:narrative.summary,
    summarySourceRefs:narrative.summary_source_refs.slice(),
    claims:narrative.claims.map(claim=>({
      text:claim.text,
      source_refs:claim.source_refs.slice()
    })),
    source:narrative.source,
    model:narrative.model||null
  };
}

function recoveryAttributionRank(value){
  return Number.isSafeInteger(value)&&value>0?value:null;
}

function recoveryAttributionRows(records,kind){
  if(records===undefined) return [];
  if(!Array.isArray(records)) return null;
  const rows=[];
  for(const record of records){
    if(!recoveryIsRecord(record)||!recoveryFiniteUnit(record.explainer_median)){
      continue;
    }
    const rank=recoveryAttributionRank(record.rank);
    if(kind==='node'){
      if(!recoveryNonBlankString(record.node_id)) continue;
      rows.push({
        rank,
        id:record.node_id.trim(),
        weight:record.explainer_median
      });
    }else{
      const relation=recoveryNonBlankString(record.relation)
        ?record.relation.trim():recoveryNonBlankString(record.edge_type)
          ?record.edge_type.trim():null;
      if(!recoveryNonBlankString(record.edge_id)
          ||!recoveryNonBlankString(record.u)
          ||!recoveryNonBlankString(record.v)
          ||!relation) continue;
      rows.push({
        rank,
        id:record.edge_id.trim(),
        u:record.u.trim(),
        v:record.v.trim(),
        relation,
        weight:record.explainer_median
      });
    }
  }
  const useRanks=rows.length>0&&rows.every(row=>row.rank!==null)
    &&new Set(rows.map(row=>row.rank)).size===rows.length;
  rows.sort((left,right)=>useRanks
    ?left.rank-right.rank||recoveryCompareId(left.id,right.id)
    :right.weight-left.weight||recoveryCompareId(left.id,right.id));
  return rows.slice(0,5).map((row,index)=>kind==='node'?{
    rank:index+1,
    nodeId:row.id,
    weight:row.weight
  }:{
    rank:index+1,
    edgeId:row.id,
    u:row.u,
    v:row.v,
    relation:row.relation,
    weight:row.weight
  });
}

function buildHighestAttributionViewModel(explanation){
  const attributions=recoveryIsRecord(explanation)?explanation.attributions:null;
  if(!recoveryIsRecord(attributions)){
    return recoveryUnavailable('no-valid-attribution-ranking');
  }
  const nodes=recoveryAttributionRows(attributions.top_local_nodes,'node');
  const connections=recoveryAttributionRows(attributions.top_edges,'edge');
  if(nodes===null||connections===null){
    return recoveryUnavailable('no-valid-attribution-ranking');
  }
  if(nodes.length===0&&connections.length===0){
    return recoveryUnavailable('no-valid-attribution-ranking');
  }
  return {available:true,nodes,connections};
}

function recoveryAttributionBar(doc,weight,label){
  const bar=recoveryElement(doc,'div','v9-attribution-bar');
  bar.setAttribute('role','progressbar');
  bar.setAttribute('aria-label',label);
  bar.setAttribute('title',label);
  bar.setAttribute('aria-valuemin','0');
  bar.setAttribute('aria-valuemax','1');
  bar.setAttribute('aria-valuenow',String(weight));
  const fill=recoveryElement(doc,'span','v9-attribution-bar-fill');
  fill.style.width=String(weight*100)+'%';
  bar.appendChild(fill);
  return bar;
}

function renderHighestAttributionPanel(doc,explanation){
  const panel=recoveryElement(doc,'section','v9-attribution-panel');
  panel.setAttribute('aria-label','Highest-attribution evidence');
  panel.appendChild(recoveryElement(doc,'h5','', 'Highest-attribution evidence'));
  panel.appendChild(recoveryElement(doc,'p','v9-attribution-caveat',
    'Shows the top 5 nodes and top 5 connections with normalized unsigned median salience weights across deterministic explainer restarts, not causal direction.'));
  const view=buildHighestAttributionViewModel(explanation);
  if(!view.available){
    panel.appendChild(recoveryElement(doc,'div','v9-recovery-status',
      'Attribution ranking unavailable in this artifact.'));
    return panel;
  }
  const grid=recoveryElement(doc,'div','v9-attribution-grid');
  const sections=[['Nodes',view.nodes],['Connections',view.connections]];
  for(const [title,rows] of sections){
    const section=recoveryElement(doc,'section','v9-attribution-section');
    section.appendChild(recoveryElement(doc,'h6','',title));
    if(!rows.length){
      section.appendChild(recoveryElement(doc,'div','v9-recovery-status',
        'No valid ranked data is available.'));
    }
    for(const row of rows){
      const item=recoveryElement(doc,'div','v9-attribution-row');
      const head=recoveryElement(doc,'div','v9-attribution-row-head');
      const fullLabel=title==='Nodes'?row.nodeId:
        row.relation+' · '+row.u+' ↔ '+row.v+' · edge '+row.edgeId;
      const identifier=recoveryElement(doc,'div','v9-attribution-connection');
      identifier.setAttribute('title',fullLabel);
      identifier.appendChild(recoveryElement(doc,'span','v9-attribution-rank',
        '#'+recoveryFormatNumber(row.rank)));
      if(title==='Nodes'){
        identifier.appendChild(recoveryElement(doc,'span','v9-attribution-id',row.nodeId));
      }else{
        identifier.appendChild(recoveryElement(doc,'span','v9-attribution-relation',row.relation));
        const endpoints=recoveryElement(doc,'span','v9-attribution-id',
          recoveryCompactIdentifier(row.u)+' ↔ '+recoveryCompactIdentifier(row.v));
        endpoints.setAttribute('title',row.u+' ↔ '+row.v);
        identifier.appendChild(endpoints);
      }
      head.appendChild(identifier);
      head.appendChild(recoveryElement(doc,'span','v9-attribution-weight',
        recoveryFormatNumber(row.weight)));
      item.appendChild(head);
      item.appendChild(recoveryAttributionBar(doc,row.weight,
        title==='Nodes'
          ?'Nodes attribution weight for '+row.nodeId
          :'Connections attribution weight for '+row.u+' ↔ '+row.v
            +' relation '+row.relation+' edge '+row.edgeId));
      item.setAttribute('title',fullLabel);
      section.appendChild(item);
    }
    grid.appendChild(section);
  }
  panel.appendChild(grid);
  return panel;
}

function validateRecoveryEvidenceBoundary(explanation,scoringDay){
  const boundary=recoveryIsRecord(explanation)
    ?explanation.evidence_boundary:null;
  const valid=recoveryIsRecord(boundary)
    &&boundary.snapshot===scoringDay
    &&boundary.edge_rule==='available_time < snapshot'
    &&boundary.caught_rule==='label_available_time_utc < snapshot';
  if(!valid) return recoveryUnavailable('invalid-evidence-boundary');
  return {
    available:true,
    snapshot:boundary.snapshot,
    edgeRule:boundary.edge_rule,
    caughtRule:boundary.caught_rule
  };
}

function buildCommunityStageView(explanation,options){
  if(!recoveryIsRecord(explanation)
      ||!recoveryNonBlankString(explanation.person_id)
      ||!recoveryIsRecord(explanation.community)
      ||explanation.community.complete!==true){
    return recoveryUnavailable('incomplete-community');
  }
  const settings=recoveryIsRecord(options)?options:{};
  const validModes=['all','flow'];
  const validStages=['first_hop','second_hop','component_pool','rank_fusion'];
  if(!validModes.includes(settings.mode)||!validStages.includes(settings.stageId)){
    return recoveryUnavailable('invalid-view-options');
  }
  const community=explanation.community;
  if(!Array.isArray(community.nodes)||!Array.isArray(community.edges)){
    return recoveryUnavailable('invalid-community-membership');
  }
  const validNodes=community.nodes.every(node=>recoveryIsRecord(node)
    &&recoveryNonBlankString(node.node_id));
  const validEdges=community.edges.every(edge=>recoveryIsRecord(edge)
    &&recoveryNonBlankString(edge.edge_id)
    &&recoveryNonBlankString(edge.u)
    &&recoveryNonBlankString(edge.v));
  if(!validNodes||!validEdges){
    return recoveryUnavailable('invalid-community-membership');
  }
  const nodeIds=community.nodes.map(node=>node.node_id);
  const edgeIds=community.edges.map(edge=>edge.edge_id);
  const nodeSet=new Set(nodeIds);
  if(nodeIds.length===0||!nodeSet.has(explanation.person_id)
      ||nodeSet.size!==nodeIds.length||new Set(edgeIds).size!==edgeIds.length
      ||community.edges.some(edge=>!nodeSet.has(edge.u)||!nodeSet.has(edge.v))){
    return recoveryUnavailable('invalid-community-membership');
  }
  return {
    available:true,
    nodeIds:nodeIds.slice().sort(),
    edgeIds:edgeIds.slice().sort(),
    mode:settings.mode,
    stageId:settings.stageId,
    selectedFactorId:recoveryNonBlankString(settings.selectedFactorId)
      ?settings.selectedFactorId:null,
    query:typeof settings.query==='string'?settings.query:''
  };
}

function recoveryFiniteUnit(value){
  return typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=1;
}

function recoverySameIds(values,expected){
  return recoveryUniqueStrings(values)
    &&values.slice().sort().join('\u0000')===expected.slice().sort().join('\u0000');
}

function recoveryValidStageRule(stage,nodeIds,edgeIds){
  if(!recoveryIsRecord(stage.edge_rule)){
    return recoverySameIds(stage.node_ids,nodeIds)
      &&recoverySameIds(stage.edge_ids,edgeIds)
      &&recoveryUniqueStrings(stage.emphasized_edge_ids)
      &&stage.emphasized_edge_ids.every(id=>edgeIds.includes(id));
  }
  if(stage.node_ids!==undefined||stage.edge_ids!==undefined
      ||stage.emphasized_edge_ids!==undefined) return false;
  const rule=stage.edge_rule;
  if(stage.stage_id==='first_hop') return rule.max_message_hop===1;
  if(stage.stage_id==='second_hop') return rule.max_message_hop===2;
  if(stage.stage_id==='component_pool') return rule.edge_type==='COTRAVEL'
    &&rule.both_pooled_members===true;
  return stage.stage_id==='rank_fusion'&&rule.match_none===true;
}

function recoveryStageEmphasizes(stage,edge,nodesById){
  if(Array.isArray(stage.emphasized_edge_ids)){
    return stage.emphasized_edge_ids.includes(edge.edge_id);
  }
  const rule=stage.edge_rule;
  if(rule.match_none===true) return false;
  if(Number.isSafeInteger(rule.max_message_hop)){
    return Number.isSafeInteger(edge.message_hop)
      &&edge.message_hop<=rule.max_message_hop;
  }
  if(rule.edge_type==='COTRAVEL'&&rule.both_pooled_members===true){
    const left=nodesById.get(edge.u);
    const right=nodesById.get(edge.v);
    return String(edge.edge_type||'').toUpperCase()==='COTRAVEL'
      &&left&&right&&left.pooled_member===true&&right.pooled_member===true;
  }
  return false;
}

function buildRecoveryGraphSlice(fullNodes,fullEdges,personId){
  const tableNodes=Array.isArray(fullNodes)?fullNodes.slice():[];
  const tableEdges=Array.isArray(fullEdges)?fullEdges.slice():[];
  const nodeId=row=>recoveryNonBlankString(row&&row.node_id)
    ?row.node_id:recoveryNonBlankString(row&&row.id)?row.id:null;
  const edgeId=row=>recoveryNonBlankString(row&&row.edge_id)
    ?row.edge_id:recoveryNonBlankString(row&&row.id)?row.id:null;
  const endpoint=row=>recoveryNonBlankString(row)?row:null;
  const sortedNodes=tableNodes.slice().sort((left,right)=>
    recoveryCompareId(String(nodeId(left)||''),String(nodeId(right)||'')));
  const sortedEdges=tableEdges.slice().sort((left,right)=>
    recoveryCompareId(String(edgeId(left)||''),String(edgeId(right)||'')));
  const selectedNodeIds=new Set();
  const attributedNodeIds=new Set();
  for(const node of tableNodes){
    const id=nodeId(node);
    if(!id)continue;
    if(id===personId)selectedNodeIds.add(id);
    if(node&&node.attributed===true){
      attributedNodeIds.add(id);selectedNodeIds.add(id);
    }
  }
  const attributedEdgeIds=new Set();
  for(const edge of tableEdges){
    if(!edge||edge.attributed!==true)continue;
    const id=edgeId(edge);
    if(id)attributedEdgeIds.add(id);
    const left=endpoint(edge.u);const right=endpoint(edge.v);
    if(left)selectedNodeIds.add(left);
    if(right)selectedNodeIds.add(right);
  }
  const sampled=tableNodes.length>RECOVERY_GRAPH_NODE_LIMIT
    ||tableEdges.length>RECOVERY_GRAPH_EDGE_LIMIT;
  if(selectedNodeIds.size>RECOVERY_GRAPH_NODE_LIMIT){
    return {
      available:false,
      reason:'mandatory-evidence-node-limit-exceeded',
      sampled,
      fullNodeCount:tableNodes.length,
      fullEdgeCount:tableEdges.length,
      nodes:[],
      edges:[],
      tableNodes,
      tableEdges
    };
  }
  for(const node of sortedNodes){
    if(selectedNodeIds.size>=RECOVERY_GRAPH_NODE_LIMIT)break;
    const id=nodeId(node);
    if(id)selectedNodeIds.add(id);
  }
  const visibleNodes=sortedNodes.filter(node=>selectedNodeIds.has(nodeId(node)));
  const visibleNodeIds=new Set(visibleNodes.map(node=>nodeId(node)));
  const selectedEdgeIds=new Set();
  for(const edge of sortedEdges){
    const id=edgeId(edge);
    if(!id)continue;
    const attributed=attributedEdgeIds.has(id);
    if(attributed&&visibleNodeIds.has(edge.u)&&visibleNodeIds.has(edge.v)
        &&selectedEdgeIds.size<RECOVERY_GRAPH_EDGE_LIMIT){
      selectedEdgeIds.add(id);
    }
  }
  for(const edge of sortedEdges){
    if(selectedEdgeIds.size>=RECOVERY_GRAPH_EDGE_LIMIT)break;
    const id=edgeId(edge);
    if(!id||attributedEdgeIds.has(id)
        ||!visibleNodeIds.has(edge&&edge.u)
        ||!visibleNodeIds.has(edge&&edge.v))continue;
    selectedEdgeIds.add(id);
  }
  const visibleEdges=sortedEdges.filter(edge=>selectedEdgeIds.has(edgeId(edge)));
  return {
    available:true,
    sampled,
    fullNodeCount:tableNodes.length,
    fullEdgeCount:tableEdges.length,
    nodes:visibleNodes,
    edges:visibleEdges,
    tableNodes,
    tableEdges
  };
}

function filterRecoveryStageSlice(slice,stageEdgeIds,personId){
  const edges=slice.edges.filter(edge=>stageEdgeIds.has(edge.edge_id));
  const nodeIds=new Set([personId]);
  for(const edge of edges){
    nodeIds.add(edge.u);nodeIds.add(edge.v);
  }
  return {
    ...slice,
    nodes:slice.nodes.filter(node=>nodeIds.has(node.id||node.node_id)),
    edges
  };
}

function buildCommunityDrawCommands(explanation,options){
  const stageView=buildCommunityStageView(explanation,options);
  if(!stageView.available) return stageView;
  const community=explanation.community;
  if(!community.nodes.every(node=>recoveryFiniteUnit(node.x)
      &&recoveryFiniteUnit(node.y))){
    return recoveryUnavailable('invalid-community-coordinates');
  }
  const requiredStages=['first_hop','second_hop','component_pool','rank_fusion'];
  if(!Array.isArray(explanation.flow_stages)
      ||explanation.flow_stages.length!==requiredStages.length){
    return recoveryUnavailable('invalid-flow-stages');
  }
  const stagesById=new Map();
  for(const stage of explanation.flow_stages){
    if(!recoveryIsRecord(stage)||!requiredStages.includes(stage.stage_id)
        ||stagesById.has(stage.stage_id)
        ||!recoveryValidStageRule(stage,stageView.nodeIds,stageView.edgeIds)){
      return recoveryUnavailable('invalid-flow-stages');
    }
    stagesById.set(stage.stage_id,stage);
  }
  if(requiredStages.some(id=>!stagesById.has(id))){
    return recoveryUnavailable('invalid-flow-stages');
  }
  const selectedStage=stagesById.get(stageView.stageId);
  const nodesById=new Map(community.nodes.map(node=>[node.node_id,node]));
  const stageEdgeIds=new Set((stageView.stageId==='first_hop'
    ||stageView.stageId==='second_hop'
    ?community.edges.filter(edge=>
      recoveryStageEmphasizes(selectedStage,edge,nodesById))
    :community.edges)
    .map(edge=>edge.edge_id));
  const overlayNodes=Array.isArray(explanation.overlayNodes)
    ?explanation.overlayNodes:[];
  const overlayEdges=Array.isArray(explanation.overlayEdges)
    ?explanation.overlayEdges:[];
  const overlayNodesById=new Map(overlayNodes.map(node=>[
    node&&node.node_id,node
  ]));
  const overlayEdgesById=new Map(overlayEdges.map(edge=>[
    edge&&edge.edge_id,edge
  ]));
  const query=stageView.query.trim().toLowerCase();
  const importanceFor=row=>recoveryFiniteUnit(row&&row.importance)
    ?row.importance:recoveryFiniteUnit(row&&row.explainer_median)
      ?row.explainer_median:0;
  const nodes=community.nodes.map(node=>{
    const overlay=overlayNodesById.get(node.node_id);
    const distance=Number(node.message_distance);
    return {
      node_id:node.node_id,
      id:node.node_id,
      // Payload x/y is the fallback; the hop-ring pass below overwrites it
      // whenever message_distance is available.
      x:node.x,
      y:node.y,
      message_distance:node.message_distance,
      hop:Number.isFinite(distance)?Math.trunc(distance):null,
      target:node.node_id===explanation.person_id,
      pooledMember:node.pooled_member===true,
      caughtBeforeSnapshot:node.caught_before_snapshot===true,
      importance:importanceFor(overlay||node),
      attributed:overlay?overlay.attributed===true:node.attributed===true,
      rank:overlay&&Number.isSafeInteger(overlay.rank)?overlay.rank
        :(Number.isSafeInteger(node.rank)?node.rank:null),
      matched:query.length>0&&node.node_id.toLowerCase().includes(query)
    };
  });
  const edges=community.edges.map(edge=>{
    const overlay=overlayEdgesById.get(edge.edge_id);
    const attributed=overlay?overlay.attributed===true:edge.attributed===true;
    return {
      edge_id:edge.edge_id,
      id:edge.edge_id,
      u:edge.u,
      v:edge.v,
      relation:recoveryNonBlankString(edge.edge_type)?edge.edge_type:'RELATION',
      importance:importanceFor(overlay||edge),
      attributed,
      rank:overlay&&Number.isSafeInteger(overlay.rank)?overlay.rank
        :(Number.isSafeInteger(edge.rank)?edge.rank:null),
      emphasized:stageView.mode==='all'||attributed
        ||stageEdgeIds.has(edge.edge_id)
    };
  });
  const slice=buildRecoveryGraphSlice(nodes,edges,explanation.person_id);
  if(!slice.available) return slice;
  // Published x/y from the chunked sidecars is a sqrt(N) grid indexed by sorted
  // node_id, so position encodes alphabetical rank and every edge is a line
  // between two unrelated cells. Recompute the hop rings here so already
  // published artifacts read structurally without being regenerated.
  //
  // Lay out over the bounded projection that can actually be drawn
  // (slice.nodes), not over the complete row set (slice.tableNodes) and not
  // over community.nodes: rings sized for a 35k-member community leave the few
  // hundred drawn nodes in slivers of one hopelessly overcrowded ring. Rows are
  // shared by reference with the canvas slice below, so assigning here updates
  // every view, and positions stay put when the stage selection changes.
  const layout=recoveryHopRingLayout(slice.nodes,slice.edges);
  if(layout){
    for(const node of slice.nodes){
      const point=layout.get(node.id);
      if(point){node.x=point.x;node.y=point.y;}
    }
  }
  const canvasSlice=filterRecoveryStageSlice(
    slice,stageEdgeIds,explanation.person_id);

  const provenanceNodes=[];
  const provenanceEdges=[];
  if(stageView.selectedFactorId!==null){
    if(!Array.isArray(explanation.factors)){
      return recoveryUnavailable('invalid-selected-factor');
    }
    const factor=explanation.factors.find(item=>recoveryIsRecord(item)
      &&item.factor_id===stageView.selectedFactorId);
    if(!factor||!recoveryUniqueStrings(factor.provenance_expansion_ids)){
      return recoveryUnavailable('invalid-selected-factor');
    }
    if(!Array.isArray(community.provenance_expansions)){
      return recoveryUnavailable('invalid-provenance-expansion');
    }
    const expansionsById=new Map();
    for(const expansion of community.provenance_expansions){
      if(!recoveryIsRecord(expansion)
          ||!recoveryNonBlankString(expansion.expansion_id)
          ||expansionsById.has(expansion.expansion_id)){
        return recoveryUnavailable('invalid-provenance-expansion');
      }
      expansionsById.set(expansion.expansion_id,expansion);
    }
    const selectedExpansions=[];
    for(const expansionId of factor.provenance_expansion_ids){
      const expansion=expansionsById.get(expansionId);
      if(!expansion) return recoveryUnavailable('invalid-provenance-expansion');
      selectedExpansions.push(expansion);
    }
    const baseIds=new Set(nodes.map(node=>node.id));
    const availableIds=new Set(baseIds);
    const outsideById=new Map();
    for(const expansion of selectedExpansions){
      if(expansion.label!=='outside message community'
          ||!Array.isArray(expansion.nodes)||!Array.isArray(expansion.edges)){
        return recoveryUnavailable('invalid-provenance-expansion');
      }
      const localIds=new Set();
      for(const node of expansion.nodes){
        if(!recoveryIsRecord(node)||!recoveryNonBlankString(node.node_id)
            ||localIds.has(node.node_id)||!recoveryFiniteUnit(node.x)
            ||!recoveryFiniteUnit(node.y)){
          return recoveryUnavailable('invalid-provenance-expansion');
        }
        localIds.add(node.node_id);
        availableIds.add(node.node_id);
        if(!baseIds.has(node.node_id)){
          const existing=outsideById.get(node.node_id);
          if(existing&&(existing.x!==node.x||existing.y!==node.y)){
            return recoveryUnavailable('invalid-provenance-expansion');
          }
          outsideById.set(node.node_id,{id:node.node_id,x:node.x,y:node.y});
        }
      }
    }
    const provenanceEdgeIds=new Set();
    for(const expansion of selectedExpansions){
      for(const edge of expansion.edges){
        if(!recoveryIsRecord(edge)||!recoveryNonBlankString(edge.edge_id)
            ||!recoveryNonBlankString(edge.u)||!recoveryNonBlankString(edge.v)
            ||provenanceEdgeIds.has(edge.edge_id)
            ||!availableIds.has(edge.u)||!availableIds.has(edge.v)){
          return recoveryUnavailable('invalid-provenance-expansion');
        }
        provenanceEdgeIds.add(edge.edge_id);
        provenanceEdges.push({
          id:edge.edge_id,
          u:edge.u,
          v:edge.v,
          relation:recoveryNonBlankString(edge.edge_type)
            ?edge.edge_type:'RELATION',
          label:'outside message community',
          dashed:true
        });
      }
    }
    provenanceNodes.push(...Array.from(outsideById.values()).sort((a,b)=>
      recoveryCompareId(a.id,b.id)));
    provenanceEdges.sort((a,b)=>recoveryCompareId(a.id,b.id));
  }
  // Neighbour index for click-to-focus. Seeded with the node itself so a
  // focused node is always inside its own neighbourhood. Built over the
  // complete projection, not the stage-filtered canvas slice, so focusing does
  // not depend on which stage happens to be selected.
  const adjacency=new Map();
  for(const node of slice.nodes) adjacency.set(node.id,new Set([node.id]));
  for(const edge of slice.edges){
    if(adjacency.has(edge.u)&&adjacency.has(edge.v)){
      adjacency.get(edge.u).add(edge.v);
      adjacency.get(edge.v).add(edge.u);
    }
  }
  const hopCounts=new Map();
  for(const node of slice.tableNodes){
    const key=node.hop===null?'?':String(node.hop);
    hopCounts.set(key,(hopCounts.get(key)||0)+1);
  }
  const policy=recoveryIsRecord(community.projection_policy)
    ?community.projection_policy:{};
  const maxNodes=recoverySafeInteger(policy.max_nodes,false)?policy.max_nodes:null;
  const maxEdges=recoverySafeInteger(policy.max_edges,false)?policy.max_edges:null;
  return {
    available:true,
    mode:stageView.mode,
    stageId:stageView.stageId,
    nodes:canvasSlice.nodes,
    edges:canvasSlice.edges,
    tableNodes:slice.tableNodes,
    tableEdges:slice.tableEdges,
    sampled:slice.sampled,
    fullNodeCount:slice.fullNodeCount,
    fullEdgeCount:slice.fullEdgeCount,
    provenanceNodes,
    provenanceEdges,
    adjacency,
    layoutSource:layout?'hop_rings':'payload',
    stats:{
      nodeCount:slice.tableNodes.length,
      edgeCount:slice.tableEdges.length,
      emphasizedEdgeCount:slice.tableEdges.filter(edge=>edge.emphasized).length,
      hopCounts,
      maxNodes,
      maxEdges,
      // The projection bound is a cap, so hitting it exactly is the signal that
      // the community was larger than what is drawn.
      clipped:(maxNodes!==null&&slice.tableNodes.length>=maxNodes)
        ||(maxEdges!==null&&slice.tableEdges.length>=maxEdges)
    }
  };
}

function selectRecoveryEvidenceEdges(edges,limit){
  const rows=(Array.isArray(edges)?edges:[]).filter(edge=>
    edge&&edge.attributed===true&&recoveryFiniteUnit(edge.importance));
  const ranked=rows.length>0&&rows.every(edge=>
    Number.isSafeInteger(edge.rank)&&edge.rank>0)
    &&new Set(rows.map(edge=>edge.rank)).size===rows.length;
  rows.sort((left,right)=>ranked
    ?left.rank-right.rank||recoveryCompareId(left.id,right.id)
    :right.importance-left.importance||recoveryCompareId(left.id,right.id));
  return rows.slice(0,Math.max(0,Number.isSafeInteger(limit)?limit:3));
}

function recoveryEvidenceBounds(commands){
  const nodes=Array.isArray(commands&&commands.nodes)?commands.nodes:[];
  const byId=new Map(nodes.map(node=>[node.id,node]));
  const ids=new Set(nodes.filter(node=>node&&node.target===true).map(node=>node.id));
  for(const edge of Array.isArray(commands&&commands.edges)?commands.edges:[]){
    if(edge&&edge.attributed===true){ids.add(edge.u);ids.add(edge.v);}
  }
  let points=Array.from(ids).map(id=>byId.get(id)).filter(Boolean);
  if(points.length<2)points=nodes.slice();
  if(!points.length)return {minX:0,minY:0,maxX:1,maxY:1};
  const minX=Math.min(...points.map(point=>point.x));
  const maxX=Math.max(...points.map(point=>point.x));
  const minY=Math.min(...points.map(point=>point.y));
  const maxY=Math.max(...points.map(point=>point.y));
  return {
    minX:Math.max(0,Number((minX-0.08).toFixed(6))),
    minY:Math.max(0,Number((minY-0.08).toFixed(6))),
    maxX:Math.min(1,Number((maxX+0.08).toFixed(6))),
    maxY:Math.min(1,Number((maxY+0.08).toFixed(6)))
  };
}

function graphPoint(point,viewport){
  const width=Number(viewport.width);
  const height=Number(viewport.height);
  const padding=Number(viewport.padding);
  const scale=Number(viewport.scale);
  const offsetX=Number(viewport.offsetX);
  const offsetY=Number(viewport.offsetY);
  const bounds=recoveryIsRecord(viewport.bounds)
    ?viewport.bounds:{minX:0,minY:0,maxX:1,maxY:1};
  const spanX=Math.max(0.12,bounds.maxX-bounds.minX);
  const spanY=Math.max(0.12,bounds.maxY-bounds.minY);
  const normalizedX=(point.x-bounds.minX)/spanX;
  const normalizedY=(point.y-bounds.minY)/spanY;
  const baseX=padding+normalizedX*Math.max(0,width-padding*2);
  const baseY=padding+normalizedY*Math.max(0,height-padding*2);
  return {
    x:(baseX-width/2)*scale+width/2+offsetX,
    y:(baseY-height/2)*scale+height/2+offsetY
  };
}

function recoveryVisibleText(value){
  return String(value===null||value===undefined?'':value)
    .replace(/[\u2013\u2014]/g,'-').replace(/\u00b7/g,' / ');
}

function recoveryElement(doc,tag,className,text){
  const element=doc.createElement(tag);
  if(className) element.className=className;
  if(text!==undefined) element.textContent=recoveryVisibleText(text);
  return element;
}

function recoveryAppendSources(doc,parent,refs){
  const row=recoveryElement(doc,'div','v9-recovery-source-row');
  for(const ref of refs){
    row.appendChild(recoveryElement(doc,'span','v9-recovery-source',ref));
  }
  parent.appendChild(row);
}

function recoveryRelationPresentation(relation){
  const key=String(relation===null||relation===undefined?'':relation)
    .trim().toUpperCase();
  if(!key) return {key:'RELATION',label:'Relation',color:'#8b8b96',dash:[12,6]};
  const known={
    COTRAVEL:{label:'Co-travel',color:'#34d399',dash:[]},
    RESIDENCE:{label:'Residence',color:'#60a5fa',dash:[9,5]},
    SHARED_PLATE:{label:'Shared plate',color:'#a78bfa',dash:[2,5]},
    OTHER_LINK:{label:'Other link',color:'#8b8b96',dash:[12,6]}
  };
  if(known[key]) return {key,label:known[key].label,color:known[key].color,
    dash:known[key].dash.slice()};
  const words=key.split('_').filter(Boolean).map(word=>word.toLowerCase());
  const label=words.length
    ?words[0].charAt(0).toUpperCase()+words[0].slice(1)
      +(words.length>1?' '+words.slice(1).join(' '):'')
    :'';
  return {key,label,color:'#8b8b96',dash:[12,6]};
}

function recoveryRelationLegendDescription(relation){
  const key=String(relation===null||relation===undefined?'':relation)
    .trim().toUpperCase();
  const cue={
    COTRAVEL:'green solid line',
    RESIDENCE:'blue dashed line',
    SHARED_PLATE:'violet dotted line'
  }[key]||'gray long-dash line';
  return cue+': observable relationship type';
}

function recoveryRelationColor(relation){
  return recoveryRelationPresentation(relation).color;
}

function recoveryGraphRelationshipOptions(edges){
  const present=new Set();
  for(const edge of Array.isArray(edges)?edges:[]){
    const key=recoveryRelationPresentation(edge&&edge.relation).key;
    if(key) present.add(key);
  }
  const known=['COTRAVEL','RESIDENCE','SHARED_PLATE'];
  const ordered=known.filter(key=>present.has(key)).concat(
    Array.from(present).filter(key=>!known.includes(key)).sort());
  return [{key:'all',label:'All types'},...ordered.map(key=>({
    key,label:recoveryRelationPresentation(key).label
  }))];
}

function filterRecoveryGraphCommands(commands,relationship){
  const input=commands&&typeof commands==='object'?commands:{};
  const tableNodes=Array.isArray(input.tableNodes)?input.tableNodes.slice():[];
  const tableEdges=Array.isArray(input.tableEdges)?input.tableEdges.slice():[];
  const sourceNodes=Array.isArray(input.nodes)?input.nodes.slice():[];
  const sourceEdges=Array.isArray(input.edges)?input.edges.slice():[];
  const relationshipOptions=recoveryGraphRelationshipOptions(sourceEdges);
  const available=new Set(relationshipOptions.map(option=>option.key));
  const requestedRaw=String(relationship===null||relationship===undefined?'':relationship)
    .trim();
  const requested=requestedRaw==='all'?'all':requestedRaw.toUpperCase();
  const selected=available.has(requested)?requested:'all';
  const cloneArrays={...input,
    nodes:sourceNodes,edges:sourceEdges,tableNodes,tableEdges,
    provenanceNodes:Array.isArray(input.provenanceNodes)
      ?input.provenanceNodes.slice():[],
    provenanceEdges:Array.isArray(input.provenanceEdges)
      ?input.provenanceEdges.slice():[],
    relationship:selected,relationshipOptions};
  if(selected==='all') return cloneArrays;
  const filteredEdges=sourceEdges.filter(edge=>
    recoveryRelationPresentation(edge&&edge.relation).key===selected);
  const targetIds=new Set(sourceNodes.filter(node=>node&&node.target===true)
    .map(node=>node.id||node.node_id).filter(Boolean));
  const nodeIds=new Set(targetIds);
  for(const edge of filteredEdges){
    if(edge&&edge.u) nodeIds.add(edge.u);
    if(edge&&edge.v) nodeIds.add(edge.v);
  }
  return {...cloneArrays,
    nodes:sourceNodes.filter(node=>node&&nodeIds.has(node.id||node.node_id)),
    edges:filteredEdges,
    provenanceNodes:[],provenanceEdges:[]};
}

const RECOVERY_LAYOUT_RADIUS=0.46;
// A ring wider than this many nodes is split across concentric sub-rings.
const RECOVERY_LAYOUT_BAND_CAPACITY=120;
const RECOVERY_LAYOUT_MAX_BANDS=4;

function recoveryHopRingLayout(nodes,edges){
  // Mirror of display_hop_ring_layout in gnn/sage_explainer.py: target at the
  // centre, one ring per message_distance, each ring ordered so a node lands in
  // the arc belonging to its nearest-hop neighbour. Recomputed here rather than
  // trusted from the payload so artifacts published before the producer emitted
  // hop-ring coordinates still read structurally. Returns null when the inputs
  // cannot support a layout, and the caller then falls back to payload x/y.
  if(!Array.isArray(nodes)||nodes.length===0) return null;
  let target=null;
  for(const node of nodes){
    if(node.target===true){target=node.node_id;break;}
  }
  const ringOf=new Map();
  for(const node of nodes){
    const distance=Number(node.message_distance);
    if(!Number.isFinite(distance)) return null;
    ringOf.set(
      node.node_id,
      node.node_id===target?0:Math.max(1,Math.trunc(distance))
    );
  }
  const neighbours=new Map();
  for(const node of nodes) neighbours.set(node.node_id,new Set());
  for(const edge of Array.isArray(edges)?edges:[]){
    if(!ringOf.has(edge.u)||!ringOf.has(edge.v)||edge.u===edge.v) continue;
    neighbours.get(edge.u).add(edge.v);
    neighbours.get(edge.v).add(edge.u);
  }
  const byRing=new Map();
  for(const entry of ringOf){
    if(!byRing.has(entry[1])) byRing.set(entry[1],[]);
    byRing.get(entry[1]).push(entry[0]);
  }
  const maxRing=Math.max.apply(null,Array.from(byRing.keys()));
  const positions=new Map();
  const angles=new Map();
  for(const nodeId of byRing.get(0)||[]){
    positions.set(nodeId,{x:0.5,y:0.5});
    angles.set(nodeId,0);
  }
  for(let ring=1;ring<=maxRing;ring+=1){
    const ringNodes=(byRing.get(ring)||[]).slice().sort(recoveryCompareId);
    if(!ringNodes.length) continue;
    const groups=new Map();
    const orphans=[];
    for(const nodeId of ringNodes){
      const parents=Array.from(neighbours.get(nodeId)||[])
        .filter(other=>ringOf.get(other)===ring-1).sort(recoveryCompareId);
      if(parents.length){
        if(!groups.has(parents[0])) groups.set(parents[0],[]);
        groups.get(parents[0]).push(nodeId);
      }else{
        orphans.push(nodeId);
      }
    }
    const ordered=[];
    const parentIds=Array.from(groups.keys()).sort((left,right)=>{
      const leftAngle=angles.has(left)?angles.get(left):0;
      const rightAngle=angles.has(right)?angles.get(right):0;
      return leftAngle===rightAngle
        ?recoveryCompareId(left,right):leftAngle-rightAngle;
    });
    for(const parent of parentIds){
      ordered.push(...groups.get(parent).slice().sort(recoveryCompareId));
    }
    ordered.push(...orphans);
    // A ring with hundreds of members collapses into a solid band of dots at a
    // single radius, which is what the 512-node projection produces at hop 2.
    // Spread a crowded ring over a few concentric sub-rings instead, and keep
    // consecutive (same-parent) nodes on one angular slot so a parent's
    // children read as a short radial spoke rather than an arc of noise.
    const bands=Math.min(RECOVERY_LAYOUT_MAX_BANDS,
      Math.max(1,Math.ceil(ordered.length/RECOVERY_LAYOUT_BAND_CAPACITY)));
    const slots=Math.ceil(ordered.length/bands);
    // Even spacing over the whole ring keeps groups from overlapping while the
    // parent-angle sweep keeps them near their connector.
    const step=2*Math.PI/slots;
    // The half-ring of headroom is what the outermost band expands into, so
    // every band still lands inside RECOVERY_LAYOUT_RADIUS.
    const baseRadius=RECOVERY_LAYOUT_RADIUS*ring/(maxRing+0.5);
    const bandStep=RECOVERY_LAYOUT_RADIUS*0.5/(maxRing+0.5)/bands;
    for(let index=0;index<ordered.length;index+=1){
      const angle=step*(Math.floor(index/bands)+0.5);
      const radius=baseRadius+index%bands*bandStep;
      angles.set(ordered[index],angle);
      positions.set(ordered[index],{
        x:0.5+radius*Math.cos(angle),
        y:0.5+radius*Math.sin(angle)
      });
    }
  }
  return positions;
}

function recoveryStableHash(value){
  const text=String(value===null||value===undefined?'':value);
  let hash=2166136261;
  for(let index=0;index<text.length;index+=1){
    hash=(hash^text.charCodeAt(index))>>>0;
    hash=Math.imul(hash,16777619)>>>0;
  }
  return hash>>>0;
}

// Published node coordinates frequently place three or more community members on
// one line, so straight edges pass through unrelated markers. A deterministic
// per-edge arc separates them without moving any published position.
function recoveryEdgeCurveOffset(edge,from,to){
  const fromX=Number(from&&from.x);const fromY=Number(from&&from.y);
  const toX=Number(to&&to.x);const toY=Number(to&&to.y);
  if(![fromX,fromY,toX,toY].every(Number.isFinite))return 0;
  const length=Math.hypot(toX-fromX,toY-fromY);
  if(!Number.isFinite(length)||length<1)return 0;
  const key=recoveryNonBlankString(edge&&edge.id)?edge.id
    :recoveryNonBlankString(edge&&edge.edge_id)?edge.edge_id:'';
  const hash=recoveryStableHash(key);
  const magnitude=Math.min(44,Math.max(10,length*0.12));
  const lane=1+(hash%3);
  const sign=((hash>>>3)%2)===0?1:-1;
  return Math.round(sign*magnitude*(lane/3)*100)/100;
}

function recoveryEdgeCurve(from,to,offset){
  const midX=(from.x+to.x)/2;const midY=(from.y+to.y)/2;
  const length=Math.hypot(to.x-from.x,to.y-from.y);
  if(!Number.isFinite(offset)||offset===0||!Number.isFinite(length)||length<1){
    return {control:{x:midX,y:midY},apex:{x:midX,y:midY},curved:false};
  }
  const normalX=-(to.y-from.y)/length;const normalY=(to.x-from.x)/length;
  return {
    control:{x:midX+normalX*offset*2,y:midY+normalY*offset*2},
    apex:{x:midX+normalX*offset,y:midY+normalY*offset},
    curved:true
  };
}

function recoveryCurvePoint(from,control,to,t){
  const inverse=1-t;
  return {
    x:inverse*inverse*from.x+2*inverse*t*control.x+t*t*to.x,
    y:inverse*inverse*from.y+2*inverse*t*control.y+t*t*to.y
  };
}

// Evidence weight is judged against the strongest attributed edge that is
// actually on screen. Without this the underlay saturates whenever a case
// happens to attribute most of its edges at high absolute weight.
function recoveryEvidenceScale(edges){
  let maximum=0;
  for(const edge of Array.isArray(edges)?edges:[]){
    if(!edge||edge.attributed!==true)continue;
    const value=typeof edge.importance==='number'&&Number.isFinite(edge.importance)
      ?Math.max(0,Math.min(1,edge.importance)):0;
    if(value>maximum)maximum=value;
  }
  return maximum>0?maximum:1;
}

function recoveryDrawArrow(context,tip,angle,color,alpha){
  context.beginPath();
  context.moveTo(tip.x,tip.y);
  context.lineTo(tip.x-8*Math.cos(angle-Math.PI/7),
    tip.y-8*Math.sin(angle-Math.PI/7));
  context.lineTo(tip.x-8*Math.cos(angle+Math.PI/7),
    tip.y-8*Math.sin(angle+Math.PI/7));
  context.closePath();
  context.fillStyle=color;
  context.globalAlpha=typeof alpha==='number'?alpha:1;
  context.fill();
  context.globalAlpha=1;
}

function recoveryEdgeStyle(edge,scale){
  const importance=typeof edge.importance==='number'
    &&Number.isFinite(edge.importance)
    ?Math.max(0,Math.min(1,edge.importance)):0;
  const reference=typeof scale==='number'&&Number.isFinite(scale)&&scale>0
    ?Math.min(1,scale):1;
  const relative=Math.max(0,Math.min(1,importance/reference));
  if(edge.attributed===true){
    return {
      alpha:Math.round((0.9+0.05*relative)*100)/100,
      lineWidth:1.6+1.4*relative,
      evidenceAlpha:Math.round((0.16+0.32*relative)*100)/100,
      evidenceLineWidth:Math.round((2.5+5.5*relative)*100)/100
    };
  }
  return edge.emphasized
    ?{alpha:0.5,lineWidth:1.35,evidenceAlpha:0,evidenceLineWidth:0}
    :{alpha:0.14,lineWidth:0.75,evidenceAlpha:0,evidenceLineWidth:0};
}

function recoveryTraceEdgePath(context,from,curve,to){
  context.beginPath();
  context.moveTo(from.x,from.y);
  if(curve.curved)context.quadraticCurveTo(curve.control.x,curve.control.y,to.x,to.y);
  else context.lineTo(to.x,to.y);
}

function recoveryStrokeGraphEdge(context,from,to,edge,scale){
  const relation=recoveryRelationPresentation(edge.relation);
  const style=recoveryEdgeStyle(edge,scale);
  const curve=recoveryEdgeCurve(from,to,recoveryEdgeCurveOffset(edge,from,to));
  context.lineCap='round';
  if(style.evidenceLineWidth>0){
    // The evidence channel reads as a halo around the relationship stroke. A
    // flat band underneath a dashed stroke shows through the gaps and turns
    // both channels into one muddy colour.
    context.setLineDash([]);
    recoveryTraceEdgePath(context,from,curve,to);
    context.strokeStyle='#fbbf24';context.globalAlpha=style.evidenceAlpha;
    context.lineWidth=style.evidenceLineWidth;
    context.shadowColor='rgba(251,191,36,.85)';
    context.shadowBlur=style.evidenceLineWidth*1.5;
    context.stroke();
    context.shadowBlur=0;context.shadowColor='transparent';
  }
  context.setLineDash(relation.dash);
  recoveryTraceEdgePath(context,from,curve,to);
  context.strokeStyle=relation.color;context.globalAlpha=style.alpha;
  context.lineWidth=style.lineWidth;context.stroke();
  context.setLineDash([]);context.globalAlpha=1;
  return {...relation,curve,style};
}

function recoveryRectOverlaps(left,right){
  return left.x<right.x+right.width&&left.x+left.width>right.x
    &&left.y<right.y+right.height&&left.y+left.height>right.y;
}

function recoveryDrawEvidenceLabels(context,edges,positionById,nodeBoxes,
    viewportWidth,viewportHeight){
  const occupied=(Array.isArray(nodeBoxes)?nodeBoxes:[]).slice();
  const margin=6;
  const hasWidth=Number.isFinite(viewportWidth)&&viewportWidth>0;
  const hasHeight=Number.isFinite(viewportHeight)&&viewportHeight>0;
  context.font='700 9px JetBrains Mono, monospace';
  for(const edge of selectRecoveryEvidenceEdges(edges,3)){
    const from=positionById.get(edge.u);const to=positionById.get(edge.v);
    if(!from||!to)continue;
    const relation=recoveryRelationPresentation(edge.relation);
    const rank=Number.isSafeInteger(edge.rank)?'#'+edge.rank:'Evidence';
    let text=rank+' '+relation.label+' '+recoveryFormatNumber(edge.importance);
    let width=Math.ceil(context.measureText(text).width)+14;
    if(hasWidth&&width>viewportWidth-margin*2){
      const maxTextWidth=Math.max(0,viewportWidth-margin*2-14);
      let clipped=text;
      while(clipped.length>1&&context.measureText(clipped+'…').width>maxTextWidth){
        clipped=clipped.slice(0,-1);
      }
      text=clipped.length<text.length?clipped+'…':clipped;
      width=Math.min(viewportWidth-margin*2,
        Math.ceil(context.measureText(text).width)+14);
    }
    const curve=recoveryEdgeCurve(from,to,recoveryEdgeCurveOffset(edge,from,to));
    const anchor=curve.apex;
    const maxX=hasWidth?Math.max(margin,viewportWidth-margin-width):Infinity;
    const maxY=hasHeight?Math.max(margin,viewportHeight-margin-18):Infinity;
    // Try progressively further placements instead of dropping the label, so a
    // published evidence rank never silently disappears from the canvas.
    const candidates=[[8,-23],[-width-8,-23],[8,7],[-width-8,7],
      [-width/2,-34],[-width/2,18],[16,-40],[-width-16,-40]];
    let box=null;
    for(const [deltaX,deltaY] of candidates){
      const next={
        x:Math.min(Math.max(margin,anchor.x+deltaX),maxX),
        y:Math.min(Math.max(margin,anchor.y+deltaY),maxY),
        width,height:18};
      if(!occupied.some(other=>recoveryRectOverlaps(next,other))){box=next;break;}
    }
    if(!box)continue;
    context.beginPath();context.moveTo(anchor.x,anchor.y);
    context.lineTo(box.x+box.width/2,box.y+box.height/2);
    context.strokeStyle=relation.color;context.globalAlpha=.55;
    context.lineWidth=1;context.stroke();context.globalAlpha=1;
    recoveryFillRoundedRect(context,box.x,box.y,box.width,box.height,5);
    context.fillStyle='rgba(12,17,26,.94)';context.fill();
    context.strokeStyle=relation.color;context.globalAlpha=.5;
    context.lineWidth=1;context.stroke();context.globalAlpha=1;
    context.fillStyle='#eef2f8';context.fillText(text,box.x+7,box.y+12);
    occupied.push(box);
  }
  context.globalAlpha=1;context.setLineDash([]);
}

function recoveryFillRoundedRect(context,x,y,width,height,radius){
  const limit=Math.max(0,Math.min(radius,width/2,height/2));
  context.beginPath();
  context.moveTo(x+limit,y);
  context.lineTo(x+width-limit,y);
  context.quadraticCurveTo(x+width,y,x+width,y+limit);
  context.lineTo(x+width,y+height-limit);
  context.quadraticCurveTo(x+width,y+height,x+width-limit,y+height);
  context.lineTo(x+limit,y+height);
  context.quadraticCurveTo(x,y+height,x,y+height-limit);
  context.lineTo(x,y+limit);
  context.quadraticCurveTo(x,y,x+limit,y);
  context.closePath();
}

// The marker box and the label box must never overlap, or a collision-checked
// label rejects itself against its own node.
function recoveryNodeMarkerBox(point,radius){
  return {x:point.x-radius-5,y:point.y-radius-5,
    width:(radius+5)*2,height:(radius+5)*2};
}

function recoveryNodeLabelBox(point,radius,textWidth){
  return {x:point.x+radius+7,y:point.y-8,
    width:Math.ceil(textWidth)+4,height:14};
}

// Lower is more important. Identity labels the reader asked for (target, search
// match, hover) are placed unconditionally; the rest yield to collisions.
function recoveryNodeLabelPriority(node,hoverId,emphasizedNodes,density){
  if(node.target===true)return 0;
  if(node.matched===true)return 1;
  if(node.id===hoverId)return 2;
  if(density==='none')return null;
  if(density==='all')return 300;
  if(density!=='key'&&density!=='auto')return null;
  if(node.attributed===true){
    return Number.isSafeInteger(node.rank)&&node.rank>0
      ?10+Math.min(node.rank,180):200;
  }
  return emphasizedNodes&&emphasizedNodes.has(node.id)?250:null;
}

function recoveryDrawHaloText(context,text,x,y){
  context.strokeStyle='rgba(6,10,16,.92)';
  context.lineWidth=3;context.lineJoin='round';
  context.strokeText(text,x,y);
  context.fillText(text,x,y);
}

function bindRecoveryCanvas(canvas,commands,state){
  const view=canvas.ownerDocument&&canvas.ownerDocument.defaultView;
  const context=canvas.getContext('2d');
  if(!context) return function(){};
  const pointers=new Map();
  let lastPoint=null;
  let lastPinchDistance=null;
  let observer=null;
  let active=commands;
  let hoverId=null;
  const positionById=new Map();
  const radiusById=new Map();

  function nodeRadius(node){
    return node.target?8:(node.pooledMember?6:4.5);
  }

  function draw(){
    const commands=active;
    const rect=canvas.getBoundingClientRect();
    const width=Math.max(1,Math.round(rect.width||canvas.clientWidth||640));
    const height=Math.max(1,Math.round(rect.height||canvas.clientHeight||410));
    const dpr=Math.max(1,Number(view&&view.devicePixelRatio)||1);
    canvas.width=Math.round(width*dpr);
    canvas.height=Math.round(height*dpr);
    context.setTransform(dpr,0,0,dpr,0,0);
    context.clearRect(0,0,width,height);
    const bounds=state.mode==='flow'
      ?recoveryEvidenceBounds(commands)
      :{minX:0,minY:0,maxX:1,maxY:1};
    const viewport={
      width,
      height,
      padding:42,
      scale:state.scale,
      offsetX:state.offsetX,
      offsetY:state.offsetY,
      bounds
    };
    positionById.clear();radiusById.clear();
    for(const node of commands.nodes.concat(commands.provenanceNodes)){
      positionById.set(node.id,graphPoint(node,viewport));
    }
    for(const node of commands.nodes)radiusById.set(node.id,nodeRadius(node));
    const hoverEdges=new Set();
    if(hoverId!==null){
      for(const edge of commands.edges){
        if(edge.u===hoverId||edge.v===hoverId)hoverEdges.add(edge.id);
      }
    }
    const evidenceScale=recoveryEvidenceScale(commands.edges);
    context.lineCap='round';
    for(const edge of commands.edges){
      const from=positionById.get(edge.u);
      const to=positionById.get(edge.v);
      if(!from||!to)continue;
      const dimmed=hoverId!==null&&!hoverEdges.has(edge.id);
      if(dimmed)context.globalAlpha=1;
      const stroke=recoveryStrokeGraphEdge(context,from,to,
        dimmed?{...edge,attributed:false,emphasized:false}:edge,evidenceScale);
      // Direction only where the model actually relied on the link; a marker on
      // every context edge reads as noise.
      if(!dimmed&&edge.attributed===true){
        const radius=(radiusById.get(edge.v)||5)+6;
        const near=recoveryCurvePoint(from,stroke.curve.control,to,0.86);
        const angle=Math.atan2(to.y-near.y,to.x-near.x);
        recoveryDrawArrow(context,
          {x:to.x-Math.cos(angle)*radius,y:to.y-Math.sin(angle)*radius},
          angle,stroke.color,.9);
      }
    }
    for(const edge of commands.provenanceEdges){
      const from=positionById.get(edge.u);
      const to=positionById.get(edge.v);
      if(!from||!to)continue;
      context.beginPath();
      context.setLineDash([6,5]);
      context.moveTo(from.x,from.y);
      context.lineTo(to.x,to.y);
      context.strokeStyle='#f59e0b';
      context.globalAlpha=.9;
      context.lineWidth=1.5;
      context.stroke();
      context.setLineDash([]);
      context.fillStyle='#fbbf24';
      context.font='9px JetBrains Mono, monospace';
      context.fillText(edge.label,(from.x+to.x)/2+5,(from.y+to.y)/2-5);
    }
    context.globalAlpha=1;
    for(const node of commands.provenanceNodes){
      const point=positionById.get(node.id);
      context.beginPath();
      context.arc(point.x,point.y,5,0,Math.PI*2);
      context.fillStyle='#f59e0b';
      context.fill();
    }
    const emphasizedNodes=new Set(commands.edges.filter(edge=>edge.emphasized)
      .flatMap(edge=>[edge.u,edge.v]));
    const nodeBoxes=[];
    const labelQueue=[];
    for(const node of commands.nodes){
      const point=positionById.get(node.id);
      if(!point)continue;
      const radius=nodeRadius(node);
      const quiet=hoverId!==null&&node.id!==hoverId
        &&!hoverEdges.has(node.id)&&!commands.edges.some(edge=>
          (edge.u===hoverId&&edge.v===node.id)
          ||(edge.v===hoverId&&edge.u===node.id));
      context.globalAlpha=quiet?.3:1;
      if(node.attributed){
        context.beginPath();
        context.arc(point.x,point.y,radius+3+2*node.importance,0,Math.PI*2);
        context.strokeStyle='#fbbf24';
        context.globalAlpha=(quiet?.25:1)*(.65+.3*node.importance);
        context.lineWidth=2+node.importance;
        context.stroke();
      }
      // A dark collar keeps the marker readable where edges pass beneath it.
      context.globalAlpha=quiet?.3:1;
      context.beginPath();
      context.arc(point.x,point.y,radius+1.5,0,Math.PI*2);
      context.fillStyle='#080d14';
      context.fill();
      context.beginPath();
      context.arc(point.x,point.y,radius,0,Math.PI*2);
      context.fillStyle=node.target?'#34d399':(node.caughtBeforeSnapshot?'#60a5fa':'#8b8b96');
      context.fill();
      if(node.target){
        context.beginPath();
        context.arc(point.x,point.y,radius+5,0,Math.PI*2);
        context.strokeStyle='#34d399';
        context.lineWidth=2.5;
        context.stroke();
      }else if(node.matched){
        context.beginPath();
        context.arc(point.x,point.y,radius+4,0,Math.PI*2);
        context.strokeStyle='#fbbf24';
        context.lineWidth=2;
        context.stroke();
      }
      if(node.id===hoverId){
        context.beginPath();
        context.arc(point.x,point.y,radius+7,0,Math.PI*2);
        context.strokeStyle='#eef2f8';
        context.globalAlpha=.85;
        context.lineWidth=1.5;
        context.stroke();
      }
      context.globalAlpha=1;
      nodeBoxes.push(recoveryNodeMarkerBox(point,radius));
      const priority=recoveryNodeLabelPriority(node,hoverId,emphasizedNodes,
        state.labelDensity);
      if(priority!==null)labelQueue.push({node,point,radius,quiet,priority});
    }
    // Sampled communities can put hundreds of markers in a narrow band, so
    // labels are placed by priority and skipped when they would collide.
    labelQueue.sort((left,right)=>left.priority-right.priority
      ||recoveryCompareId(left.node.id,right.node.id));
    context.font='10px JetBrains Mono, monospace';
    for(const entry of labelQueue){
      const text=recoveryVisibleText(entry.node.id);
      const box=recoveryNodeLabelBox(entry.point,entry.radius,
        context.measureText(text).width);
      const textX=box.x;
      if(entry.priority>2
        &&nodeBoxes.some(other=>recoveryRectOverlaps(box,other)))continue;
      context.fillStyle=entry.quiet?'#8b8b96':'#e8e8ec';
      context.globalAlpha=entry.quiet?.5:1;
      recoveryDrawHaloText(context,text,textX,entry.point.y+3);
      context.globalAlpha=1;
      nodeBoxes.push(box);
    }
    recoveryDrawEvidenceLabels(context,commands.edges,positionById,nodeBoxes,
      width,height);
    if(hoverId!==null){
      const hovered=commands.nodes.find(node=>node.id===hoverId);
      const point=positionById.get(hoverId);
      if(hovered&&point){
        recoveryDrawNodeTooltip(context,hovered,point,width,height);
      }
    }
    context.globalAlpha=1;
  }

  function hitTest(event){
    const rect=canvas.getBoundingClientRect();
    const x=event.clientX-rect.left;const y=event.clientY-rect.top;
    let bestId=null;let bestDistance=Infinity;
    for(const [id,point] of positionById){
      const reach=(radiusById.get(id)||5)+7;
      const distance=Math.hypot(point.x-x,point.y-y);
      if(distance<=reach&&distance<bestDistance){bestId=id;bestDistance=distance;}
    }
    return bestId;
  }

  function pointerDistance(){
    const values=Array.from(pointers.values());
    if(values.length<2) return null;
    return Math.hypot(values[0].x-values[1].x,values[0].y-values[1].y);
  }
  function onPointerDown(event){
    pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
    if(canvas.setPointerCapture) canvas.setPointerCapture(event.pointerId);
    lastPoint={x:event.clientX,y:event.clientY};
    lastPinchDistance=pointerDistance();
  }
  function onPointerMove(event){
    if(!pointers.has(event.pointerId)){
      const next=hitTest(event);
      if(next!==hoverId){hoverId=next;draw();}
      return;
    }
    pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
    const distance=pointerDistance();
    if(distance!==null&&lastPinchDistance!==null&&lastPinchDistance>0){
      state.scale=Math.max(.5,Math.min(4,state.scale*distance/lastPinchDistance));
      lastPinchDistance=distance;
    }else if(pointers.size===1&&lastPoint){
      state.offsetX+=event.clientX-lastPoint.x;
      state.offsetY+=event.clientY-lastPoint.y;
      lastPoint={x:event.clientX,y:event.clientY};
    }
    draw();
  }
  function onPointerUp(event){
    pointers.delete(event.pointerId);
    lastPoint=null;
    lastPinchDistance=pointerDistance();
  }
  function onPointerLeave(){
    if(hoverId===null)return;
    hoverId=null;draw();
  }
  function onWheel(event){
    event.preventDefault();
    state.scale=Math.max(.5,Math.min(4,state.scale*(event.deltaY<0?1.12:.89)));
    draw();
  }
  canvas.addEventListener('pointerdown',onPointerDown);
  canvas.addEventListener('pointermove',onPointerMove);
  canvas.addEventListener('pointerup',onPointerUp);
  canvas.addEventListener('pointercancel',onPointerUp);
  canvas.addEventListener('pointerleave',onPointerLeave);
  canvas.addEventListener('wheel',onWheel,{passive:false});
  const ResizeObserver=view&&view.ResizeObserver;
  if(ResizeObserver){
    observer=new ResizeObserver(draw);
    observer.observe(canvas);
  }else if(view){
    view.addEventListener('resize',draw);
  }
  draw();
  const dispose=function(){
    canvas.removeEventListener('pointerdown',onPointerDown);
    canvas.removeEventListener('pointermove',onPointerMove);
    canvas.removeEventListener('pointerup',onPointerUp);
    canvas.removeEventListener('pointercancel',onPointerUp);
    canvas.removeEventListener('pointerleave',onPointerLeave);
    canvas.removeEventListener('wheel',onWheel);
    if(observer) observer.disconnect();
    if(!observer&&view) view.removeEventListener('resize',draw);
  };
  // Exposed so control changes that only alter drawing can repaint the existing
  // canvas instead of tearing down and rebuilding the explanation DOM.
  dispose.draw=draw;
  dispose.setCommands=function(next){
    if(!next||typeof next!=='object')return;
    active=next;hoverId=null;draw();
  };
  return dispose;
}

function recoveryDrawNodeTooltip(context,node,point,viewportWidth,viewportHeight){
  const lines=[recoveryVisibleText(node.id)];
  const role=node.target?'Selected target'
    :node.caughtBeforeSnapshot?'Caught before snapshot'
    :node.pooledMember?'Pooled member':'Community context';
  lines.push(role);
  if(node.attributed===true){
    lines.push('Evidence weight '+recoveryFormatNumber(node.importance)
      +(Number.isSafeInteger(node.rank)?' / rank #'+node.rank:''));
  }else{
    lines.push('No model attribution');
  }
  context.font='10px JetBrains Mono, monospace';
  const width=Math.ceil(Math.max(...lines.map(line=>
    context.measureText(line).width)))+16;
  const height=lines.length*14+10;
  const margin=6;
  let x=point.x+14;
  if(Number.isFinite(viewportWidth)&&x+width>viewportWidth-margin){
    x=point.x-width-14;
  }
  x=Math.max(margin,x);
  let y=point.y-height-12;
  if(y<margin)y=point.y+14;
  if(Number.isFinite(viewportHeight)&&y+height>viewportHeight-margin){
    y=Math.max(margin,viewportHeight-margin-height);
  }
  recoveryFillRoundedRect(context,x,y,width,height,6);
  context.fillStyle='rgba(8,13,20,.96)';context.globalAlpha=1;context.fill();
  context.strokeStyle='rgba(255,255,255,.22)';context.lineWidth=1;context.stroke();
  lines.forEach((line,index)=>{
    context.fillStyle=index===0?'#eef2f8':'#a9b1c0';
    context.fillText(line,x+8,y+17+index*14);
  });
}

function recoveryValidFactor(factor){
  const counterfactual=recoveryIsRecord(factor)&&factor.counterfactual;
  return recoveryIsRecord(factor)&&recoveryNonBlankString(factor.factor_id)
    &&recoveryNonBlankString(factor.label)
    &&['stable','unstable','countervailing'].includes(factor.stability)
    &&recoveryIsRecord(counterfactual)
    &&recoverySafeInteger(counterfactual.original_hybrid_rank,false)
    &&counterfactual.original_hybrid_rank>0
    &&recoverySafeInteger(counterfactual.ablated_hybrid_rank,false)
    &&counterfactual.ablated_hybrid_rank>0;
}

function recoveryFactorStabilityLabel(stability){
  return stability==='stable'?'consistently selected by explainer'
    :stability==='unstable'?'varied across restarts'
    :'mixed signed effects across restarts';
}

function recoveryFactorEffectLabel(effect){
  return effect>0?'measured rank effect'
    :effect<0?'countervailing effect'
    :'no measured rank effect';
}

function recoveryPairFactorParts(factorId){
  if(!recoveryNonBlankString(factorId))return null;
  const match=/^pair:(pair:[^:]+|[^:]+):rel:([0-9]+)$/.exec(factorId.trim());
  return match?{groupId:match[1].startsWith('pair:')
    ?match[1]:'pair:'+match[1],relationId:Number(match[2])}:null;
}

function buildRecoveryFactorViewModel(explanation){
  if(!recoveryIsRecord(explanation)||!Array.isArray(explanation.factors))return [];
  const edges=recoveryIsRecord(explanation.community)
    &&Array.isArray(explanation.community.edges)?explanation.community.edges:[];
  return explanation.factors.filter(recoveryValidFactor).map(factor=>{
    const pair=recoveryPairFactorParts(factor.factor_id);
    const publishedEdgeId=pair
      ?pair.groupId+':rel:'+pair.relationId:null;
    const edge=pair?edges.find(candidate=>recoveryIsRecord(candidate)
      &&(candidate.canonical_pair_group_id===pair.groupId
        ||candidate.pair_group_id===pair.groupId
        ||candidate.edge_id===publishedEdgeId)
      &&Number(candidate.rel)===pair.relationId):null;
    const relation=edge&&recoveryNonBlankString(edge.edge_type)
      ?edge.edge_type.trim():null;
    const label=relation&&recoveryNonBlankString(edge.u)
      &&recoveryNonBlankString(edge.v)
      ?relation+' · '+edge.u.trim()+' ↔ '+edge.v.trim()
      :pair?'Pair relation (endpoints unavailable)':factor.label.trim();
    const effect=factor.counterfactual.ablated_hybrid_rank
      -factor.counterfactual.original_hybrid_rank;
    return {
      factorId:factor.factor_id,
      technicalId:factor.factor_id,
      label,
      effect,
      effectLabel:recoveryFactorEffectLabel(effect),
      stability:factor.stability,
      stabilityLabel:recoveryFactorStabilityLabel(factor.stability),
      ...(edge?{relation, u:edge.u.trim(), v:edge.v.trim(), edgeId:edge.edge_id.trim()}: {})
    };
  });
}

function recoverySidecarUrl(view,path){
  if(!recoverySafeSidecarPath(path))throw new Error('Unsafe sidecar path');
  const base=view.sidecarBase.endsWith('/')?view.sidecarBase:view.sidecarBase+'/';
  return base+path;
}

function recoverySafeSidecarPath(value){
  if(!recoveryNonBlankString(value)||value!==value.trim()
      ||value.startsWith('/')||value.includes('\\'))return false;
  const segments=value.split('/');
  return segments.length>0&&segments.every(segment=>
    segment.length>0&&segment!=='.'&&segment!=='..'
      &&/^[A-Za-z0-9._-]+$/.test(segment));
}

function recoverySchema3Reference(value){
  return recoveryIsRecord(value)&&recoverySafeSidecarPath(value.path)
    &&typeof value.sha256==='string'&&/^[0-9a-f]{64}$/.test(value.sha256);
}

function recoverySchema3Community(value,key){
  if(!recoveryIsRecord(value)||value.schema_version!=='1.0'
      ||value.complete!==true||value.community_key!==key
      ||!recoverySafeInteger(value.node_count,false)
      ||!recoverySafeInteger(value.edge_count,false)
      ||!recoverySafeInteger(value.provenance_observation_count,false)){
    return false;
  }
  return recoveryValidateChunkOwner(value);
}

function recoverySchema3SummaryRecord(item,cohort){
  const statuses=['not_selected','selected','available','community_only',
    'unavailable','failed'];
  const kinds=['gnn_explanation','community_control',null];
  const scoreFields=['baseline_raw','baseline_percentile',
    'seed0_gnn_probability','seed0_gnn_percentile','seed0_hybrid_score'];
  const rankFields=['baseline_rank','seed0_gnn_rank','seed0_hybrid_rank'];
  const detailKindAllowed=recoveryIsRecord(item)
    &&(item.detail_kind===null
      ||(item.detail_kind==='gnn_explanation'&&cohort==='hybrid_only')
      ||(item.detail_kind==='community_control'
        &&(cohort==='baseline_only'||cohort==='hybrid_only')));
  return recoveryIsRecord(item)&&item.cohort===cohort
    &&recoveryNonBlankString(item.case_id)
    &&recoveryNonBlankString(item.person_id)
    &&recoveryNonBlankString(item.event_id)
    &&recoveryNonBlankString(item.scoring_day)
    &&statuses.includes(item.detail_status)&&kinds.includes(item.detail_kind)
    &&detailKindAllowed
    &&scoreFields.every(key=>recoveryFiniteUnit(item[key]))
    &&rankFields.every(key=>recoverySafeInteger(item[key],false)&&item[key]>0)
    &&item.hybrid_score_semantics==='percentile_fusion_not_probability';
}

function buildRecoverySchema3ViewModel(artifact){
  if(!recoveryIsRecord(artifact)||artifact.schema_version!=='3.0'){
    return recoveryUnavailable('unsupported-or-missing-schema3-artifact');
  }
  const policy=artifact.policy;
  const validPolicy=recoveryIsRecord(policy)
    &&policy.observability_seed===0&&policy.gnn_arm==='sage'
    &&policy.inspections_per_day===5;
  const bundleId=artifact.bundle_id;
  const sidecarBase=artifact.sidecar_base;
  if(!validPolicy||typeof bundleId!=='string'||!/^[0-9a-f]{24}$/.test(bundleId)
      ||sidecarBase!=='recovery/bundles/'+bundleId+'/'){
    return recoveryUnavailable('invalid-schema3-manifest-contract');
  }
  const cohorts=artifact.cohorts;
  const cohortNames=['hybrid_only','baseline_only','recovered_by_both'];
  if(!recoveryIsRecord(cohorts)
      ||!cohortNames.every(name=>Array.isArray(cohorts[name]))){
    return recoveryUnavailable('invalid-schema3-cohorts');
  }
  const allCases=[];const caseIds=new Set();
  const normalizedCohorts={hybrid_only:[],baseline_only:[],recovered_by_both:[]};
  for(const cohort of cohortNames){
    for(const item of cohorts[cohort]){
      const normalizedCaseId=recoveryCanonicalCaseId(item&&item.case_id);
      if(!recoverySchema3SummaryRecord(item,cohort)
          ||!normalizedCaseId||caseIds.has(normalizedCaseId)){
        return recoveryUnavailable('invalid-schema3-case-records');
      }
      const normalizedItem={...item,case_id:normalizedCaseId};
      caseIds.add(normalizedCaseId);
      allCases.push(normalizedItem);
      normalizedCohorts[cohort].push(normalizedItem);
    }
  }
  const summary=artifact.summary;
  const summaryFields=['baseline_recovered','recovered_by_both',
    'hybrid_only_recovered','baseline_only_recovered','hybrid_total','net_gain'];
  if(!recoveryIsRecord(summary)
      ||!summaryFields.every(key=>recoverySafeInteger(summary[key],true))
      ||summaryFields.slice(0,-1).some(key=>summary[key]<0)
      ||summary.hybrid_only_recovered!==normalizedCohorts.hybrid_only.length
      ||summary.baseline_only_recovered!==normalizedCohorts.baseline_only.length
      ||summary.baseline_recovered!==summary.recovered_by_both
        +summary.baseline_only_recovered
      ||summary.hybrid_total!==summary.recovered_by_both
        +summary.hybrid_only_recovered
      ||summary.net_gain!==summary.hybrid_total-summary.baseline_recovered){
    return recoveryUnavailable('invalid-schema3-overlap-algebra');
  }
  const selection=artifact.selection;
  const rawSelected=selection&&selection.selected_ids;
  if(!recoveryIsRecord(selection)||!recoveryIsRecord(rawSelected)
      ||!cohortNames.every(name=>Array.isArray(rawSelected[name]))
      ||rawSelected.recovered_by_both.length!==0){
    return recoveryUnavailable('invalid-schema3-selection');
  }
  const selected={};
  for(const cohort of cohortNames){
    const values=rawSelected[cohort].map(recoveryCanonicalCaseId);
    if(values.some(value=>!value)||new Set(values).size!==values.length){
      return recoveryUnavailable('invalid-schema3-selection');
    }
    selected[cohort]=values;
  }
  const selectedSets={};
  const cohortByCaseId=new Map(allCases.map(item=>[item.case_id,item.cohort]));
  for(const cohort of cohortNames){
    const values=selected[cohort];
    if(new Set(values).size!==values.length
        ||values.some(caseId=>!caseIds.has(caseId)
          ||cohortByCaseId.get(caseId)!==cohort)){
      return recoveryUnavailable('invalid-schema3-selection');
    }
    selectedSets[cohort]=new Set(values);
  }
  const detailIndex=artifact.detail_index;
  const communityIndex=artifact.community_index;
  const communitySidecarIndex=artifact.community_sidecar_index;
  const rawFallbackValues=selection.hybrid_structural_fallback_ids||[];
  if(!Array.isArray(rawFallbackValues)){
    return recoveryUnavailable('invalid-schema3-selection');
  }
  const fallbackValues=rawFallbackValues.map(recoveryCanonicalCaseId);
  if(!Array.isArray(fallbackValues)
      ||new Set(fallbackValues).size!==fallbackValues.length
      ||fallbackValues.some(caseId=>!caseIds.has(caseId)
        ||cohortByCaseId.get(caseId)!=='hybrid_only')){
    return recoveryUnavailable('invalid-schema3-selection');
  }
  const normalizeIndex=index=>{
    const normalized={};
    for(const [caseId,ref] of Object.entries(index)){
      const normalizedId=recoveryCanonicalCaseId(caseId);
      if(!normalizedId||normalized[normalizedId]!==undefined)return null;
      normalized[normalizedId]=ref;
    }
    return normalized;
  };
  const normalizedDetailIndex=recoveryIsRecord(detailIndex)
    ?normalizeIndex(detailIndex):null;
  const normalizedCommunityIndex=recoveryIsRecord(communityIndex)
    ?normalizeIndex(communityIndex):null;
  const fallbackSet=new Set(fallbackValues);
  if(!recoveryIsRecord(detailIndex)||!recoveryIsRecord(communityIndex)
      ||!recoveryIsRecord(communitySidecarIndex)
      ||!normalizedDetailIndex||!normalizedCommunityIndex
      ||Object.entries(normalizedDetailIndex).some(([caseId,ref])=>
        !selectedSets.hybrid_only.has(caseId)||!recoverySchema3Reference(ref))
      ||Object.entries(normalizedCommunityIndex).some(([caseId,ref])=>
        !(selectedSets.baseline_only.has(caseId)||fallbackSet.has(caseId))
          ||!recoverySchema3Reference(ref))
      ||Object.entries(communitySidecarIndex).some(([key,ref])=>
        !recoveryNonBlankString(key)||!recoverySchema3Reference(ref))){
    return recoveryUnavailable('invalid-schema3-sidecar-index');
  }
  const coverage=artifact.coverage;
  const coverageFields=['hybrid_requested','baseline_requested',
    'hybrid_selected','baseline_selected','hybrid_explained',
    'baseline_community','hybrid_shortfall','baseline_shortfall','shortfall'];
  if(!recoveryIsRecord(coverage)
      ||!coverageFields.every(key=>recoverySafeInteger(coverage[key],false))
      ||!Array.isArray(coverage.shortfall_reasons)
      ||coverage.hybrid_selected!==selected.hybrid_only.length
      ||coverage.baseline_selected!==selected.baseline_only.length
      ||coverage.hybrid_explained!==Object.keys(normalizedDetailIndex).length
      ||coverage.baseline_community!==Object.keys(normalizedCommunityIndex).filter(caseId=>
        selectedSets.baseline_only.has(caseId)).length
      ||(coverage.hybrid_structural_fallback!==undefined
        &&coverage.hybrid_structural_fallback!==Object.keys(normalizedCommunityIndex).filter(
          caseId=>fallbackSet.has(caseId)).length)
      ||coverage.shortfall!==coverage.hybrid_shortfall+coverage.baseline_shortfall
      ||(coverage.shortfall>0&&!coverage.shortfall_reasons.length)){
    return recoveryUnavailable('invalid-schema3-coverage');
  }
  const defaultCohort=normalizedCohorts.hybrid_only.length?'hybrid_only':
    (normalizedCohorts.baseline_only.length?'baseline_only':'recovered_by_both');
  const caseIndex={};
  for(const item of allCases){
    caseIndex[item.case_id]={
      ...item,
      caseId:item.case_id,
      personId:item.person_id,
      detailStatus:item.detail_status,
      detailKind:item.detail_kind===undefined?null:item.detail_kind,
      selectionReason:recoveryNonBlankString(item.selection_reason)
        ?item.selection_reason:'not_selected',
      failureReason:recoveryNonBlankString(item.failure_reason)
        ?item.failure_reason:null,
      explanationUnavailableReason:recoveryNonBlankString(
      item.explanation_unavailable_reason)?item.explanation_unavailable_reason:null
    };
  }
  const eligibleExplanationIds=normalizedCohorts.hybrid_only
    .map(item=>caseIndex[item.case_id])
    .filter(record=>recoverySchema3ExplanationEligible(
      record,normalizedDetailIndex))
    .map(record=>record.caseId);
  return {
    available:true,
    schemaVersion:'3.0',
    policy:{...policy},summary:{...summary},coverage:{...coverage},
    cohorts:{
      hybrid_only:normalizedCohorts.hybrid_only.map(item=>caseIndex[item.case_id]),
      baseline_only:normalizedCohorts.baseline_only.map(item=>caseIndex[item.case_id]),
      recovered_by_both:normalizedCohorts.recovered_by_both.map(item=>caseIndex[item.case_id])
    },
    caseIndex,
    selection:{...selection,selected_ids:{...selected},
      hybrid_structural_fallback_ids:fallbackValues.slice()},
    detailIndex:{...normalizedDetailIndex},communityIndex:{...normalizedCommunityIndex},
    communitySidecarIndex:{...communitySidecarIndex},
    catalogIndex:recoveryIsRecord(artifact.catalog_index)?artifact.catalog_index:{},
    sidecarBase,defaultCohort,
    eligibleExplanationIds,
    defaultCaseId:eligibleExplanationIds[0]||null
  };
}

const RECOVERY_SCHEMA3_FILTERS=['all','hybrid_only','baseline_only',
  'recovered_by_both','gnn_explanation','community_control','all_detail'];

function recoverySchema3ExplanationEligible(record,detailIndex){
  const caseId=recoveryNormalizeCaseId(record&&record.caseId);
  return recoveryIsRecord(record)
    &&record.detailKind==='gnn_explanation'
    &&record.detailStatus==='available'
    &&caseId!==null&&recoveryIsRecord(detailIndex)
    &&Object.prototype.hasOwnProperty.call(detailIndex,caseId);
}

function filterRecoverySchema3Cases(view,filter){
  if(!recoveryIsRecord(view)||view.available!==true)return [];
  const selected=RECOVERY_SCHEMA3_FILTERS.includes(filter)?filter:'all';
  const cohortNames=['hybrid_only','baseline_only','recovered_by_both'];
  const rows=[];
  for(const cohort of cohortNames){
    for(const record of view.cohorts[cohort])rows.push(record);
  }
  if(cohortNames.includes(selected)){
    return rows.filter(record=>record.cohort===selected);
  }
  if(selected==='all_detail'){
    return rows.filter(record=>record.detailKind!==null);
  }
  if(selected==='all')return rows;
  if(selected==='gnn_explanation'){
    return rows.filter(record=>recoverySchema3ExplanationEligible(
      record,view.detailIndex));
  }
  return rows.filter(record=>record.detailKind===selected);
}

const RECOVERY_STRUCTURAL_STAGES=['first_hop','second_hop','component_pool'];
const RECOVERY_GRAPH_NODE_LIMIT=1500;
const RECOVERY_GRAPH_EDGE_LIMIT=4000;

function buildStructuralDrawCommands(control,options){
  if(!recoveryIsRecord(control)||!recoveryNonBlankString(control.person_id)
      ||!recoveryIsRecord(control.community)
      ||control.community.complete!==true){
    return recoveryUnavailable('incomplete-community');
  }
  const settings=recoveryIsRecord(options)?options:{};
  if(!['all','flow'].includes(settings.mode)
      ||!RECOVERY_STRUCTURAL_STAGES.includes(settings.stageId)){
    return recoveryUnavailable('invalid-view-options');
  }
  const community=control.community;
  if(!Array.isArray(community.nodes)||!Array.isArray(community.edges)){
    return recoveryUnavailable('invalid-community-membership');
  }
  const nodeIds=community.nodes.map(node=>recoveryIsRecord(node)?node.node_id:null);
  const nodeSet=new Set(nodeIds);
  if(!community.nodes.every(node=>recoveryIsRecord(node)
        &&recoveryNonBlankString(node.node_id))
      ||nodeIds.length===0||nodeSet.size!==nodeIds.length
      ||!nodeSet.has(control.person_id)){
    return recoveryUnavailable('invalid-community-membership');
  }
  const edgeIds=community.edges.map(edge=>recoveryIsRecord(edge)?edge.edge_id:null);
  if(!community.edges.every(edge=>recoveryIsRecord(edge)
        &&recoveryNonBlankString(edge.edge_id)
        &&recoveryNonBlankString(edge.u)&&recoveryNonBlankString(edge.v)
        &&nodeSet.has(edge.u)&&nodeSet.has(edge.v))
      ||new Set(edgeIds).size!==edgeIds.length){
    return recoveryUnavailable('invalid-community-membership');
  }
  if(!community.nodes.every(node=>recoveryFiniteUnit(node.x)
      &&recoveryFiniteUnit(node.y))){
    return recoveryUnavailable('invalid-community-coordinates');
  }
  const stages=control.structural_stages;
  if(!Array.isArray(stages)||stages.length!==RECOVERY_STRUCTURAL_STAGES.length){
    return recoveryUnavailable('invalid-structural-stages');
  }
  const stagesById=new Map();
  for(const stage of stages){
    if(!recoveryIsRecord(stage)
        ||!RECOVERY_STRUCTURAL_STAGES.includes(stage.stage_id)
        ||stagesById.has(stage.stage_id)
        ||!recoveryIsRecord(stage.edge_rule)
        ||!recoveryValidStageRule(stage,nodeIds,edgeIds)){
      return recoveryUnavailable('invalid-structural-stages');
    }
    stagesById.set(stage.stage_id,stage);
  }
  if(RECOVERY_STRUCTURAL_STAGES.some(id=>!stagesById.has(id))){
    return recoveryUnavailable('invalid-structural-stages');
  }
  const nodesById=new Map(community.nodes.map(node=>[node.node_id,node]));
  const selectedStage=stagesById.get(settings.stageId);
  const stageEdgeIds=new Set((settings.stageId==='first_hop'
    ||settings.stageId==='second_hop'
    ?community.edges.filter(edge=>
      recoveryStageEmphasizes(selectedStage,edge,nodesById))
    :community.edges)
    .map(edge=>edge.edge_id));
  const query=(typeof settings.query==='string'?settings.query:'')
    .trim().toLowerCase();
  const nodes=community.nodes.slice().sort((a,b)=>
    recoveryCompareId(a.node_id,b.node_id)).map(node=>({
      node_id:node.node_id,
      id:node.node_id,
      x:node.x,
      y:node.y,
      target:node.node_id===control.person_id,
      pooledMember:node.pooled_member===true,
      caughtBeforeSnapshot:node.caught_before_snapshot===true,
      importance:0,
      attributed:false,
      rank:null,
      matched:query.length>0&&node.node_id.toLowerCase().includes(query)
    }));
  const edges=community.edges.slice().sort((a,b)=>
    recoveryCompareId(a.edge_id,b.edge_id)).map(edge=>({
      edge_id:edge.edge_id,
      id:edge.edge_id,
      u:edge.u,
      v:edge.v,
      relation:recoveryNonBlankString(edge.edge_type)?edge.edge_type:'RELATION',
      // A control has no explainer mask, so every edge keeps neutral weight.
      importance:0,
      attributed:false,
      rank:null,
      emphasized:settings.mode==='all'
        ||stageEdgeIds.has(edge.edge_id)
  }));
  const slice=buildRecoveryGraphSlice(nodes,edges,control.person_id);
  if(!slice.available) return slice;
  const canvasSlice=filterRecoveryStageSlice(
    slice,stageEdgeIds,control.person_id);
  return {
    available:true,
    mode:settings.mode,
    stageId:settings.stageId,
    nodes:canvasSlice.nodes,
    edges:canvasSlice.edges,
    tableNodes:slice.tableNodes,
    tableEdges:slice.tableEdges,
    sampled:slice.sampled,
    fullNodeCount:slice.fullNodeCount,
    fullEdgeCount:slice.fullEdgeCount,
    provenanceNodes:[],
    provenanceEdges:[]
  };
}

function assembleRecoverySchema3Community(manifest,nodeRows,edgeRows){
  if(!recoveryIsRecord(manifest))return recoveryUnavailable('missing-community');
  if(!Array.isArray(nodeRows)||!Array.isArray(edgeRows)){
    return recoveryUnavailable('community-not-loaded');
  }
  if(nodeRows.length!==manifest.node_count
      ||edgeRows.length!==manifest.edge_count){
    return recoveryUnavailable('community-partially-loaded');
  }
  return {
    available:true,
    community:{
      complete:true,
      community_key:manifest.community_key,
      node_count:manifest.node_count,
      edge_count:manifest.edge_count,
      nodes:nodeRows,
      edges:edgeRows,
      provenance_expansions:[]
    }
  };
}

function mergeRecoverySchema3Overlay(community,overlayNodes,overlayEdges){
  if(!recoveryIsRecord(community)
      ||community.complete!==true
      ||!recoverySafeInteger(community.node_count,false)
      ||!recoverySafeInteger(community.edge_count,false)
      ||!Array.isArray(community.nodes)||!Array.isArray(community.edges)
      ||community.node_count!==community.nodes.length
      ||community.edge_count!==community.edges.length
      ||!Array.isArray(overlayNodes)||!Array.isArray(overlayEdges)){
    return recoveryUnavailable('invalid-overlay-identity');
  }
  const baseNodesById=new Map();
  for(const node of community.nodes){
    if(!recoveryIsRecord(node)||!recoveryNonBlankString(node.node_id)){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    const nodeId=node.node_id.trim();
    if(baseNodesById.has(nodeId)){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    baseNodesById.set(nodeId,node);
  }
  const baseEdgesById=new Map();
  for(const edge of community.edges){
    if(!recoveryIsRecord(edge)||!recoveryNonBlankString(edge.edge_id)
        ||!recoveryNonBlankString(edge.u)||!recoveryNonBlankString(edge.v)
        ||!recoveryNonBlankString(edge.edge_type)){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    const edgeId=edge.edge_id.trim();
    if(baseEdgesById.has(edgeId)
        ||!baseNodesById.has(edge.u.trim())||!baseNodesById.has(edge.v.trim())){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    if(edge.relation!==undefined
        &&(!recoveryNonBlankString(edge.relation)
          ||edge.relation.trim()!==edge.edge_type.trim())){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    baseEdgesById.set(edgeId,edge);
  }

  const overlayNodeById=new Map();
  const overlayNodeIds=new Set();
  for(const node of overlayNodes){
    if(!recoveryIsRecord(node)||!recoveryNonBlankString(node.node_id)){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    const nodeId=node.node_id.trim();
    if(overlayNodeIds.has(nodeId)){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    overlayNodeIds.add(nodeId);
    const hasMedian=Object.prototype.hasOwnProperty.call(node,'explainer_median');
    const hasRank=Object.prototype.hasOwnProperty.call(node,'rank');
    if(!hasMedian&&!hasRank)continue;
    if(!recoveryFiniteUnit(node.explainer_median)
        ||!recoverySafeInteger(node.rank,false)||node.rank<1){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    if(!baseNodesById.has(nodeId)){
      return recoveryUnavailable('invalid-overlay-membership');
    }
    overlayNodeById.set(nodeId,node);
  }

  const overlayEdgeById=new Map();
  const overlayEdgeIds=new Set();
  for(const edge of overlayEdges){
    if(!recoveryIsRecord(edge)||!recoveryNonBlankString(edge.edge_id)
        ||!recoveryNonBlankString(edge.u)||!recoveryNonBlankString(edge.v)
        ||!recoveryNonBlankString(edge.edge_type)){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    const edgeId=edge.edge_id.trim();
    if(overlayEdgeIds.has(edgeId)){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    overlayEdgeIds.add(edgeId);
    const hasMedian=Object.prototype.hasOwnProperty.call(edge,'explainer_median');
    const hasRank=Object.prototype.hasOwnProperty.call(edge,'rank');
    if(!hasMedian&&!hasRank)continue;
    if(!recoveryFiniteUnit(edge.explainer_median)
        ||!recoverySafeInteger(edge.rank,false)||edge.rank<1){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    const baseEdge=baseEdgesById.get(edgeId);
    if(!baseEdge)return recoveryUnavailable('invalid-overlay-membership');
    for(const field of ['u','v']){
      if(edge[field].trim()!==baseEdge[field].trim()){
        return recoveryUnavailable('invalid-overlay-membership');
      }
    }
    if(edge.edge_type.trim()!==baseEdge.edge_type.trim()
        ||(edge.relation!==undefined
          &&(!recoveryNonBlankString(edge.relation)
            ||edge.relation.trim()!==edge.edge_type.trim()))){
      return recoveryUnavailable('invalid-overlay-identity');
    }
    overlayEdgeById.set(edgeId,edge);
  }

  function normalizedRow(base,row,isEdge){
    const result={...base,importance:0,attributed:false,rank:null};
    const identityFields=isEdge
      ?['edge_id','u','v','edge_type','relation']:['node_id'];
    const overlayFields=isEdge
      ?['edge_id','u','v','edge_type','relation',
        'explainer_median','importance','attributed','rank']
      :['node_id','explainer_median','importance','attributed','rank'];
    function trimIdentityFields(){
      for(const field of identityFields){
        if(recoveryNonBlankString(result[field]))result[field]=result[field].trim();
      }
    }
    trimIdentityFields();
    if(isEdge){
      result.relation=recoveryNonBlankString(base.relation)
        ?base.relation.trim():result.edge_type;
    }
    if(row){
      for(const key of overlayFields){
        if(Object.prototype.hasOwnProperty.call(row,key))result[key]=row[key];
      }
      trimIdentityFields();
      result.importance=Math.max(0,Math.min(1,row.explainer_median));
      result.attributed=true;
      result.rank=row.rank;
      if(isEdge){
        result.relation=recoveryNonBlankString(row.relation)
          ?row.relation.trim():result.edge_type;
      }
    }
    return result;
  }
  return {
    available:true,
    nodes:community.nodes.map(node=>normalizedRow(
      node,overlayNodeById.get(node.node_id.trim()),false)),
    edges:community.edges.map(edge=>normalizedRow(
      edge,overlayEdgeById.get(edge.edge_id.trim()),true))
  };
}

function buildRecoverySchema3Detail(record,payload,communityView,overlayRows){
  if(!recoveryIsRecord(record))return recoveryUnavailable('missing-case');
  const kind=record.detailKind;
  if(kind!=='gnn_explanation'&&kind!=='community_control'){
    return recoveryUnavailable('no-detail-selected');
  }
  if(!recoveryIsRecord(payload))return recoveryUnavailable('sidecar-unavailable');
  if(!recoveryIsRecord(communityView)||communityView.available!==true){
    return {available:false,kind,
      reason:recoveryIsRecord(communityView)&&communityView.reason
        ?communityView.reason:'community-unavailable'};
  }
  const detail=payload.detail;
  const explanation=kind==='gnn_explanation'
    ?(payload.explanation||(recoveryIsRecord(detail)?detail.explanation:null))
    :null;
  if(kind==='gnn_explanation'&&!recoveryIsRecord(explanation)){
    return {available:false,kind,reason:'explanation-unavailable'};
  }
  if(kind==='community_control'&&!recoveryIsRecord(detail)){
    return {available:false,kind,reason:'structural-detail-unavailable'};
  }
  const boundarySource=kind==='gnn_explanation'?explanation:detail;
  const evidenceBoundary=recoveryIsRecord(boundarySource)
    ?boundarySource.evidence_boundary:null;
  if(!validateRecoveryEvidenceBoundary(
    {evidence_boundary:evidenceBoundary},record.scoring_day).available){
    return {available:false,kind,reason:'invalid-evidence-boundary'};
  }
  let explanationPresentation=null;
  if(kind==='gnn_explanation'){
    let presentationOverlay=overlayRows;
    if(presentationOverlay===undefined||presentationOverlay===null){
      presentationOverlay={
        available:true,
        nodes:communityView.community.nodes.map(node=>
          ({...node,importance:0,attributed:false})),
        edges:communityView.community.edges.map(edge=>
          ({...edge,importance:0,attributed:false}))
      };
    }else if(!recoveryIsRecord(presentationOverlay)
        ||presentationOverlay.available!==true
        ||!Array.isArray(presentationOverlay.nodes)
        ||!Array.isArray(presentationOverlay.edges)){
      return {available:false,kind,
        reason:recoveryIsRecord(presentationOverlay)&&presentationOverlay.reason
          ?presentationOverlay.reason:'invalid-overlay-presentation'};
    }
    explanationPresentation={...explanation,person_id:record.personId,
      community:communityView.community,
      overlayNodes:presentationOverlay.nodes,
      overlayEdges:presentationOverlay.edges};
  }
  return {
    available:true,
    kind,
    personId:record.personId,
    explanation:explanationPresentation,
    control:kind==='community_control'
      ?{person_id:record.personId,community:communityView.community,
        structural_stages:detail.structural_stages}
      :null,
    evidenceBoundary,
    nodeCount:communityView.community.nodes.length,
    edgeCount:communityView.community.edges.length,
    canvasAvailable:kind==='gnn_explanation'||(
      communityView.community.nodes.length<=RECOVERY_GRAPH_NODE_LIMIT
      &&communityView.community.edges.length<=RECOVERY_GRAPH_EDGE_LIMIT)
  };
}

const recoveryCatalogChunkCache=new Map();

async function recoveryFetchJson(url,expectedHash){
  if(typeof expectedHash!=='string'||!/^[0-9a-f]{64}$/.test(expectedHash)){
    throw new Error('Sidecar reference requires a 64-character lowercase SHA-256 hash');
  }
  if(!globalThis.crypto||!globalThis.crypto.subtle){
    throw new Error('WebCrypto SHA-256 is required to verify recovery sidecars');
  }
  const response=await fetch(url,{cache:'no-store'});
  if(!response.ok) throw new Error('HTTP '+response.status+' for '+url);
  const bytes=await response.arrayBuffer();
  const digest=await globalThis.crypto.subtle.digest('SHA-256',bytes);
  const actual=Array.from(new Uint8Array(digest))
    .map(value=>value.toString(16).padStart(2,'0')).join('');
  if(actual!==expectedHash) throw new Error('SHA-256 mismatch for '+url);
  return JSON.parse(new TextDecoder().decode(bytes));
}

function recoveryServerHelp(error){
  return 'Sidecars require local HTTP. From the repository root run: '
    +'python -m http.server 8000 --directory artifacts/v9/dashboard, '
    +'then open http://localhost:8000/index.html. Fetch error: '
    +String(error&&error.message||error);
}

function recoveryValidateChunkOwner(owner){
  if(!recoveryIsRecord(owner)||owner.complete!==true
      ||owner.nodes!==undefined||owner.edges!==undefined)return false;
  const specs=[
    ['node_chunks','node_count'],['edge_chunks','edge_count'],
    ['provenance_chunks','provenance_observation_count'],
    ['provenance_expansion_membership_chunks',null]
  ];
  for(const [field,countField] of specs){
    const refs=owner[field];
    if(!Array.isArray(refs))return false;
    let expectedOffset=0;
    for(const ref of refs){
      if(!recoveryIsRecord(ref)||!recoverySafeSidecarPath(ref.path)
          ||!recoveryNonBlankString(ref.sha256)
          ||ref.offset!==expectedOffset||!recoverySafeInteger(ref.count,false))return false;
      expectedOffset+=ref.count;
    }
    if(countField&&owner[countField]!==expectedOffset)return false;
  }
  if(owner.day_view!==undefined){
    if(!recoveryIsRecord(owner.day_view))return false;
    const daySpecs=[
      ['node_status_chunks','node_count'],
      ['edge_membership_chunks','edge_count']
    ];
    for(const [field,countField] of daySpecs){
      const refs=owner.day_view[field];
      if(!Array.isArray(refs))return false;
      let expectedOffset=0;
      for(const ref of refs){
        if(!recoveryIsRecord(ref)||!recoverySafeSidecarPath(ref.path)
            ||!recoveryNonBlankString(ref.sha256)
            ||ref.offset!==expectedOffset||!recoverySafeInteger(ref.count,false))return false;
        expectedOffset+=ref.count;
      }
      if(owner[countField]!==expectedOffset)return false;
    }
  }
  return true;
}

function recoveryValidatedChunkRows(payload,ref,rowField){
  if(!recoveryIsRecord(payload)||!recoveryIsRecord(ref)
      ||!Array.isArray(payload[rowField])
      ||payload.offset!==ref.offset||payload.count!==ref.count
      ||payload.count!==payload[rowField].length)return null;
  return payload[rowField];
}

async function recoveryResolveCatalogRows(view,rows,kind){
  const catalog=view.catalogIndex&&view.catalogIndex[kind];
  if(!recoveryIsRecord(catalog)||!Array.isArray(catalog.chunks)){
    throw new Error('Normalized catalog index is missing');
  }
  const needed=new Map();
  for(const row of rows){
    const catalogId=row&&row.catalog_id;
    const chunk=catalog.chunks.find(
      candidate=>candidate.first_id<=catalogId&&catalogId<=candidate.last_id);
    if(!chunk)throw new Error('Normalized catalog record is not indexed');
    needed.set(chunk.path,chunk);
  }
  const recordsById=new Map();
  await Promise.all(Array.from(needed.values()).map(async chunk=>{
    const cacheKey=recoverySidecarUrl(view,chunk.path)+'|'+chunk.sha256;
    let records=recoveryCatalogChunkCache.get(cacheKey);
    if(!records){
      const catalogPayload=await recoveryFetchJson(
        recoverySidecarUrl(view,chunk.path),chunk.sha256);
      records=recoveryValidatedChunkRows(catalogPayload,chunk,'records');
      if(records===null)throw new Error('Normalized catalog chunk is invalid');
      recoveryCatalogChunkCache.set(cacheKey,records);
    }
    for(const entry of records){
      if(!recoveryIsRecord(entry)||!recoveryNonBlankString(entry.record_id)
          ||!recoveryIsRecord(entry.record)){
        throw new Error('Normalized catalog chunk is invalid');
      }
      recordsById.set(entry.record_id,entry.record);
    }
  }));
  for(const row of rows){
    if(!recoveryIsRecord(row)||!recoveryNonBlankString(row.catalog_id)
        ||!recordsById.has(row.catalog_id)){
      throw new Error('Normalized catalog record is missing');
    }
    const identityField=kind==='nodes'?'node_id'
      :(kind==='edges'?'edge_id':'source_row_id');
    const catalogRecord=recordsById.get(row.catalog_id);
    if(!recoveryNonBlankString(row[identityField])
        ||!recoveryNonBlankString(catalogRecord[identityField])
        ||row[identityField]!==catalogRecord[identityField]){
      throw new Error('Normalized catalog identity contract is invalid');
    }
  }
  return rows.map(row=>{
    const detached={...row};delete detached.catalog_id;
    return {...(recordsById.get(row.catalog_id)||{}),...detached};
  });
}

async function recoveryApplyDayView(view,owner,normalized,index,resolvedRows){
  const dayConfig=normalized==='node'
    ?['node_status_chunks','node_statuses','node_id']
    :['edge_membership_chunks','edge_memberships','edge_id'];
  const dayRefs=owner.day_view[dayConfig[0]];
  if(!Array.isArray(dayRefs)||!dayRefs[index]){
    throw new Error('Normalized day-view chunk is missing');
  }
  const dayRef=dayRefs[index];
  const dayPayload=await recoveryFetchJson(
    recoverySidecarUrl(view,dayRef.path),dayRef.sha256);
  const dayRows=recoveryValidatedChunkRows(dayPayload,dayRef,dayConfig[1]);
  if(dayRows===null)throw new Error('Day-view chunk offset or count contract is invalid');
  const dayIds=dayRows.map(row=>recoveryIsRecord(row)?row[dayConfig[2]]:null);
  const resolvedIds=resolvedRows.map(row=>recoveryIsRecord(row)
    ?row[dayConfig[2]]:null);
  if(!recoverySameIds(dayIds,resolvedIds)){
    throw new Error('Normalized day-view identity contract is invalid');
  }
  const stateById=new Map(dayRows.map(row=>[row[dayConfig[2]],row]));
  return resolvedRows.map(
    row=>({...row,...(stateById.get(row[dayConfig[2]])||{})}));
}

function mountRecoveryExplorerV3(root,artifact,tools){
  const doc=root.ownerDocument;
  const view=buildRecoverySchema3ViewModel(artifact);
  const fmt=value=>recoveryFormatNumber(value);
  const state={filter:'gnn_explanation',
    caseId:view.available?view.defaultCaseId:null,caseData:null,community:null,
    nodeRows:null,edgeRows:null,overlayNodeRows:null,overlayEdgeRows:null,
    loading:false,error:null,
    mode:'flow',stageId:'first_hop',relationship:'all',selectedFactorId:null,query:'',
    scale:1,offsetX:0,offsetY:0,labelDensity:'key',openDisclosures:new Set(),
    nodeTablePage:0,edgeTablePage:0};
  let requestToken=0;let disposed=false;
  let canvasCleanup=function(){};let pendingCanvas=null;
  let graphContext=null;

  function restoreV3Focus(attribute,datasetKey,value){
    for(const control of root.querySelectorAll('['+attribute+']')){
      if(control.dataset&&control.dataset[datasetKey]===String(value)){
        // preventScroll matters: the default focus behaviour scrolls the control
        // into view, which after a re-render throws the reader back up the page.
        // Engines without support ignore the argument.
        control.focus({preventScroll:true});
        return true;
      }
    }
    return false;
  }
  // A re-render replaces live DOM, so the browser loses its scroll anchor.
  // Pin the element the reader just interacted with to the same viewport row.
  function measureAnchor(element){
    if(!element||typeof element.getBoundingClientRect!=='function')return null;
    const rect=element.getBoundingClientRect();
    return rect&&Number.isFinite(rect.top)?rect.top:null;
  }
  function restoreAnchor(element,top){
    if(top===null||top===undefined)return;
    const win=doc.defaultView;
    if(!win||typeof win.scrollBy!=='function')return;
    const next=measureAnchor(element);
    if(next===null)return;
    const delta=next-top;
    if(Math.abs(delta)>=1)win.scrollBy(0,delta);
  }
  function replaceNode(current,next){
    if(!current||!next)return false;
    if(typeof current.replaceWith==='function'){current.replaceWith(next);return true;}
    const parent=current.parentNode;
    if(!parent||!Array.isArray(parent.children))return false;
    const index=parent.children.indexOf(current);
    if(index<0)return false;
    parent.children[index]=next;next.parentNode=parent;return true;
  }
  // Only the graph panel depends on view, stage, and relationship. Rebuilding
  // just that panel keeps a control click near-instant instead of re-creating
  // the header, case list, narrative, factors, and both data tables.
  function renderGraphOnly(anchorSelector,datasetKey,value){
    if(!graphContext||!graphContext.panel||!graphContext.detailView){
      render();return;
    }
    const anchorTop=measureAnchor(graphContext.panel);
    canvasCleanup();canvasCleanup=function(){};pendingCanvas=null;
    const holder=recoveryElement(doc,'div','v9-recovery-graph-holder');
    const graph=renderGraph(holder,graphContext.detailView,graphContext.record);
    if(!graph||!graph.panel||!replaceNode(graphContext.panel,graph.panel)){
      render();
      if(anchorSelector)restoreV3Focus(anchorSelector,datasetKey,value);
      return;
    }
    graphContext.panel=graph.panel;
    if(graph.commands&&graphContext.tablesBody
        &&typeof graphContext.tablesBody.replaceChildren==='function'){
      graphContext.tablesBody.replaceChildren();
      renderGraphTable(graphContext.tablesBody,graph.commands,graphContext.record);
    }
    if(pendingCanvas){
      canvasCleanup=bindRecoveryCanvas(
        pendingCanvas.canvas,pendingCanvas.commands,state);
      pendingCanvas=null;
    }
    restoreAnchor(graphContext.panel,anchorTop);
    if(anchorSelector)restoreV3Focus(anchorSelector,datasetKey,value);
  }
  function redrawCanvas(){
    if(typeof canvasCleanup.draw==='function'){canvasCleanup.draw();return true;}
    return false;
  }
  // Search changes only which node is marked, so swap the draw commands on the
  // live canvas rather than rebuilding the toolbar out from under the input.
  function refreshCanvasCommands(){
    if(!graphContext||!graphContext.detailView
        ||typeof canvasCleanup.setCommands!=='function')return false;
    const detailView=graphContext.detailView;
    const control=detailView.kind==='community_control';
    const built=control
      ?buildStructuralDrawCommands(detailView.control,{mode:state.mode,
        stageId:activeStageId(detailView.kind),selectedFactorId:null,
        query:state.query})
      :buildCommunityDrawCommands(detailView.explanation,{mode:state.mode,
        stageId:activeStageId(detailView.kind),selectedFactorId:null,
        query:state.query});
    if(!built.available)return false;
    canvasCleanup.setCommands(
      filterRecoveryGraphCommands(built,state.relationship));
    return true;
  }
  function visibleRows(){return filterRecoverySchema3Cases(view,state.filter);}
  function currentRecord(){
    return visibleRows().find(item=>item.caseId===state.caseId)||null;
  }
  function stageIdsFor(kind){
    return kind==='community_control'
      ?RECOVERY_STRUCTURAL_STAGES
      :['first_hop','second_hop','component_pool','rank_fusion'];
  }
  function activeStageId(kind){
    const allowed=stageIdsFor(kind);
    return allowed.includes(state.stageId)?state.stageId:'first_hop';
  }
  function addText(parent,tag,className,text){
    parent.appendChild(recoveryElement(doc,tag,className,text));
  }
  function renderDisclosure(parent,key,label,renderBody){
    const details=recoveryElement(doc,'details','v9-recovery-disclosure');
    details.dataset.v3Disclosure=key;
    details.open=state.openDisclosures.has(key);
    const summary=recoveryElement(doc,'summary','v9-recovery-disclosure-summary',label);
    summary.setAttribute('aria-label',label);
    details.appendChild(summary);
    const body=recoveryElement(doc,'div','v9-recovery-disclosure-body');
    renderBody(body);
    details.appendChild(body);
    parent.appendChild(details);
    return details;
  }
  function eligibleCountLabel(rows){
    const count=(Array.isArray(rows)?rows:[]).filter(record=>
      recoverySchema3ExplanationEligible(record,view.detailIndex)).length;
    return fmt(count)+' published GNN explanation'+(count===1?'':'s');
  }
  function renderSelectedHeader(fragment,record,rows){
    const header=recoveryElement(doc,'header','v9-recovery-header');
    const copy=recoveryElement(doc,'div','v9-recovery-header-copy');
    addText(copy,'div','v9-recovery-eyebrow','Published GNN explanations');
    if(record){
      const title=recoveryElement(doc,'h3','v9-recovery-title',
        'Why case '+record.personId+' surfaced');
      title.id='v9-recovery-title';copy.appendChild(title);
      const count=eligibleCountLabel(rows);
      addText(copy,'p','v9-recovery-intro',count+' in this evidence bundle.');
      addText(copy,'p','v9-recovery-intro',
        'Event '+record.event_id+' / scoring day '
          +recoveryFormatDateOnly(record.scoring_day)+'.');
    }else{
      const title=recoveryElement(doc,'h3','v9-recovery-title',
        'Published GNN explanations unavailable');
      title.id='v9-recovery-title';copy.appendChild(title);
      addText(copy,'p','v9-recovery-intro',
        'No published GNN explanation is available for the selected case.');
    }
    header.appendChild(copy);
    addText(header,'div','v9-recovery-scope',
      'Single-seed observability · GraphSAGE seed 0 · Hybrid percentile fusion.'
        +' Hybrid score is percentile fusion, not probability.');
    fragment.appendChild(header);
  }
  function renderCohortContext(parent,record){
    const context=recoveryElement(doc,'section','v9-recovery-v3-panel');
    addText(context,'h5','','Cohort context');
    const summary=recoveryElement(doc,'div','v9-recovery-summary');
    summary.setAttribute('aria-label','Schema-3 recovery overlap summary');
    for(const [key,label] of [
      ['baseline_recovered','Baseline recovered'],
      ['recovered_by_both','Recovered by both'],
      ['hybrid_only_recovered','Hybrid-only recovered'],
      ['baseline_only_recovered','Baseline-only recovered'],
      ['hybrid_total','Hybrid total'],['net_gain','Net gain']]){
      const card=recoveryElement(doc,'article','v9-recovery-stat');
      addText(card,'b','',fmt(view.summary[key]));addText(card,'span','',label);
      summary.appendChild(card);
    }
    context.appendChild(summary);
    const coverage=recoveryElement(doc,'div','v9-recovery-coverage');
    addText(coverage,'span','',
      'Hybrid technical detail '+fmt(view.coverage.hybrid_explained)+' / '
        +fmt(view.coverage.hybrid_requested));
    addText(coverage,'span','',
      'Baseline community context '+fmt(view.coverage.baseline_community)+' / '
        +fmt(view.coverage.baseline_requested));
    if(view.coverage.hybrid_structural_fallback){
      addText(coverage,'span','',
        'Hybrid structural fallback '+fmt(view.coverage.hybrid_structural_fallback));
    }
    context.appendChild(coverage);
    if(record){
      const scores=recoveryElement(doc,'div','v9-recovery-coverage');
      for(const [key,label] of [
        ['baseline_raw','Baseline score'],
        ['baseline_percentile','Baseline percentile'],
        ['seed0_gnn_percentile','Seed-0 GNN percentile'],
        ['seed0_gnn_probability','Seed-0 GNN probability'],
        ['seed0_hybrid_score','Hybrid percentile-fusion score']]){
        if(typeof record[key]==='number'){
          addText(scores,'span','',label+': '+fmt(record[key])
            +(key==='seed0_hybrid_score'?' (percentile fusion, not probability)':''));
        }
      }
      context.appendChild(scores);
    }
    parent.appendChild(context);
  }
  function renderRecordStatus(detail,record){
    const copy={
      not_selected:'This case was retained in the cohort summary but was not selected for detail.',
      selected:'Selected detail is not available in the published bundle.',
      unavailable:'Detail is unavailable; no evidence is inferred.',
      failed:'Detail generation failed; no replacement case was selected.'
    }[record.detailStatus||'not_selected'];
    if(copy)addText(detail,'div','v9-recovery-status',copy);
    if(record.failureReason)addText(detail,'p','v9-recovery-intro',
      'Recorded reason: '+String(record.failureReason));
    if(record.explanationUnavailableReason)addText(detail,'p','v9-recovery-intro',
      'GNNExplainer was not run for this case: '
        +String(record.explanationUnavailableReason)
        +'. The exact two-hop input exceeded the explainer limits, so structural community context is published instead.');
  }
  function renderLoading(detail){
    detail.setAttribute('aria-busy','true');
    const section=recoveryElement(doc,'section','v9-recovery-loading');
    section.setAttribute('role','status');
    addText(section,'span','v9-recovery-sr-only','Loading selected evidence');
    section.appendChild(recoveryElement(doc,'div','v9-recovery-skeleton is-graph'));
    section.appendChild(recoveryElement(doc,'div','v9-recovery-skeleton is-copy'));
    section.appendChild(recoveryElement(doc,'div','v9-recovery-skeleton is-copy is-short'));
    detail.appendChild(section);
  }
  function renderError(detail,error){
    detail.setAttribute('aria-busy','false');
    const section=recoveryElement(doc,'section','v9-recovery-error');
    section.setAttribute('role','alert');
    addText(section,'h4','','Selected evidence could not be loaded');
    addText(section,'p','',recoveryServerHelp(error));
    const retry=recoveryElement(doc,'button','v9-recovery-button v9-recovery-retry','Retry evidence');
    retry.type='button';retry.dataset.v3Retry='true';
    retry.setAttribute('aria-label','Retry selected GNN evidence');
    section.appendChild(retry);
    detail.appendChild(section);
  }
  function renderRanks(parent,record){
    const panel=recoveryElement(doc,'section','v9-recovery-v3-panel');
    addText(panel,'h5','','Rank comparison');
    const values=[['Baseline rank',record.baseline_rank,false],
      ['Seed-0 Hybrid rank',record.seed0_hybrid_rank,true]];
    const ranks=recoveryElement(doc,'div','v9-recovery-ranks');
    for(const [label,value,primary] of values){
      const cell=recoveryElement(doc,'div','v9-recovery-rank'+(primary?' is-primary':''));
      addText(cell,'b','',fmt(value));addText(cell,'span','',label);
      ranks.appendChild(cell);
    }
    const delta=recoveryRankDelta(record);
    addText(ranks,'div','v9-recovery-rank-delta',
      delta===null?'Rank movement unavailable'
        :delta>0?fmt(delta)+' places higher than Baseline'
        :delta<0?fmt(Math.abs(delta))+' places lower than Baseline'
        :'No rank movement recorded');
    panel.appendChild(ranks);
    parent.appendChild(panel);
  }
  function renderCaseNavigation(grid,rows){
    const list=recoveryElement(doc,'aside','v9-recovery-v3-list');
    list.setAttribute('aria-label','Published GNN explanations');
    addText(list,'h4','',eligibleCountLabel(rows));
    const picker=recoveryElement(doc,'select','v9-recovery-v3-picker');
    picker.dataset.v3Change='case';
    picker.setAttribute('aria-label','Select published GNN explanation');
    for(const record of rows){
      const option=recoveryElement(doc,'option','',record.personId
        +' · Hybrid rank '+fmt(record.seed0_hybrid_rank));
      option.value=record.caseId;picker.appendChild(option);
    }
    if(state.caseId)picker.value=state.caseId;
    if(!rows.length){
      addText(list,'div','v9-recovery-empty',
        'No published GNN explanations are available.');
    }
    for(const record of rows){
      const button=recoveryElement(doc,'button','v9-recovery-case');
      button.type='button';button.dataset.v3Case=record.caseId;
      button.setAttribute('aria-current',String(record.caseId===state.caseId));
      button.setAttribute('aria-label','Inspect published GNN explanation for '
        +record.personId);
      addText(button,'strong','',record.personId);
      addText(button,'div','v9-recovery-case-meta',
        'Hybrid rank '+fmt(record.seed0_hybrid_rank));
      const delta=recoveryRankDelta(record);
      addText(button,'div','v9-recovery-case-evidence',
        delta===null?'Rank movement unavailable'
          :delta>0?fmt(delta)+' places higher than Baseline'
          :delta<0?fmt(Math.abs(delta))+' places lower than Baseline'
          :'No rank movement recorded');
      list.appendChild(button);
    }
    grid.appendChild(list);
    grid.appendChild(picker);
  }
  function renderFactors(column,explanation){
    const panel=recoveryElement(doc,'section','v9-recovery-panel');
    const head=recoveryElement(doc,'div','v9-recovery-panel-head');
    addText(head,'h5','','Key counterfactual factors');
    addText(head,'p','',
      'Measured effect is the rank change when a factor is removed. Zero-rank-movement factors are omitted. Restart support reports whether the explainer selected that factor consistently across deterministic restarts.');
    panel.appendChild(head);
    const factors=Array.isArray(explanation.factors)
      ?explanation.factors.filter(factor=>recoveryValidFactor(factor)
        &&factor.counterfactual.ablated_hybrid_rank!==factor.counterfactual.original_hybrid_rank).slice():[];
    factors.sort((left,right)=>
      Number(right.stability==='stable')-Number(left.stability==='stable')
      ||Math.abs(right.counterfactual.ablated_hybrid_rank-right.counterfactual.original_hybrid_rank)
        -Math.abs(left.counterfactual.ablated_hybrid_rank-left.counterfactual.original_hybrid_rank)
      ||recoveryCompareId(left.factor_id,right.factor_id));
    if(factors.length&&!factors.some(factor=>factor.stability==='stable')){
      addText(panel,'div','v9-recovery-status',
        'No factor was consistently selected across restarts. Measured rank effects are shown separately from restart support below.');
    }
    if(!factors.length){
      addText(panel,'div','v9-recovery-status',
        'No measured factors are available for this explanation.');
    }else{
      const list=recoveryElement(doc,'div','v9-recovery-factor-list');
      for(const factor of factors){
        const button=recoveryElement(doc,'button','v9-recovery-factor');
        button.type='button';button.dataset.v3Factor=factor.factor_id;
        button.title=factor.factor_id;
        button.setAttribute('aria-pressed',
          String(state.selectedFactorId===factor.factor_id));
        const readable=buildRecoveryFactorViewModel({
          factors:[factor],community:explanation.community
        })[0];
        button.setAttribute('aria-label',
          'Show '+readable.effectLabel+' for '+recoveryVisibleText(readable.label)
            +'; restart support '+readable.stabilityLabel);
        addText(button,'strong','',readable.label);
        addText(button,'span','v9-recovery-factor-signal',
          'Effect: '+recoveryFormatSigned(readable.effect)+' ranks ('
            +readable.effectLabel+'; ablated minus original)');
        addText(button,'span','',
          'Restart support: '+readable.stabilityLabel);
        list.appendChild(button);
      }
      panel.appendChild(list);
      addText(panel,'p','v9-recovery-canvas-note',
        'Per-factor provenance is published as separate attribution overlay evidence and is not drawn on the community graph in this view.');
    }
    column.appendChild(panel);
  }
  function renderNarrative(column,explanation){
    const narrative=validateRecoveryNarrative(explanation.llm_narrative);
    const panel=recoveryElement(doc,'section','v9-recovery-narrative');
    addText(panel,'h5','',narrative.visible&&narrative.source==='llm'
      ?'LLM explanation':'Evidence explanation');
    if(!narrative.visible){
      addText(panel,'p','v9-recovery-status',
        'LLM explanation unavailable for this published case.');
    }else{
      addText(panel,'p','',narrative.source==='llm'
        ?'Validated local Gemma: '+narrative.model
        :'Deterministic evidence summary.');
      addText(panel,'p','',narrative.summary);
      recoveryAppendSources(doc,panel,narrative.summarySourceRefs);
      for(const claim of narrative.claims){
        addText(panel,'p','',claim.text);
        recoveryAppendSources(doc,panel,claim.source_refs);
      }
    }
    column.appendChild(panel);
  }
  function renderStabilityAndFaithfulness(column,explanation){
    const panel=recoveryElement(doc,'section','v9-recovery-panel');
    const head=recoveryElement(doc,'div','v9-recovery-panel-head');
    addText(head,'h5','','Restart stability and removal faithfulness');
    panel.appendChild(head);
    const stability=explanation.stability;
    if(recoveryIsRecord(stability)
        &&recoverySafeInteger(stability.stable_factor_count,false)){
      addText(panel,'div','',
        'Stable factors across deterministic restarts: '
          +fmt(stability.stable_factor_count));
      if(recoveryNonBlankString(stability.signed_effect_source)){
        addText(panel,'div','',
          'Signed effect source: '+stability.signed_effect_source);
      }
    }else{
      addText(panel,'div','v9-recovery-status',
        'Restart stability is unavailable in this artifact.');
    }
    const faithfulness=explanation.faithfulness;
    const points=recoveryIsRecord(faithfulness)?faithfulness.points:null;
    if(!recoveryIsRecord(faithfulness)||!Array.isArray(points)||!points.length
        ||!recoveryFiniteUnit(faithfulness.original_probability)){
      addText(panel,'div','v9-recovery-status',
        'Edge-removal faithfulness is unavailable in this artifact.');
      column.appendChild(panel);return;
    }
    addText(panel,'p','',
      'Removing the highest-attribution edges is compared against a matched random control. A larger top-edge drop than its matched control is evidence the attribution tracked the score.');
    addText(panel,'div','',
      'Seed-0 probability before removal: '
        +recoveryFormatNumber(faithfulness.original_probability));
    const table=recoveryElement(doc,'table','v9-recovery-table');
    table.setAttribute('aria-label','Edge removal faithfulness by removed fraction');
    const header=recoveryElement(doc,'tr');
    for(const label of ['Removed fraction','Top-edge drop','Matched random drop',
      'Unmatched controls']){
      header.appendChild(recoveryElement(doc,'th','',label));
    }
    table.appendChild(header);
    for(const point of points){
      if(!recoveryIsRecord(point))continue;
      const row=recoveryElement(doc,'tr');
      const matched=typeof point.matched_random_probability_drop==='number'
        ?recoveryFormatNumber(point.matched_random_probability_drop)
        :'not measured';
      for(const value of [recoveryFormatNumber(point.fraction),
        recoveryFormatNumber(point.top_edge_probability_drop),matched,
        recoveryFormatNumber(point.unmatched_control_count)]){
        row.appendChild(recoveryElement(doc,'td','',value));
      }
      table.appendChild(row);
    }
    panel.appendChild(table);
    column.appendChild(panel);
  }
  function graphButton(label,action,value,pressed,ariaLabel){
    const button=recoveryElement(doc,'button','v9-recovery-button',label);
    button.type='button';button.dataset[action]=value;
    if(pressed!==null)button.setAttribute('aria-pressed',String(pressed));
    button.setAttribute('aria-label',ariaLabel||label);
    return button;
  }
  function graphControlGroup(label){
    const group=recoveryElement(doc,'div','v9-recovery-control-group');
    group.setAttribute('role','group');group.setAttribute('aria-label',label);
    addText(group,'span','v9-recovery-control-label',label);
    const controls=recoveryElement(doc,'div','v9-recovery-control-items');
    group.appendChild(controls);return {group,controls};
  }
  function stageDescription(stageId){
    return {
      first_hop:'Immediate message-passing relationships around the target.',
      second_hop:'Relationships available within two message-passing hops.',
      component_pool:'Co-travel links between members included in component pooling.',
      rank_fusion:'Attributed explanation evidence at the final rank-fusion stage.'
    }[stageId]||'Published explanation stage.';
  }
  function renderGraphTable(panel,commands,record){
    const wrap=recoveryElement(doc,'div','v9-recovery-table-wrap');
    addText(wrap,'h6','','Community data table');
    addText(wrap,'p','v9-recovery-canvas-note',
      'Non-canvas equivalent of the graph above. Emphasis matches the selected stage.');
    const tableNodes=Array.isArray(commands.tableNodes)
      ?commands.tableNodes:commands.nodes;
    const tableEdges=Array.isArray(commands.tableEdges)
      ?commands.tableEdges:commands.edges;
    const nodePages=Math.max(1,Math.ceil(tableNodes.length/25));
    const edgePages=Math.max(1,Math.ceil(tableEdges.length/25));
    const nodePage=Math.min(Math.max(0,state.nodeTablePage),nodePages-1);
    const edgePage=Math.min(Math.max(0,state.edgeTablePage),edgePages-1);
    const nodeTable=recoveryElement(doc,'table','v9-recovery-table');
    nodeTable.setAttribute('aria-label',
      'Community members for '+recoveryVisibleText(record.personId));
    const nodeHead=recoveryElement(doc,'tr');
    for(const label of ['Member','Focal','Pooled member','Caught before snapshot',
      'Evidence weight','Evidence rank']){
      nodeHead.appendChild(recoveryElement(doc,'th','',label));
    }
    nodeTable.appendChild(nodeHead);
    for(const node of tableNodes.slice(nodePage*25,nodePage*25+25)){
      const row=recoveryElement(doc,'tr');
      const nodeId=node.id===undefined?node.node_id:node.id;
      const weight=typeof node.importance==='number'
        ?recoveryFormatNumber(node.importance):'none';
      const rank=Number.isSafeInteger(node.rank)
        ?recoveryFormatNumber(node.rank):'none';
      for(const value of [nodeId,node.target?'yes':'no',
        node.pooledMember?'yes':'no',node.caughtBeforeSnapshot?'yes':'no',
        weight,rank]){
        row.appendChild(recoveryElement(doc,'td','',String(value)));
      }
      nodeTable.appendChild(row);
    }
    wrap.appendChild(nodeTable);
    const nodeNav=recoveryElement(doc,'div','v9-recovery-pager');
    nodeNav.appendChild(graphButton('Previous members','v3Page','node-prev',null,
      'Previous page of community members'));
    addText(nodeNav,'span','','Members page '+fmt(nodePage+1)+' / '+fmt(nodePages));
    nodeNav.appendChild(graphButton('Next members','v3Page','node-next',null,
      'Next page of community members'));
    wrap.appendChild(nodeNav);
    const edgeTable=recoveryElement(doc,'table','v9-recovery-table');
    edgeTable.setAttribute('aria-label',
      'Community relationships for '+recoveryVisibleText(record.personId));
    const edgeHead=recoveryElement(doc,'tr');
    for(const label of ['Relationship','Relation','From','To','Emphasized',
      'Evidence weight','Evidence rank']){
      edgeHead.appendChild(recoveryElement(doc,'th','',label));
    }
    edgeTable.appendChild(edgeHead);
    for(const edge of tableEdges.slice(edgePage*25,edgePage*25+25)){
      const row=recoveryElement(doc,'tr');
      const edgeId=edge.id===undefined?edge.edge_id:edge.id;
      const weight=typeof edge.importance==='number'
        ?recoveryFormatNumber(edge.importance):'none';
      const rank=Number.isSafeInteger(edge.rank)
        ?recoveryFormatNumber(edge.rank):'none';
      for(const value of [edgeId,edge.relation,edge.u,edge.v,
        edge.emphasized?'yes':'no',weight,rank]){
        row.appendChild(recoveryElement(doc,'td','',String(value)));
      }
      edgeTable.appendChild(row);
    }
    wrap.appendChild(edgeTable);
    const edgeNav=recoveryElement(doc,'div','v9-recovery-pager');
    edgeNav.appendChild(graphButton('Previous relationships','v3Page','edge-prev',
      null,'Previous page of community relationships'));
    addText(edgeNav,'span','','Relationships page '+fmt(edgePage+1)+' / '+fmt(edgePages));
    edgeNav.appendChild(graphButton('Next relationships','v3Page','edge-next',null,
      'Next page of community relationships'));
    wrap.appendChild(edgeNav);
    panel.appendChild(wrap);
  }
  function renderGraph(column,detailView,record){
    const control=detailView.kind==='community_control';
    const stageId=activeStageId(detailView.kind);
    const stageLabels={first_hop:'First hop',second_hop:'Second hop',
      component_pool:'Component pool',rank_fusion:'Rank fusion'};
    const options={mode:state.mode,stageId,
      selectedFactorId:null,query:state.query};
    const commands=control
      ?buildStructuralDrawCommands(detailView.control,options)
      :buildCommunityDrawCommands(detailView.explanation,options);
    if(!commands.available){
      const panel=recoveryElement(doc,'section','v9-recovery-graph-panel');
      addText(panel,'h5','','As-of community context + explanation evidence');
      addText(panel,'div','v9-recovery-empty',
        'Strict-bound unavailable: complete community unavailable ('
          +commands.reason+'). The complete data table is not rendered because the graph command failed closed.');
      column.appendChild(panel);return {commands:null,panel};
    }
    const canvasCommands=filterRecoveryGraphCommands(commands,state.relationship);
    if(canvasCommands.relationship!==state.relationship){
      state.relationship=canvasCommands.relationship;
    }
    const panel=recoveryElement(doc,'section','v9-recovery-graph-panel');
    const head=recoveryElement(doc,'div','v9-recovery-panel-head');
    addText(head,'h5','','As-of community context + explanation evidence');
    addText(head,'p','',control
      ?'Muted context remains visible. This control has no explanation evidence or attribution mask.'
      :'Muted context remains visible. Model evidence weight controls explanation-edge width and brightness via the unsigned explainer median. This is not a causal claim.');
    panel.appendChild(head);
    const toolbar=recoveryElement(doc,'div','v9-recovery-toolbar');
    toolbar.setAttribute('role','toolbar');
    toolbar.setAttribute('aria-label','Community graph controls');
    const viewGroup=graphControlGroup('Graph view');
    viewGroup.controls.appendChild(graphButton('Evidence first','v3Mode','flow',
      state.mode==='flow','Show evidence-first graph view'));
    viewGroup.controls.appendChild(graphButton('Full community','v3Mode','all',
      state.mode==='all','Show full community graph view'));
    toolbar.appendChild(viewGroup.group);
    const stageGroup=graphControlGroup('Explanation stage');
    for(const value of stageIdsFor(detailView.kind)){
      stageGroup.controls.appendChild(graphButton(stageLabels[value],'v3Stage',value,
        stageId===value,'Show '+stageLabels[value].toLowerCase()+' explanation stage'));
    }
    toolbar.appendChild(stageGroup.group);
    // Counts let a reviewer see what a relationship filter will yield before
    // spending a click on an empty canvas.
    const relationCounts=new Map();
    for(const edge of commands.edges){
      const key=recoveryRelationPresentation(edge&&edge.relation).key;
      relationCounts.set(key,(relationCounts.get(key)||0)+1);
    }
    const relationGroup=graphControlGroup('Relationship type');
    for(const option of canvasCommands.relationshipOptions){
      const count=option.key==='all'
        ?commands.edges.length:(relationCounts.get(option.key)||0);
      const button=graphButton(option.label,'v3Relation',option.key,
        state.relationship===option.key,
        'Show '+option.label.toLowerCase()+' relationships, '+fmt(count)
          +' in this graph view');
      addText(button,'span','v9-recovery-button-count',fmt(count));
      relationGroup.controls.appendChild(button);
    }
    toolbar.appendChild(relationGroup.group);
    const labelGroup=graphControlGroup('Node labels');
    const density=recoveryElement(doc,'select','v9-recovery-select');
    density.dataset.v3Change='density';density.setAttribute('aria-label','Node labels');
    for(const pair of [['key','Key labels'],['all','All labels'],['none','No labels']]){
      const option=recoveryElement(doc,'option','',pair[1]);
      option.value=pair[0];density.appendChild(option);
    }
    density.value=state.labelDensity;labelGroup.controls.appendChild(density);
    toolbar.appendChild(labelGroup.group);
    const searchGroup=graphControlGroup('Find node');
    const search=recoveryElement(doc,'input','v9-recovery-search');
    search.type='search';search.value=state.query;search.placeholder='Person ID';
    search.dataset.v3Input='search';
    search.setAttribute('aria-label','Search node identifiers');
    searchGroup.controls.appendChild(search);
    toolbar.appendChild(searchGroup.group);
    const navigationGroup=graphControlGroup('Graph navigation');
    navigationGroup.controls.appendChild(graphButton('+','v3Zoom','in',null,'Zoom in'));
    navigationGroup.controls.appendChild(graphButton('-','v3Zoom','out',null,'Zoom out'));
    navigationGroup.controls.appendChild(graphButton('Reset view','v3Zoom','reset',null,'Reset graph view'));
    toolbar.appendChild(navigationGroup.group);
    panel.appendChild(toolbar);
    addText(panel,'p','v9-recovery-canvas-note',stageDescription(stageId));
    if(state.relationship!=='all'&&!canvasCommands.edges.length){
      addText(panel,'div','v9-recovery-status',
        'No '+recoveryVisibleText((canvasCommands.relationshipOptions.find(option=>
          option.key===state.relationship)||{label:'selected'}).label).toLowerCase()
          +' relationships are available in this graph view. Complete tables retain all relationships.');
    }
    const legend=recoveryElement(doc,'div','v9-recovery-legend');
    legend.setAttribute('role','list');
    legend.setAttribute('aria-label','Graph legend');
    function legendItem(label,swatchClass,description){
      const item=recoveryElement(doc,'div','v9-recovery-legend-item');
      item.setAttribute('role','listitem');
      item.setAttribute('aria-label',label+(description?': '+description:''));
      if(description)item.setAttribute('title',label+' - '+description);
      const swatch=recoveryElement(doc,'span','v9-recovery-legend-swatch '+swatchClass);
      swatch.setAttribute('aria-hidden','true');
      item.appendChild(swatch);
      addText(item,'span','',label);
      legend.appendChild(item);
    }
    legendItem('Target','is-target','selected person');
    legendItem('Caught before snapshot','is-caught','label available before T');
    const relationLegendClasses={COTRAVEL:'is-cotravel',RESIDENCE:'is-residence',
      SHARED_PLATE:'is-shared-plate'};
    for(const option of canvasCommands.relationshipOptions){
      if(option.key==='all')continue;
      const swatchClass=relationLegendClasses[option.key]||'is-other-relation';
      legendItem(option.label,swatchClass,
        recoveryRelationLegendDescription(option.key));
    }
    legendItem('Model evidence weight','is-evidence','gold underlay width and brightness follow unsigned GNNExplainer attribution');
    legendItem('Attributed node','is-attributed-node','gold ring shows ranked model evidence');
    panel.appendChild(legend);
    // The full encoding caveat stays on the page but out of the reading path
    // between the controls and the graph itself.
    const description=recoveryElement(doc,'p','v9-recovery-canvas-note is-fine-print',
      control
        ?'Gold underlay shows model evidence weight. Inner color and pattern show the observable relationship type. Community controls have no attribution mask.'
        :'Gold underlay shows model evidence weight. Inner color and pattern show the observable relationship type. Model evidence weight is unsigned GNNExplainer salience, not a causal claim.');
    description.id='v9-recovery-v3-canvas-description';
    if(commands.sampled){
      addText(panel,'div','v9-recovery-sampled',
        'Sampled context: showing '+fmt(canvasCommands.nodes.length)+' of '
          +fmt(commands.fullNodeCount)+' nodes and '+fmt(canvasCommands.edges.length)
          +' of '+fmt(commands.fullEdgeCount)
          +' relationships for canvas performance; complete tables remain available.');
    }
    if(detailView.canvasAvailable){
      const wrap=recoveryElement(doc,'div','v9-recovery-canvas-wrap');
      const canvas=recoveryElement(doc,'canvas','v9-recovery-canvas');
      canvas.tabIndex=0;canvas.setAttribute('role','img');
      canvas.setAttribute('aria-label',
        (control
          ?'Community context graph for '
            +(record.cohort==='baseline_only'
              ?'baseline control ':'Hybrid structural fallback ')
          :'Community graph for Hybrid case ')
          +recoveryVisibleText(record.personId)+', '
          +(state.mode==='flow'?['Evidence','first'].join(' '):'Full community')+' view, '
          +stageLabels[stageId]+' stage, '
          +(canvasCommands.relationshipOptions.find(option=>option.key===canvasCommands.relationship)
            ||{label:'All types'}).label+' relationships, '
          +fmt(canvasCommands.nodes.length)+' members and '+fmt(canvasCommands.edges.length)
          +' relationships. Model evidence weight is unsigned GNNExplainer salience, not a causal claim.');
      canvas.setAttribute('aria-describedby','v9-recovery-v3-canvas-description');
      canvas.textContent='Interactive community graph. Use the toolbar for keyboard controls.';
      wrap.appendChild(canvas);panel.appendChild(wrap);
      pendingCanvas={canvas,commands:canvasCommands};
    }else{
      addText(panel,'div','v9-recovery-status',
        'Strict-bound unavailable: community graph is not drawn: '
          +fmt(detailView.nodeCount)+' members and '
          +fmt(detailView.edgeCount)
          +' relationships exceed the interactive rendering bound. The complete data table below carries the same evidence.');
    }
    panel.appendChild(description);
    column.appendChild(panel);
    return {commands,panel};
  }
  function renderSelectedEvidence(detail,record){
    if(state.error){
      renderError(detail,state.error);
      return;
    }
    if(state.loading){
      renderLoading(detail);
      return;
    }
    detail.setAttribute('aria-busy','false');
    if(record.detailKind===null){
      renderRecordStatus(detail,record);return;
    }
    const communityView=assembleRecoverySchema3Community(
      state.community,state.nodeRows,state.edgeRows);
    const overlayRows=record.detailKind==='gnn_explanation'
      ?mergeRecoverySchema3Overlay(communityView.community,
        state.overlayNodeRows,state.overlayEdgeRows)
      :null;
    const detailView=buildRecoverySchema3Detail(
      record,state.caseData,communityView,overlayRows);
    if(!detailView.available){
      addText(detail,'div','v9-recovery-empty',
        'Selected evidence unavailable. '+detailView.reason+'.');
      renderRecordStatus(detail,record);return;
    }
    if(detailView.kind==='community_control'){
      addText(detail,'div','v9-recovery-status',
        record.cohort==='baseline_only'
          ?'Community context only: GNNExplainer was not run for this baseline control.'
          :'Community context only: GNNExplainer was not run for this Hybrid structural fallback.');
      addText(detail,'p','v9-recovery-intro',
        'No GNN explanation, mask, or attribution is generated for this control.');
    }else{
      addText(detail,'div','v9-recovery-status','Hybrid technical detail');
    }
    if(!validateRecoveryEvidenceBoundary(
      {evidence_boundary:detailView.evidenceBoundary},record.scoring_day).available){
      renderRecordStatus(detail,record);return;
    }
    const graph=renderGraph(detail,detailView,record);
    const commands=graph.commands;
    if(!commands){renderRecordStatus(detail,record);return;}
    graphContext={detailView,record,panel:graph.panel,tablesBody:null};
    const explanationRow=recoveryElement(doc,'div','v9-recovery-explanation-row');
    if(detailView.kind==='gnn_explanation'){
      explanationRow.appendChild(renderHighestAttributionPanel(doc,detailView.explanation));
      renderFactors(explanationRow,detailView.explanation);
      renderNarrative(explanationRow,detailView.explanation);
    }else{
      const note=recoveryElement(doc,'section','v9-recovery-panel');
      addText(note,'h5','','Structural evidence only');
      addText(note,'p','',
        'Community membership is observable context, not an attribution claim.');
      explanationRow.appendChild(note);
    }
    detail.appendChild(explanationRow);
    const disclosures=recoveryElement(doc,'div','v9-recovery-disclosures');
    if(detailView.kind==='gnn_explanation'){
      renderDisclosure(disclosures,'stability',
        'Restart stability and removal faithfulness',body=>
          renderStabilityAndFaithfulness(body,detailView.explanation));
    }
    renderDisclosure(disclosures,'tables','Complete community data tables',body=>{
      graphContext.tablesBody=body;
      renderGraphTable(body,commands,record);
    });
    renderDisclosure(disclosures,'cohort','Recovery cohort context',body=>
      renderCohortContext(body,record));
    detail.appendChild(disclosures);
    renderRecordStatus(detail,record);
  }
  function render(){
    canvasCleanup();canvasCleanup=function(){};pendingCanvas=null;graphContext=null;
    const fragment=doc.createDocumentFragment();
    if(!view.available){
      const heading=recoveryElement(doc,'h3','v9-recovery-title',
        'Published GNN explanations unavailable');
      heading.id='v9-recovery-title';fragment.appendChild(heading);
      addText(fragment,'div','v9-recovery-empty',
        'Case evidence unavailable. Published GNN explanations are unavailable. '
          +view.reason+'.');
      root.replaceChildren(fragment);return;
    }
    const rows=visibleRows();
    const record=currentRecord();
    renderSelectedHeader(fragment,record,rows);
    if(!rows.length){
      const empty=recoveryElement(doc,'section','v9-recovery-empty-state');
      addText(empty,'h4','',
        'No published GNN explanations are available in this artifact.');
      addText(empty,'p','',
        'The recovery summary remains available, but no case has validated published explanation detail.');
      const disclosures=recoveryElement(doc,'div','v9-recovery-disclosures');
      renderDisclosure(disclosures,'cohort','Recovery cohort context',body=>
        renderCohortContext(body,null));
      empty.appendChild(disclosures);
      fragment.appendChild(empty);
      root.replaceChildren(fragment);return;
    }
    if(record)renderRanks(fragment,record);
    const grid=recoveryElement(doc,'div','v9-recovery-v3-grid');
    renderCaseNavigation(grid,rows);
    const detail=recoveryElement(doc,'div','v9-recovery-v3-detail');
    detail.setAttribute('aria-label','Selected GNN explanation');
    if(!record){
      addText(detail,'div','v9-recovery-empty',
        'Select a published GNN explanation to inspect its evidence.');
    }else{
      renderSelectedEvidence(detail,record);
    }
    grid.appendChild(detail);fragment.appendChild(grid);
    root.replaceChildren(fragment);
    if(pendingCanvas){
      canvasCleanup=bindRecoveryCanvas(
        pendingCanvas.canvas,pendingCanvas.commands,state);
    }
  }
  async function loadSelected(){
    const token=++requestToken;
    const record=currentRecord();
    state.caseData=null;state.community=null;state.nodeRows=null;
    state.edgeRows=null;state.overlayNodeRows=null;state.overlayEdgeRows=null;
    state.error=null;state.loading=false;
    state.relationship='all';state.scale=1;state.offsetX=0;state.offsetY=0;
    state.selectedFactorId=null;state.nodeTablePage=0;state.edgeTablePage=0;
    state.openDisclosures.clear();
    if(!record||record.detailKind===null){render();return;}
    const caseRef=view.detailIndex[state.caseId]||view.communityIndex[state.caseId];
    if(!caseRef){
      state.error=new Error('Published sidecar reference is missing for this case');
      render();return;
    }
    state.loading=true;render();
    try{
      const payload=await recoveryFetchJson(
        recoverySidecarUrl(view,caseRef.path),caseRef.sha256);
      if(disposed||token!==requestToken)return;
      // The published bundle manifest is schema 3.0, while case sidecar
      // payloads retain the writer's schema 1.0 envelope.
      if(!recoveryIsRecord(payload)
          ||!['1.0','3.0'].includes(payload.schema_version)
          ||!recoveryIsRecord(payload.case)||payload.case.case_id!==state.caseId
          ||payload.cohort!==record.cohort
          ||payload.community_key!==record.community_key){
        throw new Error('Schema-3 case sidecar identity is invalid');
      }
      if(record.cohort==='hybrid_only'
          &&record.detailKind==='gnn_explanation'
          &&!recoveryValidateChunkOwner(payload.overlay_evidence)){
        throw new Error('Schema-3 explanation overlay owner is invalid');
      }
      const communityRef=view.communitySidecarIndex[payload.community_key];
      if(!recoverySchema3Reference(communityRef))
        throw new Error('Schema-3 community sidecar reference is missing');
      const community=await recoveryFetchJson(
        recoverySidecarUrl(view,communityRef.path),communityRef.sha256);
      if(disposed||token!==requestToken)return;
      if(!recoverySchema3Community(community,payload.community_key))
        throw new Error('Schema-3 community sidecar identity is invalid');
      const detail=payload.detail||(
        payload.explanation
          ?{...payload.case,explanation:payload.explanation}
          :null
      );
      state.caseData={...payload,detail};state.community=community;
      render();
      const nodeRows=await loadCommunityRows(community,'node',token);
      if(disposed||token!==requestToken)return;
      const edgeRows=await loadCommunityRows(community,'edge',token);
      if(disposed||token!==requestToken)return;
      state.nodeRows=nodeRows;state.edgeRows=edgeRows;
      if(record.cohort==='hybrid_only'
          &&record.detailKind==='gnn_explanation'){
        const overlayNodeRows=await loadRecoverySchema3OverlayRows(
          view,payload.overlay_evidence,'node',token);
        if(disposed||token!==requestToken)return;
        const overlayEdgeRows=await loadRecoverySchema3OverlayRows(
          view,payload.overlay_evidence,'edge',token);
        if(disposed||token!==requestToken)return;
        const communityView=assembleRecoverySchema3Community(
          community,nodeRows,edgeRows);
        if(!communityView.available){
          throw new Error('Schema-3 community rows are invalid');
        }
        const overlayRows=mergeRecoverySchema3Overlay(
          communityView.community,overlayNodeRows,overlayEdgeRows);
        if(!overlayRows.available){
          throw new Error('Schema-3 overlay presentation is invalid: '
            +overlayRows.reason);
        }
        state.overlayNodeRows=overlayNodeRows;
        state.overlayEdgeRows=overlayEdgeRows;
      }
    }catch(error){if(token===requestToken)state.error=error;}
    if(token===requestToken){state.loading=false;if(!disposed)render();}
  }
  async function loadCommunityRows(community,normalized,token){
    const refs=community[normalized==='node'?'node_chunks':'edge_chunks'];
    if(!Array.isArray(refs))throw new Error('Community chunk index is missing');
    const collected=[];
    for(let index=0;index<refs.length;index+=1){
      const ref=refs[index];
      const payload=await recoveryFetchJson(
        recoverySidecarUrl(view,ref.path),ref.sha256);
      if(disposed||token!==requestToken)return collected;
      const rows=recoveryValidatedChunkRows(
        payload,ref,normalized==='node'?'nodes':'edges');
      if(rows===null)throw new Error('Chunk offset or count contract is invalid');
      let resolved=await recoveryResolveCatalogRows(view,rows,
        normalized==='node'?'nodes':'edges');
      if(disposed||token!==requestToken)return collected;
      if(recoveryIsRecord(community.day_view)){
        resolved=await recoveryApplyDayView(
          view,community,normalized,index,resolved);
        if(disposed||token!==requestToken)return collected;
      }
      collected.push(...resolved);
    }
    return collected;
  }
  async function loadRecoverySchema3OverlayRows(view,owner,normalized,token){
    if(!recoveryValidateChunkOwner(owner)){
      throw new Error('Overlay chunk owner is invalid');
    }
    if(normalized!=='node'&&normalized!=='edge'){
      throw new Error('Overlay row kind is invalid');
    }
    const refs=owner[normalized==='node'?'node_chunks':'edge_chunks'];
    if(!Array.isArray(refs))throw new Error('Overlay chunk index is missing');
    const collected=[];
    for(const ref of refs){
      const payload=await recoveryFetchJson(
        recoverySidecarUrl(view,ref.path),ref.sha256);
      if(disposed||token!==requestToken)return collected;
      const rows=recoveryValidatedChunkRows(
        payload,ref,normalized==='node'?'nodes':'edges');
      if(rows===null)throw new Error('Chunk offset or count contract is invalid');
      collected.push(...rows);
    }
    return collected;
  }
  function onV3Click(event){
    const target=event.target.closest&&event.target.closest(
      '[data-v3-filter],[data-v3-case],[data-v3-mode],[data-v3-stage],'
        +'[data-v3-relation],[data-v3-zoom],[data-v3-factor],[data-v3-page],[data-v3-retry]');
    if(!target||!root.contains(target))return;
    const data=target.dataset;
    if(data.v3Filter){
      state.filter=data.v3Filter;
      const rows=filterRecoverySchema3Cases(view,state.filter);
      if(!rows.some(item=>item.caseId===state.caseId)){
        state.caseId=(rows[0]||{}).caseId||null;
        loadSelected();return;
      }
      const anchorTop=measureAnchor(target);
      render();
      restoreV3Focus('data-v3-filter','v3Filter',data.v3Filter);
      restoreAnchor(root.querySelector('[data-v3-filter="'+data.v3Filter+'"]'),
        anchorTop);
      return;
    }
    if(data.v3Case){
      if(data.v3Case===state.caseId){render();return;}
      state.caseId=data.v3Case;loadSelected();return;
    }
    if(data.v3Retry){loadSelected();return;}
    if(data.v3Mode){
      state.mode=data.v3Mode;state.scale=1;state.offsetX=0;state.offsetY=0;
      renderGraphOnly('data-v3-mode','v3Mode',data.v3Mode);return;
    }
    if(data.v3Stage){
      state.stageId=data.v3Stage;state.scale=1;state.offsetX=0;state.offsetY=0;
      renderGraphOnly('data-v3-stage','v3Stage',data.v3Stage);return;
    }
    if(data.v3Relation){
      state.relationship=data.v3Relation;
      state.scale=1;state.offsetX=0;state.offsetY=0;
      renderGraphOnly('data-v3-relation','v3Relation',data.v3Relation);return;
    }
    if(data.v3Factor){
      state.selectedFactorId=state.selectedFactorId===data.v3Factor
        ?null:data.v3Factor;
      const anchorTop=measureAnchor(target);
      render();
      restoreAnchor(root.querySelector('[data-v3-factor="'+data.v3Factor+'"]'),
        anchorTop);
      return;
    }
    if(data.v3Page){
      const direction=data.v3Page.endsWith('next')?1:-1;
      if(data.v3Page.startsWith('node')){
        state.nodeTablePage=Math.max(0,state.nodeTablePage+direction);
      }else{
        state.edgeTablePage=Math.max(0,state.edgeTablePage+direction);
      }
      const anchorTop=measureAnchor(target);
      render();
      restoreV3Focus('data-v3-page','v3Page',data.v3Page);
      restoreAnchor(root.querySelector('[data-v3-page="'+data.v3Page+'"]'),
        anchorTop);
      return;
    }
    if(data.v3Zoom==='in')state.scale=Math.min(6,state.scale*1.25);
    else if(data.v3Zoom==='out')state.scale=Math.max(.25,state.scale/1.25);
    else{state.scale=1;state.offsetX=0;state.offsetY=0;}
    // Zoom and reset change nothing in the DOM, so repaint the live canvas.
    if(!redrawCanvas())renderGraphOnly('data-v3-zoom','v3Zoom',data.v3Zoom);
  }
  function onV3Input(event){
    if(event.target.dataset.v3Input==='search'){
      state.query=event.target.value;
      if(refreshCanvasCommands())return;
      render();
      if(restoreV3Focus('data-v3-input','v3Input','search')){
        const control=root.querySelector('[data-v3-input="search"]');
        if(control&&typeof control.setSelectionRange==='function'){
          control.setSelectionRange(control.value.length,control.value.length);
        }
      }
    }
  }
  function onV3Change(event){
    const control=event.target;const data=control.dataset;
    if(data.v3Change==='case'){
      state.caseId=control.value;loadSelected();return;
    }
    if(data.v3Change==='density'){
      state.labelDensity=control.value;
      if(redrawCanvas())return;
      render();
      restoreV3Focus('data-v3-change','v3Change','density');
    }
  }
  function onV3Toggle(event){
    const details=event.target;
    if(!details||!root.contains(details)||!details.dataset
        ||!details.dataset.v3Disclosure)return;
    const key=details.dataset.v3Disclosure;
    if(details.open)state.openDisclosures.add(key);
    else state.openDisclosures.delete(key);
  }
  root.addEventListener('click',onV3Click);root.addEventListener('input',onV3Input);
  root.addEventListener('change',onV3Change);
  root.addEventListener('toggle',onV3Toggle,true);
  root.classList.add('v9-recovery','v9-recovery-v3');render();
  if(state.caseId)loadSelected();
  return function(){disposed=true;requestToken++;canvasCleanup();
    if(root.classList&&typeof root.classList.remove==='function'){
      root.classList.remove('v9-recovery-v3');
    }
    root.removeEventListener('click',onV3Click);
    root.removeEventListener('input',onV3Input);
    root.removeEventListener('change',onV3Change);
    root.removeEventListener('toggle',onV3Toggle,true);};
}

const recoveryMounts=new WeakMap();

function mountV9RecoveryExplainer(root,artifact,tools){
  if(!root||!root.ownerDocument||!root.classList) return;
  const prior=recoveryMounts.get(root);
  if(prior) prior();
  root.classList.add('v9-recovery');
  const cleanup=mountRecoveryExplorerV3(root,artifact,tools);
  recoveryMounts.set(root,cleanup);
}
"""
