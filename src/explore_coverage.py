"""One-off check: does duration match the 'Attended' appointments? (explains check 9)"""
import duckdb
import config

con = duckdb.connect(str(config.WAREHOUSE), read_only=True)
con.sql("""
    WITH c AS (SELECT appointment_month, SUM(count_of_appointments) AS category
               FROM fact_appointments_by_category GROUP BY appointment_month),
         d AS (SELECT appointment_month, SUM(count_of_appointments) AS duration
               FROM fact_appointments_by_duration GROUP BY appointment_month),
         a AS (SELECT appointment_month, SUM(count_of_appointments) AS attended
               FROM fact_appointments_monthly
               WHERE appointment_status = 'Attended'
               GROUP BY appointment_month)
    SELECT d.appointment_month,
           ROUND(d.duration * 100.0 / c.category, 1) AS duration_pct,
           ROUND(a.attended * 100.0 / c.category, 1) AS attended_pct
    FROM d
    JOIN c ON c.appointment_month = d.appointment_month
    JOIN a ON a.appointment_month = d.appointment_month
    ORDER BY d.appointment_month
""").show()
con.close()