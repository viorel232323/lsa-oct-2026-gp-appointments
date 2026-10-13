import pandas as pd
from pathlib import Path

# %% setup

ROW = Path("data/raw")

def profile(df):
    """ One row per column: type, nulls, distinct values, explanation. """
    return pd.DataFrame({
        "type":      df.dtypes.astype(str),
        "nulls":     df.isna().sum(),
        "distinct":  df.nunique(),
        "example":   df.iloc[0]
    })

#%% Regional
Regional = pd.read_csv(ROW / "appointments_regional.csv")
print("Rows,Columns:", Regional.shape)
print(profile(Regional))


#  regional: total, date range
print("\nTotal appointments:", f"{Regional['count_of_appointments'].sum():,}")   # expect 742,804,525
print("Period:", Regional["appointment_month"].min(), "to", Regional["appointment_month"].max())

# trap 5: labels (quotes in the output show hidden spaces)
for col in ["appointment_status", "hcp_type", "appointment_mode", "time_between_book_and_appointment"]:
    print("\n", col, sorted(Regional[col].unique()))

#  trap 4: duplicate rows
print(f"\nExact duplicate rows: {Regional.duplicated().sum():,}")                     # expect 21,604
key_cols = Regional.columns.drop("count_of_appointments")
print(f"Rows sharing the same key: {Regional.duplicated(subset=key_cols).sum():,}")

# %%
