# strategies/estrategia_soma_minutos_multiplicada.py

from datetime import datetime, timedelta

# --- Metadados Obrigatórios ---
ID = "soma_minutos_multiplicada"
NOME = "Soma Minutos Multiplicada"
DESCRICAO = "Após um Branco, soma os dígitos do minuto, multiplica por 2 e por 3, e adiciona como minutos ao horário do gatilho para gerar dois alvos."
EMOJI = "🔢" # Emoji para usar em notificações de confluência

def verificar(historico, cursor):
    """
    Verifica se o último resultado foi Branco. Se sim, aplica a lógica de
    soma de dígitos do minuto e multiplicação para gerar dois novos alvos.
    """

    # 1. CONDIÇÃO DE GATILHO: O resultado mais recente deve ser um Branco.
    resultado_branco = historico[0]
    if resultado_branco['color'] != 'Branco':
        return None

    # 2. EXTRAÇÃO DOS DADOS DO GATILHO
    # Pega o horário exato em que o Branco ocorreu
    horario_base = datetime.strptime(resultado_branco['timestamp_iso'], "%Y-%m-%d %H:%M:%S")
    # Pega apenas o número do minuto (ex: 13 para o horário 17:13)
    minuto_original = horario_base.minute

    # 3. LÓGICA PRINCIPAL: SOMA DOS DÍGITOS
    # Converte o minuto em texto para poder somar cada dígito individualmente
    # Ex: 13 -> '1', '3' -> 1 + 3 = 4
    # Ex: 05 -> '5' -> 5 = 5
    soma_dos_digitos = sum(int(digito) for digito in str(minuto_original))

    # 4. LÓGICA PRINCIPAL: MULTIPLICAÇÃO
    # Multiplica a soma por 2 e por 3 para obter os minutos a serem adicionados
    minutos_a_adicionar_alvo1 = soma_dos_digitos * 2
    minutos_a_adicionar_alvo2 = soma_dos_digitos * 3
    
    # 5. CÁLCULO DOS HORÁRIOS FINAIS DOS ALVOS
    # Adiciona os minutos calculados ao horário original do Branco
    # O timedelta já cuida de virar a hora corretamente (ex: 17:55 + 10 min = 18:05)
    horario_alvo_1 = horario_base + timedelta(minutes=minutos_a_adicionar_alvo1)
    horario_alvo_2 = horario_base + timedelta(minutes=minutos_a_adicionar_alvo2)

    # 6. CRIAÇÃO DA MENSAGEM DE CONTEXTO (para fácil entendimento)
    # Ex: "Minuto 13 (1+3=4). Alvos: +8min (17:21) e +12min (17:25)"
    mensagem_contexto = (
        f"Minuto {minuto_original} ({'+'.join(str(minuto_original))}={soma_dos_digitos}). "
        f"Alvos: +{minutos_a_adicionar_alvo1}min e +{minutos_a_adicionar_alvo2}min."
    )

    # 7. RETORNO ESTRUTURADO PARA O COLETOR
    # O coletor espera um dicionário com essas chaves
    return {
        "trigger_id": resultado_branco['id'], # ID do resultado que gerou o sinal
        "message": mensagem_contexto,
        "targets": sorted([horario_alvo_1, horario_alvo_2]) # Lista com os dois horários de alvo
    }