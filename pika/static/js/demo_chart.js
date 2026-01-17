// Demo Chart JavaScript Module
// Handles demo page chart functionality with simulated data

// Initialize the demo chart manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.demoChartManager = new PikaChartManager({
        wsPath: '/ws/demo',
        rangeApiPath: '/api/range',
        rangeQueryParams: { demo: 1 },
        timeWindowStorageKey: 'pika-demo-time-window',
        voltageLabel: 'Demo Voltage',
        enableSampleRateControls: false,
        enableRangeFetchOnZoom: true,
        enableHighlightShading: true,
    });

    document.getElementById('simSpikeBtn')?.addEventListener('click', () => {
        window.demoChartManager.triggerAnomaly('spike');
    });

    document.getElementById('simDropBtn')?.addEventListener('click', () => {
        window.demoChartManager.triggerAnomaly('drop');
    });
});
