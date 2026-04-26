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

async function analyze() {
  $("error").hidden = true;
  $("result").hidden = true;

  const payload = {
    title: $("title").value.trim(),
    body: $("body").value.trim(),
    backend: $("backend").value,
    teacher_mode: $("teacher").checked,
  };

  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    $("error").textContent = err.detail || `Request failed (${res.status})`;
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

  const p = data.score_toward_review_0_to_1;
  $("meter-bar").style.setProperty("--w", `${Math.round(p * 100)}%`);
  $("meter-pct").textContent = `${Math.round(p * 100)}%`;
  $("meter-bar").setAttribute("aria-valuenow", String(Math.round(p * 100)));

  const phrases = $("phrases");
  phrases.innerHTML = "";
  (data.interpretability?.phrases_in_your_text || []).forEach((row) => {
    const li = document.createElement("li");
    const tag = row.effect === "pushes_toward_review" ? "Toward review" : "Toward reliable";
    li.innerHTML = `<span>${escapeHtml(row.phrase)}</span><span class="tag">${tag}</span>`;
    phrases.appendChild(li);
  });

  const tp = $("teacher-panel");
  if (payload.teacher_mode && data.teacher) {
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
