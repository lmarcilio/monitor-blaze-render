// static/script.js

document.addEventListener('DOMContentLoaded', () => {

    // --- ELEMENTOS DO DOM ---
    const resultsGrid = document.getElementById('results-grid');
    const statusIndicator = document.getElementById('status-indicator');
    const statusText = document.getElementById('status-text');
    const soundToggle = document.getElementById('sound-toggle');
    const roundsInput = document.getElementById('rounds-input');
    const applyRoundsBtn = document.getElementById('apply-rounds-btn');
    const sequenceAlertContainer = document.getElementById('sequence-alert-section');
    const intervalAveragesContainer = document.getElementById('interval-averages-container-index');
    const notificationSound = document.getElementById('notification-sound');
    const toggleSound = document.getElementById('toggle-sound');
    const liveEntryDisplay = document.getElementById('live-entry-display');
    const inactiveCyclePlaceholder = document.getElementById('inactive-cycle-placeholder');
    const mainEntryNumber = document.getElementById('main-entry-number');
    const mainEntryValue = document.getElementById('main-entry-value');
    const mainWinBtn = document.getElementById('main-win-btn');
    const mainLossBtn = document.getElementById('main-loss-btn');
    const visibilityToggleBtn = document.getElementById('visibility-toggle-btn');
    const visibilityControls = document.getElementById('visibility-controls');
    const visibilityList = document.getElementById('visibility-list');
    const signalsDashboard = document.getElementById('signals-dashboard');
    const columnContainers = {
        '1': document.getElementById('column-1-container'),
        '2': document.getElementById('column-2-container'),
        '3': document.getElementById('column-3-container'),
    };
    const columnTitles = {
        '1': document.getElementById('column-1-title'),
        '2': document.getElementById('column-2-title'),
        '3': document.getElementById('column-3-title'),
    };
    const whiteMinutesChartCanvas = document.getElementById('white-minutes-chart-index');
    const panelStatusIndicators = {
        '1': document.getElementById('panel-1-status'),
        '2': document.getElementById('panel-2-status'),
        '3': document.getElementById('panel-3-status'),
    };

    // --- VARIÁVEIS GLOBAIS ---
    let isSoundEnabled = false, isAudioUnlocked = false;
    let currentLimit = 120;
    let visibleIds = new Set();
    let selectedNumbers = new Set(JSON.parse(localStorage.getItem('selectedNumbers')) || []);
    let playedSoundAlerts = new Set();
    let playedSignalAlerts = new Set();
    const COLUMNS_PER_ROW = 20;
    const colorClassMap = { 'Vermelho': 'text-color-Vermelho', 'Preto': 'text-color-Preto', 'Branco': 'text-color-Branco' };
    const emojiMap = { 'Vermelho': '🔴', 'Preto': '⚫', 'Branco': '⚪️' };
    let whiteMinutesChart = null;
    let activatorCountdownInterval = null;
    
    // --- LÓGICA DE VISIBILIDADE DAS SEÇÕES ---
    const SECTIONS_TO_MANAGE = {
        'sequence-alert-section': 'Alertas de Sequência Armada',
        'signals-dashboard': 'Painel de Sinais',
        'interval-averages-section': 'Painel de Médias de Alvo',
        'white-minutes-chart-section': 'Gráfico de Minutos do Branco',
        'active-management-widget': 'Widget de Gerenciamento de Ciclo',
        'results-grid': 'Grade Principal de Resultados'
    };
    function loadVisibilityState() {
        const state = localStorage.getItem('sectionVisibility');
        if (state) return JSON.parse(state);
        const defaultState = {};
        for (const sectionId in SECTIONS_TO_MANAGE) {
            defaultState[sectionId] = true;
        }
        return defaultState;
    }
    function saveVisibilityState(state) {
        localStorage.setItem('sectionVisibility', JSON.stringify(state));
    }
    function applyVisibilityState() {
        const state = loadVisibilityState();
        for (const sectionId in state) {
            const sectionElement = document.getElementById(sectionId);
            if (sectionElement) {
                sectionElement.classList.toggle('hidden-section', !state[sectionId]);
            }
        }
    }
    function populateVisibilityControls() {
        if (!visibilityList) return;
        const state = loadVisibilityState();
        visibilityList.innerHTML = '';
        for (const sectionId in SECTIONS_TO_MANAGE) {
            const li = document.createElement('li');
            const label = document.createElement('span');
            label.textContent = SECTIONS_TO_MANAGE[sectionId];
            const switchLabel = document.createElement('label');
            switchLabel.className = 'switch';
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.checked = state[sectionId] === undefined ? true : state[sectionId];
            checkbox.dataset.sectionId = sectionId;
            const slider = document.createElement('span');
            slider.className = 'slider';
            switchLabel.append(checkbox, slider);
            li.append(label, switchLabel);
            visibilityList.appendChild(li);
        }
    }

    // --- LÓGICA DO WIDGET DE GERENCIAMENTO DE BANCA ---
    const PAYOUT_MULTIPLIER = 14;
    const MIN_ENTRY_VALUE = 0.10;
    const formatCurrency = (value) => value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    const ceilToCent = (value) => Math.ceil(value * 100) / 100;
    function saveManagementState(state) { localStorage.setItem('managementState', JSON.stringify(state)); }
    function loadManagementState() {
        const savedStateJSON = localStorage.getItem('managementState');
        const defaultState = { initialBanca: 0, cycleEnded: true, numEntries: 0, currentEntryIndex: 0 };
        const savedState = savedStateJSON ? JSON.parse(savedStateJSON) : null;
        return { ...defaultState, ...savedState };
    }
    function calculateEntries(state) {
        let entries = [];
        const stopLossAmount = (state.initialBanca * state.stopLossPercent) / 100;
        if (state.initialBanca > 0 && state.numEntries > 0 && state.multiplier > 1) {
            let geometricSumFactor = 0;
            for (let i = 0; i < state.numEntries; i++) { geometricSumFactor += Math.pow(state.multiplier, i); }
            let initialEntry = stopLossAmount / geometricSumFactor;
            if (initialEntry < MIN_ENTRY_VALUE) { initialEntry = MIN_ENTRY_VALUE; }
            let currentEntry = initialEntry;
            for (let i = 0; i < state.numEntries; i++) {
                const roundedEntry = ceilToCent(currentEntry);
                entries.push(roundedEntry);
                currentEntry = roundedEntry * state.multiplier;
            }
        }
        return entries;
    }
    function handleWinMain() {
        const state = loadManagementState();
        if (state.cycleEnded) return;
        const entries = calculateEntries(state);
        const winIndex = state.currentEntryIndex;
        if (winIndex >= entries.length) return;
        const costUntilWin = entries.slice(0, winIndex + 1).reduce((sum, val) => sum + val, 0);
        const winAmount = entries[winIndex] * PAYOUT_MULTIPLIER;
        const newBanca = state.initialBanca - costUntilWin + winAmount;
        const newState = { ...state, initialBanca: ceilToCent(newBanca), currentBanca: ceilToCent(newBanca), currentEntryIndex: 0, cycleEnded: false, cycleWon: false, };
        saveManagementState(newState);
        renderActiveManagementWidget();
    }
    function handleLossMain() {
        const state = loadManagementState();
        if (state.cycleEnded) return;
        const entries = calculateEntries(state);
        if (state.currentEntryIndex >= entries.length) return;
        const entryValue = entries[state.currentEntryIndex];
        state.currentBanca -= entryValue;
        state.currentEntryIndex++;
        if (state.currentEntryIndex >= state.numEntries) { state.cycleEnded = true; state.cycleWon = false; }
        saveManagementState(state);
        renderActiveManagementWidget();
    }
    function renderActiveManagementWidget() {
        if (!liveEntryDisplay) return;
        const state = loadManagementState();
        if (state.cycleEnded || state.initialBanca <= 0 || state.numEntries === 0) {
            liveEntryDisplay.style.display = 'none';
            inactiveCyclePlaceholder.style.display = 'block';
        } else {
            liveEntryDisplay.style.display = 'flex';
            inactiveCyclePlaceholder.style.display = 'none';
            const entries = calculateEntries(state);
            const currentEntryValue = entries[state.currentEntryIndex];
            mainEntryNumber.textContent = `Entrada ${state.currentEntryIndex + 1}`;
            mainEntryValue.textContent = formatCurrency(currentEntryValue || 0);
        }
    }

    // --- FUNÇÕES DE RENDERIZAÇÃO ---
    const renderGrid = (rows, targetsByMinute) => { // A função agora recebe o Map
        if (!resultsGrid) return;
        resultsGrid.innerHTML = '';
        const fragment = document.createDocumentFragment();

        if (!rows || rows.length === 0) {
            const p = document.createElement('p');
            p.textContent = 'Aguardando resultados...';
            fragment.appendChild(p);
        } else {
            rows.forEach(resultsInRow => {
                const rowEl = document.createElement('div');
                rowEl.className = 'results-row';

                resultsInRow.forEach(resultData => {
                    const slotEl = document.createElement('div');
                    slotEl.className = 'result-slot';
                    const rollContainerEl = document.createElement('div');
                    rollContainerEl.className = 'roll-container';
                    const timeEl = document.createElement('div');
                    timeEl.className = 'result-time';
                    
                    // ### LÓGICA DE CORREÇÃO PRINCIPAL ###
                    const targetPanels = targetsByMinute.get(resultData.time_short);
                    if (targetPanels) {
                        if (targetPanels.size > 1) {
                            // Mais de um painel, aplica a classe de piscar
                            slotEl.classList.add('multi-panel-target');
                        } else if (targetPanels.size === 1) {
                            // Apenas um painel, aplica a classe de cor específica
                            const panelId = targetPanels.values().next().value;
                            slotEl.classList.add(`panel-${panelId}-target`);
                        }
                    }

                    if (resultData.type === 'placeholder') {
                        slotEl.classList.add('placeholder');
                        timeEl.innerHTML = `<span class="time-short">${resultData.time_short}</span>`;
                    } else { 
                        if (!visibleIds.has(resultData.id)) {
                            slotEl.classList.add('new-item-animation');
                        }
                        slotEl.dataset.id = resultData.id;
                        slotEl.dataset.roll = resultData.roll;
                        rollContainerEl.classList.add(colorClassMap[resultData.color] || '');
                        rollContainerEl.textContent = resultData.roll;
                        timeEl.innerHTML = `<span class="time-short">${resultData.time_short}</span><span class="time-full">${resultData.time_full}</span>`;
                        
                        if (selectedNumbers.has(String(resultData.roll))) {
                            slotEl.classList.add('manual-selection');
                        }
                    }
                    
                    slotEl.appendChild(rollContainerEl);
                    slotEl.appendChild(timeEl);
                    rowEl.appendChild(slotEl);
                });
                
                fragment.appendChild(rowEl);
            });
        }
        resultsGrid.appendChild(fragment);
    };
    const renderSequenceAlerts = (alerts) => { if (!sequenceAlertContainer) return; const visualAlerts = alerts.filter(a => a.status === 'visual'); const alertKeys = new Set(visualAlerts.map(a => a.id)); const existingCardKeys = new Set(Array.from(sequenceAlertContainer.children).map(card => card.dataset.key)); for (const key of existingCardKeys) { if (!alertKeys.has(key)) { sequenceAlertContainer.querySelector(`[data-key="${key}"]`)?.remove(); } } visualAlerts.forEach(alert => { if (!existingCardKeys.has(alert.id)) { const card = document.createElement('div'); card.className = 'sequence-alert-card'; card.dataset.key = alert.id; const sequenceEmojis = alert.sequence.map(color => `<span class="${colorClassMap[color]}">${emojiMap[color]}</span>`).join(''); card.innerHTML = `<div class="alert-title">Sequência Armada Detectada!</div><div class="alert-body"><div class="alert-sequence-icons">${sequenceEmojis}</div><span>➡️</span><div class="alert-prediction">${emojiMap[alert.prediction]}</div></div>`; sequenceAlertContainer.appendChild(card); } }); sequenceAlertContainer.style.display = sequenceAlertContainer.children.length > 0 ? 'flex' : 'none'; };
    const renderIntervalAverages = (data) => {
        if (!intervalAveragesContainer) return;
        if (!data || data.erro || data.total_intervalos < 4) {
            intervalAveragesContainer.innerHTML = '<p>Dados insuficientes para calcular as médias (mínimo 4 intervalos).</p>';
            return;
        }
        intervalAveragesContainer.innerHTML = `
            <div class="stat-card-index"><div class="stat-value-index">${data.media_curta.toFixed(1)}</div><div class="stat-label-index">Média Curta</div></div>
            <div class="stat-card-index"><div class="stat-value-index">${data.media_longa.toFixed(1)}</div><div class="stat-label-index">Média Longa</div></div>`;
    };
    const createIndividualSignalCard = (signal) => {
        const targetDt = new Date(signal.target_timestamp.replace(' ', 'T'));
        const targetTimeString = targetDt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
        const statusText = signal.status === 'hit' ? 'ACERTO' : 'PENDENTE';
        return `<div class="signal-header"><span class="strategy-name-badge">${signal.strategy_name}</span><span class="signal-status-badge">${statusText}</span></div><div class="signal-body-simple"><span class="signal-target-icon">🎯</span><span class="signal-target-time-large">${targetTimeString}</span></div>${signal.message ? `<small style="text-align:center; color: var(--time-color);">${signal.message}</small>` : ''}`;
    };
    const createConfluenceSignalCard = (signal) => {
        const targetDt = new Date(signal.target_timestamp.replace(' ', 'T'));
        const targetTimeString = targetDt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
        const strategyNames = signal.strategy_names.join(', ');
        const statusText = signal.status === 'hit' ? 'ACERTO' : 'PENDENTE';
        const statusBadge = `<span class="signal-status-badge">${statusText}</span>`;
        return `<div class="confluence-header"><span class="confluence-title">Alvo de Confluência</span>${statusBadge}<span class="confluence-badge">${signal.count} ESTRATÉGIAS</span></div><div class="confluence-body"><span class="signal-target-time-large">⚪️ ${targetTimeString}</span></div><small class="confluence-strategies">${strategyNames}</small>`;
    };
    const renderAllSignalsInColumns = (signalsFromApi) => {
        let signalsByColumn = { '1': [], '2': [], '3': [] };
        signalsFromApi.forEach(signal => {
            if (signalsByColumn[signal.panel_id]) {
                signalsByColumn[signal.panel_id].push(signal);
            }
        });
        for (const columnId in columnContainers) {
            const container = columnContainers[columnId];
            const signals = signalsByColumn[columnId];
            const newKeys = new Set(signals.map(s => s.key));
            
            container.querySelectorAll('[data-key]').forEach(el => {
                if (!newKeys.has(el.dataset.key)) el.remove();
            });

            signals.forEach(signal => {
                const existingCard = container.querySelector(`[data-key="${signal.key}"]`);
                const statusClass = signal.status === 'hit' ? 'status-hit' : 'status-pending';
                
                if (existingCard) {
                    let newClassName;
                    if (signal.type === 'confluence') {
                        newClassName = `confluence-card blue-border ${statusClass}`;
                    } else {
                        newClassName = `signal-card ${statusClass}`;
                    }
                    if (existingCard.className !== newClassName) {
                        existingCard.className = newClassName;
                        if (signal.type === 'confluence') {
                            existingCard.innerHTML = createConfluenceSignalCard(signal);
                        } else {
                            existingCard.innerHTML = createIndividualSignalCard(signal);
                        }
                    }
                } else {
                    const card = document.createElement('div');
                    card.dataset.key = signal.key;
                    if (signal.type === 'confluence') {
                        card.className = `confluence-card blue-border ${statusClass}`;
                        card.innerHTML = createConfluenceSignalCard(signal);
                    } else {
                        card.className = `signal-card ${statusClass}`;
                        card.innerHTML = createIndividualSignalCard(signal);
                    }
                    container.appendChild(card);
                }
            });

            const placeholderEl = container.querySelector('.placeholder');
            if (container.children.length > (placeholderEl ? 1 : 0)) {
                placeholderEl?.remove();
            } else if (container.children.length === 0 && !placeholderEl) {
                const p = document.createElement('p');
                p.className = 'placeholder';
                p.textContent = 'Aguardando sinais...';
                container.appendChild(p);
            }
        }
    };
    const renderPanelStats = (stats) => {
        for (const columnId in columnTitles) {
            const titleElement = columnTitles[columnId];
            if (titleElement && stats[columnId]) {
                const data = stats[columnId];
                const statsHTML = `<span class="hit-count">(${data.hits} Acertos)</span><span class="miss-count">(${data.misses} Erros)</span>`;
                titleElement.innerHTML = `Painel Estratégia ${columnId} ${statsHTML}`;
            }
        }
    };
    async function fetchAndRenderPanelStats() {
        try {
            const response = await fetch('/api/stats/panel_accuracy');
            if (!response.ok) return;
            const stats = await response.json();
            renderPanelStats(stats);
        } catch (error) { console.error("Falha ao buscar estatísticas dos painéis:", error); }
    }
    const updatePanelStatusIndicators = (data) => {
        const { activator_window_active, activator_window_end, activator_modes_enabled } = data;

        if (activatorCountdownInterval) clearInterval(activatorCountdownInterval);

        for (const panelId in panelStatusIndicators) {
            const indicator = panelStatusIndicators[panelId];
            if (!indicator) continue;

            const isActivatorOnForPanel = activator_modes_enabled[panelId];

            if (isActivatorOnForPanel) {
                indicator.classList.add('activator-on');
                if (activator_window_active) {
                    indicator.classList.add('active');
                    indicator.classList.remove('inactive');
                    
                    const endTime = new Date(activator_window_end);
                    const updateCountdown = () => {
                        const now = new Date();
                        const timeLeft = Math.round((endTime - now) / 1000);
                        if (timeLeft > 0) {
                            const minutes = Math.floor(timeLeft / 60);
                            const seconds = timeLeft % 60;
                            indicator.textContent = `ATIVO ${minutes}:${seconds.toString().padStart(2, '0')}`;
                        } else {
                            indicator.textContent = 'AGUARDANDO';
                            indicator.classList.remove('active');
                            indicator.classList.add('inactive');
                            clearInterval(activatorCountdownInterval);
                        }
                    };
                    updateCountdown();
                    activatorCountdownInterval = setInterval(updateCountdown, 1000);

                } else {
                    indicator.textContent = 'AGUARDANDO';
                    indicator.classList.remove('active');
                    indicator.classList.add('inactive');
                }
            } else {
                indicator.textContent = '';
                indicator.className = 'panel-status-indicator';
            }
        }
    };

    async function renderWhiteMinutesChart() {
        if (!whiteMinutesChartCanvas) return;
        try {
            const response = await fetch('/api/stats/white_minutes');
            if (!response.ok) throw new Error('Falha ao buscar dados do gráfico.');
            const chartData = await response.json();

            if (!whiteMinutesChart) {
                const ctx = whiteMinutesChartCanvas.getContext('2d');
                whiteMinutesChart = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: chartData.labels,
                        datasets: [{
                            label: 'Ocorrências de Branco',
                            data: chartData.data,
                            backgroundColor: 'rgba(74, 144, 226, 0.6)',
                            borderColor: 'rgba(74, 144, 226, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { 
                                beginAtZero: true, 
                                ticks: { 
                                    color: '#FFFFFF', 
                                    stepSize: 1 
                                } 
                            },
                            x: { 
                                ticks: { 
                                    color: '#FFFFFF'
                                } 
                            }
                        }
                    }
                });
            } else {
                whiteMinutesChart.data.datasets[0].data = chartData.data;
                whiteMinutesChart.update();
            }
        } catch (error) {
            console.error('Erro ao renderizar gráfico:', error);
        }
    }

    // --- LÓGICA DE SOM ---
    const handleSoundAlerts = (sequenceAlerts, allSignals) => {
        const sequenceSoundAlerts = sequenceAlerts.filter(a => a.status === 'sound');
        sequenceSoundAlerts.forEach(alert => {
            if (!playedSoundAlerts.has(alert.id)) {
                playNotification();
                playedSoundAlerts.add(alert.id);
            }
        });
        const activeSequenceSoundIds = new Set(sequenceSoundAlerts.map(a => a.id));
        playedSoundAlerts.forEach(id => { if (!activeSequenceSoundIds.has(id)) { playedSoundAlerts.delete(id); } });
        const proximityAlertSettings = JSON.parse(localStorage.getItem('proximityAlertSettings') || '{}');
        allSignals.forEach(signal => {
            if (signal.type !== 'individual') return;
            const signalId = String(signal.id);
            if (playedSignalAlerts.has(signalId)) return;
            if (signal.is_proximate && proximityAlertSettings[signal.strategy_id]) {
                playNotification();
                playedSignalAlerts.add(signalId);
            }
        });
        const activeSignalIds = new Set(allSignals.filter(s => s.type === 'individual').map(s => String(s.id)));
        playedSignalAlerts.forEach(id => { if (!activeSignalIds.has(id)) { playedSignalAlerts.delete(id); } });
    };
    const updateSoundToggleView = () => { if (soundToggle) { soundToggle.textContent = isSoundEnabled ? '🔊' : '🔇'; soundToggle.classList.toggle('muted', !isSoundEnabled); } };
    const playNotification = () => { if (isSoundEnabled && isAudioUnlocked && notificationSound) { notificationSound.currentTime = 0; notificationSound.play().catch(e => console.error("Erro ao tocar notificação:", e)); } };

    // --- FUNÇÃO DE ATUALIZAÇÃO PRINCIPAL ---
    const fetchAndUpdate = async () => {
        visibleIds = new Set(Array.from(document.querySelectorAll('.result-slot[data-id]')).map(el => el.dataset.id));
        try {
            const [
                resultsResponse, sequenceAlertsResponse, allSignalsResponse, intervalAveragesResponse
            ] = await Promise.all([
                fetch(`/api/resultados?limite=${currentLimit}`),
                fetch('/api/sequence_alerts'),
                fetch('/api/sinais'),
                fetch('/api/stats/interval_averages'),
            ]);
            const responses = [resultsResponse, sequenceAlertsResponse, allSignalsResponse, intervalAveragesResponse];
            for (const response of responses) { if (!response.ok) throw new Error(`Falha na API: ${response.url}`); }
            
            const rows = await resultsResponse.json();
            const sequenceAlerts = await sequenceAlertsResponse.json();
            const signalsData = await allSignalsResponse.json();
            const intervalAverages = await intervalAveragesResponse.json();
            
            const { signals: allSignals, activator_modes_enabled } = signalsData;
            
            updatePanelStatusIndicators(signalsData);

            const signalsForGrid = allSignals.filter(signal => {
                if (!activator_modes_enabled[signal.panel_id]) {
                    return true;
                }
                return signalsData.activator_window_active;
            });

            // ### NOVA ESTRUTURA DE DADOS PARA AGRUPAR ALVOS POR MINUTO ###
            const targetsByMinute = new Map();
            signalsForGrid.forEach(signal => {
                const targetDt = new Date(signal.target_timestamp.replace(' ', 'T'));
                const timeShort = targetDt.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });

                if (!targetsByMinute.has(timeShort)) {
                    targetsByMinute.set(timeShort, new Set());
                }
                targetsByMinute.get(timeShort).add(signal.panel_id);
            });

            renderGrid(rows, targetsByMinute);
            renderSequenceAlerts(sequenceAlerts);
            renderAllSignalsInColumns(allSignals);
            renderIntervalAverages(intervalAverages);
            renderActiveManagementWidget();
            handleSoundAlerts(sequenceAlerts, allSignals);
            fetchAndRenderPanelStats();
            statusIndicator.classList.remove('error');
            statusText.textContent = 'Conectado';
        } catch (error) {
            console.error("Falha ao buscar dados:", error);
            statusIndicator.classList.add('error');
            statusText.textContent = 'Erro de conexão';
        }
    };

    const applyRoundLimit = () => {
        const newLimit = parseInt(roundsInput.value, 10);
        if (isNaN(newLimit) || newLimit < 20 || newLimit > 1000) { roundsInput.value = currentLimit; return; }
        currentLimit = newLimit;
        localStorage.setItem('roundLimit', currentLimit);
        visibleIds.clear();
        fetchAndUpdate();
    };

    // --- LISTENERS DE EVENTOS ---
    if (visibilityToggleBtn) { visibilityToggleBtn.addEventListener('click', (event) => { event.stopPropagation(); visibilityControls.classList.toggle('active'); }); }
    if (visibilityList) { visibilityList.addEventListener('change', (e) => { if (e.target.type === 'checkbox') { const sectionId = e.target.dataset.sectionId; const isVisible = e.target.checked; const state = loadVisibilityState(); state[sectionId] = isVisible; saveVisibilityState(state); applyVisibilityState(); } }); }
    document.addEventListener('click', (event) => { if (visibilityControls && visibilityControls.classList.contains('active')) { if (!visibilityControls.contains(event.target) && !visibilityToggleBtn.contains(event.target)) { visibilityControls.classList.remove('active'); } } });
    if (soundToggle) { soundToggle.addEventListener('click', () => { isSoundEnabled = !isSoundEnabled; localStorage.setItem('soundEnabled', isSoundEnabled); updateSoundToggleView(); isAudioUnlocked = true; if (toggleSound) { toggleSound.play().catch(e => console.error("Erro ao tocar som de clique:", e)); } }); }
    
    if (resultsGrid) { 
        resultsGrid.addEventListener('click', (event) => {
            const clickedSlot = event.target.closest('.result-slot[data-roll]');
            if (!clickedSlot) { return; } 

            const clickedNumber = clickedSlot.dataset.roll;
            let isNowSelected;

            if (selectedNumbers.has(clickedNumber)) {
                selectedNumbers.delete(clickedNumber);
                isNowSelected = false;
            } else {
                selectedNumbers.add(clickedNumber);
                isNowSelected = true;
            }
            
            localStorage.setItem('selectedNumbers', JSON.stringify(Array.from(selectedNumbers)));
            
            const slotsToUpdate = resultsGrid.querySelectorAll(`.result-slot[data-roll="${clickedNumber}"]`);
            slotsToUpdate.forEach(slot => {
                slot.classList.toggle('manual-selection', isNowSelected);
            });
        }); 
    }

    if (applyRoundsBtn) applyRoundsBtn.addEventListener('click', applyRoundLimit);
    if (roundsInput) roundsInput.addEventListener('keydown', (event) => { if (event.key === 'Enter') applyRoundLimit(); });
    if (mainWinBtn) mainWinBtn.addEventListener('click', handleWinMain);
    if (mainLossBtn) mainLossBtn.addEventListener('click', handleLossMain);

    // --- INICIALIZAÇÃO ---
    const savedLimit = localStorage.getItem('roundLimit');
    if (savedLimit) { currentLimit = parseInt(savedLimit, 10); if(roundsInput) roundsInput.value = currentLimit; }
    isSoundEnabled = localStorage.getItem('soundEnabled') === 'true';
    updateSoundToggleView();
    applyVisibilityState();
    populateVisibilityControls();
    
    fetchAndUpdate();
    renderWhiteMinutesChart();

    setInterval(fetchAndUpdate, 5000);
    setInterval(renderWhiteMinutesChart, 30000); 
});