"""
FlightPulse - SQLite Database Initialization and Verification Script
File: scripts/create_database.py

Initializes the FlightPulse SQLite database schema located at database/flightpulse.db
based on the DDL defined in sql/01_create_schema.sql.

Safety and Verification Features:
- Executes PRAGMA foreign_keys = ON on every connection.
- Uses transactions with clean rollback on error.
- Safe to rerun: checks if tables already exist and avoids destructive drops.
  If an existing database is completely empty (0 rows across all tables) and requires
  a DDL update (e.g. updating column affinities), it safely recreates the empty schema.
- Performs an exhaustive structural schema verification checking:
    1. Database accessibility.
    2. Existence of all 7 expected tables.
    3. Proper primary key definitions.
    4. Foreign key presence and targets.
    5. Active foreign key enforcement status.
    6. Unique and Not Null constraints on fact_flights.source_row_id.
    7. TEXT affinity on all 31 staging columns and single integer PK on raw_id.
"""

import os
import sys
import sqlite3

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATABASE_PATH = os.path.join(BASE_DIR, "database", "flightpulse.db")
SCHEMA_SQL_PATH = os.path.join(BASE_DIR, "sql", "01_create_schema.sql")

EXPECTED_TABLES = [
    "staging_flights_raw",
    "dim_airlines",
    "dim_airports",
    "map_airport_codes",
    "dim_dates",
    "dim_cancellation_reasons",
    "fact_flights"
]

EXPECTED_PKS = {
    "staging_flights_raw": ["raw_id"],
    "dim_airlines": ["airline_code"],
    "dim_airports": ["airport_id"],
    "map_airport_codes": ["raw_code"],
    "dim_dates": ["date_id"],
    "dim_cancellation_reasons": ["reason_code"],
    "fact_flights": ["flight_id"]
}

EXPECTED_FKS = {
    "map_airport_codes": [("airport_id", "dim_airports", "airport_id")],
    "fact_flights": [
        ("source_row_id", "staging_flights_raw", "raw_id"),
        ("date_id", "dim_dates", "date_id"),
        ("airline_code", "dim_airlines", "airline_code"),
        ("origin_airport_id", "dim_airports", "airport_id"),
        ("dest_airport_id", "dim_airports", "airport_id"),
        ("cancellation_reason_code", "dim_cancellation_reasons", "reason_code")
    ]
}

STAGING_ORIGINAL_COLS = [
    "YEAR", "MONTH", "DAY", "DAY_OF_WEEK", "AIRLINE", "FLIGHT_NUMBER", "TAIL_NUMBER",
    "ORIGIN_AIRPORT", "DESTINATION_AIRPORT", "SCHEDULED_DEPARTURE", "DEPARTURE_TIME",
    "DEPARTURE_DELAY", "TAXI_OUT", "WHEELS_OFF", "SCHEDULED_TIME", "ELAPSED_TIME",
    "AIR_TIME", "DISTANCE", "WHEELS_ON", "TAXI_IN", "SCHEDULED_ARRIVAL", "ARRIVAL_TIME",
    "ARRIVAL_DELAY", "DIVERTED", "CANCELLED", "CANCELLATION_REASON", "AIR_SYSTEM_DELAY",
    "SECURITY_DELAY", "AIRLINE_DELAY", "LATE_AIRCRAFT_DELAY", "WEATHER_DELAY"
]

def get_connection(db_path):
    """Establishes an SQLite connection with PRAGMA foreign_keys = ON."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def check_database_empty(conn):
    """Checks whether all existing tables in the database contain 0 rows."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]
    total_rows = 0
    for tbl in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {tbl};")
        total_rows += cursor.fetchone()[0]
    return total_rows == 0, tables

def create_schema(db_path, schema_path):
    """Reads and executes the schema DDL safely inside a transaction."""
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema SQL script not found at: {schema_path}")

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db_existed_before = os.path.exists(db_path) and os.path.getsize(db_path) > 0

    print(f"Connecting to database at: {db_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_connection(db_path)
    try:
        if db_existed_before:
            is_empty, existing_tables = check_database_empty(conn)
            if is_empty:
                print("  Notice: Existing database file is completely empty (0 rows across all tables).")
                # Check if staging table needs recreation to match all-TEXT definition
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(staging_flights_raw);")
                stg_cols = cursor.fetchall()
                non_text_stg = [c[1] for c in stg_cols if c[1] != "raw_id" and c[2].upper() != "TEXT"]
                if non_text_stg:
                    print("  Notice: Upgrading staging schema to all-TEXT columns in empty database...")
                    cursor.execute("DROP TABLE IF EXISTS fact_flights;")
                    cursor.execute("DROP TABLE IF EXISTS staging_flights_raw;")
                    cursor.execute("DROP TABLE IF EXISTS map_airport_codes;")
                    cursor.execute("DROP TABLE IF EXISTS dim_cancellation_reasons;")
                    cursor.execute("DROP TABLE IF EXISTS dim_dates;")
                    cursor.execute("DROP TABLE IF EXISTS dim_airports;")
                    cursor.execute("DROP TABLE IF EXISTS dim_airlines;")
            else:
                print("  Notice: Existing database contains populated data. Preserving all existing data.")

        conn.executescript(schema_sql)
        conn.commit()
        print("Schema DDL executed successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Error executing schema script: {e}", file=sys.stderr)
        raise
    finally:
        conn.close()

def verify_schema(db_path):
    """Performs deep verification of the created tables, keys, column affinities, and foreign keys."""
    print("\n--- Running Schema Verification Routine ---")
    conn = get_connection(db_path)
    cursor = conn.cursor()

    errors = []

    # 1. Verify foreign-key enforcement is active
    cursor.execute("PRAGMA foreign_keys;")
    fk_status = cursor.fetchone()
    if not fk_status or fk_status[0] != 1:
        errors.append("PRAGMA foreign_keys is NOT enabled on this connection.")
    else:
        print("  [PASS] Foreign key enforcement is actively enabled (PRAGMA foreign_keys = 1).")

    # 2. Verify all expected tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    existing_tables = [row[0] for row in cursor.fetchall()]
    print(f"  Tables found in database ({len(existing_tables)}): {sorted(existing_tables)}")

    for tbl in EXPECTED_TABLES:
        if tbl not in existing_tables:
            errors.append(f"Missing expected table: {tbl}")
        else:
            print(f"  [PASS] Table exists: {tbl}")

    # 3. Verify Primary Keys
    for tbl, expected_pk in EXPECTED_PKS.items():
        if tbl not in existing_tables:
            continue
        cursor.execute(f"PRAGMA table_info({tbl});")
        cols = cursor.fetchall()
        actual_pk = [c[1] for c in cols if c[5] > 0]
        if actual_pk != expected_pk:
            errors.append(f"Table {tbl} primary key mismatch. Expected {expected_pk}, found {actual_pk}")
        else:
            print(f"  [PASS] {tbl} primary key verified: {actual_pk}")

    # 4. Verify Foreign Keys
    for tbl, expected_fks in EXPECTED_FKS.items():
        if tbl not in existing_tables:
            continue
        cursor.execute(f"PRAGMA foreign_key_list({tbl});")
        fks = cursor.fetchall()
        actual_fks = [(fk[3], fk[2], fk[4]) for fk in fks]
        for exp in expected_fks:
            if exp not in actual_fks:
                errors.append(f"Table {tbl} missing foreign key: {exp[0]} -> {exp[1]}({exp[2]})")
            else:
                print(f"  [PASS] {tbl} foreign key verified: {exp[0]} -> {exp[1]}({exp[2]})")

    # 5. Verify source_row_id is NOT NULL and UNIQUE in fact_flights
    if "fact_flights" in existing_tables:
        cursor.execute("PRAGMA table_info(fact_flights);")
        cols = cursor.fetchall()
        col_dict = {c[1]: {"notnull": c[3]} for c in cols}
        if "source_row_id" in col_dict:
            if col_dict["source_row_id"]["notnull"] == 1:
                print("  [PASS] fact_flights.source_row_id is constrained as NOT NULL.")
            else:
                errors.append("fact_flights.source_row_id is missing NOT NULL constraint.")
        else:
            errors.append("fact_flights is missing column source_row_id.")

        cursor.execute("PRAGMA index_list(fact_flights);")
        indexes = cursor.fetchall()
        has_unique_source_row_id = False
        for idx in indexes:
            idx_name = idx[1]
            is_unique = idx[2]
            if is_unique:
                cursor.execute(f"PRAGMA index_info({idx_name});")
                idx_cols = [row[2] for row in cursor.fetchall()]
                if idx_cols == ["source_row_id"]:
                    has_unique_source_row_id = True
                    break

        if has_unique_source_row_id:
            print("  [PASS] fact_flights.source_row_id has active UNIQUE constraint (auto-indexed).")
        else:
            errors.append("fact_flights.source_row_id lacks explicit UNIQUE constraint.")

    # 6. Verify staging_flights_raw has raw_id as sole INTEGER PK and all 31 source cols as TEXT
    if "staging_flights_raw" in existing_tables:
        cursor.execute("PRAGMA table_info(staging_flights_raw);")
        stg_cols = cursor.fetchall()
        # stg_cols format: (cid, name, type, notnull, dflt_value, pk)
        stg_col_map = {c[1]: {"type": c[2].upper(), "pk": c[5]} for c in stg_cols}
        
        # Verify raw_id is the only PK
        pks = [name for name, info in stg_col_map.items() if info["pk"] > 0]
        if pks == ["raw_id"] and stg_col_map["raw_id"]["type"] == "INTEGER":
            print("  [PASS] staging_flights_raw has 'raw_id' as sole INTEGER PRIMARY KEY.")
        else:
            errors.append(f"staging_flights_raw primary key invalid. Expected ['raw_id' INTEGER], found {pks}")

        # Verify all 31 source columns are TEXT
        non_text_cols = []
        missing_source_cols = []
        for col in STAGING_ORIGINAL_COLS:
            if col not in stg_col_map:
                missing_source_cols.append(col)
            elif stg_col_map[col]["type"] != "TEXT":
                non_text_cols.append((col, stg_col_map[col]["type"]))

        if missing_source_cols:
            errors.append(f"staging_flights_raw missing source columns: {missing_source_cols}")
        if non_text_cols:
            errors.append(f"staging_flights_raw source columns with non-TEXT affinity: {non_text_cols}")
        if not missing_source_cols and not non_text_cols:
            print(f"  [PASS] All {len(STAGING_ORIGINAL_COLS)} staging source columns verified with TEXT affinity.")

    conn.close()

    if errors:
        print("\n[FAIL] Schema verification failed with the following issues:")
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        raise RuntimeError("Schema verification failed.")
    else:
        print("\n[SUCCESS] All schema verification checks passed successfully!")

def main():
    print("=== FlightPulse Database Initialization Started ===")
    create_schema(DATABASE_PATH, SCHEMA_SQL_PATH)
    verify_schema(DATABASE_PATH)
    print("\nDatabase initialization complete. Ready for Step 4.2.")

if __name__ == "__main__":
    main()
