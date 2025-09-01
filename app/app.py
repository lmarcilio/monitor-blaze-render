# app.py

import sqlite3 # Ainda pode ser útil para alguma lógica local, mas não para o DB principal
from flask import Flask, jsonify, render_template, g, request
import os
import json
import importlib.util
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import psycopg2 # Importar para PostgreSQL
from psycopg2 import extras # Para usar RowFactory similar ao SQLite

from signal_logic import process_and_filter_signals

app = Flask(__name__)

# --- Configuração de Caminhos ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STRATEGIES_DIR = os.path.join(BASE_DIR, 'strategies')

# Arquivos de configuração JSON (ainda serão usados para status/mapping/etc.
# mas as alterações feitas via frontend não serão persistentes entre deploys/reinícios
# a menos que você as salve manualmente no repositório ou migre para o DB.
# Para o Telegram, usaremos variáveis de ambiente).
STATUS_FILE = os.path.join(STRATEGIES_DIR, 'strategy_status.json')
ARMED_SEQUENCES_FILE = os.path.join(STRATEGIES_DIR, 'armed_sequences.json')
TELEGRAM_CONFIG_FILE = os.path.join(STRATEGIES_DIR, 'telegram_config.json') # Será lido, mas vars de ambiente terão prioridade
STRATEGY_MAPPING_FILE = os.path.join(STRATEGIES_DIR, 'strategyColumnMapping.json')
CONFLUENCE_CONFIG_FILE = os.path.join(STRATEGIES_DIR, 'confluenceModeSettings.json')
ACTIVATOR_CONFIG_FILE = os.path.join(STRATEGIES_DIR, 'activatorModeSettings.json')
ACTIVATOR_STATE_FILE = os.path.join(STRATEGIES_DIR, 'activator_state.json')


# --- Configuração do PostgreSQL ---
# As credenciais virão das variáveis de ambiente do Render
DATABASE_URL = os.environ.get('DATABASE_URL') # Render fornece isso automaticamente para o DB gerenciado

def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL não configurada. Conexão com o banco de dados falhou.")
    conn = psycopg2.connect(DATABASE_URL, sslmode='require') # 'sslmode=require' é importante para o Render
    return conn

def get_db():
    # Usa g para armazenar a conexão e reutilizá-la na mesma requisição
    if 'db' not in g:
        g.db = get_db_connection()
        # Configura o cursor para retornar linhas como dicionários (similar ao RowFactory do SQLite)
        g.db.cursor_factory = psycopg2.extras.RealDictCursor
    return g.db

@app.teardown_appcontext
def close_connection(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# Função para inicializar o esquema do banco de dados (tabelas)
def inicializar_banco_de_dados_pg():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Criação das tabelas para PostgreSQL
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resultados (
                id VARCHAR(255) PRIMARY KEY,
                created_at VARCHAR(255),
                roll INTEGER,
                color VARCHAR(50),
                timestamp_iso TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sinais (
                id SERIAL PRIMARY KEY,
                trigger_id VARCHAR(255) NOT NULL,
                strategy_id VARCHAR(255) NOT NULL,
                strategy_name VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                target_timestamp TIMESTAMP NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                telegram_message_id BIGINT DEFAULT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS estrategia_stats (
                strategy_id VARCHAR(255) PRIMARY KEY,
                strategy_name VARCHAR(255) NOT NULL,
                hits INTEGER DEFAULT 0,
                misses INTEGER DEFAULT 0,
                total_signals INTEGER DEFAULT 0
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notificacoes_enviadas (
                notification_key VARCHAR(255) PRIMARY KEY
            );
        """)
        conn.commit()
        print("Tabelas do PostgreSQL verificadas/criadas com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar o banco de dados PostgreSQL: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

# Chamar a inicialização do DB no startup da aplicação Flask
# Isso garante que as tabelas existam quando a aplicação for iniciada no Render
with app.app_context():
    inicializar_banco_de_dados_pg()


# --- Funções de Gerenciamento de Configuração (JSON files) ---
# Essas funções ainda gerenciam os arquivos JSON.
# Lembre-se que as alterações feitas via frontend NÃO serão persistentes
# entre deploys/reinícios no Render para esses arquivos.
# Para persistência real, você precisaria migrar essas configurações para o PostgreSQL.
def load_generic_config(file_path, default_value={}):
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True) # Garante que o diretório exista
        try:
            with open(file_path, 'w') as f: json.dump(default_value, f, indent=4)
        except IOError: pass
        return default_value
    try:
        with open(file_path, 'r') as f: return json.load(f)
    except (IOError, json.JSONDecodeError): return default_value

def save_generic_config(file_path, data):
    os.makedirs(os.path.dirname(file_path), exist_ok=True) # Garante que o diretório exista
    try:
        with open(file_path, 'w') as f: json.dump(data, f, indent=4)
        return True
    except IOError: return False

def load_strategy_mapping(): return load_generic_config(STRATEGY_MAPPING_FILE)
def save_strategy_mapping(data): return save_generic_config(STRATEGY_MAPPING_FILE, data)
def load_confluence_settings(): return load_generic_config(CONFLUENCE_CONFIG_FILE)
def save_confluence_settings(data): return save_generic_config(CONFLUENCE_CONFIG_FILE, data)
def get_strategy_status(): return load_generic_config(STATUS_FILE)
def save_strategy_status(data): return save_generic_config(STATUS_FILE, data)

def load_telegram_config():
    # Prioriza variáveis de ambiente para tokens/chat_ids
    config_from_file = load_generic_config(TELEGRAM_CONFIG_FILE, default_value={
        "channel_1": {"token": "", "chat_id": ""},
        "channel_2": {"token": "", "chat_id": ""},
        "channel_3": {"token": "", "chat_id": ""}
    })

    for i in range(1, 4):
        token_env = os.environ.get(f'TELEGRAM_TOKEN_{i}')
        chat_id_env = os.environ.get(f'TELEGRAM_CHAT_ID_{i}')
        if token_env:
            config_from_file[f'channel_{i}']['token'] = token_env
        if chat_id_env:
            config_from_file[f'channel_{i}']['chat_id'] = chat_id_env
    return config_from_file

def save_telegram_config(data):
    # Salva no arquivo local, ciente da efemeridade.
    # Para persistência real, defina as variáveis de ambiente no Render.
    return save_generic_config(TELEGRAM_CONFIG_FILE, data)

def load_armed_sequences(): return load_generic_config(ARMED_SEQUENCES_FILE, default_value=[])
def save_armed_sequences(data): return save_generic_config(ARMED_SEQUENCES_FILE, data)
def load_activator_settings(): return load_generic_config(ACTIVATOR_CONFIG_FILE)
def save_activator_settings(data): return save_generic_config(ACTIVATOR_CONFIG_FILE, data)

def carregar_estrategias():
    strategies = []
    if not os.path.exists(STRATEGIES_DIR): return []
    for filename in os.listdir(STRATEGIES_DIR):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = filename[:-3]
            try:
                spec = importlib.util.spec_from_file_location(module_name, os.path.join(STRATEGIES_DIR, filename))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if all(hasattr(module, attr) for attr in ['ID', 'NOME', 'DESCRICAO']):
                    strategies.append({'id': module.ID, 'nome': module.NOME, 'descricao': module.DESCRICAO})
            except Exception as e:
                print(f"!!! ERRO ao carregar a estratégia '{filename}': {e}")
    return sorted(strategies, key=lambda s: s['nome'])

# --- ROTAS PRINCIPAIS ---
@app.route('/')
def index(): return render_template('index.html')
@app.route('/estrategias')
def estrategias_page(): return render_template('estrategias.html')
@app.route('/estatisticas')
def estatisticas_page(): return render_template('estatisticas.html')
@app.route('/configuracao')
def configuracao_page(): return render_template('configuracao.html')

# --- ROTAS DE API ---
@app.route('/api/sinais')
def api_sinais():
    try:
        # Usar get_db() para obter a conexão PostgreSQL
        conn = get_db()
        cursor = conn.cursor()
        
        strategy_statuses = get_strategy_status()
        mapping = load_strategy_mapping()
        confluence_modes = load_confluence_settings()
        activator_modes = load_activator_settings()
        
        signals, is_active, window_end = process_and_filter_signals(
            cursor, strategy_statuses, mapping, confluence_modes, activator_modes
        )
        
        return jsonify({
            "signals": signals,
            "activator_window_active": is_active,
            "activator_window_end": window_end.isoformat() if window_end else None,
            "activator_modes_enabled": activator_modes
        })
    except Exception as e:
        print(f"[ERRO API /sinais]: {e}")
        return jsonify({"erro": str(e)}), 500

def _find_block_end_time(reference_time):
    minute = reference_time.minute
    end_minute_of_block = (minute // 10) * 10 + 9
    block_end = reference_time.replace(minute=end_minute_of_block, second=59, microsecond=999999)
    if block_end < reference_time:
         block_end += timedelta(minutes=10)
    return block_end

@app.route('/api/resultados')
def api_resultados():
    try:
        limite = request.args.get('limite', default=120, type=int)
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT timestamp_iso FROM resultados ORDER BY timestamp_iso DESC LIMIT 1")
        last_result_row = cursor.fetchone()
        latest_result_time = last_result_row['timestamp_iso'] if last_result_row else datetime.now()

        cursor.execute("SELECT MAX(target_timestamp) as max_target FROM sinais WHERE status = 'pending'")
        max_target_row = cursor.fetchone()
        latest_signal_time = max_target_row['max_target'] if max_target_row and max_target_row['max_target'] else datetime.min

        grid_end_reference_time = max(latest_result_time, latest_signal_time, datetime.now())
        grid_end_time = _find_block_end_time(grid_end_reference_time)
        
        num_minutes_needed = (limite + 1) // 2 
        grid_start_time = grid_end_time - timedelta(minutes=num_minutes_needed)
        
        cursor.execute(
            "SELECT id, roll, color, timestamp_iso FROM resultados WHERE timestamp_iso BETWEEN %s AND %s ORDER BY timestamp_iso ASC",
            (grid_start_time, grid_end_time)
        )
        resultados_brutos = cursor.fetchall()
        
        results_by_minute = defaultdict(list)
        for row in resultados_brutos:
            # PostgreSQL retorna datetime objects, não strings
            result_time = row['timestamp_iso']
            minute_key = result_time.strftime("%Y-%m-%d %H:%M")
            results_by_minute[minute_key].append(dict(row))
        
        all_slots = []
        current_minute_time = grid_start_time.replace(second=0, microsecond=0)
        
        while current_minute_time <= grid_end_time:
            minute_key = current_minute_time.strftime("%Y-%m-%d %H:%M")
            time_short = current_minute_time.strftime("%H:%M")
            
            existing_results_in_minute = sorted(results_by_minute.get(minute_key, []), key=lambda x: x['timestamp_iso'])
            
            for result in existing_results_in_minute:
                result_time = result['timestamp_iso'] # Já é datetime
                all_slots.append({
                    'type': 'result', 'id': result['id'], 'roll': result['roll'], 'color': result['color'],
                    'time_short': result_time.strftime("%H:%M"), 'time_full': result_time.strftime("%H:%M:%S")
                })
            
            num_placeholders = 2 - len(existing_results_in_minute)
            for _ in range(num_placeholders):
                all_slots.append({'type': 'placeholder', 'time_short': time_short})

            current_minute_time += timedelta(minutes=1)
        
        final_slots = all_slots[-limite:]
        
        final_rows = []
        for i in range(0, len(final_slots), 20):
            final_rows.append(final_slots[i:i+20])
            
        final_rows.reverse()

        return jsonify(final_rows)

    except Exception as e:
        print(f"[ERRO API /resultados]: {e}")
        return jsonify({"erro": str(e)}), 500


@app.route('/api/config/telegram', methods=['GET'])
def api_get_telegram_config(): return jsonify(load_telegram_config())
@app.route('/api/config/telegram', methods=['POST'])
def api_save_telegram_config():
    data = request.json
    if not isinstance(data, dict): return jsonify({'status': 'erro', 'message': 'Dados inválidos'}), 400
    if save_telegram_config(data): return jsonify({'status': 'sucesso'})
    else: return jsonify({'status': 'erro', 'message': 'Falha ao salvar o arquivo'}), 500

@app.route('/api/estrategias/status')
def api_get_all_status(): return jsonify(get_strategy_status())
@app.route('/api/estrategias/toggle', methods=['POST'])
def api_toggle_estrategia():
    data = request.json; item_id = data.get('id')
    if not item_id: return jsonify({'status': 'erro'}), 400
    status = get_strategy_status(); status[item_id] = not status.get(item_id, False); save_strategy_status(status)
    return jsonify({'status': 'sucesso', 'id': item_id, 'ativo': status[item_id]})

@app.route('/api/estrategias')
def api_listar_estrategias(): return jsonify(carregar_estrategias())
@app.route('/api/estrategias/mapping', methods=['GET'])
def api_get_strategy_mapping(): return jsonify(load_strategy_mapping())
@app.route('/api/estrategias/mapping', methods=['POST'])
def api_save_strategy_mapping():
    data = request.json
    if not isinstance(data, dict): return jsonify({'status': 'erro', 'message': 'Dados inválidos'}), 400
    if save_strategy_mapping(data): return jsonify({'status': 'sucesso'})
    else: return jsonify({'status': 'erro', 'message': 'Falha ao salvar o arquivo de mapeamento'}), 500

@app.route('/api/estrategias/confluence', methods=['GET'])
def api_get_confluence_settings(): return jsonify(load_confluence_settings())
@app.route('/api/estrategias/confluence', methods=['POST'])
def api_save_confluence_settings():
    data = request.json
    if not isinstance(data, dict): return jsonify({'status': 'erro', 'message': 'Dados inválidos'}), 400
    if save_confluence_settings(data): return jsonify({'status': 'sucesso'})
    else: return jsonify({'status': 'erro', 'message': 'Falha ao salvar o arquivo de confluência'}), 500

@app.route('/api/estrategias/activator', methods=['GET'])
def api_get_activator_settings(): return jsonify(load_activator_settings())
@app.route('/api/estrategias/activator', methods=['POST'])
def api_save_activator_settings():
    data = request.json
    if not isinstance(data, dict): return jsonify({'status': 'erro', 'message': 'Dados inválidos'}), 400
    if save_activator_settings(data): return jsonify({'status': 'sucesso'})
    else: return jsonify({'status': 'erro', 'message': 'Falha ao salvar o arquivo do ativador'}), 500

@app.route('/api/sequence_alerts')
def api_sequence_alerts():
    armed_sequences = load_armed_sequences()
    if not armed_sequences: return jsonify([])
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT color FROM resultados ORDER BY timestamp_iso DESC LIMIT 7")
    latest_results = [row['color'] for row in cursor.fetchall()]
    latest_results.reverse()
    active_alerts = []
    for armed_sequence in armed_sequences:
        n = len(armed_sequence)
        if len(latest_results) >= n and latest_results[-n:] == armed_sequence:
            active_alerts.append({"id": f"visual-{'-'.join(map(str, armed_sequence))}", "status": "visual", "sequence": armed_sequence, "prediction": "Branco"})
        if n > 1 and len(latest_results) >= n - 1 and latest_results[-(n-1):] == armed_sequence[:n-1]:
            active_alerts.append({"id": f"sound-{'-'.join(map(str, armed_sequence[:n-1]))}", "status": "sound", "sequence": armed_sequence[:n-1]})
    return jsonify(active_alerts)

@app.route('/api/stats/interval_averages')
def api_stats_interval_averages():
    try:
        conn = get_db()
        cursor = conn.cursor()
        six_hours_ago = datetime.now() - timedelta(hours=6)
        query = "SELECT timestamp_iso FROM resultados WHERE color = 'Branco' AND timestamp_iso >= %s ORDER BY timestamp_iso ASC"
        cursor.execute(query, (six_hours_ago,))
        white_timestamps = [row['timestamp_iso'] for row in cursor.fetchall()] # Já são datetime objects
        default_response = {"media_curta": 0, "media_longa": 0, "total_intervalos": 0}
        if len(white_timestamps) < 2: return jsonify(default_response)
        all_intervals = [round((white_timestamps[i] - white_timestamps[i-1]).total_seconds() / 60) for i in range(1, len(white_timestamps))]
        if not all_intervals or len(all_intervals) < 4:
            default_response["total_intervalos"] = len(all_intervals)
            return jsonify(default_response)
        sorted_intervals = sorted(all_intervals)
        midpoint = len(sorted_intervals) // 2
        lower_half = sorted_intervals[:midpoint]
        upper_half = sorted_intervals[midpoint:]
        if not lower_half:
            return jsonify(default_response)
        media_curta = sum(lower_half) / len(lower_half)
        media_longa = sum(upper_half) / len(upper_half)
        return jsonify({
            "media_curta": round(media_curta, 1),
            "media_longa": round(media_longa, 1),
            "total_intervalos": len(all_intervals)
        })
    except Exception as e:
        print(f"[ERRO AO CALCULAR MÉDIAS DE INTERVALO]: {e}"); return jsonify({"erro": str(e)}), 500

@app.route('/api/stats/panel_accuracy')
def api_get_panel_accuracy():
    try:
        mapping = load_strategy_mapping() 
        if not mapping:
            return jsonify({})
        panel_stats = {"1": {"hits": 0, "misses": 0},"2": {"hits": 0, "misses": 0},"3": {"hits": 0, "misses": 0}}
        panel_to_strategies = defaultdict(list)
        for strategy_id, panel_id in mapping.items():
            if panel_id in panel_stats:
                panel_to_strategies[panel_id].append(strategy_id)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT strategy_id, hits, misses FROM estrategia_stats")
        all_strategy_stats = cursor.fetchall()
        for stat in all_strategy_stats:
            strategy_id = stat['strategy_id']
            for panel_id, strategies in panel_to_strategies.items():
                if strategy_id in strategies:
                    panel_stats[panel_id]['hits'] += stat['hits']
                    panel_stats[panel_id]['misses'] += stat['misses']
                    break
        return jsonify(panel_stats)
    except Exception as e:
        print(f"[ERRO AO BUSCAR STATS DOS PAINÉIS]: {e}")
        return jsonify({"erro": str(e)}), 500

@app.route('/api/stats/sequences')
def api_stats_sequences():
    try:
        length = request.args.get('length', 4, type=int)
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        conn = get_db()
        cursor = conn.cursor()
        query = "SELECT color FROM resultados WHERE timestamp_iso >= %s ORDER BY timestamp_iso ASC"
        cursor.execute(query, (today_start,))
        all_colors_today = [row['color'] for row in cursor.fetchall()]
        sequences_before_white = []
        for i, color in enumerate(all_colors_today):
            if color == 'Branco' and i >= length:
                sequence = tuple(all_colors_today[i-length:i])
                sequences_before_white.append(sequence)
        sequence_counts = Counter(sequences_before_white)
        most_common = sequence_counts.most_common(10)
        formatted_sequences = [{'sequence': list(seq), 'count': count} for seq, count in most_common]
        return jsonify(formatted_sequences)
    except Exception as e:
        print(f"[ERRO API /api/stats/sequences]: {e}")
        return jsonify({"erro": str(e)}), 500

@app.route('/api/sequences/armed', methods=['GET'])
def api_get_armed_sequences():
    return jsonify(load_armed_sequences())
@app.route('/api/sequences/arm', methods=['POST'])
def api_arm_sequence():
    data = request.json
    if not isinstance(data, list):
        return jsonify({'status': 'erro', 'message': 'Dados inválidos, esperado uma lista.'}), 400
    if save_armed_sequences(data):
        return jsonify({'status': 'sucesso'})
    else:
        return jsonify({'status': 'erro', 'message': 'Falha ao salvar o arquivo de sequências.'}), 500

@app.route('/api/stats/hourly_colors')
def api_stats_hourly_colors():
    try:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        conn = get_db()
        cursor = conn.cursor()
        query = "SELECT color, timestamp_iso FROM resultados WHERE timestamp_iso >= %s"
        cursor.execute(query, (today_start,))
        results = cursor.fetchall()
        hourly_counts = {f"{h:02d}": {"Preto": 0, "Vermelho": 0, "Branco": 0} for h in range(24)}
        for row in results:
            hour_key = row['timestamp_iso'].strftime('%H') # Já é datetime
            color = row['color']
            if color in hourly_counts[hour_key]:
                hourly_counts[hour_key][color] += 1
        return jsonify(hourly_counts)
    except Exception as e:
        print(f"[ERRO API /api/stats/hourly_colors]: {e}")
        return jsonify({"erro": str(e)}), 500

@app.route('/api/stats/white_minutes')
def api_stats_white_minutes():
    try:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        conn = get_db()
        cursor = conn.cursor()
        query = "SELECT timestamp_iso FROM resultados WHERE color = 'Branco' AND timestamp_iso >= %s"
        cursor.execute(query, (today_start,))
        minutes = [row['timestamp_iso'].minute for row in cursor.fetchall()] # Já são datetime
        minute_counts = Counter(minutes)
        labels = [f"{m:02d}" for m in range(60)]
        data = [minute_counts.get(m, 0) for m in range(60)]
        return jsonify({"labels": labels, "data": data})
    except Exception as e:
        print(f"[ERRO API /api/stats/white_minutes]: {e}")
        return jsonify({"erro": str(e)}), 500

# Não usar app.run() diretamente em produção com Gunicorn
# if __name__ == '__main__':
#     load_strategy_mapping()
#     load_confluence_settings()
#     load_activator_settings()
#     load_generic_config(ACTIVATOR_STATE_FILE, default_value={"last_activation_timestamp": None})
#     get_strategy_status()
#     load_telegram_config()
#     load_armed_sequences()
    
#     app.run(debug=True, port=5005)

