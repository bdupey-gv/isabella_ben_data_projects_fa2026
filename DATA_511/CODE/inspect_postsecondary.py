"""
Inventory of the raw postsecondary files in DATA_511/DATA/RAW.

Part 1 checks every data file for fall 2018 through fall 2022: which comma-separated
values file gets used (the revised _rv version when there is one), row and column
counts, and whether the institution identifier is present.

Part 2 searches the fall 2022 data dictionaries for the variables the join needs,
so the build script gets written against real column names instead of guesses.

Run from anywhere:  python inspect_postsecondary.py
"""
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parent.parent / "DATA" / "RAW"


def files_for(fall_year):
    aid_year = f"{fall_year % 100:02d}{(fall_year + 1) % 100:02d}"
    return [f"HD{fall_year}", f"ADM{fall_year}", f"IC{fall_year}_AY",
            f"SFA{aid_year}", f"F{aid_year}_F2"]


def pick_csv(name):
    csvs = sorted((RAW / name).glob("*.csv"))
    revised = [c for c in csvs if c.stem.lower().endswith("_rv")]
    return (revised or csvs)[0] if csvs else None


def read_csv(path):
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="latin-1", low_memory=False)
    df.columns = (df.columns.str.replace("\u00ef\u00bb\u00bf", "", regex=False)
                  .str.strip().str.upper())
    return df


print("=== Part 1: data files ===")
for fall_year in range(2018, 2023):
    for name in files_for(fall_year):
        csv = pick_csv(name)
        if csv is None:
            print(f"{name:12} NO CSV FOUND")
            continue
        df = read_csv(csv)
        print(f"{name:12} {csv.name:24} rows={len(df):>6}  cols={df.shape[1]:>4}  "
              f"has UNITID={'UNITID' in df.columns}  "
              f"duplicate UNITIDs={df['UNITID'].duplicated().sum() if 'UNITID' in df.columns else 'n/a'}")

SEARCHES = {
    "HD2022": r"sector of institution|control of institution|level of institution",
    "ADM2022": r"applicants total|admissions total|enrolled total",
    "IC2022_AY": r"tuition and fees",
    "SFA2223": r"average net price|institutional grant",
    "F2223_F2": r"tuition|allowance|institutional grant|scholarship|discount",
}

print("\n=== Part 2: fall 2022 dictionary matches ===")
for name, pattern in SEARCHES.items():
    dictionaries = sorted((RAW / name).glob("*.xls*"))
    if not dictionaries:
        print(f"\n{name}: no dictionary spreadsheet found")
        continue
    book = pd.read_excel(dictionaries[0], sheet_name=None)
    varlist = next((df for sheet, df in book.items()
                    if sheet.lower().startswith("varlist")), None)
    if varlist is None:
        print(f"\n{name}: no Varlist sheet; sheets are {list(book)}")
        continue
    varlist.columns = varlist.columns.str.lower()
    if not {"varname", "vartitle"} <= set(varlist.columns):
        print(f"\n{name}: Varlist columns are {list(varlist.columns)}")
        continue
    hits = varlist[varlist["vartitle"].astype(str)
                   .str.contains(pattern, case=False, regex=True)]
    print(f"\n{name}  ({len(hits)} matches)")
    for _, row in hits.iterrows():
        print(f"  {str(row['varname']):12} {row['vartitle']}")