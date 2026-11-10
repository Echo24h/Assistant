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

// --- Products (catalog written by the developer: assistant/data/products.toml) ---

// Units a row can have: what the server stores ("" = pieces).
const UNITS = [["", "pièce"], ["g", "g"], ["ml", "ml"], ["tsp", "c. à café"],
               ["tbsp", "c. à soupe"]];

// One row: quantity, unit, product (suggested from the catalog while typing).
// Used by the recipe editor and the shopping tab.
function productRow(item = { name: "", quantity: null, unit: null }) {
  const row = el("div", "ingredient-row");
  const quantity = el("input", "qty");
  quantity.inputMode = "decimal";
  quantity.placeholder = "Qté";
  quantity.setAttribute("aria-label", "Quantité");
  quantity.value = item.quantity === null ? "" : String(Number(item.quantity.toFixed(2)));
  const unit = el("select", "unit");
  unit.setAttribute("aria-label", "Unité");
  const known = UNITS.some(([value]) => value === (item.unit || ""));
  for (const [value, label] of known ? UNITS : [...UNITS, [item.unit, item.unit]]) {
    unit.append(new Option(label, value, false, value === (item.unit || "")));
  }
  const name = el("input", "name");
  name.setAttribute("list", "product-names");
  name.setAttribute("aria-label", "Produit");
  name.placeholder = "Produit";
  name.value = item.name;
  row.append(quantity, unit, name);
  return row;
}

// The row as data, or null if no product is written. Throws on a bad quantity.
function readProductRow(row) {
  const name = row.querySelector(".name").value.trim();
  if (!name) return null;
  const typed = row.querySelector(".qty").value.trim().replace(",", ".");
  const quantity = typed === "" ? null : Number(typed);
  if (quantity !== null && !(quantity > 0)) throw new Error(`Quantité invalide pour « ${name} »`);
  return { name, quantity, unit: row.querySelector(".unit").value || null };
}

// The names offered while typing a product (one list for every tab).
async function loadProductNames() {
  const result = await api("GET", "/api/products");
  if (result.type === "error") return;
  const names = document.getElementById("product-names");
  names.textContent = "";
  for (const name of result.products) names.append(new Option(name));
}

// After an "Unknown product" error: show it, and offer to ask the developer
// to add each unknown name (the server says them between quotes).
async function offerProductRequest(errorText) {
  const names = errorText.startsWith("Unknown product")
    ? [...errorText.matchAll(/"([^"]+)"/g)].map(m => m[1]) : [];
  if (!names.length) return alert(errorText);
  for (const name of names) {
    if (confirm(`« ${name} » n'est pas dans la liste des produits.\n\n${errorText}\n\n` +
                `Demander son ajout ?`)) {
      const result = await api("POST", "/api/products/request", { name });
      alert(result.type === "error" ? result.text : `Demande envoyée pour « ${name} ».`);
    }
  }
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
