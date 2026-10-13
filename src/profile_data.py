#%% 


import pandas as pd
from pathlib import Path

ROW = Path("data/raw")

def profile(df):
    """ One row per column: type, nulls, distinct values, explanation. """
    return pd.DataFrame({
        "type":      df.dtypes.astype(str),
        "nulls":     df.isna().sum(),
        "distinct":  df.nunique(),
        "example":   df.iloc[0]
    })


#appointments_regional.csv


Regional = pd.read_csv(ROW / "appointments_regional.csv")
print("Rows,Columns:", Regional.shape)
print(profile(Regional))


#regional: total, date range
print("\nTotal appointments:", f"{Regional['count_of_appointments'].sum():,}")   
print("Period:", Regional["appointment_month"].min(), "to", Regional["appointment_month"].max())

#labels (quotes in the output show hidden spaces)
for col in ["appointment_status", "hcp_type", "appointment_mode", "time_between_book_and_appointment"]:
    print("\n", col, sorted(Regional[col].unique()))

#duplicate rows
print(f"\nExact duplicate rows: {Regional.duplicated().sum():,}")                     
key_cols = Regional.columns.drop("count_of_appointments")
print(f"Rows sharing the same key: {Regional.duplicated(subset=key_cols).sum():,}")



# %%  national_categories.csv 

Categories = pd.read_csv(ROW / "national_categories.csv")

print("Rows,Columns:", Categories.shape)
print(profile(Categories))
pd.set_option("display.width", 200)


#day-first dates, Largest First day, Period
dates = Categories["appointment_date"]
print("\nFirst date:", dates.head(1).tolist()) 

first_number = dates.str.split("/").str[0].astype(int)
print("Largest first number(date):", first_number.max())   

period = pd.to_datetime(dates, format="%d/%m/%Y")
print("Period:", period.min().date(), "to", period.max().date())

#Categories of columns
for col in ["service_setting", "context_type", "national_category"]:
    print(f"\n{col}: {sorted(Categories[col].unique())}")

#total appoinments,Exact duplicates, rows sharing the same key
print(f"\nTotal appointments: {Categories['count_of_appointments'].sum():,}")    

print(f"Exact duplicate rows: {Categories.duplicated().sum():,}")

cat_key = Categories.columns.drop("count_of_appointments")
print(f"Rows sharing the same key: {Categories.duplicated(subset=cat_key).sum():,}")


# %%
