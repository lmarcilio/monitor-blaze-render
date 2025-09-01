# strategies/estrategia_correcao_espelho.py

from datetime import datetime, timedelta

# --- Metadados Obrigatórios ---
ID = "correcao_espelho_miss"
NOME = "Correção de Espelho (+1h)"
DESCRICAO = "Se um alvo do Caçador de Espelhos errar, gera um novo alvo para 1 hora depois do horário original do erro."
EMOJI = "➡️" # Emoji para usar em notificações de confluência

# --- Configurações da Meta-Estratégia ---
# ID da estratégia que queremos observar. Deve ser exatamente igual ao ID do outro arquivo.
SOURCE_STRATEGY_ID = 'cacador_de_espelhos' 

def verificar(historico, cursor):
    """
    Esta meta-estratégia não olha para o histórico de rolagens (historico).
    Em vez disso, ela usa o cursor do banco de dados para analisar a tabela 'sinais'.
    """
    
    # 1. DEFINIR JANELA DE TEMPO
    # Vamos procurar por erros que aconteceram nos últimos 3 minutos para não sobrecarregar
    # e para agir rapidamente.
    agora = datetime.now()
    tres_minutos_atras = agora - timedelta(minutes=3)
    tres_minutos_atras_str = tres_minutos_atras.strftime("%Y-%m-%d %H:%M:%S")

    # 2. BUSCAR ERROS RECENTES DA ESTRATÉGIA ALVO
    # Um "erro" é um sinal que o coletor marcou como 'expired'.
    query = """
        SELECT id, target_timestamp 
        FROM sinais
        WHERE strategy_id = ? 
          AND status = 'expired'
          AND target_timestamp >= ?
    """
    try:
        cursor.execute(query, (SOURCE_STRATEGY_ID, tres_minutos_atras_str))
        sinais_errados = cursor.fetchall()
    except Exception as e:
        print(f"[{NOME}] Erro ao consultar o banco de dados: {e}")
        return None

    if not sinais_errados:
        return None # Nenhum erro encontrado, não faz nada.

    # 3. PROCESSAR CADA ERRO E GERAR UM NOVO SINAL (SE AINDA NÃO EXISTIR)
    sinais_de_correcao = []
    for sinal_errado in sinais_errados:
        original_signal_id = sinal_errado['id']
        horario_do_erro_str = sinal_errado['target_timestamp']
        
        # Cria um ID único para o nosso novo sinal de correção para evitar duplicatas.
        novo_trigger_id = f"correcao-{original_signal_id}"

        # VERIFICA SE JÁ CRIAMOS UM SINAL DE CORREÇÃO PARA ESTE ERRO
        cursor.execute("SELECT 1 FROM sinais WHERE trigger_id = ? LIMIT 1", (novo_trigger_id,))
        if cursor.fetchone():
            continue # Já existe, pula para o próximo erro.

        # CALCULA O NOVO ALVO
        horario_do_erro_dt = datetime.strptime(horario_do_erro_str, "%Y-%m-%d %H:%M:%S")
        novo_horario_alvo = horario_do_erro_dt + timedelta(hours=1)

        # MONTA O NOVO SINAL
        mensagem_contexto = f"Correção do alvo perdido das {horario_do_erro_dt.strftime('%H:%M')}"
        
        sinal_gerado = {
            "trigger_id": novo_trigger_id,
            "message": mensagem_contexto,
            "targets": [novo_horario_alvo]
        }
        sinais_de_correcao.append(sinal_gerado)

    # 4. RETORNA A LISTA DE NOVOS SINAIS GERADOS
    if sinais_de_correcao:
        print(f"[{NOME}] SUCESSO: {len(sinais_de_correcao)} novo(s) sinal(is) de correção gerado(s).")
        return sinais_de_correcao
    
    return None