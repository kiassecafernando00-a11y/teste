import io
import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from auth_module import autenticar

def buscar_musicas_no_drive():
    """
    Lista os ficheiros disponíveis no Google Drive com base nas configurações.
    Suporta busca em pasta específica e consultas personalizadas.
    """
    from main import carregar_config
    cfg = carregar_config()
    drive_cfg = cfg.get('paths', {}).get('drive', {})
    
    folder_id = drive_cfg.get('folder_id', '').strip()
    custom_query = drive_cfg.get('query', '').strip()

    creds = autenticar()
    service = build('drive', 'v3', credentials=creds)
    
    # Constrói a query
    if custom_query:
        query = custom_query
    else:
        # Busca genérica para áudio e vídeo (Protocolo Multi-formato)
        query = "(mimeType contains 'audio/' or mimeType contains 'video/') and trashed = false"
        if folder_id:
            query = f"'{folder_id}' in parents and {query}"
    
    print(f"[DRIVE] Query utilizada: {query}")
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    
    return items

def baixar_arquivo_drive(file_id, file_name, pasta_destino="temp_files"):
    """
    Faz o download do arquivo do Drive para a pasta local temporária.
    """
    creds = autenticar()
    service = build('drive', 'v3', credentials=creds)
    
    request = service.files().get_media(fileId=file_id)
    caminho_local = os.path.join(pasta_destino, file_name)
    
    # Garante que a pasta temporária existe
    os.makedirs(pasta_destino, exist_ok=True)
    
    fh = io.FileIO(caminho_local, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    
    done = False
    print(f"Baixando {file_name}...")
    while done is False:
        status, done = downloader.next_chunk()
        if status:
            print(f"Progresso: {int(status.progress() * 100)}%")
    
    return caminho_local

if __name__ == "__main__":
    # Teste de listagem
    print("Buscando arquivos no Drive...")
    arquivos = buscar_musicas_no_drive()
    if not arquivos:
        print("Nenhum arquivo MP3 encontrado no Drive.")
    else:
        for f in arquivos:
            print(f"Encontrado: {f['name']} (ID: {f['id']})")
