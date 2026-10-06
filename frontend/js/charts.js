/**
 * GridMind AI — Chart.js Management Module
 */

let forecastChartInstance = null;
let clusterChartInstance = null;

/**
 * Initializes or updates the Energy Consumption Forecast Chart
 * @param {Array} forecastData - Array of {month, predicted_units}
 */
function renderForecastChart(forecastData) {
  const ctx = document.getElementById('forecastChart');
  if (!ctx) return;

  const labels = forecastData.map(d => `Month ${d.month}`);
  const dataPoints = forecastData.map(d => (d.predicted_units / 1000000).toFixed(2)); // in Million Units (MWh / MU)

  if (forecastChartInstance) {
    forecastChartInstance.destroy();
  }

  forecastChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Forecasted Energy Demand (Million Units)',
          data: dataPoints,
          borderColor: '#06b6d4',
          backgroundColor: 'rgba(6, 182, 212, 0.15)',
          borderWidth: 3,
          fill: true,
          tension: 0.35,
          pointBackgroundColor: '#38bdf8',
          pointBorderColor: '#ffffff',
          pointRadius: 5,
          pointHoverRadius: 7,
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false,
      },
      plugins: {
        legend: {
          labels: { color: '#94a3b8', font: { family: 'Inter', size: 12 } }
        },
        tooltip: {
          backgroundColor: '#0f172a',
          titleColor: '#38bdf8',
          bodyColor: '#f8fafc',
          borderColor: '#334155',
          borderWidth: 1,
          padding: 10,
          callbacks: {
            label: function(context) {
              return ` ${context.parsed.y} Million Units (MU)`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#64748b' }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: {
            color: '#64748b',
            callback: function(val) { return val + ' MU'; }
          }
        }
      }
    }
  });
}

/**
 * Initializes or updates the Circle Clusters Scatter/Bubble Chart
 * @param {Array} clusterData - Array of circle records from /api/v1/dashboard/clusters
 */
function renderClustersChart(clusterData) {
  const ctx = document.getElementById('clustersChart');
  if (!ctx) return;

  const clusterColors = [
    '#3b82f6', // Cluster 0: Blue
    '#10b981', // Cluster 1: Emerald
    '#ef4444', // Cluster 2: Red
    '#f59e0b'  // Cluster 3: Amber
  ];

  const clusterLabels = [
    'Cluster 0 (Moderate Urban)',
    'Cluster 1 (High Metro Demand)',
    'Cluster 2 (High Disruption / Mining)',
    'Cluster 3 (Rural / Low Load)'
  ];

  const datasets = [0, 1, 2, 3].map(clusterId => {
    const circlesInCluster = clusterData.filter(c => c.cluster === clusterId);
    return {
      label: clusterLabels[clusterId],
      data: circlesInCluster.map(c => ({
        x: parseFloat((c.avg_load_factor * 100).toFixed(2)),
        y: parseFloat((c.disruption_rate * 100).toFixed(2)),
        r: Math.max(6, Math.min(20, Math.sqrt(c.total_units / 5000000))),
        circleName: c.Circle,
        avgUnits: c.avg_units,
        disruptionRate: (c.disruption_rate * 100).toFixed(1) + '%'
      })),
      backgroundColor: clusterColors[clusterId] + '99',
      borderColor: clusterColors[clusterId],
      borderWidth: 1.5,
      hoverBorderWidth: 2.5
    };
  });

  if (clusterChartInstance) {
    clusterChartInstance.destroy();
  }

  clusterChartInstance = new Chart(ctx, {
    type: 'bubble',
    data: { datasets: datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
        },
        tooltip: {
          backgroundColor: '#0f172a',
          titleColor: '#38bdf8',
          bodyColor: '#f8fafc',
          borderColor: '#334155',
          borderWidth: 1,
          callbacks: {
            title: function(items) {
              const raw = items[0].raw;
              return raw.circleName || 'Circle';
            },
            label: function(item) {
              const raw = item.raw;
              return [
                ` Load Factor: ${raw.x}%`,
                ` Disruption Rate: ${raw.y}%`,
                ` Avg Monthly Units: ${Math.round(raw.avgUnits).toLocaleString()} kWh`
              ];
            }
          }
        }
      },
      scales: {
        x: {
          title: {
            display: true,
            text: 'Average Load Factor (%)',
            color: '#94a3b8',
            font: { size: 12 }
          },
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#64748b' }
        },
        y: {
          title: {
            display: true,
            text: 'Historical Disruption Rate (%)',
            color: '#94a3b8',
            font: { size: 12 }
          },
          grid: { color: 'rgba(255, 255, 255, 0.05)' },
          ticks: { color: '#64748b' }
        }
      }
    }
  });
}
