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

["tog-lemma","tog-phon","tog-null","tog-comments","tog-bottomup"].forEach(id => {
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
const ROW_H   = 44;   // vertical spacing between levels
const ANN_H   = 72;   // height of annotation block below leaves (form+phon+lemma)
const PAD_X   = 32;   // horizontal padding
const PAD_TOP = 28;   // space above root
const CH_PX   = 7.5;  // approx px per character (for label width estimation)
const MIN_COL = 60;   // minimum column width (px)

const SVG_NS = "http://www.w3.org/2000/svg";

function svgElem(tag, attrs = {}, text = null) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (text !== null) el.textContent = text;
  return el;
}

// ── Toggles ───────────────────────────────────────────────────────────────
function toggles() {
  return {
    lemma:    document.getElementById("tog-lemma").checked,
    phon:     document.getElementById("tog-phon").checked,
    null_:    document.getElementById("tog-null").checked,
    comments: document.getElementById("tog-comments").checked,
    bottomup: document.getElementById("tog-bottomup").checked,
  };
}

// ── Step 1: prune ─────────────────────────────────────────────────────────
function isNullNode(node) {
  return node.form !== undefined && node.form === "" && node.phon === "";
}

function pruneNode(node, opts) {
  if (!opts.null_ && isNullNode(node)) return null;
  if (!node.children) return { ...node };
  const children = node.children.map(c => pruneNode(c, opts)).filter(Boolean);
  if (children.length === 0) return null;
  return { ...node, children };
}

// ── Step 2: measure label widths, compute column width ────────────────────
function labelWidth(node, opts) {
  // widest label this node will display
  let w = node.tag.length * CH_PX;
  if (!node.children) {
    if (node.form) w = Math.max(w, node.form.length * CH_PX);
    if (opts.phon  && node.phon)  w = Math.max(w, node.phon.length  * CH_PX);
    if (opts.lemma && node.lemma) w = Math.max(w, node.lemma.length * CH_PX);
  } else {
    if (opts.lemma && node.lemma) w = Math.max(w, node.lemma.length * CH_PX);
  }
  return w + 16; // 8px padding each side
}

function maxLabelWidthAtLeaves(node, opts) {
  if (!node.children) return labelWidth(node, opts);
  return Math.max(...node.children.map(c => maxLabelWidthAtLeaves(c, opts)));
}

// ── Step 3: assign x (leaf positions) ────────────────────────────────────
function assignX(node, leafCounter, colW) {
  if (!node.children) {
    node._x = leafCounter.n++;
  } else {
    node.children.forEach(c => assignX(c, leafCounter, colW));
    node._x = (node.children[0]._x + node.children[node.children.length - 1]._x) / 2;
  }
}

// ── Step 4a: top-down depth ───────────────────────────────────────────────
function assignDepthTopDown(node, d = 0) {
  node._row = d;
  if (node.children) node.children.forEach(c => assignDepthTopDown(c, d + 1));
}

// ── Step 4b: bottom-up height (leaves at row = maxHeight) ────────────────
function assignHeight(node) {
  if (!node.children) { node._h = 0; return 0; }
  const maxH = Math.max(...node.children.map(assignHeight));
  node._h = maxH + 1;
  return node._h;
}

function assignRowsBottomUp(node, totalHeight) {
  node._row = totalHeight - node._h;
  if (node.children) node.children.forEach(c => assignRowsBottomUp(c, totalHeight));
}

// ── Step 5: render ────────────────────────────────────────────────────────
function xPx(leafX, colW) { return PAD_X + (leafX + 0.5) * colW; }
function yPx(row)          { return PAD_TOP + row * ROW_H; }

function renderNode(node, svg, colW, maxRow, opts) {
  const cx = xPx(node._x, colW);
  const cy = yPx(node._row);

  // tag label (all nodes)
  svg.appendChild(svgElem("text", {
    x: cx, y: cy + 5, class: "lbl-tag", "text-anchor": "middle",
  }, node.tag));

  // embedded lemma on internal compound/MK nodes
  if (node.children && opts.lemma && node.lemma) {
    svg.appendChild(svgElem("text", {
      x: cx, y: cy + 18, class: "lbl-lemma", "text-anchor": "middle",
    }, node.lemma));
  }

  if (node.children) {
    // edges + recurse
    node.children.forEach(child => {
      const ccx = xPx(child._x, colW);
      const ccy = yPx(child._row);
      svg.appendChild(svgElem("line", {
        x1: cx, y1: cy + 8, x2: ccx, y2: ccy - 2, class: "tree-edge",
      }));
      renderNode(child, svg, colW, maxRow, opts);
    });
  } else {
    // leaf: dashed edge down to annotation block
    const annY = yPx(maxRow) + ANN_H * 0.3;
    if (node._row < maxRow) {
      svg.appendChild(svgElem("line", {
        x1: cx, y1: cy + 8, x2: cx, y2: annY - 4,
        class: "tree-edge tree-edge-leaf",
      }));
    }

    // annotation block
    let yOff = yPx(maxRow) + 26;
    if (node.form) {
      svg.appendChild(svgElem("text", {
        x: cx, y: yOff, class: "lbl-form", "text-anchor": "middle",
      }, node.form));
    }
    yOff += 15;
    if (opts.phon && node.phon) {
      svg.appendChild(svgElem("text", {
        x: cx, y: yOff, class: "lbl-phon", "text-anchor": "middle",
      }, node.phon));
      yOff += 14;
    }
    if (opts.lemma && node.lemma) {
      svg.appendChild(svgElem("text", {
        x: cx, y: yOff, class: "lbl-lemma", "text-anchor": "middle",
      }, node.lemma));
    }
  }
}

// ── Main entry point ──────────────────────────────────────────────────────
function renderSvgTree(data) {
  const container = document.getElementById("tree-container");
  container.innerHTML = "";
  const opts = toggles();

  const roots = data.roots.map(r => pruneNode(r, opts)).filter(Boolean);
  if (roots.length === 0) {
    container.innerHTML = '<p class="tree-placeholder">Nothing to display.</p>';
    return;
  }

  const tree = roots.length === 1 ? roots[0] : { tag: "", children: roots, lemma: null };

  // Column width: driven by widest leaf label
  const colW = Math.max(MIN_COL, maxLabelWidthAtLeaves(tree, opts));

  // X positions
  const leafCounter = { n: 0 };
  assignX(tree, leafCounter, colW);
  const totalLeaves = leafCounter.n;

  // Row assignments
  let maxRow;
  if (opts.bottomup) {
    const totalH = assignHeight(tree);
    assignRowsBottomUp(tree, totalH);
    maxRow = totalH;
  } else {
    assignDepthTopDown(tree);
    maxRow = (() => { let m = 0; const walk = n => { m = Math.max(m, n._row); if (n.children) n.children.forEach(walk); }; walk(tree); return m; })();
  }

  // SVG sizing
  const svgW = totalLeaves * colW + PAD_X * 2;
  const svgH = PAD_TOP + maxRow * ROW_H + ANN_H + 16;

  const svg = svgElem("svg", {
    width: svgW, height: svgH,
    viewBox: `0 0 ${svgW} ${svgH}`,
    class: "tree-svg",
  });

  // Comments
  if (opts.comments && data.comments && data.comments.length) {
    data.comments.forEach((c, i) => {
      svg.appendChild(svgElem("text", {
        x: PAD_X, y: 13 + i * 13, class: "lbl-comment",
      }, `# ${c}`));
    });
  }

  renderNode(tree, svg, colW, maxRow, opts);
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
