// Demo Chart JavaScript Module
// Handles demo page chart functionality with simulated data

class DemoChartManager {
    constructor() {
        this.chart = null;
        this.websocket = null;
        this.liveMode = true;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.selectedTimeWindow = 60; // Default to 60 seconds
        
        this.init();
    }

    init() {
        this.setupChart();
        this.setupEventListeners();
        this.connectWebSocket();
        this.setupQRCode();
    }

    setupChart() {
        const ctx = document.getElementById('chart').getContext('2d');

        // Apply Chart.js dark colors
        Chart.defaults.color = '#eaeaea';
        Chart.defaults.backgroundColor = 'transparent';

        this.chart = new Chart(ctx, {
            type: 'line',
            data: { 
                labels: [], 
                datasets: [
                    { 
                        label: 'Demo Voltage', 
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
                        zoom: { wheel: { enabled: true }, mode: 'x', pinch: { enabled: true } }
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
            }
        });
    }

    setupEventListeners() {
        // Time window radio buttons
        document.querySelectorAll('input[name="timeWindow"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.saveTimeWindow(parseInt(e.target.value));
            });
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
        const wsUrl = `${protocol}//${window.location.host}/ws/demo`;
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('Demo WebSocket connected');
            this.reconnectAttempts = 0;
        };

        this.websocket.onmessage = (event) => {
            this.handleWebSocketMessage(JSON.parse(event.data));
        };

        this.websocket.onclose = () => {
            console.log('Demo WebSocket disconnected');
            this.attemptReconnect();
        };

        this.websocket.onerror = (error) => {
            console.error('Demo WebSocket error:', error);
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
            container.innerText = 'No anomalies detected in demo data.';
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
        
        this.chart.update();
    }

    resetView() {
        this.chart.options.scales.x.min = undefined;
        this.chart.options.scales.x.max = undefined;
        this.chart.update();
    }

    saveTimeWindow(seconds) {
        this.selectedTimeWindow = seconds;
        localStorage.setItem('pika-demo-time-window', seconds.toString());
        this.applyTimeWindowFilter();
    }

    loadTimeWindow() {
        const saved = localStorage.getItem('pika-demo-time-window');
        if (saved) {
            this.selectedTimeWindow = parseInt(saved, 10);
            const radio = document.querySelector(`input[name="timeWindow"][value="${this.selectedTimeWindow}"]`);
            if (radio) {
                radio.checked = true;
            }
        }
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

// Initialize the demo chart manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.demoChartManager = new DemoChartManager();
});
