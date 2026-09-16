#!/usr/bin/env python3
'''Analyse UnevenGroundProbe logs: EKF against simulator truth over the traverse and hold.'''
import ast
import math
import os
import statistics
import sys

from pymavlink import mavutil


def load(binpath):
    mlog = mavutil.mavlink_connection(binpath)
    d = {"PRBU": [], "XKF1": [], "SIM2": [], "MODE": [], "RFND": []}
    while True:
        m = mlog.recv_match(type=list(d.keys()))
        if m is None:
            break
        t = m.TimeUS * 1e-6
        if m.get_type() == "PRBU":
            if m.C == 0:
                d["PRBU"].append((t, m.FH, m.TH, m.FG, m.TU, m.GV, m.GM, m.HR, m.AID))
        elif m.get_type() == "XKF1":
            if m.C == 0:
                d["XKF1"].append((t, m.PN, m.PE, m.VN, m.VE))
        elif m.get_type() == "SIM2":
            d["SIM2"].append((t, m.PN, m.PE, m.VN, m.VE))
        elif m.get_type() == "MODE":
            d["MODE"].append((t, m.Mode))
        elif m.get_type() == "RFND":
            d["RFND"].append((t, m.Dist, m.Stat))
    return d


def at(series, t):
    best = None
    for row in series:
        if row[0] <= t:
            best = row
        else:
            break
    return best


def window(series, t0, t1):
    return [r for r in series if t0 <= r[0] <= t1]


def phase(d, t0, t1):
    k0 = at(d["XKF1"], t0)
    s0 = at(d["SIM2"], t0)
    if k0 is None or s0 is None:
        return None
    errs = []
    for k in window(d["XKF1"], t0, t1):
        s = at(d["SIM2"], k[0])
        ekf = (k[1] - k0[1], k[2] - k0[2])
        tru = (s[1] - s0[1], s[2] - s0[2])
        errs.append((k[0], math.hypot(ekf[0] - tru[0], ekf[1] - tru[1]), ekf, tru))
    if not errs:
        return None
    kspd = [math.hypot(k[3], k[4]) for k in window(d["XKF1"], t0, t1)]
    sspd = [math.hypot(s[3], s[4]) for s in window(d["SIM2"], t0, t1)]
    pr = window(d["PRBU"], t0, t1)
    last = errs[-1]
    out = {
        "err_max": max(e[1] for e in errs),
        "err_end": last[1],
        "ekf_dist": math.hypot(*last[2]),
        "true_dist": math.hypot(*last[3]),
        "ekf_spd": statistics.median(kspd) if kspd else float('nan'),
        "true_spd": statistics.median(sspd) if sspd else float('nan'),
        "fh_end": pr[-1][1] if pr else float('nan'),
        "th_end": pr[-1][2] if pr else float('nan'),
        "fh_th_med": statistics.median([p[1] / p[2] for p in pr if p[2] > 0.5]) if pr else float('nan'),
        "fg_frac": sum(1 for p in pr if p[3]) / len(pr) if pr else float('nan'),
        "tu_frac": sum(1 for p in pr if p[4]) / len(pr) if pr else float('nan'),
        "hr_frac": sum(1 for p in pr if p[7]) / len(pr) if pr else float('nan'),
        "aid": sorted(set(p[8] for p in pr)),
    }
    return out


def main():
    binpath = sys.argv[1]
    events = []
    ev = binpath.replace(".BIN", ".events")
    if os.path.exists(ev):
        events = ast.literal_eval(open(ev).read())
    d = load(binpath)
    evd = {}
    for t, what in events:
        evd.setdefault(what, t)
    print("== %s" % os.path.basename(binpath))
    print("events: %s" % events)
    modes = [(round(t, 1), mo) for t, mo in d["MODE"]]
    print("modes: %s" % modes)
    # sanity: true AGL against the rangefinder while it is in range
    diffs = []
    for t, dist, stat in d["RFND"]:
        if stat == 4 and dist > 1.0:
            p = at(d["PRBU"], t)
            if p is not None and abs(p[0] - t) < 0.2:
                diffs.append(p[2] - dist)
    if diffs:
        print("sanity: TH - RFND (Good, >1m) median %+.2f m over %u samples" % (statistics.median(diffs), len(diffs)))
    for name, a, b in (("traverse", "traverse start", "traverse end"), ("hold", "hold start", "hold end")):
        if a in evd and b in evd:
            r = phase(d, evd[a], evd[b])
            if r is None:
                continue
            print("%s: err max %.1f end %.1f m | dist ekf %.0f true %.0f m | spd ekf %.2f true %.2f m/s | "
                  "FH/TH end %.1f/%.1f med ratio %.2f | FG %.0f%% TU %.0f%% HR %.0f%% AID %s" %
                  (name, r["err_max"], r["err_end"], r["ekf_dist"], r["true_dist"], r["ekf_spd"], r["true_spd"],
                   r["fh_end"], r["th_end"], r["fh_th_med"], 100 * r["fg_frac"], 100 * r["tu_frac"],
                   100 * r["hr_frac"], r["aid"]))
    # climb: first loss of relative position and true AGL then
    if "climb start" in evd:
        pr = [p for p in d["PRBU"] if p[0] >= evd["climb start"]]
        lost = next((p for p in pr if not p[7]), None)
        if lost is not None:
            print("climb: horiz_pos_rel first clear at t=%.1f true AGL %.1f m" % (lost[0], lost[2]))
        else:
            print("climb: horiz_pos_rel never cleared after climb start")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        sys.argv = [sys.argv[0], p]
        main()
