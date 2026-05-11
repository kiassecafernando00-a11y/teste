import time
import schedule
from main import executar_automacao

def agendar_publicacao(hora_execucao="02:00"):
    """
    Agenda a execução do programa para um horário específico (ex: madrugada)
    para não consumir banda de internet ou processamento durante o dia.
    """
    print(f"\n--- Agendador Ativado ---")
    print(f"O programa trabalhará todos os dias às {hora_execucao}")
    print("Mantenha este terminal aberto para a execução agendada.")
    
    # Agenda a tarefa
    schedule.every().day.at(hora_execucao).do(executar_automacao)

    while True:
        # Verifica se chegou o horário agendado
        schedule.run_pending()
        time.sleep(60) # Verifica a cada minuto

if __name__ == "__main__":
    # Exemplo: O programa fica em espera e roda às 3 da manhã
    # Você pode mudar para o horário que desejar
    agendar_publicacao("03:00")
