#!/usr/bin/env python3
"""lowhover.py LOG: in AltHold (2) or VALT (29) while flying, the true height from a downward range
finder: how long at each height, how long at centre stick below 0.6 m, and the floor contacts at
centre stick (range under 0.10 m for 0.5 s or more after being above 0.25 m), with EKF minus range"""
import os
import sys
from pymavlink import mavutil

m = mavutil.mavlink_connection(sys.argv[1])
mode = None
c3 = 1500
tho = 0.0
alt = None
armed = True  # many of these logs start at arming
rf = None
rf_scale = None
bins = [0.0] * 6  # <0.25, 0.25-0.5, 0.5-1, 1-2, 2-4, >4 seconds
edges = (0.25, 0.5, 1.0, 2.0, 4.0)
centre_low = 0.0
last_t = None
above = False
floor_t0 = None
contacts = []
err_low = []
while True:
    r = m.recv_match(type=["MODE", "RCIN", "CTUN", "RFND", "ARM"])
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
        tho = r.ThO
        alt = r.Alt
    elif ty == "RFND":
        if getattr(r, "Orient", 25) != 25 or getattr(r, "Instance", 0) != 0:
            continue
        d = r.Dist
        if rf_scale is None and d > 50:
            rf_scale = 0.01  # cm on old logs
        rf = d * (rf_scale or 1.0)
        flying = armed and mode in (2, 29) and tho > 0.05
        if last_t is not None and flying:
            dt = min(t - last_t, 0.5)
            k = sum(1 for e in edges if rf >= e)
            bins[k] += dt
            centre = abs(c3 - 1500) < 60
            if centre and rf < 0.6:
                centre_low += dt
            if rf > 0.25:
                above = True
            if rf < 0.10 and above and centre:
                if floor_t0 is None:
                    floor_t0 = t
            else:
                if floor_t0 is not None and t - floor_t0 >= 0.5:
                    contacts.append((floor_t0, t - floor_t0))
                floor_t0 = None
                if rf >= 0.10:
                    pass
            if rf < 0.6 and alt is not None:
                err_low.append(alt - rf)
            if rf >= 0.25:
                above = True
        last_t = t
tot = sum(bins)
name = os.path.basename(sys.argv[1])
err_low.sort()
q = (lambda p: err_low[int(p * (len(err_low) - 1))]) if err_low else (lambda p: float("nan"))
print("%s: %.0f s in AltHold/VALT; by range <0.25 %.0f s, 0.25-0.5 %.0f, 0.5-1 %.0f, 1-2 %.0f, 2-4 %.0f, >4 %.0f; "
      "centre stick under 0.6 m %.0f s; floor contacts at centre stick %d %s; EKF-range under 0.6 m p10/50/90 %+.2f/%+.2f/%+.2f" % (
          name, tot, *bins, centre_low, len(contacts), ["%.0f+%.1fs" % c for c in contacts[:6]], q(0.1), q(0.5), q(0.9)))
