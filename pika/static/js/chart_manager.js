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
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.selectedTimeWindow = 60;
        this.highlightsCache = [];
        this.highlightsCacheAll = [];

        this.init();
    }

    init() {
        this.setupChart();
        this.setupEventListeners();
        this.loadTimeWindow();
        this.connectWebSocket();
        this.setupQRCode();
        this.updateChartIntervals();
        if (!this.options.enableSampleRateControls) {
            const controls = document.getElementById('sampleRate')?.parentElement;
            if (controls) {
                controls.style.display = 'none';
            }
        }
    }

    setupChart() {
        const ctx = document.getElementById('chart')?.getContext('2d');
        if (!ctx) return;

        const highlightPlugin = {
            id: 'highlightPlugin',
            afterDraw: (chart) => {
                if (!this.options.enableHighlightShading) return;
                const highlights = this.highlightsCache || [];
                if (!highlights.length) return;
                const xScale = chart.scales['x'];
                const _ctx = chart.ctx;
                const top = chart.chartArea.top;
                const bottom = chart.chartArea.bottom;
                _ctx.save();
                _ctx.globalAlpha = 0.08;
                _ctx.fillStyle = 'rgb(220,20,60)';
                highlights.forEach(h => {
                    const x1 = xScale.getPixelForValue(new Date(h.start_ts * 1000));
                    const x2 = xScale.getPixelForValue(new Date(h.end_ts * 1000));
                    _ctx.fillRect(x1, top, Math.max(1, x2 - x1), bottom - top);
                });
                _ctx.restore();
            }
        };

        Chart.defaults.color = '#eaeaea';
        Chart.defaults.backgroundColor = 'transparent';

        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: this.options.voltageLabel,
                        data: [],
                        borderColor: '#90CAF9',
                        backgroundColor: 'rgba(144,202,249,0.06)',
                        tension: 0.1,
                        pointRadius: 0
                    },
                    {
                        label: 'Anomalies',
                        data: [],
                        borderColor: '#FF6B6B',
                        backgroundColor: '#FF6B6B',
                        showLine: false,
                        pointRadius: 5
                    }
                ]
            },
            options: {
                animation: false,
                plugins: {
                    zoom: {
                        pan: { enabled: true, mode: 'x', modifierKey: 'ctrl' },
                        zoom: {
                            wheel: { enabled: true },
                            mode: 'x',
                            pinch: { enabled: true },
                            onZoomComplete: ({ chart }) => this.onRangeChanged(chart)
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'second',
                            displayFormats: { second: 'HH:mm:ss' }
                        },
                        ticks: { display: false },
                        grid: {
                            color: 'rgba(255,255,255,0.08)',
                            lineWidth: (ctx) => ctx.tick.major ? 2 : 1
                        }
                    },
                    y: {
                        suggestedMin: 0,
                        suggestedMax: 3.3,
                        ticks: { color: '#d0d0d0' },
                        grid: { color: 'rgba(255,255,255,0.04)' }
                    }
                }
            },
            plugins: [highlightPlugin]
        });
    }

    setupEventListeners() {
        document.querySelectorAll('input[name="timeWindow"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.saveTimeWindow(parseInt(e.target.value));
            });
        });

        const updateRateBtn = document.getElementById('updateRateBtn');
        if (updateRateBtn && this.options.enableSampleRateControls) {
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
    }

    setupQRCode() {
        const origin = window.location.origin;
        const qrbox = document.getElementById('qrcode');
        const qurl = document.getElementById('qurl');

        if (!qrbox) return;
        if (qurl) qurl.textContent = origin;

        qrbox.innerHTML = ''; // Clear existing

        if (typeof QRCode !== 'undefined') {
            const canvas = document.createElement('canvas');
            qrbox.appendChild(canvas);
            QRCode.toCanvas(canvas, origin, { width: 160 }, function (err) {
                if (err) console.error(err);
            });
        } else {
            const img = document.createElement('img');
            img.src = 'https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=' + encodeURIComponent(origin);
            qrbox.appendChild(img);
        }
    }

    async copyURL() {
        const origin = window.location.origin;
        const copyBtn = document.getElementById('copyBtn');

        try {
            await navigator.clipboard.writeText(origin);
            if (copyBtn) {
                copyBtn.textContent = 'Copied!';
                setTimeout(() => copyBtn.textContent = 'Copy URL', 1500);
            }
        } catch (e) {
            console.error('copy failed', e);
            if (copyBtn) {
                copyBtn.textContent = 'Copy failed';
                setTimeout(() => copyBtn.textContent = 'Copy URL', 1500);
            }
        }
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}${this.options.wsPath}`;

        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = () => {
            this.reconnectAttempts = 0;
        };

        this.websocket.onmessage = (event) => {
            this.handleWebSocketMessage(JSON.parse(event.data));
        };

        this.websocket.onclose = () => {
            this.attemptReconnect();
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
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
        if (!this.chart) return;
        const [timestamp, voltage] = data;
        const point = { x: new Date(timestamp * 1000), y: voltage };

        this.chart.data.labels.push(point.x);
        this.chart.data.datasets[0].data.push(point);

        this.applyTimeWindowFilter();
        this.chart.update('none');

        const voltageDisplay = document.getElementById('qr_voltage');
        if (voltageDisplay) {
            voltageDisplay.innerText = voltage.toFixed(3) + ' V';
        }
    }

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

        this.chart.data.datasets[2] = this.chart.data.datasets[2] || {
            type: 'line',
            label: 'Marker',
            data: [],
            borderColor: 'black',
            borderWidth: 1,
            pointRadius: 0,
            fill: false
        };

        this.chart.data.datasets[2].data = [
            { x: new Date(peak), y: null },
            { x: new Date(peak), y: null }
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
}
