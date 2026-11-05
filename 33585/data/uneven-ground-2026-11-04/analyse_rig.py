#!/usr/bin/env python3
'''EKF against SITL truth over the traverse of an UnevenGroundProbe log, and the hold after it.'''
import ast, math, os, statistics, sys
from pymavlink import mavutil

def load(path):
    d = {"XKF1": [], "SIM2": [], "XKF5": []}
    m = mavutil.mavlink_connection(path)
    while True:
        x = m.recv_match(type=list(d.keys()))
        if x is None:
            break
        t = x.TimeUS * 1e-6
        if x.get_type() == "XKF1" and x.C == 0:
            d["XKF1"].append((t, x.PN, x.PE, x.VN, x.VE))
        elif x.get_type() == "SIM2":
            d["SIM2"].append((t, x.PN, x.PE, x.VN, x.VE))
        elif x.get_type() == "XKF5" and x.C == 0:
            d["XKF5"].append((t, x.HAGL))
    return d

def at(series, t):
    best = None
    for r in series:
        if r[0] <= t:
            best = r
        else:
            break
    return best

def phase(d, t0, t1):
    k0, s0 = at(d["XKF1"], t0), at(d["SIM2"], t0)
    errs = []
    for k in [r for r in d["XKF1"] if t0 <= r[0] <= t1]:
        s = at(d["SIM2"], k[0])
        e = (k[1] - k0[1], k[2] - k0[2]); tr = (s[1] - s0[1], s[2] - s0[2])
        errs.append((math.hypot(e[0] - tr[0], e[1] - tr[1]), e, tr))
    ks = [math.hypot(r[3], r[4]) for r in d["XKF1"] if t0 <= r[0] <= t1]
    ss = [math.hypot(r[3], r[4]) for r in d["SIM2"] if t0 <= r[0] <= t1]
    return "err max %.1f end %.1f m | dist ekf %.0f true %.0f m | spd ekf %.2f true %.2f" % (
        max(e[0] for e in errs), errs[-1][0], math.hypot(*errs[-1][1]), math.hypot(*errs[-1][2]),
        statistics.median(ks), statistics.median(ss))

for path in sys.argv[1:]:
    ev = ast.literal_eval(open(path.replace(".BIN", ".events")).read())
    d = load(path)
    times = {}
    for t, what in ev:
        times.setdefault(what, t)
    print("== %s" % os.path.basename(path))
    print("   events: %s" % [e for e in ev if not e[1].startswith('climb')])
    if "traverse start" in times:
        print("   traverse: " + phase(d, times["traverse start"], times.get("traverse end", 1e9)))
    if "hold start" in times:
        print("   hold: " + phase(d, times["hold start"], times.get("hold end", 1e9)))
