export const $ = id => document.getElementById(id);

export function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

export function attributesText(attributes) {
  return Object.entries(attributes || {}).map(([key, value]) => `${key}="${value}"`).join(" ");
}

export function setMessage(message, error = false) {
  const target = $("save-message");
  target.textContent = message;
  target.style.color = error ? "var(--red)" : "";
}

