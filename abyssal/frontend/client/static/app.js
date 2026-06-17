/* Abyssal — Minimal I2P Search Frontend */

const API = '/api/abyssal';
const PER_PAGE = 20;

/* ── Router ─────────────────────────────────────────────────────────────── */

function route() {
  const path = location.pathname.replace(/\/$/, '') || '/';
  const hash = location.hash.slice(1) || '/';
  const page = hash || path;
  const [base, ...rest] = page.split('/').filter(Boolean);
  switch (base) {
    case 'browse':      renderPage(DirectoryPage); break;
    case 'site':        renderPage(SiteDetailPage, rest[0]); break;
    case 'wayback':     renderPage(WaybackPage); break;
    case 'addressbook': renderPage(AddressBookPage); break;
    default:            renderPage(SearchPage); break;
  }
}

function navigate(url) {
  history.pushState(null, '', url);
  route();
}

window.addEventListener('popstate', route);
document.addEventListener('DOMContentLoaded', route);

/* ── Page Rendering ─────────────────────────────────────────────────────── */

async function renderPage(Page, ...args) {
  const m = document.getElementById('main');
  m.innerHTML = '<p class="loading">Loading...</p>';
  try {
    const p = new Page(m, ...args);
    await p.render();
  } catch (e) {
    m.innerHTML = `<div class="card"><p>Error: ${e.message}</p></div>`;
  }
}

/* ── API Helper ─────────────────────────────────────────────────────────── */

async function api(url, params = {}) {
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&');
  const full = `${API}${url}${qs ? '?' + qs : ''}`;
  const r = await fetch(full);
  if (!r.ok) throw new Error(`API ${r.status}: ${await r.text()}`);
  return r.json();
}

/* ── Helpers ────────────────────────────────────────────────────────────── */

function esc(s) { return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]); }

function safeId(s) { return 'id-' + String(s).replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 100); }

function statusBadge(online) {
  return `<span class="badge ${online ? 'online' : 'offline'}">${online ? 'Online' : 'Offline'}</span>`;
}

function extractHostname(url) {
  try { return new URL(url).hostname; } catch (_) { return url; }
}

function highlight(text, query) {
  if (!query) return esc(text);
  const re = new RegExp(`(${esc(query).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return esc(text).replace(re, '<mark style="background:#264f78;color:#e6edf3;padding:0 2px">$1</mark>');
}

function pageNav(page, total, cb) {
  const last = Math.ceil(total / PER_PAGE);
  if (last <= 1) return '';
  const d = document.createElement('div');
  d.className = 'pagination';
  d.innerHTML = `
    <button class="prev" ${page <= 1 ? 'disabled' : ''}>Prev</button>
    <span>Page ${page} of ${last}</span>
    <button class="next" ${page >= last ? 'disabled' : ''}>Next</button>
  `;
  d.querySelector('.prev').onclick = () => cb(page - 1);
  d.querySelector('.next').onclick = () => cb(page + 1);
  return d.outerHTML;
}

/* ── Search Page ────────────────────────────────────────────────────────── */

class SearchPage {
  constructor(mount) { this.m = mount; this.q = ''; this.page = 1; this.lang = ''; this.type = ''; }

  async render() {
    this.m.innerHTML = `
      <div class="search-box">
        <input id="sq" type="text" placeholder="Search I2P sites..." value="${esc(this.q)}">
        <button id="sb">Search</button>
      </div>
      <div class="filters">
        <select id="flang"><option value="">All languages</option></select>
        <select id="ftype"><option value="">All types</option></select>
      </div>
      <div id="results"></div>
    `;
    this.inp = document.getElementById('sq');
    this.btn = document.getElementById('sb');
    this.res = document.getElementById('results');
    this.flang = document.getElementById('flang');
    this.ftype = document.getElementById('ftype');

    try {
      const f = await api('/facets');
      const langOpts = (f.languages || []).map(l => `<option value="${esc(l.language)}">${esc(l.language)} (${l.count})</option>`).join('');
      const typeOpts = (f.site_types || []).map(t => `<option value="${esc(t.site_type)}">${esc(t.site_type)} (${t.count})</option>`).join('');
      this.flang.innerHTML += langOpts;
      this.ftype.innerHTML += typeOpts;
    } catch (_) {}

    this.btn.onclick = () => this.search(1);
    this.inp.onkeydown = (e) => { if (e.key === 'Enter') this.search(1); };
    this.flang.onchange = () => this.search(1);
    this.ftype.onchange = () => this.search(1);

    const p = new URLSearchParams(location.search);
    if (p.get('q')) { this.q = p.get('q'); this.inp.value = this.q; this.page = parseInt(p.get('page')) || 1; this.lang = p.get('lang') || ''; this.type = p.get('site_type') || ''; this.flang.value = this.lang; this.ftype.value = this.type; this.search(this.page); }
  }

  async search(page) {
    this.q = this.inp.value;
    this.lang = this.flang.value;
    this.type = this.ftype.value;
    this.page = page;
    const qs = `q=${encodeURIComponent(this.q)}&page=${page}&per_page=${PER_PAGE}&lang=${encodeURIComponent(this.lang)}&site_type=${encodeURIComponent(this.type)}`;
    navigate(`/?${qs}`);
    this.res.innerHTML = '<p class="loading">Searching...</p>';
    try {
      const d = await api(`/search?${qs}`);
      if (!d.results || d.results.length === 0) {
        this.res.innerHTML = '<p>No results found.</p>';
        return;
      }
      this.res.innerHTML = d.results.map(r => {
        const hostname = extractHostname(r.url);
        return card(`
          <h3><a href="/site/${esc(hostname)}">${highlight(r.title || hostname, this.q)}</a></h3>
          <div class="meta">${esc(hostname)} ${r.language ? '· ' + esc(r.language) : ''} ${r.site_type ? '· ' + esc(r.site_type) : ''}</div>
          ${r.snippet ? `<div class="snippet">${r.snippet}</div>` : ''}
          <div class="tags">${r.status_code ? `<span class="tag">HTTP ${r.status_code}</span>` : ''}</div>
        `);
      }).join('') + pageNav(page, d.total, (p) => this.search(p));
    } catch (e) {
      this.res.innerHTML = `<p>Error: ${e.message}</p>`;
    }
  }
}

/* ── Directory Page ─────────────────────────────────────────────────────── */

class DirectoryPage {
  constructor(mount) { this.m = mount; this.page = 1; }

  async render() {
    this.m.innerHTML = `<h1>Site Directory</h1><div id="dir-list"><p class="loading"></p></div>`;
    const dl = document.getElementById('dir-list');
    try {
      const d = await api(`/sites`, { page: this.page, per_page: PER_PAGE });
      if (!d.results || d.results.length === 0) { dl.innerHTML = '<p>No sites discovered yet.</p>'; return; }
      dl.innerHTML = `
        <table><thead><tr><th>Site</th><th>Status</th><th>Language</th><th>Type</th><th>Last Seen</th></tr></thead>
        <tbody>${d.results.map(s => {
          const online = s.checks_online > s.checks_offline && s.checks_online > 0;
          return `<tr>
            <td><a href="/site/${esc(s.hostname)}">${esc(s.hostname)}</a></td>
            <td>${statusBadge(online)}</td>
            <td>${s.language ? esc(s.language) : '-'}</td>
            <td>${s.site_type ? esc(s.site_type) : '-'}</td>
            <td>${s.last_seen_online ? new Date(s.last_seen_online).toLocaleDateString() : 'never'}</td>
          </tr>`;
        }).join('')}</tbody></table>
      ` + pageNav(this.page, d.total, (p) => { this.page = p; this.render(); });
    } catch (e) { dl.innerHTML = `<p>Error: ${e.message}</p>`; }
  }
}

/* ── Site Detail Page ───────────────────────────────────────────────────── */

class SiteDetailPage {
  constructor(mount, hostname) { this.m = mount; this.hostname = hostname; }

  async render() {
    this.m.innerHTML = `<a href="javascript:history.back()" style="color:var(--muted);font-size:0.9rem">← Back</a><h1>${esc(this.hostname)}</h1>`;
    try {
      const s = await api(`/sites/${encodeURIComponent(this.hostname)}`);
      const online = s.checks_online > s.checks_offline && s.checks_online > 0;
      this.m.innerHTML += `
        <div class="card">
          <div class="meta">Language: ${s.language || '-'} · Type: ${s.site_type || '-'} · ${statusBadge(online)}</div>
          ${s.b32 ? `<div class="meta" style="word-break:break-all">b32: ${esc(s.b32)}</div>` : ''}
        </div>
        <h2>Pages (${s.pages ? s.pages.length : 0})</h2>
        ${this.renderTree(s.page_tree || [])}
      `;
    } catch (e) {
      this.m.innerHTML += `<p>Error: ${e.message}</p>`;
    }
  }

  renderTree(nodes) {
    if (!nodes || nodes.length === 0) return '<p>No pages.</p>';
    let html = '<div class="tree">';
    for (const n of nodes) {
      if (n.name === '(index)') continue;
      if (n.type === 'dir') {
        html += `<div class="folder"><div class="folder-toggle" onclick="this.parentElement.classList.toggle('open')">${esc(n.name)}</div><div class="folder-children">${this.renderTree(n.children)}</div></div>`;
      } else if (n.page) {
        const title = n.page.title || n.name;
        html += `<div class="file"><a href="/" onclick="return false">${esc(title)}</a></div>`;
      }
    }
    html += '</div>';
    return html;
  }
}

/* ── Wayback Page ───────────────────────────────────────────────────────── */

class WaybackPage {
  constructor(mount) { this.m = mount; }

  async render() {
    this.m.innerHTML = `<h1>Wayback Machine</h1><div id="wb"><p class="loading"></p></div>`;
    const wb = document.getElementById('wb');
    try {
      const stats = await api('/wayback/stats');
      wb.innerHTML = `
        <div class="card">
          <div class="meta">Total snapshots: ${stats.total_snapshots}</div>
          <div class="meta">Total URLs: ${stats.total_urls}</div>
          <div class="meta">Archive size: ${stats.archive_size || 'N/A'}</div>
        </div>
      `;

      const urls = await api('/wayback/urls');
      if (Array.isArray(urls) && urls.length > 0) {
        const recent = urls.slice(0, PER_PAGE);
        wb.innerHTML += `<h2>Recent URLs</h2>${recent.map(u => `
          <div class="card snapshot">
            <div><a href="${esc(u.url)}" target="_blank">${esc(u.title || u.url)}</a></div>
            <div class="time">Captures: ${u.capture_count || 0} · <a href="#" onclick="showSnapshots('${safeId(u.url)}');return false">View snapshots</a></div>
            <div id="${safeId(u.url)}"></div>
          </div>
        `).join('')}`;
        this._urlMap = {};
        recent.forEach(u => { this._urlMap[safeId(u.url)] = u.url; });
        window._wbUrlMap = this._urlMap;
      }
    } catch (e) { wb.innerHTML = `<p>Error: ${e.message}</p>`; }
  }
}

window.showSnapshots = async function(id) {
  const el = document.getElementById(id);
  if (!el) return;
  const url = (window._wbUrlMap || {})[id];
  if (!url) { el.innerHTML = '<p>No URL data.</p>'; return; }
  el.innerHTML = '<p class="loading"></p>';
  try {
    const d = await api(`/wayback/snapshots?url=${encodeURIComponent(url)}`);
    if (!d.snapshots || d.snapshots.length === 0) { el.innerHTML = '<p>No snapshots.</p>'; return; }
    el.innerHTML = d.snapshots.map(s => `
      <div style="padding:0.3rem 0;font-size:0.9rem">
        <span class="time">${esc(s.timestamp)}</span>
        <span class="status" style="color:${s.status_code === 200 ? 'var(--green)' : 'var(--orange)'}">HTTP ${s.status_code}</span>
        <span class="time">${s.content_type || ''}</span>
      </div>
    `).join('');
  } catch (e) { el.innerHTML = `<p>Error: ${e.message}</p>`; }
};

/* ── Address Book Page ──────────────────────────────────────────────────── */

class AddressBookPage {
  constructor(mount) { this.m = mount; this.page = 1; }

  async render() {
    this.m.innerHTML = `<h1>Public Address Book</h1><div id="ab"><p class="loading"></p></div>`;
    const ab = document.getElementById('ab');
    try {
      const d = await api('/addressbook', { page: this.page, per_page: PER_PAGE });
      if (!d.sites || d.sites.length === 0) { ab.innerHTML = '<p>No entries yet.</p>'; return; }
      const lines = d.sites.map(s => {
        const b32 = s.b32 ? (s.b32.endsWith('.b32.i2p') ? s.b32 : s.b32 + '.b32.i2p') : '';
        return `${esc(s.hostname)}=${b32}`;
      }).join('\n');
      ab.innerHTML = `
        <p style="margin-bottom:1rem">Hosts gathered from crawling I2P registries. Serve as <code>hosts.txt</code> for your I2P router.</p>
        <div class="hosts-list">${lines}</div>
      ` + pageNav(this.page, d.total, (p) => { this.page = p; this.render(); });
    } catch (e) { ab.innerHTML = `<p>Error: ${e.message}</p>`; }
  }
}

/* ── Bootstrap ──────────────────────────────────────────────────────────── */

route();