import numpy as np
from gnn import detector

def test_fit_predict_separates_a_trivial_signal():
    rng = np.random.default_rng(0)
    Xtr = np.concatenate([rng.normal(0,1,(200,2)), rng.normal(3,1,(200,2))])
    ytr = np.array([0]*200 + [1]*200)
    Xte = np.array([[0,0],[3,3]])
    for m in ("hgb","logistic"):
        p = detector.fit_predict(Xtr, ytr, Xte, model=m, seed=1)
        assert p.shape == (2,)
        assert p[1] > p[0]
