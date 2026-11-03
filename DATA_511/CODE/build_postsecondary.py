"""
Builds the institution-by-year table for the yield project.

One row per private nonprofit four-year institution per fall, fall 2018 through
fall 2022. Joins five raw files per fall on UNITID:

    HD{Y}            directory: name, state, locale, size; filter to SECTOR == 2
    ADM{Y}           applicants, admits, enrolled (the yield target lives here)
    IC{Y}_AY         published tuition and fees for academic year Y to Y+1
    SFA{Y}{Y+1}      net price and grant aid for the fall Y first-time cohort
    F{Y}{Y+1}_F2     finance, private nonprofit form, fiscal year ending Y+1

Variable suffixes are relative to each file's own year, so the same names
work every year: CHG2AY3 is the file's current academic year in IC{Y}_AY,
and the "2" suffix (NPGRN2) is the current aid year in SFA{Y}{Y+1}.

Only selects, renames, and joins. Feature engineering belongs in the notebook.

Run from anywhere:  python build_postsecondary.py
Writes:             DATA_511/DATA/PROCESSED/postsecondary_panel.csv.gz
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "DATA" / "RAW"
OUT = ROOT / "DATA" / "PROCESSED" / "postsecondary_panel.csv.gz"

FALL_YEARS = range(2018, 2023)

# Raw column -> readable name, per source file
COLUMNS = {
    "HD": {
        "UNITID": "unitid",
        "INSTNM": "institution_name",
        "STABBR": "state",
        "LOCALE": "locale",
        "INSTSIZE": "size_category",
        "SECTOR": "sector",
    },
    "ADM": {
        "UNITID": "unitid",
        "APPLCN": "applicants",
        "ADMSSN": "admits",
        "ENRLT": "enrolled",
    },
    "IC_AY": {
        "UNITID": "unitid",
        "CHG2AY3": "sticker_tuition_fees",
    },
    "SFA": {
        "UNITID": "unitid",
        "NPGRN2": "average_net_price",
        "AGRNT_P": "first_time_percent_any_grant",
        "AGRNT_A": "first_time_average_any_grant",
        "IGRNT_P": "first_time_percent_institutional_grant",
        "IGRNT_A": "first_time_average_institutional_grant",
        "IGRNT_T": "first_time_total_institutional_grant",
    },
    "F": {
        "UNITID": "unitid",
        "F2D01": "tuition_fee_revenue",
        "F2C08": "allowances_applied_to_tuition",
        "F2C05": "institutional_grants_funded",
        "F2C06": "institutional_grants_unfunded",
        "F2C161": "allowances_endowment_gifts_tuition",
        "F2C171": "allowances_other_institutional_tuition",
    },
}


def file_names(fall_year):
    aid_year = f"{fall_year % 100:02d}{(fall_year + 1) % 100:02d}"
    return {
        "HD": f"HD{fall_year}",
        "ADM": f"ADM{fall_year}",
        "IC_AY": f"IC{fall_year}_AY",
        "SFA": f"SFA{aid_year}",
        "F": f"F{aid_year}_F2",
    }


def read_raw(name):
    csvs = sorted((RAW / name).glob("*.csv"))
    revised = [c for c in csvs if c.stem.lower().endswith("_rv")]
    path = (revised or csvs)[0]
    try:
        df = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="latin-1", low_memory=False)
    df.columns = (df.columns.str.replace("\u00ef\u00bb\u00bf", "", regex=False)
                  .str.strip().str.upper())
    return df


def select(df, source, name):
    wanted = COLUMNS[source]
    missing = [c for c in wanted if c not in df.columns]
    if missing:
        print(f"  WARNING {name}: missing {missing}, filled as empty")
    return df.reindex(columns=list(wanted)).rename(columns=wanted)


years = []
for fall_year in FALL_YEARS:
    names = file_names(fall_year)
    print(f"Fall {fall_year}")

    hd = select(read_raw(names["HD"]), "HD", names["HD"])
    table = hd[hd["sector"] == 2].drop(columns="sector")

    adm = select(read_raw(names["ADM"]), "ADM", names["ADM"])
    table = table.merge(adm, on="unitid", how="inner", validate="one_to_one")

    for source in ("IC_AY", "SFA", "F"):
        part = select(read_raw(names[source]), source, names[source])
        table = table.merge(part, on="unitid", how="left", validate="one_to_one")

    table.insert(1, "fall_year", fall_year)
    print(f"  {len(table)} institutions")
    years.append(table)

panel = pd.concat(years, ignore_index=True)
panel.to_csv(OUT, index=False, compression="gzip")

print(f"\nWrote {OUT}")
print(f"{len(panel)} rows, {panel.shape[1]} columns, "
      f"{OUT.stat().st_size / 1_048_576:.2f} megabytes")
print("\nRows per fall:")
print(panel["fall_year"].value_counts().sort_index().to_string())
print("\nMissing values by column:")
print(panel.isna().sum().to_string())