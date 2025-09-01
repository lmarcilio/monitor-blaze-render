# telegram_notifier.py

import requests
import json
import os
from datetime import datetime

# --- Configurações e Caminhos ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STRATEGIES_DIR = os.path.join(BASE_DIR, '..', 'strategies')
TELEGRAM_CONFIG_FILE = os.path.join(STRATEGIES_DIR, 'telegram_config.json')

MESSAGE_TEMPLATES = {
    '1': "🔥🔥🔥ESTRATÉGIA 1🔥🔥🔥\n⚪️ {}",
    '2': "🌀🌀🌀ESTRATÉGIA 2🌀🌀🌀\n⚪️ {}",
    '3': "🔆🔆🔆ESTRATÉGIA 3🔆🔆🔆\n⚪️ {}",
    'default': "Sinal: {}"
}

# --- Funções Internas ---
def _load_telegram_config():
    try:
        with open(TELEGRAM_CONFIG_FILE, 'r') as f: return json.load(f)
    except (IOError, json.JSONDecodeError):
        print("[TELEGRAM] Erro: Não foi possível ler o arquivo de configuração do Telegram.")
        return None

def _get_channel_credentials(channel_key):
    panel_num = channel_key.split('_')[1] # Extrai '1', '2' ou '3'
    token = os.environ.get(f'TELEGRAM_TOKEN_{panel_num}')
    chat_id = os.environ.get(f'TELEGRAM_CHAT_ID_{panel_num}')

    if token and chat_id:
        return token, chat_id
    
    config = _load_telegram_config()
    if config:
        channel_config = config.get(channel_key, {})
        return channel_config.get("token"), channel_config.get("chat_id")
    
    return None, None

def _format_signal_message(panel_id, target_time):
    # target_time já deve ser um datetime object aqui
    horario_formatado = target_time.strftime('%H:%M')
    template = MESSAGE_TEMPLATES.get(str(panel_id), MESSAGE_TEMPLATES['default'])
    return template.format(horario_formatado)

def _format_confluence_message(panel_id, target_time, emojis):
    # target_time já deve ser um datetime object aqui
    horario_formatado = target_time.strftime('%H:%M')
    
    panel_template = MESSAGE_TEMPLATES.get(str(panel_id), "Sinal de Confluência")
    header = panel_template.split('\n')[0]
    
    emojis_str = " ".join(emojis) if emojis else ""
    
    return f"{header}\n{emojis_str}\n⚪️ {horario_formatado}"

# --- Funções de Envio e Edição ---
def send_telegram_message(message, channel_key):
    token, chat_id = _get_channel_credentials(channel_key)
    if not token or not chat_id:
        print(f"⚠️ [TELEGRAM] Credenciais não configuradas para '{channel_key}'.")
        return None
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
    try:
        response = requests.post(api_url, data=payload, timeout=10)
        if response.status_code == 200:
            print(f"🚀 [TELEGRAM] Notificação enviada com sucesso para '{channel_key}'!")
            return response.json()['result']['message_id']
        else:
            print(f"⚠️ [TELEGRAM] Erro ao enviar para Telegram ({channel_key}): {response.text}")
            return None
    except requests.RequestException as e:
        print(f"⚠️ [TELEGRAM] Falha de conexão com a API do Telegram ({channel_key}): {e}")
        return None

def _edit_telegram_message(new_text, message_id, channel_key):
    token, chat_id = _get_channel_credentials(channel_key)
    if not token or not chat_id or not message_id: return False
    api_url = f"https://api.telegram.org/bot{token}/editMessageText"
    payload = {'chat_id': chat_id, 'message_id': message_id, 'text': new_text, 'parse_mode': 'HTML'}
    try:
        response = requests.post(api_url, data=payload, timeout=10)
        return response.status_code == 200
    except requests.RequestException: return False

def edit_message_to_hit(panel_id, target_time, message_id, channel_key):
    original_message = _format_signal_message(panel_id, target_time)
    new_text = f"✅✅✅ <b>ACERTO</b> ✅✅✅\n\n{original_message}"
    if _edit_telegram_message(new_text, message_id, channel_key):
        print(f"✅ [TELEGRAM] Mensagem {message_id} editada para ACERTO.")
    else:
        print(f"⚠️ [TELEGRAM] Falha ao editar mensagem {message_id} para ACERTO.")

def edit_message_to_miss(panel_id, target_time, message_id, channel_key):
    original_message = _format_signal_message(panel_id, target_time)
    lines = original_message.split('\n'); lines[-1] = f"<s>{lines[-1]}</s>"; striked_message = "\n".join(lines)
    new_text = f"❌❌❌ <b>ERRO</b> ❌❌❌\n\n{striked_message}"
    if _edit_telegram_message(new_text, message_id, channel_key):
        print(f"❌ [TELEGRAM] Mensagem {message_id} editada para ERRO.")
    else:
        print(f"⚠️ [TELEGRAM] Falha ao editar mensagem {message_id} para ERRO.")

def edit_confluence_to_hit(panel_id, target_time, message_id, channel_key, emojis):
    original_message = _format_confluence_message(panel_id, target_time, emojis)
    new_text = f"✅✅✅ <b>ACERTO</b> ✅✅✅\n\n{original_message}"
    if _edit_telegram_message(new_text, message_id, channel_key):
        print(f"✅ [TELEGRAM] Mensagem de confluência {message_id} editada para ACERTO.")
    else:
        print(f"⚠️ [TELEGRAM] Falha ao editar mensagem de confluência {message_id} para ACERTO.")

def edit_confluence_to_miss(panel_id, target_time, message_id, channel_key, emojis):
    original_message = _format_confluence_message(panel_id, target_time, emojis)
    lines = original_message.split('\n'); lines[-1] = f"<s>{lines[-1]}</s>"; striked_message = "\n".join(lines)
    new_text = f"❌❌❌ <b>ERRO</b> ❌❌❌\n\n{striked_message}"
    if _edit_telegram_message(new_text, message_id, channel_key):
        print(f"❌ [TELEGRAM] Mensagem de confluência {message_id} editada para ERRO.")
    else:
        print(f"⚠️ [TELEGRAM] Falha ao editar mensagem de confluência {message_id} para ERRO.")

# --- Funções de Notificação ---
def send_signal_notification(panel_id, target_time):
    mensagem = _format_signal_message(panel_id, target_time)
    return send_telegram_message(mensagem, channel_key=f'channel_{panel_id}')

def send_confluence_notification(panel_id, target_time, emojis):
    mensagem = _format_confluence_message(panel_id, target_time, emojis)
    return send_telegram_message(mensagem, channel_key=f'channel_{panel_id}')

