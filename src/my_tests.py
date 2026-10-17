#Initialise Spark
import os, sys
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

from pyspark.sql import SparkSession
spark = SparkSession.builder.appName("lsa-oct-2026").master("local[*]").getOrCreate()
print(spark.version)


#Spark Monitoring Page
print(spark.sparkContext.uiWebUrl)


#Partitions test
df = spark.read.csv("data/raw/appointments_regional.csv", header=True)
print(df.rdd.getNumPartitions())

#See how many Logical processors
print(spark.sparkContext.defaultParallelism) 

#Action1 - test
df.groupBy("appointment_month").count().show()  

#Action2 - test
spark.range(1_000_000_000).selectExpr("sum(id)").show()