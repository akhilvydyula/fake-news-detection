"""TF-IDF + linear model (strong, fast baseline)."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.pipeline import Pipeline

from src.config import ARTIFACTS, DEFAULT_RANDOM_STATE


def train_classical(train_path: Path, val_path: Path | None = None) -> Pipeline:
    train = pd.read_csv(train_path)
    X_train = train["text"].astype(str)
    y_train = train["is_fake"].astype(int)

    pipe = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=50_000,
                    ngram_range=(1, 2),
                    min_df=2,
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=200,
                    class_weight="balanced",
                    random_state=DEFAULT_RANDOM_STATE,
                    solver="saga",
                ),
            ),
        ]
    )
    pipe.fit(X_train, y_train)

    if val_path and val_path.exists():
        val = pd.read_csv(val_path)
        proba = pipe.predict_proba(val["text"].astype(str))[:, 1]
        pred = (proba >= 0.5).astype(int)
        print("=== Classical (val) ===")
        print(classification_report(val["is_fake"], pred, digits=4))
        try:
            print("ROC-AUC:", round(roc_auc_score(val["is_fake"], proba), 4))
        except ValueError:
            pass

    out_dir = ARTIFACTS / "classical"
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, out_dir / "logreg_tfidf.joblib")
    return pipe


def export_keyword_hints(pipe: Pipeline, top_k: int = 40) -> dict:
    """Map approximate 'fake' vs 'real' n-grams from linear coefficients."""
    vec: TfidfVectorizer = pipe.named_steps["tfidf"]
    clf: LogisticRegression = pipe.named_steps["clf"]
    feats = vec.get_feature_names_out()
    coef = clf.coef_.ravel()
    order = coef.argsort()
    fake_like = [feats[i] for i in order[-top_k:][::-1]]
    real_like = [feats[i] for i in order[:top_k]]
    hints = {
        "note": "Heuristic: high log-reg weight toward fake class (dataset-specific; not universal truth).",
        "ngrams_associated_with_predicted_fake": fake_like,
        "ngrams_associated_with_predicted_real": real_like,
    }
    out = ARTIFACTS / "classical" / "keyword_hints.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(hints, indent=2), encoding="utf-8")
    return hints
