'use strict';

// ── Estado Global ────────────────────────────────────────────
const state = {
  audio: null, audioPath: null,
  coverMusic: null, coverMusicPath: null,
  video: null, videoPath: null,
  coverVideo: null, coverVideoPath: null,
  batch: [],   batchCounter: 0,
  jobInterval: null // Para evitar múltiplos loops de polling
};

const PAGE_META = {
  dashboard: ['Dashboard de Produção', 'Gerencie e publique sua música com IA'],
  library:   ['Biblioteca', 'Histórico de publicações'],
  queue:     ['Fila de Upload', 'Ficheiros pendentes de processamento'],
  settings:  ['Configurações do Sistema', 'Gerencie chaves de API e preferências']
};

// ── Inicialização ────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initSSE();
  updateResources();
  updateClock();
  setInterval(updateClock, 1000);
  setInterval(updateResources, 5000); // Aumentado para 5s para poupar CPU
  
  // Carregamento inicial
  loadModuleStatus();
  carregarContas();
  addBatchRow();
  
  // Loops de auto-refresh dinâmico
  setInterval(loadModuleStatus, 15000); // Atualiza status a cada 15s
  setInterval(() => {
    // Só atualiza a fila se ela estiver visível
    const queueSec = document.getElementById('section-queue');
    if (queueSec && queueSec.style.display !== 'none') loadQueue();
  }, 10000);

  // Listeners de Drop Zone da Fila
  const dzq = document.getElementById('dropZoneQueue');
  if (dzq) {
      dzq.addEventListener('dragover', e => { e.preventDefault(); dzq.classList.add('dz-over'); });
      dzq.addEventListener('dragleave', () => dzq.classList.remove('dz-over'));
      dzq.addEventListener('drop', dzDropQueue);
  }
});


// ── Navegação & UI ───────────────────────────────────────────
function showSection(id, btn) {
  document.querySelectorAll('.app-section').forEach(s => s.style.display = 'none');
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  
  const sec = document.getElementById(`section-${id}`);
  if (sec) sec.style.display = 'flex';
  if (btn) btn.classList.add('active');
  
  const [title, sub] = PAGE_META[id] || ['—', '—'];
  const t = document.getElementById('pageTitle');
  const s = document.getElementById('pageSub');
  if (t) t.innerText = title;
  if (s) s.innerText = sub;
  
  const ms = document.querySelector('.mode-selector');
  if (ms) ms.style.display = id === 'dashboard' ? 'flex' : 'none';
  
  // Auto-load data when entering sections
  if (id === 'library')  loadLibrary();
  if (id === 'queue')    loadQueue();
  if (id === 'settings') { loadSettings(); carregarContas(); }
}

function switchWizardTab(mode, btn) {
  document.querySelectorAll('.wizard-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.wizard-content').forEach(c => c.classList.remove('active'));
  if (btn) btn.classList.add('active');
  const el = document.getElementById(`wiz-${mode}`);
  if (el) el.classList.add('active');
}

function switchSettingsTab(tabId, btn) {
    document.querySelectorAll('.stab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.stab-content').forEach(c => c.classList.remove('active'));
    if (btn) btn.classList.add('active');
    const el = document.getElementById(`stab-${tabId}`);
    if (el) el.classList.add('active');
    if (tabId === 'status') carregarStatusModulos();
}

// ── Publicação & Upload ──────────────────────────────────────
async function uploadFile(endpoint, field, file) {
  const fd = new FormData();
  fd.append(field, file);
  const r = await fetch(endpoint, { method: 'POST', body: fd });
  return r.json();
}

async function buildSession(mediaFile, coverFile, titulo) {
  const mRes = await uploadFile('/upload-media', 'file', mediaFile);
  if (!mRes.success) throw new Error(mRes.error || 'Erro no upload de média');
  let coverPath = null;
  if (coverFile) {
    const cRes = await uploadFile('/upload-cover', 'file', coverFile);
    if (cRes.success) coverPath = cRes.path;
  }
  return { media_path: mRes.path, media_name: mRes.name, cover_path: coverPath, titulo: titulo || '' };
}

async function submitSessions(sessions, scheduleInputId) {
  const dateEl = document.getElementById(scheduleInputId);
  const isScheduled = dateEl && dateEl.closest('.schedule-picker')?.style.display !== 'none' && dateEl.value;
  
  const endpoint = isScheduled ? '/schedule' : '/publish';
  const body = { sessions };
  if (isScheduled) body.scheduled_at = new Date(dateEl.value).toISOString();

  return fetch(endpoint, {
    method: 'POST', 
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  }).then(r => r.json());
}

async function publishMusic() {
  const path = state.audioPath;
  if (!path) return showToast('Aguarde o upload do áudio concluir', 'info');
  
  const btn = document.getElementById('btnPublishMusic');
  const status = document.getElementById('publishMusicStatus');
  btn.disabled = true; status.textContent = '🚀 Iniciando publicação...';
  
  try {
    const titulo = document.getElementById('musicTitle').value;
    const session = { 
        media_path: path, 
        media_name: state.audio.name, 
        cover_path: state.coverMusicPath, 
        titulo: titulo || '' 
    };
    
    const res = await submitSessions([session], 'scheduleDateMusic');
    if (res.success) {
      const msg = res.scheduled_at ? `⏰ Agendado!` : `🚀 Publicação iniciada!`;
      status.textContent = msg; showToast(msg, 'success');
      if (!res.scheduled_at) pollJobStatus(res.job_id);
    } else { 
      status.textContent = `❌ ${res.error}`; 
    }
  } catch(e) { 
    status.textContent = `❌ ${e.message}`; 
    showToast(e.message, 'error');
  }
  finally { btn.disabled = false; }
}

async function publishVideo() {
  const path = state.videoPath;
  if (!path) return showToast('Aguarde o upload do vídeo concluir', 'info');
  
  const btn = document.getElementById('btnPublishVideo');
  const status = document.getElementById('publishVideoStatus');
  btn.disabled = true; status.textContent = '🚀 Iniciando publicação...';
  
  try {
    const titulo = document.getElementById('videoTitle').value;
    const session = { 
        media_path: path, 
        media_name: state.video.name, 
        cover_path: state.coverVideoPath, 
        titulo: titulo || '' 
    };

    const res = await submitSessions([session], 'scheduleDateVideo');
    if (res.success) {
      const msg = res.scheduled_at ? `⏰ Agendado!` : `🚀 Job iniciado!`;
      status.textContent = msg; showToast(msg, 'success');
      if (!res.scheduled_at) pollJobStatus(res.job_id);
    } else { 
      status.textContent = `❌ ${res.error}`; 
    }
  } catch(e) { 
    status.textContent = `❌ ${e.message}`; 
    showToast(e.message, 'error'); 
  }
  finally { btn.disabled = false; }
}

// ── Lote (Batch) ─────────────────────────────────────────────
function addBatchRow(file = null) {
  const id = ++state.batchCounter;
  state.batch.push({ id, media: null, cover: null });
  const list = document.getElementById('batchList');
  if (!list) return;
  const row = document.createElement('div');
  row.className = 'batch-row'; row.id = `brow-${id}`;
  row.innerHTML = `
    <div class="batch-slot">
      <input type="file" id="bm-${id}" style="display:none" onchange="setBatchMedia(${id},this)">
      <button class="batch-slot-btn" id="bmbtn-${id}" onclick="document.getElementById('bm-${id}').click()">🎵 Selecionar Média</button>
    </div>
    <div class="batch-slot">
      <input type="file" id="bc-${id}" style="display:none" onchange="setBatchCover(${id},this)">
      <button class="batch-slot-btn" id="bcbtn-${id}" onclick="document.getElementById('bc-${id}').click()">🖼️ Selecionar Capa</button>
    </div>
    <div class="batch-slot">
      <input type="text" class="dark-input batch-title-input" id="bt-${id}" placeholder="Título (opcional)">
    </div>
    <button class="batch-remove" onclick="removeBatchRow(${id})">✕</button>`;
  list.appendChild(row);
  if (file) setBatchMediaFile(id, file);
}

function setBatchMedia(id, input) { if (input.files[0]) setBatchMediaFile(id, input.files[0]); }
function setBatchMediaFile(id, file) {
  const entry = state.batch.find(b => b.id === id);
  if (entry) entry.media = file;
  const btn = document.getElementById(`bmbtn-${id}`);
  if (btn) { btn.textContent = `✅ ${file.name}`; btn.classList.add('loaded'); }
}
function setBatchCover(id, input) {
  const f = input.files[0]; if (!f) return;
  const entry = state.batch.find(b => b.id === id);
  if (entry) entry.cover = f;
  const btn = document.getElementById(`bcbtn-${id}`);
  if (btn) { btn.textContent = `✅ ${f.name}`; btn.classList.add('loaded'); }
}
function removeBatchRow(id) {
  state.batch = state.batch.filter(b => b.id !== id);
  document.getElementById(`brow-${id}`)?.remove();
}
function clearBatch() {
  state.batch = []; state.batchCounter = 0;
  const list = document.getElementById('batchList');
  if (list) list.innerHTML = '';
  addBatchRow();
}

async function publishBatch() {
  const valid = state.batch.filter(b => b.media);
  if (!valid.length) return showToast('Adicione arquivos ao lote', 'error');
  const btn = document.getElementById('btnPublishBatch');
  const status = document.getElementById('publishBatchStatus');
  btn.disabled = true; status.textContent = `⏳ A enviar ${valid.length} ficheiro(s)...`;
  try {
    const sessions = [];
    for (const item of valid) {
      const titulo = document.getElementById(`bt-${item.id}`)?.value || '';
      const session = await buildSession(item.media, item.cover, titulo);
      sessions.push(session);
    }
    const res = await submitSessions(sessions, 'scheduleDateBatch');
    if (res.success) {
      const msg = res.scheduled_at ? `⏰ Lote agendado!` : `🚀 Lote iniciado!`;
      status.textContent = msg; showToast(msg, 'success');
      if (!res.scheduled_at) pollJobStatus(res.job_id);
    } else { status.textContent = `❌ ${res.error}`; }
  } catch(e) { status.textContent = `❌ ${e.message}`; showToast(e.message, 'error'); }
  finally { btn.disabled = false; }
}

// ── Configurações (Settings) ─────────────────────────────────
async function loadSettings() {
    try {
        const cfg = await fetch('/settings').then(r => r.json());
        const set = (id, v) => { const e = document.getElementById(id); if (e) e.value = v || ''; };
        const chk = (id, v) => { const e = document.getElementById(id); if (e) e.checked = !!v; };
        
        set('cfgGeminiKey', cfg.api_keys?.gemini);
        set('cfgOpenAIKey', cfg.api_keys?.openai);
        set('cfgClientSecret', cfg.api_keys?.client_secret);
        set('cfgVisibility', cfg.youtube?.visibility);
        set('cfgTitlePrefix', cfg.youtube?.title_prefix);
        set('cfgTitleSuffix', cfg.youtube?.title_suffix);
        set('cfgDefaultTags', cfg.youtube?.default_tags);
        set('cfgDefaultDesc', cfg.youtube?.default_description);
        set('cfgDriveFolderId', cfg.paths?.drive?.folder_id);
        set('cfgDriveQuery', cfg.paths?.drive?.query);
        set('cfgUploadFolder', cfg.processing?.upload_folder);
        set('cfgTempFolder', cfg.processing?.temp_folder);
        set('cfgDelay', cfg.processing?.antispam_delay_seconds);
        chk('cfgAutoDelete', cfg.processing?.auto_delete_originals);
        chk('cfgUseArtEngine', cfg.processing?.use_autonomous_art);
        set('cfgResolution', cfg.video?.resolution);
        set('cfgPreset', cfg.video?.preset);
        set('cfgCrf', cfg.video?.crf);
        set('cfgAudioBitrate', cfg.audio?.bitrate);
        
        showToast('Configurações carregadas', 'success');
    } catch { showToast('Erro ao carregar configurações', 'error'); }
}

async function saveSettings() {
    const btn = document.getElementById('btnSaveSettings');
    const msg = document.getElementById('saveStatusMsg');
    if (btn) btn.disabled = true;
    
    // Funções auxiliares para evitar erros se o ID não existir no HTML
    const getV = id => document.getElementById(id)?.value || '';
    const getN = id => parseInt(document.getElementById(id)?.value) || 0;
    const getC = id => document.getElementById(id)?.checked || false;

    try {
        const cfg = {
            api_keys: {
                gemini: getV('cfgGeminiKey'),
                openai: getV('cfgOpenAIKey'),
                client_secret: getV('cfgClientSecret')
            },
            youtube: {
                visibility: getV('cfgVisibility'),
                title_prefix: getV('cfgTitlePrefix'),
                title_suffix: getV('cfgTitleSuffix'),
                default_tags: getV('cfgDefaultTags'),
                default_description: getV('cfgDefaultDesc')
            },
            paths: {
                drive: {
                    folder_id: getV('cfgDriveFolderId'),
                    query: getV('cfgDriveQuery')
                }
            },
            processing: {
                upload_folder: getV('cfgUploadFolder'),
                temp_folder: getV('cfgTempFolder'),
                antispam_delay_seconds: getN('cfgDelay'),
                auto_delete_originals: getC('cfgAutoDelete'),
                use_autonomous_art: getC('cfgUseArtEngine')
            },
            video: {
                resolution: getV('cfgResolution'),
                preset: getV('cfgPreset'),
                crf: getN('cfgCrf')
            },
            audio: { bitrate: getV('cfgAudioBitrate') }
        };

        logToMonitor("A guardar configurações no servidor...");
        
        const res = await fetch('/settings', {
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cfg)
        }).then(r => r.json());

        if (res.success) {
            showToast('Configurações guardadas!', 'success');
            logToMonitor("✅ Configurações gravadas com sucesso.");
            if (msg) { msg.textContent = '✅ Guardado'; setTimeout(()=>msg.textContent='',3000); }
            loadModuleStatus();
        } else {
            throw new Error(res.error || 'Erro desconhecido no servidor');
        }
    } catch (e) {
        console.error("Erro ao guardar:", e);
        showToast('Erro ao guardar configurações', 'error');
        logToMonitor(`❌ ERRO AO GUARDAR: ${e.message}`);
    } finally {
        if (btn) btn.disabled = false;
    }
}

async function testGemini() {
    const key = document.getElementById('cfgGeminiKey').value;
    const btn = document.getElementById('btnTestGemini');
    const hint = document.getElementById('geminiStatus');
    if (!key) return showToast('Insira a chave primeiro', 'info');

    btn.disabled = true; hint.textContent = 'A testar...';
    try {
        const res = await fetch('/test-gemini', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key })
        }).then(r => r.json());

        hint.textContent = res.success ? '✅ Conexão OK!' : '❌ Chave Inválida';
        hint.style.color = res.success ? 'var(--green)' : 'var(--red)';
        showToast(res.success ? 'Gemini OK!' : 'Chave inválida', res.success?'success':'error');
    } catch { hint.textContent = '❌ Erro de rede'; }
    finally { btn.disabled = false; }
}

// ── Biblioteca (Library) ─────────────────────────────────────
let libraryData = [];
async function loadLibrary() {
  const wrap = document.getElementById('libraryTable');
  if (!wrap) return;
  wrap.innerHTML = '<p class="empty-state">A carregar...</p>';
  try {
    const rows = await fetch('/library').then(r => r.json());
    libraryData = rows;
    renderLibrary(rows);
  } catch { wrap.innerHTML = '<p class="empty-state">Erro ao carregar biblioteca.</p>'; }
}

function filterLibrary() {
  const q = document.getElementById('libSearch')?.value.toLowerCase();
  const filtered = libraryData.filter(r => 
    (r.titulo || r.title || '').toLowerCase().includes(q) || 
    (r.ficheiro || r.file_name || '').toLowerCase().includes(q)
  );
  renderLibrary(filtered);
}

function renderLibrary(rows) {
  const wrap = document.getElementById('libraryTable');
  if (!wrap) return;
  if (!rows.length) { wrap.innerHTML = '<p class="empty-state">Vazio.</p>'; return; }
  
  const ext = f => (f||'').split('.').pop().toLowerCase();
  const icon = f => ['mp4','mov','avi','mkv','webm'].includes(ext(f)) ? '🎬' : '🎵';
  const ago = d => {
    if (!d) return '—';
    try {
        const s = Math.floor((Date.now() - new Date(d.replace(' ', 'T'))) / 1000);
        if (isNaN(s)) return d;
        if (s < 60) return 'agora';
        if (s < 3600) return `${Math.floor(s/60)}m`;
        if (s < 86400) return `${Math.floor(s/3600)}h`;
        return new Date(d).toLocaleDateString('pt');
    } catch { return d; }
  };
  
  const total = rows.length;
  const pub = rows.filter(r => r.youtube_id || r.video_id).length;
  
  wrap.innerHTML = `
    <div class="lib-stats">
      <div class="lib-stat"><span class="lib-stat-val">${total}</span><span class="lib-stat-lbl">Total</span></div>
      <div class="lib-stat"><span class="lib-stat-val" style="color:var(--green)">${pub}</span><span class="lib-stat-lbl">Publicados</span></div>
      <div class="lib-stat"><span class="lib-stat-val" style="color:var(--amber)">${total-pub}</span><span class="lib-stat-lbl">Pendentes</span></div>
    </div>
    <div class="lib-table">
      <div class="lib-thead"><span>Ficheiro</span><span>Título</span><span>YouTube</span><span>Data</span></div>
      <div class="lib-tbody">
        ${rows.map(r => {
          const fileName = r.nome_arquivo || r.ficheiro || r.file_name || '—';
          const title = r.titulo || r.title || fileName.replace(/\.[^.]+$/,'');
          const videoId = r.youtube_id || r.video_id;
          return `
          <div class="lib-row">
            <div class="lib-cell lib-file">
              <span class="lib-file-icon">${icon(fileName)}</span>
              <span class="lib-file-name" title="${fileName}">${fileName}</span>
            </div>
            <div class="lib-cell lib-title" title="${title}">${title}</div>
            <div class="lib-cell">
              ${videoId ? `<a href="https://youtu.be/${videoId}" target="_blank" class="lib-yt-link">
                    <svg viewBox="0 0 24 24" fill="currentColor" width="12" height="12"><path d="M22.54 6.42a2.78 2.78 0 0 0-1.95-1.96C18.88 4 12 4 12 4s-6.88 0-8.59.46A2.78 2.78 0 0 0 1.46 6.42 29 29 0 0 0 1 12a29 29 0 0 0 .46 5.58A2.78 2.78 0 0 0 3.41 19.54C5.12 20 12 20 12 20s6.88 0 8.59-.46a2.78 2.78 0 0 0 1.95-1.96A29 29 0 0 0 23 12a29 29 0 0 0-.46-5.58z"/><polygon points="9.75 15.02 15.5 12 9.75 8.98 9.75 15.02" fill="white"/></svg>
                    Ver
                </a>` : `<span class="badge badge-warn">Pendente</span>`}
            </div>
            <div class="lib-cell lib-date">${ago(r.data_publicacao || r.data || r.date)}</div>
          </div>`;
        }).join('')}
      </div>
    </div>`;
}


// ── Fila de Upload (Queue) ───────────────────────────────────
async function loadQueue() {
  const lista = document.getElementById('queueList');
  if (!lista) return;
  lista.innerHTML = '<p class="empty-state">A carregar...</p>';
  try {
    const files = await fetch('/pending-files').then(r => r.json());
    if (!files.length) { lista.innerHTML = '<p class="empty-state">Vazio.</p>'; return; }
    const ext = f => (f||'').split('.').pop().toLowerCase();
    const icon = f => ['mp4','mov','avi','mkv','webm'].includes(ext(f)) ? '🎬' : '🎵';
    lista.innerHTML = files.map(name => `
        <div class="queue-file-item">
          <div class="queue-file-icon">${icon(name)}</div>
          <div class="queue-file-info">
            <span class="queue-file-name">${name}</span>
            <span class="queue-file-size">${ext(name).toUpperCase()}</span>
          </div>
          <div class="queue-file-actions">
            <button class="btn-icon-sm" onclick="removeFromQueue('${name}')">✕</button>
          </div>
        </div>`).join('');
  } catch { lista.innerHTML = '<p class="empty-state">Erro.</p>'; }
}

async function removeFromQueue(filename) {
    try {
        await fetch('/delete-pending', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({filename}) });
        loadQueue(); showToast('Removido', 'success');
    } catch { showToast('Erro', 'error'); }
}

async function clearQueue() {
    if (!confirm('Limpar toda a fila?')) return;
    try {
        await fetch('/clear-queue', { method:'POST' });
        loadQueue(); showToast('Fila limpa', 'success');
    } catch { showToast('Erro', 'error'); }
}

// ── YouTube Accounts ─────────────────────────────────────────
async function carregarContas() {
  try {
    const d = await fetch('/accounts').then(r => r.json());
    const lista = document.getElementById('accountsList');
    if (!lista) return;
    const contas = d.contas || [];
    if (!contas.length) { lista.innerHTML = '<p class="empty-state">Sem contas.</p>'; return; }
    lista.innerHTML = contas.map(c => {
      const char = (c.email||'?')[0].toUpperCase();
      const colors = ['#f44336', '#e91e63', '#9c27b0', '#673ab7', '#3f51b5', '#2196f3', '#03a9f4', '#00bcd4', '#009688', '#4caf50'];
      const color = colors[char.charCodeAt(0) % colors.length];
      
      return `
      <div class="account-item ${c.ativa ? 'active-account' : ''}">
        <div class="account-avatar" style="background:${color}">${char}</div>
        <div class="account-info">
            <div class="account-email">${c.email}</div>
            ${c.ativa ? '<span class="account-badge">Ativa</span>' : ''}
        </div>
        <div class="account-actions">
          ${!c.ativa ? `<button class="btn-ghost btn-sm" onclick="trocarConta('${c.email}')">Activar</button>` : ''}
          <button class="btn-ghost btn-danger btn-sm" onclick="removerConta('${c.email}')">✕</button>
        </div>
      </div>`;
    }).join('');
    if (d.ativa) {
        document.getElementById('sidebarAvatar').textContent = d.ativa[0].toUpperCase();
        document.getElementById('sidebarEmail').textContent = d.ativa;
    }
  } catch {}
}

async function adicionarConta() {
  const msg = document.getElementById('accountLoginMsg');
  if (msg) msg.style.display = 'flex';
  
  try { 
      await fetch('/accounts/add', { method: 'POST' });
      // Polling para detectar quando a conta foi adicionada
      let attempts = 0;
      const initialCount = (await fetch('/accounts').then(r=>r.json())).contas?.length || 0;
      
      const check = setInterval(async () => {
          attempts++;
          const d = await fetch('/accounts').then(r=>r.json());
          if ((d.contas?.length > initialCount) || attempts > 30) {
              clearInterval(check);
              if (msg) msg.style.display = 'none';
              carregarContas();
              if (d.contas?.length > initialCount) showToast('Conta adicionada!', 'success');
          }
      }, 3000);
  } catch {
      if (msg) msg.style.display = 'none';
      showToast('Erro ao iniciar login', 'error');
  }
}
async function trocarConta(email) {
  await fetch('/accounts/switch', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({email}) });
  carregarContas(); showToast('Conta trocada', 'success');
}
async function removerConta(email) {
  if (confirm(`Remover ${email}?`)) {
    await fetch('/accounts/remove', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({email}) });
    carregarContas(); showToast('Conta removida', 'error');
  }
}

// ── Status & Utils ───────────────────────────────────────────
async function loadModuleStatus() {
  try {
    const d = await fetch('/module-status').then(r => r.json());
    const set = (id, ok, msg) => { const e = document.getElementById(id); if (e) e.innerHTML = `<span class="badge ${ok?'badge-ok':'badge-warn'}">${msg}</span>`; };
    set('statusGemini', d.gemini?.ok, d.gemini?.msg || '—');
    set('statusFfmpeg', d.ffmpeg?.ok, d.ffmpeg?.ok ? 'OK' : 'Falta');
    set('statusYoutube', d.youtube?.ok, d.youtube?.email || '—');
    set('statusDrive', d.drive?.ok, d.drive?.msg || '—');
    set('statusDb', d.db?.ok, d.db?.msg || '—');
    
    const allOk = d.gemini?.ok && d.ffmpeg?.ok && d.youtube?.ok;
    document.getElementById('statusDot').style.background = allOk ? 'var(--green)' : 'var(--amber)';
    document.getElementById('statusText').textContent = allOk ? 'Sistema Ativo' : 'Atenção';
  } catch {}
}

async function carregarStatusModulos() {
    try {
        const d = await fetch('/module-status').then(r => r.json());
        const set = (cardId, badgeId, ok, msg) => {
            const b = document.getElementById(badgeId);
            const c = document.getElementById(cardId);
            if (b) { b.className = `badge ${ok?'badge-ok':'badge-warn'}`; b.textContent = msg; }
            if (c) { c.classList.toggle('smod-ok', !!ok); c.classList.toggle('smod-err', !ok); }
        };
        set('smod-gemini', 'modGemini', d.gemini?.ok, d.gemini?.msg || 'Erro');
        set('smod-ffmpeg', 'modFfmpeg', d.ffmpeg?.ok, d.ffmpeg?.ok ? 'OK' : 'Não encontrado');
        set('smod-youtube', 'modYouTube', d.youtube?.ok, d.youtube?.email || 'Inativo');
        set('smod-drive', 'modDrive', d.drive?.ok, d.drive?.msg || 'Inativo');
        set('smod-db', 'modDB', d.db?.ok, d.db?.msg || 'Erro');

        // Atualizar header do console
        const hGem = document.getElementById('h-gemini');
        const hGpu = document.getElementById('h-gpu');
        if (hGem) hGem.innerText = d.gemini?.ok ? 'Ok' : 'Offline';
        if (hGpu) hGpu.innerText = d.ffmpeg?.ok ? 'Ativa' : 'Erro';
    } catch {}
}

function pollJobStatus(jobId) {
  if (state.jobInterval) clearInterval(state.jobInterval);
  
  const bar = document.getElementById('progressBar');
  const pct = document.getElementById('progressPercent');
  const sts = document.getElementById('currentStatus');
  
  state.jobInterval = setInterval(async () => {
    try {
      const data = await fetch(`/job-status/${jobId}`).then(r => r.json());
      const p = data.progress || 0;
      updateProgress(p, data.current_step);
      
      const btn = document.getElementById('cancelBtn');
      if (data.status === 'running') {
          if (btn) btn.classList.remove('inactive');
          label = data.current_step ? `⚡ ${data.current_step}` : 'Processando...';
          const fileDisp = document.getElementById('fileNameDisplay');
          if (fileDisp && data.current_file) fileDisp.innerText = data.current_file;
      } else {
          if (btn) btn.classList.add('inactive');
          
          // Hard Reset Visual: Se não está rodando, nada pode estar pulsando
          Object.values(steps).forEach(s => s && s.classList.remove('active'));

          if (data.status === 'done') {
              label = 'CONCLUÍDO';
              // No 'done', todos ficam verdes
              Object.values(steps).forEach(s => s && s.classList.add('completed'));
          } else {
              label = data.status === 'error' ? 'INTERROMPIDO' : 'INATIVO';
              // No erro/interrompido, limpa tudo inclusive o verde
              Object.values(steps).forEach(s => s && s.classList.remove('completed'));
          }
      }
      if (sts) sts.innerHTML = label;

      if (data.status === 'done' || data.status === 'error') {
        clearInterval(state.jobInterval); state.jobInterval = null;
        loadLibrary(); showToast(data.status === 'done' ? 'Concluído!' : 'Erro!', data.status==='done'?'success':'error');
      }
    } catch { clearInterval(state.jobInterval); state.jobInterval = null; }
  }, 2000); // Polling a cada 2s é suficiente
}

function initSSE() {
  const src = new EventSource('/stream-logs');
  src.onopen = () => {
    const el = document.getElementById('logConsole');
    if (el) el.innerHTML = '';
  };
  src.onmessage = e => {
    const msg = e.data;
    const el = document.getElementById('logConsole'); if (!el) return;

    // Filtro de Atividades de Trabalho (Esconde logs técnicos/configuração)
    const workTags = ['[IA]', '[CAPA]', '[FFMPEG]', '[YOUTUBE]', '[JOB]', '[MOTOR]', '[SHORT]', '[VIBE]', '[AUDITORIA]', '[ANTISPAM]', '✅', '❌', '🛑', '⚠️'];
    const isWork = workTags.some(tag => msg.toUpperCase().includes(tag)) || msg.includes('Progresso:') || msg.includes('Upload:');
    if (!isWork) return; 

    // Lógica para evitar spam de progresso (Substitui a linha anterior de percentagem)
    const isProgress = msg.includes('Progresso:') || msg.includes('Upload:') || msg.includes('Render:');
    if (isProgress) {
        const last = el.lastElementChild;
        const lastText = last ? last.textContent : "";
        const isLastProgress = lastText.includes('Progresso:') || lastText.includes('Upload:') || lastText.includes('Render:');
        
        if (last && isLastProgress) {
            last.textContent = msg;
            last.className = 'log progress-live' + (msg.includes('ERRO') ? ' error' : '');
            return;
        }
    }

    // Atualiza o pipeline visual instantaneamente via logs
    updatePipeline(msg);

    const d = document.createElement('div');
    d.className = 'log' + (msg.includes('ERRO') || msg.includes('❌') ? ' error' : '');
    d.textContent = msg; 
    el.appendChild(d); 
    if (el.children.length > 500) el.removeChild(el.children[0]);
    el.scrollTop = el.scrollHeight;
  };
}

function clearConsole() { const el = document.getElementById('logConsole'); if (el) el.innerHTML = ''; }

async function syncDrive() {
    showToast('Iniciando busca no Google Drive...', 'info');
    try {
        await fetch('/sync-drive', { method: 'POST' });
    } catch (e) {
        showToast('Erro ao sincronizar Drive', 'error');
    }
}
async function updateResources() {
  try {
    const d = await fetch('/stats').then(r => r.json());
    document.getElementById('cpuBar').style.width = d.cpu + '%';
    document.getElementById('cpuVal').textContent = d.cpu + '%';
    document.getElementById('ramBar').style.width = d.ram + '%';
    document.getElementById('ramVal').textContent = d.ram + '%';
    
    const dBar = document.getElementById('diskBar');
    const dVal = document.getElementById('diskVal');
    if (dBar) dBar.style.width = d.disk + '%';
    if (dVal) dVal.textContent = d.disk + '%';
    
    const nSent = document.getElementById('netSent');
    const nRecv = document.getElementById('netRecv');
    if (nSent) nSent.textContent = d.net_sent;
    if (nRecv) nRecv.textContent = d.net_recv;
    
  } catch {}
}
function updateClock() { document.getElementById('liveClock').textContent = new Date().toLocaleTimeString('pt'); }

async function openAuditReport() {
  try {
    const res = await fetch('/audit-report');
    const data = await res.json();
    if (!data.report) {
       showToast('Relatório vazio ou não encontrado', 'info');
       return;
    }
    const blob = new Blob([data.report], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
  } catch (e) {
    showToast('Erro ao carregar relatório', 'error');
  }
}

function showToast(msg, type = 'info') {

  const c = document.getElementById('toastContainer'); if (!c) return;
  const t = document.createElement('div');
  t.className = `toast ${type}`; t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => t.classList.add('show'), 10);
  setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 400); }, 3500);
}

function toggleSchedule(mode) {
  const pk = document.getElementById(`schedulePicker${mode.charAt(0).toUpperCase()+mode.slice(1)}`);
  if (pk) pk.style.display = pk.style.display === 'none' ? 'flex' : 'none';
}

async function syncDrive() {
  const btn = event.currentTarget;
  if (btn) btn.disabled = true;
  try {
    const res = await fetch('/sync-drive', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast('☁️ Varredura do Drive iniciada!', 'success');
    } else {
      showToast(data.error || 'Erro ao sincronizar', 'error');
    }
  } catch (e) {
    showToast('Erro de conexão', 'error');
  } finally {
    if (btn) btn.disabled = false;
  }
}

function dzOver(e, el) { e.preventDefault(); el.classList.add('dz-over'); }

function dzLeave(el)   { el.classList.remove('dz-over'); }

async function dzDropBatch(e) {
  e.preventDefault();
  const el = document.getElementById('dropBatch');
  if (el) el.classList.remove('dz-over');
  handleBatchFiles(Array.from(e.dataTransfer.files));
}

function onBatchFileSelected(input) {
  if (input.files.length) handleBatchFiles(Array.from(input.files));
  input.value = ''; // Reset para permitir selecionar os mesmos ficheiros
}

function handleBatchFiles(files) {
  if (!files.length) return;
  logToMonitor(`Adicionando ${files.length} ficheiro(s) ao lote local.`);
  
  if (state.batch.length === 1 && !state.batch[0].media) {
      clearBatch();
  }

  for (const f of files) {
      const ext = f.name.split('.').pop().toLowerCase();
      if (['mp3','wav','flac','mp4','mov','avi','mkv'].includes(ext)) {
          addBatchRow(f);
      } else if (['jpg','jpeg','png','webp'].includes(ext)) {
          const lastWithoutCover = [...state.batch].reverse().find(b => b.media && !b.cover);
          if (lastWithoutCover) {
              setBatchCoverFile(lastWithoutCover.id, f);
          }
      }
  }
  showToast(`${files.length} ficheiros preparados no lote`, 'info');
}

function setBatchCoverFile(id, file) {
  const entry = state.batch.find(b => b.id === id);
  if (entry) entry.cover = file;
  const btn = document.getElementById(`bcbtn-${id}`);
  if (btn) { btn.textContent = `✅ ${file.name}`; btn.classList.add('loaded'); }
}

function appendLog(msg) {
  const el = document.getElementById('logConsole');
  if (!el) return;
  const d = document.createElement('div');
  d.className = 'log' + (msg.includes('ERRO') || msg.includes('❌') ? ' error' : '');
  d.textContent = msg;
  el.appendChild(d);
  el.scrollTop = el.scrollHeight;
}

function logToMonitor(msg) {
  appendLog(`[SISTEMA] ${msg}`);
  fetch('/log-frontend', { 
    headers: { 'Content-Type': 'application/json' },
    method: 'POST', 
    body: JSON.stringify({ msg })
  }).catch(() => {});
}

async function dzDropQueue(e) {
  e.preventDefault();
  const dzq = document.getElementById('dropZoneQueue');
  if (dzq) dzq.classList.remove('dz-over');
  handleQueueFiles(Array.from(e.dataTransfer.files));
}

function onQueueFileSelected(input) {
  if (input.files.length) handleQueueFiles(Array.from(input.files));
  input.value = '';
}

async function handleQueueFiles(files) {
  if (!files.length) return;
  logToMonitor(`A carregar ${files.length} ficheiro(s) para a fila de upload...`);
  showToast(`A carregar ${files.length} ficheiro(s)...`, 'info');
  
  const fd = new FormData();
  files.forEach(f => fd.append('files', f));

  try {
    const res = await fetch('/upload-batch', { method: 'POST', body: fd }).then(r => r.json());
    if (res.success) {
      showToast('✅ Ficheiros carregados na fila!', 'success');
      loadQueue();
    } else {
      showToast(res.error || 'Erro no upload', 'error');
    }
  } catch (e) {
    showToast('Erro de conexão', 'error');
  }
}

async function processQueue() {
  logToMonitor("Iniciando processamento de todos os ficheiros pendentes na fila...");
  showToast("Iniciando processamento...", 'info');
  try {
      const res = await fetch('/process-queue', { method: 'POST' }).then(r => r.json());
      if (res.success) {
          showToast('🚀 Pipeline de processamento iniciado!', 'success');
          pollJobStatus(res.job_id);
      } else {
          showToast(res.error || 'Erro ao iniciar', 'error');
      }
  } catch {
      showToast('Erro de rede', 'error');
  }
}


function dzDrop(e, el, type) {
  e.preventDefault(); el.classList.remove('dz-over');
  const file = e.dataTransfer.files[0];
  if (file) applyFile(type, file, el);
}

function onFileSelected(type, input) {
  const file = input.files[0]; if (!file) return;
  const el = {
    'audio': document.getElementById('dropAudio'),
    'cover-music': document.getElementById('dropCoverMusic'),
    'video': document.getElementById('dropVideo'),
    'cover-video': document.getElementById('dropCoverVideo')
  }[type];
  applyFile(type, file, el);
}

async function applyFile(type, file, el) {
  if (el) {
    el.classList.add('dz-loaded');
    const t = el.querySelector('.dz-text');
    if (t) t.innerHTML = `<div class="upload-progress-mini"></div><span class="dz-filename">A carregar: ${file.name}...</span>`;
  }

  // Upload imediato em background
  const endpoint = type.includes('cover') ? '/upload-cover' : '/upload-media';
  try {
      const res = await uploadFile(endpoint, 'file', file);
      if (res.success) {
          if (type === 'audio') { state.audio = file; state.audioPath = res.path; }
          if (type === 'cover-music') { state.coverMusic = file; state.coverMusicPath = res.path; }
          if (type === 'video') { state.video = file; state.videoPath = res.path; }
          if (type === 'cover-video') { state.coverVideo = file; state.coverVideoPath = res.path; }
          
          if (el) {
              const t = el.querySelector('.dz-text');
              if (t) t.innerHTML = `✅ <span class="dz-filename">${file.name}</span>`;
          }
          showToast(`Pronto: ${file.name}`, 'success');
      } else {
          throw new Error(res.error);
      }
  } catch (e) {
      if (el) {
          el.classList.remove('dz-loaded');
          const t = el.querySelector('.dz-text');
          if (t) t.innerHTML = `❌ Erro no upload`;
      }
      showToast(`Erro ao carregar ${file.name}: ${e.message}`, 'error');
  }
}

function updateProgress(percent, statusMsg) {
    const bar = document.getElementById('progressBar');
    const label = document.getElementById('progressPercent');
    const status = document.getElementById('currentStatus');
    const consoleDiv = document.getElementById('logConsole');

    if (bar) bar.style.width = percent + '%';
    if (label) label.innerText = percent + '%';
    
    // Auto-scroll para o console estático
    if (consoleDiv) {
        consoleDiv.scrollTop = consoleDiv.scrollHeight;
    }

    // Lógica do Pipeline Visual
    updatePipeline(statusMsg);
}

function updatePipeline(msg) {
    const m = (msg || "").toLowerCase();
    const steps = {
        ai: document.getElementById('step-ai'),
        art: document.getElementById('step-art'),
        render: document.getElementById('step-render'),
        upload: document.getElementById('step-upload')
    };

    if (!steps.ai) return;

    // Se houver qualquer mensagem e nada estiver ativo, começa pela IA
    const anyActive = Object.values(steps).some(s => s.classList.contains('active'));
    if (m && !anyActive) {
        steps.ai.classList.add('active');
    }

    // Lógica de ativação baseada em palavras-chave e TAGS reais do motor
    const isAI     = m.includes('[ia]') || m.includes('analisando') || m.includes('metadados') || m.includes('vibe');
    const isArt    = m.includes('[capa]') || m.includes('arte') || m.includes('dall-e') || m.includes('imagem');
    const isRender = m.includes('[ffmpeg]') || m.includes('[render]') || m.includes('[motor]') || m.includes('vídeo') || m.includes('short');
    const isUpload = m.includes('[youtube]') || m.includes('upload') || m.includes('enviando') || m.includes('publicando');

    if (isAI) {
        steps.ai.classList.add('active');
        steps.ai.classList.remove('completed');
    } 
    
    if (isArt) {
        steps.ai.classList.add('completed');
        steps.ai.classList.remove('active');
        steps.art.classList.add('active');
        steps.art.classList.remove('completed');
    } 
    
    if (isRender) {
        steps.ai.classList.add('completed');
        steps.ai.classList.remove('active');
        steps.art.classList.add('completed');
        steps.art.classList.remove('active');
        steps.render.classList.add('active');
        steps.render.classList.remove('completed');
    } 
    
    if (isUpload) {
        steps.ai.classList.add('completed');
        steps.art.classList.add('completed');
        steps.render.classList.add('completed');
        steps.ai.classList.remove('active');
        steps.art.classList.remove('active');
        steps.render.classList.remove('active');
        steps.upload.classList.add('active');
        steps.upload.classList.remove('completed');
    } 

    if (m.includes('concluído') || m.includes('sucesso') || m.includes('✅')) {
        Object.values(steps).forEach(s => { 
            if(s) {
                s.classList.add('completed');
                s.classList.remove('active');
            }
        });
    }
}

async function cancelarProcesso() {
    const btn = document.getElementById('cancelBtn');
    if (btn && btn.classList.contains('inactive')) return; // Evita cliques se inativo

    if (!confirm("Tem certeza que deseja interromper o processamento atual definitivamente?")) return;
    
    // Desabilita para evitar clique duplo
    if (btn) btn.classList.add('inactive');

    try {
        const res = await fetch('/cancel-job', { method: 'POST' });
        
        if (!res.ok) throw new Error("Erro no servidor");
        
        const data = await res.json();
        if (data.success) {
            showToast("Interrupção solicitada!", "warning");
            
            // Limpeza Imediata (Hard Reset)
            const el = document.getElementById('logConsole');
            if (el) el.innerHTML = ''; 
            const bar = document.getElementById('progressBar');
            if (bar) bar.style.width = '0%'; 
            const pct = document.getElementById('progressPercent');
            if (pct) pct.innerText = '0%';
            const sts = document.getElementById('currentStatus');
            if (sts) sts.innerText = 'Inativo (Interrompido)';
            const fileDisp = document.getElementById('fileNameDisplay');
            if (fileDisp) fileDisp.innerText = 'Aguardando...';

            Object.values(steps).forEach(s => s && s.classList.remove('active', 'completed'));
        } else {
            showToast("Falha ao cancelar: " + data.error, "error");
            if (btn) btn.classList.remove('inactive'); // Reabilita se falhar
        }
    } catch (e) {
        // Se a interrupção funcionou, o servidor pode estar reiniciando. 
        // Só mostramos erro se não houver um job ativo sendo limpo.
        console.warn("Fetch Cancel Error:", e);
        // showToast("Erro de rede ao cancelar.", "error"); // Removido para evitar confusão
    }
}
