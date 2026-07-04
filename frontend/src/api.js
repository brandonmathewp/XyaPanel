const BASE = '/api';

async function request(path, options = {}) {
  const token = localStorage.getItem('token');
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return data;
}

export const api = {
  // Health
  health: () => request('/health'),

  // Auth
  adminLogin: (email, password) => request('/auth/admin/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  resellerLogin: (username, password) => request('/auth/reseller/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  resellerRegister: (body) => request('/auth/reseller/register', { method: 'POST', body: JSON.stringify(body) }),
  generateInviteCodes: (count, expiresInHours) => request('/auth/admin/invite-codes/generate?count=' + count + '&expires_in_hours=' + expiresInHours, { method: 'POST' }),
  listInviteCodes: () => request('/auth/admin/invite-codes'),

  // Licenses
  generateLicense: (body) => request('/licenses/admin/generate', { method: 'POST', body: JSON.stringify(body) }),
  listLicenses: (params = '') => request('/licenses/admin/list?' + params),
  getLicense: (key) => request(`/licenses/admin/${encodeURIComponent(key)}`),
  revokeLicense: (key) => request(`/licenses/admin/${encodeURIComponent(key)}/revoke`, { method: 'POST' }),
  pauseLicense: (key) => request(`/licenses/admin/${encodeURIComponent(key)}/pause`, { method: 'POST' }),
  resumeLicense: (key) => request(`/licenses/admin/${encodeURIComponent(key)}/resume`, { method: 'POST' }),

  // Products
  createProduct: (body) => request('/products/admin', { method: 'POST', body: JSON.stringify(body) }),
  listProducts: (params = '') => request('/products/admin?' + params),
  getProduct: (id) => request(`/products/admin/${encodeURIComponent(id)}`),
  updateProduct: (id, body) => request(`/products/admin/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteProduct: (id) => request(`/products/admin/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  storeProducts: (params = '') => request('/products/store?' + params),

  // Reseller
  resellerStore: (params = '') => request('/reseller/store?' + params),
  purchaseStock: (body) => request('/reseller/store/purchase', { method: 'POST', body: JSON.stringify(body) }),
  generateResellerKey: (body) => request('/reseller/generate-key', { method: 'POST', body: JSON.stringify(body) }),
  resellerKeys: (params = '') => request('/reseller/keys?' + params),
  resellerLedger: (params = '') => request('/reseller/ledger?' + params),
  adminCredit: (body) => request('/reseller/admin/credit', { method: 'POST', body: JSON.stringify(body) }),
};

export default api;
