// To-do list, read and changed directly in the database: no model, 0 tokens.

document.addEventListener("DOMContentLoaded", () => {
  const list = document.getElementById("task-list");
  const empty = document.getElementById("task-empty");
  const form = document.getElementById("task-form");
  const title = document.getElementById("task-title");
  const due = document.getElementById("task-due");
  const showDone = document.getElementById("task-show-done");

  const today = new Date().toLocaleDateString("sv"); // "YYYY-MM-DD", local time

  function formatDue(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString("fr-CH", {
      weekday: "short", day: "numeric", month: "short",
    });
  }

  function render(tasks) {
    list.textContent = "";
    empty.hidden = tasks.length > 0;
    for (const task of tasks) {
      const item = el("li", task.done ? "done" : "");

      const box = el("input");
      box.type = "checkbox";
      box.checked = Boolean(task.done);
      box.setAttribute("aria-label", "Terminée");
      box.addEventListener("change", async () => {
        await api("POST", "/api/tasks/done", { id: task.id, done: box.checked });
        load();
      });

      item.append(box, el("span", "title", task.title));
      if (task.due_date) {
        const late = !task.done && task.due_date < today;
        item.append(el("span", late ? "due late" : "due", formatDue(task.due_date)));
      }

      const remove = el("button", "delete", "×");
      remove.setAttribute("aria-label", "Supprimer");
      remove.addEventListener("click", async () => {
        if (!confirm(`Supprimer « ${task.title} » ?`)) return;
        await api("POST", "/api/tasks/delete", { id: task.id });
        load();
      });
      item.append(remove);
      list.append(item);
    }
  }

  async function load() {
    const result = await api("GET", "/api/tasks" + (showDone.checked ? "?all=1" : ""));
    if (result.type === "error") {
      list.textContent = "";
      list.append(el("li", "", result.text));
      return;
    }
    render(result.tasks);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const result = await api("POST", "/api/tasks/add", {
      title: title.value.trim(),
      due_date: due.value || null,
    });
    if (result.type === "error") return alert(result.text);
    title.value = "";
    due.value = "";
    load();
  });

  showDone.addEventListener("change", load);
  onShow.tasks = load; // reload each time the tab is opened (the agent may have changed tasks)
});
