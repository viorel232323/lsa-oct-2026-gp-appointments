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

### D6. Sum rows, never drop them
- **What:** after cleaning the labels, rows with the same key (ICB, month, status, HCP type, mode, booking wait) were combined with `groupBy` + `sum`.
- **Why:** each row holds real, separate appointments. Dropping them as "duplicates" would delete appointments and shrink the total. Summing keeps every appointment and leaves one row per key.
- **Evidence:** rows 596,821 → 295,692; total appointments 742,804,525 before and after **(unchanged)**.

### D7. One Parquet file per month folder
- **What:** `.repartition("appointment_month")` before writing.
- **Why:** without it, each of the 8 shuffle chunks wrote its own file into every month folder (240 small files). Many tiny files are slow to read.
- **Evidence:** 240 -> 30 Parquet files; rows and total unchanged after reading back.