# 🚀 AutoTube Publisher

O **AutoTube Publisher** é uma solução profissional de automação para criadores de conteúdo no YouTube. Ele gerencia todo o pipeline de produção: desde a geração de roteiros e artes com IA até a renderização de vídeos e o upload automatizado para múltiplos canais.

## 🌟 Principais Funcionalidades

- **🧠 Inteligência Artificial Multimodal**: Geração automática de metadados (títulos, descrições e tags) otimizados para SEO.
- **🎨 Art Engine Autônomo**: Criação de capas (thumbnails) de alta qualidade usando DALL-E 3.
- **🎬 Renderização Dinâmica**: Motor de vídeo baseado em FFmpeg para processamento rápido e eficiente.
- **📅 Agendamento e Batch Processing**: Gerenciamento de filas de postagem e processamento em lote.
- **🔐 Multi-Account Management**: Suporte para autenticação OAuth e gestão de múltiplos canais de forma segura.
- **📊 Dashboard Web**: Interface amigável para monitorar o status da produção em tempo real.

## 🛠️ Tecnologias Utilizadas

- **Linguagem**: Python 3.x
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Backend**: Flask / Python Web Server
- **Processamento de Mídia**: FFmpeg
- **IA**: OpenAI API (GPT & DALL-E)
- **Banco de Dados**: SQLite3
- **Autenticação**: Google OAuth2

## 📋 Pré-requisitos

Antes de começar, você precisará ter instalado:
- [Python 3.10+](https://www.python.org/)
- [FFmpeg](https://ffmpeg.org/)
- Uma conta no [Google Cloud Console](https://console.cloud.google.com/) com a YouTube API ativada.

## 🚀 Como Executar

1. **Clone o repositório**:
   ```bash
   git clone https://github.com/SEU_USUARIO/AutoTube_Publisher.git
   cd AutoTube_Publisher
   ```

2. **Crie um ambiente virtual e instale as dependências**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # No Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure suas chaves**:
   - Adicione seu `client_secret.json` na raiz do projeto.
   - Configure o `config.json` com suas preferências de API.

4. **Inicie o sistema**:
   ```bash
   python main.py
   ```

---

## 🔒 Segurança

Este projeto utiliza um arquivo `.gitignore` para garantir que informações sensíveis como chaves de API (`config.json`, `client_secret.json`) e tokens de acesso nunca sejam enviados para o repositório público.

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---
Desenvolvido com ❤️ por [Kiasseca Fernando](https://github.com/kiassecafernando00-a11y)
