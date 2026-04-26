"""Operator checks: artifact files and UI paths. Does not import TensorFlow or sklearn."""

from __future__ import annotations

import json
import sys

from src.config import ARTIFACTS, PROJECT_ROOT


def run() -> int:
    web = PROJECT_ROOT / "web" / "index.html"
    static = PROJECT_ROOT / "static" / "index.html"
    classical = ARTIFACTS / "classical" / "logreg_tfidf.joblib"
    bilstm = ARTIFACTS / "keras_bilstm" / "model.keras"
    mini = ARTIFACTS / "keras_mini_transformer" / "model.keras"
    metrics = ARTIFACTS / "metrics.json"

    out = {
        "project_root": str(PROJECT_ROOT),
        "artifacts_dir": str(ARTIFACTS),
        "classical_model_present": classical.is_file(),
        "keras_bilstm_present": bilstm.is_file(),
        "keras_mini_transformer_present": mini.is_file(),
        "metrics_json_present": metrics.is_file(),
        "product_ui_index_present": web.is_file(),
        "legacy_ui_index_present": static.is_file(),
    }
    out["api_classical_ready"] = out["classical_model_present"]
    print(json.dumps(out, indent=2))
    return 0 if out["classical_model_present"] else 1


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
