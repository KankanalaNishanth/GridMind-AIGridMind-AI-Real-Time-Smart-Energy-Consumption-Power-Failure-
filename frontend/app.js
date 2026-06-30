const state = {
  labels: [],
  usage: [],
  forecast: [],
};

const chart = new Chart(document.getElementById("usageChart"), {
  type: "line",
  data: {
    labels: state.labels,
    datasets: [
      {
        label: "Consumption kWh",
        data: state.usage,
        borderColor: "#45c7d8",
        backgroundColor: "rgba(69, 199, 216, 0.14)",
        tension: 0.35,
        fill: true,
      },
      {
        label: "AI forecast kWh",
        data: state.forecast,
        borderColor: "#f5c451",
        borderDash: [5, 5],
        tension: 0.35,
      },
    ],
  },
  options: {
    responsive: true,
    interaction: { mode: "index", intersect: false },
    plugins: { legend: { labels: { color: "#eef4f8" } } },
    scales: {
      x: { ticks: { color: "#91a2af", maxRotation: 0 }, grid: { color: "#26323d" } },
      y: { ticks: { color: "#91a2af" }, grid: { color: "#26323d" } },
    },
  },
});

document.getElementById("refreshButton").addEventListener("click", loadDashboard);

async function loadDashboard() {
  const [snapshot, recent, alerts, report] = await Promise.all([
    fetchJson("/api/dashboard"),
    fetchJson("/api/telemetry/recent?limit=80"),
    fetchJson("/api/alerts?limit=20"),
    fetchJson("/api/reports/history"),
  ]);
  renderSnapshot(snapshot);
  renderHistory(recent, snapshot.prediction);
  renderAlerts(alerts);
  renderReport(report);
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} failed with ${response.status}`);
  return response.json();
}

function renderSnapshot(snapshot) {
  document.getElementById("totalConsumption").textContent = formatNumber(snapshot.total_consumption_kwh, " kWh");
  document.getElementById("averageLoad").textContent = formatNumber(snapshot.average_load_kw, " kW");
  document.getElementById("anomalyCount").textContent = snapshot.anomaly_count ?? 0;
  setRisk(snapshot.outage_risk ?? 0);

  if (snapshot.latest) {
    document.getElementById("latestArea").textContent = `${snapshot.latest.circle} / ${snapshot.latest.area}`;
    document.getElementById("deviceStatus").textContent = snapshot.latest.device_status;
  }
  if (snapshot.prediction) {
    document.getElementById("recommendation").textContent = snapshot.prediction.recommendation;
  }
}

function renderHistory(rows, prediction) {
  state.labels.length = 0;
  state.usage.length = 0;
  state.forecast.length = 0;
  rows.forEach((row) => {
    state.labels.push(new Date(row.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    state.usage.push(row.power_consumption_kwh);
    state.forecast.push(null);
  });
  if (prediction && state.forecast.length) {
    state.forecast[state.forecast.length - 1] = prediction.demand_forecast_kwh;
  }
  chart.update();
}

function renderAlerts(alerts) {
  const target = document.getElementById("alertsList");
  target.innerHTML = alerts.length
    ? alerts
        .map(
          (alert) => `
            <article class="alert">
              <strong>${alert.severity.toUpperCase()} - ${alert.circle} / ${alert.area}</strong>
              <span>${alert.message}</span>
              <small>${new Date(alert.timestamp).toLocaleString()} - risk ${Math.round(alert.outage_risk * 100)}%</small>
            </article>
          `,
        )
        .join("")
    : "<p>No alerts yet.</p>";
}

function renderReport(rows) {
  const target = document.getElementById("reportList");
  target.innerHTML = rows.length
    ? rows
        .slice(0, 8)
        .map(
          (row) => `
            <article class="report-row">
              <strong>${row._id}</strong>
              <span>${formatNumber(row.consumption_kwh, " kWh")} across ${row.records} records</span>
              <small>Average load ${formatNumber(row.average_load_kw, " kW")} - outage events ${row.outages}</small>
            </article>
          `,
        )
        .join("")
    : "<p>Stream telemetry to build historical reports.</p>";
}

function setRisk(value) {
  const risk = Math.max(0, Math.min(value, 1));
  document.getElementById("outageRisk").textContent = `${Math.round(risk * 100)}%`;
  document.getElementById("riskLabel").textContent = `${Math.round(risk * 100)}%`;
  document.getElementById("riskNeedle").style.transform = `rotate(${risk * 270 - 135}deg)`;
}

function setConnection(connected) {
  document.getElementById("statusDot").style.background = connected ? "#64d28c" : "#f5c451";
  document.getElementById("connectionText").textContent = connected ? "Live" : "Polling";
}

function formatNumber(value, suffix) {
  return `${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}${suffix}`;
}

function connectSocket() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/api/ws`);
  socket.addEventListener("open", () => setConnection(true));
  socket.addEventListener("close", () => {
    setConnection(false);
    setTimeout(connectSocket, 2500);
  });
  socket.addEventListener("message", (message) => {
    const payload = JSON.parse(message.data);
    const snapshot = {
      latest: payload.event,
      prediction: payload.prediction,
      outage_risk: payload.prediction.outage_risk,
      total_consumption_kwh: 0,
      average_load_kw: payload.event.grid_load_kw,
      anomaly_count: payload.prediction.is_anomaly ? 1 : 0,
    };
    renderSnapshot(snapshot);
    loadDashboard();
  });
}

loadDashboard().catch((error) => {
  console.warn(error);
  setConnection(false);
});
connectSocket();

