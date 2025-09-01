// static/configuracao.js

document.addEventListener('DOMContentLoaded', () => {

    // --- LÓGICA PARA CONFIGURAÇÃO DO TELEGRAM ---
    const telegramForm = document.getElementById('telegram-form');
    if (telegramForm) {
        const token1Input = document.getElementById('token_1');
        const chatId1Input = document.getElementById('chat_id_1');
        const token2Input = document.getElementById('token_2');
        const chatId2Input = document.getElementById('chat_id_2');
        const token3Input = document.getElementById('token_3');
        const chatId3Input = document.getElementById('chat_id_3');
        const statusDiv = document.getElementById('save-status');

        const loadTelegramSettings = async () => {
            try {
                const response = await fetch('/api/config/telegram');
                if (!response.ok) throw new Error('Falha ao carregar configurações.');
                const config = await response.json();
                if (config.channel_1) {
                    token1Input.value = config.channel_1.token || '';
                    chatId1Input.value = config.channel_1.chat_id || '';
                }
                if (config.channel_2) {
                    token2Input.value = config.channel_2.token || '';
                    chatId2Input.value = config.channel_2.chat_id || '';
                }
                if (config.channel_3) {
                    token3Input.value = config.channel_3.token || '';
                    chatId3Input.value = config.channel_3.chat_id || '';
                }
            } catch (error) {
                if(statusDiv) {
                    statusDiv.textContent = 'Erro ao carregar dados.';
                    statusDiv.style.color = '#ef5350';
                }
                console.error(error);
            }
        };

        const saveTelegramSettings = async (event) => {
            event.preventDefault(); 
            if(!statusDiv) return;
            statusDiv.textContent = 'Salvando...';
            statusDiv.style.color = '#ffc107';
            const configData = {
                channel_1: { token: token1Input.value, chat_id: chatId1Input.value },
                channel_2: { token: token2Input.value, chat_id: chatId2Input.value },
                channel_3: { token: token3Input.value, chat_id: chatId3Input.value }
            };
            try {
                const response = await fetch('/api/config/telegram', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(configData)
                });
                if (!response.ok) throw new Error('O servidor retornou um erro.');
                const result = await response.json();
                if (result.status === 'sucesso') {
                    statusDiv.textContent = 'Configurações salvas com sucesso!';
                    statusDiv.style.color = '#34C759';
                } else {
                    throw new Error(result.message || 'Erro desconhecido ao salvar.');
                }
            } catch (error) {
                statusDiv.textContent = `Erro: ${error.message}`;
                statusDiv.style.color = '#ef5350';
                console.error(error);
            }
        };
        
        telegramForm.addEventListener('submit', saveTelegramSettings);
        loadTelegramSettings();
    }

    // --- LÓGICA DA FERRAMENTA DE GERENCIAMENTO ATIVO ---
    const bancaInput = document.getElementById('banca-input');
    const stopWinInput = document.getElementById('stop-win-input');
    const stopLossInput = document.getElementById('stop-loss-input');
    const multiplierInput = document.getElementById('multiplier-input');
    const entriesInput = document.getElementById('entries-input');
    const allManagementInputs = [bancaInput, stopWinInput, stopLossInput, multiplierInput, entriesInput];

    const totalRiskValue = document.getElementById('total-risk-value');
    const restartCycleBtn = document.getElementById('restart-cycle-btn');
    
    const currentBancaValue = document.getElementById('current-banca-value');
    const currentBancaBox = document.getElementById('current-banca-box');
    const cyclePLValue = document.getElementById('cycle-pl-value');
    const cyclePLBox = document.getElementById('cycle-pl-box');
    const entryList = document.getElementById('entry-list');
    const entryListWrapper = document.getElementById('entry-list-wrapper');

    const PAYOUT_MULTIPLIER = 14;
    const MIN_ENTRY_VALUE = 0.10;

    const formatCurrency = (value) => value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    const ceilToCent = (value) => Math.ceil(value * 100) / 100;

    function renderManagementTool() {
        const state = loadState();

        if (parseFloat(bancaInput.value) !== state.initialBanca) bancaInput.value = state.initialBanca;
        if (parseFloat(stopWinInput.value) !== state.stopWinPercent) stopWinInput.value = state.stopWinPercent;
        if (parseFloat(stopLossInput.value) !== state.stopLossPercent) stopLossInput.value = state.stopLossPercent;
        if (parseFloat(multiplierInput.value) !== state.multiplier) multiplierInput.value = state.multiplier;
        if (parseInt(entriesInput.value) !== state.numEntries) entriesInput.value = state.numEntries;

        currentBancaValue.textContent = formatCurrency(state.currentBanca);
        const cyclePL = state.currentBanca - state.initialBanca;
        cyclePLValue.textContent = formatCurrency(cyclePL);
        cyclePLBox.classList.remove('profit', 'loss');
        if (cyclePL > 0) cyclePLBox.classList.add('profit');
        if (cyclePL < 0) cyclePLBox.classList.add('loss');

        const stopWinAmount = (state.initialBanca * state.stopWinPercent) / 100;
        const stopWinTarget = state.initialBanca + stopWinAmount;
        currentBancaBox.classList.toggle('win-goal-reached', state.currentBanca >= stopWinTarget);

        let entries = [];
        const stopLossAmount = (state.initialBanca * state.stopLossPercent) / 100;

        if (state.initialBanca > 0 && state.numEntries > 0 && state.multiplier > 1) {
            let geometricSumFactor = 0;
            for (let i = 0; i < state.numEntries; i++) {
                geometricSumFactor += Math.pow(state.multiplier, i);
            }
            
            let initialEntry = stopLossAmount / geometricSumFactor;
            
            if (initialEntry < MIN_ENTRY_VALUE) {
                initialEntry = MIN_ENTRY_VALUE;
            }

            let currentEntry = initialEntry;
            for (let i = 0; i < state.numEntries; i++) {
                const roundedEntry = ceilToCent(currentEntry);
                entries.push(roundedEntry);
                currentEntry = roundedEntry * state.multiplier;
            }
        }

        const totalCalculatedRisk = entries.reduce((sum, val) => sum + val, 0);
        totalRiskValue.textContent = formatCurrency(totalCalculatedRisk);
        
        entryList.innerHTML = '';
        restartCycleBtn.style.display = 'none';

        if (totalCalculatedRisk > state.initialBanca) {
            const warningMessage = `
                <div class="risk-warning">
                    <strong>Risco Inviável!</strong>
                    <p>O risco total (${formatCurrency(totalCalculatedRisk)}) excede a banca inicial (${formatCurrency(state.initialBanca)}).</p>
                    <p>Ajuste o multiplicador, o nº de entradas ou a % de stop loss.</p>
                </div>`;
            entryListWrapper.innerHTML = warningMessage;
            return;
        } else {
            entryListWrapper.innerHTML = '';
            entryListWrapper.appendChild(entryList);
        }
        
        if (entries.length === 0) {
            entryList.innerHTML = '<p class="placeholder">Preencha os valores para calcular.</p>';
            return;
        }

        let cumulativeRisk = 0;
        entries.forEach((entryValue, index) => {
            cumulativeRisk += entryValue;
            const item = document.createElement('div');
            item.className = 'entry-item';

            if (cumulativeRisk > stopLossAmount * 1.05) {
                item.classList.add('alert-danger');
            } else if (cumulativeRisk > stopLossAmount * 0.8) {
                item.classList.add('alert-warning');
            }

            const isPastEntry = index < state.currentEntryIndex;
            const isActiveEntry = index === state.currentEntryIndex && !state.cycleEnded;

            if (isPastEntry) item.classList.add('loss');
            if (isActiveEntry) item.classList.add('active');
            
            item.innerHTML = `<span class="entry-number">Entrada ${index + 1}</span><span class="entry-value">${formatCurrency(entryValue)}</span><div class="entry-actions"></div>`;
            
            const winBtn = document.createElement('button');
            winBtn.className = 'action-btn win-btn';
            winBtn.textContent = 'Acerto';
            winBtn.onclick = () => handleWin(entries, index);

            const lossBtn = document.createElement('button');
            lossBtn.className = 'action-btn loss-btn';
            lossBtn.textContent = 'Erro';
            lossBtn.onclick = () => handleLoss(entryValue);

            winBtn.disabled = !isActiveEntry;
            lossBtn.disabled = !isActiveEntry;
            
            item.querySelector('.entry-actions').append(winBtn, lossBtn);
            entryList.appendChild(item);
        });

        if (state.cycleEnded) {
            const endMessage = document.createElement('div');
            endMessage.className = 'cycle-end-message';
            if (state.cycleWon) {
                endMessage.classList.add('win');
                endMessage.textContent = '🎉 Meta Atingida! Um novo ciclo será iniciado com a banca atualizada.';
            } else {
                endMessage.classList.add('loss');
                endMessage.textContent = '🛑 Stop Loss Atingido! Clique abaixo para reiniciar com a banca atual.';
                restartCycleBtn.style.display = 'block';
            }
            entryList.appendChild(endMessage);
        }
    }

    function handleWin(allEntries, winIndex) {
        const state = loadState();
        if (state.cycleEnded) return;
        const costUntilWin = allEntries.slice(0, winIndex + 1).reduce((sum, val) => sum + val, 0);
        const winAmount = allEntries[winIndex] * PAYOUT_MULTIPLIER;
        const newBanca = state.initialBanca - costUntilWin + winAmount;
        const newState = { ...state, cycleEnded: true, cycleWon: true };
        saveState(newState);
        setTimeout(() => resetCycle(newBanca), 2500);
        renderManagementTool();
    }
    
    function handleLoss(entryValue) {
        const state = loadState();
        if (state.cycleEnded) return;
        state.currentBanca -= entryValue;
        state.currentEntryIndex++;
        if (state.currentEntryIndex >= state.numEntries) {
            state.cycleEnded = true;
            state.cycleWon = false;
        }
        saveState(state);
        renderManagementTool();
    }

    function restartCycleFromButton() {
        const currentState = loadState();
        resetCycle(currentState.currentBanca);
    }

    function resetCycle(newBancaValue = null) {
        let initialBanca;
        if (newBancaValue !== null) {
            initialBanca = newBancaValue;
        } else {
            const currentState = loadState();
            initialBanca = currentState.initialBanca > 0 ? currentState.currentBanca : (parseFloat(bancaInput.value) || 0);
        }
        const newState = {
            initialBanca: ceilToCent(initialBanca),
            currentBanca: ceilToCent(initialBanca),
            stopWinPercent: parseFloat(stopWinInput.value) || 10,
            stopLossPercent: parseFloat(stopLossInput.value) || 10,
            multiplier: parseFloat(multiplierInput.value) || 1.077,
            numEntries: parseInt(entriesInput.value) || 5,
            currentEntryIndex: 0,
            cycleEnded: false,
            cycleWon: false,
        };
        saveState(newState);
        renderManagementTool();
    }

    function saveState(state) {
        localStorage.setItem('managementState', JSON.stringify(state));
    }

    function loadState() {
        const savedStateJSON = localStorage.getItem('managementState');
        const defaultState = {
            initialBanca: 50,
            currentBanca: 50,
            stopWinPercent: 10,
            stopLossPercent: 10,
            multiplier: 1.077,
            numEntries: 5,
            currentEntryIndex: 0,
            cycleEnded: false,
            cycleWon: false,
        };
        const savedState = savedStateJSON ? JSON.parse(savedStateJSON) : null;
        return { ...defaultState, ...savedState };
    }

    allManagementInputs.forEach(input => input.addEventListener('change', () => {
        const newInitialBanca = parseFloat(bancaInput.value) || loadState().initialBanca;
        resetCycle(newInitialBanca);
    }));

    restartCycleBtn.addEventListener('click', restartCycleFromButton);
    renderManagementTool();
});