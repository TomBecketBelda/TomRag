(function () {
  function createUserManager(options) {
    const userSelect = options.userSelect;
    const registerUserBtn = options.registerUserBtn;
    const deleteUserBtn = options.deleteUserBtn;
    const onInfo = typeof options.onInfo === "function" ? options.onInfo : function () {};

    let users = [];
    let currentUserId = null;

    function renderUsers() {
      const visibleUsers = users.filter((u) => (u.name || "").trim().toLowerCase() !== "llm");
      userSelect.innerHTML = "";
      if (!visibleUsers.length) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "Sin usuarios";
        userSelect.appendChild(opt);
        currentUserId = null;
        userSelect.disabled = true;
        if (deleteUserBtn) deleteUserBtn.disabled = true;
        return;
      }

      userSelect.disabled = false;
      for (const user of visibleUsers) {
        const opt = document.createElement("option");
        opt.value = String(user.id);
        opt.textContent = user.name;
        if (user.id === currentUserId) opt.selected = true;
        userSelect.appendChild(opt);
      }

      if (!currentUserId || !visibleUsers.some((u) => u.id === currentUserId)) {
        currentUserId = visibleUsers[0].id;
        userSelect.value = String(currentUserId);
      }

      const currentName = users.find((u) => u.id === currentUserId)?.name || "";
      if (deleteUserBtn) deleteUserBtn.disabled = !currentUserId || currentName.toLowerCase() === "llm";
    }

    async function fetchUsers() {
      try {
        const r = await fetch("/api/users");
        const data = await r.json();
        if (!r.ok || !Array.isArray(data.users)) return [];
        return data.users;
      } catch (_) {
        return [];
      }
    }

    async function createUser(name) {
      const r = await fetch("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
      });

      let data = {};
      try {
        data = await r.json();
      } catch (_) {
        data = {};
      }

      if (!r.ok || !data.user || typeof data.user.id !== "number") {
        throw new Error(data.error || "No se pudo registrar el usuario");
      }
      return data.user;
    }

    async function deleteUser(userId) {
      const r = await fetch("/api/users/" + encodeURIComponent(userId), {
        method: "DELETE"
      });

      let data = {};
      try {
        data = await r.json();
      } catch (_) {
        data = {};
      }

      if (!r.ok) {
        throw new Error(data.error || "No se pudo borrar el usuario");
      }
      return data;
    }

    async function refreshUsers() {
      users = await fetchUsers();
      renderUsers();
      return users;
    }

    async function ensureUserSelected() {
      await refreshUsers();
      const hasVisibleUsers = users.some((u) => (u.name || "").trim().toLowerCase() !== "llm");
      if (!hasVisibleUsers) {
        const created = await createUser("Usuario 1");
        users = [...users, created];
        currentUserId = created.id;
        renderUsers();
      }
    }

    function getCurrentUserId() {
      return currentUserId;
    }

    function getCurrentUserName() {
      return users.find((u) => u.id === currentUserId)?.name || "Usuario";
    }

    function bindEvents() {
      userSelect.addEventListener("change", () => {
        const value = Number(userSelect.value);
        if (Number.isInteger(value) && value > 0) {
          currentUserId = value;
          renderUsers();
        }
      });

      registerUserBtn.addEventListener("click", async () => {
        const name = (window.prompt("Nombre del nuevo usuario:") || "").trim();
        if (!name) return;

        try {
          const user = await createUser(name);
          await refreshUsers();
          currentUserId = user.id;
          userSelect.value = String(currentUserId);
          renderUsers();
          onInfo("Usuario registrado: " + user.name);
        } catch (err) {
          onInfo("No se pudo registrar el usuario: " + (err?.message || err));
        }
      });

      if (deleteUserBtn) {
        deleteUserBtn.addEventListener("click", async () => {
          if (!currentUserId) return;
          const name = users.find((u) => u.id === currentUserId)?.name || "este usuario";
          const ok = window.confirm("¿Borrar '" + name + "'? Sus mensajes se conservarán sin autor.");
          if (!ok) return;

          try {
            await deleteUser(currentUserId);
            await refreshUsers();
            onInfo("Usuario borrado: " + name);
          } catch (err) {
            onInfo("No se pudo borrar el usuario: " + (err?.message || err));
          }
        });
      }
    }

    return {
      bindEvents,
      ensureUserSelected,
      getCurrentUserId,
      getCurrentUserName
    };
  }

  window.createUserManager = createUserManager;
})();
