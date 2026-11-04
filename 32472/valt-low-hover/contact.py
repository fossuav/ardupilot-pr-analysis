#!/usr/bin/env python3
"""contact.py LOG T0 T1: 10 Hz rows of range finder, baro (from the log start), EKF height
and target (CTUN Alt/DAlt), climb rate and its demand, throttle stick and out, and the core 0
ground effect flags"""
import sys
from pymavlink import mavutil

m = mavutil.mavlink_connection(sys.argv[1])
t0, t1 = float(sys.argv[2]), float(sys.argv[3])
last = {}
b0 = None
nxt = t0
print("    t     RF   baro  EKFalt  DAlt    CRt  DCRt    C3   ThO TO TD")
while True:
    r = m.recv_match(type=["RFND", "BARO", "CTUN", "RCIN", "XKF4"])
    if r is None:
        break
    ty = r.get_type()
    t = r.TimeUS * 1e-6
    if ty == "BARO" and r.I == 0:
        if b0 is None:
            b0 = r.Alt
        last["baro"] = r.Alt - b0
    elif ty == "RFND":
        last["rf"] = r.Dist
    elif ty == "CTUN":
        last.update(alt=r.Alt, dalt=r.DAlt, crt=r.CRt * 0.01 if abs(r.CRt) > 20 else r.CRt, dcrt=r.DCRt, tho=r.ThO)
    elif ty == "RCIN":
        last["c3"] = r.C3
    elif ty == "XKF4" and r.C == 0:
        last["to"] = 1 if r.SS & 2048 else 0
        last["td"] = 1 if r.SS & 4096 else 0
    if t >= nxt and t <= t1:
        nxt += 0.1
        g = lambda k: last.get(k, float('nan'))
        print("%6.1f %6.2f %6.2f %7.2f %5.2f %6.2f %5.2f %5d %5.2f %2d %2d" % (
            t, g("rf"), g("baro"), g("alt"), g("dalt"), g("crt"), g("dcrt"), last.get("c3", 0), g("tho"),
            last.get("to", -1), last.get("td", -1)))
    if t > t1:
        break
