#!/usr/bin/env python3
"""Max |replay - flown| of XKF1 VD, PD and yaw per time bin, core 0 vs 100.
usage: diff_bins.py <replay BIN> <from s> <to s> [bin s]
"""
import sys
from pymavlink import mavutil

path, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
bw = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
flown, rep = {}, {}
m = mavutil.mavlink_connection(path, robust_parsing=True)
while True:
    msg = m.recv_match(type=['XKF1'])
    if msg is None:
        break
    ts = msg.TimeUS * 1e-6
    if ts < t0 or ts > t1:
        continue
    if msg.C == 0:
        flown[msg.TimeUS] = msg
    elif msg.C == 100:
        rep[msg.TimeUS] = msg
bins = {}
for t in sorted(set(flown) & set(rep)):
    a, b = flown[t], rep[t]
    k = int((t * 1e-6 - t0) / bw)
    dy = abs(a.Yaw - b.Yaw)
    dy = min(dy, 360 - dy)
    cur = bins.get(k, (0, 0, 0))
    bins[k] = (max(cur[0], abs(a.VD - b.VD)), max(cur[1], abs(a.PD - b.PD)), max(cur[2], dy))
for k in sorted(bins):
    print("%8.2f  VD %.2e  PD %.2e  Yaw %.2e" % (t0 + k * bw, *bins[k]))
