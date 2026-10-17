# Data Profile — NHS GP Appointments

**Source:** NHS England, *Appointments in General Practice* (Open Government Licence v3.0)

**Files profiled:** raw copies in `data/raw/` (listed in `docs/manifest.json`)

**Code:** `src/profile_data.py`. Rerun it to reproduce every number below.

<br>

## 1. appointments_regional.csv

<br>

### Overview
| Item | Value |
|---|---|
| Rows × columns | 596,821 × 7 |
| Period | 2020-01 to 2022-06 (30 months) |
| Total appointments | 742,804,525 |
| Nulls | None in any column |
| Grain (intended) | ICB × month × status × staff type × appoinment mode × booking wait |
| Grain (actual) | **Not unique.** See Finding 2 |
<br>


### Columns
| Column | Type(as found) | Nulls | Distinct | Example | Notes |
|---|---|---|---|---|---|
| icb_ons_code | text | 0 | 42 | E54000034 |  |
| appointment_month | text | 0 | 30 | 2020-01 | Text `YYYY-MM`, not a date |
| appointment_status | text | 0 | 3 | Attended | Attended, DNA (did not attend), Unknown |
| hcp_type | text | 0 | 3 | GP | GP, Other Practice staff, Unknown |
| appointment_mode | text | 0 | 5 | Face-to-Face | Face-to-Face, Home Visit, Telephone, , Video/Online, Unknown |
| time_between_book_and_appointment | text | 0 | 8 | 1 Day |'Same Day', '1 Day','2 to 7 Days', '8 to 14 Days', '15 to 21 Days' , '22 to 28 Days', , 'More than 28 Days', 'Unknown / Data Quality'|
| count_of_appointments | integer | 0 | 22,807 | 8107 | |
<br>


### Findings

**1 Coverage:** 42 ICBs, 30 months, no nulls, **Total appointments:** 742,804,525.

**2. Duplicate rows: keep and sum, never drop**
- **21,604** rows are exact copies of another row.

- **301,129** rows share their 6 descriptive columns (this includes the exact copies).
- They are **real appointments**. Dropping them would lose data.

**3. Untidy labels**
- Double spaces in booking-wait bands: `15  to 21 Days`, `22  to 28 Days`.
- Alphabetical order is wrong for the bands: `15 to 21 Days` sorts before `2 to 7 Days`.

**4. Month is text, not a date.**

**5. appointment_status - Unknown:**  In some cases, 
the final status of an appointment remains as ‘Booked’. It is not known from the data whether or not these appointments actually attended. For this reason, the status of these appointments is reported as 'Unknown'.



<br>

## 2. national_categories.csv

<br>

### Overview
| Item | Value |
|---|---|
| Rows × columns | 817,394 × 8 |
| Period | 2021-08-01 to 2022-06-30 (334 days, 11 months) |
| Total appointments | 296,046,770 |
| Nulls | None in any column |
| Grain (one row is) | Sub-ICB location × day × service setting × national category. **Unique (0 duplicates)** |

### Columns
| Column | Type (as found) | Nulls | Distinct | Example | Notes |
|---|---|---|---|---|---|
| appointment_date | text | 0 | 334 | 02/08/2021 | **Day-first** text (2 August), not a date |
| icb_ons_code | text | 0 | 42 | E54000050 | Same 42 ICBs as the regional file |
| sub_icb_location_name | text | 0 | 106 | NHS North East and North Cumbria ICB - 00L | Sub-ICB **code is hidden at the end** of the name  |
| service_setting | text | 0 | 5 | Primary Care Network | Extended Access Provision, General Practice,Primary Care Network, Other, Unmapped |
| context_type | text | 0 | 3 | Care Related Encounter | Care Related Encounter, Inconsistent Mapping, Unmapped |
| national_category | text | 0 | 18 | Patient contact during Care Home Round | 18 categories |
| count_of_appointments | integer | 0 | 9,957 | 3 | The measure.  `Sum` it. |
| appointment_month | text | 0 | 11 | 2021-08 | Text `YYYY-MM`, same format as the regional file |

### Findings

**1. Coverage:** 334 distinct dates = **every day** from 1 Aug 2021 to 30 Jun 2022,
so no missing days. 42 ICBs, 106 sub-ICB locations, no nulls, **total appointments** 296,046,770.

**2. Day-first dates** 

`appointment_date` is text like `02/08/2021`, meaning **2 August**, not 8 February.

- the first number goes up to **31**, and no month is above 12, so it must be the day.

**3. Hidden byte-order mark**
- First 3 bytes of the file
- pandas removes it silently, so it doesn't show in the profile. Spark may read it.

**4. Sub-ICB code is inside the name**
- `NHS North East and North Cumbria ICB - 00L` → the code is `00L`.

## 3. actual_duration.csv

### Overview
| Item | Value |
|---|---|
| Rows × columns | 137,793 × 8 |
| Period | 2021-12-01 to 2022-06-30 |
| Total appointments | 167,980,692 |
| Nulls | 0 |
| Grain (one row is) | Sub-ICB location × day × duration band. ___ (0 duplicates = unique) |

### Columns
| Column | Type (as found) | Nulls | Distinct | Example | Notes |
|---|---|---|---|---|---|
|sub_icb_location_code|text|0| 106 |00L |Sub-ICB code in **its own column** (in the categories file it's hidden in the name) |  
|sub_icb_location_ons_code|  text |  0 | 106 |E38000130 |      
|sub_icb_location_name|text |  0 | 106 |NHS North East and North Cumbria ICB - 00L| 
|icb_ons_code|text |0 | 42 | E54000050 | Same 42 ICBs as the other files
|region_ons_code| text | 0 |   7 |  E40000012 | The 7 NHS regions.
|appointment_date| text | 0 | 212 | 2021-12-01 | Text `YYYY-MM-DD` (year-month-day)
|actual_duration|  text | 0 | 7 |   31-60 Minutes | 6 time bands + Unknown / Data Quality
|count_of_appointments| text | 0 | 7611 | 364 | The measure.

### Findings

**1. Coverage.** 212 distinct dates = **every day** from 1 Dec 2021 to 30 Jun 2022,
so no missing days. 7 regions, 42 ICBs, 106 sub-ICB locations, no nulls.
The 7 duration bands add up exactly to the total of 167,980,692.


**2. The file is Excel, not CSV** 

- The name ends `.csv.xlsx`: it is an Excel workbook, and Spark cannot read Excel.

**3. A third date format**
- Dates are text `2021-12-01` (year-month-day), created by the Excel conversion.
- Each file stores dates differently.

**4. Almost a quarter of durations are unusable**

| Duration band | Appointments | Share |
|---|---:|---:|
| 1-5 Minutes | 28,600,865 | 
| 6-10 Minutes | 33,800,815 | 
| 11-15 Minutes | 25,160,882 | 
| 16-20 Minutes | 16,004,247 | 
| 21-30 Minutes | 15,026,365 |
| 31-60 Minutes | 9,103,432 | 
| **Unknown / Data Quality** | **40,284,086** | **24.0%** |
| **Total** | **167,980,692** | 

**5. Band order is wrong when sorted alphabetically**
- Alphabetical order puts `11-15 Minutes` before `6-10 Minutes`.

**6. No duplicates.** 0 exact duplicate rows.