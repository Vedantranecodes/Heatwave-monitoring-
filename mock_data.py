"""
Fallback mock meteorological data for Climate Intelligence Platform.
Used when PostgreSQL heatwave_db is offline or during offline demonstrations.
"""

from datetime import datetime, timedelta, date

FALLBACK_REGIONS = [
    {"region_id": 1, "region_name": "Delhi NCR", "state": "Delhi", "watch_temp_c": 40.0, "warning_temp_c": 43.0, "severe_temp_c": 45.0},
    {"region_id": 2, "region_name": "Nagpur", "state": "Maharashtra", "watch_temp_c": 41.0, "warning_temp_c": 44.0, "severe_temp_c": 46.5},
    {"region_id": 3, "region_name": "Ahmedabad", "state": "Gujarat", "watch_temp_c": 40.5, "warning_temp_c": 43.5, "severe_temp_c": 45.5},
    {"region_id": 4, "region_name": "Jaipur", "state": "Rajasthan", "watch_temp_c": 41.0, "warning_temp_c": 44.0, "severe_temp_c": 46.5},
    {"region_id": 5, "region_name": "Mumbai", "state": "Maharashtra", "watch_temp_c": 35.0, "warning_temp_c": 37.0, "severe_temp_c": 39.0}
]

FALLBACK_STATIONS = [
    # Delhi NCR
    {"station_id": 1, "region_id": 1, "region_name": "Delhi NCR", "state": "Delhi", "station_name": "Safdarjung Observatory", "latitude": 28.5833, "longitude": 77.2000, "elevation_m": 216.0, "temperature_c": 42.4, "humidity_pct": 32.0, "wind_speed_kmh": 14.0, "heat_index_c": 44.8, "risk_level": "Watch", "watch_temp_c": 40.0, "warning_temp_c": 43.0, "severe_temp_c": 45.0, "is_active": True},
    {"station_id": 2, "region_id": 1, "region_name": "Delhi NCR", "state": "Delhi", "station_name": "Palam Airport Station", "latitude": 28.5665, "longitude": 77.1031, "elevation_m": 237.0, "temperature_c": 43.8, "humidity_pct": 28.0, "wind_speed_kmh": 16.5, "heat_index_c": 46.2, "risk_level": "Warning", "watch_temp_c": 40.0, "warning_temp_c": 43.0, "severe_temp_c": 45.0, "is_active": True},
    {"station_id": 3, "region_id": 1, "region_name": "Delhi NCR", "state": "Delhi", "station_name": "Lodhi Road AWS", "latitude": 28.5912, "longitude": 77.2270, "elevation_m": 211.0, "temperature_c": 41.9, "humidity_pct": 35.0, "wind_speed_kmh": 11.0, "heat_index_c": 44.1, "risk_level": "Watch", "watch_temp_c": 40.0, "warning_temp_c": 43.0, "severe_temp_c": 45.0, "is_active": True},
    
    # Nagpur (Epicenter)
    {"station_id": 4, "region_id": 2, "region_name": "Nagpur", "state": "Maharashtra", "station_name": "Sonegaon Airport Met", "latitude": 21.0922, "longitude": 79.0583, "elevation_m": 310.0, "temperature_c": 46.8, "humidity_pct": 22.0, "wind_speed_kmh": 18.0, "heat_index_c": 48.9, "risk_level": "Severe", "watch_temp_c": 41.0, "warning_temp_c": 44.0, "severe_temp_c": 46.5, "is_active": True},
    {"station_id": 5, "region_id": 2, "region_name": "Nagpur", "state": "Maharashtra", "station_name": "Ramdaspeth Urban AWS", "latitude": 21.1350, "longitude": 79.0740, "elevation_m": 315.0, "temperature_c": 45.6, "humidity_pct": 25.0, "wind_speed_kmh": 12.0, "heat_index_c": 47.4, "risk_level": "Warning", "watch_temp_c": 41.0, "warning_temp_c": 44.0, "severe_temp_c": 46.5, "is_active": True},
    {"station_id": 6, "region_id": 2, "region_name": "Nagpur", "state": "Maharashtra", "station_name": "MIDC Hingna Station", "latitude": 21.1100, "longitude": 78.9800, "elevation_m": 325.0, "temperature_c": 46.1, "humidity_pct": 21.0, "wind_speed_kmh": 14.5, "heat_index_c": 48.0, "risk_level": "Warning", "watch_temp_c": 41.0, "warning_temp_c": 44.0, "severe_temp_c": 46.5, "is_active": True},

    # Ahmedabad
    {"station_id": 7, "region_id": 3, "region_name": "Ahmedabad", "state": "Gujarat", "station_name": "Sabarmati Riverfront Met", "latitude": 23.0330, "longitude": 72.5800, "elevation_m": 53.0, "temperature_c": 42.1, "humidity_pct": 36.0, "wind_speed_kmh": 15.0, "heat_index_c": 45.0, "risk_level": "Watch", "watch_temp_c": 40.5, "warning_temp_c": 43.5, "severe_temp_c": 45.5, "is_active": True},
    {"station_id": 8, "region_id": 3, "region_name": "Ahmedabad", "state": "Gujarat", "station_name": "Navrangpura Urban AWS", "latitude": 23.0365, "longitude": 72.5611, "elevation_m": 55.0, "temperature_c": 41.5, "humidity_pct": 38.0, "wind_speed_kmh": 13.0, "heat_index_c": 44.2, "risk_level": "Watch", "watch_temp_c": 40.5, "warning_temp_c": 43.5, "severe_temp_c": 45.5, "is_active": True},
    {"station_id": 9, "region_id": 3, "region_name": "Ahmedabad", "state": "Gujarat", "station_name": "Ahmedabad Airport AWS", "latitude": 23.0734, "longitude": 72.6347, "elevation_m": 58.0, "temperature_c": 43.2, "humidity_pct": 33.0, "wind_speed_kmh": 17.0, "heat_index_c": 46.1, "risk_level": "Watch", "watch_temp_c": 40.5, "warning_temp_c": 43.5, "severe_temp_c": 45.5, "is_active": True},

    # Jaipur
    {"station_id": 10, "region_id": 4, "region_name": "Jaipur", "state": "Rajasthan", "station_name": "Sanganer Airport Station", "latitude": 26.8242, "longitude": 75.8122, "elevation_m": 385.0, "temperature_c": 44.5, "humidity_pct": 20.0, "wind_speed_kmh": 20.0, "heat_index_c": 45.8, "risk_level": "Warning", "watch_temp_c": 41.0, "warning_temp_c": 44.0, "severe_temp_c": 46.5, "is_active": True},
    {"station_id": 11, "region_id": 4, "region_name": "Jaipur", "state": "Rajasthan", "station_name": "Amer Foothills AWS", "latitude": 26.9855, "longitude": 75.8507, "elevation_m": 430.0, "temperature_c": 43.0, "humidity_pct": 23.0, "wind_speed_kmh": 15.0, "heat_index_c": 44.3, "risk_level": "Watch", "watch_temp_c": 41.0, "warning_temp_c": 44.0, "severe_temp_c": 46.5, "is_active": True},
    {"station_id": 12, "region_id": 4, "region_name": "Jaipur", "state": "Rajasthan", "station_name": "Mansarovar City Met", "latitude": 26.8530, "longitude": 75.7600, "elevation_m": 390.0, "temperature_c": 44.1, "humidity_pct": 19.0, "wind_speed_kmh": 16.0, "heat_index_c": 45.2, "risk_level": "Warning", "watch_temp_c": 41.0, "warning_temp_c": 44.0, "severe_temp_c": 46.5, "is_active": True},

    # Mumbai (Coastal high humidity)
    {"station_id": 13, "region_id": 5, "region_name": "Mumbai", "state": "Maharashtra", "station_name": "Colaba Coastal Met", "latitude": 18.9067, "longitude": 72.8147, "elevation_m": 11.0, "temperature_c": 35.8, "humidity_pct": 78.0, "wind_speed_kmh": 22.0, "heat_index_c": 43.5, "risk_level": "Watch", "watch_temp_c": 35.0, "warning_temp_c": 37.0, "severe_temp_c": 39.0, "is_active": True},
    {"station_id": 14, "region_id": 5, "region_name": "Mumbai", "state": "Maharashtra", "station_name": "Santacruz Suburban AWS", "latitude": 19.0896, "longitude": 72.8656, "elevation_m": 14.0, "temperature_c": 37.4, "humidity_pct": 74.0, "wind_speed_kmh": 18.0, "heat_index_c": 46.1, "risk_level": "Warning", "watch_temp_c": 35.0, "warning_temp_c": 37.0, "severe_temp_c": 39.0, "is_active": True},
    {"station_id": 15, "region_id": 5, "region_name": "Mumbai", "state": "Maharashtra", "station_name": "Powai Lake Urban Met", "latitude": 19.1290, "longitude": 72.9050, "elevation_m": 45.0, "temperature_c": 36.5, "humidity_pct": 76.0, "wind_speed_kmh": 14.0, "heat_index_c": 44.8, "risk_level": "Watch", "watch_temp_c": 35.0, "warning_temp_c": 37.0, "severe_temp_c": 39.0, "is_active": True}
]

# Set recorded_at timestamp to now
for st in FALLBACK_STATIONS:
    st["reading_id"] = st["station_id"] + 1000
    st["recorded_at"] = datetime.now()

FALLBACK_ALERTS = [
    {
        "alert_id": 1,
        "region_id": 2,
        "region_name": "Nagpur",
        "alert_level": "Severe",
        "message": "Red Alert: Extreme heatwave conditions recorded across Nagpur (46.8°C at Sonegaon). Stay indoors.",
        "created_at": datetime.now() - timedelta(hours=2),
        "is_resolved": False
    },
    {
        "alert_id": 2,
        "region_id": 4,
        "region_name": "Jaipur",
        "alert_level": "Warning",
        "message": "Orange Alert: Sustained high thermal load above 44°C across Jaipur airport and urban corridors.",
        "created_at": datetime.now() - timedelta(hours=4),
        "is_resolved": False
    },
    {
        "alert_id": 3,
        "region_id": 1,
        "region_name": "Delhi NCR",
        "alert_level": "Warning",
        "message": "Orange Alert: Heatwave conditions building up in Delhi NCR (>43.5°C). Avoid outdoor exposure from 12-4 PM.",
        "created_at": datetime.now() - timedelta(hours=5),
        "is_resolved": False
    },
    {
        "alert_id": 4,
        "region_id": 5,
        "region_name": "Mumbai",
        "alert_level": "Watch",
        "message": "Yellow Alert: High humidity (78%) elevating coastal heat index past 43°C in Mumbai suburban area.",
        "created_at": datetime.now() - timedelta(hours=8),
        "is_resolved": False
    }
]

def generate_fallback_trends(region_id: int, days: int = 30):
    """Generate 30 days of realistic daily aggregates."""
    reg = next((r for r in FALLBACK_REGIONS if r["region_id"] == region_id), FALLBACK_REGIONS[0])
    base_t = 32.0 if "Mumbai" in reg["region_name"] else 38.5
    
    today = date.today()
    trend_data = []
    for i in range(days, 0, -1):
        day_date = today - timedelta(days=i)
        # Add heat wave variation
        wave_bump = 3.5 if 10 <= i <= 16 else 0.0
        avg_t = round(base_t + wave_bump + (i % 5) * 0.4 - 1.2, 2)
        min_t = round(avg_t - 6.5, 2)
        max_t = round(avg_t + 5.5, 2)
        trend_data.append({
            "region_id": reg["region_id"],
            "region_name": reg["region_name"],
            "reading_date": day_date,
            "total_readings": 72,
            "min_temp_c": min_t,
            "avg_temp_c": avg_t,
            "max_temp_c": max_t,
            "avg_humidity_pct": 35.0 if "Mumbai" not in reg["region_name"] else 75.0,
            "max_heat_index_c": round(max_t + 2.5, 2)
        })
    return trend_data

def generate_fallback_forecast(region_id: int):
    """Generate 7-day predictive forecast."""
    reg = next((r for r in FALLBACK_REGIONS if r["region_id"] == region_id), FALLBACK_REGIONS[0])
    base_t = 35.0 if "Mumbai" in reg["region_name"] else 42.0
    
    today = date.today()
    forecast_data = []
    for i in range(1, 8):
        future_date = today + timedelta(days=i)
        pred_temp = round(base_t + 1.2 * i * 0.3 + (i % 3) * 0.6, 2)
        risk = "Severe" if pred_temp >= reg["severe_temp_c"] else ("Warning" if pred_temp >= reg["warning_temp_c"] else ("Watch" if pred_temp >= reg["watch_temp_c"] else "Normal"))
        forecast_data.append({
            "prediction_id": 100 + i,
            "region_id": reg["region_id"],
            "region_name": reg["region_name"],
            "predicted_for": future_date,
            "predicted_temp_c": pred_temp,
            "risk_level": risk,
            "model_name": "RandomForestRegressor_v1",
            "created_at": datetime.now()
        })
    return forecast_data
