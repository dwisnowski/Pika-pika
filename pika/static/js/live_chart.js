// Live Chart JavaScript Module
// Handles real-time voltage monitoring with WebSocket updates

class LiveChartManager {
    constructor() {
        this.chart = null;
        this.websocket = null;
        this.liveMode = true;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.selectedTimeWindow = 60; // Default to 60 seconds
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
    }

    setupChart() {
        const ctx = document.getElementById('chart').getContext('2d');

        // Plugin to draw shaded rectangles for highlight durations
        const highlightPlugin = {
            id: 'highlightPlugin',
            afterDraw: (chart, args, options) => {
                const highlights = this.highlightsCache || [];
                if (!highlights.length) return;
                const xScale = chart.scales['x'];
                const ctx = chart.ctx;
                const top = chart.chartArea.top;
                const bottom = chart.chartArea.bottom;
                ctx.save();
                ctx.globalAlpha = 0.08;
                ctx.fillStyle = 'rgb(220,20,60)';
                highlights.forEach(h => {
                    const x1 = xScale.getPixelForValue(new Date(h.start_ts * 1000));
                    const x2 = xScale.getPixelForValue(new Date(h.end_ts * 1000));
                    // Draw rectangle
                    ctx.fillRect(x1, top, Math.max(1, x2 - x1), bottom - top);
                });
                ctx.restore();
            }
        };

        // Apply Chart.js dark colors
        Chart.defaults.color = '#eaeaea';
        Chart.defaults.backgroundColor = 'transparent';

        this.chart = new Chart(ctx, {
            type: 'line',
            data: { 
                labels: [], 
                datasets: [
                    { 
                        label: 'Voltage', 
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
                        zoom: { wheel: { enabled: true }, mode: 'x', pinch: { enabled: true }, onZoomComplete: ({chart}) => this.onRangeChanged(chart) }
                    }
                },
                scales: { 
                    x: { 
                        type: 'time', 
                        time: { unit: 'second', tooltipFormat: 'HH:mm:ss.SSS' }, 
                        ticks: { color: '#d0d0d0' }, 
                        grid: { color: 'rgba(255,255,255,0.04)' } 
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
        // Time window radio buttons
        document.querySelectorAll('input[name="timeWindow"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.saveTimeWindow(parseInt(e.target.value));
            });
        });

        // Sample rate update
        document.getElementById('updateRateBtn').addEventListener('click', () => {
            this.updateSampleRate();
        });

        // Reset view button
        document.getElementById('resetView').addEventListener('click', () => {
            this.resetView();
        });

        // Copy URL button
        document.getElementById('copyBtn').addEventListener('click', async () => {
            await this.copyURL();
        });
    }

    setupQRCode() {
        const origin = window.location.origin;
        const qrbox = document.getElementById('qrcode');
        const qurl = document.getElementById('qurl');
        
        if (qurl) qurl.textContent = origin;

        // Try to generate QR code locally
        if (typeof QRCode !== 'undefined') {
            QRCode.toCanvas(qrbox, origin, { width: 160 }, function (err) {
                if (err) console.error(err);
            });
        } else {
            // Fallback to img-based API
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
            copyBtn.textContent = 'Copied!';
            setTimeout(() => copyBtn.textContent = 'Copy URL', 1500);
        } catch (e) {
            console.error('copy failed', e);
            copyBtn.textContent = 'Copy failed';
            setTimeout(() => copyBtn.textContent = 'Copy URL', 1500);
        }
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/live`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
        };

        this.websocket.onmessage = (event) => {
            this.handleWebSocketMessage(JSON.parse(event.data));
        };

        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
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
                break;
            case 'ping':
                // Keep connection alive
                break;
        }
    }

    updateChartData(data) {
        if (!data || !data.length) return;
        
        this.chart.data.labels = data.map(d => new Date(d[0] * 1000));
        this.chart.data.datasets[0].data = data.map(d => ({x: new Date(d[0] * 1000), y: d[1]}));
        this.chart.update();
    }

    addNewSample(data) {
        const [timestamp, voltage] = data;
        const point = {x: new Date(timestamp * 1000), y: voltage};
        
        this.chart.data.labels.push(point.x);
        this.chart.data.datasets[0].data.push(point);
        
        // Keep only recent data points based on time window
        this.applyTimeWindowFilter();
        
        this.chart.update('none'); // Update without animation for live data
    }

    renderHighlightsList(highlights) {
        const container = document.getElementById('highlightsList');
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
            
            el.innerHTML = `<strong>#${idx+1}</strong> <br/>Peak: ${h.peak_value.toFixed(3)} @ ${new Date(h.peak_ts*1000).toLocaleTimeString()}<br/><small>${start} → ${end}</small>`;
            el.style.cursor = 'pointer';
            el.addEventListener('click', () => this.focusOnHighlight(h));
            container.appendChild(el);
        });
    }

    focusOnHighlight(h) {
        // Zoom x axis to highlight ± window
        const peak = h.peak_ts * 1000;
        const width = Math.max((h.end_ts - h.start_ts) * 1000 * 2, 10000); // At least 10s window
        
        this.chart.options.scales.x.min = new Date(peak - width/2);
        this.chart.options.scales.x.max = new Date(peak + width/2);
        
        // Add a temporary vertical marker dataset
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
            {x: new Date(peak), y: null}, 
            {x: new Date(peak), y: null}
        ];
        
        // Rely on plugin to draw shaded region; cache highlights for plugin
        this.highlightsCache = [h];
        this.chart.update();
    }

    resetView() {
        this.chart.options.scales.x.min = undefined;
        this.chart.options.scales.x.max = undefined;
        this.highlightsCache = this.highlightsCacheAll || [];
        this.chart.update();
    }

    async updateSampleRate() {
        const rateInput = document.getElementById('sampleRate');
        const currentRateSpan = document.getElementById('currentRate');
        const newRate = parseInt(rateInput.value);
        
        if (newRate < 1 || newRate > 100) {
            alert('Sample rate must be between 1 and 100 Hz');
            return;
        }

        try {
            const response = await fetch('/api/config/sample-rate', {
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
        const start = Math.floor(startMs / 1000);
        const end = Math.floor(endMs / 1000);
        const maxp = 3000; // Request up to 3000 points for responsive view
        
        try {
            const res = await fetch(`/api/range?start=${start}&end=${end}&max_points=${maxp}`);
            const payload = await res.json();
            const data = payload.data || [];
            
            this.chart.data.labels = data.map(d => new Date(d[0] * 1000));
            this.chart.data.datasets[0].data = data.map(d => ({x: new Date(d[0] * 1000), y: d[1]}));
            this.chart.update();
        } catch (e) {
            console.error('range fetch error', e);
        }
    }

    onRangeChanged(chartInstance) {
        const xscale = chartInstance.scales.x;
        const min = xscale.min; // ms
        const max = xscale.max; // ms
        
        if (min != null && max != null) {
            // If zoomed to more than a small window, fetch aggregated data
            this.fetchRange(min, max);
        }
    }

    loadTimeWindow() {
        const saved = localStorage.getItem('pika-time-window');
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
        localStorage.setItem('pika-time-window', seconds.toString());
        this.applyTimeWindowFilter();
    }

    applyTimeWindowFilter() {
        const now = Date.now();
        const cutoff = now - (this.selectedTimeWindow * 1000);
        
        // Filter existing data
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
        this.chart.update('none');
    }

    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
        
        console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
        
        setTimeout(() => {
            this.connectWebSocket();
        }, delay);
    }
}

// Initialize the chart manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.liveChartManager = new LiveChartManager();
});
