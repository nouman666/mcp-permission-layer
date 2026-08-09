"""Shared metrics helpers for evaluation tables."""

from __future__ import annotations

import math
import random
from typing import Iterable


def confusion_counts(y_true_attack: list[bool], y_pred_allow: list[bool]) -> dict:
    """
    Attack = positive class.
    TP: attack & denied (blocked)
    FN: attack & allowed (ASR numerator)
    TN: benign & allowed
    FP: benign & denied
    """
    tp = fp = tn = fn = 0
    for is_attack, allowed in zip(y_true_attack, y_pred_allow):
        if is_attack and not allowed:
            tp += 1
        elif is_attack and allowed:
            fn += 1
        elif (not is_attack) and allowed:
            tn += 1
        else:
            fp += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}


def derive_rates(counts: dict) -> dict:
    tp, fp, tn, fn = counts["tp"], counts["fp"], counts["tn"], counts["fn"]
    n_attack = tp + fn
    n_benign = tn + fp
    asr = (fn / n_attack * 100.0) if n_attack else 0.0
    block = (tp / n_attack * 100.0) if n_attack else 0.0
    tsr = (tn / n_benign * 100.0) if n_benign else 0.0
    precision = (tp / (tp + fp)) if (tp + fp) else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "asr": asr,
        "block_rate": block,
        "tsr": tsr,
        "precision": precision * 100.0,
        "recall": recall * 100.0,
        "f1": f1 * 100.0,
        "n_attack": n_attack,
        "n_benign": n_benign,
        **counts,
    }


def bootstrap_ci(
    y_true_attack: list[bool],
    y_pred_allow: list[bool],
    metric: str = "asr",
    n_boot: int = 1000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict:
    """Bootstrap mean ± std and percentile CI for a metric key from derive_rates."""
    rng = random.Random(seed)
    n = len(y_true_attack)
    if n == 0:
        return {"mean": 0.0, "std": 0.0, "ci95_low": 0.0, "ci95_high": 0.0}

    values = []
    idx = list(range(n))
    for _ in range(n_boot):
        sample = [rng.choice(idx) for _ in range(n)]
        yt = [y_true_attack[i] for i in sample]
        yp = [y_pred_allow[i] for i in sample]
        values.append(derive_rates(confusion_counts(yt, yp))[metric])

    values.sort()
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / max(1, len(values) - 1)
    std = math.sqrt(var)
    lo = values[int((alpha / 2) * len(values))]
    hi = values[min(len(values) - 1, int((1 - alpha / 2) * len(values)))]
    point = derive_rates(confusion_counts(y_true_attack, y_pred_allow))[metric]
    return {
        "point": point,
        "mean": mean,
        "std": std,
        "ci95_low": lo,
        "ci95_high": hi,
        "n_boot": n_boot,
    }


def mean_std(xs: Iterable[float]) -> tuple[float, float]:
    vals = list(xs)
    if not vals:
        return 0.0, 0.0
    m = sum(vals) / len(vals)
    if len(vals) == 1:
        return m, 0.0
    v = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
    return m, math.sqrt(v)


def percentile(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    k = (len(s) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)
