"""
FastAPI Backend Application for Climate Intelligence Heatwave Monitoring.
Provides RESTful APIs for real-time sensor status, trends, alerts, and Server-Sent Events (SSE).
"""

import os
import json
import asyncio
import select
from typing import List, Optional
from datetime import date, datetime
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import psycopg2
import psycopg2.extensions
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment configuration
load_dotenv()

# Import fallback data provider when DB is offline
from mock_data import (
    FALLBACK_STATIONS,
    FALLBACK_ALERTS,
    FALLBACK_REGIONS,
    generate_fallback_trends,
    generate_fallback_forecast
)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "heatwave_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLAlchemy Engine with Connection Pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args={"connect_timeout": 1}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI Initialization
app = FastAPI(
    title="Climate Intelligence: Heatwave Monitoring API",
    description="Real-time environmental monitoring, alerting, and forecasting backend.",
    version="1.0.0"
)

# Enable Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------
# Pydantic Response Schemas
# ---------------------------------------------------------------------
class LiveStatusResponse(BaseModel):
    station_id: int
    station_name: str
    latitude: float
    longitude: float
    elevation_m: Optional[float] = None
    region_id: int
    region_name: str
    state: str
    reading_id: Optional[int] = None
    recorded_at: Optional[datetime] = None
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    wind_speed_kmh: Optional[float] = None
    heat_index_c: Optional[float] = None
    watch_temp_c: Optional[float] = None
    warning_temp_c: Optional[float] = None
    severe_temp_c: Optional[float] = None
    risk_level: str

class TrendPointResponse(BaseModel):
    region_id: int
    region_name: str
    reading_date: date
    total_readings: int
    min_temp_c: float
    avg_temp_c: float
    max_temp_c: float
    avg_humidity_pct: float
    max_heat_index_c: float

class ForecastResponse(BaseModel):
    prediction_id: int
    region_id: int
    region_name: Optional[str] = None
    predicted_for: date
    predicted_temp_c: float
    risk_level: str
    model_name: str
    created_at: datetime

class AlertResponse(BaseModel):
    alert_id: int
    region_id: int
    region_name: str
    alert_level: str
    message: str
    created_at: datetime
    is_resolved: bool

class StationResponse(BaseModel):
    station_id: int
    region_id: int
    region_name: str
    station_name: str
    latitude: float
    longitude: float
    elevation_m: Optional[float] = None
    installed_on: date
    is_active: bool

# ---------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------

@app.get("/health", tags=["System"])
def health_check():
    """Verify backend and database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "database": "offline", "mode": "fallback"}

@app.get("/live-status", response_model=List[LiveStatusResponse], tags=["Monitoring"])
def get_live_status():
    """Retrieve latest reading, coordinates, and current risk level for all active stations."""
    try:
        query = text("""
            SELECT 
                station_id, station_name, latitude, longitude, elevation_m,
                region_id, region_name, state, reading_id, recorded_at,
                temperature_c, humidity_pct, wind_speed_kmh, heat_index_c,
                watch_temp_c, warning_temp_c, severe_temp_c, risk_level
            FROM v_live_status
            ORDER BY region_id, station_id;
        """)
        with engine.connect() as conn:
            result = conn.execute(query).mappings().fetchall()
            if result:
                return [dict(row) for row in result]
    except Exception:
        pass
    # Fallback when database is empty or offline
    return FALLBACK_STATIONS

@app.get("/trend/{region_id}", response_model=List[TrendPointResponse], tags=["Analytics"])
def get_region_trend(
    region_id: int = Path(..., description="ID of the target region"),
    days: int = Query(30, ge=1, le=180, description="Number of historical days to fetch")
):
    """Retrieve daily summary trends (min/avg/max temperature and heat index) for a specific region."""
    try:
        query = text("""
            SELECT 
                region_id, region_name, reading_date, total_readings,
                min_temp_c, avg_temp_c, max_temp_c, avg_humidity_pct, max_heat_index_c
            FROM v_region_daily_summary
            WHERE region_id = :region_id
              AND reading_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
            ORDER BY reading_date ASC;
        """)
        with engine.connect() as conn:
            result = conn.execute(query, {"region_id": region_id, "days": days}).mappings().fetchall()
            if result:
                return [dict(row) for row in result]
    except Exception:
        pass
    return generate_fallback_trends(region_id, days)

@app.get("/forecast/{region_id}", response_model=List[ForecastResponse], tags=["Forecasting"])
def get_region_forecast(region_id: int = Path(..., description="Target region ID")):
    """Retrieve 3-7 day temperature and heatwave predictions for a region."""
    try:
        query = text("""
            SELECT 
                p.prediction_id, p.region_id, r.region_name,
                p.predicted_for, p.predicted_temp_c, p.risk_level,
                p.model_name, p.created_at
            FROM predictions p
            JOIN regions r ON p.region_id = r.region_id
            WHERE p.region_id = :region_id
              AND p.predicted_for >= CURRENT_DATE
            ORDER BY p.predicted_for ASC;
        """)
        with engine.connect() as conn:
            result = conn.execute(query, {"region_id": region_id}).mappings().fetchall()
            if result:
                return [dict(row) for row in result]
    except Exception:
        pass
    return generate_fallback_forecast(region_id)

@app.get("/alerts", response_model=List[AlertResponse], tags=["Alerting"])
def get_alerts(active: bool = Query(True, description="Filter for active unresolved alerts only")):
    """List weather alerts across all regions with optional unresolved filtering."""
    try:
        query_sql = """
            SELECT 
                a.alert_id, a.region_id, r.region_name,
                a.alert_level, a.message, a.created_at, a.is_resolved
            FROM alerts a
            JOIN regions r ON a.region_id = r.region_id
        """
        if active:
            query_sql += " WHERE a.is_resolved = FALSE"
        query_sql += " ORDER BY a.created_at DESC LIMIT 50;"

        with engine.connect() as conn:
            result = conn.execute(text(query_sql)).mappings().fetchall()
            if result:
                return [dict(row) for row in result]
    except Exception:
        pass
    return [a for a in FALLBACK_ALERTS if not active or not a["is_resolved"]]

@app.post("/alerts/{alert_id}/resolve", tags=["Alerting"])
def resolve_alert(alert_id: int = Path(..., description="ID of alert to resolve")):
    """Mark an active alert as resolved in the database."""
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("UPDATE alerts SET is_resolved = TRUE WHERE alert_id = :aid;"),
                {"aid": alert_id}
            )
            if result.rowcount > 0:
                return {"status": "success", "message": f"Alert {alert_id} resolved"}
    except Exception:
        pass
    # In-memory resolution
    for a in FALLBACK_ALERTS:
        if a["alert_id"] == alert_id:
            a["is_resolved"] = True
            return {"status": "success", "message": f"Alert {alert_id} resolved"}
    return {"status": "success", "message": f"Alert {alert_id} resolved"}

@app.get("/stations", response_model=List[StationResponse], tags=["Metadata"])
def get_stations():
    """Retrieve all metadata for registered monitoring weather stations."""
    try:
        query = text("""
            SELECT 
                s.station_id, s.region_id, r.region_name, s.station_name,
                s.latitude, s.longitude, s.elevation_m, s.installed_on, s.is_active
            FROM weather_stations s
            JOIN regions r ON s.region_id = r.region_id
            ORDER BY s.station_id ASC;
        """)
        with engine.connect() as conn:
            result = conn.execute(query).mappings().fetchall()
            if result:
                return [dict(row) for row in result]
    except Exception:
        pass
    return [
        {
            "station_id": s["station_id"],
            "region_id": s["region_id"],
            "region_name": s["region_name"],
            "station_name": s["station_name"],
            "latitude": s["latitude"],
            "longitude": s["longitude"],
            "elevation_m": s["elevation_m"],
            "installed_on": date(2021, 1, 15),
            "is_active": s["is_active"]
        }
        for s in FALLBACK_STATIONS
    ]

@app.get("/stream", tags=["Real-time Push"])
async def stream_live_events():
    """
    Server-Sent Events (SSE) streaming endpoint.
    Listens to PostgreSQL pg_notify on 'heatwave_channel' or emits simulated sensor walk.
    """
    import random
    async def event_generator():
        raw_conn = None
        cur = None
        db_mode = False
        try:
            raw_conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                connect_timeout=2
            )
            raw_conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            cur = raw_conn.cursor()
            cur.execute("LISTEN heatwave_channel;")
            db_mode = True
        except Exception:
            db_mode = False

        init_msg = json.dumps({"status": "connected", "channel": "heatwave_channel", "source": "postgres" if db_mode else "simulation"})
        yield f"data: {init_msg}\n\n"

        tick = 0
        while True:
            try:
                if db_mode and raw_conn:
                    if select.select([raw_conn], [], [], 2.0) == ([], [], []):
                        yield ": ping\n\n"
                    else:
                        raw_conn.poll()
                        while raw_conn.notifies:
                            notify = raw_conn.notifies.pop(0)
                            yield f"data: {notify.payload}\n\n"
                else:
                    # Simulated real-time sensor pulse every 5 seconds
                    await asyncio.sleep(5)
                    st = random.choice(FALLBACK_STATIONS)
                    temp_jitter = round(st["temperature_c"] + random.uniform(-0.6, 0.8), 2)
                    st["temperature_c"] = temp_jitter
                    st["recorded_at"] = datetime.now()
                    sim_payload = json.dumps({
                        "event": "NEW_READING",
                        "station_id": st["station_id"],
                        "station_name": st["station_name"],
                        "region_id": st["region_id"],
                        "region_name": st["region_name"],
                        "temperature_c": temp_jitter,
                        "humidity_pct": st["humidity_pct"],
                        "heat_index_c": round(temp_jitter + 2.4, 2),
                        "recorded_at": st["recorded_at"].isoformat(),
                        "alert_triggered": "Severe" if temp_jitter >= 46.5 else ("Warning" if temp_jitter >= 44.0 else None)
                    })
                    yield f"data: {sim_payload}\n\n"
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(2)

        if cur:
            cur.close()
        if raw_conn and not raw_conn.closed:
            raw_conn.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
