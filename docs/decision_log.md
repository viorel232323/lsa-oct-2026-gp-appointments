# Decision Log -  Transform

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
- **Evidence:** rows **596,821 → 295,692**; total appointments 742,804,525 before and after **(unchanged)**.

### D7. One Parquet file per month folder
- **What:** `.repartition("appointment_month")` before writing.
- **Why:** without it, each of the 8 shuffle chunks wrote its own file into every month folder (240 small files). Many tiny files are slow to read.
- **Evidence:** 240 -> 30 Parquet files; rows and total unchanged after reading back.

## national_categories.csv

**Reused rules:** D1–D2 (explicit schema, FAILFAST), D4 (repeated spaces collapsed in `service_setting`, `context_type`, `national_category`), D7 (one Parquet file per month folder).

### D8. Explicit schema removes the hidden mark in the header
- **What:** read with an explicit schema plus `header=True`.
- **Why:** the file starts with 3 invisible bytes (EF BB BF, a "byte-order mark"). Without a schema, Spark names the first column `\ufeffappointment_date`, so any code using `appointment_date` fails. With a schema, the names come from my schema, not the file.

### D9. Day-first dates parsed with a fixed format
- **What:** `F.to_date("appointment_date", "dd/MM/yyyy")`.
- **Why:** dates are UK style (`02/08/2021` = 2 August). If the format were guessed, it could be read as 8 February. A fixed format leaves nothing to guess.
- **Evidence:** 0 empty dates; 0 rows where the date's month is not = `appointment_month`.

### D10. Sub-ICB code extracted from the name
- **What:** new column `sub_icb_code` = `regexp_extract(sub_icb_location_name, r"-\s*(\w+)\s*$", 1)`. The original name column is kept.
- **Why:** this file has no code column; the code only appears at the end of the name (`NHS Kent and Medway ICB - 91Q` -> `91Q`). The duration file has `sub_icb_location_code`, so a code column lets the two be matched. The `$` (end of text) means dashes inside names, like Stoke-on-Trent, are ignored.
- **Evidence:** 106 distinct codes; 0 empty codes.

### D11. No grouping needed
- **What:** no `groupBy` / `sum` on this file, unlike regional (D6).
- **Why:** each row is already unique on its key (date, sub-ICB, service setting, context type, national category), so there is nothing to combine.
- **Evidence:** 0 key duplicates after cleaning; **rows 817,394 in and out**; total 296,046,770 unchanged.

## actual_duration.csv

**Reused rules:** D1–D2 (explicit schema, FAILFAST), D4 (repeated spaces collapsed in `actual_duration`), D7 (one Parquet file per month folder).

### D12. Year-first dates parsed with a fixed format
- **What:** `F.to_date("appointment_date", "yyyy-MM-dd")`.
- **Why:** this CSV was made from the Excel file by pandas in Extract, which writes dates year-first (`2021-12-01`). A fixed format leaves nothing to guess.
- **Evidence:** 0 empty dates.

### D13. `appointment_month` added from the date
- **What:** `F.date_format("appointment_date", "yyyy-MM")` as a new text column.
- **Why:** this file only has a daily date. The other two files have `appointment_month`, so adding it lets all three be partitioned the same way and compared by month.
- **Evidence:** 7 months, 2021-12 to 2022-06.

### D14. Keep the "Unknown / Data Quality" band
- **What:** rows with `actual_duration = "Unknown / Data Quality"` are kept, not removed.
- **Why:** they are real appointments whose length wasn't recorded. Removing them would shrink the total and hide a data-quality issue the dashboard should show.
- **Evidence:** 20,161 rows kept; total 167,980,692 unchanged.

### D15. Duration covers only 7 months (limitation)
- **What:** no fix possible; recorded as a limitation.
- **Why:** the source only has Dec 2021 – Jun 2022, while regional covers Jan 2020 – Jun 2022. Any comparison using duration must be limited to those 7 months.
- **Evidence:** distinct `appointment_month` = 7 values.

### D16. No grouping needed
- **What:** no `groupBy` / `sum`, same as D11.
- **Why:** each row is already unique on its key (sub-ICB code, date, duration band).
- **Evidence:** 0 key duplicates; **rows 137,793 in and out**; total 167,980,692 **unchanged**.

## Tests

### D17. Tests read the clean Parquet with pandas
- **What:** `tests/test_clean_data.py` has 6 tests: row counts, totals preserved, no duplicate keys, no double spaces, dates day-first, counts positive.
- **Why:** pandas starts in seconds with no Java. A second, independent tool also proves the Parquet files are readable outside Spark. Totals are compared with the raw CSVs, not only with typed numbers.
- **Evidence:** 6 passed (result in README). Test was broken on purpose once and failed, proving it catches its rule.