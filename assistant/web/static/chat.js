// Chat with the agent: uses the model, costs tokens.

document.addEventListener("DOMContentLoaded", () => {
  const log = document.getElementById("log");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const send = document.getElementById("chat-send");

  // Text from the agent can contain email content written by strangers:
  // it is ALWAYS inserted as text. Only **bold** is rendered, as <b> elements.
  function addMessage(kind, text) {
    const div = el("div", "msg " + kind);
    text.split(/\*\*(.+?)\*\*/s).forEach((part, i) => {
      div.appendChild(i % 2 ? el("b", "", part) : document.createTextNode(part));
    });
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function addMeta(text) {
    log.appendChild(el("div", "meta", text));
  }

  function setBusy(busy) {
    send.disabled = busy;
    send.textContent = busy ? "…" : "Envoyer";
  }

  // Show what the server answered: a reply, an error, or a question (✅ / ❌).
  function show(event) {
    if (event.type === "question") {
      const box = addMessage("question", "⚠ " + event.text);
      const actions = el("div", "actions");
      for (const [label, yes, cls] of [["✅ Oui", true, "yes"], ["❌ Non", false, "no"]]) {
        const button = el("button", cls, label);
        button.addEventListener("click", async () => {
          actions.querySelectorAll("button").forEach(b => (b.disabled = true));
          show(await api("POST", "/api/confirm", { yes }));
        });
        actions.appendChild(button);
      }
      box.appendChild(actions);
      return; // still busy until the agent's final reply
    }
    addMessage(event.type === "error" ? "error" : "bot", event.text || "");
    if (event.tokens) {
      const t = event.tokens;
      addMeta(`ce message : ${t.in} entrée, ${t.out} sortie · ` +
              `conversation : ${t.total_in} entrée, ${t.total_out} sortie`);
    }
    setBusy(false);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || send.disabled) return;
    input.value = "";
    addMessage("me", text);
    setBusy(true);
    show(await api("POST", "/api/ask", { text }));
  });

  // Enter sends, Shift+Enter makes a new line.
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });

  document.getElementById("reset").addEventListener("click", async () => {
    await api("POST", "/api/reset", {});
    log.textContent = "";
    addMeta("Nouvelle conversation");
  });
});
