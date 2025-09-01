# strategies/estrategia_soma_horario.py

from datetime import datetime, timedelta

# --- Metadados Obrigatórios ---
ID = "soma_digitos_horario" # ID único para esta nova estratégia
NOME = "Alvo Pós-Branco (Soma Dígitos do Horário)"
DESCRICAO = "Quando um Branco sai, soma todos os dígitos do seu horário (HH:MM:SS) e usa o resultado como minutos para gerar um alvo."

# --- Função Principal de Verificação (CORRIGIDA) ---
def verificar(historico, cursor):
    """
    Verifica se o último resultado foi Branco e, em caso afirmativo,
    calcula um alvo somando os dígitos do seu próprio timestamp.
    """

    # 1. Condição de gatilho: ser um Branco.
    resultado_branco = historico[0]
    if resultado_branco['color'] != 'Branco':
        return None

    # 2. Extrai o horário base do gatilho
    horario_base = datetime.strptime(resultado_branco['timestamp_iso'], "%Y-%m-%d %H:%M:%S")

    # 3. Executa a lógica principal da estratégia
    horario_formatado = horario_base.strftime("%H:%M:%S")
    digitos_str = horario_formatado.replace(":", "")
    minutos_a_somar = sum(int(digito) for digito in digitos_str)
    horario_final_alvo = horario_base + timedelta(minutes=minutos_a_somar)

    # 4. Formata a mensagem e retorna os dados de forma estruturada
    mensagem_contexto = f"Soma dos dígitos de {horario_formatado} = {minutos_a_somar} min."
    
    return {
        "trigger_id": resultado_branco['id'],
        "message": mensagem_contexto,
        "targets": [horario_final_alvo]
    }