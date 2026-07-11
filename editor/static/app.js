"use strict";

// ── State ──────────────────────────────────────────────────────────────────
let activeDoc = null;
let activeUtt = null;

// ── Helpers ────────────────────────────────────────────────────────────────
async function apiFetch(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} — ${path}`);
  return res.json();
}

function clearActive(list) {
  list.querySelectorAll("li.active").forEach(el => el.classList.remove("active"));
}

// ── Tab switching ──────────────────────────────────────────────────────────
document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.add("hidden"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.remove("hidden");
  });
});

// ── Documents pane ─────────────────────────────────────────────────────────
async function loadDocuments() {
  const docs = await apiFetch("/api/documents");
  const list = document.getElementById("doc-list");
  list.innerHTML = "";
  docs.forEach(doc => {
    const li = document.createElement("li");
    li.textContent = doc.label;
    li.title = `${doc.utterance_count} utterances`;
    li.addEventListener("click", () => selectDocument(doc.id, li));
    list.appendChild(li);
  });
}

async function selectDocument(docId, liElem) {
  if (activeDoc === docId) return;
  activeDoc = docId;
  activeUtt = null;
  clearActive(document.getElementById("doc-list"));
  liElem.classList.add("active");
  document.getElementById("utt-list").innerHTML = "";
  document.getElementById("tree-display").textContent = "Select an utterance.";

  const utts = await apiFetch(`/api/documents/${docId}`);
  const list = document.getElementById("utt-list");
  list.innerHTML = "";
  utts.forEach(utt => {
    const li = document.createElement("li");
    const sid = document.createElement("div");
    sid.textContent = utt.sentence_id;
    const hdr = document.createElement("div");
    hdr.className = "utt-header";
    hdr.textContent = utt.header;
    li.appendChild(sid);
    li.appendChild(hdr);
    li.addEventListener("click", () => selectUtterance(docId, utt.sentence_id, li));
    list.appendChild(li);
  });
}

// ── Utterances pane ────────────────────────────────────────────────────────
async function selectUtterance(docId, sentenceId, liElem) {
  if (activeUtt === sentenceId) return;
  activeUtt = sentenceId;
  clearActive(document.getElementById("utt-list"));
  liElem.classList.add("active");

  const data = await apiFetch(`/api/utterances/${docId}/${encodeURIComponent(sentenceId)}`);
  document.getElementById("tree-display").textContent = data.tree;

  // Switch to Tree tab
  document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.add("hidden"));
  document.querySelector('.tab[data-tab="tree"]').classList.add("active");
  document.getElementById("tab-tree").classList.remove("hidden");
}

// ── Dictionary pane ────────────────────────────────────────────────────────
let _dictTimer = null;

document.getElementById("dict-input").addEventListener("input", e => {
  clearTimeout(_dictTimer);
  const q = e.target.value.trim();
  if (!q) {
    document.getElementById("dict-results").innerHTML = "";
    document.getElementById("dict-entry").classList.add("hidden");
    return;
  }
  _dictTimer = setTimeout(() => searchDict(q), 300);
});

async function searchDict(q) {
  const hits = await apiFetch(`/api/dictionary?q=${encodeURIComponent(q)}`);
  const list = document.getElementById("dict-results");
  list.innerHTML = "";
  document.getElementById("dict-entry").classList.add("hidden");

  hits.forEach(hit => {
    const li = document.createElement("li");
    li.textContent = `${hit.id}  ${hit.gloss}  [${hit.forms.join(", ")}]  ${hit.pos}`;
    li.title = hit.id;
    li.addEventListener("click", () => showEntry(hit.id));
    list.appendChild(li);
  });
}

async function showEntry(entryId) {
  const data = await apiFetch(`/api/dictionary/${encodeURIComponent(entryId)}`);
  const box = document.getElementById("dict-entry");
  box.innerHTML = "";
  box.classList.remove("hidden");

  const h3 = document.createElement("h3");
  h3.textContent = data.id;
  box.appendChild(h3);

  data.fields.forEach(f => {
    const row = document.createElement("div");
    row.className = "dict-field";
    const tag = document.createElement("span");
    tag.className = "dict-tag";
    tag.textContent = f.tag;
    const val = document.createElement("span");
    val.className = "dict-value";
    val.textContent = f.value;
    row.appendChild(tag);
    row.appendChild(val);
    box.appendChild(row);
  });
}

// ── Init ───────────────────────────────────────────────────────────────────
loadDocuments();
