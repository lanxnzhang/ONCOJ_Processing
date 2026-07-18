import {api} from "./api.js";
import {state} from "./state.js";
import {$, escapeHtml} from "./utils.js";

let openDocumentCallback = null;

function activeDocumentExtras(document) {
  if (!state.current || state.current.name !== document.name) return "";
  const sentenceItems = state.current.sentences.map(sentence => `
    <details class="outline-group">
      <summary>${escapeHtml(sentence.id || "Sentence")} <span class="outline-meta">${sentence.words} words</span></summary>
      <div class="outline-group">${state.current.words.filter(word => word.sentence_id === sentence.id).slice(0, 120).map(word => `
        <button data-outline-word="${escapeHtml(word.path)}">${escapeHtml(word.form || word.tag)}</button>
      `).join("")}</div>
    </details>`).join("");
  return `<div class="outline-group">${sentenceItems}</div>`;
}

export function renderOutline() {
  const filter = $("outline-filter").value.trim().toLowerCase();
  $("outline").innerHTML = state.outline.map(collection => `
    <details open>
      <summary>${escapeHtml(collection.label)}</summary>
      <div class="outline-group">${collection.families.map(family => {
        const documents = family.documents.filter(document => document.name.toLowerCase().includes(filter));
        if (!documents.length) return "";
        return `<details ${state.current?.collection === collection.collection && documents.some(document => document.name === state.current.name) ? "open" : ""}>
          <summary>${escapeHtml(family.name)}</summary>
          <div class="outline-group">${documents.map(document => `
            <button class="${document.modified ? "modified" : ""} ${state.current?.name === document.name && state.current?.collection === collection.collection ? "active" : ""}" data-document="${escapeHtml(document.name)}" data-collection="${collection.collection}">
              ${escapeHtml(document.id)} <span class="outline-meta">${document.sentences}</span>
            </button>${activeDocumentExtras(document)}
          `).join("")}</div>
        </details>`;
      }).join("")}</div>
    </details>
  `).join("");

  $("outline").querySelectorAll("[data-document]").forEach(button => {
    button.onclick = () => openDocumentCallback(button.dataset.collection, button.dataset.document);
  });
  $("outline").querySelectorAll("[data-outline-word]").forEach(button => {
    button.onclick = event => {
      event.stopPropagation();
      document.dispatchEvent(new CustomEvent("node-select", {detail: button.dataset.outlineWord}));
    };
  });
}

export async function loadOutline(openDocument) {
  openDocumentCallback = openDocument;
  state.outline = await api.outline();
  renderOutline();
}

export function setupOutline() {
  $("outline-filter").oninput = renderOutline;
}

