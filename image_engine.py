from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

def gerar_capa_personalizada(titulo_musica, caminho_base, caminho_saida):
    """
    Cria uma capa 16:9 (1920x1080) com efeito de fundo desfocado e título posicionado.
    """
    try:
        # 1. Carrega a imagem original
        img_original = Image.open(caminho_base).convert("RGBA")
        
        # 2. Cria o Canvas Full HD (1920x1080)
        canvas = Image.new("RGBA", (1920, 1080), (0, 0, 0, 255))
        
        # 3. EFEITO PREMIUM: Fundo desfocado
        # Redimensiona para preencher tudo e aplica desfoque
        bg = img_original.resize((1920, 1080), Image.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=30))
        # Escurece um pouco o fundo para o texto brilhar
        overlay = Image.new("RGBA", bg.size, (0, 0, 0, 100))
        bg = Image.alpha_composite(bg, overlay)
        canvas.paste(bg, (0, 0))
        
        # 4. Coloca a imagem principal centralizada
        # Redimensiona para altura de 1080 mantendo proporção
        aspect = img_original.width / img_original.height
        new_h = 1080
        new_w = int(new_h * aspect)
        img_mid = img_original.resize((new_w, new_h), Image.LANCZOS)
        
        offset_x = (1920 - new_w) // 2
        canvas.paste(img_mid, (offset_x, 0), img_mid if img_mid.mode == 'RGBA' else None)
        
        # 5. Adição de Texto Profissional (POP 3.1: Branding)
        draw = ImageDraw.Draw(canvas)
        
        # Tentativa de carregar fonte robusta (POP: Leitura clara)
        font_paths = ["arial.ttf", "Roboto-Bold.ttf", "Verdana.ttf"]
        fonte_titulo = None
        for p in font_paths:
            try:
                fonte_titulo = ImageFont.truetype(p, 70)
                break
            except: continue
        
        if not fonte_titulo: fonte_titulo = ImageFont.load_default()

        texto = titulo_musica.upper()
        
        # Calcula largura do texto para centralizar (POP: Centralizado)
        text_w = draw.textlength(texto, font=fonte_titulo)
        
        # Posição: Superior (POP 3.3: Para não obstruir o Spectrum na base)
        pos_x = (1920 - text_w) // 2
        pos_y = 120
        
        # Sombra Robusta (Contraste Máximo)
        for dx, dy in [(-2,-2), (2,-2), (-2,2), (2,2), (3,3)]:
            draw.text((pos_x+dx, pos_y+dy), texto, font=fonte_titulo, fill="black")
            
        # Texto principal (Branco Puro para contraste)
        draw.text((pos_x, pos_y), texto, font=fonte_titulo, fill="#ffffff")

        # 6. Salva o resultado final
        canvas.convert("RGB").save(caminho_saida, "JPEG", quality=95)
        print(f"Capa Premium gerada: {caminho_saida}")
        return True
        
    except Exception as e:
        print(f"Erro ao gerar capa premium: {e}")
        return False

if __name__ == "__main__":
    # Teste rápido se rodar o arquivo diretamente
    pass
