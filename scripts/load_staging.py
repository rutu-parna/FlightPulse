"""
FlightPulse - Raw Flight Dataset Ingestion Script
File: scripts/load_staging.py

Ingests all 5,819,079 flight records from data/raw/flights.csv into staging_flights_raw
inside database/flightpulse.db.

Core Principles & Safety Rules:
1. Pure string preservation: Uses Python standard-library csv.reader. Non-empty values
   are inserted as exact strings into TEXT affinity columns.
2. Missing-value policy: Empty strings ('') are converted to None (SQL NULL).
3. Chunked processing: Reads and inserts in configurable batches (default 10,000 rows),
   never loading the entire 565MB file into RAM.
4. Transaction control: All inserts run inside a single controlled transaction. If an error
   occurs, the entire transaction rolls back cleanly, leaving zero partial data.
5. Idempotence & safety: Refuses to load if staging_flights_raw is already populated.
   Never truncates or drops tables automatically.
6. Progress monitoring: Reports metrics every 100,000 inserted rows.
7. Post-load validation: Asserts exact row counts, schema affinities, key integrity,
   sample data parity, and executes PRAGMA foreign_key_check.
"""

import os
import sys
import csv
import time
import sqlite3
import shutil

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATABASE_PATH = os.path.join(BASE_DIR, "database", "flightpulse.db")
FLIGHTS_CSV_PATH = os.path.join(BASE_DIR, "data", "raw", "flights.csv")

EXPECTED_ROW_COUNT = 5819079
BATCH_SIZE = 10000
PROGRESS_INTERVAL = 100000

EXPECTED_COLUMNS = [
    "YEAR", "MONTH", "DAY", "DAY_OF_WEEK", "AIRLINE", "FLIGHT_NUMBER", "TAIL_NUMBER",
    "ORIGIN_AIRPORT", "DESTINATION_AIRPORT", "SCHEDULED_DEPARTURE", "DEPARTURE_TIME",
    "DEPARTURE_DELAY", "TAXI_OUT", "WHEELS_OFF", "SCHEDULED_TIME", "ELAPSED_TIME",
    "AIR_TIME", "DISTANCE", "WHEELS_ON", "TAXI_IN", "SCHEDULED_ARRIVAL", "ARRIVAL_TIME",
    "ARRIVAL_DELAY", "DIVERTED", "CANCELLED", "CANCELLATION_REASON", "AIR_SYSTEM_DELAY",
    "SECURITY_DELAY", "AIRLINE_DELAY", "LATE_AIRCRAFT_DELAY", "WEATHER_DELAY"
]

def check_preconditions(db_path, csv_path):
    """Verifies environment, disk space, and staging table state before ingestion."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Source raw file not found: {csv_path}")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at: {db_path}. Run scripts/create_database.py first.")

    # Check disk space
    disk_stat = shutil.disk_usage(os.path.dirname(db_path))
    free_gb = disk_stat.free / (1024 ** 3)
    csv_mb = os.path.getsize(csv_path) / (1024 ** 2)
    print(f"Pre-flight Checks:")
    print(f"  Source CSV size: {csv_mb:.2f} MB")
    print(f"  Available disk space: {free_gb:.2f} GB (Estimated growth: ~1.2 - 1.8 GB)")
    if free_gb < 3.0:
        raise RuntimeError(f"Insufficient disk space. At least 3.0 GB free required, found {free_gb:.2f} GB.")

    # Check that staging table exists and is empty
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='staging_flights_raw';")
    if not cursor.fetchone():
        conn.close()
        raise RuntimeError("Table 'staging_flights_raw' does not exist. Run scripts/create_database.py first.")

    cursor.execute("SELECT COUNT(*) FROM staging_flights_raw;")
    existing_count = cursor.fetchone()[0]
    conn.close()

    if existing_count > 0:
        raise RuntimeError(
            f"Pre-flight Abort: staging_flights_raw already contains {existing_count:,} rows. "
            "Refusing to load to prevent duplicate or corrupted data. "
            "If a reload is explicitly needed, inspect and clear the database manually."
        )

    print("  staging_flights_raw confirmed empty. Proceeding to ingestion.")

def ingest_staging(db_path, csv_path, batch_size=BATCH_SIZE):
    """Reads flights.csv in chunks and inserts records using parameterized SQL."""
    insert_sql = f"""
    INSERT INTO staging_flights_raw ({', '.join(EXPECTED_COLUMNS)})
    VALUES ({', '.join(['?'] * len(EXPECTED_COLUMNS))})
    """

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    # Optimize SQLite temporary journaling during large controlled load
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA cache_size = -64000;") # 64MB memory cache

    cursor = conn.cursor()
    total_inserted = 0
    start_time = time.time()
    last_progress_time = start_time

    print(f"\nStarting ingestion of {EXPECTED_ROW_COUNT:,} records (batch size: {batch_size:,})...")

    try:
        # Single controlled transaction enclosing all chunks
        conn.execute("BEGIN TRANSACTION;")

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            if header != EXPECTED_COLUMNS:
                raise ValueError(f"CSV header does not match expected columns.\nExpected: {EXPECTED_COLUMNS}\nFound: {header}")

            batch = []
            for row_idx, row in enumerate(reader, 1):
                # Clean missing value handling: empty string becomes None (SQL NULL), all others preserved as strings
                processed_row = tuple(val if val != "" else None for val in row)
                batch.append(processed_row)

                if len(batch) >= batch_size:
                    cursor.executemany(insert_sql, batch)
                    total_inserted += len(batch)
                    batch = []

                    # Periodic progress display every 100,000 rows
                    if total_inserted % PROGRESS_INTERVAL == 0:
                        elapsed = time.time() - start_time
                        pct = (total_inserted / EXPECTED_ROW_COUNT) * 100
                        rate = total_inserted / elapsed if elapsed > 0 else 0
                        print(f"  Inserted: {total_inserted:,} / {EXPECTED_ROW_COUNT:,} ({pct:.1f}%) | "
                              f"Elapsed: {elapsed:.1f}s | Rate: {rate:,.0f} rows/s")

            # Final remaining batch
            if batch:
                cursor.executemany(insert_sql, batch)
                total_inserted += len(batch)

        conn.commit()
        total_time = time.time() - start_time
        overall_rate = total_inserted / total_time if total_time > 0 else 0
        print(f"\n[SUCCESS] Transaction committed successfully!")
        print(f"  Total records inserted: {total_inserted:,}")
        print(f"  Total elapsed time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
        print(f"  Overall processing rate: {overall_rate:,.0f} rows/second")
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Ingestion encountered an exception: {e}", file=sys.stderr)
        print("  Transaction rolled back cleanly. No partial data was retained.", file=sys.stderr)
        raise
    finally:
        conn.close()

    return total_inserted, total_time, overall_rate

def validate_staging(db_path, csv_path):
    """Executes all post-load structural and data parity checks."""
    print("\n--- Running Staging Validation Suite ---")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()
    errors = []

    # 1. Total count check
    cursor.execute("SELECT COUNT(*) FROM staging_flights_raw;")
    actual_count = cursor.fetchone()[0]
    if actual_count != EXPECTED_ROW_COUNT:
        errors.append(f"Row count mismatch: expected {EXPECTED_ROW_COUNT:,}, found {actual_count:,}")
    else:
        print(f"  [PASS] Staging record count matches exactly: {actual_count:,}")

    # 2. Schema check: all 31 columns exist with TEXT affinity and raw_id is INTEGER PK
    cursor.execute("PRAGMA table_info(staging_flights_raw);")
    cols = cursor.fetchall()
    col_map = {c[1]: {"type": c[2].upper(), "pk": c[5]} for c in cols}

    pks = [name for name, info in col_map.items() if info["pk"] > 0]
    if pks == ["raw_id"] and col_map["raw_id"]["type"] == "INTEGER":
        print("  [PASS] raw_id verified as the sole INTEGER PRIMARY KEY.")
    else:
        errors.append(f"Invalid primary key: expected ['raw_id' INTEGER], found {pks}")

    non_text = [name for name in EXPECTED_COLUMNS if name not in col_map or col_map[name]["type"] != "TEXT"]
    if non_text:
        errors.append(f"Columns lacking TEXT affinity: {non_text}")
    else:
        print("  [PASS] All 31 source columns verified with TEXT affinity.")

    # 3. Foreign key check
    cursor.execute("PRAGMA foreign_key_check;")
    fk_violations = cursor.fetchall()
    if fk_violations:
        errors.append(f"Foreign key violations detected: {fk_violations}")
    else:
        print("  [PASS] PRAGMA foreign_key_check returned 0 violations.")

    # 4. Parity Spot Check against CSV source records (Rows 1, 100, 1000, 50000, 100000)
    sample_indices = [1, 2, 100, 1000, 50000, 100000, 1000000, 5000000]
    print(f"  Performing field-by-field parity check across {len(sample_indices)} sample records...")
    
    # Read target rows from CSV
    target_csv_rows = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader) # header
        cur_idx = 1
        max_idx = max(sample_indices)
        for row in reader:
            if cur_idx in sample_indices:
                target_csv_rows[cur_idx] = tuple(val if val != "" else None for val in row)
            if cur_idx >= max_idx:
                break
            cur_idx += 1

    # Query matching rows from SQLite by raw_id
    cols_sql = ", ".join(EXPECTED_COLUMNS)
    mismatches = 0
    for idx, expected_row in target_csv_rows.items():
        cursor.execute(f"SELECT {cols_sql} FROM staging_flights_raw WHERE raw_id = ?;", (idx,))
        db_row = cursor.fetchone()
        if db_row != expected_row:
            errors.append(f"Data parity mismatch at row {idx}:\n  CSV: {expected_row}\n  DB:  {db_row}")
            mismatches += 1

    if mismatches == 0:
        print(f"  [PASS] All 31 columns match identically across all sampled records.")

    conn.close()

    if errors:
        print("\n[FAIL] Validation encountered errors:")
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        raise RuntimeError("Staging validation failed.")
    else:
        print("\n[SUCCESS] All staging validation checks passed!")

def main():
    print("=== FlightPulse Staging Ingestion Started ===")
    check_preconditions(DATABASE_PATH, FLIGHTS_CSV_PATH)
    total_inserted, elapsed_time, rate = ingest_staging(DATABASE_PATH, FLIGHTS_CSV_PATH)
    validate_staging(DATABASE_PATH, FLIGHTS_CSV_PATH)

    db_size_mb = os.path.getsize(DATABASE_PATH) / (1024 * 1024)
    print(f"\nFinal Summary:")
    print(f"  Total records loaded: {total_inserted:,}")
    print(f"  Elapsed time: {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
    print(f"  Processing rate: {rate:,.0f} rows/second")
    print(f"  Final database file size: {db_size_mb:.2f} MB ({db_size_mb/1024:.2f} GB)")

if __name__ == "__main__":
    main()

