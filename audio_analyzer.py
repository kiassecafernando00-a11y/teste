import librosa
import numpy as np
import os

def analisar_vibe_musical(caminho_audio):
    """
    Analisa o arquivo MP3 para detectar BPM e nível de energia.
    """
    if not os.path.exists(caminho_audio):
        print(f"❌ Erro: Arquivo não encontrado para análise: {caminho_audio}")
        return None

    print(f"🎵 Analisando características sonoras de: {os.path.basename(caminho_audio)}")
    
    try:
        # Carrega apenas os primeiros 45 segundos para análise rápida (POP 5.1)
        # y = wave form, sr = sample rate
        y, sr = librosa.load(caminho_audio, duration=45, sr=11025)
        
        # 1. Detectar BPM
        # beat_track retorna o tempo (BPM) e os frames dos beats
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        
        # Garantir que tempo é um float simples (pode vir como array em algumas versões)
        if isinstance(tempo, np.ndarray):
            bpm = float(tempo[0])
        else:
            bpm = float(tempo)
        
        # 2. Calcular 'Energia' (RMS - Root Mean Square)
        rms = librosa.feature.rms(y=y)
        energia = float(np.mean(rms))
        
        # Classificação de Vibe e Sugestão de Cor para o Spectrum
        if bpm < 90:
            vibe = "Chill/Relaxing"
            cor_sugerida = "blue"
            cor_rgb = "0000FF" # Azul
        elif 90 <= bpm < 125:
            vibe = "Groovy/Steady"
            cor_sugerida = "purple"
            cor_rgb = "800080" # Roxo
        else:
            vibe = "High Energy/Powerful"
            cor_sugerida = "red"
            cor_rgb = "FF0000" # Vermelho
            
        return {
            "bpm": round(bpm),
            "vibe": vibe,
            "cor_nome": cor_sugerida,
            "cor_hex": cor_rgb,
            "energia": energia
        }
    except Exception as e:
        print(f"⚠️ Falha na análise técnica do áudio: {e}")
        return {
            "bpm": 0,
            "vibe": "Unknown",
            "cor_nome": "white",
            "cor_hex": "FFFFFF",
            "energia": 0
        }

if __name__ == "__main__":
    # Teste rápido
    import sys
    if len(sys.argv) > 1:
        res = analisar_vibe_musical(sys.argv[1])
        print(res)
