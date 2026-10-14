-- =====================================================================
-- DATABASE: heatwave_db
-- STEP 4: ADVANCED DATABASE OBJECTS (VIEWS, FUNCTIONS, TRIGGERS, TCL, RBAC)
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. VIEW: v_live_status
-- Purpose: Real-time dashboard view with latest reading and dynamic risk status.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_live_status AS
SELECT DISTINCT ON (s.station_id)
    s.station_id,
    s.station_name,
    s.latitude,
    s.longitude,
    s.elevation_m,
    r.region_id,
    r.region_name,
    r.state,
    tr.reading_id,
    tr.recorded_at,
    tr.temperature_c,
    tr.humidity_pct,
    tr.wind_speed_kmh,
    tr.heat_index_c,
    th.watch_temp_c,
    th.warning_temp_c,
    th.severe_temp_c,
    CASE 
        WHEN tr.temperature_c >= th.severe_temp_c THEN 'Severe'
        WHEN tr.temperature_c >= th.warning_temp_c THEN 'Warning'
        WHEN tr.temperature_c >= th.watch_temp_c THEN 'Watch'
        ELSE 'Normal'
    END AS risk_level
FROM weather_stations s
JOIN regions r ON s.region_id = r.region_id
LEFT JOIN heatwave_thresholds th ON r.region_id = th.region_id
LEFT JOIN temperature_readings tr ON s.station_id = tr.station_id
WHERE s.is_active = TRUE
ORDER BY s.station_id, tr.recorded_at DESC;

-- ---------------------------------------------------------------------
-- 2. VIEW: v_region_daily_summary
-- Purpose: Aggregated historical daily trends per region for charting.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_region_daily_summary AS
SELECT 
    r.region_id,
    r.region_name,
    DATE(tr.recorded_at) AS reading_date,
    COUNT(tr.reading_id) AS total_readings,
    ROUND(MIN(tr.temperature_c), 2) AS min_temp_c,
    ROUND(AVG(tr.temperature_c), 2) AS avg_temp_c,
    ROUND(MAX(tr.temperature_c), 2) AS max_temp_c,
    ROUND(AVG(tr.humidity_pct), 2) AS avg_humidity_pct,
    ROUND(MAX(tr.heat_index_c), 2) AS max_heat_index_c
FROM regions r
JOIN weather_stations s ON r.region_id = s.region_id
JOIN temperature_readings tr ON s.station_id = tr.station_id
GROUP BY r.region_id, r.region_name, DATE(tr.recorded_at)
ORDER BY reading_date DESC, r.region_name ASC;

-- ---------------------------------------------------------------------
-- 3. FUNCTION: calc_heat_index(temp_c, humidity_pct)
-- Purpose: Computes Rothfusz/Steadman Apparent Temperature in Celsius.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION calc_heat_index(
    temp_c NUMERIC, 
    humidity_pct NUMERIC
) 
RETURNS NUMERIC AS $$
DECLARE
    vapor_pressure NUMERIC;
    calculated_hi NUMERIC;
BEGIN
    -- Below 26°C, physiological heat stress is negligible; return raw temp
    IF temp_c < 26.0 THEN
        RETURN ROUND(temp_c, 2);
    END IF;

    -- Standard Steadman / Australian Apparent Temperature formula (metric)
    vapor_pressure := (humidity_pct / 100.0) * 6.105 * EXP((17.27 * temp_c) / (237.7 + temp_c));
    calculated_hi := temp_c + (0.33 * vapor_pressure) - 4.00;

    -- Return higher of actual temp or computed apparent heat index
    RETURN ROUND(GREATEST(temp_c, calculated_hi), 2);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- ---------------------------------------------------------------------
-- 4. TRIGGER 1: BEFORE INSERT ON temperature_readings
-- Purpose: Automatically calculate and assign heat_index_c if missing.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_fn_auto_heat_index()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.heat_index_c IS NULL THEN
        NEW.heat_index_c := calc_heat_index(NEW.temperature_c, NEW.humidity_pct);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_auto_heat_index ON temperature_readings;
CREATE TRIGGER trg_auto_heat_index
BEFORE INSERT ON temperature_readings
FOR EACH ROW
EXECUTE FUNCTION trg_fn_auto_heat_index();

-- ---------------------------------------------------------------------
-- 5. TRIGGER 2: AFTER INSERT ON temperature_readings
-- Purpose: Threshold alert generation and real-time pg_notify publication.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_fn_threshold_alert_notify()
RETURNS TRIGGER AS $$
DECLARE
    v_region_id INT;
    v_region_name VARCHAR(100);
    v_station_name VARCHAR(120);
    v_warning_temp NUMERIC(5,2);
    v_severe_temp NUMERIC(5,2);
    v_current_level VARCHAR(20) := NULL;
    v_existing_alert_count INT;
    v_payload JSON;
BEGIN
    -- Retrieve regional threshold configuration
    SELECT s.region_id, s.station_name, r.region_name, th.warning_temp_c, th.severe_temp_c
    INTO v_region_id, v_station_name, v_region_name, v_warning_temp, v_severe_temp
    FROM weather_stations s
    JOIN regions r ON s.region_id = r.region_id
    LEFT JOIN heatwave_thresholds th ON r.region_id = th.region_id
    WHERE s.station_id = NEW.station_id;

    -- Check if warning or severe thresholds are breached
    IF NEW.temperature_c >= v_severe_temp THEN
        v_current_level := 'Severe';
    ELSIF NEW.temperature_c >= v_warning_temp THEN
        v_current_level := 'Warning';
    END IF;

    -- Process alert insertion if an alert condition is met
    IF v_current_level IS NOT NULL THEN
        -- Prevent duplicate open alerts for the same region within the past 6 hours
        SELECT COUNT(*)
        INTO v_existing_alert_count
        FROM alerts
        WHERE region_id = v_region_id
          AND is_resolved = FALSE
          AND alert_level = v_current_level
          AND created_at > (CURRENT_TIMESTAMP - INTERVAL '6 hours');

        IF v_existing_alert_count = 0 THEN
            INSERT INTO alerts (region_id, alert_level, message, created_at, is_resolved)
            VALUES (
                v_region_id,
                v_current_level,
                FORMAT('Heatwave Alert [%s]: %s recorded %s°C (Heat Index %s°C) at %s.',
                       v_current_level, v_station_name, NEW.temperature_c, NEW.heat_index_c, NEW.recorded_at),
                CURRENT_TIMESTAMP,
                FALSE
            );
        END IF;
    END IF;

    -- Publish real-time event to PostgreSQL NOTIFY bus
    v_payload := json_build_object(
        'event', 'NEW_READING',
        'reading_id', NEW.reading_id,
        'station_id', NEW.station_id,
        'station_name', v_station_name,
        'region_id', v_region_id,
        'region_name', v_region_name,
        'temperature_c', NEW.temperature_c,
        'humidity_pct', NEW.humidity_pct,
        'heat_index_c', NEW.heat_index_c,
        'recorded_at', NEW.recorded_at,
        'alert_triggered', v_current_level
    );

    PERFORM pg_notify('heatwave_channel', v_payload::text);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_threshold_alert_notify ON temperature_readings;
CREATE TRIGGER trg_threshold_alert_notify
AFTER INSERT ON temperature_readings
FOR EACH ROW
EXECUTE FUNCTION trg_fn_threshold_alert_notify();

-- ---------------------------------------------------------------------
-- 6. TRANSACTION CONTROL LANGUAGE (TCL) DEMONSTRATION
-- Purpose: Demonstrates ATOMIC batch insertion with SAVEPOINT & partial ROLLBACK.
-- ---------------------------------------------------------------------
DO $$
BEGIN
    -- Step A: Start implicit transaction block
    -- Insert a valid batch reading
    INSERT INTO temperature_readings (station_id, recorded_at, temperature_c, humidity_pct, wind_speed_kmh)
    VALUES (1, CURRENT_TIMESTAMP, 41.20, 35.00, 12.00);

    -- Step B: Establish a savepoint before a risky operation
    SAVEPOINT sp_batch_checkpoint;

    BEGIN
        -- Intentionally insert an invalid row violating CHECK constraint (humidity > 100)
        INSERT INTO temperature_readings (station_id, recorded_at, temperature_c, humidity_pct, wind_speed_kmh)
        VALUES (1, CURRENT_TIMESTAMP, 55.00, 150.00, 10.00);
    EXCEPTION WHEN check_violation THEN
        -- Step C: Rollback to savepoint safely without losing prior valid row
        RAISE NOTICE 'Invalid reading caught. Rolling back to sp_batch_checkpoint.';
        ROLLBACK TO sp_batch_checkpoint;
    END;

    -- Step D: Insert another valid reading
    INSERT INTO temperature_readings (station_id, recorded_at, temperature_c, humidity_pct, wind_speed_kmh)
    VALUES (2, CURRENT_TIMESTAMP, 42.10, 30.00, 15.00);

    -- Transaction commits successfully at the end of the DO block
    RAISE NOTICE 'TCL Batch operation completed successfully.';
END $$;

-- ---------------------------------------------------------------------
-- 7. ROLE-BASED ACCESS CONTROL (RBAC): GRANT & REVOKE
-- Purpose: Security roles for Dashboard (Read-Only) and Ingestion Pipeline (Data Writer).
-- ---------------------------------------------------------------------

-- Create roles if they don't already exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'dashboard_reader') THEN
        CREATE ROLE dashboard_reader WITH LOGIN PASSWORD 'ReaderPass_2026!';
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'data_writer') THEN
        CREATE ROLE data_writer WITH LOGIN PASSWORD 'WriterPass_2026!';
    END IF;
END $$;

-- Dashboard Reader: Read-only access to tables, views, and execution of calc function
GRANT CONNECT ON DATABASE heatwave_db TO dashboard_reader;
GRANT USAGE ON SCHEMA public TO dashboard_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO dashboard_reader;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO dashboard_reader;
GRANT EXECUTE ON FUNCTION calc_heat_index(NUMERIC, NUMERIC) TO dashboard_reader;

-- Restrict dashboard reader from modifying data
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM dashboard_reader;

-- Data Writer: Append permissions for streaming sensor ingest
GRANT CONNECT ON DATABASE heatwave_db TO data_writer;
GRANT USAGE ON SCHEMA public TO data_writer;
GRANT INSERT, UPDATE ON TABLE temperature_readings TO data_writer;
GRANT USAGE, SELECT ON SEQUENCE temperature_readings_reading_id_seq TO data_writer;
GRANT USAGE, SELECT ON SEQUENCE alerts_alert_id_seq TO data_writer;
GRANT INSERT ON TABLE alerts TO data_writer;
