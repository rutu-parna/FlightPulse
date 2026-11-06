# FlightPulse - Comprehensive Data Profiling Report

This profiling report presents empirical statistics and structural observations obtained from inspecting the raw CSV files stored in `data/raw/`: `airlines.csv`, `airports.csv`, and `flights.csv`.

---

## 1. File Metadata & Physical Characteristics

| Metric | `airlines.csv` | `airports.csv` | `flights.csv` |
|:---|:---|:---|:---|
| **File Path** | `data/raw/airlines.csv` | `data/raw/airports.csv` | `data/raw/flights.csv` |
| **File Size (Bytes)** | 359 Bytes | 23,867 Bytes | 592,406,591 Bytes |
| **File Size (MB)** | 0.0003 MB | 0.02 MB | **564.96 MB** |
| **File Encoding** | UTF-8 | UTF-8 | UTF-8 |
| **Delimiter** | Comma (`,`) | Comma (`,`) | Comma (`,`) |
| **Total Rows** | 14 | 322 | **5,819,079** |
| **Total Columns** | 2 | 7 | **31** |
| **Duplicate Rows** | 0 (0.0%) | 0 (0.0%) | **0 (0.0%)** |
| **Deduplication Method** | Exact full DataFrame | Exact full DataFrame | **Global 64-bit row hashing across 100% of rows (5,819,079)** |

---

## 2. Table-by-Table Data Profiles

### 2.1 `airlines.csv` Profile
- **Total Records**: 14
- **Completeness**: 100% complete (0 null values across both columns).
- **Columns & Data Types**:
  - `IATA_CODE`: `TEXT` (14 unique 2-letter codes: `AA`, `AS`, `B6`, `DL`, `EV`, `F9`, `HA`, `MQ`, `NK`, `OO`, `UA`, `US`, `VX`, `WN`)
  - `AIRLINE`: `TEXT` (14 unique airline company names)

### 2.2 `airports.csv` Profile
- **Total Records**: 322
- **Completeness**:
  - `IATA_CODE`: 0 nulls (322 unique 3-letter uppercase airport codes)
  - `AIRPORT`: 0 nulls (322 unique airport facility names)
  - `CITY`: 0 nulls (308 unique cities)
  - `STATE`: 0 nulls (54 unique states/territories)
  - `COUNTRY`: 0 nulls (`USA` across all rows)
  - `LATITUDE`: **3 nulls (0.93%)** — Missing for airports `ECP` (Panama City Beach, FL), `PBG` (Plattsburgh, NY), and `UST` (St. Augustine, FL).
  - `LONGITUDE`: **3 nulls (0.93%)** — Missing for `ECP`, `PBG`, and `UST`.

---

### 2.3 `flights.csv` Profile

- **Total Records**: **5,819,079**
- **Date Range & Temporal Scope**:
  - **Minimum Date**: `2015-01-01`
  - **Maximum Date**: `2015-12-31`
  - **Documented Year**: **Calendar Year 2015** (365 days; not 2025).
- **Unique Entity Identifiers**:
  - **Unique Operating Airlines**: 14 (Matches 100% of airlines in `airlines.csv`).
  - **Unique Origin Airports**: **628**
  - **Unique Destination Airports**: **629**

#### Airport Identifier Discrepancy & Join Implications
> [!WARNING]
> **Major Architectural & Join Finding**:
> - In `airports.csv`, all 322 entries use 3-letter IATA airport codes (`ORD`, `ATL`, `LAX`, etc.).
> - In `flights.csv`, Months 1–9 and 11–12 exclusively use standard 3-letter IATA codes.
> - **Month 10 (October 2015)**: All 486,165 flights in October exclusively use 5-digit US Bureau of Transportation Statistics (DOT) numeric airport IDs (e.g., `10397` for Atlanta, `13930` for Chicago O'Hare).
> - **Join Impact**: A standard inner join `flights.ORIGIN_AIRPORT = airports.IATA_CODE` will **silently drop all 486,165 October flights (8.35% of the entire annual dataset)** or produce NULL parent keys.
> - **Resolution Strategy**: In Phase 3 (Database Schema & ETL), a translation bridge/mapping table between 5-digit DOT codes and 3-letter IATA codes must be established before enforcing relational integrity.

---

## 3. Column-Level Profiling & Missing Values (`flights.csv`)

> [!NOTE]
> All missingness percentages are computed strictly using the total row count denominator: $N = 5,819,079$.
> Null values in delay causes are **not data quality defects**; under US DOT reporting standards, delay attribution is legally mandated only when a flight arrives $\ge 15$ minutes late.

| Column Name | Inferred SQLite Type | Observed Pandas Type | Null Count | Null % (of 5,819,079) | Missingness Classification & Domain Rationale |
|:---|:---|:---|:---|:---|:---|
| `YEAR` | `INTEGER` | `int64` | 0 | 0.00% | Complete (constant 2015) |
| `MONTH` | `INTEGER` | `int64` | 0 | 0.00% | Complete (1 to 12) |
| `DAY` | `INTEGER` | `int64` | 0 | 0.00% | Complete (1 to 31) |
| `DAY_OF_WEEK` | `INTEGER` | `int64` | 0 | 0.00% | Complete (1 to 7) |
| `AIRLINE` | `TEXT` | `string` | 0 | 0.00% | Complete (14 carrier codes) |
| `FLIGHT_NUMBER` | `TEXT` | `string` | 0 | 0.00% | Complete |
| `TAIL_NUMBER` | `TEXT` | `string` | 14,721 | 0.25% | Operational (unassigned aircraft on cancelled flights) |
| `ORIGIN_AIRPORT` | `TEXT` | `string` | 0 | 0.00% | Complete (IATA + DOT numeric codes) |
| `DESTINATION_AIRPORT` | `TEXT` | `string` | 0 | 0.00% | Complete (IATA + DOT numeric codes) |
| `SCHEDULED_DEPARTURE` | `TEXT` | `int64` (`HHMM`) | 0 | 0.00% | Complete (0001 - 2359) |
| `DEPARTURE_TIME` | `REAL` | `float64` | 86,153 | 1.48% | Operational (flight cancelled prior to pushback) |
| `DEPARTURE_DELAY` | `REAL` | `float64` | 86,153 | 1.48% | Operational (flight cancelled prior to departure) |
| `TAXI_OUT` | `REAL` | `float64` | 89,047 | 1.53% | Operational (cancelled at gate or pre-taxi) |
| `WHEELS_OFF` | `REAL` | `float64` | 89,047 | 1.53% | Operational (aircraft never took off) |
| `SCHEDULED_TIME` | `REAL` | `float64` | 6 | 0.0001% | Isolated missing published block duration |
| `ELAPSED_TIME` | `REAL` | `float64` | 105,071 | 1.81% | Operational (flight cancelled or diverted) |
| `AIR_TIME` | `REAL` | `float64` | 105,071 | 1.81% | Operational (flight cancelled or diverted) |
| `DISTANCE` | `REAL` | `int64` | 0 | 0.00% | Complete |
| `WHEELS_ON` | `REAL` | `float64` | 92,513 | 1.59% | Operational (aircraft cancelled or diverted) |
| `TAXI_IN` | `REAL` | `float64` | 92,513 | 1.59% | Operational (aircraft cancelled or diverted) |
| `SCHEDULED_ARRIVAL` | `TEXT` | `int64` (`HHMM`) | 0 | 0.00% | Complete |
| `ARRIVAL_TIME` | `REAL` | `float64` | 92,513 | 1.59% | Operational (flight cancelled or diverted) |
| `ARRIVAL_DELAY` | `REAL` | `float64` | 105,071 | 1.81% | Operational (flight cancelled or diverted) |
| `DIVERTED` | `INTEGER` | `int64` | 0 | 0.00% | Complete (0 or 1) |
| `CANCELLED` | `INTEGER` | `int64` | 0 | 0.00% | Complete (0 or 1) |
| `CANCELLATION_REASON` | `TEXT` | `string` | 5,729,195 | 98.46% | **Conditional Domain Logic**: Populated only when `CANCELLED == 1` |
| `AIR_SYSTEM_DELAY` | `REAL` | `float64` | 4,755,640 | 81.73% | **Conditional Domain Logic**: Mandated by DOT only when `ARRIVAL_DELAY >= 15` |
| `SECURITY_DELAY` | `REAL` | `float64` | 4,755,640 | 81.73% | **Conditional Domain Logic**: Mandated by DOT only when `ARRIVAL_DELAY >= 15` |
| `AIRLINE_DELAY` | `REAL` | `float64` | 4,755,640 | 81.73% | **Conditional Domain Logic**: Mandated by DOT only when `ARRIVAL_DELAY >= 15` |
| `LATE_AIRCRAFT_DELAY` | `REAL` | `float64` | 4,755,640 | 81.73% | **Conditional Domain Logic**: Mandated by DOT only when `ARRIVAL_DELAY >= 15` |
| `WEATHER_DELAY` | `REAL` | `float64` | 4,755,640 | 81.73% | **Conditional Domain Logic**: Mandated by DOT only when `ARRIVAL_DELAY >= 15` |

---

## 4. Delay Distribution Analysis & Denominators

### 4.1 Departure Delay Distribution
- **Total Flights in File**: 5,819,079
- **Cancelled / Unmeasured Departures**: 86,153 (1.48%)
- **Measured Denominator ($N_{\text{dep}}$)**: **5,732,926 flights**
- **Summary Metrics**:
  - Minimum: -82.0 minutes | Maximum: 1,988.0 minutes (~33.1 hours)
  - Mean: **9.37 minutes** | Standard Deviation: **37.08 minutes**
  - $Q_1$ (25th Percentile): -5.0 min | Median (50th Percentile): **-1.0 min** | $Q_3$ (75th Percentile): 8.0 min
  - 90th Percentile: 35.0 min | 95th Percentile: 66.0 min

**Categorical Performance (Denominator: $N_{\text{dep}} = 5,732,926$)**:
- Early Departures ($\text{Delay} < 0$): **3,277,948 flights (57.18%)**
- Exactly On-Time ($\text{Delay} = 0$): **329,360 flights (5.75%)**
- Delayed Departures ($\text{Delay} > 0$): **2,125,618 flights (37.08%)**
- Standard Departure Delay ($\ge 15$ min): **1,057,554 flights (18.45%)**
- Severe Departure Delay ($\ge 60$ min): **330,965 flights (5.77%)**

---

### 4.2 Arrival Delay Distribution
- **Total Flights in File**: 5,819,079
- **Cancelled / Diverted / Unmeasured Arrivals**: 105,071 (1.81%)
- **Measured Denominator ($N_{\text{arr}}$)**: **5,714,008 flights**
- **Summary Metrics**:
  - Minimum: -87.0 minutes | Maximum: 1,971.0 minutes (~32.85 hours)
  - Mean: **4.41 minutes** | Standard Deviation: **39.27 minutes**
  - $Q_1$ (25th Percentile): -13.0 min | Median (50th Percentile): **-5.0 min** | $Q_3$ (75th Percentile): 7.0 min
  - 90th Percentile: 34.0 min | 95th Percentile: 65.0 min

**Categorical Performance (Denominator: $N_{\text{arr}} = 5,714,008$)**:
- Early Arrivals ($\text{Delay} < 0$): **3,500,899 flights (61.27%)**
- Exactly On-Time ($\text{Delay} = 0$): **126,213 flights (2.21%)**
- Delayed Arrivals ($\text{Delay} > 0$): **2,086,896 flights (36.52%)**
- Standard DOT Delay ($\ge 15$ min): **1,063,439 flights (18.61%)**
- Severe Arrival Delay ($\ge 60$ min): **325,591 flights (5.70%)**

---

## 5. Cancellations, Diversions & Delay Causes

### 5.1 Flight Cancellations
- **Total Flights Evaluated**: 5,819,079
- **Non-Cancelled (`0`)**: 5,729,195 (98.45%)
- **Cancelled (`1`)**: **89,884 (1.55%)**
- **Cancellation Reasons Distribution** (Total: 89,884):
  - **Reason B (Weather)**: 48,851 (54.35%)
  - **Reason A (Carrier / Airline Operations)**: 25,262 (28.10%)
  - **Reason C (National Aviation System / NAS)**: 15,749 (17.52%)
  - **Reason D (Security Breach)**: 22 (0.02%)

### 5.2 Flight Diversions
- **Total Flights Evaluated**: 5,819,079
- **Completed Flights (`0`)**: 5,803,892 (99.74%)
- **Diverted Flights (`1`)**: **15,187 (0.26%)**

### 5.3 Delay Causes Breakdown
Under US DOT standard reporting regulations, delay-cause fields are recorded only when a flight has an arrival delay $\ge 15$ minutes.
- **Flights Delayed $\ge 15$ Minutes ($N_{\ge 15}$)**: **1,063,439 flights (18.61% of measured arrivals)**
- **Flights with Delay-Causes Reported**: **1,063,439 rows (100.0% of flights with $\text{ARRIVAL\_DELAY} \ge 15$)**
- **Unpopulated Rows**: 4,755,640 (81.73% of total flights; expected domain behavior).

| Delay Cause Field | Reported Records | % of Total Flights ($N=5.82\text{M}$) | % of $\ge 15$ Min Delayed Flights ($N=1.06\text{M}$) | Non-Zero Records | Mean Delay (when recorded) | Max Delay |
|:---|:---|:---|:---|:---|:---|:---|
| `LATE_AIRCRAFT_DELAY` | 1,063,439 | 18.28% | **100.0%** | 556,953 (52.37%) | **23.47 min** | 1,331 min |
| `AIRLINE_DELAY` | 1,063,439 | 18.28% | **100.0%** | 570,022 (53.60%) | **18.97 min** | 1,971 min |
| `AIR_SYSTEM_DELAY` | 1,063,439 | 18.28% | **100.0%** | 564,826 (53.11%) | **13.48 min** | 1,134 min |
| `WEATHER_DELAY` | 1,063,439 | 18.28% | **100.0%** | 64,716 (6.09%) | **2.92 min** | 1,211 min |
| `SECURITY_DELAY` | 1,063,439 | 18.28% | **100.0%** | 3,484 (0.33%) | **0.08 min** | 573 min |
