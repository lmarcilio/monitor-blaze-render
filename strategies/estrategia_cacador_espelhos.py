# strategies/estrategia_cacador_espelhos.py

from datetime import datetime, timedelta

# --- Metadados Obrigatórios ---
ID = "cacador_de_espelhos"
NOME = "Caçador de Espelhos"
DESCRICAO = "Após um Branco, combina os números anterior e posterior para criar alvos de minutos espelhados (ex: 3 e 14 -> :35 e :53)."
EMOJI = "🪞" # Emoji para usar em notificações de confluência

# --- Constantes da Estratégia ---
# Mapeia números de dois dígitos para um, conforme a regra
MAPA_DEZENA = {
    10: 1,
    11: 2,
    12: 3,
    13: 4,
    14: 5
}

def _mapear_numero(roll):
    """Retorna o dígito correspondente ao número, aplicando a regra das dezenas."""
    return MAPA_DEZENA.get(roll, roll)

def verificar(historico, cursor):
    """
    Verifica se o resultado anterior foi um Branco. Se sim, pega os números
    imediatamente antes e depois do Branco para formar os alvos.
    """
    
    # 1. CONDIÇÃO DE GATILHO
    # A estratégia só pode ser verificada se tivermos o número antes do branco,
    # o branco em si, e o número depois do branco.
    # O gatilho real é o número que sai *depois* do branco.
    if len(historico) < 3 or historico[1]['color'] != 'Branco':
        return None

    # 2. EXTRAÇÃO DOS DADOS
    resultado_posterior = historico[0]
    resultado_branco = historico[1]
    resultado_anterior = historico[2]

    horario_base = datetime.strptime(resultado_posterior['timestamp_iso'], "%Y-%m-%d %H:%M:%S")

    # 3. LÓGICA DE CÁLCULO
    # Mapeia os números para seus dígitos correspondentes
    digito_anterior = _mapear_numero(resultado_anterior['roll'])
    digito_posterior = _mapear_numero(resultado_posterior['roll'])

    # Forma os minutos espelhados
    alvo_minuto_1 = int(f"{digito_anterior}{digito_posterior}")
    alvo_minuto_2 = int(f"{digito_posterior}{digito_anterior}")

    # 4. MONTAGEM DOS ALVOS
    alvos_finais_dt = []
    minutos_processados = set()

    for minuto_base in [alvo_minuto_1, alvo_minuto_2]:
        if minuto_base in minutos_processados:
            continue
        minutos_processados.add(minuto_base)

        # Trata minutos acima de 59 (ex: 71 vira minuto 11)
        minuto_alvo_real = minuto_base % 60
        
        # Calcula a próxima vez que esse minuto ocorrerá
        proximo_horario_alvo = horario_base.replace(minute=minuto_alvo_real, second=0, microsecond=0)
        
        # Se o horário calculado já passou, adiciona uma hora para pegar o da próxima hora
        if proximo_horario_alvo <= horario_base:
            proximo_horario_alvo += timedelta(hours=1)
            
        alvos_finais_dt.append(proximo_horario_alvo)

    if not alvos_finais_dt:
        return None

    # 5. FORMATAÇÃO DO RETORNO
    minutos_str = " e ".join([f"'{m % 60:02d}'" for m in sorted(list(minutos_processados))])
    mensagem_contexto = (
        f"Espelho: {resultado_anterior['roll']} ⚪ {resultado_posterior['roll']} "
        f"-> Alvos para minuto(s) {minutos_str}"
    )

    return {
        "trigger_id": resultado_posterior['id'], # O gatilho é o resultado *após* o branco
        "message": mensagem_contexto,
        "targets": sorted(alvos_finais_dt)
    }