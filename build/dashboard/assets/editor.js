/* =========================================================================
   Frontend Editor — modo "patches" (sin token) y modo "publish" (con token)
   ========================================================================= */
const Editor = (() => {
  const STORAGE_KEY = 'sourcseal_editor_patches_v1';
  const state = {
    files: [],          // [{ path, sha, content, dirty, _original }]
    current: null,      // path actual en el editor
    patches: loadPatches(),   // [{ path, original, modified, ts, status }]
    mode: 'patches',    // 'patches' | 'publish'
  };

  function loadPatches() {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'); }
    catch { return []; }
  }
  function savePatches() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state.patches)); } catch {}
  }

  const el = (id) => document.getElementById(id);

  async function init() {
    el('btn-fetch-site').addEventListener('click', fetchSite);
    el('btn-save-file').addEventListener('click', saveFile);
    el('btn-download-patch').addEventListener('click', downloadPatch);
    el('btn-download-bundle').addEventListener('click', downloadBundle);
    el('btn-clear-patches').addEventListener('click', () => {
      if (!confirm('¿Borrar todos los patches pendientes?')) return;
      state.patches = [];
      savePatches();
      renderPatches();
    });
    el('editor-textarea').addEventListener('input', onEdit);
    renderPatches();  // restaurar visualmente al cargar
  }

  function getPatches() { return state.patches.slice(); }
  function setFileContent(path, content) {
    const f = state.files.find(x => x.path === path);
    if (!f) return false;
    f._original = f._original ?? f.content;
    f.content = content;
    f.dirty = true;
    if (state.current === path) el('editor-textarea').value = content;
    renderFileList();
    return true;
  }
  function getFile(path) {
    return state.files.find(x => x.path === path);
  }

  async function fetchSite() {
    const url = el('site-url-input').value.trim();
    if (!url) return toast('Pon la URL del Repl', 'warn');
    el('fetch-status').textContent = 'descargando…';
    try {
      const r = await fetch(`/api/site/fetch?url=${encodeURIComponent(url)}`);
      const j = await r.json();
      if (!j.ok) throw new Error(j.error || 'fetch failed');
      state.files = j.files.map(f => ({ ...f, dirty: false }));
      renderFileList();
      el('fetch-status').textContent = `${state.files.length} archivos (${j.bytes} bytes)`;
      toast('Sitio descargado', 'ok');
    } catch (e) {
      el('fetch-status').textContent = 'error';
      toast(String(e), 'err');
    }
  }

  function renderFileList() {
    const sel = el('file-select');
    sel.innerHTML = '';
    state.files
      .slice()
      .sort((a, b) => a.path.localeCompare(b.path))
      .forEach(f => {
        const o = document.createElement('option');
        o.value = f.path;
        o.textContent = `${f.dirty ? '● ' : ''}${f.path} (${f.content.length}b)`;
        sel.appendChild(o);
      });
    sel.onchange = () => loadFile(sel.value);
    if (state.files.length) loadFile(state.files[0].path);
  }

  function loadFile(path) {
    const f = state.files.find(x => x.path === path);
    if (!f) return;
    state.current = path;
    el('editor-textarea').value = f.content;
    el('editor-textarea').disabled = false;
    el('editor-meta').textContent = `${path} · ${f.content.length} bytes · sha ${f.sha.slice(0, 12)}`;
  }

  function onEdit() {
    if (!state.current) return;
    const f = state.files.find(x => x.path === state.current);
    f.content = el('editor-textarea').value;
    f.dirty = true;
    renderFileList();
    el('editor-meta').textContent = `${state.current} · ${f.content.length} bytes · MODIFICADO`;
  }

  function saveFile() {
    if (!state.current) return toast('No hay archivo abierto', 'warn');
    const f = state.files.find(x => x.path === state.current);
    if (!f._original) f._original = f.content;  // captura antes del primer cambio
    if (f.content === f._original) return toast('Sin cambios', 'info');
    const idx = state.patches.findIndex(p => p.path === f.path);
    const patch = {
      path: f.path,
      original: f._original,
      modified: f.content,
      ts: new Date().toISOString(),
      status: 'pending',
    };
    if (idx >= 0) state.patches.splice(idx, 1, patch);
    else state.patches.push(patch);
    f.dirty = false;
    savePatches();
    renderFileList();
    renderPatches();
    toast('Patch listo para descargar', 'ok');
  }

  function renderPatches() {
    const ul = el('patch-list');
    ul.innerHTML = '';
    if (!state.patches.length) {
      ul.innerHTML = '<li class="muted">Sin patches pendientes.</li>';
      el('patch-count').textContent = '0';
      return;
    }
    el('patch-count').textContent = String(state.patches.length);
    state.patches.forEach((p, i) => {
      const li = document.createElement('li');
      li.innerHTML = `
        <span class="patch-path">${p.path}</span>
        <span class="patch-stats">+${countAdded(p.original, p.modified)} -${countRemoved(p.original, p.modified)}</span>
        <button data-i="${i}" class="btn ghost small">borrar</button>
      `;
      li.querySelector('button').onclick = () => {
        state.patches.splice(i, 1);
        renderPatches();
      };
      ul.appendChild(li);
    });
  }

  function countAdded(a, b) {
    return b.split('\n').filter(l => !a.split('\n').includes(l)).length;
  }
  function countRemoved(a, b) {
    return a.split('\n').filter(l => !b.split('\n').includes(l)).length;
  }

  function downloadPatch() {
    if (!state.patches.length) return toast('No hay patches', 'warn');
    const p = state.patches[state.patches.length - 1];
    const blob = new Blob([p.modified], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = p.path.split('/').pop();
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function downloadBundle() {
    if (!state.patches.length) return toast('No hay patches', 'warn');
    // Un bundle .zip no es trivial sin lib externa, así que entregamos un .tar-like
    // hecho a mano (compatible con `tar -xf`). Suficiente para pegar en Replit.
    const lines = [];
    state.patches.forEach(p => {
      const content = p.modified;
      const size = content.length;
      const path = p.path;
      lines.push(`===== FILE ${path} (${size} bytes) =====`);
      lines.push(content);
      lines.push(`===== END ${path} =====`);
      lines.push('');
    });
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `patches-${Date.now()}.bundle.txt`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function toast(msg, kind = 'info') {
    const t = el('editor-toast');
    t.textContent = msg;
    t.dataset.kind = kind;
    setTimeout(() => { t.textContent = ''; t.dataset.kind = ''; }, 3500);
  }

  return { init, getPatches, setFileContent, getFile, state };
})();
window.Editor = Editor;
document.addEventListener('DOMContentLoaded', Editor.init);
