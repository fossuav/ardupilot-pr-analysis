#!/usr/bin/env python3
"""washscan.py LOG: in AltHold (2) or VALT (29) while flying, baro height minus range finder height
(both from the last arming, or the log start for logs that begin armed), binned by range"""
import os
import sys
from pymavlink import mavutil

m = mavutil.mavlink_connection(sys.argv[1])
mode = None
armed = True
tho = 0.0
baro = None
b0 = None
rf0 = None
rf = None
scale = None
bins = {}
while True:
    r = m.recv_match(type=["MODE", "ARM", "CTUN", "BARO", "RFND"])
    if r is None:
        break
    ty = r.get_type()
    if ty == "MODE":
        mode = r.ModeNum
    elif ty == "ARM":
        armed = r.ArmState == 1
        if armed:
            b0 = baro
            rf0 = rf
    elif ty == "CTUN":
        tho = r.ThO
    elif ty == "BARO" and r.I == 0:
        baro = r.Alt
        if b0 is None:
            b0 = baro
    elif ty == "RFND" and getattr(r, "Orient", 25) == 25 and getattr(r, "Instance", 0) == 0:
        if scale is None and r.Dist > 50:
            scale = 0.01
        rf = r.Dist * (scale or 1.0)
        if rf0 is None:
            rf0 = rf
        if armed and mode in (2, 29) and tho > 0.05 and baro is not None and b0 is not None:
            k = min(int(rf / 0.25), 6)
            bins.setdefault(k, []).append((baro - b0) - (rf - rf0))
print(os.path.basename(sys.argv[1]))
for k in sorted(bins):
    e = sorted(bins[k])
    q = lambda p: e[int(p * (len(e) - 1))]
    print("  range %.2f-%s m: n %5d  baro-range p10 %+6.2f median %+6.2f p90 %+6.2f" % (
        k * 0.25, ("%.2f" % (k * 0.25 + 0.25)) if k < 6 else "up", len(e), q(0.1), q(0.5), q(0.9)))
