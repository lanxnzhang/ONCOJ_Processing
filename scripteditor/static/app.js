"use strict";
const $ = id => document.getElementById(id);
let descriptors = [];
let allLines = [];
let allDictionaryEntries = [];
let currentFilteredLines = [];
let filteredLineCount = 0;
let currentRunId = null;
let editingResultId = null;
let editingEntryOriginalId = null;

async function json(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || data.description || `HTTP ${response.status}`);
  return data;
}
function escapeHtml(value) {
  const div = document.createElement("div"); div.textContent = value ?? ""; return div.innerHTML;
}
function linkLemmaIds(value) {
  return escapeHtml(value).replace(/\b[A-Za-z]+\d{6}[a-z]*\b/g,
    id => `<button type="button" class="lemma-link" data-lemma="${id}">${id}</button>`);
}
async function loadScripts() {
  const [scripts, documents] = await Promise.all([json("/api/scripts"), json("/api/documents")]);
  $("script").innerHTML = scripts.map(s => `<option value="${s.id}">${s.name}</option>`).join("");
  $("process-files").innerHTML = documents.map(group =>
    `<optgroup label="${escapeHtml(group.label)}">${group.files.map(file => `<option selected value="${file.id}">${file.name}</option>`).join("")}</optgroup>`
  ).join("");
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
function selectedProcessFiles() {
  return [...$("process-files").selectedOptions].map(option => option.value);
}
function applyLineFilters() {
  const category = $("filter-category").value;
  const candidates = $("filter-candidates").value;
  const file = $("filter-file").value;
  const limit = Math.max(1, Math.min(10000, Number($("filter-limit").value) || 200));
  const requestedStart = Math.max(1, Number($("filter-start").value) || 1);
  const filtered = allLines.filter(row =>
    (category === "all" || row.category === category) &&
    (file === "all" || row.file === file) &&
    (candidates === "all" || (candidates === "multiple") === Boolean(row.multiple_candidates)) &&
    (!$("hide-confirmed").checked || !row.confirmed)
  );
  currentFilteredLines = filtered;
  filteredLineCount = filtered.length;
  const start = filtered.length ? Math.min(requestedStart, filtered.length) : 1;
  if (start !== requestedStart) $("filter-start").value = start;
  const shown = renderLines(filtered, start - 1, limit);
  const end = shown ? start + shown - 1 : 0;
  $("visible-count").textContent = shown
    ? `${start.toLocaleString()}–${end.toLocaleString()} of ${filtered.length.toLocaleString()} matched`
    : "0 matched";
  updateConfirmationCount();
}
function renderLines(lines, offset = 0, limit = 200) {
  const shown = lines.slice(offset, offset + limit);
  $("lines").innerHTML = lines.length ? `${lines.length > shown.length ? `<div class="notice">Browsing a selected range of ${lines.length.toLocaleString()} matching changes.</div>` : ""}${shown.map(r => `<article class="${r.confirmed ? "result-confirmed" : ""}">
    <div class="card-head"><strong>${escapeHtml(r.form)}</strong><span class="badge ${r.category}">${r.category}</span>${r.multiple_candidates ? '<span class="badge multiple">multiple candidates</span>' : ""}<code>${r.new_lemma ? `<button type="button" class="lemma-link" data-lemma="${escapeHtml(r.new_lemma)}">${escapeHtml(r.new_lemma)}</button>` : "—"}</code></div>
    <p>${escapeHtml(r.file)} · utterance ${escapeHtml(r.utterance)} · line ${r.position}</p>
    <div class="path">${r.path.map(escapeHtml).join(" <b>›</b> ")}</div>
    ${r.multiple_candidates ? `<p class="candidates">Candidates: ${r.candidates.map(id => `<button type="button" class="candidate-link" data-lemma="${escapeHtml(id)}">${escapeHtml(id)}</button>`).join(", ")}</p>` : ""}
    <details><summary>Before / after</summary><pre>${escapeHtml(r.before)}\n${escapeHtml(r.after)}</pre></details>
    <div class="result-review">
      <label class="review-confirm"><input type="checkbox" data-review-confirm="${escapeHtml(r.reviewId)}" ${r.confirmed ? "checked" : ""}> Confirm</label>
      ${r.candidates.length > 1 ? `<label>Chosen lemma<select data-review-choice="${escapeHtml(r.reviewId)}">${r.candidates.map(id => `<option value="${escapeHtml(id)}" ${id === r.selectedLemma ? "selected" : ""}>${escapeHtml(id)}</option>`).join("")}</select></label><button type="button" data-add-entry="${escapeHtml(r.reviewId)}">Add new entry</button>` : ""}
      <span>Selected: <button type="button" class="lemma-link" data-lemma="${escapeHtml(r.selectedLemma)}">${escapeHtml(r.selectedLemma)}</button></span>
    </div>
  </article>`).join("")}` : '<div class="empty">No processed text lines.</div>';
  return shown.length;
}
function renderDictionary(entries) {
  $("dictionary").innerHTML = entries.length ? entries.map(e => `<article>
    <div class="card-head"><strong>${escapeHtml(e.id)}</strong><span class="badge ${e.category}">${e.category}</span>${e.manual ? `<button type="button" data-edit-entry="${escapeHtml(e.id)}">Edit entry</button>` : ""}<label class="dictionary-review-select"><input type="checkbox" data-dictionary-confirm="${escapeHtml(e.id)}" ${e.confirmed ? "checked" : ""}> Include in final output</label></div>
    <dl>${e.fields.map(f => `<dt>${escapeHtml(f.tag)}</dt><dd>${f.values.map(escapeHtml).join(" · ")}</dd>`).join("")}</dl>
    <details><summary>Full revised entry</summary><pre>${escapeHtml(e.after || "(deleted)")}</pre></details>
  </article>`).join("") : '<div class="empty">No dictionary changes.</div>';
}
function updateConfirmationCount() {
  const lines = allLines.filter(row => row.confirmed).length;
  const entries = allDictionaryEntries.filter(entry => entry.confirmed).length;
  $("confirmation-count").textContent = `${lines} line${lines === 1 ? "" : "s"} · ${entries} dictionary entr${entries === 1 ? "y" : "ies"} confirmed`;
}
function reviewScopeRows() {
  const category = $("review-category").value;
  if (category === "visible") return currentFilteredLines;
  if (category === "all") return allLines;
  return allLines.filter(row => row.category === category);
}
function setScopeConfirmation(confirmed) {
  reviewScopeRows().forEach(row => { row.confirmed = confirmed; });
  applyLineFilters();
}
function openDictionary() {
  $("dictionary-drawer").classList.remove("hidden");
  $("dictionary-query").focus();
}
function closeDictionary() {
  $("dictionary-drawer").classList.add("hidden");
}
function dictionarySearchFields() {
  return [...document.querySelectorAll("#dictionary-search-fields input:checked")].map(input => input.value);
}
async function searchDictionary() {
  const query = $("dictionary-query").value.trim();
  const fields = dictionarySearchFields();
  if (!query) { $("dictionary-message").textContent = "Enter a form, lemma ID, or other search term."; return; }
  if (!fields.length) { $("dictionary-message").textContent = "Select at least one search field."; return; }
  const params = new URLSearchParams({q: query});
  fields.forEach(field => params.append("field", field));
  $("dictionary-message").textContent = "Searching…";
  try {
    const matches = await json(`/api/dictionary/search?${params}`);
    $("dictionary-message").textContent = `${matches.length} result${matches.length === 1 ? "" : "s"}${matches.length === 100 ? " (first 100)" : ""}.`;
    $("dictionary-reader-entry").classList.add("hidden");
    $("dictionary-results").innerHTML = matches.map(entry => `<button type="button" class="dictionary-result" data-lemma="${escapeHtml(entry.id)}"><strong>${escapeHtml(entry.id)}</strong> ${escapeHtml(entry.gloss)}<span>${escapeHtml(entry.forms.join(", "))}${entry.pos.length ? ` · ${escapeHtml(entry.pos.join(", "))}` : ""}</span></button>`).join("");
  } catch (error) { $("dictionary-message").textContent = error.message; }
}
async function openDictionaryEntry(entryId) {
  openDictionary();
  $("dictionary-message").textContent = `Opening ${entryId}…`;
  try {
    const entry = await json(`/api/dictionary/${encodeURIComponent(entryId)}`);
    $("dictionary-query").value = entry.id;
    $("dictionary-message").textContent = "Complete dictionary entry";
    $("dictionary-reader-entry").innerHTML = `<h3>${escapeHtml(entry.id)}</h3><dl class="dictionary-fields">${entry.fields.map(field => `<dt>${escapeHtml(field.label)}</dt><dd>${field.values.map(value => `<div class="dictionary-field-value">${linkLemmaIds(value)}</div>`).join("")}</dd>`).join("")}</dl>`;
    $("dictionary-reader-entry").classList.remove("hidden");
  } catch (error) { $("dictionary-message").textContent = error.message; }
}
function entryFieldRow(tag = "", value = "") {
  return `<div class="entry-field-row"><input class="entry-tag" value="${escapeHtml(tag)}" placeholder=".TAG"><input class="entry-value" value="${escapeHtml(value)}" placeholder="Value"><button type="button" class="remove-entry-field">×</button></div>`;
}
async function validateNewEntryId() {
  const id = $("new-entry-id").value.trim();
  const message = $("new-entry-id-message");
  if (!currentRunId || !id) { message.textContent = ""; return false; }
  const pendingConflict = allDictionaryEntries.find(entry => entry.id !== id && entry.id !== editingEntryOriginalId && (entry.id.match(/\d+/) || [])[0] === (id.match(/\d+/) || [])[0]);
  const result = await json(`/api/runs/${currentRunId}/dictionary/check-id/${encodeURIComponent(id)}`);
  const conflict = result.conflict || Boolean(pendingConflict);
  message.classList.toggle("conflict", conflict || !result.valid);
  message.textContent = pendingConflict ? `Numeric portion already used by pending entry ${pendingConflict.id}.` : result.message;
  return result.valid && !conflict;
}
async function openNewEntryEditor(reviewId) {
  if (!currentRunId) return;
  const row = allLines.find(item => item.reviewId === reviewId);
  if (!row) return;
  editingResultId = reviewId;
  editingEntryOriginalId = null;
  openDictionary();
  $("dictionary-reader-entry").classList.add("hidden");
  $("new-entry-editor").classList.remove("hidden");
  const suggestion = await json(`/api/runs/${currentRunId}/dictionary/suggest-id`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({form: row.form})});
  $("new-entry-id").value = suggestion.id;
  $("new-entry-id-message").textContent = "Automatically generated unique ID.";
  $("new-entry-id-message").classList.remove("conflict");
  $("new-entry-fields").innerHTML = [
    [".GLOSS", ""], [".MEANING", ""], [".FORM", suggestion.form],
    [".KANA", suggestion.kana], [".POS", ""],
  ].map(([tag, value]) => entryFieldRow(tag, value)).join("");
}
function editManualEntry(entryId) {
  const entry = allDictionaryEntries.find(item => item.id === entryId && item.manual);
  if (!entry) return;
  editingResultId = null;
  editingEntryOriginalId = entryId;
  openDictionary();
  $("dictionary-reader-entry").classList.add("hidden");
  $("new-entry-editor").classList.remove("hidden");
  $("new-entry-id").value = entry.id;
  $("new-entry-id-message").textContent = "Edit the ID or fields before final output.";
  $("new-entry-id-message").classList.remove("conflict");
  $("new-entry-fields").innerHTML = entry.fields.flatMap(field => field.values.map(value => entryFieldRow(field.tag, value))).join("");
}
function closeNewEntryEditor() {
  editingResultId = null;
  editingEntryOriginalId = null;
  $("new-entry-editor").classList.add("hidden");
}
async function saveNewEntry() {
  if (!await validateNewEntryId()) return;
  const id = $("new-entry-id").value.trim();
  const grouped = new Map();
  document.querySelectorAll("#new-entry-fields .entry-field-row").forEach(row => {
    const tag = row.querySelector(".entry-tag").value.trim().toUpperCase();
    const value = row.querySelector(".entry-value").value;
    if (tag) grouped.set(tag, [...(grouped.get(tag) || []), value]);
  });
  const fields = [...grouped].map(([tag, values]) => ({tag, values}));
  const entry = {id, category: "added", fields, confirmed: true, manual: true};
  if (editingEntryOriginalId && editingEntryOriginalId !== id) {
    allLines.forEach(result => {
      result.candidates = result.candidates.map(candidate => candidate === editingEntryOriginalId ? id : candidate);
      if (result.selectedLemma === editingEntryOriginalId) result.selectedLemma = id;
    });
  }
  allDictionaryEntries = allDictionaryEntries.filter(item => item.id !== id && item.id !== editingEntryOriginalId);
  allDictionaryEntries.push(entry);
  const row = allLines.find(item => item.reviewId === editingResultId);
  if (row) {
    if (!row.candidates.includes(id)) row.candidates.push(id);
    row.selectedLemma = id;
    row.multiple_candidates = true;
  }
  renderDictionary(allDictionaryEntries);
  closeNewEntryEditor();
  applyLineFilters();
}
async function finalizeReview() {
  if (!currentRunId) { $("status").textContent = "Run a processor before creating final output."; return; }
  const lines = allLines.map(row => ({
    file: row.file, utterance: row.utterance, position: row.position,
    before: row.before, lemma: row.selectedLemma, confirmed: row.confirmed,
  }));
  $("finalize-review").disabled = true;
  $("status").textContent = "Creating reviewed final output…";
  try {
    const result = await json(`/api/runs/${currentRunId}/finalize`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({lines, dictionary: allDictionaryEntries})});
    $("files").innerHTML = `<div class="notice">Reviewed output: ${result.confirmed_lines} confirmed lines and ${result.confirmed_dictionary_entries} confirmed dictionary entries.</div>` + result.files.map(file => `<a target="_blank" href="/api/runs/${currentRunId}/final/${encodeURIComponent(file)}">FINAL · ${escapeHtml(file)}</a>`).join("");
    $("status").textContent = "Reviewed final output created. Unconfirmed proposals were excluded.";
  } catch (error) { $("status").textContent = error.message; }
  finally { $("finalize-review").disabled = false; }
}
async function run() {
  const files = selectedProcessFiles();
  if (!files.length) { $("status").textContent = "Select at least one XML file to process."; return; }
  $("run").disabled = true; $("status").textContent = "Running…";
  try {
    const data = await json("/api/run", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({script: $("script").value, settings: settings(), files})});
    $("line-count").textContent = data.lines.length; $("dict-count").textContent = data.dictionary.length;
    currentRunId = data.run_id;
    allLines = data.lines.map((row, index) => ({...row, reviewId: `result-${index}`, confirmed: false, selectedLemma: row.new_lemma, candidates: [...new Set(row.candidates?.length ? row.candidates : [row.new_lemma])]}));
    allDictionaryEntries = data.dictionary.map(entry => ({...entry, confirmed: false, manual: false}));
    const resultFiles = [...new Set(data.lines.map(row => row.file))].sort();
    $("filter-file").innerHTML = '<option value="all">All processed files</option>' + resultFiles.map(name => `<option value="${name}">${name}</option>`).join("");
    $("console").textContent = data.console || ""; applyLineFilters(); renderDictionary(allDictionaryEntries);
    $("files").innerHTML = data.files.length ? data.files.map(f => `<a target="_blank" href="/api/runs/${data.run_id}/files/${encodeURIComponent(f)}">${escapeHtml(f)}</a>`).join("") : '<div class="empty">No output files.</div>';
    $("status").textContent = `Completed run ${data.run_id}. Repository data was not changed.`;
  } catch (error) { $("status").textContent = error.message; }
  finally { $("run").disabled = false; }
}
document.querySelectorAll(".tab").forEach(button => button.onclick = () => {
  document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b === button));
  document.querySelectorAll(".panel").forEach(p => p.classList.toggle("hidden", p.id !== button.dataset.tab));
  $("line-filters").classList.toggle("hidden", button.dataset.tab !== "lines");
});
[$("filter-category"), $("filter-candidates"), $("filter-file")].forEach(control => control.oninput = () => { $("filter-start").value = 1; applyLineFilters(); });
[$("filter-start"), $("filter-limit")].forEach(control => control.oninput = applyLineFilters);
$("range-prev").onclick = () => { const size = Math.max(1, Number($("filter-limit").value) || 200); $("filter-start").value = Math.max(1, Number($("filter-start").value) - size); applyLineFilters(); };
$("range-next").onclick = () => { const size = Math.max(1, Number($("filter-limit").value) || 200); const next = Number($("filter-start").value) + size; if (next <= filteredLineCount) $("filter-start").value = next; applyLineFilters(); };
$("select-all").onclick = () => [...$("process-files").options].forEach(option => option.selected = true);
$("select-none").onclick = () => [...$("process-files").options].forEach(option => option.selected = false);
$("open-dictionary").onclick = openDictionary;
$("close-dictionary").onclick = closeDictionary;
$("dictionary-search-button").onclick = searchDictionary;
$("dictionary-query").onkeydown = event => { if (event.key === "Enter") searchDictionary(); };
document.addEventListener("click", event => {
  const addEntry = event.target.closest("[data-add-entry]");
  if (addEntry) { openNewEntryEditor(addEntry.dataset.addEntry); return; }
  const editEntry = event.target.closest("[data-edit-entry]");
  if (editEntry) { editManualEntry(editEntry.dataset.editEntry); return; }
  const removeField = event.target.closest(".remove-entry-field");
  if (removeField) { removeField.closest(".entry-field-row").remove(); return; }
  const link = event.target.closest("[data-lemma]");
  if (link) openDictionaryEntry(link.dataset.lemma);
});
document.addEventListener("change", event => {
  if (event.target.matches("[data-review-confirm]")) {
    const row = allLines.find(item => item.reviewId === event.target.dataset.reviewConfirm);
    if (row) row.confirmed = event.target.checked;
    applyLineFilters();
  } else if (event.target.matches("[data-review-choice]")) {
    const row = allLines.find(item => item.reviewId === event.target.dataset.reviewChoice);
    if (row) { row.selectedLemma = event.target.value; row.confirmed = false; }
    applyLineFilters();
  } else if (event.target.matches("[data-dictionary-confirm]")) {
    const entry = allDictionaryEntries.find(item => item.id === event.target.dataset.dictionaryConfirm);
    if (entry) entry.confirmed = event.target.checked;
    updateConfirmationCount();
  }
});
$("confirm-category").onclick = () => setScopeConfirmation(true);
$("unconfirm-category").onclick = () => setScopeConfirmation(false);
$("hide-confirmed").onchange = applyLineFilters;
$("finalize-review").onclick = finalizeReview;
$("cancel-new-entry").onclick = closeNewEntryEditor;
$("add-entry-field").onclick = () => $("new-entry-fields").insertAdjacentHTML("beforeend", entryFieldRow());
$("save-new-entry").onclick = saveNewEntry;
$("new-entry-id").oninput = () => { clearTimeout($("new-entry-id")._timer); $("new-entry-id")._timer = setTimeout(validateNewEntryId, 250); };
$("script").onchange = loadSettings; $("run").onclick = run; loadScripts();
