// Vanilla JS frontend for the AI Finance Controller API.
// No build step, no framework — talks to the API on the same origin it's served from.

const API = ""; // same-origin; change to a full URL if the frontend is ever hosted separately

// ---------- small helpers ----------

function $(id) {
  return document.getElementById(id);
}

function showBanner(message, isError = false) {
  const el = $("banner");
  el.textContent = message;
  el.className = "banner " + (isError ? "error" : "ok");
  clearTimeout(showBanner._t);
  showBanner._t = setTimeout(() => (el.className = "banner hidden"), 4000);
}

async function api(path, options = {}) {
  const res = await fetch(API + path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ? JSON.stringify(body.detail) : JSON.stringify(body);
    } catch (_) {
      /* response wasn't JSON */
    }
    throw new Error(`${res.status} ${detail}`);
  }
  const contentType = res.headers.get("content-type") || "";
  return contentType.includes("application/json") ? res.json() : res.text();
}

function shortId(id) {
  return id ? id.slice(0, 8) : "-";
}

function fmtDate(iso) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString();
}

function pill(text) {
  const cls = (text || "").toLowerCase().replace(/[^a-z]/g, "");
  return `<span class="pill ${cls}">${text}</span>`;
}

// ---------- tab navigation ----------

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => activateTab(btn.dataset.tab));
});

function activateTab(name) {
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === "tab-" + name));

  if (name === "dashboard") loadDashboard();
  if (name === "ingestion") loadBatches();
  if (name === "records") loadRecords();
  if (name === "exceptions") loadExceptions();
}

// ---------- dashboard ----------

async function loadDashboard() {
  try {
    const summary = await api("/dashboard/summary");
    $("sum-total").textContent = summary.total_records;
    $("sum-matched").textContent = summary.auto_matched;
    $("sum-rate").textContent = summary.match_rate_pct + "%";
    $("sum-ai").textContent = summary.ai_suggested;
    $("sum-unresolved").textContent = summary.unresolved_exceptions;
    $("sum-review").textContent = summary.needs_review;

    const perf = await api("/dashboard/performance-by-source");
    $("perf-body").innerHTML = perf.length
      ? perf.map((p) => `<tr><td>${p.source_type}</td><td>${p.total}</td><td>${p.matched}</td><td>${p.match_rate_pct}%</td></tr>`).join("")
      : `<tr><td colspan="4" class="empty">No data yet</td></tr>`;

    const reasons = await api("/dashboard/reason-codes");
    $("reason-body").innerHTML = reasons.length
      ? reasons.map((r) => `<tr><td>${r.reason_code}</td><td>${r.count}</td></tr>`).join("")
      : `<tr><td colspan="2" class="empty">No data yet</td></tr>`;
  } catch (err) {
    showBanner("Failed to load dashboard: " + err.message, true);
  }
}

// ---------- ingestion ----------

$("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = $("upload-file").files[0];
  if (!file) return;

  const form = new FormData();
  form.append("source_type", $("upload-source-type").value);
  form.append("file", file);

  try {
    const result = await api("/ingest/upload", { method: "POST", body: form });
    showBanner(`Uploaded ${result.records_ingested} records into batch ${shortId(result.batch.id)}`);
    $("upload-form").reset();
    loadBatches();
  } catch (err) {
    showBanner("Upload failed: " + err.message, true);
  }
});

async function loadBatches() {
  try {
    const batches = await api("/ingest/batches");
    $("batches-body").innerHTML = batches.length
      ? batches.map(batchRow).join("")
      : `<tr><td colspan="6" class="empty">No batches yet</td></tr>`;
  } catch (err) {
    showBanner("Failed to load batches: " + err.message, true);
  }
}

function batchRow(b) {
  return `<tr>
    <td>${b.source_type}</td>
    <td>${b.original_filename || "-"}</td>
    <td>${pill(b.status)}</td>
    <td>${b.total_records}</td>
    <td>${fmtDate(b.created_at)}</td>
    <td>
      <button class="btn small" onclick="runNormalize('${b.id}')">Normalize</button>
      <button class="btn small" onclick="runMatch('${b.id}')">Match</button>
      <button class="btn small" onclick="runAiResolve('${b.id}')">AI Resolve</button>
    </td>
  </tr>`;
}

async function runNormalize(batchId) {
  try {
    const r = await api(`/normalize/run/${batchId}`, { method: "POST" });
    showBanner(`Normalization queued (task ${shortId(r.task_id)})`);
  } catch (err) {
    showBanner("Normalize failed: " + err.message, true);
  }
}

async function runMatch(batchId) {
  try {
    const r = await api(`/match/run/${batchId}`, { method: "POST" });
    showBanner("Matching complete: " + JSON.stringify(r.counts));
    loadBatches();
  } catch (err) {
    showBanner("Matching failed: " + err.message, true);
  }
}

async function runAiResolve(batchId) {
  try {
    const r = await api(`/ai/resolve/${batchId}`, { method: "POST" });
    showBanner(`AI resolution queued (task ${shortId(r.task_id)})`);
  } catch (err) {
    showBanner("AI resolve failed: " + err.message, true);
  }
}

// ---------- records ----------

async function loadRecords() {
  const params = new URLSearchParams({ limit: "100" });
  const source = $("rec-filter-source").value;
  const status = $("rec-filter-status").value;
  if (source) params.set("source_type", source);
  if (status) params.set("status", status);

  try {
    const records = await api("/records?" + params.toString());
    $("records-body").innerHTML = records.length
      ? records.map(recordRow).join("")
      : `<tr><td colspan="7" class="empty">No records match these filters</td></tr>`;
  } catch (err) {
    showBanner("Failed to load records: " + err.message, true);
  }
}

function recordRow(r) {
  return `<tr>
    <td>${r.source_type}</td>
    <td>${r.txn_id || "-"}</td>
    <td>${r.reference_no || "-"}</td>
    <td>${r.amount} ${r.currency}</td>
    <td>${r.txn_date}</td>
    <td>${r.narration_clean || r.narration_raw || "-"}</td>
    <td>${pill(r.status)}</td>
  </tr>`;
}

// ---------- exceptions ----------

async function loadExceptions() {
  const params = new URLSearchParams({ limit: "100" });
  const status = $("exc-filter-status").value;
  if (status) params.set("status", status);

  try {
    const exceptions = await api("/exceptions?" + params.toString());
    $("exceptions-body").innerHTML = exceptions.length
      ? exceptions.map(exceptionRow).join("")
      : `<tr><td colspan="5" class="empty">No exceptions match these filters</td></tr>`;
  } catch (err) {
    showBanner("Failed to load exceptions: " + err.message, true);
  }
}

function exceptionRow(e) {
  const canReview = e.status === "open";
  const hasSuggestion = !!e.ai_suggested_match_id;
  return `<tr>
    <td>${e.reason_code}</td>
    <td>${e.confidence_tier ? pill(e.confidence_tier) : "-"}</td>
    <td>${e.explanation || "-"}</td>
    <td>${pill(e.status)}</td>
    <td>
      ${canReview && hasSuggestion ? `<button class="btn small" onclick="approveException('${e.id}')">Approve</button>` : ""}
      ${canReview ? `<button class="btn small danger" onclick="rejectException('${e.id}')">Reject</button>` : ""}
      ${canReview ? `<button class="btn small" onclick="commentException('${e.id}')">Comment</button>` : ""}
    </td>
  </tr>`;
}

function reviewerId() {
  return $("exc-reviewer-id").value || null;
}

async function approveException(id) {
  try {
    await api(`/exceptions/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewer_id: reviewerId() }),
    });
    showBanner("Exception approved");
    loadExceptions();
  } catch (err) {
    showBanner("Approve failed: " + err.message, true);
  }
}

async function rejectException(id) {
  try {
    await api(`/exceptions/${id}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewer_id: reviewerId() }),
    });
    showBanner("Exception rejected");
    loadExceptions();
  } catch (err) {
    showBanner("Reject failed: " + err.message, true);
  }
}

async function commentException(id) {
  const comment = window.prompt("Comment:");
  if (!comment) return;
  try {
    await api(`/exceptions/${id}/comment`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewer_id: reviewerId(), comment }),
    });
    showBanner("Comment added");
    loadExceptions();
  } catch (err) {
    showBanner("Comment failed: " + err.message, true);
  }
}

// ---------- reports ----------

function downloadReport() {
  const report = $("report-type").value;
  const format = $("report-format").value;
  window.location.href = `/reports/export?report=${report}&format=${format}`;
}

async function previewReport() {
  const report = $("report-type").value;
  try {
    const rows = await api(`/reports/${report}`);
    $("report-preview").textContent = JSON.stringify(rows, null, 2);
  } catch (err) {
    showBanner("Preview failed: " + err.message, true);
  }
}

// ---------- dev tools ----------

async function generateSyntheticData() {
  const total = $("dev-total").value || 100;
  const seed = $("dev-seed").value;
  const params = new URLSearchParams({ total_records: total });
  if (seed) params.set("seed", seed);

  try {
    const result = await api(`/dev/synthetic-data?${params.toString()}`, { method: "POST" });
    $("dev-result").textContent = JSON.stringify(result, null, 2);
    showBanner("Synthetic data generated");
    loadBatches();
  } catch (err) {
    showBanner("Generation failed: " + err.message, true);
  }
}

// ---------- initial load ----------

loadDashboard();
