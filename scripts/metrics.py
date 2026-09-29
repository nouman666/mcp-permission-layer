"""Shared metrics helpers for evaluation tables."""

from __future__ import annotations

import math
import random
from typing import Iterable


# Reviewer 1 Comment 5 implemented: the benign-call utility metric is BCAR
# (Benign Call Allow Rate), not task-level success. Revised outputs use BCAR only.
# Reviewer 1 Comment 7 implemented: bootstrap resampling is class-stratified.


def confusion_counts(y_true_attack: list[bool], y_pred_allow: list[bool]) -> dict:
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
    bcar = (tn / n_benign * 100.0) if n_benign else 0.0
    precision = (tp / (tp + fp)) if (tp + fp) else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "asr": asr,
        "block_rate": block,
        "bcar": bcar,
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
    """Class-stratified bootstrap percentile interval for a derived metric."""
    rng = random.Random(seed)
    attack_idx = [i for i, v in enumerate(y_true_attack) if v]
    benign_idx = [i for i, v in enumerate(y_true_attack) if not v]
    if not attack_idx and not benign_idx:
        return {"point": 0.0, "mean": 0.0, "std": 0.0, "ci95_low": 0.0, "ci95_high": 0.0, "n_boot": n_boot}

    values = []
    for _ in range(n_boot):
        sample = []
        if attack_idx:
            sample.extend(rng.choice(attack_idx) for _ in range(len(attack_idx)))
        if benign_idx:
            sample.extend(rng.choice(benign_idx) for _ in range(len(benign_idx)))
        yt = [y_true_attack[i] for i in sample]
        yp = [y_pred_allow[i] for i in sample]
        values.append(derive_rates(confusion_counts(yt, yp))[metric])

    values.sort()
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / max(1, len(values) - 1)
    std = math.sqrt(var)
    lo_i = min(len(values) - 1, max(0, int((alpha / 2) * len(values))))
    hi_i = min(len(values) - 1, max(0, int((1 - alpha / 2) * len(values))))
    point = derive_rates(confusion_counts(y_true_attack, y_pred_allow))[metric]
    return {
        "point": point,
        "mean": mean,
        "std": std,
        "ci95_low": values[lo_i],
        "ci95_high": values[hi_i],
        "n_boot": n_boot,
        "method": "class-stratified percentile bootstrap",
    }


def zero_event_upper_bound(n: int, alpha: float = 0.05) -> float:
    """One-sided exact binomial upper bound when zero events are observed."""
    if n <= 0:
        return 100.0
    return (1.0 - alpha ** (1.0 / n)) * 100.0


def wilson_interval(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Two-sided 95% Wilson interval, returned as percentages."""
    if n <= 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt((p * (1 - p) / n) + z * z / (4 * n * n)) / denom
    return max(0.0, center - half) * 100.0, min(1.0, center + half) * 100.0


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
