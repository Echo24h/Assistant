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

  // "ce message : 0,0006 $ (5 200 tokens, dont 4 900 en cache) · conversation : 0,0021 $"
  function usageText(t) {
    const tokens = u => u.in + u.cache_read + u.cache_write;
    const usd = x => x === null ? "" : `${x.toFixed(4).replace(".", ",")} $ `;
    const n = x => x.toLocaleString("fr-FR");
    return `ce message : ${usd(t.message_usd)}(${n(tokens(t.message))} tokens, ` +
           `dont ${n(t.message.cache_read)} en cache, ${n(t.message.out)} en sortie) · ` +
           `conversation : ${usd(t.total_usd)}(${n(tokens(t.total))} tokens)`;
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
    if (event.tokens) addMeta(usageText(event.tokens));
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
