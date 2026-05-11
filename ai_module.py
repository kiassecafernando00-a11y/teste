import warnings
# Suprime avisos de depreciação ANTES de importar o pacote (POP 4.1)
warnings.filterwarnings("ignore", category=FutureWarning)

import requests
import json
import os
import google.generativeai as genai
import time

# Caminho absoluto para evitar problemas de diretório de trabalho no Windows
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')


def _carregar_gemini_key():
    """
    Lê a chave Gemini EXCLUSIVAMENTE do config.json usando caminho absoluto.
    """
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            key = cfg.get('api_keys', {}).get('gemini', '')
            if key: return key
    except Exception as e:
        print(f"[IA] Erro ao ler config.json: {e}")
    
    # Tenta ler do diretório atual se o absoluto falhar por algum motivo
    try:
        if os.path.exists('config.json'):
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f).get('api_keys', {}).get('gemini', '')
    except: pass
    
    return ''


from monitor_module import auditor
import subprocess

def extrair_metadados_tecnicos(caminho):
    """
    Extrai informações reais do ficheiro usando ffprobe para dar contexto à IA.
    """
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', 
            '-print_format', 'json', 
            '-show_format', '-show_streams', 
            caminho
        ]
        res = subprocess.check_output(cmd).decode('utf-8')
        dados = json.loads(res)
        
        formato = dados.get('format', {})
        tags = formato.get('tags', {})
        stream_a = next((s for s in dados.get('streams', []) if s['codec_type'] == 'audio'), {})
        stream_v = next((s for s in dados.get('streams', []) if s['codec_type'] == 'video'), {})
        
        info = {
            "duracao": f"{float(formato.get('duration', 0))/60:.2f} min",
            "bitrate": f"{int(formato.get('bit_rate', 0))/1000:.0f} kbps",
            "tags_arquivo": tags,
            "canais": stream_a.get('channels'),
            "resolucao": f"{stream_v.get('width')}x{stream_v.get('height')}" if stream_v else "N/A",
            "codec": stream_a.get('codec_name') or stream_v.get('codec_name')
        }
        return info
    except Exception as e:
        print(f"[IA] Erro na análise técnica: {e}")
        return {}

def gerar_metadados_musica(caminho_arquivo, vibe_info=None):
    """
    Usa Gemini IA para criar Título, Descrição e Tags baseadas na análise real do arquivo.
    """
    nome_arquivo = os.path.basename(caminho_arquivo)
    key = _carregar_gemini_key()

    if not key:
        msg = "Gemini API Key não configurada."
        print(f"[IA] AVISO: {msg}")
        auditor.registrar_violacao('IA_SEO', nome_arquivo, msg, "ALTA")
        return _metadados_fallback(nome_arquivo)

    # Carrega preferências de YouTube (prefixo, sufixo, tags padrão)
    cfg_yt = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg_yt = json.load(f).get('youtube', {})

    prefixo  = cfg_yt.get('title_prefix', '')
    sufixo   = cfg_yt.get('title_suffix', '')
    tags_pad = cfg_yt.get('default_tags', 'music, audio, youtube')
    desc_pad = cfg_yt.get('default_description', '')

    try:
        # 1. DESCOBERTA AUTOMÁTICA: Lista modelos disponíveis para esta chave
        url_list = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        res_list = requests.get(url_list, timeout=30)
        
        modelo_escolhido = "gemini-1.5-flash" # Fallback padrão
        
        if res_list.status_code == 200:
            modelos_disponiveis = [m['name'].split('/')[-1] for m in res_list.json().get('models', []) 
                                  if 'generateContent' in m.get('supportedGenerationMethods', [])]
            
            # Prioridade: 1.5-flash -> 1.5-pro -> primeiro da lista
            if 'gemini-1.5-flash' in modelos_disponiveis:
                modelo_escolhido = 'gemini-1.5-flash'
            elif 'gemini-1.5-pro' in modelos_disponiveis:
                modelo_escolhido = 'gemini-1.5-pro'
            elif modelos_disponiveis:
                modelo_escolhido = modelos_disponiveis[0]

        # Saneamento de Nome (POP 1.3)
        termos_limpeza = [
            '_master', '_v1', '_v2', '_final', '_audio', 
            '(Official Video)', '[HQ]', '(HD)', '(4K)', 
            '.mp3', '.wav', '.mp4', '.mov'
        ]
        nome_limpo = nome_arquivo
        for termo in termos_limpeza:
            nome_limpo = nome_limpo.replace(termo, '').replace(termo.upper(), '')
        
        nome_limpo = nome_limpo.replace('_', ' ').replace('-', ' ').strip()

        # 1. ANÁLISE PROFUNDA (Deep Analysis)
        analise = extrair_metadados_tecnicos(caminho_arquivo)
        tags_raw = json.dumps(analise.get('tags_arquivo', {}), ensure_ascii=False)

        # Prompt Profissional (Diretriz Sonic AI)
        prompt = f"""
        Você é o Diretor de Operações do SONIC PUBLISHER AI. Sua missão é criar metadados musicais de elite.
        
        [CONTEXTO TÉCNICO]:
        - Título Original: {nome_limpo}
        - Vibe: {vibe_info.get('vibe') if vibe_info else 'Desconhecida'}
        - BPM: {vibe_info.get('bpm') if vibe_info else 'N/A'}
        - Duração: {analise.get('duracao')}
        - Metadados ID3: {tags_raw}

        TAREFA:
        1. Gere um Título envolvente (use o original como base).
        2. Escreva uma Descrição Humana: Imagine que você é um curador de rádio falando com um amigo. 
           - Remova termos técnicos como 'processamento', 'upload', 'renderização'.
           - Descreva a atmosfera sonora e a emoção da música.
           - Inclua a Letra Completa (se for áudio).
           - Ficha Técnica: Artista: Autor Anônimo | Produção: Sonic AI.
        3. 15 Tags de alto impacto (SEO).

        SAÍDA: Retorne APENAS um objeto JSON válido com as chaves "titulo", "descricao", "tags".
        """

        # 2. CHAMADA IA (Multimodal ou Apenas Texto)
        genai.configure(api_key=key)
        model = genai.GenerativeModel(modelo_escolhido)
        
        multimodal = cfg_yt.get('ai_multimodal_enabled', False) # Vem do config pai (processing)
        # Tenta pegar da raiz do config se não estiver em youtube
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                multimodal = json.load(f).get('processing', {}).get('ai_multimodal_enabled', False)

        if multimodal:
            print(f"[IA] 'Ouvindo' ficheiro para transcrição: {nome_arquivo}...")
            try:
                # Carrega o ficheiro para o Gemini
                media_file = genai.upload_file(path=caminho_arquivo)
                
                # Aguarda processamento do ficheiro (necessário para alguns formatos)
                timeout = 60
                while media_file.state.name == "PROCESSING" and timeout > 0:
                    time.sleep(2)
                    timeout -= 2
                    media_file = genai.get_file(media_file.name)
                
                if media_file.state.name != "ACTIVE":
                    raise Exception("Falha ao processar ficheiro no Gemini.")

                # Prompt Final com Transcrição
                response = model.generate_content([
                    prompt,
                    media_file
                ])
                
                texto = response.text
                dados = json.loads(texto.replace('```json', '').replace('```', '').strip())
                
                # Limpeza: Remove o ficheiro do Gemini após uso
                genai.delete_file(media_file.name)
            except Exception as e:
                print(f"[IA] Erro na análise multimodal: {e}. Usando modo texto apenas.")
                # Fallback para modo texto se o upload falhar
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo_escolhido}:generateContent?key={key}"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=60)
                if res.status_code == 200:
                    texto = res.json()['candidates'][0]['content']['parts'][0]['text']
                    dados = json.loads(texto.replace('```json', '').replace('```', '').strip())
                else:
                    return _metadados_fallback(nome_arquivo)
        else:
            print(f"[IA] Processando via metadados (Modo Rápido)...")
            # Fallback para modo texto se o upload estiver desativado ou falhar
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo_escolhido}:generateContent?key={key}"
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=60)
            if res.status_code == 200:
                texto = res.json()['candidates'][0]['content']['parts'][0]['text']
                dados = json.loads(texto.replace('```json', '').replace('```', '').strip())
            else:
                return _metadados_fallback(nome_arquivo)

        print(f"[IA] Modelo detectado e usado: {modelo_escolhido}")
        
        # --- CAMADA DE AUDITORIA CRÍTICA (SONIC AI) ---
        dados_auditados = auditoria_critica_sonic("Metadados Musicais", json.dumps(dados, ensure_ascii=False))
        if dados_auditados:
            try:
                return json.loads(dados_auditados)
            except:
                return dados
        return dados

    except json.JSONDecodeError as e:
        print(f"[IA] Erro ao parsear JSON da resposta: {e}")
        return _metadados_fallback(nome_arquivo)
    except Exception as e:
        erro_msg = str(e)
        if "429" in erro_msg or "RESOURCE_EXHAUSTED" in erro_msg:
            print("[IA] LIMITE EXCEDIDO: A sua quota gratuita do Gemini atingiu o limite. Aguarde 1 a 2 minutos e tente novamente.")
        else:
            print(f"[IA] Erro ao gerar metadados: {erro_msg}")
        return _metadados_fallback(nome_arquivo)

def auditoria_critica_sonic(contexto, conteudo):
    """
    O Cérebro da IA revisa o próprio trabalho antes de liberar.
    Garante tom humano, sem jargões e alta qualidade estética.
    """
    key = _carregar_gemini_key()
    if not key: return None

    print(f"[AUDITORIA] Validando {contexto} contra as Leis de Ouro...")
    
    prompt_auditoria = f"""
    Você é o Auditor Chefe do SONIC PUBLISHER AI. Sua missão é garantir a perfeição absoluta.
    
    CONTEÚDO PARA REVISÃO ({contexto}):
    '{conteudo}'
    
    LEIS DE OURO:
    1. TOM HUMANO: O texto parece escrito por uma pessoa real? Se houver palavras como 'processamento', 'algoritmo', 'upload', 'IA', reescreva.
    2. EMOÇÃO: O texto evoca uma sensação ou descreve a atmosfera musical?
    3. SEM TEXTO EM IMAGENS: Se o contexto for 'Prompt Visual', garanta que o prompt proíba explicitamente textos, marcas d'água e deformações.
    4. FOCO NO USUÁRIO: A descrição ajuda o ouvinte a se conectar com a obra?

    TAREFA:
    Se o conteúdo estiver perfeito, retorne exatamente o conteúdo original.
    Se violar as leis, reescreva-o para ser perfeito e retorne apenas a versão corrigida (no mesmo formato original, ex: JSON).
    """

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": prompt_auditoria}]}]}
        res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=40)
        
        if res.status_code == 200:
            texto = res.json()['candidates'][0]['content']['parts'][0]['text']
            # Limpa possíveis blocos de código Markdown
            texto_limpo = texto.replace('```json', '').replace('```', '').strip()
            return texto_limpo
    except Exception as e:
        print(f"[AUDITORIA ERRO] {e}")
    
    return None

def _metadados_fallback(nome_arquivo):
    """Metadados genéricos usados quando a IA não está disponível."""
    nome_limpo = os.path.splitext(nome_arquivo)[0].replace('_', ' ').replace('-', ' ').strip()

    # Tenta usar as tags e descrição padrão mesmo sem IA
    cfg_yt = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            cfg_yt = json.load(f).get('youtube', {})

    return {
        "titulo":    nome_limpo,
        "descricao": cfg_yt.get('default_description', f"Música: {nome_limpo}\nPublicada automaticamente pelo AutoTube Publisher."),
        "tags":      cfg_yt.get('default_tags', 'music, audio, youtube, automation'),
    }


if __name__ == "__main__":
    meta = gerar_metadados_musica("Vibe_Eletronica_Deep_House_2024.mp3")
    print(meta)
