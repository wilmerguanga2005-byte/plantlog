(function () {
  const f = document.getElementById("form-cierre"); if (!f) return;
  f.addEventListener("submit", async (e) => {
    e.preventDefault(); const btn = f.querySelector("button"); btn.disabled = true; btn.textContent = "Generando marbetes…";
    try {
      const r = await MES.post(f.dataset.url, {volumen_total_l: f.volumen.value, unidades: f.unidades.value, merma_l: f.merma.value || 0});
      MES.toast(`${r.botellas_creadas} botellas generadas con QR.`); setTimeout(() => location.reload(), 800);
    } catch (err) { MES.toast(err.message, "danger"); btn.disabled = false; btn.textContent = "Cerrar envasado y generar marbetes"; }
  });
})();
