# strategies/estrategia_soma_vermelhos.py

from datetime import datetime, timedelta

# --- Metadados Obrigatórios (Atualizados) ---
ID = "soma_tres_vermelhos_antes_branco" 
NOME = "Alvo Sequencial Pós-Branco (3 Vermelhos 1-7)"
DESCRICAO = "Após um Branco, busca os 3 Vermelhos (números 1-7) anteriores. Usa cada um para gerar um alvo sequencial (alvo1 + num2 = alvo2, etc.)."

# --- Função Principal de Verificação (CORRIGIDA) ---
def verificar(historico, cursor):
    """
    Verifica se o último resultado foi Branco. Se sim, busca os 3 resultados
    vermelhos (com números de 1 a 7) anteriores no histórico e gera 3 alvos sequenciais.
    """

    # 1. Condição de gatilho: o resultado mais recente deve ser um Branco.
    resultado_branco = historico[0]
    if resultado_branco['color'] != 'Branco':
        return None

    # 2. Buscar os 3 números vermelhos (entre 1 e 7) no histórico
    numeros_vermelhos_encontrados = []
    for resultado_passado in historico[1:]:
        # A condição agora tem duas partes: ser Vermelho E ter o número entre 1 e 7
        if resultado_passado['color'] == 'Vermelho' and 1 <= resultado_passado['roll'] <= 7:
            numeros_vermelhos_encontrados.append(resultado_passado['roll'])
        
        # Para assim que encontrar 3
        if len(numeros_vermelhos_encontrados) == 3:
            break
    
    # 3. Validação: A estratégia só roda se encontrar exatamente 3 números
    if len(numeros_vermelhos_encontrados) < 3:
        return None

    # 4. Cálculo sequencial dos 3 alvos
    horario_base = datetime.strptime(resultado_branco['timestamp_iso'], "%Y-%m-%d %H:%M:%S")

    # Pega os números na ordem em que foram encontrados (do mais recente para o mais antigo)
    primeiro_numero = numeros_vermelhos_encontrados[0]
    segundo_numero = numeros_vermelhos_encontrados[1]
    terceiro_numero = numeros_vermelhos_encontrados[2]

    # Calcula os alvos de forma sequencial, como você descreveu
    alvo1 = horario_base + timedelta(minutes=primeiro_numero)
    alvo2 = alvo1 + timedelta(minutes=segundo_numero)
    alvo3 = alvo2 + timedelta(minutes=terceiro_numero)
    
    # 5. Formatação da mensagem e retorno com múltiplos alvos
    numeros_str = f"{primeiro_numero}, {segundo_numero}, {terceiro_numero}"
    mensagem_contexto = f"Alvos sequenciais usando os vermelhos: {numeros_str}."
    
    return {
        "trigger_id": resultado_branco['id'],
        "message": mensagem_contexto,
        # A chave "targets" agora contém uma lista com os três horários
        "targets": [alvo1, alvo2, alvo3]
    }