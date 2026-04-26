"""Keras BiLSTM and a compact multi-head-attention encoder classifier."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import classification_report, roc_auc_score
from tensorflow import keras
from tensorflow.keras import layers

from src.config import ARTIFACTS, DEFAULT_RANDOM_STATE
from src.models.evaluate import binary_classification_metrics


def _build_vectorize_layer(texts: pd.Series, max_tokens: int = 20_000, seq_len: int = 256):
    vec = layers.TextVectorization(
        max_tokens=max_tokens,
        output_sequence_length=seq_len,
        standardize="lower_and_strip_punctuation",
    )
    vec.adapt(tf.data.Dataset.from_tensor_slices(texts.astype(str)).batch(1024))
    return vec


def build_bilstm(vec: layers.TextVectorization) -> keras.Model:
    inputs = keras.Input(shape=(), dtype=tf.string)
    x = vec(inputs)
    x = layers.Embedding(input_dim=vec.vocabulary_size(), output_dim=128, mask_zero=True)(x)
    x = layers.Bidirectional(layers.LSTM(64, dropout=0.2))(x)
    x = layers.Dense(64, activation="relu")(x)
    out = layers.Dense(1, activation="sigmoid")(x)
    return keras.Model(inputs, out)


def build_mini_transformer(vec: layers.TextVectorization, num_heads: int = 4, ff_dim: int = 128) -> keras.Model:
    inputs = keras.Input(shape=(), dtype=tf.string)
    x = vec(inputs)
    embed = layers.Embedding(input_dim=vec.vocabulary_size(), output_dim=128, mask_zero=True)(x)
    y = layers.MultiHeadAttention(num_heads=num_heads, key_dim=32)(embed, embed)
    y = layers.LayerNormalization(epsilon=1e-6)(embed + y)
    ffn = layers.Dense(ff_dim, activation="relu")(y)
    ffn = layers.Dense(128)(ffn)
    y = layers.LayerNormalization(epsilon=1e-6)(y + ffn)
    y = layers.GlobalAveragePooling1D()(y)
    y = layers.Dropout(0.2)(y)
    y = layers.Dense(64, activation="relu")(y)
    out = layers.Dense(1, activation="sigmoid")(y)
    return keras.Model(inputs, out)


def train_keras_model(
    train_path: Path,
    val_path: Path,
    kind: str = "bilstm",
    epochs: int = 4,
    batch_size: int = 64,
) -> tuple[keras.Model, dict[str, float]]:
    keras.utils.set_random_seed(DEFAULT_RANDOM_STATE)
    train = pd.read_csv(train_path)
    val = pd.read_csv(val_path)

    vec = _build_vectorize_layer(train["text"])
    model = build_bilstm(vec) if kind == "bilstm" else build_mini_transformer(vec)

    model.compile(
        optimizer=keras.optimizers.Adam(1e-3),
        loss="binary_crossentropy",
        metrics=["accuracy", keras.metrics.AUC(name="auc")],
    )

    X_train = train["text"].astype(str).to_numpy()
    y_train = train["is_fake"].astype(np.float32).to_numpy()
    X_val = val["text"].astype(str).to_numpy()
    y_val = val["is_fake"].astype(np.float32).to_numpy()

    cb = [
        keras.callbacks.EarlyStopping(patience=2, restore_best_weights=True, monitor="val_auc", mode="max"),
    ]
    model.fit(
        X_train,
        y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=batch_size,
        callbacks=cb,
        verbose=1,
    )

    proba = model.predict(X_val, verbose=0).ravel()
    pred = (proba >= 0.5).astype(int)
    print(f"=== Keras {kind} (val) ===")
    print(classification_report(val["is_fake"], pred, digits=4))
    try:
        print("ROC-AUC:", round(roc_auc_score(val["is_fake"], proba), 4))
    except ValueError:
        pass

    val_metrics = binary_classification_metrics(val["is_fake"].to_numpy(), proba)

    out_dir = ARTIFACTS / f"keras_{kind}"
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save(out_dir / "model.keras")
    summary = {
        "val_precision": val_metrics["precision"],
        "val_recall": val_metrics["recall"],
        "val_f1": val_metrics["f1"],
        "val_roc_auc": val_metrics["roc_auc"] or 0.0,
    }
    return model, summary


def evaluate_keras_on_csv(model: keras.Model, csv_path: Path) -> dict:
    df = pd.read_csv(csv_path)
    X = df["text"].astype(str).to_numpy()
    y = df["is_fake"].to_numpy()
    proba = model.predict(X, verbose=0).ravel()
    return binary_classification_metrics(y, proba)
