// Shared helpers and tab switching. Loaded before chat.js and tasks.js.

// Every request is JSON: the server refuses anything else (CSRF protection).
async function api(method, path, data) {
  const options = { method, headers: { "Content-Type": "application/json" } };
  if (data !== undefined) options.body = JSON.stringify(data);
  let response;
  try {
    response = await fetch(path, options);
  } catch {
    return { type: "error", text: "Connexion impossible (Tailscale activé ?)" };
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) return { type: "error", text: body.error || "Erreur " + response.status };
  return body;
}

// Create an element with text (never HTML: text can come from emails).
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

// Tabs: show one view, hide the others. Each view can react to being shown.
const onShow = {};
function showView(name) {
  for (const tab of document.querySelectorAll("nav [role=tab]")) {
    tab.setAttribute("aria-selected", String(tab.dataset.view === name));
  }
  for (const view of document.querySelectorAll(".view")) {
    view.hidden = view.id !== "view-" + name;
  }
  document.getElementById("reset").hidden = name !== "chat";
  if (onShow[name]) onShow[name]();
}

document.addEventListener("DOMContentLoaded", () => {
  for (const tab of document.querySelectorAll("nav [role=tab]")) {
    tab.addEventListener("click", () => showView(tab.dataset.view));
  }
});
