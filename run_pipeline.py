"""Run the whole pipeline in order: extract -> transform -> load -> checks.
Exit codes: 0 = loaded, 2 = stopped by a failed quality check, 1 = crashed."""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import duckdb
import config

LOG = Path("logs/pipeline.log")
STAGES = ["extract", "transform", "load", "checks"]
DATASETS = {"regional": "appointments_regional.csv",
            "categories": "national_categories.csv",
            "duration": "actual_duration.csv"}


def log(message):
    """Print a line and also add it to logs/pipeline.log."""
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}  {message}"
    print(line)
    LOG.parent.mkdir(exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------- What to verify after each stage ----------
def summarise_extract(args):
    manifest = json.loads((config.DOCS / "manifest.json").read_text(encoding="utf-8"))
    rows = {entry["file_name"]: entry["row_count"] for entry in manifest}
    for name, file_name in DATASETS.items():
        expected = config.EXPECTED[name]["raw_rows"]
        assert rows[file_name] == expected, f"{file_name}: {rows[file_name]:,} rows != expected {expected:,}"
    return " / ".join(f"{rows[f]:,}" for f in DATASETS.values()) + " raw rows"


def summarise_transform(args):
    con = duckdb.connect()                                  
    parts = []
    for name in DATASETS:
        path = f"{Path(args.out).as_posix()}/{name}/**/*.parquet"
        rows, total = con.execute(
            f"SELECT COUNT(*), SUM(count_of_appointments) FROM read_parquet('{path}')").fetchone()
        exp = config.EXPECTED[name]
        assert rows == exp["rows"] and total == exp["total"], \
            f"{name}: {rows:,} rows / {total:,} appointments != expected {exp['rows']:,} / {exp['total']:,}"
        parts.append(f"{name} {rows:,} rows {total:,} appointments")
    con.close()
    return "; ".join(parts)


def summarise_load(args):
    con = duckdb.connect(args.warehouse, read_only=True)
    facts, dims = con.execute("""
        SELECT COUNT(*) FILTER (WHERE table_name LIKE 'fact_%'),
               COUNT(*) FILTER (WHERE table_name LIKE 'dim_%')
        FROM information_schema.tables""").fetchone()
    con.close()
    assert (facts, dims) == (3, 5), f"expected 3 facts and 5 dimensions, found {facts} and {dims}"
    return f"{facts} facts, {dims} dimensions"


def summarise_checks(args):
    report = json.loads((config.DOCS / "quality_report.json").read_text(encoding="utf-8"))
    return f"{report['passed']}/{report['total']} passed"


SUMMARIES = {"extract": summarise_extract, "transform": summarise_transform,
             "load": summarise_load, "checks": summarise_checks}


# ---------- Running ----------
def parse_args():
    parser = argparse.ArgumentParser(description="Run the GP appointments pipeline.")
    parser.add_argument("--source", default=str(config.SOURCE), help="folder with the original NHS files")
    parser.add_argument("--raw", default=str(config.RAW), help="folder for the raw copies")
    parser.add_argument("--out", default=str(config.CLEAN), help="folder for the clean Parquet")
    parser.add_argument("--warehouse", default=str(config.WAREHOUSE), help="DuckDB file")
    return parser.parse_args()


def run_stage(stage, env):
    start = time.perf_counter()
    result = subprocess.run([sys.executable, "-m", f"src.{stage}"], env=env)
    return result.returncode, time.perf_counter() - start


def main():
    args = parse_args()
    env = {**os.environ, "GP_SOURCE": args.source, "GP_RAW": args.raw,
           "GP_CLEAN": args.out, "GP_WAREHOUSE": args.warehouse}
    log(f"pipeline start  raw={args.raw}  out={args.out}  warehouse={args.warehouse}")

    for stage in STAGES:
        code, seconds = run_stage(stage, env)
        if code != 0:
            log(f"{stage} FAILED after {seconds:.1f}s (exit {code})")
            return 2 if code == 2 else 1
        try:
            detail = SUMMARIES[stage](args)
        except AssertionError as error:
            log(f"{stage} CHECK FAILED: {error}")
            return 2
        log(f"{stage} OK in {seconds:.1f}s  {detail}")
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except Exception as error:                       # anything unexpected = a crash
        log(f"pipeline CRASHED: {error!r}")
        exit_code = 1
    log(f"exit {exit_code}")
    sys.exit(exit_code)