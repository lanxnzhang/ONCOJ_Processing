export const state = {
  outline: [],
  current: null,
  selectedPath: "",
  mode: "text",
  layer: "text",
  clipboard: null,
};

export function walk(node, visitor) {
  visitor(node);
  node.children.forEach(child => walk(child, visitor));
}

export function findNode(path, root = state.current?.tree) {
  if (!root) return null;
  if (root.path === path) return root;
  for (const child of root.children) {
    const found = findNode(path, child);
    if (found) return found;
  }
  return null;
}

export function selectedNode() {
  return findNode(state.selectedPath);
}

export function sentenceForPath(path = state.selectedPath) {
  if (!state.current) return null;
  const parts = path ? path.split(".") : [];
  for (let length = parts.length; length >= 1; length -= 1) {
    const node = findNode(parts.slice(0, length).join("."));
    if (node?.tag === "block") return node;
  }
  return null;
}

export function cloneNodeForPaste(node) {
  if (!node) return null;
  return {
    tag: node.tag,
    attributes: {...node.attributes},
    text: node.text,
    children: node.children.map(cloneNodeForPaste),
  };
}

