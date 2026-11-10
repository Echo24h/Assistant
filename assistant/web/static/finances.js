// Shared expenses and who owes whom: no model, 0 tokens.
// Amounts arrive already written ("45.50 CHF"): the page does no money math.

document.addEventListener("DOMContentLoaded", () => {
  const settle = document.getElementById("fin-settle");
  const form = document.getElementById("fin-form");
  const newBox = document.getElementById("fin-new");
  const category = document.getElementById("fin-category");
  const payer = document.getElementById("fin-payer");
  const day = document.getElementById("fin-day");
  const monthLabel = document.getElementById("fin-month");
  const totals = document.getElementById("fin-totals");
  const list = document.getElementById("fin-list");

  let month = new Date().toLocaleDateString("sv").slice(0, 7); // "YYYY-MM", local time
  let filled = false; // the selects are filled once

  function shiftMonth(delta) {
    const [y, m] = month.split("-").map(Number);
    const d = new Date(y, m - 1 + delta, 1);
    month = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    load();
  }

  // "Anna te doit 45.00 CHF", from the point of view of the person reading.
  function sentence(s, me) {
    if (s.to === me) return `${s.from} te doit ${s.amount}`;
    if (s.from === me) return `Tu dois ${s.amount} à ${s.to}`;
    return `${s.from} doit ${s.amount} à ${s.to}`;
  }

  async function load() {
    const result = await api("GET", "/api/finances?month=" + month);
    list.textContent = "";
    if (result.type === "error") return list.append(el("li", "", result.text));

    if (!filled) {
      for (const c of result.categories) category.append(new Option(c, c));
      for (const p of result.people) {
        payer.append(new Option(p.name, p.id, false, p.name === result.me));
      }
      filled = true;
    }
    settle.textContent = result.settle.length
      ? result.settle.map(s => sentence(s, result.me)).join(" · ")
      : "✓ Tout est réglé";

    const [y, m] = month.split("-").map(Number);
    monthLabel.textContent = new Date(y, m - 1, 1)
      .toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
    totals.textContent = Object.entries(result.by_category)
      .map(([name, amount]) => `${name} ${amount}`).join(" · ") || "Aucune dépense ce mois-ci.";

    for (const e of result.expenses) list.append(row(e));
  }

  function row(e) {
    const li = el("li");
    const text = el("span", "title", e.description);
    const [y, m, d] = e.day.split("-").map(Number);
    const when = new Date(y, m - 1, d).toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
    text.append(el("span", "sub", `${when} · ${e.category} · payé par ${e.paid_by} · pour ${e.for_whom}`));
    const remove = el("button", "delete", "×");
    remove.setAttribute("aria-label", "Supprimer");
    remove.addEventListener("click", async () => {
      if (!confirm(`Supprimer « ${e.description} » (${e.amount}) ?`)) return;
      await api("POST", "/api/finances/delete", { id: e.id });
      load();
    });
    li.append(text, el("span", "due", e.amount), remove);
    return li;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const result = await api("POST", "/api/finances/add", {
      amount: document.getElementById("fin-amount").value,
      description: document.getElementById("fin-description").value,
      category: category.value,
      day: day.value || null,
      paid_by: Number(payer.value),
      split: document.getElementById("fin-split").value,
    });
    if (result.type === "error") return alert(result.text);
    document.getElementById("fin-amount").value = "";
    document.getElementById("fin-description").value = "";
    day.value = "";
    newBox.open = false;
    load();
  });

  document.getElementById("fin-prev").addEventListener("click", () => shiftMonth(-1));
  document.getElementById("fin-next").addEventListener("click", () => shiftMonth(1));
  onShow.finances = load;
});
