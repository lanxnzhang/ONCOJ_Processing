"use strict";
const $ = id => document.getElementById(id);
let descriptors = [];

async function json(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || data.description || `HTTP ${response.status}`);
  return data;
}
function escapeHtml(value) {
  const div = document.createElement("div"); div.textContent = value ?? ""; return div.innerHTML;
}
async function loadScripts() {
  const scripts = await json("/api/scripts");
  $("script").innerHTML = scripts.map(s => `<option value="${s.id}">${s.name}</option>`).join("");
  await loadSettings();
}
async function loadSettings() {
  descriptors = await json(`/api/scripts/${$("script").value}/settings`);
  const renderSetting = d => {
    const id = `setting-${d.name}`;
    let input;
    if (d.type === "bool") input = `<input id="${id}" type="checkbox" ${d.value ? "checked" : ""}>`;
    else if (d.choices) input = `<select id="${id}">${d.choices.map(v => `<option ${v === d.value ? "selected" : ""}>${v}</option>`).join("")}</select>`;
    else input = `<input id="${id}" type="${d.type === "int" ? "number" : "text"}" value="${escapeHtml(d.value)}">`;
    return `<label class="setting ${d.type === "bool" ? "boolean" : ""}"><span>${d.name.replaceAll("_", " ")} <i class="help" title="${escapeHtml(d.description)}">?</i></span>${input}</label>`;
  };
  const general = descriptors.filter(d => !d.advanced).map(renderSetting).join("");
  const advanced = descriptors.filter(d => d.advanced).map(renderSetting).join("");
  $("settings").innerHTML = `${general}${advanced ? `<details class="advanced"><summary>Advanced settings</summary>${advanced}</details>` : ""}`;
}
function settings() {
  return Object.fromEntries(descriptors.map(d => {
    const el = $(`setting-${d.name}`);
    return [d.name, d.type === "bool" ? el.checked : d.type === "int" ? Number(el.value) : el.value];
  }));
}
function renderLines(lines) {
  const shown = lines.slice(0, 1000);
  $("lines").innerHTML = lines.length ? `${lines.length > shown.length ? `<div class="notice">Showing the first ${shown.length.toLocaleString()} of ${lines.length.toLocaleString()} changes.</div>` : ""}${shown.map(r => `<article>
    <div class="card-head"><strong>${escapeHtml(r.form)}</strong><span class="badge ${r.category}">${r.category}</span>${r.multiple_candidates ? '<span class="badge multiple">multiple candidates</span>' : ""}<code>${escapeHtml(r.new_lemma || "—")}</code></div>
    <p>${escapeHtml(r.file)} · utterance ${escapeHtml(r.utterance)} · line ${r.position}</p>
    <div class="path">${r.path.map(escapeHtml).join(" <b>›</b> ")}</div>
    ${r.multiple_candidates ? `<p class="candidates">Candidates: ${r.candidates.map(escapeHtml).join(", ")}</p>` : ""}
    <details><summary>Before / after</summary><pre>${escapeHtml(r.before)}\n${escapeHtml(r.after)}</pre></details>
  </article>`).join("")}` : '<div class="empty">No processed text lines.</div>';
}
function renderDictionary(entries) {
  $("dictionary").innerHTML = entries.length ? entries.map(e => `<article>
    <div class="card-head"><strong>${escapeHtml(e.id)}</strong><span class="badge ${e.category}">${e.category}</span></div>
    <dl>${e.fields.map(f => `<dt>${escapeHtml(f.tag)}</dt><dd>${f.values.map(escapeHtml).join(" · ")}</dd>`).join("")}</dl>
    <details><summary>Full revised entry</summary><pre>${escapeHtml(e.after || "(deleted)")}</pre></details>
  </article>`).join("") : '<div class="empty">No dictionary changes.</div>';
}
async function run() {
  $("run").disabled = true; $("status").textContent = "Running…";
  try {
    const data = await json("/api/run", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({script: $("script").value, settings: settings()})});
    $("line-count").textContent = data.lines.length; $("dict-count").textContent = data.dictionary.length;
    $("console").textContent = data.console || ""; renderLines(data.lines); renderDictionary(data.dictionary);
    $("files").innerHTML = data.files.length ? data.files.map(f => `<a target="_blank" href="/api/runs/${data.run_id}/files/${encodeURIComponent(f)}">${escapeHtml(f)}</a>`).join("") : '<div class="empty">No output files.</div>';
    $("status").textContent = `Completed run ${data.run_id}. Repository data was not changed.`;
  } catch (error) { $("status").textContent = error.message; }
  finally { $("run").disabled = false; }
}
document.querySelectorAll(".tab").forEach(button => button.onclick = () => {
  document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b === button));
  document.querySelectorAll(".panel").forEach(p => p.classList.toggle("hidden", p.id !== button.dataset.tab));
});
$("script").onchange = loadSettings; $("run").onclick = run; loadScripts();
