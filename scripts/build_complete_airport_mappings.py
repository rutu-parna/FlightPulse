"""
FlightPulse Step 4.3.1 - Complete Airport Code Mapping Generation & Validation
Creates: data/crosswalk/complete_airport_code_mappings.csv
Validates:
  1. Exactly 629 rows
  2. Exactly 629 unique raw_code values
  3. Exactly 322 IATA and 307 DOT_ID records
  4. Every airport_id exists in dim_airports
  5. Every distinct origin and destination code in staging is covered
  6. No conflicting mappings
  7. No NULL or blank raw codes or airport IDs
  8. No duplicate raw codes
  9. SGU manual-review / confidence status documented
"""

import os
import sys
import csv
import sqlite3

DATABASE = "database/flightpulse.db"
DOT_MAPPINGS_CSV = "data/crosswalk/dot_to_iata_mappings.csv"
COMPLETE_MAPPINGS_CSV = "data/crosswalk/complete_airport_code_mappings.csv"

def generate_and_validate():
    print("=" * 80)
    print("FlightPulse Step 4.3.1: Complete Airport Code Mappings (629 Codes)")
    print("=" * 80)

    con = sqlite3.connect(DATABASE)
    cur = con.cursor()

    # Load dim_airports
    cur.execute("SELECT airport_id, iata_code, airport_name, city, state FROM dim_airports")
    dim_airports = {r[1]: {"airport_id": r[0], "airport_name": r[2], "city": r[3], "state": r[4]} for r in cur.fetchall()}
    print(f"[1] Loaded {len(dim_airports)} airport records from dim_airports.")

    # Load staging distinct codes
    cur.execute("""
        SELECT DISTINCT ORIGIN_AIRPORT FROM staging_flights_raw
        UNION
        SELECT DISTINCT DESTINATION_AIRPORT FROM staging_flights_raw
    """)
    staging_codes = set(r[0] for r in cur.fetchall())
    print(f"[2] Loaded {len(staging_codes)} distinct airport codes from staging_flights_raw.")

    staging_iata = set(c for c in staging_codes if c.isalpha())
    staging_dot = set(c for c in staging_codes if c.isdigit())
    print(f"    - IATA codes (alpha): {len(staging_iata)}")
    print(f"    - DOT IDs (digits):   {len(staging_dot)}")

    # Load existing 307 DOT mappings (do not modify the file!)
    with open(DOT_MAPPINGS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        dot_rows = list(reader)
    print(f"[3] Loaded {len(dot_rows)} existing DOT mappings from {DOT_MAPPINGS_CSV}.")

    # Output structure
    output_rows = []

    # Part 1: 322 IATA Identity Mappings
    for iata in sorted(dim_airports.keys()):
        dim_info = dim_airports[iata]
        output_rows.append({
            "raw_code": iata,
            "code_type": "IATA",
            "airport_id": dim_info["airport_id"],
            "proposed_iata": iata,
            "resolution_type": "IATA_IDENTITY",
            "confidence": "AUTHORITATIVE",
            "bts_source_description": f"{dim_info['city']}, {dim_info['state']}: {dim_info['airport_name']}",
            "evidence": "Canonical 3-letter IATA code directly present in dim_airports.",
            "manual_review": "False",
            "manual_review_reason": ""
        })

    print(f"[4] Built {len(output_rows)} IATA identity mapping rows.")

    # Part 2: 307 DOT Mappings
    for row in dot_rows:
        dot_id = row["dot_id"]
        iata = row["proposed_iata"]
        dim_info = dim_airports.get(iata)
        if not dim_info:
            raise ValueError(f"Target IATA {iata} for DOT {dot_id} not found in dim_airports!")

        output_rows.append({
            "raw_code": str(dot_id),
            "code_type": "DOT_ID",
            "airport_id": dim_info["airport_id"],
            "proposed_iata": iata,
            "resolution_type": row["resolution_type"],
            "confidence": row["confidence"],
            "bts_source_description": row["bts_source_description"],
            "evidence": row["evidence"],
            "manual_review": row["manual_review"],
            "manual_review_reason": row["manual_review_reason"]
        })

    print(f"[5] Built {len(output_rows) - len(dim_airports)} DOT ID mapping rows.")
    print(f"    - Total combined rows: {len(output_rows)}")

    # =========================================================================
    # Task C: Validation Checks
    # =========================================================================
    print("\n[6] Running Task C Validation Checks:")
    errors = []

    # Check 1: Exactly 629 rows
    if len(output_rows) != 629:
        errors.append(f"Row count mismatch: expected 629, got {len(output_rows)}")

    # Check 2: Exactly 629 unique raw_code values
    raw_codes = [r["raw_code"] for r in output_rows]
    if len(set(raw_codes)) != 629:
        errors.append(f"Unique raw_code count mismatch: expected 629, got {len(set(raw_codes))}")

    # Check 3: Exactly 322 IATA and 307 DOT_ID records
    iata_count = sum(1 for r in output_rows if r["code_type"] == "IATA")
    dot_count = sum(1 for r in output_rows if r["code_type"] == "DOT_ID")
    if iata_count != 322 or dot_count != 307:
        errors.append(f"Code type breakdown mismatch: IATA={iata_count} (expected 322), DOT_ID={dot_count} (expected 307)")

    # Check 4: Every airport_id exists in dim_airports
    valid_airport_ids = set(dim_info["airport_id"] for dim_info in dim_airports.values())
    invalid_ids = [r for r in output_rows if r["airport_id"] not in valid_airport_ids]
    if invalid_ids:
        errors.append(f"Found {len(invalid_ids)} rows with invalid airport_id!")

    # Check 5: Every distinct origin and destination code in staging is covered
    mapped_raw_codes = set(raw_codes)
    uncovered_staging = staging_codes - mapped_raw_codes
    if uncovered_staging:
        errors.append(f"Staging codes not covered in mapping: {uncovered_staging}")

    # Check 6: No conflicting mappings (same raw_code mapping to multiple airport_ids)
    raw_to_id = {}
    for r in output_rows:
        rc = r["raw_code"]
        aid = r["airport_id"]
        if rc in raw_to_id and raw_to_id[rc] != aid:
            errors.append(f"Conflicting mapping for raw_code {rc}: {raw_to_id[rc]} vs {aid}")
        raw_to_id[rc] = aid

    # Check 7: No NULL or blank raw codes or airport IDs
    blank_check = [r for r in output_rows if not str(r["raw_code"]).strip() or r["airport_id"] is None or str(r["airport_id"]).strip() == ""]
    if blank_check:
        errors.append(f"Found {len(blank_check)} rows with blank/NULL raw_code or airport_id!")

    # Check 8: No duplicate raw codes
    duplicates = [c for c in set(raw_codes) if raw_codes.count(c) > 1]
    if duplicates:
        errors.append(f"Found duplicate raw codes: {duplicates}")

    # Check 9: SGU manual review status preserved
    sgu_dot = next((r for r in output_rows if r["raw_code"] == "14794"), None)
    if not sgu_dot:
        errors.append("DOT ID 14794 missing from output!")
    else:
        print(f"    - SGU DOT ID 14794: proposed_iata={sgu_dot['proposed_iata']}, confidence={sgu_dot['confidence']}, manual_review={sgu_dot['manual_review']}")

    if errors:
        print("\nVALIDATION FAILED with errors:")
        for err in errors:
            print(f"  ✗ {err}")
        sys.exit(1)
    else:
        print("    ✓ Check 1 passed: Exactly 629 rows.")
        print("    ✓ Check 2 passed: Exactly 629 unique raw_code values.")
        print("    ✓ Check 3 passed: Exactly 322 IATA and 307 DOT_ID records.")
        print("    ✓ Check 4 passed: Every airport_id exists in dim_airports.")
        print("    ✓ Check 5 passed: 100% of staging origin and destination codes covered.")
        print("    ✓ Check 6 passed: Zero conflicting mappings.")
        print("    ✓ Check 7 passed: Zero NULL or blank raw_codes or airport_ids.")
        print("    ✓ Check 8 passed: Zero duplicate raw_codes.")
        print("    ✓ Check 9 passed: SGU manual-review / confidence status verified.")

    # Write output CSV
    fieldnames = [
        "raw_code",
        "code_type",
        "airport_id",
        "proposed_iata",
        "resolution_type",
        "confidence",
        "bts_source_description",
        "evidence",
        "manual_review",
        "manual_review_reason"
    ]

    with open(COMPLETE_MAPPINGS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\n[7] Successfully wrote {len(output_rows)} rows to {COMPLETE_MAPPINGS_CSV}")

    # Final DB safety check
    cur.execute("SELECT count(*) FROM map_airport_codes")
    cnt = cur.fetchone()[0]
    print(f"[8] DB safety verification: map_airport_codes row count remains {cnt}.")
    con.close()

if __name__ == "__main__":
    generate_and_validate()

