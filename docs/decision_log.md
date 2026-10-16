# Decision Log — Week 2 Transform

Every change made to the data between `data/raw/` and `data/clean/`, and why.
Numbers come from `src/transform.py` and `docs/data_profile.md`.

---

## appointments_regional.csv

### D1. Read every file with an explicit schema
- **Why:** column types are correct and identical on every run; no extra pass to guess types.
- **Evidence:** `printSchema()` shows `count_of_appointments` as integer, all labels as text.

### D2. Read in FAILFAST mode
- **Why:** a value that doesn't fit its type stops the job, instead of silently becoming empty.
- **Evidence:** all 596,821 rows read with no errors.

### D3. Remove repeated spaces in all label columns
- **Why:** booking-wait bands contain double spaces (`15  to 21 Days`, `22  to 28 Days`).
  Applied to all 4 label columns, in case others hide the same problem.
- **How:** replace any run of spaces with one space, then trim the ends.
- **Evidence:** double spaces left = 0.

### D4. Keep `appointment_month` as text; add `month_start` as a date
- **Why:** there is no "month-only" date type. The text `2020-01` matches the other two files
  and gives readable Parquet folder names. `month_start` (e.g. `2020-01-01`) is used for sorting and charts.
- **How:** `to_date(appointment_month, 'yyyy-MM')`, with the format stated explicitly.
- **Evidence:** 0 empty dates after conversion.

### D5. Standardise `Other Practice staff` → `Other Practice Staff`
- **Why:** match the spelling in the metadata.