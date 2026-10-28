import shutil

import duckdb
import pytest

import config
from src import load, checks

FACT_TABLES = {"regional": "fact_appointments_monthly",
               "categories": "fact_appointments_by_category",
               "duration": "fact_appointments_by_duration"}


# ---------- Fixtures: a temporary warehouse just for testing ----------
@pytest.fixture(scope="module")
def warehouse_file(tmp_path_factory):
    """build a fresh warehouse in a temporary folder, once for this whole file."""
    path = tmp_path_factory.mktemp("warehouse") / "test.duckdb"
    con = duckdb.connect(str(path))
    load.build_dimensions(con)
    load.create_facts(con)
    load.load_facts(con)
    con.close()
    return path


@pytest.fixture
def con(warehouse_file):
    """a connection to the test warehouse, for tests that only read."""
    con = duckdb.connect(str(warehouse_file))
    yield con
    con.close()


@pytest.fixture
def scratch(warehouse_file, tmp_path):
    """a copy of the test warehouse, for tests that change or break it."""
    copy = tmp_path / "scratch.duckdb"
    shutil.copy(warehouse_file, copy)
    con = duckdb.connect(str(copy))
    yield con
    con.close()


def rows_and_total(con, table):
    return con.execute(f"SELECT COUNT(*), SUM(count_of_appointments) FROM {table}").fetchone()


# Test 1: loading the same month twice changes nothing
def test_load_same_month_twice(scratch):
    table = "fact_appointments_monthly"
    before = rows_and_total(scratch, table)
    load.load_month(scratch, table, load.FACTS[table], "2021-08")
    load.load_month(scratch, table, load.FACTS[table], "2021-08")
    assert rows_and_total(scratch, table) == before


# Test 2: each fact's rows and total equal the EXPECTED constants
def test_fact_totals_match_expected(con):
    for name, table in FACT_TABLES.items():
        rows, total = rows_and_total(con, table)
        assert rows == config.EXPECTED[name]["rows"], table
        assert total == config.EXPECTED[name]["total"], table


# Test 3: every sub-ICB code in the daily facts exists in dim_geography
@pytest.mark.parametrize("table", ["fact_appointments_by_category", "fact_appointments_by_duration"])
def test_no_orphan_sub_icb_codes(con, table):
    orphans = con.execute(f"""
        SELECT COUNT(*) FROM {table} f
        LEFT JOIN dim_geography g ON f.sub_icb_code = g.sub_icb_code
        WHERE g.sub_icb_code IS NULL""").fetchone()[0]
    assert orphans == 0


# Test 4: every label in a fact exists in its dimension
@pytest.mark.parametrize("fact, dim, column", [
    ("fact_appointments_monthly", "dim_booking_wait", "time_between_book_and_appointment"),
    ("fact_appointments_by_duration", "dim_duration_band", "actual_duration"),
    ("fact_appointments_by_category", "dim_national_category", "national_category"),
])
def test_labels_exist_in_dimension(con, fact, dim, column):
    unknown = con.execute(f"""
        SELECT COUNT(*) FROM {fact} f
        LEFT JOIN {dim} d ON f.{column} = d.{column}
        WHERE d.{column} IS NULL""").fetchone()[0]
    assert unknown == 0


# Test 5: dim_date has one row per day, no gaps, no duplicates
def test_dim_date_complete(con):
    rows, distinct_days, first, last = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT date), MIN(date), MAX(date) FROM dim_date").fetchone()
    assert rows == distinct_days                       # no duplicates
    assert rows == (last - first).days + 1             # no gaps
    assert (str(first), str(last)) == ("2020-01-01", "2022-12-31")


# Test 6a: all 9 checks pass on a good warehouse
def test_checks_pass_on_good_warehouse(con):
    results = checks.run_checks(con)
    failed = [r for r in results if r["status"] == "FAIL"]
    assert failed == []


# Test 6b: a deliberately broken load makes the checks FAIL
def test_checks_catch_a_broken_load(scratch):
    # Break it: insert Aug 2021 a second time WITHOUT deleting first, so it doubles
    scratch.execute(f"INSERT INTO fact_appointments_monthly "
                    f"{load.FACTS['fact_appointments_monthly']} WHERE appointment_month = '2021-08'")
    status = {r["check"].split(".")[0]: r["status"] for r in checks.run_checks(scratch)}
    assert status["1"] == "FAIL"        # regional total no longer matches
    assert status["4"] == "FAIL"        # Aug 2021 no longer reconciles with categories