#!/usr/bin/env python3
"""timeline.py LOG: per 1 s while armed, true height above the arming point (SIM), EKF height
and target (CTUN Alt/DAlt), baro, range finder, throttle stick and out, and the EKF ground
effect flags (XKF4.SS takeoff 2048, touchdown 4096) on core 0"""
import sys
from pymavlink import mavutil

m = mavutil.mavlink_connection(sys.argv[1])
armed = False
g = None
last = {}
rows = {}
while True:
    r = m.recv_match(type=["ARM", "SIM", "CTUN", "BARO", "RFND", "RCIN", "XKF4", "PARM"])
    if r is None:
        break
    ty = r.get_type()
    if ty == "PARM":
        if r.Name == "SCR_USER1":
            last["E"] = r.Value
        continue
    t = r.TimeUS * 1e-6
    if ty == "ARM":
        armed = r.ArmState == 1
        continue
    if ty == "SIM":
        if not armed:
            g = r.Alt
        if g is not None:
            last["h"] = r.Alt - g
    elif ty == "CTUN":
        last["alt"] = r.Alt
        last["dalt"] = r.DAlt
        last["tho"] = r.ThO
    elif ty == "BARO" and r.I == 0:
        last["baro"] = r.Alt
    elif ty == "RFND":
        last["rf"] = r.Dist
    elif ty == "RCIN":
        last["c3"] = r.C3
    elif ty == "XKF4" and r.C == 0:
        last["to"] = 1 if r.SS & 2048 else 0
        last["td"] = 1 if r.SS & 4096 else 0
    if armed:
        rows[int(t)] = dict(last)
print("SCR_USER1 (baro error at the floor):", last.get("E"))
print("   t  trueH  EKFalt  DAlt   baro    RF    C3   ThO  TO TD")
for k in sorted(rows):
    v = rows[k]
    print("%4d %6.2f %7.2f %5.2f %6.2f %5.2f %5d %5.2f %3d %2d" % (
        k, v.get("h", float("nan")), v.get("alt", float("nan")), v.get("dalt", float("nan")),
        v.get("baro", float("nan")), v.get("rf", float("nan")), v.get("c3", 0), v.get("tho", float("nan")),
        v.get("to", -1), v.get("td", -1)))
