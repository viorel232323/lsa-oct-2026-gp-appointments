#%% Spark Initialisation
import os, sys
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

from pyspark.sql import SparkSession, functions as F

spark = (SparkSession.builder
         .appName("lsa-oct-2026-transform")
         .master("local[*]")
         .config("spark.driver.memory", "4g")
         .config("spark.sql.shuffle.partitions", "8")
         .getOrCreate())


regional_schema = """
    icb_ons_code                       STRING,
    appointment_month                  STRING,
    appointment_status                 STRING,
    hcp_type                           STRING,
    appointment_mode                   STRING,
    time_between_book_and_appointment  STRING,
    count_of_appointments              INT
"""

regional = spark.read.csv("data/raw/appointments_regional.csv",
                          header=True, schema=regional_schema, mode= "FAILFAST")

regional.printSchema()     # shows each column and its type
print(f"Rows: {regional.count():,}") 

#%% add month_start as a real date (and keep appointment_month as text)
regional = regional.withColumn("month_start", F.to_date("appointment_month", "yyyy-MM"))
# check: every month converted, none empty
print("Empty dates:", regional.filter(F.col("month_start").isNull()).count())
regional.select("appointment_month","month_start").distinct().orderBy("month_start").show(3) 
    

#%% Tidy the labels

label_cols = ["appointment_status", "hcp_type", 
              "appointment_mode",
              "time_between_book_and_appointment"]

for a in label_cols:
    regional = regional.withColumn(a, F.trim(F.regexp_replace(a, r"\s+", " ")))

#standardise the staff type name

regional = regional.withColumn(
    "hcp_type",
    F.when(F.col("hcp_type") == "Other Practice staff", "Other Practice Staff").otherwise(F.col("hcp_type"))
                                )
# %% Checks
print("Double spaces left:",
      regional.filter(F.col("time_between_book_and_appointment").contains("  ")).count())
regional.select("hcp_type").distinct().show()
regional.select("time_between_book_and_appointment").distinct().show(truncate=False)
# %%


