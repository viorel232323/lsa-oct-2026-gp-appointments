import shutil
from pathlib import Path
import pandas as pd

import hashlib
import json
from datetime import datetime, timezone
import config


SOURCE = config.SOURCE                                              #Source files(actual)
ROW = config.RAW                                                    #empty
ROW.mkdir(parents=True, exist_ok=True)


xlsx = SOURCE / "actual_duration.csv.xlsx"                          #xlsx(actual)
CSV = ROW / "actual_duration.csv"                                   #empty

FILES = [
    "appointments_regional.csv",                        
    "national_categories.csv",                                                    
]

#copy csv files
for name in FILES:
    shutil.copy(SOURCE / name, ROW / name)                          #Source to ROW
    print("copied", name)

#convert xlsx to csv
df = pd.read_excel(xlsx, engine="openpyxl")                         #Excel to CSV
df.to_csv(CSV, index=False)

MANIFEST_FILES = FILES +[CSV.name]                                  #Concatenate Excel file to the CSV Files(list)


def file_info(path):
    """extract from a file: name, size in bytes, sha256, rows count, extraction time """
    #1 checksum: a unique fingerprint of the file's exact bytes
    with open(path, "rb") as f:
        checksum = hashlib.file_digest(f, "sha256").hexdigest()
    
    # 2. row count (header not counted)
        rows = len(pd.read_csv(path, dtype=str))

    # 3. put all facts into one dict

    return {
        "file_name": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": checksum,
        "row_count": rows,
        "extracted at": datetime.now(timezone.utc).isoformat(timespec="seconds") 
    }
#Test1-Succesfull:  print(file_info(ROW / "appointments_regional.csv"))


#Loop over all the files
manifest = []

for name in MANIFEST_FILES:
    manifest.append(file_info(ROW/name))
    
    print("recorded",name)
#Test2-Succesfull: print(manifest)


#Write the JSON file
DOCS = config.DOCS

with open(DOCS / "manifest.json", "w",encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
    print("manifest written:", DOCS/"manifest.json")

