const API = {
  _silent: false,

  async request(method, url, body = null) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (res.status === 401 && !url.includes('/login')) {
      if (!this._silent) window.location.hash = '#/login';
      throw new Error('Unauthorized');
    }
    const data = await res.json();
    if (res.status === 202) { data._status = 202; return data; }
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  },

  async silentGet(url) {
    this._silent = true;
    try { return await this.request('GET', url); }
    finally { this._silent = false; }
  },

  get(url) { return this.request('GET', url); },
  post(url, body) { return this.request('POST', url, body); },
  put(url, body) { return this.request('PUT', url, body); },
  del(url) { return this.request('DELETE', url); },

  // Admin auth
  login(username, password, totp_code = '') { return this.post('/admin/api/login', { username, password, totp_code }); },
  logout() { return this.post('/admin/api/logout'); },
  me() { return this.silentGet('/admin/api/me'); },

  // 2FA
  setup2FA() { return this.post('/admin/api/2fa/setup'); },
  verify2FA(code) { return this.post('/admin/api/2fa/verify', { code }); },
  disable2FA(code) { return this.post('/admin/api/2fa/disable', { code }); },

  // Dashboard
  dashboard() { return this.get('/admin/api/dashboard'); },
  serverInfo() { return this.get('/admin/api/server-info'); },

  // Devices
  devices(page = 1, search = '') {
    return this.get(`/admin/api/devices?page=${page}&per_page=20&search=${encodeURIComponent(search)}`);
  },
  device(id) { return this.get(`/admin/api/devices/${encodeURIComponent(id)}`); },
  deviceStats() { return this.get('/admin/api/devices/stats'); },
  updateDeviceTags(id, data) { return this.put(`/admin/api/devices/${encodeURIComponent(id)}/tags`, data); },
  deleteDevice(id) { return this.del(`/admin/api/devices/${encodeURIComponent(id)}`); },

  // Users
  users(page = 1, search = '') {
    return this.get(`/admin/api/users?page=${page}&per_page=20&search=${encodeURIComponent(search)}`);
  },
  createUser(data) { return this.post('/admin/api/users', data); },
  updateUser(id, data) { return this.put(`/admin/api/users/${id}`, data); },
  deleteUser(id) { return this.del(`/admin/api/users/${id}`); },
  userAddressBook(id) { return this.get(`/admin/api/users/${id}/address-book`); },

  // Groups
  groups() { return this.get('/admin/api/groups'); },
  createGroup(data) { return this.post('/admin/api/groups', data); },
  updateGroup(id, data) { return this.put(`/admin/api/groups/${id}`, data); },
  deleteGroup(id) { return this.del(`/admin/api/groups/${id}`); },

  // Address books
  addressBooks(page = 1) { return this.get(`/admin/api/address-books?page=${page}`); },
  addressBook(id) { return this.get(`/admin/api/address-books/${id}`); },
  updateAddressBook(id, data) { return this.put(`/admin/api/address-books/${id}`, data); },
  deleteAddressBook(id) { return this.del(`/admin/api/address-books/${id}`); },

  // Logs
  connectionLogs(page = 1, search = '') {
    return this.get(`/admin/api/connection-logs?page=${page}&per_page=30&search=${encodeURIComponent(search)}`);
  },
  fileAudits(page = 1) { return this.get(`/admin/api/file-audits?page=${page}`); },
  auditLogs(page = 1) { return this.get(`/admin/api/audit-logs?page=${page}`); },

  // Settings
  settings() { return this.get('/admin/api/settings'); },
  updateSettings(data) { return this.put('/admin/api/settings', data); },
  deleteSetting(key) { return this.del(`/admin/api/settings/${encodeURIComponent(key)}`); },

  // API Keys
  apiKeys() { return this.get('/admin/api/api-keys'); },
  createApiKey(data) { return this.post('/admin/api/api-keys', data); },
  deleteApiKey(id) { return this.del(`/admin/api/api-keys/${id}`); },
  toggleApiKey(id) { return this.post(`/admin/api/api-keys/${id}/toggle`); },

  // Deploy
  deployConfig() { return this.get('/admin/api/deploy/config'); },
  updateDeployConfig(data) { return this.put('/admin/api/deploy/config', data); },
  async deployScript(platform, password = 'random') {
    const res = await fetch(`/admin/api/deploy/script/${platform}?password=${encodeURIComponent(password)}`, { credentials: 'include' });
    if (!res.ok) { const d = await res.json(); throw new Error(d.error || `HTTP ${res.status}`); }
    return res.text();
  },
};
