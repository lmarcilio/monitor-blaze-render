// static/estatisticas.js

document.addEventListener('DOMContentLoaded', () => {

    // --- ELEMENTOS DO DOM ---
    const intervalAveragesContainer = document.getElementById('interval-averages-container');
    const sequenceListContainer = document.getElementById('sequence-list');
    const sequenceItemTemplate = document.getElementById('sequence-item-template');
    const sequenceFilterBtns = document.querySelectorAll('.filter-btn[data-length]');
    const hourlyStatsGrid = document.getElementById('hourly-stats-grid');
    const viewToggleButtons = document.getElementById('view-toggle-buttons');
    
    // --- MAPAS E VARIÁVEIS GLOBAIS ---
    const colorClassMap = { 'Vermelho': 'text-color-Vermelho', 'Preto': 'text-color-Preto', 'Branco': 'text-color-Branco' };
    const emojiMap = { 'Vermelho': '🔴', 'Preto': '⚫', 'Branco': '⚪️' };
    let currentSequenceLength = parseInt(localStorage.getItem('sequenceLengthFilter') || '4', 10);
    let armedSequences = [];
    let hourlyColorData = null;
    let currentViewMode = 'count';

    // --- FUNÇÕES DE FETCH (BUSCAR DADOS) ---
    async function fetchHourlyColorStats() {
        if (!hourlyStatsGrid) return;
        try {
            const response = await fetch('/api/stats/hourly_colors');
            if (!response.ok) throw new Error('Falha ao buscar contadores horários.');
            hourlyColorData = await response.json();
            renderHourlyStats();
        } catch (error) {
            console.error(error);
            hourlyStatsGrid.innerHTML = '<p class="no-data-message">Erro ao carregar contadores horários.</p>';
        }
    }

    async function fetchIntervalAverages() {
        if (!intervalAveragesContainer) return;
        try {
            const response = await fetch('/api/stats/interval_averages');
            if (!response.ok) throw new Error('Falha ao buscar médias de intervalo.');
            const data = await response.json();
            renderIntervalAverages(data);
        } catch (error) {
            console.error(error);
            intervalAveragesContainer.innerHTML = '<p class="no-data-message">Erro ao carregar médias.</p>';
        }
    }

    async function fetchSequences() {
        if (!sequenceListContainer) return;
        try {
            const response = await fetch(`/api/stats/sequences?length=${currentSequenceLength}`);
            if (!response.ok) throw new Error('Falha ao buscar sequências.');
            const data = await response.json();
            renderSequences(data);
        } catch (error) {
            console.error(error);
            sequenceListContainer.innerHTML = '<p class="no-data-message">Erro ao carregar sequências.</p>';
        }
    }
    
    // ### NOVA FUNÇÃO PARA BUSCAR DADOS E RENDERIZAR O GRÁFICO ###
    async function fetchAndRenderWhiteMinutesChart() {
        const canvas = document.getElementById('white-minutes-chart');
        if (!canvas) return;

        try {
            const response = await fetch('/api/stats/white_minutes');
            if (!response.ok) throw new Error('Falha ao buscar dados para o gráfico.');
            const chartData = await response.json();

            const ctx = canvas.getContext('2d');
            new Chart(ctx, {
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
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                title: (tooltipItems) => `Minuto ${tooltipItems[0].label}`,
                                label: (tooltipItem) => `${tooltipItem.raw} ocorrência(s)`
                            }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                color: 'var(--time-color)',
                                stepSize: 1 // Garante que a escala seja de números inteiros
                            },
                            title: {
                                display: true,
                                text: 'Nº de Ocorrências',
                                color: 'var(--text-color)'
                            }
                        },
                        x: {
                            ticks: {
                                color: 'var(--time-color)'
                            },
                            title: {
                                display: true,
                                text: 'Minuto da Hora',
                                color: 'var(--text-color)'
                            }
                        }
                    }
                }
            });
        } catch(error) {
            console.error('Erro ao renderizar gráfico:', error);
        }
    }

    // --- FUNÇÕES DE RENDERIZAÇÃO (EXIBIR NA TELA) ---
    // ... (as outras funções de renderização continuam aqui, sem alterações) ...
    function renderHourlyStats() {
        if (!hourlyStatsGrid || !hourlyColorData) return;
        
        hourlyStatsGrid.innerHTML = '';
        const currentHour = new Date().getHours();
        
        for (let i = 0; i < 24; i++) {
            const hourKey = String(i).padStart(2, '0');
            const data = hourlyColorData[hourKey];
            const total = data.Preto + data.Vermelho + data.Branco;

            const item = document.createElement('div');
            item.className = 'hour-stat-item';
            
            if (i === currentHour) item.classList.add('current-hour');
            if (i > currentHour) item.classList.add('disabled');

            let pretoValue, vermelhoValue, brancoValue;
            if (currentViewMode === 'percentage') {
                pretoValue = total > 0 ? `${((data.Preto / total) * 100).toFixed(0)}%` : '0%';
                vermelhoValue = total > 0 ? `${((data.Vermelho / total) * 100).toFixed(0)}%` : '0%';
                brancoValue = total > 0 ? `${((data.Branco / total) * 100).toFixed(0)}%` : '0%';
            } else { // 'count'
                pretoValue = data.Preto;
                vermelhoValue = data.Vermelho;
                brancoValue = data.Branco;
            }
            
            item.innerHTML = `
                <span class="hour-label">${hourKey}:00</span>
                <div class="color-counts-wrapper">
                    <div class="color-count preto-bg">${pretoValue}</div>
                    <div class="color-count vermelho-bg">${vermelhoValue}</div>
                    <div class="color-count branco-bg">${brancoValue}</div>
                </div>
            `;
            hourlyStatsGrid.appendChild(item);
        }
    }

    function renderIntervalAverages(data) {
        if (!intervalAveragesContainer) return;
        if (!data || data.erro || data.total_intervalos < 4) {
            intervalAveragesContainer.innerHTML = '<p class="no-data-message">Dados insuficientes (mínimo 4 intervalos).</p>';
            return;
        }
        intervalAveragesContainer.innerHTML = `
            <div class="stat-card"><div class="stat-value">${data.media_curta.toFixed(1)} min</div><div class="stat-label">Média Curta</div></div>
            <div class="stat-card"><div class="stat-value">${data.media_longa.toFixed(1)} min</div><div class="stat-label">Média Longa</div></div>`;
    }

    function renderSequences(sequences) {
        if (!sequenceListContainer || !sequenceItemTemplate) return;
        sequenceListContainer.innerHTML = '';
        if (!sequences || sequences.length === 0) {
            sequenceListContainer.innerHTML = '<p class="no-data-message">Nenhuma sequência encontrada com este comprimento.</p>';
            return;
        }
        const armedSequencesSet = new Set(armedSequences.map(s => JSON.stringify(s)));

        sequences.forEach((item, index) => {
            const cardClone = sequenceItemTemplate.content.cloneNode(true);
            const cardElement = cardClone.querySelector('.sequence-item');
            cardElement.querySelector('.sequence-rank').textContent = `#${index + 1}`;
            cardElement.querySelector('.sequence-count').textContent = `${item.count}x`;
            
            const iconsContainer = cardElement.querySelector('.sequence-icons');
            iconsContainer.innerHTML = '';
            item.sequence.forEach(color => {
                const span = document.createElement('span');
                span.className = colorClassMap[color] || '';
                span.textContent = emojiMap[color] || '';
                iconsContainer.appendChild(span);
            });
            
            const toggle = cardElement.querySelector('input[type="checkbox"]');
            toggle.dataset.sequence = JSON.stringify(item.sequence);
            toggle.checked = armedSequencesSet.has(toggle.dataset.sequence);

            sequenceListContainer.appendChild(cardElement);
        });
    }


    // --- LÓGICA DE SEQUÊNCIAS ARMADAS ---
    async function loadArmedSequences() {
        try {
            const response = await fetch('/api/sequences/armed');
            if (!response.ok) throw new Error('Falha ao buscar sequências armadas.');
            armedSequences = await response.json();
        } catch (error) {
            console.error(error);
            armedSequences = [];
        }
    }

    async function updateArmedSequences(sequence, shouldArm) {
        const sequenceStr = JSON.stringify(sequence);
        const index = armedSequences.findIndex(s => JSON.stringify(s) === sequenceStr);
        if (shouldArm && index === -1) {
            armedSequences.push(sequence);
        } else if (!shouldArm && index > -1) {
            armedSequences.splice(index, 1);
        }
        try {
            const response = await fetch('/api/sequences/arm', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(armedSequences)
            });
            if (!response.ok) throw new Error('Falha ao salvar sequência no servidor.');
            console.log('Sequências armadas atualizadas no servidor.');
        } catch (error) {
            console.error(error);
            alert('Erro ao atualizar sequência armada. Verifique o console.');
        }
    }

    // --- EVENTOS ---
    if (viewToggleButtons) {
        viewToggleButtons.addEventListener('click', (e) => {
            const clickedButton = e.target.closest('.toggle-btn');
            if (!clickedButton) return;

            const newView = clickedButton.dataset.view;
            if (newView === currentViewMode) return;

            currentViewMode = newView;
            
            viewToggleButtons.querySelectorAll('.toggle-btn').forEach(btn => btn.classList.remove('active'));
            clickedButton.classList.add('active');
            
            renderHourlyStats();
        });
    }

    if (sequenceFilterBtns.length > 0) {
        sequenceFilterBtns.forEach(btn => {
            if (parseInt(btn.dataset.length, 10) === currentSequenceLength) {
                btn.classList.add('active');
            }
            btn.addEventListener('click', () => {
                sequenceFilterBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentSequenceLength = parseInt(btn.dataset.length, 10);
                localStorage.setItem('sequenceLengthFilter', currentSequenceLength);
                fetchSequences();
            });
        });
    }

    if (sequenceListContainer) {
        sequenceListContainer.addEventListener('change', (e) => {
            if (e.target.matches('input[type="checkbox"]')) {
                const sequence = JSON.parse(e.target.dataset.sequence);
                updateArmedSequences(sequence, e.target.checked);
            }
        });
    }
    
    // --- INICIALIZAÇÃO ---
    async function initialize() {
        fetchHourlyColorStats();
        await loadArmedSequences();
        fetchIntervalAverages();
        fetchSequences();
        fetchAndRenderWhiteMinutesChart(); // ### ADICIONADO: Chama a função do gráfico ###
    }

    initialize();
});