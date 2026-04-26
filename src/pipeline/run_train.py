"""End-to-end training entrypoint (data build + classical + Keras + metrics + optional MLflow)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import classification_report, roc_auc_score

from src.config import ARTIFACTS, DATA_PROCESSED, DEFAULT_MAX_SAMPLES, PROJECT_ROOT
from src.models.classical import export_keyword_hints, train_classical
from src.models.evaluate import classical_metrics_on_split, overfitting_reading
from src.models.keras_models import evaluate_keras_on_csv, train_keras_model


def _maybe_build_data(max_samples: int, ag_sports: int, seed: int) -> None:
    cmd = [
        sys.executable,
        "-m",
        "src.data.build_dataset",
        "--max-samples",
        str(max_samples),
        "--ag-sports-extra",
        str(ag_sports),
        "--seed",
        str(seed),
    ]
    subprocess.check_call(cmd, cwd=str(PROJECT_ROOT))


def _eval_classical_test() -> None:
    import joblib

    test = pd.read_csv(DATA_PROCESSED / "test.csv")
    pipe = joblib.load(ARTIFACTS / "classical" / "logreg_tfidf.joblib")
    proba = pipe.predict_proba(test["text"].astype(str))[:, 1]
    pred = (proba >= 0.5).astype(int)
    print("=== Classical (test) ===")
    print(classification_report(test["is_fake"], pred, digits=4))
    try:
        print("ROC-AUC:", round(roc_auc_score(test["is_fake"], proba), 4))
    except ValueError:
        pass


def _write_metrics_json(pipe, keras_results: dict) -> dict:
    train_p = DATA_PROCESSED / "train.csv"
    val_p = DATA_PROCESSED / "val.csv"
    test_p = DATA_PROCESSED / "test.csv"
    classical_block = {
        "train": classical_metrics_on_split(pipe, train_p),
        "val": classical_metrics_on_split(pipe, val_p),
        "test": classical_metrics_on_split(pipe, test_p),
    }
    note = overfitting_reading(
        classical_block["train"],
        classical_block["val"],
        classical_block["test"],
    )
    payload = {
        "classical": classical_block,
        "keras": keras_results,
        "overfitting_note": note,
        "label_meaning": {
            "is_fake_1": "Model treats as 'needs editorial review' relative to training data.",
            "is_fake_0": "Closer to 'reliable' articles in training—not a guarantee of truth.",
        },
    }
    out = ARTIFACTS / "metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _maybe_mlflow_log(
    args: argparse.Namespace,
    metrics_payload: dict,
    max_samples_effective: int,
    keras_epochs_effective: int,
) -> None:
    if not args.mlflow:
        return
    try:
        import mlflow
    except ImportError:
        print("MLflow not installed; skip. pip install mlflow")
        return

    uri = os.environ.get("MLFLOW_TRACKING_URI", str(PROJECT_ROOT / "mlruns"))
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(args.mlflow_experiment)
    with mlflow.start_run(run_name=args.mlflow_run_name):
        mlflow.log_params(
            {
                "max_samples_effective": max_samples_effective,
                "quick": args.quick,
                "keras_epochs": keras_epochs_effective,
            }
        )
        c = metrics_payload.get("classical", {})
        for split in ("train", "val", "test"):
            if split not in c:
                continue
            m = c[split]
            for k, v in m.items():
                if k in ("confusion_matrix", "confusion_labels", "threshold"):
                    continue
                if v is None:
                    continue
                mlflow.log_metric(f"classical_{split}_{k}", float(v))

        for kind, summary in metrics_payload.get("keras", {}).items():
            if not isinstance(summary, dict):
                continue
            for k, v in summary.items():
                if isinstance(v, bool) or v is None:
                    continue
                if isinstance(v, (int, float)):
                    mlflow.log_metric(f"{kind}_{k}", float(v))

        mlflow.log_artifact(str(ARTIFACTS / "classical" / "logreg_tfidf.joblib"))
        mlflow.log_artifact(str(ARTIFACTS / "classical" / "keyword_hints.json"))
        mlflow.log_artifact(str(ARTIFACTS / "metrics.json"))
    print("MLflow run logged. UI: mlflow ui --backend-store-uri", uri)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--skip-build", action="store_true", help="Reuse existing CSVs in data/processed/.")
    p.add_argument("--max-samples", type=int, default=DEFAULT_MAX_SAMPLES)
    p.add_argument("--ag-sports-extra", type=int, default=2000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--quick", action="store_true", help="Smaller data and fewer epochs for smoke tests.")
    p.add_argument("--keras-epochs", type=int, default=4)
    p.add_argument("--mlflow", action="store_true", help="Log params, metrics, and key artifacts to MLflow.")
    p.add_argument("--mlflow-experiment", type=str, default="fake-news-detection")
    p.add_argument("--mlflow-run-name", type=str, default="train")
    args = p.parse_args()

    max_samples = 2500 if args.quick else args.max_samples
    ag = min(500 if args.quick else args.ag_sports_extra, max_samples // 2)
    epochs = 1 if args.quick else args.keras_epochs

    if not args.skip_build:
        _maybe_build_data(max_samples=max_samples, ag_sports=ag, seed=args.seed)

    train_path = DATA_PROCESSED / "train.csv"
    val_path = DATA_PROCESSED / "val.csv"
    test_path = DATA_PROCESSED / "test.csv"
    if not train_path.exists():
        raise SystemExit("Missing train.csv — run without --skip-build first.")

    pipe = train_classical(train_path, val_path)
    export_keyword_hints(pipe, top_k=50)

    bilstm_model, bilstm_sum = train_keras_model(
        train_path, val_path, kind="bilstm", epochs=epochs, batch_size=64
    )
    mt_model, mt_sum = train_keras_model(
        train_path, val_path, kind="mini_transformer", epochs=epochs, batch_size=64
    )

    keras_results: dict = {
        "bilstm_val": bilstm_sum,
        "mini_transformer_val": mt_sum,
    }
    if test_path.exists():
        keras_results["bilstm_test"] = evaluate_keras_on_csv(bilstm_model, test_path)
        keras_results["mini_transformer_test"] = evaluate_keras_on_csv(mt_model, test_path)

    metrics_payload = _write_metrics_json(pipe, keras_results)

    _eval_classical_test()
    _maybe_mlflow_log(args, metrics_payload, max_samples, epochs)

    print("\nArtifacts written under:", ARTIFACTS.resolve())
    print("Overfitting hint:", metrics_payload.get("overfitting_note"))


if __name__ == "__main__":
    main()
