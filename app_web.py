import os
import sys
import threading
import queue
import glob
import sqlite3
import psutil
import json
import shutil
import uuid
from datetime import datetime
from flask import Flask, render_template, Response, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename
from concurrent.futures import ThreadPoolExecutor

# ── Fix UTF-8 no Windows ─────────────────────────────────────────
# O terminal do Windows usa cp1252 por defeito, que não suporta emojis.
# Forçamos UTF-8 para evitar UnicodeEncodeError ao fazer print.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

def safe_log(msg):
    """Print direto no terminal sem passar pelo interceptor."""
    try:
        sys.stdout.write(str(msg) + '\n')
        sys.stdout.flush()
    except:
        pass
import main as motor
from video_engine import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS
from auth_module import (
    listar_contas, adicionar_conta, trocar_conta_activa,
    remover_conta, _get_active_account
)
import auth_module

FORMATOS_ACEITES = AUDIO_EXTENSIONS.union(VIDEO_EXTENSIONS)
IMAGEM_EXT = {'.jpg', '.jpeg', '.png', '.webp'}

# ── Config Inicial ──────────────────────────────────────────────
app = Flask(__name__)
CORS(app)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
import os

# Caminho absoluto para evitar problemas de diretório no Windows
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')
SCHEDULE_PATH = 'scheduled_jobs.json'

def carregar_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}
    return {}

# Inicializa pastas a partir da configuração real
_cfg = carregar_config()
app.config['UPLOAD_FOLDER'] = _cfg.get('paths', {}).get('upload_folder') or _cfg.get('processing', {}).get('upload_folder') or 'musicas_pendentes'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('temp_files', exist_ok=True)


# ── Logs (Broadcaster) ─────────────────────────────────────────
class LogBroadcaster:
    def __init__(self, max_buffer=50):
        self.clients = []
        self.buffer = []
        self.max_buffer = max_buffer
        self.lock = threading.Lock()

    def broadcast(self, msg):
        with self.lock:
            self.buffer.append(msg)
            if len(self.buffer) > self.max_buffer:
                self.buffer.pop(0)
            for q in self.clients[:]:
                try:
                    q.put_nowait(msg)
                except:
                    self.clients.remove(q)

    def subscribe(self):
        with self.lock:
            q = queue.Queue(maxsize=100)
            for msg in self.buffer:
                try: q.put_nowait(msg)
                except: pass
            self.clients.append(q)
            return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.clients:
                self.clients.remove(q)

broadcaster = LogBroadcaster()
jobs_status = {}  # job_id -> {status, progress, msg, files}
ACTIVE_JOB_ID = None
# Executor global para gerenciar a fila de processamento (1 por vez para não travar o PC)
job_executor = ThreadPoolExecutor(max_workers=1)

def log_to_web(msg):
    global ACTIVE_JOB_ID
    msg = str(msg)
    
    job_id = ACTIVE_JOB_ID
    if job_id and job_id in jobs_status:
        if "[JOB]" in msg:
            parts = msg.split(": ")
            if len(parts) > 1:
                jobs_status[job_id]['current_file'] = parts[1]
        
        if "[FFMPEG]" in msg:  jobs_status[job_id]['current_step'] = "Processamento FFmpeg"
        if "[IA]" in msg:      jobs_status[job_id]['current_step'] = "IA analisando metadados"
        if "[CAPA]" in msg:    jobs_status[job_id]['current_step'] = "Gerando arte autônoma"
        if "[YOUTUBE]" in msg: jobs_status[job_id]['current_step'] = "Upload para YouTube"
        if "[RENDER]" in msg:  jobs_status[job_id]['current_step'] = "Renderizando vídeo"
        if "[SHORT]" in msg:   jobs_status[job_id]['current_step'] = "Criando Short Vertical"
        if "[VIBE]" in msg or "🎵 Analisando" in msg: jobs_status[job_id]['current_step'] = "Análise de Vibe Musical"

    broadcaster.broadcast(msg)
    safe_log(msg)
    
    if job_id and job_id in jobs_status:
        # Marcos fixos por etapa (Progresso Macro)
        if "[IA]" in msg:     jobs_status[job_id]['progress'] = max(jobs_status[job_id].get('progress', 0), 10)
        if "[CAPA]" in msg:   jobs_status[job_id]['progress'] = max(jobs_status[job_id].get('progress', 0), 30)
        if "[RENDER]" in msg: jobs_status[job_id]['progress'] = max(jobs_status[job_id].get('progress', 0), 50)
        if "[YOUTUBE]" in msg: jobs_status[job_id]['progress'] = max(jobs_status[job_id].get('progress', 0), 85)

        # Atualização Granular (Smooth)
        import re
        match = re.search(r'(?:Upload|Render|Progresso):\s*(\d+)%', msg, re.IGNORECASE)
        if match:
            sub_pct = int(match.group(1))
            total_files = jobs_status[job_id].get('_total_files', 1)
            current_idx = jobs_status[job_id].get('_current_idx', 0)
            
            # Ajusta base dependendo da etapa
            base = 50 if "[RENDER]" in msg or "[FFMPEG]" in msg else 85 if "[YOUTUBE]" in msg else 0
            increment = 35 if base == 50 else 10 if base == 85 else 0
            
            global_pct = int(((current_idx + (sub_pct/100)) / total_files) * 100)
            # Garante que o progresso granular respeite o progresso total
            jobs_status[job_id]['progress'] = max(jobs_status[job_id].get('progress', 0), global_pct)

# ── Interceptor de Print (Garante que tudo vá para o Dashboard) ──
import builtins
_old_print = builtins.print
def sonic_print(*args, **kwargs):
    msg = " ".join(map(str, args))
    log_to_web(msg)
builtins.print = sonic_print

@app.route('/log-frontend', methods=['POST'])
def log_frontend():
    msg = request.json.get('msg', '')
    if msg: log_to_web(f"[FRONTEND] {msg}")
    return jsonify({"success": True})

motor.print = log_to_web
auth_module.print = log_to_web
import ai_module
import youtube_module
import video_engine
ai_module.print = log_to_web
youtube_module.print = log_to_web
video_engine.print = log_to_web


@app.before_request
def debug_request():
    if request.path != '/stats':
        safe_log(f"[REQ] {request.method} {request.path}")

# ── Config ──────────────────────────────────────────────────────
def carregar_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def salvar_config(dados):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)

# ── Agendamentos ────────────────────────────────────────────────
def carregar_agendamentos():
    if os.path.exists(SCHEDULE_PATH):
        try:
            with open(SCHEDULE_PATH, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    return []
                return json.loads(content)
        except Exception as e:
            print(f"⚠️ Erro ao carregar agendamentos (JSON corrompido?): {e}")
            return []
    return []

def salvar_agendamentos(jobs):
    with open(SCHEDULE_PATH, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)

def verificar_agendamentos():
    """Thread que verifica e executa jobs agendados e faz varredura do Drive."""
    import time
    last_drive_sync = 0
    while True:
        try:
            # 1. Verifica agendamentos manuais
            jobs = carregar_agendamentos()
            agora = datetime.now()
            restantes = []
            for job in jobs:
                agendado = datetime.fromisoformat(job['scheduled_at'])
                if agora >= agendado and job['status'] == 'pending':
                    job['status'] = 'running'
                    job_executor.submit(executar_job, job)
                else:
                    restantes.append(job)
            salvar_agendamentos(restantes)
            
            # 2. Varredura do Drive removida do loop automático (POP: Manual apenas)
            # if time.time() - last_drive_sync > 120:
            #     log_to_web("[AUTOMAÇÃO] Iniciando varredura automática do Drive...")
            #     threading.Thread(target=motor.executar_automacao, kwargs={'log_callback': log_to_web}, daemon=True).start()
            #     last_drive_sync = time.time()


                
        except Exception as e:
            print(f"Erro no agendador: {e}")
        time.sleep(30)

threading.Thread(target=verificar_agendamentos, daemon=True).start()


def executar_job(job):
    """Executa um job (imediato ou agendado)."""
    global ACTIVE_JOB_ID
    from video_engine import reset_cancelamento
    reset_cancelamento()
    
    job_id = job['id']
    ACTIVE_JOB_ID = job_id
    
    cfg = carregar_config()
    sessoes = job.get('sessions', [])
    total = len(sessoes)
    
    jobs_status[job_id] = {
        'status': 'running', 
        'progress': 0, 
        'current_step': 'Iniciando análise...',
        'files': [],
        '_total_files': total,
        '_current_idx': 0
    }
    
    sucessos = 0
    try:
        for i, sessao in enumerate(sessoes):
            nome = sessao.get('media_name', '')
            
            # POP: Verifica se o job foi cancelado antes de iniciar cada arquivo
            import video_engine
            if video_engine.SHOULD_CANCEL:
                log_to_web("🛑 [JOB] Cancelamento detectado. Interrompendo fila...")
                break

            jobs_status[job_id]['files'].append({'name': nome, 'status': 'processing'})
            log_to_web(f"[JOB] Processando {i+1}/{total}: {nome}")
            
            ok = motor.processar_sessao(
                media_path   = sessao.get('media_path'),
                cover_path   = sessao.get('cover_path'),
                titulo       = sessao.get('titulo') or None,
                cfg          = cfg,
                log_callback = log_to_web
            )

            if ok:
                sucessos += 1
            
            jobs_status[job_id]['files'][i]['status'] = 'done' if ok else 'error'
            # Atualiza para o próximo degrau fixo
            jobs_status[job_id]['progress'] = int(((i + 1) / total) * 100)
            delay = cfg.get('processing', {}).get('antispam_delay_seconds', 900)
            if ok and (i + 1) < total and delay > 0:
                log_to_web(f"[ANTISPAM] Aguardando {delay}s...")
                import time; time.sleep(delay)
        
        jobs_status[job_id]['status'] = 'done'
        ACTIVE_JOB_ID = None # Limpa o job ativo
    except Exception as e:
        jobs_status[job_id]['status'] = 'error'
        ACTIVE_JOB_ID = None # Limpa mesmo em erro
        log_to_web(f"❌ JOB {job_id[:8]} ERRO: {e}")

# ── Rotas Base ──────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/stream-logs')
def stream_logs():
    def generate():
        q = broadcaster.subscribe()
        try:
            while True:
                msg = q.get()
                yield f"data: {msg}\n\n"
        except GeneratorExit:
            pass
        finally:
            broadcaster.unsubscribe(q)
    return Response(generate(), mimetype='text/event-stream')

@app.route('/stats')
def get_stats():
    import psutil
    net = psutil.net_io_counters()
    disk = psutil.disk_usage('/')
    return jsonify({
        "cpu": psutil.cpu_percent(interval=0.1), 
        "ram": psutil.virtual_memory().percent,
        "net_sent": round(net.bytes_sent / (1024 * 1024), 2), # MB enviado
        "net_recv": round(net.bytes_recv / (1024 * 1024), 2), # MB recebido
        "disk": disk.percent
    })

# ── Upload de Ficheiros ─────────────────────────────────────────
def _save_upload(file, subfolder=''):
    """Salva um ficheiro e retorna o caminho."""
    folder = os.path.join(app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(folder, exist_ok=True)
    filename = secure_filename(file.filename)
    path = os.path.join(folder, filename)
    file.save(path)
    return path, filename

@app.route('/upload-media', methods=['POST'])
def upload_media():
    """Upload de um único ficheiro de mídia (áudio ou vídeo)."""
    file = request.files.get('file')
    if not file: return jsonify({"error": "Sem ficheiro"}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in FORMATOS_ACEITES:
        return jsonify({"error": f"Formato '{ext}' não suportado"}), 415
    tipo = 'audio' if ext in AUDIO_EXTENSIONS else 'video'
    path, name = _save_upload(file)
    return jsonify({"success": True, "path": path, "name": name, "type": tipo})

@app.route('/upload-cover', methods=['POST'])
def upload_cover():
    """Upload de imagem de capa."""
    file = request.files.get('file')
    if not file: return jsonify({"error": "Sem ficheiro"}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in IMAGEM_EXT:
        return jsonify({"error": "Formato de imagem não suportado. Use JPG, PNG ou WEBP"}), 415
    path, name = _save_upload(file, 'covers')
    return jsonify({"success": True, "path": path, "name": name})

@app.route('/upload-batch', methods=['POST'])
def upload_batch():
    """Triagem Industrial: Recebe, valida e inicia o processamento automático."""
    from database import ja_foi_postado
    files = request.files.getlist('files')
    if not files: return jsonify({"error": "Nenhum ficheiro recebido."}), 400
    
    log_to_web(f"📥 [ADMISSÃO] Recebendo lote de {len(files)} ficheiro(s)...")
    
    resultado = []
    sessoes_para_job = []
    duplicados = 0
    formatos_invalidos = 0
    
    for file in files:
        nome_original = file.filename
        if ja_foi_postado(f"LOCAL_{secure_filename(nome_original)}"):
            log_to_web(f"⚠️ [SKIP] {nome_original} já publicado anteriormente. Ignorado.")
            duplicados += 1
            continue
            
        ext = os.path.splitext(nome_original)[1].lower()
        if ext not in FORMATOS_ACEITES:
            log_to_web(f"❌ [ERRO] Formato de {nome_original} não suportado.")
            formatos_invalidos += 1
            continue
            
        tipo = 'audio' if ext in AUDIO_EXTENSIONS else 'video'
        path, name = _save_upload(file)
        resultado.append({"path": path, "name": name, "type": tipo})
        sessoes_para_job.append({"media_path": path, "media_name": name, "type": tipo})

    if sessoes_para_job:
        log_to_web(f"📦 [FILA] {len(sessoes_para_job)} ficheiro(s) adicionados à fila de processamento local.")
    else:
        log_to_web(f"🛑 [FILTRO] Nenhum ficheiro novo admitido (Duplicados: {duplicados} | Inválidos: {formatos_invalidos})")

    return jsonify({"success": True, "admitidos": len(sessoes_para_job), "duplicados": duplicados})

@app.route('/process-queue', methods=['POST'])
def process_queue():
    """Lê todos os ficheiros na pasta de upload e inicia um job de processamento em massa."""
    folder = app.config['UPLOAD_FOLDER']
    sessoes = []
    
    # Faz varredura da pasta local
    for ext in FORMATOS_ACEITES:
        for f in glob.glob(os.path.join(folder, f'*{ext}')):
            name = os.path.basename(f)
            tipo = 'audio' if os.path.splitext(f)[1].lower() in AUDIO_EXTENSIONS else 'video'
            sessoes.append({
                "media_path": f,
                "media_name": name,
                "type": tipo
            })
    
    if not sessoes:
        return jsonify({"success": False, "error": "Nenhum ficheiro na fila para processar."})
    
    job_id = str(uuid.uuid4())
    job = {"id": job_id, "sessions": sessoes, "scheduled_at": datetime.now().isoformat()}
    job_executor.submit(executar_job, job)
    
    log_to_web(f"🚀 [MOTOR] Processamento em massa iniciado para {len(sessoes)} ficheiro(s).")
    return jsonify({"success": True, "job_id": job_id, "count": len(sessoes)})



# ── Publicação ──────────────────────────────────────────────────
@app.route('/publish', methods=['POST'])
def publish():
    """Publica imediatamente uma ou mais sessões de mídia."""
    data = request.json or {}
    sessions = data.get('sessions', [])
    if not sessions: return jsonify({"error": "Nenhuma sessão de mídia"}), 400

    job_id = str(uuid.uuid4())
    job = {"id": job_id, "status": "running", "sessions": sessions, "created_at": datetime.now().isoformat()}
    job_executor.submit(executar_job, job)
    return jsonify({"success": True, "job_id": job_id})

@app.route('/schedule', methods=['POST'])
def schedule():
    """Agenda a publicação para uma data/hora específica."""
    data = request.json or {}
    sessions = data.get('sessions', [])
    scheduled_at = data.get('scheduled_at', '')
    if not sessions or not scheduled_at:
        return jsonify({"error": "Sessões e data/hora são obrigatórios"}), 400

    job_id = str(uuid.uuid4())
    job = {
        "id": job_id, "status": "pending",
        "sessions": sessions, "scheduled_at": scheduled_at,
        "created_at": datetime.now().isoformat()
    }
    jobs = carregar_agendamentos()
    jobs.append(job)
    salvar_agendamentos(jobs)
    return jsonify({"success": True, "job_id": job_id, "scheduled_at": scheduled_at})

@app.route('/sync-drive', methods=['POST'])
def sync_drive():
    """Inicia a varredura automática do Google Drive."""
    threading.Thread(target=motor.executar_automacao, daemon=True).start()
    return jsonify({"success": True, "message": "Varredura do Drive iniciada em background."})


# ── Status de Jobs ──────────────────────────────────────────────
@app.route('/jobs', methods=['GET'])
def get_jobs():
    agendados = carregar_agendamentos()
    em_curso = [{"id": k, **v} for k, v in jobs_status.items()]
    return jsonify({"scheduled": agendados, "active": em_curso})

@app.route('/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    return jsonify(jobs_status.get(job_id, {"status": "not_found"}))

@app.route('/cancel-job', methods=['POST'])
def cancel_job():
    global ACTIVE_JOB_ID
    from video_engine import solicitar_cancelamento
    
    if (ACTIVE_JOB_ID and ACTIVE_JOB_ID in jobs_status):
        jobs_status[ACTIVE_JOB_ID]['status'] = 'error'
        jobs_status[ACTIVE_JOB_ID]['current_step'] = 'Interrompido pelo utilizador'
        
    threading.Thread(target=solicitar_cancelamento, daemon=True).start()
    log_to_web("⚠️ [COMANDO] Solicitação de interrupção enviada.")
    return jsonify({"success": True, "message": "Interrupção iniciada."})

@app.route('/cancel-schedule/<job_id>', methods=['DELETE'])
def cancel_schedule(job_id):
    jobs = [j for j in carregar_agendamentos() if j['id'] != job_id]
    salvar_agendamentos(jobs)
    return jsonify({"success": True})

# ── Biblioteca ──────────────────────────────────────────────────
@app.route('/library')
def get_library():
    conn = sqlite3.connect('automacao.db')
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT * FROM postagens ORDER BY data_publicacao DESC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/pending-files')
def get_pending_files():
    folder = app.config['UPLOAD_FOLDER']
    todos = []
    for ext in FORMATOS_ACEITES:
        # Busca case-insensitive no Windows
        todos.extend(glob.glob(os.path.join(folder, f'*{ext}')))
    return jsonify([os.path.basename(f) for f in sorted(todos)])

@app.route('/delete-pending', methods=['POST'])
def delete_pending():
    nome = request.json.get('filename', '')
    if not nome: return jsonify({"error": "Nome inválido"}), 400
    
    # IMPORTANTE: Usamos o nome direto pois ele veio do glob do servidor
    folder = app.config['UPLOAD_FOLDER']
    caminho = os.path.join(folder, nome)
    
    if os.path.exists(caminho):
        try:
            os.remove(caminho)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": f"Erro ao apagar: {str(e)}"}), 500
    return jsonify({"error": "Ficheiro não encontrado"}), 404

@app.route('/clear-queue', methods=['POST'])
def clear_queue():
    """Remove todos os ficheiros da fila de uploads."""
    folder = app.config['UPLOAD_FOLDER']
    count = 0
    erros = []
    for ext in FORMATOS_ACEITES:
        for f in glob.glob(os.path.join(folder, f'*{ext}')):
            try:
                os.remove(f)
                count += 1
            except Exception as e:
                erros.append(f"{os.path.basename(f)}: {str(e)}")
    
    return jsonify({"success": True, "count": count, "errors": erros})



# ── Status dos Módulos ──────────────────────────────────────────
@app.route('/module-status')
def get_module_status():
    status = {}
    cfg = carregar_config()
    key = cfg.get('api_keys', {}).get('gemini', '')
    status['gemini'] = {'ok': bool(key), 'msg': 'Configurada' if key else 'Não configurada'}
    ffmpeg = shutil.which('ffmpeg')
    status['ffmpeg'] = {'ok': bool(ffmpeg), 'msg': ffmpeg or 'Não encontrado'}
    try:
        email = _get_active_account()
        status['youtube'] = {'ok': bool(email), 'email': email, 'msg': email or 'Desconectada'}
    except:
        status['youtube'] = {'ok': False, 'msg': 'Erro'}
    try:
        conn = sqlite3.connect('automacao.db')
        n = conn.execute('SELECT COUNT(*) FROM postagens').fetchone()[0]
        conn.close()
        status['db'] = {'ok': True, 'msg': f'{n} registos'}
    except:
        status['db'] = {'ok': False, 'msg': 'Erro'}
    status['drive'] = {'ok': status['youtube']['ok'], 'msg': 'Ativo' if status['youtube']['ok'] else 'Inativo'}
    return jsonify(status)

@app.route('/audit-report', methods=['GET'])
def get_audit_report():
    """Retorna o conteúdo do relatório de auditoria."""
    from monitor_module import auditor
    return jsonify({"report": auditor.gerar_resumo_executivo()})

# ── Configurações ───────────────────────────────────────────────

@app.route('/settings', methods=['GET', 'POST'])
def manage_settings():
    if request.method == 'GET':
        return jsonify(carregar_config())
    try:
        dados = request.json
        if not dados: return jsonify({"error": "Sem dados"}), 400

        # --- Garante valores padrão para campos de pasta ---
        # Se o utilizador deixar vazio, o Windows falha com WinError 3
        proc = dados.setdefault('processing', {})
        if not proc.get('upload_folder'):
            proc['upload_folder'] = 'musicas_pendentes'
        if not proc.get('temp_folder'):
            proc['temp_folder'] = 'temp_files'

        # Cria as pastas garantidas
        nova_pasta = proc['upload_folder']
        temp_pasta = proc['temp_folder']
        os.makedirs(nova_pasta, exist_ok=True)
        os.makedirs(temp_pasta, exist_ok=True)
        app.config['UPLOAD_FOLDER'] = nova_pasta

        salvar_config(dados)
        return jsonify({"success": True})
    except Exception as e:
        safe_log(f"[ERRO CRITICO] Falha ao salvar configuracoes: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/test-gemini', methods=['POST'])
def test_gemini():
    import requests
    key = request.json.get('key', '')
    if not key: return jsonify({"error": "Sem chave"}), 400
    try:
        res = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}", timeout=10)
        if res.status_code == 200:
            return jsonify({"success": True, "message": "Conexão estabelecida!"})
        return jsonify({"error": "Chave inválida"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Contas YouTube ──────────────────────────────────────────────
@app.route('/accounts', methods=['GET'])
def get_accounts():
    return jsonify({"contas": listar_contas(), "ativa": _get_active_account()})

@app.route('/accounts/add', methods=['POST'])
def add_account():
    threading.Thread(target=adicionar_conta, daemon=True).start()
    return jsonify({"status": "login_iniciado", "message": "Janela de login aberta."})

@app.route('/accounts/switch', methods=['POST'])
def switch_account():
    email = request.json.get('email')
    if not email: return jsonify({"error": "E-mail necessário"}), 400
    trocar_conta_activa(email)
    return jsonify({"success": True})

@app.route('/accounts/remove', methods=['POST'])
def remove_account():
    email = request.json.get('email')
    if not email: return jsonify({"error": "E-mail necessário"}), 400
    remover_conta(email)
    return jsonify({"success": True})

@app.route('/sync-drive', methods=['POST'])
def sync_drive_manual():
    """Dispara a sincronização do Drive sob demanda."""
    threading.Thread(target=motor.executar_automacao, kwargs={'log_callback': log_to_web}, daemon=True).start()
    return jsonify({"success": True, "message": "Sincronização iniciada."})

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
