#!/usr/bin/env python3
"""Quality checks and exploratory correlation for the curated Sindh 2022 dataset.

Uses only Python's standard library. This is district-level ecological analysis,
not an asset-level damage-curve calibration.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "pakistan_2022_sindh_flood_damage_exploratory.csv"
OUTPUT = ROOT / "reports" / "pakistan_2022_sindh_exploratory_analysis.json"

def pearson(xs, ys):
    mx, my = mean(xs), mean(ys)
    numerator = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denom_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    denom_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    return numerator / (denom_x * denom_y) if denom_x and denom_y else None

def ranks(values):
    order = sorted(range(len(values)), key=values.__getitem__)
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        rank = (i + 1 + j) / 2.0
        for k in order[i:j]:
            out[k] = rank
        i = j
    return out

def main():
    with INPUT.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 23:
        raise ValueError(f"Expected 23 matched non-Karachi Sindh districts; found {len(rows)}")
    names = [r["district_name"] for r in rows]
    if len(set(names)) != len(names):
        raise ValueError("Duplicate district names found")
    flooded = [float(r["pct_admin_area_flooded_2022"]) for r in rows]
    partial = [int(r["partially_damaged_houses_as_of_2022-10-24"]) for r in rows]
    full = [int(r["fully_damaged_houses_as_of_2022-10-24"]) for r in rows]
    damaged = [int(r["total_damaged_houses_as_of_2022-10-24"]) for r in rows]
    if any(not 0 <= x <= 100 for x in flooded):
        raise ValueError("Flooded area percentage outside [0, 100]")
    if any(p + f != total for p, f, total in zip(partial, full, damaged)):
        raise ValueError("Partial + full damaged houses do not equal total for every row")
    rho = pearson(ranks(flooded), ranks(damaged))
    result = {
        "analysis": "Exploratory district-level association between a published 2022 flood-extent percentage and reported house damage counts",
        "n_matched_districts": len(rows),
        "sum_partially_damaged_houses_in_matched_districts": sum(partial),
        "sum_fully_damaged_houses_in_matched_districts": sum(full),
        "sum_total_damaged_houses_in_matched_districts": sum(damaged),
        "min_pct_admin_area_flooded": min(flooded),
        "max_pct_admin_area_flooded": max(flooded),
        "pearson_r_raw_pct_vs_house_count": pearson(flooded, damaged),
        "spearman_rho_pct_vs_house_count": rho,
        "pearson_r_log1p_pct_vs_log1p_house_count": pearson([math.log1p(x) for x in flooded], [math.log1p(y) for y in damaged]),
        "top_5_by_flooded_area_pct": [
            {"district": rows[i]["district_name"], "pct_admin_area_flooded_2022": flooded[i], "houses_damaged_as_of_2022_10_24": damaged[i]}
            for i in sorted(range(len(rows)), key=lambda i: flooded[i], reverse=True)[:5]
        ],
        "qa": {
            "district_count_expected": 23,
            "district_count_pass": True,
            "unique_district_names_pass": True,
            "flood_percent_range_pass": True,
            "partial_plus_full_equals_total_pass": True,
        },
        "interpretation_limits": [
            "The flood-extent table is a third-party 2026 Zenodo analysis of VIIRS-derived flood polygons and administrative boundaries; it is not the PDMA damage inventory.",
            "PDMA figures are district-level house-damage counts reported as of 2022-10-24, not geolocated building records.",
            "Flood extent and damage sources differ in method, timing, and measurement; district-level association cannot establish causality.",
            "No flood-depth-to-damage ratios, replacement values, insurance losses, or building-level vulnerability parameters are observed here.",
            "Do not use this result to calibrate or validate CRPA monetary loss curves.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
