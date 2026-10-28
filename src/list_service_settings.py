import duckdb

print(duckdb.sql("""
    SELECT service_setting, SUM(count_of_appointments) AS appointments
    FROM read_parquet('data/clean/categories/**/*.parquet')
    GROUP BY service_setting
    ORDER BY appointments DESC
"""))