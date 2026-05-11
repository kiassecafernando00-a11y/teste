import time
import json
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from auth_module import get_youtube_service, _get_active_account

# Caminho absoluto para o config.json (POP 1.2)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')


def _carregar_cfg_youtube():
    """Lê as preferências de publicação do config.json."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f).get('youtube', {})
    return {}


from monitor_module import auditor

def fazer_upload_youtube(caminho_video, titulo, descricao, tags, privacidade=None):
    """
    Faz o upload do vídeo para o YouTube usando EXCLUSIVAMENTE a conta
    autenticada via OAuth (configurada em Configurações → Contas YouTube).

    - privacidade: se None, usa o valor de config.json (youtube.visibility)
    """
    conta_activa = _get_active_account()
    if not conta_activa:
        msg = "Nenhuma conta YouTube conectada."
        print(f"[YOUTUBE] AVISO: {msg}")
        print("[YOUTUBE] Acede a Configurações → Contas YouTube → Adicionar Conta.")
        auditor.registrar_violacao('UPLOAD', os.path.basename(caminho_video), msg, "ALTA")
        return None

    print(f"[YOUTUBE] A usar conta: {conta_activa}")

    # Lê visibilidade do config se não foi passada explicitamente
    if privacidade is None:
        cfg = _carregar_cfg_youtube()
        privacidade = cfg.get('visibility', 'private')

    print(f"[YOUTUBE] Visibilidade: {privacidade}")

    try:
        youtube = get_youtube_service(email=conta_activa)
    except FileNotFoundError as e:
        print(f"[YOUTUBE] Erro de autenticação: {e}")
        return None
    except Exception as e:
        print(f"[YOUTUBE] Falha ao criar serviço: {e}")
        return None

    # Normaliza as tags para lista
    if isinstance(tags, str):
        lista_tags = [t.strip() for t in tags.split(',') if t.strip()]
    else:
        lista_tags = list(tags) if tags else []

    corpo = {
        'snippet': {
            'title':       titulo[:100],       # YouTube limita título a 100 chars
            'description': descricao[:5000],   # YouTube limita descrição a 5000 chars
            'tags':        lista_tags[:500],   # YouTube limita a 500 tags
            'categoryId':  '10'               # 10 = Música
        },
        'status': {
            'privacyStatus': privacidade
        }
    }

    media = MediaFileUpload(
        caminho_video,
        chunksize=1024 * 1024 * 10,   # 10 MB por chunk para maior estabilidade
        resumable=True,
        mimetype='video/mp4'
    )

    request = youtube.videos().insert(
        part=','.join(corpo.keys()),
        body=corpo,
        media_body=media
    )

    print(f"[YOUTUBE] Upload iniciado: '{titulo}'")

    response    = None
    tentativas  = 0
    max_tent    = 5

    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                pct = int(status.progress() * 100)
                print(f"[YOUTUBE] Upload: {pct}%")

        except HttpError as e:
            if e.resp.status in [500, 502, 503, 504]:
                tentativas += 1
                if tentativas > max_tent:
                    print(f"[YOUTUBE] Upload cancelado após {max_tent} falhas de rede.")
                    return None
                print(f"[YOUTUBE] Erro de rede ({e.resp.status}). Tentativa {tentativas}/{max_tent} em 10s...")
                time.sleep(10)
            elif e.resp.status == 403:
                print("[YOUTUBE] Erro 403: Quota excedida ou permissão negada. Verifique as credenciais.")
                return None
            elif e.resp.status == 401:
                print("[YOUTUBE] Erro 401: Token expirado ou conta desautorizada. Reconecte a conta.")
                return None
            elif e.resp.status == 400 and "uploadLimitExceeded" in str(e):
                print(f"[YOUTUBE] 🛑 Limite diário de upload atingido para a conta: {conta_activa}")
                print("[YOUTUBE] DICA: Adicione ou troque para outra conta no Painel de Configurações.")
                return "LIMIT_EXCEEDED"
            else:
                print(f"[YOUTUBE] Erro da API: {e}")
                return None

        except Exception as e:
            tentativas += 1
            if tentativas > max_tent:
                print(f"[YOUTUBE] Erro fatal após {max_tent} tentativas: {e}")
                return None
            
            # POP 1.4: Recuperação de Erros de Rede/SSL
            espera = 15 * tentativas
            print(f"[YOUTUBE] Erro inesperado ({e}). Tentando recuperar (T {tentativas}/{max_tent}) em {espera}s...")
            time.sleep(espera)
            # Re-inicializa a request se necessário ou apenas continua se for chunk
            continue

    video_id = response.get('id')
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"[YOUTUBE] ✅ Publicado com sucesso!")
    print(f"[YOUTUBE] Conta: {conta_activa}")
    print(f"[YOUTUBE] URL:   {url}")
    return video_id


if __name__ == "__main__":
    print("Teste de upload desativado. Use main.py para produção.")
