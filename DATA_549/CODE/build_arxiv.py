"""
Builds the arXiv abstract sample for the language project.

Streams the full Kaggle metadata snapshot (one JSON record per line) from
DATA_549/DATA/RAW without loading it into memory, and keeps a balanced random
sample of papers from three fields:

    computational_linguistics   primary category cs.CL (topic shifted toward language models)
    math                        primary category math.*
    astrophysics                primary category astro-ph*

Each paper is labeled by the date of its FIRST version, so later revisions
can't move an old paper into the post class:

    pre_chatgpt    2019-01-01 through 2022-11-29
    (gap)          2022-11-30 through 2023-02-28, dropped as ambiguous
    post_chatgpt   2023-03-01 onward

Sampling is reservoir sampling with a fixed seed, so reruns give the same rows.

Run from anywhere:  python build_arxiv.py
Writes:             DATA_549/DATA/PROCESSED/arxiv_abstracts_sample.csv.gz
Read it back with:  pd.read_csv(path, dtype={"id": str})   # keeps IDs like 0704.0001 intact
"""
import json
import random
import time
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "DATA" / "RAW" / "arxiv-metadata-oai-snapshot.json"
OUT = ROOT / "DATA" / "PROCESSED" / "arxiv_abstracts_sample.csv.gz"

PER_GROUP = 10_000          # papers per field per label, 60,000 total
SEED = 549

PRE_START, PRE_END = date(2019, 1, 1), date(2022, 11, 29)
POST_START = date(2023, 3, 1)


def field_for(primary):
    if primary == "cs.CL":
        return "computational_linguistics"
    if primary.startswith("math."):
        return "math"
    if primary.startswith("astro-ph"):
        return "astrophysics"
    return None


def label_for(first_date):
    if PRE_START <= first_date <= PRE_END:
        return "pre_chatgpt"
    if first_date >= POST_START:
        return "post_chatgpt"
    return None


def collapse(text):
    return " ".join(str(text).split()) if text else ""


rng = random.Random(SEED)
reservoirs = {}   # (field, label) -> list of rows
seen = {}         # (field, label) -> eligible papers encountered
lines = 0
started = time.time()

with open(RAW, encoding="utf-8") as f:
    for line in f:
        lines += 1
        if lines % 500_000 == 0:
            print(f"  {lines:,} lines scanned, {time.time() - started:,.0f} seconds")

        paper = json.loads(line)
        categories = (paper.get("categories") or "").split()
        if not categories:
            continue
        field = field_for(categories[0])
        if field is None:
            continue

        abstract = collapse(paper.get("abstract"))
        comments = collapse(paper.get("comments"))
        if not abstract or "withdrawn" in comments.lower():
            continue

        versions = paper.get("versions") or []
        if not versions:
            continue
        first_date = parsedate_to_datetime(versions[0]["created"]).date()
        label = label_for(first_date)
        if label is None:
            continue

        key = (field, label)
        seen[key] = seen.get(key, 0) + 1
        row = {
            "id": paper.get("id"),
            "title": collapse(paper.get("title")),
            "abstract": abstract,
            "authors": collapse(paper.get("authors")),
            "author_count": len(paper.get("authors_parsed") or []),
            "categories": " ".join(categories),
            "primary_category": categories[0],
            "category_count": len(categories),
            "field": field,
            "comments": comments,
            "journal_ref": collapse(paper.get("journal-ref")),
            "doi": paper.get("doi") or "",
            "license": paper.get("license") or "",
            "first_version_date": first_date.isoformat(),
            "version_count": len(versions),
            "label": label,
        }

        bucket = reservoirs.setdefault(key, [])
        if len(bucket) < PER_GROUP:
            bucket.append(row)
        else:
            j = rng.randrange(seen[key])
            if j < PER_GROUP:
                bucket[j] = row

sample = pd.DataFrame([row for bucket in reservoirs.values() for row in bucket])
sample = sample.sort_values(["field", "label", "first_version_date"]).reset_index(drop=True)
sample.to_csv(OUT, index=False, compression="gzip")

print(f"\nScanned {lines:,} lines in {time.time() - started:,.0f} seconds")
print(f"Wrote {OUT}")
print(f"{len(sample):,} rows, {sample.shape[1]} columns, "
      f"{OUT.stat().st_size / 1_048_576:.1f} megabytes")
print("\nEligible papers found vs kept, by field and label:")
for key in sorted(seen):
    print(f"  {key[0]:26} {key[1]:13} found {seen[key]:>8,}   kept {len(reservoirs[key]):>6,}")