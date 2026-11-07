# FlightPulse Dimension Tables & Reference Data Population Report (Step 4.3)

**Execution Date**: 2026-11-07  
**Database**: `database/flightpulse.db`  
**Script**: `scripts/load_dimensions.py`  
**Status**: Completed successfully without errors or foreign-key violations.

---

## 1. Executive Summary

In Step 4.3 of the FlightPulse implementation, four dimension and reference tables were populated from verified raw files and calendar generators:
1. `dim_airlines` (14 records)
2. `dim_cancellation_reasons` (4 records)
3. `dim_dates` (365 records)
4. `dim_airports` (322 records)

In strict adherence to design requirements:
- `map_airport_codes` was **intentionally retained at 0 records** pending ingestion of the official BTS crosswalk reference file. No artificial or guessed mappings were created.
- `fact_flights` remains **unpopulated (0 records)**.
- NULL coordinate values in `dim_airports` were strictly preserved for three airports (`ECP`, `PBG`, and `UST`).
- All 14 airlines, 365 dates, and 322 alphabetical IATA airport codes found in `staging_flights_raw` achieved a **100% referential match** against the dimension tables.

---

## 2. Table-by-Table Population & Validation Results

### 2.1 `dim_airlines`
- **Source**: `data/raw/airlines.csv` (14 records)
- **Inserted Records**: 14
- **Schema Mapping**:
  - `IATA_CODE` $\rightarrow$ `airline_code` (TEXT PRIMARY KEY)
  - `AIRLINE` $\rightarrow$ `airline_name` (TEXT NOT NULL)
- **Validation**:
  - Distinct airline codes in `data/raw/airlines.csv`: 14
  - Duplicate codes found: 0
  - Missing airline names: 0
  - Distinct `AIRLINE` codes in `staging_flights_raw`: 14 (`AA`, `AS`, `B6`, `DL`, `EV`, `F9`, `HA`, `MQ`, `NK`, `OO`, `UA`, `US`, `VX`, `WN`)
  - **Match Rate**: **100% (14 / 14)**. Zero unmatched carrier codes in staging.

---

### 2.2 `dim_cancellation_reasons`
- **Source**: U.S. Department of Transportation (DOT) Form 234 specification
- **Inserted Records**: 4
- **Records**:
  | reason_code | reason_description |
  | :--- | :--- |
  | `A` | Airline/Carrier |
  | `B` | Weather |
  | `C` | National Air System (NAS) |
  | `D` | Security |
- **Validation**:
  - Distinct cancellation reason codes found in `staging_flights_raw.CANCELLATION_REASON`: `A`, `B`, `C`, `D` (plus empty strings for non-cancelled flights).
  - Unrecognized cancellation codes in staging: 0.
  - **Match Rate**: **100% (4 / 4)**.

---

### 2.3 `dim_dates`
- **Source**: Programmatic calendar generation covering all 365 calendar days of 2015 (`2015-01-01` to `2015-12-31`).
- **Inserted Records**: 365
- **Fields Computed**:
  - `date_key`: Integer surrogate key (`YYYYMMDD`, e.g., `20150101` to `20151231`)
  - `full_date`: ISO text date (`YYYY-MM-DD`)
  - `year`: 2015
  - `quarter`: 1 to 4
  - `month`: 1 to 12
  - `month_name`: January to December
  - `day_of_month`: 1 to 31
  - `day_of_week`: 1 (Monday) to 7 (Sunday), conforming to ISO-8601 and table `CHECK (day_of_week BETWEEN 1 AND 7)`
  - `day_name`: Monday to Sunday
  - `is_weekend`: 1 for Saturday/Sunday, 0 for weekdays
- **Validation**:
  - Date range: Exactly 365 contiguous days (2015 was not a leap year).
  - Primary key uniqueness: 365 unique `date_key` values.
  - Distinct dates in `staging_flights_raw`: Formed by composite `YEAR`, `MONTH`, `DAY`.
  - Date coverage in staging: Exactly 365 unique dates.
  - **Match Rate**: **100% (365 / 365)**.

---

### 2.4 `dim_airports`
- **Source**: `data/raw/airports.csv` (322 records)
- **Inserted Records**: 322
- **Schema Mapping**:
  - `IATA_CODE` $\rightarrow$ `iata_code` (TEXT NOT NULL UNIQUE)
  - `AIRPORT` $\rightarrow$ `airport_name` (TEXT NOT NULL)
  - `CITY` $\rightarrow$ `city` (TEXT NOT NULL)
  - `STATE` $\rightarrow$ `state` (TEXT NOT NULL)
  - `COUNTRY` $\rightarrow$ `country` (TEXT NOT NULL)
  - `LATITUDE` $\rightarrow$ `latitude` (REAL, or NULL if empty/missing)
  - `LONGITUDE` $\rightarrow$ `longitude` (REAL, or NULL if empty/missing)
  - Surrogate key: `airport_id` (`INTEGER PRIMARY KEY AUTOINCREMENT`, IDs 1 to 322)
- **Preservation of NULL Coordinates**:
  - Exactly three airports have missing coordinate values in `airports.csv`. These were preserved strictly as SQL `NULL` without substitution or interpolation:
    1. **`ECP`** (Northwest Florida Beaches International Airport, Panama City, FL)
    2. **`PBG`** (Plattsburgh International Airport, Plattsburgh, NY)
    3. **`UST`** (Northeast Florida Regional Airport, St. Augustine, FL)
- **Staging Cross-Check**:
  - `staging_flights_raw` contains 629 distinct airport code values across origin and destination columns:
    - **322 alphabetical IATA codes** (Jan–Sep, Nov–Dec flights): All 322 match records in `dim_airports` (100% match).
    - **307 five-digit numeric DOT ID codes** (October flights): Confirmed to belong to October 2015 records where the DOT Bureau of Transportation Statistics numeric facility identifier was reported instead of IATA 3-letter strings.
  - Unmatched alphabetical airport codes: 0.

---

## 3. Investigation of Official BTS Airport Crosswalk

### 3.1 Context & Problem Statement
In October 2015, the source records in `flights.csv` logged airport locations as 5-digit numeric strings (e.g., `'11298'`, `'12892'`, `'10397'`) rather than 3-letter IATA alphabetic codes (e.g., `'DFW'`, `'LAX'`, `'ATL'`). There are **307 distinct numeric codes** in staging that require authoritative resolution before `fact_flights` can be populated.

### 3.2 Authoritative Source: DOT BTS TranStats
The authoritative source for these numeric identifiers is the **U.S. Department of Transportation (USDOT) Bureau of Transportation Statistics (BTS)**:
- **Repository**: USDOT BTS TranStats (Office of Airline Information)
- **Reference Table**: `L_AIRPORT_ID` lookup table (Lookup for DOT 5-digit Airport ID to 3-letter Airport Code / Description).
- **Secondary Reference**: BTS Master Coordinate Table (`L_AIRPORT`) and DOT Form 234 T-100 / On-Time Reporting Carrier Airport ID master directory.

### 3.3 Target Structure for `map_airport_codes`
The approved schema provides the mapping bridge:
```sql
CREATE TABLE IF NOT EXISTS map_airport_codes (
    mapping_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    code_type    TEXT NOT NULL CHECK (code_type IN ('IATA', 'DOT_ID', 'ICAO')),
    source_code  TEXT NOT NULL UNIQUE,
    airport_id   INTEGER NOT NULL REFERENCES dim_airports(airport_id)
);
```

### 3.4 Integration & Verification Protocol for Step 4.4
To resolve the 307 October DOT codes without compromising data integrity:
1. **Source Download / Acquisition**: Retrieve the official `L_AIRPORT_ID` table published by USDOT BTS for 2015.
2. **Deterministic Cross-Reference**:
   - Match each 5-digit DOT ID to its official BTS IATA code string.
   - Join against `dim_airports.iata_code` to link to the canonical `dim_airports.airport_id`.
3. **Route & Operational Verification**:
   - Verify that carrier-route pairs in October (e.g., carrier flights between DOT `'11298'` and `'12892'`) match the historical September/November operations between corresponding IATA facilities (e.g., `'DFW'` and `'LAX'`).
4. **Audit**:
   - Ensure 100% of the 307 numeric codes resolve to existing facilities in `dim_airports`.
   - Any facilities not present in the 322-airport baseline must be logged in an audit report.

---

## 4. Final Database Row Count & Foreign Key Audit

```text
Table Name                 Row Count   Status
---------------------------------------------------------------
staging_flights_raw        5,819,079   Complete (Step 4.2)
dim_airlines                      14   Complete (Step 4.3)
dim_cancellation_reasons           4   Complete (Step 4.3)
dim_dates                        365   Complete (Step 4.3)
dim_airports                     322   Complete (Step 4.3)
map_airport_codes                  0   Deferred to Crosswalk Step
fact_flights                       0   Deferred to Fact Step
---------------------------------------------------------------
Foreign Key Violations:            0   PASSED (PRAGMA foreign_key_check)
```

