#!/usr/bin/env python3
"""Compare two Replay outputs of one log, replayed core 0 (XKF1 C 100), against
each other and against the flown core 0 (XKF1 C 0 in the source log).

Prints when the two replays first differ, the largest yaw (deg, wrapped), GZ
(deg/s) and VD (m/s) difference between them, and for each replay the rms yaw
and VD error against the flown EKF over the window where it follows the flight
(before T, default the whole log).
usage: cmp_replays.py <source log> <replay A BIN> <replay B BIN> [T]
"""
import math
import sys
from pymavlink import mavutil


def series(path, core):
    m = mavutil.mavlink_connection(path, robust_parsing=True)
    out = {}
    while True:
        msg = m.recv_match(type=['XKF1'])
        if msg is None:
            break
        if msg.C == core:
            out[msg.TimeUS] = (msg.Yaw, msg.GZ, msg.VD)
    return out


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


src, ra, rb = sys.argv[1], sys.argv[2], sys.argv[3]
tmax = float(sys.argv[4]) * 1e6 if len(sys.argv) > 4 else 1e18
flown = series(src, 0)
a = series(ra, 100)
b = series(rb, 100)
common = sorted(set(a) & set(b))
first = None
dy = dg = dv = 0.0
for t in common:
    ya, ga, va = a[t]
    yb, gb, vb = b[t]
    d = (abs(wrap(ya - yb)), abs(ga - gb), abs(va - vb))
    if first is None and max(d) > 1e-4:
        first = t
    dy, dg, dv = max(dy, d[0]), max(dg, d[1]), max(dv, d[2])
print("samples %d; first difference %s; max |dyaw| %.2f deg, |dGZ| %.3f deg/s, |dVD| %.3f m/s" % (
    len(common), ("%.2f s" % (first * 1e-6)) if first else "none", dy, dg, dv))
for name, r in (("A", a), ("B", b)):
    ts = [t for t in sorted(set(r) & set(flown)) if t < tmax]
    if not ts:
        continue
    ey = math.sqrt(sum(wrap(r[t][0] - flown[t][0]) ** 2 for t in ts) / len(ts))
    ev = math.sqrt(sum((r[t][2] - flown[t][2]) ** 2 for t in ts) / len(ts))
    gz = max(abs(r[t][1]) for t in ts)
    print("  %s against flown (%d samples%s): rms yaw %.2f deg, rms VD %.3f m/s, max |GZ| %.2f deg/s" % (
        name, len(ts), (" to %.1f s" % (tmax * 1e-6)) if tmax < 1e17 else "", ey, ev, gz))
