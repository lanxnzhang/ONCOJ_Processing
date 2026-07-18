import {api} from "./api.js";
import {state, findNode, selectedNode} from "./state.js";
import {$, escapeHtml, setMessage} from "./utils.js";

let mutateCallback = null;
let openLocationCallback = null;
let pendingLemmaPath = null;
let editingDictionaryId = null;

function activateTool(name) {
  document.querySelectorAll("[data-tool]").forEach(button => button.classList.toggle("active", button.dataset.tool === name));
  document.querySelectorAll(".tool-view").forEach(view => view.classList.toggle("hidden", view.id !== `tool-${name}`));
}

function attributeRow(name = "", value = "") {
  return `<div class="attribute-row"><input class="attribute-name" placeholder="attribute" value="${escapeHtml(name)}"><input class="attribute-value" placeholder="value" value="${escapeHtml(value)}"><button type="button" data-remove-row>×</button></div>`;
}

function bindRemoveRows(container) {
  container.querySelectorAll("[data-remove-row]").forEach(button => button.onclick = () => button.parentElement.remove());
}

export function renderInspector() {
  const node = selectedNode();
  $("inspector-empty").classList.toggle("hidden", Boolean(node));
  $("inspector-form").classList.toggle("hidden", !node);
  if (!node) return;
  $("node-tag").value = node.tag;
  $("node-text").value = node.text || "";
  $("attribute-rows").innerHTML = Object.entries(node.attributes).map(([name, value]) => attributeRow(name, value)).join("");
  bindRemoveRows($("attribute-rows"));
  $("find-lemma").disabled = node.layer !== "word";
}

export async function renderProblems() {
  const documentProblems = state.current?.problems || [];
  let dictionaryProblems = [];
  try { dictionaryProblems = await api.dictionaryProblems(); } catch (_) { /* shown by document checks */ }
  const problems = [
    ...documentProblems.map(item => ({...item, source: "document"})),
    ...dictionaryProblems.map(item => ({...item, source: "dictionary"})),
  ];
  $("problem-count").textContent = problems.length;
  $("problems").innerHTML = problems.length ? problems.map((item, index) => `
    <button class="problem ${item.severity}" data-problem-index="${index}"><span class="problem-dot"></span><span><strong>${escapeHtml(item.message)}</strong><span>${escapeHtml(item.code)} · ${escapeHtml(item.source)}</span></span></button>
  `).join("") : '<div class="quiet">No problems detected.</div>';
  $("problems").querySelectorAll("[data-problem-index]").forEach(button => {
    button.onclick = () => {
      const item = problems[Number(button.dataset.problemIndex)];
      if (item.source === "document") document.dispatchEvent(new CustomEvent("node-select", {detail: item.path}));
      else activateTool("dictionary");
    };
  });
}

function criterionRow() {
  return `<div class="criterion-row">
    <select class="criterion-mode"><option value="include">Include</option><option value="exclude">Exclude</option></select>
    <select class="criterion-field"><option value="any">Any</option><option value="tag">Tag</option><option value="form">Form</option><option value="lemma">Lemma</option><option value="phon">Phon</option><option value="attributes">Attributes</option><option value="sentence">Sentence</option></select>
    <select class="criterion-operator"><option value="contains">Contains</option><option value="equals">Equals</option><option value="starts">Starts with</option><option value="exists">Exists</option></select>
    <input class="criterion-value" placeholder="value"><button type="button" data-remove-row>×</button>
  </div>`;
}

function dictionaryFieldRow(tag = "", value = "") {
  return `<div class="dictionary-field-row"><input class="dictionary-tag" value="${escapeHtml(tag)}" placeholder=".TAG"><input class="dictionary-value" value="${escapeHtml(value)}" placeholder="Value"><button type="button" data-remove-row>×</button></div>`;
}

function showDictionaryEntry(entry, isNew = false) {
  editingDictionaryId = isNew ? null : entry.id;
  $("dictionary-id").value = entry.id;
  $("dictionary-id").disabled = !isNew;
  $("dictionary-delete").classList.toggle("hidden", isNew);
  $("dictionary-fields").innerHTML = entry.fields.flatMap(field => field.values.map(value => dictionaryFieldRow(field.tag, value))).join("");
  bindRemoveRows($("dictionary-fields"));
  $("dictionary-editor").classList.remove("hidden");
}

async function openDictionaryEntry(id) {
  activateTool("dictionary");
  showDictionaryEntry(await api.dictionaryEntry(id));
}

async function searchDictionary() {
  const query = $("dictionary-query").value.trim();
  if (!query) return;
  const results = await api.dictionarySearch(query);
  $("dictionary-results").innerHTML = results.map(entry => `<button class="result-item" data-entry-id="${escapeHtml(entry.id)}"><strong>${escapeHtml(entry.id)} · ${escapeHtml(entry.gloss)}</strong><span>${escapeHtml(entry.forms.join(", "))} · ${escapeHtml(entry.pos.join(", "))}</span></button>`).join("") || '<div class="quiet">No dictionary matches.</div>';
  $("dictionary-results").querySelectorAll("[data-entry-id]").forEach(button => button.onclick = () => openDictionaryEntry(button.dataset.entryId));
}

function dictionaryPayload() {
  const grouped = new Map();
  $("dictionary-fields").querySelectorAll(".dictionary-field-row").forEach(row => {
    let tag = row.querySelector(".dictionary-tag").value.trim().toUpperCase();
    if (!tag.startsWith(".")) tag = "." + tag;
    if (tag !== ".") grouped.set(tag, [...(grouped.get(tag) || []), row.querySelector(".dictionary-value").value]);
  });
  return {id: $("dictionary-id").value.trim(), fields: [...grouped].map(([tag, values]) => ({tag, values}))};
}

async function saveDictionaryEntry(event) {
  event.preventDefault();
  const payload = dictionaryPayload();
  try {
    const entry = editingDictionaryId
      ? await api.updateDictionaryEntry(editingDictionaryId, payload)
      : await api.createDictionaryEntry(payload);
    showDictionaryEntry(entry);
    setMessage(`Dictionary entry ${entry.id} saved in compreditor workspace.`);
    if (pendingLemmaPath) {
      const node = findNode(pendingLemmaPath);
      await mutateCallback({operation: "update", path: pendingLemmaPath, tag: node.tag, attributes: {...node.attributes, lemma: entry.id}, text: node.text});
      pendingLemmaPath = null;
    }
    await renderProblems();
  } catch (error) { setMessage(error.message, true); }
}

async function runSearch(event) {
  event.preventDefault();
  const criteria = [...$("search-criteria").querySelectorAll(".criterion-row")].map(row => ({
    exclude: row.querySelector(".criterion-mode").value === "exclude",
    field: row.querySelector(".criterion-field").value,
    operator: row.querySelector(".criterion-operator").value,
    value: row.querySelector(".criterion-value").value,
  }));
  const payload = {
    query: $("search-query").value,
    scope: $("search-scope").value,
    logic: $("search-logic").value,
    structure: $("search-structure").value,
    criteria,
    current: state.current ? {collection: state.current.collection, name: state.current.name} : null,
  };
  $("search-results").innerHTML = '<div class="quiet">Searching…</div>';
  try {
    const results = await api.search(payload);
    $("search-results").innerHTML = results.map((item, index) => item.kind === "dictionary"
      ? `<button class="result-item" data-search-index="${index}"><strong>${escapeHtml(item.id)} · ${escapeHtml(item.gloss)}</strong><span>Dictionary · ${escapeHtml(item.forms.join(", "))}</span></button>`
      : `<button class="result-item" data-search-index="${index}"><strong>${escapeHtml(item.label)} · &lt;${escapeHtml(item.tag)}&gt;</strong><span>${escapeHtml(item.collection)}/${escapeHtml(item.file)} · ${escapeHtml(item.sentence_id)}</span></button>`
    ).join("") || '<div class="quiet">No matches.</div>';
    $("search-results").querySelectorAll("[data-search-index]").forEach(button => button.onclick = () => {
      const item = results[Number(button.dataset.searchIndex)];
      if (item.kind === "dictionary") openDictionaryEntry(item.id);
      else openLocationCallback(item.collection, item.file, item.path);
    });
  } catch (error) { $("search-results").innerHTML = `<div class="quiet">${escapeHtml(error.message)}</div>`; }
}

export async function openLemmaDialog() {
  const node = selectedNode();
  if (!node || node.layer !== "word") return;
  const form = node.attributes.form || "";
  $("lemma-form-label").textContent = `Dictionary candidates for “${form}”`;
  $("lemma-candidates").innerHTML = '<div class="quiet">Searching dictionary…</div>';
  $("lemma-dialog").showModal();
  const candidates = await api.dictionaryCandidates(form);
  $("lemma-candidates").innerHTML = candidates.map(entry => `<button class="result-item" data-lemma-id="${escapeHtml(entry.id)}"><strong>${escapeHtml(entry.id)} · ${escapeHtml(entry.gloss)}</strong><span>${escapeHtml(entry.pos.join(", "))}</span></button>`).join("") || '<div class="quiet">No existing dictionary candidate.</div>';
  $("lemma-candidates").querySelectorAll("[data-lemma-id]").forEach(button => button.onclick = async () => {
    await mutateCallback({operation: "update", path: node.path, tag: node.tag, attributes: {...node.attributes, lemma: button.dataset.lemmaId}, text: node.text});
    $("lemma-dialog").close();
  });
}

export function setupTools({mutate, openLocation}) {
  mutateCallback = mutate;
  openLocationCallback = openLocation;
  document.querySelectorAll("[data-tool]").forEach(button => button.onclick = () => activateTool(button.dataset.tool));
  $("add-attribute").onclick = () => { $("attribute-rows").insertAdjacentHTML("beforeend", attributeRow()); bindRemoveRows($("attribute-rows")); };
  $("inspector-form").onsubmit = async event => {
    event.preventDefault();
    const node = selectedNode();
    const attributes = Object.fromEntries([...$("attribute-rows").querySelectorAll(".attribute-row")].map(row => [row.querySelector(".attribute-name").value.trim(), row.querySelector(".attribute-value").value]).filter(([name]) => name));
    await mutateCallback({operation: "update", path: node.path, tag: $("node-tag").value, attributes, text: $("node-text").value});
  };

  $("search-form").onsubmit = runSearch;
  $("add-criterion").onclick = () => { $("search-criteria").insertAdjacentHTML("beforeend", criterionRow()); bindRemoveRows($("search-criteria")); };
  $("dictionary-search").onclick = searchDictionary;
  $("dictionary-query").onkeydown = event => { if (event.key === "Enter") { event.preventDefault(); searchDictionary(); } };
  $("dictionary-new").onclick = async () => showDictionaryEntry(await api.suggestLemma("", 1), true);
  $("dictionary-add-field").onclick = () => { $("dictionary-fields").insertAdjacentHTML("beforeend", dictionaryFieldRow()); bindRemoveRows($("dictionary-fields")); };
  $("dictionary-editor").onsubmit = saveDictionaryEntry;
  $("dictionary-delete").onclick = async () => {
    if (!editingDictionaryId || !confirm(`Delete ${editingDictionaryId} from the workspace dictionary?`)) return;
    await api.deleteDictionaryEntry(editingDictionaryId);
    $("dictionary-editor").classList.add("hidden");
    setMessage(`Dictionary entry ${editingDictionaryId} deleted from workspace.`);
    editingDictionaryId = null;
    await renderProblems();
  };
  $("close-lemma").onclick = () => $("lemma-dialog").close();
  $("create-lemma").onclick = async () => {
    const node = selectedNode();
    const draft = await api.suggestLemma(node.attributes.form || "", Number($("lemma-start").value) || 1);
    pendingLemmaPath = node.path;
    showDictionaryEntry(draft, true);
    activateTool("dictionary");
    $("lemma-dialog").close();
  };
}

