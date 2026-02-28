const chat = document.getElementById("chat");
const form = document.getElementById("f");
const q = document.getElementById("q");
const clearBtn = document.getElementById("clear");
const historyList = document.getElementById("history-list");

function addMsg(role, text, fuentes) {
  const div = document.createElement("div");
  div.className = "msg " + (role === "Tu" ? "user" : "bot");
  div.textContent = role + ": " + text;
  chat.appendChild(div);
  if (fuentes && fuentes.length) {
    const src = document.createElement("div");
    src.className = "src";
    src.textContent = "Fuentes: " + fuentes.join(", ");
    chat.appendChild(src);
  }
  chat.scrollTop = chat.scrollHeight;
}

function renderHistorySidebar(messages) {
  historyList.innerHTML = "";
  if (!messages.length) {
    const empty = document.createElement("div");
    empty.className = "history-item";
    empty.textContent = "Sin mensajes guardados.";
    historyList.appendChild(empty);
    return;
  }

  for (const m of messages) {
    const item = document.createElement("div");
    item.className = "history-item";

    const meta = document.createElement("div");
    meta.className = "history-meta";
    const role = m.role === "user" ? "Tu" : "Asistente";
    const date = m.created_at ? new Date(m.created_at).toLocaleString() : "";
    meta.textContent = role + (date ? " - " + date : "");

    const text = document.createElement("div");
    text.className = "history-text";
    text.textContent = m.content || "";

    item.appendChild(meta);
    item.appendChild(text);
    historyList.appendChild(item);
  }
}

function renderChat(messages) {
  chat.innerHTML = "";
  for (const m of messages) {
    const role = m.role === "user" ? "Tu" : "Asistente";
    addMsg(role, m.content || "", m.sources || []);
  }
}

async function fetchHistory() {
  try {
    const r = await fetch("/api/history");
    const data = await r.json();
    if (!r.ok || !Array.isArray(data.messages)) return [];
    return data.messages;
  } catch (_) {
    return [];
  }
}

async function cargarHistorial() {
  const messages = await fetchHistory();
  renderChat(messages);
  renderHistorySidebar(messages);
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const pregunta = q.value.trim();
  if (!pregunta) return;
  addMsg("Tu", pregunta);
  q.value = "";
  try {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pregunta })
    });

    let data = {};
    try {
      data = await r.json();
    } catch (_) {
      data = {};
    }

    if (!r.ok) {
      const msg = data.error || data.respuesta || ("Error HTTP " + r.status);
      addMsg("Asistente", msg, []);
      return;
    }

    addMsg("Asistente", data.respuesta || "No se pudo responder.", data.fuentes || []);
    const messages = await fetchHistory();
    renderHistorySidebar(messages);
  } catch (err) {
    addMsg("Asistente", "Error de red o del servidor: " + (err?.message || err), []);
  }
});

clearBtn.addEventListener("click", async () => {
  try {
    const r = await fetch("/api/history", { method: "DELETE" });
    if (r.ok) {
      chat.innerHTML = "";
      renderHistorySidebar([]);
      addMsg("Asistente", "Historial eliminado.", []);
    }
  } catch (_) {}
});

cargarHistorial();
