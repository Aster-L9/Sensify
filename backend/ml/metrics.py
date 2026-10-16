"""
Evaluation metrics and target checks.

Ground-truth labels are used here, and only here: to measure what the detector did.
"""
import operator

import numpy as np
from sklearn.metrics import roc_auc_score

from app.analysis.windows import flag_windows
from app.sim.topology import TICK_SECONDS
from ml.dataset import DatasetRun

GRACE_TICKS = 12  # a flag up to 1 minute after the event ends still counts as a detection
POSITIVE_PHASES = {"onset", "active", "peak"}
_OPS = {">=": operator.ge, "<=": operator.le}


def _event_window(run: DatasetRun) -> tuple[int, int]:
    n_ticks = len(run.labels.phase)
    return run.labels.event_start_tick, min(run.labels.event_end_tick + GRACE_TICKS, n_ticks - 1)


def _rate(detected: int, total: int) -> dict:
    return {"detected": detected, "total": total, "rate": (detected / total) if total else None}


def detection_metrics(flags: dict[str, np.ndarray], runs: list[DatasetRun],
                      scores: dict[str, np.ndarray] | None = None) -> dict:
    scenario = [r for r in runs if r.scenario_type != "normal"]
    normal = [r for r in runs if r.scenario_type == "normal"]

    per_type: dict[str, list[int]] = {}
    ttd, localized, detected_total = [], [], 0
    for run in scenario:
        start, end = _event_window(run)
        window = flags[run.run_id][start:end + 1]
        hit_ticks = np.flatnonzero(window.any(axis=1))
        counts = per_type.setdefault(run.scenario_type, [0, 0])
        counts[1] += 1
        if hit_ticks.size:
            counts[0] += 1
            detected_total += 1
            ttd.append(float(hit_ticks[0] * TICK_SECONDS))
            evidence = scores[run.run_id][start:end + 1].max(axis=0) if scores else window.sum(axis=0)
            localized.append(int(np.argmax(evidence)) == int(np.argmax(run.labels.is_target)))

    true_windows = all_windows = 0
    for run in runs:
        f = flags[run.run_id]
        for i in range(f.shape[1]):
            for s, e in flag_windows(f[:, i]):
                all_windows += 1
                if run.scenario_type != "normal":
                    start, end = _event_window(run)
                    true_windows += int(s <= end and e >= start)

    per_type_rates = {t: _rate(*c) for t, c in sorted(per_type.items())}
    roc_auc = None
    if scores:
        pos = [scores[r.run_id][np.isin(r.labels.phase, list(POSITIVE_PHASES)), int(np.argmax(r.labels.is_target))]
               for r in scenario]
        neg = [scores[r.run_id].ravel() for r in normal]
        if pos and neg:
            y_score = np.concatenate(pos + neg)
            y_true = np.concatenate([np.ones(sum(len(p) for p in pos)), np.zeros(sum(len(n) for n in neg))])
            roc_auc = float(roc_auc_score(y_true, y_score))

    rates = [v["rate"] for v in per_type_rates.values() if v["rate"] is not None]
    return {
        "overall": _rate(detected_total, len(scenario)),
        "per_type": per_type_rates,
        "per_type_min_rate": min(rates) if rates else None,
        "time_to_detect_s": {"median": float(np.median(ttd)) if ttd else None,
                             "p90": float(np.percentile(ttd, 90)) if ttd else None},
        "false_alarm": {
            "tick_rate": float(np.mean([flags[r.run_id].mean() for r in normal])) if normal else None,
            "windows_per_run": float(np.mean([sum(len(flag_windows(flags[r.run_id][:, i]))
                                                  for i in range(flags[r.run_id].shape[1])) for r in normal]))
            if normal else None,
        },
        "window_precision": (true_windows / all_windows) if all_windows else None,
        "localization_hit_rate": (float(np.mean(localized)) if localized else None),
        "roc_auc": roc_auc,
    }


def trust_metrics(status: dict[str, np.ndarray], runs: list[DatasetRun]) -> dict:
    """Share of compromised-reporting runs whose target loses trust, and false low trust on honest runs."""
    detected, compromised, honest_low = 0, 0, []
    for run in runs:
        rc = run.labels.reporting_compromised
        low = status[run.run_id] != "Supported"
        if rc.any():
            target = int(np.argmax(run.labels.is_target))
            compromised += 1
            detected += int(low[rc[:, target], target].sum() >= 2)
        else:
            honest_low.append(low.mean())
    return {
        "compromise_detection_rate": (detected / compromised) if compromised else None,
        "compromised_runs": compromised,
        "low_trust_rate_honest": float(np.mean(honest_low)) if honest_low else None,
    }


def _lookup(metrics: dict, dotted: str):
    value = metrics
    for key in dotted.split("."):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def compare_targets(metrics: dict, targets: dict) -> dict:
    out = {}
    for name, t in targets.items():
        value = _lookup(metrics, t["metric"])
        passed = value is not None and _OPS[t["op"]](value, t["value"])
        out[name] = {"value": value, "target": t["value"], "op": t["op"], "passed": bool(passed)}
    return out
