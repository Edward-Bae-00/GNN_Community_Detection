"""Realistic tabular baseline: every reasonable per-person / per-event OBSERVABLE
feature a non-graph analyst model would use — as-of own history, observed
demographics, and per-event context. NO relational/graph propagation, NO neighbor
labels, NO future/outcome columns. This is a strong, defensible baseline; the GNN's
only structural advantage is as-of caught-propagation across the graph, which none
of these per-person features can capture.

All as-of counts are over the row's RESOLVED identity (same substrate the GNN uses),
strictly before the row's crossing time T. Own prior outcomes (secondary/seizure/
arrest) are historical and leak-free for the current event (current outcome excluded).
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd

_ASOF = ["prior_crossings", "prior_secondary", "prior_seizure", "prior_arrests"]
# party_size and vehicle/document co-use counts are EXCLUDED on purpose: they are
# relational (co-travel / shared-asset) shadows of the graph signal, and the whole
# point of the demo is per-person attributes vs relational structure. `hour` is the
# only per-event (non-relational) numeric kept here.
_JSON = ["hour"]
_DEMO = ["age_bucket", "sex"]
_CTX = ["citizenship_country", "residence_country", "region",
        "mode_of_transportation", "travel_category", "declared_trip_purpose",
        "day_of_week"]
FEATURE_NAMES = _ASOF + _JSON + _DEMO + _CTX


def _asof_history(corpus_dir, obs_to_identity) -> dict:
    """resolved identity -> event times, label times, and outcome flags."""
    ce = pd.read_csv(corpus_dir / "crossing_events.csv",
                     usecols=["event_timestamp_utc", "observed_person_record_id",
                              "label_available_time_utc",
                              "secondary_referral_flag", "seizure_flag", "arrest_flag"])
    ce["identity"] = ce["observed_person_record_id"].map(obs_to_identity)
    ce["t"] = pd.to_datetime(ce["event_timestamp_utc"], utc=True, errors="coerce")
    ce["label_available"] = pd.to_datetime(
        ce["label_available_time_utc"], utc=True, errors="coerce")
    ce = ce.dropna(subset=["identity", "t"]).sort_values("t")
    for c in ["secondary_referral_flag", "seizure_flag", "arrest_flag"]:
        ce[c] = ce[c].astype(str).str.lower().eq("true").astype(int)
    hist = {}
    for ident, g in ce.groupby("identity", sort=False):
        hist[ident] = (
            g["t"].values.astype("datetime64[ns]"),
            g["label_available"].values.astype("datetime64[ns]"),
            g["secondary_referral_flag"].values,
            g["seizure_flag"].values,
            g["arrest_flag"].values)
    return hist


def _event_context(corpus_dir) -> pd.DataFrame:
    """event_id -> per-event observable context (categoricals integer-coded)."""
    cols = ["citizenship_country", "residence_country", "region",
            "mode_of_transportation", "travel_category", "declared_trip_purpose",
            "day_of_week"]
    ce = pd.read_csv(corpus_dir / "crossing_events.csv", usecols=["event_id"] + cols)
    for c in cols:
        ce[c] = ce[c].astype("category").cat.codes
    return ce.set_index("event_id")


def _pre_event_json(corpus_dir) -> dict:
    """event_id -> dict of leak-safe pre-event features."""
    ef = pd.read_csv(corpus_dir / "event_features.csv",
                     usecols=["event_id", "pre_event_features_json"])
    out = {}
    for eid, js in zip(ef["event_id"], ef["pre_event_features_json"]):
        try:
            out[eid] = json.loads(js) if isinstance(js, str) else {}
        except Exception:
            out[eid] = {}
    return out


def _observed_demo(corpus_dir) -> pd.DataFrame:
    obs = pd.read_csv(corpus_dir / "observed_person_records.csv",
                      usecols=["observed_person_record_id", "observed_dob_year_bucket",
                               "observed_sex_marker"])
    obs["age_bucket"] = obs["observed_dob_year_bucket"].astype("category").cat.codes
    obs["sex"] = obs["observed_sex_marker"].astype("category").cat.codes
    return obs.set_index("observed_person_record_id")[["age_bucket", "sex"]]


def build_baseline_features(rows: pd.DataFrame, corpus_dir, obs_to_identity):
    hist = _asof_history(corpus_dir, obs_to_identity)
    ctx = _event_context(corpus_dir)
    js = _pre_event_json(corpus_dir)
    demo = _observed_demo(corpus_dir)
    rows = rows.reset_index(drop=True)
    X = np.zeros((len(rows), len(FEATURE_NAMES)), dtype=float)
    col = {c: i for i, c in enumerate(FEATURE_NAMES)}
    for r, row in rows.iterrows():
        eid = row["event_id"]; obs_id = row["primary_obs_id"]
        ident = obs_to_identity.get(obs_id)
        T = np.datetime64(pd.Timestamp(row["t"]).tz_convert(None))
        h = hist.get(ident)
        if h is not None:
            t, label_available, c_sec, c_seiz, c_arr = h
            k = int(np.searchsorted(t, T, side="left"))  # # strictly-prior crossings
            X[r, col["prior_crossings"]] = k
            available = label_available[:k] < T
            X[r, col["prior_secondary"]] = c_sec[:k][available].sum()
            X[r, col["prior_seizure"]] = c_seiz[:k][available].sum()
            X[r, col["prior_arrests"]] = c_arr[:k][available].sum()
        d = js.get(eid, {})
        X[r, col["hour"]] = float(d.get("hour", 0) or 0)
        if obs_id in demo.index:
            X[r, col["age_bucket"]] = float(demo.at[obs_id, "age_bucket"])
            X[r, col["sex"]] = float(demo.at[obs_id, "sex"])
        if eid in ctx.index:
            for c in _CTX:
                X[r, col[c]] = float(ctx.at[eid, c])
    return X, list(FEATURE_NAMES)
