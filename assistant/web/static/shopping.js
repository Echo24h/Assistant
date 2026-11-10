// Shopping list, shared by the household: no model, 0 tokens. Made for the shop:
// grouped by aisle in the shop's order (aisles come from the product catalog),
// tick what is in the cart, then remove the ticked items.

document.addEventListener("DOMContentLoaded", () => {
  const list = document.getElementById("shop-list");
  const empty = document.getElementById("shop-empty");
  const form = document.getElementById("shop-form");
  const clear = document.getElementById("shop-clear");
  const slot = document.getElementById("shop-row");
  let entry = productRow(); // quantity, unit, product (app.js)
  slot.append(entry);

  async function load() {
    const result = await api("GET", "/api/shopping");
    list.textContent = "";
    if (result.type === "error") return list.append(el("li", "", result.text));
    empty.hidden = result.items.length > 0;
    clear.hidden = !result.items.some(item => item.checked);

    // The server sends the list already in the shop's order: a heading each
    // time the aisle changes. Ticked items come last, under "Dans le panier".
    let heading = null;
    for (const item of result.items) {
      const group = item.checked ? "Dans le panier" : item.aisle;
      if (group !== heading) {
        heading = group;
        list.append(el("li", "aisle", group));
      }
      list.append(row(item));
    }
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
    let item;
    try {
      item = readProductRow(entry);
    } catch (error) {
      return alert(error.message);
    }
    if (!item) return;
    const result = await api("POST", "/api/shopping/add", item);
    if (result.type === "error") return offerProductRequest(result.text);
    const fresh = productRow(); // an empty row for the next product
    entry.replaceWith(fresh);
    entry = fresh;
    entry.querySelector(".name").focus();
    load();
  });

  clear.addEventListener("click", async () => {
    await api("POST", "/api/shopping/clear", {});
    load();
  });

  onShow.shopping = () => { load(); loadProductNames(); };
});
