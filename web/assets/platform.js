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
  var insightPanel = document.getElementById("insight-panel");

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
      '%, var(--border) 0);">' +
      '<span class="donut-inner">' +
      pct +
      "%</span></div>" +
      '<div class="cap">' +
      escapeHtml(caption) +
      "</div></div>"
    );
  }

  function renderInsightResults(data) {
    setAnalyzeStatus("Insight complete — classical keyword breakdown below.", "ok");
    if (resultsPlaceholder) resultsPlaceholder.hidden = true;
    if (resultsContent) resultsContent.hidden = false;
    if (insightPanel) {
      insightPanel.hidden = false;
    }
    if (summaryBox) summaryBox.hidden = true;
    if (ringsEl) ringsEl.innerHTML = "";
    if (signalCardsEl) signalCardsEl.innerHTML = "";
    if (framingEl) framingEl.innerHTML = "";

    var fr = data.fake_risk || {};
    var pct =
      fr.percent_scale_toward_review != null
        ? fr.percent_scale_toward_review
        : Math.round((fr.score_toward_review_0_to_1 || 0) * 100);
    var mq = (data.model && data.model.holdout_quality) || {};
    var hold = mq.classical_tfidf_logistic || {};
    var test = hold.holdout_test || {};
    var qualHtml = "";
    if (mq.available && test.accuracy != null) {
      qualHtml =
        '<p class="field-hint" style="margin:0 0 0.75rem;">Last training hold-out test accuracy (same classical model): <strong>' +
        String(Math.round(test.accuracy * 10000) / 10000) +
        "</strong>";
      if (test.roc_auc != null) {
        qualHtml += ' · ROC-AUC: <strong>' + escapeHtml(String(test.roc_auc).slice(0, 8)) + "</strong>";
      }
      if (test.f1 != null) {
        qualHtml += ' · F1: <strong>' + escapeHtml(String(test.f1).slice(0, 8)) + "</strong>";
      }
      qualHtml += "</p>";
    } else if (mq.note) {
      qualHtml = '<p class="field-hint" style="margin:0 0 0.75rem;">' + escapeHtml(mq.note) + "</p>";
    }

    var kw = data.keywords || {};
    var tr = kw.toward_editorial_review || [];
    var tk = kw.toward_reliable_style || [];

    function chips(items) {
      if (!items || !items.length) {
        return '<p class="field-hint">None surfaced.</p>';
      }
      return (
        '<ul class="keyword-chip-list">' +
        items
          .map(function (x) {
            var st = x.strength != null ? " · " + String(x.strength) : "";
            return "<li>" + escapeHtml(x.phrase || "") + (st ? '<span style="color:var(--muted);font-size:0.72rem;">' + escapeHtml(st) + "</span>" : "") + "</li>";
          })
          .join("") +
        "</ul>"
      );
    }

    var why = data.why || {};
    var soc = data.societal_concern || {};
    var aspects = soc.risk_aspects || [];

    if (insightPanel) {
      insightPanel.innerHTML =
        "<h3>Classical model insight</h3>" +
        qualHtml +
        '<div class="insight-score">' +
        pct +
        "%</div>" +
        '<p style="margin:0 0 0.35rem;color:var(--muted);font-size:0.85rem;">toward “needs review” vs. this model’s training labels (not a truth score)</p>' +
        '<p class="insight-lead"><strong>' +
        escapeHtml(fr.headline || "") +
        "</strong> " +
        escapeHtml(fr.detail || "") +
        "</p>" +
        "<h3>Why this score</h3>" +
        '<p class="insight-lead">' +
        escapeHtml(why.executive_summary || "") +
        "</p>" +
        '<p class="insight-lead">' +
        escapeHtml(why.longer_story || "") +
        "</p>" +
        "<h3>Triage concern (coarse)</h3>" +
        '<p class="insight-lead"><strong>' +
        escapeHtml(soc.level || "") +
        '</strong> — ' +
        escapeHtml(soc.rationale || "") +
        "</p>" +
        aspects
          .map(function (a) {
            return '<p class="field-hint" style="margin:0.35rem 0;">' + escapeHtml(a) + "</p>";
          })
          .join("") +
        '<h3 style="margin-top:1rem;">Keywords (statistical)</h3><p class="field-hint" style="margin:0 0 0.5rem;">' +
        escapeHtml(kw.method || "") +
        '</p><div class="insight-keywords two-col"><div><strong>Toward review</strong>' +
        chips(tr) +
        '</div><div><strong>Toward reliable-style</strong>' +
        chips(tk) +
        "</div></div>";
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

  function renderResults(data) {
    setAnalyzeStatus("Analysis complete — scores and signals are below.", "ok");
    if (resultsPlaceholder) resultsPlaceholder.hidden = true;
    if (resultsContent) resultsContent.hidden = false;
    if (insightPanel) {
      insightPanel.innerHTML = "";
      insightPanel.hidden = true;
    }

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
    var insightChk = document.getElementById("chk-keyword-insight");
    var useInsight = !!(insightChk && insightChk.checked);

    var payload = {};
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
    if (!useInsight) {
      payload.backend = backend;
      payload.teacher_mode = false;
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
          if (res.data && res.data.fake_risk && res.data.keywords) {
            renderInsightResults(res.data);
          } else {
            renderResults(res.data);
          }
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

  function renderQueueJobs(jobs) {
    var queueList = document.getElementById("queue-list");
    if (!queueList) return;
    if (!jobs || !jobs.length) {
      queueList.innerHTML = '<p class="field-hint">No queued jobs yet for this org.</p>';
      return;
    }
    queueList.innerHTML = jobs
      .map(function (job) {
        var rid = String(job.job_id || "").slice(0, 8);
        var summary = ((job.result || {}).summary || "").trim();
        var topSignals = (job.result && job.result.top_signals) || [];
        return (
          '<article class="queue-item">' +
          '<div class="queue-item-top">' +
          '<span class="queue-id">Job ' +
          escapeHtml(rid) +
          '</span>' +
          '<span class="queue-status ' +
          escapeHtml(job.status || "pending") +
          '">' +
          escapeHtml(job.status || "pending") +
          "</span>" +
          "</div>" +
          (summary
            ? '<p class="queue-summary">' + escapeHtml(summary) + "</p>"
            : "") +
          (topSignals.length
            ? '<p class="field-hint">Top signals: ' + escapeHtml(topSignals.join(", ")) + "</p>"
            : "") +
          (job.error ? '<p class="err" style="margin-top:0.4rem;">' + escapeHtml(job.error) + "</p>" : "") +
          "</article>"
        );
      })
      .join("");
  }

  function queueError(message) {
    var queueErr = document.getElementById("queue-err");
    if (!queueErr) return;
    if (!message) {
      queueErr.hidden = true;
      queueErr.textContent = "";
      return;
    }
    queueErr.hidden = false;
    queueErr.textContent = message;
  }

  async function refreshQueue() {
    var orgInput = document.getElementById("queue-org-id");
    var orgId = (orgInput && orgInput.value && orgInput.value.trim()) || "demo-org";
    try {
      var r = await fetch(apiUrl("/api/v1/jobs?org_id=" + encodeURIComponent(orgId)));
      var body = await r.json();
      if (!r.ok) {
        queueError(formatErrorDetail(body && body.detail, r.status));
        return;
      }
      queueError("");
      renderQueueJobs(body.jobs || []);
    } catch (e) {
      queueError("Could not load queue jobs: " + String((e && e.message) || e));
    }
  }

  async function submitQueueJob() {
    var queueBtn = document.getElementById("queue-submit-btn");
    var lastJob = document.getElementById("queue-last-job");
    var payload = {
      org_id: ((document.getElementById("queue-org-id") || {}).value || "demo-org").trim() || "demo-org",
      title: ((document.getElementById("queue-title") || {}).value || "").trim(),
      body: ((document.getElementById("queue-body") || {}).value || "").trim(),
      url: ((document.getElementById("queue-url") || {}).value || "").trim() || null,
      backend: ((document.getElementById("queue-backend") || {}).value || "classical").trim(),
      teacher_mode: false,
    };
    if (!payload.url && ((payload.title + " " + payload.body).trim().length < 20)) {
      queueError("Enter at least ~20 characters (title + body), or provide a URL.");
      return;
    }
    queueError("");
    if (queueBtn) queueBtn.disabled = true;
    try {
      var res = await fetch(apiUrl("/api/v1/jobs/submit"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      var data = await res.json();
      if (!res.ok) {
        queueError(formatErrorDetail(data && data.detail, res.status));
        return;
      }
      if (lastJob) {
        lastJob.textContent = "Latest job id: " + data.job_id + " (" + data.status + ")";
      }
      await refreshQueue();
    } catch (e2) {
      queueError("Could not submit job: " + String((e2 && e2.message) || e2));
    } finally {
      if (queueBtn) queueBtn.disabled = false;
    }
  }

  function init() {
    loadHealth();
    fillCurlExamples();
    maybeDemoRunFromQuery();
    var queueForm = document.getElementById("queue-form");
    var queueRefresh = document.getElementById("queue-refresh-btn");
    if (queueForm) {
      queueForm.addEventListener("submit", function (e) {
        e.preventDefault();
        submitQueueJob();
      });
    }
    if (queueRefresh) {
      queueRefresh.addEventListener("click", function () {
        refreshQueue();
      });
    }
    refreshQueue();
    setInterval(refreshQueue, 4000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
