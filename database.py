import sqlite3

def iniciar_db():
    conn = sqlite3.connect('automacao.db')
    cursor = conn.cursor()
    # Cria tabela para rastrear vídeos postados
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS postagens (
            id_drive TEXT PRIMARY KEY,
            nome_arquivo TEXT,
            titulo TEXT,
            data_publicacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            youtube_id TEXT
        )
    ''')
    # Migração: adiciona coluna titulo se não existir
    try:
        cursor.execute('ALTER TABLE postagens ADD COLUMN titulo TEXT')
    except:
        pass
    conn.commit()

    conn.close()

def ja_foi_postado(id_drive):
    conn = sqlite3.connect('automacao.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM postagens WHERE id_drive = ?', (id_drive,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado is not None

def registrar_postagem(id_drive, nome_arquivo, youtube_id, titulo=None):
    conn = sqlite3.connect('automacao.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO postagens (id_drive, nome_arquivo, youtube_id, titulo) VALUES (?, ?, ?, ?)', 
                   (id_drive, nome_arquivo, youtube_id, titulo))
    conn.commit()
    conn.close()

