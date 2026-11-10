// Shared helpers and tab switching. Loaded before chat.js and tasks.js.

// The last error shown, joined to bug reports (bugs.js).
let lastError = "";

// Every request is JSON: the server refuses anything else (CSRF protection).
async function api(method, path, data) {
  const result = await request(method, path, data);
  if (result.type === "error") lastError = `${method} ${path}: ${result.text}`;
  return result;
}

async function request(method, path, data) {
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

// "1000 g" -> "1 kg", "2.5" -> "2,5", "tbsp" -> "c. à soupe". Empty if no quantity.
const UNIT_LABELS = { tsp: "c. à café", tbsp: "c. à soupe" };
function formatAmount(quantity, unit) {
  if (quantity === null || quantity === undefined) return "";
  if (unit === "g" && quantity >= 1000) { quantity /= 1000; unit = "kg"; }
  if (unit === "ml" && quantity >= 1000) { quantity /= 1000; unit = "l"; }
  const number = Number(quantity.toFixed(2)).toLocaleString("fr-FR");
  return unit ? `${number} ${UNIT_LABELS[unit] || unit}` : number;
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
