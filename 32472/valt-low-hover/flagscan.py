#!/usr/bin/env python3
"""flagscan.py LOG: while armed and flying in VALT, the share of core 0 XKF4 samples with the
EKF ground effect flags set (takeoff 2048, touchdown 4096), binned by range finder height,
with the baro minus range finder height in each bin (both from the arming point)"""
import sys
from collections import defaultdict
from pymavlink import mavutil

m = mavutil.mavlink_connection(sys.argv[1])
armed = True  # these logs start at arming
mode = None
rf = None
baro = None
b0 = None
bins = defaultdict(lambda: [0, 0, 0, []])
tflag = []
while True:
    r = m.recv_match(type=["ARM", "MODE", "RFND", "BARO", "XKF4"])
    if r is None:
        break
    ty = r.get_type()
    if ty == "ARM":
        armed = r.ArmState == 1
        if armed:
            b0 = baro
    elif ty == "MODE":
        mode = r.ModeNum
    elif ty == "RFND":
        rf = r.Dist
    elif ty == "BARO" and r.I == 0:
        baro = r.Alt
        if b0 is None:
            b0 = baro
    elif ty == "XKF4" and r.C == 0 and armed and mode == 29 and rf is not None:
        k = min(int(rf / 0.25), 8)
        b = bins[k]
        b[0] += 1
        if r.SS & 2048:
            b[1] += 1
        if r.SS & 4096:
            b[2] += 1
        if baro is not None and b0 is not None:
            b[3].append(baro - b0 - rf)
print("RF bin      n   takeoff%  touchdown%   baro-RF p10 median p90")
for k in sorted(bins):
    n, to, td, e = bins[k]
    e.sort()
    q = (lambda p: e[int(p * (len(e) - 1))]) if e else (lambda p: float('nan'))
    print("%.2f-%.2f %5d %8.0f %10.0f   %+6.2f %+6.2f %+6.2f" % (k * 0.25, k * 0.25 + 0.25, n, 100.0 * to / n, 100.0 * td / n, q(0.1), q(0.5), q(0.9)))
