"""Train/val/test metrics for debugging overfitting and for teacher-facing dashboards."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support, roc_auc_score
from sklearn.pipeline import Pipeline


def binary_classification_metrics(y_true: np.ndarray, proba: np.ndarray, threshold: float = 0.5) -> dict[str, Any]:
    y_true = np.asarray(y_true).astype(int)
    proba = np.asarray(proba, dtype=float)
    y_pred = (proba >= threshold).astype(int)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred).tolist()
    out: dict[str, Any] = {
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "threshold": threshold,
        "confusion_matrix": cm,
        "confusion_labels": ["predicted_reliable", "predicted_review"],
    }
    if len(np.unique(y_true)) > 1:
        out["roc_auc"] = float(roc_auc_score(y_true, proba))
    else:
        out["roc_auc"] = None
    return out


def classical_metrics_on_split(pipe: Pipeline, csv_path: Path) -> dict[str, Any]:
    df = pd.read_csv(csv_path)
    X = df["text"].astype(str)
    y = df["is_fake"].astype(int).to_numpy()
    proba = pipe.predict_proba(X)[:, 1]
    return binary_classification_metrics(y, proba)


def overfitting_reading(train: dict[str, Any], val: dict[str, Any], test: dict[str, Any]) -> str:
    """Short heuristic note for educators (not a formal statistical test)."""
    t_auc = train.get("roc_auc")
    v_auc = val.get("roc_auc")
    te_auc = test.get("roc_auc")
    parts = []
    if t_auc is not None and v_auc is not None and t_auc - v_auc > 0.08:
        parts.append(
            "Train ROC-AUC is noticeably higher than validation—possible overfitting or shortcut features."
        )
    if v_auc is not None and te_auc is not None and abs(v_auc - te_auc) < 0.02:
        parts.append("Validation and test ROC-AUC are close - hold-out split looks stable.")
    if not parts:
        parts.append(
            "Compare train vs val metrics manually: large gaps in accuracy or AUC often mean overfitting; "
            "similar train/val but poor test can mean data drift or leakage."
        )
    return " ".join(parts)
