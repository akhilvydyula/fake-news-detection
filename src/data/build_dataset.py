"""
Build a stratified CSV for training from public datasets.

Important: BBC robots.txt and terms prohibit systematic scraping and creating
datasets from BBC content for model training. This project uses HuggingFace
datasets with clear research licensing instead. For a sport-heavy "real" prior,
we optionally blend AG News sports headlines (label==1) — not BBC.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from datasets import load_dataset
from sklearn.model_selection import train_test_split

from src.config import (
    DATA_PROCESSED,
    DEFAULT_MAX_SAMPLES,
    DEFAULT_RANDOM_STATE,
    HF_AG_NEWS,
    HF_FAKE_NEWS,
    TEST_SIZE,
    VAL_SIZE,
)
from src.data.preprocess import clean_text, combine_title_body


def _load_fake_news_hf() -> pd.DataFrame:
    ds = load_dataset(HF_FAKE_NEWS, split="train")
    rows = []
    for ex in ds:
        text = combine_title_body(ex.get("title"), ex.get("text"))
        # GonzaloA/fake_news: label 0 = unreliable/fake-style, 1 = reliable/real-style
        is_fake = 1 if int(ex["label"]) == 0 else 0
        rows.append({"text": text, "is_fake": is_fake, "source": "gonzalo_fake_news"})
    return pd.DataFrame(rows)


def _load_ag_news_sports(max_rows: int | None) -> pd.DataFrame:
    if max_rows is None or max_rows <= 0:
        return pd.DataFrame(columns=["text", "is_fake", "source"])
    ag = load_dataset(HF_AG_NEWS, split="train")
    # AG News: 0 World, 1 Sports, 2 Business, 3 Sci/Tech
    texts = []
    for ex in ag:
        if int(ex["label"]) != 1:
            continue
        texts.append(clean_text(ex["text"]))
        if len(texts) >= max_rows:
            break
    return pd.DataFrame(
        {"text": texts, "is_fake": 0, "source": "ag_news_sports"},
    )


def build_frame(
    max_samples: int = DEFAULT_MAX_SAMPLES,
    ag_sports_extra: int = 2000,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> pd.DataFrame:
    base = _load_fake_news_hf()
    base = base[base["text"].str.len() > 40]
    extra = _load_ag_news_sports(min(ag_sports_extra, max_samples // 2))
    df = pd.concat([base, extra], ignore_index=True)
    df = df.drop_duplicates(subset=["text"]).reset_index(drop=True)

    if len(df) > max_samples:
        strat = df["is_fake"]
        df, _ = train_test_split(
            df,
            train_size=max_samples,
            stratify=strat,
            random_state=random_state,
        )
        df = df.reset_index(drop=True)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Build processed training CSV from HF datasets.")
    parser.add_argument("--max-samples", type=int, default=DEFAULT_MAX_SAMPLES)
    parser.add_argument("--ag-sports-extra", type=int, default=2000, help="Extra real sports lines from AG News.")
    parser.add_argument("--out", type=Path, default=DATA_PROCESSED / "labeled_news.csv")
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_STATE)
    args = parser.parse_args()

    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    df = build_frame(max_samples=args.max_samples, ag_sports_extra=args.ag_sports_extra, random_state=args.seed)

    train, test = train_test_split(df, test_size=TEST_SIZE, stratify=df["is_fake"], random_state=args.seed)
    train, val = train_test_split(
        train,
        test_size=VAL_SIZE / (1 - TEST_SIZE),
        stratify=train["is_fake"],
        random_state=args.seed,
    )

    train.to_csv(DATA_PROCESSED / "train.csv", index=False)
    val.to_csv(DATA_PROCESSED / "val.csv", index=False)
    test.to_csv(DATA_PROCESSED / "test.csv", index=False)
    df.to_csv(args.out, index=False)

    print(f"Wrote {len(train)} train, {len(val)} val, {len(test)} test rows.")
    print(f"Full merged: {args.out} ({len(df)} rows)")
    print("Class balance (full):", df["is_fake"].value_counts().to_dict())


if __name__ == "__main__":
    main()
