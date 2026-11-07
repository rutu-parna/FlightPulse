# FlightPulse Airport Code Mapping Ingestion Report (Step 4.3.2)

**Execution Date**: 2026-11-08  
**Database**: `database/flightpulse.db`  
**Target Table**: `map_airport_codes`  
**Source Dataset**: `data/crosswalk/complete_airport_code_mappings.csv`  
**Script**: `scripts/load_airport_mappings.py`  
**Status**: Completed successfully without errors or foreign-key violations.

---

## 1. Executive Summary

In Step 4.3.2 of the FlightPulse implementation, `map_airport_codes` was populated from the validated crosswalk file `data/crosswalk/complete_airport_code_mappings.csv`.

- **Total Ingested Rows**: **629**
- **Table State Prior to Ingestion**: Verified empty (0 records).
- **Transaction Safety**: All 629 records were inserted inside a single atomic SQLite transaction using parameterized batch execution (`executemany`).
- **Referential Integrity**: 100% of foreign keys resolve to canonical facilities in `dim_airports` (IDs 1–322). `PRAGMA foreign_key_check` reported **0 violations**.
- **Coverage**: 100% of distinct origin and destination codes across all 5,819,079 rows in `staging_flights_raw` resolve to an airport facility.
- **Audit Metadata Preservation**: In compliance with database constraints, `map_airport_codes` stores only schema-defined columns (`raw_code`, `airport_id`, `code_type`). Detailed audit provenance (resolution type, evidence, confidence level, and manual review notes) is preserved in `data/crosswalk/complete_airport_code_mappings.csv` and `data/crosswalk/dot_to_iata_mappings.csv`.

---

## 2. Ingestion Details & Methodology

### 2.1 Source File & Row Breakdown
- **File**: `data/crosswalk/complete_airport_code_mappings.csv`
- **Total Validated Records**: 629
- **Code Type Distribution**:
  - `IATA` (Canonical 3-letter alphabetic identifiers for Jan–Sep & Nov–Dec flights): **322 records**
  - `DOT_ID` (USDOT BTS 5-digit numeric identifiers for October flights): **307 records**

### 2.2 Pre-Ingestion Guardrails
Prior to starting the database transaction, `scripts/load_airport_mappings.py` programmatically validated:
1. `map_airport_codes` was completely empty (0 rows).
2. Exactly 629 records were present in the source file with 0 empty or NULL raw codes or airport IDs.
3. All 629 raw codes were mutually exclusive (no duplicate codes).
4. All referenced `airport_id` values existed in `dim_airports`.
5. Every distinct origin and destination airport in `staging_flights_raw` was accounted for.
6. Zero conflicting mappings existed (no raw code mapped to multiple distinct airport IDs).

### 2.3 Transaction Handling & Execution
- **Transaction Control**: Atomic `BEGIN TRANSACTION;` $\rightarrow$ `executemany(...)` $\rightarrow$ `COMMIT;` with automatic `ROLLBACK;` upon any unexpected exception.
- **SQL Statement**:
  ```sql
  INSERT INTO map_airport_codes (raw_code, airport_id, code_type)
  VALUES (?, ?, ?);
  ```
- **Execution Duration**: **10.35 seconds** (including full staging scans for origin and destination verification).

---

## 3. Database Table Counts (Before vs. After)

```text
Table Name                 Before Count   After Count   Change    Status
---------------------------------------------------------------------------------
staging_flights_raw           5,819,079     5,819,079        0    Unmodified
dim_airlines                         14            14        0    Unmodified
dim_cancellation_reasons              4             4        0    Unmodified
dim_dates                           365           365        0    Unmodified
dim_airports                        322           322        0    Unmodified
map_airport_codes                     0           629     +629    POPULATED (Step 4.3.2)
fact_flights                          0             0        0    Pending Fact Step
---------------------------------------------------------------------------------
PRAGMA foreign_key_check:             0             0        0    PASSED (0 violations)
```

---

## 4. Post-Insertion Verification

1. **Table Volume**: `map_airport_codes` contains exactly 629 records.
2. **Code Type Breakdown**:
   - `SELECT count(*) FROM map_airport_codes WHERE code_type = 'IATA'` $\rightarrow$ **322**
   - `SELECT count(*) FROM map_airport_codes WHERE code_type = 'DOT_ID'` $\rightarrow$ **307**
3. **Operational Resolution (Staging Coverage)**:
   - Distinct unmapped origins: **0**
   - Distinct unmapped destinations: **0**
   - Unmapped staging flights: **0**
4. **Foreign Key Integrity**:
   - `PRAGMA foreign_key_check(map_airport_codes)` returned **0 violations**.
   - Full database `PRAGMA foreign_key_check` returned **0 violations**.

---

## 5. SGU (`14794` $\rightarrow$ `SGU`) Audit Status

In the database, the record was inserted strictly according to DDL specifications:
```sql
('14794', 281, 'DOT_ID') -- References dim_airports.airport_id 281 ('SGU', 'St. George Regional Airport')
```
The audit limitation remains formally documented in `data/crosswalk/complete_airport_code_mappings.csv` and `data/crosswalk/dot_to_iata_mappings.csv`:
- **Resolution Type**: `FACILITY_RENAME_RECONCILIATION`
- **Confidence**: `MEDIUM`
- **Manual Review Flag**: `True`
- **Reason**: BTS maintained `AirportID 14794` across the 2011 physical relocation of the airport facility, incrementing `AirportSeqID` while retaining the station ID. However, the legacy textual description in BTS `L_AIRPORT_ID` retains the municipal airfield title (`"St. George, UT: St George Municipal"`).

