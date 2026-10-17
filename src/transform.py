#%% Spark Initialisation
import os, sys
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

os.environ["HADOOP_HOME"] = r"C:\hadoop"
os.environ["PATH"] = r"C:\hadoop\bin;" + os.environ["PATH"]

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

# add month_start as a real date (and keep appointment_month as text)
regional = regional.withColumn("month_start", F.to_date("appointment_month", "yyyy-MM"))
# check: every month converted, none empty
print("Empty dates:", regional.filter(F.col("month_start").isNull()).count())
regional.select("appointment_month","month_start").distinct().orderBy("month_start").show(3) 
    

# Tidy the labels

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
#  Checks
print("Double spaces left:",
      regional.filter(F.col("time_between_book_and_appointment").contains("  ")).count())
regional.select("hcp_type").distinct().show()
regional.select("time_between_book_and_appointment").distinct().show(truncate=False)

# Groupby and Sum

key_cols = ["icb_ons_code", "appointment_month", "month_start", "appointment_status",
            "hcp_type", "appointment_mode", "time_between_book_and_appointment"]

regional_clean = (regional
                  .groupBy(key_cols)
                  .agg(F.sum("count_of_appointments").alias("count_of_appointments"))
)

# Checks

rows_before = regional.count()
rows_after = regional_clean.count()
total_before = regional.agg(F.sum("count_of_appointments")).first()[0]
total_after = regional_clean.agg(F.sum("count_of_appointments")).first()[0]

print(f"Rows: {rows_before:,} -> {rows_after:,}")
print(f"Total appointments: {total_before:,} -> {total_after:,}")

#%% Writing Regional as Paquet

(regional_clean
    .repartition("appointment_month")
    .write
    .mode("overwrite")
    .partitionBy("appointment_month")
    .parquet("data/clean/regional"))
print("written")

#%% Read back and count

from pathlib import Path
back = spark.read.parquet("data/clean/regional")
print(f"Rows: {back.count():,}")                                                   
print(f"Total appointments: {back.agg(F.sum('count_of_appointments')).first()[0]:,}")         
print("Parquet files:", len(list(Path("data/clean/regional").rglob("*.parquet"))))  
back.printSchema()                                                                  




#%% Check schema
regional.printSchema()

# %% Stop Spark session(release memory)
spark.stop()
