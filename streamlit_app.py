"""Streamlit product UI for the News Trust Platform.

Run locally:
    streamlit run streamlit_app.py

The app reuses the existing model artifacts and service code. It does not train.
"""

from __future__ import annotations

import os
import re
from html import escape
from typing import Any

import django
import httpx
import pandas as pd
import streamlit as st

from src.ingest.fetch_url import fetch_url_text
from src.service.enrichment import enrich_platform_payload
from src.service.predictor import (
    Backend,
    artifacts_ready,
    build_api_response,
    build_full_text,
    load_metrics_json,
    product_framing,
    warm_classical_cache,
)


SAMPLE_TITLE = "City sample: council approves transit plan after debate"
SAMPLE_BODY = (
    "Residents filled the chamber as officials voted in favor of the downtown connector. "
    "The mayor said work could start next year if federal funds arrive. "
    "Critics asked for stronger parking and accessibility measures near stations."
)


def _brand() -> str:
    return os.environ.get("PLATFORM_BRAND_NAME", "News Trust Platform")


@st.cache_resource(show_spinner=False)
def _setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "newstrust.settings")
    django.setup()


@st.cache_resource(show_spinner=False)
def _warm_models() -> dict[str, bool]:
    """Load the classical model once and return artifact availability."""
    warm_classical_cache()
    return artifacts_ready()


def _run_rss_ingest() -> dict[str, int]:
    _setup_django()
    from platformapp.services import fetch_and_score_feeds

    return fetch_and_score_feeds(max_entries_per_feed=5)


def _recent_rss_articles(limit: int = 25) -> list[dict[str, Any]]:
    _setup_django()
    from platformapp.models import ScoredArticle

    rows = (
        ScoredArticle.objects.select_related("feed")
        .order_by("-flagged_for_review", "-scored_at", "-ingested_at")[:limit]
    )
    return [
        {
            "title": a.title,
            "feed": a.feed.name,
            "prediction": a.prediction.replace("_", " "),
            "confidence": round(a.confidence, 4),
            "flagged": a.flagged_for_review,
            "url": a.url,
        }
        for a in rows
    ]


def _analyze_text(title: str, body: str, backend: Backend) -> dict[str, Any]:
    text = build_full_text(title, body)
    if len(text.strip()) < 20:
        raise ValueError("Text is too short. Add a headline and at least a short paragraph.")
    base = build_api_response(text, backend, teacher_mode=False)
    if base is None:
        raise RuntimeError(
            f"Model files for '{backend}' are missing. Use the Classical backend or add trained artifacts."
        )
    out = enrich_platform_payload(base, text, backend)
    out["source"] = {"type": "paste"}
    st.session_state.last_source_text = text
    return out


def _analyze_url(url: str, backend: Backend) -> dict[str, Any]:
    if not url.strip():
        raise ValueError("Enter a URL or switch to Paste mode.")
    try:
        text, meta = fetch_url_text(url)
    except ValueError:
        raise
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Could not fetch URL: {exc}") from exc
    if len(text.strip()) < 20:
        raise ValueError("Extracted text is too short. Paste the article text manually.")
    base = build_api_response(text, backend, teacher_mode=False)
    if base is None:
        raise RuntimeError(
            f"Model files for '{backend}' are missing. Use the Classical backend or add trained artifacts."
        )
    out = enrich_platform_payload(base, text, backend)
    out["source"] = {"type": "url", **meta}
    st.session_state.last_source_text = text
    return out


def _score_label(score: float) -> tuple[str, str]:
    if score < 0.35:
        return "Low", "low"
    if score < 0.55:
        return "Medium", "medium"
    return "Elevated", "high"


def _pct(x: Any) -> str:
    if x is None:
        return "N/A"
    try:
        return f"{float(x):.1%}"
    except (TypeError, ValueError):
        return "N/A"


def _accuracy_from_confusion(cm: Any) -> float | None:
    if not cm or len(cm) != 2 or len(cm[0]) != 2:
        return None
    tn, fp = int(cm[0][0]), int(cm[0][1])
    fn, tp = int(cm[1][0]), int(cm[1][1])
    total = tn + fp + fn + tp
    if total <= 0:
        return None
    return (tn + tp) / total


def _model_quality() -> dict[str, Any]:
    metrics = load_metrics_json()
    if not metrics or "classical" not in metrics:
        return {
            "available": False,
            "note": "No artifacts/metrics.json found. Run training later to populate accuracy, F1, precision, recall, and ROC-AUC.",
        }
    classical = metrics["classical"]
    test = classical.get("test") or {}
    val = classical.get("val") or {}
    return {
        "available": True,
        "test": {
            "accuracy": _accuracy_from_confusion(test.get("confusion_matrix")),
            "precision": test.get("precision"),
            "recall": test.get("recall"),
            "f1": test.get("f1"),
            "roc_auc": test.get("roc_auc"),
        },
        "validation": {
            "accuracy": _accuracy_from_confusion(val.get("confusion_matrix")),
            "precision": val.get("precision"),
            "recall": val.get("recall"),
            "f1": val.get("f1"),
            "roc_auc": val.get("roc_auc"),
        },
        "confusion_matrix": test.get("confusion_matrix"),
        "note": "Metrics describe the last held-out evaluation run, not a guarantee about this individual article.",
    }


def _split_phrases(phrases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    review = [p for p in phrases if p.get("effect") == "pushes_toward_review"]
    reliable = [p for p in phrases if p.get("effect") == "pushes_toward_reliable"]
    return review, reliable


def _phrase_df(phrases: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for p in phrases:
        effect = str(p.get("effect", "")).replace("_", " ")
        rows.append(
            {
                "phrase": p.get("phrase", ""),
                "direction": "review" if p.get("effect") == "pushes_toward_review" else "reliable",
                "effect": effect,
                "strength": float(p.get("strength") or 0.0),
            }
        )
    return pd.DataFrame(rows)


def _highlight_text(text: str, review_phrases: list[dict[str, Any]], reliable_phrases: list[dict[str, Any]]) -> str:
    """Highlight matched phrases in escaped article text."""
    snippets: list[tuple[str, str]] = []
    for p in review_phrases[:10]:
        phrase = str(p.get("phrase", "")).strip()
        if len(phrase) >= 3:
            snippets.append((phrase, "hl-review"))
    for p in reliable_phrases[:8]:
        phrase = str(p.get("phrase", "")).strip()
        if len(phrase) >= 3:
            snippets.append((phrase, "hl-reliable"))
    if not snippets:
        return escape(text)
    snippets.sort(key=lambda item: len(item[0]), reverse=True)
    pattern = re.compile("|".join(re.escape(s[0]) for s in snippets), re.IGNORECASE)
    style_by_lower = {phrase.lower(): css for phrase, css in snippets}

    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        css = style_by_lower.get(token.lower(), "hl-review")
        return f'<mark class="{css}">{escape(token)}</mark>'

    parts: list[str] = []
    last = 0
    for m in pattern.finditer(text):
        parts.append(escape(text[last : m.start()]))
        parts.append(repl(m))
        last = m.end()
    parts.append(escape(text[last:]))
    return "".join(parts)


def _risk_next_steps(score: float, review_phrases: list[dict[str, Any]]) -> list[str]:
    if score >= 0.55:
        base = [
            "Queue this article for editorial review before publishing.",
            "Verify named entities, sources, dates, and claims independently.",
            "Ask an editor to review the highlighted review-driving phrases.",
        ]
    elif score >= 0.35:
        base = [
            "Run a quick source and quote check before treating this as low risk.",
            "Compare the highlighted phrases with the article context.",
            "Spot-check similar articles in the RSS review queue.",
        ]
    else:
        base = [
            "No strong model warning, but still apply normal editorial checks.",
            "Use this result as triage, not a truth verdict.",
            "Monitor future RSS items for higher composite attention.",
        ]
    if review_phrases[:3]:
        base.append("Top review drivers: " + ", ".join(str(p.get("phrase", "")) for p in review_phrases[:3]) + ".")
    return base


def _quality_card(label: str, value: Any, helper: str = "") -> str:
    return (
        '<div class="quality-card">'
        f'<div class="quality-label">{escape(label)}</div>'
        f'<div class="quality-value">{escape(_pct(value))}</div>'
        f'<div class="quality-helper">{escape(helper)}</div>'
        "</div>"
    )


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
          --ntp-bg: #070a10;
          --ntp-card: #101624;
          --ntp-card2: #151d2e;
          --ntp-border: #263246;
          --ntp-text: #edf4ff;
          --ntp-muted: #9aa9bf;
          --ntp-accent: #67e8c9;
          --ntp-accent2: #7c9cff;
          --ntp-danger: #fb7185;
          --ntp-warn: #fbbf24;
          --ntp-ok: #4ade80;
        }
        .stApp {
          background:
            radial-gradient(ellipse 900px 520px at 10% -20%, rgba(103,232,201,.16), transparent),
            radial-gradient(ellipse 760px 460px at 90% 0%, rgba(124,156,255,.14), transparent),
            var(--ntp-bg);
          color: var(--ntp-text);
        }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stSidebar"] {
          background: rgba(10,14,20,.96);
          border-right: 1px solid var(--ntp-border);
        }
        .block-container { padding-top: 2rem; max-width: 1240px; }
        .ntp-hero {
          border: 1px solid var(--ntp-border);
          border-radius: 28px;
          padding: clamp(1.5rem, 4vw, 3.25rem);
          background:
            linear-gradient(135deg, rgba(21,29,46,.92), rgba(10,14,20,.96)),
            radial-gradient(circle at 80% 20%, rgba(124,156,255,.2), transparent 35%);
          box-shadow: 0 28px 70px rgba(0,0,0,.35);
          margin-bottom: 1.5rem;
        }
        .ntp-eyebrow {
          display: inline-flex;
          border: 1px solid rgba(103,232,201,.32);
          border-radius: 999px;
          padding: .35rem .8rem;
          color: var(--ntp-accent);
          font-weight: 700;
          letter-spacing: .08em;
          text-transform: uppercase;
          font-size: .72rem;
          margin-bottom: 1rem;
        }
        .ntp-title {
          font-size: clamp(2.2rem, 5vw, 4.4rem);
          line-height: 1.02;
          font-weight: 850;
          letter-spacing: -.06em;
          margin: 0 0 .75rem;
        }
        .ntp-gradient {
          background: linear-gradient(105deg, var(--ntp-accent), var(--ntp-accent2));
          -webkit-background-clip: text;
          background-clip: text;
          color: transparent;
        }
        .ntp-lead {
          color: var(--ntp-muted);
          font-size: 1.06rem;
          max-width: 760px;
          line-height: 1.7;
          margin: 0;
        }
        .ntp-card {
          border: 1px solid var(--ntp-border);
          border-radius: 18px;
          background: linear-gradient(165deg, rgba(16,22,36,.92), rgba(21,29,46,.72));
          padding: 1.1rem 1.2rem;
          height: 100%;
        }
        .ntp-card h4 {
          margin: 0 0 .35rem;
          font-size: 1rem;
        }
        .ntp-card p {
          color: var(--ntp-muted);
          margin: 0;
          font-size: .9rem;
          line-height: 1.55;
        }
        .ntp-status {
          display: inline-flex;
          align-items: center;
          gap: .45rem;
          border-radius: 999px;
          padding: .35rem .75rem;
          font-size: .78rem;
          font-weight: 700;
          border: 1px solid var(--ntp-border);
        }
        .ntp-status.low { color: var(--ntp-ok); border-color: rgba(74,222,128,.35); }
        .ntp-status.medium { color: var(--ntp-warn); border-color: rgba(251,191,36,.35); }
        .ntp-status.high { color: var(--ntp-danger); border-color: rgba(251,113,133,.35); }
        .signal-card {
          border: 1px solid var(--ntp-border);
          border-radius: 16px;
          padding: 1rem;
          margin-bottom: .85rem;
          background: rgba(10,14,20,.68);
        }
        .signal-card strong { font-size: 1rem; }
        .signal-card p { color: var(--ntp-muted); margin: .4rem 0 .7rem; }
        .small-muted { color: var(--ntp-muted); font-size: .86rem; }
        .highlight-box {
          border: 1px solid var(--ntp-border);
          border-radius: 18px;
          background: rgba(10,14,20,.78);
          padding: 1rem 1.15rem;
          line-height: 1.85;
          max-height: 420px;
          overflow: auto;
          color: var(--ntp-text);
        }
        mark {
          border-radius: .4rem;
          padding: .12rem .28rem;
          color: #061018;
          font-weight: 800;
        }
        mark.hl-review {
          background: linear-gradient(135deg, #fb7185, #fbbf24);
        }
        mark.hl-reliable {
          background: linear-gradient(135deg, #4ade80, #67e8c9);
        }
        .insight-list {
          margin: .35rem 0 0;
          padding-left: 1.1rem;
          color: var(--ntp-muted);
        }
        .insight-list li { margin: .35rem 0; }
        .research-note {
          border-left: 4px solid var(--ntp-accent2);
          padding: .75rem 1rem;
          border-radius: 12px;
          background: rgba(124,156,255,.09);
          color: var(--ntp-muted);
        }
        .quality-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 1rem;
          margin: 1rem 0 1.4rem;
        }
        .quality-card {
          border: 1px solid var(--ntp-border);
          border-radius: 18px;
          background: rgba(16,22,36,.86);
          padding: 1rem 1.05rem;
          min-height: 118px;
        }
        .quality-label {
          color: var(--ntp-muted);
          font-size: .76rem;
          font-weight: 800;
          letter-spacing: .07em;
          text-transform: uppercase;
          margin-bottom: .55rem;
          white-space: normal;
        }
        .quality-value {
          color: var(--ntp-text);
          font-size: clamp(1.85rem, 3vw, 2.55rem);
          line-height: 1.05;
          font-weight: 850;
          letter-spacing: -.045em;
          white-space: nowrap;
        }
        .quality-helper {
          margin-top: .35rem;
          color: var(--ntp-muted);
          font-size: .78rem;
        }
        div[data-testid="stMetric"] {
          border: 1px solid var(--ntp-border);
          border-radius: 16px;
          background: rgba(16,22,36,.8);
          padding: 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _hero() -> None:
    st.markdown(
        f"""
        <div class="ntp-hero">
          <div class="ntp-eyebrow">{_brand()} · Editorial AI Triage</div>
          <div class="ntp-title">Trust decisions, <span class="ntp-gradient">made faster.</span></div>
          <p class="ntp-lead">
            Paste an article or test a URL. The platform returns a readable risk score, a short summary,
            AI-style heuristic signals, and review cards that help a newsroom decide what needs attention.
            This is an assistive triage tool, not a replacement for editorial judgment.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_capabilities() -> None:
    cols = st.columns(3)
    cards = [
        ("Multi-signal triage", "Misinformation-style score, AI-style heuristic, and composite attention in one workflow."),
        ("No retraining required", "Runs against the current artifacts in this repo. Training stays optional for later."),
        ("Production API aligned", "Uses the same service layer as the REST API so the Streamlit MVP mirrors backend behavior."),
    ]
    for col, (title, body) in zip(cols, cards, strict=True):
        with col:
            st.markdown(f'<div class="ntp-card"><h4>{title}</h4><p>{body}</p></div>', unsafe_allow_html=True)


def _render_signal_cards(cards: list[dict[str, Any]]) -> None:
    for card in cards:
        score = float(card.get("score_0_to_1") or 0)
        label, css = _score_label(score)
        st.markdown(
            f"""
            <div class="signal-card">
              <div style="display:flex;justify-content:space-between;gap:1rem;align-items:start;">
                <strong>{card.get("icon", "•")} {card.get("title", "Signal")}</strong>
                <span class="ntp-status {css}">{label} · {score:.0%}</span>
              </div>
              <p>{card.get("one_liner", "")}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(min(max(score, 0.0), 1.0))
        for reason in card.get("signals") or []:
            st.caption(reason)


def _render_results(data: dict[str, Any]) -> None:
    platform = data.get("platform") or {}
    dims = platform.get("dimensions") or {}
    summary = data.get("user_summary") or {}
    score = float(data.get("score_toward_review_0_to_1") or 0)
    label, css = _score_label(score)
    source = data.get("source") or {}
    source_type = source.get("type", "paste")
    article_text = ""
    if source_type == "url" and platform.get("article_summary"):
        article_text = platform["article_summary"]
    elif st.session_state.get("last_source_text"):
        article_text = str(st.session_state.last_source_text)

    st.subheader("Analysis Results")
    st.markdown(
        f'<span class="ntp-status {css}">Overall review attention: {label} · {score:.0%}</span>',
        unsafe_allow_html=True,
    )
    st.write("")

    m1, m2, m3 = st.columns(3)
    m1.metric("Misinformation-style", f"{float(dims.get('misinformation_style_0_to_1', score)):.0%}")
    m2.metric("AI-style heuristic", f"{float(dims.get('ai_text_experimental_0_to_1', 0)):.0%}")
    m3.metric("Composite attention", f"{float(dims.get('composite_attention_0_to_1', score)):.0%}")

    phrases = (data.get("interpretability") or {}).get("phrases_in_your_text") or []
    review_phrases, reliable_phrases = _split_phrases(phrases)
    phrase_df = _phrase_df(phrases)

    overview_tab, evidence_tab, charts_tab, quality_tab, action_tab = st.tabs(
        ["Overview", "Highlighted Evidence", "Charts", "Model Quality", "Action Plan"]
    )

    with overview_tab:
        st.markdown("### Editorial Summary")
        st.info(summary.get("headline", "Analysis complete."))
        st.write(summary.get("detail", ""))
        st.caption(summary.get("simple_scale", ""))

        if platform.get("article_summary"):
            st.markdown("### Article Snapshot")
            st.write(platform["article_summary"])

        st.markdown("### Signal Cards")
        _render_signal_cards(platform.get("signal_cards") or [])

    with evidence_tab:
        st.markdown("### Why did the model react this way?")
        st.markdown(
            '<p class="small-muted">Highlighted yellow/red terms pushed the model toward review. Green terms pulled it toward reliable-style language. These are statistical TF-IDF/logistic-regression cues, not proof of truth or falsehood.</p>',
            unsafe_allow_html=True,
        )
        if article_text:
            highlighted = _highlight_text(article_text, review_phrases, reliable_phrases)
            st.markdown(f'<div class="highlight-box">{highlighted}</div>', unsafe_allow_html=True)
        else:
            st.info("No article text snapshot is available for highlighting.")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Pushed toward review")
            if review_phrases:
                for item in review_phrases[:8]:
                    st.write(f"**{item.get('phrase')}** · strength `{float(item.get('strength') or 0):.4f}`")
            else:
                st.caption("No strong review-driving phrase captured.")
        with c2:
            st.markdown("#### Pulled toward reliable")
            if reliable_phrases:
                for item in reliable_phrases[:8]:
                    st.write(f"**{item.get('phrase')}** · strength `{float(item.get('strength') or 0):.4f}`")
            else:
                st.caption("No strong reliable-style phrase captured.")

        if not phrase_df.empty:
            st.markdown("#### Evidence Table")
            st.dataframe(phrase_df, width="stretch", hide_index=True)

    with charts_tab:
        st.markdown("### Analysis Charts")
        dim_df = pd.DataFrame(
            [
                {"signal": "Misinformation-style", "score": float(dims.get("misinformation_style_0_to_1", score))},
                {"signal": "AI-style heuristic", "score": float(dims.get("ai_text_experimental_0_to_1", 0))},
                {"signal": "Composite attention", "score": float(dims.get("composite_attention_0_to_1", score))},
            ]
        )
        st.bar_chart(dim_df.set_index("signal"), height=260)

        if not phrase_df.empty:
            top = phrase_df.copy().head(12)
            top["signed_strength"] = top.apply(
                lambda r: r["strength"] if r["direction"] == "review" else -r["strength"],
                axis=1,
            )
            st.markdown("#### Phrase Contribution Direction")
            st.caption("Positive bars increase review attention; negative bars pull toward reliable-style language.")
            st.bar_chart(top.set_index("phrase")[["signed_strength"]], height=300)

        st.markdown("#### Decision Thresholds")
        threshold_df = pd.DataFrame(
            [
                {"zone": "Low / monitor", "threshold": 0.35},
                {"zone": "Medium / spot-check", "threshold": 0.55},
                {"zone": "This article", "threshold": score},
            ]
        )
        st.bar_chart(threshold_df.set_index("zone"), height=220)

    with quality_tab:
        st.markdown("### Model Validation / Research Metrics")
        quality = _model_quality()
        if quality["available"]:
            t = quality["test"]
            v = quality["validation"]
            st.markdown(
                '<div class="quality-grid">'
                + _quality_card("Test accuracy", t.get("accuracy"), "Correct labels on held-out test set")
                + _quality_card("Test F1", t.get("f1"), "Balance of precision and recall")
                + _quality_card("Precision", t.get("precision"), "Flagged items that were truly review-class")
                + _quality_card("Recall", t.get("recall"), "Review-class items caught by the model")
                + _quality_card("ROC-AUC", t.get("roc_auc"), "Ranking quality across thresholds")
                + "</div>",
                unsafe_allow_html=True,
            )
            st.markdown("#### Validation vs Test")
            qdf = pd.DataFrame(
                [
                    {"split": "test", **{k: val for k, val in t.items() if isinstance(val, (int, float))}},
                    {"split": "validation", **{k: val for k, val in v.items() if isinstance(val, (int, float))}},
                ]
            )
            display_qdf = qdf.copy()
            for col in display_qdf.columns:
                if col != "split":
                    display_qdf[col] = display_qdf[col].map(_pct)
            st.dataframe(display_qdf, width="stretch", hide_index=True)
            cm = quality.get("confusion_matrix")
            if cm:
                st.markdown("#### Test Confusion Matrix")
                st.dataframe(
                    pd.DataFrame(cm, index=["actual reliable", "actual review"], columns=["pred reliable", "pred review"]),
                    width="stretch",
                )
            st.markdown(f'<div class="research-note">{escape(quality["note"])}</div>', unsafe_allow_html=True)
        else:
            st.warning(quality["note"])
            st.markdown(
                """
                <div class="research-note">
                Current demo can still score articles because the trained model artifact exists.
                To publish model-performance numbers in a paper or stakeholder deck, generate
                <code>artifacts/metrics.json</code> from a controlled training/evaluation run.
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### Methodology")
        st.write(
            "The deployed classical model uses TF-IDF text features with logistic regression. "
            "The phrase table ranks per-article terms by their contribution to the model's review-class score."
        )

    with action_tab:
        st.markdown("### AI-Driven Recommendations")
        steps = _risk_next_steps(score, review_phrases)
        st.markdown(
            "<ul class='insight-list'>" + "".join(f"<li>{escape(step)}</li>" for step in steps) + "</ul>",
            unsafe_allow_html=True,
        )
        st.markdown("### Suggested Workflow")
        workflow = pd.DataFrame(
            [
                {"stage": "1. Triage", "owner": "Model", "output": f"{score:.0%} review attention"},
                {"stage": "2. Evidence review", "owner": "Editor", "output": "Inspect highlighted phrases and source claims"},
                {"stage": "3. Verification", "owner": "Researcher", "output": "Check citations, dates, names, and corroboration"},
                {"stage": "4. Decision", "owner": "Desk lead", "output": "Publish, revise, escalate, or reject"},
            ]
        )
        st.dataframe(workflow, width="stretch", hide_index=True)

        with st.expander("Product caveats", expanded=False):
            for title, copy in product_framing().items():
                st.markdown(f"**{title.replace('_', ' ').title()}**")
                st.write(copy.replace("**", ""))


def _render_rss_monitor() -> None:
    st.divider()
    st.markdown("## Daily RSS Ingestion")
    st.caption("Use this as the product review queue. In production, run the same job daily with cron, GitLab schedules, or a platform scheduler.")
    c1, c2 = st.columns([0.32, 0.68])
    with c1:
        if st.button("Run RSS ingest now", width="stretch"):
            try:
                result = _run_rss_ingest()
                st.success(f"RSS ingest complete: {result}")
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
    with c2:
        st.markdown(
            '<p class="small-muted">Command equivalent: <code>run.bat migrate</code> once, then <code>run.bat score-feeds</code> daily.</p>',
            unsafe_allow_html=True,
        )
    try:
        rows = _recent_rss_articles()
    except Exception as exc:  # noqa: BLE001
        st.info(f"Run migrations first to enable the RSS queue: {exc}")
        return
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("No scored RSS articles yet. Click Run RSS ingest now or run `run.bat score-feeds`.")


def _initialize_state() -> None:
    st.session_state.setdefault("mode", "Paste")
    st.session_state.setdefault("title", "")
    st.session_state.setdefault("body", "")
    st.session_state.setdefault("url", "")
    st.session_state.setdefault("backend", "classical")
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("last_source_text", "")
    st.session_state.setdefault("auto_demo_done", False)


def _set_sample() -> None:
    st.session_state.mode = "Paste"
    st.session_state.title = SAMPLE_TITLE
    st.session_state.body = SAMPLE_BODY


def _run_sample_analysis() -> None:
    """Run the tested sample without mutating widget state after render."""
    backend = st.session_state.backend
    with st.spinner("Analyzing the tested sample with the current model artifacts..."):
        st.session_state.last_result = _analyze_text(SAMPLE_TITLE, SAMPLE_BODY, backend)


def _run_analysis() -> None:
    backend = st.session_state.backend
    mode = st.session_state.mode
    with st.spinner("Analyzing with the current model artifacts..."):
        if mode == "URL":
            st.session_state.last_result = _analyze_url(st.session_state.url, backend)
        else:
            st.session_state.last_result = _analyze_text(
                st.session_state.title,
                st.session_state.body,
                backend,
            )


def main() -> None:
    st.set_page_config(
        page_title=f"{_brand()} | News Trust Platform",
        page_icon="◎",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_css()
    _initialize_state()

    demo_param = st.query_params.get("demo")
    if demo_param == "1" and not st.session_state.auto_demo_done:
        _set_sample()
        st.session_state.auto_demo_done = True
        try:
            _run_analysis()
        except Exception as exc:  # noqa: BLE001 - surface product errors in UI.
            st.session_state.last_error = str(exc)

    ready = _warm_models()

    with st.sidebar:
        st.title(_brand())
        st.caption("Streamlit MVP · no model training required")
        st.markdown("### Model")
        available_backends: list[Backend] = ["classical"]
        if ready.get("bilstm"):
            available_backends.append("bilstm")
        if ready.get("mini_transformer"):
            available_backends.append("mini_transformer")
        st.selectbox(
            "Backend",
            options=available_backends,
            key="backend",
            help="Classical uses the existing TF-IDF + Logistic Regression artifact.",
        )
        st.markdown("### Artifact Status")
        for name, ok in ready.items():
            st.write(("✅" if ok else "⚠️") + f" {name}")
        st.divider()
        st.caption("Local: `run.bat streamlit`")
        st.caption("Demo URL: `?demo=1`")

    _hero()
    _render_capabilities()
    st.write("")

    left, right = st.columns([0.92, 1.08], gap="large")

    with left:
        st.markdown("## Analyze Content")
        st.radio("Input mode", ["Paste", "URL"], horizontal=True, key="mode")
        if st.session_state.mode == "Paste":
            st.text_input("Title", key="title", placeholder="Optional headline")
            st.text_area(
                "Article body",
                key="body",
                height=220,
                placeholder="Paste article text here...",
            )
        else:
            st.text_input("Article URL", key="url", placeholder="https://example.com/article")
            st.caption("URL fetch blocks localhost/private networks and works best on public HTML articles.")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Load Sample & Run", width="stretch", type="secondary"):
                try:
                    _run_sample_analysis()
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))
        with c2:
            if st.button("Analyze", width="stretch", type="primary"):
                try:
                    _run_analysis()
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))

        st.markdown(
        '<p class="small-muted">Results render on the right immediately. Use the sample button for a zero-typing demo.</p>',
            unsafe_allow_html=True,
        )

    with right:
        if st.session_state.get("last_error"):
            st.error(st.session_state.pop("last_error"))
        if st.session_state.last_result:
            _render_results(st.session_state.last_result)
        else:
            st.markdown("## Results")
            st.markdown(
                """
                <div class="ntp-card">
                  <h4>Ready for a one-click demo</h4>
                  <p>Click <strong>Load Sample & Run</strong>. The app will run tested sample copy
                  through the existing model and display signal cards here.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    _render_rss_monitor()


if __name__ == "__main__":
    main()
