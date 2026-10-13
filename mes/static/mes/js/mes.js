/* Utilidades globales: CSRF, fetch JSON, badge de alertas, gobernanza humana del agente IA */
window.MES = {
  csrf: () => document.querySelector('meta[name="csrf-token"]').content,
  async req(url, method = "GET", body) {
    const r = await fetch(url, {method, credentials: "same-origin",
      headers: {"Content-Type": "application/json", "X-CSRFToken": MES.csrf()}, body: body ? JSON.stringify(body) : undefined});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || `Error ${r.status}`);
    return j;
  },
  get: (u) => MES.req(u), post: (u, b) => MES.req(u, "POST", b || {}),
  toast(msg, tipo = "success") {
    const el = document.createElement("div");
    el.className = `alert alert-${tipo} position-fixed shadow`; el.style.cssText = "right:1rem;bottom:1rem;z-index:2000;max-width:360px";
    el.textContent = msg; document.body.appendChild(el); setTimeout(() => el.remove(), 4500);
  },
};

// Badge de alertas pendientes (refresco cada 15 s)
(async function badge() {
  const b = document.getElementById("badge-alertas"); if (!b) return;
  try { const {pendientes} = await MES.get("/api/v1/alertas/pendientes/"); b.textContent = pendientes; b.classList.toggle("d-none", pendientes === 0); } catch (e) {}
  setTimeout(badge, 15000);
})();

// Botones [Aprobar medida] / [Descartar] — gobernanza humana
document.addEventListener("click", async (ev) => {
  const btn = ev.target.closest("[data-alerta-accion]"); if (!btn) return;
  const {alertaId, alertaAccion} = btn.dataset;
  btn.closest(".agent-actions").querySelectorAll("button").forEach(b => b.disabled = true);
  try {
    await MES.post(`/api/v1/alertas/${alertaId}/${alertaAccion}/`);
    MES.toast(alertaAccion === "aprobar" ? "Medida aprobada y registrada en el EBR." : "Sugerencia descartada y auditada.");
    const caja = document.getElementById(`alerta-${alertaId}`); if (caja) caja.remove();
    document.dispatchEvent(new CustomEvent("alerta-resuelta", {detail: alertaId}));
  } catch (e) {
    MES.toast(e.message, "danger");
    btn.closest(".agent-actions").querySelectorAll("button").forEach(b => b.disabled = false);
  }
});
