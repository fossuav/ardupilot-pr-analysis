#!/usr/bin/env python3
"""Compare a Replay output's replayed EKF3 core (C 100 + n) with the flown one
(C n) in the same log: XKF1 VD, PD, VN, VE, Roll, Pitch, Yaw sample by sample
on matching TimeUS. Prints the first time each field differs by more than its
tolerance, and the max difference in each window between the given times.
usage: cmp_flown.py <replay BIN> [core] [window edges s ...]
"""
import sys
from pymavlink import mavutil

path = sys.argv[1]
core = int(sys.argv[2]) if len(sys.argv) > 2 else 0
edges = [float(x) for x in sys.argv[3:]]
fields = {'VD': 0.01, 'PD': 0.01, 'VN': 0.01, 'VE': 0.01, 'Roll': 0.05, 'Pitch': 0.05, 'Yaw': 0.1}
flown, rep = {}, {}
m = mavutil.mavlink_connection(path, robust_parsing=True)
while True:
    msg = m.recv_match(type=['XKF1'])
    if msg is None:
        break
    if msg.C == core:
        flown[msg.TimeUS] = msg
    elif msg.C == core + 100:
        rep[msg.TimeUS] = msg
common = sorted(set(flown) & set(rep))
print("flown %d, replayed %d, matched %d samples" % (len(flown), len(rep), len(common)))
first = {}
win = {}
for t in common:
    a, b = flown[t], rep[t]
    ts = t * 1e-6
    w = sum(1 for e in edges if ts >= e)
    for f, tol in fields.items():
        d = abs(getattr(a, f) - getattr(b, f))
        if f == 'Yaw':
            d = min(d, 360 - d)
        if d > tol and f not in first:
            first[f] = (ts, getattr(a, f), getattr(b, f))
        key = (w, f)
        win[key] = max(win.get(key, 0.0), d)
for f in fields:
    if f in first:
        print("  %-5s first differs at %.3f s (flown %.4f, replay %.4f)" % (f, first[f][0], first[f][1], first[f][2]))
    else:
        print("  %-5s never differs beyond %.2f" % (f, fields[f]))
bounds = [0.0] + edges + [float('inf')]
for w in range(len(bounds) - 1):
    print("  window %.2f-%.2f s: " % (bounds[w], bounds[w + 1]) +
          ", ".join("%s %.3g" % (f, win.get((w, f), 0.0)) for f in fields))
