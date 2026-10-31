#!/usr/bin/env python3
"""Yaw and stillness side by side: the flown core 0 (XKF1/XKFM C 0 in the source
log) and each Replay's core 0 (C 100), every STEP seconds from T0 to T1.
usage: yaw_timeline.py <source log> T0 T1 STEP name=<replay BIN> [name=<BIN>...]
"""
import bisect
import sys
from pymavlink import mavutil


def load(path, core):
    m = mavutil.mavlink_connection(path, robust_parsing=True)
    yaw, gz, ognm = [], [], []
    while True:
        msg = m.recv_match(type=['XKF1', 'XKFM'])
        if msg is None:
            break
        if msg.C != core:
            continue
        t = msg.TimeUS * 1e-6
        if msg.get_type() == 'XKF1':
            yaw.append((t, msg.Yaw))
            gz.append((t, msg.GZ))
        else:
            ognm.append((t, msg.OGNM))
    return yaw, gz, ognm


def at(series, t):
    i = bisect.bisect_right([x[0] for x in series], t) - 1
    return series[i][1] if i >= 0 else None


src, t0, t1, step = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
runs = [("flown", load(src, 0))]
for arg in sys.argv[5:]:
    name, path = arg.split("=", 1)
    runs.append((name, load(path, 100)))
print("     t  " + "  ".join("%-22s" % n for n, _ in runs))
t = t0
while t <= t1:
    cells = []
    for name, (yaw, gz, ognm) in runs:
        y, g, o = at(yaw, t), at(gz, t), at(ognm, t)
        cells.append("%6s %5s %s" % (("%.1f" % y) if y is not None else "-", ("%.2f" % g) if g is not None else "-",
                                       ("S" if o else "m") if o is not None else "?"))
    print("%6.1f  %s" % (t, "  ".join("%-22s" % c for c in cells)))
    t += step
