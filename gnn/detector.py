"""Scikit-learn fitting helpers shared by tabular detector experiments."""

from __future__ import annotations
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

def fit_predict(X_train, y_train, X_test, *, model="hgb", seed=42, sample_weight=None):
    """Fit the tabular detector and return positive-class scores for validation and test rows."""
    y = np.asarray(y_train).astype(int)
    if model == "hgb":
        clf = HistGradientBoostingClassifier(random_state=seed,
                                             class_weight="balanced")
        fit_params = {"sample_weight": sample_weight} if sample_weight is not None else {}
        clf.fit(X_train, y, **fit_params)
    elif model == "logistic":
        clf = make_pipeline(StandardScaler(with_mean=True),
                            LogisticRegression(max_iter=1000, class_weight="balanced"))
        fit_params = {"logisticregression__sample_weight": sample_weight} if sample_weight is not None else {}
        clf.fit(X_train, y, **fit_params)
    else:
        raise ValueError(f"unknown model {model!r}")
    return clf.predict_proba(X_test)[:, 1]
