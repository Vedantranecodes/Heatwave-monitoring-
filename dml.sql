-- =====================================================================
-- DATABASE: heatwave_db
-- STEP 2: DML DATA POPULATION, MANIPULATION, AND ADVANCED SQL
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. INSERT REGIONS (5 major Indian metropolitan/climate zones)
-- ---------------------------------------------------------------------
INSERT INTO regions (region_name, state, country, population) VALUES
('Delhi NCR', 'Delhi', 'India', 33000000),
('Nagpur', 'Maharashtra', 'India', 2900000),
('Ahmedabad', 'Gujarat', 'India', 8400000),
('Jaipur', 'Rajasthan', 'India', 4100000),
('Mumbai', 'Maharashtra', 'India', 21000000);

-- ---------------------------------------------------------------------
-- 2. INSERT WEATHER STATIONS (3 stations per region = 15 stations)
-- ---------------------------------------------------------------------
INSERT INTO weather_stations (region_id, station_name, latitude, longitude, elevation_m, installed_on, is_active) VALUES
-- Delhi NCR (Region 1)
(1, 'Safdarjung Observatory', 28.58330, 77.20000, 216.00, '2021-01-15', TRUE),
(2, 'Palam Airport Station', 28.56650, 77.10310, 237.00, '2021-03-20', TRUE),
(1, 'Lodhi Road AWS', 28.59120, 77.22700, 211.00, '2022-05-10', TRUE),

-- Nagpur (Region 2)
(2, 'Sonegaon Airport Met', 21.09220, 79.05830, 310.00, '2020-11-01', TRUE),
(2, 'Ramdaspeth Urban AWS', 21.13500, 79.07400, 315.00, '2022-02-18', TRUE),
(2, 'MIDC Hingna Industrial Station', 21.11000, 78.98000, 325.00, '2023-01-11', TRUE),

-- Ahmedabad (Region 3)
(3, 'Sabarmati Riverfront Met', 23.03300, 72.58000, 53.00, '2021-08-05', TRUE),
(3, 'Navrangpura Urban Station', 23.03650, 72.56110, 55.00, '2022-04-12', TRUE),
(3, 'Ahmedabad Airport AWS', 23.07340, 72.63470, 58.00, '2020-09-25', TRUE),

-- Jaipur (Region 4)
(4, 'Sanganer Airport Station', 26.82420, 75.81220, 385.00, '2021-06-14', TRUE),
(4, 'Amer Foothills AWS', 26.98550, 75.85070, 430.00, '2022-10-03', TRUE),
(4, 'Mansarovar City Met', 26.85300, 75.76000, 390.00, '2023-03-01', TRUE),

-- Mumbai (Region 5)
(5, 'Colaba Coastal Observatory', 18.90670, 72.81470, 11.00, '2020-01-10', TRUE),
(5, 'Santacruz Suburban AWS', 19.08960, 72.86560, 14.00, '2020-01-10', TRUE),
(5, 'Powai Lake Agro-Urban Met', 19.12900, 72.90500, 45.00, '2022-11-20', TRUE);

-- Fix Delhi Palam region assignment (Station 2 to Region 1)
UPDATE weather_stations SET region_id = 1 WHERE station_name = 'Palam Airport Station';

-- ---------------------------------------------------------------------
-- 3. INSERT HEATWAVE THRESHOLDS (IMD Standards & Regional Sensitivities)
-- ---------------------------------------------------------------------
INSERT INTO heatwave_thresholds (region_id, watch_temp_c, warning_temp_c, severe_temp_c, min_consecutive_days) VALUES
(1, 40.00, 43.00, 45.00, 2), -- Delhi
(2, 41.00, 44.00, 46.50, 2), -- Nagpur (Central India hot spot)
(3, 40.50, 43.50, 45.50, 2), -- Ahmedabad
(4, 41.00, 44.00, 46.50, 2), -- Jaipur (Desert climate)
(5, 35.00, 37.00, 39.00, 2); -- Mumbai (Coastal threshold criteria is lower due to humidity)

-- ---------------------------------------------------------------------
-- 4. BULK INSERT REALISTIC 30-DAY HOURLY READINGS VIA generate_series()
-- ---------------------------------------------------------------------
-- Generates 30 days * 24 hours = 720 readings per station (10,800+ total rows)
-- Simulates daily solar curve, coastal vs inland differences, and 43C-46C heat spikes
INSERT INTO temperature_readings (station_id, recorded_at, temperature_c, humidity_pct, wind_speed_kmh, heat_index_c)
WITH time_series AS (
    SELECT generate_series(
        DATE_TRUNC('hour', CURRENT_TIMESTAMP - INTERVAL '30 days'),
        DATE_TRUNC('hour', CURRENT_TIMESTAMP),
        INTERVAL '1 hour'
    ) AS ts
),
computed_readings AS (
    SELECT 
        s.station_id,
        ts.ts AS recorded_at,
        ROUND((
            -- Base temperature by region
            CASE 
                WHEN s.region_id = 5 THEN 31.0 -- Mumbai (coastal moderate)
                WHEN s.region_id = 2 THEN 36.5 -- Nagpur (intense heat)
                WHEN s.region_id = 4 THEN 36.0 -- Jaipur
                WHEN s.region_id = 1 THEN 35.5 -- Delhi
                ELSE 35.0                      -- Ahmedabad
            END
            -- Diurnal curve: peaks at 14:00 (2 PM), coolest at 05:00 (5 AM)
            + 6.5 * SIN(RADIANS((EXTRACT(HOUR FROM ts.ts) - 8) * 15))
            -- Heatwave spike simulation during days 18 to 24
            + CASE 
                WHEN EXTRACT(DAY FROM ts.ts) BETWEEN 18 AND 24 AND s.region_id IN (1, 2, 3, 4) 
                THEN (4.5 + RANDOM() * 3.5)
                ELSE 0.0 
              END
            -- Random micro-fluctuation
            + (RANDOM() * 2.0 - 1.0)
        )::numeric, 2) AS temp,
        ROUND((
            -- Humidity inversely related to heat
            CASE 
                WHEN s.region_id = 5 THEN (65.0 + RANDOM() * 20.0) -- Mumbai high humidity
                ELSE (22.0 + RANDOM() * 28.0)                      -- Inland drier
            END
        )::numeric, 2) AS hum,
        ROUND((5.0 + RANDOM() * 22.0)::numeric, 2) AS wind
    FROM weather_stations s
    CROSS JOIN time_series ts
    WHERE s.is_active = TRUE
)
SELECT 
    station_id,
    recorded_at,
    temp AS temperature_c,
    hum AS humidity_pct,
    wind AS wind_speed_kmh,
    -- Heat Index calculation (apparent temperature)
    ROUND((temp + 0.33 * (hum / 100.0 * 6.105 * EXP((17.27 * temp) / (237.7 + temp))) - 0.70 * wind - 4.00)::numeric, 2) AS heat_index_c
FROM computed_readings;

-- ---------------------------------------------------------------------
-- 5. INSERT HISTORICAL & RECENT HEATWAVE EVENTS
-- ---------------------------------------------------------------------
INSERT INTO heatwave_events (region_id, start_date, end_date, max_temp_c, severity, status) VALUES
(2, CURRENT_DATE - INTERVAL '12 days', CURRENT_DATE - INTERVAL '8 days', 46.20, 'Severe', 'Resolved'),
(1, CURRENT_DATE - INTERVAL '10 days', CURRENT_DATE - INTERVAL '6 days', 44.80, 'Warning', 'Resolved'),
(4, CURRENT_DATE - INTERVAL '5 days', NULL, 45.10, 'Warning', 'Active'),
(3, CURRENT_DATE - INTERVAL '3 days', NULL, 43.60, 'Watch', 'Active');

-- ---------------------------------------------------------------------
-- 6. INSERT ALERTS
-- ---------------------------------------------------------------------
INSERT INTO alerts (region_id, alert_level, message, created_at, is_resolved) VALUES
(2, 'Severe', 'Red Alert: Extreme heatwave conditions (>45°C) recorded across Nagpur urban stations.', CURRENT_TIMESTAMP - INTERVAL '10 days', TRUE),
(1, 'Warning', 'Orange Alert: High temperatures forecasted above 43°C in Delhi NCR. Stay hydrated.', CURRENT_TIMESTAMP - INTERVAL '8 days', TRUE),
(4, 'Warning', 'Orange Alert: Continuous heatwave conditions exceeding 44°C in Jaipur.', CURRENT_TIMESTAMP - INTERVAL '2 days', FALSE),
(3, 'Watch', 'Yellow Alert: Heat index approaching critical threshold in Ahmedabad.', CURRENT_TIMESTAMP - INTERVAL '12 hours', FALSE);

-- ---------------------------------------------------------------------
-- 7. INSERT ALERT SUBSCRIBERS
-- ---------------------------------------------------------------------
INSERT INTO alert_subscribers (region_id, name, email, phone) VALUES
(1, 'Amit Sharma', 'amit.sharma@delhi-disaster.gov.in', '+919811001122'),
(2, 'Dr. Priya Patil', 'dr.priya@nagpurhealth.org', '+919822003344'),
(3, 'Rajesh Patel', 'rajesh.patel@ahmedabad-corp.in', '+919879005566'),
(4, 'Sanjay Singh', 'sanjay.singh@jaipur-relief.gov.in', '+919414007788'),
(5, 'Neha Mehta', 'neha.mehta@mumbai-coastal.org', '+919820009900');

-- ---------------------------------------------------------------------
-- 8. DML DEMONSTRATIONS: UPDATE STATEMENTS
-- ---------------------------------------------------------------------

-- Example 1: Sensor recalibration correction (updates faulty reading reading)
UPDATE temperature_readings
SET temperature_c = 43.50,
    heat_index_c = 47.10
WHERE station_id = 1 
  AND recorded_at = DATE_TRUNC('hour', CURRENT_TIMESTAMP - INTERVAL '24 hours');

-- Example 2: Operational alert resolution (mark active alert as resolved)
UPDATE alerts
SET is_resolved = TRUE
WHERE region_id = 3
  AND is_resolved = FALSE
  AND created_at < CURRENT_TIMESTAMP - INTERVAL '6 hours';

-- ---------------------------------------------------------------------
-- 9. DML DEMONSTRATION: DELETE STATEMENT
-- ---------------------------------------------------------------------

-- Temporary dummy inactive station to demonstrate safe deletion
INSERT INTO weather_stations (region_id, station_name, latitude, longitude, elevation_m, installed_on, is_active)
VALUES (1, 'Decommissioned Old Palam Post', 28.56000, 77.10000, 230.00, '2015-01-01', FALSE);

-- Example 3: Delete decommissioned station with WHERE clause
DELETE FROM weather_stations
WHERE is_active = FALSE
  AND station_name = 'Decommissioned Old Palam Post';

-- ---------------------------------------------------------------------
-- 10. ADVANCED DML: INSERT ... RETURNING
-- ---------------------------------------------------------------------
-- Returns the auto-generated primary key and calculated heat index instantly
INSERT INTO temperature_readings (station_id, recorded_at, temperature_c, humidity_pct, wind_speed_kmh, heat_index_c)
VALUES (4, CURRENT_TIMESTAMP, 44.50, 28.00, 14.50, 48.20)
RETURNING reading_id, station_id, temperature_c, heat_index_c, recorded_at;

-- ---------------------------------------------------------------------
-- 11. ADVANCED DML: ON CONFLICT DO UPDATE (UPSERT)
-- ---------------------------------------------------------------------
-- Upsert subscriber details: if email exists, update phone and region instead of failing
INSERT INTO alert_subscribers (region_id, name, email, phone)
VALUES (2, 'Dr. Priya Patil', 'dr.priya@nagpurhealth.org', '+919999988888')
ON CONFLICT (email) 
DO UPDATE SET 
    phone = EXCLUDED.phone,
    region_id = EXCLUDED.region_id;
