# coletor_blaze.py

import requests
import json
import time
import sqlite3 # Ainda pode ser útil para alguma lógica local, mas não para o DB principal
import os
import importlib.util
from collections import defaultdict, Counter
from datetime import datetime, timezone, timedelta
import psycopg2 # Importar para PostgreSQL
from psycopg2 import extras # Para usar RowFactory similar ao SQLite

# Importa as funções de notificação do telegram_notifier
from telegram_notifier import send_signal_notification, send_confluence_notification, edit_message_to_hit, edit_message_to_miss, edit_confluence_to_hit, edit_confluence_to_miss

# Importa a lógica de sinais do arquivo centralizado
from signal_logic import process_and_filter_signals

# --- Configuração de Caminhos ---
script_dir = os.path.dirname(os.path.abspath(__file__)) 
base_dir = os.path.dirname(script_dir)
strategies_folder = os.path.join(base_dir, 'strategies')
# db_folder = os.path.join(base_dir, 'database') # Não precisamos mais de uma pasta local para o DB
# db_path = os.path.join(db_folder, 'blaze_data.db') # Não precisamos mais de um caminho local para o DB

status_file_path = os.path.join(strategies_folder, 'strategy_status.json')
MAPPING_CONFIG_PATH = os.path.join(strategies_folder, 'strategyColumnMapping.json')
CONFLUENCE_CONFIG_PATH = os.path.join(strategies_folder, 'confluenceModeSettings.json')
ACTIVATOR_CONFIG_PATH = os.path.join(strategies_folder, 'activatorModeSettings.json')
ACTIVATOR_STATE_FILE = os.path.join(strategies_folder, 'activator_state.json')

# --- Constantes ---
url = "https://blaze.bet.br/api/singleplayer-originals/originals/roulette_games/recent/1"
MAPA_CORES = {1: "Vermelho", 2: "Preto", 0: "Branco"}
last_notifier_warning_time = None

# Variável global para armazenar as estratégias carregadas
todas_estrategias = {}

# --- Configuração do PostgreSQL para o Coletor ---
DATABASE_URL = os.environ.get('DATABASE_URL') # Render fornece isso automaticamente para o DB gerenciado

def get_db_connection_collector():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL não configurada. Conexão com o banco de dados falhou.")
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

# --- FUNÇÕES DO COLETOR ---

def ensure_config_files_exist():
    os.makedirs(strategies_folder, exist_ok=True)
    configs_to_check = {
        MAPPING_CONFIG_PATH: {},
        CONFLUENCE_CONFIG_PATH: {},
        ACTIVATOR_CONFIG_PATH: {},
        status_file_path: {},
        ACTIVATOR_STATE_FILE: {"last_activation_timestamp": None}
    }
    for path, default in configs_to_check.items():
        if not os.path.exists(path):
            with open(path, 'w') as f: json.dump(default, f, indent=4)
            print(f"Arquivo de configuração criado: {os.path.basename(path)}")
            
# A inicialização do esquema do DB será feita pelo app.py no Web Service
# Não precisamos mais de inicializar_banco_de_dados() aqui no coletor.
# def inicializar_banco_de_dados():
#     os.makedirs(db_folder, exist_ok=True)
#     conn = sqlite3.connect(db_path)
#     cursor = conn.cursor()
#     # ... (criação de tabelas SQLite) ...
#     conn.commit()
#     conn.close()

def salvar_no_banco(conn, game_id, data_formatada, data_iso_db, roll, cor):
    try:
        cursor = conn.cursor()
        # Usar INSERT INTO ... ON CONFLICT DO NOTHING para PostgreSQL
        cursor.execute("""
            INSERT INTO resultados (id, created_at, roll, color, timestamp_iso)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING;
        """, (game_id, data_formatada, roll, cor, data_iso_db))
        conn.commit()
    except psycopg2.Error as e: print(f"\n[ERRO DE BANCO DE DADOS]: {e}")

def salvar_sinal_no_banco(conn, strategy_id, strategy_name, signal_data):
    cursor = conn.cursor()
    trigger_id = signal_data['trigger_id']
    num_targets = len(signal_data.get('targets', []))
    if num_targets == 0: return
    
    # Verificar se o sinal já existe para evitar duplicatas
    # Usar EXISTS para PostgreSQL
    query_check = """
        SELECT EXISTS (
            SELECT 1 FROM sinais 
            WHERE trigger_id = %s AND strategy_id = %s AND target_timestamp = %s
        );
    """
    
    signals_added_count = 0
    context_message = signal_data['message']

    for target_datetime in signal_data['targets']:
        target_iso = target_datetime # Já é um datetime object
        
        cursor.execute(query_check, (trigger_id, strategy_id, target_iso))
        if cursor.fetchone()[0]: # Se já existe, pula
            continue

        cursor.execute("""
            INSERT INTO sinais (trigger_id, strategy_id, strategy_name, message, target_timestamp)
            VALUES (%s, %s, %s, %s, %s);
        """, (trigger_id, strategy_id, strategy_name, context_message, target_iso))
        signals_added_count += 1
    
    if signals_added_count > 0:
        # Usar INSERT INTO ... ON CONFLICT (PRIMARY KEY) DO UPDATE para PostgreSQL
        cursor.execute("""
            INSERT INTO estrategia_stats (strategy_id, strategy_name, total_signals)
            VALUES (%s, %s, %s)
            ON CONFLICT (strategy_id) DO UPDATE SET
            total_signals = estrategia_stats.total_signals + EXCLUDED.total_signals,
            strategy_name = EXCLUDED.strategy_name;
        """, (strategy_id, strategy_name, signals_added_count))
        print(f"\n✅ SINAL GERADO! Estratégia '{strategy_name}' acionada. {signals_added_count} alvo(s) salvo(s).")
    conn.commit()


def load_frontend_config():
    # No coletor, também precisamos carregar as configurações de arquivo
    # mas cientes de que elas podem ser efêmeras no Render.
    # Para o Telegram, o telegram_notifier já lê de variáveis de ambiente.
    try:
        with open(MAPPING_CONFIG_PATH, 'r') as f: mapping = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): mapping = {}
    try:
        with open(CONFLUENCE_CONFIG_PATH, 'r') as f: confluence_modes = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): confluence_modes = {}
    try:
        with open(ACTIVATOR_CONFIG_PATH, 'r') as f: activator_modes = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): activator_modes = {}
    return mapping, confluence_modes, activator_modes

def processar_e_enviar_notificacoes():
    global todas_estrategias
    
    status_ativo = ler_status_ativo()
    mapping, confluence_modes, activator_modes = load_frontend_config()
    
    if not any(status_ativo.values()) or not mapping:
        return

    conn = None
    try:
        conn = get_db_connection_collector()
        # Configura o cursor para retornar linhas como dicionários
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        signals, _, _ = process_and_filter_signals(
            cursor, status_ativo, mapping, confluence_modes, activator_modes
        )

        if not signals: return

        cursor.execute("SELECT notification_key FROM notificacoes_enviadas")
        sent_notifications_db = {row['notification_key'] for row in cursor.fetchall()}

        # Agrupa os sinais pela notificação que eles gerariam para evitar duplicatas.
        grouped_notifications = defaultdict(list)
        for signal in signals:
            key = (signal['panel_id'], signal['target_timestamp'], signal['type'])
            grouped_notifications[key].append(signal)

        # Agora, processa cada grupo de notificação único.
        for (panel_id, timestamp, signal_type), signal_group in grouped_notifications.items():
            
            # Cria uma chave de notificação única baseada no painel e horário.
            if signal_type == 'individual':
                notification_key = f"individual-{panel_id}-{timestamp}"
            elif signal_type == 'confluence':
                notification_key = f"confluence-{panel_id}-{timestamp}"
            else:
                continue

            # Se esta notificação exata já foi enviada, pula.
            if notification_key in sent_notifications_db:
                continue

            # Envia UMA notificação para este grupo.
            horario_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            message_id = None

            if signal_type == 'confluence':
                first_signal = signal_group[0] 
                emojis = []
                if todas_estrategias and 'strategy_names' in first_signal:
                     involved_strategy_ids = [sid for sid, s_mod in todas_estrategias.items() if s_mod.NOME in first_signal['strategy_names']]
                     emojis = [todas_estrategias.get(sid).EMOJI for sid in involved_strategy_ids if todas_estrategias.get(sid) and hasattr(todas_estrategias.get(sid), 'EMOJI')]
                message_id = send_confluence_notification(panel_id, horario_dt, emojis)
            
            elif signal_type == 'individual':
                message_id = send_signal_notification(panel_id, horario_dt)

            # Se a mensagem foi enviada, atualiza o banco de dados para TODOS os sinais no grupo.
            if message_id:
                cursor.execute("INSERT INTO notificacoes_enviadas (notification_key) VALUES (%s) ON CONFLICT (notification_key) DO NOTHING;", (notification_key,))
                
                all_db_ids = []
                for s in signal_group:
                    all_db_ids.extend(s.get('db_ids', []))
                
                if all_db_ids:
                    # Usar UNNEST para atualizar múltiplos IDs em PostgreSQL
                    cursor.execute("""
                        UPDATE sinais SET telegram_message_id = %s
                        WHERE id IN (SELECT unnest(%s::int[]));
                    """, (message_id, all_db_ids))
                
                conn.commit()

    except Exception as e:
        print(f"[ERRO NO PROCESSADOR DE NOTIFICAÇÕES]: {e}")
    finally:
        if conn: conn.close()
        
def gerenciar_sinais_antigos():
    global todas_estrategias
    try:
        conn = get_db_connection_collector()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        agora = datetime.now()
        limite_expiracao = agora - timedelta(minutes=2)
        
        cursor.execute("SELECT id, strategy_id, telegram_message_id, target_timestamp FROM sinais WHERE status = 'pending' AND target_timestamp < %s", (limite_expiracao,))
        sinais_expirados = cursor.fetchall()
        
        if sinais_expirados:
            mapping, confluence_modes, _ = load_frontend_config()
            expired_strategy_ids = []
            for signal in sinais_expirados:
                expired_strategy_ids.append(signal['strategy_id'])
                if signal['telegram_message_id']:
                    panel_id = mapping.get(signal['strategy_id'])
                    if panel_id and panel_id != 'none':
                        target_time = signal['target_timestamp'] # Já é datetime
                        if confluence_modes.get(str(panel_id)):
                            cursor.execute("SELECT DISTINCT strategy_id FROM sinais WHERE telegram_message_id = %s", (signal['telegram_message_id'],))
                            confluence_strategy_ids = [row['strategy_id'] for row in cursor.fetchall()]
                            emojis = []
                            if todas_estrategias:
                                emojis = [todas_estrategias.get(sid).EMOJI for sid in confluence_strategy_ids if todas_estrategias.get(sid) and hasattr(todas_estrategias.get(sid), 'EMOJI')]
                            edit_confluence_to_miss(panel_id=panel_id, target_time=target_time, message_id=signal['telegram_message_id'], channel_key=f"channel_{panel_id}", emojis=emojis)
                        else:
                            edit_message_to_miss(panel_id=panel_id, target_time=target_time, message_id=signal['telegram_message_id'], channel_key=f"channel_{panel_id}")

            # Atualizar contadores de erros
            for strategy_id, miss_count in Counter(expired_strategy_ids).items():
                cursor.execute("""
                    UPDATE estrategia_stats SET misses = misses + %s
                    WHERE strategy_id = %s;
                """, (miss_count, strategy_id))
            
            cursor.execute("UPDATE sinais SET status = 'expired' WHERE status = 'pending' AND target_timestamp < %s", (limite_expiracao,))
            print(f"🕰️  {len(sinais_expirados)} alvo(s) pendente(s) foram marcados como 'expirado' (erro).")
        
        limite_delecao = agora - timedelta(hours=2)
        cursor.execute("DELETE FROM sinais WHERE status IN ('hit', 'expired') AND target_timestamp < %s", (limite_delecao,))
        cursor.execute("DELETE FROM notificacoes_enviadas WHERE notification_key IN (SELECT notification_key FROM sinais WHERE status IN ('hit', 'expired') AND target_timestamp < %s)", (limite_delecao,))
        
        limite_delecao_resultados = agora - timedelta(hours=49)
        cursor.execute("DELETE FROM resultados WHERE timestamp_iso < %s", (limite_delecao_resultados,))
        conn.commit()
        conn.close()
    except psycopg2.Error as e: print(f"\n[ERRO AO GERENCIAR DADOS ANTIGOS]: {e}")

def verificar_acertos(horario_do_branco):
    global todas_estrategias
    try:
        conn = get_db_connection_collector()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("SELECT id, target_timestamp, strategy_id, telegram_message_id FROM sinais WHERE status = 'pending'")
        alvos_pendentes = cursor.fetchall()
        horario_do_branco_naive = horario_do_branco.replace(tzinfo=None)
        
        if not alvos_pendentes: 
            conn.close()
            return
        
        mapping, confluence_modes, _ = load_frontend_config()

        for alvo in alvos_pendentes:
            alvo_dt = alvo['target_timestamp'] # Já é datetime
            # Verifica se o branco ocorreu dentro de 1 minuto antes ou depois do alvo
            if (alvo_dt - timedelta(minutes=1)) <= horario_do_branco_naive <= (alvo_dt + timedelta(minutes=1)):
                print(f"\n🎯 ACERTO! O branco das {horario_do_branco.strftime('%H:%M:%S')} atingiu o alvo da estratégia {alvo['strategy_id']}.")
                cursor.execute("UPDATE sinais SET status = 'hit' WHERE id = %s", (alvo['id'],))
                cursor.execute("UPDATE estrategia_stats SET hits = hits + 1 WHERE strategy_id = %s", (alvo['strategy_id'],))
                conn.commit()
                
                if alvo['telegram_message_id']:
                    panel_id = mapping.get(alvo['strategy_id'])
                    if panel_id and panel_id != 'none':
                        if confluence_modes.get(str(panel_id)):
                            cursor.execute("SELECT DISTINCT strategy_id FROM sinais WHERE telegram_message_id = %s", (alvo['telegram_message_id'],))
                            confluence_strategy_ids = [row['strategy_id'] for row in cursor.fetchall()]
                            emojis = []
                            if todas_estrategias:
                                emojis = [todas_estrategias.get(sid).EMOJI for sid in confluence_strategy_ids if todas_estrategias.get(sid) and hasattr(todas_estrategias.get(sid), 'EMOJI')]
                            edit_confluence_to_hit(panel_id=panel_id, target_time=alvo_dt, message_id=alvo['telegram_message_id'], channel_key=f"channel_{panel_id}", emojis=emojis)
                        else:
                            edit_message_to_hit(panel_id=panel_id, target_time=alvo_dt, message_id=alvo['telegram_message_id'], channel_key=f"channel_{panel_id}")
        conn.close()
    except psycopg2.Error as e: print(f"\n[ERRO AO VERIFICAR ACERTOS]: {e}")

def carregar_estrategias():
    estrategias = {}
    if not os.path.exists(strategies_folder): return {}
    for filename in os.listdir(strategies_folder):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = filename[:-3]
            module_path = os.path.join(strategies_folder, filename)
            try:
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
                if hasattr(module, 'ID') and hasattr(module, 'verificar'):
                    estrategias[module.ID] = module
            except Exception as e: print(f"Erro ao carregar estratégia '{filename}': {e}")
    return estrategias

def ler_status_ativo():
    try:
        if os.path.exists(status_file_path):
            with open(status_file_path, 'r') as f: return json.load(f)
    except (IOError, json.JSONDecodeError): return {}
    return {}

def coletar_dados_roleta():
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Erro ao coletar dados da roleta: {e}")
        return None

if __name__ == "__main__":
    # O coletor não precisa inicializar o esquema do DB, o Web Service já faz isso.
    # Mas ele precisa garantir que os arquivos de configuração JSON existam.
    ensure_config_files_exist()
    todas_estrategias = carregar_estrategias() # Popula a variável global
    print(f"Estratégias carregadas: {', '.join([s.NOME for s in todas_estrategias.values()])}")
    
    ultimo_id_processado = None
    print("--------------------------------------------------")
    print(">>>     COLETOR DE RESULTADOS INICIADO     <<<")
    print("--------------------------------------------------")

    while True:
        conn_collector = None # Definir conn_collector aqui
        try:
            conn_collector = get_db_connection_collector() # Obter conexão para o loop
            cursor_collector = conn_collector.cursor(cursor_factory=psycopg2.extras.RealDictCursor) # Cursor para o coletor
            
            # Passar o cursor para as funções que precisam dele
            gerenciar_sinais_antigos() 
            processar_e_enviar_notificacoes() # Esta função já obtém sua própria conexão
            
            dados_recentes = coletar_dados_roleta()
            
            if dados_recentes and isinstance(dados_recentes, list) and len(dados_recentes) > 0:
                if dados_recentes[0].get('id') != ultimo_id_processado:
                    ultimo_id_processado = dados_recentes[0].get('id')
                    
                    jogo_recente = dados_recentes[0]
                    if all(k in jogo_recente for k in ['id', 'created_at', 'color', 'roll']):
                        try:
                            utc_time = datetime.strptime(jogo_recente['created_at'], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
                            local_time = utc_time.astimezone()
                            cor_recente = MAPA_CORES.get(jogo_recente['color'])
                            
                            salvar_no_banco(conn_collector, jogo_recente['id'], local_time.strftime("%d/%m/%Y %H:%M:%S"), local_time, jogo_recente['roll'], cor_recente) # Passar local_time como datetime

                            if cor_recente == "Branco":
                                verificar_acertos(local_time) # Esta função já obtém sua própria conexão

                            statuses = ler_status_ativo()
                            estrategias_ativas = {sid: s for sid, s in todas_estrategias.items() if statuses.get(sid, False)}

                            if estrategias_ativas:
                                # Usar o cursor_collector para buscar histórico
                                cursor_collector.execute("SELECT id, roll, color, timestamp_iso FROM resultados ORDER BY timestamp_iso DESC LIMIT 50")
                                historico_completo = cursor_collector.fetchall()
                                
                                if historico_completo:
                                    for strategy_id, strategy_module in estrategias_ativas.items():
                                        try:
                                            # Passar o cursor_collector para a função verificar da estratégia
                                            resultado_sinal = strategy_module.verificar(historico_completo, cursor_collector)
                                            sinais_a_salvar = []
                                            if resultado_sinal:
                                                if isinstance(resultado_sinal, list):
                                                    sinais_a_salvar.extend(resultado_sinal)
                                                elif isinstance(resultado_sinal, dict):
                                                    sinais_a_salvar.append(resultado_sinal)

                                            for sinal_data in sinais_a_salvar:
                                                if sinal_data and sinal_data.get('targets'):
                                                    salvar_sinal_no_banco(conn_collector, strategy_id, strategy_module.NOME, sinal_data)
                                        except Exception as e:
                                            print(f"[ERRO na execução da ESTRATÉGIA {strategy_module.NOME}]: {e}")
                        
                        except Exception as e:
                            print(f"Erro ao processar resultado: {e}")
                
        finally:
            if conn_collector: conn_collector.close() # Fechar a conexão no final do loop
        
        time.sleep(2)

