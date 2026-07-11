"use strict";

// ── State ──────────────────────────────────────────────────────────────────
let activeDoc = null;
let activeUtt = null;
let currentTreeData = null;

// ── Helpers ────────────────────────────────────────────────────────────────
async function apiFetch(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} — ${path}`);
  return res.json();
}

function clearActive(list) {
  list.querySelectorAll("li.active").forEach(el => el.classList.remove("active"));
}

// ── Toggle state ───────────────────────────────────────────────────────────
function toggles() {
  return {
    lemma:    document.getElementById("tog-lemma").checked,
    phon:     document.getElementById("tog-phon").checked,
    null_:    document.getElementById("tog-null").checked,
    comments: document.getElementById("tog-comments").checked,
  };
}

["tog-lemma","tog-phon","tog-null","tog-comments"].forEach(id => {
  document.getElementById(id).addEventListener("change", () => {
    if (currentTreeData) renderSvgTree(currentTreeData);
  });
});

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
  currentTreeData = null;
  clearActive(document.getElementById("doc-list"));
  liElem.classList.add("active");
  document.getElementById("utt-list").innerHTML = "";
  document.getElementById("tree-container").innerHTML =
    '<p class="tree-placeholder">Select an utterance.</p>';

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

  const data = await apiFetch(
    `/api/utterances/${docId}/${encodeURIComponent(sentenceId)}/tree`
  );
  currentTreeData = data;
  renderSvgTree(data);

  // Switch to Tree tab
  document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.add("hidden"));
  document.querySelector('.tab[data-tab="tree"]').classList.add("active");
  document.getElementById("tab-tree").classList.remove("hidden");
}

// ══════════════════════════════════════════════════════════════════════════
// SVG Tree Renderer
// ══════════════════════════════════════════════════════════════════════════

// Layout constants
const COL_W   = 90;   // horizontal cell width per leaf
const ROW_H   = 48;   // vertical spacing between levels
const LEAF_H  = 88;   // extra height for leaf annotation block
const PAD_X   = 40;   // horizontal padding
const PAD_TOP = 32;   // space above root

// Font metrics (approximate, for SVG text positioning)
const FONT_TAG  = 13; // px, syntactic tag
const FONT_FORM = 13; // px, italic word form
const FONT_ANN  = 11; // px, phon / lemma

const SVG_NS = "http://www.w3.org/2000/svg";

function svgElem(tag, attrs = {}, text = null) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (text !== null) el.textContent = text;
  return el;
}

// ── Step 1: prune the tree according to toggles ───────────────────────────
function isNullNode(node) {
  return node.form !== undefined && node.form === "" && node.phon === "";
}

function pruneNode(node, opts) {
  if (!opts.null_ && isNullNode(node)) return null;
  if (!node.children) return { ...node }; // leaf
  const children = node.children
    .map(c => pruneNode(c, opts))
    .filter(Boolean);
  if (children.length === 0) return null;
  return { ...node, children };
}

// ── Step 2: assign leaf positions (Reingold-Tilford simplified) ───────────
// Returns { leaves, depth } for each node:
//   leaves: number of leaf descendants
//   xCenter: center x (in leaf units)
//   depth: depth in tree

function assignX(node, leafCounter = { n: 0 }) {
  if (!node.children) {
    const x = leafCounter.n;
    leafCounter.n++;
    node._x = x;
    node._leaves = 1;
  } else {
    node.children.forEach(c => assignX(c, leafCounter));
    const first = node.children[0]._x;
    const last  = node.children[node.children.length - 1]._x;
    node._x = (first + last) / 2;
    node._leaves = node.children.reduce((s, c) => s + c._leaves, 0);
  }
}

function assignDepth(node, d = 0) {
  node._depth = d;
  if (node.children) node.children.forEach(c => assignDepth(c, d + 1));
}

function maxDepth(node) {
  if (!node.children) return node._depth;
  return Math.max(...node.children.map(maxDepth));
}

// ── Step 3: render into SVG ───────────────────────────────────────────────

function xPx(leafX, totalLeaves) {
  // map 0-based leaf index to pixel center
  return PAD_X + (leafX + 0.5) * COL_W;
}

function yPx(depth, bottomDepth) {
  // internal levels grow downward; leaves are at the bottom
  return PAD_TOP + depth * ROW_H;
}

function leafYPx(bottomDepth) {
  return PAD_TOP + bottomDepth * ROW_H;
}

function renderNode(node, svg, totalLeaves, bottomDepth, opts) {
  const cx = xPx(node._x, totalLeaves);
  const cy = node.children ? yPx(node._depth, bottomDepth) : leafYPx(bottomDepth);

  // draw edges to children
  if (node.children) {
    node.children.forEach(child => {
      const ccx = xPx(child._x, totalLeaves);
      const ccy = child.children ? yPx(child._depth, bottomDepth) : leafYPx(bottomDepth);
      svg.appendChild(svgElem("line", {
        x1: cx, y1: cy, x2: ccx, y2: ccy,
        class: "tree-edge",
      }));
    });
  }

  // draw node label
  if (!node.children) {
    // Leaf: stacked annotation block
    let yOffset = cy;

    // word form (italic)
    if (node.form) {
      svg.appendChild(svgElem("text", {
        x: cx, y: yOffset,
        class: "lbl-form",
        "text-anchor": "middle",
      }, node.form));
    }
    yOffset += 16;

    // phon/script tag
    if (opts.phon && node.phon) {
      svg.appendChild(svgElem("text", {
        x: cx, y: yOffset,
        class: "lbl-phon",
        "text-anchor": "middle",
      }, node.phon));
      yOffset += 14;
    }

    // lemma ID
    if (opts.lemma && node.lemma) {
      svg.appendChild(svgElem("text", {
        x: cx, y: yOffset,
        class: "lbl-lemma",
        "text-anchor": "middle",
      }, node.lemma));
    }
  } else {
    // Internal node: just the tag
    svg.appendChild(svgElem("text", {
      x: cx, y: cy + 5,
      class: "lbl-tag",
      "text-anchor": "middle",
    }, node.tag));

    // embedded lemma on compound nodes
    if (opts.lemma && node.lemma) {
      svg.appendChild(svgElem("text", {
        x: cx, y: cy + 18,
        class: "lbl-lemma",
        "text-anchor": "middle",
      }, node.lemma));
    }
  }

  // recurse
  if (node.children) {
    node.children.forEach(c => renderNode(c, svg, totalLeaves, bottomDepth, opts));
  }
}

// ── Main entry point ──────────────────────────────────────────────────────

function renderSvgTree(data) {
  const container = document.getElementById("tree-container");
  container.innerHTML = "";
  const opts = toggles();

  // Prune each root and collect non-null ones
  const roots = data.roots.map(r => pruneNode(r, opts)).filter(Boolean);
  if (roots.length === 0) {
    container.innerHTML = '<p class="tree-placeholder">Nothing to display.</p>';
    return;
  }

  // Wrap multiple roots in a synthetic root if needed
  let tree;
  if (roots.length === 1) {
    tree = roots[0];
  } else {
    tree = { tag: "", children: roots, lemma: null };
  }

  // Assign layout
  const leafCounter = { n: 0 };
  assignX(tree, leafCounter);
  assignDepth(tree);
  const totalLeaves = leafCounter.n;
  const bottom = maxDepth(tree);

  // SVG dimensions
  const svgW = totalLeaves * COL_W + PAD_X * 2;
  const svgH = PAD_TOP + bottom * ROW_H + LEAF_H;

  const svg = svgElem("svg", {
    width: svgW, height: svgH,
    viewBox: `0 0 ${svgW} ${svgH}`,
    class: "tree-svg",
  });

  // Comments header
  if (opts.comments && data.comments && data.comments.length) {
    data.comments.forEach((c, i) => {
      svg.appendChild(svgElem("text", {
        x: PAD_X, y: 14 + i * 14,
        class: "lbl-comment",
      }, `# ${c}`));
    });
  }

  // Render edges first (so labels draw on top)
  renderNode(tree, svg, totalLeaves, bottom, opts);

  container.appendChild(svg);
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
