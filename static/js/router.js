const Router = {
  routes: {},
  currentPage: null,

  register(path, handler) {
    this.routes[path] = handler;
  },

  async navigate(path) {
    if (window.location.hash !== `#${path}`) {
      window.location.hash = path;
      return;
    }
    await this._load(path);
  },

  async _load(path) {
    const basePath = path.split('?')[0];
    const handler = this.routes[basePath] || this.routes['/404'];
    if (handler) {
      this.currentPage = basePath;
      document.querySelectorAll('[data-nav]').forEach(el => {
        el.classList.toggle('bg-slate-700', el.dataset.nav === basePath);
        el.classList.toggle('text-white', el.dataset.nav === basePath);
      });
      const content = document.getElementById('page-content');
      if (content) {
        content.innerHTML = '<div class="flex items-center justify-center h-64"><div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div></div>';
        try {
          await handler(content);
        } catch (e) {
          content.innerHTML = `<div class="bg-red-900/50 border border-red-500 p-4 rounded-lg text-red-200">${e.message}</div>`;
        }
      }
    }
  },

  init() {
    window.addEventListener('hashchange', () => {
      const path = window.location.hash.slice(1) || '/dashboard';
      this._load(path);
    });
    const path = window.location.hash.slice(1) || '/dashboard';
    this._load(path);
  },
};
