"""Isolated accessible renderer for the V9 GNN architecture comparison."""

GNN_ARCHITECTURE_VIEW_MODEL_JS = r"""
function buildGNNArchitectureViewModel(data, _population, _requestedK, demoData) {
  const gnnIds = ['sage', 'rgcn', 'gat', 'gin', 'kpiaa'];
  const DAILY_BUDGETS = [5, 10, 25];
  const unavailable = () => ({
    available: false,
    dailyKs: [],
    rows: [],
    provenance: null
  });

  if (!data || typeof data !== 'object' || data.artifact_kind !== 'gnn_architecture_comparison'
      || !Array.isArray(data.architecture_order)) return unavailable();

  const dailyKs = (Array.isArray(data.daily_ks) ? data.daily_ks : [])
    .filter(k => Number.isInteger(k) && DAILY_BUDGETS.includes(k));
  const rows = [];
  const dailyMetrics = (metrics, k) => ({
    found: metrics['daily_found@' + k],
    budget: metrics['daily_budget@' + k],
    precision: metrics['daily_precision@' + k],
    recall: metrics['daily_recall@' + k],
    f1: metrics['daily_f1@' + k]
  });

  if (demoData && demoData.overall_daily && demoData.overall_daily.baseline) {
    const baseDaily = demoData.overall_daily.baseline;
    rows.push({
      id: 'baseline',
      label: 'Tabular Baseline',
      looksFor: 'Row-level history, demographics, and prior crossing behaviors.',
      daily: Object.fromEntries(dailyKs.map(k => [String(k), dailyMetrics(baseDaily, k)])),
      isBaseline: true
    });
  }

  gnnIds.forEach(id => {
    const row = data.architectures[id];
    if (!row || !row.ensemble || !row.ensemble.daily) return;
    rows.push({
      id,
      label: row.label,
      looksFor: row.looks_for,
      daily: Object.fromEntries(dailyKs.map(k => [String(k), dailyMetrics(row.ensemble.daily, k)])),
      isBaseline: false
    });
  });

  const firstGnn = data.architectures[gnnIds[0]];
  const dailyDays = firstGnn && firstGnn.ensemble && firstGnn.ensemble.daily
    ? firstGnn.ensemble.daily.n_days : null;
  return {
    available: true,
    dailyKs,
    nDays: dailyDays,
    dailyDays,
    rows,
    provenance: {
      corpus: data.corpus,
      seeds: Array.isArray(data.seeds) ? data.seeds.slice() : [],
      epochs: data.epochs,
      trainBucket: data.train_bucket
    }
  };
}
"""

GNN_ARCHITECTURE_CSS = r"""
#v9-gnn-architecture-comparison {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.02);
  margin-top: 18px;
}
#v9-gnn-architecture-comparison h3 {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text1);
  letter-spacing: -0.01em;
}
#v9-gnn-architecture-comparison .gnn-hint {
  color: var(--text2);
  font-size: 12px;
  line-height: 1.5;
  margin-bottom: 24px;
  max-width: 720px;
}
#v9-gnn-architecture-comparison .gnn-controls-row {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  align-items: flex-end;
  margin-bottom: 24px;
}
#v9-gnn-architecture-comparison .gnn-segmented {
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: rgba(0,0,0,0.02);
}
#v9-gnn-architecture-comparison .gnn-segmented button {
  border: 0;
  border-radius: 4px;
  padding: 6px 12px;
  color: var(--text2);
  background: transparent;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}
#v9-gnn-architecture-comparison .gnn-segmented button[aria-pressed="true"] {
  color: var(--text1);
  background: var(--surface);
  box-shadow: 0 1px 2px rgba(0,0,0,0.06);
}
#v9-gnn-architecture-comparison .gnn-segmented button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
#v9-gnn-architecture-comparison .gnn-depth-select {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--text2);
  font-weight: 500;
}
#v9-gnn-architecture-comparison select {
  padding: 6px 28px 6px 12px;
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  color: var(--text1);
  background: var(--surface);
  font-size: 12px;
  cursor: pointer;
  appearance: auto;
}
#v9-gnn-architecture-comparison .gnn-chart-wrap {
  width: 100%;
  overflow-x: auto;
  margin-bottom: 24px;
}
#v9-gnn-architecture-comparison svg {
  display: block;
  width: 100%;
  min-width: 600px;
  max-width: 800px;
  height: auto;
}
#v9-gnn-architecture-comparison svg text {
  fill: var(--text2);
  font-size: 12px;
}
#v9-gnn-architecture-comparison .gnn-axis {
  stroke: var(--border);
  stroke-width: 1px;
}
#v9-gnn-architecture-comparison .gnn-bar {
  fill: var(--text1);
  transition: width 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}
#v9-gnn-architecture-comparison .gnn-bar.baseline {
  fill: var(--text3);
}
#v9-gnn-architecture-comparison .gnn-bar-label {
  fill: var(--text1);
  font-size: 12px;
  font-weight: 500;
}
#v9-gnn-architecture-comparison .gnn-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  margin-bottom: 16px;
}
#v9-gnn-architecture-comparison table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  text-align: left;
}
#v9-gnn-architecture-comparison th, 
#v9-gnn-architecture-comparison td {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
}
#v9-gnn-architecture-comparison tbody tr:last-child th,
#v9-gnn-architecture-comparison tbody tr:last-child td {
  border-bottom: 0;
}
#v9-gnn-architecture-comparison th {
  color: var(--text2);
  font-weight: 500;
  white-space: nowrap;
}
#v9-gnn-architecture-comparison th:nth-child(2),
#v9-gnn-architecture-comparison td:nth-child(2) {
  min-width: 180px;
  max-width: 300px;
  white-space: normal;
}
#v9-gnn-architecture-comparison td.numeric {
  font-variant-numeric: tabular-nums;
  text-align: right;
}
#v9-gnn-architecture-comparison th.numeric {
  text-align: right;
}
#v9-gnn-architecture-comparison .baseline-row {
  background: rgba(0,0,0,0.015);
}
#v9-gnn-architecture-comparison details {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  overflow: hidden;
  margin-bottom: 24px;
}
#v9-gnn-architecture-comparison summary {
  padding: 12px 14px;
  cursor: pointer;
  font-weight: 500;
  font-size: 13px;
  color: var(--text1);
  user-select: none;
  background: rgba(0,0,0,0.01);
}
#v9-gnn-architecture-comparison .gnn-details-content {
  padding: 0 14px 14px;
  border-top: 1px solid var(--border);
}
#v9-gnn-architecture-comparison .gnn-details-content h4 {
  margin: 16px 0 8px;
  font-size: 12px;
  color: var(--text2);
  font-weight: 600;
}
#v9-gnn-architecture-comparison .gnn-provenance {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  color: var(--text3);
  font-size: 11px;
}
#v9-gnn-architecture-comparison .gnn-sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0;
}
#v9-gnn-architecture-comparison .gnn-f1-chart-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}
#v9-gnn-architecture-comparison .gnn-f1-chart {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: var(--surface);
}
#v9-gnn-architecture-comparison .gnn-f1-chart h4 {
  margin: 0;
  color: var(--text1);
  font-size: 12px;
  font-weight: 600;
}
#v9-gnn-architecture-comparison .gnn-chart-subtitle {
  margin: 4px 0 14px;
  color: var(--text3);
  font-size: 10px;
  line-height: 1.4;
}
#v9-gnn-architecture-comparison .gnn-chart-axis {
  display: flex;
  justify-content: space-between;
  margin: 0 0 5px 92px;
  color: var(--text3);
  font-family: var(--font-mono);
  font-size: 9px;
}
#v9-gnn-architecture-comparison .gnn-chart-row {
  display: grid;
  grid-template-columns: 84px minmax(0, 1fr) 38px;
  gap: 7px;
  align-items: center;
  margin: 7px 0;
}
#v9-gnn-architecture-comparison .gnn-chart-label {
  overflow: hidden;
  color: var(--text2);
  font-size: 10px;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}
#v9-gnn-architecture-comparison .gnn-chart-row.baseline .gnn-chart-label {
  color: var(--text1);
  font-weight: 600;
}
#v9-gnn-architecture-comparison .gnn-chart-track {
  height: 9px;
  overflow: hidden;
  border-radius: 3px;
  background: var(--border);
}
#v9-gnn-architecture-comparison .gnn-chart-fill {
  height: 100%;
  min-width: 2px;
  border-radius: 3px;
  background: #4f7890;
}
#v9-gnn-architecture-comparison .gnn-chart-fill.baseline {
  background: var(--text3);
}
#v9-gnn-architecture-comparison .gnn-chart-value {
  color: var(--text1);
  font-family: var(--font-mono);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
#v9-gnn-architecture-comparison .gnn-chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  margin-top: 14px;
  color: var(--text3);
  font-size: 10px;
}
#v9-gnn-architecture-comparison .gnn-chart-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
#v9-gnn-architecture-comparison .gnn-chart-swatch {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  background: #4f7890;
}
#v9-gnn-architecture-comparison .gnn-chart-swatch.baseline {
  background: var(--text3);
}
@media (max-width: 700px) {
  #v9-gnn-architecture-comparison .gnn-controls-row {
    flex-direction: column;
    align-items: stretch;
  }
  #v9-gnn-architecture-comparison .gnn-f1-chart-grid {
    grid-template-columns: 1fr;
  }
}
"""

GNN_ARCHITECTURE_UI_JS = r"""
function mountV9GNNArchitectureComparison(mount, artifact, helpers, demoArtifact) {
  if (!mount) return;
  const architectureLabels = {
    baseline: 'Tabular Baseline',
    sage: 'GraphSAGE',
    rgcn: 'RGCN full graph',
    gat: 'GAT (attention)',
    gin: 'GIN',
    kpiaa: 'KPI-AA (approx)'
  };
  const escapeValue = value => {
    const candidate = helpers && (helpers.escapeHTML || helpers.escapeHtml || helpers.escape || helpers.esc);
    if (typeof candidate === 'function') return candidate(String(value == null ? '' : value));
    return String(value == null ? '' : value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  };
  const fmt = value => Number(value).toLocaleString(undefined, {maximumFractionDigits: 4});
  const architectureDescription = value => {
    const text = String(value == null ? '' : value).trim();
    const sentence = text.match(/^.*?[.!?](?:\s|$)/);
    return (sentence ? sentence[0] : text).trim();
  };
  const unavailable = () => {
    mount.innerHTML = '<h3 id="v9-gnn-architecture-title">GNN architecture comparison unavailable</h3><p>No GNN architecture comparison artifact is embedded. Rerun <code>.venv/bin/python -m gnn.gnn_architecture_bakeoff</code> to publish it.</p>';
  };
  
  if (!artifact) { unavailable(); return; }
  const render = () => {
    const vm = buildGNNArchitectureViewModel(artifact, null, null, demoArtifact);
    if (!vm.available) { unavailable(); return; }
    const rows = vm.rows;
    const esc = escapeValue;
    const allF1 = vm.dailyKs.flatMap(k => rows.map(row => Number((row.daily[String(k)] || {}).f1) || 0));
    const f1Scale = Math.max(0.3, ...allF1);
    const metric = value => {
      const number = Number(value);
      return Number.isFinite(number) ? number.toFixed(3) : 'n/a';
    };
    const dailyCharts = vm.dailyKs.map(k => {
      const chartRows = rows.map(row => {
        const d = row.daily[String(k)] || {};
        const f1 = Number(d.f1) || 0;
        const width = Math.max(0, Math.min(100, (f1 / f1Scale) * 100));
        const label = architectureLabels[row.id] || row.label;
        const tooltip = 'Precision '+metric(d.precision)+'; Recall '+metric(d.recall)+'; F1 '+metric(d.f1);
        return '<div class="gnn-chart-row '+(row.isBaseline ? 'baseline' : '')+'" title="'+esc(tooltip)+'"><span class="gnn-chart-label">'+esc(label)+'</span><div class="gnn-chart-track"><div class="gnn-chart-fill '+(row.isBaseline ? 'baseline' : '')+'" style="width:'+width.toFixed(2)+'%"></div></div><span class="gnn-chart-value">'+metric(d.f1)+'</span></div>';
      }).join('');
      const dataRows = rows.map(row => {
        const d = row.daily[String(k)] || {};
        const label = architectureLabels[row.id] || row.label;
        return '<tr><th scope="row">'+esc(label)+'</th><td>'+esc(architectureDescription(row.looksFor))+'</td><td>'+fmt(d.found)+'</td><td>'+fmt(d.budget)+'</td><td>'+metric(d.precision)+'</td><td>'+metric(d.recall)+'</td><td>'+metric(d.f1)+'</td></tr>';
      }).join('');
      return '<section class="gnn-f1-chart" aria-labelledby="gnn-f1-chart-title-'+esc(k)+'"><h4 id="gnn-f1-chart-title-'+esc(k)+'">Daily budget K='+esc(k)+'</h4><p class="gnn-chart-subtitle">F1 score; higher is better. Bar lengths use the same scale across all daily budgets.</p><div class="gnn-chart-axis"><span>0</span><span>'+metric(f1Scale)+'</span></div><div aria-label="F1 score by architecture at daily budget K='+esc(k)+'; higher is better">'+chartRows+'</div><div class="gnn-chart-legend"><span><i class="gnn-chart-swatch"></i>GNN architecture</span><span><i class="gnn-chart-swatch baseline"></i>Tabular baseline</span></div><table class="gnn-chart-data gnn-sr-only"><caption>Daily budget K='+esc(k)+' metrics by architecture</caption><thead><tr><th>Architecture</th><th>Mechanism</th><th>Found</th><th>Budget</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead><tbody>'+dataRows+'</tbody></table></section>';
    }).join('');

    mount.innerHTML = '<h3 id="v9-gnn-architecture-title">Models & Architectures</h3>'
      + '<div class="gnn-hint">Daily capacity metrics compare the tabular baseline against five GNN architectures. The GNNs use caught-propagation signal, while the baseline relies on row-level history.</div>'
      + '<div id="v9-gnn-architecture-daily" class="gnn-daily-only"><p style="color: var(--text2); font-size: 12px; margin: 0 0 12px;">Aggregates across '+esc(vm.nDays)+' test days; each K is the per-day inspection budget.</p><div class="gnn-f1-chart-grid">'+dailyCharts+'</div></div>'
      + '<div class="gnn-provenance"><span>Corpus: '+esc(vm.provenance.corpus)+'</span><span>Seeds: '+esc(vm.provenance.seeds.join(', '))+'</span><span>Epochs: '+esc(vm.provenance.epochs)+'</span><span>Train bucket: '+esc(vm.provenance.trainBucket)+'</span></div>';
  };
  render();
}
"""

__all__ = [
    "GNN_ARCHITECTURE_VIEW_MODEL_JS",
    "GNN_ARCHITECTURE_UI_JS",
    "GNN_ARCHITECTURE_CSS",
]
