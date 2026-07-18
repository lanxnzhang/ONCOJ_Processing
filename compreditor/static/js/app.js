import {api} from "./api.js";
import {loadOutline, renderOutline, setupOutline} from "./outline.js";
import {renderContext, renderModes, setupModes} from "./modes.js";
import {cloneNodeForPaste, findNode, selectedNode, sentenceForPath, state} from "./state.js";
import {openLemmaDialog, renderInspector, renderProblems, setupTools} from "./tools.js";
import {$, setMessage} from "./utils.js";

function updateHeader() {
  const current = state.current;
  $("editor-title").textContent = current ? current.name.replace(".xml", "") : "No text selected";
  $("breadcrumbs").textContent = current ? `COJ / ${current.collection} / ${current.name} / ${state.layer}` : "COJ / Select a text";
  $("source-badge").textContent = current?.source || "read only";
  $("source-badge").classList.toggle("workspace", current?.source === "workspace");
  $("delete-document").classList.toggle("hidden", !current);
}

async function refreshOutline() {
  await loadOutline(openDocument);
}

function acceptDocument(payload, path = null) {
  state.current = payload;
  const requested = path ?? payload.selected_path ?? state.selectedPath;
  state.selectedPath = findNode(requested, payload.tree) ? requested : "";
  updateHeader();
  renderModes();
  renderInspector();
  renderProblems();
  renderOutline();
}

async function openDocument(collection, name, path = "") {
  try {
    setMessage(`Opening ${name}…`);
    const payload = await api.document(collection, name);
    state.selectedPath = path;
    acceptDocument(payload, path);
    setMessage(payload.source === "workspace" ? "Editing isolated workspace copy." : "Viewing canonical source; the first edit creates a workspace copy.");
  } catch (error) { setMessage(error.message, true); }
}

async function openLocation(collection, name, path) {
  await openDocument(collection, name, path);
  selectNode(path);
}

function inferLayer(node) {
  if (!node || node.layer === "document") return "text";
  if (node.layer === "sentence") return "sentence";
  if (node.layer === "word") return "word";
  return state.layer;
}

function selectNode(path) {
  if (!state.current || !findNode(path)) return;
  state.selectedPath = path;
  state.layer = inferLayer(selectedNode());
  document.querySelectorAll("[data-layer]").forEach(button => button.classList.toggle("active", button.dataset.layer === state.layer));
  updateHeader();
  renderModes();
  renderInspector();
}

async function mutate(body) {
  if (!state.current) return;
  try {
    setMessage("Saving edit to compreditor workspace…");
    const payload = await api.editNode(state.current.collection, state.current.name, body);
    acceptDocument(payload, payload.selected_path);
    await refreshOutline();
    setMessage("Saved in compreditor/workspace. Canonical data was not changed.");
  } catch (error) { setMessage(error.message, true); }
}

async function saveTable(rows) {
  if (!state.current) return;
  try {
    setMessage("Saving table changes…");
    const payload = await api.editWords(state.current.collection, state.current.name, rows);
    acceptDocument(payload);
    await refreshOutline();
    setMessage("Table changes saved in compreditor/workspace.");
  } catch (error) { setMessage(error.message, true); }
}

async function nodeAction(operation) {
  const node = selectedNode();
  if (!node || !state.current) return;
  if (operation === "copy") {
    state.clipboard = cloneNodeForPaste(node);
    setMessage(`Copied <${node.tag}> branch.`);
    return;
  }
  if (operation === "paste") {
    if (!state.clipboard) { setMessage("Copy an item before pasting.", true); return; }
    await mutate({operation: "paste", path: node.path, node: state.clipboard});
    return;
  }
  if (operation === "add") {
    const tag = prompt("Tag for the new child or branch:", node.tag === "document" ? "block" : "N");
    if (tag) await mutate({operation: "add", path: node.path, tag, attributes: tag === "block" ? {id: "", header: ""} : {}});
    return;
  }
  if (operation === "delete") {
    if (!node.path) { setMessage("Delete the text with the Delete text button.", true); return; }
    if (confirm(`Delete <${node.tag}> and all of its children?`)) await mutate({operation: "delete", path: node.path});
    return;
  }
  if (operation === "reparent") {
    if (!node.path) { setMessage("The document root cannot be moved.", true); return; }
    const targetPath = prompt("Path of the new parent node (shown in Inspector/search navigation):", "");
    if (targetPath !== null) await mutate({operation: "reparent", path: node.path, target_path: targetPath.trim()});
    return;
  }
  if (operation === "up" || operation === "down") await mutate({operation: "move", path: node.path, direction: operation});
}

function focusLayer(layer) {
  if (!state.current) return;
  state.layer = layer;
  if (layer === "document" || layer === "text") state.selectedPath = "";
  if (layer === "sentence") {
    state.selectedPath = sentenceForPath()?.path || state.current.sentences[0]?.path || "";
  }
  if (layer === "word") {
    const selected = selectedNode();
    if (selected?.layer !== "word") state.selectedPath = state.current.words[0]?.path || "";
  }
  document.querySelectorAll("[data-layer]").forEach(button => button.classList.toggle("active", button.dataset.layer === layer));
  updateHeader();
  renderModes();
  renderInspector();
}

function setupLayout() {
  $("toggle-left").onclick = () => $("app-shell").classList.toggle("left-collapsed");
  $("toggle-right").onclick = () => $("app-shell").classList.toggle("right-collapsed");
  document.querySelectorAll("[data-layer]").forEach(button => button.onclick = () => focusLayer(button.dataset.layer));
  document.querySelectorAll("[data-operation]").forEach(button => button.onclick = () => nodeAction(button.dataset.operation));
  document.addEventListener("node-select", event => selectNode(event.detail));
  $("find-lemma").onclick = openLemmaDialog;
}

function setupDocuments() {
  $("new-document").onclick = () => $("new-document-dialog").showModal();
  $("new-document-form").onsubmit = async event => {
    event.preventDefault();
    try {
      const payload = await api.createDocument({collection: $("new-document-collection").value, name: $("new-document-name").value});
      $("new-document-dialog").close();
      acceptDocument(payload);
      await refreshOutline();
      setMessage("New text created in compreditor/workspace.");
    } catch (error) { setMessage(error.message, true); }
  };
  $("delete-document").onclick = async () => {
    if (!state.current || !confirm(`Delete ${state.current.name} from the comprehensive editor workspace?`)) return;
    try {
      await api.deleteDocument(state.current.collection, state.current.name);
      state.current = null;
      state.selectedPath = "";
      updateHeader();
      renderModes();
      renderInspector();
      await refreshOutline();
      setMessage("Text hidden by a workspace deletion marker. Canonical data was not changed.");
    } catch (error) { setMessage(error.message, true); }
  };
}

async function init() {
  setupLayout();
  setupDocuments();
  setupOutline();
  setupModes(saveTable);
  setupTools({mutate, openLocation});
  await refreshOutline();
  await renderProblems();
}

init().catch(error => setMessage(error.message, true));
