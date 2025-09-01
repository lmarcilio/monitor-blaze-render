# strategies/estrategia_combinacao_digitos.py

from datetime import datetime, timedelta

# --- Metadados Obrigatórios ---
ID = "combinacao_digitos_vizinhos"
NOME = "Combinação de Dígitos"
DESCRICAO = "Após um Branco, combina o último dígito do número anterior com o primeiro dígito do número posterior para gerar um alvo."
EMOJI = "🧩"

# --- Funções Auxiliares da Estratégia ---

def _get_last_digit(roll):
    """Retorna o último dígito de um número. Ex: 14 -> 4"""
    return roll % 10

def _get_first_digit(roll):
    """Retorna o primeiro dígito de um número. Ex: 14 -> 1, 7 -> 7"""
    if roll < 10:
        return roll
    return int(str(roll)[0])

# --- Função Principal de Verificação ---

def verificar(historico, cursor):
    """
    Verifica a sequência [Número Anterior] - [Branco] - [Número Posterior]
    e aplica a lógica de combinação de dígitos.
    """
    
    # 1. CONDIÇÃO DE GATILHO
    # Precisa de pelo menos 3 resultados no histórico, e o do meio deve ser um Branco.
    # O gatilho real é o número que sai APÓS o Branco.
    if len(historico) < 3 or historico[1]['color'] != 'Branco':
        return None

    # 2. EXTRAÇÃO DOS DADOS
    resultado_posterior = historico[0]
    resultado_branco = historico[1]
    resultado_anterior = historico[2]

    horario_base = datetime.strptime(resultado_posterior['timestamp_iso'], "%Y-%m-%d %H:%M:%S")

    # 3. APLICAÇÃO DA LÓGICA
    # Pega o último dígito do número anterior
    last_digit_anterior = _get_last_digit(resultado_anterior['roll'])
    # Pega o primeiro dígito do número posterior
    first_digit_posterior = _get_first_digit(resultado_posterior['roll'])

    # Combina os dígitos como strings e depois converte para inteiro
    alvo_minuto_combinado = int(f"{last_digit_anterior}{first_digit_posterior}")

    # 4. TRATAMENTO DE MINUTOS > 59
    # O operador '%' (módulo) resolve isso de forma elegante. 
    # Ex: 11 % 60 = 11.  91 % 60 = 31.
    minuto_final = alvo_minuto_combinado % 60

    # 5. CÁLCULO DO HORÁRIO FINAL DO ALVO
    # Define o alvo para o minuto calculado na hora atual
    horario_alvo = horario_base.replace(minute=minuto_final, second=0, microsecond=0)

    # Se o horário calculado já passou, avança para a próxima hora
    if horario_alvo <= horario_base:
        horario_alvo += timedelta(hours=1)

    # 6. FORMATAÇÃO DO RETORNO
    mensagem_contexto = (
        f"Combinação: {resultado_anterior['roll']} (final {last_digit_anterior}) + "
        f"{resultado_posterior['roll']} (inicial {first_digit_posterior}) -> Alvo : {minuto_final:02d}"
    )

    return {
        "trigger_id": resultado_posterior['id'],
        "message": mensagem_contexto,
        "targets": [horario_alvo]
    }