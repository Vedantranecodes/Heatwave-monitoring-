"""
Real-time sensor stream simulator for heatwave_db.
Generates stochastic random-walk weather readings and pushes them to PostgreSQL.
"""

import os
import sys
import time
import signal
import random
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Load environment variables
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "heatwave_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
INTERVAL_SEC = float(os.getenv("SIMULATION_INTERVAL_SEC", "5"))
SPIKE_PROBABILITY = float(os.getenv("SPIKE_PROBABILITY", "0.10"))

# Graceful termination flag
running = True

def handle_sigint(signum, frame):
    """Handle graceful shutdown on Ctrl+C."""
    global running
    print("\n[INFO] Termination signal received. Stopping simulator cleanly...")
    running = False

signal.signal(signal.SIGINT, handle_sigint)

def get_connection():
    """Establish and return a robust PostgreSQL connection."""
    while running:
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                connect_timeout=5
            )
            conn.autocommit = False
            return conn
        except psycopg2.OperationalError as err:
            print(f"[RECONNECT] Database unavailable ({err.args[0].strip()}). Retrying in 3 seconds...")
            time.sleep(3)
    return None

def fetch_active_stations(cursor):
    """Fetch all active stations with their latest observed readings."""
    cursor.execute("""
        SELECT 
            s.station_id,
            s.station_name,
            r.region_name,
            COALESCE(tr.temperature_c, 34.00) AS last_temp,
            COALESCE(tr.humidity_pct, 45.00) AS last_humidity,
            COALESCE(tr.wind_speed_kmh, 12.00) AS last_wind
        FROM weather_stations s
        JOIN regions r ON s.region_id = r.region_id
        LEFT JOIN LATERAL (
            SELECT temperature_c, humidity_pct, wind_speed_kmh
            FROM temperature_readings
            WHERE station_id = s.station_id
            ORDER BY recorded_at DESC
            LIMIT 1
        ) tr ON TRUE
        WHERE s.is_active = TRUE
        ORDER BY s.station_id;
    """)
    return cursor.fetchall()

def compute_random_walk(last_temp, last_hum, last_wind, is_coastal):
    """Generate next step with mean-reverting random walk and thermal spikes."""
    target_base = 31.0 if is_coastal else 37.0
    
    # 1. Stochastic jitter with mean reversion
    temp_delta = random.gauss(0, 0.35) - 0.05 * (last_temp - target_base)
    new_temp = round(last_temp + temp_delta, 2)

    # 2. Occasional heatwave thermal spike
    is_spike = random.random() < SPIKE_PROBABILITY
    if is_spike:
        spike_val = round(random.uniform(1.5, 3.5), 2)
        new_temp += spike_val

    # Clamp to realistic meteorological extremes
    new_temp = max(24.0, min(48.5, round(new_temp, 2)))

    # Humidity: Inversely correlated with temperature fluctuations
    hum_target = 70.0 if is_coastal else 35.0
    hum_delta = -0.5 * temp_delta + random.gauss(0, 0.8) - 0.05 * (last_hum - hum_target)
    new_hum = max(10.0, min(95.0, round(last_hum + hum_delta, 2)))

    # Wind speed: Gamma/Gaussian variation
    wind_delta = random.gauss(0, 1.2)
    new_wind = max(1.0, min(60.0, round(last_wind + wind_delta, 2)))

    return new_temp, new_hum, new_wind, is_spike

def run_simulation_loop():
    """Main execution loop for continuous data ingestion."""
    print("=================================================================")
    print("   HEATWAVE_DB: REAL-TIME SENSOR STREAM SIMULATOR (PYTHON 3.11)  ")
    print("=================================================================")
    print(f" Target: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f" Frequency: Every {INTERVAL_SEC} seconds | Press Ctrl+C to stop.")
    print("-----------------------------------------------------------------")

    conn = get_connection()
    if not conn:
        return

    # In-memory station state tracker
    station_state = {}

    try:
        while running:
            batch_start = time.time()
            now = datetime.now()

            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Sync station list on first run or periodically
                    if not station_state:
                        stations = fetch_active_stations(cur)
                        for st in stations:
                            station_state[st["station_id"]] = {
                                "name": st["station_name"],
                                "region": st["region_name"],
                                "temp": float(st["last_temp"]),
                                "humidity": float(st["last_humidity"]),
                                "wind": float(st["last_wind"]),
                                "is_coastal": "Mumbai" in st["region_name"]
                            }

                    # Prepare and insert batch transaction
                    insert_query = """
                        INSERT INTO temperature_readings 
                            (station_id, recorded_at, temperature_c, humidity_pct, wind_speed_kmh)
                        VALUES (%s, %s, %s, %s, %s);
                    """
                    
                    batch_records = []
                    log_messages = []

                    for st_id, state in station_state.items():
                        new_temp, new_hum, new_wind, spiked = compute_random_walk(
                            state["temp"], state["humidity"], state["wind"], state["is_coastal"]
                        )
                        # Update current state
                        state["temp"] = new_temp
                        state["humidity"] = new_hum
                        state["wind"] = new_wind

                        batch_records.append((st_id, now, new_temp, new_hum, new_wind))
                        
                        spike_tag = " [HEAT SPIKE!]" if spiked else ""
                        log_messages.append(
                            f"  -> Station {st_id:02d} ({state['name'][:22]:<22}) | "
                            f"{new_temp:5.2f}°C | Hum: {new_hum:4.1f}% | Wind: {new_wind:4.1f} km/h{spike_tag}"
                        )

                    # Execute batch inside single transaction
                    cur.executemany(insert_query, batch_records)
                    conn.commit()

                    # Print clean operational logs
                    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Batch committed ({len(batch_records)} stations):")
                    for line in log_messages:
                        print(line)

            except (psycopg2.DatabaseError, psycopg2.OperationalError) as db_err:
                print(f"[ERROR] Transaction failed: {db_err}. Rolling back...")
                if conn:
                    conn.rollback()
                    conn.close()
                conn = get_connection()
                station_state.clear()
                continue

            # Sleep remaining interval duration
            elapsed = time.time() - batch_start
            sleep_duration = max(0.0, INTERVAL_SEC - elapsed)
            time.sleep(sleep_duration)

    finally:
        if conn and not conn.closed:
            conn.close()
            print("[INFO] PostgreSQL connection closed safely.")

if __name__ == "__main__":
    run_simulation_loop()
