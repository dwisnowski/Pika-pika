// Live Chart JavaScript Module
// Handles real-time voltage monitoring with WebSocket updates

// Initialize the chart manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.liveChartManager = new PikaChartManager({
        wsPath: '/ws/live',
        rangeApiPath: '/api/range',
        sampleRatePath: '/api/config/sample-rate',
        timeWindowStorageKey: 'pika-time-window',
        voltageLabel: 'Voltage',
        enableSampleRateControls: true,
        enableRangeFetchOnZoom: true,
        enableHighlightShading: true,
    });
});
