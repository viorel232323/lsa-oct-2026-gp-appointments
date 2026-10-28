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

<br>
<br>

# Tests

### D17. Tests read the clean Parquet with pandas
- **What:** `tests/test_clean_data.py` has 6 tests: row counts, totals preserved, no duplicate keys, no double spaces, dates day-first, counts positive.
- **Why:** pandas starts in seconds with no Java. A second, independent tool also proves the Parquet files are readable outside Spark. Totals are compared with the raw CSVs, not only with typed numbers.
- **Evidence:** 6 passed (result in README). Test was broken on purpose once and failed, proving it catches its rule.

## Load & Automate

### D18. Star schema: 3 fact tables, 5 dimensions
- **What:** in `warehouse/warehouse.duckdb`:
  - `fact_appointments_monthly` (ICB * month * status * staff type * mode * booking wait)
  - `fact_appointments_by_category` (sub-ICB * day * service setting * national category)
  - `fact_appointments_by_duration` (sub-ICB * day * duration band)
  - `dim_geography` (106 sub-ICBs), `dim_date` (every day 2020-01-01 to 2022-12-31), `dim_booking_wait` (8 bands), `dim_duration_band` (7 bands), `dim_national_category` (one row per category).
- **Why:** facts hold the counts and dimensions hold the descriptions, once. Three facts, not one, because they have different grains and date ranges (30, 11 and 7 months); forcing them into one table would invent appointments.
- **Evidence:** fact rows and totals equal exactly: 295,692 / 742,804,525 · 817,394 / 296,046,770 · 137,793 / 167,980,692.

### D19. NHS codes are the keys
- **What:** ICB and sub-ICB codes join the tables; no invented ID numbers.
- **Why:** they are real, stable identifiers. Invented keys would add a mapping step with no benefit at this size.

### D20. One name and one type per concept
- **What:** the month is always `appointment_month` as text `YYYY-MM` (all facts and `dim_date`); the day is always `appointment_date` as DATE; the sub-ICB code is always `sub_icb_code` (duration's `sub_icb_location_code` is renamed in the load).
- **Why:** the month comes back from the Parquet folder names as text, so text is kept everywhere. Mixing types for one concept makes joins silently return nothing. `YYYY-MM` text also sorts in date order, so `BETWEEN '2021-08' AND '2022-06'` works.

### D21. Descriptions moved out of the facts
- **What:** names, ICB and region codes → `dim_geography`; `context_type` → `dim_national_category`.
- **Why:** each description is stored once instead of repeated on every row.
- **Evidence:** checked first: each national category has exactly 1 context type and each sub-ICB code has exactly 1 name, ICB and region (0 conflicts), so nothing is lost or duplicated.

### D22. Band dimensions have an explicit sort order
- **What:** `sort_order` 1–8 in `dim_booking_wait` (Same Day -> More than 28 Days, Unknown last) and 1–7 in `dim_duration_band` (1-5 -> 31-60 Minutes, Unknown last).
- **Why:** alphabetical order puts `1 Day` before `Same Day` and `11-15` before `6-10`. The order is decided once here, so the Week 4 charts don't have to.
- **Evidence:** 0 fact labels missing from their dimension (checks 6–7 and tests).

### D23. Load is safe to rerun
- **What:** dimensions are rebuilt each run (`CREATE OR REPLACE`). Facts are loaded month by month: `BEGIN` → delete the month → insert the month → `COMMIT`, with `ROLLBACK` on any error.
- **Why:** a scheduled job will run twice one day. A rerun must replace, never double. The transaction means a failure halfway leaves the month as it was.
- **Evidence:** full pipeline run 3 times in a row → identical rows and totals, exit 0 each time; the test "load the same month twice" passes.

### D24. No DISTINCT or GROUP BY in the fact load
- **Why:** look-alike rows were already summed in D6. Aggregating again would delete real appointments.
- **Evidence:** check 4: 11 months compared, 0 differ.

### D25. Paths live in `config.py`
- **What:** `config.py` holds every path (`data/source`, `data/raw`, `data/clean`, the warehouse, `docs`) and the Hadoop folder. Environment variables (`GP_SOURCE`, `GP_RAW`, `GP_CLEAN`, `GP_WAREHOUSE`) or `run_pipeline.py --raw/--out/...` override them. The Hadoop settings apply on Windows only. The original NHS files sit untouched in `data/source`, and extract copies them into `data/raw`.
- **Why:** no path is tied to one machine. Proven: the project moved to a second laptop with no code changes, only installs.

### D26. Expected figures are constants, checked inside the pipeline
- **What:** `EXPECTED` in `config.py` holds raw rows, clean rows and totals. `transform.py` asserts against them, and `run_pipeline.py` checks every stage's output: raw rows, Parquet rows and totals, warehouse rows and totals, 3 facts + 5 dimensions.
- **Why:** comparing with a number from the same run only proves arithmetic works, and a printed "PASS" lets a bad run carry on.

### D27. Every label column cleaned, capitals checked
- **What:** the space clean-up (D4) now covers every label column, including names. A new transform check fails if two labels differ only by capital letters.
- **Evidence:** the check passes on every column; only `hcp_type` needed a fix (D5).

### D28. One command, exit codes, log file
- **What:** `run_pipeline.py` runs extract -> transform -> load -> checks, each as its own process, and stops at the first failure. Exit codes: 0 = **loaded**, 2 = a quality check **failed**, 1 = **crashed**. Each stage's figures and duration go to the screen and to `logs/pipeline.log`.
- **Why:** a notebook can't be scheduled; the exit code lets a scheduler tell a good run from a bad one without reading the log. Separate processes mean Spark shuts down fully after transform and the DuckDB file is never held by two stages.
- **Evidence:** 3 consecutive runs, exit 0 each.

### D29. Run all 9 checks, then judge
- **What:** `src/checks.py` runs all 9 checks, records each with the figures compared in `docs/quality_report.json`, then exits 2 if any failed.
- **Why:** one failure must not hide the other eight. Checks compare the warehouse against `EXPECTED`, not against itself.
- **Evidence:** 9/9 PASS. A test inserts one month twice on purpose, and checks 1 and 4 then FAIL, proving the checks can fail.

### D30. Check 9: duration covers about 91%, which is expected
- **What:** the threshold is 90%, not 100%.
- **Why:** `metadata_nhs.txt` defines actual duration as "the length in minutes of the consultation **that took place**". The category file counts all appointments, including DNA and Unknown status; the duration file counts only consultations that happened. Durations that are null, under 1 minute or over 60 minutes go to "Unknown / Data Quality", and recording differs by GP system supplier (EMIS, TPP). Forcing the two to agree would create a reporting error.
- **Evidence:** in every month, duration's share of category appointments equals the Attended share to 0.1% (e.g. Dec 2021: 90.9% vs 90.9%; May 2022: 92.2% vs 92.2%). Lowest month: 90.9% (Dec 2021). Query: `src/explore_coverage.py`.

### D31. Tests use a temporary warehouse
- **What:** `tests/test_warehouse.py` builds its own warehouse in a throw-away folder, using the real load functions.
- **Why:** tests never touch `warehouse/warehouse.duckdb`, and they test the actual pipeline code.
- **Evidence:** 16 tests pass 