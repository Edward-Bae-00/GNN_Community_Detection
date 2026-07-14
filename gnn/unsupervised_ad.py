import json
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score

from gnn import config as FC
from gnn.demo_baseline import build_baseline_features
from gnn.run_demo import _build_oracle

def load_pool_with_region(corpus_dir):
    """Loads the test set and training set with region and ground truth labels."""
    # 1. Ground Truth
    egt = pd.read_csv(
        corpus_dir / "event_ground_truth.csv", 
        usecols=["event_id", "primary_person_id", "true_contraband_present"]
    )
    # Convert string boolean if necessary
    if egt["true_contraband_present"].dtype == object:
        egt["true_contraband_present"] = egt["true_contraband_present"].astype(str).str.lower().eq("true")
    else:
        egt["true_contraband_present"] = egt["true_contraband_present"].fillna(False).astype(bool)

    # 2. Splits
    splits = pd.read_csv(
        corpus_dir / "train_valid_test_splits.csv", 
        usecols=["entity_id", "split"]
    )
    
    # 3. Events (to get time, obs_id, and region)
    ev = pd.read_csv(
        corpus_dir / "crossing_events.csv", 
        usecols=["event_id", "event_timestamp_utc", "observed_person_record_id", "region"]
    )
    
    # Merge
    df = egt.merge(splits, left_on="event_id", right_on="entity_id", how="inner")
    df = df.merge(ev, on="event_id", how="inner")
    
    df["t"] = pd.to_datetime(df.event_timestamp_utc, utc=True, errors="coerce")
    df = df.rename(columns={"observed_person_record_id": "primary_obs_id"})
    
    return df

def find_best_threshold_f1(y_true, scores, num_thresholds=100):
    """Finds the threshold that maximizes F1 score.

    Returns (best_threshold, precision, recall, f1).  If there are no
    positive labels the function returns None to signal that threshold
    tuning is impossible rather than silently returning zeros.
    """
    # Lower scores in Isolation Forest mean more anomalous.
    # We will negate scores so that higher = more anomalous.
    anom_scores = -scores

    # If all labels are false, we can't calculate a meaningful best threshold
    if y_true.sum() == 0:
        return None

    min_score = anom_scores.min()
    max_score = anom_scores.max()

    best_f1 = -1
    best_p = 0
    best_r = 0
    best_t = min_score

    thresholds = np.linspace(min_score, max_score, num_thresholds)
    
    for t in thresholds:
        y_pred = (anom_scores >= t)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_p = precision_score(y_true, y_pred, zero_division=0)
            best_r = recall_score(y_true, y_pred, zero_division=0)
            best_t = t
            
    return best_t, best_p, best_r, best_f1

def _extract_features(df, corpus_dir, obs2id):
    """Build feature matrix for *df* and assert row alignment."""
    X, names = build_baseline_features(
        df[["event_id", "primary_obs_id", "t"]], corpus_dir, obs2id
    )
    assert X.shape[0] == len(df), (
        f"Feature matrix rows ({X.shape[0]}) != DataFrame rows ({len(df)})"
    )
    return X, names

def main():
    corpus_dir = FC.CORPUS_DIR
    print(f"Loading data from {corpus_dir}...")
    
    obs2id = _build_oracle(corpus_dir)
    df = load_pool_with_region(corpus_dir)
    
    results = {}
    
    # Process each region separately
    regions = df["region"].dropna().unique()
    print(f"Found {len(regions)} regions: {regions}")
    
    for region in regions:
        print(f"\n--- Processing Region: {region} ---")
        region_df = df[df["region"] == region].copy()
        
        train_df = region_df[region_df["split"] == "train"].copy()
        valid_df = region_df[region_df["split"] == "validation"].copy()
        test_df = region_df[region_df["split"] == "test"].copy()
        
        print(f"Train: {len(train_df)}, Valid: {len(valid_df)}, Test: {len(test_df)}")
        
        if len(train_df) < 50 or len(valid_df) < 50 or len(test_df) < 50:
            print(f"Skipping {region} due to insufficient data.")
            continue
        
        # --- Fix 2: train only on normal (non-contraband) rows ---
        train_normals = train_df[~train_df["true_contraband_present"]].copy()
        print(f"Training on {len(train_normals)} normal rows "
              f"(dropped {len(train_df) - len(train_normals)} positives)")
            
        print("Extracting features...")
        X_train, feature_names = _extract_features(train_normals, corpus_dir, obs2id)
        X_valid, _ = _extract_features(valid_df, corpus_dir, obs2id)
        X_test, _ = _extract_features(test_df, corpus_dir, obs2id)
        
        y_valid = valid_df["true_contraband_present"].values
        y_test = test_df["true_contraband_present"].values
        
        print(f"Valid anomalies: {y_valid.sum()} / {len(y_valid)}")
        print(f"Test  anomalies: {y_test.sum()} / {len(y_test)}")
        
        print("Training Isolation Forest...")
        clf = IsolationForest(n_estimators=100, random_state=42, n_jobs=-1)
        clf.fit(X_train)
        
        # --- Fix 1 & 3: tune threshold on the validation set ---
        print("Tuning threshold on validation set...")
        valid_scores = clf.decision_function(X_valid)
        tune_result = find_best_threshold_f1(y_valid, valid_scores)

        if tune_result is None:
            print(f"Skipping {region}: no positives in validation set.")
            continue

        best_t, val_p, val_r, val_f1 = tune_result
        print(f"  Val  — P: {val_p:.4f} | R: {val_r:.4f} | F1: {val_f1:.4f}")

        # --- Evaluate on test set with the frozen threshold ---
        print("Evaluating on test set with frozen threshold...")
        test_scores = clf.decision_function(X_test)
        test_preds = (-test_scores >= best_t)

        test_p = precision_score(y_test, test_preds, zero_division=0)
        test_r = recall_score(y_test, test_preds, zero_division=0)
        test_f1 = f1_score(y_test, test_preds, zero_division=0)
        
        results[region] = {
            "train_normal_samples": len(train_normals),
            "train_positive_excluded": int(len(train_df) - len(train_normals)),
            "valid_samples": len(valid_df),
            "test_samples": len(test_df),
            "test_anomalies": int(y_test.sum()),
            "val_f1": round(val_f1, 4),
            "val_precision": round(val_p, 4),
            "val_recall": round(val_r, 4),
            "test_f1": round(test_f1, 4),
            "test_precision": round(test_p, 4),
            "test_recall": round(test_r, 4),
            "threshold": float(best_t),
        }
        
        print(f"Results for {region}:")
        print(f"  Test — P: {test_p:.4f} | R: {test_r:.4f} | F1: {test_f1:.4f}")

    # Save to diagnostics
    out_path = FC.RESULTS / "unsupervised_ad_results.json"
    FC.RESULTS.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nSaved detailed results to {out_path}")

if __name__ == "__main__":
    main()
