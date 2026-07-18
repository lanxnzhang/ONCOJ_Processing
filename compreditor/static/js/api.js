export async function request(path, options = {}) {
  const config = {...options};
  if (config.body && typeof config.body !== "string") {
    config.headers = {"Content-Type": "application/json", ...(config.headers || {})};
    config.body = JSON.stringify(config.body);
  }
  const response = await fetch(path, config);
  const type = response.headers.get("content-type") || "";
  const data = type.includes("json") ? await response.json() : await response.text();
  if (!response.ok) throw new Error(data.error || data.description || `HTTP ${response.status}`);
  return data;
}

export const api = {
  outline: () => request("/api/outline"),
  document: (collection, name) => request(`/api/documents/${collection}/${encodeURIComponent(name)}`),
  createDocument: body => request("/api/documents", {method: "POST", body}),
  deleteDocument: (collection, name) => request(`/api/documents/${collection}/${encodeURIComponent(name)}`, {method: "DELETE"}),
  editNode: (collection, name, body) => request(`/api/documents/${collection}/${encodeURIComponent(name)}/nodes`, {method: "POST", body}),
  editWords: (collection, name, rows) => request(`/api/documents/${collection}/${encodeURIComponent(name)}/words`, {method: "PUT", body: {rows}}),
  search: body => request("/api/search", {method: "POST", body}),
  dictionarySearch: query => request(`/api/dictionary?q=${encodeURIComponent(query)}`),
  dictionaryEntry: id => request(`/api/dictionary/${encodeURIComponent(id)}`),
  dictionaryCandidates: form => request(`/api/dictionary/candidates?form=${encodeURIComponent(form)}`),
  dictionaryProblems: () => request("/api/dictionary/problems"),
  suggestLemma: (form, start) => request(`/api/dictionary/suggest-id?form=${encodeURIComponent(form)}&start=${encodeURIComponent(start)}`),
  createDictionaryEntry: body => request("/api/dictionary", {method: "POST", body}),
  updateDictionaryEntry: (id, body) => request(`/api/dictionary/${encodeURIComponent(id)}`, {method: "PUT", body}),
  deleteDictionaryEntry: id => request(`/api/dictionary/${encodeURIComponent(id)}`, {method: "DELETE"}),
};
