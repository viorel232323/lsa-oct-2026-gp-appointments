# GP Appointments Data Pipeline

An end-to-end data pipeline for NHS England **"Appointments in General Practice"** data, built for the **LSA Data Engineering Internship.**

**Extract → Transform → Load → Checks**, run by one command.

| Week | Stage | Status |
|---|---|---|
| 1 | Extract: copy raw files, convert Excel, write manifest, profile the data | ✅ Done |
| 2 | Transform: clean with PySpark, write Parquet, test with pytest | ✅ Done |
| 3 | Load & automate: DuckDB star schema, idempotent load, 9 quality checks, one command | ✅ Done |
| 4 | Showcase: dashboard in Streamlit + Plotly | To do |

## Tech stack
- **Python 3.12**, in a virtual environment
- **PySpark 4.2.0**: cleaning and transforming (needs Java; tested with Java 25, Eclipse Temurin)
- **DuckDB**: the warehouse, a single file
- **pandas, openpyxl, pyarrow**: Excel conversion, profiling, reading Parquet in tests
- **pytest**: data and warehouse tests
- **Streamlit + Plotly**: Week 4

## The data
| Dataset | One row is… | Raw rows | Clean rows | Total appointments | Period |
|---|---|---|---|---|---|
| `appointments_regional` | ICB × month × status × HCP type × mode × booking wait | 596,821 | 295,692 | 742,804,525 | Jan 2020 – Jun 2022 |
| `national_categories` | sub-ICB × day × service setting × context type × national category | 817,394 | 817,394 | 296,046,770 | Aug 2021 – Jun 2022 |
| `actual_duration` | sub-ICB × day × duration band | 137,793 | 137,793 | 167,980,692 | Dec 2021 – Jun 2022 |

Full profile: [docs/data_profile.md](docs/data_profile.md)

## Folder layout
```
lsa-oct-2026-gp-appointments/
├── config.py               # all paths + the expected figures, in one place
├── run_pipeline.py         # one command: extract → transform → load → checks
├── pytest.ini              # lets the tests import config and src
├── requirements.txt
├── src/
│   ├── extract.py          # copy source files, Excel → CSV, write manifest
│   ├── profile_data.py     # profile the 3 raw files
│   ├── transform.py        # clean with PySpark → Parquet (asserts every total)
│   ├── load.py             # build the DuckDB star schema (safe to rerun)
│   ├── checks.py           # the 9 quality checks → docs/quality_report.json
│   └── explore_coverage.py # evidence for check 9 (duration = attended)
├── tests/
│   ├── test_clean_data.py  #the clean Parquet
│   └── test_warehouse.py   #the warehouse
├── docs/
│   ├── data_profile.md     # what the raw data looks like
│   ├── decision_log.md     # why each choice was made
│   ├── manifest.json       # file sizes, SHA-256 checksums, row counts
│   └── quality_report.json # result of the 9 checks
├── app/                    #dashboard
├── data/source/            # original NHS files (not on GitHub, you add them)
├── data/raw/               # not on GitHub, rebuilt by extract
├── data/clean/             # not on GitHub, rebuilt by transform
├── warehouse/              # not on GitHub, rebuilt by load
└── logs/                   # not on GitHub, pipeline.log
```

## Setup from a clean clone (Windows)
1. Install **Python 3.12** (python.org; tick "Add python.exe to PATH") and **Java** (adoptium.net, Temurin; tick "Set JAVA_HOME").
2. **Windows only:** download `winutils.exe` and `hadoop.dll` from [cdarlint/winutils](https://github.com/cdarlint/winutils) (`hadoop-3.3.6/bin`) into `C:\hadoop\bin`. Spark needs them to write files on Windows.
3. Clone the repo and create the environment:
   ```
   git clone https://github.com/viorel232323/lsa-oct-2026-gp-appointments.git
   cd lsa-oct-2026-gp-appointments
   py -3.12 -m venv .venv --prompt gp-pipeline
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   If activation says "running scripts is disabled", run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
4. Put the **4 original files** in `data/source/`: `appointments_regional.csv`, `national_categories.csv`, the actual-duration `.xlsx`, `metadata_nhs.txt`.

On Mac, Linux or Colab, skip step 2 and activate with `source .venv/bin/activate`.

## How to run
From the project folder, with the environment active:
```
python run_pipeline.py
```
Every path has a default in `config.py`. To use other folders:
```
python run_pipeline.py --source path/to/files --raw data/raw --out data/clean --warehouse warehouse/warehouse.duckdb
```

Expected end of the output (also written to `logs/pipeline.log`):
```
extract OK    596,821 / 817,394 / 137,793 raw rows
transform OK  regional 295,692 rows 742,804,525 appointments; ...
load OK       3 facts, 5 dimensions; 295,692 rows 742,804,525 / 817,394 rows 296,046,770 / 137,793 rows 167,980,692
checks OK     9/9 passed
exit 0
```

| Exit code | Meaning |
|---|---|
| `0` | Loaded, all checks passed |
| `2` | Stopped by a failed quality check |
| `1` | Crashed |

In PowerShell, `echo $LASTEXITCODE` shows the last exit code. Each stage can also run on its own, e.g. `python -m src.load`.

**Safe to rerun:** the pipeline was run 3 times in a row with identical rows and totals and exit 0 each time. The load deletes and reinserts each month inside a transaction, so nothing ever doubles.

## The warehouse (`warehouse/warehouse.duckdb`)
| Table | Type | One row is… |
|---|---|---|
| `fact_appointments_monthly` | Fact | ICB × month × status × staff type × mode × booking wait |
| `fact_appointments_by_category` | Fact | sub-ICB × day × service setting × national category |
| `fact_appointments_by_duration` | Fact | sub-ICB × day × duration band |
| `dim_geography` | Dimension | sub-ICB, with its ICB and region (106 rows) |
| `dim_date` | Dimension | day, 2020-01-01 to 2022-12-31, with month, year, weekday |
| `dim_booking_wait` | Dimension | booking-wait band, with a sort order |
| `dim_duration_band` | Dimension | duration band, with a sort order |
| `dim_national_category` | Dimension | national category, with its context type |

## Quality checks
`src/checks.py` runs 9 checks and writes [docs/quality_report.json](docs/quality_report.json), one entry per check with PASS/FAIL and the figures compared:

1–3. Each fact total matches its expected figure.
4. Regional and category monthly totals match, Aug 2021 – Jun 2022.
5. Every sub-ICB code exists in `dim_geography`.
6–7. Every booking-wait and duration label is a known band.
8. No null dates or counts in the category fact.
9. Duration covers at least 90% of category appointments each month. It is about 91% because duration only counts consultations that took place; see D30 in the decision log.

## Tests
```
python -m pytest -v
```
16 tests: 6 for the clean Parquet (row counts, totals preserved, no duplicate keys, no double spaces, day-first dates, positive counts) and 10 for the warehouse (reload twice changes nothing, totals, no orphans, known labels, complete calendar, checks pass, and **a broken load makes the checks fail**).

Result on 28 Oct 2026: **16 passed**.

## Documentation
- [Data profile](docs/data_profile.md)
- [Decision log](docs/decision_log.md): every choice, Weeks 1–3
- [Quality report](docs/quality_report.json)





