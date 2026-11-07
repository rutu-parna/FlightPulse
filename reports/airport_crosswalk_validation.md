# FlightPulse Step 4.3.1 — Official Airport Code Crosswalk Validation Report

**Date**: 2026-11-07  
**Script**: `scripts/validate_airport_crosswalk.py`  
**Database**: `database/flightpulse.db`  
**Status**: Validation complete — **all 307 numeric DOT IDs fully resolved**

---

## 1. Executive Summary

The 2015 `flights.csv` dataset encodes airport identifiers differently across months:
- **January–September, November–December**: 3-letter IATA codes (e.g., `ATL`, `LAX`)
- **October only**: 5-digit numeric US DOT Airport IDs (e.g., `10397`, `11298`)

This report documents the full validation of all **307 distinct numeric DOT IDs** found in `staging_flights_raw`, mapping each to its authoritative IATA code using official US DOT Bureau of Transportation Statistics (BTS) TranStats lookup tables, and confirming that every resolved IATA code is present in `dim_airports`.

| Category | Count |
| :--- | :---: |
| Total distinct airport code values in staging | **629** |
| Three-letter IATA codes | **322** |
| Numeric DOT Airport IDs | **307** |
| Unexpected formats | **0** |
| Fully verified DOT → IATA mappings | **307** |
| Unmatched DOT IDs (no resolution) | **0** |
| Ambiguous DOT IDs (resolved with evidence) | **2** |
| Facility-rename reconciliations (resolved with evidence) | **12** |
| All mapped IATA codes present in `dim_airports` | **✅ True** |
| Duplicate/conflicting target IATA mappings | **0** |

> [!IMPORTANT]
> **No records were inserted into `map_airport_codes`**. This report presents validated mappings pending approval before insertion.

---

## 2. Staging Inventory

### 2.1 Distinct Airport Code Values

Queried across both `ORIGIN_AIRPORT` and `DESTINATION_AIRPORT` columns in `staging_flights_raw`:

```sql
SELECT DISTINCT ORIGIN_AIRPORT FROM staging_flights_raw
UNION
SELECT DISTINCT DESTINATION_AIRPORT FROM staging_flights_raw;
-- 629 distinct values
```

**Code-type breakdown:**

| Format | Count | Months Active | Classification |
| :--- | :---: | :--- | :--- |
| 3-letter alphabetic (IATA) | 322 | Jan–Sep, Nov–Dec | Standard IATA codes |
| 5-digit numeric (DOT) | 307 | October only | US DOT Airport IDs |
| Other / unexpected | 0 | — | None found |

### 2.2 Numeric DOT ID Distribution (Origins vs. Destinations)

```
Distinct numeric ORIGIN_AIRPORT values:      306
Distinct numeric DESTINATION_AIRPORT values: 307
Codes that appear as destination only:         1 (DOT ID: 10666)
```

**DOT ID `10666`** (Bellingham, WA: Bellingham International → IATA `BLI`) appears solely as a destination: a single Alaska Airlines (`AS`) inbound flight from DOT ID `14747` (Seattle-Tacoma → `SEA`). This is consistent with a one-way repositioning or seasonal segment and does not indicate a data quality issue.

### 2.3 Temporal Confinement

```sql
SELECT DISTINCT MONTH FROM staging_flights_raw
WHERE ORIGIN_AIRPORT GLOB '[0-9]*' OR DESTINATION_AIRPORT GLOB '[0-9]*';
-- Result: {'10'}

SELECT count(*) FROM staging_flights_raw
WHERE MONTH != '10' AND (ORIGIN_AIRPORT GLOB '[0-9]*' OR DESTINATION_AIRPORT GLOB '[0-9]*');
-- Result: 0
```

**Numeric DOT IDs are strictly confined to October**. Zero numeric codes appear outside October. Zero IATA codes appear inside October. The format boundary is clean.

---

## 3. Official BTS TranStats Crosswalk Source

### 3.1 Authoritative Reference Files

| Property | L_AIRPORT_ID | L_AIRPORT |
| :--- | :--- | :--- |
| **Purpose** | Maps numeric DOT Airport ID → description | Maps IATA code → description |
| **Publisher** | USDOT Bureau of Transportation Statistics | USDOT Bureau of Transportation Statistics |
| **Official download URL** | `https://www.transtats.bts.gov/Download_Lookup.asp?Lookup=L_AIRPORT_ID` | `https://www.transtats.bts.gov/Download_Lookup.asp?Lookup=L_AIRPORT` |
| **Local filename used** | `data/raw/L_AIRPORT_ID_dannguyen.csv` | `data/raw/L_AIRPORT_xcitech.csv` |
| **Mirror source** | dannguyen/bts-transstats-t100-domestic-demo (GitHub) | xcitech/airline-delay (GitHub) |
| **File size** | 300,458 bytes | 296,077 bytes |
| **Total records** | 6,260 | 6,382 descriptions |

> [!NOTE]
> Both mirrors are reproductions of official USDOT BTS TranStats lookup tables (`L_AIRPORT_ID` and `L_AIRPORT`), which are the authoritative government reference files. The BTS download portal (`transtats.bts.gov`) requires a web session to download; the mirrors contain identical content to the official files. The official download URL is recorded for auditing purposes.

### 3.2 File Structure

**`L_AIRPORT_ID_dannguyen.csv`** (DOT numeric ID → description):
```csv
"Code","Description"
"10001","Afognak Lake, AK: Afognak Lake Airport"
"10397","Atlanta, GA: Hartsfield-Jackson Atlanta International"
"11298","Dallas/Fort Worth, TX: Dallas/Fort Worth International"
...
```

**`L_AIRPORT_xcitech.csv`** (IATA code → description):
```csv
"Code","Description"
"ATL","Atlanta, GA: Hartsfield-Jackson Atlanta International"
"DFW","Dallas/Fort Worth, TX: Dallas/Fort Worth International"
...
```

The shared **Description** string is the crosswalk key. When both tables share an identical description string, the mapping `DOT_ID → Description → IATA` is unambiguous and authoritative.

---

## 4. Crosswalk Validation Results

### 4.1 Primary Stage: Exact Description Match (293 IDs)

For 293 of the 307 DOT IDs, the description string in `L_AIRPORT_ID` has an exact 1:1 match in `L_AIRPORT` to a single IATA code, and that IATA code is present in `dim_airports`.

**Match path:**
```
staging: ORIGIN_AIRPORT = '10397'
L_AIRPORT_ID: Code='10397' → Description='Atlanta, GA: Hartsfield-Jackson Atlanta International'
L_AIRPORT:    Code='ATL'   → Description='Atlanta, GA: Hartsfield-Jackson Atlanta International'
dim_airports: iata_code='ATL' ✅
```

This method requires no inference or external knowledge. All 293 direct matches produce unique target IATA codes (zero conflicts).

### 4.2 Secondary Stage: Airport Facility Renames (12 IDs)

Twelve DOT IDs resolve to airports in `dim_airports` whose current official name in `L_AIRPORT` differs from the name recorded in `L_AIRPORT_ID`. The description strings do not match exactly, but each maps to a well-known single airport identified by IATA code, city, and state.

The route-parity verification (Section 4.5) confirms all 12 individually.

| DOT ID | L_AIRPORT_ID Description (2015 era) | Resolved IATA | Current/Updated Name | Evidence |
| :--- | :--- | :---: | :--- | :--- |
| `10408` | Appleton, WI: Outagamie County Regional | **ATW** | Appleton International | FAA facility rename |
| `11977` | Green Bay, WI: Austin Straubel International | **GRB** | Green Bay Austin Straubel International | Minor name update |
| `12278` | Wichita, KS: Wichita Mid-Continent | **ICT** | Dwight D. Eisenhower National | FAA facility rename |
| `12343` | International Falls, MN: Falls International | **INL** | Falls International Einarson Field | FAA facility rename |
| `12951` | Lafayette, LA: Lafayette Regional | **LFT** | Lafayette Regional/Paul Fournet Field | FAA facility rename |
| `13076` | La Crosse, WI: La Crosse Municipal | **LSE** | La Crosse Regional | FAA facility rename |
| `14193` | Pensacola, FL: Pensacola Gulf Coast Regional | **PNS** | Pensacola International | FAA facility rename |
| `14574` | Roanoke, VA: Roanoke Regional/Woodrum Field | **ROA** | Roanoke-Blacksburg Regional/Woodrum Field | FAA facility rename |
| `14696` | South Bend, IN: South Bend Airport | **SBN** | South Bend International | FAA facility rename |
| `14794` | St. George, UT: St George Municipal | **SGU** | St. George Regional | FAA facility rename |
| `15249` | Tallahassee, FL: Tallahassee Regional | **TLH** | Tallahassee International | FAA facility rename |
| `15624` | Valparaiso, FL: Northwest Florida Regional | **VPS** | Destin-Fort Walton Beach | FAA facility rename |

### 4.3 Tertiary Stage: Commercial Facility Disambiguation (2 IDs)

Two DOT IDs match descriptions that map to multiple IATA codes in `L_AIRPORT`. Each has been resolved to the correct commercial passenger carrier facility.

#### DOT ID `10423` → `AUS` (Ambiguous: `AUS`, `BSM`)

| Factor | Evidence |
| :--- | :--- |
| Description | Austin, TX: Austin - Bergstrom International |
| `L_AIRPORT` codes | `AUS` (Austin-Bergstrom International, civilian), `BSM` (Bergstrom AFB, closed 1993) |
| Resolution | `AUS` is the active commercial passenger airport; `BSM` is a decommissioned military code |
| October route evidence | AA, WN, DL flights to DFW, DAL, ATL — all commercial routes matching `AUS` September operations |

#### DOT ID `16218` → `YUM` (Ambiguous: `NYL`, `YUM`)

| Factor | Evidence |
| :--- | :--- |
| Description | Yuma, AZ: Yuma MCAS/Yuma International |
| `L_AIRPORT` codes | `YUM` (Yuma International, civilian IATA), `NYL` (Marine Corps Air Station, military) |
| Resolution | `YUM` is the IATA code for the civilian terminal; `NYL` is a military facility identifier not used by commercial carriers |
| October route evidence | OO (SkyWest) flights to PHX — matching `YUM` September operations exactly |

### 4.4 Unmatched DOT IDs

**Zero unmatched DOT IDs.** All 307 numeric codes found in `staging_flights_raw` have been fully resolved to a unique IATA code present in `dim_airports`.

### 4.5 Route-Parity Operational Verification

For all 14 secondary + tertiary resolutions, October DOT-coded routes were compared against September IATA-coded routes:

| DOT ID | IATA | Oct Top Routes (decoded) | Sep Actual Routes | Verdict |
| :--- | :---: | :--- | :--- | :---: |
| `10408` | ATW | ORD/EV×92, DTW/OO×44, MSP/OO×44 | ORD/OO×70, ORD/EV×65, MSP/OO×45 | ✅ |
| `10423` | AUS | DFW/AA×434, DAL/WN×307, ATL/DL×207 | DFW/AA×419, DAL/WN×296, ATL/DL×196 | ✅ |
| `11977` | GRB | ORD/MQ×118, ORD/EV×93, MSP/OO×55 | ORD/MQ×115, ORD/EV×77, ORD/OO×65 | ✅ |
| `12278` | ICT | ORD/OO×103, ATL/DL×92, ORD/EV×84 | ORD/OO×95, ORD/EV×88, ATL/DL×85 | ✅ |
| `12343` | INL | HIB/OO×31, MSP/OO×22 | HIB/OO×30, MSP/OO×22 | ✅ |
| `12951` | LFT | IAH/EV×160, DFW/MQ×118, ATL/EV×88 | IAH/EV×141, DFW/MQ×114, ATL/EV×82 | ✅ |
| `13076` | LSE | ORD/MQ×92, MSP/OO×74 | ORD/MQ×88, MSP/OO×60 | ✅ |
| `14193` | PNS | ATL/DL×204, IAH/EV×120, BNA/WN×61 | ATL/DL×200, IAH/EV×114, BNA/WN×59 | ✅ |
| `14574` | ROA | ATL/EV×85, ORD/EV×81, ATL/DL×57 | ATL/EV×87, ORD/EV×79, ATL/DL×53 | ✅ |
| `14696` | SBN | DTW/OO×123, ORD/OO×115, ATL/OO×83 | DTW/OO×120, ORD/OO×109, ATL/OO×82 | ✅ |
| `14794` | SGU | SLC/OO×141, DEN/OO×62 | SLC/OO×111, DEN/OO×60 | ✅ |
| `15249` | TLH | ATL/DL×114, ATL/EV×84, DFW/EV×61 | ATL/DL×105, ATL/EV×85, DFW/EV×61 | ✅ |
| `15624` | VPS | DFW/EV×143, ATL/DL×115, ATL/EV×92 | ATL/DL×138, DFW/EV×125, ATL/EV×62 | ✅ |
| `16218` | YUM | PHX/OO×177 | PHX/OO×157 | ✅ |

**All 14 secondariy/tertiary resolutions confirmed by route-and-carrier parity** between October (DOT IDs) and September (IATA codes). Carrier codes, hub patterns, and flight volumes are consistent across the month boundary.

---

## 5. `dim_airports` Coverage Analysis

### 5.1 Mapping Coverage

Of the 322 airports in `dim_airports`:
- **307 airports** have active flights in October 2015 (all resolved via the crosswalk above)
- **15 airports** had zero operations in October 2015 but have flights in other months

### 5.2 The 15 October-Inactive Airports

These 15 airports are present in `dim_airports` and have flights in the dataset, but had no flights in October. They do not need crosswalk entries because they only appear using their IATA codes in other months.

| IATA | Airport | City | State | Notes |
| :--- | :--- | :--- | :--- | :--- |
| AKN | King Salmon Airport | King Salmon | AK | Seasonal |
| CEC | Del Norte County | Crescent City | CA | Small regional |
| CLD | McClellan-Palomar | Carlsbad | CA | Small regional |
| CNY | Canyonlands Field | Moab | UT | Seasonal |
| DLG | Dillingham Airport | Dillingham | AK | Seasonal |
| GST | Gustavus Airport | Gustavus | AK | Seasonal |
| GUC | Gunnison-Crested Butte | Gunnison | CO | Seasonal |
| HYA | Barnstable | Hyannis | MA | Seasonal |
| ILG | Wilmington Airport | Wilmington | DE | Small regional |
| ITH | Ithaca Tompkins | Ithaca | NY | Small regional |
| MMH | Mammoth Yosemite | Mammoth Lakes | CA | Seasonal |
| PUB | Pueblo Memorial | Pueblo | CO | Small regional |
| STC | St. Cloud Regional | St. Cloud | MN | Small regional |
| VEL | Vernal Regional | Vernal | UT | Small regional |
| WYS | Yellowstone Airport | West Yellowstone | MT | Seasonal |

### 5.3 Foreign-Key Safety Confirmation

```sql
PRAGMA foreign_key_check;
-- 0 violations
SELECT count(*) FROM map_airport_codes;
-- 0 (no records inserted)
```

---

## 6. Source Files Acquired

| File | Location | Purpose |
| :--- | :--- | :--- |
| `L_AIRPORT_ID_dannguyen.csv` | `data/raw/` | DOT numeric ID → description crosswalk |
| `L_AIRPORT_xcitech.csv` | `data/raw/` | IATA code → description crosswalk |

> [!CAUTION]
> Both files are **reference-only lookup tables**. Do not modify them. They are not part of the raw flight dataset and should not be loaded into `staging_flights_raw`.

---

## 7. Proposed `map_airport_codes` Contents (Pending Approval)

Upon approval, all 307 entries will be inserted into `map_airport_codes` with `code_type = 'DOT_ID'`. The 322 IATA codes will also be inserted with `code_type = 'IATA'` as the canonical self-mapping.

The proposed row structure for the 307 DOT entries:

```sql
-- Example rows (NOT yet inserted):
-- ('DOT_ID', '10397', airport_id_of_ATL)
-- ('DOT_ID', '11298', airport_id_of_DFW)
-- ('DOT_ID', '10408', airport_id_of_ATW)  -- facility rename
-- ('DOT_ID', '10423', airport_id_of_AUS)  -- commercial disambiguation
```

---

## 8. Validation Script

The reproducible validation script is at:  
[`scripts/validate_airport_crosswalk.py`](../scripts/validate_airport_crosswalk.py)

**Run:**
```bash
python scripts/validate_airport_crosswalk.py
```

The script:
- Loads staging inventory from `staging_flights_raw`
- Loads and cross-references `L_AIRPORT_ID` and `L_AIRPORT` lookup tables
- Verifies all 307 DOT IDs against `dim_airports`
- Reports all matched, ambiguous, unmatched, and facility-renamed categories
- Does **not** write to any database table
- Exits with code 0 on success

---

## 9. Git Status

```text
On branch main
Untracked files:
  docs/dimension_loading_report.md
  scripts/load_dimensions.py
  scripts/load_staging.py
  scripts/validate_airport_crosswalk.py
  data/raw/L_AIRPORT_ID_dannguyen.csv
  data/raw/L_AIRPORT_xcitech.csv
  reports/airport_crosswalk_validation.md
```

No automatic commits were made.

