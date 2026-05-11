import os
import time
import json
import shutil
import threading
from ai_module import gerar_metadados_musica
from video_engine import processar_midia, detectar_tipo
from youtube_module import fazer_upload_youtube
from database import iniciar_db, ja_foi_postado, registrar_postagem
from image_engine import gerar_capa_personalizada
from autonomous_art_engine import AutonomousArtEngine
from auth_module import listar_contas, trocar_conta_activa, _get_active_account
from vertical_engine import criar_youtube_short
from audio_analyzer import analisar_vibe_musical
import hashlib

def calcular_hash_arquivo(caminho):
    """Calcula o hash MD5 de um ficheiro para identificar duplicatas reais."""
    try:
        hash_md5 = hashlib.md5()
        with open(caminho, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except:
        return None

iniciar_db()
art_designer = AutonomousArtEngine()
CONFIG_PATH = 'config.json'
PASTA_TEMP  = 'temp_files'
_lock_automacao = threading.Lock()

def carregar_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def _log(msg):
    """Log seguro para evitar UnicodeEncodeError no Windows."""
    try:
        print(msg)
    except:
        try:
            print(str(msg).encode('ascii', errors='replace').decode('ascii'))
        except:
            pass

def _limpar(*caminhos):
    """Remove ficheiros temporários com segurança."""
    for c in caminhos:
        if c and os.path.exists(c) and PASTA_TEMP in str(c):
            try: os.remove(c)
            except: pass

def processar_sessao(media_path, cover_path=None, titulo=None, cfg=None, log_callback=None):
    """
    Fluxo completo para um único ficheiro (áudio ou vídeo) com capa opcional.
    """
    def _log(msg):
        globals()['_log'](msg) # Chama a versão global segura
        if log_callback:
            try: log_callback(msg)
            except: pass

    from monitor_module import auditor

    if cfg is None:
        cfg = carregar_config()

    os.makedirs(PASTA_TEMP, exist_ok=True)

    nome = os.path.basename(media_path)
    tipo = detectar_tipo(media_path)
    
    # Gera um ID baseado no conteúdo (Hash) para evitar duplicatas reais
    hash_f = calcular_hash_arquivo(media_path)
    id_ref = f"HASH_{hash_f}" if hash_f else f"LOCAL_{nome}"
    
    _log(f"\n{'='*50}")
    _log(f"[SESSÃO] {nome}  ({tipo.upper() if tipo else 'desconhecido'})")
    _log(f"[ID_REF] {id_ref}")
    _log(f"{'='*50}")

    if ja_foi_postado(id_ref):
        _log(f"[SKIP] Este ficheiro (ou conteúdo idêntico) já foi publicado anteriormente.")
        return True # Retorna True para continuar o lote se houver

    if tipo is None:
        _log(f"[SKIP] Formato não suportado: {nome}")
        return False

    video_gerado = os.path.join(PASTA_TEMP, f"yt_{id_ref[:30].replace(':', '_')}.mp4")
    capa_gerada  = None

    try:
        # 0. Análise de Vibe (Novo)
        vibe_info = analisar_vibe_musical(media_path)
        cor_spectrum = vibe_info.get('cor_nome') if vibe_info else None

        # 1. Metadados via Gemini AI (Deep Analysis)
        import video_engine
        if video_engine.SHOULD_CANCEL: return False

        _log("[IA] Iniciando análise técnica profunda...")
        meta = gerar_metadados_musica(media_path, vibe_info=vibe_info)

        # Verificação pós-análise IA
        if video_engine.SHOULD_CANCEL: return False

        # Título: manual tem prioridade sobre IA
        if titulo and titulo.strip():
            meta['titulo'] = titulo.strip()
            _log(f"[IA] Título personalizado: {meta['titulo']}")
        else:
            _log(f"[IA] Título gerado: {meta['titulo']}")

        # --- FORMATAÇÃO FINAL DE METADADOS (Branding) ---
        yt_cfg = cfg.get('youtube', {})
        
        # 1. Aplicar Prefixo/Sufixo ao Título (Manual ou IA)
        prefix = yt_cfg.get('title_prefix', '').strip()
        suffix = yt_cfg.get('title_suffix', '').strip()
        if prefix: meta['titulo'] = f"{prefix} {meta['titulo']}"
        if suffix: meta['titulo'] = f"{meta['titulo']} {suffix}"

        # 2. Adicionar Tags Padrão
        default_tags = yt_cfg.get('default_tags', '')
        if default_tags:
            extras = [t.strip() for t in default_tags.split(',') if t.strip()]
            if isinstance(meta.get('tags'), list):
                meta['tags'] = list(set(meta['tags'] + extras))
            elif isinstance(meta.get('tags'), str):
                meta['tags'] = f"{default_tags}, {meta['tags']}"
            else:
                meta['tags'] = extras

        # 3. Adicionar Descrição Padrão
        default_desc = yt_cfg.get('default_description', '')
        if default_desc and default_desc not in meta.get('descricao', ''):
            meta['descricao'] = f"{meta.get('descricao', '')}\n\n{default_desc}".strip()

        # --- REGRA 1: VALIDAÇÃO DE QUALIDADE (POP 1.1) ---
        if os.path.getsize(media_path) < 1 * 1024 * 1024: # Menor que 1MB
            msg = "Ficheiro demasiado pequeno (<1MB). Possível áudio corrompido."
            _log(f"[ALERTA] {msg}")
            auditor.registrar_violacao("VALIDAÇÃO", nome, msg, "ALTA")
            return False

        # --- REGRA 2: FILTRO DE LINGUAGEM PÓS-IA (POP 2.1) ---
        if "!!!" in meta.get('descricao', '') or any(e in meta.get('titulo', '') for e in ["🔥", "🚀", "🎵"]):
            msg = "Uso de emojis ou pontuação excessiva detectado. Aplicando correção automática."
            auditor.registrar_violacao("IA_SEO", nome, msg, "MÉDIA")
            meta['titulo'] = meta['titulo'].replace("🔥", "").replace("🚀", "").replace("🎵", "").strip()
            meta['descricao'] = meta['descricao'].replace("!!!", ".").strip()

        # 2. Capa: usa capa fornecida, gera autônoma, ou usa personalizada (fallback)
        if tipo == 'audio':
            p_cfg = cfg.get('processing', {})
            v_cfg = cfg.get('video', {})
            use_art_engine = p_cfg.get('use_autonomous_art', False)
            fundo_padrao = v_cfg.get('cover_image_path', 'assets/fundo_padrao.jpg')

            if cover_path and os.path.exists(cover_path):
                _log(f"[CAPA] Usando capa fornecida: {os.path.basename(cover_path)}")
                capa_para_usar = cover_path
            elif use_art_engine:
                import video_engine
                if video_engine.SHOULD_CANCEL: return False

                _log("[CAPA] Motor de Arte Autônoma: Criando arte única via DALL-E 3...")
                try:
                    # Tenta gerar a arte autônoma pura (Design Padrão solicitado)
                    capa_final_pura = art_designer.criar_capa_autonoma_pura(meta['titulo'], id_ref[:20])
                    
                    # Verificação pós-geração de arte
                    if video_engine.SHOULD_CANCEL: return False

                    if not capa_final_pura:
                        raise Exception("Falha ao gerar arte autônoma via OpenAI")
                    
                    capa_para_usar = capa_final_pura
                    _log("✅ Arte autônoma gerada e ajustada para 16:9 com sucesso.")
                except Exception as e:
                    _log(f"⚠️ Erro no Motor de Arte: {e}. Aplicando fallback de design clássico...")
                    if os.path.exists(fundo_padrao):
                        capa_gerada = os.path.join(PASTA_TEMP, f"capa_{id_ref[:20]}.jpg")
                        gerar_capa_personalizada(meta['titulo'], fundo_padrao, capa_gerada)
                        capa_para_usar = capa_gerada
                    else:
                        capa_para_usar = None
            elif os.path.exists(fundo_padrao):
                # Gera capa clássica (Título sobre fundo)
                _log("[CAPA] Gerando capa clássica (Título sobre Fundo)...")
                capa_gerada = os.path.join(PASTA_TEMP, f"capa_{id_ref[:20]}.jpg")
                gerar_capa_personalizada(meta['titulo'], fundo_padrao, capa_gerada)
                capa_para_usar = capa_gerada
            else:
                _log("[CAPA] Sem capa — fundo preto será usado.")
                capa_para_usar = None
        else:
            # Vídeo: capa é opcional (usado como thumbnail, não sobreposto)
            capa_para_usar = cover_path if cover_path and os.path.exists(cover_path) else None
            if capa_para_usar:
                _log(f"[CAPA] Thumbnail de vídeo: {os.path.basename(capa_para_usar)}")

        # 3. Processamento FFmpeg
        _log(f"[FFMPEG] Processando {tipo.upper()}...")
        try:
            sucesso = processar_midia(media_path, capa_para_usar, video_gerado, cfg, cor_spectrum=cor_spectrum, log_callback=log_callback)
        except Exception as e:
            auditor.registrar_violacao("RENDER", nome, f"Falha no motor FFmpeg: {e}")
            return False

        if not sucesso:
            auditor.registrar_violacao("RENDER", nome, "Falha na renderização de saída.")
            _limpar(video_gerado, capa_gerada)
            shutil.rmtree(PASTA_TEMP, ignore_errors=True)
            os.makedirs(PASTA_TEMP, exist_ok=True)
            return False

        # --- FLUXO DE PUBLICAÇÃO DUPLA (VÍDEO + SHORT) ---
        if cfg.get('processing', {}).get('generate_shorts', False):
            short_gerado = os.path.join(PASTA_TEMP, f"short_{id_ref[:20]}.mp4")
            _log("[MOTOR] Criando versão Shorts (Vertical 9:16) para divulgação...")
            
            if tipo == 'audio' and capa_para_usar:
                sucesso_short = criar_youtube_short(media_path, capa_para_usar, short_gerado)
                if sucesso_short:
                    # Metadados específicos para o Short
                    titulo_short = f"{meta['titulo']} #Shorts #VibeGlobal"
                    _log(f"[YOUTUBE] Enviando Short: {titulo_short}")
                    
                    # Upload do Short
                    id_short = fazer_upload_youtube(
                        short_gerado, 
                        titulo_short, 
                        meta.get('descricao', ''), 
                        meta.get('tags', []),
                        "public"
                    )
                    
                    if id_short and id_short != "LIMIT_EXCEEDED":
                        _log(f"🚀 Short publicado com sucesso: https://youtube.com/shorts/{id_short}")
                    else:
                        _log("⚠️ Falha ou limite atingido ao enviar o Short.")
                else:
                    _log("⚠️ Falha técnica ao gerar o Short Vertical.")
            else:
                _log("[AVISO] Geração de Shorts ignorada (Tipo de mídia não suportado ou capa ausente).")

        # 4. Upload YouTube com Rotação Automática (Se limite atingido)
        id_yt = None
        while True:
            import video_engine
            if video_engine.SHOULD_CANCEL: 
                _log("🛑 [YOUTUBE] Upload cancelado pelo utilizador.")
                return False

            print(f"[YOUTUBE] Enviando '{meta['titulo']}'...")
            id_yt = fazer_upload_youtube(video_gerado, meta['titulo'], meta['descricao'], meta['tags'])
            
            if id_yt == "LIMIT_EXCEEDED":
                _log("⚠️ CONTA LIMITADA: O YouTube atingiu o limite diário para esta conta.")
                contas = listar_contas()
                conta_atual = _get_active_account()
                outras = [c['email'] for c in contas if c['email'] != conta_atual]
                
                if outras:
                    nova_conta = outras[0]
                    _log(f"🔄 ROTAÇÃO AUTOMÁTICA: Trocando para a conta: {nova_conta}")
                    trocar_conta_activa(nova_conta)
                    _log("⏳ Aguardando 10s para estabilização...")
                    time.sleep(10)
                    continue # Tenta o upload novamente com a nova conta
                else:
                    _log("❌ FALHA CRÍTICA: Não há outras contas disponíveis para rotação.")
                    break # Sai do loop e falha o upload
            else:
                break # Sucesso ou erro genérico
        
        if id_yt and id_yt != "LIMIT_EXCEEDED":
            registrar_postagem(id_ref, nome, id_yt, meta.get('titulo'))
            print(f"[OK] Publicado: https://youtube.com/watch?v={id_yt}")

            # Auto-delete do original se configurado
            if cfg.get('processing', {}).get('auto_delete_originals'):
                try:
                    os.remove(media_path)
                    print(f"[LIMPEZA] Original removido: {nome}")
                except: pass

            return True
        else:
            _log(f"[ERRO] Upload YouTube falhou para: {nome}")
            return False
            return False

    except Exception as e:
        print(f"[ERRO FATAL] {nome}: {e}")
        return False
    finally:
        _limpar(video_gerado, capa_gerada, locals().get('short_gerado'))

def processar_em_lote(lista, delay=None, log_callback=None):
    """
    Processa múltiplas sessões em sequência com Protocolo Antispam.
    """
    def _log(msg):
        print(msg)

    cfg = carregar_config()
    if delay is None:
        delay = cfg.get('processing', {}).get('antispam_delay_seconds', 900)
        # Limite mínimo reduzido para 60s para maior flexibilidade (conforme pedido de rapidez)
        if delay < 60: delay = 60

    total = len(lista)
    if total == 0:
        _log("[AVISO] Lote vazio.")
        return

    _log(f"\n[LOTE] {total} sessão(ões) na fila.")
    concluidos = 0

    for i, sessao in enumerate(lista):
        media = sessao.get('media_path') or sessao
        cover = sessao.get('cover_path') if isinstance(sessao, dict) else None
        titulo = sessao.get('titulo') if isinstance(sessao, dict) else None

        if not media or not os.path.exists(str(media)):
            _log(f"[SKIP] Ficheiro não encontrado: {media}")
            continue

        if ja_foi_postado(f"LOCAL_{os.path.basename(str(media))}"):
            _log(f"[SKIP] Já publicado: {os.path.basename(str(media))}")
            continue

        if processar_sessao(str(media), cover, titulo, cfg, log_callback=log_callback):
            concluidos += 1
            if (i + 1) < total:
                _log(f"[POP ANTISPAM] Aguardando {delay}s antes da próxima publicação...")
                time.sleep(delay)

    _log(f"\n[FINAL] {concluidos}/{total} publicados com sucesso.")

def executar_automacao(lista_manual=None, log_callback=None):
    """Ponto de entrada principal com trava de segurança contra duplicidade."""
    def _log(msg):
        if log_callback: log_callback(msg)
        print(msg)

    if not _lock_automacao.acquire(blocking=False):
        _log("[AVISO] Já existe uma varredura ou processamento em curso. Ignorando nova solicitação.")
        return

    try:
        _log("\n[SISTEMA] Motor Sonic Publisher AI Ativo")
        if lista_manual:
            processar_em_lote(lista_manual, log_callback=log_callback)
        else:
            _log("[DRIVE] Buscando ficheiros no Google Drive...")
            try:
                from drive_module import buscar_musicas_no_drive, baixar_arquivo_drive
                arquivos = buscar_musicas_no_drive()
                if arquivos:
                    sessoes = []
                    for a in arquivos:
                        _log(f"[DRIVE] Descarregando: {a['name']}...")
                        caminho = baixar_arquivo_drive(a['id'], a['name'], PASTA_TEMP)
                        if caminho and os.path.exists(caminho):
                            sessoes.append({'media_path': caminho, 'cover_path': None, 'titulo': None})
                    if sessoes:
                        _log(f"[DRIVE] {len(sessoes)} ficheiro(s) prontos para processar.")
                        processar_em_lote(sessoes, log_callback=log_callback)
                else:
                    _log("[DRIVE] Nenhum ficheiro novo encontrado.")

                # --- VERIFICAÇÃO LOCAL (musicas_pendentes) ---
                _log("[LOCAL] Buscando ficheiros na pasta 'musicas_pendentes'...")
                pasta_local = 'musicas_pendentes'
                if os.path.exists(pasta_local):
                    arquivos_locais = [os.path.join(pasta_local, f) for f in os.listdir(pasta_local) 
                                     if detectar_tipo(f)]
                    if arquivos_locais:
                        _log(f"[LOCAL] Encontrados {len(arquivos_locais)} ficheiros.")
                        sessoes_locais = [{'media_path': a, 'cover_path': None, 'titulo': None} for a in arquivos_locais]
                        processar_em_lote(sessoes_locais, log_callback=log_callback)
                    else:
                        _log("[LOCAL] Nenhum ficheiro pendente.")

            except Exception as e:
                _log(f"[ERRO NO MOTOR] {e}")
    finally:
        _lock_automacao.release()


if __name__ == "__main__":
    executar_automacao()
