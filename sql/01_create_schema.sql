-- ============================================================================
-- FlightPulse - SQLite Relational Database DDL Schema
-- Script: sql/01_create_schema.sql
-- Description: Creates the staging table, dimension tables, airport code bridge,
--              and central fact table with integrity constraints and foreign keys.
-- Database Target: database/flightpulse.db
-- Specification: docs/database_design.md & docs/database_relationships.md
-- ============================================================================

-- Enforce foreign-key constraints on every connection
PRAGMA foreign_keys = ON;

-- ============================================================================
-- 1. RAW STAGING LAYER (Unmutated text landing mirror of flights.csv)
-- ============================================================================
-- Preserves all 31 original flight columns without transformation or data loss.
-- All 31 source columns are declared as TEXT to ensure pure string preservation
-- without premature type coercion, rounding, or float representations.
-- Only raw_id is INTEGER PRIMARY KEY AUTOINCREMENT for ingestion sequence tracking.
CREATE TABLE IF NOT EXISTS staging_flights_raw (
    raw_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    YEAR                    TEXT,
    MONTH                   TEXT,
    DAY                     TEXT,
    DAY_OF_WEEK             TEXT,
    AIRLINE                 TEXT,
    FLIGHT_NUMBER           TEXT,
    TAIL_NUMBER             TEXT,
    ORIGIN_AIRPORT          TEXT,
    DESTINATION_AIRPORT     TEXT,
    SCHEDULED_DEPARTURE     TEXT,
    DEPARTURE_TIME          TEXT,
    DEPARTURE_DELAY         TEXT,
    TAXI_OUT                TEXT,
    WHEELS_OFF              TEXT,
    SCHEDULED_TIME          TEXT,
    ELAPSED_TIME            TEXT,
    AIR_TIME                TEXT,
    DISTANCE                TEXT,
    WHEELS_ON               TEXT,
    TAXI_IN                 TEXT,
    SCHEDULED_ARRIVAL       TEXT,
    ARRIVAL_TIME            TEXT,
    ARRIVAL_DELAY           TEXT,
    DIVERTED                TEXT,
    CANCELLED               TEXT,
    CANCELLATION_REASON     TEXT,
    AIR_SYSTEM_DELAY        TEXT,
    SECURITY_DELAY          TEXT,
    AIRLINE_DELAY           TEXT,
    LATE_AIRCRAFT_DELAY     TEXT,
    WEATHER_DELAY           TEXT
);

-- ============================================================================
-- 2. DIMENSION TABLES
-- ============================================================================

-- 2.1 Operating Airlines Dimension (14 certified carriers)
CREATE TABLE IF NOT EXISTS dim_airlines (
    airline_code            TEXT PRIMARY KEY,
    airline_name            TEXT NOT NULL
);

-- 2.2 Commercial Airports Dimension (322 facilities)
-- Note: latitude and longitude are nullable; ECP, PBG, and UST remain NULL
-- until verified enrichment is performed.
CREATE TABLE IF NOT EXISTS dim_airports (
    airport_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    iata_code               TEXT NOT NULL UNIQUE,
    airport_name            TEXT NOT NULL,
    city                    TEXT NOT NULL,
    state                   TEXT NOT NULL,
    country                 TEXT NOT NULL DEFAULT 'USA',
    latitude                REAL,
    longitude               REAL
);

-- 2.3 Airport Code Cross-Reference Bridge Table
-- Reconciles 3-letter IATA codes and October 2015 5-digit DOT numeric IDs
-- to canonical airport_id. Populated with verified crosswalk data only.
CREATE TABLE IF NOT EXISTS map_airport_codes (
    raw_code                TEXT PRIMARY KEY,
    airport_id              INTEGER NOT NULL,
    code_type               TEXT NOT NULL CHECK (code_type IN ('IATA', 'DOT_ID')),
    FOREIGN KEY (airport_id) REFERENCES dim_airports(airport_id)
);

-- 2.4 Calendar Date Dimension (365 calendar days of 2015)
CREATE TABLE IF NOT EXISTS dim_dates (
    date_id                 INTEGER PRIMARY KEY, -- Format: YYYYMMDD (e.g. 20150101)
    full_date               TEXT NOT NULL UNIQUE, -- Format: YYYY-MM-DD
    year                    INTEGER NOT NULL CHECK (year = 2015),
    month                   INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
    day                     INTEGER NOT NULL CHECK (day BETWEEN 1 AND 31),
    day_of_week             INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
    day_name                TEXT NOT NULL,
    month_name              TEXT NOT NULL,
    is_weekend              INTEGER NOT NULL CHECK (is_weekend IN (0, 1)),
    quarter                 INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4)
);

-- 2.5 Cancellation Reasons Dimension (Official US DOT Form 234 categories)
CREATE TABLE IF NOT EXISTS dim_cancellation_reasons (
    reason_code             TEXT PRIMARY KEY,
    reason_description      TEXT NOT NULL,
    responsible_entity      TEXT NOT NULL
);

-- ============================================================================
-- 3. ANALYTICAL FACT LAYER
-- ============================================================================
-- Central transactional fact table containing all operational measures.
-- Source row lineage: source_row_id is NOT NULL and UNIQUE, referencing staging.
CREATE TABLE IF NOT EXISTS fact_flights (
    flight_id                           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_row_id                       INTEGER NOT NULL UNIQUE,
    date_id                             INTEGER NOT NULL,
    airline_code                        TEXT NOT NULL,
    flight_number                       TEXT NOT NULL,
    tail_number                         TEXT,
    origin_airport_id                   INTEGER NOT NULL,
    dest_airport_id                     INTEGER NOT NULL,
    
    -- Scheduled Departure
    scheduled_departure_raw             TEXT NOT NULL,
    scheduled_departure_time            TEXT NOT NULL,
    scheduled_departure_is_midnight     INTEGER NOT NULL DEFAULT 0,
    
    -- Actual Departure
    departure_time_raw                  TEXT,
    actual_departure_time               TEXT,
    departure_is_midnight               INTEGER,
    departure_delay_min                 REAL,
    
    -- Ground Operations & Taxiing (Preserved whenever recorded, including diverted flights)
    taxi_out_min                        REAL,
    wheels_off_raw                      TEXT,
    wheels_off_time                     TEXT,
    wheels_off_is_midnight              INTEGER,
    wheels_on_raw                       TEXT,
    wheels_on_time                      TEXT,
    wheels_on_is_midnight               INTEGER,
    taxi_in_min                         REAL,
    
    -- Flight Duration & Distance Metrics
    scheduled_duration_min              REAL,
    actual_duration_min                 REAL,
    air_time_min                        REAL,
    distance_miles                      REAL NOT NULL,
    
    -- Scheduled Arrival
    scheduled_arrival_raw               TEXT NOT NULL,
    scheduled_arrival_time              TEXT NOT NULL,
    scheduled_arrival_is_midnight       INTEGER NOT NULL DEFAULT 0,
    
    -- Actual Arrival
    arrival_time_raw                    TEXT,
    actual_arrival_time                 TEXT,
    arrival_is_midnight                 INTEGER,
    arrival_delay_min                   REAL,
    
    -- Flight Status Flags
    is_diverted                         INTEGER NOT NULL DEFAULT 0,
    is_cancelled                        INTEGER NOT NULL DEFAULT 0,
    cancellation_reason_code            TEXT,
    
    -- Causal Delay Metrics (Populated strictly when arrival_delay_min >= 15 per DOT rules)
    air_system_delay_min                REAL,
    security_delay_min                  REAL,
    airline_delay_min                   REAL,
    late_aircraft_delay_min             REAL,
    weather_delay_min                   REAL,

    -- Foreign Key Constraints
    FOREIGN KEY (source_row_id) REFERENCES staging_flights_raw(raw_id),
    FOREIGN KEY (date_id) REFERENCES dim_dates(date_id),
    FOREIGN KEY (airline_code) REFERENCES dim_airlines(airline_code),
    FOREIGN KEY (origin_airport_id) REFERENCES dim_airports(airport_id),
    FOREIGN KEY (dest_airport_id) REFERENCES dim_airports(airport_id),
    FOREIGN KEY (cancellation_reason_code) REFERENCES dim_cancellation_reasons(reason_code),

    -- Table Integrity Constraints
    CHECK (origin_airport_id != dest_airport_id),
    CHECK (is_diverted IN (0, 1)),
    CHECK (is_cancelled IN (0, 1)),
    CHECK (NOT (is_cancelled = 1 AND is_diverted = 1)),
    CHECK (
        (is_cancelled = 0 AND cancellation_reason_code IS NULL) OR
        (is_cancelled = 1 AND cancellation_reason_code IN ('A', 'B', 'C', 'D'))
    )
);
