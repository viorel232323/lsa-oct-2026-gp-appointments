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

#%% national_categories.csv

categories_schema = """
    appointment_date       STRING,
    icb_ons_code           STRING,
    sub_icb_location_name  STRING,
    service_setting        STRING,
    context_type           STRING,
    national_category      STRING,
    count_of_appointments  INT,
    appointment_month      STRING
"""
categories = spark.read.csv("data/raw/national_categories.csv",
                            header=True, schema=categories_schema, mode="FAILFAST")
print(f"Rows: {categories.count():,}")       

#Categories: transform: appointment_date -> date
                           #Extract sub-icb code
                           #Trim extra spaces
categories = (categories
    .withColumn("appointment_date", F.to_date("appointment_date", "dd/MM/yyyy"))
    .withColumn("sub_icb_code", F.regexp_extract("sub_icb_location_name", r"-\s*(\w+)\s*$", 1)))

for c in ["service_setting", "context_type", "national_category"]:
    categories = categories.withColumn(c, F.trim(F.regexp_replace(c, r"\s+", " ")))

#Categories: checks
total = categories.agg(F.sum("count_of_appointments")).first()[0]
print(f"Total appointments: {total:,}")   
print("Empty dates:", categories.filter(F.col("appointment_date").isNull()).count())
print("Month mismatches:",
      categories.filter(F.date_format("appointment_date", "yyyy-MM") != F.col("appointment_month")).count()) 
print("Distinct sub-ICB codes:", categories.select("sub_icb_code").distinct().count()) 
print("Empty codes:", categories.filter(F.col("sub_icb_code") == "").count())

#No duplicate Keys
key = ["appointment_date", "sub_icb_location_name", "service_setting", "context_type", "national_category"]
print("Key duplicates:", categories.count() - categories.select(key).distinct().count())   


# %% Categories: write
(categories
    .repartition("appointment_month")
    .write.mode("overwrite")
    .partitionBy("appointment_month")
    .parquet("data/clean/categories"))
print("written")

#%% Read appointments_duration.csv with an explicit schema
duration_schema = """
    sub_icb_location_code      STRING,
    sub_icb_location_ons_code  STRING,
    sub_icb_location_name      STRING,
    icb_ons_code               STRING,
    region_ons_code            STRING,
    appointment_date           STRING,
    actual_duration            STRING,
    count_of_appointments      INT
"""
duration = spark.read.csv("data/raw/actual_duration.csv",
                          header=True, schema=duration_schema, mode="FAILFAST")
print(f"Rows: {duration.count():,}")     
duration.select("appointment_date").show(4)

# Dates, month column, label tidy

duration = (duration
    .withColumn("appointment_date", F.to_date("appointment_date", "yyyy-MM-dd"))
    .withColumn("appointment_month", F.date_format("appointment_date", "yyyy-MM"))
    .withColumn("actual_duration", F.trim(F.regexp_replace("actual_duration", r"\s+", " "))))

#Duration: checks
total = duration.agg(F.sum("count_of_appointments")).first()[0]
print(f"Total appointments: {total:,}")                                                          
print("Empty dates:", duration.filter(F.col("appointment_date").isNull()).count())  
duration.select("appointment_month").distinct().orderBy("appointment_month").show()  #7 months
duration.groupBy("actual_duration").count().orderBy("actual_duration").show(truncate=False)  # the duration bands

key = ["sub_icb_location_code", "appointment_date", "actual_duration"]
print("Key duplicates:", duration.count() - duration.select(key).distinct().count())

#%% Duration: Write

(duration
    .repartition("appointment_month")
    .write.mode("overwrite")
    .partitionBy("appointment_month")
    .parquet("data/clean/duration"))
print("written")




#%% Check schema
regional.printSchema()
categories.printSchema()

# %% Stop Spark session(release memory)
spark.stop()
