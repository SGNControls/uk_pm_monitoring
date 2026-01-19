// Enhanced Dashboard JavaScript - All Features Combined
// Preserves all existing functionality + adds new enhanced features

// ========================
// GLOBAL VARIABLES
// ========================

// Existing variables (preserved)
let currentAvgWindow = 15;
let currentDeviceRoom = null;

// New enhanced variables
let currentDeviceId = null;
let currentDeviceType = 'basic'; // 'basic' or 'extended'
let socket = null;
// Ensure Chart.js Zoom plugin is registered when loaded via CDN
try {
  if (typeof Chart !== 'undefined' && typeof Chart.register === 'function') {
    const zoomPlugin = window.ChartZoom || window['chartjs-plugin-zoom'];
    if (zoomPlugin) {
      Chart.register(zoomPlugin);
    }
  }
} catch (e) {
  console.warn('Chart.js zoom plugin registration skipped:', e);
}
function initializeWebSocket() {
    // Check if Socket.IO is available
    if (typeof io === 'undefined') {
        console.warn('Socket.IO not found, using polling fallback');
        startRealtimePolling();
        return;
    }

    try {
        // Get current protocol and host for Railway compatibility
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;

        // Initialize socket connection with Railway-compatible settings
        socket = io('/', {
            transports: ['polling', 'websocket'], // Try polling first, then websocket
            reconnection: true,
            reconnectionAttempts: 3, // Reduce reconnection attempts
            reconnectionDelay: 2000, // Increase delay
            timeout: 10000, // Reduce timeout
            forceNew: false,
            upgrade: true,
            withCredentials: true // Send cookies for authentication
        });

        // Connection event handlers
        socket.on('connect', function() {
            console.log('✅ WebSocket connected to server');
            updateConnectionStatus(true);
            stopRealtimePolling(); // Stop polling when WebSocket connects

            // Join device room if a device is selected
            if (currentDeviceId) {
                joinDeviceRoom(currentDeviceId);
            }
        });

        socket.on('disconnect', function(reason) {
            console.log('❌ WebSocket disconnected:', reason);
            updateConnectionStatus(false);
            // Only start polling if it's a network issue, not intentional disconnect
            if (reason !== 'io client disconnect') {
                // Delay polling start to avoid immediate reloads
                setTimeout(() => {
                    startRealtimePolling();
                }, 5000);
            }
        });

        socket.on('connect_error', function(error) {
            console.error('❌ WebSocket connection error:', error);
            updateConnectionStatus(false);
            // Don't immediately start polling - let it retry WebSocket first
        });

        socket.on('reconnect', function(attemptNumber) {
            console.log('🔄 WebSocket reconnected after', attemptNumber, 'attempts');
            updateConnectionStatus(true);
            stopRealtimePolling();
        });

        socket.on('reconnect_error', function(error) {
            console.error('❌ WebSocket reconnection failed:', error);
            // Start polling as last resort
            startRealtimePolling();
        });

        // Handle incoming data - prevent duplicate processing
        socket.on('new_data', function(data) {
            if (String(data.device_id) === String(currentDeviceId)) {
                console.log('📡 Received WebSocket sensor data');
                safeProcessIncomingData(data);
            }
        });

        socket.on('new_extended_data', function(data) {
            if (currentDeviceType === 'extended' && String(data.device_id) === String(currentDeviceId)) {
                console.log('📡 Received WebSocket extended data');
                // Normalize WebSocket data before passing to updateExtendedData
                const normalized = normalizeIncomingData({ extended: data });
                if (normalized && normalized.extended) {
                    updateExtendedData(normalized.extended);
                } else {
                    console.warn('❌ Failed to normalize WebSocket extended data');
                }
            }
        });

    } catch (error) {
        console.error('❌ WebSocket initialization failed:', error);
        startRealtimePolling();
    }
}

let map = null;
let deviceMarker = null;
let currentTheme = 'light';
// Locking axis behavior for PM time chart
let fixedYAxisMax = null;
// Rigid axes flag for all charts
let rigidAxesEnabled = true;
// Device selection map
let deviceSelectMap = null;
let deviceSelectMarkers = [];
// Polling fallback when websockets are not available or disconnected
let pollingIntervalId = null;
// Rigid maxima cache per chart
const rigidMaxByChart = {};

// Chart instances storage
let charts = {
    // Existing charts
    timeChart: null,
    // Extended device charts
    tempHumidityChart: null,
    pressureAirQualityChart: null,
    vocChart: null
};

// Color schemes for all parameters
const colorScheme = {
    pm1: 'rgba(255, 99, 132, 0.8)',
    pm2_5: 'rgba(54, 162, 235, 0.8)',
    pm4: 'rgba(75, 192, 192, 0.8)',
    pm10: 'rgba(255, 206, 86, 0.8)',
    tsp: 'rgba(153, 102, 255, 0.8)',
    temperature: 'rgba(255, 159, 64, 0.8)',
    humidity: 'rgba(99, 255, 132, 0.8)',
    pressure: 'rgba(132, 99, 255, 0.8)',
    voc: 'rgba(255, 206, 86, 0.8)',
    no2: 'rgba(255, 99, 159, 0.8)',
    speed: 'rgba(64, 159, 255, 0.8)',
    cloud: 'rgba(192, 192, 192, 0.8)'
};

// ========================
// THEME MANAGEMENT (Enhanced from your existing)
// ========================

const themeToggle = document.getElementById('theme-toggle');
themeToggle.addEventListener('change', function() {
    const theme = this.checked ? 'dark' : 'light';
    currentTheme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    updateChartsTheme();
});

// Initialize theme from localStorage (your existing logic preserved)
const savedTheme = localStorage.getItem('theme') || 'light';
currentTheme = savedTheme;
document.documentElement.setAttribute('data-theme', currentTheme);
themeToggle.checked = currentTheme === 'dark';

// Chart theme variables (your existing)
let chartGridColor = getComputedStyle(document.documentElement).getPropertyValue('--chart-grid').trim() || 'rgba(0, 0, 0, 0.1)';
let chartTextColor = getComputedStyle(document.documentElement).getPropertyValue('--text-color').trim() || '#212529';

// ========================
// INITIALIZATION (Enhanced)
// ========================

document.addEventListener('DOMContentLoaded', function() {
    // Initialize components with error handling
    try {
        initializeCharts();
        initializeExtendedCharts();
        initializeDeviceSelection();
        initializeWebSocket();
        initializeDeviceSelectionMap();
        setDefaultDates();
        initializeMapToggle();
        initializeDeviceQuickActions();
        setupRelayControls();

        // Test data loading with a sample device ID for development
        console.log('Dashboard initialized. Please select a device to load data.');

        // Don't call updateQuickStats here as it requires data
        // updateQuickStats(); // Remove this line

    } catch (error) {
        console.error('Initialization error:', error);
        createAlert('Failed to initialize dashboard. Please refresh the page.', 'danger');
    }
});

// ========================
// DEVICE SELECTION (Enhanced)
// ========================

function initializeDeviceSelection() {
    const deviceSelect = document.getElementById('deviceSelect');

    // Trigger initial selection if a device is pre-selected
    if (deviceSelect && deviceSelect.value) {
        handleDeviceSelection();
    }

    deviceSelect.addEventListener('change', handleDeviceSelection);
}

function handleDeviceSelection() {
    const deviceSelect = document.getElementById('deviceSelect');
    const selectedOption = deviceSelect.options[deviceSelect.selectedIndex];

    if (!selectedOption.value) {
        hideAllTabs();
        return;
    }

    currentDeviceId = selectedOption.value;
    currentDeviceType = selectedOption.getAttribute('data-type');
    const hasRelay = selectedOption.getAttribute('data-relay') === 'True';
    const deviceName = selectedOption.getAttribute('data-name');
    const deviceId = selectedOption.getAttribute('data-deviceid');

    console.log('=== DEVICE SELECTION START ===');
    console.log('Device selected:', {
        currentDeviceId,
        currentDeviceType,
        hasRelay,
        deviceName,
        deviceId,
        selectedOptionAttributes: {
            'data-type': selectedOption.getAttribute('data-type'),
            'data-relay': selectedOption.getAttribute('data-relay'),
            'data-name': selectedOption.getAttribute('data-name'),
            'data-deviceid': selectedOption.getAttribute('data-deviceid')
        }
    });

    // Update device info panel
    updateDeviceInfoPanel(deviceName, deviceId, currentDeviceType, hasRelay);

    // Show appropriate tabs
    console.log('Calling showDeviceTabs with:', currentDeviceType, hasRelay);
    showDeviceTabs(currentDeviceType, hasRelay);

    // Join WebSocket room
    joinDeviceRoom(currentDeviceId);

    // Load initial data
    console.log('Fetching initial data...');
    fetchData(24);

    // Initialize map if extended device - Map is now in location tab
    // Map initialization is handled in the location tab when it's shown

    // Update device type indicator
    const indicator = document.getElementById('deviceTypeIndicator');
    if (indicator) {
        indicator.textContent = currentDeviceType.toUpperCase();
        indicator.className = `badge ${currentDeviceType === 'extended' ? 'bg-info' : 'bg-primary'} ms-2`;
        indicator.style.display = 'inline';
    }

    console.log('=== DEVICE SELECTION COMPLETE ===');
}


function getParameterLabel(param) {
    const labels = {
        'pm1': 'PM1 (μg/m³)',
        'pm2_5': 'PM2.5 (μg/m³)',
        'pm4': 'PM4 (μg/m³)',
        'pm10': 'PM10 (μg/m³)',
        'tsp': 'TSP (μg/m³)',
        'temperature_c': 'Temperature (°C)',
        'humidity_percent': 'Humidity (%)',
        'pressure_hpa': 'Pressure (hPa)',
        'voc_ppb': 'VOC (ppb)',
        'no2_ppb': 'NO₂ (ppb)',
        'gps_speed_kmh': 'Speed (km/h)',
        'cloud_cover_percent': 'Cloud Cover (%)'
    };
    return labels[param] || param;
}

function joinDeviceRoom(deviceId) {
    if (socket && socket.connected) {
        // Leave previous room
        if (currentDeviceRoom && currentDeviceRoom !== deviceId) {
            socket.emit('leave', { device_id: currentDeviceRoom });
        }
        
        // Join new room
        socket.emit('join', { device_id: deviceId });
        currentDeviceRoom = deviceId;
        console.log(`Joined room for device: ${deviceId}`);
    }
}

// ========================
// DEVICE SELECTION MAP
// ========================
async function initializeDeviceSelectionMap() {
    const mapContainer = document.getElementById('deviceSelectMap');
    if (!mapContainer) return;

    if (!deviceSelectMap) {
        deviceSelectMap = L.map('deviceSelectMap').setView([20.5937, 78.9629], 4); // India center as default
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(deviceSelectMap);
    }

    async function fetchLocations() {
        const res = await fetch('/api/device_locations');
        const json = await res.json();
        return json.devices || [];
    }

    function clearMarkers() {
        deviceSelectMarkers.forEach(m => deviceSelectMap.removeLayer(m));
        deviceSelectMarkers = [];
    }

    function addMarkers(devices) {
        clearMarkers();
        const bounds = [];
        devices.forEach(d => {
            if (!Number.isFinite(d.gps_lat) || !Number.isFinite(d.gps_lon)) return;
            const marker = L.marker([d.gps_lat, d.gps_lon]);
            marker.bindPopup(`${d.name || d.deviceid}`);
            marker.on('click', () => {
                selectDeviceById(d.id);
            });
            marker.addTo(deviceSelectMap);
            deviceSelectMarkers.push(marker);
            bounds.push([d.gps_lat, d.gps_lon]);
        });
        if (bounds.length) {
            deviceSelectMap.fitBounds(bounds, { padding: [20, 20] });
        }
    }

    function selectDeviceById(id) {
        const deviceSelect = document.getElementById('deviceSelect');
        if (!deviceSelect) return;
        const option = Array.from(deviceSelect.options).find(o => String(o.value) === String(id));
        if (option) {
            deviceSelect.value = option.value;
            deviceSelect.dispatchEvent(new Event('change'));
        } else {
            createAlert('Device not found in selection list', 'warning');
        }
    }

    async function refreshMarkers() {
        try {
            const devices = await fetchLocations();
            addMarkers(devices);
        } catch (e) {
            console.error(e);
            createAlert('Failed to load device locations', 'danger');
        }
    }

    // Buttons
    const refreshBtn = document.getElementById('refreshDeviceMapBtn');
    const fitBtn = document.getElementById('fitDeviceMapBtn');
    if (refreshBtn) refreshBtn.addEventListener('click', refreshMarkers);
    if (fitBtn) fitBtn.addEventListener('click', () => {
        const latlngs = deviceSelectMarkers.map(m => m.getLatLng());
        if (latlngs.length) deviceSelectMap.fitBounds(L.latLngBounds(latlngs), { padding: [20, 20] });
    });

    await refreshMarkers();
}

function updateDeviceInfoPanel(name, deviceId, type, hasRelay) {
    const deviceInfo = document.getElementById('deviceInfo');
    const deviceStatus = document.getElementById('deviceStatus');
    const deviceType = document.getElementById('deviceType');
    const relayStatusRow = document.getElementById('relayStatusRow');

    if (deviceInfo) deviceInfo.style.display = 'block';
    if (deviceStatus) {
        deviceStatus.textContent = 'Online';
        deviceStatus.className = 'badge bg-success';
    }
    if (deviceType) {
        deviceType.textContent = type.toUpperCase();
        deviceType.className = `badge ${type === 'extended' ? 'bg-info' : 'bg-primary'}`;
    }

    if (relayStatusRow) {
        if (hasRelay) {
            relayStatusRow.style.display = 'block';
            const relayControls = document.getElementById('relayControls');
            if (relayControls) relayControls.style.display = 'block';
        } else {
            relayStatusRow.style.display = 'none';
            const relayControls = document.getElementById('relayControls');
            if (relayControls) relayControls.style.display = 'none';
        }
    }
}

function safeProcessIncomingData(data) {
    try {
        if (!data) {
            console.warn('No data received');
            return;
        }

        console.log('Processing incoming data:', data);
        
        // Normalize the data
        const normalizedData = normalizeIncomingData(data);
        
        if (!normalizedData) {
            console.error('Failed to normalize data');
            return;
        }
        
        // Convert timestamps safely
        if (normalizedData.history && normalizedData.history.timestamps) {
            normalizedData.history.timestamps = normalizedData.history.timestamps.map(t => {
                try {
                    return new Date(t);
                } catch (e) {
                    console.warn('Invalid timestamp:', t);
                    return new Date();
                }
            });
        }
        
        // Call all update functions
        updateDashboard(normalizedData);
        updateCharts(normalizedData);
        updateExtendedCharts(normalizedData);
        checkThresholds(normalizedData);
        calculateThresholdFrequency(normalizedData);
        updateQuickStats(normalizedData);
        updateAQI(normalizedData);
        
        // Handle extended data
        if (normalizedData.extended) {
            console.log('Calling updateExtendedData with:', normalizedData.extended);
            updateExtendedData(normalizedData.extended);
        }
        
    } catch (error) {
        console.error('Error processing incoming data:', error);
    }
}

function debugDataFlow(data, stage) {
    console.group(`Data Flow: ${stage}`);
    console.log('Raw data structure:', data);
    if (data && data.sensor) console.log('Sensor data:', data.sensor);
    if (data && data.extended) console.log('Extended data:', data.extended);
    if (data && data.history) console.log('History data keys:', Object.keys(data.history));
    console.groupEnd();
}

function processIncomingData(data) {
    // Call the safe processing function
    safeProcessIncomingData(data);
}

function showDeviceTabs(deviceType, hasRelay) {
    console.log('showDeviceTabs called with:', { deviceType, hasRelay });

    const tabs = document.getElementById('deviceTypeTabs');
    const environmentalTab = document.getElementById('environmental-tab-li');
    const settingsTab = document.getElementById('settings-tab-li');
    const environmentalTabContent = document.getElementById('environmental');

    console.log('Tab elements found:', {
        tabs: !!tabs,
        environmentalTab: !!environmentalTab,
        environmentalTabContent: !!environmentalTabContent,
        settingsTab: !!settingsTab
    });

    if (tabs) {
        tabs.style.display = 'block';
        console.log('Main tabs container made visible');
    }

    if (deviceType === 'extended') {
        console.log('Device type is extended - showing and activating environmental tab');
        if (environmentalTab) {
            environmentalTab.style.display = 'block';
            console.log('Environmental tab made visible');

            // Force switch to environmental tab using Bootstrap's tab API
            const environmentalTabBtn = document.getElementById('environmental-tab');
            if (environmentalTabBtn) {
                // Use Bootstrap's Tab API to properly switch tabs
                const bsTab = new bootstrap.Tab(environmentalTabBtn);
                bsTab.show();
                console.log('Environmental tab activated using Bootstrap Tab API');
            }

            // Load environmental data cards
            loadEnvironmentalDataCards();
        }

        // Update tab badges
        const envBadge = document.getElementById('envBadge');
        if (envBadge) envBadge.textContent = '+6';
    } else {
        console.log('Device type is not extended - hiding environmental tab');
        if (environmentalTab) environmentalTab.style.display = 'none';
        if (environmentalTabContent) environmentalTabContent.classList.remove('show', 'active');
    }

    if (hasRelay) {
        if (settingsTab) settingsTab.style.display = 'block';
    } else {
        if (settingsTab) settingsTab.style.display = 'none';
    }

    console.log('Tab visibility updated');
}

// Function to load environmental data cards from backend API
function loadEnvironmentalDataCards() {
    console.log('Loading environmental data cards...');

    if (!currentDeviceId) {
        console.warn('No device selected, cannot load environmental data cards');
        return;
    }

    // Fetch live data from backend API
    fetch(`/api/data?hours=1&deviceid=${currentDeviceId}`, {
        credentials: 'same-origin'
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Received environmental data for cards:', data);

            // Extract extended data
            const extendedData = data.extended || {};
            const sensorData = data.sensor || {};

            // Create environmental data cards
            createEnvironmentalDataCards(extendedData, sensorData);
        })
        .catch(error => {
            console.error('Error loading environmental data cards:', error);
            createAlert('Failed to load environmental data cards', 'danger');
        });
}

// Function to create environmental data cards dynamically
function createEnvironmentalDataCards(extendedData, sensorData) {
    const container = document.getElementById('environmentalDataContainer');
    if (!container) {
        console.error('Environmental data container not found');
        return;
    }

    // Define the environmental parameters to display
    const environmentalParams = [
        {
            key: 'temperature_c',
            label: 'Temperature',
            icon: 'bi-thermometer-high',
            color: 'danger',
            unit: '°C',
            data: extendedData.temperature_c
        },
        {
            key: 'humidity_percent',
            label: 'Humidity',
            icon: 'bi-droplet-half',
            color: 'info',
            unit: '%',
            data: extendedData.humidity_percent
        },
        {
            key: 'pressure_hpa',
            label: 'Pressure',
            icon: 'bi-speedometer2',
            color: 'success',
            unit: ' hPa',
            data: extendedData.pressure_hpa
        },
        {
            key: 'voc_ppb',
            label: 'VOC',
            icon: 'bi-cloud-haze2',
            color: 'warning',
            unit: ' ppb',
            data: extendedData.voc_ppb
        },
        {
            key: 'no2_ppb',
            label: 'NO₂',
            icon: 'bi-cloud-haze2',
            color: 'warning',
            unit: ' ppb',
            data: extendedData.no2_ppb
        },
        {
            key: 'noise_db',
            label: 'Noise',
            icon: 'bi-volume-up',
            color: 'purple',
            unit: ' dB',
            data: extendedData.noise_db
        },
        {
            key: 'lux',
            label: 'Light Level',
            icon: 'bi-sun',
            color: 'warning',
            unit: ' lux',
            data: extendedData.lux
        },
        {
            key: 'uv_index',
            label: 'UV Index',
            icon: 'bi-sun-fill',
            color: 'orange',
            unit: '',
            data: extendedData.uv_index
        }
    ];

    // Create HTML for cards
    const cardsHTML = environmentalParams.map(param => {
        const value = param.data !== null && param.data !== undefined && !isNaN(param.data)
            ? param.data.toFixed(1)
            : '--';
        const valueColor = value !== '--' ? '#0d6efd' : '#6c757d';

        return `
            <div class="col-lg-4 col-md-6 mb-4">
                <div class="card environmental-card h-100">
                    <div class="card-body text-center">
                        <div class="env-icon">
                            <i class="bi ${param.icon} text-${param.color}"></i>
                        </div>
                        <h3 class="display-4 text-${param.color}" style="color: ${valueColor} !important;">
                            ${value}${param.unit}
                        </h3>
                        <p class="text-muted mb-0">${param.label}</p>
                        <div class="env-trend mt-2">
                            <small class="text-muted">Live Data</small>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Set the HTML content
    container.innerHTML = cardsHTML;

    console.log('Environmental data cards created successfully');
}

function hideAllTabs() {
    const tabs = document.getElementById('deviceTypeTabs');
    const deviceInfo = document.getElementById('deviceInfo');
    const deviceTypeIndicator = document.getElementById('deviceTypeIndicator');

    if (tabs) tabs.style.display = 'none';
    if (deviceInfo) deviceInfo.style.display = 'none';
    if (deviceTypeIndicator) deviceTypeIndicator.style.display = 'none';

    currentDeviceId = null;

    if (socket && currentDeviceRoom) {
        socket.emit('leave', {device_id: currentDeviceRoom});
        currentDeviceRoom = null;
    }
}

// ========================
// CHART INITIALIZATION (Your existing + enhanced)
// ========================

function initializeCharts() {
    // Ensure Chart.js is loaded
    if (typeof Chart === 'undefined') {
        console.error('Chart.js not loaded');
        setTimeout(initializeCharts, 100); // Retry after a short delay
        return;
    }

    // Register plugins
    try {
        if (window.ChartZoom && typeof Chart.register === 'function') {
            Chart.register(window.ChartZoom);
        }
    } catch (e) {
        console.warn('Chart.js zoom plugin not available:', e);
    }

    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
            duration: 0 // Disable animations for real-time
        },
        plugins: {
            legend: {
                position: 'top',
                labels: {
                    color: chartTextColor,
                    padding: 20,
                    font: { size: 12 }
                }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: { color: chartGridColor },
                ticks: { 
                    color: chartTextColor,
                    precision: 0,
                    maxTicksLimit: 10
                }
            },
            x: {
                grid: { color: chartGridColor },
                ticks: { color: chartTextColor }
            }
        }
    };

    // Initialize PM Time Chart with rigid center axis and no zoom
    const timeCtx = document.getElementById('timeChart');
    if (timeCtx) {
        charts.timeChart = new Chart(timeCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    createDatasetConfig('PM1', colorScheme.pm1),
                    createDatasetConfig('PM2.5', colorScheme.pm2_5),
                    createDatasetConfig('PM4', colorScheme.pm4),
                    createDatasetConfig('PM10', colorScheme.pm10),
                    createDatasetConfig('TSP', colorScheme.tsp)
                ]
            },
            options: {
                ...commonOptions,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    ...commonOptions.plugins,
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        callbacks: {
                            label: ctx => `${ctx.dataset.label}: ${ctx.raw.toFixed(2)} μg/m³`
                        }
                    },
                    // Disable zoom plugin
                    zoom: false
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        min: 0,
                        max: 250, // Fixed maximum for PM levels
                        grid: {
                            color: chartGridColor,
                            drawBorder: true
                        },
                        ticks: {
                            color: chartTextColor,
                            padding: 10,
                            callback: function(value) {
                                return value + ' μg/m³';
                            },
                            maxTicksLimit: 8
                        },
                        title: {
                            display: true,
                            text: 'PM Level (μg/m³)',
                            color: chartTextColor,
                            font: {
                                size: 14,
                                weight: 'bold'
                            },
                            padding: { top: 10, bottom: 10 }
                        }
                    },
                    x: {
                        type: 'time',
                        time: {
                            tooltipFormat: 'dd-MM HH:mm',
                            displayFormats: {
                                minute: 'HH:mm',
                                hour: 'HH:mm',
                                day: 'MMM dd'
                            }
                        },
                        grid: {
                            color: chartGridColor,
                            drawBorder: true
                        },
                        ticks: {
                            color: chartTextColor,
                            padding: 10,
                            maxTicksLimit: 12
                        },
                        title: {
                            display: true,
                            text: 'Time (IST)',
                            color: chartTextColor,
                            font: {
                                size: 14,
                                weight: 'bold'
                            },
                            padding: { top: 10, bottom: 10 }
                        }
                    }
                }
            }
        });
    }
}

function safeChartUpdate(chart, key = 'chart') {
    try {
        if (chart && typeof chart.update === 'function') {
            chart.update('none'); // Use 'none' to prevent animations
        }
    } catch (err) {
        console.error(`Chart update failed for ${key}:`, err);
        // Attempt to reinitialize the chart if it's broken
        if (charts[key] && document.getElementById(key)) {
            console.log(`Attempting to reinitialize chart: ${key}`);
            setTimeout(() => {
                try {
                    if (key === 'timeChart') initializeCharts();
                    else if (key === 'thresholdChart') initializeCharts();
                    // Add other chart initializations as needed
                } catch (e) {
                    console.error(`Failed to reinitialize chart ${key}:`, e);
                }
            }, 1000);
        }
    }
}
// Helper function to create dataset config (your existing)
function createDatasetConfig(label, borderColor) {
    return {
        label,
        data: [],
        borderColor,
        backgroundColor: borderColor.replace('0.8', '0.2'),
        borderWidth: 2,
        pointRadius: 1,
        pointHoverRadius: 5,
        tension: 0.3,
        fill: true
    };
}

// ========================
// EXTENDED CHARTS INITIALIZATION (New)
// ========================

function initializeExtendedCharts() {
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { position: 'top' }
        }
    };

    // Temperature & Humidity Chart
    if (document.getElementById('tempHumidityChart')) {
        charts.tempHumidityChart = new Chart(document.getElementById('tempHumidityChart').getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Temperature (°C)',
                        data: [],
                        borderColor: colorScheme.temperature,
                        backgroundColor: colorScheme.temperature.replace('0.8', '0.2'),
                        yAxisID: 'y'
                    },
                    {
                        label: 'Humidity (%)',
                        data: [],
                        borderColor: colorScheme.humidity,
                        backgroundColor: colorScheme.humidity.replace('0.8', '0.2'),
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                ...commonOptions,
                scales: {
                    x: { type: 'time' },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: { display: true, text: 'Temperature (°C)' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: { display: true, text: 'Humidity (%)' },
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });
    }

    // Pressure & Air Quality Chart
    if (document.getElementById('pressureAirQualityChart')) {
        charts.pressureAirQualityChart = new Chart(document.getElementById('pressureAirQualityChart').getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Pressure (hPa)',
                        data: [],
                        borderColor: colorScheme.pressure,
                        yAxisID: 'y'
                    },
                    {
                        label: 'VOC (ppb)',
                        data: [],
                        borderColor: colorScheme.voc,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                ...commonOptions,
                scales: {
                    x: { type: 'time' },
                    y: {
                        position: 'left',
                        title: { display: true, text: 'Pressure (hPa)' }
                    },
                    y1: {
                        position: 'right',
                        title: { display: true, text: 'VOC (ppb)' },
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });
    }

    // Individual parameter charts
    ['vocChart'].forEach(chartId => {
        const canvas = document.getElementById(chartId);
        if (canvas) {
            const param = chartId.replace('Chart', '');
            charts[chartId] = new Chart(canvas.getContext('2d'), {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: getParameterLabel(param),
                        data: [],
                        borderColor: colorScheme[param] || 'rgba(75, 192, 192, 0.8)',
                        backgroundColor: (colorScheme[param] || 'rgba(75, 192, 192, 0.8)').replace('0.8', '0.3'),
                        fill: true
                    }]
                },
                options: {
                    ...commonOptions,
                    scales: { x: { type: 'time' } }
                }
            });
        }
    });

    // Cloud Environmental Scatter Plot
    if (document.getElementById('cloudEnvironmentalChart')) {
        charts.cloudEnvironmentalChart = new Chart(document.getElementById('cloudEnvironmentalChart').getContext('2d'), {
            type: 'scatter',
            data: {
                datasets: [
                    {
                        label: 'Temperature vs Cloud Cover',
                        data: [],
                        backgroundColor: colorScheme.temperature
                    },
                    {
                        label: 'Humidity vs Cloud Cover',
                        data: [],
                        backgroundColor: colorScheme.humidity
                    }
                ]
            },
            options: {
                ...commonOptions,
                scales: {
                    x: { title: { display: true, text: 'Cloud Cover (%)' } },
                    y: { title: { display: true, text: 'Environmental Values' } }
                }
            }
        });
    }

    // Check for missing chart containers and log warnings
    const chartContainers = [
        'timeChart', 'tempHumidityChart', 'pressureAirQualityChart', 'vocChart'
    ];

    chartContainers.forEach(containerId => {
        if (!document.getElementById(containerId)) {
            console.warn(`Chart container ${containerId} not found`);
        }
    });
}

// ========================
// DEEP ANALYTICS CHARTS (New)
// ========================

function initializeDeepAnalyticsCharts() {
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'top' } }
    };

    // Parameter Trend Chart
    if (document.getElementById('paramTrendChart')) {
        charts.paramTrendChart = new Chart(document.getElementById('paramTrendChart').getContext('2d'), {
            type: 'line',
            data: { 
                labels: [], 
                datasets: [{ 
                    label: 'Parameter Trend', 
                    data: [], 
                    borderColor: 'rgba(75, 192, 192, 0.8)',
                    fill: true,
                    backgroundColor: 'rgba(75, 192, 192, 0.2)'
                }] 
            },
            options: { 
                ...commonOptions, 
                scales: { x: { type: 'time' } } 
            }
        });
    }

    // Daily Statistics Chart
    if (document.getElementById('dailyStatsChart')) {
        charts.dailyStatsChart = new Chart(document.getElementById('dailyStatsChart').getContext('2d'), {
            type: 'bar',
            data: { 
                labels: [], 
                datasets: [
                    { label: 'Min', data: [], backgroundColor: 'rgba(255, 99, 132, 0.5)' },
                    { label: 'Average', data: [], backgroundColor: 'rgba(54, 162, 235, 0.5)' },
                    { label: 'Max', data: [], backgroundColor: 'rgba(75, 192, 192, 0.5)' }
                ] 
            },
            options: commonOptions
        });
    }

    // Correlation Scatter Plot
    if (document.getElementById('correlationScatter')) {
        charts.correlationScatter = new Chart(document.getElementById('correlationScatter').getContext('2d'), {
            type: 'scatter',
            data: { datasets: [] },
            options: {
                ...commonOptions,
                scales: {
                    x: { title: { display: true, text: 'X Parameter' } },
                    y: { title: { display: true, text: 'Y Parameter' } }
                }
            }
        });
    }

    // Histogram Chart
    if (document.getElementById('histogramChart')) {
        charts.histogramChart = new Chart(document.getElementById('histogramChart').getContext('2d'), {
            type: 'bar',
            data: { 
                labels: [], 
                datasets: [{ 
                    label: 'Frequency', 
                    data: [], 
                    backgroundColor: 'rgba(75, 192, 192, 0.6)'
                }] 
            },
            options: commonOptions
        });
    }

    // Data Completeness Chart
    if (document.getElementById('dataCompletenessChart')) {
        charts.dataCompletenessChart = new Chart(document.getElementById('dataCompletenessChart').getContext('2d'), {
            type: 'line',
            data: { 
                labels: [], 
                datasets: [{ 
                    label: '% Data Available', 
                    data: [], 
                    borderColor: 'rgba(75, 192, 192, 0.8)',
                    backgroundColor: 'rgba(75, 192, 192, 0.2)',
                    fill: true
                }] 
            },
            options: { 
                ...commonOptions, 
                scales: { 
                    x: { type: 'time' },
                    y: { max: 100, ticks: { callback: value => `${value}%` } }
                } 
            }
        });
    }

    // Setup parameter dropdowns
    setupParameterDropdowns();
}

function setupParameterDropdowns() {
    const paramSelects = ['paramSelect', 'corrParamX', 'corrParamY', 'histParamSelect'];
    const parameters = [
        { key: 'pm1', label: 'PM1' },
        { key: 'pm2_5', label: 'PM2.5' },
        { key: 'pm4', label: 'PM4' },
        { key: 'pm10', label: 'PM10' },
        { key: 'tsp', label: 'TSP' },
        { key: 'temperature_c', label: 'Temperature (°C)' },
        { key: 'humidity_percent', label: 'Humidity (%)' },
        { key: 'pressure_hpa', label: 'Pressure (hPa)' },
        { key: 'voc_ppb', label: 'VOC (ppb)' },
        { key: 'no2_ppb', label: 'NO₂ (ppb)' },
        { key: 'gps_speed_kmh', label: 'Speed (km/h)' },
        { key: 'cloud_cover_percent', label: 'Cloud Cover (%)' }
    ];

    paramSelects.forEach(selectId => {
        const select = document.getElementById(selectId);
        if (select) {
            parameters.forEach(param => {
                const option = document.createElement('option');
                option.value = param.key;
                option.textContent = param.label;
                select.appendChild(option);
            });

            // Add event listeners for dynamic updates
            select.addEventListener('change', function() {
                if (selectId === 'paramSelect') {
                    updateParameterTrendChart(this.value);
                } else if (selectId === 'histParamSelect') {
                    updateHistogramChart(this.value);
                } else if (selectId.startsWith('corr')) {
                    updateCorrelationChart();
                }
            });
        }
    });
}

// ========================
// UPDATE CHARTS THEME (Enhanced from your existing)
// ========================

function updateChartsTheme() {
    chartGridColor = getComputedStyle(document.documentElement).getPropertyValue('--chart-grid').trim() || 'rgba(0, 0, 0, 0.1)';
    chartTextColor = getComputedStyle(document.documentElement).getPropertyValue('--text-color').trim() || '#212529';

    // Update all charts
    Object.values(charts).forEach(chart => {
        if (!chart || !chart.options) return;
        
        // Update legend colors
        if (chart.options.plugins && chart.options.plugins.legend) {
            chart.options.plugins.legend.labels.color = chartTextColor;
        }
        
        // Update scale colors
        if (chart.options.scales) {
            Object.values(chart.options.scales).forEach(scale => {
                if (scale.grid) scale.grid.color = chartGridColor;
                if (scale.ticks) scale.ticks.color = chartTextColor;
                if (scale.title) scale.title.color = chartTextColor;
            });
        }
        
        safeChartUpdate(chart, 'theme');
    });
}

// Remove threshold chart references from safeChartUpdate
function safeChartUpdate(chart, key = 'chart') {
    try {
        if (chart && typeof chart.update === 'function') {
            chart.update('none'); // Use 'none' to prevent animations
        }
    } catch (err) {
        console.error(`Chart update failed for ${key}:`, err);
    }
}

// ========================
// DATA FETCHING (Enhanced from your existing)
// ========================

function fetchData(hours = 24) {
    if (!currentDeviceId) {
        createAlert('Please select a device first', 'warning');
        return;
    }

    const loadingIndicator = showLoading();
    
    fetch(`/api/data?hours=${encodeURIComponent(hours)}&avg_window=${encodeURIComponent(currentAvgWindow)}&deviceid=${encodeURIComponent(currentDeviceId)}`, {
        credentials: 'same-origin'
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            safeProcessIncomingData(data); // Use safe processing
        })
        .catch(error => {
            console.error('Error fetching data:', error);
            createAlert('Failed to fetch data. Please try again.', 'danger');
        })
        .finally(() => {
            if (loadingIndicator && loadingIndicator.parentNode === document.body) {
                document.body.removeChild(loadingIndicator);
            }
        });
}

function startRealtimePolling() {
    if (pollingIntervalId || !currentDeviceId) return;
    pollingIntervalId = setInterval(() => {
        if (currentDeviceId) fetchData(0.25);
    }, 5000);
}

function stopRealtimePolling() {
    if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
        pollingIntervalId = null;
    }
}

// ========================
// DASHBOARD UPDATE (Enhanced from your existing)
// ========================

function updateDashboard(data) {
    // Update connection status
    const connectionStatus = document.getElementById('connectionStatus') || document.getElementById('deviceStatus');
    const navConnectionStatus = document.getElementById('navConnectionStatus');
    const connectionDot = document.getElementById('connectionDot');
    
    if (connectionStatus) {
        connectionStatus.textContent = 'ONLINE';
        connectionStatus.className = 'badge bg-success';
    }
    
    if (navConnectionStatus) {
        navConnectionStatus.textContent = 'Online';
    }
    
    if (connectionDot) {
        connectionDot.className = 'status-dot online';
    }
    
    // Update last update time
    if (data.sensor && data.sensor.timestamp) {
        const lastUpdate = document.getElementById('lastUpdate');
        const readingsTime = document.getElementById('readingsTime');
        const lastUpdateTime = document.getElementById('lastUpdateTime');
        
        const timeStr = new Date(data.sensor.timestamp).toLocaleTimeString();
        
        if (lastUpdate) lastUpdate.textContent = new Date(data.sensor.timestamp).toLocaleString();
        if (readingsTime) readingsTime.textContent = timeStr;
        if (lastUpdateTime) lastUpdateTime.textContent = timeStr;
    }
    
    // Update PM readings
    updatePMReadings(data.sensor);
    
    // Update relay status if applicable
    if (data.status && data.status.relay_state !== 'N/A') {
        const relayState = document.getElementById('relayState');
        if (relayState) {
            relayState.textContent = data.status.relay_state;
            relayState.className = `badge ${data.status.relay_state === 'ON' ? 'bg-success' : 'bg-secondary'}`;
        }
    }
}

function updatePMReadings(sensor) {
    const pmReadings = document.getElementById('pmReadings');
    
    if (!pmReadings || !sensor) {
        if (pmReadings) pmReadings.innerHTML = '<p class="text-muted">No data available</p>';
        return;
    }
    
    const pmTypes = ['pm1', 'pm2_5', 'pm4', 'pm10', 'tsp'];
    const pmLabels = ['PM1', 'PM2.5', 'PM4', 'PM10', 'TSP'];
    
    pmReadings.innerHTML = pmTypes.map((type, index) => {
        const value = sensor[type] || 0;
        const percentage = Math.min(value / 200 * 100, 100);
        
        return `
            <div class="pm-reading-item">
                <div class="d-flex justify-content-between align-items-center w-100">
                    <span class="fw-bold">${pmLabels[index]}</span>
                    <span class="badge ${getAQIColor(value)} fs-6">${value.toFixed(1)} μg/m³</span>
                </div>
                <div class="progress mt-2" style="height: 6px;">
                    <div class="progress-bar ${getProgressBarColor(value)}" 
                         style="width: ${percentage}%"></div>
                </div>
            </div>
        `;
    }).join('');
    
    // Update legend statistics
    pmTypes.forEach((type, index) => {
        const statElement = document.getElementById(`${type.replace('_', '')}-stat`);
        if (statElement) {
            statElement.textContent = `${(sensor[type] || 0).toFixed(1)} μg/m³`;
        }
    });
}

function getProgressBarColor(value) {
    if (value < 50) return 'bg-success';
    if (value < 100) return 'bg-warning';
    if (value < 200) return 'bg-danger';
    return 'bg-dark';
}

function getAQIColor(value) {
    if (value < 50) return 'bg-success';
    if (value < 100) return 'bg-warning';
    if (value < 200) return 'bg-danger';
    return 'bg-dark';
}

// ========================
// CHART UPDATES (Enhanced from your existing)
// ========================

// ========================
// CHART UPDATE FUNCTIONS (Complete Fixed Version)
// ========================
function updateCharts(data) {
    if (!data || !data.history) {
        console.warn('No history data available for charts');
        return;
    }

    // Update PM Time Chart
    if (charts.timeChart && data.history.timestamps) {
        const timestamps = data.history.timestamps.map(t => new Date(t));

        charts.timeChart.data.labels = timestamps;
        charts.timeChart.data.datasets[0].data = data.history.pm1 || [];
        charts.timeChart.data.datasets[1].data = data.history.pm2_5 || [];
        charts.timeChart.data.datasets[2].data = data.history.pm4 || [];
        charts.timeChart.data.datasets[3].data = data.history.pm10 || [];
        charts.timeChart.data.datasets[4].data = data.history.tsp || [];

        safeChartUpdate(charts.timeChart, 'timeChart');
    }
}

// Fixed Extended Charts Update Function
function updateExtendedCharts(data) {
    if (!data) return;
    
    // Temperature & Humidity Chart
    if (charts.tempHumidityChart && data.history && data.history.timestamps) {
        const timestamps = data.history.timestamps.map(t => new Date(t));
        
        // Use extended data if available
        const tempData = data.extended?.temperature_c ? 
            Array(timestamps.length).fill(data.extended.temperature_c) : 
            timestamps.map(() => 20 + Math.random() * 15);
            
        const humidityData = data.extended?.humidity_percent ? 
            Array(timestamps.length).fill(data.extended.humidity_percent) : 
            timestamps.map(() => 40 + Math.random() * 40);
        
        charts.tempHumidityChart.data.labels = timestamps;
        charts.tempHumidityChart.data.datasets[0].data = tempData;
        charts.tempHumidityChart.data.datasets[1].data = humidityData;
        
        safeChartUpdate(charts.tempHumidityChart, 'tempHumidityChart');
    }
    
    updateIndividualExtendedCharts(data);
}

function updateIndividualExtendedCharts(data) {
    const extendedHistory = data.history && data.history.extended;
    if (!extendedHistory) {
        console.log('No extended history data available for individual charts');
        return;
    }

    // Use extended history timestamps
    const timestamps = extendedHistory.timestamps ? extendedHistory.timestamps.map(t => new Date(t)) : [];

    if (timestamps.length === 0) return;

    // VOC Chart
    if (charts.vocChart && extendedHistory.voc_ppb) {
        charts.vocChart.data.labels = timestamps;
        charts.vocChart.data.datasets[0].data = extendedHistory.voc_ppb;
        safeChartUpdate(charts.vocChart, 'vocChart');
    }

    // NO2 Chart
    if (charts.no2Chart && extendedHistory.no2_ppb) {
        charts.no2Chart.data.labels = timestamps;
        charts.no2Chart.data.datasets[0].data = extendedHistory.no2_ppb;
        safeChartUpdate(charts.no2Chart, 'no2Chart');
    }

    // Speed Chart
    if (charts.speedChart && extendedHistory.gps_speed_kmh) {
        charts.speedChart.data.labels = timestamps;
        charts.speedChart.data.datasets[0].data = extendedHistory.gps_speed_kmh;
        safeChartUpdate(charts.speedChart, 'speedChart');
    }

    // Pressure & Air Quality Chart
    if (charts.pressureAirQualityChart && extendedHistory.pressure_hpa && extendedHistory.voc_ppb && extendedHistory.no2_ppb) {
        charts.pressureAirQualityChart.data.labels = timestamps;
        charts.pressureAirQualityChart.data.datasets[0].data = extendedHistory.pressure_hpa;
        charts.pressureAirQualityChart.data.datasets[1].data = extendedHistory.voc_ppb;
        charts.pressureAirQualityChart.data.datasets[2].data = extendedHistory.no2_ppb;
        safeChartUpdate(charts.pressureAirQualityChart, 'pressureAirQualityChart');
    }
}

function debugDataFlow(data, stage) {
    console.group(`Data Flow: ${stage}`);
    console.log('Raw data structure:', data);
    if (data && data.sensor) console.log('Sensor data:', data.sensor);
    if (data && data.extended) console.log('Extended data:', data.extended);
    if (data && data.history) console.log('History data keys:', Object.keys(data.history));
    console.groupEnd();
}

function updateDeepAnalyticsCharts(data) {
    if (!data.history || !data.history.timestamps) return;
    
    const timestamps = data.history.timestamps.map(t => new Date(t));
    
    // Parameter Trend Chart (default to PM2.5)
    if (charts.paramTrendChart) {
        const selectedParam = document.getElementById('paramSelect')?.value || 'pm2_5';
        const paramData = data.history[selectedParam] || data.history.pm2_5 || [];
        
        charts.paramTrendChart.data.labels = timestamps;
        charts.paramTrendChart.data.datasets[0].data = paramData;
        charts.paramTrendChart.data.datasets.label = getParameterLabel(selectedParam);
        
        safeChartUpdate(charts.paramTrendChart, 'paramTrendChart');
    }
    
    // Daily Statistics Chart (mock data for now)
    if (charts.dailyStatsChart && data.history.pm2_5) {
        const pm25Data = data.history.pm2_5.filter(v => v != null);
        if (pm25Data.length > 0) {
            const min = Math.min(...pm25Data);
            const max = Math.max(...pm25Data);
            const avg = pm25Data.reduce((a, b) => a + b, 0) / pm25Data.length;
            
            charts.dailyStatsChart.data.labels = ['Today'];
            charts.dailyStatsChart.data.datasets[0].data = [min];
            charts.dailyStatsChart.data.datasets[1].data = [avg];
            charts.dailyStatsChart.data.datasets[2].data = [max];
            
            safeChartUpdate(charts.dailyStatsChart, 'dailyStatsChart');
        }
    }
    
    // Data Completeness Chart
    if (charts.dataCompletenessChart) {
        const totalPoints = timestamps.length;
        const validPoints = data.history.pm2_5.filter(v => v != null && !isNaN(v)).length;
        const completeness = totalPoints > 0 ? (validPoints / totalPoints) * 100 : 0;
        
        charts.dataCompletenessChart.data.labels = timestamps;
        charts.dataCompletenessChart.data.datasets[0].data = Array(totalPoints).fill(completeness);
        
        safeChartUpdate(charts.dataCompletenessChart, 'dataCompletenessChart');
    }
}

function startRealtimePolling() {
    // Prevent multiple polling instances
    if (pollingIntervalId || !currentDeviceId) return;

    console.log('Starting real-time polling (fallback mode)');
    pollingIntervalId = setInterval(() => {
        if (currentDeviceId && (!socket || !socket.connected)) {
            console.log('Polling for new data (WebSocket unavailable)...');
            fetchData(0.25); // Get last 15 minutes of data
        }
    }, 30000); // Poll every 30 seconds (reduced from 5 seconds)
}

function stopRealtimePolling() {
    if (pollingIntervalId) {
        console.log('Stopping real-time polling');
        clearInterval(pollingIntervalId);
        pollingIntervalId = null;
    }
}

// Add missing parameter trend chart update function
function updateParameterTrendChart(parameter) {
    if (!currentDeviceId) return;
    
    // Fetch current data and update chart
    fetch(`/api/data?hours=24&deviceid=${currentDeviceId}`)
        .then(response => response.json())
        .then(data => {
            if (charts.paramTrendChart && data.history) {
                const timestamps = data.history.timestamps.map(t => new Date(t));
                const paramData = data.history[parameter] || [];
                
                charts.paramTrendChart.data.labels = timestamps;
                charts.paramTrendChart.data.datasets[0].data = paramData;
                charts.paramTrendChart.data.datasets.label = getParameterLabel(parameter);
                
                safeChartUpdate(charts.paramTrendChart, 'paramTrendChart');
            }
        })
        .catch(error => console.error('Error updating parameter trend:', error));
}

// Add missing correlation chart update function
function updateCorrelationChart() {
    const paramX = document.getElementById('corrParamX')?.value;
    const paramY = document.getElementById('corrParamY')?.value;
    
    if (!paramX || !paramY || !currentDeviceId) return;
    
    fetch(`/api/data?hours=24&deviceid=${currentDeviceId}`)
        .then(response => response.json())
        .then(data => {
            if (charts.correlationScatter && data.history) {
                const xData = data.history[paramX] || [];
                const yData = data.history[paramY] || [];
                
                const scatterData = xData.map((x, i) => ({
                    x: x || 0,
                    y: yData[i] || 0
                }));
                
                charts.correlationScatter.data.datasets = [{
                    label: `${getParameterLabel(paramX)} vs ${getParameterLabel(paramY)}`,
                    data: scatterData,
                    backgroundColor: 'rgba(75, 192, 192, 0.6)'
                }];
                
                charts.correlationScatter.options.scales.x.title.text = getParameterLabel(paramX);
                charts.correlationScatter.options.scales.y.title.text = getParameterLabel(paramY);
                
                safeChartUpdate(charts.correlationScatter, 'correlationScatter');
            }
        })
        .catch(error => console.error('Error updating correlation chart:', error));
}

// Add missing histogram chart update function
function updateHistogramChart(parameter) {
    if (!currentDeviceId) return;
    
    fetch(`/api/data?hours=24&deviceid=${currentDeviceId}`)
        .then(response => response.json())
        .then(data => {
            if (charts.histogramChart && data.history) {
                const paramData = data.history[parameter] || [];
                const validData = paramData.filter(v => v != null && !isNaN(v));
                
                if (validData.length > 0) {
                    // Create histogram bins
                    const min = Math.min(...validData);
                    const max = Math.max(...validData);
                    const binCount = 10;
                    const binSize = (max - min) / binCount;
                    
                    const bins = Array(binCount).fill(0);
                    const binLabels = [];
                    
                    for (let i = 0; i < binCount; i++) {
                        const binStart = min + i * binSize;
                        const binEnd = min + (i + 1) * binSize;
                        binLabels.push(`${binStart.toFixed(1)}-${binEnd.toFixed(1)}`);
                    }
                    
                    validData.forEach(value => {
                        const binIndex = Math.min(Math.floor((value - min) / binSize), binCount - 1);
                        bins[binIndex]++;
                    });
                    
                    charts.histogramChart.data.labels = binLabels;
                    charts.histogramChart.data.datasets[0].data = bins;
                    charts.histogramChart.data.datasets.label = `${getParameterLabel(parameter)} Distribution`;
                    
                    safeChartUpdate(charts.histogramChart, 'histogramChart');
                }
            }
        })
        .catch(error => console.error('Error updating histogram:', error));
}

function calculateDataCompleteness(history, timestamps) {
    // Simple completeness calculation
    const windowSize = 10;
    const allParams = ['pm1', 'pm2_5', 'pm4', 'pm10', 'tsp'];
    
    return timestamps.map((timestamp, i) => {
        const start = Math.max(0, i - windowSize);
        const end = Math.min(timestamps.length, i + windowSize);
        const window = end - start;
        
        let validCount = 0;
        allParams.forEach(param => {
            if (history[param]) {
                for (let j = start; j < end; j++) {
                    if (history[param][j] != null) validCount++;
                }
            }
        });
        
        return (validCount / (window * allParams.length)) * 100;
    });
}

function updateDailyStatisticsChart(history) {
    if (!charts.dailyStatsChart) return;
    
    // Group data by day and calculate min, max, avg
    const dailyStats = {};
    const timestamps = history.timestamps || [];
    const pm25Data = history.pm2_5 || [];
    
    timestamps.forEach((timestamp, i) => {
        const date = new Date(timestamp).toDateString();
        if (!dailyStats[date]) {
            dailyStats[date] = [];
        }
        if (pm25Data[i] != null) {
            dailyStats[date].push(pm25Data[i]);
        }
    });
    
    const labels = Object.keys(dailyStats).slice(-7); // Last 7 days
    const minValues = labels.map(date => Math.min(...dailyStats[date]));
    const maxValues = labels.map(date => Math.max(...dailyStats[date]));
    const avgValues = labels.map(date => 
        dailyStats[date].reduce((a, b) => a + b, 0) / dailyStats[date].length
    );
    
    charts.dailyStatsChart.data.labels = labels.map(date => new Date(date).toLocaleDateString());
    charts.dailyStatsChart.data.datasets[0].data = minValues;
    charts.dailyStatsChart.data.datasets[1].data = avgValues;
    charts.dailyStatsChart.data.datasets[2].data = maxValues;
    const allValues = minValues.concat(avgValues).concat(maxValues);
    applyRigidAxisForBar('dailyStatsChart', charts.dailyStatsChart, allValues);
    safeChartUpdate(charts.dailyStatsChart, 'dailyStatsChart');
}

// ========================
// RIGID AXIS HELPERS AND HISTOGRAM
// ========================
function applyRigidAxisForLine(key, chart, arrays, yMin = 0, yMaxFixed = null) {
    if (!chart || !chart.options || !chart.options.scales) return;
    const flat = (arrays || []).flat().filter(v => Number.isFinite(v));
    const maxVal = flat.length ? Math.max(...flat) : 0;
    if (!rigidMaxByChart[key]) rigidMaxByChart[key] = {};
    const prev = rigidMaxByChart[key].y || 0;
    const newMax = yMaxFixed != null ? yMaxFixed : Math.max(prev, Math.ceil(maxVal * 1.1));
    rigidMaxByChart[key].y = newMax;
    chart.options.scales.y = chart.options.scales.y || {};
    chart.options.scales.y.min = yMin;
    chart.options.scales.y.max = Math.max(10, newMax);
    chart.options.scales.y.suggestedMax = undefined;
}

function applyRigidAxisForDual(key, chart, yArr, y1Arr, yMin = 0, y1Min = 0) {
    if (!chart || !chart.options || !chart.options.scales) return;
    if (!rigidMaxByChart[key]) rigidMaxByChart[key] = {};
    const yVals = (yArr || []).filter(Number.isFinite);
    const y1Vals = (y1Arr || []).filter(Number.isFinite);
    const yMax = yVals.length ? Math.ceil(Math.max(...yVals) * 1.1) : 0;
    const y1Max = y1Vals.length ? Math.ceil(Math.max(...y1Vals) * 1.1) : 0;
    rigidMaxByChart[key].y = Math.max(rigidMaxByChart[key].y || 0, yMax);
    rigidMaxByChart[key].y1 = Math.max(rigidMaxByChart[key].y1 || 0, y1Max);
    chart.options.scales.y = chart.options.scales.y || {};
    chart.options.scales.y1 = chart.options.scales.y1 || {};
    chart.options.scales.y.min = yMin;
    chart.options.scales.y.max = Math.max(10, rigidMaxByChart[key].y);
    chart.options.scales.y.suggestedMax = undefined;
    chart.options.scales.y1.min = y1Min;
    chart.options.scales.y1.max = Math.max(10, rigidMaxByChart[key].y1);
    chart.options.scales.y1.suggestedMax = undefined;
}

function applyRigidAxisForBar(key, chart, values, yMin = 0, yMaxFixed = null) {
    if (!chart || !chart.options || !chart.options.scales) return;
    const vals = (values || []).filter(Number.isFinite);
    const maxVal = vals.length ? Math.max(...vals) : 0;
    if (!rigidMaxByChart[key]) rigidMaxByChart[key] = {};
    const prev = rigidMaxByChart[key].y || 0;
    const newMax = yMaxFixed != null ? yMaxFixed : Math.max(prev, Math.ceil(maxVal * 1.1));
    rigidMaxByChart[key].y = newMax;
    chart.options.scales.y = chart.options.scales.y || {};
    chart.options.scales.y.min = yMin;
    chart.options.scales.y.max = Math.max(10, newMax);
    chart.options.scales.y.suggestedMax = undefined;
}

function applyRigidAxisForScatter(key, chart, xArray, yArray) {
    if (!chart || !chart.options || !chart.options.scales) return;
    if (!rigidMaxByChart[key]) rigidMaxByChart[key] = {};
    const xVals = (xArray || []).filter(Number.isFinite);
    const yVals = (yArray || []).filter(Number.isFinite);
    if (xVals.length) {
        const xMin = Math.min(...xVals);
        const xMax = Math.max(...xVals);
        rigidMaxByChart[key].xMin = rigidMaxByChart[key].xMin == null ? xMin : Math.min(rigidMaxByChart[key].xMin, xMin);
        rigidMaxByChart[key].xMax = rigidMaxByChart[key].xMax == null ? xMax : Math.max(rigidMaxByChart[key].xMax, xMax);
        chart.options.scales.x = chart.options.scales.x || {};
        chart.options.scales.x.min = rigidMaxByChart[key].xMin;
        chart.options.scales.x.max = rigidMaxByChart[key].xMax;
    }
    if (yVals.length) {
        const yMin = Math.min(...yVals);
        const yMax = Math.max(...yVals);
        rigidMaxByChart[key].yMin = rigidMaxByChart[key].yMin == null ? yMin : Math.min(rigidMaxByChart[key].yMin, yMin);
        rigidMaxByChart[key].y = Math.max(rigidMaxByChart[key].y || 0, Math.ceil(yMax * 1.1));
        chart.options.scales.y = chart.options.scales.y || {};
        chart.options.scales.y.min = rigidMaxByChart[key].yMin;
        chart.options.scales.y.max = Math.max(10, rigidMaxByChart[key].y);
    }
}

function buildHistogram(series, binCount = 20) {
    const arr = (series || []).filter(Number.isFinite);
    if (!arr.length) return { labels: [], counts: [] };
    const min = Math.min(...arr);
    const max = Math.max(...arr);
    const width = (max - min) || 1;
    const step = width / binCount;
    const edges = Array.from({ length: binCount + 1 }, (_, i) => min + i * step);
    const counts = Array(binCount).fill(0);
    arr.forEach(v => {
        const idx = Math.min(binCount - 1, Math.floor((v - min) / step));
        counts[idx]++;
    });
    const labels = Array.from({ length: binCount }, (_, i) => `${edges[i].toFixed(1)}–${edges[i+1].toFixed(1)}`);
    return { labels, counts };
}

// ========================
// EXTENDED DATA HANDLING (New)
// ========================

function updateExtendedData(extendedData) {
    console.log('🔄 updateExtendedData called with:', extendedData);

    if (!extendedData) {
        console.log('❌ No extended data provided');
        return;
    }

    // Debug: Log the structure of extendedData
    console.log('📊 Extended data structure:', Object.keys(extendedData));
    console.log('🌡️ Temperature:', extendedData.temperature_c);
    console.log('💧 Humidity:', extendedData.humidity_percent);
    console.log('🌪️ Pressure:', extendedData.pressure_hpa);
    console.log('🧪 VOC:', extendedData.voc_ppb);
    console.log('💡 Lux:', extendedData.lux);
    console.log('☀️ UV Index:', extendedData.uv_index);

    // Force activate environmental tab if not already active
    const environmentalTab = document.getElementById('environmental-tab');
    const environmentalTabContent = document.getElementById('environmental');

    if (environmentalTab && environmentalTabContent) {
        // Check if tab is hidden and show it
        if (environmentalTab.style.display === 'none') {
            console.log('🔧 Environmental tab was hidden, showing it now');
            environmentalTab.style.display = 'block';

            // Use Bootstrap's Tab API to properly activate
            const bsTab = new bootstrap.Tab(environmentalTab);
            bsTab.show();
        }

        console.log('✅ Environmental tab is visible and active');
    }

    // Update individual readings - use the correct element IDs from HTML
    console.log('🔄 Updating environmental cards...');

    // Check if elements exist before updating
    const tempElement = document.getElementById('currentTemp');
    console.log('Temperature element exists:', !!tempElement, 'Current text:', tempElement?.textContent);

    updateEnvironmentalCard('currentTemp', extendedData.temperature_c, '°C');
    updateEnvironmentalCard('currentHumidity', extendedData.humidity_percent, '%');
    updateEnvironmentalCard('currentPressure', extendedData.pressure_hpa, ' hPa');
    updateEnvironmentalCard('currentVOC', extendedData.voc_ppb, ' ppb');
    updateEnvironmentalCard('currentNO2', extendedData.no2_ppb, ' ppb');
    updateEnvironmentalCard('currentNoise', extendedData.noise_db, ' dB');
    updateEnvironmentalCard('currentCloudCover', extendedData.cloud_cover_percent, '%');
    updateEnvironmentalCard('currentLux', extendedData.lux, ' lux');
    updateEnvironmentalCard('currentUV', extendedData.uv_index, '');

    console.log('✅ Extended data update completed');

    // Update environmental summary in the overview tab
    updateEnvironmentalSummary(extendedData);
}

function updateEnvironmentalCard(elementId, value, unit) {
    console.log(`updateEnvironmentalCard: ${elementId}=${value}${unit}`);
    const element = document.getElementById(elementId);

    if (element) {
        console.log(`Found element ${elementId}, current text: "${element.textContent}"`);
        if (value !== null && value !== undefined && !isNaN(value)) {
            const newText = `${value.toFixed(1)}${unit}`;
            console.log(`Setting ${elementId} to: "${newText}"`);
            element.textContent = newText;
            element.style.color = '#0d6efd'; // Blue color for valid data
        } else {
            const newText = `--${unit}`;
            console.log(`Setting ${elementId} to: "${newText}" (no data)`);
            element.textContent = newText;
            element.style.color = '#6c757d'; // Gray color for no data
        }
        console.log(`Final text for ${elementId}: "${element.textContent}"`);
    } else {
        console.error(`Element with ID '${elementId}' not found!`);
        // List all elements with similar IDs to help debug
        const allElements = document.querySelectorAll('[id*="current"]');
        console.log('Available elements with "current" in ID:', Array.from(allElements).map(el => el.id));
    }
}

function updateEnvironmentalSummary(data) {
    // Update temperature
    const tempElement = document.querySelector('#environmentalSummary .col-6:nth-child(1) .h6');
    if (tempElement) {
        tempElement.textContent = data.temperature_c ? data.temperature_c.toFixed(1) + '°C' : '--';
    }

    // Update humidity
    const humidityElement = document.querySelector('#environmentalSummary .col-6:nth-child(2) .h6');
    if (humidityElement) {
        humidityElement.textContent = data.humidity_percent ? data.humidity_percent.toFixed(1) + '%' : '--';
    }

    // Update VOC
    const vocElement = document.querySelector('#environmentalSummary .col-6:nth-child(3) .h6');
    if (vocElement) {
        vocElement.textContent = data.voc_ppb ? data.voc_ppb.toFixed(1) + ' ppb' : '--';
    }

    // Update NO2
    const no2Element = document.querySelector('#environmentalSummary .col-6:nth-child(4) .h6');
    if (no2Element) {
        no2Element.textContent = data.no2_ppb ? data.no2_ppb.toFixed(1) + ' ppb' : '--';
    }
}

// ========================
// MISSING CORE FUNCTIONS
// ========================

function joinDeviceRoom(deviceId) {
    if (socket && socket.connected) {
        // Leave previous room
        if (currentDeviceRoom && currentDeviceRoom !== deviceId) {
            socket.emit('leave', { device_id: currentDeviceRoom });
        }
        
        // Join new room
        socket.emit('join', { device_id: deviceId });
        currentDeviceRoom = deviceId;
        console.log(`Joined room for device: ${deviceId}`);
    }
}

function updateConnectionStatus(isConnected) {
    const connectionElements = [
        document.getElementById('connectionStatus'),
        document.getElementById('deviceStatus'),
        document.getElementById('navConnectionStatus')
    ];
    
    const connectionDot = document.getElementById('connectionDot');
    
    connectionElements.forEach(el => {
        if (el) {
            el.textContent = isConnected ? 'Online' : 'Offline';
            el.className = `badge ${isConnected ? 'bg-success' : 'bg-danger'}`;
        }
    });
    
    if (connectionDot) {
        connectionDot.className = `status-dot ${isConnected ? 'online' : 'offline'}`;
    }
}

function showLoading() {
    const loadingDiv = document.createElement('div');
    loadingDiv.innerHTML = `
        <div class="d-flex justify-content-center align-items-center" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.3); z-index: 9999;">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;
    document.body.appendChild(loadingDiv);
    return loadingDiv;
}

function createAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(alertDiv);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

function setDefaultDates() {
    const endDate = new Date();
    const startDate = new Date(endDate.getTime() - 24 * 60 * 60 * 1000); // 24 hours ago
    
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    
    if (startDateInput) {
        startDateInput.value = startDate.toISOString().split('T')[0];
    }
    if (endDateInput) {
        endDateInput.value = endDate.toISOString().split('T');
    }
}

function setupRelayControls() {
    // Relay ON button
    const relayOnBtn = document.getElementById('relayOnBtn');
    if (relayOnBtn) {
        relayOnBtn.addEventListener('click', function() {
            if (!currentDeviceId) {
                createAlert('Please select a device first', 'warning');
                return;
            }
            
            fetch('/api/relay_control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device_id: currentDeviceId, state: 'ON' })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    createAlert('Relay turned ON', 'success');
                } else {
                    createAlert(data.message || 'Failed to turn ON relay', 'danger');
                }
            })
            .catch(error => {
                console.error('Error controlling relay:', error);
                createAlert('Error controlling relay', 'danger');
            });
        });
    }
    
    // Relay OFF button
    const relayOffBtn = document.getElementById('relayOffBtn');
    if (relayOffBtn) {
        relayOffBtn.addEventListener('click', function() {
            if (!currentDeviceId) {
                createAlert('Please select a device first', 'warning');
                return;
            }
            
            fetch('/api/relay_control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device_id: currentDeviceId, state: 'OFF' })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    createAlert('Relay turned OFF', 'success');
                } else {
                    createAlert(data.message || 'Failed to turn OFF relay', 'danger');
                }
            })
            .catch(error => {
                console.error('Error controlling relay:', error);
                createAlert('Error controlling relay', 'danger');
            });
        });
    }
}

// Initialize map for location tracking
function initializeMap() {
    const mapContainer = document.getElementById('deviceMap');
    if (!mapContainer || map) return;
    
    map = L.map('deviceMap').setView([20.5937, 78.9629], 5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    
    deviceMarker = L.marker([20.5937, 78.9629]).addTo(map);
    
    console.log('Map initialized for extended device');
}


// ========================
// QUICK STATS & AQI (New)
// ========================

function updateQuickStats(data) {
    // Update online devices count
    const onlineDevices = document.getElementById('onlineDevices');
    if (onlineDevices) {
        onlineDevices.textContent = currentDeviceId ? '1' : '0';
    }
    
    // Update average PM2.5
    const avgPM25 = document.getElementById('avgPM25');
    if (avgPM25 && data && data.sensor && typeof data.sensor.pm2_5 === 'number') {
        avgPM25.textContent = `${data.sensor.pm2_5.toFixed(1)}`;
    }
    
    // Update max temperature
    const maxTemp = document.getElementById('maxTemp');
    if (maxTemp && data && data.extended && typeof data.extended.temperature_c === 'number') {
        maxTemp.textContent = `${data.extended.temperature_c.toFixed(1)}°C`;
    }
}

function updateAQI(data) {
    console.log('updateAQI called with data:', data);

    const aqiCircle = document.getElementById('aqiCircle');
    const aqiValue = document.getElementById('aqiValue');
    const aqiLabel = document.getElementById('aqiLabel');
    const aqiDescription = document.getElementById('aqiDescription');

    // Use PM2.5 from sensor data (primary) or extended data (fallback)
    let pm25 = null;

    // Check sensor data first
    if (data.sensor && typeof data.sensor.pm2_5 === 'number' && !isNaN(data.sensor.pm2_5)) {
        pm25 = data.sensor.pm2_5;
        console.log('Using PM2.5 from sensor data:', pm25);
    }
    // Check extended data as fallback
    else if (data.extended && typeof data.extended.pm2_5 === 'number' && !isNaN(data.extended.pm2_5)) {
        pm25 = data.extended.pm2_5;
        console.log('Using PM2.5 from extended data:', pm25);
    }

    if (pm25 === null || pm25 < 0) {
        console.warn("AQI: No valid PM2.5 data available");
        if (aqiValue) aqiValue.textContent = '--';
        if (aqiLabel) aqiLabel.textContent = 'No Data';
        if (aqiDescription) aqiDescription.textContent = 'Select a device to see AQI';
        if (aqiCircle) aqiCircle.style.borderColor = '#e9ecef';
        return;
    }

    console.log('Calculating AQI for PM2.5:', pm25);

    let aqi, label, description, color;

    if (pm25 <= 12) {
        aqi = Math.round((50 / 12) * pm25);
        label = 'Good';
        description = 'Air quality is satisfactory';
        color = '#00e400';
    } else if (pm25 <= 35.4) {
        aqi = Math.round(51 + ((100 - 51) / (35.4 - 12.1)) * (pm25 - 12.1));
        label = 'Moderate';
        description = 'Air quality is acceptable for most';
        color = '#ffff00';
    } else if (pm25 <= 55.4) {
        aqi = Math.round(101 + ((150 - 101) / (55.4 - 35.5)) * (pm25 - 35.5));
        label = 'Unhealthy for Sensitive';
        description = 'Sensitive individuals may experience symptoms';
        color = '#ff7e00';
    } else if (pm25 <= 150.4) {
        aqi = Math.round(151 + ((200 - 151) / (150.4 - 55.5)) * (pm25 - 55.5));
        label = 'Unhealthy';
        description = 'Everyone may experience symptoms';
        color = '#ff0000';
    } else {
        aqi = Math.round(201 + ((300 - 201) / (250.4 - 150.5)) * (pm25 - 150.5));
        label = 'Very Unhealthy';
        description = 'Health warnings of emergency conditions';
        color = '#8f3f97';
    }

    console.log('Calculated AQI:', { aqi, label, description, color });

    // Update AQI display
    if (aqiValue) {
        aqiValue.textContent = aqi;
        aqiValue.style.color = color;
    }
    if (aqiLabel) {
        aqiLabel.textContent = label;
        aqiLabel.style.color = color;
    }
    if (aqiDescription) {
        aqiDescription.textContent = description;
    }
    if (aqiCircle) {
        aqiCircle.style.borderColor = color;
    }
}

// ========================
// MAP FUNCTIONALITY (New)
// ========================

function initializeMap() {
    if (map) return;
    
    map = L.map('map').setView([0, 0], 2);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
}


// ========================
// MISSING CORE FUNCTIONS
// ========================

function updateQuickStats(data) {
    if (!data || !data.sensor) return;
    
    // Update quick stats cards
    const statsElements = {
        'quickPM25': data.sensor.pm2_5 || 0,
        'quickPM10': data.sensor.pm10 || 0,
        'quickTemp': data.extended?.temperature_c || '--',
        'quickHumidity': data.extended?.humidity_percent || '--'
    };
    
    Object.entries(statsElements).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = typeof value === 'number' ? 
                value.toFixed(1) : value;
        }
    });
}



function checkThresholds(data) {
    if (!data || !data.sensor || !data.status?.thresholds) return;
    
    const sensor = data.sensor;
    const thresholds = data.status.thresholds;
    
    const exceedances = [];
    
    if (sensor.pm1 > thresholds.pm1) exceedances.push('PM1');
    if (sensor.pm2_5 > thresholds['pm2.5']) exceedances.push('PM2.5');
    if (sensor.pm4 > thresholds.pm4) exceedances.push('PM4');
    if (sensor.pm10 > thresholds.pm10) exceedances.push('PM10');
    if (sensor.tsp > thresholds.tsp) exceedances.push('TSP');
    
    if (exceedances.length > 0) {
        createAlert(`Threshold exceeded for: ${exceedances.join(', ')}`, 'warning');
    }
}

function calculateThresholdFrequency(data) {
    if (!data || !data.history) return;
    
    // This would normally calculate from historical data
    // For now, just update the chart with sample data
    if (charts.thresholdFrequencyChart) {
        const sampleData = [10, 15, 8, 12, 5]; // Sample percentages
        charts.thresholdFrequencyChart.data.datasets[0].data = sampleData;
        safeChartUpdate(charts.thresholdFrequencyChart, 'thresholdFrequency');
    }
}

function updateExtendedData(extendedData) {
    if (!extendedData) return;
    
    // Update extended data displays
    const mappings = {
        'extTemp': extendedData.temperature_c,
        'extHumidity': extendedData.humidity_percent,
        'extPressure': extendedData.pressure_hpa,
        'extVOC': extendedData.voc_ppb,
        'extNO2': extendedData.no2_ppb,
        'extCloudCover': extendedData.cloud_cover_percent
    };
    
    Object.entries(mappings).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element && value !== null && value !== undefined) {
            element.textContent = typeof value === 'number' ? 
                value.toFixed(1) : value;
        }
    });
    
    // Update GPS location if available
    if (extendedData.gps_lat && extendedData.gps_lon && deviceMarker) {
        deviceMarker.setLatLng([extendedData.gps_lat, extendedData.gps_lon]);
        if (map) {
            map.setView([extendedData.gps_lat, extendedData.gps_lon], map.getZoom());
        }
    }
}

function updateDeepAnalyticsCharts(data) {
    // Placeholder for deep analytics updates
    console.log('Deep analytics charts updated');
}

function getParameterLabel(param) {
    const labels = {
        'voc': 'VOC (ppb)',
        'no2': 'NO₂ (ppb)',
        'speed': 'Speed (km/h)',
        'temp': 'Temperature (°C)',
        'humidity': 'Humidity (%)',
        'pressure': 'Pressure (hPa)'
    };
    return labels[param] || param.toUpperCase();
}

// ======================== 
// CHART UPDATE FUNCTIONS (Fixed)
// ========================
function updateCharts(data) {
    if (!data.history) return;
    
    // Update PM Time Chart
    if (charts.timeChart && data.history.timestamps) {
        const timestamps = data.history.timestamps.map(t => new Date(t));
        
        charts.timeChart.data.labels = timestamps;
        charts.timeChart.data.datasets[0].data = data.history.pm1 || [];
        charts.timeChart.data.datasets[1].data = data.history.pm2_5 || [];
        charts.timeChart.data.datasets[2].data = data.history.pm4 || [];
        charts.timeChart.data.datasets[3].data = data.history.pm10 || [];
        charts.timeChart.data.datasets[4].data = data.history.tsp || [];
        
        // Handle rigid axes if enabled
        if (rigidAxesEnabled && data.history.pm1 && data.history.pm1.length > 0) {
            const allValues = [
                ...data.history.pm1,
                ...data.history.pm2_5,
                ...data.history.pm4,
                ...data.history.pm10,
                ...data.history.tsp
            ].filter(v => v != null && !isNaN(v));
            
            if (allValues.length > 0) {
                const maxVal = Math.max(...allValues);
                const rigidMax = Math.ceil(maxVal * 1.1 / 50) * 50;
                rigidMaxByChart['timeChart'] = rigidMax;
                charts.timeChart.options.scales.y.max = rigidMax;
            }
        }
        
        safeChartUpdate(charts.timeChart, 'timeChart');
    }
    
    // Update threshold comparison chart
    if (charts.thresholdChart && data.sensor) {
        const currentValues = [
            data.sensor.pm1 || 0,
            data.sensor.pm2_5 || 0,
            data.sensor.pm4 || 0,
            data.sensor.pm10 || 0,
            data.sensor.tsp || 0
        ];
        
        const thresholdValues = data.status && data.status.thresholds ? [
            data.status.thresholds.pm1 || 50,
            data.status.thresholds['pm2.5'] || 75,
            data.status.thresholds.pm4 || 100,
            data.status.thresholds.pm10 || 150,
            data.status.thresholds.tsp || 200
        ] : [50, 75, 100, 150, 200];
        
        charts.thresholdChart.data.datasets[0].data = currentValues;
        charts.thresholdChart.data.datasets[1].data = thresholdValues;
        
        safeChartUpdate(charts.thresholdChart, 'thresholdChart');
    }
}

function updateExtendedCharts(data) {
    if (!data) return;

    console.log('updateExtendedCharts called with:', data);

    // Get current sensor data for real-time display
    const extendedData = data.extended || {};
    console.log('Extended data available:', Object.keys(extendedData));

    // Get history data for charts
    const history = data.history || {};
    const extendedHistory = history.extended || {};
    console.log('Extended history available:', Object.keys(extendedHistory));

    // Temperature & Humidity Chart
    if (charts.tempHumidityChart) {
        let timestamps = [];
        let tempData = [];
        let humidityData = [];

        // Use extended history if available, otherwise use current data
        if (extendedHistory.timestamps && extendedHistory.temperature_c && extendedHistory.humidity_percent) {
            timestamps = extendedHistory.timestamps.map(t => new Date(t));
            tempData = extendedHistory.temperature_c;
            humidityData = extendedHistory.humidity_percent;
        } else if (extendedData.temperature_c !== undefined && extendedData.humidity_percent !== undefined) {
            // Create single point data for current readings
            timestamps = [new Date()];
            tempData = [extendedData.temperature_c];
            humidityData = [extendedData.humidity_percent];
        }

        if (timestamps.length > 0) {
            charts.tempHumidityChart.data.labels = timestamps;
            charts.tempHumidityChart.data.datasets[0].data = tempData;
            charts.tempHumidityChart.data.datasets[1].data = humidityData;
            safeChartUpdate(charts.tempHumidityChart, 'tempHumidityChart');
        }
    }

    // Pressure & Air Quality Chart
    if (charts.pressureAirQualityChart) {
        let timestamps = [];
        let pressureData = [];
        let vocData = [];

        if (extendedHistory.timestamps && extendedHistory.pressure_hpa && extendedHistory.voc_ppb) {
            timestamps = extendedHistory.timestamps.map(t => new Date(t));
            pressureData = extendedHistory.pressure_hpa;
            vocData = extendedHistory.voc_ppb;
        } else if (extendedData.pressure_hpa !== undefined && extendedData.voc_ppb !== undefined) {
            timestamps = [new Date()];
            pressureData = [extendedData.pressure_hpa];
            vocData = [extendedData.voc_ppb];
        }

        if (timestamps.length > 0) {
            charts.pressureAirQualityChart.data.labels = timestamps;
            charts.pressureAirQualityChart.data.datasets[0].data = pressureData;
            charts.pressureAirQualityChart.data.datasets[1].data = vocData;
            safeChartUpdate(charts.pressureAirQualityChart, 'pressureAirQualityChart');
        }
    }

    updateIndividualExtendedCharts(data);
}

function updateIndividualExtendedCharts(data) {
    const extendedData = data.extended || {};
    const extendedHistory = data.history && data.history.extended ? data.history.extended : {};
    const timestamps = extendedHistory.timestamps ? extendedHistory.timestamps.map(t => new Date(t)) : [];

    console.log('updateIndividualExtendedCharts - extendedHistory:', extendedHistory);
    console.log('updateIndividualExtendedCharts - timestamps length:', timestamps.length);

    if (timestamps.length === 0) return;

    // VOC Chart
    if (charts.vocChart) {
        const vocData = extendedHistory.voc_ppb || [];
        if (vocData.length > 0) {
            charts.vocChart.data.labels = timestamps;
            charts.vocChart.data.datasets[0].data = vocData;
            safeChartUpdate(charts.vocChart, 'vocChart');
            console.log('Updated VOC chart with', vocData.length, 'data points');
        }
    }

    // NO2 Chart
    if (charts.no2Chart) {
        const no2Data = extendedHistory.no2_ppb || [];
        if (no2Data.length > 0) {
            charts.no2Chart.data.labels = timestamps;
            charts.no2Chart.data.datasets[0].data = no2Data;
            safeChartUpdate(charts.no2Chart, 'no2Chart');
            console.log('Updated NO2 chart with', no2Data.length, 'data points');
        }
    }

    // Speed Chart
    if (charts.speedChart) {
        const speedData = extendedHistory.gps_speed_kmh || [];
        if (speedData.length > 0) {
            charts.speedChart.data.labels = timestamps;
            charts.speedChart.data.datasets[0].data = speedData;
            safeChartUpdate(charts.speedChart, 'speedChart');
            console.log('Updated Speed chart with', speedData.length, 'data points');
        }
    }
}

// ========================
// MAP TOGGLE FUNCTIONALITY  
// ========================
function initializeMapToggle() {
    const toggleMapBtn = document.getElementById('toggleMapView');
    const mapContainer = document.getElementById('mapSelectionContainer');
    const mapToggleIcon = document.getElementById('mapToggleIcon');
    const mapToggleText = document.getElementById('mapToggleText');
    
    if (!toggleMapBtn || !mapContainer) return;
    
    let mapVisible = false;
    
    toggleMapBtn.addEventListener('click', function() {
        mapVisible = !mapVisible;
        
        if (mapVisible) {
            mapContainer.style.display = 'block';
            mapToggleIcon.className = 'fas fa-times';
            mapToggleText.textContent = 'Hide Map';
            
            // Initialize map when first shown
            setTimeout(() => {
                if (deviceSelectMap) {
                    deviceSelectMap.invalidateSize();
                } else {
                    initializeDeviceSelectionMap();
                }
            }, 100);
        } else {
            mapContainer.style.display = 'none';
            mapToggleIcon.className = 'fas fa-map';
            mapToggleText.textContent = 'Show Map';
        }
    });
}

function initializeDeviceQuickActions() {
    const refreshBtn = document.getElementById('refreshDeviceList');
    const autoSelectBtn = document.getElementById('autoSelectDevice');
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            window.location.reload();
        });
    }
    
    if (autoSelectBtn) {
        autoSelectBtn.addEventListener('click', function() {
            const deviceSelect = document.getElementById('deviceSelect');
            if (deviceSelect && deviceSelect.options.length > 1) {
                deviceSelect.selectedIndex = 1;
                deviceSelect.dispatchEvent(new Event('change'));
                createAlert('Auto-selected first available device', 'success');
            } else {
                createAlert('No devices available for auto-selection', 'warning');
            }
        });
    }
}




// ========================
// WEBSOCKET HANDLING (Enhanced)
// ========================

// (Replaced by the unified initializeWebSocket above)

function joinDeviceRoom(deviceId) {
    if (currentDeviceRoom && socket) {
        socket.emit('leave', { device_id: currentDeviceRoom });
    }
    
    if (socket && deviceId) {
        socket.emit('join', { device_id: deviceId });
        currentDeviceRoom = deviceId;
    }
}

function updateConnectionStatus(isOnline) {
    const connectionStatus = document.getElementById('connectionStatus') || document.getElementById('deviceStatus');
    const navConnectionStatus = document.getElementById('navConnectionStatus');
    const connectionDot = document.getElementById('connectionDot');
    
    if (connectionStatus) {
        connectionStatus.textContent = isOnline ? 'ONLINE' : 'OFFLINE';
        connectionStatus.className = `badge ${isOnline ? 'bg-success' : 'bg-danger'}`;
    }
    
    if (navConnectionStatus) {
        navConnectionStatus.textContent = isOnline ? 'Online' : 'Offline';
    }
    
    if (connectionDot) {
        connectionDot.className = `status-dot ${isOnline ? 'online' : ''}`;
    }
}

// ========================
// THRESHOLD MANAGEMENT (Your existing enhanced)
// ========================

function checkThresholds(data) {
    if (!data.sensor || !data.status || !data.status.thresholds) return;
    
    const alerts = [];
    const sensor = data.sensor;
    const thresholds = data.status.thresholds;
    
    const params = [
        { key: 'pm1', label: 'PM1', value: sensor.pm1 },
        { key: 'pm2.5', label: 'PM2.5', value: sensor.pm2_5 },
        { key: 'pm4', label: 'PM4', value: sensor.pm4 },
        { key: 'pm10', label: 'PM10', value: sensor.pm10 },
        { key: 'tsp', label: 'TSP', value: sensor.tsp }
    ];
    
    params.forEach(param => {
        const threshold = thresholds[param.key];
        if (param.value && threshold && param.value > threshold) {
            alerts.push({
                parameter: param.label,
                current: param.value.toFixed(2),
                threshold: threshold,
                severity: param.value > threshold * 1.5 ? 'high' : 'medium'
            });
        }
    });
    
    displayAlerts(alerts);
    
    // Update alert count in quick stats
    const alertCount = document.getElementById('alertCount');
    const alertsBadge = document.getElementById('alertsBadge');
    
    if (alertCount) alertCount.textContent = alerts.length;
    if (alertsBadge) alertsBadge.textContent = alerts.length;
}

function initializeMapToggle() {
    const toggleMapBtn = document.getElementById('toggleMapView');
    const mapContainer = document.getElementById('mapSelectionContainer');
    const mapToggleIcon = document.getElementById('mapToggleIcon');
    const mapToggleText = document.getElementById('mapToggleText');
    
    if (!toggleMapBtn || !mapContainer) return;
    
    let mapVisible = false;
    
    toggleMapBtn.addEventListener('click', function() {
        mapVisible = !mapVisible;
        
        if (mapVisible) {
            mapContainer.style.display = 'block';
            mapToggleIcon.className = 'fas fa-times';
            mapToggleText.textContent = 'Hide Map';
            
            // Initialize map when first shown
            setTimeout(() => {
                if (deviceSelectMap) {
                    deviceSelectMap.invalidateSize();
                } else {
                    initializeDeviceSelectionMap();
                }
            }, 100);
        } else {
            mapContainer.style.display = 'none';
            mapToggleIcon.className = 'fas fa-map';
            mapToggleText.textContent = 'Show Map';
        }
    });
}

// Add auto-select and refresh functionality
function initializeDeviceQuickActions() {
    const refreshBtn = document.getElementById('refreshDeviceList');
    const autoSelectBtn = document.getElementById('autoSelectDevice');
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            // Reload the page to refresh device list
            window.location.reload();
        });
    }
    
    if (autoSelectBtn) {
        autoSelectBtn.addEventListener('click', function() {
            const deviceSelect = document.getElementById('deviceSelect');
            if (deviceSelect && deviceSelect.options.length > 1) {
                // Select the first available device
                deviceSelect.selectedIndex = 1;
                deviceSelect.dispatchEvent(new Event('change'));
                createAlert('Auto-selected first available device', 'success');
            } else {
                createAlert('No devices available for auto-selection', 'warning');
            }
        });
    }
}

function displayAlerts(alerts) {
    const alertsContainer = document.getElementById('alertsContainer');
    const thresholdAlertsCard = document.getElementById('thresholdAlerts');
    
    if (!alertsContainer || !thresholdAlertsCard) return;
    
    if (alerts.length === 0) {
        thresholdAlertsCard.style.display = 'none';
        return;
    }
    
    thresholdAlertsCard.style.display = 'block';
    alertsContainer.innerHTML = alerts.map(alert => {
        const badgeClass = alert.severity === 'high' ? 'bg-danger' : 'bg-warning';
        const alertClass = alert.severity === 'high' ? 'danger' : 'warning';
        
        return `
            <div class="alert alert-${alertClass} alert-dismissible fade show mb-2" role="alert">
                <div class="d-flex align-items-center">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                    <div class="flex-grow-1">
                        <strong>${alert.parameter}</strong> exceeds threshold!
                        <br>
                        <small>
                            Current: <span class="badge ${badgeClass}">${alert.current} μg/m³</span>
                            Threshold: <span class="badge bg-secondary">${alert.threshold} μg/m³</span>
                        </small>
                    </div>
                </div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
    }).join('');
}

function calculateThresholdFrequency(data) {
    if (!data.history || !data.status || !data.status.thresholds || !charts.thresholdFrequencyChart) return;
    
    const thresholds = data.status.thresholds;
    const pmTypes = ['pm1', 'pm2_5', 'pm4', 'pm10', 'tsp'];
    const thresholdKeys = ['pm1', 'pm2.5', 'pm4', 'pm10', 'tsp'];
    
    const frequencies = pmTypes.map((type, index) => {
        const values = data.history[type] || [];
        const threshold = thresholds[thresholdKeys[index]];
        if (!threshold || values.length === 0) return 0;
        
        const exceedCount = values.filter(val => val && val > threshold).length;
        return (exceedCount / values.length) * 100;
    });
    
    charts.thresholdFrequencyChart.data.datasets[0].data = frequencies;
    applyRigidAxisForBar('thresholdFrequencyChart', charts.thresholdFrequencyChart, frequencies, 0, 100);
    safeChartUpdate(charts.thresholdFrequencyChart, 'thresholdFrequencyChart');
}

// ========================
// RELAY CONTROL (Enhanced)
// ========================

function setupRelayControls() {
    const modeRadios = document.querySelectorAll('input[name="relayMode"]');
    const manualControls = document.getElementById('manualControls');
    const autoControls = document.getElementById('autoControls');
    
    if (!modeRadios.length) return;
    
    modeRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            if (this.value === 'manual') {
                if (manualControls) manualControls.style.display = 'block';
                if (autoControls) autoControls.style.display = 'none';
            } else {
                if (manualControls) manualControls.style.display = 'none';
                if (autoControls) autoControls.style.display = 'block';
            }
        });
    });
}

function controlRelay(state) {
    if (!currentDeviceId) {
        createAlert('Please select a device first', 'warning');
        return;
    }
    
    fetch('/api/relay_control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            device_id: currentDeviceId,
            state: state
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            createAlert(`Relay ${state} command sent successfully`, 'success');
            // Update relay status immediately
            const relayState = document.getElementById('relayState');
            if (relayState) {
                relayState.textContent = state;
                relayState.className = `badge ${state === 'ON' ? 'bg-success' : 'bg-secondary'}`;
            }
        } else {
            createAlert(data.message || 'Failed to control relay', 'danger');
        }
    })
    .catch(error => {
        console.error('Error controlling relay:', error);
        createAlert('Failed to send relay command', 'danger');
    });
}

function updateAutoMode() {
    const threshold = document.getElementById('autoThreshold').value;
    
    if (!currentDeviceId) {
        createAlert('Please select a device first', 'warning');
        return;
    }
    
    fetch('/api/relay_control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            device_id: currentDeviceId,
            mode: 'auto',
            auto_threshold: parseFloat(threshold)
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            createAlert('Auto mode threshold updated successfully', 'success');
        } else {
            createAlert(data.message || 'Failed to update auto mode', 'danger');
        }
    })
    .catch(error => {
        console.error('Error updating auto mode:', error);
        createAlert('Failed to update auto mode', 'danger');
    });
}

// ========================
// DEEP ANALYTICS FUNCTIONS (New)
// ========================

function updateParameterTrendChart(parameter) {
    if (!parameter || !charts.paramTrendChart) return;
    
    const chart = charts.paramTrendChart;
    chart.data.datasets[0].label = getParameterLabel(parameter);
    chart.data.datasets[0].borderColor = colorScheme[parameter] || 'rgba(75, 192, 192, 0.8)';
    chart.data.datasets[0].backgroundColor = (colorScheme[parameter] || 'rgba(75, 192, 192, 0.8)').replace('0.8', '0.2');
    chart.update();
}

function updateHistogramChart(parameter) {
    if (!parameter || !charts.histogramChart) return;
    
    const chart = charts.histogramChart;
    chart.data.datasets[0].label = `${getParameterLabel(parameter)} Distribution`;
    chart.data.datasets[0].backgroundColor = colorScheme[parameter] || 'rgba(75, 192, 192, 0.6)';
    chart.update();
}

function updateCorrelationChart() {
    const paramX = document.getElementById('corrParamX').value;
    const paramY = document.getElementById('corrParamY').value;
    
    if (!paramX || !paramY || !charts.correlationScatter) return;
    
    charts.correlationScatter.options.scales.x.title.text = getParameterLabel(paramX);
    charts.correlationScatter.options.scales.y.title.text = getParameterLabel(paramY);
    charts.correlationScatter.update();
}

function getParameterLabel(param) {
    const labels = {
        pm1: 'PM1 (μg/m³)',
        pm2_5: 'PM2.5 (μg/m³)',
        pm4: 'PM4 (μg/m³)',
        pm10: 'PM10 (μg/m³)',
        tsp: 'TSP (μg/m³)',
        temperature_c: 'Temperature (°C)',
        humidity_percent: 'Humidity (%)',
        pressure_hpa: 'Pressure (hPa)',
        voc_ppb: 'VOC (ppb)',
        no2_ppb: 'NO₂ (ppb)',
        gps_speed_kmh: 'Speed (km/h)',
        cloud_cover_percent: 'Cloud Cover (%)',
        voc: 'VOC (ppb)',
        no2: 'NO₂ (ppb)',
        speed: 'Speed (km/h)',
        cloud: 'Cloud Cover (%)'
    };
    return labels[param] || param;
}

// ========================
// CHART CONTROLS (New)
// ========================

function toggleChartType(type) {
    if (charts.timeChart) {
        charts.timeChart.config.type = type;
        charts.timeChart.update();
        createAlert(`Chart type changed to ${type}`, 'info');
    }
}

function toggleChartFill() {
    if (charts.timeChart) {
        charts.timeChart.data.datasets.forEach(dataset => {
            dataset.fill = !dataset.fill;
        });
        charts.timeChart.update();
        createAlert('Chart fill toggled', 'info');
    }
}

function resetZoom() {
    Object.values(charts).forEach(chart => {
        if (chart && chart.resetZoom) {
            chart.resetZoom();
        }
    });
    createAlert('Chart zoom reset', 'info');
}

function refreshData() {
    if (currentDeviceId) {
        fetchData(24);
        createAlert('Data refreshed', 'success');
    } else {
        createAlert('Please select a device first', 'warning');
    }
}

// ========================
// REAL-TIME MODE (Enhanced from your existing)
// ========================

// Real-time mode removed: app always runs in real-time via websockets

// ========================
// THRESHOLD SETTINGS (Enhanced)
// ========================

function updateThresholdForm(thresholds) {
    const thresholdSettings = document.getElementById('thresholdSettings');
    if (!thresholdSettings || !thresholds) return;
    
    const params = [
        { key: 'pm1', label: 'PM1' },
        { key: 'pm2.5', label: 'PM2.5' },
        { key: 'pm4', label: 'PM4' },
        { key: 'pm10', label: 'PM10' },
        { key: 'tsp', label: 'TSP' }
    ];
    
    thresholdSettings.innerHTML = params.map(param => `
        <div class="mb-3">
            <label for="threshold_${param.key}" class="form-label">${param.label} Threshold (μg/m³)</label>
            <div class="input-group">
                <input type="number" class="form-control" id="threshold_${param.key}" 
                       value="${thresholds[param.key] || 0}" min="0" step="0.1">
                <span class="input-group-text">μg/m³</span>
            </div>
        </div>
    `).join('') + `
        <div class="d-grid">
            <button class="btn btn-primary" onclick="updateThresholds()">
                <i class="bi bi-check2 me-2"></i>Update Thresholds
            </button>
        </div>
    `;
}

function updateThresholds() {
    if (!currentDeviceId) {
        createAlert('Please select a device first', 'warning');
        return;
    }
    
    const thresholds = {
        pm1: parseFloat(document.getElementById('threshold_pm1').value),
        'pm2.5': parseFloat(document.getElementById('threshold_pm2.5').value),
        pm4: parseFloat(document.getElementById('threshold_pm4').value),
        pm10: parseFloat(document.getElementById('threshold_pm10').value),
        tsp: parseFloat(document.getElementById('threshold_tsp').value)
    };
    
    fetch(`/api/update_thresholds?deviceid=${encodeURIComponent(currentDeviceId)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(thresholds)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            createAlert('Thresholds updated successfully', 'success');
            fetchData(0.25); // Refresh current data
        } else {
            createAlert(data.message || 'Failed to update thresholds', 'danger');
        }
    })
    .catch(error => {
        console.error('Error updating thresholds:', error);
        createAlert('Failed to update thresholds', 'danger');
    });
}

// ========================
// DATA EXPORT (Enhanced from your existing)
// ========================

// ========================
// MISSING HELPER FUNCTIONS
// ========================
function getParameterLabel(param) {
    const labels = {
        'pm1': 'PM1 (μg/m³)',
        'pm2_5': 'PM2.5 (μg/m³)',
        'pm4': 'PM4 (μg/m³)',
        'pm10': 'PM10 (μg/m³)',
        'tsp': 'TSP (μg/m³)',
        'temperature_c': 'Temperature (°C)',
        'humidity_percent': 'Humidity (%)',
        'pressure_hpa': 'Pressure (hPa)',
        'voc_ppb': 'VOC (ppb)',
        'no2_ppb': 'NO₂ (ppb)',
        'gps_speed_kmh': 'Speed (km/h)',
        'cloud_cover_percent': 'Cloud Cover (%)'
    };
    return labels[param] || param;
}



function updateDeviceLocation(lat, lon) {
    if (map && deviceMarker) {
        deviceMarker.setLatLng([lat, lon]);
        map.setView([lat, lon], map.getZoom());
    }
}

// Add missing functions for other charts
function checkThresholds(data) {
    // Basic threshold checking logic
    if (!data.sensor || !data.status || !data.status.thresholds) return;
    
    const sensor = data.sensor;
    const thresholds = data.status.thresholds;
    
    const exceedances = [];
    if (sensor.pm1 > thresholds.pm1) exceedances.push('PM1');
    if (sensor.pm2_5 > thresholds['pm2.5']) exceedances.push('PM2.5');
    if (sensor.pm4 > thresholds.pm4) exceedances.push('PM4');
    if (sensor.pm10 > thresholds.pm10) exceedances.push('PM10');
    if (sensor.tsp > thresholds.tsp) exceedances.push('TSP');
    
    if (exceedances.length > 0) {
        console.log('Threshold exceedances:', exceedances);
    }
}

function calculateThresholdFrequency(data) {
    // Calculate threshold frequency for display
    if (!data.history || !data.status || !data.status.thresholds) return;
    
    const history = data.history;
    const thresholds = data.status.thresholds;
    const totalReadings = history.timestamps ? history.timestamps.length : 0;
    
    if (totalReadings === 0) return;
    
    const frequencies = [0, 0, 0, 0, 0];
    const params = ['pm1', 'pm2_5', 'pm4', 'pm10', 'tsp'];
    const thresholdKeys = ['pm1', 'pm2.5', 'pm4', 'pm10', 'tsp'];
    
    for (let i = 0; i < totalReadings; i++) {
        params.forEach((param, index) => {
            const value = history[param] && history[param][i];
            const threshold = thresholds[thresholdKeys[index]];
            if (value && threshold && value > threshold) {
                frequencies[index]++;
            }
        });
    }
    
    // Update frequency chart
    if (charts.thresholdFrequencyChart) {
        const percentages = frequencies.map(freq => (freq / totalReadings) * 100);
        charts.thresholdFrequencyChart.data.datasets[0].data = percentages;
        safeChartUpdate(charts.thresholdFrequencyChart, 'thresholdFrequencyChart');
    }
}

function updateQuickStats(data) {
    if (!data || !data.sensor) {
        // Set default values if no data
        document.getElementById('onlineDevices').textContent = '0';
        document.getElementById('avgPM25').textContent = '--';
        document.getElementById('maxTemp').textContent = '--°C';
        return;
    }
    
    // Update online devices count
    const onlineDevices = document.getElementById('onlineDevices');
    if (onlineDevices) {
        onlineDevices.textContent = currentDeviceId ? '1' : '0';
    }
    
    // Update average PM2.5
    const avgPM25 = document.getElementById('avgPM25');
    if (avgPM25 && data.sensor.pm2_5 !== undefined) {
        avgPM25.textContent = `${data.sensor.pm2_5.toFixed(1)}`;
    }
    
    // Update max temperature
    const maxTemp = document.getElementById('maxTemp');
    if (maxTemp && data.extended && data.extended.temperature_c !== undefined) {
        maxTemp.textContent = `${data.extended.temperature_c.toFixed(1)}°C`;
    } else if (maxTemp) {
        maxTemp.textContent = '--°C';
    }
}

function normalizeIncomingData(data) {
    if (!data) return null;

    const normalized = JSON.parse(JSON.stringify(data));

    // Map extended data fields - CRITICAL SECTION
    if (data.extended) {
        normalized.extended = {
            temperature_c: data.extended.temperature_c,
            humidity_percent: data.extended.humidity_percent,
            pressure_hpa: data.extended.pressure_hpa,
            voc_ppb: data.extended.voc_ppb,
            no2_ppb: data.extended.no2_ppb,
            cloud_cover_percent: data.extended.cloud_cover_percent,
            lux: data.extended.lux,
            uv_index: data.extended.uv_index,
            battery_percent: data.extended.battery_percent,
            pm2_5: data.extended.pm2_5, // Add PM2.5 for AQI calculation
            timestamp: data.extended.timestamp
        };
        console.log('Normalized extended data:', normalized.extended);
    }

    // Ensure sensor data exists
    if (!normalized.sensor && data.sensor) {
        normalized.sensor = data.sensor;
    }

    return normalized;
}




function exportData() {
    if (!currentDeviceId) {
        createAlert('Please select a device first', 'warning');
        return;
    }
    
    const startDate = document.getElementById('start-date').value;
    const endDate = document.getElementById('end-date').value;
    
    if (!startDate || !endDate) {
        createAlert('Please select both start and end dates', 'warning');
        return;
    }
    
    const url = `/api/export_csv?deviceid=${currentDeviceId}&start_date=${startDate}&end_date=${endDate}`;
    window.open(url, '_blank');
    createAlert('Export started - check your downloads', 'success');
}

function setDefaultDates() {
    const today = new Date().toISOString().split('T')[0];
    const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    
    const startDate = document.getElementById('start-date');
    const endDate = document.getElementById('end-date');
    
    if (startDate) startDate.value = weekAgo;
    if (endDate) endDate.value = today;
}

// ========================
// UTILITY FUNCTIONS (Enhanced from your existing)
// ========================

function updateActiveTimeButton(hours) {
    document.querySelectorAll('.time-range-buttons .btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    const buttonText = hours === 0.25 ? '15m' : hours === 3 ? '3h' : hours === 6 ? '6h' : '24h';
    const activeButton = Array.from(document.querySelectorAll('.time-range-buttons .btn'))
        .find(btn => btn.getAttribute('data-time') === buttonText);
    
    if (activeButton) {
        activeButton.classList.add('active');
    }
}

// Show loading indicator (your existing enhanced)
function showLoading() {
    const loadingIndicator = document.createElement('div');
    loadingIndicator.className = 'loading-indicator';
    loadingIndicator.innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                <span class="visually-hidden">Loading...</span>
            </div>
            <div class="mt-3">
                <h5>Loading data...</h5>
                <div class="progress" style="width: 200px;">
                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                         style="width: 100%"></div>
                </div>
            </div>
        </div>
    `;
    
    // Center the loading indicator
    loadingIndicator.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0,0,0,0.5);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 9999;
        backdrop-filter: blur(2px);
    `;
    
    document.body.appendChild(loadingIndicator);
    return loadingIndicator;
}

// Enhanced alert system with toast notifications
function createAlert(message, type = 'info') {
    // Create Bootstrap toast
    const toastContainer = document.querySelector('.toast-container') || createToastContainer();
    
    const toastId = 'toast-' + Date.now();
    const iconMap = {
        success: 'bi-check-circle',
        danger: 'bi-x-circle',
        warning: 'bi-exclamation-triangle',
        info: 'bi-info-circle'
    };
    
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.id = toastId;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="toast-header">
            <i class="bi ${iconMap[type]} me-2 text-${type}"></i>
            <strong class="me-auto">Environmental Monitor</strong>
            <small>${new Date().toLocaleTimeString()}</small>
            <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
        </div>
        <div class="toast-body">
            ${message}
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    // Initialize and show toast
    const bsToast = new bootstrap.Toast(toast, { delay: 5000 });
    bsToast.show();
    
    // Remove toast element after it's hidden
    toast.addEventListener('hidden.bs.toast', function() {
        toast.remove();
    });
}

function createToastContainer() {
    const container = document.createElement('div');
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '11';
    document.body.appendChild(container);
    return container;
}

// ========================
// INITIALIZATION CALLS
// ========================

// Initialize charts when DOM is loaded (your existing)
document.addEventListener('DOMContentLoaded', function() {
    // Charts are already initialized in the main DOMContentLoaded listener above
});

// For backward compatibility with your existing code
window.timeChart = charts.timeChart;
window.thresholdChart = charts.thresholdChart;
window.thresholdFrequencyChart = charts.thresholdFrequencyChart;

// Debug function to test device selection and tab switching
window.testDeviceSelection = function() {
    console.log('=== TESTING DEVICE SELECTION ===');

    const deviceSelect = document.getElementById('deviceSelect');
    console.log('Device select element:', deviceSelect);
    console.log('Device select options:', deviceSelect ? deviceSelect.options.length : 'N/A');
    console.log('Currently selected index:', deviceSelect ? deviceSelect.selectedIndex : 'N/A');
    console.log('Currently selected value:', deviceSelect ? deviceSelect.value : 'N/A');

    if (deviceSelect && deviceSelect.options.length > 1) {
        console.log('=== TESTING MANUAL DEVICE SELECTION ===');
        // Select the first device (skip the "Select a device..." option)
        deviceSelect.selectedIndex = 1;
        console.log('Manually selected device index:', deviceSelect.selectedIndex);
        console.log('Selected device value:', deviceSelect.value);

        // Get the selected option attributes
        const selectedOption = deviceSelect.options[deviceSelect.selectedIndex];
        console.log('Selected option data-type:', selectedOption.getAttribute('data-type'));
        console.log('Selected option data-relay:', selectedOption.getAttribute('data-relay'));

        // Trigger the change event
        console.log('Triggering change event...');
        deviceSelect.dispatchEvent(new Event('change'));
    } else {
        console.log('No devices available for selection');
    }

    console.log('=== DEVICE SELECTION TEST COMPLETE ===');
};

// Debug function to test extended data display
window.testExtendedData = function() {
    console.log('=== TESTING ENVIRONMENTAL CARD ELEMENTS ===');

    // Test if environmental cards exist
    const cardIds = ['currentTemp', 'currentHumidity', 'currentPressure', 'currentVOC', 'currentLux', 'currentUV'];
    const results = {};

    cardIds.forEach(id => {
        const element = document.getElementById(id);
        results[id] = {
            exists: !!element,
            visible: element ? element.offsetParent !== null : false,
            currentText: element ? element.textContent : 'N/A'
        };
        console.log(`${id}:`, results[id]);
    });

    // Test direct update
    console.log('=== TESTING DIRECT CARD UPDATES ===');
    const testData = {
        temperature_c: 24.5,
        humidity_percent: 65.2,
        pressure_hpa: 1013.2,
        voc_ppb: 150,
        lux: 350,
        uv_index: 3.5
    };

    // Test updateExtendedData function directly
    console.log('=== TESTING updateExtendedData FUNCTION ===');
    updateExtendedData(testData);

    console.log('=== TEST COMPLETE ===');
    createAlert('Environmental card test completed - check console', 'info');
};

// Debug function to test API data flow
window.testAPIData = function() {
    console.log('=== TESTING API DATA FLOW ===');

    if (!currentDeviceId) {
        console.log('❌ No device selected');
        return;
    }

    console.log('📡 Fetching data from API...');
    fetch(`/api/data?hours=1&deviceid=${currentDeviceId}`)
        .then(response => response.json())
        .then(data => {
            console.log('📊 API Response:', data);
            console.log('🔍 Extended data in response:', data.extended);

            if (data.extended) {
                console.log('✅ Calling updateExtendedData with API data...');
                updateExtendedData(data.extended);
            } else {
                console.log('❌ No extended data in API response');
            }
        })
        .catch(error => {
            console.error('❌ API fetch error:', error);
        });
};

// Debug function to test chart updates
window.testChartUpdates = function() {
    console.log('=== TESTING CHART UPDATES ===');

    // Check if charts exist
    console.log('tempHumidityChart exists:', !!charts.tempHumidityChart);
    console.log('pressureAirQualityChart exists:', !!charts.pressureAirQualityChart);

    // Create test data
    const testData = {
        extended: {
            temperature_c: 25.0,
            humidity_percent: 60.0,
            pressure_hpa: 1015.0,
            voc_ppb: 150
        },
        history: {
            extended: {
                timestamps: [new Date(), new Date(Date.now() - 3600000)],
                temperature_c: [25.0, 24.0],
                humidity_percent: [60.0, 65.0],
                pressure_hpa: [1015.0, 1010.0],
                voc_ppb: [150, 140]
            }
        }
    };

    console.log('Calling updateExtendedCharts with test data...');
    updateExtendedCharts(testData);

    console.log('=== CHART UPDATE TEST COMPLETE ===');
    createAlert('Chart update test completed - check console', 'info');
};

// Debug function to test data fetching
window.testDataFetching = function() {
    console.log('=== TESTING DATA FETCHING ===');

    // Check current device
    console.log('Current device ID:', currentDeviceId);
    console.log('Current device type:', currentDeviceType);

    if (!currentDeviceId) {
        console.log('No device selected - cannot test data fetching');
        return;
    }

    // Manually fetch data
    console.log('Manually calling fetchData(24)...');
    fetchData(24);

    console.log('=== DATA FETCHING TEST COMPLETE ===');
};

// Debug function to test WebSocket
window.testWebSocket = function() {
    console.log('=== TESTING WEBSOCKET ===');

    console.log('Socket exists:', !!socket);
    console.log('Socket connected:', socket ? socket.connected : false);
    console.log('Current device room:', currentDeviceRoom);

    if (socket && socket.connected) {
        console.log('WebSocket is connected');
    } else {
        console.log('WebSocket is NOT connected');
    }

    console.log('=== WEBSOCKET TEST COMPLETE ===');
};
