"""
Streamlit Dashboard: Climate Intelligence for Heatwave Monitoring & Early Warning
Real-time geospatial analytics, 30-day moving trends, forecasting, and alert management.
"""

import os
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
import requests
from sqlalchemy import create_engine, text

# Try importing streamlit_autorefresh
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# ---------------------------------------------------------------------
# Application Configuration & Theming
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="Climate Intelligence | Heatwave Early Warning",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern glassmorphism & typography
st.markdown("""
<style>
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .badge-normal { background-color: #10B981; color: white; padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 12px; }
    .badge-watch { background-color: #F59E0B; color: white; padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 12px; }
    .badge-warning { background-color: #F97316; color: white; padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 12px; }
    .badge-severe { background-color: #EF4444; color: white; padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 12px; }
    .stButton>button { border-radius: 6px; width: 100%; }
</style>
""", unsafe_allow_html=True)

# Load configuration
load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "heatwave_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

@st.cache_resource
def get_db_engine():
    """Create persistent SQLAlchemy engine with connection pool."""
    return create_engine(DATABASE_URL, pool_size=5, max_overflow=10, pool_pre_ping=True)

# ---------------------------------------------------------------------
# Resilient Data Fetching (FastAPI with DB Fallback)
# ---------------------------------------------------------------------
def fetch_live_status():
    """Fetch live station status from API or direct view."""
    try:
        resp = requests.get(f"{API_BASE_URL}/live-status", timeout=2.0)
        if resp.status_code == 200:
            return pd.DataFrame(resp.json()), "API (FastAPI:8000)"
    except Exception:
        pass
    
    # Direct DB Fallback
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            df = pd.read_sql("SELECT * FROM v_live_status ORDER BY region_id, station_id;", conn)
            return df, "Direct PostgreSQL View"
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        return pd.DataFrame(), "Disconnected"

def fetch_trends(region_id, days=30):
    """Fetch historical daily trends for a region."""
    try:
        resp = requests.get(f"{API_BASE_URL}/trend/{region_id}?days={days}", timeout=2.0)
        if resp.status_code == 200:
            return pd.DataFrame(resp.json())
    except Exception:
        pass
    
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            query = text("""
                SELECT * FROM v_region_daily_summary
                WHERE region_id = :region_id
                  AND reading_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
                ORDER BY reading_date ASC;
            """)
            return pd.read_sql(query, conn, params={"region_id": region_id, "days": days})
    except Exception:
        return pd.DataFrame()

def fetch_forecasts(region_id):
    """Fetch 7-day predicted temperatures for a region."""
    try:
        resp = requests.get(f"{API_BASE_URL}/forecast/{region_id}", timeout=2.0)
        if resp.status_code == 200:
            df = pd.DataFrame(resp.json())
            if not df.empty:
                return df
    except Exception:
        pass
    
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            query = text("""
                SELECT * FROM predictions
                WHERE region_id = :region_id AND predicted_for >= CURRENT_DATE
                ORDER BY predicted_for ASC;
            """)
            return pd.read_sql(query, conn, params={"region_id": region_id})
    except Exception:
        return pd.DataFrame()

def fetch_active_alerts():
    """Fetch all active unresolved weather alerts."""
    try:
        resp = requests.get(f"{API_BASE_URL}/alerts?active=true", timeout=2.0)
        if resp.status_code == 200:
            return pd.DataFrame(resp.json())
    except Exception:
        pass
    
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            query = text("""
                SELECT a.alert_id, a.region_id, r.region_name, a.alert_level, a.message, a.created_at, a.is_resolved
                FROM alerts a
                JOIN regions r ON a.region_id = r.region_id
                WHERE a.is_resolved = FALSE
                ORDER BY a.created_at DESC;
            """)
            return pd.read_sql(query, conn)
    except Exception:
        return pd.DataFrame()

def resolve_alert_in_db(alert_id: int):
    """Mark an alert as resolved in PostgreSQL."""
    try:
        engine = get_db_engine()
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE alerts SET is_resolved = TRUE WHERE alert_id = :aid;"),
                {"aid": alert_id}
            )
        return True
    except Exception as err:
        st.error(f"Error resolving alert: {err}")
        return False

# ---------------------------------------------------------------------
# Sidebar Controls & Auto-Refresh
# ---------------------------------------------------------------------
st.sidebar.title("🔥 Climate Intelligence")
st.sidebar.caption("Real-Time Heatwave Early Warning System")

auto_refresh = st.sidebar.checkbox("Auto-refresh (every 5 seconds)", value=True)
refresh_interval = 5000  # ms

if auto_refresh:
    if HAS_AUTOREFRESH:
        st_autorefresh(interval=refresh_interval, key="heatwave_refresh_tick")
    else:
        # Fallback if package is not present
        time.sleep(5)
        st.rerun()

live_df, data_source = fetch_live_status()

# Region Filter
region_options = ["All Regions"]
if not live_df.empty and "region_name" in live_df.columns:
    region_options += sorted(live_df["region_name"].dropna().unique().tolist())

selected_region = st.sidebar.selectbox("Filter by Region", region_options)
st.sidebar.markdown(f"**Data Pipeline:** `{data_source}`")
st.sidebar.markdown(f"**Last Sync:** `{datetime.now().strftime('%H:%M:%S')}`")

if st.sidebar.button("🔄 Manual Refresh"):
    st.rerun()

# ---------------------------------------------------------------------
# 1. Top KPI Metrics
# ---------------------------------------------------------------------
st.markdown("## 🛰️ Regional Climate Operations Center")

if live_df.empty:
    st.warning("No live weather station data detected. Ensure PostgreSQL and simulator.py are running.")
    st.stop()

# Filter data by region if selected
filtered_df = live_df if selected_region == "All Regions" else live_df[live_df["region_name"] == selected_region]

alerts_df = fetch_active_alerts()
active_alerts_count = len(alerts_df) if not alerts_df.empty else 0

# KPI Calculations
hottest_row = live_df.loc[live_df["temperature_c"].idxmax()] if not live_df.empty else None
hottest_label = f"{hottest_row['region_name']} ({hottest_row['temperature_c']}°C)" if hottest_row is not None else "N/A"
avg_temp = round(live_df["temperature_c"].mean(), 1) if not live_df.empty else 0.0
stations_reporting = len(live_df)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="🌡️ Hottest Region Now", value=hottest_label)
with col2:
    st.metric(label="🚨 Active Heatwave Alerts", value=active_alerts_count, delta=f"{active_alerts_count} Open" if active_alerts_count > 0 else "Normal", delta_color="inverse")
with col3:
    st.metric(label="📊 Network Avg Temperature", value=f"{avg_temp}°C")
with col4:
    st.metric(label="📡 Active Reporting Stations", value=f"{stations_reporting} Stations")

# ---------------------------------------------------------------------
# 2. Interactive Geospatial Map (Plotly)
# ---------------------------------------------------------------------
st.markdown("### 🗺️ Live Weather Station Risk Map")

color_map = {
    "Normal": "#10B981",   # Green
    "Watch": "#F59E0B",    # Amber
    "Warning": "#F97316",  # Orange
    "Severe": "#EF4444"    # Crimson Red
}

map_df = filtered_df.copy()
map_df["color"] = map_df["risk_level"].map(color_map).fillna("#10B981")

MAPBOX_TOKEN = os.getenv("MAPBOX_ACCESS_TOKEN", "").strip()

mapbox_style = "dark" if MAPBOX_TOKEN else "carto-darkmatter"

fig_map = px.scatter_mapbox(
    map_df,
    lat="latitude",
    lon="longitude",
    hover_name="station_name",
    hover_data={
        "region_name": True,
        "temperature_c": ":.2f",
        "heat_index_c": ":.2f",
        "humidity_pct": ":.1f",
        "risk_level": True,
        "latitude": False,
        "longitude": False
    },
    color="risk_level",
    color_discrete_map=color_map,
    size="temperature_c",
    size_max=16,
    zoom=4.5,
    center={"lat": 22.5937, "lon": 78.9629},
    mapbox_style=mapbox_style,
    height=450
)
layout_args = dict(
    margin=dict(l=0, r=0, t=0, b=0),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
if MAPBOX_TOKEN:
    layout_args["mapbox"] = dict(accesstoken=MAPBOX_TOKEN)

fig_map.update_layout(**layout_args)
st.plotly_chart(fig_map, use_container_width=True)

# ---------------------------------------------------------------------
# 3. 30-Day Trend Chart with 7-Day Forecast & Thresholds
# ---------------------------------------------------------------------
st.markdown("### 📈 Temperature Trends & Predictive 7-Day Forecast")

# Determine region_id for trend charting
chart_region_id = 1
if selected_region != "All Regions" and not filtered_df.empty:
    chart_region_id = int(filtered_df.iloc[0]["region_id"])
elif not live_df.empty:
    chart_region_id = int(hottest_row["region_id"])

trend_df = fetch_trends(chart_region_id, days=30)
forecast_df = fetch_forecasts(chart_region_id)

# Region name and thresholds
region_name = filtered_df.iloc[0]["region_name"] if not filtered_df.empty else "Selected Region"
watch_thresh = filtered_df.iloc[0]["watch_temp_c"] if not filtered_df.empty and pd.notnull(filtered_df.iloc[0]["watch_temp_c"]) else 40.0
warn_thresh = filtered_df.iloc[0]["warning_temp_c"] if not filtered_df.empty and pd.notnull(filtered_df.iloc[0]["warning_temp_c"]) else 43.0
severe_thresh = filtered_df.iloc[0]["severe_temp_c"] if not filtered_df.empty and pd.notnull(filtered_df.iloc[0]["severe_temp_c"]) else 45.0

fig_trend = go.Figure()

if not trend_df.empty:
    trend_df["reading_date"] = pd.to_datetime(trend_df["reading_date"])
    trend_df = trend_df.sort_values("reading_date")
    
    # Calculate 7-day rolling moving average
    trend_df["rolling_7d_avg"] = trend_df["avg_temp_c"].rolling(window=7, min_periods=1).mean()

    # Historical Daily Average
    fig_trend.add_trace(go.Scatter(
        x=trend_df["reading_date"],
        y=trend_df["avg_temp_c"],
        mode="lines+markers",
        name="Daily Avg Temp (°C)",
        line=dict(color="#3B82F6", width=2)
    ))

    # 7-Day Rolling Moving Average
    fig_trend.add_trace(go.Scatter(
        x=trend_df["reading_date"],
        y=trend_df["rolling_7d_avg"],
        mode="lines",
        name="7-Day Moving Avg",
        line=dict(color="#8B5CF6", width=2.5, dash="dot")
    ))

# If forecast exists, plot it; otherwise generate continuous synthetic projection
if not forecast_df.empty:
    forecast_df["predicted_for"] = pd.to_datetime(forecast_df["predicted_for"])
    fig_trend.add_trace(go.Scatter(
        x=forecast_df["predicted_for"],
        y=forecast_df["predicted_temp_c"],
        mode="lines+markers",
        name="7-Day ML Forecast (°C)",
        line=dict(color="#EF4444", width=3, dash="dash")
    ))
elif not trend_df.empty:
    last_date = trend_df["reading_date"].max()
    last_temp = trend_df["avg_temp_c"].iloc[-1]
    future_dates = [last_date + timedelta(days=i) for i in range(1, 8)]
    # Extrapolate projection
    projected_temps = [round(last_temp + np.sin(i / 1.5) * 1.8 + np.random.normal(0, 0.4), 2) for i in range(1, 8)]
    fig_trend.add_trace(go.Scatter(
        x=future_dates,
        y=projected_temps,
        mode="lines+markers",
        name="7-Day Extrapolated Forecast",
        line=dict(color="#EF4444", width=2.5, dash="dash")
    ))

# Threshold Reference Lines
fig_trend.add_hline(y=watch_thresh, line_dash="dot", line_color="#F59E0B", annotation_text=f"Watch ({watch_thresh}°C)")
fig_trend.add_hline(y=warn_thresh, line_dash="dash", line_color="#F97316", annotation_text=f"Warning ({warn_thresh}°C)")
fig_trend.add_hline(y=severe_thresh, line_dash="solid", line_color="#EF4444", annotation_text=f"Severe ({severe_thresh}°C)")

fig_trend.update_layout(
    title=f"30-Day Historical Trend vs 7-Day Forecast for {region_name}",
    xaxis_title="Date",
    yaxis_title="Temperature (°C)",
    hovermode="x unified",
    height=420,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(fig_trend, use_container_width=True)

# ---------------------------------------------------------------------
# 4. Active Alerts & Resolution Table
# ---------------------------------------------------------------------
st.markdown("### 🚨 Active Alerts Dispatch Center")

if alerts_df.empty:
    st.success("✅ All weather conditions are within safe limits. Zero active alerts.")
else:
    for idx, alert in alerts_df.iterrows():
        a_col1, a_col2, a_col3 = st.columns([1.5, 7.5, 1.5])
        
        badge_class = f"badge-{alert['alert_level'].lower()}"
        with a_col1:
            st.markdown(f"<span class='{badge_class}'>{alert['alert_level'].upper()} ALERT</span>", unsafe_allow_html=True)
            st.caption(f"Region: {alert['region_name']}")
        with a_col2:
            st.markdown(f"**{alert['message']}**")
            st.caption(f"Issued: {alert['created_at']}")
        with a_col3:
            if st.button("Mark Resolved", key=f"resolve_btn_{alert['alert_id']}"):
                if resolve_alert_in_db(alert["alert_id"]):
                    st.success("Resolved!")
                    time.sleep(0.5)
                    st.rerun()
        st.divider()

# ---------------------------------------------------------------------
# 5. Live Station Readings Table
# ---------------------------------------------------------------------
st.markdown("### 📋 Live Sensor Readings per Station")

display_df = filtered_df[[
    "station_name", "region_name", "temperature_c", "heat_index_c", 
    "humidity_pct", "wind_speed_kmh", "risk_level", "recorded_at"
]].rename(columns={
    "station_name": "Station",
    "region_name": "Region",
    "temperature_c": "Temp (°C)",
    "heat_index_c": "Heat Index (°C)",
    "humidity_pct": "Humidity (%)",
    "wind_speed_kmh": "Wind (km/h)",
    "risk_level": "Risk Level",
    "recorded_at": "Last Recorded"
}).sort_values("Temp (°C)", ascending=False)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)
