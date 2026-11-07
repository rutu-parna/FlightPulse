"""
FlightPulse Step 4.3.2 - Load Airport Mappings
Script: scripts/load_airport_mappings.py

Loads validated airport mappings from data/crosswalk/complete_airport_code_mappings.csv
into map_airport_codes.

Requirements:
1. Connects to database/flightpulse.db with foreign keys enabled.
2. Reads complete_airport_code_mappings.csv (validates 629 records: 322 IATA, 307 DOT_ID).
3. Verifies raw codes are unique and non-empty.
4. Verifies all airport_id values exist in dim_airports.
5. Verifies all distinct origin/destination codes in staging_flights_raw are covered.
6. Verifies no conflicting mappings exist.
7. Confirms map_airport_codes is empty before insertion; stops without modifying anything if not empty.
8. Inserts all records inside one SQLite transaction using parameterized executemany.
9. Rolls back the transaction if any error occurs.
10. Validates table state post-insertion.
"""

import os
import sys
import csv
import time
import sqlite3

DATABASE = "database/flightpulse.db"
MAPPINGS_CSV = "data/crosswalk/complete_airport_code_mappings.csv"

def load_airport_mappings():
    start_time = time.time()
    print("=" * 80)
    print("FlightPulse Step 4.3.2: Populate map_airport_codes")
    print("=" * 80)

    # 1. Check prerequisites
    if not os.path.exists(DATABASE):
        print(f"ERROR: Database file {DATABASE} not found!", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(MAPPINGS_CSV):
        print(f"ERROR: Mapping CSV {MAPPINGS_CSV} not found!", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(DATABASE)
    con.execute("PRAGMA foreign_keys = ON;")
    cur = con.cursor()

    try:
        # 2. Check that map_airport_codes is currently empty
        cur.execute("SELECT count(*) FROM map_airport_codes")
        initial_count = cur.fetchone()[0]
        print(f"[1] Initial map_airport_codes row count: {initial_count}")
        if initial_count != 0:
            print("ERROR: map_airport_codes is not empty! Aborting without modifying data.", file=sys.stderr)
            con.close()
            sys.exit(1)

        # 3. Read complete_airport_code_mappings.csv
        print(f"[2] Reading {MAPPINGS_CSV}...")
        with open(MAPPINGS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"    - Read {len(rows)} rows from CSV.")

        # 4. Validate exact 629 records (322 IATA, 307 DOT_ID)
        if len(rows) != 629:
            raise ValueError(f"Expected exactly 629 rows, found {len(rows)}.")

        iata_rows = [r for r in rows if r["code_type"] == "IATA"]
        dot_rows = [r for r in rows if r["code_type"] == "DOT_ID"]
        if len(iata_rows) != 322 or len(dot_rows) != 307:
            raise ValueError(f"Expected 322 IATA and 307 DOT_ID rows; found {len(iata_rows)} IATA and {len(dot_rows)} DOT_ID.")

        # 5. Check uniqueness and non-emptiness of raw codes
        raw_codes = [r["raw_code"].strip() for r in rows]
        if any(not c for c in raw_codes):
            raise ValueError("Found empty or blank raw_code in mappings CSV.")

        if len(set(raw_codes)) != 629:
            raise ValueError(f"Expected 629 unique raw_code values, found {len(set(raw_codes))}.")

        # 6. Verify airport_id values exist in dim_airports
        cur.execute("SELECT airport_id FROM dim_airports")
        valid_airport_ids = set(r[0] for r in cur.fetchall())
        for r in rows:
            aid = int(r["airport_id"])
            if aid not in valid_airport_ids:
                raise ValueError(f"Referenced airport_id {aid} for raw_code {r['raw_code']} does not exist in dim_airports.")

        # 7. Verify all 629 distinct staging codes are covered
        cur.execute("""
            SELECT DISTINCT ORIGIN_AIRPORT FROM staging_flights_raw
            UNION
            SELECT DISTINCT DESTINATION_AIRPORT FROM staging_flights_raw
        """)
        staging_distinct = set(r[0] for r in cur.fetchall())
        missing_from_csv = staging_distinct - set(raw_codes)
        if missing_from_csv:
            raise ValueError(f"Staging codes missing from mapping CSV: {missing_from_csv}")

        # 8. Check for conflicting mappings (raw_code mapping to multiple airport_ids)
        mapping_dict = {}
        for r in rows:
            rc = r["raw_code"]
            aid = int(r["airport_id"])
            if rc in mapping_dict and mapping_dict[rc] != aid:
                raise ValueError(f"Conflicting mapping for raw_code {rc}: {mapping_dict[rc]} vs {aid}")
            mapping_dict[rc] = aid

        print("[3] Pre-insertion validation passed successfully:")
        print("    - 629 total rows verified (322 IATA, 307 DOT_ID)")
        print("    - 629 unique, non-empty raw_code values")
        print("    - 100% valid dim_airports foreign keys")
        print("    - 100% coverage of staging origin and destination codes")
        print("    - Zero conflicting mappings")

        # 9. Prepare insert parameters
        insert_data = [
            (r["raw_code"].strip(), int(r["airport_id"]), r["code_type"].strip())
            for r in rows
        ]

        # 10. Execute insertion in one transaction
        print("[4] Inserting 629 records into map_airport_codes inside a single transaction...")
        con.execute("BEGIN TRANSACTION;")
        cur.executemany("""
            INSERT INTO map_airport_codes (raw_code, airport_id, code_type)
            VALUES (?, ?, ?)
        """, insert_data)
        con.commit()
        print("    ✓ Transaction committed successfully.")

        # 11. Post-insertion validation
        print("[5] Running post-insertion validation...")
        cur.execute("SELECT count(*) FROM map_airport_codes")
        final_count = cur.fetchone()[0]
        if final_count != 629:
            raise ValueError(f"Post-insertion count mismatch: expected 629, got {final_count}")

        cur.execute("SELECT count(*) FROM map_airport_codes WHERE code_type = 'IATA'")
        final_iata = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM map_airport_codes WHERE code_type = 'DOT_ID'")
        final_dot = cur.fetchone()[0]
        if final_iata != 322 or final_dot != 307:
            raise ValueError(f"Post-insertion code_type mismatch: IATA={final_iata}, DOT_ID={final_dot}")

        # Verify distinct origins and destinations resolve
        cur.execute("""
            SELECT count(DISTINCT s.ORIGIN_AIRPORT)
            FROM staging_flights_raw s
            LEFT JOIN map_airport_codes m ON s.ORIGIN_AIRPORT = m.raw_code
            WHERE m.raw_code IS NULL
        """)
        unmapped_origins = cur.fetchone()[0]
        if unmapped_origins != 0:
            raise ValueError(f"Found {unmapped_origins} unmapped distinct ORIGIN_AIRPORT values!")

        cur.execute("""
            SELECT count(DISTINCT s.DESTINATION_AIRPORT)
            FROM staging_flights_raw s
            LEFT JOIN map_airport_codes m ON s.DESTINATION_AIRPORT = m.raw_code
            WHERE m.raw_code IS NULL
        """)
        unmapped_dests = cur.fetchone()[0]
        if unmapped_dests != 0:
            raise ValueError(f"Found {unmapped_dests} unmapped distinct DESTINATION_AIRPORT values!")

        # Verify foreign keys using PRAGMA
        cur.execute("PRAGMA foreign_key_check(map_airport_codes)")
        fk_violations = cur.fetchall()
        if fk_violations:
            raise ValueError(f"PRAGMA foreign_key_check reported {len(fk_violations)} violations: {fk_violations}")

        elapsed = time.time() - start_time
        print("\n[6] POST-INSERTION VALIDATION PASSED:")
        print(f"    - map_airport_codes total rows: {final_count}")
        print(f"    - IATA records:                  {final_iata}")
        print(f"    - DOT_ID records:                {final_dot}")
        print(f"    - Unmapped origins:              {unmapped_origins}")
        print(f"    - Unmapped destinations:         {unmapped_dests}")
        print(f"    - Foreign key violations:        {len(fk_violations)}")
        print(f"    - Execution elapsed time:        {elapsed:.4f} seconds")

    except Exception as e:
        con.rollback()
        print(f"\nERROR OCCURRED: {e}", file=sys.stderr)
        print("Transaction rolled back. No changes made.", file=sys.stderr)
        con.close()
        sys.exit(1)

    con.close()
    return True

if __name__ == "__main__":
    load_airport_mappings()

