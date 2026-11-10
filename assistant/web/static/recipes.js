// Recipes, shared by the household: read and changed directly, no model, 0 tokens.

document.addEventListener("DOMContentLoaded", () => {
  const list = document.getElementById("recipe-list");
  const empty = document.getElementById("recipe-empty");
  const importForm = document.getElementById("import-form");
  const importUrl = document.getElementById("import-url");
  const newBox = document.getElementById("recipe-new");
  const form = document.getElementById("recipe-form");

  async function load() {
    const result = await api("GET", "/api/recipes");
    list.textContent = "";
    if (result.type === "error") return list.append(el("li", "", result.text));
    empty.hidden = result.recipes.length > 0;
    for (const recipe of result.recipes) list.append(item(recipe));
  }

  // A recipe: its title; a tap shows the details (loaded only then).
  function item(recipe) {
    const li = el("li", "recipe");
    const head = el("button", "recipe-head", recipe.title);
    head.append(el("span", "due", `${recipe.servings} pers.`));
    const body = el("div", "recipe-body");
    body.hidden = true;
    head.addEventListener("click", async () => {
      body.hidden = !body.hidden;
      if (!body.hidden && !body.childElementCount) {
        details(body, await api("GET", `/api/recipes/get?id=${recipe.id}`));
      }
    });
    li.append(head, body);
    return li;
  }

  function details(body, recipe) {
    if (recipe.type === "error") return body.append(el("p", "error", recipe.text));

    // Send to the shopping list, for N people (the server scales the quantities).
    const row = el("div", "row");
    const servings = el("input");
    servings.type = "number";
    servings.min = 1;
    servings.max = 100;
    servings.value = recipe.servings;
    servings.setAttribute("aria-label", "Nombre de personnes");
    const shop = el("button", "", "🛒 Ajouter aux courses");
    shop.addEventListener("click", async () => {
      const result = await api("POST", "/api/recipes/shop",
                               { id: recipe.id, servings: Number(servings.value) });
      shop.textContent = result.type === "error" ? result.text : `✓ ${result.added} ajoutés`;
    });
    row.append(servings, el("span", "", "pers."), shop);

    const ingredients = el("ul", "ingredients");
    for (const i of recipe.ingredients) {
      ingredients.append(el("li", "", `${formatAmount(i.quantity, i.unit)} ${i.name}`.trim()));
    }
    body.append(row, ingredients);
    if (recipe.instructions) body.append(el("p", "steps", recipe.instructions));

    // Only real web links (never "javascript:..."), opened without sending our address.
    if (/^https?:\/\//.test(recipe.source_url || "")) {
      const link = el("a", "source", "Voir la recette d'origine");
      link.href = recipe.source_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      body.append(link);
    }

    const remove = el("button", "small danger", "Supprimer la recette");
    remove.addEventListener("click", async () => {
      if (!confirm(`Supprimer « ${recipe.title} » ?`)) return;
      await api("POST", "/api/recipes/delete", { id: recipe.id });
      load();
    });
    body.append(remove);
  }

  importForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const button = importForm.querySelector("button");
    button.disabled = true;
    button.textContent = "…";
    const result = await api("POST", "/api/recipes/import", { url: importUrl.value.trim() });
    button.disabled = false;
    button.textContent = "Importer";
    if (result.type === "error") return alert(result.text);
    importUrl.value = "";
    load();
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const result = await api("POST", "/api/recipes/add", {
      title: document.getElementById("recipe-title").value,
      servings: Number(document.getElementById("recipe-servings").value),
      ingredients: document.getElementById("recipe-ingredients").value,
      instructions: document.getElementById("recipe-instructions").value,
    });
    if (result.type === "error") return alert(result.text);
    form.reset();
    newBox.open = false;
    load();
  });

  onShow.recipes = load;
});
