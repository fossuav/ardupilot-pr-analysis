#!/usr/bin/env python3
"""Metrics for the #32471 accel-bias covariance restore A/B, 2026-09-15.

    analyse_restore.py [--csv out.csv] LOG.BIN ...

Log names encode the cell: s1_<pre|nopre|plat>_<vrf>_v<V>_r<run>.BIN for the
arm-release probe (RestoreArmProbe) and s2_<step>_v<V>_r<run>.BIN for the
acro-exit probe (RestoreAcroProbe). V is 1 restore as pushed, 2 no restore,
3 no inhibit, 4 candidate restore.

Release time is the core-0 PRBR falling edge (E=0) where the variant has an
inhibit, else the ARM event (S1) or the ACRO exit (S2); a run whose inhibited
variant has no falling edge is reported as NO_RELEASE and must not be counted.

Height error e(t) = (-XKF1.PD) - (-SIM2.PD), core 0. S1 re-zeroes both at arm
(the archive's metrics.py definition, so worst|err| over 35 s after arm is
comparable with the 2026-09-04/05 tables). S2 references e to its mean over the
5 s before acro entry.
"""
import csv
import os
import re
import sys

import numpy as np
from pymavlink import DFReader

ARMED_EV = 10


def load(path):
    r = DFReader.DFReader_binary(path)
    d = {"MODE": [], "XKF1": [], "XKF2": [], "SIM2": [], "PRBR": [], "EV": [], "XKV2": []}
    while True:
        m = r.recv_match(type=list(d.keys()))
        if m is None:
            break
        ty = m.get_type()
        t = m.TimeUS * 1e-6
        if ty == "MODE":
            d[ty].append((t, m.Mode))
        elif ty == "XKF1" and m.C == 0:
            d[ty].append((t, m.PD))
        elif ty == "XKF2" and m.C == 0:
            d[ty].append((t, m.AZ))
        elif ty == "SIM2":
            d[ty].append((t, m.PD))
        elif ty == "PRBR" and m.C == 0:
            d[ty].append((t, m.E, m.Pb, m.Pa, m.Sv, m.Gr, m.V))
        elif ty == "EV":
            d[ty].append((t, m.Id))
        elif ty == "XKV2" and m.C == 0:
            d[ty].append((t, m.V15))
    return d


def interp(arr, t):
    return float(np.interp(t, arr[:, 0], arr[:, 1]))


def window(t, v, a, b):
    sel = (t >= a) & (t <= b)
    return v[sel]


def analyse(path):
    name = os.path.basename(path)[:-4]
    d = load(path)
    xkf1 = np.array(d["XKF1"])
    xkf2 = np.array(d["XKF2"])
    sim2 = np.array(d["SIM2"])
    out = {"log": name}
    m1 = re.match(r"s1_(pre|nopre|plat|platd\d)_([0-9.]+)_v(\d)_r(\d)", name)
    m2 = re.match(r"s2_([0-9.]+)_v(\d)_r(\d)", name)
    if not (m1 or m2) or len(xkf1) == 0 or len(sim2) == 0:
        out["status"] = "UNPARSED"
        return out
    falls = [p for p in d["PRBR"] if p[1] == 0]
    if m1:
        kind, size, var, run = m1.group(1), float(m1.group(2)), int(m1.group(3)), int(m1.group(4))
        out.update(scen="S1", cell="%s %.2f" % (kind, size), var=var, run=run)
        arms = [t for t, i in d["EV"] if i == ARMED_EV]
        if not arms:
            out["status"] = "NO_ARM"
            return out
        t_arm = arms[0]
        rel = [p for p in falls if abs(p[0] - t_arm) < 5]
        t_rel = rel[0][0] if rel else t_arm
        truth = np.column_stack((sim2[:, 0], -sim2[:, 1]))
        pd0 = interp(xkf1, t_arm)
        alt0 = interp(truth, t_arm)
        e = (-(xkf1[:, 1] - pd0)) - (np.interp(xkf1[:, 0], truth[:, 0], truth[:, 1]) - alt0)
        ref_bias = interp(xkf2, t_rel)
        out["worst35"] = float(np.abs(window(xkf1[:, 0], e, t_arm, t_arm + 35)).max())
        up = np.nonzero((truth[:, 0] > t_arm) & (truth[:, 1] - alt0 > 0.5))[0]
        if len(up):
            t_lift = truth[up[0], 0]
            out["lift_s"] = float(t_lift - t_arm)
            out["az_liftoff"] = float(interp(xkf2, t_lift) - interp(xkf2, t_arm - 1))
    else:
        size, var, run = float(m2.group(1)), int(m2.group(2)), int(m2.group(3))
        out.update(scen="S2", cell="step %.2f" % size, var=var, run=run)
        t_in = next(t for t, md in d["MODE"] if md == 1)
        t_out = next(t for t, md in d["MODE"] if md == 2 and t > t_in)
        rel = [p for p in falls if p[0] >= t_out - 0.5 and p[0] < t_out + 5]
        t_rel = rel[0][0] if rel else t_out
        truth = np.column_stack((sim2[:, 0], -sim2[:, 1]))
        e = (-xkf1[:, 1]) - np.interp(xkf1[:, 0], truth[:, 0], truth[:, 1])
        e = e - window(xkf1[:, 0], e, t_in - 5, t_in).mean()
        ref_bias = window(xkf2[:, 0], xkf2[:, 1], t_in - 5, t_in).mean()
        e_rel = float(np.interp(t_rel, xkf1[:, 0], e))
        out["err_at_rel"] = e_rel
        sgn = 1.0 if e_rel >= 0 else -1.0
        after = window(xkf1[:, 0], e, t_rel, t_rel + 35)
        out["overshoot"] = float(max(0.0, (-sgn * after).max()))
        a_rel = interp(truth, t_rel)
        tw = window(truth[:, 0], truth[:, 1], t_rel, t_rel + 20)
        out["alt_drop20"] = float(a_rel - tw.min())
        tw35 = window(truth[:, 0], truth[:, 1], t_rel, t_rel + 35)
        out["alt_exc35"] = float(np.abs(tw35 - a_rel).max())
    inhibited = not ((m1 and var == 3) or (m2 and var == 3))
    if inhibited and not rel:
        out["status"] = "NO_RELEASE"
    else:
        out["status"] = "ok"
    if rel:
        out["P15_before"] = rel[0][2]
        out["P15_after"] = rel[0][3]
    out["mean0_10"] = float(np.abs(window(xkf1[:, 0], e, t_rel, t_rel + 10)).mean())
    out["mean10_35"] = float(np.abs(window(xkf1[:, 0], e, t_rel + 10, t_rel + 35)).mean())
    az = window(xkf2[:, 0], xkf2[:, 1], t_rel, t_rel + 35) - ref_bias
    tz = window(xkf2[:, 0], xkf2[:, 0], t_rel, t_rel + 35) - t_rel
    out["az_at_rel"] = float(interp(xkf2, t_rel) - ref_bias)
    out["az_peak"] = float(az.max())
    out["az_final"] = float(window(xkf2[:, 0], xkf2[:, 1], t_rel + 30, t_rel + 35).mean() - ref_bias)
    target = size if m2 else out["az_final"]
    hit = np.nonzero(az >= 0.8 * target)[0] if abs(target) > 0.02 else []
    out["t80"] = float(tz[hit[0]]) if len(hit) else float("nan")
    return out


def main():
    args = sys.argv[1:]
    csv_out = None
    if args and args[0] == "--csv":
        csv_out = args[1]
        args = args[2:]
    rows = [analyse(p) for p in args]
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    for r in rows:
        print("  ".join("%s=%s" % (k, ("%.4g" % v) if isinstance(v, float) else v) for k, v in r.items()))
    if csv_out:
        with open(csv_out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for r in rows:
                w.writerow(r)


if __name__ == "__main__":
    main()
