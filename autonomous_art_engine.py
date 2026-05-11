import openai
import requests
from PIL import Image
import os
import io
import json

# --- CONFIGURAÇÕES DE AMBIENTE ---
# Carrega a chave do config.json para manter o sistema integrado
def _get_api_key():
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f).get('api_keys', {}).get('openai', '')
    except:
        pass
    return os.getenv("OPENAI_API_KEY", "")

class AutonomousArtEngine:
    def __init__(self, temp_path="temp_files"):
        self.temp_path = temp_path
        # Garante que a pasta temporária existe
        if not os.path.exists(temp_path):
            os.makedirs(temp_path)
        
        # Configura a chave na inicialização
        self.api_key = _get_api_key()
        openai.api_key = self.api_key

    def _criar_prompt_visual_puro(self, titulo_musica):
        """
        Usa GPT para traduzir o título da música em um prompt visual rico e artístico,
        estritamente instruído a NÃO incluir texto.
        """
        if not self.api_key:
            print("⚠️ OpenAI API Key não configurada. Usando prompt genérico.")
            return f"An abstract digital art piece inspired by the concept of '{titulo_musica}', cinematic lighting, no text."

        print(f"🧠 Derivando conceito artístico puro para: {titulo_musica}")
        
        prompt_sistema = (
            "Você é um Diretor de Arte de elite, especializado em capas de álbuns de música de alto nível "
            "e tendências visuais de plataformas como Behance e ArtStation. "
            "Sua tarefa é ler o título da música e criar um prompt em INGLÊS para o DALL-E 3 que gere "
            "uma imagem de ALTO ENGAJAMENTO, visualmente impactante e esteticamente premiada. "
            "A arte deve ser profunda, rica em detalhes e capturar a alma da música. "
            "ESTILOS RECOMENDADOS: Cyberpunk surrealista, fotorrealismo cinematográfico, "
            "abstração orgânica com luz volumétrica, ou minimalismo elegante e futurista. "
            "REGRAS ESTRITAS: A imagem deve ser PURE ART. Não deve conter NENHUM texto, NENHUMA letra, "
            "NENHUMA marca d'água, NENHUM logotipo e NENHUM caractere sobreposto. "
            "A composição deve ser balanceada, usando cores vibrantes e harmônicas para atrair cliques."
        )
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": f"Título da música: {titulo_musica}"}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            if "insufficient_quota" in str(e).lower():
                print("❌ OpenAI: Quota insuficiente ou créditos expirados.")
            else:
                print(f"❌ Erro ao gerar prompt com GPT: {e}")
            return f"An abstract digital art piece inspired by the concept of '{titulo_musica}', cinematic lighting, no text."

    def _gerar_imagem_dalle(self, prompt_visual, id_unique):
        """
        Chama a API do DALL-E 3 para gerar a imagem baseada no prompt.
        """
        if not self.api_key:
            return None

        print(f"🎨 IA gerando arte exclusiva (pode levar até 30 segundos)...")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt_visual,
                n=1,
                size="1024x1024",
                quality="hd",
                response_format="url"
            )
            image_url = response.data[0].url
            
            img_data = requests.get(image_url).content
            caminho_local_base = os.path.join(self.temp_path, f"base_art_{id_unique}.png")
            
            with open(caminho_local_base, 'wb') as f:
                f.write(img_data)
                
            return caminho_local_base
        except Exception as e:
            if "insufficient_quota" in str(e).lower() or "billing_hard_limit_reached" in str(e).lower():
                print("❌ OpenAI DALL-E: Sem créditos ou limite de faturamento atingido.")
            else:
                print(f"❌ Erro na geração/download da imagem com DALL-E: {e}")
            return None

    def _processar_para_proporcao_video(self, caminho_base, id_unique):
        """
        Crop inteligente para 16:9 (1920x1080).
        """
        print(f"✂️ Ajustando arte para formato de vídeo (16:9)...")
        try:
            img = Image.open(caminho_base)
            
            # Dimensões alvo
            target_w = 1920
            target_h = 1080
            
            # Redimensionar a largura para 1920, altura proporcional
            # Se a imagem é 1024x1024, redimensionando W para 1920, H vira 1920.
            img_resized = img.resize((target_w, target_w), Image.Resampling.LANCZOS)
            
            # Crop central
            left = 0
            top = (target_w - target_h) / 2
            right = target_w
            bottom = top + target_h
            
            img_final = img_resized.crop((left, top, right, bottom))
            
            caminho_final = os.path.join(self.temp_path, f"capa_pura_{id_unique}.jpg")
            img_final.convert("RGB").save(caminho_final, "JPEG", quality=98)
            
            return caminho_final
            
        except Exception as e:
            print(f"❌ Erro ao processar proporção da imagem: {e}")
            return None

    def criar_capa_autonoma_pura(self, titulo_musica, id_unique):
        """
        Fluxo completo: Prompt -> Geração DALL-E -> Crop 16:9.
        """
        if not self.api_key:
            print("❌ OpenAI API Key ausente no config.json. Operação cancelada.")
            return None

        prompt_original = self._criar_prompt_visual_puro(titulo_musica)
        
        # Auditoria Sonic AI (Camada de Decisão Autônoma)
        from ai_module import auditoria_critica_sonic
        prompt = auditoria_critica_sonic("Prompt Visual (DALL-E)", prompt_original) or prompt_original
        
        caminho_base = self._gerar_imagem_dalle(prompt, id_unique)
        
        if caminho_base:
            caminho_final = self._processar_para_proporcao_video(caminho_base, id_unique)
            if caminho_base and os.path.exists(caminho_base):
                try: os.remove(caminho_base)
                except: pass
            return caminho_final
        
        return None

# Instância global para integração
art_engine = AutonomousArtEngine()
