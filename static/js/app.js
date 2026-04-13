const App = {
  user: null,

  async init() {
    try {
      this.user = await API.me();
      this.showApp();
      this.registerRoutes();
      Router.init();
    } catch {
      this.showLogin();
    }
  },

  showLogin() {
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('login-screen').classList.add('flex');
    document.getElementById('app-shell').classList.add('hidden');
    this.bindLogin();
  },

  showApp() {
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('login-screen').classList.remove('flex');
    document.getElementById('app-shell').classList.remove('hidden');
    if (this.user) {
      document.getElementById('user-name').textContent = this.user.username;
      document.getElementById('user-avatar').textContent = this.user.username[0].toUpperCase();
    }
    // Mobile menu
    const btn = document.getElementById('mobile-menu-btn');
    const sidebar = document.getElementById('sidebar');
    btn?.addEventListener('click', () => sidebar.classList.toggle('open'));
  },

  bindLogin() {
    const btn = document.getElementById('login-btn');
    const uEl = document.getElementById('login-username');
    const pEl = document.getElementById('login-password');
    const errEl = document.getElementById('login-error');

    const doLogin = async () => {
      errEl.classList.add('hidden');
      try {
        this.user = await API.login(uEl.value, pEl.value);
        this.showApp();
        this.registerRoutes();
        Router.init();
      } catch (e) {
        errEl.textContent = e.message;
        errEl.classList.remove('hidden');
      }
    };
    btn.onclick = doLogin;
    pEl.onkeydown = (e) => { if (e.key === 'Enter') doLogin(); };
    uEl.onkeydown = (e) => { if (e.key === 'Enter') pEl.focus(); };
  },

  async logout() {
    try { await API.logout(); } catch {}
    this.user = null;
    this.showLogin();
  },

  registerRoutes() {
    Router.register('/dashboard', Pages.dashboard);
    Router.register('/devices', Pages.devices);
    Router.register('/users', Pages.users);
    Router.register('/groups', Pages.groups);
    Router.register('/address-books', Pages.addressBooks);
    Router.register('/connection-logs', Pages.connectionLogs);
    Router.register('/audit-logs', Pages.auditLogs);
    Router.register('/settings', Pages.settings);
    Router.register('/api-keys', Pages.apiKeys);
    Router.register('/login', () => App.showLogin());
  },
};

// ── Helper functions ───────────────────────────────────────────────

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'className') el.className = v;
    else if (k === 'onclick') el.onclick = v;
    else if (k === 'innerHTML') el.innerHTML = v;
    else el.setAttribute(k, v);
  }
  for (const c of children) {
    if (typeof c === 'string') el.appendChild(document.createTextNode(c));
    else if (c) el.appendChild(c);
  }
  return el;
}

function formatDate(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleString('tr-TR');
}

function pagination(page, total, perPage, onClick) {
  const pages = Math.ceil(total / perPage);
  if (pages <= 1) return document.createDocumentFragment();
  const wrap = h('div', { className: 'flex items-center justify-between mt-4' });
  wrap.appendChild(h('span', { className: 'text-sm text-slate-400' }, `Toplam: ${total}`));
  const btns = h('div', { className: 'flex gap-1' });
  for (let i = 1; i <= Math.min(pages, 10); i++) {
    const cls = i === page
      ? 'px-3 py-1 rounded text-sm bg-blue-600 text-white'
      : 'px-3 py-1 rounded text-sm bg-slate-700 text-slate-300 hover:bg-slate-600 cursor-pointer';
    btns.appendChild(h('button', { className: cls, onclick: () => onClick(i) }, String(i)));
  }
  wrap.appendChild(btns);
  return wrap;
}

function modal(title, bodyEl, onClose) {
  const overlay = h('div', { className: 'modal-overlay', onclick: (e) => { if (e.target === overlay) onClose(); } });
  const box = h('div', { className: 'modal fade-in' });
  const header = h('div', { className: 'flex items-center justify-between mb-4' });
  header.appendChild(h('h3', { className: 'text-lg font-semibold text-white' }, title));
  header.appendChild(h('button', { className: 'text-slate-400 hover:text-white', onclick: onClose, innerHTML: '&times;' }));
  box.appendChild(header);
  box.appendChild(bodyEl);
  overlay.appendChild(box);
  document.body.appendChild(overlay);
  return overlay;
}

function closeModal(overlay) {
  overlay?.remove();
}

function searchBar(placeholder, onSearch) {
  const wrap = h('div', { className: 'flex gap-2 mb-4' });
  const input = h('input', { className: 'input flex-1', placeholder, type: 'text' });
  const btn = h('button', { className: 'btn btn-primary', onclick: () => onSearch(input.value) }, 'Ara');
  input.onkeydown = (e) => { if (e.key === 'Enter') onSearch(input.value); };
  wrap.appendChild(input);
  wrap.appendChild(btn);
  return wrap;
}

// ── Pages ──────────────────────────────────────────────────────────

const Pages = {};

// ── Dashboard ──────────────────────────────────────────────────────

Pages.dashboard = async (el) => {
  const data = await API.dashboard();

  el.innerHTML = '';
  el.appendChild(h('h1', { className: 'text-2xl font-bold text-white mb-6' }, 'Dashboard'));

  // Stat cards
  const grid = h('div', { className: 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8' });

  const stats = [
    { label: 'Toplam Cihaz', value: data.total_peers, color: 'blue', icon: '<svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>' },
    { label: 'Çevrimiçi', value: data.online_peers, color: 'green', icon: '<svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.636 18.364a9 9 0 010-12.728m12.728 0a9 9 0 010 12.728m-9.9-2.829a5 5 0 010-7.07m7.072 0a5 5 0 010 7.07M13 12a1 1 0 11-2 0 1 1 0 012 0z"/></svg>' },
    { label: 'Kullanıcı', value: data.total_users, color: 'purple', icon: '<svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197"/></svg>' },
    { label: 'Toplam Bağlantı', value: data.total_connections, color: 'amber', icon: '<svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>' },
  ];

  const colors = {
    blue: 'from-blue-600/20 to-blue-900/20 border-blue-500/30',
    green: 'from-green-600/20 to-green-900/20 border-green-500/30',
    purple: 'from-purple-600/20 to-purple-900/20 border-purple-500/30',
    amber: 'from-amber-600/20 to-amber-900/20 border-amber-500/30',
  };
  const textColors = { blue: 'text-blue-400', green: 'text-green-400', purple: 'text-purple-400', amber: 'text-amber-400' };

  for (const s of stats) {
    const card = h('div', { className: `stat-card bg-gradient-to-br ${colors[s.color]} border rounded-xl p-5` });
    const top = h('div', { className: 'flex items-center justify-between mb-3' });
    top.appendChild(h('span', { className: `${textColors[s.color]}`, innerHTML: s.icon }));
    card.appendChild(top);
    card.appendChild(h('div', { className: 'text-3xl font-bold text-white' }, String(s.value)));
    card.appendChild(h('div', { className: 'text-sm text-slate-400 mt-1' }, s.label));
    grid.appendChild(card);
  }
  el.appendChild(grid);

  // Chart area
  const chartSection = h('div', { className: 'grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8' });

  // Daily connections bar chart (simple CSS)
  const chartCard = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl p-5' });
  chartCard.appendChild(h('h3', { className: 'text-white font-semibold mb-4' }, 'Haftalık Bağlantılar'));
  const chartBody = h('div', { className: 'flex items-end gap-2 h-40' });
  const days = Object.entries(data.daily_connections || {}).sort((a, b) => a[0].localeCompare(b[0]));
  const maxVal = Math.max(...days.map(d => d[1]), 1);
  for (const [day, count] of days) {
    const pct = (count / maxVal) * 100;
    const bar = h('div', { className: 'flex-1 flex flex-col items-center gap-1' });
    const barInner = h('div', {
      className: 'w-full bg-blue-500 rounded-t',
      style: `height: ${Math.max(pct, 2)}%; min-height: 2px; transition: height 0.3s ease`,
    });
    bar.appendChild(barInner);
    bar.appendChild(h('span', { className: 'text-xs text-slate-500' }, day.slice(5)));
    bar.appendChild(h('span', { className: 'text-xs text-slate-400' }, String(count)));
    chartBody.appendChild(bar);
  }
  chartCard.appendChild(chartBody);
  chartSection.appendChild(chartCard);

  // Recent connections
  const recentCard = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl p-5' });
  recentCard.appendChild(h('h3', { className: 'text-white font-semibold mb-4' }, 'Son Bağlantılar'));
  if (data.recent_connections?.length) {
    const list = h('div', { className: 'space-y-2 max-h-40 overflow-y-auto' });
    for (const c of data.recent_connections) {
      const row = h('div', { className: 'flex items-center justify-between text-sm py-1 border-b border-slate-700/50' });
      row.appendChild(h('span', { className: 'text-slate-300' }, `${c.from_peer} → ${c.to_peer}`));
      row.appendChild(h('span', { className: 'text-slate-500 text-xs' }, formatDate(c.timestamp)));
      list.appendChild(row);
    }
    recentCard.appendChild(list);
  } else {
    recentCard.appendChild(h('p', { className: 'text-slate-500 text-sm' }, 'Henüz bağlantı kaydı yok'));
  }
  chartSection.appendChild(recentCard);
  el.appendChild(chartSection);
};

// ── Devices ────────────────────────────────────────────────────────

Pages.devices = async (el) => {
  let page = 1, search = '';

  async function load() {
    const res = await API.devices(page, search);
    render(res.data, res.total);
  }

  function render(devices, total) {
    el.innerHTML = '';
    const header = h('div', { className: 'flex items-center justify-between mb-6' });
    header.appendChild(h('h1', { className: 'text-2xl font-bold text-white' }, 'Cihazlar'));
    el.appendChild(header);
    el.appendChild(searchBar('Cihaz ID veya not ara...', (v) => { search = v; page = 1; load(); }));

    const table = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl overflow-hidden' });
    const thead = '<div class="grid grid-cols-6 gap-4 px-5 py-3 bg-slate-750 border-b border-slate-700 text-xs font-semibold text-slate-400 uppercase tracking-wider"><span>ID</span><span>Takma Ad</span><span>Durum</span><span>IP</span><span>Kayıt Tarihi</span><span>İşlem</span></div>';
    table.innerHTML = thead;

    for (const d of devices) {
      const online = d.last_seen && (Date.now() - new Date(d.last_seen).getTime() < 300000);
      const row = h('div', { className: 'grid grid-cols-6 gap-4 px-5 py-3 table-row border-b border-slate-700/50 items-center text-sm' });
      row.appendChild(h('span', { className: 'text-white font-mono' }, d.id));
      row.appendChild(h('span', { className: 'text-slate-300' }, d.alias || '-'));
      row.appendChild(h('span', {}, h('span', { className: online ? 'badge badge-green' : 'badge badge-red' }, online ? 'Çevrimiçi' : 'Çevrimdışı')));
      row.appendChild(h('span', { className: 'text-slate-400' }, d.info?.ip || '-'));
      row.appendChild(h('span', { className: 'text-slate-400' }, formatDate(d.created_at)));
      const editBtn = h('button', { className: 'btn btn-ghost text-xs', onclick: () => editDevice(d) }, 'Düzenle');
      row.appendChild(editBtn);
      table.appendChild(row);
    }
    if (!devices.length) {
      table.appendChild(h('div', { className: 'px-5 py-8 text-center text-slate-500' }, 'Cihaz bulunamadı'));
    }
    el.appendChild(table);
    el.appendChild(pagination(page, total, 20, (p) => { page = p; load(); }));
  }

  function editDevice(d) {
    const form = h('div', { className: 'space-y-4' });
    form.innerHTML = `
      <div><label class="block text-sm text-slate-400 mb-1">Takma Ad</label><input id="ed-alias" class="input w-full" value="${d.alias || ''}"></div>
      <div><label class="block text-sm text-slate-400 mb-1">Notlar</label><textarea id="ed-notes" class="input w-full" rows="3">${d.notes || ''}</textarea></div>
      <div class="flex justify-end gap-2">
        <button class="btn btn-ghost" id="ed-cancel">İptal</button>
        <button class="btn btn-primary" id="ed-save">Kaydet</button>
      </div>`;
    const m = modal(`Cihaz: ${d.id}`, form, () => closeModal(m));
    form.querySelector('#ed-cancel').onclick = () => closeModal(m);
    form.querySelector('#ed-save').onclick = async () => {
      await API.updateDeviceTags(d.id, {
        alias: form.querySelector('#ed-alias').value,
        notes: form.querySelector('#ed-notes').value,
      });
      closeModal(m);
      load();
    };
  }

  await load();
};

// ── Users ──────────────────────────────────────────────────────────

Pages.users = async (el) => {
  let page = 1, search = '';

  async function load() {
    const res = await API.users(page, search);
    render(res.data, res.total);
  }

  function render(users, total) {
    el.innerHTML = '';
    const header = h('div', { className: 'flex items-center justify-between mb-6' });
    header.appendChild(h('h1', { className: 'text-2xl font-bold text-white' }, 'Kullanıcılar'));
    header.appendChild(h('button', { className: 'btn btn-primary', onclick: showCreateUser }, '+ Yeni Kullanıcı'));
    el.appendChild(header);
    el.appendChild(searchBar('Kullanıcı ara...', (v) => { search = v; page = 1; load(); }));

    const table = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl overflow-hidden' });
    table.innerHTML = '<div class="grid grid-cols-6 gap-4 px-5 py-3 border-b border-slate-700 text-xs font-semibold text-slate-400 uppercase tracking-wider"><span>Kullanıcı</span><span>E-posta</span><span>Grup</span><span>Durum</span><span>Kayıt</span><span>İşlem</span></div>';

    for (const u of users) {
      const row = h('div', { className: 'grid grid-cols-6 gap-4 px-5 py-3 table-row border-b border-slate-700/50 items-center text-sm' });
      row.appendChild(h('span', { className: 'text-white font-medium' }, u.username));
      row.appendChild(h('span', { className: 'text-slate-400' }, u.email || '-'));
      row.appendChild(h('span', { className: 'text-slate-400' }, u.group_name || '-'));
      row.appendChild(h('span', {}, h('span', { className: u.status === 1 ? 'badge badge-green' : 'badge badge-red' }, u.status === 1 ? 'Aktif' : 'Devre Dışı')));
      row.appendChild(h('span', { className: 'text-slate-400' }, formatDate(u.created_at)));
      const actions = h('div', { className: 'flex gap-1' });
      actions.appendChild(h('button', { className: 'btn btn-ghost text-xs', onclick: () => editUser(u) }, 'Düzenle'));
      actions.appendChild(h('button', { className: 'btn btn-danger text-xs', onclick: () => deleteUser(u) }, 'Sil'));
      row.appendChild(actions);
      table.appendChild(row);
    }
    if (!users.length) {
      table.appendChild(h('div', { className: 'px-5 py-8 text-center text-slate-500' }, 'Kullanıcı bulunamadı'));
    }
    el.appendChild(table);
    el.appendChild(pagination(page, total, 20, (p) => { page = p; load(); }));
  }

  function showCreateUser() {
    const form = h('div', { className: 'space-y-4' });
    form.innerHTML = `
      <div><label class="block text-sm text-slate-400 mb-1">Kullanıcı Adı</label><input id="cu-user" class="input w-full"></div>
      <div><label class="block text-sm text-slate-400 mb-1">Şifre</label><input id="cu-pass" type="password" class="input w-full"></div>
      <div><label class="block text-sm text-slate-400 mb-1">E-posta</label><input id="cu-email" class="input w-full"></div>
      <div class="flex justify-end gap-2">
        <button class="btn btn-ghost" id="cu-cancel">İptal</button>
        <button class="btn btn-primary" id="cu-save">Oluştur</button>
      </div>`;
    const m = modal('Yeni Kullanıcı', form, () => closeModal(m));
    form.querySelector('#cu-cancel').onclick = () => closeModal(m);
    form.querySelector('#cu-save').onclick = async () => {
      await API.createUser({
        username: form.querySelector('#cu-user').value,
        password: form.querySelector('#cu-pass').value,
        email: form.querySelector('#cu-email').value,
      });
      closeModal(m);
      load();
    };
  }

  function editUser(u) {
    const form = h('div', { className: 'space-y-4' });
    form.innerHTML = `
      <div><label class="block text-sm text-slate-400 mb-1">E-posta</label><input id="eu-email" class="input w-full" value="${u.email || ''}"></div>
      <div><label class="block text-sm text-slate-400 mb-1">Yeni Şifre (boş bırakılabilir)</label><input id="eu-pass" type="password" class="input w-full"></div>
      <div><label class="block text-sm text-slate-400 mb-1">Durum</label><select id="eu-status" class="input w-full"><option value="1" ${u.status===1?'selected':''}>Aktif</option><option value="0" ${u.status===0?'selected':''}>Devre Dışı</option></select></div>
      <div class="flex justify-end gap-2">
        <button class="btn btn-ghost" id="eu-cancel">İptal</button>
        <button class="btn btn-primary" id="eu-save">Kaydet</button>
      </div>`;
    const m = modal(`Kullanıcı: ${u.username}`, form, () => closeModal(m));
    form.querySelector('#eu-cancel').onclick = () => closeModal(m);
    form.querySelector('#eu-save').onclick = async () => {
      const data = { email: form.querySelector('#eu-email').value, status: parseInt(form.querySelector('#eu-status').value) };
      const pw = form.querySelector('#eu-pass').value;
      if (pw) data.password = pw;
      await API.updateUser(u.id, data);
      closeModal(m);
      load();
    };
  }

  async function deleteUser(u) {
    if (!confirm(`"${u.username}" kullanıcısını silmek istediğinize emin misiniz?`)) return;
    await API.deleteUser(u.id);
    load();
  }

  await load();
};

// ── Groups ─────────────────────────────────────────────────────────

Pages.groups = async (el) => {
  async function load() {
    const res = await API.groups();
    render(res.data);
  }

  function render(groups) {
    el.innerHTML = '';
    const header = h('div', { className: 'flex items-center justify-between mb-6' });
    header.appendChild(h('h1', { className: 'text-2xl font-bold text-white' }, 'Gruplar'));
    header.appendChild(h('button', { className: 'btn btn-primary', onclick: showCreate }, '+ Yeni Grup'));
    el.appendChild(header);

    const grid = h('div', { className: 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4' });
    for (const g of groups) {
      const card = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl p-5' });
      card.appendChild(h('h3', { className: 'text-white font-semibold text-lg mb-2' }, g.name));
      card.appendChild(h('p', { className: 'text-slate-400 text-sm mb-4' }, g.description || 'Açıklama yok'));
      const info = h('div', { className: 'flex gap-4 mb-4 text-sm' });
      info.appendChild(h('span', { className: 'text-slate-400' }, `${g.user_count} kullanıcı`));
      info.appendChild(h('span', { className: 'text-slate-400' }, `${g.peer_count} cihaz`));
      card.appendChild(info);
      const actions = h('div', { className: 'flex gap-2' });
      actions.appendChild(h('button', { className: 'btn btn-ghost text-xs', onclick: () => editGroup(g) }, 'Düzenle'));
      actions.appendChild(h('button', { className: 'btn btn-danger text-xs', onclick: () => delGroup(g) }, 'Sil'));
      card.appendChild(actions);
      grid.appendChild(card);
    }
    if (!groups.length) {
      grid.appendChild(h('div', { className: 'col-span-full text-center py-8 text-slate-500' }, 'Henüz grup oluşturulmamış'));
    }
    el.appendChild(grid);
  }

  function showCreate() {
    const form = h('div', { className: 'space-y-4' });
    form.innerHTML = `
      <div><label class="block text-sm text-slate-400 mb-1">Grup Adı</label><input id="cg-name" class="input w-full"></div>
      <div><label class="block text-sm text-slate-400 mb-1">Açıklama</label><textarea id="cg-desc" class="input w-full" rows="2"></textarea></div>
      <div class="flex justify-end gap-2">
        <button class="btn btn-ghost" id="cg-cancel">İptal</button>
        <button class="btn btn-primary" id="cg-save">Oluştur</button>
      </div>`;
    const m = modal('Yeni Grup', form, () => closeModal(m));
    form.querySelector('#cg-cancel').onclick = () => closeModal(m);
    form.querySelector('#cg-save').onclick = async () => {
      await API.createGroup({ name: form.querySelector('#cg-name').value, description: form.querySelector('#cg-desc').value });
      closeModal(m);
      load();
    };
  }

  function editGroup(g) {
    const form = h('div', { className: 'space-y-4' });
    form.innerHTML = `
      <div><label class="block text-sm text-slate-400 mb-1">Grup Adı</label><input id="eg-name" class="input w-full" value="${g.name}"></div>
      <div><label class="block text-sm text-slate-400 mb-1">Açıklama</label><textarea id="eg-desc" class="input w-full" rows="2">${g.description || ''}</textarea></div>
      <div class="flex justify-end gap-2">
        <button class="btn btn-ghost" id="eg-cancel">İptal</button>
        <button class="btn btn-primary" id="eg-save">Kaydet</button>
      </div>`;
    const m = modal(`Grup: ${g.name}`, form, () => closeModal(m));
    form.querySelector('#eg-cancel').onclick = () => closeModal(m);
    form.querySelector('#eg-save').onclick = async () => {
      await API.updateGroup(g.id, { name: form.querySelector('#eg-name').value, description: form.querySelector('#eg-desc').value });
      closeModal(m);
      load();
    };
  }

  async function delGroup(g) {
    if (!confirm(`"${g.name}" grubunu silmek istediğinize emin misiniz?`)) return;
    await API.deleteGroup(g.id);
    load();
  }

  await load();
};

// ── Address Books ──────────────────────────────────────────────────

Pages.addressBooks = async (el) => {
  let page = 1;

  async function load() {
    const res = await API.addressBooks(page);
    render(res.data, res.total);
  }

  function render(books, total) {
    el.innerHTML = '';
    el.appendChild(h('h1', { className: 'text-2xl font-bold text-white mb-6' }, 'Adres Defterleri'));

    const table = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl overflow-hidden' });
    table.innerHTML = '<div class="grid grid-cols-6 gap-4 px-5 py-3 border-b border-slate-700 text-xs font-semibold text-slate-400 uppercase tracking-wider"><span>Kullanıcı</span><span>Ad</span><span>Peer</span><span>Etiket</span><span>Güncelleme</span><span>İşlem</span></div>';

    for (const ab of books) {
      const row = h('div', { className: 'grid grid-cols-6 gap-4 px-5 py-3 table-row border-b border-slate-700/50 items-center text-sm' });
      row.appendChild(h('span', { className: 'text-white' }, ab.username));
      row.appendChild(h('span', { className: 'text-slate-300' }, ab.name));
      row.appendChild(h('span', { className: 'badge badge-blue' }, String(ab.peer_count)));
      row.appendChild(h('span', { className: 'badge badge-yellow' }, String(ab.tag_count)));
      row.appendChild(h('span', { className: 'text-slate-400' }, formatDate(ab.updated_at)));
      const actions = h('div', { className: 'flex gap-1' });
      actions.appendChild(h('button', { className: 'btn btn-ghost text-xs', onclick: () => viewBook(ab) }, 'Görüntüle'));
      actions.appendChild(h('button', { className: 'btn btn-danger text-xs', onclick: () => delBook(ab) }, 'Sil'));
      row.appendChild(actions);
      table.appendChild(row);
    }
    if (!books.length) {
      table.appendChild(h('div', { className: 'px-5 py-8 text-center text-slate-500' }, 'Adres defteri bulunamadı'));
    }
    el.appendChild(table);
    el.appendChild(pagination(page, total, 20, (p) => { page = p; load(); }));
  }

  async function viewBook(ab) {
    const data = await API.addressBook(ab.id);
    const body = h('div', { className: 'space-y-4' });
    body.appendChild(h('p', { className: 'text-sm text-slate-400' }, `GUID: ${data.guid}`));
    if (data.tags?.length) {
      const tagsEl = h('div', { className: 'flex flex-wrap gap-2' });
      for (const t of data.tags) {
        const name = typeof t === 'string' ? t : t.name || JSON.stringify(t);
        tagsEl.appendChild(h('span', { className: 'badge badge-blue' }, name));
      }
      body.appendChild(h('div', {}, h('span', { className: 'text-sm text-slate-400' }, 'Etiketler: '), tagsEl));
    }
    const peerList = h('div', { className: 'max-h-60 overflow-y-auto space-y-1' });
    for (const p of (data.peers || [])) {
      const id = typeof p === 'string' ? p : p.id || JSON.stringify(p);
      peerList.appendChild(h('div', { className: 'text-sm py-1 px-2 bg-slate-700/50 rounded font-mono' }, id));
    }
    if (!data.peers?.length) peerList.appendChild(h('p', { className: 'text-slate-500 text-sm' }, 'Peer yok'));
    body.appendChild(peerList);
    const m = modal(`Adres Defteri: ${data.name}`, body, () => closeModal(m));
  }

  async function delBook(ab) {
    if (!confirm(`"${ab.username}" adres defterini silmek istediğinize emin misiniz?`)) return;
    await API.deleteAddressBook(ab.id);
    load();
  }

  await load();
};

// ── Connection Logs ────────────────────────────────────────────────

Pages.connectionLogs = async (el) => {
  let page = 1, search = '';

  async function load() {
    const res = await API.connectionLogs(page, search);
    render(res.data, res.total);
  }

  function render(logs, total) {
    el.innerHTML = '';
    el.appendChild(h('h1', { className: 'text-2xl font-bold text-white mb-6' }, 'Bağlantı Logları'));
    el.appendChild(searchBar('Peer ID ara...', (v) => { search = v; page = 1; load(); }));

    const table = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl overflow-hidden' });
    table.innerHTML = '<div class="grid grid-cols-5 gap-4 px-5 py-3 border-b border-slate-700 text-xs font-semibold text-slate-400 uppercase tracking-wider"><span>Kaynak</span><span>Hedef</span><span>İşlem</span><span>IP</span><span>Zaman</span></div>';

    for (const l of logs) {
      const row = h('div', { className: 'grid grid-cols-5 gap-4 px-5 py-3 table-row border-b border-slate-700/50 items-center text-sm' });
      row.appendChild(h('span', { className: 'text-white font-mono' }, l.from_peer));
      row.appendChild(h('span', { className: 'text-slate-300 font-mono' }, l.to_peer));
      row.appendChild(h('span', { className: 'badge badge-blue' }, l.action));
      row.appendChild(h('span', { className: 'text-slate-400' }, l.ip || '-'));
      row.appendChild(h('span', { className: 'text-slate-400' }, formatDate(l.timestamp)));
      table.appendChild(row);
    }
    if (!logs.length) {
      table.appendChild(h('div', { className: 'px-5 py-8 text-center text-slate-500' }, 'Bağlantı logu bulunamadı'));
    }
    el.appendChild(table);
    el.appendChild(pagination(page, total, 30, (p) => { page = p; load(); }));
  }

  await load();
};

// ── Audit Logs ─────────────────────────────────────────────────────

Pages.auditLogs = async (el) => {
  let page = 1;

  async function load() {
    const res = await API.auditLogs(page);
    render(res.data, res.total);
  }

  function render(logs, total) {
    el.innerHTML = '';
    el.appendChild(h('h1', { className: 'text-2xl font-bold text-white mb-6' }, 'Denetim Logları'));

    const table = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl overflow-hidden' });
    table.innerHTML = '<div class="grid grid-cols-4 gap-4 px-5 py-3 border-b border-slate-700 text-xs font-semibold text-slate-400 uppercase tracking-wider"><span>İşlem</span><span>Detay</span><span>IP</span><span>Zaman</span></div>';

    for (const a of logs) {
      const row = h('div', { className: 'grid grid-cols-4 gap-4 px-5 py-3 table-row border-b border-slate-700/50 items-center text-sm' });
      row.appendChild(h('span', { className: 'badge badge-yellow' }, a.action));
      row.appendChild(h('span', { className: 'text-slate-300' }, a.details || '-'));
      row.appendChild(h('span', { className: 'text-slate-400' }, a.ip_address || '-'));
      row.appendChild(h('span', { className: 'text-slate-400' }, formatDate(a.timestamp)));
      table.appendChild(row);
    }
    if (!logs.length) {
      table.appendChild(h('div', { className: 'px-5 py-8 text-center text-slate-500' }, 'Denetim logu bulunamadı'));
    }
    el.appendChild(table);
    el.appendChild(pagination(page, total, 30, (p) => { page = p; load(); }));
  }

  await load();
};

// ── Settings ───────────────────────────────────────────────────────

Pages.settings = async (el) => {
  const [settingsRes, serverInfo] = await Promise.all([API.settings(), API.serverInfo()]);

  el.innerHTML = '';
  el.appendChild(h('h1', { className: 'text-2xl font-bold text-white mb-6' }, 'Sunucu Ayarları'));

  // Server info card
  const infoCard = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl p-5 mb-6' });
  infoCard.appendChild(h('h3', { className: 'text-white font-semibold mb-3' }, 'Sunucu Bilgileri'));
  const infoGrid = h('div', { className: 'space-y-2 text-sm' });
  infoGrid.appendChild(h('div', { className: 'flex justify-between' },
    h('span', { className: 'text-slate-400' }, 'Public Key:'),
    h('span', { className: 'text-white font-mono text-xs break-all' }, serverInfo.public_key || 'Bulunamadı')
  ));
  infoGrid.appendChild(h('div', { className: 'flex justify-between' },
    h('span', { className: 'text-slate-400' }, 'RustDesk DB:'),
    h('span', {}, h('span', { className: serverInfo.rustdesk_db_exists ? 'badge badge-green' : 'badge badge-red' }, serverInfo.rustdesk_db_exists ? 'Bağlı' : 'Bulunamadı'))
  ));
  infoCard.appendChild(infoGrid);
  el.appendChild(infoCard);

  // Settings key-value
  const settingsCard = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl p-5 mb-6' });
  settingsCard.appendChild(h('h3', { className: 'text-white font-semibold mb-3' }, 'Yapılandırma'));

  const settingsList = h('div', { className: 'space-y-2' });
  for (const s of settingsRes.data) {
    const row = h('div', { className: 'flex items-center gap-3 py-2 border-b border-slate-700/50' });
    row.appendChild(h('span', { className: 'text-slate-300 font-mono text-sm w-1/3' }, s.key));
    row.appendChild(h('span', { className: 'text-white text-sm flex-1' }, s.value));
    row.appendChild(h('button', { className: 'text-red-400 hover:text-red-300 text-sm', onclick: async () => {
      await API.deleteSetting(s.key);
      Router.navigate('/settings');
    }}, 'Sil'));
    settingsList.appendChild(row);
  }
  if (!settingsRes.data.length) {
    settingsList.appendChild(h('p', { className: 'text-slate-500 text-sm py-2' }, 'Yapılandırma ayarı yok'));
  }
  settingsCard.appendChild(settingsList);

  // Add new setting
  const addForm = h('div', { className: 'flex gap-2 mt-4' });
  const keyInput = h('input', { className: 'input flex-1', placeholder: 'Anahtar' });
  const valInput = h('input', { className: 'input flex-1', placeholder: 'Değer' });
  const addBtn = h('button', { className: 'btn btn-primary', onclick: async () => {
    if (keyInput.value) {
      await API.updateSettings({ [keyInput.value]: valInput.value });
      Router.navigate('/settings');
    }
  }}, 'Ekle');
  addForm.appendChild(keyInput);
  addForm.appendChild(valInput);
  addForm.appendChild(addBtn);
  settingsCard.appendChild(addForm);

  el.appendChild(settingsCard);
};

// ── API Keys ───────────────────────────────────────────────────────

Pages.apiKeys = async (el) => {
  async function load() {
    const res = await API.apiKeys();
    render(res.data);
  }

  function render(keys) {
    el.innerHTML = '';
    const header = h('div', { className: 'flex items-center justify-between mb-6' });
    header.appendChild(h('h1', { className: 'text-2xl font-bold text-white' }, 'API Anahtarları'));
    header.appendChild(h('button', { className: 'btn btn-primary', onclick: showCreate }, '+ Yeni Anahtar'));
    el.appendChild(header);

    const table = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl overflow-hidden' });
    table.innerHTML = '<div class="grid grid-cols-5 gap-4 px-5 py-3 border-b border-slate-700 text-xs font-semibold text-slate-400 uppercase tracking-wider"><span>Ad</span><span>Ön Ek</span><span>Durum</span><span>Oluşturma</span><span>İşlem</span></div>';

    for (const k of keys) {
      const row = h('div', { className: 'grid grid-cols-5 gap-4 px-5 py-3 table-row border-b border-slate-700/50 items-center text-sm' });
      row.appendChild(h('span', { className: 'text-white' }, k.name));
      row.appendChild(h('span', { className: 'text-slate-400 font-mono' }, k.key_prefix + '...'));
      row.appendChild(h('span', {}, h('span', { className: k.is_active ? 'badge badge-green' : 'badge badge-red' }, k.is_active ? 'Aktif' : 'Devre Dışı')));
      row.appendChild(h('span', { className: 'text-slate-400' }, formatDate(k.created_at)));
      const actions = h('div', { className: 'flex gap-1' });
      actions.appendChild(h('button', { className: 'btn btn-ghost text-xs', onclick: async () => { await API.toggleApiKey(k.id); load(); }}, k.is_active ? 'Devre Dışı' : 'Etkinleştir'));
      actions.appendChild(h('button', { className: 'btn btn-danger text-xs', onclick: async () => { if (confirm('Bu API anahtarını silmek istediğinize emin misiniz?')) { await API.deleteApiKey(k.id); load(); }}}, 'Sil'));
      row.appendChild(actions);
      table.appendChild(row);
    }
    if (!keys.length) {
      table.appendChild(h('div', { className: 'px-5 py-8 text-center text-slate-500' }, 'API anahtarı bulunamadı'));
    }
    el.appendChild(table);
  }

  function showCreate() {
    const form = h('div', { className: 'space-y-4' });
    form.innerHTML = `
      <div><label class="block text-sm text-slate-400 mb-1">Anahtar Adı</label><input id="ak-name" class="input w-full" placeholder="Uygulama adı"></div>
      <div class="flex justify-end gap-2">
        <button class="btn btn-ghost" id="ak-cancel">İptal</button>
        <button class="btn btn-primary" id="ak-save">Oluştur</button>
      </div>`;
    const m = modal('Yeni API Anahtarı', form, () => closeModal(m));
    form.querySelector('#ak-cancel').onclick = () => closeModal(m);
    form.querySelector('#ak-save').onclick = async () => {
      const res = await API.createApiKey({ name: form.querySelector('#ak-name').value });
      closeModal(m);
      // Show the key
      const keyBody = h('div', { className: 'space-y-4' });
      keyBody.innerHTML = `
        <p class="text-sm text-yellow-300">Bu anahtarı şimdi kopyalayın. Tekrar gösterilmeyecektir!</p>
        <div class="bg-slate-900 p-3 rounded-lg font-mono text-sm text-green-400 break-all select-all">${res.key}</div>
        <div class="flex justify-end">
          <button class="btn btn-primary" id="ak-done">Tamam</button>
        </div>`;
      const m2 = modal('API Anahtarı Oluşturuldu', keyBody, () => { closeModal(m2); load(); });
      keyBody.querySelector('#ak-done').onclick = () => { closeModal(m2); load(); };
    };
  }

  await load();
};

// ── Boot ───────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => App.init());
