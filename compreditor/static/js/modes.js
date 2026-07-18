import {state, findNode, sentenceForPath, walk} from "./state.js";
import {$, attributesText, escapeHtml} from "./utils.js";

let saveTableCallback = null;

function textNodes(node, baseDepth = 0) {
  const depth = node.path ? node.path.split(".").length - baseDepth : 0;
  const attrs = attributesText(node.attributes);
  const preview = node.tag === "comment" ? node.attributes.raw : node.attributes.form || node.text || "";
  return `<div class="text-node ${node.path === state.selectedPath ? "selected" : ""}" data-node-path="${node.path}">
    <span class="indent" style="width:${Math.max(0, depth) * 17}px"></span>
    <code>&lt;${escapeHtml(node.tag)}${attrs ? ` ${escapeHtml(attrs)}` : ""}&gt;</code>
    <span class="node-preview">${escapeHtml(preview)}</span>
  </div>${node.children.map(child => textNodes(child, baseDepth)).join("")}`;
}

function treeNode(node) {
  const form = node.attributes.form || "";
  const details = [node.attributes.phon, node.attributes.lemma].filter(Boolean).join(" · ");
  return `<li><button class="tree-node ${node.path === state.selectedPath ? "selected" : ""}" data-node-path="${node.path}">
    <strong>${escapeHtml(node.tag)}</strong>${form ? `<span class="tree-form">${escapeHtml(form)}</span>` : ""}${details ? `<span class="tree-attrs">${escapeHtml(details)}</span>` : ""}
  </button>${node.children.length ? `<ul>${node.children.filter(child => child.tag !== "comment").map(treeNode).join("")}</ul>` : ""}</li>`;
}

function focusedSentence() {
  const selected = sentenceForPath();
  if (selected) return selected;
  return state.current?.tree.children.find(child => child.tag === "block") || state.current?.tree;
}

function bindSelection(container) {
  container.querySelectorAll("[data-node-path]").forEach(element => {
    element.onclick = () => document.dispatchEvent(new CustomEvent("node-select", {detail: element.dataset.nodePath}));
  });
}

function renderText() {
  const root = state.layer === "sentence" || state.layer === "word" ? focusedSentence() : state.current.tree;
  const baseDepth = root.path ? root.path.split(".").length : 0;
  $("mode-text").innerHTML = textNodes(root, baseDepth);
  bindSelection($("mode-text"));
}

function renderTable() {
  const sentence = state.layer === "sentence" || state.layer === "word" ? focusedSentence() : null;
  const nodes = [];
  walk(sentence || state.current.tree, node => nodes.push(node));
  $("mode-table").innerHTML = `<table class="word-table"><thead><tr><th>Path</th><th>Layer</th><th>Tag</th><th>Form</th><th>Phon</th><th>Lemma</th><th>Text / other attributes</th></tr></thead><tbody>${nodes.map(node => `
    <tr class="${node.path === state.selectedPath ? "selected" : ""}" data-node-path="${node.path}">
      <td><code>${escapeHtml(node.path || "root")}</code></td>
      <td>${escapeHtml(node.layer)}</td>
      <td><input data-field="tag" value="${escapeHtml(node.tag)}"></td>
      <td><input data-field="form" value="${escapeHtml(node.attributes.form || "")}"></td>
      <td><input data-field="phon" value="${escapeHtml(node.attributes.phon || "")}"></td>
      <td><input data-field="lemma" value="${escapeHtml(node.attributes.lemma || "")}"></td>
      <td><input data-field="text" value="${escapeHtml(node.text || "")}" placeholder="${escapeHtml(Object.entries(node.attributes).filter(([key]) => !["form", "phon", "lemma"].includes(key)).map(([key, value]) => `${key}=${value}`).join(" · "))}"></td>
    </tr>`).join("")}</tbody></table><button id="save-table" class="primary table-save">Save table changes</button>`;
  $("mode-table").querySelectorAll("tr[data-node-path]").forEach(row => {
    row.onclick = event => {
      if (event.target.matches("input")) return;
      document.dispatchEvent(new CustomEvent("node-select", {detail: row.dataset.nodePath}));
    };
  });
  $("save-table").onclick = () => {
    const rows = [...$("mode-table").querySelectorAll("tr[data-node-path]")].map(row => ({
      path: row.dataset.nodePath,
      ...Object.fromEntries([...row.querySelectorAll("input")].map(input => [input.dataset.field, input.value])),
    }));
    saveTableCallback(rows);
  };
}

function renderTree() {
  const root = focusedSentence();
  $("mode-tree").innerHTML = `<ul class="syntax-tree">${treeNode(root)}</ul>`;
  bindSelection($("mode-tree"));
}

export function renderContext() {
  if (!state.current) return;
  const selected = findNode(state.selectedPath);
  const sentence = sentenceForPath();
  const context = $("context-strip");
  if (!sentence) {
    context.classList.add("hidden");
    return;
  }
  const words = state.current.words.filter(word => word.path.startsWith(sentence.path + "."));
  context.innerHTML = `<small>${escapeHtml(sentence.attributes.id || "Sentence")} · ${escapeHtml(state.current.name)}</small>${words.map(word => word.path === selected?.path ? `<mark>${escapeHtml(word.form)}</mark>` : escapeHtml(word.form)).join(" ")}`;
  context.classList.remove("hidden");
}

export function renderModes() {
  ["text", "table", "tree"].forEach(mode => $("mode-" + mode).classList.toggle("hidden", mode !== state.mode || !state.current));
  $("editor-empty").classList.toggle("hidden", Boolean(state.current));
  if (!state.current) return;
  if (state.mode === "text") renderText();
  else if (state.mode === "table") renderTable();
  else renderTree();
  renderContext();
}

export function setupModes(saveTable) {
  saveTableCallback = saveTable;
  document.querySelectorAll("[data-mode]").forEach(button => {
    button.onclick = () => {
      state.mode = button.dataset.mode;
      document.querySelectorAll("[data-mode]").forEach(item => item.classList.toggle("active", item === button));
      renderModes();
    };
  });
}
