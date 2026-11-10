// The 🐞 button: describe a bug, with the context that helps to fix it.
// Stored on our server only (python -m assistant bugs), never sent elsewhere.

document.addEventListener("DOMContentLoaded", () => {
  const dialog = document.getElementById("bug-dialog");
  const form = document.getElementById("bug-form");
  const text = document.getElementById("bug-text");
  const withChat = document.getElementById("bug-chat");
  const imageInput = document.getElementById("bug-image");
  const send = form.querySelector("button[type=submit]");

  document.getElementById("bug-open").addEventListener("click", () => {
    text.value = "";
    imageInput.value = "";
    dialog.showModal();
    text.focus();
  });
  document.getElementById("bug-cancel").addEventListener("click", () => dialog.close());

  // What the person cannot easily say: where, the last error, the browser,
  // and (if they agree) the last messages of the chat.
  function context() {
    const lines = [`Navigateur : ${navigator.userAgent}`];
    if (lastError) lines.push(`Dernière erreur : ${lastError}`);
    if (withChat.checked) {
      const messages = [...document.querySelectorAll("#log .msg")].slice(-8);
      lines.push("Derniers messages :",
                 ...messages.map(m => `[${m.classList[1]}] ${m.textContent}`));
    }
    return lines.join("\n");
  }

  // A screenshot, made smaller (1600 px max) and re-encoded as JPEG by drawing
  // it on a canvas: lighter to send, and the photo's metadata (EXIF, GPS
  // position...) is not copied.
  async function shrink(file) {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.8);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    let image = null;
    if (imageInput.files.length) {
      try {
        image = await shrink(imageInput.files[0]);
      } catch {
        return alert("Cette image ne peut pas être lue : essaie une capture d'écran.");
      }
    }
    const tab = document.querySelector("nav [aria-selected=true]");
    send.disabled = true;
    const result = await api("POST", "/api/bugs/report", {
      description: text.value,
      place: tab ? tab.dataset.view : "unknown",
      details: context(),
      image,
    });
    send.disabled = false;
    if (result.type === "error") return alert(result.text);
    dialog.close();
    alert(`Merci ! Bug n°${result.id} enregistré.`);
  });
});
