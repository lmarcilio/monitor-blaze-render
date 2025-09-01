# strategies/exemplo_estrategia.py

from datetime import datetime, timedelta

# --- Metadados (sem alteração) ---
ID = "soma_minutos_pos_branco"
NOME = "Alvo Pós-Branco (Soma Minutos)"
DESCRICAO = "Quando um Branco é coletado, ele identifica os 3 números anteriores e os soma como minutos para gerar 3 horários de possíveis entradas."

# --- Função Principal de Verificação (CORRIGIDA) ---
def verificar(historico, cursor):
    # Condição de gatilho
    if historico[0]['color'] != 'Branco' or len(historico) < 4:
        return None

    # Horário base
    horario_base = datetime.strptime(historico[0]['timestamp_iso'], "%Y-%m-%d %H:%M:%S")

    # Números para a soma
    primeiro_a_somar = historico[1]['roll']
    segundo_a_somar = historico[2]['roll']
    terceiro_a_somar = historico[3]['roll']

    # Cálculo dos alvos
    alvo1 = horario_base + timedelta(minutes=primeiro_a_somar)
    alvo2 = alvo1 + timedelta(minutes=segundo_a_somar)
    alvo3 = alvo2 + timedelta(minutes=terceiro_a_somar)
    
    # Mensagem de contexto
    mensagem_contexto = (
        f"Números usados na soma: {primeiro_a_somar}, {segundo_a_somar}, {terceiro_a_somar}."
    )
    
    # Lista de alvos
    lista_de_alvos = [alvo1, alvo2, alvo3]
    
    # Retorno estruturado
    return {
        "trigger_id": historico[0]['id'],
        "message": mensagem_contexto,
        "targets": lista_de_alvos
    }