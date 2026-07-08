from __future__ import annotations
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

def fit_predict(X_train, y_train, X_test, *, model="hgb", seed=42):
    y = np.asarray(y_train).astype(int)
    if model == "hgb":
        clf = HistGradientBoostingClassifier(random_state=seed,
                                             class_weight="balanced")
    elif model == "logistic":
        clf = make_pipeline(StandardScaler(with_mean=True),
                            LogisticRegression(max_iter=1000, class_weight="balanced"))
    else:
        raise ValueError(f"unknown model {model!r}")
    clf.fit(X_train, y)
    return clf.predict_proba(X_test)[:, 1]
