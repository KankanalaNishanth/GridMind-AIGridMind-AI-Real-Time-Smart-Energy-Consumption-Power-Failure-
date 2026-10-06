/**
 * GridMind AI — Main Frontend Application Logic
 */

// API Configuration — auto-detect backend URL
const API_BASE = window.location.origin.includes('http') && !window.location.protocol.startsWith('file')
  ? `${window.location.origin}/api/v1`
  : 'http://localhost:8000/api/v1';

let circlesData = [];
let streamInterval = null;
let authToken = localStorage.getItem('gridmind_auth_token') || null;
let currentUser = null;

// Initialize on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  initClock();
  initThemeToggle();
  initTabs();
  initAuth();
  setupSecurityTab();
  checkSystemHealth();
  loadDashboardSummary();
  loadCirclesData();
  setupPredictionForm();
  setupAnomalyForm();
  setupForecastControls();
  setupStreamSimulator();
  loadEvaluationSummary();
});

/* ==========================================================================
   Clock & Header Status
   ========================================================================== */
function initClock() {
  const clockEl = document.getElementById('liveClock');
  if (!clockEl) return;
  const update = () => {
    const now = new Date();
    clockEl.innerText = now.toLocaleTimeString() + ' | ' + now.toLocaleDateString();
  };
  update();
  setInterval(update, 1000);
}

function initThemeToggle() {
  const btn = document.getElementById('themeToggleBtn');
  if (!btn) return;
  btn.addEventListener('click', () => {
    const current = document.body.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    document.body.setAttribute('data-theme', next);
    btn.innerHTML = next === 'dark' ? '🌙 Dark' : '☀️ Light';
  });
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${type === 'danger' ? '⚠️' : type === 'success' ? '✅' : 'ℹ️'}</span> ${message}`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* ==========================================================================
   Authentication & Role-Based Access Control (RBAC) System
   ========================================================================== */

async function authFetch(url, options = {}) {
  options.headers = options.headers || {};
  if (authToken) {
    options.headers['Authorization'] = `Bearer ${authToken}`;
  }
  const res = await fetch(url, options);
  if (res.status === 401) {
    handleUnauthorized();
  }
  return res;
}

function handleUnauthorized() {
  localStorage.removeItem('gridmind_auth_token');
  localStorage.removeItem('gridmind_auth_user');
  authToken = null;
  currentUser = null;
  updateHeaderUserUI(null);
  applyRoleRestrictions(null);
  openLoginModal();
  showToast('Session expired or authentication required.', 'danger');
}

function initAuth() {
  setupRolePills();
  setupLoginForm();
  setupHeaderAuthButtons();

  // Check saved session
  if (authToken) {
    verifySession();
  } else {
    // Immediately display login modal on browser launch for security
    openLoginModal();
  }
}

async function verifySession() {
  try {
    const res = await authFetch(`${API_BASE}/auth/me`);
    if (res.ok) {
      currentUser = await res.json();
      localStorage.setItem('gridmind_auth_user', JSON.stringify(currentUser));
      updateHeaderUserUI(currentUser);
      applyRoleRestrictions(currentUser);
      closeLoginModal();
      loadSecurityAuditLogs();
    } else {
      openLoginModal();
    }
  } catch (e) {
    console.warn('Session verification error:', e);
    openLoginModal();
  }
}

function setupRolePills() {
  const pills = document.querySelectorAll('.role-pill-btn');
  const userInput = document.getElementById('authUsernameInput');
  const passInput = document.getElementById('authPasswordInput');

  pills.forEach(pill => {
    pill.addEventListener('click', () => {
      pills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');

      const user = pill.getAttribute('data-user');
      const pass = pill.getAttribute('data-pass');
      if (userInput && user) userInput.value = user;
      if (passInput && pass) passInput.value = pass;
    });
  });
}

function setupLoginForm() {
  const form = document.getElementById('authLoginForm');
  const errBox = document.getElementById('authErrorMsg');
  const errText = document.getElementById('authErrorText');
  const submitBtn = document.getElementById('authSubmitBtn');

  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (errBox) errBox.style.display = 'none';
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span>⏳</span> Verifying Credentials...';
    }

    const username = document.getElementById('authUsernameInput')?.value.trim();
    const password = document.getElementById('authPasswordInput')?.value;

    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Authentication failed.');
      }

      authToken = data.access_token;
      currentUser = data.user;
      localStorage.setItem('gridmind_auth_token', authToken);
      localStorage.setItem('gridmind_auth_user', JSON.stringify(currentUser));

      updateHeaderUserUI(currentUser);
      applyRoleRestrictions(currentUser);
      closeLoginModal();
      showToast(`Authenticated as ${currentUser.name} (${currentUser.role_label})`, 'success');
      loadSecurityAuditLogs();

    } catch (err) {
      if (errBox && errText) {
        errText.innerText = err.message || 'Invalid username or password.';
        errBox.style.display = 'flex';
      }
      showToast(err.message || 'Login failed', 'danger');
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>🔐</span> Sign In to Grid Mind Platform';
      }
    }
  });
}

function setupHeaderAuthButtons() {
  const loginTrigger = document.getElementById('loginTriggerBtn');
  const logoutBtn = document.getElementById('logoutBtn');

  if (loginTrigger) {
    loginTrigger.addEventListener('click', () => openLoginModal());
  }

  if (logoutBtn) {
    logoutBtn.addEventListener('click', handleLogout);
  }
}

async function handleLogout() {
  if (authToken) {
    try {
      await authFetch(`${API_BASE}/auth/logout`, { method: 'POST' });
    } catch (e) {
      console.warn('Logout notification error:', e);
    }
  }

  localStorage.removeItem('gridmind_auth_token');
  localStorage.removeItem('gridmind_auth_user');
  authToken = null;
  currentUser = null;

  updateHeaderUserUI(null);
  applyRoleRestrictions(null);
  showToast('Logged out safely.', 'info');
  openLoginModal();
}

function openLoginModal() {
  const modal = document.getElementById('authModalOverlay');
  if (modal) modal.classList.add('active');
}

function closeLoginModal() {
  const modal = document.getElementById('authModalOverlay');
  if (modal) modal.classList.remove('active');
}

function updateHeaderUserUI(user) {
  const badge = document.getElementById('headerUserBadge');
  const nameEl = document.getElementById('headerUserName');
  const roleEl = document.getElementById('headerUserRole');
  const iconEl = document.getElementById('headerUserIcon');
  const logoutBtn = document.getElementById('logoutBtn');
  const loginTrigger = document.getElementById('loginTriggerBtn');

  if (!badge) return;

  if (user) {
    badge.style.display = 'flex';
    if (logoutBtn) logoutBtn.style.display = 'inline-flex';
    if (loginTrigger) loginTrigger.style.display = 'none';

    if (nameEl) nameEl.innerText = user.name || user.username;

    // Support both new RBAC roles (DE/AE) and legacy roles
    const roleMap = {
      'DE':             { label: 'Divisional Engineer', icon: '🏛️' },
      'AE':             { label: 'Asst. Engineer',      icon: '👷' },
      'admin':          { label: 'Super Admin',          icon: '⚡' },
      'security_admin': { label: 'Security Admin',       icon: '🛡️' },
      'operator':       { label: 'Grid Operator',        icon: '📊' },
    };
    const roleInfo = roleMap[user.role] || { label: user.role_label || user.role, icon: '👤' };
    if (roleEl) {
      roleEl.innerText = roleInfo.label;
      roleEl.className = `user-badge-role ${user.role}`;
    }
    if (iconEl) iconEl.innerText = roleInfo.icon;
  } else {
    badge.style.display = 'none';
    if (logoutBtn) logoutBtn.style.display = 'none';
    if (loginTrigger) loginTrigger.style.display = 'inline-flex';
  }
}

function applyRoleRestrictions(user) {
  // Highlight active user card in Security tab
  document.querySelectorAll('.security-user-card').forEach(c => c.classList.remove('active-user'));
  if (user) {
    const card = document.getElementById(`card-user-${user.username}`);
    if (card) card.classList.add('active-user');
  }

  // Stream simulation restriction
  const simBtn = document.getElementById('btnStartSimulation');
  if (simBtn) {
    if (user && user.role === 'operator') {
      simBtn.disabled = true;
      simBtn.title = '🔒 Restricted: Kafka Stream Simulation requires Super Admin or Security Admin role.';
      simBtn.innerHTML = '🔒 Simulation Restricted (Admin/SecAdmin Only)';
    } else {
      simBtn.disabled = false;
      simBtn.title = 'Run Live Stream Simulation';
      simBtn.innerHTML = '🚀 Run Live Stream Simulation';
    }
  }
}

/* ==========================================================================
   Security & Access Control Tab Operations
   ========================================================================== */
function setupSecurityTab() {
  const refreshBtn = document.getElementById('refreshAuditLogsBtn');
  const simCheckBtn = document.getElementById('simulateSecurityCheckBtn');

  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      loadSecurityAuditLogs();
      showToast('Security audit trail refreshed.', 'info');
    });
  }

  if (simCheckBtn) {
    simCheckBtn.addEventListener('click', async () => {
      try {
        const res = await authFetch(`${API_BASE}/auth/audit-event`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            event_type: 'MANUAL_SECURITY_AUDIT',
            status: 'SUCCESS',
            details: `Manual integrity scan performed by ${currentUser ? currentUser.name : 'Unknown User'}`
          })
        });
        if (res.ok) {
          showToast('Security audit event successfully verified and logged.', 'success');
          loadSecurityAuditLogs();
        }
      } catch (e) {
        showToast('Failed to record security audit check.', 'danger');
      }
    });
  }
}

async function loadSecurityAuditLogs() {
  const tbody = document.getElementById('auditLogsTableBody');
  if (!tbody) return;

  try {
    const res = await authFetch(`${API_BASE}/auth/audit-logs?limit=25`);
    if (!res.ok) {
      if (res.status === 403) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--accent-amber); padding: 1.5rem;">🔒 Access Restricted: Security Audit Logs require Super Admin or Security Admin role.</td></tr>`;
      }
      return;
    }
    const data = await res.json();
    const logs = data.logs || [];

    tbody.innerHTML = '';
    if (logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No security events recorded yet.</td></tr>`;
      return;
    }

    logs.forEach(item => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="color: var(--text-muted);">${item.timestamp}</td>
        <td><strong>${item.username}</strong></td>
        <td><span class="user-badge-role ${item.role}" style="font-size: 0.65rem;">${item.role}</span></td>
        <td><code style="color: var(--accent-cyan);">${item.event_type}</code></td>
        <td><span class="audit-status-badge ${item.status}">${item.status}</span></td>
        <td style="color: var(--text-muted);">${item.client_ip}</td>
        <td style="color: var(--text-secondary);">${item.details}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.warn('Failed to load audit logs:', err);
  }
}

/* ==========================================================================
   Tabs Management
   ========================================================================== */
function initTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  const panels = document.querySelectorAll('.tab-panel');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.getAttribute('data-tab');
      tabBtns.forEach(b => b.classList.remove('active'));
      panels.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const panel = document.getElementById(targetId);
      if (panel) panel.classList.add('active');

      // Trigger redraws if charts need resizing
      if (targetId === 'tab-forecasting' && forecastChartInstance) {
        forecastChartInstance.resize();
      }
      if (targetId === 'tab-clustering' && clusterChartInstance) {
        clusterChartInstance.resize();
      }
      if (targetId === 'tab-security') {
        loadSecurityAuditLogs();
      }
    });
  });
}

/* ==========================================================================
   System Health & Overview Data
   ========================================================================== */
async function checkSystemHealth() {
  const indicator = document.getElementById('apiHealthIndicator');
  const text = document.getElementById('apiHealthText');

  try {
    const res = await fetch(`${API_BASE}/health`);
    if (res.ok) {
      const data = await res.json();
      if (indicator) {
        indicator.classList.remove('offline');
      }
      if (text) text.innerText = `API Online (v${data.version || '1.0'})`;
    } else {
      throw new Error();
    }
  } catch {
    if (indicator) indicator.classList.add('offline');
    if (text) text.innerText = 'API Offline';
  }
}

async function loadDashboardSummary() {
  try {
    const res = await authFetch(`${API_BASE}/dashboard/summary`);
    if (!res.ok) throw new Error();
    const data = await res.json();

    const totalEl = document.getElementById('kpiTotalRecords');
    const anomalyEl = document.getElementById('kpiAnomalyCount');
    const circlesEl = document.getElementById('kpiCirclesCount');

    if (totalEl) totalEl.innerText = Number(data.total_records || 156294).toLocaleString();
    if (anomalyEl) anomalyEl.innerText = Number(data.anomaly_count || 7815).toLocaleString();
    if (circlesEl) circlesEl.innerText = `${data.circles || 16} Circles`;
  } catch (e) {
    console.warn('Dashboard summary fallback used', e);
  }
}

async function loadCirclesData() {
  try {
    const res = await authFetch(`${API_BASE}/dashboard/clusters`);
    if (!res.ok) throw new Error();
    circlesData = await res.json();

    populateCircleDropdowns(circlesData);
    renderClustersTable(circlesData);
    renderClustersChart(circlesData);
  } catch (e) {
    console.warn('Could not load clusters from API, using defaults', e);
  }
}

function populateCircleDropdowns(circles) {
  const selects = [document.getElementById('predCircle'), document.getElementById('anomCircle')];
  selects.forEach(select => {
    if (!select) return;
    select.innerHTML = '';
    circles.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.Circle;
      opt.text = c.Circle;
      select.appendChild(opt);
    });
  });
}

/* ==========================================================================
   Disruption & Power Failure Predictor
   ========================================================================== */
function setupPredictionForm() {
  const form = document.getElementById('disruptionForm');
  if (!form) return;

  // Real-time feature calculation listeners
  ['predTotServices', 'predBilledServices', 'predLoad', 'predUnits'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', updateFeaturePreviews);
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    await submitDisruptionPrediction();
  });
}

function updateFeaturePreviews() {
  const tot = parseFloat(document.getElementById('predTotServices')?.value || 1);
  const billed = parseFloat(document.getElementById('predBilledServices')?.value || 0);
  const load = parseFloat(document.getElementById('predLoad')?.value || 1);
  const units = parseFloat(document.getElementById('predUnits')?.value || 0);

  const billingRatio = (billed / Math.max(tot, 1)).toFixed(3);
  const avgUnits = (units / Math.max(billed, 1)).toFixed(1);
  const loadFactor = (units / Math.max(load * 24 * 30, 0.1)).toFixed(3);

  const rRatio = document.getElementById('featBillingRatio');
  const rAvg = document.getElementById('featAvgUnits');
  const rLoad = document.getElementById('featLoadFactor');

  if (rRatio) rRatio.innerText = billingRatio;
  if (rAvg) rAvg.innerText = avgUnits;
  if (rLoad) rLoad.innerText = loadFactor;
}

async function submitDisruptionPrediction() {
  const payload = {
    circle: document.getElementById('predCircle').value,
    tot_services: parseInt(document.getElementById('predTotServices').value),
    billed_services: parseInt(document.getElementById('predBilledServices').value),
    load: parseFloat(document.getElementById('predLoad').value),
    units: parseFloat(document.getElementById('predUnits').value),
    month_num: parseInt(document.getElementById('predMonth').value)
  };

  const btn = document.getElementById('btnSubmitDisruption');
  if (btn) btn.innerText = 'Analyzing with Random Forest...';

  try {
    const res = await authFetch(`${API_BASE}/predict/disruption`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Prediction failed');
    }

    const data = await res.json();
    displayDisruptionResult(data);
    showToast(`Disruption prediction: ${data.label}`, data.alert ? 'danger' : 'success');
  } catch (err) {
    showToast(`Error: ${err.message}`, 'danger');
  } finally {
    if (btn) btn.innerHTML = '⚡ Predict Power Disruption Risk';
  }
}

function displayDisruptionResult(data) {
  const gaugeVal = document.getElementById('disruptionRiskPercent');
  const gaugeCircle = document.getElementById('disruptionGauge');
  const banner = document.getElementById('disruptionAlertBanner');
  const recBox = document.getElementById('disruptionRecommendation');

  const riskPct = Math.round(data.disruption_risk * 100);
  if (gaugeVal) gaugeVal.innerText = `${riskPct}%`;

  if (gaugeCircle) {
    if (data.alert) {
      gaugeCircle.style.background = 'radial-gradient(circle, #3b1616 0%, #1e1b4b 100%)';
      gaugeCircle.style.border = '4px solid #ef4444';
      gaugeVal.style.color = '#ef4444';
    } else {
      gaugeCircle.style.background = 'radial-gradient(circle, #064e3b 0%, #0f172a 100%)';
      gaugeCircle.style.border = '4px solid #10b981';
      gaugeVal.style.color = '#10b981';
    }
  }

  if (banner) {
    banner.className = `alert-banner ${data.alert ? 'danger' : 'success'}`;
    banner.innerHTML = data.alert
      ? '⚠️ HIGH DISRUPTION RISK ALERT — Potential Power Failure Detected'
      : '✅ NORMAL GRID CONDITIONS — Feeder Within Safe Load Threshold';
  }

  if (recBox) {
    if (data.alert) {
      recBox.innerHTML = `<strong>Dispatch Recommendation:</strong> Dispatch maintenance crew to Circle <em>${data.circle}</em> immediately. Feeder exhibits severe load distress and abnormal billing ratio. Implement proactive load balancing to avoid substation trip.`;
    } else {
      recBox.innerHTML = `<strong>Dispatch Recommendation:</strong> Feeder operational parameters for Circle <em>${data.circle}</em> are stable. Continue automated smart meter telemetry monitoring.`;
    }
  }
}

// Preset Loader for Disruption Testing
window.loadDisruptionPreset = function(type) {
  const presets = {
    highRisk: {
      circle: 'BHUPALAPALLY',
      tot_services: 950,
      billed_services: 0,
      load: 850,
      units: 0,
      month_num: 15
    },
    normalResidential: {
      circle: 'HANUMAKONDA',
      tot_services: 750,
      billed_services: 680,
      load: 320,
      units: 54000,
      month_num: 6
    },
    industrialHeavy: {
      circle: 'KARIMNAGAR',
      tot_services: 920,
      billed_services: 890,
      load: 1400,
      units: 180000,
      month_num: 10
    },
    subsidizedAgri: {
      circle: 'KAMAREDDY',
      tot_services: 450,
      billed_services: 320,
      load: 350,
      units: 28000,
      month_num: 8
    }
  };

  const p = presets[type];
  if (!p) return;

  document.getElementById('predCircle').value = p.circle;
  document.getElementById('predTotServices').value = p.tot_services;
  document.getElementById('predBilledServices').value = p.billed_services;
  document.getElementById('predLoad').value = p.load;
  document.getElementById('predUnits').value = p.units;
  document.getElementById('predMonth').value = p.month_num;

  updateFeaturePreviews();
  showToast(`Loaded ${type} preset`);
};

/* ==========================================================================
   Smart Meter Anomaly Detector (Isolation Forest)
   ========================================================================== */
function setupAnomalyForm() {
  const form = document.getElementById('anomalyForm');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    await submitAnomalyDetection();
  });
}

async function submitAnomalyDetection() {
  const payload = {
    circle: document.getElementById('anomCircle').value,
    tot_services: parseInt(document.getElementById('anomTotServices').value),
    billed_services: parseInt(document.getElementById('anomBilledServices').value),
    load: parseFloat(document.getElementById('anomLoad').value),
    units: parseFloat(document.getElementById('anomUnits').value),
    month_num: parseInt(document.getElementById('anomMonth').value)
  };

  const btn = document.getElementById('btnSubmitAnomaly');
  if (btn) btn.innerText = 'Calculating Isolation Forest Score...';

  try {
    const res = await authFetch(`${API_BASE}/predict/anomaly`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Anomaly detection failed');
    }

    const data = await res.json();
    displayAnomalyResult(data);
    showToast(data.is_anomaly ? 'Meter Anomaly Flagged!' : 'Meter Reading Verified Normal', data.is_anomaly ? 'danger' : 'success');
  } catch (err) {
    showToast(`Error: ${err.message}`, 'danger');
  } finally {
    if (btn) btn.innerHTML = '🔍 Run Isolation Forest Anomaly Scan';
  }
}

function displayAnomalyResult(data) {
  const scoreVal = document.getElementById('anomScoreValue');
  const banner = document.getElementById('anomAlertBanner');
  const expBox = document.getElementById('anomExplanation');

  if (scoreVal) {
    scoreVal.innerText = data.anomaly_score.toFixed(4);
    scoreVal.style.color = data.is_anomaly ? '#ef4444' : '#10b981';
  }

  if (banner) {
    banner.className = `alert-banner ${data.is_anomaly ? 'danger' : 'success'}`;
    banner.innerHTML = data.is_anomaly
      ? '🚨 SMART METER ANOMALY DETECTED — Possible Theft, Tampering or Defective Sensor'
      : '✅ NORMAL SMART METER READING — Consonant with Consumption Profile';
  }

  if (expBox) {
    if (data.is_anomaly) {
      expBox.innerHTML = `<strong>Isolation Forest Analysis:</strong> Score is below the anomaly alert threshold (-0.1). Feeder reading shows stark divergence between connected load and reported consumption units. Recommend physical inspection of smart meter seal and current transformers.`;
    } else {
      expBox.innerHTML = `<strong>Isolation Forest Analysis:</strong> Isolation depth score indicates normal multidimensional distribution. Energy consumption aligns with expected historical baseline.`;
    }
  }
}

window.loadAnomalyPreset = function(type) {
  const presets = {
    theftZero: {
      circle: 'PEDDAPALLY',
      tot_services: 500,
      billed_services: 0,
      load: 600,
      units: 0,
      month_num: 12
    },
    surgeAnomaly: {
      circle: 'NIZAMABAD',
      tot_services: 300,
      billed_services: 290,
      load: 50,
      units: 180000,
      month_num: 7
    },
    normalMeter: {
      circle: 'WARANGAL',
      tot_services: 650,
      billed_services: 620,
      load: 320,
      units: 48000,
      month_num: 5
    }
  };

  const p = presets[type];
  if (!p) return;

  document.getElementById('anomCircle').value = p.circle;
  document.getElementById('anomTotServices').value = p.tot_services;
  document.getElementById('anomBilledServices').value = p.billed_services;
  document.getElementById('anomLoad').value = p.load;
  document.getElementById('anomUnits').value = p.units;
  document.getElementById('anomMonth').value = p.month_num;

  showToast(`Loaded ${type} preset`);
};

/* ==========================================================================
   Energy Demand Forecasting (SARIMA)
   ========================================================================== */
function setupForecastControls() {
  const slider = document.getElementById('forecastStepsSlider');
  const valDisplay = document.getElementById('forecastStepsValue');
  const btn = document.getElementById('btnRunForecast');

  if (slider && valDisplay) {
    slider.addEventListener('input', () => {
      valDisplay.innerText = `${slider.value} Months`;
    });
  }

  if (btn) {
    btn.addEventListener('click', () => {
      const steps = parseInt(slider ? slider.value : 6);
      fetchForecast(steps);
    });
  }

  // Load initial 6-month forecast
  fetchForecast(6);
}

async function fetchForecast(steps = 6) {
  const btn = document.getElementById('btnRunForecast');
  if (btn) btn.innerText = 'Calculating SARIMA Forecast...';

  try {
    const res = await authFetch(`${API_BASE}/predict/forecast?steps=${steps}`);
    if (!res.ok) throw new Error('Forecast calculation failed');
    const data = await res.json();

    renderForecastChart(data.forecast);
    renderForecastTable(data.forecast);
    showToast(`Generated ${steps}-Month SARIMA Forecast`, 'success');
  } catch (err) {
    showToast(`Forecast error: ${err.message}`, 'danger');
  } finally {
    if (btn) btn.innerHTML = '📈 Generate Forecast';
  }
}

function renderForecastTable(forecast) {
  const tbody = document.getElementById('forecastTableBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  forecast.forEach((pt, idx) => {
    const kwh = Math.round(pt.predicted_units);
    const mwh = (pt.predicted_units / 1000).toFixed(1);
    const mu = (pt.predicted_units / 1000000).toFixed(2);

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>Month ${pt.month}</strong></td>
      <td>${mu} MU</td>
      <td>${Number(mwh).toLocaleString()} MWh</td>
      <td>${kwh.toLocaleString()} kWh</td>
      <td><span class="cluster-tag cluster-1">Projected</span></td>
    `;
    tbody.appendChild(tr);
  });
}

/* ==========================================================================
   Circle Clustering & Segmentation (K-Means)
   ========================================================================== */
function renderClustersTable(circles) {
  const tbody = document.getElementById('clustersTableBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const clusterLabels = [
    { name: 'Moderate Urban', class: 'cluster-0' },
    { name: 'High Metro Demand', class: 'cluster-1' },
    { name: 'Heavy Disruption / Coal Belt', class: 'cluster-2' },
    { name: 'Rural Low Load', class: 'cluster-3' }
  ];

  circles.forEach(c => {
    const tr = document.createElement('tr');
    const cMeta = clusterLabels[c.cluster] || { name: `Cluster ${c.cluster}`, class: 'cluster-0' };

    tr.innerHTML = `
      <td><strong>${c.Circle}</strong></td>
      <td><span class="cluster-tag ${cMeta.class}">${cMeta.name}</span></td>
      <td>${Math.round(c.avg_units).toLocaleString()} kWh</td>
      <td>${(c.total_units / 1000000).toFixed(1)} MU</td>
      <td>${Math.round(c.avg_connections)}</td>
      <td>${(c.avg_billing_ratio * 100).toFixed(1)}%</td>
      <td>${(c.avg_load_factor * 100).toFixed(1)}%</td>
      <td><strong style="color: ${c.disruption_rate > 0.45 ? '#ef4444' : '#10b981'}">${(c.disruption_rate * 100).toFixed(1)}%</strong></td>
    `;
    tbody.appendChild(tr);
  });
}

/* ==========================================================================
   Live Telemetry & Kafka Stream Simulator
   ========================================================================== */
function setupStreamSimulator() {
  const btn = document.getElementById('btnStartSimulation');
  if (!btn) return;

  btn.addEventListener('click', async () => {
    const count = parseInt(document.getElementById('streamCountInput')?.value || 25);
    await runStreamSimulation(count);
  });
}

async function runStreamSimulation(n = 25) {
  const btn = document.getElementById('btnStartSimulation');
  const termBody = document.getElementById('streamTerminalBody');
  const countEl = document.getElementById('streamProcessedCount');
  const alertEl = document.getElementById('streamAlertCount');

  if (btn) {
    btn.disabled = true;
    btn.innerText = '⚡ Streaming & ML Scoring in progress...';
  }

  try {
    const res = await authFetch(`${API_BASE}/stream/simulate?n=${n}`, { method: 'POST' });
    if (res.status === 403) {
      throw new Error('Action Denied: Kafka Live Stream Simulation requires Super Admin or Security Admin role.');
    }
    if (!res.ok) throw new Error('Simulation failed');
    const data = await res.json();

    const records = data.records || data.sample || [];
    if (countEl) countEl.innerText = data.messages_processed;
    if (alertEl) alertEl.innerText = data.alerts_generated;

    if (termBody) termBody.innerHTML = '';

    // Animate streaming packet by packet
    let index = 0;
    if (streamInterval) clearInterval(streamInterval);

    streamInterval = setInterval(() => {
      if (index >= records.length) {
        clearInterval(streamInterval);
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '🚀 Run Live Stream Simulation';
        }
        showToast(`Simulation complete: ${data.alerts_generated} alerts flagged`, data.alerts_generated > 0 ? 'danger' : 'success');
        return;
      }

      const p = records[index];
      const row = document.createElement('div');
      row.className = 'stream-row';

      const time = p.timestamp ? p.timestamp.split(' ')[1].slice(0, 8) : new Date().toLocaleTimeString();
      row.innerHTML = `
        <span class="stream-time">[${time}]</span>
        <span class="stream-circle">${p.circle}</span>
        <span class="stream-units">${Math.round(p.units)} kWh</span>
        <span class="stream-score">Disrupt: ${(p.disruption_risk * 100).toFixed(0)}%</span>
        <span class="stream-badge ${p.alert ? 'alert' : 'normal'}">${p.alert ? 'ALERT' : 'OK'}</span>
      `;

      if (termBody) {
        termBody.prepend(row);
      }
      index++;
    }, 120);

  } catch (err) {
    showToast(`Stream error: ${err.message}`, 'danger');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '🚀 Run Live Stream Simulation';
    }
  }
}

/* ==========================================================================
   Model Evaluation & Reports
   ========================================================================== */
async function loadEvaluationSummary() {
  try {
    const res = await authFetch(`${API_BASE}/evaluate/summary`);
    if (!res.ok) return;
    const data = await res.json();

    const rfEl = document.getElementById('evalRfAuc');
    const isoEl = document.getElementById('evalIsoCount');
    const sarimaEl = document.getElementById('evalSarimaMape');

    if (rfEl && data.random_forest) {
      rfEl.innerText = data.random_forest.roc_auc.toFixed(4);
    }
    if (isoEl && data.isolation_forest) {
      isoEl.innerText = `${data.isolation_forest.anomalies_detected} (${data.isolation_forest.anomaly_rate_pct}%)`;
    }
    if (sarimaEl && data.sarima) {
      sarimaEl.innerText = `${data.sarima.mape_pct.toFixed(2)}%`;
    }
  } catch (e) {
    console.warn('Evaluation summary fetch error', e);
  }
}
