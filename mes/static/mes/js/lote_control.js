/* Tarjeta de predicción de rendimiento (ML) */
(async function () {
  const box = document.getElementById("pred-box"); if (!box) return;
  const set = (id, t) => document.getElementById(id).textContent = t;
  try {
    const d = await MES.get(box.dataset.url);
    if (!d.disponible) { set("pred-msg", d.mensaje); return; }
    const bar = document.getElementById("pred-bar");
    bar.style.width = d.rendimiento_estimado_pct + "%"; bar.textContent = d.rendimiento_estimado_pct.toFixed(1) + " %";
    bar.className = "progress-bar " + (d.rendimiento_estimado_pct >= d.rendimiento_teorico_pct - 3 ? "bg-success" : d.rendimiento_estimado_pct >= d.rendimiento_teorico_pct - 8 ? "bg-warning text-dark" : "bg-danger");
    set("pred-teorico", d.rendimiento_teorico_pct.toFixed(1) + " %");
    set("pred-mae", "± " + d.mae_estimado_pct.toFixed(2) + " pp");
    set("pred-vol", `${d.volumen_proyectado.toFixed(1)} ${d.unidad}`);
    set("pred-msg", `Basado en ${d.lecturas_usadas} lecturas de las primeras ${d.horas_analizadas} h.`);
  } catch (e) { set("pred-msg", "No se pudo calcular la predicción: " + e.message); }
})();
