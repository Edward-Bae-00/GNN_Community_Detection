# Synthetic CBP Graph Corpus - Data Guide

> Current-status note (2026-07-08): this guide was originally written for the
> V7-era corpus/dashboard stack and still contains historical V6/V7 sections.
> The active checkout now contains V8, V9, and V9dev corpora. For current
> V9-positive-control design/results, use `Documents/Data/changes_3.md`; for
> repository onboarding, use the root `README.md`, `AGENTS.md`, and `CLAUDE.md`.
> Treat older dashboard-stack and V7-latest wording as legacy context unless
> refreshed in a later data-guide rewrite.

## What This Dataset Is

A fully synthetic, privacy-safe graph corpus that models **U.S. Customs and Border Protection (CBP) crossing events** and the social/logistic networks around them. It is designed for research in **graph neural network (GNN) community detection**, entity resolution, and anomaly scoring — not for operational use.

The active corpus snapshots in this checkout are **v8**, **v9**, and **v9dev**.
V8 is the honest thin-relational-signal track; V9 is the designed
positive-control corpus used by `gnn/`; V9dev is the small test
profile. Historical V7 details below are retained for context.

---

## Data Realism & Interdiction Rates

A key design choice: **most smuggling goes undetected.** This matches real-world evidence.

### Current dataset rates

| Metric | Value |
|--------|-------|
| True-contraband events | 3,736 |
| Caught true-contraband events (seizures) | 327 |
| Got through undetected | 3,409 |
| **Event interdiction rate** | **~8.8%** |

### Real-world evidence supporting these rates

**CBP's own estimate (cocaine):** CBP estimated it seized only **~3%** of cocaine trafficked through U.S. ports of entry — the only drug for which the agency published an internal flow estimate.
> Cited in Cato Institute analysis of DHS data ([source](https://www.cato.org/blog/fentanyl-smuggled-us-citizens-us-citizens-not-asylum-seekers))

**Congressional Research Service (CRS R45812, July 2019):** *"[O]f the total amount of illicit drugs that reach the U.S. border by land, air, or sea… an unknown portion is successfully smuggled into the country."* CRS explicitly notes the total flow is **not known with precision**, making exact interdiction rates impossible to calculate — but acknowledges the seized fraction is small relative to estimated supply.
> [CRS Report R45812 — Illicit Drug Flows and Seizures in the United States](https://www.congress.gov/crs-product/R45812)

**Senator Angus King / JIATF-South (maritime):** In Senate Armed Services hearings, Sen. King cited intelligence showing the military interdicts only **~25% of *known* maritime drug shipments** — and that figure only counts shipments already identified by intelligence, not the unknown ones.
> [Sen. King press release](https://www.king.senate.gov/newsroom/press-releases/king-its-inexcusable-that-military-halts-only-25-percent-of-known-drug-shipments)

**RAND Corporation (1994, "Controlling Cocaine"):** RAND's simulation model for ONDCP concluded that even large increases in interdiction spending would produce only marginal reductions in domestic cocaine consumption, implying that the baseline seizure rate is a small fraction of total flow.
> [RAND MR-331](https://www.rand.org/pubs/monograph_reports/MR331.html)

**DHS / CBP FY2024 seizure volumes:** In FY2024, CBP seized ~18,900 lbs of fentanyl at the Southwest border (down 22% from the prior year) and ~55,000 lbs total of all drugs in August 2025 alone. While these are large absolute numbers, the DEA estimates U.S. annual consumption vastly exceeds what is seized.
> [CBP December 2024 Monthly Update](https://www.cbp.gov/newsroom/national-media-release/cbp-releases-december-2024-monthly-update) · [DHS August 2025 Drug Seizure Report](https://www.dhs.gov/news/2025/09/30/cbp-reports-drug-seizures-surge-again-august)

### Bottom line

Expert consensus places the overall narcotics interdiction rate somewhere in the **5–15% range** depending on drug type and smuggling vector. The dataset's ~7% rate sits squarely within that range.

---

## Snapshot Methodology

The active V8, V9, and V9dev corpora are checked-in synthetic snapshots. The
generator entrypoint has been retired from this checkout, so historical sections
below may still use older generator language. Key design principles:

1. **Connectivity = what the government observes.** No synthetic social-media or phone-call graphs. Person-to-person edges come only from co-travel, shared addresses, shared vehicles, shared employers, and repeated routes.

2. **Families ≠ addresses.** Kinship uses a hidden `family_id` that can span multiple households. Some relatives live apart but co-travel — a realistic entity-resolution challenge.

3. **Undetected smuggling.** Each event has a latent `true_contraband_present` flag generated *independently* of enforcement. Detection probability is < 1 at every stage, producing realistic false negatives. Ground truth is quarantined in `event_ground_truth.csv`.

4. **Demographics are independent of smuggling propensity.** A demographics-only model stays at chance (negative control for fairness auditing).

5. **Hidden co-offender cells with an unfindable fraction (V6/V7).** A second hidden grouping, `org_id`, separate from the family community label and spanning **at least two families per cell**, models smuggling cells. Like family, it is never an edge or a feature — it surfaces only through observable records (cross-family co-travel, a shared vehicle, a shared small carrier/broker). A deliberate fraction of members are **dark**: truly in the cell but leaving *no* observable trail (operational security — burner phones, recruiting strangers, never co-travelling). The gap between true and observable cell connectivity is the structural analog of undetected smuggling — some genuine co-offenders are simply unrecoverable from the data. See the V6/V7 sections below.

6. **Entity-resolution recoverability (V7).** V7 adds a downstream ER layer on top of the V6-style corpus. It summarizes observed identity fragments, deterministic same-document/same-event ER clusters, oracle clusters, and weak-link pairs that are recoverable only by combining multiple observable signals. Truth columns remain evaluation labels and are not operational features.

---

## V6: Non-Family Co-Offender Structure

V5 capped the graph approach: all person-to-person structure was family-derived, so only **29 / 735 (3.95%)** hidden false-negative test smugglers could ever reach a prior caught anchor through leak-safe connectivity. V6 adds non-family co-offender cells to lift this without changing the base task.

- **Generation history:** the V6 snapshot was produced by the historical generator with the org layer enabled; v3/v4/v5 were byte-identical to before. Cells are drawn from existing elevated-propensity persons and every cell spans **≥2 families** — no propensity is changed, so corpus-wide contraband/seizure prevalence stays within noise of V5 (seizures 339 vs 358; FN slip-through 90.5% vs 90.3%).
- **Channels by mode affinity** (`passenger_vehicle`/`pedestrian`/`air`/`truck`): cross-family co-travel → `PERSON_ASSOCIATED_WITH_PERSON` (still co-travel-derived, validator-safe); passenger-vehicle cells also share one vehicle; air cells share a carrier; truck cells share a truck + small broker. Co-travel is time-correlated by construction (same event).
- **Golden ground truth:** `org_membership_ground_truth.csv` holds the *full* membership incl. `is_dark` members. `is_observable=true` means the member actually surfaced through same-org co-travel, shared vehicle, or shared carrier/broker records. `org_id` never appears on `persons.csv` / `node_features.csv` / `event_features.csv` / `crossing_events.csv` (enforced by `validate_corpus.py`, including JSON/string payload scans).
- **Result (`border_anomaly.graph_ceiling` with `CBP_CORPUS=synthetic_cbp_graph_corpus_v6`):** observable reachability `A_direct_only` rises **3.95% → 7.74%** (51/659). `graph_ceiling.json` reports full vs actually observable cell reachability; their difference is the truly-linked-but-unfindable fraction.

---

## V7: Entity-Resolution Recoverability Layer

V7 keeps the V6-style hidden co-offender structure and adds ER artifacts to test the thesis pathway: whether learned ER models, including possible GNN variants, can recover identity links that deterministic ER misses and whether better identity clusters improve downstream graph detection.

- **Generation history:** V7 uses the same 200K-event / 120K-person scale as V6 and adds ER artifacts before generated schema/docs are scanned.
- **ER outputs:** `identity_fragmentation_profile.csv`, `record_link_evidence.csv`, `baseline_er_clusters.csv`, `oracle_er_clusters.csv`, and `v7_er_recoverability_summary.json`.
- **Feature/label contract:** `record_link_evidence.csv` includes labels and canonical IDs for training/evaluation metadata, but model features should use only observable evidence fields such as same document, DOB bucket, sex marker, source system, vehicle, carrier, and residence. It deliberately excludes hidden family/org truth as model evidence.
- **V7 ER summary:** the summary now reports deterministic coverage plus **oracle weak-link coverage** using observable evidence only: 116,148 deterministic true pairs, 818 weak-link positive true pairs, deterministic recall 0.906, and deterministic + weak-link oracle coverage 0.912. It does **not** report a measured learned ER-GNN recall; learned ER training and downstream comparison remain future work.
- **Dashboard:** the unified dashboard includes V7 in the corpus switcher and adds an **Entity Resolution** tab when a corpus has `entity_resolution` data. That tab explicitly states that no learned ER-GNN result has been produced yet.

---

## Dashboard Tabs & What They Show

The unified dashboard (`index.html`) loads `data_v*.json` files for V2-V7 and organizes each corpus into several tabs:

| Tab | Contents |
|-----|----------|
| **Overview** | High-level counts: nodes by type (person, event, document, vehicle, etc.), edge types, outcome rates (secondary, search, seizure, arrest), and train/validation/test split sizes |
| **Temporal** | Monthly crossing volume over ~4 fiscal years (FY2022–FY2025), day-of-week and hour-of-day heatmaps, volume by region over time |
| **Geographic** | Crossings by region, field office, and port of entry; route flows (origin → port → destination); state-level choropleth maps |
| **Communities** | Community-type distribution (11 types), community map visualization showing geographic clustering, community size distribution |
| **Outcomes** | Outcome funnels (secondary → search → seizure → arrest → prosecution) broken down by traveler segment, mode, citizenship, and direction |
| **Seizures** | Drug seizure details: drug types, detection methods, conveyance types, monthly seizure/arrest trends, quantity statistics |
| **Graph** | Graph structure metrics: degree distribution, node/edge type counts, edge categories (structural vs. social vs. outcome), connectivity patterns |
| **Entity Resolution** | V7 ER summary: observed identity records, candidate links, deterministic coverage, oracle weak-link coverage, fragmentation tiers, and a note that no learned ER-GNN result exists yet |
| **Explorer** | Interactive force-directed graph of the person-to-person subgraph (~9,686 nodes, ~16,202 links) with full filtering and community drill-down |

---

## Explorer Tab — Filters Explained

The Explorer tab is the interactive network visualization. Here is what every filter does:

### Role Chips (top row)

These filter **people by their enforcement outcome**. They are additive — turning on multiple chips shows people matching *any* of the selected roles.

| Chip | Meaning |
|------|---------|
| **Carried** | Person carried contraband on at least one crossing (flag `r & 1`). Includes both caught and uncaught carriers. |
| **Interdiction** | Person is a member of an interdiction-linked community — i.e., belongs to a community type specifically flagged as smuggling-associated (flag `r & 2`). |
| **Seized** | At least one crossing by this person resulted in a drug seizure (flag `r & 4`). |
| **Arrested** | Person was arrested during at least one crossing (flag `r & 8`). |
| **Near smuggler** | Person was *not* flagged with any of the above roles, but is a direct graph neighbor of someone who carried contraband (`ns` flag). |
| **Near arrest** | Person is a direct graph neighbor of someone who was arrested (`na` flag). |

### Community Type Chips

Filter by the **type of community** the person belongs to. There are 11 types:

| Type | Description |
|------|-------------|
| **Low-frequency / one-time** | People who crossed only once or very rarely. Largest group (~15K). |
| **Family travel** | Family clusters who travel together. Linked by kinship and co-travel edges. |
| **Routine commuter** | Daily or near-daily border commuters (work, school, shopping). |
| **Airport passenger** | Air-mode travelers processed at airport CBP facilities. |
| **Interdiction-linked** | Communities with elevated smuggling involvement. Key target for GNN detection. |
| **High-frequency benign** | Frequent crossers with no enforcement flags. |
| **Seasonal worker** | Agricultural or seasonal employment-driven crossers. |
| **Commercial trucking** | Commercial drivers and fleet-associated persons. |
| **Rental-reliant** | People who primarily use rental vehicles for crossings. |
| **Prior stops, no seizures** | People who have been referred to secondary inspection before but never had a seizure. |
| **Admin document issue** | People flagged for document irregularities (expired, mismatched, etc.). |

### Attribute Dropdowns

| Filter | What it controls |
|--------|-----------------|
| **Region** | The CBP geographic region of the person's crossings: Southern Border, Northern Border, Coastal/Interior, or Preclearance (pre-clearance facilities in Canada/Caribbean). |
| **Traveler segment** | Behavioral classification of the traveler (e.g., `routine_commuter`, `airport_traveler`, `family_traveler`, `commercial_driver`, `seasonal_worker`, etc.). |
| **Citizenship** | Country of citizenship on the person's travel document. Top values: US, Mexico, Canada, plus ~13 other countries. |
| **Age** | Age bucket: 0–17, 18–24, 25–34, 35–44, 45–54, 55–64, 65+. |

### Jump to Community

Select a specific community ID from the dropdown to **drill into** that community. This filters the graph to show only members of that community plus their immediate neighbors, switches to Focus mode, and zooms the camera to frame them.

### Connection Types

Toggle which **edge types** are displayed:

| Type | What it represents |
|------|--------------------|
| **Associated** | General association — co-travel, co-appearance in the same crossing event. |
| **Family** | Kinship link (same `family_id` in the generator). |
| **Co-address** | Shared residential address on file. |
| **Co-vehicle** | Used the same vehicle across different crossings. |
| **Co-business** | Linked to the same employer or business entity. |
| **Co-travel** | Traveled together in the same crossing event (same party). |

Links can have **multiple types simultaneously** (stored as a bitmask). For example, two family members who also share an address and traveled together would have a link with `family | co_address | co_event` flags set.

### Colour By

- **Community** — nodes colored by their community type (11 colors).
- **Role** — nodes colored by enforcement role: orange = carrier, rose = interdiction, red = arrested, amber = seizure, dark gray = no role.

### Filter Mode

- **Highlight** — all nodes remain visible; non-matching nodes are dimmed to 16% opacity.
- **Focus** — non-matching nodes are completely hidden (`display: none`). Used automatically when drilling into a community.

### Node Details (sidebar)

Clicking any node shows:
- Person ID, community, community type
- Region, segment, citizenship, age
- Number of border crossings
- Total graph connections (degree)
- Whether they are linked to a smuggler or arrest
- Breakdown of visible connections by tie type
- "Drill into community" button

---

## File Layout

```
Documents/Data/
  synthetic_cbp_graph_corpus_v8/
    *.csv                         — V8 honest-track corpus tables
    README.md                     — generated corpus inventory
    DATA_DICTIONARY.md            — table/column descriptions
    VALIDATION_REPORT.md          — generated validation report

  synthetic_cbp_graph_corpus_v9/
    *.csv                         — full V9 positive-control corpus tables
    dashboard_data.json           — dashboard payload from build_dashboard.py
    dashboard_standalone.html     — standalone corpus dashboard shell
    README.md                     — generated corpus inventory

  synthetic_cbp_graph_corpus_v9dev/
    *.csv                         — small V9 dev/test corpus
    README.md                     — generated corpus inventory

  scripts/
    validate_corpus.py            — validation harness
    build_dashboard.py            — corpus dashboard data/shell builder
    build_v9_dashboard.py         — V9 dashboard packager

  v9_dashboard/
    index.html                    — V9 dashboard shell
    data_v9.json                  — V9 dashboard data payload

  RealWorld_Data/
    *.csv                         — aggregate calibration/reference inputs
```

---

## Key Node Properties (Explorer JSON)

| Field | Type | Meaning |
|-------|------|---------|
| `id` | string | Person ID (e.g., `P00001504`) |
| `ct` | int | Community type index (into `community_types` array) |
| `rg` | int | Region index (into `regions` array) |
| `sg` | int | Traveler segment index |
| `ci` | int | Citizenship index |
| `ag` | int | Age bucket index |
| `cr` | int | Number of border crossings |
| `r` | int | Role bitmask: bit 0 = carried, bit 1 = interdiction, bit 2 = seized, bit 3 = arrested |
| `ns` | 0/1 | Neighbor of a smuggler |
| `na` | 0/1 | Neighbor of an arrested person |
| `cm` | string | Community ID (e.g., `C0000625`) |
| `d` | int | Degree (number of graph connections) |

## Key Link Properties

Links are stored as `[source_idx, target_idx, tie_bitmask, weight]`:

| Bit | Tie type |
|-----|----------|
| 0 (1) | associated |
| 1 (2) | family |
| 2 (4) | co_address |
| 3 (8) | co_vehicle |
| 4 (16) | co_business |
| 5 (32) | co_event (co-travel) |
