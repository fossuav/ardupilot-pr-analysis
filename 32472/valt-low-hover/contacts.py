#!/usr/bin/env python3
"""contacts.py LOG: floor contacts in VALT after first liftoff (range under 0.10 m for 0.3 s or more),
with the throttle stick over the 2 s before (near centre is within 80 of 1500), how long it stayed
down, the most stick it took to leave, the ground effect flags before contact, and the contact rate
per minute of VALT flight under 0.6 m"""
import os
import sys
from pymavlink import mavutil

m = mavutil.mavlink_connection(sys.argv[1])
mode = None
armed = True
c3 = 1500
ge = 0
lifted = False
hist = []  # (t, c3, ge)
low_t = 0.0
last = None
ep = None
eps = []
disarm_t = None
while True:
    r = m.recv_match(type=["MODE", "ARM", "RCIN", "XKF4", "RFND"])
    if r is None:
        break
    ty = r.get_type()
    t = r.TimeUS * 1e-6
    if ty == "MODE":
        mode = r.ModeNum
    elif ty == "ARM":
        armed = r.ArmState == 1
        if not armed:
            disarm_t = t
    elif ty == "RCIN":
        c3 = r.C3
        hist.append((t, c3, ge))
    elif ty == "XKF4" and r.C == 0:
        ge = 1 if (r.SS & (2048 | 4096)) else 0
    elif ty == "RFND" and r.Orient == 25 and r.Instance == 0:
        rf = r.Dist
        valt = armed and mode == 29
        if valt and rf > 0.3:
            lifted = True
        if valt and lifted and last is not None and rf < 0.6:
            low_t += min(t - last, 0.5)
        last = t
        if valt and lifted and rf < 0.10:
            if ep is None:
                pre = [h for h in hist if t - 2.0 <= h[0] <= t]
                ep = dict(t0=t, pre_c3=sum(h[1] for h in pre) / max(1, len(pre)),
                          pre_ge=sum(h[2] for h in pre) / max(1, len(pre)), maxc3=c3)
            ep["t1"] = t
            ep["maxc3"] = max(ep["maxc3"], c3)
        elif ep is not None:
            ep["end"] = "lift" if (valt and rf >= 0.10) else "mode/disarm"
            if ep["t1"] - ep["t0"] >= 0.3:
                eps.append(ep)
            ep = None
if ep is not None and ep["t1"] - ep["t0"] >= 0.3:
    ep["end"] = "log end"
    eps.append(ep)
name = os.path.basename(sys.argv[1])
near = [e for e in eps if abs(e["pre_c3"] - 1500) <= 80 and e["end"] == "lift"]
print("%s: %.0f s of VALT under 0.6 m; %d floor contacts, %d from near centre stick that it then left "
      "(%.1f per min under 0.6 m); stays %s s" % (
          name, low_t, len(eps), len(near), 60.0 * len(near) / max(low_t, 1e-6),
          sorted(round(e["t1"] - e["t0"], 1) for e in near)))
for e in eps:
    print("   %6.1f  %4.1f s  stick before %4.0f (GE %3.0f%%)  most stick to leave %4d  %s" % (
        e["t0"], e["t1"] - e["t0"], e["pre_c3"], 100 * e["pre_ge"], e["maxc3"], e["end"]))
