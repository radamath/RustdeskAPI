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

    const doLogin = async (totpCode = '') => {
      errEl.classList.add('hidden');
      try {
        const res = await API.login(uEl.value, pEl.value, totpCode);
        if (res._status === 202 && res.requires_2fa) {
          this.show2FAPrompt(uEl.value, pEl.value, errEl);
          return;
        }
        this.user = res;
        this.showApp();
        this.registerRoutes();
        Router.init();
      } catch (e) {
        errEl.textContent = e.message;
        errEl.classList.remove('hidden');
      }
    };
    btn.onclick = () => doLogin();
    pEl.onkeydown = (e) => { if (e.key === 'Enter') doLogin(); };
    uEl.onkeydown = (e) => { if (e.key === 'Enter') pEl.focus(); };
  },

  show2FAPrompt(username, password, errEl) {
    const loginBox = document.querySelector('#login-screen > div');
    let totpDiv = document.getElementById('totp-section');
    if (totpDiv) totpDiv.remove();
    totpDiv = document.createElement('div');
    totpDiv.id = 'totp-section';
    totpDiv.innerHTML = `
      <div class="mt-4 p-4 bg-slate-700/50 rounded-lg border border-slate-600">
        <label class="block text-sm font-medium text-slate-300 mb-1">2FA Doğrulama Kodu</label>
        <input id="totp-code" type="text" class="input w-full text-center text-lg tracking-widest" maxlength="6" placeholder="000000" autocomplete="one-time-code">
        <button id="totp-btn" class="btn btn-primary w-full justify-center mt-3">Doğrula</button>
      </div>`;
    loginBox.appendChild(totpDiv);
    const codeEl = document.getElementById('totp-code');
    const totpBtn = document.getElementById('totp-btn');
    codeEl.focus();
    const doVerify = async () => {
      errEl.classList.add('hidden');
      try {
        const res = await API.login(username, password, codeEl.value);
        if (res._status === 202) { errEl.textContent = 'Geçersiz kod'; errEl.classList.remove('hidden'); return; }
        this.user = res;
        this.showApp();
        this.registerRoutes();
        Router.init();
      } catch (e) { errEl.textContent = e.message; errEl.classList.remove('hidden'); }
    };
    totpBtn.onclick = doVerify;
    codeEl.onkeydown = (e) => { if (e.key === 'Enter') doVerify(); };
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
    Router.register('/security', Pages.security);
    Router.register('/deploy', Pages.deploy);
    Router.register('/login', () => App.showLogin());
  },
};

// ── Helper functions ───────────────────────────────────────────────

function toast(msg, duration = 3000) {
  const el = document.createElement('div');
  el.textContent = msg;
  el.className = 'fixed bottom-6 right-6 z-[9999] bg-green-600 text-white px-5 py-3 rounded-lg shadow-lg text-sm font-medium transition-opacity duration-300';
  document.body.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, duration);
}

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

function formatDuration(sec) {
  if (sec == null || Number.isNaN(sec) || sec < 0) return '';
  const s = Math.floor(sec % 60);
  const m = Math.floor((sec / 60) % 60);
  const h = Math.floor(sec / 3600);
  if (h > 0) return `${h} sa ${m} dk ${s} sn`;
  if (m > 0) return `${m} dk ${s} sn`;
  return `${s} sn`;
}

function connectionLogPeerCell(id, name) {
  const wrap = h('div', { className: 'flex flex-col gap-0.5 min-w-0' });
  wrap.appendChild(h('span', { className: 'text-white font-mono text-xs break-all' }, id || '—'));
  wrap.appendChild(h('span', {
    className: name ? 'text-slate-300 text-xs truncate' : 'text-slate-600 text-xs',
    title: name || '',
  }, name || '—'));
  return wrap;
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

function buildPeerTable(peers) {
  const peerTable = h('div', { className: 'max-h-80 overflow-y-auto rounded-lg border border-slate-700' });
  const peerHeader = h('div', { className: 'grid grid-cols-12 gap-2 px-4 py-2 bg-slate-700/60 text-xs font-semibold text-slate-400 uppercase tracking-wider sticky top-0' });
  peerHeader.appendChild(h('span', { className: 'col-span-1' }, ''));
  peerHeader.appendChild(h('span', { className: 'col-span-2' }, 'ID'));
  peerHeader.appendChild(h('span', { className: 'col-span-2' }, 'Bilgisayar'));
  peerHeader.appendChild(h('span', { className: 'col-span-2' }, 'Lokal IP'));
  peerHeader.appendChild(h('span', { className: 'col-span-2' }, 'Global IP'));
  peerHeader.appendChild(h('span', { className: 'col-span-1' }, 'Platform'));
  peerHeader.appendChild(h('span', { className: 'col-span-2 text-right' }, 'İşlem'));
  peerTable.appendChild(peerHeader);

  for (const p of peers) {
    const pid = typeof p === 'string' ? p : (p.id || '');
    const hostname = (typeof p === 'object' ? p.hostname : '') || '-';
    const localIp = (typeof p === 'object' ? p.local_ip : '') || '-';
    const globalIp = (typeof p === 'object' ? p.ip : '') || '-';
    const platform = (typeof p === 'object' ? (p.platform || '') : '') || '-';
    const online = typeof p === 'object' ? p.online : false;

    const peerRow = h('div', { className: 'grid grid-cols-12 gap-2 px-4 py-2.5 border-b border-slate-700/50 items-center text-sm hover:bg-slate-700/30 transition-colors' });
    const statusDot = h('span', { className: `inline-block w-2.5 h-2.5 rounded-full ${online ? 'bg-green-500 shadow-green-500/50 shadow-sm' : 'bg-slate-600'}` });
    peerRow.appendChild(h('span', { className: 'col-span-1 flex items-center' }, statusDot));
    peerRow.appendChild(h('span', { className: 'col-span-2 text-white font-mono text-xs' }, pid));
    peerRow.appendChild(h('span', { className: 'col-span-2 text-slate-300 text-xs truncate' }, hostname));
    peerRow.appendChild(h('span', { className: 'col-span-2 text-green-400 font-mono text-xs' }, localIp));
    peerRow.appendChild(h('span', { className: 'col-span-2 text-slate-500 font-mono text-xs' }, globalIp));
    peerRow.appendChild(h('span', { className: 'col-span-1 text-slate-400 text-xs truncate' }, platform));

    const connectBtn = h('button', {
      className: 'btn btn-primary text-xs px-3 py-1',
      onclick: () => { window.location.href = `rustdesk://connection/new/${pid}`; },
    });
    connectBtn.innerHTML = '<svg class="w-3.5 h-3.5 inline mr-1 -mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>Bağlan';
    peerRow.appendChild(h('span', { className: 'col-span-2 text-right' }, connectBtn));

    peerTable.appendChild(peerRow);
  }
  return peerTable;
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

  // Online peers list
  const onlineSection = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl p-5 mb-8' });
  onlineSection.appendChild(h('h3', { className: 'text-white font-semibold mb-4' }, `Çevrimiçi Cihazlar (${data.online_list?.length || 0})`));
  if (data.online_list?.length) {
    const oTable = h('div', { className: 'overflow-x-auto' });
    oTable.innerHTML = '<div class="grid grid-cols-5 gap-4 px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider border-b border-slate-700"><span>ID</span><span>IP Adresi</span><span>Hostname</span><span>OS</span><span>Son Görülme</span></div>';
    for (const p of data.online_list) {
      const row = h('div', { className: 'grid grid-cols-5 gap-4 px-4 py-2 table-row border-b border-slate-700/50 items-center text-sm' });
      row.appendChild(h('span', { className: 'text-white font-mono' }, p.id));
      row.appendChild(h('span', { className: 'text-blue-400 font-mono' }, p.ip || '-'));
      row.appendChild(h('span', { className: 'text-slate-300' }, p.hostname || '-'));
      row.appendChild(h('span', { className: 'text-slate-400' }, p.os || '-'));
      row.appendChild(h('span', { className: 'text-slate-400' }, formatDate(p.last_seen)));
      oTable.appendChild(row);
    }
    onlineSection.appendChild(oTable);
  } else {
    onlineSection.appendChild(h('p', { className: 'text-slate-500 text-sm' }, 'Şu anda çevrimiçi cihaz yok'));
  }
  el.appendChild(onlineSection);
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
    el.appendChild(searchBar('Cihaz ID, hostname veya not ara...', (v) => { search = v; page = 1; load(); }));

    const onlineCount = devices.filter(d => d.online).length;
    const statsBar = h('div', { className: 'flex gap-4 mb-4 text-sm' });
    statsBar.appendChild(h('span', { className: 'text-slate-400' }, `Toplam: ${total}`));
    statsBar.appendChild(h('span', { className: 'text-green-400' }, `Çevrimiçi: ${onlineCount}`));
    statsBar.appendChild(h('span', { className: 'text-slate-500' }, `Çevrimdışı: ${devices.length - onlineCount}`));
    el.appendChild(statsBar);

    const table = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl overflow-hidden' });
    table.innerHTML = '<div class="grid grid-cols-12 gap-2 px-5 py-3 border-b border-slate-700 text-xs font-semibold text-slate-400 uppercase tracking-wider"><span class="col-span-1"></span><span class="col-span-1">ID</span><span class="col-span-2">Bilgisayar</span><span class="col-span-1">Takma Ad</span><span class="col-span-2">Lokal IP</span><span class="col-span-2">Global IP</span><span class="col-span-1">Platform</span><span class="col-span-2 text-right">İşlem</span></div>';

    for (const d of devices) {
      const row = h('div', { className: 'grid grid-cols-12 gap-2 px-5 py-3 table-row border-b border-slate-700/50 items-center text-sm' });

      const statusDot = h('span', { className: `inline-block w-2.5 h-2.5 rounded-full ${d.online ? 'bg-green-500 shadow-green-500/50 shadow-sm' : 'bg-slate-600'}` });
      row.appendChild(h('span', { className: 'col-span-1 flex items-center' }, statusDot));
      row.appendChild(h('span', { className: 'col-span-1 text-white font-mono text-xs' }, d.id));
      row.appendChild(h('span', { className: 'col-span-2 text-slate-300 text-xs truncate' }, d.hostname || '-'));
      row.appendChild(h('span', { className: `col-span-1 text-xs truncate ${d.alias ? 'text-amber-400 font-medium' : 'text-slate-500'}` }, d.alias || '-'));
      row.appendChild(h('span', { className: 'col-span-2 text-green-400 font-mono text-xs' }, d.local_ip || '-'));
      row.appendChild(h('span', { className: 'col-span-2 text-slate-500 font-mono text-xs' }, d.global_ip || '-'));
      row.appendChild(h('span', { className: 'col-span-1 text-slate-400 text-xs truncate' }, d.platform || '-'));

      const actions = h('div', { className: 'col-span-2 flex gap-1 justify-end' });
      const connectBtn = h('button', { className: 'btn btn-primary text-xs px-2 py-1', onclick: () => { window.location.href = `rustdesk://connection/new/${d.id}`; } });
      connectBtn.innerHTML = '<svg class="w-3 h-3 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>';
      actions.appendChild(connectBtn);
      actions.appendChild(h('button', { className: 'btn btn-ghost text-xs px-2 py-1', onclick: () => editDevice(d) }, 'Düzenle'));
      actions.appendChild(h('button', { className: 'btn btn-danger text-xs px-2 py-1', onclick: () => deleteDevice(d) }, 'Sil'));
      row.appendChild(actions);
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
      <div class="grid grid-cols-2 gap-4 text-sm mb-4">
        <div><span class="text-slate-400">ID:</span> <span class="text-white font-mono">${d.id}</span></div>
        <div><span class="text-slate-400">Hostname:</span> <span class="text-white">${d.hostname || '-'}</span></div>
        <div><span class="text-slate-400">Lokal IP:</span> <span class="text-green-400 font-mono">${d.local_ip || '-'}</span></div>
        <div><span class="text-slate-400">Global IP:</span> <span class="text-slate-300 font-mono">${d.global_ip || '-'}</span></div>
        <div><span class="text-slate-400">Platform:</span> <span class="text-slate-300">${d.platform || '-'}</span></div>
        <div><span class="text-slate-400">Durum:</span> <span class="${d.online ? 'text-green-400' : 'text-red-400'}">${d.online ? 'Çevrimiçi' : 'Çevrimdışı'}</span></div>
      </div>
      <div><label class="block text-sm text-slate-400 mb-1">Takma Ad</label><input id="ed-alias" class="input w-full" value="${d.alias || ''}"></div>
      <div><label class="block text-sm text-slate-400 mb-1">Notlar</label><textarea id="ed-notes" class="input w-full" rows="3">${d.notes || ''}</textarea></div>
      <div class="flex justify-end gap-2">
        <button class="btn btn-ghost" id="ed-cancel">İptal</button>
        <button class="btn btn-primary" id="ed-save">Kaydet</button>
      </div>`;
    const m = modal(`Cihaz: ${d.id}`, form, () => closeModal(m));
    form.querySelector('#ed-cancel').onclick = () => closeModal(m);
    form.querySelector('#ed-save').onclick = async () => {
      const saveBtn = form.querySelector('#ed-save');
      saveBtn.disabled = true;
      saveBtn.textContent = 'Kaydediliyor...';
      await API.updateDeviceTags(d.id, {
        alias: form.querySelector('#ed-alias').value,
        notes: form.querySelector('#ed-notes').value,
      });
      closeModal(m);
      toast('Kaydedildi – takma ad tüm adres defterlerine senkronize edildi');
      load();
    };
  }

  async function deleteDevice(d) {
    if (!confirm(`"${d.id}" (${d.hostname || 'isimsiz'}) cihazını silmek istediğinize emin misiniz?\n\nBu işlem heartbeat ve etiket verilerini siler.`)) return;
    await API.deleteDevice(d.id);
    load();
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
    table.innerHTML = '<div class="grid grid-cols-7 gap-4 px-5 py-3 border-b border-slate-700 text-xs font-semibold text-slate-400 uppercase tracking-wider"><span>Kullanıcı</span><span>Rol</span><span>E-posta</span><span>Adres Defteri</span><span>Durum</span><span>Kayıt</span><span>İşlem</span></div>';

    for (const u of users) {
      const roleBadge = u.role === 'admin' ? 'badge badge-yellow' : 'badge badge-blue';
      const roleLabel = u.role === 'admin' ? 'Admin' : 'Kullanıcı';

      const row = h('div', { className: 'grid grid-cols-7 gap-4 px-5 py-3 table-row border-b border-slate-700/50 items-center text-sm cursor-pointer hover:bg-slate-700/50 transition-colors', onclick: () => viewUserAB(u) });
      row.appendChild(h('span', { className: 'text-white font-medium' }, u.username));
      row.appendChild(h('span', {}, h('span', { className: roleBadge }, roleLabel)));
      row.appendChild(h('span', { className: 'text-slate-400' }, u.email || '-'));
      const abInfo = h('span', { className: 'flex items-center gap-1' });
      abInfo.appendChild(h('span', { className: 'badge badge-blue' }, String(u.ab_peer_count || 0)));
      abInfo.appendChild(h('span', { className: 'text-slate-500 text-xs' }, 'cihaz'));
      row.appendChild(abInfo);
      row.appendChild(h('span', {}, h('span', { className: u.status === 1 ? 'badge badge-green' : 'badge badge-red' }, u.status === 1 ? 'Aktif' : 'Devre Dışı')));
      row.appendChild(h('span', { className: 'text-slate-400' }, formatDate(u.created_at)));
      const actions = h('div', { className: 'flex gap-1' });
      actions.appendChild(h('button', { className: 'btn btn-ghost text-xs', onclick: (e) => { e.stopPropagation(); editUser(u); } }, 'Düzenle'));
      actions.appendChild(h('button', { className: 'btn btn-danger text-xs', onclick: (e) => { e.stopPropagation(); deleteUser(u); } }, 'Sil'));
      row.appendChild(actions);
      table.appendChild(row);
    }
    if (!users.length) {
      table.appendChild(h('div', { className: 'px-5 py-8 text-center text-slate-500' }, 'Kullanıcı bulunamadı'));
    }
    el.appendChild(table);
    el.appendChild(pagination(page, total, 20, (p) => { page = p; load(); }));
  }

  async function viewUserAB(u) {
    const data = await API.userAddressBook(u.id);
    const body = h('div', { className: 'space-y-4' });

    const infoRow = h('div', { className: 'flex items-center gap-3 text-sm' });
    const roleBadge = u.role === 'admin' ? 'badge badge-yellow' : 'badge badge-blue';
    const roleLabel = u.role === 'admin' ? 'Admin' : 'Kullanıcı';
    infoRow.appendChild(h('span', { className: roleBadge }, roleLabel));
    if (u.role === 'admin') {
      infoRow.appendChild(h('span', { className: 'text-slate-500 text-xs italic' }, 'Tüm sistem cihazları otomatik eklenir'));
    }
    body.appendChild(infoRow);

    const peerSection = h('div', { className: 'space-y-2' });
    peerSection.appendChild(h('h4', { className: 'text-sm font-semibold text-slate-300' }, `Adres Defteri (${data.peers?.length || 0} cihaz)`));

    if (data.peers?.length) {
      peerSection.appendChild(buildPeerTable(data.peers));
    } else {
      peerSection.appendChild(h('div', { className: 'text-center py-6 text-slate-500' }, 'Adres defterinde kayıtlı cihaz yok'));
    }
    body.appendChild(peerSection);

    const m = modal(`${u.username} — Adres Defteri`, body, () => closeModal(m));
    m.querySelector('.modal').classList.add('modal-wide');
  }

  function showCreateUser() {
    const form = h('div', { className: 'space-y-4' });
    form.innerHTML = `
      <div><label class="block text-sm text-slate-400 mb-1">Kullanıcı Adı</label><input id="cu-user" class="input w-full"></div>
      <div><label class="block text-sm text-slate-400 mb-1">Şifre</label><input id="cu-pass" type="password" class="input w-full"></div>
      <div><label class="block text-sm text-slate-400 mb-1">E-posta</label><input id="cu-email" class="input w-full"></div>
      <div><label class="block text-sm text-slate-400 mb-1">Rol</label>
        <select id="cu-role" class="input w-full">
          <option value="user">Kullanıcı</option>
          <option value="admin">Admin</option>
        </select>
        <p class="text-xs text-slate-500 mt-1">Admin rolü: tüm sistem cihazları adres defterine otomatik eklenir</p>
      </div>
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
        role: form.querySelector('#cu-role').value,
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
      <div><label class="block text-sm text-slate-400 mb-1">Rol</label>
        <select id="eu-role" class="input w-full">
          <option value="user" ${u.role !== 'admin' ? 'selected' : ''}>Kullanıcı</option>
          <option value="admin" ${u.role === 'admin' ? 'selected' : ''}>Admin</option>
        </select>
        <p class="text-xs text-slate-500 mt-1">Admin rolü: tüm sistem cihazları adres defterine otomatik eklenir</p>
      </div>
      <div><label class="block text-sm text-slate-400 mb-1">Durum</label><select id="eu-status" class="input w-full"><option value="1" ${u.status===1?'selected':''}>Aktif</option><option value="0" ${u.status===0?'selected':''}>Devre Dışı</option></select></div>
      <div class="flex justify-end gap-2">
        <button class="btn btn-ghost" id="eu-cancel">İptal</button>
        <button class="btn btn-primary" id="eu-save">Kaydet</button>
      </div>`;
    const m = modal(`Kullanıcı: ${u.username}`, form, () => closeModal(m));
    form.querySelector('#eu-cancel').onclick = () => closeModal(m);
    form.querySelector('#eu-save').onclick = async () => {
      const data = {
        email: form.querySelector('#eu-email').value,
        role: form.querySelector('#eu-role').value,
        status: parseInt(form.querySelector('#eu-status').value),
      };
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
      const row = h('div', { className: 'grid grid-cols-6 gap-4 px-5 py-3 table-row border-b border-slate-700/50 items-center text-sm cursor-pointer hover:bg-slate-700/50 transition-colors', onclick: () => viewBook(ab) });
      row.appendChild(h('span', { className: 'text-white font-medium' }, ab.username));
      row.appendChild(h('span', { className: 'text-slate-300' }, ab.name));
      row.appendChild(h('span', { className: 'badge badge-blue' }, String(ab.peer_count)));
      row.appendChild(h('span', { className: 'badge badge-yellow' }, String(ab.tag_count)));
      row.appendChild(h('span', { className: 'text-slate-400' }, formatDate(ab.updated_at)));
      const actions = h('div', { className: 'flex gap-1' });
      actions.appendChild(h('button', { className: 'btn btn-ghost text-xs', onclick: (e) => { e.stopPropagation(); viewBook(ab); } }, 'Görüntüle'));
      actions.appendChild(h('button', { className: 'btn btn-danger text-xs', onclick: (e) => { e.stopPropagation(); delBook(ab); } }, 'Sil'));
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

    const infoRow = h('div', { className: 'flex items-center gap-4 text-sm' });
    infoRow.appendChild(h('span', { className: 'text-slate-400' }, `Kullanıcı: `));
    infoRow.appendChild(h('span', { className: 'text-white font-medium' }, data.username));
    infoRow.appendChild(h('span', { className: 'text-slate-600' }, '|'));
    infoRow.appendChild(h('span', { className: 'text-slate-400' }, `GUID: `));
    infoRow.appendChild(h('span', { className: 'text-slate-300 font-mono text-xs' }, data.guid));
    body.appendChild(infoRow);

    if (data.tags?.length) {
      const tagsWrap = h('div', { className: 'flex items-center gap-2 flex-wrap' });
      tagsWrap.appendChild(h('span', { className: 'text-sm text-slate-400' }, 'Etiketler:'));
      for (const t of data.tags) {
        const name = typeof t === 'string' ? t : t.name || JSON.stringify(t);
        tagsWrap.appendChild(h('span', { className: 'badge badge-blue' }, name));
      }
      body.appendChild(tagsWrap);
    }

    const peerSection = h('div', { className: 'space-y-2' });
    peerSection.appendChild(h('h4', { className: 'text-sm font-semibold text-slate-300' }, `Cihazlar (${data.peers?.length || 0})`));

    if (data.peers?.length) {
      peerSection.appendChild(buildPeerTable(data.peers));
    } else {
      peerSection.appendChild(h('div', { className: 'text-center py-6 text-slate-500' }, 'Bu adres defterinde kayıtlı cihaz yok'));
    }
    body.appendChild(peerSection);

    const m = modal(`${data.username} — Adres Defteri`, body, () => closeModal(m));
    m.querySelector('.modal').classList.add('modal-wide');
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
    el.appendChild(h('h1', { className: 'text-2xl font-bold text-white mb-2' }, 'Bağlantı Logları'));
    el.appendChild(h('p', { className: 'text-slate-500 text-xs mb-6' }, 'Her oturum tek satır · süre ve cihaz adları (db_v2 / Heartbeat) · UI v7'));
    el.appendChild(searchBar('Peer ID ara...', (v) => { search = v; page = 1; load(); }));

    const table = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl overflow-hidden' });
    table.innerHTML = '<div class="grid grid-cols-5 gap-4 px-5 py-3 border-b border-slate-700 text-xs font-semibold text-slate-400 uppercase tracking-wider"><span>Kaynak</span><span>Hedef</span><span>Bağlantı</span><span>IP</span><span>Zaman / süre</span></div>';

    for (const l of logs) {
      const row = h('div', { className: 'grid grid-cols-5 gap-4 px-5 py-3 table-row border-b border-slate-700/50 items-start text-sm' });
      row.appendChild(connectionLogPeerCell(l.from_peer, l.from_name));
      row.appendChild(connectionLogPeerCell(l.to_peer, l.to_name));

      const actions = h('div', { className: 'flex flex-wrap items-center gap-x-2 gap-y-1' });
      if (l.has_connect && l.connect_at) {
        actions.appendChild(h('span', { className: 'badge badge-blue shrink-0' }, 'Bağlandı'));
        actions.appendChild(h('span', { className: 'text-slate-400 text-xs' }, formatDate(l.connect_at)));
      }
      if (l.has_close && l.close_at) {
        actions.appendChild(h('span', { className: 'badge badge-slate shrink-0' }, 'Kapandı'));
        actions.appendChild(h('span', { className: 'text-slate-400 text-xs' }, formatDate(l.close_at)));
      }
      if (!actions.childNodes.length) {
        actions.appendChild(h('span', { className: 'text-slate-500 text-xs' }, '—'));
      }
      row.appendChild(actions);

      row.appendChild(h('span', { className: 'text-slate-400 break-all' }, l.ip || '-'));

      const mainTs = l.connect_at || l.close_at;
      const timeSpans = [];
      if (mainTs) timeSpans.push(h('span', {}, formatDate(mainTs)));
      if (l.duration_sec != null) {
        timeSpans.push(h('span', {}, `Süre: ${formatDuration(l.duration_sec)}`));
      } else if (l.has_connect && !l.has_close) {
        timeSpans.push(h('span', { className: 'text-slate-500' }, 'Süre: —'));
      }
      row.appendChild(h(
        'div',
        { className: 'flex flex-col gap-0.5 text-slate-400 text-xs' },
        ...(timeSpans.length ? timeSpans : [h('span', {}, '—')]),
      ));
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

// ── Security (2FA) ─────────────────────────────────────────────────

Pages.security = async (el) => {
  const me = await API.me();
  el.innerHTML = '';
  el.appendChild(h('h1', { className: 'text-2xl font-bold text-white mb-6' }, 'Güvenlik'));

  const card = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl p-6 max-w-lg' });
  card.appendChild(h('h3', { className: 'text-white font-semibold mb-2' }, 'İki Faktörlü Doğrulama (2FA)'));
  card.appendChild(h('p', { className: 'text-slate-400 text-sm mb-4' }, 'Google Authenticator veya benzeri bir TOTP uygulaması ile hesabınızı koruyun.'));

  if (me.totp_enabled) {
    card.appendChild(h('div', { className: 'flex items-center gap-2 mb-4' },
      h('span', { className: 'badge badge-green' }, 'Etkin'),
      h('span', { className: 'text-slate-300 text-sm' }, '2FA aktif durumda')
    ));
    const disableForm = h('div', { className: 'space-y-3' });
    disableForm.innerHTML = `
      <div><label class="block text-sm text-slate-400 mb-1">Devre dışı bırakmak için mevcut 2FA kodunuzu girin</label>
      <input id="dis-code" type="text" class="input w-full text-center tracking-widest" maxlength="6" placeholder="000000"></div>
      <button id="dis-btn" class="btn btn-danger">2FA Devre Dışı Bırak</button>`;
    card.appendChild(disableForm);
    card.querySelector('#dis-btn').onclick = async () => {
      try {
        await API.disable2FA(card.querySelector('#dis-code').value);
        Router.navigate('/security');
      } catch (e) { alert(e.message); }
    };
  } else {
    card.appendChild(h('div', { className: 'flex items-center gap-2 mb-4' },
      h('span', { className: 'badge badge-red' }, 'Devre Dışı'),
      h('span', { className: 'text-slate-300 text-sm' }, '2FA henüz kurulmamış')
    ));
    const setupBtn = h('button', { className: 'btn btn-primary', onclick: async () => {
      const res = await API.setup2FA();
      card.innerHTML = '';
      card.appendChild(h('h3', { className: 'text-white font-semibold mb-4' }, '2FA Kurulumu'));
      card.appendChild(h('p', { className: 'text-slate-400 text-sm mb-4' }, 'Aşağıdaki QR kodu TOTP uygulamanız ile taratın:'));
      const qrImg = h('img', { src: res.qr_code, className: 'mx-auto mb-4 rounded-lg', style: 'width: 200px; height: 200px; image-rendering: pixelated;' });
      card.appendChild(qrImg);
      card.appendChild(h('p', { className: 'text-xs text-slate-500 text-center mb-4 font-mono break-all' }, `Manuel giriş: ${res.secret}`));
      const verifyForm = h('div', { className: 'space-y-3' });
      verifyForm.innerHTML = `
        <div><label class="block text-sm text-slate-400 mb-1">Uygulamadaki 6 haneli kodu girin</label>
        <input id="v-code" type="text" class="input w-full text-center text-lg tracking-widest" maxlength="6" placeholder="000000" autocomplete="one-time-code"></div>
        <button id="v-btn" class="btn btn-primary w-full justify-center">Doğrula ve Etkinleştir</button>`;
      card.appendChild(verifyForm);
      card.querySelector('#v-code').focus();
      card.querySelector('#v-btn').onclick = async () => {
        try {
          await API.verify2FA(card.querySelector('#v-code').value);
          Router.navigate('/security');
        } catch (e) { alert(e.message); }
      };
      card.querySelector('#v-code').onkeydown = (e) => {
        if (e.key === 'Enter') card.querySelector('#v-btn').click();
      };
    }}, '2FA Kurulumunu Başlat');
    card.appendChild(setupBtn);
  }
  el.appendChild(card);
};

// ── Client Deploy ──────────────────────────────────────────────────

Pages.deploy = async (el) => {
  let cfg = await API.deployConfig();
  let activeMainTab = 'custom';

  el.innerHTML = '';
  el.appendChild(h('h1', { className: 'text-2xl font-bold text-white mb-2' }, 'Client Dağıtımı'));
  el.appendChild(h('p', { className: 'text-slate-400 mb-6 text-sm' }, 'Özel markalı RustDesk istemcisi oluşturun veya hızlı kurulum scriptleri kullanın.'));

  // ── Main tabs: Custom Client vs Quick Deploy ──
  const mainTabBar = h('div', { className: 'flex gap-1 mb-6 bg-slate-800 rounded-lg p-1 border border-slate-700 w-fit' });
  const tabCustom = h('button', { className: 'px-4 py-2 rounded-md text-sm font-medium transition-colors' }, 'Özel Client (RDGen)');
  const tabQuick = h('button', { className: 'px-4 py-2 rounded-md text-sm font-medium transition-colors' }, 'Hızlı Dağıtım (Script)');
  mainTabBar.appendChild(tabCustom);
  mainTabBar.appendChild(tabQuick);
  el.appendChild(mainTabBar);

  const mainContent = h('div');
  el.appendChild(mainContent);

  function setMainTab(tab) {
    activeMainTab = tab;
    tabCustom.className = `px-4 py-2 rounded-md text-sm font-medium transition-colors ${tab === 'custom' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`;
    tabQuick.className = `px-4 py-2 rounded-md text-sm font-medium transition-colors ${tab === 'quick' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-white'}`;
    if (tab === 'custom') renderCustomTab();
    else renderQuickTab();
  }
  tabCustom.onclick = () => setMainTab('custom');
  tabQuick.onclick = () => setMainTab('quick');

  // ════════════════════════════════════════════════════════════════
  //  CUSTOM CLIENT TAB (RDGen)
  // ════════════════════════════════════════════════════════════════
  let buildPollTimer = null;

  function renderCustomTab() {
    if (buildPollTimer) { clearInterval(buildPollTimer); buildPollTimer = null; }
    mainContent.innerHTML = '';

    // ── Server + branding config ──
    const card = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl p-6 mb-6' });
    card.innerHTML = `
      <h2 class="text-lg font-semibold text-white mb-4">Sunucu & Marka Ayarları</h2>
      ${cfg.rdgen_internal ? `
      <div class="mb-4 bg-slate-900/50 border border-slate-600 rounded-lg p-4">
        <p class="text-sm text-slate-300"><strong>RDGen entegre mod:</strong> Build istekleri bu API konteynerinden Docker ağındaki RDGen servisine gider. İndirme bağlantıları doğrudan bu yönetim paneli üzerinden (admin oturumu ile) verilir; ayrı bir RDGen web adresi açmanız gerekmez.</p>
        <p class="text-xs text-amber-200/90 mt-2 bg-amber-900/20 border border-amber-800/40 rounded px-2 py-1.5"><strong>Not:</strong> <code class="bg-slate-800 px-1 rounded">http://IP:8080</code> ile RDGen sayfasını tarayıcıda açarsanız konsolda &quot;Cross-Origin-Opener-Policy / untrustworthy origin&quot; uyarısı görülebilir; bu HTTP+düz IP kullanımından kaynaklanır. Özel client oluşturmayı <strong>buradan</strong> (Build Başlat) yapın; doğrudan 8080 kullanmayın. Zorunluysa RDGen için HTTPS + alan adı (Nginx/Caddy) kullanın.</p>
        <p class="text-xs text-slate-500 mt-2">GitHub Actions&apos;ın derlenmiş dosyayı geri yükleyebilmesi için fork repo <code class="bg-slate-800 px-1 rounded">GENURL</code> değeri hâlâ internetten erişilebilir bir adres olmalı (tercihen HTTPS + alan adı veya Nginx ters proxy).</p>
        <p class="text-xs text-slate-500 mt-1">Ters proxy kullanıyorsanız sunucuda <code class="bg-slate-800 px-1 rounded">PUBLIC_BASE_URL</code> ortam değişkenini (örn. <code class="bg-slate-800 px-1 rounded">https://panel.example.com</code>) tanımlayın; böylece indirme linkleri doğru kök adresi kullanır.</p>
      </div>
      ` : `
      <div class="mb-4">
        <label class="block text-sm text-slate-400 mb-1">RDGen Sunucu URL</label>
        <div class="flex items-center gap-2">
          <input id="rc-rdgen-url" class="input flex-1" placeholder="https://rdgen.crayoneater.org" value="${esc(cfg.rdgen_url || '')}">
          <button id="rc-rdgen-help" class="btn text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 whitespace-nowrap" type="button">Self-Host Rehberi</button>
        </div>
        <p class="text-xs text-slate-500 mt-1">Boş bırakılırsa varsayılan public instance (rdgen.crayoneater.org) kullanılır.</p>
      </div>
      `}
      <div class="mb-4">
        <label class="block text-sm text-slate-400 mb-1">Self-Hosted Runner Anahtarı (SH_SECRET)</label>
        <div class="flex items-center gap-2">
          <input id="rc-sh-secret" type="password" class="input flex-1" placeholder="Opsiyonel — yalnızca self-hosted runner kullanıyorsanız" value="${esc(cfg.sh_secret || '')}">
          <button type="button" class="btn text-xs bg-slate-700 hover:bg-slate-600 text-slate-300" onclick="const i=this.previousElementSibling;i.type=i.type==='password'?'text':'password';this.textContent=i.type==='password'?'Göster':'Gizle'">Göster</button>
        </div>
        <p class="text-xs text-slate-500 mt-1">Self-hosted GitHub runner kullanıyorsanız runner makinesindeki SH_SECRET değerini buraya girin. Build'ler runner üzerinde çalışır (~5-10 dk).</p>
      </div>
      ${!cfg.rdgen_internal ? `
      <div id="rc-rdgen-guide" class="hidden mb-4 bg-slate-900 border border-slate-600 rounded-lg p-5 text-sm text-slate-300 leading-relaxed">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-white font-semibold">RDGen Self-Host Kurulum Rehberi</h3>
          <button id="rc-rdgen-guide-close" class="text-slate-500 hover:text-white text-lg">&times;</button>
        </div>
        <p class="mb-3">Kendi RDGen sunucunuzu kurarak build'leri bağımsız şekilde tetikleyebilirsiniz. Kurulum adımları:</p>
        <ol class="list-decimal list-inside space-y-2 mb-3">
          <li><strong>GitHub Fork:</strong> <a href="https://github.com/bryangerlach/rdgen" target="_blank" class="text-blue-400 underline">bryangerlach/rdgen</a> repo'sunu kendi GitHub hesabınıza fork'layın.</li>
          <li><strong>GitHub Token:</strong> Settings &rarr; Developer Settings &rarr; Fine-grained Tokens &rarr; Yeni token oluşturun. Sadece fork'ladığınız rdgen repo'sunu seçin, <em>Actions</em> ve <em>Workflows</em> için Read & Write izni verin.</li>
          <li><strong>GitHub Secrets:</strong> Fork'ladığınız repo &rarr; Settings &rarr; Secrets &rarr; Actions &rarr; İki secret ekleyin:
            <ul class="list-disc list-inside ml-4 mt-1">
              <li><code class="bg-slate-800 px-1 rounded">GENURL</code> = RDGen sunucunuzun erişilebilir URL'si (ör: https://rdgen.sizedomain.com)</li>
              <li><code class="bg-slate-800 px-1 rounded">ZIP_PASSWORD</code> = Rastgele güçlü bir şifre</li>
            </ul>
          </li>
          <li><strong>Actions Aktif:</strong> Fork repo &rarr; Actions sekmesi &rarr; yeşil "I understand, enable Actions" butonuna tıklayın.</li>
          <li><strong>Docker Compose:</strong> docker-compose.yml dosyanızdaki <code class="bg-slate-800 px-1 rounded">rdgen</code> servisinin environment değişkenlerini doldurun (GHUSER, GHBEARER, ZIP_PASSWORD, GENURL).</li>
          <li><strong>Başlatın:</strong> <code class="bg-slate-800 px-1 rounded">docker compose up -d rdgen</code></li>
        </ol>
        <div class="bg-slate-800 border border-slate-700 rounded p-3 mb-3">
          <p class="text-xs text-slate-400 mb-2 font-semibold">Build Süresini Hızlandırma (Opsiyonel)</p>
          <p class="text-xs text-slate-400">Build'ler GitHub Actions üzerinde çalışır (~30-45 dk). Hızlandırmak için güçlü bir Windows makinede <strong>self-hosted GitHub runner</strong> kurabilirsiniz:</p>
          <ol class="list-decimal list-inside text-xs text-slate-400 mt-1 space-y-1">
            <li>Fork repo &rarr; Settings &rarr; Actions &rarr; Runners &rarr; "New self-hosted runner"</li>
            <li>Runner'ı Windows makineye kurun (RustDesk build ortamı hazır olmalı)</li>
            <li>Makineye <code class="bg-slate-700 px-1 rounded">SH_SECRET</code> environment variable tanımlayın</li>
            <li>Sonraki build'ler cache sayesinde <strong>~5-10 dk</strong>'ya düşebilir</li>
          </ol>
        </div>
        <p class="text-xs text-slate-500">Detaylı bilgi: <a href="https://github.com/bryangerlach/rdgen/blob/master/setup.md" target="_blank" class="text-blue-400 underline">setup.md</a></p>
      </div>
      ` : ''}
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div>
          <label class="block text-sm text-slate-400 mb-1">Sunucu Adresi *</label>
          <input id="rc-host" class="input w-full" placeholder="rustdesk.example.com" value="${esc(cfg.host)}">
        </div>
        <div>
          <label class="block text-sm text-slate-400 mb-1">API URL</label>
          <input id="rc-api" class="input w-full" placeholder="http://host:21114" value="${esc(cfg.api)}">
        </div>
        <div>
          <label class="block text-sm text-slate-400 mb-1">Relay (opsiyonel)</label>
          <input id="rc-relay" class="input w-full" value="${esc(cfg.relay)}">
        </div>
      </div>
      <div class="mb-4">
        <label class="block text-sm text-slate-400 mb-1">Public Key (otomatik)</label>
        <input class="input w-full bg-slate-900 text-slate-500 cursor-not-allowed" readonly value="${esc(cfg.key) || 'Bulunamadı'}">
      </div>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div>
          <label class="block text-sm text-slate-400 mb-1">Uygulama Adı</label>
          <input id="rc-appname" class="input w-full" placeholder="Radamath Remote" value="${esc(cfg.appname)}">
        </div>
        <div>
          <label class="block text-sm text-slate-400 mb-1">Dosya Adı (boşluksuz)</label>
          <input id="rc-exename" class="input w-full" placeholder="RadamathRemote" value="${esc(cfg.exename)}">
        </div>
        <div>
          <label class="block text-sm text-slate-400 mb-1">Şirket Adı</label>
          <input id="rc-compname" class="input w-full" placeholder="Şirketiniz" value="${esc(cfg.compname)}">
        </div>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
        <div>
          <label class="block text-sm text-slate-400 mb-1">Uygulama İkonu (PNG, 256x256)</label>
          <div class="flex items-center gap-2 flex-wrap">
            <input type="file" id="rc-icon-file" accept=".png" class="text-sm text-slate-400 file:mr-2 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-sm file:bg-slate-700 file:text-slate-300 hover:file:bg-slate-600">
            <button type="button" id="rc-icon-clear" class="text-sm px-2 py-1 rounded border border-slate-600 text-slate-400 hover:bg-slate-700 hover:text-red-300" title="Kayıtlı ikonu sil">Kaldır</button>
            <div id="rc-icon-preview" class="w-10 h-10 shrink-0 rounded bg-slate-700 flex items-center justify-center overflow-hidden">${cfg.iconbase64 ? '<img src="data:image/png;base64,' + cfg.iconbase64 + '" class="w-full h-full object-contain">' : '<span class="text-slate-500 text-xs">Yok</span>'}</div>
          </div>
        </div>
        <div>
          <label class="block text-sm text-slate-400 mb-1">Uygulama Logosu (PNG)</label>
          <div class="flex items-center gap-2 flex-wrap">
            <input type="file" id="rc-logo-file" accept=".png" class="text-sm text-slate-400 file:mr-2 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-sm file:bg-slate-700 file:text-slate-300 hover:file:bg-slate-600">
            <button type="button" id="rc-logo-clear" class="text-sm px-2 py-1 rounded border border-slate-600 text-slate-400 hover:bg-slate-700 hover:text-red-300" title="Kayıtlı logoyu sil">Kaldır</button>
            <div id="rc-logo-preview" class="w-10 h-10 shrink-0 rounded bg-slate-700 flex items-center justify-center overflow-hidden">${cfg.logobase64 ? '<img src="data:image/png;base64,' + cfg.logobase64 + '" class="w-full h-full object-contain">' : '<span class="text-slate-500 text-xs">Yok</span>'}</div>
          </div>
        </div>
      </div>
      <button id="rc-save" class="btn btn-primary">Ayarları Kaydet</button>
      <span id="rc-save-ok" class="ml-3 text-sm text-green-400 hidden">Kaydedildi</span>
    `;
    mainContent.appendChild(card);

    let iconB64 = cfg.iconbase64 || '';
    let logoB64 = cfg.logobase64 || '';

    function handleFileInput(inputId, previewId, setter) {
      card.querySelector(inputId).onchange = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
          const b64 = reader.result.split(',')[1];
          setter(b64);
          card.querySelector(previewId).innerHTML = `<img src="${reader.result}" class="w-full h-full object-contain">`;
        };
        reader.readAsDataURL(file);
      };
    }
    handleFileInput('#rc-icon-file', '#rc-icon-preview', v => { iconB64 = v; });
    handleFileInput('#rc-logo-file', '#rc-logo-preview', v => { logoB64 = v; });

    function clearIcon() {
      iconB64 = '';
      const inp = card.querySelector('#rc-icon-file');
      if (inp) inp.value = '';
      card.querySelector('#rc-icon-preview').innerHTML = '<span class="text-slate-500 text-xs">Yok</span>';
    }
    function clearLogo() {
      logoB64 = '';
      const inp = card.querySelector('#rc-logo-file');
      if (inp) inp.value = '';
      card.querySelector('#rc-logo-preview').innerHTML = '<span class="text-slate-500 text-xs">Yok</span>';
    }
    card.querySelector('#rc-icon-clear').onclick = clearIcon;
    card.querySelector('#rc-logo-clear').onclick = clearLogo;

    if (!cfg.rdgen_internal) {
      const guidePanel = card.querySelector('#rc-rdgen-guide');
      const helpBtn = card.querySelector('#rc-rdgen-help');
      if (guidePanel && helpBtn) {
        helpBtn.onclick = () => guidePanel.classList.toggle('hidden');
        card.querySelector('#rc-rdgen-guide-close').onclick = () => guidePanel.classList.add('hidden');
      }
    }

    card.querySelector('#rc-save').onclick = async () => {
      const data = {
        sh_secret: card.querySelector('#rc-sh-secret').value.trim(),
        host: card.querySelector('#rc-host').value.trim(),
        api: card.querySelector('#rc-api').value.trim(),
        relay: card.querySelector('#rc-relay').value.trim(),
        appname: card.querySelector('#rc-appname').value.trim(),
        exename: card.querySelector('#rc-exename').value.trim(),
        compname: card.querySelector('#rc-compname').value.trim(),
        iconbase64: iconB64,
        logobase64: logoB64,
      };
      if (!cfg.rdgen_internal) {
        const ru = card.querySelector('#rc-rdgen-url');
        if (ru) data.rdgen_url = ru.value.trim();
      }
      await API.updateDeployConfig(data);
      Object.assign(cfg, data);
      const ok = card.querySelector('#rc-save-ok');
      ok.classList.remove('hidden');
      setTimeout(() => ok.classList.add('hidden'), 2500);
    };

    // ── Build section ──
    const buildCard = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl p-6 mb-6' });
    buildCard.innerHTML = `
      <h2 class="text-lg font-semibold text-white mb-4">Client Build</h2>
      <div class="flex flex-wrap gap-4 items-end mb-4">
        <div>
          <label class="block text-sm text-slate-400 mb-1">Platform</label>
          <select id="rc-platform" class="input">
            <option value="windows">Windows 64-bit</option>
            <option value="windows-x86">Windows 32-bit</option>
            <option value="linux">Linux</option>
            <option value="macos">macOS</option>
            <option value="android">Android</option>
          </select>
        </div>
        <div>
          <label class="block text-sm text-slate-400 mb-1">RustDesk Sürümü</label>
          <select id="rc-version" class="input">
            <option value="nightly">Nightly</option>
            <option value="1.4.6" selected>1.4.6</option>
            <option value="1.4.5">1.4.5</option>
            <option value="1.4.4">1.4.4</option>
            <option value="1.4.3">1.4.3</option>
            <option value="1.3.9">1.3.9</option>
          </select>
        </div>
        <button id="rc-build-btn" class="btn btn-primary">Build Başlat</button>
      </div>
      <div id="rc-build-status" class="hidden">
        <div class="flex items-center gap-3 mb-2">
          <div class="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" id="rc-spinner"></div>
          <span class="text-sm text-blue-300" id="rc-stage-text">Başlatılıyor...</span>
        </div>
        <div class="w-full bg-slate-700 rounded-full h-2">
          <div id="rc-progress-bar" class="bg-blue-500 h-2 rounded-full transition-all duration-500" style="width: 5%"></div>
        </div>
        <p class="text-xs text-slate-500 mt-2">Build süresi: ~30-45 dakika. Bu sayfayı açık tutun.</p>
      </div>
      <div id="rc-build-error" class="hidden mt-3 bg-red-900/30 border border-red-700/50 rounded-lg p-3 text-sm text-red-300"></div>
    `;
    mainContent.appendChild(buildCard);

    // ── Downloads section ──
    const dlCard = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl p-6', id: 'rc-downloads-card' });
    dlCard.innerHTML = '<h2 class="text-lg font-semibold text-white mb-4">İndirmeler</h2><div id="rc-dl-list" class="text-sm text-slate-500">Henüz build yapılmadı.</div>';
    mainContent.appendChild(dlCard);

    // Build button handler
    buildCard.querySelector('#rc-build-btn').onclick = async () => {
      const btn = buildCard.querySelector('#rc-build-btn');
      const statusDiv = buildCard.querySelector('#rc-build-status');
      const errDiv = buildCard.querySelector('#rc-build-error');
      errDiv.classList.add('hidden');
      btn.disabled = true;
      btn.textContent = 'Gönderiliyor...';

      try {
        const res = await API.startBuild({
          platform: buildCard.querySelector('#rc-platform').value,
          version: buildCard.querySelector('#rc-version').value,
        });
        statusDiv.classList.remove('hidden');
        buildCard.querySelector('#rc-stage-text').textContent = res.stage || 'Build kuyruğa alındı...';
        renderDownloads(res.downloads || []);
        startPolling();
      } catch (e) {
        errDiv.textContent = e.message;
        errDiv.classList.remove('hidden');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Build Başlat';
      }
    };

    function startPolling() {
      if (buildPollTimer) clearInterval(buildPollTimer);
      let elapsed = 0;
      buildPollTimer = setInterval(async () => {
        elapsed += 15;
        try {
          const s = await API.buildStatus();
          const stageEl = buildCard.querySelector('#rc-stage-text');
          const bar = buildCard.querySelector('#rc-progress-bar');
          const spinner = buildCard.querySelector('#rc-spinner');
          if (stageEl) stageEl.textContent = s.stage || '...';
          const pct = Math.min(5 + (elapsed / 2700) * 90, 95);
          if (bar) bar.style.width = (s.status === 'completed' ? 100 : pct) + '%';

          if (s.status === 'completed') {
            clearInterval(buildPollTimer);
            buildPollTimer = null;
            if (stageEl) stageEl.textContent = 'Build tamamlandı!';
            if (stageEl) stageEl.className = 'text-sm text-green-400 font-medium';
            if (spinner) spinner.className = 'w-4 h-4 text-green-400';
            if (spinner) spinner.innerHTML = '<svg fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>';
            toast('Build tamamlandı! İndirme linkleri hazır.');
            renderDownloads(s.downloads || []);
          } else if (s.status === 'error') {
            clearInterval(buildPollTimer);
            buildPollTimer = null;
            const errDiv = buildCard.querySelector('#rc-build-error');
            if (errDiv) { errDiv.textContent = s.stage; errDiv.classList.remove('hidden'); }
            buildCard.querySelector('#rc-build-status')?.classList.add('hidden');
          }
        } catch { /* network blip, keep polling */ }
      }, 15000);
    }

    function renderDownloads(links) {
      const list = document.querySelector('#rc-dl-list');
      if (!list) return;
      if (!links.length) { list.innerHTML = '<span class="text-slate-500">Henüz build yapılmadı.</span>'; return; }
      list.innerHTML = '';
      for (const dl of links) {
        const row = h('a', {
          href: dl.url,
          target: '_blank',
          className: 'flex items-center gap-3 px-4 py-3 rounded-lg bg-slate-700/50 hover:bg-slate-700 transition-colors mb-2 group',
        });
        row.innerHTML = `
          <svg class="w-5 h-5 text-blue-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
          <span class="text-slate-200 group-hover:text-white text-sm">${dl.label}</span>
        `;
        list.appendChild(row);
      }
    }

    // Check for existing build on load
    API.buildStatus().then(s => {
      if (s.status === 'generating') {
        buildCard.querySelector('#rc-build-status').classList.remove('hidden');
        buildCard.querySelector('#rc-stage-text').textContent = s.stage || 'Devam ediyor...';
        renderDownloads(s.downloads || []);
        startPolling();
      } else if (s.status === 'completed') {
        renderDownloads(s.downloads || []);
      }
    }).catch(() => {});
  }

  // ════════════════════════════════════════════════════════════════
  //  QUICK DEPLOY TAB (Scripts)
  // ════════════════════════════════════════════════════════════════
  function renderQuickTab() {
    if (buildPollTimer) { clearInterval(buildPollTimer); buildPollTimer = null; }
    mainContent.innerHTML = '';

    // Config string
    const cfgStr = `${cfg.host || ''},key=${cfg.key || ''},api=${cfg.api || ''},relay=${cfg.relay || ''}`;
    const cfgCard = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl p-6 mb-6' });
    cfgCard.innerHTML = `
      <h2 class="text-lg font-semibold text-white mb-3">Config String</h2>
      <p class="text-xs text-slate-500 mb-2">RustDesk istemcisinde Ayarlar → Ağ → Sunucu Yapılandırmasını İçe Aktar'a yapıştırın.</p>
      <div class="flex gap-2">
        <code class="flex-1 bg-slate-900 text-green-400 px-4 py-3 rounded-lg text-xs font-mono break-all select-all">${esc(cfgStr)}</code>
        <button class="btn btn-ghost text-xs self-start" id="qs-copy-cfg">Kopyala</button>
      </div>
    `;
    mainContent.appendChild(cfgCard);
    cfgCard.querySelector('#qs-copy-cfg').onclick = () => { navigator.clipboard.writeText(cfgStr); toast('Kopyalandı'); };

    // Script section
    const scriptCard = h('div', { className: 'bg-slate-800 border border-slate-700 rounded-xl overflow-hidden' });
    mainContent.appendChild(scriptCard);

    const platforms = [
      { id: 'windows', label: 'Windows', ext: '.ps1' },
      { id: 'linux', label: 'Linux', ext: '.sh' },
      { id: 'macos', label: 'macOS', ext: '.sh' },
    ];
    let qsPlatform = 'windows';
    let qsCache = {};

    function renderQS() {
      scriptCard.innerHTML = '';
      const tabs = h('div', { className: 'flex border-b border-slate-700' });
      for (const p of platforms) {
        tabs.appendChild(h('button', {
          className: `px-5 py-3 text-sm font-medium transition-colors ${p.id === qsPlatform ? 'text-blue-400 border-b-2 border-blue-400 bg-slate-700/30' : 'text-slate-400 hover:text-white'}`,
          onclick: () => { qsPlatform = p.id; renderQS(); },
        }, p.label));
      }
      scriptCard.appendChild(tabs);

      const body = h('div', { className: 'p-6' });
      scriptCard.appendChild(body);

      if (!cfg.host || !cfg.key) {
        body.innerHTML = '<div class="text-center py-8 text-slate-500">Önce Özel Client sekmesinden sunucu adresini kaydedin.</div>';
        return;
      }

      body.innerHTML = '<div class="text-center py-8 text-slate-500">Yükleniyor...</div>';

      if (qsCache[qsPlatform]) { showQSScript(body, qsCache[qsPlatform]); return; }

      API.deployScript(qsPlatform, 'random').then(s => { qsCache[qsPlatform] = s; showQSScript(body, s); })
        .catch(e => { body.innerHTML = `<div class="text-center py-8 text-red-400">${e.message}</div>`; });
    }

    function showQSScript(container, script) {
      const p = platforms.find(x => x.id === qsPlatform);
      container.innerHTML = '';
      const toolbar = h('div', { className: 'flex justify-between items-center mb-3' });
      toolbar.appendChild(h('span', { className: 'text-sm text-slate-400' }, `${p.label} Kurulum Scripti`));
      const btns = h('div', { className: 'flex gap-2' });
      btns.appendChild(h('button', { className: 'btn btn-ghost text-xs', onclick: () => { navigator.clipboard.writeText(script); toast('Kopyalandı'); } }, 'Kopyala'));
      btns.appendChild(h('button', { className: 'btn btn-primary text-xs', onclick: () => {
        const blob = new Blob([script], { type: 'text/plain' });
        const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `rustdesk-install-${qsPlatform}${p.ext}`; a.click();
      }}, 'İndir'));
      toolbar.appendChild(btns);
      container.appendChild(toolbar);
      const pre = h('pre', { className: 'bg-slate-900 text-green-400 p-4 rounded-lg text-xs font-mono overflow-x-auto max-h-80 leading-relaxed' });
      pre.textContent = script;
      container.appendChild(pre);
    }

    renderQS();
  }

  function esc(s) { return (s || '').replace(/"/g, '&quot;').replace(/</g, '&lt;'); }

  setMainTab('custom');
};

// ── Boot ───────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => App.init());
