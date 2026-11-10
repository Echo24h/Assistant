// Recipes, shared by the household: read and changed directly, no model, 0 tokens.

document.addEventListener("DOMContentLoaded", () => {
  const list = document.getElementById("recipe-list");
  const empty = document.getElementById("recipe-empty");
  const importForm = document.getElementById("import-form");
  const importUrl = document.getElementById("import-url");
  const newBox = document.getElementById("recipe-new");
  const newForm = document.getElementById("recipe-new-form");

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

    const change = el("button", "small", "✏️ Modifier");
    change.addEventListener("click", () => editor(body, recipe));
    body.append(change);

    const remove = el("button", "small danger", "Supprimer la recette");
    remove.addEventListener("click", async () => {
      if (!confirm(`Supprimer « ${recipe.title} » ?`)) return;
      await api("POST", "/api/recipes/delete", { id: recipe.id });
      load();
    });
    body.append(remove);
  }

  // Ingredients as rows (productRow in app.js), with × and "+ Ingrédient".
  // Nothing typed has to be guessed: the page sends a list of objects.
  function ingredientRows(items) {
    const box = el("div", "ingredient-rows");
    const rows = el("div");
    const add = el("button", "small", "+ Ingrédient");
    add.type = "button";

    function addRow(item) {
      const row = productRow(item);
      const remove = el("button", "delete", "×");
      remove.type = "button";
      remove.setAttribute("aria-label", "Retirer cet ingrédient");
      remove.addEventListener("click", () => row.remove());
      row.append(remove);
      rows.append(row);
      return row.querySelector(".name");
    }

    for (const item of items) addRow(item);
    if (!items.length) addRow();
    add.addEventListener("click", () => addRow().focus());
    box.append(rows, add);
    box.rows = () => [...rows.children].map(readProductRow).filter(Boolean);
    return box;
  }

  // One form to write a new recipe (recipe = null) or to change one.
  function recipeForm(recipe, done) {
    const form = el("form", "stack");
    const title = el("input");
    title.placeholder = "Titre";
    title.maxLength = 200;
    title.required = true;
    title.value = recipe ? recipe.title : "";
    const servings = el("input");
    servings.type = "number";
    servings.min = 1;
    servings.max = 100;
    servings.required = true;
    servings.value = recipe ? recipe.servings : 2;
    const people = el("label", "", "Pour ");
    people.append(servings, " personnes");
    const ingredients = ingredientRows(recipe ? recipe.ingredients : []);
    const steps = el("textarea");
    steps.rows = 5;
    steps.placeholder = "Étapes (facultatif)";
    steps.value = recipe ? recipe.instructions : "";
    const buttons = el("div", "row");
    buttons.append(el("button", "", "Enregistrer"));
    if (recipe) {
      const cancel = el("button", "small", "Annuler");
      cancel.type = "button";
      cancel.addEventListener("click", done);
      buttons.append(cancel);
    }
    form.append(title, people, el("strong", "", "Ingrédients"), ingredients, steps, buttons);

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      let rows;
      try {
        rows = ingredients.rows();
      } catch (error) {
        return alert(error.message);
      }
      const data = { title: title.value, servings: Number(servings.value),
                     ingredients: rows, instructions: steps.value };
      const result = recipe
        ? await api("POST", "/api/recipes/update", { id: recipe.id, ...data })
        : await api("POST", "/api/recipes/add", data);
      if (result.type === "error") return offerProductRequest(result.text);
      done();
    });
    return form;
  }

  function editor(body, recipe) {
    body.textContent = "";
    body.append(recipeForm(recipe, load));
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

  // "Écrire une recette": a fresh form each time the box is opened.
  newBox.addEventListener("toggle", () => {
    newForm.textContent = "";
    if (newBox.open) newForm.append(recipeForm(null, () => { newBox.open = false; load(); }));
  });

  onShow.recipes = () => { load(); loadProductNames(); };
});
