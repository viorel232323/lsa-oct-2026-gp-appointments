"""Load: build the star schema in DuckDB from the clean Parquet. Safe to rerun."""
import duckdb
import config

REGIONAL   = f"{config.CLEAN.as_posix()}/regional/**/*.parquet"
CATEGORIES = f"{config.CLEAN.as_posix()}/categories/**/*.parquet"
DURATION   = f"{config.CLEAN.as_posix()}/duration/**/*.parquet"


def build_dimensions(con):
    """Rebuild the 5 small dimension tables from scratch."""
    con.execute(f"""
        CREATE OR REPLACE TABLE dim_geography AS
        SELECT DISTINCT
            sub_icb_location_code      AS sub_icb_code,
            sub_icb_location_ons_code  AS sub_icb_ons_code,
            sub_icb_location_name      AS sub_icb_name,
            icb_ons_code,
            region_ons_code
        FROM read_parquet('{DURATION}', hive_partitioning = true)
        ORDER BY sub_icb_code
    """)
    con.execute(f"""
        CREATE OR REPLACE TABLE dim_national_category AS
        SELECT DISTINCT national_category, context_type
        FROM read_parquet('{CATEGORIES}', hive_partitioning = true)
        ORDER BY national_category
    """)
    con.execute("""
        CREATE OR REPLACE TABLE dim_date AS
        SELECT
            CAST(d AS DATE)        AS date,
            strftime(d, '%Y-%m')   AS appointment_month,
            year(d)                AS year,
            month(d)               AS month,
            monthname(d)           AS month_name,
            dayname(d)             AS weekday_name,
            isodow(d)              AS weekday_number,
            isodow(d) IN (6, 7)    AS is_weekend
        FROM range(DATE '2020-01-01', DATE '2023-01-01', INTERVAL 1 DAY) AS t(d)
    """)
    con.execute("""
        CREATE OR REPLACE TABLE dim_booking_wait AS
        SELECT * FROM (VALUES
            ('Same Day',               1),
            ('1 Day',                  2),
            ('2 to 7 Days',            3),
            ('8 to 14 Days',           4),
            ('15 to 21 Days',          5),
            ('22 to 28 Days',          6),
            ('More than 28 Days',      7),
            ('Unknown / Data Quality', 8)
        ) AS t(time_between_book_and_appointment, sort_order)
    """)
    con.execute("""
        CREATE OR REPLACE TABLE dim_duration_band AS
        SELECT * FROM (VALUES
            ('1-5 Minutes',            1),
            ('6-10 Minutes',           2),
            ('11-15 Minutes',          3),
            ('16-20 Minutes',          4),
            ('21-30 Minutes',          5),
            ('31-60 Minutes',          6),
            ('Unknown / Data Quality', 7)
        ) AS t(actual_duration, sort_order)
    """)


def create_facts(con):
    """Create the 3 fact tables once; later runs keep them."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS fact_appointments_monthly (
            appointment_month                  VARCHAR,
            icb_ons_code                       VARCHAR,
            appointment_status                 VARCHAR,
            hcp_type                           VARCHAR,
            appointment_mode                   VARCHAR,
            time_between_book_and_appointment  VARCHAR,
            count_of_appointments              BIGINT
        )""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS fact_appointments_by_category (
            appointment_date       DATE,
            appointment_month      VARCHAR,
            sub_icb_code           VARCHAR,
            service_setting        VARCHAR,
            national_category      VARCHAR,
            count_of_appointments  BIGINT
        )""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS fact_appointments_by_duration (
            appointment_date       DATE,
            appointment_month      VARCHAR,
            sub_icb_code           VARCHAR,
            actual_duration        VARCHAR,
            count_of_appointments  BIGINT
        )""")


# What each fact is filled from (column order = table order).
FACTS = {
    "fact_appointments_monthly": f"""
        SELECT appointment_month, icb_ons_code, appointment_status, hcp_type,
               appointment_mode, time_between_book_and_appointment, count_of_appointments
        FROM read_parquet('{REGIONAL}', hive_partitioning = true)""",
    "fact_appointments_by_category": f"""
        SELECT appointment_date, appointment_month, sub_icb_code, service_setting,
               national_category, count_of_appointments
        FROM read_parquet('{CATEGORIES}', hive_partitioning = true)""",
    "fact_appointments_by_duration": f"""
        SELECT appointment_date, appointment_month, sub_icb_location_code AS sub_icb_code,
               actual_duration, count_of_appointments
        FROM read_parquet('{DURATION}', hive_partitioning = true)""",
}


def load_month(con, table, select_sql, month):
    """Delete this month, insert this month, in one transaction."""
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(f"DELETE FROM {table} WHERE appointment_month = ?", [month])
        con.execute(f"INSERT INTO {table} {select_sql} WHERE appointment_month = ?", [month])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


def load_facts(con):
    """Load every month of every fact table."""
    for table, select_sql in FACTS.items():
        months = [row[0] for row in con.execute(
            f"SELECT DISTINCT appointment_month FROM ({select_sql}) ORDER BY 1").fetchall()]
        for month in months:
            load_month(con, table, select_sql, month)
        rows, total = con.execute(
            f"SELECT COUNT(*), SUM(count_of_appointments) FROM {table}").fetchone()
        print(f"{table}: {len(months)} months, {rows:,} rows, {total:,} appointments")


def run():
    config.WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(config.WAREHOUSE))
    try:
        build_dimensions(con)
        create_facts(con)
        load_facts(con)
    finally:
        con.close()


if __name__ == "__main__":
    run()