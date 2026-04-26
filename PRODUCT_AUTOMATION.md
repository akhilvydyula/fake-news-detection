# Product view: automating triage on unseen news (not replacing journalists)

This document is for **you and your students**: how ML fits a **generic news pipeline** when volume is too large for 100% human pre-review.

## 1. What problem ML actually solves

| Humans alone | + ML triage |
|--------------|-------------|
| Every new article needs initial sorting | Models **score** unseen text in milliseconds |
| Reviewers burn out on obvious/low-risk items | **Queues** can prioritize high scores (“needs review”) |
| Inconsistent first-pass decisions | **Same rule** applied to every item (with known biases) |

ML does **not** solve: legal liability, moral judgment, or “is this sentence objectively true?” It approximates **similarity to patterns** in training data (e.g. “looks like articles we labeled needs-review vs reliable”).

## 2. Unseen data → automation flow

1. **Ingest:** CMS webhook, RSS, or (where allowed) `GET` URL → plain text (`src/ingest/fetch_url.py` + `/api/analyze-url`).
2. **Score:** Trained model(s) output `P(needs review)` — classical (explainable), neural, or later a transformer/LLM head.
3. **Explain:** Phrase-level cues (TF–IDF × weights) or attention-based methods for deep models — see UI **“Why this score?”**.
4. **Route:** Rules you define, e.g.  
   - &lt; 0.3 → auto path + spot audits  
   - 0.3–0.5 → junior reviewer  
   - &gt; 0.5 → senior / fact-check  
5. **Feedback loop:** Store human labels; retrain or fine-tune on **your** distribution (essential for any serious product).

## 3. “Human-written vs LLM-generated” vs “fake news”

- **Misinformation / low credibility** (what this repo targets in training): often about **content style and source mix** in a labeled dataset.
- **AI-generated text** detection is a **different** task (perplexity, watermarks, specialized classifiers). A human can write false stories; an LLM can write bland true summaries. Your product copy should **not** equate “not fake” with “human wrote it.”

The API returns `product_framing` fields that state this explicitly for end users.

## 4. Model tiers (what to teach, in order)

| Tier | Typical stack | Strengths | Limits |
|------|----------------|-----------|--------|
| Classical | TF–IDF + logistic regression | Fast, interpretable, cheap | Misses long-range semantics |
| Deep (CNN/LSTM) | Keras / PyTorch | Captures order and local patterns | Harder to explain; needs data |
| Transformers | BERT-family, fine-tuned | Strong transfer; SOTA-ish on many text CLF | Compute, drift, still not “truth” |
| LLM + RAG | Retrieve evidence, prompt for critique | Good for **assistant** workflows | Hallucination, cost, policy; not a single “fake” score |

**PyTorch:** same ideas as Keras; swap in `torch.nn` + HF `AutoModelForSequenceClassification` with a labeled head.

**RAG:** retrieve trusted sources, ask the LLM to compare claims—useful for **assistive** fact-check UX, not a drop-in replacement for your classifier without careful eval.

## 5. Generic deployment across websites

- Keep **one scoring service** (FastAPI): every site sends **normalized text** (title + body).
- **Per-tenant calibration:** thresholds and optional fine-tunes per brand/locale.
- **Compliance:** respect robots.txt, copyright, and GDPR when fetching URLs; prefer **your** CMS as the source of truth.

## 6. Notebooks

See **`notebooks/03_automation_product_and_model_zoo.ipynb`** for a class-friendly narrative, accuracy caveats at scale, and extension exercises.
