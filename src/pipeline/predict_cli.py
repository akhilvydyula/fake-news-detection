"""Score a single article or a CSV with trained artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import tensorflow as tf


def predict_classical(text: str) -> float:
    from src.config import ARTIFACTS

    pipe = joblib.load(ARTIFACTS / "classical" / "logreg_tfidf.joblib")
    return float(pipe.predict_proba([text])[0, 1])


def predict_keras(text: str, kind: str = "bilstm") -> float:
    from src.config import ARTIFACTS

    model = tf.keras.models.load_model(ARTIFACTS / f"keras_{kind}" / "model.keras")
    p = model.predict(np.array([text], dtype=str), verbose=0).ravel()[0]
    return float(p)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--text", type=str, default="", help="Raw article text (title + body).")
    p.add_argument("--text-file", type=Path, help="UTF-8 file with article text.")
    p.add_argument("--csv", type=Path, help="CSV with a 'text' column to score.")
    p.add_argument("--backend", choices=("classical", "bilstm", "mini_transformer"), default="classical")
    args = p.parse_args()

    if args.text_file:
        text = args.text_file.read_text(encoding="utf-8", errors="replace").strip()
    else:
        text = args.text.strip()

    if args.csv:
        df = pd.read_csv(args.csv)
        if "text" not in df.columns:
            raise SystemExit("CSV must contain a 'text' column.")
        rows = []
        for t in df["text"].astype(str):
            if args.backend == "classical":
                score = predict_classical(t)
            else:
                score = predict_keras(t, kind="bilstm" if args.backend == "bilstm" else "mini_transformer")
            rows.append(score)
        df["p_fake"] = rows
        out = args.csv.with_name(args.csv.stem + "_scored.csv")
        df.to_csv(out, index=False)
        print("Wrote:", out)
        return

    if not text:
        raise SystemExit("Provide --text, --text-file, or --csv.")

    if args.backend == "classical":
        score = predict_classical(text)
    else:
        score = predict_keras(text, kind="bilstm" if args.backend == "bilstm" else "mini_transformer")

    print("P(fake):", round(score, 4))
    print("Suggested flag:", "review" if score >= 0.5 else "likely_reliable")


if __name__ == "__main__":
    main()
