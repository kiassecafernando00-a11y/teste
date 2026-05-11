import os
import sys

def criar_tarefa_windows(caminho_script, hora="02:00"):
    """
    Cria uma tarefa no Windows que executa o programa todos os dias na hora marcada.
    """
    nome_tarefa = "AutoTubePublisher_Job"
    # Garante o caminho absoluto
    caminho_absoluto = os.path.abspath(caminho_script)
    # Comando schtasks para criar a tarefa diária (com mudança de diretório e tratamento de espaços)
    diretorio = os.path.dirname(caminho_absoluto)
    # No Windows/schtasks, aspas internas devem ser escapadas com \ e o comando envolto em "
    comando_exec = f'cmd /c \"cd /d \\\"{diretorio}\\\" && python \\\"{caminho_absoluto}\\\"\"'
    comando = f'schtasks /create /tn \"{nome_tarefa}\" /tr \"{comando_exec}\" /sc daily /st {hora} /f'
    
    print(f"Executando comando: {comando}")
    
    try:
        resultado = os.system(comando)
        if resultado == 0:
            print(f"\n[OK] Tarefa agendada com sucesso para às {hora}!")
            print(f"O Windows executará o script '{caminho_absoluto}' automaticamente.")
        else:
            print(f"\n[ERRO] Falha ao agendar tarefa. Código de erro: {resultado}")
    except Exception as e:
        print(f"Erro ao agendar: {e}")

if __name__ == "__main__":
    # Pega o caminho do main.py que está na mesma pasta
    diretorio_atual = os.path.dirname(os.path.abspath(__file__))
    caminho_main = os.path.join(diretorio_atual, "main.py")
    
    print("--- Instalador de Agendamento Profissional (Windows) ---")
    hora_input = input("Que horas o robô deve rodar todos os dias? (Ex: 03:00): ") or "03:00"
    
    criar_tarefa_windows(caminho_main, hora_input)
