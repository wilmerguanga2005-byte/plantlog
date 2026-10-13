/* Gráfica de control estadístico (Chart.js): serie en vivo + LSC, LIC y valor óptimo */
(function () {
  const cv = document.getElementById("chart-control"); if (!cv) return;
  const urlBase = cv.dataset.url, etapa = cv.dataset.etapa;
  let variable = cv.dataset.variable || "TEMP", chart, timer;
  const $ = (id) => document.getElementById(id);

  const linea = (label, color, dash) => ({label, data: [], borderColor: color, borderDash: dash, borderWidth: 1.6,
    pointRadius: 0, fill: false, order: 2});

  function crear() {
    chart = new Chart(cv, {
      type: "line",
      data: {labels: [], datasets: [
        {label: "Lectura", data: [], borderColor: "#2b6a8f", backgroundColor: "#2b6a8f", borderWidth: 2, tension: .25,
         pointRadius: 3, pointBackgroundColor: [], order: 1},
        linea("LSC", "#b3261e", [6, 4]), linea("LIC", "#b3261e", [6, 4]), linea("Óptimo", "#1c7c54", [2, 3])]},
      options: {responsive: true, maintainAspectRatio: false, animation: false, interaction: {mode: "index", intersect: false},
        plugins: {legend: {position: "bottom"}},
        scales: {x: {ticks: {maxTicksLimit: 8, maxRotation: 0}}, y: {title: {display: true, text: ""}}}},
    });
  }

  async function cargar() {
    const q = new URLSearchParams({variable}); if (etapa) q.set("etapa", etapa);
    let d; try { d = await MES.get(`${urlBase}?${q}`); } catch (e) { return; }
    const lim = d.limites, n = d.puntos.length, v = d.puntos.map(p => p.v);
    chart.data.labels = d.puntos.map(p => p.t);
    chart.data.datasets[0].data = v;
    chart.data.datasets[0].label = `${d.variable} (${d.unidad})`;
    chart.data.datasets[0].pointBackgroundColor = v.map(x => lim && (x > lim.max || x < lim.min) ? "#b3261e" : "#2b6a8f");
    chart.data.datasets[0].pointRadius = v.map(x => lim && (x > lim.max || x < lim.min) ? 6 : 3);
    [[1, "max"], [2, "min"], [3, "optimo"]].forEach(([i, k]) => chart.data.datasets[i].data = lim ? Array(n).fill(lim[k]) : []);
    if (lim) { const pad = (lim.max - lim.min) * .25; chart.options.scales.y.min = Math.min(lim.min, ...v) - pad; chart.options.scales.y.max = Math.max(lim.max, ...v) + pad; }
    chart.options.scales.y.title.text = d.unidad;
    chart.update();

    const media = n ? v.reduce((a, b) => a + b, 0) / n : 0;
    const sd = n > 1 ? Math.sqrt(v.reduce((a, b) => a + (b - media) ** 2, 0) / (n - 1)) : 0;
    const ult = n ? v[n - 1] : null, fuera = lim && ult !== null && (ult > lim.max || ult < lim.min);
    $("st-ultimo").textContent = ult === null ? "—" : `${ult.toFixed(2)} ${d.unidad}`;
    $("st-media").textContent = media.toFixed(2); $("st-sigma").textContent = sd.toFixed(2); $("st-n").textContent = n;
    $("st-limites").textContent = lim ? `${lim.min} – ${lim.max} (${lim.tipo})` : "Sin límites definidos";
    const e = $("st-estado"); e.textContent = ult === null ? "Sin datos" : fuera ? "Fuera de control" : "En control";
    e.className = "tag " + (ult === null ? "off" : fuera ? "pcc" : "ok");
  }

  document.querySelectorAll("[data-var]").forEach(b => b.addEventListener("click", () => {
    document.querySelectorAll("[data-var]").forEach(x => x.classList.remove("active")); b.classList.add("active");
    variable = b.dataset.var; cargar();
  }));
  const live = $("toggle-vivo");
  const ciclo = () => { clearInterval(timer); if (live.checked) timer = setInterval(cargar, 10000); };
  live.addEventListener("change", ciclo);
  crear(); cargar(); ciclo();
  document.addEventListener("alerta-resuelta", cargar);
})();
