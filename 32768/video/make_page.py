#!/usr/bin/env python3
"""Build explainer.html from explainer.src.html with the CSVs inlined."""
import csv
import json
from pathlib import Path

HERE = Path(__file__).parent
D = HERE / "data"


def rows(name):
    with open(D / name) as f:
        return list(csv.DictReader(f))


log12 = [[round(float(r["time_s"]), 1), round(float(r["Alt"]), 3), round(float(r["Temp"]), 2)]
         for i, r in enumerate(rows("log12_baro.csv")) if i % 2 == 0]
ekf = [[round(float(r["time_s"]), 2), round(-float(r["PD"]), 3), round(float(r["VD"]), 3)]
       for r in rows("sitl_xkf1.csv")]
baro = [[round(float(r["time_s"]), 2), round(float(r["Alt"]), 3)] for r in rows("sitl_baro.csv")]
data = json.dumps({"log12": log12, "sitl_ekf": ekf, "sitl_baro": baro}, separators=(",", ":"))
src = (HERE / "explainer.src.html").read_text()
(HERE / "explainer.html").write_text(src.replace("__DATA__", data))
