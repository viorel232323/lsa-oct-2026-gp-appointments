"""Transform: clean the 3 raw CSVs with PySpark and write Parquet partitioned by month.
Every check is an assert against config.EXPECTED, so a wrong number stops the run (exit code 2)."""
import os
import sys

import config

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
if os.name == "nt":                                   
    os.environ["HADOOP_HOME"] = config.HADOOP_HOME
    os.environ["PATH"] = config.HADOOP_HOME + r"\bin;" + os.environ["PATH"]

from pyspark.sql import SparkSession, functions as F

RAW = config.RAW.as_posix()
CLEAN = config.CLEAN.as_posix()

REGIONAL_LABELS = ["appointment_status", "hcp_type", "appointment_mode",
                   "time_between_book_and_appointment"]
CATEGORY_LABELS = ["sub_icb_location_name", "service_setting", "context_type", "national_category"]
DURATION_LABELS = ["sub_icb_location_name", "actual_duration"]


#Helpers
def total_of(df):
    return df.agg(F.sum("count_of_appointments")).first()[0]


def tidy_labels(df, columns):
    """ collapse repeated spaces and trim, in every label column."""
    for c in columns:
        df = df.withColumn(c, F.trim(F.regexp_replace(c, r"\s+", " ")))
    return df


def assert_consistent_capitals(df, columns, name):
    """Fail if two labels differ only by capital letters (e.g. 'staff' vs 'Staff')."""
    for c in columns:
        exact = df.select(c).distinct().count()
        ignoring_case = df.select(F.lower(F.col(c))).distinct().count()
        assert exact == ignoring_case, \
            f"{name}.{c}: {exact - ignoring_case} label(s) differ only by capitals"


def write_parquet(df, name):
    """one Parquet file per month folder."""
    (df.repartition("appointment_month")
       .write.mode("overwrite")
       .partitionBy("appointment_month")
       .parquet(f"{CLEAN}/{name}"))


# ---------- appointments_regional ----------
def transform_regional(spark):
    exp = config.EXPECTED["regional"]
    schema = """
        icb_ons_code                       STRING,
        appointment_month                  STRING,
        appointment_status                 STRING,
        hcp_type                           STRING,
        appointment_mode                   STRING,
        time_between_book_and_appointment  STRING,
        count_of_appointments              INT
    """
    df = spark.read.csv(f"{RAW}/appointments_regional.csv",
                        header=True, schema=schema, mode="FAILFAST")          # D1, D2
    rows_in, total_in = df.count(), total_of(df)
    assert rows_in == exp["raw_rows"], f"regional raw rows {rows_in:,} != expected {exp['raw_rows']:,}"

    df = df.withColumn("month_start", F.to_date("appointment_month", "yyyy-MM"))       # D3
    assert df.filter(F.col("month_start").isNull()).count() == 0, "regional: unparsed months"

    df = tidy_labels(df, REGIONAL_LABELS)                                          # D4
    df = df.withColumn("hcp_type",                                                 # D5
        F.when(F.col("hcp_type") == "Other Practice staff", "Other Practice Staff")
         .otherwise(F.col("hcp_type")))
    assert_consistent_capitals(df, REGIONAL_LABELS, "regional")

    key = ["icb_ons_code", "appointment_month", "month_start"] + REGIONAL_LABELS
    clean = (df.groupBy(key)                                                       # D6
               .agg(F.sum("count_of_appointments").alias("count_of_appointments")))

    rows_out, total_out = clean.count(), total_of(clean)
    assert rows_out == exp["rows"], f"regional rows {rows_out:,} != expected {exp['rows']:,}"
    assert total_out == total_in == exp["total"], \
        f"regional total {total_out:,} (raw {total_in:,}) != expected {exp['total']:,}"

    write_parquet(clean, "regional")
    print(f"regional: {rows_in:,} -> {rows_out:,} rows, {total_out:,} appointments")


# ---------- national_categories ----------
def transform_categories(spark):
    exp = config.EXPECTED["categories"]
    schema = """
        appointment_date       STRING,
        icb_ons_code           STRING,
        sub_icb_location_name  STRING,
        service_setting        STRING,
        context_type           STRING,
        national_category      STRING,
        count_of_appointments  INT,
        appointment_month      STRING
    """   # D8: names come from this schema, so the hidden byte-order mark in the header is ignored
    df = spark.read.csv(f"{RAW}/national_categories.csv",
                        header=True, schema=schema, mode="FAILFAST")
    rows_in, total_in = df.count(), total_of(df)
    assert rows_in == exp["raw_rows"], f"categories raw rows {rows_in:,} != expected {exp['raw_rows']:,}"

    df = (df.withColumn("appointment_date", F.to_date("appointment_date", "dd/MM/yyyy"))          # D9
            .withColumn("sub_icb_code",
                        F.regexp_extract("sub_icb_location_name", r"-\s*(\w+)\s*$", 1)))         # D10
    df = tidy_labels(df, CATEGORY_LABELS)
    assert_consistent_capitals(df, CATEGORY_LABELS, "categories")

    assert df.filter(F.col("appointment_date").isNull()).count() == 0, "categories: unparsed dates"
    wrong_month = df.filter(F.date_format("appointment_date", "yyyy-MM") != F.col("appointment_month")).count()
    assert wrong_month == 0, f"categories: {wrong_month:,} dates outside their month (day-first parse failed?)"
    assert df.filter(F.col("sub_icb_code") == "").count() == 0, "categories: sub-ICB code missing from name"

    key = ["appointment_date", "sub_icb_location_name", "service_setting", "context_type", "national_category"]
    duplicates = rows_in - df.select(key).distinct().count()
    assert duplicates == 0, f"categories: {duplicates:,} duplicate keys"                          # D11

    total_out = total_of(df)
    assert total_out == total_in == exp["total"], \
        f"categories total {total_out:,} (raw {total_in:,}) != expected {exp['total']:,}"

    write_parquet(df, "categories")
    print(f"categories: {rows_in:,} rows, {total_out:,} appointments")


# ---------- actual_duration ----------
def transform_duration(spark):
    exp = config.EXPECTED["duration"]
    schema = """
        sub_icb_location_code      STRING,
        sub_icb_location_ons_code  STRING,
        sub_icb_location_name      STRING,
        icb_ons_code               STRING,
        region_ons_code            STRING,
        appointment_date           STRING,
        actual_duration            STRING,
        count_of_appointments      INT
    """
    df = spark.read.csv(f"{RAW}/actual_duration.csv",
                        header=True, schema=schema, mode="FAILFAST")
    rows_in, total_in = df.count(), total_of(df)
    assert rows_in == exp["raw_rows"], f"duration raw rows {rows_in:,} != expected {exp['raw_rows']:,}"

    df = (df.withColumn("appointment_date", F.to_date("appointment_date", "yyyy-MM-dd"))          # D12
            .withColumn("appointment_month", F.date_format("appointment_date", "yyyy-MM")))      # D13
    df = tidy_labels(df, DURATION_LABELS)
    assert_consistent_capitals(df, DURATION_LABELS, "duration")

    assert df.filter(F.col("appointment_date").isNull()).count() == 0, "duration: unparsed dates"
    key = ["sub_icb_location_code", "appointment_date", "actual_duration"]
    duplicates = rows_in - df.select(key).distinct().count()
    assert duplicates == 0, f"duration: {duplicates:,} duplicate keys"                            # D16

    total_out = total_of(df)
    assert total_out == total_in == exp["total"], \
        f"duration total {total_out:,} (raw {total_in:,}) != expected {exp['total']:,}"

    write_parquet(df, "duration")
    print(f"duration: {rows_in:,} rows, {total_out:,} appointments")


# ---------- Run all three ----------
def main():
    spark = (SparkSession.builder
             .appName("lsa-oct-2026-transform")
             .master("local[*]")
             .config("spark.driver.memory", "4g")
             .config("spark.sql.shuffle.partitions", "8")
             .getOrCreate())
    try:
        transform_regional(spark)
        transform_categories(spark)
        transform_duration(spark)
    except AssertionError as error:
        print(f"CHECK FAILED: {error}")
        sys.exit(2)                       
    finally:
        spark.stop()


if __name__ == "__main__":
    main()