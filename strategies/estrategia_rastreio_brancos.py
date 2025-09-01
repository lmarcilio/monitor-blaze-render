# strategies/estrategia_rastreio_brancos.py

from datetime import datetime, timedelta
from collections import defaultdict
import sqlite3
import os

# --- Metadados Obrigatórios ---
ID = "rastreio_brancos"
NOME = "Confluência de Minutos em Horas Distintas"
DESCRICAO = "Analisa as últimas 6h. Se um mesmo minuto (ex: :14) teve 'Branco' em 2 ou mais horas diferentes (ex: 18:14 e 22:14), gera um sinal para a próxima ocorrência desse minuto."

def _sinal_ja_pendente(cursor, target_dt):
    """Verifica se já existe um sinal pendente para este alvo."""
    target_str = target_dt.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "SELECT 1 FROM sinais WHERE strategy_id = ? AND target_timestamp = ? AND status = 'pending' LIMIT 1",
        (ID, target_str)
    )
    return cursor.fetchone() is not None

# --- Função Principal de Verificação (CORRIGIDA) ---
# Agora usa o 'cursor' passado pelo coletor, sem criar uma nova conexão.
def verificar(historico, cursor):
    """
    Esta função analisa o histórico para encontrar minutos com recorrência de brancos
    em horas diferentes.
    """
    agora = datetime.now()
    seis_horas_atras = agora - timedelta(hours=6)

    try:
        # 1. PEGAR TODOS OS BRANCOS DAS ÚLTIMAS 6 HORAS
        cursor.execute(
            "SELECT timestamp_iso FROM resultados WHERE color = 'Branco' AND timestamp_iso >= ?",
            (seis_horas_atras.strftime("%Y-%m-%d %H:%M:%S"),)
        )
        timestamps_brancos = [datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S") for row in cursor.fetchall()]

        if not timestamps_brancos:
            return None

        # 2. AGRUPAR AS HORAS EM QUE CADA MINUTO APARECEU
        minuto_para_horas = defaultdict(set)
        for ts in timestamps_brancos:
            minuto_para_horas[ts.minute].add(ts.hour)

        # 3. ENCONTRAR OS MINUTOS "QUENTES" (que apareceram em 2+ horas diferentes)
        minutos_quentes = []
        for minuto, horas_set in minuto_para_horas.items():
            if len(horas_set) >= 2:
                minutos_quentes.append(minuto)

        if not minutos_quentes:
            return None

        # 4. GERAR SINAIS PARA OS MINUTOS QUENTES
        sinais_gerados = []
        for minuto_alvo in sorted(minutos_quentes):
            
            horario_alvo = agora.replace(minute=minuto_alvo, second=0, microsecond=0)
            if agora.minute >= minuto_alvo:
                horario_alvo += timedelta(hours=1)
            
            if not _sinal_ja_pendente(cursor, horario_alvo):
                horas_do_padrao = sorted(list(minuto_para_horas[minuto_alvo]))
                mensagem = f"Minuto :'{minuto_alvo:02d}' repetiu nas horas {horas_do_padrao}."
                sinal = {
                    "trigger_id": f"{ID}-{horario_alvo.strftime('%Y%m%d%H%M')}",
                    "message": mensagem,
                    "targets": [horario_alvo]
                }
                sinais_gerados.append(sinal)

        return sinais_gerados if sinais_gerados else None

    except Exception as e:
        print(f"[ERRO GRAVE na execução da ESTRATÉGIA {NOME}]: {e}")
        return None