import json
from datetime import datetime
from pathlib import Path
import sys

import duckdb
import config
from config import EXPECTED

REPORT = Path("docs/quality_report.json")


def one_value(con, sql):    
    """Run a query that returns a single value."""
    return con.execute(sql).fetchone()[0]


def make_result(name, passed, detail):
    return {"check": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def run_checks(con):
    results = []

    # Checks 1-3: each fact total equals the expected constant
    facts = [("fact_appointments_monthly", "regional"),
             ("fact_appointments_by_category", "categories"),
             ("fact_appointments_by_duration", "duration")]
    
    for number, (table, key) in enumerate(facts, start=1):
        total = one_value(con, f"SELECT SUM(count_of_appointments) FROM {table}")
        expected = EXPECTED[key]["total"]
        results.append(make_result(f"{number}.{table} total", total == expected,
                                   f"{total:,} vs expected {expected:,}"))

    # Check 4: regional and category monthly totals reconcile in the overlap
    months, differ = con.execute("""
        WITH r AS (SELECT appointment_month, SUM(count_of_appointments) AS regional
                    FROM fact_appointments_monthly
                    WHERE appointment_month BETWEEN '2021-08' AND '2022-06'
                    GROUP BY appointment_month),
             c AS (SELECT appointment_month, SUM(count_of_appointments) AS category
                    FROM fact_appointments_by_category
                    GROUP BY appointment_month)
        SELECT COUNT(*),
               SUM(CASE WHEN r.regional IS DISTINCT FROM c.category THEN 1 ELSE 0 END)
        FROM r FULL JOIN c ON r.appointment_month = c.appointment_month
    """).fetchone()
    results.append(make_result("4. Regional and category monthly totals reconcile, Aug 2021 - Jun 2022",
                               differ == 0, f"{months} months compared, {differ} differ"))

    # Check 5: every sub-ICB code in the daily facts exists in dim_geography
    orphans = one_value(con, """
        SELECT
          (SELECT COUNT(*) FROM fact_appointments_by_category f
             LEFT JOIN dim_geography g ON f.sub_icb_code = g.sub_icb_code
             WHERE g.sub_icb_code IS NULL)
        + (SELECT COUNT(*) FROM fact_appointments_by_duration f
             LEFT JOIN dim_geography g ON f.sub_icb_code = g.sub_icb_code
             WHERE g.sub_icb_code IS NULL)
    """)
    results.append(make_result("5. Every sub-ICB code exists in dim_geography",
                               orphans == 0, f"{orphans:,} orphan rows"))

    # Check 6: every booking-wait label is a known band
    unknown_wait = one_value(con, """
        SELECT COUNT(*) FROM fact_appointments_monthly f
        LEFT JOIN dim_booking_wait d
          ON f.time_between_book_and_appointment = d.time_between_book_and_appointment
        WHERE d.time_between_book_and_appointment IS NULL
    """)
    results.append(make_result("6. Every booking-wait label is a known band",
                               unknown_wait == 0, f"{unknown_wait:,} rows with an unknown label"))

    # Check 7: every duration label is a known band
    unknown_duration = one_value(con, """
        SELECT COUNT(*) FROM fact_appointments_by_duration f
        LEFT JOIN dim_duration_band d ON f.actual_duration = d.actual_duration
        WHERE d.actual_duration IS NULL
    """)
    results.append(make_result("7. Every duration label is a known band",
                               unknown_duration == 0, f"{unknown_duration:,} rows with an unknown label"))

    # Check 8: no null dates or counts in the category fact
    nulls = one_value(con, """
        SELECT COUNT(*) FROM fact_appointments_by_category
        WHERE appointment_date IS NULL OR count_of_appointments IS NULL
    """)
    results.append(make_result("8. No null dates or counts in the category fact",
                               nulls == 0, f"{nulls:,} null rows"))

    # Check 9: duration covers at least 90% of category appointments each month
    lowest = one_value(con, """
        WITH c AS (SELECT appointment_month, SUM(count_of_appointments) AS category
                   FROM fact_appointments_by_category GROUP BY appointment_month),
             d AS (SELECT appointment_month, SUM(count_of_appointments) AS duration
                   FROM fact_appointments_by_duration GROUP BY appointment_month)
        SELECT MIN(d.duration * 100.0 / c.category)
        FROM d JOIN c ON d.appointment_month = c.appointment_month
    """)
    results.append(make_result("9. Duration covers at least 90% of category appointments each month",
                               lowest >= 90, f"lowest month {lowest:.1f}%"))

    return results


def write_report(results, path=REPORT):
    passed = sum(r["status"] == "PASS" for r in results)
    report = {"run_at": datetime.now().isoformat(timespec="seconds"),
              "passed": passed, "total": len(results), "checks": results}
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return passed


if __name__ == "__main__":
    con = duckdb.connect(str(config.WAREHOUSE))
    try:
        results = run_checks(con)
        passed = write_report(results)
        for r in results:
            print(f"{r['status']}  {r['check']}: {r['detail']}")
        print(f"checks: {passed}/{len(results)} passed")
        if passed < len(results):
            sys.exit(2)          # 2 = a quality check failed
    finally:
        con.close()