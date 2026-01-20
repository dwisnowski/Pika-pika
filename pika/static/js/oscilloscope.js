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
        this.maxBufferSize = 4000;  // Increased for more cycle data
        this.running = true;
        this.singleCapture = false;

        // WebSocket
        this.websocket = null;
        this.batchMode = true;

        // CSV state
        this.csvEnabled = true;

        // ZMPT101B calibration
        this.adcOffset = 1.65;  // DC offset in ADC volts
        this.acScaleFactor = 120 * Math.sqrt(2);  // Peak voltage for 120VAC RMS

        // Low-pass filter settings
        this.lpfEnabled = true;
        this.lpfCutoff = 120;  // Hz (default for 60Hz signal, allows 2nd harmonic)
        this.filteredBuffer = [];

        // Display mode: 'rolling' or 'cycle'
        this.displayMode = 'rolling';

        // RMS envelope
        this.showRMSEnvelope = false;
        this.rmsWindowMs = 16.67;  // ~1 cycle at 60Hz
        this.rmsEnvelopeBuffer = [];

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

        // Low-pass filter toggle
        const lpfToggle = document.getElementById('lpfToggle');
        if (lpfToggle) {
            lpfToggle.addEventListener('click', () => {
                this.lpfEnabled = !this.lpfEnabled;
                lpfToggle.classList.toggle('active', this.lpfEnabled);
            });
        }

        // LPF cutoff slider
        const lpfCutoffInput = document.getElementById('lpfCutoff');
        const lpfCutoffValue = document.getElementById('lpfCutoffValue');
        if (lpfCutoffInput) {
            lpfCutoffInput.addEventListener('input', (e) => {
                this.lpfCutoff = parseInt(e.target.value);
                if (lpfCutoffValue) lpfCutoffValue.textContent = this.lpfCutoff + ' Hz';
            });
        }

        // Display mode toggle (rolling vs cycle-locked)
        const modeRolling = document.getElementById('modeRolling');
        const modeCycle = document.getElementById('modeCycle');
        if (modeRolling) {
            modeRolling.addEventListener('click', () => {
                this.displayMode = 'rolling';
                modeRolling.classList.add('active');
                if (modeCycle) modeCycle.classList.remove('active');
            });
        }
        if (modeCycle) {
            modeCycle.addEventListener('click', () => {
                this.displayMode = 'cycle';
                modeCycle.classList.add('active');
                if (modeRolling) modeRolling.classList.remove('active');
            });
        }

        // RMS envelope toggle
        const rmsToggle = document.getElementById('rmsToggle');
        if (rmsToggle) {
            rmsToggle.addEventListener('click', () => {
                this.showRMSEnvelope = !this.showRMSEnvelope;
                rmsToggle.classList.toggle('active', this.showRMSEnvelope);
            });
        }
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
                body: JSON.stringify({ enabled: !this.csvEnabled })
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
        this.dataBuffer.push({ t: timestamp * 1000, v: voltage });

        // Limit buffer size
        while (this.dataBuffer.length > this.maxBufferSize) {
            this.dataBuffer.shift();
        }
    }

    // Simple IIR low-pass filter (single-pole)
    applyLowPassFilter(data, sampleRate) {
        if (!this.lpfEnabled || data.length < 2) return data;

        const rc = 1.0 / (2.0 * Math.PI * this.lpfCutoff);
        const dt = 1.0 / sampleRate;
        const alpha = dt / (rc + dt);

        const filtered = [{ t: data[0].t, v: data[0].v }];

        for (let i = 1; i < data.length; i++) {
            const prevFiltered = filtered[i - 1].v;
            const newVal = prevFiltered + alpha * (data[i].v - prevFiltered);
            filtered.push({ t: data[i].t, v: newVal });
        }

        return filtered;
    }

    // Extract one complete cycle starting from a rising zero crossing
    extractCycle(data) {
        if (data.length < 20) return data;

        const mean = data.reduce((s, d) => s + d.v, 0) / data.length;

        // Find rising zero crossings
        const crossings = [];
        for (let i = 1; i < data.length; i++) {
            if (data[i - 1].v < mean && data[i].v >= mean) {
                crossings.push(i);
            }
        }

        // Need at least 2 crossings for one cycle
        if (crossings.length < 2) return data.slice(-100);

        // Get the most recent complete cycle
        const startIdx = crossings[crossings.length - 2];
        const endIdx = crossings[crossings.length - 1];

        // Return cycle data, normalized to start at t=0
        const cycleData = data.slice(startIdx, endIdx + 1);
        const t0 = cycleData[0].t;
        return cycleData.map(d => ({ t: d.t - t0, v: d.v }));
    }

    // Calculate RMS envelope over rolling window
    calculateRMSEnvelope(data, windowMs) {
        if (data.length < 10) return [];

        const envelope = [];
        const halfWindow = windowMs / 2;

        for (let i = 0; i < data.length; i++) {
            const centerT = data[i].t;
            const windowStart = centerT - halfWindow;
            const windowEnd = centerT + halfWindow;

            // Get samples in window
            const windowSamples = data.filter(d => d.t >= windowStart && d.t <= windowEnd);

            if (windowSamples.length > 0) {
                // Calculate RMS (subtract DC offset for AC RMS)
                const sumSq = windowSamples.reduce((s, d) => {
                    const ac = d.v - this.adcOffset;
                    return s + ac * ac;
                }, 0);
                const rms = Math.sqrt(sumSq / windowSamples.length);
                envelope.push({ t: data[i].t, v: rms });
            }
        }

        return envelope;
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

        // Estimate sample rate from data
        const dt = this.dataBuffer.length > 1 ?
            (this.dataBuffer[this.dataBuffer.length - 1].t - this.dataBuffer[0].t) / this.dataBuffer.length : 1;
        const estimatedSampleRate = 1000 / dt;

        // Apply low-pass filter if enabled
        let displayData = this.lpfEnabled ?
            this.applyLowPassFilter(this.dataBuffer, estimatedSampleRate) :
            this.dataBuffer;

        // Calculate Y scale
        const voltsVisible = this.voltsPerDiv * this.divisions.y;
        const yOffset = (this.vPosition / 100) * (height / 2);
        const yCenter = height / 2 + yOffset;

        let visibleData;
        let timeWindow;
        let startTime;

        if (this.displayMode === 'cycle') {
            // Cycle-locked mode: extract and display one complete cycle
            visibleData = this.extractCycle(displayData);
            timeWindow = visibleData.length > 1 ?
                visibleData[visibleData.length - 1].t - visibleData[0].t : this.timePerDiv * this.divisions.x;
            startTime = 0;
        } else {
            // Rolling mode: show latest time window
            timeWindow = this.timePerDiv * this.divisions.x;
            const now = displayData[displayData.length - 1].t;
            startTime = now - timeWindow;
            visibleData = displayData.filter(d => d.t >= startTime);
        }

        // Draw main waveform
        this.drawWaveform(ctx, visibleData, width, height, voltsVisible, yCenter, startTime, timeWindow, '#90CAF9', 2);

        // Draw RMS envelope if enabled
        if (this.showRMSEnvelope) {
            const envelope = this.calculateRMSEnvelope(visibleData, this.rmsWindowMs);
            if (envelope.length > 0) {
                // Draw envelope as filled area from center
                ctx.beginPath();
                ctx.fillStyle = 'rgba(255, 152, 0, 0.3)';

                envelope.forEach((point, i) => {
                    const x = this.displayMode === 'cycle' ?
                        (point.t / timeWindow) * width :
                        ((point.t - startTime) / timeWindow) * width;
                    const yTop = yCenter - (point.v / voltsVisible) * height;
                    const yBottom = yCenter + (point.v / voltsVisible) * height;

                    if (i === 0) {
                        ctx.moveTo(x, yTop);
                    } else {
                        ctx.lineTo(x, yTop);
                    }
                });

                // Draw back along bottom
                for (let i = envelope.length - 1; i >= 0; i--) {
                    const point = envelope[i];
                    const x = this.displayMode === 'cycle' ?
                        (point.t / timeWindow) * width :
                        ((point.t - startTime) / timeWindow) * width;
                    const yBottom = yCenter + (point.v / voltsVisible) * height;
                    ctx.lineTo(x, yBottom);
                }

                ctx.closePath();
                ctx.fill();

                // Draw RMS line (top of envelope)
                ctx.beginPath();
                ctx.strokeStyle = '#FF9800';
                ctx.lineWidth = 1;
                envelope.forEach((point, i) => {
                    const x = this.displayMode === 'cycle' ?
                        (point.t / timeWindow) * width :
                        ((point.t - startTime) / timeWindow) * width;
                    const y = yCenter - (point.v / voltsVisible) * height;
                    if (i === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                });
                ctx.stroke();
            }
        }

        // Update measurements from visible data
        this.updateMeasurements(visibleData);
        this.updateMeasurementDisplay();
    }

    drawWaveform(ctx, data, width, height, voltsVisible, yCenter, startTime, timeWindow, color, lineWidth) {
        if (data.length < 2) return;

        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;

        data.forEach((point, i) => {
            const x = this.displayMode === 'cycle' ?
                (point.t / timeWindow) * width :
                ((point.t - startTime) / timeWindow) * width;
            const y = yCenter - ((point.v - this.adcOffset) / voltsVisible) * height;

            if (i === 0) {
                ctx.moveTo(x, Math.max(0, Math.min(height, y)));
            } else {
                ctx.lineTo(x, Math.max(0, Math.min(height, y)));
            }
        });

        ctx.stroke();
    }

    updateMeasurements(data) {
        if (data.length < 2) return;

        let minV = Infinity, maxV = -Infinity, sumVSq = 0;

        data.forEach(point => {
            minV = Math.min(minV, point.v);
            maxV = Math.max(maxV, point.v);
            const ac = point.v - this.adcOffset;
            sumVSq += ac * ac;
        });

        this.measurements.vpp = maxV - minV;
        this.measurements.vrms = Math.sqrt(sumVSq / data.length);

        // Estimate AC voltage from ADC reading
        const acPeak = (this.measurements.vpp / 2) * 170;
        this.measurements.acVoltage = acPeak / Math.sqrt(2);

        // Frequency via zero-crossing
        this.calculateFrequency(data);
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
            this.measurements.freq = 1000 / (avgPeriod * 2);
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
