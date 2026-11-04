#!/usr/bin/env python3
"""switch.py LOG: each change of core 0's takeoff_expected flag (XKF4.SS 2048) in VALT, with the range
finder, the EKF's height above ground (XKF5.HAGL) and the EKF height (CTUN.Alt) at that moment, then a
summary of which of them sits at TKOFF_GNDEFF_ALT when the flag clears"""
import os
import sys
from pymavlink import mavutil

m = mavutil.mavlink_connection(sys.argv[1])
mode = None
rf = hagl = alt = None
to = None
alt0 = None
rows = []
while True:
    r = m.recv_match(type=["MODE", "RFND", "XKF5", "CTUN", "XKF4"])
    if r is None:
        break
    ty = r.get_type()
    t = r.TimeUS * 1e-6
    if ty == "MODE":
        mode = r.ModeNum
    elif ty == "RFND" and r.Orient == 25 and r.Instance == 0:
        rf = r.Dist
    elif ty == "XKF5" and r.C == 0:
        hagl = r.HAGL
    elif ty == "CTUN":
        alt = r.Alt
        if alt0 is None:
            alt0 = alt
    elif ty == "XKF4" and r.C == 0:
        f = 1 if r.SS & 2048 else 0
        if to is not None and f != to and mode == 29:
            rows.append((t, f, rf, hagl, alt - alt0 if alt is not None else float("nan")))
        to = f
print(os.path.basename(sys.argv[1]))
print("    t   flag  range  HAGL  EKF-above-start")
for t, f, a, b, c in rows[:40]:
    print("%6.1f   %s  %5.2f  %5.2f  %+6.2f" % (t, "set  " if f else "clear", a, b, c))
cl = [r for r in rows if r[1] == 0]
if cl:
    med = lambda xs: sorted(xs)[len(xs) // 2]
    print("at %d clears: median range %.2f, HAGL %.2f, EKF above start %+.2f" % (
        len(cl), med([r[2] for r in cl]), med([r[3] for r in cl]), med([r[4] for r in cl])))
