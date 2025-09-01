# strategies/estrategia_numeros_magicos.py

from datetime import datetime, timedelta

# --- Metadados Obrigatórios (Atualizados) ---
ID = "numeros_magicos"
NOME = "Confluência de Números Altos"
DESCRICAO = "Gatilho com os números 10, 12, 13 ou 14. Gera 3 alvos (+7, +14, +21 min). Um sinal é criado no painel quando 6 sinais apontam para o mesmo horário."

# --- Constantes da Estratégia (ATUALIZADAS) ---
MAGIC_NUMBERS = {10, 12, 13, 14} 
MINUTES_TO_ADD = [7, 14, 21]

# --- Propriedade Customizada para Confluência ---
CONFLUENCE_COUNT = 6

# --- Função Principal de Verificação ---
def verificar(historico, cursor):
    resultado_gatilho = historico[0]
    
    if resultado_gatilho['roll'] not in MAGIC_NUMBERS:
        return None

    horario_base = datetime.strptime(resultado_gatilho['timestamp_iso'], "%Y-%m-%d %H:%M:%S")
    
    alvos = []
    for minutos in MINUTES_TO_ADD:
        alvos.append(horario_base + timedelta(minutes=minutos))

    mensagem_contexto = f"Gatilho: Número {resultado_gatilho['roll']} às {horario_base.strftime('%H:%M:%S')}."
    
    return {
        "trigger_id": resultado_gatilho['id'],
        "message": mensagem_contexto,
        "targets": alvos 
    }