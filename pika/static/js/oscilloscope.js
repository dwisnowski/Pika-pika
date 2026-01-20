/**
 * Oscilloscope JavaScript Module
 * Real-time oscilloscope visualization for ZMPT101B voltage sensor
 */

class Oscilloscope {
    constructor() {
        this.canvas = document.getElementById('scopeCanvas');
        this.ctx = this.canvas.getContext('2d');
        this.gridSvg = document.getElementById('scopeGrid');

        // Display settings
        this.voltsPerDiv = 0.5;  // V per division
        this.timePerDiv = 10;    // ms per division
        this.vPosition = 0;      // Vertical position offset (-100 to 100)
        this.divisions = { x: 10, y: 8 };

        // Data
        this.dataBuffer = [];
        this.maxBufferSize = 2000;
        this.running = true;
        this.singleCapture = false;

        // WebSocket
        this.websocket = null;
        this.batchMode = true;

        // CSV state
        this.csvEnabled = true;

        // ZMPT101B calibration
        // Assuming centered around 1.65V (half of 3.3V) with ~1V peak-to-peak for 120VAC
        this.adcOffset = 1.65;  // DC offset in ADC volts
        this.acScaleFactor = 120 * Math.sqrt(2);  // Peak voltage for 120VAC RMS

        // Measurements
        this.measurements = {
            vpp: 0,
            vrms: 0,
            freq: 0,
            acVoltage: 0
        };

        this.init();
    }

    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());

        this.setupControls();
        this.drawGrid();
        this.connectWebSocket();
        this.loadStatus();
        this.startRenderLoop();
    }

    resizeCanvas() {
        const container = this.canvas.parentElement;
        this.canvas.width = container.clientWidth;
        this.canvas.height = container.clientHeight;
        this.drawGrid();
    }

    setupControls() {
        // Volts/Div buttons
        document.querySelectorAll('[data-volts]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('[data-volts]').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.voltsPerDiv = parseFloat(e.target.dataset.volts);
            });
        });

        // Time/Div buttons
        document.querySelectorAll('[data-time]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('[data-time]').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.timePerDiv = parseInt(e.target.dataset.time);
            });
        });

        // Sample rate presets
        document.querySelectorAll('[data-rate]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('[data-rate]').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                const rate = parseInt(e.target.dataset.rate);
                document.getElementById('sampleRateInput').value = rate;
                this.setSampleRate(rate);
            });
        });

        // Sample rate input
        document.getElementById('sampleRateInput').addEventListener('change', (e) => {
            const rate = parseInt(e.target.value);
            if (rate >= 1 && rate <= 860) {
                this.setSampleRate(rate);
            }
        });

        // Channel buttons
        document.querySelectorAll('[data-channel]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('[data-channel]').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                const channel = parseInt(e.target.dataset.channel);
                this.setChannel(channel);
            });
        });

        // Vertical position
        document.getElementById('vPosition').addEventListener('input', (e) => {
            this.vPosition = parseInt(e.target.value);
        });

        // Run/Stop button
        document.getElementById('runStopBtn').addEventListener('click', () => {
            this.running = !this.running;
            this.updateRunStopButton();
        });

        // Single capture
        document.getElementById('singleBtn').addEventListener('click', () => {
            this.singleCapture = true;
            this.running = true;
            this.dataBuffer = [];
            this.updateRunStopButton();
        });

        // CSV toggle
        document.getElementById('csvToggle').addEventListener('click', () => {
            this.toggleCSV();
        });

        // Data mode toggle
        document.getElementById('realtimeBtn').addEventListener('click', () => {
            document.getElementById('realtimeBtn').classList.add('active');
            document.getElementById('batchBtn').classList.remove('active');
            this.batchMode = false;
        });

        document.getElementById('batchBtn').addEventListener('click', () => {
            document.getElementById('batchBtn').classList.add('active');
            document.getElementById('realtimeBtn').classList.remove('active');
            this.batchMode = true;
        });
    }

    updateRunStopButton() {
        const btn = document.getElementById('runStopBtn');
        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');

        if (this.running) {
            btn.textContent = 'RUN';
            btn.classList.remove('stopped');
            btn.classList.add('running');
            dot.classList.remove('paused');
            text.textContent = 'Streaming';
        } else {
            btn.textContent = 'STOP';
            btn.classList.remove('running');
            btn.classList.add('stopped');
            dot.classList.add('paused');
            text.textContent = 'Stopped';
        }
    }

    async loadStatus() {
        try {
            const res = await fetch('/api/oscilloscope/status');
            const status = await res.json();

            this.csvEnabled = status.csv_write_enabled;
            this.updateCSVDisplay();

            // Update sample rate input
            document.getElementById('sampleRateInput').value = status.sample_hz || 400;

            // Update channel button
            document.querySelectorAll('[data-channel]').forEach(b => b.classList.remove('active'));
            const activeChannel = document.querySelector(`[data-channel="${status.adc_channel || 0}"]`);
            if (activeChannel) activeChannel.classList.add('active');
        } catch (e) {
            console.error('Failed to load oscilloscope status', e);
        }
    }

    async toggleCSV() {
        this.csvEnabled = !this.csvEnabled;

        try {
            await fetch('/api/oscilloscope/mode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: !this.csvEnabled })  // oscilloscope mode = CSV disabled
            });
            this.updateCSVDisplay();
        } catch (e) {
            console.error('Failed to toggle CSV mode', e);
        }
    }

    updateCSVDisplay() {
        const toggle = document.getElementById('csvToggle');
        const status = document.getElementById('csvStatus');

        if (this.csvEnabled) {
            toggle.classList.remove('paused');
            status.textContent = 'ON';
        } else {
            toggle.classList.add('paused');
            status.textContent = 'OFF';
        }
    }

    async setSampleRate(rate) {
        try {
            await fetch('/api/oscilloscope/sample-rate', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sample_hz: rate })
            });
        } catch (e) {
            console.error('Failed to set sample rate', e);
        }
    }

    async setChannel(channel) {
        try {
            await fetch('/api/config/adc-channel', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ channel: channel })
            });
        } catch (e) {
            console.error('Failed to set channel', e);
        }
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/live`;

        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = () => {
            console.log('Oscilloscope WebSocket connected');
        };

        this.websocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (e) {
                console.error('Failed to parse message', e);
            }
        };

        this.websocket.onclose = () => {
            console.warn('WebSocket closed, reconnecting...');
            setTimeout(() => this.connectWebSocket(), 2000);
        };
    }

    handleMessage(data) {
        if (!this.running) return;

        switch (data.type) {
            case 'new_sample':
                this.addSample(data.data);
                break;
            case 'batch_samples':
                data.data.forEach(sample => this.addSample(sample));
                break;
            case 'recent_data':
                data.data.forEach(sample => this.addSample(sample));
                break;
        }

        // Single capture mode
        if (this.singleCapture && this.dataBuffer.length >= this.maxBufferSize / 2) {
            this.running = false;
            this.singleCapture = false;
            this.updateRunStopButton();
        }
    }

    addSample(sample) {
        const [timestamp, voltage] = sample;
        this.dataBuffer.push({ t: timestamp * 1000, v: voltage });  // Convert to ms

        // Limit buffer size
        while (this.dataBuffer.length > this.maxBufferSize) {
            this.dataBuffer.shift();
        }
    }

    drawGrid() {
        const svg = this.gridSvg;
        svg.innerHTML = '';

        const width = this.canvas.width;
        const height = this.canvas.height;

        // Grid lines
        for (let i = 0; i <= this.divisions.x; i++) {
            const x = (i / this.divisions.x) * width;
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', x);
            line.setAttribute('y1', 0);
            line.setAttribute('x2', x);
            line.setAttribute('y2', height);
            line.setAttribute('stroke', i === this.divisions.x / 2 ? '#444' : '#222');
            line.setAttribute('stroke-width', i === this.divisions.x / 2 ? '2' : '1');
            svg.appendChild(line);
        }

        for (let i = 0; i <= this.divisions.y; i++) {
            const y = (i / this.divisions.y) * height;
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', 0);
            line.setAttribute('y1', y);
            line.setAttribute('x2', width);
            line.setAttribute('y2', y);
            line.setAttribute('stroke', i === this.divisions.y / 2 ? '#444' : '#222');
            line.setAttribute('stroke-width', i === this.divisions.y / 2 ? '2' : '1');
            svg.appendChild(line);
        }
    }

    render() {
        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;

        // Clear
        ctx.fillStyle = '#0a0a0a';
        ctx.fillRect(0, 0, width, height);

        if (this.dataBuffer.length < 2) return;

        // Calculate visible time window
        const timeWindow = this.timePerDiv * this.divisions.x;  // Total ms visible
        const now = this.dataBuffer[this.dataBuffer.length - 1].t;
        const startTime = now - timeWindow;

        // Filter visible data
        const visibleData = this.dataBuffer.filter(d => d.t >= startTime);

        // Calculate Y scale
        const voltsVisible = this.voltsPerDiv * this.divisions.y;
        const yOffset = (this.vPosition / 100) * (height / 2);
        const yCenter = height / 2 + yOffset;

        // Draw waveform
        ctx.beginPath();
        ctx.strokeStyle = '#90CAF9';
        ctx.lineWidth = 2;

        let minV = Infinity, maxV = -Infinity, sumV = 0, sumVSq = 0;

        visibleData.forEach((point, i) => {
            const x = ((point.t - startTime) / timeWindow) * width;
            const y = yCenter - ((point.v - this.adcOffset) / voltsVisible) * height;

            if (i === 0) {
                ctx.moveTo(x, Math.max(0, Math.min(height, y)));
            } else {
                ctx.lineTo(x, Math.max(0, Math.min(height, y)));
            }

            // Measurements
            minV = Math.min(minV, point.v);
            maxV = Math.max(maxV, point.v);
            sumV += point.v;
            sumVSq += point.v * point.v;
        });

        ctx.stroke();

        // Update measurements
        if (visibleData.length > 0) {
            this.measurements.vpp = maxV - minV;
            this.measurements.vrms = Math.sqrt(sumVSq / visibleData.length);

            // Estimate AC voltage from ADC reading
            // ZMPT101B: Vpp on ADC corresponds to Vpeak of AC
            // Assuming linear scaling with Vpp of ~1V ADC = ~170V AC peak
            const acPeak = (this.measurements.vpp / 2) * 170;  // Rough estimate
            this.measurements.acVoltage = acPeak / Math.sqrt(2);  // Convert to RMS

            // Frequency via zero-crossing
            this.calculateFrequency(visibleData);
        }

        this.updateMeasurementDisplay();
    }

    calculateFrequency(data) {
        if (data.length < 10) return;

        const mean = data.reduce((s, d) => s + d.v, 0) / data.length;
        let crossings = [];

        for (let i = 1; i < data.length; i++) {
            if ((data[i - 1].v < mean && data[i].v >= mean) ||
                (data[i - 1].v >= mean && data[i].v < mean)) {
                crossings.push(data[i].t);
            }
        }

        if (crossings.length >= 2) {
            const avgPeriod = (crossings[crossings.length - 1] - crossings[0]) / (crossings.length - 1);
            this.measurements.freq = 1000 / (avgPeriod * 2);  // Half period to full period
        }
    }

    updateMeasurementDisplay() {
        document.getElementById('measVpp').textContent = this.measurements.vpp.toFixed(3) + ' V';
        document.getElementById('measVrms').textContent = this.measurements.vrms.toFixed(3) + ' V';
        document.getElementById('measFreq').textContent = this.measurements.freq.toFixed(1) + ' Hz';
        document.getElementById('measAC').textContent = this.measurements.acVoltage.toFixed(1) + ' V';
    }

    startRenderLoop() {
        const loop = () => {
            this.render();
            requestAnimationFrame(loop);
        };
        requestAnimationFrame(loop);
    }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    window.oscilloscope = new Oscilloscope();
});
