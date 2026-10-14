
DROP TABLE IF EXISTS alert_subscribers CASCADE;
DROP TABLE IF EXISTS alerts CASCADE;
DROP TABLE IF EXISTS predictions CASCADE;
DROP TABLE IF EXISTS heatwave_events CASCADE;
DROP TABLE IF EXISTS heatwave_thresholds CASCADE;
DROP TABLE IF EXISTS temperature_readings CASCADE;
DROP TABLE IF EXISTS weather_stations CASCADE;
DROP TABLE IF EXISTS regions CASCADE;


CREATE TABLE regions (
    region_id SERIAL PRIMARY KEY,
    region_name VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL DEFAULT 'India',
    population BIGINT CHECK (population >= 0),
    CONSTRAINT uq_region_state UNIQUE (region_name, state)
);

-- Table: weather_stations
CREATE TABLE weather_stations (
    station_id SERIAL PRIMARY KEY,
    region_id INT NOT NULL,
    station_name VARCHAR(120) NOT NULL UNIQUE,
    latitude NUMERIC(8, 5) NOT NULL CHECK (latitude BETWEEN -90.00000 AND 90.00000),
    longitude NUMERIC(8, 5) NOT NULL CHECK (longitude BETWEEN -180.00000 AND 180.00000),
    elevation_m NUMERIC(6, 2) CHECK (elevation_m >= -500.00),
    installed_on DATE NOT NULL DEFAULT CURRENT_DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_stations_region FOREIGN KEY (region_id)
        REFERENCES regions(region_id) ON DELETE CASCADE
);

-- Table: temperature_readings
CREATE TABLE temperature_readings (
    reading_id BIGSERIAL PRIMARY KEY,
    station_id INT NOT NULL,
    recorded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    temperature_c NUMERIC(5, 2) NOT NULL CHECK (temperature_c BETWEEN -20.00 AND 65.00),
    humidity_pct NUMERIC(5, 2) NOT NULL CHECK (humidity_pct BETWEEN 0.00 AND 100.00),
    wind_speed_kmh NUMERIC(5, 2) NOT NULL DEFAULT 0.00 CHECK (wind_speed_kmh >= 0.00),
    heat_index_c NUMERIC(5, 2),
    CONSTRAINT fk_readings_station FOREIGN KEY (station_id)
        REFERENCES weather_stations(station_id) ON DELETE CASCADE
);

-- Table: heatwave_thresholds
CREATE TABLE heatwave_thresholds (
    threshold_id SERIAL PRIMARY KEY,
    region_id INT NOT NULL UNIQUE,
    watch_temp_c NUMERIC(5, 2) NOT NULL CHECK (watch_temp_c > 0.00),
    warning_temp_c NUMERIC(5, 2) NOT NULL CHECK (warning_temp_c >= watch_temp_c),
    severe_temp_c NUMERIC(5, 2) NOT NULL CHECK (severe_temp_c >= warning_temp_c),
    min_consecutive_days INT NOT NULL DEFAULT 2 CHECK (min_consecutive_days >= 1),
    CONSTRAINT fk_thresholds_region FOREIGN KEY (region_id)
        REFERENCES regions(region_id) ON DELETE CASCADE
);

-- Table: heatwave_events
CREATE TABLE heatwave_events (
    event_id SERIAL PRIMARY KEY,
    region_id INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    max_temp_c NUMERIC(5, 2) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('Normal', 'Watch', 'Warning', 'Severe')),
    status VARCHAR(20) NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Resolved')),
    CONSTRAINT fk_events_region FOREIGN KEY (region_id)
        REFERENCES regions(region_id) ON DELETE CASCADE,
    CONSTRAINT chk_event_date_range CHECK (end_date IS NULL OR end_date >= start_date)
);

-- Table: predictions
CREATE TABLE predictions (
    prediction_id SERIAL PRIMARY KEY,
    region_id INT NOT NULL,
    predicted_for DATE NOT NULL,
    predicted_temp_c NUMERIC(5, 2) NOT NULL,
    risk_level VARCHAR(20) NOT NULL CHECK (risk_level IN ('Normal', 'Watch', 'Warning', 'Severe')),
    model_name VARCHAR(50) NOT NULL DEFAULT 'RandomForestRegressor_v1',
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_predictions_region FOREIGN KEY (region_id)
        REFERENCES regions(region_id) ON DELETE CASCADE
);

-- Table: alerts
CREATE TABLE alerts (
    alert_id SERIAL PRIMARY KEY,
    region_id INT NOT NULL,
    alert_level VARCHAR(20) NOT NULL CHECK (alert_level IN ('Watch', 'Warning', 'Severe')),
    message TEXT NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_alerts_region FOREIGN KEY (region_id)
        REFERENCES regions(region_id) ON DELETE CASCADE
);

-- Table: alert_subscribers
CREATE TABLE alert_subscribers (
    subscriber_id SERIAL PRIMARY KEY,
    region_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    phone VARCHAR(20),
    CONSTRAINT fk_subscribers_region FOREIGN KEY (region_id)
        REFERENCES regions(region_id) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- 3. INDEXES FOR PERFORMANCE OPTIMIZATION
-- ---------------------------------------------------------------------

-- High-frequency composite index on streaming readings
CREATE INDEX idx_readings_station_recorded_at 
ON temperature_readings(station_id, recorded_at DESC);

-- Foreign key lookup indexes for fast joins across regions
CREATE INDEX idx_stations_region_id ON weather_stations(region_id);
CREATE INDEX idx_events_region_id ON heatwave_events(region_id);
CREATE INDEX idx_predictions_region_id ON predictions(region_id);
CREATE INDEX idx_alerts_region_id ON alerts(region_id);
CREATE INDEX idx_subscribers_region_id ON alert_subscribers(region_id);

-- ---------------------------------------------------------------------
-- 4. ALTER TABLE DEMONSTRATION EXAMPLES
-- ---------------------------------------------------------------------

-- Example: Add an optional description column to regions
ALTER TABLE regions 
ADD COLUMN IF NOT EXISTS climate_zone VARCHAR(50) DEFAULT 'Subtropical';

-- Example: Add index on predictions date lookup
ALTER TABLE predictions 
ADD CONSTRAINT chk_pred_temp CHECK (predicted_temp_c BETWEEN -20.00 AND 65.00);

-- ---------------------------------------------------------------------
-- 5. TRUNCATE EXAMPLE (Demonstration for resetting staging data)
-- ---------------------------------------------------------------------
-- TRUNCATE TABLE temperature_readings, alerts, predictions RESTART IDENTITY CASCADE;
