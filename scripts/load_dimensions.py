"""
FlightPulse - Dimension Tables and Reference Data Population Script
File: scripts/load_dimensions.py

Populates dimension tables for FlightPulse (database/flightpulse.db):
1. dim_airlines: 14 operating carriers from data/raw/airlines.csv
2. dim_cancellation_reasons: 4 verified US DOT 2015 cancellation codes (A, B, C, D)
3. dim_dates: 365 calendar days of 2015 (2015-01-01 to 2015-12-31)
4. dim_airports: 322 verified airport facilities from data/raw/airports.csv
   (preserving missing coordinates as NULL)

Safety & Invariants:
- Uses transactions with clean rollback on error.
- Enforces PRAGMA foreign_keys = ON.
- Does NOT populate fact_flights or map_airport_codes with unverified data.
- Refuses to overwrite populated dimension tables unless empty.
- Runs exhaustive post-load validations on counts, NULLs, duplicates, and coverage.
"""

import os
import sys
import csv
import sqlite3
import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATABASE_PATH = os.path.join(BASE_DIR, "database", "flightpulse.db")
AIRLINES_CSV_PATH = os.path.join(BASE_DIR, "data", "raw", "airlines.csv")
AIRPORTS_CSV_PATH = os.path.join(BASE_DIR, "data", "raw", "airports.csv")

# Verified 2015 US DOT Form 234 Cancellation Reason Standards
CANCELLATION_REASONS = [
    ("A", "Airline/Carrier", "Carrier operations, crew, maintenance, or baggage issues"),
    ("B", "Weather", "Significant meteorological conditions delaying flight operations"),
    ("C", "National Air System (NAS)", "FAA air traffic control, heavy traffic volume, or airport operations"),
    ("D", "Security", "Evacuation of terminal/concourse, re-boarding, or security screening breaches")
]

def get_connection(db_path):
    """Establishes an SQLite connection with PRAGMA foreign_keys = ON."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def check_table_empty(cursor, table_name):
    """Returns True if table is empty (0 rows), False otherwise."""
    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
    return cursor.fetchone()[0] == 0

def load_dim_airlines(conn, csv_path):
    """Loads dim_airlines from data/raw/airlines.csv."""
    print("Populating dim_airlines...")
    cursor = conn.cursor()

    if not check_table_empty(cursor, "dim_airlines"):
        print("  Notice: dim_airlines already populated. Skipping insert.")
        return 0

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Missing file: {csv_path}")

    airlines = []
    seen_codes = set()
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row_idx, row in enumerate(reader, 1):
            if len(row) < 2 or not row[0].strip() or not row[1].strip():
                raise ValueError(f"Invalid row in airlines.csv at line {row_idx}: {row}")
            code = row[0].strip()
            name = row[1].strip()
            if code in seen_codes:
                raise ValueError(f"Duplicate airline code in airlines.csv: {code}")
            seen_codes.add(code)
            airlines.append((code, name))

    cursor.executemany(
        "INSERT INTO dim_airlines (airline_code, airline_name) VALUES (?, ?);",
        airlines
    )
    print(f"  [SUCCESS] Inserted {len(airlines)} records into dim_airlines.")
    return len(airlines)

def load_dim_cancellation_reasons(conn):
    """Loads dim_cancellation_reasons from verified DOT Form 234 definitions."""
    print("Populating dim_cancellation_reasons...")
    cursor = conn.cursor()

    if not check_table_empty(cursor, "dim_cancellation_reasons"):
        print("  Notice: dim_cancellation_reasons already populated. Skipping insert.")
        return 0

    cursor.executemany(
        "INSERT INTO dim_cancellation_reasons (reason_code, reason_description, responsible_entity) VALUES (?, ?, ?);",
        CANCELLATION_REASONS
    )
    print(f"  [SUCCESS] Inserted {len(CANCELLATION_REASONS)} records into dim_cancellation_reasons.")
    return len(CANCELLATION_REASONS)

def load_dim_dates(conn):
    """Generates and loads all 365 calendar dates of 2015 into dim_dates."""
    print("Populating dim_dates...")
    cursor = conn.cursor()

    if not check_table_empty(cursor, "dim_dates"):
        print("  Notice: dim_dates already populated. Skipping insert.")
        return 0

    start_date = datetime.date(2015, 1, 1)
    end_date = datetime.date(2015, 12, 31)
    curr = start_date
    date_records = []

    while curr <= end_date:
        date_id = int(curr.strftime("%Y%m%d"))
        full_date = curr.strftime("%Y-%m-%d")
        year = curr.year
        month = curr.month
        day = curr.day
        day_of_week = curr.isoweekday() # 1 = Monday, 7 = Sunday per ISO standard & schema CHECK constraint
        day_name = curr.strftime("%A")
        month_name = curr.strftime("%B")
        is_weekend = 1 if day_of_week in (6, 7) else 0
        quarter = (month - 1) // 3 + 1

        date_records.append((
            date_id, full_date, year, month, day, day_of_week, day_name, month_name, is_weekend, quarter
        ))
        curr += datetime.timedelta(days=1)

    cursor.executemany(
        """
        INSERT INTO dim_dates (
            date_id, full_date, year, month, day, day_of_week, day_name, month_name, is_weekend, quarter
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        date_records
    )
    print(f"  [SUCCESS] Inserted {len(date_records)} calendar dates into dim_dates.")
    return len(date_records)

def load_dim_airports(conn, csv_path):
    """Loads verified commercial airports from data/raw/airports.csv."""
    print("Populating dim_airports...")
    cursor = conn.cursor()

    if not check_table_empty(cursor, "dim_airports"):
        print("  Notice: dim_airports already populated. Skipping insert.")
        return 0

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Missing file: {csv_path}")

    airports = []
    seen_iata = set()
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row_idx, row in enumerate(reader, 1):
            if len(row) < 7:
                raise ValueError(f"Malformed row in airports.csv at line {row_idx}: {row}")
            iata = row[0].strip()
            name = row[1].strip()
            city = row[2].strip()
            state = row[3].strip()
            country = row[4].strip() if row[4].strip() else "USA"
            
            # Preserve missing coordinates as NULL (None)
            lat_str = row[5].strip()
            lon_str = row[6].strip()
            lat = float(lat_str) if lat_str else None
            lon = float(lon_str) if lon_str else None

            if not iata:
                raise ValueError(f"Missing IATA_CODE at line {row_idx}")
            if iata in seen_iata:
                raise ValueError(f"Duplicate IATA code in airports.csv: {iata}")
            seen_iata.add(iata)

            airports.append((iata, name, city, state, country, lat, lon))

    cursor.executemany(
        """
        INSERT INTO dim_airports (
            iata_code, airport_name, city, state, country, latitude, longitude
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        airports
    )
    print(f"  [SUCCESS] Inserted {len(airports)} verified airport records into dim_airports.")
    return len(airports)

def validate_dimensions(conn):
    """Runs comprehensive validation across loaded dimensions and staging coverage."""
    print("\n--- Running Dimension Validation Suite ---")
    cursor = conn.cursor()
    errors = []

    # 1. Row counts check
    expected_counts = {
        "dim_airlines": 14,
        "dim_cancellation_reasons": 4,
        "dim_dates": 365,
        "dim_airports": 322,
        "map_airport_codes": 0,
        "fact_flights": 0
    }

    for tbl, expected in expected_counts.items():
        cursor.execute(f"SELECT COUNT(*) FROM {tbl};")
        actual = cursor.fetchone()[0]
        if actual != expected:
            errors.append(f"Table {tbl} row count mismatch: expected {expected}, found {actual}")
        else:
            print(f"  [PASS] {tbl} record count verified: {actual}")

    # 2. Check dim_airlines coverage against staging_flights_raw
    cursor.execute("SELECT DISTINCT AIRLINE FROM staging_flights_raw;")
    stg_airlines = {row[0] for row in cursor.fetchall()}
    cursor.execute("SELECT airline_code FROM dim_airlines;")
    dim_airlines = {row[0] for row in cursor.fetchall()}
    
    unmatched_airlines = stg_airlines - dim_airlines
    if unmatched_airlines:
        errors.append(f"Staging has unmatched airlines: {unmatched_airlines}")
    else:
        print(f"  [PASS] All {len(stg_airlines)} distinct staging airlines match dim_airlines 100%.")

    # 3. Check dim_dates coverage against staging_flights_raw
    cursor.execute("""
        SELECT DISTINCT printf('%04d-%02d-%02d', CAST(YEAR AS INT), CAST(MONTH AS INT), CAST(DAY AS INT))
        FROM staging_flights_raw;
    """)
    stg_dates = {row[0] for row in cursor.fetchall()}
    cursor.execute("SELECT full_date FROM dim_dates;")
    dim_dates = {row[0] for row in cursor.fetchall()}

    unmatched_dates = stg_dates - dim_dates
    if unmatched_dates:
        errors.append(f"Staging has dates outside 2015 calendar dimension: {unmatched_dates}")
    elif len(stg_dates) != 365:
        errors.append(f"Staging distinct date count unexpected: found {len(stg_dates)}, expected 365")
    else:
        print(f"  [PASS] All 365 staging calendar dates match dim_dates 100%.")

    # 4. Check dim_airports coordinates nullability policy
    cursor.execute("SELECT iata_code FROM dim_airports WHERE latitude IS NULL OR longitude IS NULL;")
    null_coords = [r[0] for r in cursor.fetchall()]
    expected_null_coords = ["ECP", "PBG", "UST"]
    if sorted(null_coords) != sorted(expected_null_coords):
        errors.append(f"Unexpected NULL coordinates: expected {expected_null_coords}, found {null_coords}")
    else:
        print(f"  [PASS] Preserved NULL coordinates strictly for verified airports: {null_coords}")

    # 5. Check airport code representation in staging_flights_raw
    cursor.execute("SELECT DISTINCT ORIGIN_AIRPORT FROM staging_flights_raw UNION SELECT DISTINCT DESTINATION_AIRPORT FROM staging_flights_raw;")
    stg_airports = {r[0] for r in cursor.fetchall()}
    cursor.execute("SELECT iata_code FROM dim_airports;")
    dim_iatas = {r[0] for r in cursor.fetchall()}

    alpha_airports = {a for a in stg_airports if not a.isdigit()}
    numeric_airports = {a for a in stg_airports if a.isdigit()}

    unmatched_alpha = alpha_airports - dim_iatas
    if unmatched_alpha:
        errors.append(f"Staging alphabetical airport codes not found in dim_airports: {unmatched_alpha}")
    else:
        print(f"  [PASS] All {len(alpha_airports)} alphabetical IATA airport codes in staging match dim_airports 100%.")

    print(f"  [AUDIT NOTE] Found {len(numeric_airports)} distinct 5-digit DOT numeric airport IDs in staging (October 2015).")
    print(f"  [AUDIT NOTE] map_airport_codes intentionally unpopulated (0 records) pending official BTS crosswalk validation.")

    # 6. Execute PRAGMA foreign_key_check
    cursor.execute("PRAGMA foreign_key_check;")
    fk_violations = cursor.fetchall()
    if fk_violations:
        errors.append(f"Foreign key violations detected: {fk_violations}")
    else:
        print("  [PASS] PRAGMA foreign_key_check returned 0 violations.")

    if errors:
        print("\n[FAIL] Dimension validation failed with issues:")
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        raise RuntimeError("Dimension validation failed.")
    else:
        print("\n[SUCCESS] All dimension validation checks passed successfully!")

def main():
    print("=== FlightPulse Dimension Data Population Started ===")
    conn = get_connection(DATABASE_PATH)
    try:
        conn.execute("BEGIN TRANSACTION;")
        load_dim_airlines(conn, AIRLINES_CSV_PATH)
        load_dim_cancellation_reasons(conn)
        load_dim_dates(conn)
        load_dim_airports(conn, AIRPORTS_CSV_PATH)
        conn.commit()
        print("\nAll dimension tables committed successfully.")
        validate_dimensions(conn)
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Transaction aborted and rolled back: {e}", file=sys.stderr)
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    main()

