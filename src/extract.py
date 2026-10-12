import shutil
from pathlib import Path
import pandas as pd

SOURCE = Path(r"C:\lsa-oct-2026-external\Data Engineering\data")
ROW = Path("data/raw")

xlsx = SOURCE / "actual_duration.csv.xlsx"
CSV = ROW / "actual_duration.csv"

FILES = [
    "appointments_regional.csv",
    "national_categories.csv"
]

#copy csv files
for name in FILES:
    shutil.copy(SOURCE / name, ROW / name)
    print("copied", name)

#convert xlsx to csv
df = pd.read_excel(xlsx, engine="openpyxl")
df.to_csv(CSV, index=False)