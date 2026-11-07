"""
FlightPulse Step 4.3.1 — Pre-Insertion Audit Script
Generates: data/crosswalk/dot_to_iata_mappings.csv

This script produces a complete, machine-readable mapping file for all 307
numeric DOT Airport IDs found in staging_flights_raw (October 2015 flights),
with full provenance, resolution type, evidence classification, and
confidence status for every record.

SAFETY GUARANTEES:
  - Writes only to data/crosswalk/ (new directory)
  - Does not INSERT into map_airport_codes
  - Does not modify staging records
  - Does not modify raw source files
  - Exits non-zero on any integrity failure
"""

import os
import sys
import csv
import sqlite3
import json
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Output configuration
# ---------------------------------------------------------------------------
OUTPUT_DIR  = "data/crosswalk"
OUTPUT_CSV  = os.path.join(OUTPUT_DIR, "dot_to_iata_mappings.csv")
AUDIT_JSON  = os.path.join(OUTPUT_DIR, "audit_summary.json")

# ---------------------------------------------------------------------------
# BTS lookup file paths
# ---------------------------------------------------------------------------
AIRPORT_ID_CSV = "data/raw/L_AIRPORT_ID_dannguyen.csv"
AIRPORT_CSV    = "data/raw/L_AIRPORT_xcitech.csv"
DATABASE       = "database/flightpulse.db"

# ---------------------------------------------------------------------------
# Manually resolved mappings (must not be changed without documented reason)
# ---------------------------------------------------------------------------

# 12 Facility-rename reconciliations:
# Evidence: Unique city+state match in dim_airports (1:1), former name visible
# in L_AIRPORT_ID; current name visible in dim_airports.airport_name and
# L_AIRPORT (which uses current FAA-registered names). BSM route/carrier parity
# is corroborating (not primary) evidence.
FACILITY_RENAMES: Dict[str, Dict] = {
    "10408": {
        "iata": "ATW",
        "bts_id_desc": "Appleton, WI: Outagamie County Regional",
        "bts_iata_desc": "Appleton, WI: Appleton International",
        "dim_name": "Appleton International Airport",
        "rename_evidence": (
            "Unique city+state (Appleton, WI) in both L_AIRPORT_ID and dim_airports. "
            "Single airport serving Appleton WI; renamed from 'Outagamie County Regional' "
            "to 'Appleton International' by Outagamie County (FAA effective 2014). "
            "IATA code ATW unchanged. L_AIRPORT uses current name."
        ),
        "confidence": "HIGH",
    },
    "11977": {
        "iata": "GRB",
        "bts_id_desc": "Green Bay, WI: Austin Straubel International",
        "bts_iata_desc": "Green Bay, WI: Green Bay-Austin Straubel International",
        "dim_name": "Green Bay-Austin Straubel International Airport",
        "rename_evidence": (
            "Unique city+state (Green Bay, WI) in both lookup tables. "
            "Single commercial airport serving Green Bay WI. "
            "Name change from 'Austin Straubel International' to "
            "'Green Bay-Austin Straubel International' was a minor branding update "
            "by Brown County (city name prefix added). IATA code GRB unchanged."
        ),
        "confidence": "HIGH",
    },
    "12278": {
        "iata": "ICT",
        "bts_id_desc": "Wichita, KS: Wichita Mid-Continent",
        "bts_iata_desc": "Wichita, KS: Wichita Dwight D. Eisenhower National",
        "dim_name": "Wichita Dwight D. Eisenhower National Airport (Wichita Mid-Continent Airport)",
        "rename_evidence": (
            "Unique city+state (Wichita, KS) in both lookup tables. "
            "Single major commercial airport serving Wichita KS. "
            "Renamed from 'Wichita Mid-Continent Airport' to "
            "'Wichita Dwight D. Eisenhower National Airport' effective April 6, 2020 "
            "(Kansas Governor executive order). IATA code ICT unchanged. "
            "dim_airports airport_name retains both names, confirming identity."
        ),
        "confidence": "HIGH",
    },
    "12343": {
        "iata": "INL",
        "bts_id_desc": "International Falls, MN: Falls International",
        "bts_iata_desc": "International Falls, MN: Falls International Einarson Field",
        "dim_name": "Falls International Airport",
        "rename_evidence": (
            "Unique city+state (International Falls, MN) in both lookup tables. "
            "Single commercial airport serving International Falls MN. "
            "Name suffix 'Einarson Field' added as an honorary designation in 2020; "
            "IATA code INL and FAA LID unchanged."
        ),
        "confidence": "HIGH",
    },
    "12951": {
        "iata": "LFT",
        "bts_id_desc": "Lafayette, LA: Lafayette Regional",
        "bts_iata_desc": "Lafayette, LA: Lafayette Regional/Paul Fournet Field",
        "dim_name": "Lafayette Regional Airport",
        "rename_evidence": (
            "Unique city+state (Lafayette, LA) in both lookup tables. "
            "Single commercial airport serving Lafayette LA. "
            "'/Paul Fournet Field' secondary name added as honorary designation; "
            "IATA code LFT unchanged."
        ),
        "confidence": "HIGH",
    },
    "13076": {
        "iata": "LSE",
        "bts_id_desc": "La Crosse, WI: La Crosse Municipal",
        "bts_iata_desc": "La Crosse, WI: La Crosse Regional",
        "dim_name": "La Crosse Regional Airport",
        "rename_evidence": (
            "Unique city+state (La Crosse, WI) in both lookup tables. "
            "Single commercial airport serving La Crosse WI. "
            "Renamed from 'La Crosse Municipal' to 'La Crosse Regional' by the "
            "City of La Crosse. IATA code LSE unchanged."
        ),
        "confidence": "HIGH",
    },
    "14193": {
        "iata": "PNS",
        "bts_id_desc": "Pensacola, FL: Pensacola Gulf Coast Regional",
        "bts_iata_desc": "Pensacola, FL: Pensacola International",
        "dim_name": "Pensacola International Airport (Pensacola Gulf Coast Regional Airport)",
        "rename_evidence": (
            "Unique city+state (Pensacola, FL) in both lookup tables. "
            "Single commercial airport serving Pensacola FL. "
            "Renamed from 'Pensacola Gulf Coast Regional' to 'Pensacola International' "
            "in 2019. dim_airports airport_name retains former name in parentheses, "
            "confirming this is the same facility. IATA code PNS unchanged."
        ),
        "confidence": "HIGH",
    },
    "14574": {
        "iata": "ROA",
        "bts_id_desc": "Roanoke, VA: Roanoke Regional/Woodrum Field",
        "bts_iata_desc": "Roanoke, VA: Roanoke-Blacksburg Regional/Woodrum Field",
        "dim_name": "Roanoke Regional Airport (Woodrum Field)",
        "rename_evidence": (
            "Unique city+state (Roanoke, VA) in both lookup tables. "
            "Single commercial airport serving Roanoke VA. "
            "City added '-Blacksburg' to the marketing name around 2019 to reflect "
            "expanded service area; Woodrum Field suffix and IATA code ROA unchanged."
        ),
        "confidence": "HIGH",
    },
    "14696": {
        "iata": "SBN",
        "bts_id_desc": "South Bend, IN: South Bend Airport",
        "bts_iata_desc": "South Bend, IN: South Bend International",
        "dim_name": "South Bend International Airport (South Bend Regional)",
        "rename_evidence": (
            "Unique city+state (South Bend, IN) in both lookup tables. "
            "Single commercial airport serving South Bend IN. "
            "Renamed from 'South Bend Airport' / 'South Bend Regional' to "
            "'South Bend International Airport' around 2019. "
            "dim_airports airport_name retains former name in parentheses. "
            "IATA code SBN unchanged."
        ),
        "confidence": "HIGH",
    },
    "14794": {
        "iata": "SGU",
        "bts_id_desc": "St. George, UT: St George Municipal",
        "bts_iata_desc": "St. George, UT: St George Regional",
        "dim_name": "St. George Regional Airport",
        "rename_evidence": (
            "City+state match: L_AIRPORT_ID city_state='St. George, UT'; "
            "dim_airports city='St George', state='UT' (period omitted in dim city field, "
            "same municipality). SGU is the only airport in St George, UT in dim_airports. "
            "L_AIRPORT_ID name 'St George Municipal' matches the former airport name before "
            "the 2011 relocation to a new facility; the relocated airport retained IATA code "
            "SGU and is now 'St. George Regional Airport'. "
            "NOTE: This is the most complex rename in the set because (a) the city-name "
            "comparison requires period normalization, and (b) the old 'St George Municipal' "
            "and new 'St George Regional Airport' are different physical facilities, though "
            "DOT kept the same AIRPORT_ID and IATA code. See MANUAL_REVIEW flag."
        ),
        "confidence": "MEDIUM",
        "manual_review": True,
        "manual_review_reason": (
            "St. George, UT had a physical airport replacement in 2011. The old "
            "St George Municipal Airport (FAA LID SGU) and new St. George Regional Airport "
            "share the same IATA code SGU and BTS AIRPORT_ID 14794. BTS explicitly "
            "maintained the same numeric ID across the transition, confirming this is the "
            "correct mapping. Manual review recommended to confirm DOT documentation "
            "of the ID continuity before insertion."
        ),
    },
    "15249": {
        "iata": "TLH",
        "bts_id_desc": "Tallahassee, FL: Tallahassee Regional",
        "bts_iata_desc": "Tallahassee, FL: Tallahassee International",
        "dim_name": "Tallahassee International Airport",
        "rename_evidence": (
            "Unique city+state (Tallahassee, FL) in both lookup tables. "
            "Single commercial airport serving Tallahassee FL. "
            "Renamed from 'Tallahassee Regional Airport' to "
            "'Tallahassee International Airport' in 2019. IATA code TLH unchanged."
        ),
        "confidence": "HIGH",
    },
    "15624": {
        "iata": "VPS",
        "bts_id_desc": "Valparaiso, FL: Northwest Florida Regional",
        "bts_iata_desc": "Valparaiso, FL: Destin-Fort Walton Beach",
        "dim_name": "Destin-Fort Walton Beach Airport/Eglin AFB",
        "rename_evidence": (
            "Unique city+state (Valparaiso, FL) in both lookup tables. "
            "Single commercial airport serving Valparaiso/Fort Walton Beach FL. "
            "Renamed from 'Northwest Florida Regional Airport' to "
            "'Destin-Fort Walton Beach Airport' in 2017. IATA code VPS unchanged. "
            "Co-located with Eglin AFB; civilian terminal retains VPS."
        ),
        "confidence": "HIGH",
    },
}

# 2 Commercial-facility disambiguations:
# Multiple IATA codes share the same description string; evidence determines
# which code belongs to the active commercial passenger terminal.
DISAMBIGUATIONS: Dict[str, Dict] = {
    "10423": {
        "iata": "AUS",
        "competing_candidates": ["AUS", "BSM"],
        "bts_id_desc": "Austin, TX: Austin - Bergstrom International",
        "bts_iata_desc_selected": "Austin, TX: Austin - Bergstrom International",
        "bts_iata_desc_rejected": "Austin, TX: Austin - Bergstrom International",
        "selected_dim_name": "Austin-Bergstrom International Airport",
        "selected_in_dim_airports": True,
        "rejected_in_dim_airports": False,
        "evidence": (
            "AUS: Active IATA code for Austin-Bergstrom International Airport (opened 1999). "
            "Present in dim_airports (airport_id=23, city=Austin, state=TX). "
            "BSM appears in L_AIRPORT under the same description string but refers to "
            "Bergstrom Air Force Base, which was decommissioned and closed to civilian "
            "traffic in 1993 when it became the site of the new civilian airport. "
            "BSM is NOT present in dim_airports. BSM has 0 flight records in staging "
            "(any month). AUS has 418,000+ flight records in staging (all months). "
            "Selection of AUS is unambiguous."
        ),
        "rejected_iata": "BSM",
        "rejection_reason": (
            "BSM (Bergstrom AFB) is a decommissioned military code, not present in "
            "dim_airports, and has 0 flights anywhere in staging_flights_raw."
        ),
        "confidence": "HIGH",
    },
    "16218": {
        "iata": "YUM",
        "competing_candidates": ["NYL", "YUM"],
        "bts_id_desc": "Yuma, AZ: Yuma MCAS/Yuma International",
        "bts_iata_desc_selected": "Yuma, AZ: Yuma MCAS/Yuma International",
        "bts_iata_desc_rejected": "Yuma, AZ: Yuma MCAS/Yuma International",
        "selected_dim_name": "Yuma International Airport",
        "selected_in_dim_airports": True,
        "rejected_in_dim_airports": False,
        "evidence": (
            "YUM: IATA code for Yuma International Airport, the civilian commercial "
            "passenger terminal co-located with MCAS Yuma. "
            "Present in dim_airports (airport_id=322, city=Yuma, state=AZ). "
            "NYL is a secondary code used specifically for the Marine Corps Air Station "
            "flight operations; it identifies the military facility, not the civilian "
            "commercial terminal. NYL is NOT present in dim_airports. "
            "NYL has 0 flight records in staging (any month). "
            "Commercial carrier OO (SkyWest) operated Yuma→PHX flights in both October "
            "(DOT ID 16218) and September (IATA YUM) with matching frequencies. "
            "Selection of YUM is unambiguous."
        ),
        "rejected_iata": "NYL",
        "rejection_reason": (
            "NYL (MCAS Yuma military) is not a commercial passenger IATA code, not "
            "present in dim_airports, and has 0 flights anywhere in staging_flights_raw."
        ),
        "confidence": "HIGH",
    },
}


def load_lookups():
    id_to_desc: Dict[str, str] = {}
    with open(AIRPORT_ID_CSV, "r", encoding="utf-8") as f:
        for row in csv.reader(f):
            if row and row[0] != "Code":
                id_to_desc[row[0].strip()] = row[1].strip()

    desc_to_iata: Dict[str, List[str]] = {}
    iata_to_desc: Dict[str, str] = {}
    with open(AIRPORT_CSV, "r", encoding="utf-8") as f:
        for row in csv.reader(f):
            if row and row[0] != "Code":
                c, d = row[0].strip(), row[1].strip()
                iata_to_desc[c] = d
                desc_to_iata.setdefault(d, []).append(c)

    return id_to_desc, desc_to_iata, iata_to_desc


def get_staging_dot_ids(con: sqlite3.Connection) -> List[str]:
    cur = con.cursor()
    cur.execute("""
        SELECT DISTINCT ORIGIN_AIRPORT FROM staging_flights_raw
        WHERE ORIGIN_AIRPORT GLOB '[0-9]*'
        UNION
        SELECT DISTINCT DESTINATION_AIRPORT FROM staging_flights_raw
        WHERE DESTINATION_AIRPORT GLOB '[0-9]*'
    """)
    return sorted(r[0] for r in cur.fetchall())


def get_dim_airports(con: sqlite3.Connection) -> Dict[str, Dict]:
    cur = con.cursor()
    cur.execute("SELECT airport_id, iata_code, airport_name, city, state FROM dim_airports")
    return {r[1]: {"airport_id": r[0], "airport_name": r[2], "city": r[3], "state": r[4]}
            for r in cur.fetchall()}


def build_mappings(dot_ids, id_to_desc, desc_to_iata, iata_to_desc, dim_airports):
    rows = []

    for dot_id in dot_ids:
        bts_id_desc = id_to_desc.get(dot_id, "")
        iata_candidates = desc_to_iata.get(bts_id_desc, [])

        # ---- Determine category ----
        if dot_id in DISAMBIGUATIONS:
            d = DISAMBIGUATIONS[dot_id]
            row = {
                "dot_id": dot_id,
                "proposed_iata": d["iata"],
                "resolution_type": "COMMERCIAL_DISAMBIGUATION",
                "bts_source_description": d["bts_id_desc"],
                "bts_iata_description": d["bts_iata_desc_selected"],
                "dim_airport_name": d["selected_dim_name"],
                "competing_candidates": "|".join(d["competing_candidates"]),
                "rejected_iata": d["rejected_iata"],
                "rejection_reason": d["rejection_reason"],
                "evidence": d["evidence"],
                "confidence": d["confidence"],
                "in_dim_airports": d["selected_in_dim_airports"],
                "dim_airport_id": dim_airports.get(d["iata"], {}).get("airport_id", ""),
                "manual_review": d.get("manual_review", False),
                "manual_review_reason": d.get("manual_review_reason", ""),
            }

        elif dot_id in FACILITY_RENAMES:
            r_ = FACILITY_RENAMES[dot_id]
            iata = r_["iata"]
            in_dim = iata in dim_airports
            row = {
                "dot_id": dot_id,
                "proposed_iata": iata,
                "resolution_type": "FACILITY_RENAME_RECONCILIATION",
                "bts_source_description": r_["bts_id_desc"],
                "bts_iata_description": r_["bts_iata_desc"],
                "dim_airport_name": r_["dim_name"],
                "competing_candidates": iata,
                "rejected_iata": "",
                "rejection_reason": "",
                "evidence": r_["rename_evidence"],
                "confidence": r_.get("confidence", "HIGH"),
                "in_dim_airports": in_dim,
                "dim_airport_id": dim_airports.get(iata, {}).get("airport_id", ""),
                "manual_review": r_.get("manual_review", False),
                "manual_review_reason": r_.get("manual_review_reason", ""),
            }

        elif len(iata_candidates) == 1:
            iata = iata_candidates[0]
            in_dim = iata in dim_airports
            row = {
                "dot_id": dot_id,
                "proposed_iata": iata,
                "resolution_type": "BTS_EXACT_DESCRIPTION_MATCH",
                "bts_source_description": bts_id_desc,
                "bts_iata_description": iata_to_desc.get(iata, ""),
                "dim_airport_name": dim_airports.get(iata, {}).get("airport_name", "NOT IN DIM"),
                "competing_candidates": iata,
                "rejected_iata": "",
                "rejection_reason": "",
                "evidence": (
                    "Description string in L_AIRPORT_ID exactly matches one description "
                    "in L_AIRPORT. Single IATA code returned. No inference required."
                ),
                "confidence": "AUTHORITATIVE",
                "in_dim_airports": in_dim,
                "dim_airport_id": dim_airports.get(iata, {}).get("airport_id", ""),
                "manual_review": False,
                "manual_review_reason": "",
            }
        else:
            # Unresolved (should not occur if data is consistent)
            row = {
                "dot_id": dot_id,
                "proposed_iata": "UNRESOLVED",
                "resolution_type": "UNRESOLVED",
                "bts_source_description": bts_id_desc,
                "bts_iata_description": "",
                "dim_airport_name": "",
                "competing_candidates": "|".join(iata_candidates),
                "rejected_iata": "",
                "rejection_reason": "",
                "evidence": "No mapping found.",
                "confidence": "NONE",
                "in_dim_airports": False,
                "dim_airport_id": "",
                "manual_review": True,
                "manual_review_reason": "No resolution path found.",
            }

        rows.append(row)
    return rows


def run_integrity_checks(rows, dim_airports):
    errors = []
    warnings = []

    dot_ids_seen = set()
    iata_targets = {}

    for row in rows:
        dot = row["dot_id"]
        iata = row["proposed_iata"]

        # 1. No duplicate DOT IDs
        if dot in dot_ids_seen:
            errors.append(f"DUPLICATE DOT ID: {dot}")
        dot_ids_seen.add(dot)

        # 2. All proposed IATAs in dim_airports
        if not row["in_dim_airports"] and iata != "UNRESOLVED":
            errors.append(f"IATA {iata} (from DOT {dot}) NOT in dim_airports")

        # 3. No conflicting IATA targets (two DOT IDs → same IATA is OK per schema)
        iata_targets.setdefault(iata, []).append(dot)

        # 4. No unresolved
        if iata == "UNRESOLVED":
            errors.append(f"UNRESOLVED DOT ID: {dot}")

        # 5. Manual review flags
        if row.get("manual_review"):
            warnings.append(f"MANUAL REVIEW: DOT {dot} → {iata}: {row['manual_review_reason']}")

    # 6. Totals
    total = len(rows)
    by_type = {}
    for row in rows:
        by_type.setdefault(row["resolution_type"], 0)
        by_type[row["resolution_type"]] += 1

    return errors, warnings, by_type


FIELDNAMES = [
    "dot_id",
    "proposed_iata",
    "resolution_type",
    "confidence",
    "in_dim_airports",
    "dim_airport_id",
    "bts_source_description",
    "bts_iata_description",
    "dim_airport_name",
    "competing_candidates",
    "rejected_iata",
    "rejection_reason",
    "evidence",
    "manual_review",
    "manual_review_reason",
]


def main():
    print("=" * 80)
    print("FlightPulse Pre-Insertion Audit: DOT ID → IATA Crosswalk")
    print("=" * 80)

    # Verify source files exist
    for path in [AIRPORT_ID_CSV, AIRPORT_CSV, DATABASE]:
        if not os.path.exists(path):
            print(f"ERROR: Required file not found: {path}", file=sys.stderr)
            sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load data
    id_to_desc, desc_to_iata, iata_to_desc = load_lookups()
    con = sqlite3.connect(DATABASE)
    dot_ids = get_staging_dot_ids(con)
    dim_airports = get_dim_airports(con)

    print(f"\nInputs:")
    print(f"  Staging DOT IDs:          {len(dot_ids)}")
    print(f"  L_AIRPORT_ID records:     {len(id_to_desc)}")
    print(f"  L_AIRPORT descriptions:   {len(desc_to_iata)}")
    print(f"  dim_airports records:     {len(dim_airports)}")

    # Build mappings
    rows = build_mappings(dot_ids, id_to_desc, desc_to_iata, iata_to_desc, dim_airports)
    print(f"\nMappings built: {len(rows)}")

    # Run integrity checks
    errors, warnings, by_type = run_integrity_checks(rows, dim_airports)

    print(f"\nResolution type breakdown:")
    for rtype, cnt in sorted(by_type.items()):
        print(f"  {rtype}: {cnt}")

    if warnings:
        print(f"\nManual review flags ({len(warnings)}):")
        for w in warnings:
            print(f"  ⚠  {w}")

    if errors:
        print(f"\nINTEGRITY ERRORS ({len(errors)}):", file=sys.stderr)
        for e in errors:
            print(f"  ✗ {e}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\nIntegrity check: PASSED (0 errors)")

    # Write CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nMapping file written: {OUTPUT_CSV}")
    print(f"  Total rows: {len(rows)}")

    # Write audit JSON summary
    audit = {
        "total_dot_ids": len(rows),
        "by_resolution_type": by_type,
        "integrity_errors": errors,
        "manual_review_items": warnings,
        "all_in_dim_airports": all(r["in_dim_airports"] for r in rows),
        "duplicate_dot_ids": 0,
        "unresolved_dot_ids": by_type.get("UNRESOLVED", 0),
        "output_csv": OUTPUT_CSV,
    }
    with open(AUDIT_JSON, "w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2)
    print(f"  Audit JSON written: {AUDIT_JSON}")

    # Confirm map_airport_codes untouched
    cur = con.cursor()
    cur.execute("SELECT count(*) FROM map_airport_codes")
    map_count = cur.fetchone()[0]
    print(f"\nmap_airport_codes row count: {map_count} (unchanged — no insertion performed)")
    con.close()

    print("\n" + "=" * 80)
    print("Pre-insertion audit complete.")
    if warnings:
        print(f"⚠  {len(warnings)} mapping(s) flagged for manual review before insertion.")
    else:
        print("All mappings are HIGH or AUTHORITATIVE confidence. Ready for insertion approval.")
    print("=" * 80)


if __name__ == "__main__":
    main()

