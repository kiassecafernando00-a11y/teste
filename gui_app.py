import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import sys
import os
from main import executar_automacao

# Configurações Globais de Tema
ctk.set_appearance_mode("Dark") 
ctk.set_default_color_theme("blue")

class TextHandler:
    """Captura o print do terminal e joga no console da GUI"""
    def __init__(self, widget):
        self.widget = widget

    def write(self, text):
        self.widget.insert("end", text)
        self.widget.see("end")

    def flush(self):
        pass

class AppPrincipal(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Janela
        self.title("Sonic Publisher AI - AutoTube Publisher v3.0")
        self.geometry("1100x700")

        # Layout de 2 colunas
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- BARRA LATERAL ---
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color="#121212")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo_label = ctk.CTkLabel(
            self.sidebar, 
            text="SONIC\nPUBLISHER AI", 
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 40))

        # Lista interna de arquivos selecionados
        self.arquivos_selecionados = []

        # Botões do Menu
        self.btn_upload = self.criar_botao_menu("📂 Carregar Músicas", self.carregar_musicas)
        self.btn_upload.grid(row=1, column=0, padx=20, pady=10)

        self.btn_history = self.criar_botao_menu("📊 Ver Histórico", self.ver_historico)
        self.btn_history.grid(row=2, column=0, padx=20, pady=10)

        # Agendamento
        self.frame_agendamento = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.frame_agendamento.grid(row=3, column=0, padx=20, pady=30)
        
        self.lbl_hora = ctk.CTkLabel(self.frame_agendamento, text="Agendar para:", font=("Arial", 12))
        self.lbl_hora.pack()
        self.input_hora = ctk.CTkEntry(self.frame_agendamento, placeholder_text="02:00", width=100, justify="center")
        self.input_hora.insert(0, "03:00")
        self.input_hora.pack(pady=5)

        # Botão PUBLICAR LOTE
        self.btn_start = ctk.CTkButton(
            self.sidebar, 
            text="🚀 PUBLICAR LOTE", 
            fg_color="#27ae60", 
            hover_color="#1e8449",
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_process_thread
        )
        self.btn_start.grid(row=5, column=0, padx=20, pady=(150, 20), sticky="s")

        # --- ÁREA PRINCIPAL ---
        self.main_content = ctk.CTkFrame(self, corner_radius=15, fg_color="#1e1e1e")
        self.main_content.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_content.grid_columnconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(1, weight=1)

        self.header_label = ctk.CTkLabel(
            self.main_content, 
            text="Fila de Processamento Inteligente", 
            font=ctk.CTkFont(size=18, weight="bold")
        )
        self.header_label.grid(row=0, column=0, padx=30, pady=(20, 10), sticky="w")

        # Console de Logs
        self.musica_textbox = ctk.CTkTextbox(
            self.main_content, 
            fg_color="#000000", 
            border_color="#333333",
            border_width=1,
            corner_radius=10,
            text_color="#2ecc71", # Verde Matrix
            font=("Consolas", 12)
        )
        self.musica_textbox.grid(row=1, column=0, padx=30, pady=10, sticky="nsew")
        
        # Redirecionamento do terminal para a GUI
        sys.stdout = TextHandler(self.musica_textbox)

        # --- FOOTER ---
        self.footer = ctk.CTkFrame(self.main_content, fg_color="transparent")
        self.footer.grid(row=2, column=0, padx=30, pady=20, sticky="ew")
        
        self.status_icon = ctk.CTkLabel(self.footer, text="●", text_color="#e74c3c", font=("Arial", 16))
        self.status_icon.grid(row=0, column=0, padx=(0, 5))
        
        self.status_text = ctk.CTkLabel(self.footer, text="Sistema Offline", font=("Arial", 13))
        self.status_text.grid(row=0, column=1, sticky="w")

        self.progress_bar = ctk.CTkProgressBar(self.footer, width=400, height=12, progress_color="#27ae60")
        self.progress_bar.grid(row=0, column=2, padx=20, sticky="e")
        self.progress_bar.set(0)

    def criar_botao_menu(self, texto, comando):
        return ctk.CTkButton(
            self.sidebar, 
            text=texto, 
            command=comando,
            anchor="w",
            fg_color="transparent",
            text_color="#ffffff",
            hover_color="#222222",
            height=40
        )

    def carregar_musicas(self):
        arquivos = filedialog.askopenfilenames(filetypes=[("Áudio", "*.mp3")])
        if arquivos:
            self.arquivos_selecionados = list(arquivos) # Salva para o processamento
            self.musica_textbox.delete("0.0", "end")
            print(f"--- {len(arquivos)} Músicas Carregadas Localmente ---")
            for i, f in enumerate(arquivos, 1):
                print(f"[{i}] {os.path.basename(f)}")
            self.status_icon.configure(text_color="#f1c40f")
            self.status_text.configure(text="Aguardando Início")
            
            # Automação Total: Inicia o processo imediatamente após carregar
            print("\n[AUTO-START] Arquivos detectados. Iniciando produção agora...")
            self.start_process_thread()

    def start_process_thread(self):
        print("\n>>> BOTÃO 'PUBLICAR LOTE' CLICADO")
        if not self.arquivos_selecionados:
            print("INFO: Nenhuma música local selecionada. O robô buscará arquivos no Google Drive.")
        else:
            print(f"INFO: Preparando lote manual com {len(self.arquivos_selecionados)} arquivo(s).")
            
        self.btn_start.configure(state="disabled")
        self.status_icon.configure(text_color="#2ecc71")
        self.status_text.configure(text="Processando em Lote...")
        self.progress_bar.start()
        
        thread = threading.Thread(target=self.run_automation)
        thread.daemon = True
        thread.start()

    def run_automation(self):
        try:
            # Passa a lista manual para o motor principal
            executar_automacao(lista_manual=self.arquivos_selecionados)
            self.status_text.configure(text="Concluído com Sucesso")
            messagebox.showinfo("Sonic Publisher AI", "Produção Finalizada!")
        except Exception as e:
            print(f"ERRO: {e}")
            messagebox.showerror("Erro", f"Falha: {e}")
        finally:
            self.progress_bar.stop()
            self.progress_bar.set(1.0)
            self.btn_start.configure(state="normal")

    def ver_historico(self):
        try:
            import sqlite3
            if not os.path.exists('automacao.db'):
                messagebox.showinfo("Aviso", "Nenhum histórico encontrado ainda.")
                return
                
            conn = sqlite3.connect('automacao.db')
            cursor = conn.cursor()
            cursor.execute("SELECT nome_arquivo, data_publicacao FROM postagens ORDER BY data_publicacao DESC LIMIT 15")
            logs = cursor.fetchall()
            
            hist_win = ctk.CTkToplevel(self)
            hist_win.title("Histórico de Publicações")
            hist_win.geometry("600x450")
            hist_win.attributes("-topmost", True)
            
            label_h = ctk.CTkLabel(hist_win, text="Últimas 15 Publicações", font=("Arial", 16, "bold"))
            label_h.pack(pady=10)
            
            txt = ctk.CTkTextbox(hist_win, width=580, height=380, font=("Consolas", 11))
            txt.pack(padx=10, pady=10)
            
            if not logs:
                txt.insert("0.0", "Nenhuma postagem registrada no banco de dados.")
            else:
                for log in logs:
                    txt.insert("end", f"📅 {log[1]} | 🎵 {log[0]}\n")
            conn.close()
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível ler o histórico: {e}")

if __name__ == "__main__":
    app = AppPrincipal()
    app.mainloop()
