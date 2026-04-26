(function () {
  "use strict";

  const pages = document.querySelectorAll("[data-page]");
  const navLinks = document.querySelectorAll(".nav-links a[data-page]");
  const brandLogo = document.getElementById("brand-logo");
  const footerBrand = document.getElementById("footer-brand");
  const heroTitle = document.getElementById("hero-title");

  function showPage(name) {
    pages.forEach((el) => {
      const p = el.getAttribute("data-page");
      if (el.classList.contains("page")) {
        el.classList.toggle("active", p === name);
      }
    });
    navLinks.forEach((a) => {
      a.classList.toggle("active", a.getAttribute("data-page") === name);
    });
  }

  function routeFromHash() {
    const h = (location.hash || "#home").replace("#", "") || "home";
    const allowed = ["home", "dashboard", "pricing", "docs", "security"];
    showPage(allowed.includes(h) ? h : "home");
  }

  window.addEventListener("hashchange", routeFromHash);

  navLinks.forEach((a) => {
    a.addEventListener("click", (e) => {
      const p = a.getAttribute("data-page");
      if (p) {
        e.preventDefault();
        location.hash = "#" + p;
      }
    });
  });

  document.querySelector(".logo")?.addEventListener("click", (e) => {
    e.preventDefault();
    location.hash = "#home";
  });

  async function loadHealth() {
    try {
      const r = await fetch("/api/health");
      if (!r.ok) return;
      const j = await r.json();
      const brand = j.brand || "News Trust Platform";
      if (footerBrand) footerBrand.textContent = brand;
      if (brandLogo) {
        const parts = brand.trim().split(/\s+/);
        if (parts.length >= 2) {
          brandLogo.innerHTML =
            escapeHtml(parts.slice(0, -1).join(" ")) +
            " <span>" +
            escapeHtml(parts[parts.length - 1]) +
            "</span>";
        } else {
          brandLogo.textContent = brand;
        }
      }
      if (heroTitle && j.brand && j.brand !== "News Trust Platform") {
        heroTitle.textContent = brand + " — triage news before you trust it";
      }
    } catch (_) {
      /* offline demo */
    }
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function stripMdBold(s) {
    return String(s).replace(/\*\*/g, "");
  }

  const modeRadios = document.querySelectorAll('input[name="mode"]');
  const pasteFields = document.getElementById("paste-fields");
  const urlFields = document.getElementById("url-fields");

  modeRadios.forEach((r) => {
    r.addEventListener("change", () => {
      const url = r.value === "url";
      if (pasteFields) pasteFields.style.display = url ? "none" : "";
      if (urlFields) urlFields.style.display = url ? "" : "none";
    });
  });

  const btn = document.getElementById("btn-analyze");
  const errEl = document.getElementById("analyze-err");
  const resultsPlaceholder = document.getElementById("results-placeholder");
  const resultsContent = document.getElementById("results-content");
  const ringsEl = document.getElementById("rings");
  const signalCardsEl = document.getElementById("signal-cards");
  const summaryBox = document.getElementById("summary-box");
  const summaryText = document.getElementById("summary-text");
  const framingEl = document.getElementById("product-framing");

  function ringCard(label, value, caption) {
    const pct = Math.max(0, Math.min(100, Math.round(Number(value) * 100)));
    let color = "var(--ok)";
    if (pct >= 55) color = "var(--danger)";
    else if (pct >= 35) color = "var(--warn)";
    return (
      '<div class="ring-card">' +
      '<div class="label">' +
      escapeHtml(label) +
      "</div>" +
      '<div class="donut" style="background:conic-gradient(' +
      color +
      " " +
      pct +
      "%, var(--border) 0);">" +
      '<span class="donut-inner">' +
      pct +
      "%</span></div>" +
      '<div class="cap">' +
      escapeHtml(caption) +
      "</div></div>"
    );
  }

  function renderResults(data) {
    if (resultsPlaceholder) resultsPlaceholder.hidden = true;
    if (resultsContent) resultsContent.hidden = false;

    const plat = data.platform || {};
    const dims = plat.dimensions || {};

    if (summaryText && summaryBox) {
      const sum = plat.article_summary || "";
      if (sum) {
        summaryText.textContent = sum;
        summaryBox.hidden = false;
      } else {
        summaryBox.hidden = true;
      }
    }

    if (ringsEl) {
      ringsEl.innerHTML =
        ringCard(
          "Misinformation-style",
          dims.misinformation_style_0_to_1 ?? data.score_toward_review_0_to_1,
          "Pattern vs. training labels (not fact-check).",
        ) +
        ringCard(
          "AI-style (experimental)",
          dims.ai_text_experimental_0_to_1 ?? 0,
          plat.ai_style_block?.disclaimer || "Heuristic only.",
        ) +
        ringCard(
          "Composite attention",
          dims.composite_attention_0_to_1 ?? data.score_toward_review_0_to_1,
          "Combined triage signal for queues.",
        );
    }

    if (signalCardsEl) {
      const cards = plat.signal_cards || plat.agents || [];
      signalCardsEl.innerHTML = cards
        .map((a) => {
          const pct = Math.round((a.score_0_to_1 || 0) * 100);
          const signals = (a.signals || []).slice(0, 2);
          const sigHtml = signals.length
            ? "<p>" +
              signals.map((s) => escapeHtml(s)).join(" ") +
              "</p>"
            : "";
          return (
            '<div class="signal-card">' +
            '<div class="ico">' +
            escapeHtml(a.icon || "•") +
            "</div>" +
            "<div>" +
            "<h4>" +
            escapeHtml(a.title || "") +
            "</h4>" +
            "<p>" +
            escapeHtml(a.one_liner || "") +
            "</p>" +
            sigHtml +
            '<div class="bar-wrap"><div class="bar" style="width:' +
            pct +
            '%"></div></div>' +
            "</div></div>"
          );
        })
        .join("");
    }

    if (framingEl && data.product_framing) {
      const pf = data.product_framing;
      framingEl.innerHTML = Object.keys(pf)
        .map(
          (k) =>
            "<p><strong>" +
            escapeHtml(k.replace(/_/g, " ")) +
            ":</strong> " +
            escapeHtml(stripMdBold(pf[k])) +
            "</p>",
        )
        .join("");
    }
  }

  btn?.addEventListener("click", async () => {
    if (errEl) {
      errEl.hidden = true;
      errEl.textContent = "";
    }

    const mode = document.querySelector('input[name="mode"]:checked')?.value || "paste";
    const backend = document.getElementById("backend")?.value || "classical";
    const apiKey = document.getElementById("apiKey")?.value?.trim() || "";

    const payload = { backend, teacher_mode: false };
    if (mode === "url") {
      const url = document.getElementById("url")?.value?.trim();
      if (!url) {
        if (errEl) {
          errEl.textContent = "Enter a URL.";
          errEl.hidden = false;
        }
        return;
      }
      payload.url = url;
    } else {
      payload.title = document.getElementById("title")?.value || "";
      payload.body = document.getElementById("body")?.value || "";
    }

    const headers = { "Content-Type": "application/json" };
    if (apiKey) headers["X-API-Key"] = apiKey;

    btn.disabled = true;
    try {
      const r = await fetch("/api/v1/analyze", {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        const msg = data.detail || r.statusText || "Request failed";
        if (errEl) {
          errEl.textContent = typeof msg === "string" ? msg : JSON.stringify(msg);
          errEl.hidden = false;
        }
        return;
      }
      renderResults(data);
    } catch (e) {
      if (errEl) {
        errEl.textContent = String(e.message || e);
        errEl.hidden = false;
      }
    } finally {
      btn.disabled = false;
    }
  });

  function fillCurlExamples() {
    const origin = location.origin || "";
    const paste = document.getElementById("curl-paste");
    const url = document.getElementById("curl-url");
    const usage = document.getElementById("curl-usage");
    if (paste) {
      paste.textContent =
        'curl -sS -X POST "' +
        origin +
        '/api/v1/analyze" \\\n' +
        '  -H "Content-Type: application/json" \\\n' +
        '  -d \'{"title":"Headline","body":"First sentence. Second sentence with enough length for analysis.",' +
        '"backend":"classical"}\'';
    }
    if (url) {
      url.textContent =
        'curl -sS -X POST "' +
        origin +
        '/api/v1/analyze" \\\n' +
        '  -H "Content-Type: application/json" \\\n' +
        '  -d \'{"url":"https://example.com/article","backend":"classical"}\'';
    }
    if (usage) {
      usage.textContent =
        'curl -sS "' +
        origin +
        '/api/v1/usage?days=30" \\\n' +
        '  -H "X-API-Key: YOUR_KEY"';
    }
  }

  routeFromHash();
  loadHealth();
  fillCurlExamples();
})();
