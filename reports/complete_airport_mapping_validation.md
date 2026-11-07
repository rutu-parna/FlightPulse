# FlightPulse Step 4.3.1 — Complete Airport Code Mapping Validation Report

**Date**: 2026-11-08  
**Generated Files**:
- `data/crosswalk/complete_airport_code_mappings.csv` (629 rows)
- `scripts/build_complete_airport_mappings.py` (Generation and validation script)
**Target Database**: `database/flightpulse.db`  
**Status**: Validation **PASSED** across all 9 integrity checks.

---

## 1. Executive Summary

This report completes **Step 4.3.1** of the FlightPulse implementation:
1. **Task A (SGU Deep-Dive Investigation)**: Authoritative USDOT Bureau of Transportation Statistics (BTS) documentation was examined regarding the 2011 relocation of St. George Airport (Utah). BTS TranStats Master Coordinate and On-Time Performance specifications confirm that BTS maintained **AirportID `14794`** across the transition while incrementing `AirportSeqID` (`1479401` $\rightarrow$ `1479402` $\rightarrow$ `1479405`). While continuity is corroborated by federal dataset architecture, its legacy label in `L_AIRPORT_ID` retains the historical facility designation. In accordance with strict auditing guidelines, the mapping is retained with **MEDIUM confidence** and the manual review flag is preserved.
2. **Task B (Complete Mapping Generation)**: Generated `data/crosswalk/complete_airport_code_mappings.csv` containing all **629 distinct raw codes** appearing in `staging_flights_raw` across the entire 2015 calendar year.
3. **Task C (Pre-Insertion Validation)**: Verified all 9 strict relational and operational criteria. Zero database modifications were made to `map_airport_codes` or any staging/dimension table.

---

## 2. Task A — Authoritative Investigation of DOT Airport ID 14794 (SGU)

### 2.1 Background
In January 2011, the original land-locked **St. George Municipal Airport** on the downtown mesa was closed and replaced by a brand-new facility, **St. George Regional Airport**, located southeast of the city. Both facilities have operated under IATA code `SGU`. In `L_AIRPORT_ID`, code `14794` is labeled as `"St. George, UT: St George Municipal"`.

### 2.2 Authoritative Source & Architecture Analysis

- **Authoritative Source**: U.S. Department of Transportation (USDOT) Bureau of Transportation Statistics (BTS) TranStats Aviation Support Tables — *Master Coordinate Table* and *Reporting Carrier On-Time Performance Data Dictionary*.
- **Official Documentation Reference**:
  - BTS Variable Definition: `AirportID` vs. `AirportSeqID` (`https://www.transtats.bts.gov/Fields.asp?Table_ID=236`)
  - BTS Lookup Table: `L_AIRPORT_ID` (`https://www.transtats.bts.gov/Download_Lookup.asp?Lookup=L_AIRPORT_ID`)
- **Key Technical Findings**:
  1. **BTS `AirportID` Design Principle**: The USDOT BTS TranStats schema explicitly defines `AirportID` (e.g., `14794`) as a *longitudinal constant* assigned to an airport market/station to support multi-decade trend analysis regardless of municipal name adjustments or facility rebuilds.
  2. **BTS `AirportSeqID` Evolution**: To account for physical coordinate shifts or terminal moves without breaking `AirportID` longitudinal continuity, BTS uses `AirportSeqID`. BTS TranStats records show sequence identifiers for St. George progressing from `1479401` (initial municipal airfield) to `1479402` and `1479405` (modern regional airport site), while the root `AirportID` remained strictly `14794`.
  3. **2015 Operating Context**: In the 2015 flight dataset, SkyWest Airlines (`OO`) operated scheduled passenger flights connecting St. George with Salt Lake City (`SLC` / DOT `14869`) and Denver (`DEN` / DOT `11292`). Carrier, route, and frequency parity between September 2015 (IATA `SGU`) and October 2015 (DOT `14794`) align 100%.

### 2.3 Confidence Assessment & Conclusion
- **Conclusion**: The mapping `14794` $\rightarrow$ `SGU` (`airport_id` = 281 in `dim_airports`) is verified by BTS TranStats architectural design and route mirroring.
- **Auditing Decision**: In strict compliance with the instruction that *"route parity alone must not be presented as authoritative identifier evidence"* and because the textual description in `L_AIRPORT_ID` retains the pre-relocation municipal label rather than the regional label, the mapping retains **`MEDIUM` confidence** with `manual_review = True`. This provides complete transparency for the eventual database insertion approval.

---

## 3. Task B — Structure of Complete Mapping File

The generated crosswalk file, `data/crosswalk/complete_airport_code_mappings.csv`, unifies all airport codes present in the raw landing layer:

```text
data/crosswalk/complete_airport_code_mappings.csv
├── Part 1: 322 Canonical IATA Identity Mappings (Jan–Sep, Nov–Dec staging codes)
└── Part 2: 307 USDOT Bureau of Transportation Statistics Numeric ID Mappings (October staging codes)
Total: 629 Rows
```

### Schema of `complete_airport_code_mappings.csv`
| Column | Type | Description |
| :--- | :--- | :--- |
| `raw_code` | TEXT | The raw string code appearing in `staging_flights_raw` |
| `code_type` | TEXT | `IATA` (3-letter alpha) or `DOT_ID` (5-digit numeric) |
| `airport_id` | INTEGER | Foreign key referencing canonical `dim_airports.airport_id` |
| `proposed_iata` | TEXT | Canonical 3-letter IATA code corresponding to the facility |
| `resolution_type` | TEXT | `IATA_IDENTITY`, `BTS_EXACT_DESCRIPTION_MATCH`, `FACILITY_RENAME_RECONCILIATION`, or `COMMERCIAL_DISAMBIGUATION` |
| `confidence` | TEXT | `AUTHORITATIVE`, `HIGH`, or `MEDIUM` |
| `bts_source_description` | TEXT | Facility name / location string from BTS reference |
| `evidence` | TEXT | Authoritative cross-reference and provenance justification |
| `manual_review` | TEXT | Boolean flag (`True` / `False`) |
| `manual_review_reason` | TEXT | Reason for manual review (if flagged) |

---

## 4. Task C — Pre-Insertion Validation Results

All 9 mandatory validation criteria were checked programmatically via `scripts/build_complete_airport_mappings.py`:

| # | Validation Requirement | Expected | Actual | Status |
| :-: | :--- | :---: | :---: | :---: |
| **1** | Total Row Count | Exactly 629 | **629** | **PASSED** |
| **2** | Unique `raw_code` Values | Exactly 629 | **629** | **PASSED** |
| **3** | Code Type Breakdown | 322 `IATA`, 307 `DOT_ID` | **322 IATA, 307 DOT_ID** | **PASSED** |
| **4** | Referential Integrity to `dim_airports` | 100% valid `airport_id` | **100% (IDs 1–322)** | **PASSED** |
| **5** | Staging Distinct Code Coverage | 100% (629 / 629) | **100% (0 missing)** | **PASSED** |
| **6** | Mapping Determinism (No Conflicts) | 0 ambiguous targets | **0 conflicts** | **PASSED** |
| **7** | Nullability Constraint Check | 0 NULL or blank fields | **0 NULL / blank** | **PASSED** |
| **8** | Duplicate Code Check | 0 duplicate `raw_code` | **0 duplicates** | **PASSED** |
| **9** | SGU Audit Status Preservation | `MEDIUM` / `manual_review=True` | **Preserved** | **PASSED** |

### Breakdown by Resolution Type & Confidence

| Resolution Type | Code Type | Count | Confidence | Manual Review |
| :--- | :---: | :---: | :---: | :---: |
| `IATA_IDENTITY` | `IATA` | 322 | `AUTHORITATIVE` | False |
| `BTS_EXACT_DESCRIPTION_MATCH` | `DOT_ID` | 293 | `AUTHORITATIVE` | False |
| `FACILITY_RENAME_RECONCILIATION` | `DOT_ID` | 11 | `HIGH` | False |
| `FACILITY_RENAME_RECONCILIATION` (SGU) | `DOT_ID` | 1 | `MEDIUM` | **True** |
| `COMMERCIAL_DISAMBIGUATION` (AUS, YUM) | `DOT_ID` | 2 | `HIGH` | False |
| **Total** | — | **629** | — | **1 Flagged** |

---

## 5. Database Safety Confirmation

- **Database Path**: `database/flightpulse.db`
- `staging_flights_raw`: 5,819,079 rows (unaltered)
- `dim_airports`: 322 rows (unaltered)
- `map_airport_codes`: **0 rows** (retained empty pending formal insertion approval)
- `PRAGMA foreign_key_check`: **0 violations**

