(function () {
  "use strict";

  /** Prefix for API when app is mounted under a subpath (set <html data-api-base="/myapp">). */
  function apiUrl(path) {
    var base = (document.documentElement.getAttribute("data-api-base") || "").replace(/\/$/, "");
    if (!path.startsWith("/")) path = "/" + path;
    return base + path;
  }

  var brandLogo = document.getElementById("brand-logo");
  var footerBrand = document.getElementById("footer-brand");
  var heroBrandLine = document.getElementById("hero-brand-line");

  async function loadHealth() {
    try {
      var r = await fetch(apiUrl("/api/health"));
      if (!r.ok) return;
      var j = await r.json();
      var brand = j.brand || "News Trust Platform";
      if (footerBrand) footerBrand.textContent = brand;
      if (heroBrandLine) heroBrandLine.textContent = brand;
      if (brandLogo) {
        var parts = brand.trim().split(/\s+/);
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
    } catch (_) {
      /* offline or wrong api base */
    }
  }

  function escapeHtml(s) {
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function stripMdBold(s) {
    return String(s).replace(/\*\*/g, "");
  }

  function formatErrorDetail(detail, status) {
    if (detail == null) return "Request failed (" + status + ")";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map(function (e) {
          if (!e || typeof e !== "object") return JSON.stringify(e);
          var loc = e.loc ? e.loc.join(".") : "";
          var msg = e.msg || e.message || JSON.stringify(e);
          return loc ? msg + " (" + loc + ")" : msg;
        })
        .join("; ");
    }
    return JSON.stringify(detail);
  }

  /** Same article as scripts/smoke_analyze.py (paste mode, meets min length). */
  var SAMPLE_ARTICLE = {
    title: "City sample: council approves transit plan after debate",
    body:
      "Residents filled the chamber as officials voted in favor of the downtown connector. " +
      "The mayor said work could start next year if federal funds arrive. " +
      "Critics asked for stronger parking and accessibility measures near stations.",
  };

  var modeRadios = document.querySelectorAll('#analyze-form input[name="mode"]');
  var pasteFields = document.getElementById("paste-fields");
  var urlFields = document.getElementById("url-fields");

  modeRadios.forEach(function (r) {
    r.addEventListener("change", function () {
      var url = r.value === "url";
      if (pasteFields) pasteFields.style.display = url ? "none" : "";
      if (urlFields) urlFields.style.display = url ? "" : "none";
    });
  });

  var analyzeForm = document.getElementById("analyze-form");
  var errEl = document.getElementById("analyze-err");
  var resultsPlaceholder = document.getElementById("results-placeholder");
  var resultsContent = document.getElementById("results-content");
  var ringsEl = document.getElementById("rings");
  var signalCardsEl = document.getElementById("signal-cards");
  var summaryBox = document.getElementById("summary-box");
  var summaryText = document.getElementById("summary-text");
  var framingEl = document.getElementById("product-framing");
  var resultsPanel = document.getElementById("results-panel");
  var analyzeStatusEl = document.getElementById("analyze-status");
  var analysisResultsAnchor = document.getElementById("analysis-results");

  function setAnalyzeStatus(text, kind) {
    if (!analyzeStatusEl) return;
    if (!text) {
      analyzeStatusEl.textContent = "";
      analyzeStatusEl.hidden = true;
      analyzeStatusEl.className = "analyze-status";
      return;
    }
    analyzeStatusEl.textContent = text;
    analyzeStatusEl.hidden = false;
    analyzeStatusEl.className = "analyze-status" + (kind === "ok" ? " analyze-status-ok" : kind === "err" ? " analyze-status-err" : "");
  }

  function ringCard(label, value, caption) {
    var pct = Math.max(0, Math.min(100, Math.round(Number(value) * 100)));
    var color = "var(--ok)";
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
    setAnalyzeStatus("Analysis complete — scores and signals are below.", "ok");
    if (resultsPlaceholder) resultsPlaceholder.hidden = true;
    if (resultsContent) resultsContent.hidden = false;

    var plat = data.platform || {};
    var dims = plat.dimensions || {};

    if (summaryText && summaryBox) {
      var sum = plat.article_summary || "";
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
          dims.misinformation_style_0_to_1 != null
            ? dims.misinformation_style_0_to_1
            : data.score_toward_review_0_to_1,
          "Pattern vs. training labels (not fact-check).",
        ) +
        ringCard(
          "AI-style (experimental)",
          dims.ai_text_experimental_0_to_1 != null ? dims.ai_text_experimental_0_to_1 : 0,
          (plat.ai_style_block && plat.ai_style_block.disclaimer) || "Heuristic only.",
        ) +
        ringCard(
          "Composite attention",
          dims.composite_attention_0_to_1 != null
            ? dims.composite_attention_0_to_1
            : data.score_toward_review_0_to_1,
          "Combined triage signal for queues.",
        );
    }

    if (signalCardsEl) {
      var cards = plat.signal_cards || plat.agents || [];
      signalCardsEl.innerHTML = cards
        .map(function (a) {
          var pct = Math.round((a.score_0_to_1 || 0) * 100);
          var signals = (a.signals || []).slice(0, 2);
          var sigHtml = signals.length
            ? "<p>" +
              signals
                .map(function (s) {
                  return escapeHtml(s);
                })
                .join(" ") +
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
      var pf = data.product_framing;
      framingEl.innerHTML = Object.keys(pf)
        .map(function (k) {
          return (
            "<p><strong>" +
            escapeHtml(k.replace(/_/g, " ")) +
            ":</strong> " +
            escapeHtml(stripMdBold(pf[k])) +
            "</p>"
          );
        })
        .join("");
    }

    var scrollTarget = analysisResultsAnchor || resultsPanel;
    if (scrollTarget && scrollTarget.scrollIntoView) {
      try {
        scrollTarget.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (_) {
        scrollTarget.scrollIntoView(true);
      }
    }
  }

  function runAnalyze(submitBtn) {
    if (!analyzeForm) return;

    if (errEl) {
      errEl.hidden = true;
      errEl.textContent = "";
    }

    var mode =
      (analyzeForm.querySelector('input[name="mode"]:checked') || {}).value || "paste";
    var backendEl = document.getElementById("backend");
    var backend = (backendEl && backendEl.value) || "classical";
    var apiKeyEl = document.getElementById("apiKey");
    var apiKey = (apiKeyEl && apiKeyEl.value && apiKeyEl.value.trim()) || "";

    var payload = { backend: backend, teacher_mode: false };
    if (mode === "url") {
      var urlEl = document.getElementById("url");
      var url = (urlEl && urlEl.value && urlEl.value.trim()) || "";
      if (!url) {
        if (errEl) {
          errEl.textContent = "Enter a URL.";
          errEl.hidden = false;
        }
        return;
      }
      payload.url = url;
    } else {
      var titleEl = document.getElementById("title");
      var bodyEl = document.getElementById("article-body");
      payload.title = (titleEl && titleEl.value) || "";
      payload.body = (bodyEl && bodyEl.value) || "";
      var combined = (payload.title + "\n" + payload.body).trim();
      if (combined.length < 20) {
        if (errEl) {
          errEl.textContent =
            "Text is too short — add a headline and at least a short paragraph (about 20+ characters total), or click Load sample.";
          errEl.hidden = false;
          errEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
        setAnalyzeStatus("", null);
        return;
      }
    }

    var headers = { "Content-Type": "application/json" };
    if (apiKey) headers["X-API-Key"] = apiKey;

    var prevBtnText = "";
    if (submitBtn) {
      submitBtn.disabled = true;
      prevBtnText = submitBtn.textContent || "";
      submitBtn.textContent = "Analyzing…";
    }
    var t0 = Date.now();
    var statusTick = setInterval(function () {
      var s = Math.floor((Date.now() - t0) / 1000);
      setAnalyzeStatus("Analyzing… (" + s + "s)", null);
    }, 500);
    setAnalyzeStatus("Analyzing… (0s)", null);
    if (analysisResultsAnchor && analysisResultsAnchor.scrollIntoView) {
      try {
        analysisResultsAnchor.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (_) {
        analysisResultsAnchor.scrollIntoView(true);
      }
    }

    var analyzeTimeoutMs = 120000;
    var abortCtrl = typeof AbortController !== "undefined" ? new AbortController() : null;
    var abortTimer =
      abortCtrl &&
      setTimeout(function () {
        try {
          abortCtrl.abort();
        } catch (_) {}
      }, analyzeTimeoutMs);

    fetch(apiUrl("/api/v1/analyze"), {
      method: "POST",
      headers: headers,
      body: JSON.stringify(payload),
      signal: abortCtrl ? abortCtrl.signal : undefined,
    })
      .then(function (r) {
        return r.text().then(function (text) {
          var data = {};
          if (text) {
            try {
              data = JSON.parse(text);
            } catch (_) {
              data = { detail: text.slice(0, 400) || "Non-JSON response (" + r.status + ")" };
            }
          }
          return { ok: r.ok, status: r.status, data: data };
        });
      })
      .then(function (res) {
        if (!res.ok) {
          var msg = formatErrorDetail(res.data && res.data.detail, res.status);
          if (res.status === 401) {
            msg +=
              " If this server requires a key, paste it into “API key” below and try again.";
          }
          setAnalyzeStatus("Request failed — see message under the button.", "err");
          if (errEl) {
            errEl.textContent = msg;
            errEl.hidden = false;
            errEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
          }
          return;
        }
        try {
          renderResults(res.data);
        } catch (e2) {
          setAnalyzeStatus("Could not render results.", "err");
          if (errEl) {
            errEl.textContent = "Could not render results: " + String((e2 && e2.message) || e2);
            errEl.hidden = false;
            errEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
          }
        }
      })
      .catch(function (e) {
        var aborted = e && (e.name === "AbortError" || /aborted/i.test(String(e.message || "")));
        setAnalyzeStatus(aborted ? "Timed out waiting for the server." : "Network error — start the server from the project root.", "err");
        if (errEl) {
          errEl.textContent = aborted
            ? "No response after " +
              Math.round(analyzeTimeoutMs / 1000) +
              "s. Use “Classical” if you picked a Keras backend (first neural run loads TensorFlow). Check the terminal for errors."
            : "Network error — is the API running? " + String((e && e.message) || e);
          errEl.hidden = false;
          errEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
      })
      .finally(function () {
        if (statusTick) {
          clearInterval(statusTick);
          statusTick = null;
        }
        if (abortTimer) clearTimeout(abortTimer);
        if (submitBtn) {
          submitBtn.disabled = false;
          if (prevBtnText) submitBtn.textContent = prevBtnText;
        }
      });
  }

  var btnAnalyze = document.getElementById("btn-analyze");
  function triggerAnalyze(e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    runAnalyze(btnAnalyze);
  }
  if (analyzeForm) {
    analyzeForm.addEventListener("submit", triggerAnalyze, true);
    analyzeForm.addEventListener("keydown", function (e) {
      if (e.key !== "Enter") return;
      if (!e.ctrlKey && !e.metaKey) return;
      var t = e.target;
      if (!t || t.id !== "article-body") return;
      e.preventDefault();
      runAnalyze(btnAnalyze);
    });
  }

  var loadSampleBtn = document.getElementById("btn-load-sample");
  if (loadSampleBtn) {
    loadSampleBtn.addEventListener("click", function () {
      var pasteRadio = analyzeForm && analyzeForm.querySelector('input[name="mode"][value="paste"]');
      if (pasteRadio) {
        pasteRadio.checked = true;
        pasteRadio.dispatchEvent(new Event("change", { bubbles: true }));
      }
      if (pasteFields) pasteFields.style.display = "";
      if (urlFields) urlFields.style.display = "none";
      var tEl = document.getElementById("title");
      var bEl = document.getElementById("article-body");
      if (tEl) tEl.value = SAMPLE_ARTICLE.title;
      if (bEl) bEl.value = SAMPLE_ARTICLE.body;
      if (errEl) {
        errEl.hidden = true;
        errEl.textContent = "";
      }
      requestAnimationFrame(function () {
        runAnalyze(btnAnalyze);
      });
    });
  }

  function maybeDemoRunFromQuery() {
    try {
      var params = new URLSearchParams(location.search || "");
      if (params.get("demo") !== "1" || !analyzeForm) return;
      if (!location.hash || location.hash === "#" || location.hash === "#home") {
        location.hash = "#dashboard";
      }
      setTimeout(function () {
        var pasteRadio = analyzeForm.querySelector('input[name="mode"][value="paste"]');
        if (pasteRadio) {
          pasteRadio.checked = true;
          pasteRadio.dispatchEvent(new Event("change", { bubbles: true }));
        }
        if (pasteFields) pasteFields.style.display = "";
        if (urlFields) urlFields.style.display = "none";
        var tEl = document.getElementById("title");
        var bEl = document.getElementById("article-body");
        if (tEl) tEl.value = SAMPLE_ARTICLE.title;
        if (bEl) bEl.value = SAMPLE_ARTICLE.body;
        if (errEl) {
          errEl.hidden = true;
          errEl.textContent = "";
        }
        runAnalyze(btnAnalyze);
      }, 50);
    } catch (_) {}
  }

  function fillCurlExamples() {
    var origin = location.origin || "";
    var base = (document.documentElement.getAttribute("data-api-base") || "").replace(/\/$/, "");
    var root = origin + base;
    var paste = document.getElementById("curl-paste");
    var url = document.getElementById("curl-url");
    var usage = document.getElementById("curl-usage");
    if (paste) {
      paste.textContent =
        'curl -sS -X POST "' +
        root +
        '/api/v1/analyze" \\\n' +
        '  -H "Content-Type: application/json" \\\n' +
        '  -d \'{"title":"Headline","body":"First sentence. Second sentence with enough length for analysis.",' +
        '"backend":"classical"}\'';
    }
    if (url) {
      url.textContent =
        'curl -sS -X POST "' +
        root +
        '/api/v1/analyze" \\\n' +
        '  -H "Content-Type: application/json" \\\n' +
        '  -d \'{"url":"https://example.com/article","backend":"classical"}\'';
    }
    if (usage) {
      usage.textContent =
        'curl -sS "' +
        root +
        '/api/v1/usage?days=30" \\\n' +
        '  -H "X-API-Key: YOUR_KEY"';
    }
  }

  function init() {
    loadHealth();
    fillCurlExamples();
    maybeDemoRunFromQuery();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
