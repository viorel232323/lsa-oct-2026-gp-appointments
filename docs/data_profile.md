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
| appointment_mode | text | 0 | 5 | Face-to-Face | Face-to-Face, Home Visit, Telephone, Unknown, Video/Online |
| time_between_book_and_appointment | text | 0 | 8 | 1 Day |'Same Day', '1 Day','2 to 7 Days', '8 to 14 Days', '15 to 21 Days' , '22 to 28 Days', , 'More than 28 Days', 'Unknown / Data Quality'|
| count_of_appointments | integer | 0 | 22,807 | 8107 | |
<br>


### Findings

**1 Coverage:** 42 ICBs, 30 months, no nulls, **total** 742,804,525.

**2. Duplicate rows: keep and sum, never drop**
- **21,604** rows are exact copies of another row.

- **301,129** rows share their 6 descriptive columns (this includes the exact copies).
- They are **real appointments**. Dropping them would lose data.

**3. Untidy labels**
- Double spaces in booking-wait bands: `15  to 21 Days`, `22  to 28 Days`.
- Alphabetical order is wrong for the bands: `15 to 21 Days` sorts before `2 to 7 Days`.

**4. Month is text, not a date.**