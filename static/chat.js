const chat = document.getElementById("chat");
const form = document.getElementById("f");
const q = document.getElementById("q");
const clearBtn = document.getElementById("clear");
const newChatBtn = document.getElementById("new-chat");
const historyList = document.getElementById("history-list");
const userSelect = document.getElementById("user-select");
const registerUserBtn = document.getElementById("register-user");
const deleteUserBtn = document.getElementById("delete-user");
const toggleLlmBtn = document.getElementById("toggle-llm");

let conversations = [];
let currentConversationId = null;
let lastRenderedMessageId = null;

// Añade un mensaje al panel de chat y, si existen, muestra sus fuentes.
function addMsg(role, text, fuentes, isUser = false) {
  const div = document.createElement("div");
  div.className = "msg " + (isUser ? "user" : "bot");
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

// Renderiza todo el historial recibido en el panel de chat.
function renderChat(messages) {
  chat.innerHTML = "";
  for (const m of messages) {
    const isUser = m.role === "user";
    const role = m.user_name || (isUser ? "Usuario" : "Asistente");
    addMsg(role, m.content || "", m.sources || [], isUser);
  }
  const last = messages[messages.length - 1];
  lastRenderedMessageId = last ? Number(last.id || 0) : 0;
}

// Genera una vista previa corta del último mensaje de una conversación.
function previewText(conversation) {
  const last = String(conversation.last_message || "").replace(/\s+/g, " ").trim();
  if (last) {
    const MAX = 90;
    return last.length > MAX ? last.slice(0, MAX - 1) + "…" : last;
  }
  return "Sin mensajes";
}

// Dibuja la lista de conversaciones y sus acciones en el lateral.
function renderConversations() {
  historyList.innerHTML = "";
  if (!conversations.length) {
    const empty = document.createElement("div");
    empty.className = "history-item";
    empty.textContent = "No hay chats todavía.";
    historyList.appendChild(empty);
    return;
  }

  for (const c of conversations) {
    const item = document.createElement("div");
    item.className = "history-item history-chat";
    if (c.id === currentConversationId) item.classList.add("active");
    item.dataset.id = String(c.id);

    const head = document.createElement("div");
    head.className = "history-head";

    const meta = document.createElement("div");
    meta.className = "history-meta";
    const date = c.updated_at ? new Date(c.updated_at).toLocaleString() : "";
    const count = Number(c.message_count || 0);
    const llmTag = c.llm_enabled === false ? " - LLM OFF" : "";
    meta.textContent = (c.title || "Nuevo chat") + " - " + count + " msg" + llmTag + (date ? " - " + date : "");
    head.appendChild(meta);

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "delete-conversation";
    deleteBtn.textContent = "Eliminar";
    deleteBtn.addEventListener("click", async (ev) => {
      // Evita que el click en "Eliminar" también seleccione la conversación.
      ev.stopPropagation();
      await deleteConversation(c.id);
    });
    head.appendChild(deleteBtn);

    const text = document.createElement("div");
    text.className = "history-text";
    text.textContent = previewText(c);

    item.appendChild(head);
    item.appendChild(text);
    item.addEventListener("click", () => {
      void selectConversation(c.id);
    });
    historyList.appendChild(item);
  }
}

// Obtiene todas las conversaciones desde la API.
async function fetchConversations() {
  try {
    const r = await fetch("/api/conversations");
    const data = await r.json();
    if (!r.ok || !Array.isArray(data.conversations)) return [];
    return data.conversations;
  } catch (_) {
    // Fallback silencioso para no romper la interfaz por un fallo temporal de red.
    return [];
  }
}

// Crea una nueva conversación vacía en el backend.
async function createConversation() {
  const r = await fetch("/api/conversations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({})
  });
  const data = await r.json();
  if (!r.ok || !data.conversation || typeof data.conversation.id !== "number") {
    throw new Error(data.error || "No se pudo crear el chat");
  }
  return data.conversation;
}

// Elimina una conversación por id mediante la API.
async function deleteConversationById(conversationId) {
  const r = await fetch("/api/conversations/" + encodeURIComponent(conversationId), {
    method: "DELETE"
  });
  let data = {};
  try {
    data = await r.json();
  } catch (_) {
    data = {};
  }
  if (!r.ok) {
    throw new Error(data.error || ("Error HTTP " + r.status));
  }
  return data;
}

// Cambia el estado de LLM (on/off) para una conversación.
async function setConversationLlm(conversationId, enabled) {
  const r = await fetch("/api/conversations/" + encodeURIComponent(conversationId) + "/llm", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled })
  });
  let data = {};
  try {
    data = await r.json();
  } catch (_) {
    data = {};
  }
  if (!r.ok || !data.conversation) {
    throw new Error(data.error || ("Error HTTP " + r.status));
  }
  return data.conversation;
}

// Recupera los mensajes de una conversación concreta.
async function fetchHistory(conversationId) {
  if (typeof conversationId !== "number") return [];
  try {
    const r = await fetch("/api/history?conversation_id=" + encodeURIComponent(conversationId));
    const data = await r.json();
    if (!r.ok || !Array.isArray(data.messages)) return [];
    return data.messages;
  } catch (_) {
    return [];
  }
}

// Refresca el estado local de conversaciones y lo vuelve a pintar.
async function refreshConversations() {
  conversations = await fetchConversations();
  renderConversations();
  syncLlmButton();
}

// Selecciona una conversación y carga su historial en pantalla.
async function selectConversation(conversationId) {
  currentConversationId = conversationId;
  renderConversations();
  syncLlmButton();
  const messages = await fetchHistory(conversationId);
  renderChat(messages);
}

// Sincroniza el chat actual solo si detecta mensajes nuevos.
async function syncCurrentConversation() {
  if (!currentConversationId) return;
  const messages = await fetchHistory(currentConversationId);
  const last = messages[messages.length - 1];
  const nextLastId = last ? Number(last.id || 0) : 0;
  if (nextLastId !== lastRenderedMessageId) {
    // Solo re-renderizamos cuando cambia el último mensaje para reducir parpadeos.
    renderChat(messages);
    await refreshConversations();
  }
}

// Garantiza que exista y quede seleccionada una conversación activa.
async function ensureConversationSelected() {
  await refreshConversations();
  if (!conversations.length) {
    // Primera ejecución: garantiza un chat disponible antes de enviar mensajes.
    const created = await createConversation();
    conversations = [created];
  }
  if (!currentConversationId || !conversations.some((c) => c.id === currentConversationId)) {
    currentConversationId = conversations[0].id;
  }
  renderConversations();
  syncLlmButton();
  await selectConversation(currentConversationId);
}

// Devuelve la conversación actualmente seleccionada en memoria.
function getCurrentConversation() {
  return conversations.find((c) => c.id === currentConversationId) || null;
}

// Sincroniza el texto/estado del botón para activar o desactivar LLM.
function syncLlmButton() {
  if (!toggleLlmBtn) return;
  const currentConversation = getCurrentConversation();
  if (!currentConversation) {
    toggleLlmBtn.disabled = true;
    toggleLlmBtn.textContent = "Desactivar LLM";
    toggleLlmBtn.classList.remove("is-off");
    return;
  }
  const enabled = currentConversation.llm_enabled !== false;
  toggleLlmBtn.disabled = false;
  toggleLlmBtn.textContent = enabled ? "Desactivar LLM" : "Activar LLM";
  toggleLlmBtn.classList.toggle("is-off", !enabled);
}

// Gestiona el flujo de borrado con confirmación y recarga de UI.
async function deleteConversation(conversationId) {
  const convo = conversations.find((c) => c.id === conversationId);
  const nombre = convo?.title || ("Chat " + conversationId);
  const ok = window.confirm("¿Eliminar '" + nombre + "'? Esta acción borra sus mensajes.");
  if (!ok) return;

  try {
    const data = await deleteConversationById(conversationId);
    const nextId = typeof data.next_conversation_id === "number" ? data.next_conversation_id : null;

    await refreshConversations();
    if (conversationId === currentConversationId) {
      currentConversationId = nextId;
      if (currentConversationId) {
        await selectConversation(currentConversationId);
      } else {
        await ensureConversationSelected();
      }
    } else {
      renderConversations();
    }
  } catch (err) {
    addMsg("Asistente", "No se pudo eliminar el chat: " + (err?.message || err), []);
  }
}

const userManager = window.createUserManager({
  userSelect,
  registerUserBtn,
  deleteUserBtn,
  onInfo: (text) => addMsg("Asistente", text, [])
});
userManager.bindEvents();

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const content = q.value.trim();
  if (!content) return;
  if (!currentConversationId) await ensureConversationSelected();
  if (!userManager.getCurrentUserId()) await userManager.ensureUserSelected();

  const currentUserId = userManager.getCurrentUserId();
  // Limpia el input de inmediato para mejorar sensación de respuesta en UI.
  q.value = "";
  try {
    const r = await fetch("/api/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content, conversation_id: currentConversationId, user_id: currentUserId })
    });

    let data = {};
    try {
      data = await r.json();
    } catch (_) {
      data = {};
    }

    if (!r.ok) {
      const msg = data.error || ("Error HTTP " + r.status);
      addMsg("Sistema", msg, []);
      return;
    }

    if (typeof data.conversation_id === "number") {
      // El backend puede redirigir a otra conversación válida; lo respetamos.
      currentConversationId = data.conversation_id;
    }
    await syncCurrentConversation();
    if (data.llm_enabled === false) {
      addMsg("Asistente", "LLM desactivado en esta conversación. Solo se ha guardado tu mensaje.", []);
    }
  } catch (err) {
    addMsg("Sistema", "Error de red o del servidor: " + (err?.message || err), []);
  }
});

clearBtn.addEventListener("click", async () => {
  if (!currentConversationId) return;
  try {
    const r = await fetch(
      "/api/history?conversation_id=" + encodeURIComponent(currentConversationId),
      { method: "DELETE" }
    );
    if (r.ok) {
      chat.innerHTML = "";
      // Mostramos confirmación como mensaje del sistema en el propio chat.
      addMsg("Asistente", "Chat limpiado.", []);
      await refreshConversations();
    }
  } catch (_) {}
});

newChatBtn.addEventListener("click", async () => {
  try {
    const created = await createConversation();
    currentConversationId = created.id;
    await refreshConversations();
    renderChat([]);
    renderConversations();
  } catch (err) {
    addMsg("Asistente", "No se pudo crear un nuevo chat: " + (err?.message || err), []);
  }
});

if (toggleLlmBtn) {
  toggleLlmBtn.addEventListener("click", async () => {
    const currentConversation = getCurrentConversation();
    if (!currentConversation) return;
    const nextEnabled = currentConversation.llm_enabled === false;
    try {
      const updated = await setConversationLlm(currentConversation.id, nextEnabled);
      // Actualización optimista local sin refetch completo de conversaciones.
      conversations = conversations.map((c) => (c.id === updated.id ? { ...c, ...updated } : c));
      renderConversations();
      syncLlmButton();
      const messages = await fetchHistory(updated.id);
      renderChat(messages);
      addMsg("Asistente", nextEnabled ? "LLM activado para esta conversación." : "LLM desactivado para esta conversación.", []);
    } catch (err) {
      addMsg("Sistema", "No se pudo cambiar el estado del LLM: " + (err?.message || err), []);
    }
  });
}

(async () => {
  await userManager.ensureUserSelected();
  await ensureConversationSelected();
})();

setInterval(() => {
  // Polling simple para sincronizar cambios que puedan llegar desde otra pestaña/sesión.
  void syncCurrentConversation();
}, 2000);
