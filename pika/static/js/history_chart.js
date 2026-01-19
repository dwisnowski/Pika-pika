// History Chart JavaScript Module
// Handles historical data browsing and analysis

class HistoryChartManager {
    constructor() {
        this.chart = null;
        this.currentData = [];
        this.anomalies = [];
        this.showAnomalies = true;
        this.smoothData = false;

        this.init();
    }

    init() {
        this.setupChart();
        this.setupEventListeners();
        this.loadInitialData();
    }

    setupChart() {
        const ctx = document.getElementById('historyChart').getContext('2d');

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
                        backgroundColor: 'rgba(144,202,249,0.1)',
                        tension: 0.1,
                        pointRadius: 1
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
                        time: { unit: 'minute', tooltipFormat: 'HH:mm:ss' },
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
        // Load data button
        document.getElementById('loadData').addEventListener('click', () => {
            this.loadDataRange();
        });

        // Load demo data button
        document.getElementById('loadDemoData').addEventListener('click', () => {
            this.loadDemoData();
        });

        // Export data button
        document.getElementById('exportData').addEventListener('click', () => {
            this.exportToCSV();
        });

        // Show anomalies checkbox
        document.getElementById('showAnomalies').addEventListener('change', (e) => {
            this.showAnomalies = e.target.checked;
            this.updateAnomalyMarkers();
        });

        // Smooth data checkbox
        document.getElementById('smoothData').addEventListener('change', (e) => {
            this.smoothData = e.target.checked;
            this.applyDataSmoothing();
        });

        // Date change listeners
        document.getElementById('startDate').addEventListener('change', () => {
            this.validateDateRange();
        });

        document.getElementById('endDate').addEventListener('change', () => {
            this.validateDateRange();
        });
    }

    loadInitialData() {
        // Set default date range (last 24 hours)
        const now = new Date();
        const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);

        document.getElementById('endDate').value = now.toISOString().split('T')[0];
        document.getElementById('startDate').value = yesterday.toISOString().split('T')[0];

        // Load initial data
        this.loadDataRange();
    }

    validateDateRange() {
        const startDate = new Date(document.getElementById('startDate').value);
        const endDate = new Date(document.getElementById('endDate').value);
        const loadBtn = document.getElementById('loadData');

        if (startDate >= endDate) {
            loadBtn.disabled = true;
            loadBtn.textContent = 'Invalid Date Range';
        } else {
            loadBtn.disabled = false;
            loadBtn.textContent = 'Load Data';
        }
    }

    async loadDataRange() {
        const startDate = new Date(document.getElementById('startDate').value);
        const endDate = new Date(document.getElementById('endDate').value);

        if (startDate >= endDate) {
            alert('Start date must be before end date');
            return;
        }

        const startTs = Math.floor(startDate.getTime() / 1000);
        // Set end timestamp to the end of the selected day (23:59:59)
        const endTs = Math.floor(endDate.getTime() / 1000) + 86399;

        const loadingIndicator = document.getElementById('loadingIndicator');
        const progressBar = document.getElementById('loadingProgressBar');
        const statusText = document.getElementById('loadingStatusText');
        const percentageText = document.getElementById('loadingPercentage');
        const loadBtn = document.getElementById('loadData');

        try {
            // Show loading state
            loadBtn.textContent = 'Loading...';
            loadBtn.disabled = true;
            loadingIndicator.style.display = 'block';
            this.updateProgress(0, 'Initializing requests...');

            // Fetch historical data, anomalies, and analysis in parallel
            this.updateProgress(10, 'Requesting data from server...');

            const [dataRes, highlightsRes, analysisRes] = await Promise.all([
                fetch(`/api/range?start=${startTs}&end=${endTs}&max_points=5000`).then(r => r.json()),
                fetch(`/api/highlights?start=${startTs}&end=${endTs}`).then(r => r.json()),
                fetch(`/api/analysis/history?start=${startTs}&end=${endTs}`).then(r => r.json()).catch(e => {
                    console.warn("Failed to fetch analysis", e);
                    return { data: [] };
                })
            ]);

            this.updateProgress(60, 'Processing data...');

            if (dataRes.data) {
                this.currentData = dataRes.data;
            } else {
                this.currentData = [];
            }

            if (highlightsRes.highlights) {
                this.anomalies = highlightsRes.highlights;
            } else {
                this.anomalies = [];
            }

            if (analysisRes.data) {
                this.analysisData = analysisRes.data;
            } else {
                this.analysisData = [];
            }

            this.updateProgress(80, 'Updating charts and statistics...');

            // Clear chart and reload
            this.updateChart();
            this.calculateStatistics();
            this.updateAnomalyDisplay();

            this.updateProgress(100, 'Complete');
            setTimeout(() => { loadingIndicator.style.display = 'none'; }, 1000);

        } catch (error) {
            console.error('Error loading historical data:', error);
            statusText.textContent = 'Error loading data';
            statusText.style.color = 'var(--danger)';
            alert('Failed to load historical data. Please try again.');
        } finally {
            // Reset loading state
            loadBtn.textContent = 'Load Data';
            loadBtn.disabled = false;
        }
    }

    updateProgress(percent, text) {
        const progressBar = document.getElementById('loadingProgressBar');
        const statusText = document.getElementById('loadingStatusText');
        const percentageText = document.getElementById('loadingPercentage');

        if (progressBar) progressBar.style.width = `${percent}%`;
        if (statusText) statusText.textContent = text;
        if (percentageText) percentageText.textContent = `${percent}%`;
    }

    async loadDemoData() {
        const demoBtn = document.getElementById('loadDemoData');
        const loadingIndicator = document.getElementById('loadingIndicator');
        const loadBtn = document.getElementById('loadData');

        try {
            // Show loading state
            demoBtn.textContent = 'Loading Demo...';
            demoBtn.disabled = true;
            loadBtn.disabled = true;
            loadingIndicator.style.display = 'block';
            this.updateProgress(0, 'Initializing demo request...');

            // Define a range that would capture most of the demo data
            const now = Math.floor(Date.now() / 1000);
            const startTs = now - 3600 * 24; // last 24 hours
            const endTs = now + 86400; // include some future just in case or for full day

            this.updateProgress(10, 'Fetching demo data...');

            const [dataRes, highlightsRes, analysisRes] = await Promise.all([
                fetch(`/api/range?start=${startTs}&end=${endTs}&max_points=5000&source=demo`).then(r => r.json()),
                fetch(`/api/highlights?start=${startTs}&end=${endTs}&source=demo`).then(r => r.json()),
                fetch(`/api/analysis/history?start=${startTs}&end=${endTs}`).then(r => r.json()).catch(e => {
                    console.warn("Failed to fetch analysis", e);
                    return { data: [] };
                })
            ]);

            this.updateProgress(60, 'Processing demo data...');

            if (dataRes.data) {
                this.currentData = dataRes.data;
            } else {
                this.currentData = [];
            }

            if (highlightsRes.highlights) {
                this.anomalies = highlightsRes.highlights;
            } else {
                this.anomalies = [];
            }

            if (analysisRes.data) {
                this.analysisData = analysisRes.data;
            } else {
                this.analysisData = [];
            }

            this.updateProgress(80, 'Updating charts...');

            this.updateChart();
            this.calculateStatistics();
            this.updateAnomalyDisplay();

            // Update date inputs to reflect what we just loaded (approximate)
            const startDateObj = new Date(startTs * 1000);
            const endDateObj = new Date(now * 1000);
            document.getElementById('startDate').value = startDateObj.toISOString().split('T')[0];
            document.getElementById('endDate').value = endDateObj.toISOString().split('T')[0];
            this.validateDateRange();

            this.updateProgress(100, 'Demo Loaded');
            setTimeout(() => { loadingIndicator.style.display = 'none'; }, 1000);

        } catch (error) {
            console.error('Error loading demo data:', error);
            alert('Failed to load demo data. Make sure demo is active and generating data.');
        } finally {
            // Reset loading state
            demoBtn.textContent = 'Load Demo Data';
            demoBtn.disabled = false;
            loadBtn.disabled = false;
        }
    }

    updateChart() {
        // Prepare datasets array
        const datasets = [];

        // 1. Raw Voltage Dataset
        if (this.currentData && this.currentData.length > 0) {
            let processedData = this.currentData;
            if (this.smoothData) {
                processedData = this.applyDataSmoothing(this.currentData);
            }

            datasets.push({
                label: 'Voltage',
                data: processedData.map(d => ({ x: new Date(d[0] * 1000), y: d[1] })),
                borderColor: '#90CAF9',
                backgroundColor: 'rgba(144,202,249,0.1)',
                tension: 0.1,
                pointRadius: 1
            });
        }

        // 2. RMS Voltage Dataset (Analysis)
        if (this.analysisData && this.analysisData.length > 0) {
            datasets.push({
                label: 'RMS Voltage',
                data: this.analysisData.map(d => ({
                    x: new Date(d.ts * 1000),
                    y: d.rms
                })),
                borderColor: '#66BB6A', // Green
                backgroundColor: 'rgba(102, 187, 106, 0.1)',
                borderWidth: 2,
                pointRadius: 0,
                tension: 0.2
            });
        }

        // 3. Anomalies Dataset
        if (this.showAnomalies && this.anomalies && this.anomalies.length > 0) {
            datasets.push({
                label: 'Anomalies',
                data: this.anomalies.map(a => ({
                    x: new Date(a.peak_ts * 1000),
                    y: a.peak_value
                })),
                borderColor: '#FF6B6B',
                backgroundColor: '#FF6B6B',
                showLine: false,
                pointRadius: 6,
                pointStyle: 'triangle'
            });
        }

        // Update the chart
        this.chart.data.datasets = datasets;
        this.chart.update();
    }

    applyDataSmoothing(data) {
        // Simple 1-second moving average
        const smoothed = [];
        const windowSize = 100; // Assuming 100Hz sampling, 1 second = 100 samples

        for (let i = 0; i < data.length; i++) {
            const start = Math.max(0, i - Math.floor(windowSize / 2));
            const end = Math.min(data.length, i + Math.ceil(windowSize / 2));
            const window = data.slice(start, end);

            const sum = window.reduce((acc, point) => acc + point[1], 0);
            const avg = sum / window.length;

            smoothed.push([data[i][0], avg]);
        }

        return smoothed;
    }

    updateAnomalyMarkers() {
        if (!this.showAnomalies) {
            // Remove anomaly dataset
            if (this.chart.data.datasets.length > 1) {
                this.chart.data.datasets = this.chart.data.datasets.slice(0, 1);
            }
        } else {
            // Add anomaly dataset
            const anomalyData = this.anomalies.map(a => ({
                x: new Date(a.peak_ts * 1000),
                y: a.peak_value
            }));

            if (this.chart.data.datasets.length === 1) {
                this.chart.data.datasets.push({
                    label: 'Anomalies',
                    data: anomalyData,
                    borderColor: '#FF6B6B',
                    backgroundColor: '#FF6B6B',
                    showLine: false,
                    pointRadius: 6,
                    pointStyle: 'triangle'
                });
            } else {
                this.chart.data.datasets[1].data = anomalyData;
            }
        }

        this.chart.update();
    }

    updateAnomalyDisplay() {
        const anomalyCount = document.getElementById('anomalyTotal');
        const anomalyList = document.getElementById('anomalyList');

        anomalyCount.textContent = this.anomalies.length;

        if (!this.anomalies || !this.anomalies.length) {
            anomalyList.innerHTML = '<p style="color:var(--muted);">No anomalies detected in selected date range.</p>';
            return;
        }

        // Sort by severity (score)
        const sortedAnomalies = [...this.anomalies].sort((a, b) => b.score - a.score);

        anomalyList.innerHTML = sortedAnomalies.map((a, idx) => {
            const start = new Date(a.start_ts * 1000).toLocaleString();
            const end = new Date(a.end_ts * 1000).toLocaleString();
            const type = a.type || 'unknown';

            return `
                <div style="padding:8px; border-bottom:1px solid #eee;">
                    <strong>#${idx + 1}</strong> - ${type.toUpperCase()}<br/>
                    <small>Peak: ${a.peak_value.toFixed(3)}V | Duration: ${(a.end_ts - a.start_ts).toFixed(1)}s</small><br/>
                    <small style="color:var(--muted);">${start} → ${end}</small>
                </div>
            `;
        }).join('');
    }

    calculateStatistics() {
        if (!this.currentData || !this.currentData.length) {
            this.updateStatisticsDisplay(null);
            return;
        }

        const voltages = this.currentData.map(d => d[1]);
        const mean = voltages.reduce((sum, v) => sum + v, 0) / voltages.length;
        const min = Math.min(...voltages);
        const max = Math.max(...voltages);

        // Calculate standard deviation
        const variance = voltages.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / voltages.length;
        const std = Math.sqrt(variance);

        this.updateStatisticsDisplay({
            mean: mean,
            min: min,
            max: max,
            std: std,
            count: voltages.length
        });
    }

    updateStatisticsDisplay(stats) {
        if (!stats) {
            document.getElementById('meanVoltage').textContent = '--';
            document.getElementById('minVoltage').textContent = '--';
            document.getElementById('maxVoltage').textContent = '--';
            document.getElementById('stdVoltage').textContent = '--';
            document.getElementById('totalSamples').textContent = '--';
            return;
        }

        document.getElementById('meanVoltage').textContent = stats.mean.toFixed(3);
        document.getElementById('minVoltage').textContent = stats.min.toFixed(3);
        document.getElementById('maxVoltage').textContent = stats.max.toFixed(3);
        document.getElementById('stdVoltage').textContent = stats.std.toFixed(3);
        document.getElementById('totalSamples').textContent = stats.count.toLocaleString();
    }

    async exportToCSV() {
        if (!this.currentData || !this.currentData.length) {
            alert('No data to export');
            return;
        }

        // Create CSV content
        const headers = ['Timestamp', 'Voltage', 'Date'];
        const rows = this.currentData.map(d => [
            new Date(d[0] * 1000).toISOString(),
            d[1].toFixed(6),
            new Date(d[0] * 1000).toLocaleString()
        ]);

        const csvContent = [headers, ...rows]
            .map(row => row.join(','))
            .join('\n');

        // Create download link
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `pika-history-${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}

// Initialize the history chart manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.historyChartManager = new HistoryChartManager();
});
