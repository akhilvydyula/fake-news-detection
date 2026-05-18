"""Streamlit product UI for the News Trust Platform.

Run locally:
    streamlit run streamlit_app.py

The app reuses the existing model artifacts and service code. It does not train.
"""

from __future__ import annotations

import os
from typing import Any

import django
import httpx
import streamlit as st

from src.ingest.fetch_url import fetch_url_text
from src.service.enrichment import enrich_platform_payload
from src.service.predictor import (
    Backend,
    artifacts_ready,
    build_api_response,
    build_full_text,
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
    return out


def _score_label(score: float) -> tuple[str, str]:
    if score < 0.35:
        return "Low", "low"
    if score < 0.55:
        return "Medium", "medium"
    return "Elevated", "high"


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

    st.markdown("### Editorial Summary")
    st.info(summary.get("headline", "Analysis complete."))
    st.write(summary.get("detail", ""))
    st.caption(summary.get("simple_scale", ""))

    if platform.get("article_summary"):
        st.markdown("### Article Snapshot")
        st.write(platform["article_summary"])

    st.markdown("### Signal Cards")
    _render_signal_cards(platform.get("signal_cards") or [])

    phrases = (data.get("interpretability") or {}).get("phrases_in_your_text") or []
    if phrases:
        st.markdown("### Phrases That Moved the Score")
        rows = [
            {
                "phrase": p.get("phrase"),
                "effect": str(p.get("effect", "")).replace("_", " "),
                "strength": p.get("strength"),
            }
            for p in phrases
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

    with st.expander("Model and product caveats", expanded=False):
        for title, copy in product_framing().items():
            st.markdown(f"**{title.replace('_', ' ').title()}**")
            st.write(copy.replace("**", ""))


def _render_rss_monitor() -> None:
    st.divider()
    st.markdown("## Daily RSS Ingestion")
    st.caption("Use this as the product review queue. In production, run the same job daily with cron, GitLab schedules, or a platform scheduler.")
    c1, c2 = st.columns([0.32, 0.68])
    with c1:
        if st.button("Run RSS ingest now", use_container_width=True):
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
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("No scored RSS articles yet. Click Run RSS ingest now or run `run.bat score-feeds`.")


def _initialize_state() -> None:
    st.session_state.setdefault("mode", "Paste")
    st.session_state.setdefault("title", "")
    st.session_state.setdefault("body", "")
    st.session_state.setdefault("url", "")
    st.session_state.setdefault("backend", "classical")
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("auto_demo_done", False)


def _set_sample() -> None:
    st.session_state.mode = "Paste"
    st.session_state.title = SAMPLE_TITLE
    st.session_state.body = SAMPLE_BODY


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
            if st.button("Load Sample & Run", use_container_width=True, type="secondary"):
                _set_sample()
                try:
                    _run_analysis()
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))
        with c2:
            if st.button("Analyze", use_container_width=True, type="primary"):
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
                  <p>Click <strong>Load Sample & Run</strong>. The app will fill tested sample copy,
                  run the existing model, and display signal cards here.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    _render_rss_monitor()


if __name__ == "__main__":
    main()
