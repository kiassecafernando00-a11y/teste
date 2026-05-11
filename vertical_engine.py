import ffmpeg
import os

def criar_youtube_short(caminho_mp3, caminho_imagem, caminho_saida, duracao=60, start_time=0):
    """
    Gera um vídeo vertical (1080x1920) de 60 segundos com efeito Ken Burns 
    (zoom suave) e ondas sonoras.
    """
    print(f"🎬 Iniciando criação de Short Vertical: {os.path.basename(caminho_saida)}")
    
    try:
        # 1. Inputs
        # Pega o trecho solicitado (default 60s)
        audio = ffmpeg.input(caminho_mp3, ss=start_time, t=duracao)
        
        # 2. Processamento da Imagem (Efeito de Zoom Suave / Ken Burns)
        # Redimensiona para preencher a tela vertical e aplica zoom lento
        # Aumentamos a escala para 3414x1920 para dar margem ao zoom sem perder qualidade excessiva
        video = (
            ffmpeg.input(caminho_imagem, loop=1, framerate=30)
            .filter('scale', 3414, 1920) 
            .filter('zoompan', z='zoom+0.001', d=duracao*30, s='1080x1920', x='iw/2-(iw/zoom/2)', y='ih/2-(ih/zoom/2)')
            .filter('format', 'yuv420p')
        )

        # 3. Onda Sonora Vertical (Centralizada)
        spectrum = (
            audio
            .filter('showwaves', s='1080x400', mode='cline', colors='white@0.6', r=15)
        )

        # 4. Sobreposição
        # Coloca a onda sonora no meio da tela vertical (y=760 em uma tela de 1920)
        v_final = ffmpeg.overlay(video, spectrum, x=0, y=760)

        from video_engine import get_melhor_vcodec
        codec = get_melhor_vcodec()
        
        # 5. Saída
        # Usamos apenas o áudio do arquivo MP3 (audio.audio) para ignorar capas embutidas
        out = ffmpeg.output(
            v_final, audio.audio,
            caminho_saida,
            vcodec=codec,
            acodec='aac',
            t=duracao,
            r=30, # Força 30fps para o encoder Intel QSV não reclamar
            pix_fmt='yuv420p',
            preset='ultrafast' if codec == 'libx264' else 'veryfast'
        )
        
        # Executa com captura de erro detalhada
        try:
            out.run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
        except ffmpeg.Error as e:
            print(f"❌ Erro detalhado do FFmpeg: {e.stderr.decode()}")
            raise e

        print(f"✅ Short Vertical gerado com sucesso: {os.path.basename(caminho_saida)}")
        return True

    except Exception as e:
        print(f"❌ Erro ao gerar Short: {e}")
        return False

if __name__ == "__main__":
    # Teste rápido se executado diretamente
    import sys
    if len(sys.argv) > 3:
        criar_youtube_short(sys.argv[1], sys.argv[2], sys.argv[3])
