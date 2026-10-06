/**
 * GridMind AI — Role-Based UI Controller
 * =======================================
 * Handles:
 *  - Token management (storage, refresh, expiry)
 *  - Role-based navigation rendering (PUBLIC / AE / DE)
 *  - Authenticated API calls with automatic token refresh
 *  - Logout
 *
 * NOTE: All security decisions are enforced server-side.
 * Frontend UI changes are PRESENTATION ONLY.
 */

const API = '/api/v1';

// ---------------------------------------------------------------------------
// Token Management
// ---------------------------------------------------------------------------

const Auth = {
  getToken: () => sessionStorage.getItem('gridmind_token'),
  getRefreshToken: () => sessionStorage.getItem('gridmind_refresh_token'),
  getUser: () => {
    const raw = sessionStorage.getItem('gridmind_user');
    try { return raw ? JSON.parse(raw) : null; } catch { return null; }
  },
  getRole: () => Auth.getUser()?.role || null,
  isLoggedIn: () => !!Auth.getToken(),

  store: (data) => {
    sessionStorage.setItem('gridmind_token', data.access_token);
    sessionStorage.setItem('gridmind_refresh_token', data.refresh_token);
    sessionStorage.setItem('gridmind_user', JSON.stringify(data.user));
  },

  clear: () => {
    sessionStorage.removeItem('gridmind_token');
    sessionStorage.removeItem('gridmind_refresh_token');
    sessionStorage.removeItem('gridmind_user');
  },

  async refresh() {
    const refreshToken = Auth.getRefreshToken();
    if (!refreshToken) return false;
    try {
      const resp = await fetch(`${API}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (resp.ok) {
        const data = await resp.json();
        sessionStorage.setItem('gridmind_token', data.access_token);
        return true;
      }
    } catch (e) { /* network error */ }
    return false;
  },
};

// ---------------------------------------------------------------------------
// Authenticated Fetch (auto-refresh on 401)
// ---------------------------------------------------------------------------

async function apiFetch(url, options = {}) {
  const token = Auth.getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  let resp = await fetch(url, { ...options, headers });

  // Try token refresh once on 401
  if (resp.status === 401 && Auth.getRefreshToken()) {
    const refreshed = await Auth.refresh();
    if (refreshed) {
      headers.Authorization = `Bearer ${Auth.getToken()}`;
      resp = await fetch(url, { ...options, headers });
    }
  }

  if (resp.status === 401 || resp.status === 403) {
    // Clear session on persistent auth failure
    if (resp.status === 401) {
      Auth.clear();
      window.location.href = '/login.html';
      return null;
    }
  }

  return resp;
}

// ---------------------------------------------------------------------------
// Navigation Menus (Role-Based)
// ---------------------------------------------------------------------------

const NAV_CONFIG = {
  PUBLIC: [
    { label: '🏠 Home',             href: '/index.html' },
    { label: '📊 Public Dashboard', href: '#public-dashboard' },
    { label: '📈 Energy Trends',    href: '#energy-trends' },
    { label: '🚨 Public Alerts',    href: '#public-alerts' },
    { label: 'ℹ️ About GridMind',    href: '#about' },
    { label: '🔐 Login',            href: '/login.html' },
  ],
  AE: [
    { label: '📊 Dashboard',        href: '/dashboard.html' },
    { label: '⚡ Live Energy',       href: '#live-energy' },
    { label: '🔍 Anomalies',         href: '#anomalies' },
    { label: '🤖 Predictions',       href: '#predictions' },
    { label: '🚨 Alerts',            href: '#alerts' },
    { label: '🗂️ My Division',       href: '#my-division' },
    { label: '📋 Reports',           href: '#reports' },
    { label: '👤 Profile',           href: '#profile' },
    { label: '🚪 Logout',            href: '#', id: 'logoutBtn' },
  ],
  DE: [
    { label: '📊 Dashboard',        href: '/de_dashboard.html' },
    { label: '🗺️ Division Monitor', href: '#divisions' },
    { label: '⚡ Live Energy',       href: '#live-energy' },
    { label: '🔍 Anomalies',         href: '#anomalies' },
    { label: '🤖 Predictions',       href: '#predictions' },
    { label: '🚨 Alerts',            href: '#alerts' },
    { label: '👷 AE Management',     href: '#ae-management' },
    { label: '📋 Reports',           href: '#reports' },
    { label: '📜 Audit Logs',        href: '#audit-logs' },
    { label: '👤 Profile',           href: '#profile' },
    { label: '🚪 Logout',            href: '#', id: 'logoutBtn' },
  ],
};

/**
 * Inject role-appropriate navigation into a container element.
 * @param {string} containerId - CSS selector or element ID for nav container
 */
function renderNav(containerId = 'gridmind-nav') {
  const container = document.getElementById(containerId);
  if (!container) return;

  const role = Auth.getRole();
  const items = NAV_CONFIG[role] || NAV_CONFIG.PUBLIC;

  container.innerHTML = items.map(item => `
    <a href="${item.href}" ${item.id ? `id="${item.id}"` : ''} class="nav-link">
      ${item.label}
    </a>
  `).join('');

  // Attach logout handler
  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      await logout();
    });
  }

  // Show user badge if logged in
  const user = Auth.getUser();
  if (user) {
    const badge = document.getElementById('user-badge');
    if (badge) {
      badge.textContent = `${user.name || user.username} (${user.role})`;
      badge.style.display = 'inline-block';
    }
  }
}

// ---------------------------------------------------------------------------
// Logout
// ---------------------------------------------------------------------------

async function logout() {
  const refreshToken = Auth.getRefreshToken();
  try {
    await apiFetch(`${API}/auth/logout`, {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  } catch (e) { /* ignore network errors on logout */ }
  Auth.clear();
  window.location.href = '/login.html';
}

// ---------------------------------------------------------------------------
// Guard: require authentication for a page
// ---------------------------------------------------------------------------

function requireAuth(allowedRoles = ['AE', 'DE']) {
  if (!Auth.isLoggedIn()) {
    window.location.href = '/login.html';
    return false;
  }
  const role = Auth.getRole();
  if (!allowedRoles.includes(role)) {
    // Redirect to appropriate page
    if (role === 'AE') {
      window.location.href = '/dashboard.html';
    } else {
      window.location.href = '/login.html';
    }
    return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// Public API helpers (no auth required)
// ---------------------------------------------------------------------------

async function fetchPublicEnergySummary() {
  const resp = await fetch(`${API}/public/energy-summary`);
  if (resp.ok) return resp.json();
  return null;
}

async function fetchPublicAlerts() {
  const resp = await fetch(`${API}/public/alerts`);
  if (resp.ok) return resp.json();
  return null;
}

// ---------------------------------------------------------------------------
// Auto-init on DOMContentLoaded
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  renderNav('gridmind-nav');
});

// Export for module usage
if (typeof module !== 'undefined') {
  module.exports = { Auth, apiFetch, renderNav, logout, requireAuth };
}
