import ffmpeg
import os
import json
import subprocess
import re
import signal

# Registro global para permitir interrupção
ACTIVE_FFMPEG_PROCESS = None
SHOULD_CANCEL = False

def solicitar_cancelamento():
    global SHOULD_CANCEL, ACTIVE_FFMPEG_PROCESS
    SHOULD_CANCEL = True
    if ACTIVE_FFMPEG_PROCESS:
        try:
            # Tenta terminar suavemente
            ACTIVE_FFMPEG_PROCESS.terminate()
            # Se não morrer em 2s, mata de vez
            try:
                ACTIVE_FFMPEG_PROCESS.wait(timeout=2)
            except:
                ACTIVE_FFMPEG_PROCESS.kill()
            print("[MOTOR] FFmpeg encerrado com sucesso.")
        except Exception as e:
            print(f"[MOTOR] Nota: Processo já estava encerrado ou erro ao matar: {e}")
        finally:
            ACTIVE_FFMPEG_PROCESS = None

def reset_cancelamento():
    global SHOULD_CANCEL
    SHOULD_CANCEL = False

# ── Detecção de Codec na Inicialização (executado apenas 1x) ─────────────
def _testar_codec(codec):
    """Verifica silenciosamente se o FFmpeg suporta um codec específico."""
    try:
        subprocess.run(
            ['ffmpeg', '-f', 'lavfi', '-i', 'color=c=black:s=64x64',
             '-frames:v', '1', '-vcodec', codec, '-f', 'null', '-'],
            capture_output=True, check=True, timeout=10
        )
        return True
    except Exception:
        return False

def _detectar_melhor_codec():
    """Detecta e cacheia o codec mais rápido disponível (GPU > CPU)."""
    if _testar_codec('h264_nvenc'):
        print("[MOTOR] Turbo: NVIDIA NVENC Ativo (GPU)")
        return 'h264_nvenc'
    if _testar_codec('h264_qsv'):
        print("[MOTOR] Turbo: Intel QSV Ativo (GPU)")
        return 'h264_qsv'
    print("[MOTOR] Usando libx264 (CPU ultrafast)")
    return 'libx264'

# Cache global
_CODEC_CACHE = _detectar_melhor_codec()

def get_melhor_vcodec():
    return _CODEC_CACHE

# ── Tipos de Arquivo Suportados ──────────────────────────────────────────
AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.ogg', '.aac', '.m4a', '.wma', '.opus', '.aiff'}
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.webm', '.3gp', '.ts', '.mpeg', '.mpg'}

def detectar_tipo(caminho):
    ext = os.path.splitext(caminho)[1].lower()
    if ext in AUDIO_EXTENSIONS: return 'audio'
    if ext in VIDEO_EXTENSIONS: return 'video'
    return None

def get_audio_info(caminho):
    """Retorna bitrate (kbps) e duração (segundos)."""
    try:
        probe = ffmpeg.probe(caminho)
        audio = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
        bitrate = int(audio['bit_rate']) // 1000 if audio and 'bit_rate' in audio else 0
        duration = float(probe['format']['duration'])
        return bitrate, duration
    except:
        return 0, 0

def processar_midia(caminho_entrada, caminho_capa, caminho_saida, cfg=None, cor_spectrum=None, log_callback=None):
    tipo = detectar_tipo(caminho_entrada)
    if not cfg: cfg = {}
    if tipo == 'audio':
        return criar_video_com_spectrum(caminho_entrada, caminho_capa, caminho_saida, cfg, cor_spectrum, log_callback)
    elif tipo == 'video':
        return converter_video_para_youtube(caminho_entrada, caminho_saida, cfg, log_callback)
    return False

from monitor_module import auditor

def _build_output_args(codec, v_bit, preset, v_cfg):
    args = {
        'b:v':      v_bit,
        'threads':  'auto',
        'pix_fmt':  'yuv420p',
        'movflags': '+faststart',
    }
    if codec == 'libx264':
        args['preset'] = preset
        args['tune']   = 'stillimage'
        args['crf']    = v_cfg.get('crf', 28)
    elif codec == 'h264_nvenc':
        args['rc']  = 'vbr'
        args['cq']  = v_cfg.get('crf', 28)
        args['preset'] = 'p1'
    elif codec == 'h264_qsv':
        args['global_quality'] = v_cfg.get('crf', 28)
        args['preset']         = 'veryfast'
    
    if codec == 'libx264':
        args['threads'] = '0' 
    return args

def _run_ffmpeg_with_progress(ffmpeg_out, total_duration, label="Render", log_callback=None):
    """Executa FFmpeg e captura progresso temporal para o log."""
    if total_duration <= 0:
        ffmpeg_out.run(overwrite_output=True)
        return True

    # Obtém comando final
    cmd = ['ffmpeg', '-y'] + ffmpeg_out.get_args()
    
    try:
        # Abre processo capturando stderr (onde o FFmpeg cospe os stats)
        global ACTIVE_FFMPEG_PROCESS
        process = subprocess.Popen(
            cmd, 
            stderr=subprocess.PIPE, 
            universal_newlines=True, 
            encoding='utf-8', 
            errors='replace'
        )
        ACTIVE_FFMPEG_PROCESS = process

        # Regex para capturar time=00:00:00.00
        time_regex = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.\d{2}")
        
        last_pct = -1
        for line in process.stderr:
            match = time_regex.search(line)
            if match:
                h, m, s = map(int, match.groups())
                current_seconds = h * 3600 + m * 60 + s
                pct = int((current_seconds / total_duration) * 100)
                if pct > last_pct and pct <= 100:
                    msg = f"[{label}] Progresso: {pct}%"
                    if log_callback:
                        try: log_callback(msg)
                        except: pass
                    else:
                        print(msg)
                    last_pct = pct
            
            # POP: Verifica cancelamento durante o processamento
            if SHOULD_CANCEL:
                process.terminate()
                print("[MOTOR] Processo interrompido pelo utilizador.")
                break
        
        process.wait()
        ACTIVE_FFMPEG_PROCESS = None
        return process.returncode == 0
    except Exception as e:
        print(f"[MOTOR] Erro ao monitorar progresso: {e}")
        return False

def criar_video_com_spectrum(caminho_audio, caminho_imagem, caminho_saida, cfg, cor_spectrum=None, log_callback=None):
    print(f"[MOTOR] Preparando: {os.path.basename(caminho_audio)}")

    bitrate, duration = get_audio_info(caminho_audio)
    if bitrate > 0 and bitrate < 128:
        erro_msg = f"Bitrate insuficiente: {bitrate}kbps (mínimo: 128kbps)"
        auditor.registrar_violacao('VALIDAÇÃO', os.path.basename(caminho_audio), erro_msg, "MÉDIA")
        return False

    v_cfg   = cfg.get('video', {})
    s_cfg   = cfg.get('spectrum', {})
    res     = v_cfg.get('resolution') or '1280x720'
    v_bit   = v_cfg.get('video_bitrate') or '2000k'
    a_bit   = v_cfg.get('audio_bitrate') or '192k'
    preset  = v_cfg.get('quality_preset') or 'ultrafast'
    codec   = get_melhor_vcodec()

    s_mode  = s_cfg.get('mode', 'cline')
    s_color = cor_spectrum or s_cfg.get('color', '0xffffff@0.6')
    s_y     = s_cfg.get('position_y', 580)

    w, h = res.split('x')
    
    try:
        audio_input = ffmpeg.input(caminho_audio)
        audio_stream = audio_input.audio

        if caminho_imagem and os.path.exists(caminho_imagem):
            video_input = ffmpeg.input(caminho_imagem, loop=1, r=30)
        else:
            video_input = ffmpeg.input(f'color=c=black:s={res}:r=30', format='lavfi')

        spectrum = audio_stream.filter('showwaves', s=f'{w}x200', mode=s_mode, colors=s_color, r=15)
        v = ffmpeg.overlay(video_input, spectrum, x=0, y=s_y)

        output_args = _build_output_args(codec, v_bit, preset, v_cfg)
        
        out = ffmpeg.output(
            v, audio_stream, caminho_saida,
            vcodec=codec, acodec='aac', audio_bitrate=a_bit,
            r=30,
            **{**output_args, 'shortest': None}
        )

        return _run_ffmpeg_with_progress(out, duration, "Render", log_callback)

    except Exception as e:
        print(f"[MOTOR ERRO] Spectrum: {e}")
        auditor.registrar_violacao('RENDER', os.path.basename(caminho_audio), str(e), "ALTA")
        return False

def converter_video_para_youtube(caminho_entrada, caminho_saida, cfg, log_callback=None):
    print(f"[MOTOR] Normalizando vídeo: {os.path.basename(caminho_entrada)}")
    
    v_cfg = cfg.get('video', {})
    res   = v_cfg.get('resolution', '1280x720')
    w, h  = res.split('x')
    codec = get_melhor_vcodec()
    
    try:
        probe = ffmpeg.probe(caminho_entrada)
        duration = float(probe['format']['duration'])
        
        entrada = ffmpeg.input(caminho_entrada)
        output_args = _build_output_args(codec, v_cfg.get('video_bitrate', '2000k'), 'ultrafast', v_cfg)
        
        out = ffmpeg.output(
            entrada, caminho_saida,
            vcodec=codec, acodec='aac',
            audio_bitrate=v_cfg.get('audio_bitrate', '192k'),
            vf=f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2',
            **output_args
        )
        return _run_ffmpeg_with_progress(out, duration, "Conversão", log_callback)
    except Exception as e:
        print(f"[MOTOR ERRO] Conversão: {e}")
        return False
