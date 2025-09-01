# signal_logic.py

from collections import defaultdict
from datetime import datetime, timedelta
import json
import os
import psycopg2 # Importar para PostgreSQL
from psycopg2 import extras # Para usar RealDictCursor

# Adicione os caminhos dos arquivos de configuração aqui para que a lógica seja autossuficiente
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STRATEGIES_DIR = os.path.join(BASE_DIR, '..', 'strategies')
ACTIVATOR_STATE_FILE = os.path.join(STRATEGIES_DIR, 'activator_state.json')

def _load_generic_config(file_path, default_value={}):
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True) # Garante que o diretório exista
        try:
            with open(file_path, 'w') as f: json.dump(default_value, f, indent=4)
        except IOError: pass
        return default_value
    try:
        with open(file_path, 'r') as f: return json.load(f)
    except (IOError, json.JSONDecodeError): return default_value

def _save_generic_config(file_path, data):
    os.makedirs(os.path.dirname(file_path), exist_ok=True) # Garante que o diretório exista
    try:
        with open(file_path, 'w') as f: json.dump(data, f, indent=4)
    except IOError: pass

def _load_activator_state():
    return _load_generic_config(ACTIVATOR_STATE_FILE, default_value={"last_activation_timestamp": None})

def _save_activator_state(state):
    _save_generic_config(ACTIVATOR_STATE_FILE, state)

def process_and_filter_signals(cursor, strategy_statuses, mapping, confluence_modes, activator_modes):
    """
    Lógica unificada para processar, filtrar e formatar sinais.
    Esta função será a única fonte da verdade para o que deve ser mostrado e notificado.
    """
    try:
        # --- Lógica do Ativador ---
        activator_state = _load_activator_state()
        last_activation_str = activator_state.get("last_activation_timestamp")
        activation_dt = datetime.fromisoformat(last_activation_str) if last_activation_str else None

        # Usar o cursor passado para buscar o último resultado
        cursor.execute("SELECT roll, timestamp_iso FROM resultados ORDER BY timestamp_iso DESC LIMIT 1")
        last_result = cursor.fetchone()

        if last_result:
            last_roll_time = last_result['timestamp_iso'] # Já é datetime object
            # A ativação só ocorre se não houver uma ativação recente ou se o último resultado for mais novo que a última ativação
            if not activation_dt or last_roll_time > activation_dt:
                soma = last_roll_time.minute + last_result['roll']
                if soma % 10 == 0 or soma % 10 == 5:
                    activation_dt = last_roll_time
                    _save_activator_state({"last_activation_timestamp": activation_dt.isoformat()})

        is_window_active = False
        window_end = None
        if activation_dt:
            window_end = activation_dt + timedelta(minutes=3)
            if datetime.now() < window_end:
                is_window_active = True
        
        # --- Lógica de Sinais ---
        active_strategy_ids = [sid for sid, is_active in strategy_statuses.items() if is_active]
        if not active_strategy_ids:
            return [], is_window_active, window_end

        # Usar %s para placeholders em psycopg2
        placeholders = ','.join(['%s'] * len(active_strategy_ids))
        
        two_minutes_ago = datetime.now() - timedelta(minutes=2)
        query = f"""
            SELECT id, strategy_id, strategy_name, message, target_timestamp, status
            FROM sinais 
            WHERE strategy_id IN ({placeholders})
              AND (status = 'pending' OR (status = 'hit' AND target_timestamp >= %s))
            ORDER BY target_timestamp ASC
        """
        params = active_strategy_ids + [two_minutes_ago]
        cursor.execute(query, params)

        all_signals = [dict(row) for row in cursor.fetchall()]

        signals_by_panel = defaultdict(list)
        for signal in all_signals:
            panel_id = mapping.get(signal['strategy_id'])
            if panel_id and panel_id != 'none':
                signals_by_panel[panel_id].append(signal)
        
        strategy_count_by_panel = defaultdict(int)
        for strategy_id in active_strategy_ids:
            panel_id = mapping.get(strategy_id)
            if panel_id in ['1', '2', '3']:
                strategy_count_by_panel[panel_id] += 1

        final_output = []
        for panel_id, signals in signals_by_panel.items():
            panel_signals = signals
            
            # Aplica filtro do ativador se estiver ligado para este painel
            if activator_modes.get(str(panel_id)):
                if not is_window_active:
                    panel_signals = [] 
                else:
                    # target_timestamp já é datetime object
                    panel_signals = [s for s in panel_signals if activation_dt <= s['target_timestamp'] < window_end]
            
            if not panel_signals: continue

            # Aplica filtro de confluência
            if confluence_modes.get(str(panel_id)):
                grouped_by_time = defaultdict(list)
                for signal in panel_signals: grouped_by_time[signal['target_timestamp']].append(signal)

                for timestamp, group in grouped_by_time.items():
                    required_count = strategy_count_by_panel.get(panel_id, 0)
                    unique_strategies_in_group = set(s['strategy_id'] for s in group)
                    
                    trigger_condition_met = False
                    if required_count >= 3 and len(unique_strategies_in_group) == required_count:
                        trigger_condition_met = True
                    elif required_count == 2 and len(unique_strategies_in_group) >= 2:
                        trigger_condition_met = True
                    
                    if trigger_condition_met:
                        is_hit = any(s['status'] == 'hit' for s in group)
                        confluence_status = 'hit' if is_hit else 'pending'
                        final_output.append({
                            "type": "confluence", "panel_id": panel_id, "key": timestamp.isoformat(), # Converter datetime para string
                            "db_ids": [s['id'] for s in group],
                            "target_timestamp": timestamp.isoformat(), # Converter datetime para string
                            "strategy_names": sorted(list(set(s['strategy_name'] for s in group))),
                            "count": len(unique_strategies_in_group),
                            "status": confluence_status
                        })
            else: # Modo individual
                for signal in panel_signals:
                    final_output.append({
                        "type": "individual", "panel_id": panel_id, "key": str(signal['id']),
                        "db_ids": [signal['id']],
                        "strategy_id": signal['strategy_id'], "strategy_name": signal['strategy_name'],
                        "message": signal['message'], "target_timestamp": signal['target_timestamp'].isoformat(), # Converter datetime para string
                        "status": signal['status']
                    })
        
        return final_output, is_window_active, window_end
    except Exception as e:
        print(f"[ERRO na Lógica Central de Sinais]: {e}")
        return [], False, None

