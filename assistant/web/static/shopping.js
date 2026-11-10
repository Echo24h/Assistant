// Shopping list, shared by the household: no model, 0 tokens. Made for the shop:
// tick what is in the cart, then remove the ticked items at the end.

document.addEventListener("DOMContentLoaded", () => {
  const list = document.getElementById("shop-list");
  const empty = document.getElementById("shop-empty");
  const form = document.getElementById("shop-form");
  const text = document.getElementById("shop-text");
  const clear = document.getElementById("shop-clear");

  async function load() {
    const result = await api("GET", "/api/shopping");
    list.textContent = "";
    if (result.type === "error") return list.append(el("li", "", result.text));
    empty.hidden = result.items.length > 0;
    clear.hidden = !result.items.some(item => item.checked);
    for (const item of result.items) list.append(row(item));
  }

  function row(item) {
    const li = el("li", item.checked ? "done" : "");
    const box = el("input");
    box.type = "checkbox";
    box.checked = Boolean(item.checked);
    box.setAttribute("aria-label", "Dans le panier");
    box.addEventListener("change", async () => {
      await api("POST", "/api/shopping/check", { id: item.id, checked: box.checked });
      load();
    });
    const label = el("span", "title", item.name);
    const amount = formatAmount(item.quantity, item.unit);
    const remove = el("button", "delete", "×");
    remove.setAttribute("aria-label", "Retirer");
    remove.addEventListener("click", async () => {
      await api("POST", "/api/shopping/delete", { id: item.id });
      load();
    });
    li.append(box, label);
    if (amount) li.append(el("span", "due", amount));
    li.append(remove);
    return li;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const result = await api("POST", "/api/shopping/add", { text: text.value });
    if (result.type === "error") return alert(result.text);
    text.value = "";
    load();
  });

  clear.addEventListener("click", async () => {
    await api("POST", "/api/shopping/clear", {});
    load();
  });

  onShow.shopping = load;
});
