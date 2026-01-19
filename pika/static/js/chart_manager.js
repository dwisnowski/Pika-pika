class PikaChartManager {
    constructor(options = {}) {
        this.options = {
            wsPath: options.wsPath || '/ws/live',
            rangeApiPath: options.rangeApiPath || '/api/range',
            sampleRatePath: options.sampleRatePath || '/api/config/sample-rate',
            timeWindowStorageKey: options.timeWindowStorageKey || 'pika-time-window',
            voltageLabel: options.voltageLabel || 'Voltage',
            enableSampleRateControls: options.enableSampleRateControls !== false,
            enableRangeFetchOnZoom: options.enableRangeFetchOnZoom !== false,
            enableHighlightShading: options.enableHighlightShading !== false,
            maxRangePoints: options.maxRangePoints || 3000,
            rangeQueryParams: options.rangeQueryParams || {},
        };

        this.chart = null;
        this.websocket = null;
        this.liveMode = true;
        this.renderInterval = null;
        this.renderQueue = [];
        this.targetFps = 60;
        this.lastRender = 0;

        this.init();
    }

    init() {
        this.setupChart();
        this.setupEventListeners();
        this.loadTimeWindow();
        this.connectWebSocket();
        this.setupQRCode();
        this.updateChartIntervals();
        this.startRenderLoop();
        this.loadAnalysisConfig();

        if (!this.options.enableSampleRateControls) {
            const controls = document.getElementById('sampleRate')?.parentElement;
            if (controls) {
                controls.style.display = 'none';
            }
        }
    }

    startRenderLoop() {
        const render = (now) => {
            requestAnimationFrame(render);

            const interval = 1000 / this.targetFps;
            const delta = now - this.lastRender;

            if (delta > interval) {
                this.lastRender = now - (delta % interval);
                this.processRenderQueue();
            }
        };
        requestAnimationFrame(render);
    }

    processRenderQueue() {
        if (!this.chart || this.renderQueue.length === 0) return;

        // Process all queued points
        const points = this.renderQueue.splice(0, this.renderQueue.length);

        // Add to chart
        points.forEach(p => {
            this.chart.data.labels.push(p.x);
            this.chart.data.datasets[0].data.push(p);
        });

        // Prune old data (performance)
        // Keep slightly more than window to allow smooth scrolling?
        // Actually, applyTimeWindowFilter does filtering, but we should remove from dataset too.
        // For simple pruning:
        const maxPoints = 5000; // Safety limit
        if (this.chart.data.labels.length > maxPoints) {
            const removeCount = this.chart.data.labels.length - maxPoints;
            this.chart.data.labels.splice(0, removeCount);
            this.chart.data.datasets[0].data.splice(0, removeCount);
        }

        this.applyTimeWindowFilter();
        this.chart.update('none');

        // Update Text Display (use last point)
        if (points.length > 0) {
            const last = points[points.length - 1];
            const voltageDisplay = document.getElementById('qr_voltage');
            if (voltageDisplay) {
                voltageDisplay.innerText = last.y.toFixed(3) + ' V';
            }
        }
    }

    setupEventListeners() {
        document.querySelectorAll('input[name="timeWindow"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.saveTimeWindow(parseInt(e.target.value));
            });
        });

        const updateRateBtn = document.getElementById('updateRateBtn');
        if (updateRateBtn) {
            updateRateBtn.addEventListener('click', () => {
                this.updateSampleRate();
            });
        }

        const resetViewBtn = document.getElementById('resetView');
        if (resetViewBtn) {
            resetViewBtn.addEventListener('click', () => {
                this.resetView();
            });
        }

        const copyBtn = document.getElementById('copyBtn');
        if (copyBtn) {
            copyBtn.addEventListener('click', async () => {
                await this.copyURL();
            });
        }

        // Settings Modal Controls
        const settingsBtn = document.getElementById('settingsBtn');
        const closeSettingsBtn = document.getElementById('settingsBtnClose') || document.getElementById('closeSettingsBtn'); // Handle multiple potential IDs
        const settingsModal = document.getElementById('settingsModal');

        if (settingsBtn && settingsModal) {
            settingsBtn.addEventListener('click', () => {
                settingsModal.style.display = 'flex';
                this.loadAnalysisConfig(); // Reload fresh status
            });
        }

        if (closeSettingsBtn && settingsModal) {
            closeSettingsBtn.addEventListener('click', () => settingsModal.style.display = 'none');
        }

        const updateAnalysisBtn = document.getElementById('updateAnalysisBtn');
        if (updateAnalysisBtn) {
            updateAnalysisBtn.addEventListener('click', () => this.saveAnalysisConfig());
        }

        const chartFpsSelect = document.getElementById('chartFps');
        if (chartFpsSelect) {
            chartFpsSelect.addEventListener('change', (e) => {
                this.targetFps = parseInt(e.target.value);
            });
        }
    }

    setupChart() {
        const ctx = document.getElementById('chart').getContext('2d');
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: this.options.voltageLabel,
                        data: [],
                        borderColor: '#90CAF9',
                        borderWidth: 2,
                        pointRadius: 0,
                        fill: false,
                        tension: 0.1,
                        segment: {
                            borderColor: ctx => {
                                if (ctx.p0.parsed.y > 3.0 || ctx.p0.parsed.y < 0.3) return '#FF6B6B';
                                return undefined; // use default
                            }
                        }
                    },
                    {
                        label: 'Anomalies',
                        data: [],
                        backgroundColor: 'rgba(255, 107, 107, 0.2)',
                        pointBackgroundColor: '#FF6B6B',
                        pointRadius: 5,
                        showLine: false
                    },
                    {
                        label: 'Min',
                        data: [],
                        pointBackgroundColor: '#FF6B6B',
                        pointRadius: 4,
                        showLine: false
                    },
                    {
                        label: 'Max',
                        data: [],
                        pointBackgroundColor: '#90CAF9',
                        pointRadius: 4,
                        showLine: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                parsing: false, // Performance
                normalized: true, // Performance
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'second',
                            displayFormats: { second: 'HH:mm:ss' }
                        },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    },
                    y: {
                        beginAtZero: true,
                        suggestedMax: 3.3,
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    }
                },
                plugins: {
                    legend: { display: false },
                    zoom: {
                        pan: { enabled: true, mode: 'x' },
                        zoom: {
                            wheel: { enabled: true },
                            pinch: { enabled: true },
                            mode: 'x',
                            onZoomComplete: ({ chart }) => this.onRangeChanged(chart)
                        }
                    }
                }
            }
        });
    }

    setupQRCode() {
        const canvas = document.getElementById('qrcode');
        if (!canvas) return;
        const url = window.location.origin;
        QRCode.toCanvas(canvas, url, {
            width: 120,
            margin: 2,
            color: { dark: '#ffffff', light: '#00000000' }
        }, (err) => {
            if (err) console.error(err);
        });
    }

    async copyURL() {
        try {
            await navigator.clipboard.writeText(window.location.origin);
            const btn = document.getElementById('copyBtn');
            const original = btn.innerText;
            btn.innerText = 'Copied!';
            setTimeout(() => btn.innerText = original, 2000);
        } catch (err) {
            console.error('Failed to copy', err);
        }
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}${this.options.wsPath}`;

        console.log('Connecting to WebSocket:', wsUrl);
        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
        };

        this.websocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (e) {
                console.error('Failed to parse WS message', e);
            }
        };

        this.websocket.onclose = () => {
            console.warn('WebSocket closed. Attempting reconnect...');
            this.attemptReconnect();
        };

        this.websocket.onerror = (err) => {
            console.error('WebSocket error:', err);
        };
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'recent_data':
                this.updateChartData(data.data);
                break;
            case 'new_sample':
                this.addNewSample(data.data);
                break;
            case 'highlights':
                this.renderHighlightsList(data.highlights);
                this.highlightsCacheAll = data.highlights;
                this.highlightsCache = data.highlights;
                break;
            case 'config_update':
                // Optional: update UI if config changed from another client
                break;
            case 'ping':
                break;
        }
    }

    updateChartData(data) {
        if (!this.chart) return;
        if (!data || !data.length) return;

        this.chart.data.labels = data.map(d => new Date(d[0] * 1000));
        this.chart.data.datasets[0].data = data.map(d => ({ x: new Date(d[0] * 1000), y: d[1] }));
        this.chart.update();

        this.applyTimeWindowFilter();
        this.chart.update('none');
    }

    addNewSample(data) {
        // Instead of updating immediately, push to queue
        const [timestamp, voltage] = data;
        this.renderQueue.push({ x: new Date(timestamp * 1000), y: voltage });
    }

    async loadAnalysisConfig() {
        try {
            const res = await fetch('/api/config/analysis');
            const config = await res.json();

            document.getElementById('enableRms').checked = config.enable_rms !== false;
            document.getElementById('enableFreq').checked = config.enable_freq !== false;
            document.getElementById('enableSags').checked = config.enable_sags_swells !== false;
        } catch (e) {
            console.error("Failed to load analysis config", e);
        }
    }

    async saveAnalysisConfig() {
        const config = {
            enable_rms: document.getElementById('enableRms').checked,
            enable_freq: document.getElementById('enableFreq').checked,
            enable_sags_swells: document.getElementById('enableSags').checked
        };

        try {
            await fetch('/api/config/analysis', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            // Visual feedback?
            const btn = document.getElementById('updateAnalysisBtn');
            const original = btn.textContent;
            btn.textContent = "Saved!";
            setTimeout(() => btn.textContent = original, 1500);

        } catch (e) {
            console.error("Failed to save analysis config", e);
            alert("Failed to save configuration");
        }
    }

    // ... renderHighlightsList, focusOnHighlight, resetView, load/saveTimeWindow ...

    // ... updateChartIntervals, applyTimeWindowFilter, updateMinMaxDisplay, updateSampleRate ...

    // ... fetchRange, onRangeChanged, attemptReconnect, triggerAnomaly ...


    renderHighlightsList(highlights) {
        const container = document.getElementById('highlightsList');
        if (!container) return;

        container.innerHTML = '';

        if (!highlights || !highlights.length) {
            container.innerText = 'No anomalies detected.';
            return;
        }

        highlights.sort((a, b) => b.score - a.score);
        highlights.forEach((h, idx) => {
            const el = document.createElement('div');
            el.style.padding = '6px';
            el.style.borderBottom = '1px solid #eee';

            const start = new Date(h.start_ts * 1000).toLocaleString();
            const end = new Date(h.end_ts * 1000).toLocaleString();

            el.innerHTML = `<strong>#${idx + 1}</strong> <br/>Peak: ${h.peak_value.toFixed(3)} @ ${new Date(h.peak_ts * 1000).toLocaleTimeString()}<br/><small>${start} → ${end}</small>`;
            el.style.cursor = 'pointer';
            el.addEventListener('click', () => this.focusOnHighlight(h));
            container.appendChild(el);
        });
    }

    focusOnHighlight(h) {
        if (!this.chart) return;

        const peak = h.peak_ts * 1000;
        const width = Math.max((h.end_ts - h.start_ts) * 1000 * 2, 10000);

        this.chart.options.scales.x.min = new Date(peak - width / 2);
        this.chart.options.scales.x.max = new Date(peak + width / 2);

        this.chart.data.datasets[4] = this.chart.data.datasets[4] || {
            type: 'line',
            label: 'Focus Marker',
            data: [],
            borderColor: 'white',
            borderWidth: 1,
            pointRadius: 0,
            fill: false
        };

        this.chart.data.datasets[4].data = [
            { x: new Date(peak), y: 0 },
            { x: new Date(peak), y: 3.3 }
        ];

        this.highlightsCache = [h];
        this.chart.update();
    }

    resetView() {
        if (!this.chart) return;

        this.chart.options.scales.x.min = undefined;
        this.chart.options.scales.x.max = undefined;
        this.highlightsCache = this.highlightsCacheAll || [];
        this.chart.update();
    }

    loadTimeWindow() {
        const saved = localStorage.getItem(this.options.timeWindowStorageKey);
        if (saved) {
            this.selectedTimeWindow = parseInt(saved, 10);
            const radio = document.querySelector(`input[name="timeWindow"][value="${this.selectedTimeWindow}"]`);
            if (radio) {
                radio.checked = true;
            }
        }
        this.applyTimeWindowFilter();
    }

    saveTimeWindow(seconds) {
        this.selectedTimeWindow = seconds;
        localStorage.setItem(this.options.timeWindowStorageKey, seconds.toString());
        this.updateChartIntervals();
        this.applyTimeWindowFilter();
    }

    updateChartIntervals() {
        if (!this.chart) return;
        const seconds = this.selectedTimeWindow;
        let unit = 'second';
        let stepSize = 1;

        if (seconds <= 10) { stepSize = 1; }
        else if (seconds <= 30) { stepSize = 5; }
        else if (seconds <= 60) { stepSize = 10; }
        else if (seconds <= 300) { unit = 'minute'; stepSize = 1; }
        else { unit = 'minute'; stepSize = 2; }

        this.chart.options.scales.x.time.unit = unit;
        this.chart.options.scales.x.time.stepSize = stepSize;
        this.chart.update('none');
    }

    applyTimeWindowFilter() {
        if (!this.chart) return;

        const now = Date.now();
        const cutoff = now - (this.selectedTimeWindow * 1000);

        const filteredLabels = [];
        const filteredData = [];

        this.chart.data.labels.forEach((label, index) => {
            if (label.getTime() >= cutoff) {
                filteredLabels.push(label);
                filteredData.push(this.chart.data.datasets[0].data[index]);
            }
        });

        this.chart.data.labels = filteredLabels;
        this.chart.data.datasets[0].data = filteredData;

        this.updateMinMaxDisplay();
    }

    updateMinMaxDisplay() {
        if (!this.chart) return;

        const data = this.chart.data.datasets[0].data;
        let minPoint = null;
        let maxPoint = null;

        data.forEach(point => {
            if (point && typeof point.y === 'number') {
                if (!minPoint || point.y < minPoint.y) minPoint = point;
                if (!maxPoint || point.y > maxPoint.y) maxPoint = point;
            }
        });

        const minEl = document.getElementById('minVoltage');
        const maxEl = document.getElementById('maxVoltage');

        if (minPoint && maxPoint) {
            if (minEl) minEl.textContent = minPoint.y.toFixed(3) + 'V';
            if (maxEl) maxEl.textContent = maxPoint.y.toFixed(3) + 'V';

            // Update Markers
            this.chart.data.datasets[2].data = [minPoint];
            this.chart.data.datasets[3].data = [maxPoint];
        } else {
            if (minEl) minEl.textContent = '0.000V';
            if (maxEl) maxEl.textContent = '0.000V';
            this.chart.data.datasets[2].data = [];
            this.chart.data.datasets[3].data = [];
        }
    }

    async updateSampleRate() {
        const rateInput = document.getElementById('sampleRate');
        const currentRateSpan = document.getElementById('currentRate');

        if (!rateInput || !currentRateSpan) return;

        const newRate = parseInt(rateInput.value);
        if (newRate < 1 || newRate > 100) {
            alert('Sample rate must be between 1 and 100 Hz');
            return;
        }

        try {
            const response = await fetch(this.options.sampleRatePath, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sample_hz: newRate })
            });

            const result = await response.json();
            if (result.success) {
                currentRateSpan.textContent = ` (Updated to ${newRate} Hz)`;
                setTimeout(() => {
                    currentRateSpan.textContent = '';
                }, 3000);
            } else {
                currentRateSpan.textContent = ' (Update failed)';
            }
        } catch (error) {
            console.error('Failed to update sample rate:', error);
            currentRateSpan.textContent = ' (Error)';
        }
    }

    async fetchRange(startMs, endMs) {
        if (!this.chart) return;

        const start = Math.floor(startMs / 1000);
        const end = Math.floor(endMs / 1000);
        const maxp = this.options.maxRangePoints;

        try {
            const url = new URL(this.options.rangeApiPath, window.location.origin);
            url.searchParams.set('start', String(start));
            url.searchParams.set('end', String(end));
            url.searchParams.set('max_points', String(maxp));
            Object.entries(this.options.rangeQueryParams || {}).forEach(([k, v]) => {
                url.searchParams.set(k, String(v));
            });

            const res = await fetch(url.toString());
            const payload = await res.json();

            const data = payload.data || payload.points || [];

            this.chart.data.labels = data.map(d => new Date(d[0] * 1000));
            this.chart.data.datasets[0].data = data.map(d => ({ x: new Date(d[0] * 1000), y: d[1] }));
            this.chart.update();
            this.updateMinMaxDisplay();
        } catch (e) {
            console.error('range fetch error', e);
        }
    }

    onRangeChanged(chartInstance) {
        if (!this.options.enableRangeFetchOnZoom) return;

        const xscale = chartInstance.scales.x;
        const min = xscale.min;
        const max = xscale.max;

        if (min != null && max != null) {
            this.fetchRange(min, max);
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);

        setTimeout(() => {
            this.connectWebSocket();
        }, delay);
    }

    triggerAnomaly(type = 'spike') {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                type: 'trigger_anomaly',
                anomaly_type: type
            }));
        }
    }
}
