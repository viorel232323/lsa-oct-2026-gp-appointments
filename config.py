"""One place for settings: paths, and the numbers every run must reproduce."""
import os
from pathlib import Path

# Each path has a default inside the project; an environment variable can override it.
SOURCE    = Path(os.environ.get("GP_SOURCE", "data/source"))
RAW       = Path(os.environ.get("GP_RAW", "data/raw"))
CLEAN     = Path(os.environ.get("GP_CLEAN", "data/clean"))
WAREHOUSE = Path(os.environ.get("GP_WAREHOUSE", "warehouse/warehomkdir data\sourceuse.duckdb"))
DOCS      = Path("docs")

HADOOP_HOME = os.environ.get("HADOOP_HOME", r"C:\hadoop")

EXPECTED = {
    "regional":   {"raw_rows": 596_821, "rows": 295_692, "total": 742_804_525},
    "categories": {"raw_rows": 817_394, "rows": 817_394, "total": 296_046_770},
    "duration":   {"raw_rows": 137_793, "rows": 137_793, "total": 167_980_692},
}