/**
 * Climate Intelligence Heatwave Monitoring System
 * Vanilla JavaScript Frontend Controller (Chart.js + Leaflet.js + SSE)
 */

// ---------------------------------------------------------------------
// 1. Central Configuration
// ---------------------------------------------------------------------
const CONFIG = {
  API_BASE: 'http://localhost:8000',
  ENDPOINTS: {
    LIVE_STATUS: '/live-status',
    TREND: (regionId, days) => `/trend/${regionId}?days=${days}`,
    FORECAST: (regionId) => `/forecast/${regionId}`,
    ALERTS: (active = true) => `/alerts?active=${active}`,
    STATIONS: '/stations',
    STREAM: '/stream',
    RESOLVE_ALERT: (id) => `/alerts/${id}/resolve`
  },
  POLL_INTERVAL_MS: 5000,
  RECONNECT_DELAY_MS: 4000,
  MAPBOX_TOKEN: '' // Optional: provide a Mapbox public access token, or leave empty for free CartoDB dark tiles
};

// ---------------------------------------------------------------------
// 2. Reactive State Store
// ---------------------------------------------------------------------
const state = {
  selectedRegion: 'ALL',
  historicalDays: 30,
  stations: [],
  alerts: [],
  trends: [],
  forecasts: [],
  sortColumn: 'temperature_c',
  sortOrder: 'desc',
  searchQuery: '',
  isConnected: false,
  eventSource: null,
  pollTimer: null,
  theme: localStorage.getItem('heatwave_theme') || 'dark',
  cachedKpis: {
    hottestVal: '',
    alertsVal: null,
    avgTempVal: '',
    stationsVal: ''
  }
};

// UI Element References
const elements = {
  themeToggleBtn: document.getElementById('themeToggleBtn'),
  themeIcon: document.getElementById('themeIcon'),
  connectionPill: document.getElementById('connectionPill'),
  connectionText: document.getElementById('connectionText'),
  lastSyncTime: document.getElementById('lastSyncTime'),
  regionSelect: document.getElementById('regionSelect'),
  trendDaysSelect: document.getElementById('trendDaysSelect'),
  stationSearch: document.getElementById('stationSearch'),
  
  // KPI Elements
  kpiHottest: document.getElementById('kpiHottest'),
  kpiHottestVal: document.getElementById('kpiHottestVal'),
  kpiHottestSub: document.getElementById('kpiHottestSub'),
  
  kpiAlerts: document.getElementById('kpiAlerts'),
  kpiAlertsVal: document.getElementById('kpiAlertsVal'),
  kpiAlertsSub: document.getElementById('kpiAlertsSub'),
  
  kpiAvgTemp: document.getElementById('kpiAvgTemp'),
  kpiAvgTempVal: document.getElementById('kpiAvgTempVal'),
  kpiAvgTempSub: document.getElementById('kpiAvgTempSub'),
  
  kpiStations: document.getElementById('kpiStations'),
  kpiStationsVal: document.getElementById('kpiStationsVal'),
  kpiStationsSub: document.getElementById('kpiStationsSub'),
  
  // Panels
  alertsContainer: document.getElementById('alertsContainer'),
  alertsCountBadge: document.getElementById('alertsCountBadge'),
  stationTableBody: document.getElementById('stationTableBody'),
  chartHeading: document.getElementById('chartHeading'),
  chartRegionBadge: document.getElementById('chartRegionBadge'),
  toastContainer: document.getElementById('toastContainer')
};

// Map & Chart Singletons
let leafletMap = null;
let tileLayer = null;
const markersMap = new Map(); // station_id -> L.circleMarker
let trendChartInstance = null;

// Risk Level Styles
const RISK_COLORS = {
  'Normal': '#10b981',
  'Watch': '#f59e0b',
  'Warning': '#f97316',
  'Severe': '#ef4444'
};

// ---------------------------------------------------------------------
// 3. Theme Manager
// ---------------------------------------------------------------------
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  elements.themeIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
  localStorage.setItem('heatwave_theme', theme);
  state.theme = theme;

  // Refresh Chart.js text colors
  if (trendChartInstance) {
    const textColor = theme === 'dark' ? '#94a3b8' : '#475569';
    const gridColor = theme === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)';
    trendChartInstance.options.scales.x.ticks.color = textColor;
    trendChartInstance.options.scales.y.ticks.color = textColor;
    trendChartInstance.options.scales.x.grid.color = gridColor;
    trendChartInstance.options.scales.y.grid.color = gridColor;
    trendChartInstance.update();
  }
}

elements.themeToggleBtn.addEventListener('click', () => {
  const nextTheme = state.theme === 'dark' ? 'light' : 'dark';
  applyTheme(nextTheme);
});

// ---------------------------------------------------------------------
// 4. Geospatial Map (Leaflet.js)
// ---------------------------------------------------------------------
function initLeafletMap() {
  // Center of India
  leafletMap = L.map('stationMap', {
    zoomControl: true,
    attributionControl: false
  }).setView([22.5937, 78.9629], 5);

  if (CONFIG.MAPBOX_TOKEN) {
    // Mapbox Dark-v11 High Definition Tiles
    const mapboxUrl = `https://api.mapbox.com/styles/v1/mapbox/dark-v11/tiles/{z}/{x}/{y}?access_token=${CONFIG.MAPBOX_TOKEN}`;
    tileLayer = L.tileLayer(mapboxUrl, {
      maxZoom: 18,
      tileSize: 512,
      zoomOffset: -1,
      attribution: '© Mapbox'
    }).addTo(leafletMap);
  } else {
    // Open-source dark mode CartoDB basemap tiles (no API token required)
    const cartoDarkUrl = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
    tileLayer = L.tileLayer(cartoDarkUrl, {
      maxZoom: 19,
      subdomains: 'abcd',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
    }).addTo(leafletMap);
  }
}

function updateMapMarkers(stations) {
  if (!leafletMap) return;

  const filtered = state.selectedRegion === 'ALL' 
    ? stations 
    : stations.filter(s => s.region_name === state.selectedRegion);

  // Track active IDs to remove decommissioned ones
  const activeIds = new Set(filtered.map(s => s.station_id));

  // Remove markers not in current filter
  markersMap.forEach((marker, id) => {
    if (!activeIds.has(id)) {
      leafletMap.removeLayer(marker);
      markersMap.delete(id);
    }
  });

  // Add or update markers in-place
  filtered.forEach(station => {
    const lat = parseFloat(station.latitude);
    const lon = parseFloat(station.longitude);
    if (isNaN(lat) || isNaN(lon)) return;

    const risk = station.risk_level || 'Normal';
    const color = RISK_COLORS[risk] || RISK_COLORS['Normal'];
    const temp = station.temperature_c != null ? Number(station.temperature_c).toFixed(1) : '--';
    const hi = station.heat_index_c != null ? Number(station.heat_index_c).toFixed(1) : '--';
    const hum = station.humidity_pct != null ? Number(station.humidity_pct).toFixed(0) : '--';
    const recorded = station.recorded_at ? new Date(station.recorded_at).toLocaleTimeString() : '--';

    const popupHtml = `
      <div style="font-family: Inter, sans-serif; font-size: 12px; line-height: 1.5; min-width: 160px;">
        <strong style="font-size: 13px; display: block; margin-bottom: 4px;">${escapeHtml(station.station_name)}</strong>
        <div><strong>Region:</strong> ${escapeHtml(station.region_name)}</div>
        <div><strong>Temperature:</strong> <span style="font-weight: 700; color: ${color};">${temp}°C</span></div>
        <div><strong>Heat Index:</strong> ${hi}°C</div>
        <div><strong>Humidity:</strong> ${hum}%</div>
        <div style="margin-top: 4px;"><span style="background:${color}; color:#fff; padding:2px 6px; border-radius:3px; font-weight:700; font-size:10px;">${risk.toUpperCase()}</span></div>
        <div style="font-size: 10px; color: #888; margin-top: 4px;">Recorded: ${recorded}</div>
      </div>
    `;

    if (markersMap.has(station.station_id)) {
      const marker = markersMap.get(station.station_id);
      marker.setLatLng([lat, lon]);
      marker.setStyle({
        color: color,
        fillColor: color,
        fillOpacity: 0.85,
        radius: 8 + (parseFloat(station.temperature_c || 30) - 25) * 0.4
      });
      marker.setPopupContent(popupHtml);
    } else {
      const marker = L.circleMarker([lat, lon], {
        radius: 8 + (parseFloat(station.temperature_c || 30) - 25) * 0.4,
        color: color,
        fillColor: color,
        fillOpacity: 0.85,
        weight: 2
      }).bindPopup(popupHtml).addTo(leafletMap);

      markersMap.set(station.station_id, marker);
    }
  });

  // Adjust zoom to selection if specific region is chosen
  if (state.selectedRegion !== 'ALL' && filtered.length > 0) {
    const group = L.featureGroup(Array.from(markersMap.values()));
    leafletMap.fitBounds(group.getBounds().pad(0.3));
  }
}

// ---------------------------------------------------------------------
// 5. Trend & Forecast Chart (Chart.js)
// ---------------------------------------------------------------------
function initTrendChart() {
  const ctx = document.getElementById('trendChart').getContext('2d');
  const textColor = state.theme === 'dark' ? '#94a3b8' : '#475569';
  const gridColor = state.theme === 'dark' ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)';

  trendChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        {
          label: 'Daily Avg Temp (°C)',
          data: [],
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          fill: true,
          tension: 0.3,
          borderWidth: 2.5,
          pointRadius: 3
        },
        {
          label: '7-Day Moving Avg',
          data: [],
          borderColor: '#8b5cf6',
          borderDash: [4, 4],
          fill: false,
          tension: 0.3,
          borderWidth: 2,
          pointRadius: 0
        },
        {
          label: '7-Day Forecast',
          data: [],
          borderColor: '#ef4444',
          borderDash: [6, 4],
          fill: false,
          tension: 0.2,
          borderWidth: 2.5,
          pointRadius: 4,
          pointBackgroundColor: '#ef4444'
        },
        {
          label: 'Watch (40°C)',
          data: [],
          borderColor: '#f59e0b',
          borderDash: [2, 2],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false
        },
        {
          label: 'Warning (43°C)',
          data: [],
          borderColor: '#f97316',
          borderDash: [5, 5],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false
        },
        {
          label: 'Severe (45°C)',
          data: [],
          borderColor: '#ef4444',
          borderWidth: 2,
          pointRadius: 0,
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          position: 'top',
          labels: {
            color: textColor,
            font: { family: 'Inter', size: 11 },
            boxWidth: 12
          }
        },
        tooltip: {
          backgroundColor: 'rgba(17, 24, 39, 0.95)',
          titleFont: { family: 'Inter', weight: 'bold' },
          bodyFont: { family: 'Inter' },
          padding: 10
        }
      },
      scales: {
        x: {
          ticks: { color: textColor, font: { family: 'Inter', size: 10 } },
          grid: { color: gridColor }
        },
        y: {
          title: { display: true, text: 'Temperature (°C)', color: textColor },
          ticks: { color: textColor, font: { family: 'Inter', size: 10 } },
          grid: { color: gridColor }
        }
      }
    }
  });
}

function updateTrendChart(trends, forecasts) {
  if (!trendChartInstance) return;

  const labels = [];
  const historicalTemps = [];
  const movingAvg = [];
  const forecastTemps = [];

  // Sort chronological
  const sortedTrends = [...trends].sort((a, b) => new Date(a.reading_date) - new Date(b.reading_date));

  sortedTrends.forEach((pt, i) => {
    labels.push(pt.reading_date);
    const avg = parseFloat(pt.avg_temp_c);
    historicalTemps.push(avg);
    forecastTemps.push(null);

    // Compute 7-day rolling moving average
    const windowStart = Math.max(0, i - 6);
    const windowSlice = sortedTrends.slice(windowStart, i + 1);
    const sum = windowSlice.reduce((acc, curr) => acc + parseFloat(curr.avg_temp_c), 0);
    movingAvg.push(roundTo(sum / windowSlice.length, 2));
  });

  // Append Forecast Points
  if (forecasts && forecasts.length > 0) {
    const sortedForecasts = [...forecasts].sort((a, b) => new Date(a.predicted_for) - new Date(b.predicted_for));
    
    // Connect forecast line from last historical point
    if (historicalTemps.length > 0) {
      forecastTemps[historicalTemps.length - 1] = historicalTemps[historicalTemps.length - 1];
    }

    sortedForecasts.forEach(f => {
      labels.push(f.predicted_for);
      historicalTemps.push(null);
      movingAvg.push(null);
      forecastTemps.push(parseFloat(f.predicted_temp_c));
    });
  }

  // Threshold lines across entire X-axis
  const watchLine = labels.map(() => 40.0);
  const warnLine = labels.map(() => 43.0);
  const severeLine = labels.map(() => 45.0);

  trendChartInstance.data.labels = labels;
  trendChartInstance.data.datasets[0].data = historicalTemps;
  trendChartInstance.data.datasets[1].data = movingAvg;
  trendChartInstance.data.datasets[2].data = forecastTemps;
  trendChartInstance.data.datasets[3].data = watchLine;
  trendChartInstance.data.datasets[4].data = warnLine;
  trendChartInstance.data.datasets[5].data = severeLine;

  trendChartInstance.update('none'); // Update without animation flicker
}

// ---------------------------------------------------------------------
// 6. KPI Card Renderers with Value Change Flash
// ---------------------------------------------------------------------
function updateKpiWithFlash(element, valueContainer, newVal, cacheKey) {
  if (state.cachedKpis[cacheKey] !== newVal) {
    valueContainer.textContent = newVal;
    state.cachedKpis[cacheKey] = newVal;
    element.classList.remove('card-flash');
    void element.offsetWidth; // Trigger CSS reflow
    element.classList.add('card-flash');
  }
}

function updateKpis(stations, alerts) {
  const filtered = state.selectedRegion === 'ALL'
    ? stations
    : stations.filter(s => s.region_name === state.selectedRegion);

  if (filtered.length === 0) {
    elements.kpiHottestVal.textContent = '--';
    elements.kpiAvgTempVal.textContent = '-- °C';
    elements.kpiStationsVal.textContent = '0 / 0';
    return;
  }

  // 1. Hottest Region & Peak Temp
  let hottest = filtered[0];
  let tempSum = 0;
  let validTempCount = 0;

  filtered.forEach(s => {
    const t = parseFloat(s.temperature_c);
    if (!isNaN(t)) {
      tempSum += t;
      validTempCount++;
      if (t > parseFloat(hottest.temperature_c || -99)) {
        hottest = s;
      }
    }
  });

  const hottestValStr = `${Number(hottest.temperature_c).toFixed(1)}°C`;
  updateKpiWithFlash(elements.kpiHottest, elements.kpiHottestVal, hottestValStr, 'hottestVal');
  elements.kpiHottestSub.textContent = `${hottest.region_name} (${hottest.station_name})`;

  // 2. Active Alerts Count
  const filteredAlerts = state.selectedRegion === 'ALL'
    ? alerts
    : alerts.filter(a => a.region_name === state.selectedRegion);
  const alertsCount = filteredAlerts.length;
  updateKpiWithFlash(elements.kpiAlerts, elements.kpiAlertsVal, alertsCount.toString(), 'alertsVal');
  elements.kpiAlertsSub.textContent = alertsCount > 0 ? `${alertsCount} require field monitoring` : 'All regional zones nominal';

  // 3. Network Avg Temperature
  const avgTemp = validTempCount > 0 ? (tempSum / validTempCount).toFixed(1) : '--';
  updateKpiWithFlash(elements.kpiAvgTemp, elements.kpiAvgTempVal, `${avgTemp}°C`, 'avgTempVal');

  // 4. Stations Reporting
  const stationsStr = `${filtered.length} / ${stations.length}`;
  updateKpiWithFlash(elements.kpiStations, elements.kpiStationsVal, stationsStr, 'stationsVal');
}

// ---------------------------------------------------------------------
// 7. Active Alerts Dispatch Panel
// ---------------------------------------------------------------------
function renderAlerts(alerts) {
  const filtered = state.selectedRegion === 'ALL'
    ? alerts
    : alerts.filter(a => a.region_name === state.selectedRegion);

  elements.alertsCountBadge.textContent = `${filtered.length} Active`;

  if (filtered.length === 0) {
    elements.alertsContainer.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">✅</span>
        <p>No active heatwave alerts. All monitored regions are currently within safe thresholds.</p>
      </div>
    `;
    return;
  }

  let html = '';
  filtered.forEach(alert => {
    const level = alert.alert_level || 'Watch';
    const timeStr = alert.created_at ? new Date(alert.created_at).toLocaleString() : '--';
    html += `
      <div class="alert-item severity-${level}" id="alert_card_${alert.alert_id}">
        <div class="alert-info">
          <div class="alert-meta">
            <span class="alert-badge badge-${level.toLowerCase()}">${escapeHtml(level)}</span>
            <strong>${escapeHtml(alert.region_name)}</strong>
            <span>• ${timeStr}</span>
          </div>
          <div class="alert-text">${escapeHtml(alert.message)}</div>
        </div>
        <button class="resolve-btn" onclick="handleResolveAlert(${alert.alert_id})">
          ✓ Mark Resolved
        </button>
      </div>
    `;
  });

  elements.alertsContainer.innerHTML = html;
}

window.handleResolveAlert = async function(alertId) {
  try {
    const res = await fetch(`${CONFIG.API_BASE}${CONFIG.ENDPOINTS.RESOLVE_ALERT(alertId)}`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Failed to resolve alert');
    
    showToast(`Alert #${alertId} marked as resolved!`, 'success');
    
    // Optimistically remove from state and refresh
    state.alerts = state.alerts.filter(a => a.alert_id !== alertId);
    renderAlerts(state.alerts);
    updateKpis(state.stations, state.alerts);
  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
  }
};

// ---------------------------------------------------------------------
// 8. Station Readings Table (Searchable & Sortable)
// ---------------------------------------------------------------------
function renderStationTable(stations) {
  let filtered = state.selectedRegion === 'ALL'
    ? [...stations]
    : stations.filter(s => s.region_name === state.selectedRegion);

  // Apply search query
  if (state.searchQuery.trim() !== '') {
    const query = state.searchQuery.toLowerCase();
    filtered = filtered.filter(s => 
      s.station_name.toLowerCase().includes(query) || 
      s.region_name.toLowerCase().includes(query)
    );
  }

  // Apply Sorting
  filtered.sort((a, b) => {
    let valA = a[state.sortColumn];
    let valB = b[state.sortColumn];

    if (valA == null) valA = '';
    if (valB == null) valB = '';

    if (!isNaN(Number(valA)) && !isNaN(Number(valB))) {
      return state.sortOrder === 'asc' ? Number(valA) - Number(valB) : Number(valB) - Number(valA);
    }
    return state.sortOrder === 'asc' 
      ? String(valA).localeCompare(String(valB)) 
      : String(valB).localeCompare(String(valA));
  });

  if (filtered.length === 0) {
    elements.stationTableBody.innerHTML = `
      <tr><td colspan="8" style="text-align:center; padding: 24px; color: var(--text-muted);">
        No matching stations found.
      </td></tr>
    `;
    return;
  }

  let html = '';
  filtered.forEach(s => {
    const risk = s.risk_level || 'Normal';
    const temp = s.temperature_c != null ? Number(s.temperature_c).toFixed(2) : '--';
    const hi = s.heat_index_c != null ? Number(s.heat_index_c).toFixed(2) : '--';
    const hum = s.humidity_pct != null ? Number(s.humidity_pct).toFixed(1) : '--';
    const wind = s.wind_speed_kmh != null ? Number(s.wind_speed_kmh).toFixed(1) : '--';
    const time = s.recorded_at ? new Date(s.recorded_at).toLocaleTimeString() : '--';

    html += `
      <tr>
        <td><strong>${escapeHtml(s.station_name)}</strong></td>
        <td>${escapeHtml(s.region_name)}</td>
        <td><strong style="color:${RISK_COLORS[risk]};">${temp}</strong></td>
        <td>${hi}</td>
        <td>${hum}%</td>
        <td>${wind}</td>
        <td><span class="tier-pill tier-${risk.toLowerCase()}">${risk}</span></td>
        <td style="color:var(--text-secondary);">${time}</td>
      </tr>
    `;
  });

  elements.stationTableBody.innerHTML = html;
}

// Table Header Click Sort Listener
document.querySelectorAll('.data-table th.sortable').forEach(th => {
  th.addEventListener('click', () => {
    const col = th.getAttribute('data-sort');
    if (state.sortColumn === col) {
      state.sortOrder = state.sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
      state.sortColumn = col;
      state.sortOrder = 'desc';
    }

    // Update Header Indicators
    document.querySelectorAll('.data-table th.sortable').forEach(header => {
      header.classList.remove('active-sort', 'asc', 'desc');
      const ind = header.querySelector('.sort-indicator');
      if (ind) ind.textContent = '';
    });
    th.classList.add('active-sort', state.sortOrder);
    const currentInd = th.querySelector('.sort-indicator');
    if (currentInd) currentInd.textContent = state.sortOrder === 'asc' ? '▲' : '▼';

    renderStationTable(state.stations);
  });
});

elements.stationSearch.addEventListener('input', (e) => {
  state.searchQuery = e.target.value;
  renderStationTable(state.stations);
});

// ---------------------------------------------------------------------
// 9. API Data Fetching Pipeline
// ---------------------------------------------------------------------
async function fetchAllData() {
  try {
    const [liveRes, alertsRes] = await Promise.all([
      fetch(`${CONFIG.API_BASE}${CONFIG.ENDPOINTS.LIVE_STATUS}`),
      fetch(`${CONFIG.API_BASE}${CONFIG.ENDPOINTS.ALERTS(true)}`)
    ]);

    if (!liveRes.ok || !alertsRes.ok) throw new Error('API server unreachable');

    state.stations = await liveRes.json();
    state.alerts = await alertsRes.json();

    setConnectionStatus(true);
    populateRegionDropdown(state.stations);

    // Refresh UI components
    updateKpis(state.stations, state.alerts);
    updateMapMarkers(state.stations);
    renderAlerts(state.alerts);
    renderStationTable(state.stations);
    elements.lastSyncTime.textContent = new Date().toLocaleTimeString();

    // Fetch Trends for active region
    await fetchActiveTrend();

  } catch (err) {
    console.warn('[HEATWAVE] Fetch failed:', err);
    setConnectionStatus(false);
  }
}

async function fetchActiveTrend() {
  let targetRegionId = 1;
  let targetRegionName = 'National / Region 1';

  if (state.selectedRegion !== 'ALL') {
    const found = state.stations.find(s => s.region_name === state.selectedRegion);
    if (found) {
      targetRegionId = found.region_id;
      targetRegionName = found.region_name;
    }
  } else if (state.stations.length > 0) {
    // Default to the hottest station's region
    const hottest = [...state.stations].sort((a,b) => (b.temperature_c||0) - (a.temperature_c||0))[0];
    targetRegionId = hottest.region_id;
    targetRegionName = hottest.region_name;
  }

  elements.chartHeading.textContent = `Temperature Trend & 7-Day Forecast`;
  elements.chartRegionBadge.textContent = targetRegionName;

  try {
    const [trendRes, forecastRes] = await Promise.all([
      fetch(`${CONFIG.API_BASE}${CONFIG.ENDPOINTS.TREND(targetRegionId, state.historicalDays)}`),
      fetch(`${CONFIG.API_BASE}${CONFIG.ENDPOINTS.FORECAST(targetRegionId)}`)
    ]);

    if (trendRes.ok && forecastRes.ok) {
      state.trends = await trendRes.json();
      state.forecasts = await forecastRes.json();
      updateTrendChart(state.trends, state.forecasts);
    }
  } catch (e) {
    console.warn('[TREND] Error fetching trends:', e);
  }
}

function populateRegionDropdown(stations) {
  const currentVal = elements.regionSelect.value;
  const regions = Array.from(new Set(stations.map(s => s.region_name))).sort();

  // If already populated, skip rebuilding
  if (elements.regionSelect.options.length > 1) return;

  regions.forEach(reg => {
    const opt = document.createElement('option');
    opt.value = reg;
    opt.textContent = reg;
    elements.regionSelect.appendChild(opt);
  });

  if (currentVal) elements.regionSelect.value = currentVal;
}

elements.regionSelect.addEventListener('change', (e) => {
  state.selectedRegion = e.target.value;
  updateKpis(state.stations, state.alerts);
  updateMapMarkers(state.stations);
  renderAlerts(state.alerts);
  renderStationTable(state.stations);
  fetchActiveTrend();
});

elements.trendDaysSelect.addEventListener('change', (e) => {
  state.historicalDays = parseInt(e.target.value, 10);
  fetchActiveTrend();
});

// ---------------------------------------------------------------------
// 10. Real-time Server-Sent Events (SSE) Engine
// ---------------------------------------------------------------------
function initEventSource() {
  if (state.eventSource) {
    state.eventSource.close();
  }

  try {
    const sseUrl = `${CONFIG.API_BASE}${CONFIG.ENDPOINTS.STREAM}`;
    const es = new EventSource(sseUrl);
    state.eventSource = es;

    es.onopen = () => {
      setConnectionStatus(true);
      document.getElementById('transportType').textContent = 'Live SSE';
      // Clear polling interval when stream is connected
      if (state.pollTimer) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
      }
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === 'NEW_READING') {
          handleIncomingReading(data);
        }
      } catch (err) {
        // Ping comment or heartbeat
      }
    };

    es.onerror = () => {
      setConnectionStatus(false);
      es.close();
      state.eventSource = null;
      // Gracefully fallback to polling
      startPollingFallback();
      setTimeout(initEventSource, CONFIG.RECONNECT_DELAY_MS);
    };

  } catch (err) {
    startPollingFallback();
  }
}

function handleIncomingReading(payload) {
  // Update state.stations in-place
  const stIndex = state.stations.findIndex(s => s.station_id === payload.station_id);
  if (stIndex !== -1) {
    state.stations[stIndex].temperature_c = payload.temperature_c;
    state.stations[stIndex].humidity_pct = payload.humidity_pct;
    state.stations[stIndex].heat_index_c = payload.heat_index_c;
    state.stations[stIndex].recorded_at = payload.recorded_at;
    
    // Recalculate local risk level
    const temp = parseFloat(payload.temperature_c);
    const severeThresh = parseFloat(state.stations[stIndex].severe_temp_c || 45);
    const warnThresh = parseFloat(state.stations[stIndex].warning_temp_c || 43);
    const watchThresh = parseFloat(state.stations[stIndex].watch_temp_c || 40);

    if (temp >= severeThresh) state.stations[stIndex].risk_level = 'Severe';
    else if (temp >= warnThresh) state.stations[stIndex].risk_level = 'Warning';
    else if (temp >= watchThresh) state.stations[stIndex].risk_level = 'Watch';
    else state.stations[stIndex].risk_level = 'Normal';
  }

  // Re-render UI elements seamlessly
  updateKpis(state.stations, state.alerts);
  updateMapMarkers(state.stations);
  renderStationTable(state.stations);
  elements.lastSyncTime.textContent = new Date().toLocaleTimeString();

  // If thermal spike triggered an alert
  if (payload.alert_triggered) {
    fetch(`${CONFIG.API_BASE}${CONFIG.ENDPOINTS.ALERTS(true)}`)
      .then(res => res.json())
      .then(alerts => {
        state.alerts = alerts;
        renderAlerts(state.alerts);
        updateKpis(state.stations, state.alerts);
        showToast(`⚠️ Heat Alert Triggered in ${payload.region_name}: ${payload.temperature_c}°C`, 'warning');
      });
  }
}

function startPollingFallback() {
  document.getElementById('transportType').textContent = 'HTTP Polling (5s)';
  if (!state.pollTimer) {
    state.pollTimer = setInterval(fetchAllData, CONFIG.POLL_INTERVAL_MS);
  }
}

function setConnectionStatus(connected) {
  state.isConnected = connected;
  if (connected) {
    elements.connectionPill.className = 'status-pill connected';
    elements.connectionText.textContent = 'Live SSE Connected';
  } else {
    elements.connectionPill.className = 'status-pill disconnected';
    elements.connectionText.textContent = 'Disconnected (Retrying)';
  }
}

// ---------------------------------------------------------------------
// 11. Utilities & Toast Notifications
// ---------------------------------------------------------------------
function showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${type === 'success' ? '✅' : '⚠️'}</span><span>${escapeHtml(message)}</span>`;
  elements.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function roundTo(val, dec = 2) {
  return Number(Math.round(val + 'e' + dec) + 'e-' + dec);
}

// ---------------------------------------------------------------------
// 12. Bootstrap Application
// ---------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  applyTheme(state.theme);
  initLeafletMap();
  initTrendChart();
  fetchAllData();
  initEventSource();
});
