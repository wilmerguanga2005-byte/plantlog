/* Balance de materia: barras apiladas (continúa + merma) y rendimiento real vs receta */
(function () {
  const el = document.getElementById("balance-data"); if (!el) return;
  const c = JSON.parse(el.textContent);
  new Chart(document.getElementById("chart-balance"), {
    data: {labels: c.labels, datasets: [
      {type: "bar", label: "Continúa (kg)", data: c.continua, backgroundColor: "#1c7c54", stack: "m", yAxisID: "y"},
      {type: "bar", label: "Merma declarada (kg)", data: c.merma, backgroundColor: "#b3261e", stack: "m", yAxisID: "y"},
      {type: "line", label: "Rendimiento real (%)", data: c.real, borderColor: "#2b6a8f", backgroundColor: "#2b6a8f", yAxisID: "y2", tension: .2, spanGaps: true},
      {type: "line", label: "Rendimiento receta (%)", data: c.esperado, borderColor: "#c98a00", borderDash: [5, 4], pointRadius: 0, yAxisID: "y2"}]},
    options: {responsive: true, maintainAspectRatio: false,
      plugins: {tooltip: {callbacks: {title: (i) => c.nombres[i[0].dataIndex]}}, legend: {position: "bottom"}},
      scales: {x: {stacked: true}, y: {stacked: true, title: {display: true, text: "kg"}},
               y2: {position: "right", min: 85, max: 101, grid: {drawOnChartArea: false}, title: {display: true, text: "%"}}}},
  });
  // Clic en fila: precarga el formulario de registro
  document.querySelectorAll("tr[data-seg]").forEach(tr => tr.addEventListener("click", () => {
    const f = document.getElementById("form-balance"); if (!f) return;
    f.seguimiento.value = tr.dataset.seg;
    ["masa_entra_kg", "masa_incorporada_kg", "masa_continua_kg", "merma_declarada_kg", "motivo_merma"].forEach(k => f[k].value = tr.dataset[k.replace(/_/g, "")] ?? "");
    document.getElementById("form-etapa").textContent = tr.dataset.nombre;
    document.querySelectorAll("tr[data-seg]").forEach(r => r.classList.remove("row-act")); tr.classList.add("row-act");
  }));
  // Cálculo en vivo de la merma al teclear
  const f = document.getElementById("form-balance");
  if (f) f.addEventListener("input", () => {
    const n = (k) => parseFloat(f[k].value) || 0, disp = n("masa_entra_kg") + n("masa_incorporada_kg");
    document.getElementById("calc-merma").textContent = (disp - n("masa_continua_kg")).toFixed(3);
    document.getElementById("calc-rend").textContent = disp ? (n("masa_continua_kg") / disp * 100).toFixed(2) : "0.00";
  });
})();
