#!/usr/bin/env python3
"""Aggregate analyse_restore.py CSV rows into mean and min..max per cell and variant.

    aggregate.py rows.csv
"""
import csv
import math
import sys
from collections import defaultdict

S1_KEYS = ["worst35", "mean0_10", "mean10_35", "lift_s", "az_liftoff", "az_final", "t80"]
S2_KEYS = ["err_at_rel", "mean0_10", "mean10_35", "alt_drop20", "overshoot", "az_peak", "t80"]
VNAME = {"1": "V1 restore", "2": "V2 none", "3": "V3 no inhibit", "4": "V4 scaled 1/16"}


def fmt(vals):
    vals = [v for v in vals if not math.isnan(v)]
    if not vals:
        return "-"
    m = sum(vals) / len(vals)
    if len(vals) == 1:
        return "%.2f" % m
    return "%.2f (%.2f..%.2f)" % (m, min(vals), max(vals))


rows = list(csv.DictReader(open(sys.argv[1])))
bad = [r["log"] for r in rows if r.get("status") != "ok"]
groups = defaultdict(list)
for r in rows:
    if r.get("status") == "ok":
        groups[(r["scen"], r["cell"], r["var"])].append(r)

for scen, keys in (("S1", S1_KEYS), ("S2", S2_KEYS)):
    cells = sorted({(c, v) for (s, c, v) in groups if s == scen})
    if not cells:
        continue
    print("\n%s | cell | variant | n | %s |" % (scen, " | ".join(keys)))
    print("|---" * (len(keys) + 3) + "|")
    for c, v in cells:
        g = groups[(scen, c, v)]
        cols = []
        for k in keys:
            cols.append(fmt([float(x[k]) if x.get(k) not in (None, "", "nan") else float("nan") for x in g]))
        print("| %s | %s | %d | %s |" % (c, VNAME.get(v, v), len(g), " | ".join(cols)))
if bad:
    print("\nnot counted:", " ".join(bad))
