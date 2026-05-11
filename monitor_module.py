import datetime
import os

class MonitorErros:
    def __init__(self, log_path="relatorio_final.txt"):
        self.log_path = log_path
        self._preparar_arquivo()

    def _preparar_arquivo(self):
        """Cria o cabeçalho do relatório se ele não existir."""
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w", encoding="utf-8") as f:
                f.write(f"=== RELATÓRIO DE AUDITORIA SONIC PUBLISHER AI ===\n")
                f.write(f"Iniciado em: {datetime.datetime.now()}\n")
                f.write("-" * 50 + "\n")

    def registrar_violacao(self, fase, arquivo, erro, criticidade="ALTA"):
        """
        Registra uma falha técnica ou de regra de negócio.
        Fases: 'VALIDAÇÃO', 'IA_SEO', 'RENDER', 'UPLOAD'
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mensagem = (
            f"[{timestamp}] | FASE: {fase} | CRITICIDADE: {criticidade}\n"
            f"ARQUIVO: {arquivo}\n"
            f"DETALHE DO ERRO: {erro}\n"
            f"{'-' * 50}\n"
        )
        
        # Também envia para o console web se possível
        try:
            from app_web import log_to_web
            log_to_web(f"⚠️ [AUDITORIA] {fase}: {erro}")
        except:
            print(f"⚠️ VIOLAÇÃO DE PROTOCOLO DETECTADA: {fase} - {arquivo}")
        
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(mensagem)

    def gerar_resumo_executivo(self):
        """Retorna uma string pronta para ser enviada por e-mail ou exibida na GUI."""
        if not os.path.exists(self.log_path):
            return "Nenhum erro registrado até o momento."
        
        with open(self.log_path, "r", encoding="utf-8") as f:
            return f.read()

# Instância global para uso em todo o sistema
auditor = MonitorErros()
