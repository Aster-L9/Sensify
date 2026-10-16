"""
ML normal-behaviour model: one Isolation Forest per segment, trained only
on normal runs, with scores calibrated so 0.5 is the decision threshold.

The model artifact also carries the reference profile, which the
consistency checks and the threshold baseline use.
"""
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from app.analysis.features import FEATURE_SPEC_VERSION, build_features
from app.analysis.frame import ReportedRun
from app.analysis.reference import ReferenceProfile
from app.sim.topology import SEGMENT_CODES

THRESHOLD = 0.5
N_SEG = len(SEGMENT_CODES)
DEFAULT_ALPHA = 0.004  # target tick false-alarm rate; chosen on the validation split
PERSIST_K, PERSIST_N = 3, 4  # a tick is flagged when 3 of the last 4 scores reach the threshold


def _fit_forest(blocks: list[np.ndarray], n_estimators: int, max_samples: int, seed: int):
    X = np.vstack(blocks)
    mean, std = X.mean(axis=0), X.std(axis=0)
    std[std < 1e-9] = 1.0
    forest = IsolationForest(n_estimators=n_estimators, max_samples=min(max_samples, len(X)),
                             contamination="auto", random_state=seed)
    forest.fit((X - mean) / std)
    return mean, std, forest


@dataclass
class DetectorModel:
    version: int | None
    feature_spec: str
    scalers: list[tuple[np.ndarray, np.ndarray]]  # per segment (mean, std)
    forests: list[IsolationForest]
    calib: list[tuple[float, float]]  # per segment (threshold raw score, scale)
    reference: ReferenceProfile
    params: dict = field(default_factory=dict)

    @classmethod
    def fit(cls, train_runs: list[ReportedRun], val_runs: list[ReportedRun], *, n_estimators: int = 150,
            max_samples: int = 256, alpha: float = DEFAULT_ALPHA, random_state: int = 2026,
            calibration_folds: int = 4) -> "DetectorModel":
        """Fit one forest per segment on the training runs, then calibrate on unseen scores.

        Calibration is cross-fitted: each training fold is scored by a forest fitted without
        it, and the validation runs by the final forest, so the threshold rests on many
        genuinely unseen normal ticks rather than a handful of validation runs.
        """
        train = [build_features(r) for r in train_runs]
        val = [build_features(r) for r in val_runs]
        folds = calibration_folds if calibration_folds >= 2 and len(train) >= calibration_folds else 0
        scalers, forests, calib = [], [], []
        for i in range(N_SEG):
            mean, std, forest = _fit_forest([f[i] for f in train], n_estimators, max_samples, random_state + i)
            unseen = [-forest.score_samples((v[i] - mean) / std) for v in val]
            for k in range(folds):
                rest = [f[i] for j, f in enumerate(train) if j % folds != k]
                held = [f[i] for j, f in enumerate(train) if j % folds == k]
                f_mean, f_std, f_forest = _fit_forest(rest, n_estimators, max_samples, random_state + i + 100 * (k + 1))
                unseen += [-f_forest.score_samples((h - f_mean) / f_std) for h in held]
            raw = np.concatenate(unseen)
            thr = float(np.quantile(raw, 1 - alpha))
            # Anchor the curve on the threshold: the median normal tick maps to ~0.05, the threshold to 0.5.
            scale = max((thr - float(np.median(raw))) / 3, 1e-6)
            scalers.append((mean, std))
            forests.append(forest)
            calib.append((thr, scale))
        params = {"n_estimators": n_estimators, "max_samples": max_samples, "alpha": alpha,
                  "random_state": random_state, "train_runs": len(train_runs), "val_runs": len(val_runs),
                  "calibration": "cross-fit" if folds else "validation",
                  "calibration_folds": folds, "calibration_samples": int(raw.shape[0]),
                  "persistence": f"{PERSIST_K} of {PERSIST_N}"}
        return cls(None, FEATURE_SPEC_VERSION, scalers, forests, calib, ReferenceProfile.fit(train_runs), params)

    def raw_scores(self, run: ReportedRun) -> np.ndarray:
        feats = build_features(run)
        out = np.empty((run.n_ticks, N_SEG))
        for i, (mean, std) in enumerate(self.scalers):
            out[:, i] = -self.forests[i].score_samples((feats[i] - mean) / std)
        return out

    def score(self, run: ReportedRun) -> np.ndarray:
        raw = self.raw_scores(run)
        thr = np.array([c[0] for c in self.calib])
        scale = np.array([c[1] for c in self.calib])
        return 1.0 / (1.0 + np.exp(-(raw - thr) / scale))

    def save(self, path: Path) -> None:
        joblib.dump({
            "version": self.version, "feature_spec": self.feature_spec, "scalers": self.scalers,
            "forests": self.forests, "calib": self.calib, "reference": self.reference.to_dict(),
            "params": self.params,
        }, path, compress=3)

    @classmethod
    def load(cls, path: Path) -> "DetectorModel":
        d = joblib.load(path)
        return cls(d["version"], d["feature_spec"], d["scalers"], d["forests"], d["calib"],
                   ReferenceProfile.from_dict(d["reference"]), d["params"])


def persist_flags(scores: np.ndarray, threshold: float = THRESHOLD,
                  k: int = PERSIST_K, n: int = PERSIST_N) -> np.ndarray:
    """Flag a tick when the score reaches the threshold in at least k of the last n ticks (causal)."""
    above = (scores >= threshold).astype(int)
    count = above.copy()
    for lag in range(1, n):
        count[lag:] += above[:-lag]
    return count >= k
