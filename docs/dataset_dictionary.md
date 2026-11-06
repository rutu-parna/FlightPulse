# Dataset Dictionary: FlightPulse

This data dictionary defines the schema, physical attributes, inferred SQLite datatypes, null semantics, and business definitions for all datasets in `data/raw/`.

---

## 1. `airlines.csv`

- **Description**: Lookup dimension table mapping two-letter IATA airline codes to full carrier names.
- **File Size**: 359 Bytes
- **Encoding**: UTF-8 | **Delimiter**: Comma (`,`)
- **Total Records**: 14 | **Total Columns**: 2
- **Duplicates**: 0 (Full dataset deduplication)

| Column Name | Inferred SQLite Type | Observed Pandas Type | Null Count | Null % (of 14) | Primary / Foreign Key | Description |
|:---|:---|:---|:---|:---|:---|:---|
| `IATA_CODE` | `TEXT` | `string` | 0 | 0.0% | **Primary Key** | Unique 2-character carrier abbreviation (e.g. `AA`, `DL`, `UA`). |
| `AIRLINE` | `TEXT` | `string` | 0 | 0.0% | - | Full legal carrier operating name (e.g. `American Airlines Inc.`). |

---

## 2. `airports.csv`

- **Description**: Master reference table for commercial airports across the United States and territories.
- **File Size**: 23.87 KB (23,867 Bytes)
- **Encoding**: UTF-8 | **Delimiter**: Comma (`,`)
- **Total Records**: 322 | **Total Columns**: 7
- **Duplicates**: 0 (Full dataset deduplication)

| Column Name | Inferred SQLite Type | Observed Pandas Type | Null Count | Null % (of 322) | Primary / Foreign Key | Description |
|:---|:---|:---|:---|:---|:---|:---|
| `IATA_CODE` | `TEXT` | `string` | 0 | 0.0% | **Primary Key** | 3-letter IATA identifier for the airport (e.g., `JFK`, `ORD`, `LAX`). |
| `AIRPORT` | `TEXT` | `string` | 0 | 0.0% | - | Official airport name. |
| `CITY` | `TEXT` | `string` | 0 | 0.0% | - | Municipality / metropolitan area served. |
| `STATE` | `TEXT` | `string` | 0 | 0.0% | - | US state or territorial postal code (54 unique values). |
| `COUNTRY` | `TEXT` | `string` | 0 | 0.0% | - | Country name (`USA` across all rows). |
| `LATITUDE` | `REAL` | `float64` | 3 | 0.93% | - | Geographic latitude coordinate in decimal degrees. *(Missing for ECP, PBG, UST)* |
| `LONGITUDE` | `REAL` | `float64` | 3 | 0.93% | - | Geographic longitude coordinate in decimal degrees. *(Missing for ECP, PBG, UST)* |

---

## 3. `flights.csv`

- **Description**: Granular operational log of domestic flights conducted in calendar year 2015.
- **File Size**: 564.96 MB (592,406,591 Bytes)
- **Encoding**: UTF-8 | **Delimiter**: Comma (`,`)
- **Total Records**: 5,819,079 | **Total Columns**: 31
- **Duplicates**: 0 (Verified via global 64-bit row hashing across 100% of 5,819,079 rows)
- **Temporal Scope**: `2015-01-01` to `2015-12-31` (Calendar Year 2015)

> [!NOTE]
> **Null Semantics**: Delay cause attributes (`AIR_SYSTEM_DELAY`, `SECURITY_DELAY`, `AIRLINE_DELAY`, `LATE_AIRCRAFT_DELAY`, `WEATHER_DELAY`) are unpopulated for flights arriving on time or with $<15$ minutes delay per Federal Aviation Administration (FAA) / US DOT reporting guidelines. These nulls represent normal flight operations, not missing data defects.

| Column Name | Inferred SQLite Type | Observed Pandas Type | Null Count | Null % (of 5,819,079) | Key / Join Role | Description |
|:---|:---|:---|:---|:---|:---|:---|
| `YEAR` | `INTEGER` | `int64` | 0 | 0.00% | - | Calendar year of flight (`2015`). |
| `MONTH` | `INTEGER` | `int64` | 0 | 0.00% | - | Departure month (1–12). |
| `DAY` | `INTEGER` | `int64` | 0 | 0.00% | - | Departure day of the month (1–31). |
| `DAY_OF_WEEK` | `INTEGER` | `int64` | 0 | 0.00% | - | Day of week integer (1 = Monday, 7 = Sunday). |
| `AIRLINE` | `TEXT` | `string` | 0 | 0.00% | Foreign Key (`airlines.IATA_CODE`) | Two-character carrier operating code. |
| `FLIGHT_NUMBER` | `TEXT` | `string` | 0 | 0.00% | - | Operating flight number. |
| `TAIL_NUMBER` | `TEXT` | `string` | 14,721 | 0.25% | - | FAA aircraft registration tail number. |
| `ORIGIN_AIRPORT` | `TEXT` | `string` | 0 | 0.00% | Join Key *(See Note)* | Departure airport. Months 1–9, 11–12 use 3-letter IATA; Month 10 uses 5-digit DOT IDs. |
| `DESTINATION_AIRPORT` | `TEXT` | `string` | 0 | 0.00% | Join Key *(See Note)* | Arrival airport. Months 1–9, 11–12 use 3-letter IATA; Month 10 uses 5-digit DOT IDs. |
| `SCHEDULED_DEPARTURE` | `TEXT` | `int64` (`HHMM`) | 0 | 0.00% | - | Planned departure local time in `HHMM` clock format (e.g. `0005` = 00:05). |
| `DEPARTURE_TIME` | `REAL` | `float64` | 86,153 | 1.48% | - | Actual pushback time (`HHMM`). Null if flight was cancelled. |
| `DEPARTURE_DELAY` | `REAL` | `float64` | 86,153 | 1.48% | - | Difference between actual and scheduled departure in minutes. Negative = early. |
| `TAXI_OUT` | `REAL` | `float64` | 89,047 | 1.53% | - | Taxiing duration from gate pushback to wheels-off takeoff (minutes). |
| `WHEELS_OFF` | `REAL` | `float64` | 89,047 | 1.53% | - | Local wheels-off takeoff timestamp (`HHMM`). |
| `SCHEDULED_TIME` | `REAL` | `float64` | 6 | 0.0001% | - | Scheduled block elapsed flight duration (minutes). |
| `ELAPSED_TIME` | `REAL` | `float64` | 105,071 | 1.81% | - | Actual total block duration (`AIR_TIME + TAXI_OUT + TAXI_IN`). Null if cancelled/diverted. |
| `AIR_TIME` | `REAL` | `float64` | 105,071 | 1.81% | - | Airborne flight duration between takeoff and landing (minutes). |
| `DISTANCE` | `REAL` | `int64` | 0 | 0.00% | - | Great-circle flight distance in statute miles. |
| `WHEELS_ON` | `REAL` | `float64` | 92,513 | 1.59% | - | Local wheels-on touchdown timestamp (`HHMM`). |
| `TAXI_IN` | `REAL` | `float64` | 92,513 | 1.59% | - | Taxiing duration from touchdown to arrival gate (minutes). |
| `SCHEDULED_ARRIVAL` | `TEXT` | `int64` (`HHMM`) | 0 | 0.00% | - | Planned arrival local time in `HHMM` clock format. |
| `ARRIVAL_TIME` | `REAL` | `float64` | 92,513 | 1.59% | - | Actual gate arrival local time in `HHMM` format. |
| `ARRIVAL_DELAY` | `REAL` | `float64` | 105,071 | 1.81% | - | Difference between actual and scheduled arrival in minutes. Negative = early. |
| `DIVERTED` | `INTEGER` | `int64` | 0 | 0.00% | - | Binary diversion flag (1 = Diverted, 0 = Not Diverted). |
| `CANCELLED` | `INTEGER` | `int64` | 0 | 0.00% | - | Binary cancellation flag (1 = Cancelled, 0 = Completed). |
| `CANCELLATION_REASON` | `TEXT` | `string` | 5,729,195 | 98.46% | - | Reason code: `A` = Carrier, `B` = Weather, `C` = NAS, `D` = Security. Null if completed. |
| `AIR_SYSTEM_DELAY` | `REAL` | `float64` | 4,755,640 | 81.73% | - | Delay attributed to air traffic control or airport capacity (minutes). |
| `SECURITY_DELAY` | `REAL` | `float64` | 4,755,640 | 81.73% | - | Delay attributed to terminal or security screening breaches (minutes). |
| `AIRLINE_DELAY` | `REAL` | `float64` | 4,755,640 | 81.73% | - | Delay attributed to carrier operations, maintenance, crew, baggage (minutes). |
| `LATE_AIRCRAFT_DELAY` | `REAL` | `float64` | 4,755,640 | 81.73% | - | Delay propagated from a late inbound aircraft leg (minutes). |
| `WEATHER_DELAY` | `REAL` | `float64` | 4,755,640 | 81.73% | - | Delay attributed to meteorological conditions (minutes). |
