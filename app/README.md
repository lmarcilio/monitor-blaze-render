# 🤖 Monitor de Estratégias Blaze

Este é um sistema completo para monitorar os resultados da roleta Blaze Double, aplicar um conjunto customizável de estratégias em tempo real e enviar sinais de entrada através do Telegram.

## ✨ Funcionalidades

- **Coletor de Dados:** Um script (`coletor_blaze.py`) que busca os últimos resultados da roleta em tempo real e os armazena em um banco de dados SQLite.
- **Mecanismo de Estratégias:** Suporte para múltiplas estratégias modulares (arquivos `estrategia_*.py`), que são verificadas a cada novo resultado.
- **Painel Web (Dashboard):** Uma interface Flask (`app.py`) para visualizar:
    - Resultados recentes em uma grade.
    - Sinais de entrada gerados pelas estratégias, organizados em painéis.
    - Estatísticas detalhadas sobre o jogo (frequência de cores, sequências, etc.).
- **Notificações via Telegram:** Integração para enviar alertas de sinais e confluências para canais configuráveis.
- **Alta Customização:** Permite ativar/desativar estratégias, configurar modos de confluência e mapear quais estratégias aparecem em cada painel da interface.

## 🚀 Como Executar

1.  **Clone o repositório (se necessário):**
    ```bash
    git clone https://github.com/SeuUsuario/monitor-blaze-strategies.git
    cd monitor-blaze-strategies
    ```

2.  **Crie e ative um ambiente virtual (recomendado):**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # Mac/Linux
    source venv/bin/activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure as Notificações:**
    - Renomeie o arquivo `telegram_config.json.example` para `telegram_config.json`.
    - Preencha com os tokens e chat IDs do seu bot do Telegram.
    *(Este passo não é necessário se você já tem seu arquivo de configuração, mas é uma boa prática para projetos compartilhados).*

5.  **Inicie o Coletor:**
    Abra um terminal e execute:
    ```bash
    python coletor_blaze.py
    ```

6.  **Inicie a Aplicação Web:**
    Abra **outro** terminal e execute:
    ```bash
    flask --app app run
    ```
    Acesse o painel em `http://127.0.0.1:5000` no seu navegador.