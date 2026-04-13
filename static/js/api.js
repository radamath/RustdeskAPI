const API = {
  async request(method, url, body = null) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (res.status === 401 && !url.includes('/login')) {
      window.location.hash = '#/login';
      throw new Error('Unauthorized');
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  },

  get(url) { return this.request('GET', url); },
  post(url, body) { return this.request('POST', url, body); },
  put(url, body) { return this.request('PUT', url, body); },
  del(url) { return this.request('DELETE', url); },

  // Admin auth
  login(username, password) { return this.post('/admin/api/login', { username, password }); },
  logout() { return this.post('/admin/api/logout'); },
  me() { return this.get('/admin/api/me'); },

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

  // Users
  users(page = 1, search = '') {
    return this.get(`/admin/api/users?page=${page}&per_page=20&search=${encodeURIComponent(search)}`);
  },
  createUser(data) { return this.post('/admin/api/users', data); },
  updateUser(id, data) { return this.put(`/admin/api/users/${id}`, data); },
  deleteUser(id) { return this.del(`/admin/api/users/${id}`); },

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
};
