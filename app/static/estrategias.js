// static/estrategias.js

document.addEventListener('DOMContentLoaded', () => {
    const strategyListContainer = document.getElementById('strategy-list');
    const strategyCardTemplate = document.getElementById('strategy-card-template');
    const confluenceToggles = document.querySelectorAll('.confluence-toggle');
    const activatorToggles = document.querySelectorAll('.activator-toggle');

    const loadSettings = (key, defaultValue = {}) => {
        try {
            const settings = localStorage.getItem(key);
            return settings ? JSON.parse(settings) : defaultValue;
        } catch (e) {
            console.error(`Erro ao carregar configurações de ${key}:`, e);
            return defaultValue;
        }
    };
    const saveSettings = (key, settings) => localStorage.setItem(key, JSON.stringify(settings));

    const saveConfigToServer = async (endpoint, settings) => {
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            if (!response.ok) {
                throw new Error(`Falha ao salvar configuração em ${endpoint}`);
            }
            console.log(`Configuração salva em ${endpoint}:`, settings);
        } catch (error) {
            console.error(error);
            alert("ERRO: Não foi possível salvar a configuração no servidor.");
        }
    };

    const saveConfluenceSetting = (panel, isEnabled) => {
        const settings = loadSettings('confluenceModeSettings');
        settings[panel] = isEnabled;
        saveSettings('confluenceModeSettings', settings);
        saveConfigToServer('/api/estrategias/confluence', settings);
    };

    const saveActivatorSetting = (panel, isEnabled) => {
        const settings = loadSettings('activatorModeSettings');
        settings[panel] = isEnabled;
        saveSettings('activatorModeSettings', settings);
        saveConfigToServer('/api/estrategias/activator', settings);
    };

    const saveStrategyMapping = (strategyId, column) => {
        const mapping = loadSettings('strategyColumnMapping');
        mapping[strategyId] = column;
        saveSettings('strategyColumnMapping', mapping);
        saveConfigToServer('/api/estrategias/mapping', mapping);
    };

    const saveProximityAlertSetting = (strategyId, isEnabled) => {
        const settings = loadSettings('proximityAlertSettings');
        settings[strategyId] = isEnabled;
        saveSettings('proximityAlertSettings', settings);
    };

    confluenceToggles.forEach(toggle => {
        toggle.addEventListener('change', () => saveConfluenceSetting(toggle.dataset.panel, toggle.checked));
    });

    activatorToggles.forEach(toggle => {
        toggle.addEventListener('change', () => saveActivatorSetting(toggle.dataset.panel, toggle.checked));
    });

    const updatePage = async () => {
        try {
            const [strategies, statuses, mapping, confluenceSettings, activatorSettings] = await Promise.all([
                fetch('/api/estrategias').then(res => res.json()),
                fetch('/api/estrategias/status').then(res => res.json()),
                fetch('/api/estrategias/mapping').then(res => res.json()),
                fetch('/api/estrategias/confluence').then(res => res.json()),
                fetch('/api/estrategias/activator').then(res => res.json())
            ]);
            
            confluenceToggles.forEach(toggle => {
                toggle.checked = confluenceSettings[toggle.dataset.panel] || false;
            });
            saveSettings('confluenceModeSettings', confluenceSettings);
            
            activatorToggles.forEach(toggle => {
                toggle.checked = activatorSettings[toggle.dataset.panel] || false;
            });
            saveSettings('activatorModeSettings', activatorSettings);
            
            renderStrategies(strategies, statuses, mapping);

        } catch (error) {
            console.error("Falha ao atualizar dados:", error);
            strategyListContainer.innerHTML = '<p>Erro ao carregar estratégias. Verifique o console para mais detalhes.</p>';
        }
    };
    
    const renderStrategies = (strategies, statuses, mapping) => {
        if (!strategyListContainer || !strategyCardTemplate) return;
        
        const proximityAlerts = loadSettings('proximityAlertSettings');
        strategyListContainer.innerHTML = '';

        if (!strategies || strategies.length === 0) {
            strategyListContainer.innerHTML = '<p>Nenhuma estratégia foi carregada. Verifique o console do servidor Flask para erros.</p>';
            return;
        }

        strategies.forEach(strategy => {
            const cardClone = strategyCardTemplate.content.cloneNode(true);
            const cardElement = cardClone.querySelector('.strategy-card');
            cardElement.dataset.id = strategy.id;
            cardElement.querySelector('.strategy-name').textContent = strategy.nome;
            cardElement.querySelector('.strategy-description').textContent = strategy.descricao;
            
            const toggle = cardElement.querySelector('.strategy-toggle');
            toggle.checked = statuses[strategy.id] || false;
            toggle.addEventListener('change', () => toggleStrategyStatus(strategy.id));
            cardElement.classList.toggle('active', toggle.checked);

            const columnSelect = cardElement.querySelector('.column-select');
            columnSelect.value = mapping[strategy.id] || 'none';
            columnSelect.addEventListener('change', (e) => saveStrategyMapping(strategy.id, e.target.value));
            
            const proximityToggle = cardElement.querySelector('.proximity-toggle');
            proximityToggle.checked = proximityAlerts[strategy.id] || false;
            proximityToggle.addEventListener('change', (e) => saveProximityAlertSetting(strategy.id, e.target.checked));

            strategyListContainer.appendChild(cardElement);
        });
    };

    const toggleStrategyStatus = async (strategyId) => {
        try {
            await fetch('/api/estrategias/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: strategyId })
            });
            setTimeout(updatePage, 200);
        } catch (error) {
            console.error(error);
            alert('Ocorreu um erro ao alterar o status.');
        }
    };

    updatePage();
});