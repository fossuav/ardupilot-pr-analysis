#!/usr/bin/env python3
"""holds.py LOG [DZ]: VALT centre-stick holds (stick within DZ of 1500 for 2 s or more, armed, starting
with the range finder at 0.2 m or more): start, lowest and end range, how many reach the floor (range
under 0.10 m), how fast, how long they then stay on it, the ground effect flags, and the change in EKF
height minus range over the hold (the estimate's drift, which a centre-stick hold turns into a sink)"""
import os
import sys
from pymavlink import mavutil

dz = float(sys.argv[2]) if len(sys.argv) > 2 else 50
m = mavutil.mavlink_connection(sys.argv[1])
mode = None
armed = True
c3 = 1500
alt = None
ge = 0
cur = None
holds = []


def close(h, t):
    if h is not None and t - h["t0"] >= 2.0 and h["rf0"] is not None and h["rf0"] >= 0.2:
        h["t1"] = t
        holds.append(h)


while True:
    r = m.recv_match(type=["MODE", "ARM", "RCIN", "CTUN", "RFND", "XKF4"])
    if r is None:
        break
    ty = r.get_type()
    t = r.TimeUS * 1e-6
    if ty == "MODE":
        mode = r.ModeNum
    elif ty == "ARM":
        armed = r.ArmState == 1
    elif ty == "RCIN":
        c3 = r.C3
    elif ty == "CTUN":
        alt = r.Alt
    elif ty == "XKF4" and r.C == 0:
        ge = 1 if (r.SS & (2048 | 4096)) else 0
    elif ty == "RFND" and r.Orient == 25 and r.Instance == 0:
        rf = r.Dist
        holding = armed and mode == 29 and abs(c3 - 1500) <= dz
        if not holding:
            close(cur, t)
            cur = None
            continue
        if cur is None:
            cur = dict(t0=t, rf0=rf, e0=(alt - rf) if alt is not None else None, rfs=[], ge=[0, 0],
                       floor_t=None, floor_dur=0.0, last=t)
        cur["rfs"].append(rf)
        cur["ge"][0] += 1
        cur["ge"][1] += ge
        if rf < 0.10:
            if cur["floor_t"] is None:
                cur["floor_t"] = t
            cur["floor_dur"] += t - cur["last"]
        cur["rf1"] = rf
        cur["e1"] = (alt - rf) if alt is not None else None
        cur["last"] = t
close(cur, cur["last"] if cur else 0)

name = os.path.basename(sys.argv[1])
tot = sum(h["t1"] - h["t0"] for h in holds)
fl = [h for h in holds if h["floor_t"] is not None]
print("%s: %d centre-stick holds, %.0f s; %d reach the floor; on the floor %.0f s of %.0f s (%.0f%%)" % (
    name, len(holds), tot, len(fl), sum(h["floor_dur"] for h in holds), tot,
    100.0 * sum(h["floor_dur"] for h in holds) / max(tot, 1e-6)))
print("   t0     dur  rf0   rfmin rf1   floor@  onfloor  GE%   d(EKF-rf)")
for h in holds:
    de = (h["e1"] - h["e0"]) if (h["e0"] is not None and h["e1"] is not None) else float("nan")
    fa = ("%6.1f" % (h["floor_t"] - h["t0"])) if h["floor_t"] is not None else "     -"
    print("%6.1f %6.1f %5.2f %5.2f %5.2f %s %7.1f %5.0f %+8.2f" % (
        h["t0"], h["t1"] - h["t0"], h["rf0"], min(h["rfs"]), h["rf1"], fa, h["floor_dur"],
        100.0 * h["ge"][1] / max(1, h["ge"][0]), de))
