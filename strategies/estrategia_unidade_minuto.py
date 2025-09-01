# strategies/estrategia_unidade_minuto.py

from datetime import datetime, timedelta

# --- Metadados Obrigatórios (Atualizados) ---
ID = "unidade_minuto_pos_branco"
NOME = "Gatilho de Confluência por Unidade de Minuto"
DESCRICAO = "Após um Branco, gera um par de alvos. Esses alvos são contados pela API e só são exibidos no painel se houver 4 ou mais sinais para o mesmo minuto."

# --- Lógica da Estratégia ---
MAPA_DIGITOS = {
    0: 5, 1: 7, 2: 6, 3: 9, 4: 8,
    5: 0, 6: 2, 7: 1, 8: 4, 9: 3
}

# --- Função Principal de Verificação (CORRIGIDA) ---
def verificar(historico, cursor):
    """
    Verifica se o último resultado foi Branco e, se sim, gera dois alvos
    com base no último dígito do minuto do horário do Branco.
    """

    # 1. Condição de gatilho
    resultado_branco = historico[0]
    if resultado_branco['color'] != 'Branco':
        return None

    # 2. Extração de dados
    horario_base = datetime.strptime(resultado_branco['timestamp_iso'], "%Y-%m-%d %H:%M:%S")
    minuto_gatilho = horario_base.minute
    digito_gatilho = minuto_gatilho % 10

    # 3. Mapeamento
    if digito_gatilho not in MAPA_DIGITOS:
        return None
    digito_alvo = MAPA_DIGITOS[digito_gatilho]

    # 4. Cálculo do primeiro alvo
    minutos_para_adicionar = 0
    while True:
        minutos_para_adicionar += 1
        minuto_futuro = (minuto_gatilho + minutos_para_adicionar) % 60
        if minuto_futuro % 10 == digito_alvo:
            break
            
    horario_alvo_1 = (horario_base + timedelta(minutes=minutos_para_adicionar)).replace(second=0, microsecond=0)

    # 5. Cálculo do segundo alvo
    horario_alvo_2 = horario_alvo_1 + timedelta(minutes=2)

    # 6. Formatação e retorno
    mensagem_contexto = (
        f"Gatilho no minuto ':{minuto_gatilho:02d}' (dígito {digito_gatilho}). "
        f"Alvo para minuto com final '{digito_alvo}'."
    )

    return {
        "trigger_id": resultado_branco['id'],
        "message": mensagem_contexto,
        "targets": [horario_alvo_1, horario_alvo_2]
    }