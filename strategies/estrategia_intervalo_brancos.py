# strategies/estrategia_intervalo_brancos.py

# --- Metadados Obrigatórios ---
ID = "intervalo_brancos"
NOME = "Análise de Intervalo entre Brancos"
DESCRICAO = "Calcula e exibe a frequência de cada intervalo de tempo (em minutos) entre os resultados 'Branco' ocorridos nas últimas 6 horas. Ordenado pelo mais frequente."

# --- Função Principal de Verificação (CORRIGIDA) ---
def verificar(historico, cursor):
    """
    Esta estratégia é apenas para exibição de dados na interface
    e não gera sinais de entrada. Portanto, sempre retorna None.
    A lógica de cálculo real fica na API do Flask.
    """
    return None