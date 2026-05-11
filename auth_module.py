import os
import pickle
import json
import builtins

# Permite redirecionar logs do monitor
print = builtins.print
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Escopos necessários
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

# Caminho absoluto para evitar problemas de diretório no Windows (POP 1.2)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')
TOKENS_DIR   = os.path.join(BASE_DIR, 'tokens')


def _get_active_account():
    """Retorna o e-mail da conta activa guardado no config.json."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        return cfg.get('youtube_account', {}).get('active_email', '')
    return ''


def _set_active_account(email):
    """Guarda o e-mail da conta activa no config.json."""
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    cfg.setdefault('youtube_account', {})['active_email'] = email
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def _token_path(email):
    """Retorna o caminho do token para um e-mail."""
    os.makedirs(TOKENS_DIR, exist_ok=True)
    safe = email.replace('@', '_').replace('.', '_')
    return os.path.join(TOKENS_DIR, f'token_{safe}.pickle')


def _get_email_from_creds(creds):
    """Obtém o e-mail da conta a partir das credenciais OAuth."""
    try:
        import requests
        r = requests.get(
            'https://www.googleapis.com/oauth2/v1/userinfo',
            headers={'Authorization': f'Bearer {creds.token}'}
        )
        return r.json().get('email', 'E-mail não identificado')
    except Exception:
        return 'E-mail não identificado'


def listar_contas():
    """
    Retorna lista de dicionários com os e-mails das contas guardadas.
    Limpa ficheiros corrompidos automaticamente.
    """
    os.makedirs(TOKENS_DIR, exist_ok=True)
    ativa = _get_active_account()
    contas = []

    for ficheiro in os.listdir(TOKENS_DIR):
        if ficheiro.startswith('token_') and ficheiro.endswith('.pickle'):
            caminho = os.path.join(TOKENS_DIR, ficheiro)
            email_detectado = None
            try:
                with open(caminho, 'rb') as f:
                    creds = pickle.load(f)
                
                # Tenta obter o e-mail real
                email_detectado = _get_email_from_creds(creds)
                
                if email_detectado == 'E-mail não identificado':
                    # Tenta renovar se estiver expirado
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                        email_detectado = _get_email_from_creds(creds)
                
                # Se ainda assim não identificou, tenta extrair do nome do ficheiro (fallback de emergência)
                if email_detectado == 'E-mail não identificado':
                    # token_email_gmail_com.pickle -> email@gmail.com
                    partes = ficheiro.replace('token_', '').replace('.pickle', '').split('_')
                    if len(partes) >= 3:
                        email_detectado = f"{partes[0]}@{partes[1]}.{partes[2]}"

                if email_detectado and '@' in email_detectado:
                    contas.append({
                        'email': email_detectado, 
                        'ativa': email_detectado == ativa, 
                        'ficheiro': ficheiro
                    })
                else:
                    # Se o ficheiro existe mas não tem e-mail válido, removemos para limpar a 'confusão'
                    os.remove(caminho)
                    print(f"[AUTH] Removido token inválido/corrompido: {ficheiro}")

            except Exception as e:
                # Se não consegue sequer abrir o pickle, remove o ficheiro lixo
                try: os.remove(caminho)
                except: pass
                print(f"[AUTH] Removendo ficheiro de token ilegível: {ficheiro} ({e})")

    return contas


def autenticar(email=None):
    """
    Gerencia a autenticação OAuth 2.0 com suporte a múltiplas contas.
    - Se email for fornecido: usa/cria token para essa conta.
    - Se não: usa a conta activa no config.json.
    - Se não houver nenhuma: abre o fluxo de login.
    """
    if email is None:
        email = _get_active_account()

    token_file = _token_path(email) if email else os.path.join(TOKENS_DIR, 'token_default.pickle')

    # Compatibilidade retroativa: token.pickle na raiz
    if not os.path.exists(token_file) and os.path.exists('token.pickle') and not email:
        token_file = 'token.pickle'

    creds = None
    if os.path.exists(token_file):
        with open(token_file, 'rb') as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print(f"[AUTH] Token renovado para: {email or 'conta padrão'}")
            except Exception as e:
                print(f"[AUTH] Falha ao renovar token: {e}. A fazer novo login...")
                creds = None

        if not creds:
            client_secret = _get_client_secret_path()
            if not os.path.exists(client_secret):
                raise FileNotFoundError(
                    f"'{client_secret}' não encontrado. Faça download em console.cloud.google.com"
                )
            print("[AUTH] A abrir janela de login Google no navegador...")
            flow = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
            creds = flow.run_local_server(port=0)

        # Descobre o e-mail real da conta autenticada
        email_real = _get_email_from_creds(creds)
        token_file = _token_path(email_real)

        with open(token_file, 'wb') as f:
            pickle.dump(creds, f)

        # Define como conta activa se for a primeira
        if not _get_active_account():
            _set_active_account(email_real)

        print(f"[AUTH] Autenticado como: {email_real}")

    return creds


def adicionar_conta():
    """
    Força o fluxo de login para adicionar uma NOVA conta.
    Retorna o e-mail da conta adicionada.
    """
    client_secret = _get_client_secret_path()
    if not os.path.exists(client_secret):
        raise FileNotFoundError(f"'{client_secret}' não encontrado.")

    print("[AUTH] A abrir janela de login Google para nova conta...")
    flow = InstalledAppFlow.from_client_secrets_file(client_secret, SCOPES)
    creds = flow.run_local_server(port=0)

    email = _get_email_from_creds(creds)
    with open(_token_path(email), 'wb') as f:
        pickle.dump(creds, f)

    print(f"[AUTH] Nova conta adicionada: {email}")
    return email


def trocar_conta_activa(email):
    """Define qual conta é usada para os uploads."""
    token = _token_path(email)
    if not os.path.exists(token):
        raise ValueError(f"Conta '{email}' não encontrada. Faça login primeiro.")
    _set_active_account(email)
    print(f"[AUTH] Conta activa: {email}")


def remover_conta(email):
    """Remove os tokens de uma conta (desconecta)."""
    token = _token_path(email)
    if os.path.exists(token):
        os.remove(token)
        print(f"[AUTH] Conta removida: {email}")

    # Se era a conta activa, limpa a configuração
    if _get_active_account() == email:
        _set_active_account('')


def _get_client_secret_path():
    """Lê o caminho do client_secret.json a partir do config.json."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        return cfg.get('api_keys', {}).get('client_secret', 'client_secret.json') or 'client_secret.json'
    return 'client_secret.json'


def get_youtube_service(email=None):
    """Retorna o serviço YouTube para a conta activa (ou a especificada)."""
    creds = autenticar(email)
    return build('youtube', 'v3', credentials=creds)


if __name__ == "__main__":
    print("Testando autenticação multi-conta...")
    email = adicionar_conta()
    print(f"Conta adicionada: {email}")
    contas = listar_contas()
    print(f"Contas disponíveis: {contas}")
