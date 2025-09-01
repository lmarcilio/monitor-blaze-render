# strategies/estrategia_dez_minutos.py

from datetime import datetime, timedelta

# --- Metadados Obrigatórios ---
ID = "soma_dez_min_antes" # ID único para esta nova estratégia
NOME = "Alvo Pós-Branco (10 Minutos Antes)"
DESCRICAO = "Quando um Branco sai, busca o número de ~10 minutos atrás e o soma como minutos para gerar um único alvo."

# --- Função Principal de Verificação (CORRIGIDA) ---
def verificar(historico, cursor):
    """
    Verifica se o último resultado foi Branco e, em caso afirmativo,
    tenta encontrar o resultado de 10 minutos antes para o cálculo.
    """

    # 1. Condição de gatilho: ser um Branco e ter pelo menos alguns resultados para analisar.
    if historico[0]['color'] != 'Branco' or len(historico) < 10:
        return None

    # 2. Define os horários de referência
    resultado_branco = historico[0]
    horario_branco = datetime.strptime(resultado_branco['timestamp_iso'], "%Y-%m-%d %H:%M:%S")
    horario_alvo_busca = horario_branco - timedelta(minutes=10)

    # 3. Busca pelo resultado mais próximo do nosso alvo de 10 minutos atrás
    resultado_encontrado = None
    menor_diferenca = timedelta(days=1) # Começa com uma diferença muito grande

    # Itera sobre o histórico (pulando o próprio branco)
    for resultado_passado in historico[1:]:
        horario_passado = datetime.strptime(resultado_passado['timestamp_iso'], "%Y-%m-%d %H:%M:%S")
        diferenca_atual = abs(horario_passado - horario_alvo_busca)

        # Se a diferença atual for menor que a menor já encontrada, este é nosso novo candidato
        if diferenca_atual < menor_diferenca:
            menor_diferenca = diferenca_atual
            resultado_encontrado = resultado_passado

    # 4. Validação: Se não encontramos um resultado ou se o mais próximo está muito longe (ex: mais de 90s de diferença),
    # significa que não temos dados confiáveis para aquele minuto. Então, cancelamos a operação.
    if not resultado_encontrado or menor_diferenca > timedelta(seconds=90):
        return None

    # 5. Se chegamos aqui, encontramos um resultado válido! Vamos calcular o alvo.
    numero_a_somar = resultado_encontrado['roll']
    horario_final_alvo = horario_branco + timedelta(minutes=numero_a_somar)

    # 6. Formata a mensagem e retorna os dados de forma estruturada
    horario_encontrado_str = datetime.strptime(resultado_encontrado['timestamp_iso'], "%Y-%m-%d %H:%M:%S").strftime('%H:%M')
    
    mensagem_contexto = f"Usado número {numero_a_somar} (da jogada das ~{horario_encontrado_str})."
    
    return {
        "trigger_id": resultado_branco['id'],
        "message": mensagem_contexto,
        "targets": [horario_final_alvo] # Retorna uma lista com um único alvo
    }