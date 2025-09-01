# strategies/estrategia_medias_intervalo.py

import sqlite3
import os
from datetime import datetime, timedelta

# --- METADADOS DA ESTRATÉGIA ---
ID = 'medias_intervalo_brancos'
NOME = 'Sinal por Média de Intervalo'
DESCRICAO = 'Gera um sinal de alvo com base no tempo médio de ocorrência entre os resultados brancos.'

# --- CAMINHO DO BANCO DE DADOS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '..', '..', 'database', 'blaze_data.db')

def _get_all_intervals(cursor):
    """
    Função auxiliar que busca todos os intervalos entre brancos nas últimas 6 horas.
    """
    try:
        six_hours_ago = datetime.now() - timedelta(hours=6)
        six_hours_ago_str = six_hours_ago.strftime("%Y-%m-%d %H:%M:%S")
        
        query = "SELECT timestamp_iso FROM resultados WHERE color = 'Branco' AND timestamp_iso >= ? ORDER BY timestamp_iso ASC"
        cursor.execute(query, (six_hours_ago_str,))
        
        white_timestamps = [datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S") for row in cursor.fetchall()]
        
        if len(white_timestamps) < 2:
            return []

        return [round((white_timestamps[i] - white_timestamps[i-1]).total_seconds() / 60) for i in range(1, len(white_timestamps))]

    except Exception as e:
        print(f"[{ID}] Erro ao buscar intervalos: {e}")
        return []

def verificar(historico, cursor):
    """
    Verifica se o último resultado foi Branco e gera sinais de média.
    """
    if not historico:
        return None

    ultimo_resultado = historico[0]
    
    if ultimo_resultado['color'] != 'Branco':
        return None

    try:
        all_intervals = _get_all_intervals(cursor)
        
        if not all_intervals or len(all_intervals) < 2:
            print(f"[{NOME}] Dados insuficientes ({len(all_intervals)} intervalos). Mínimo de 2 necessário. Nenhum sinal gerado.")
            return None

        sorted_intervals = sorted(all_intervals)
        
        midpoint = len(sorted_intervals) // 2
        lower_half = sorted_intervals[:midpoint]
        upper_half = sorted_intervals[midpoint:]

        if not lower_half:
            lower_half = [upper_half.pop(0)]

        media_curta = round(sum(lower_half) / len(lower_half))
        media_longa = round(sum(upper_half) / len(upper_half))

        if media_curta == media_longa:
            media_longa += 1
        
        trigger_id = ultimo_resultado['id']
        horario_gatilho = datetime.strptime(ultimo_resultado['timestamp_iso'], "%Y-%m-%d %H:%M:%S")
        
        alvo_curto_dt = horario_gatilho + timedelta(minutes=media_curta)
        alvo_longo_dt = horario_gatilho + timedelta(minutes=media_longa)

        sinais_gerados = [
            {'trigger_id': f"{trigger_id}-curta", 'message': f"Média Curta ({media_curta} min)", 'targets': [alvo_curto_dt]},
            {'trigger_id': f"{trigger_id}-longa", 'message': f"Média Longa ({media_longa} min)", 'targets': [alvo_longo_dt]}
        ]

        print(f"[{NOME}] SUCESSO: 2 novos sinais gerados (Curta: {media_curta}m, Longa: {media_longa}m).")
        return sinais_gerados

    except Exception as e:
        print(f"[{NOME}] Erro durante a verificação: {e}")
        return None