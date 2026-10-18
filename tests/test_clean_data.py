from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]      
CLEAN = ROOT / "data" / "clean"
RAW = ROOT / "data" / "raw"

#Test1: Row counts
regional   = pd.read_parquet(CLEAN / "regional")
categories = pd.read_parquet(CLEAN / "categories")
duration   = pd.read_parquet(CLEAN / "duration")

def test_row_counts():
    assert len(regional) == 295_692
    assert len(duration) == 137_793
    assert len(categories) == 817_394

#Test2: Total appointments preserved
def raw_total(file_name):
    """Sum of count_of_appointments in a raw CSV."""
    raw = pd.read_csv(RAW / file_name, usecols=["count_of_appointments"])
    return raw["count_of_appointments"].sum()


def test_totals_preserved():
    assert regional["count_of_appointments"].sum()   == raw_total("appointments_regional.csv") == 742_804_525
    assert categories["count_of_appointments"].sum() == raw_total("national_categories.csv")   == 296_046_770
    assert duration["count_of_appointments"].sum()   == raw_total("actual_duration.csv")       == 167_980_692

# Test 3: no duplicate keys
REGIONAL_KEY = ["icb_ons_code", "appointment_month", "appointment_status",
                "hcp_type", "appointment_mode", "time_between_book_and_appointment"]
CATEGORIES_KEY = ["appointment_date", "sub_icb_location_name", "service_setting",
                  "context_type", "national_category"]
DURATION_KEY = ["sub_icb_location_code", "appointment_date", "actual_duration"]


def test_no_duplicate_keys():
    assert regional.duplicated(subset=REGIONAL_KEY).sum() == 0
    #assert pd.concat([regional, regional.head(1)]).duplicated(subset=REGIONAL_KEY).sum() == 0
    assert categories.duplicated(subset=CATEGORIES_KEY).sum() == 0
    assert duration.duplicated(subset=DURATION_KEY).sum() == 0

# Test 4: no double spaces in labels
LABEL_COLS = [
    (regional,   ["appointment_status", "hcp_type", "appointment_mode",
                  "time_between_book_and_appointment"]),
    (categories, ["service_setting", "context_type", "national_category"]),
    (duration,   ["actual_duration"]),
]


def test_no_double_spaces():
    for df, cols in LABEL_COLS:
        for c in cols:
            assert df[c].str.contains("  ", regex=False, na=False).sum() == 0, c

# Test 5: dates parsed day-first(national_categories)
def test_dates_day_first():
    dates = pd.to_datetime(categories["appointment_date"])
    #dates = pd.to_datetime(categories["appointment_date"].astype(str), format="%Y-%d-%m", errors="coerce")
    assert dates.isna().sum() == 0                              # no empty dates

    month_from_date = dates.dt.strftime("%Y-%m")
    month_column = categories["appointment_month"].astype(str)
    assert (month_from_date != month_column).sum() == 0         # every date sits in its own month

# Test 6: all counts are positive
def test_counts_positive():
    for name, df in [("regional", regional), ("categories", categories), ("duration", duration)]:
        counts = df["count_of_appointments"]
        #counts = pd.concat([df["count_of_appointments"], pd.Series([0])])
        assert counts.isna().sum() == 0, name      # no empty counts
        assert (counts <= 0).sum() == 0, name      # no zero or negative counts