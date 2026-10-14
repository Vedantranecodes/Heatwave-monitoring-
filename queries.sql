-- =====================================================================
-- DATABASE: heatwave_db
-- STEP 3: ANALYTICAL & ADVANCED SQL QUERIES (1 TO 15)
-- =====================================================================

-- ---------------------------------------------------------------------
-- QUERY 1: Basic SELECT with WHERE, ORDER BY, LIMIT
-- Purpose: Retrieve the top 10 highest recorded temperatures in the system.
-- ---------------------------------------------------------------------
SELECT reading_id, station_id, recorded_at, temperature_c, heat_index_c
FROM temperature_readings
WHERE temperature_c >= 40.00
ORDER BY temperature_c DESC, recorded_at DESC
LIMIT 10;

-- ---------------------------------------------------------------------
-- QUERY 2: Compound Filtering and String Matching
-- Purpose: Find all active stations in Maharashtra with elevation > 15m.
-- ---------------------------------------------------------------------
SELECT s.station_id, s.station_name, r.region_name, r.state, s.elevation_m
FROM weather_stations s
JOIN regions r ON s.region_id = r.region_id
WHERE r.state = 'Maharashtra' 
  AND s.is_active = TRUE 
  AND s.elevation_m > 15.00
ORDER BY s.elevation_m DESC;

-- ---------------------------------------------------------------------
-- QUERY 3: Aggregates with GROUP BY
-- Purpose: Calculate summary statistics (min, avg, max, count) per station.
-- ---------------------------------------------------------------------
SELECT 
    s.station_id,
    s.station_name,
    COUNT(r.reading_id) AS total_readings,
    ROUND(MIN(r.temperature_c), 2) AS min_temp,
    ROUND(AVG(r.temperature_c), 2) AS avg_temp,
    ROUND(MAX(r.temperature_c), 2) AS max_temp,
    ROUND(AVG(r.humidity_pct), 2) AS avg_humidity
FROM weather_stations s
JOIN temperature_readings r ON s.station_id = r.station_id
GROUP BY s.station_id, s.station_name
ORDER BY avg_temp DESC;

-- ---------------------------------------------------------------------
-- QUERY 4: Aggregates with HAVING Clause
-- Purpose: Find stations where average daytime temperature exceeds 36°C.
-- ---------------------------------------------------------------------
SELECT 
    s.station_name,
    COUNT(r.reading_id) AS readings_count,
    ROUND(AVG(r.temperature_c), 2) AS avg_day_temp
FROM weather_stations s
JOIN temperature_readings r ON s.station_id = r.station_id
WHERE EXTRACT(HOUR FROM r.recorded_at) BETWEEN 10 AND 18
GROUP BY s.station_name
HAVING AVG(r.temperature_c) > 36.00
ORDER BY avg_day_temp DESC;

-- ---------------------------------------------------------------------
-- QUERY 5: INNER JOIN across 3 Tables
-- Purpose: Join readings, stations, and regions with regional thresholds.
-- ---------------------------------------------------------------------
SELECT 
    reg.region_name,
    st.station_name,
    rd.recorded_at,
    rd.temperature_c,
    th.warning_temp_c,
    th.severe_temp_c
FROM temperature_readings rd
INNER JOIN weather_stations st ON rd.station_id = st.station_id
INNER JOIN regions reg ON st.region_id = reg.region_id
INNER JOIN heatwave_thresholds th ON reg.region_id = th.region_id
WHERE rd.temperature_c >= th.warning_temp_c
ORDER BY rd.recorded_at DESC
LIMIT 15;

-- ---------------------------------------------------------------------
-- QUERY 6: LEFT OUTER JOIN
-- Purpose: List all regions and their active alerts, including regions with 0 alerts.
-- ---------------------------------------------------------------------
SELECT 
    r.region_id,
    r.region_name,
    r.state,
    COUNT(a.alert_id) AS total_active_alerts,
    COALESCE(MAX(a.alert_level), 'None') AS highest_active_level
FROM regions r
LEFT JOIN alerts a ON r.region_id = a.region_id AND a.is_resolved = FALSE
GROUP BY r.region_id, r.region_name, r.state
ORDER BY total_active_alerts DESC, r.region_name ASC;

-- ---------------------------------------------------------------------
-- QUERY 7: Multi-table Aggregation with Subscriber Metrics
-- Purpose: Correlate region population, subscriber count, and event count.
-- ---------------------------------------------------------------------
SELECT 
    r.region_name,
    r.population,
    COUNT(DISTINCT s.subscriber_id) AS registered_subscribers,
    COUNT(DISTINCT e.event_id) AS recorded_heatwave_events,
    COALESCE(MAX(e.max_temp_c), 0.00) AS historical_peak_c
FROM regions r
LEFT JOIN alert_subscribers s ON r.region_id = s.region_id
LEFT JOIN heatwave_events e ON r.region_id = e.region_id
GROUP BY r.region_id, r.region_name, r.population
ORDER BY registered_subscribers DESC;

-- ---------------------------------------------------------------------
-- QUERY 8: Subquery in WHERE (National 95th Percentile Outliers)
-- Purpose: Identify readings that fall strictly in the top 5% hottest readings nationally.
-- ---------------------------------------------------------------------
SELECT 
    r.reading_id,
    s.station_name,
    r.recorded_at,
    r.temperature_c
FROM temperature_readings r
JOIN weather_stations s ON r.station_id = s.station_id
WHERE r.temperature_c > (
    SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY temperature_c)
    FROM temperature_readings
)
ORDER BY r.temperature_c DESC
LIMIT 20;

-- ---------------------------------------------------------------------
-- QUERY 9: Correlated Subquery & Threshold Breach Check
-- Purpose: Find stations whose max temperature breached their region's severe threshold.
-- ---------------------------------------------------------------------
SELECT 
    s.station_id,
    s.station_name,
    r.region_name,
    (SELECT MAX(temperature_c) FROM temperature_readings WHERE station_id = s.station_id) AS peak_temp,
    th.severe_temp_c
FROM weather_stations s
JOIN regions r ON s.region_id = r.region_id
JOIN heatwave_thresholds th ON r.region_id = th.region_id
WHERE (
    SELECT MAX(temperature_c) 
    FROM temperature_readings 
    WHERE station_id = s.station_id
) >= th.severe_temp_c
ORDER BY peak_temp DESC;

-- ---------------------------------------------------------------------
-- QUERY 10: Common Table Expression (CTE) for Daily Diurnal Swings
-- Purpose: Calculate the diurnal range (max - min) per station per day.
-- ---------------------------------------------------------------------
WITH daily_metrics AS (
    SELECT 
        station_id,
        DATE(recorded_at) AS reading_date,
        MIN(temperature_c) AS min_t,
        MAX(temperature_c) AS max_t,
        AVG(humidity_pct) AS avg_h
    FROM temperature_readings
    GROUP BY station_id, DATE(recorded_at)
)
SELECT 
    s.station_name,
    dm.reading_date,
    dm.min_t,
    dm.max_t,
    ROUND((dm.max_t - dm.min_t)::numeric, 2) AS diurnal_range_c
FROM daily_metrics dm
JOIN weather_stations s ON dm.station_id = s.station_id
WHERE (dm.max_t - dm.min_t) >= 12.00
ORDER BY diurnal_range_c DESC
LIMIT 15;

-- ---------------------------------------------------------------------
-- QUERY 11: Window Function - 7-Day Moving Average
-- Purpose: Compute rolling 7-day average temperature per station over daily averages.
-- ---------------------------------------------------------------------
WITH daily_station_avg AS (
    SELECT 
        station_id,
        DATE(recorded_at) AS obs_date,
        ROUND(AVG(temperature_c), 2) AS daily_avg_temp
    FROM temperature_readings
    GROUP BY station_id, DATE(recorded_at)
)
SELECT 
    s.station_name,
    dsa.obs_date,
    dsa.daily_avg_temp,
    ROUND(
        AVG(dsa.daily_avg_temp) OVER (
            PARTITION BY dsa.station_id 
            ORDER BY dsa.obs_date 
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        )::numeric, 2
    ) AS rolling_7day_avg_c
FROM daily_station_avg dsa
JOIN weather_stations s ON dsa.station_id = s.station_id
ORDER BY s.station_name, dsa.obs_date DESC
LIMIT 20;

-- ---------------------------------------------------------------------
-- QUERY 12: Window Function - DENSE_RANK() of Hottest Regions
-- Purpose: Rank regions by peak recorded temperature in the last 30 days.
-- ---------------------------------------------------------------------
WITH regional_peaks AS (
    SELECT 
        reg.region_id,
        reg.region_name,
        MAX(tr.temperature_c) AS peak_temp,
        MAX(tr.heat_index_c) AS peak_heat_index
    FROM regions reg
    JOIN weather_stations ws ON reg.region_id = ws.region_id
    JOIN temperature_readings tr ON ws.station_id = tr.station_id
    GROUP BY reg.region_id, reg.region_name
)
SELECT 
    region_name,
    peak_temp,
    peak_heat_index,
    DENSE_RANK() OVER (ORDER BY peak_temp DESC) AS heat_rank
FROM regional_peaks
ORDER BY heat_rank ASC;

-- ---------------------------------------------------------------------
-- QUERY 13: Window Function - LAG() for Day-Over-Day Change
-- Purpose: Compute day-over-day peak temperature change to detect sudden heat waves.
-- ---------------------------------------------------------------------
WITH daily_peaks AS (
    SELECT 
        station_id,
        DATE(recorded_at) AS obs_date,
        MAX(temperature_c) AS daily_max_temp
    FROM temperature_readings
    GROUP BY station_id, DATE(recorded_at)
)
SELECT 
    ws.station_name,
    dp.obs_date,
    dp.daily_max_temp,
    LAG(dp.daily_max_temp, 1) OVER (
        PARTITION BY dp.station_id ORDER BY dp.obs_date
    ) AS prev_day_max_temp,
    ROUND((
        dp.daily_max_temp - LAG(dp.daily_max_temp, 1) OVER (
            PARTITION BY dp.station_id ORDER BY dp.obs_date
        )
    )::numeric, 2) AS dod_temp_change_c
FROM daily_peaks dp
JOIN weather_stations ws ON dp.station_id = ws.station_id
ORDER BY dod_temp_change_c DESC NULLS LAST
LIMIT 15;

-- ---------------------------------------------------------------------
-- QUERY 14: DISTINCT ON for Latest Station Readings
-- Purpose: Instantly retrieve the latest single reading per weather station.
-- ---------------------------------------------------------------------
SELECT DISTINCT ON (s.station_id)
    s.station_id,
    s.station_name,
    r.region_name,
    tr.recorded_at AS latest_reading_time,
    tr.temperature_c AS latest_temp,
    tr.humidity_pct AS latest_humidity,
    tr.heat_index_c AS latest_heat_index
FROM weather_stations s
JOIN regions r ON s.region_id = r.region_id
JOIN temperature_readings tr ON s.station_id = tr.station_id
ORDER BY s.station_id, tr.recorded_at DESC;

-- ---------------------------------------------------------------------
-- QUERY 15: Gaps-and-Islands CTE to Detect Consecutive Heatwave Days
-- Purpose: Detect streaks of consecutive days where daily max breached warning threshold.
-- ---------------------------------------------------------------------
WITH daily_max_temps AS (
    SELECT 
        s.region_id,
        DATE(tr.recorded_at) AS reading_date,
        MAX(tr.temperature_c) AS daily_max
    FROM weather_stations s
    JOIN temperature_readings tr ON s.station_id = tr.station_id
    GROUP BY s.region_id, DATE(tr.recorded_at)
),
breached_days AS (
    SELECT 
        d.region_id,
        d.reading_date,
        d.daily_max,
        th.warning_temp_c,
        -- Islands technique: grouping consecutive dates by subtracting row sequence
        d.reading_date - (ROW_NUMBER() OVER (PARTITION BY d.region_id ORDER BY d.reading_date))::int AS island_grp
    FROM daily_max_temps d
    JOIN heatwave_thresholds th ON d.region_id = th.region_id
    WHERE d.daily_max >= th.warning_temp_c
)
SELECT 
    r.region_name,
    MIN(b.reading_date) AS streak_start,
    MAX(b.reading_date) AS streak_end,
    COUNT(*) AS consecutive_days,
    MAX(b.daily_max) AS streak_peak_temp,
    MAX(b.warning_temp_c) AS regional_threshold
FROM breached_days b
JOIN regions r ON b.region_id = r.region_id
GROUP BY r.region_name, b.island_grp
HAVING COUNT(*) >= 2
ORDER BY consecutive_days DESC, streak_start DESC;
