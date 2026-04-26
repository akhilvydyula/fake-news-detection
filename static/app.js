const $ = (id) => document.getElementById(id);

function verdictClass(verdict) {
  if (verdict === "likely_reliable") return "ok";
  if (verdict === "uncertain") return "mid";
  return "warn";
}

function badgeLabel(verdict) {
  if (verdict === "likely_reliable") return "Lower priority";
  if (verdict === "uncertain") return "Medium priority";
  return "Higher priority review";
}

function inputMode() {
  const r = document.querySelector('input[name="inputmode"]:checked');
  return r ? r.value : "paste";
}

function syncInputModeUi() {
  const url = inputMode() === "url";
  $("url-row").hidden = !url;
  document.querySelectorAll(".paste-only").forEach((el) => {
    el.style.display = url ? "none" : "";
  });
}

document.querySelectorAll('input[name="inputmode"]').forEach((r) => {
  r.addEventListener("change", syncInputModeUi);
});
syncInputModeUi();

async function analyze() {
  $("error").hidden = true;
  $("result").hidden = true;

  const backend = $("backend").value;
  const teacher_mode = $("teacher").checked;
  let res;

  if (inputMode() === "url") {
    const url = $("url").value.trim();
    if (!url) {
      $("error").textContent = "Enter an https URL or switch to Paste text.";
      $("error").hidden = false;
      return;
    }
    res = await fetch("/api/analyze-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, backend, teacher_mode }),
    });
  } else {
    const payload = {
      title: $("title").value.trim(),
      body: $("body").value.trim(),
      backend,
      teacher_mode,
    };
    res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const d = err.detail;
    $("error").textContent = typeof d === "string" ? d : JSON.stringify(d || err) || `Request failed (${res.status})`;
    $("error").hidden = false;
    return;
  }

  const data = await res.json();
  const u = data.user_summary;
  const badge = $("verdict-badge");
  badge.textContent = badgeLabel(u.verdict);
  badge.className = "badge " + verdictClass(u.verdict);

  $("headline").textContent = u.headline;
  $("detail").textContent = u.detail;
  $("scale-note").textContent = u.simple_scale;

  $("executive-why").textContent = data.executive_why || "";

  const p = data.score_toward_review_0_to_1;
  $("meter-bar").style.setProperty("--w", `${Math.round(p * 100)}%`);
  $("meter-pct").textContent = `${Math.round(p * 100)}%`;
  $("meter-bar").setAttribute("aria-valuenow", String(Math.round(p * 100)));

  const phrases = $("phrases");
  phrases.innerHTML = "";
  (data.interpretability?.phrases_in_your_text || []).forEach((row) => {
    const li = document.createElement("li");
    const tag = row.effect === "pushes_toward_review" ? "Toward review" : "Toward reliable";
    li.innerHTML = `<span>${escapeHtml(String(row.phrase))}</span><span class="tag">${tag}</span>`;
    phrases.appendChild(li);
  });

  const fp = $("framing-panel");
  const fl = $("framing-list");
  if (data.product_framing) {
    fp.hidden = false;
    fl.innerHTML = "";
    Object.values(data.product_framing).forEach((txt) => {
      const li = document.createElement("li");
      li.textContent = txt.replace(/\*\*/g, "");
      fl.appendChild(li);
    });
  } else {
    fp.hidden = true;
  }

  const tp = $("teacher-panel");
  if (teacher_mode && data.teacher) {
    tp.hidden = false;
    $("teacher-note").textContent = data.teacher.note || "";
    $("teacher-json").textContent = JSON.stringify(data.teacher, null, 2);
  } else {
    tp.hidden = true;
  }

  $("result").hidden = false;
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

$("analyze").addEventListener("click", analyze);
