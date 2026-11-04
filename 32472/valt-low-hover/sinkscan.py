#!/usr/bin/env python3
"""sinkscan.py LOG: in VALT with the stick near centre (within 80 of 1500) and the range finder between
0.10 and 0.80 m, the true vertical speed from the range finder (over 0.5 s) against the speed the stick
asked for, and the share of that time sinking faster than 0.1 m/s without being asked to"""
import os
import sys
from pymavlink import mavutil

m = mavutil.mavlink_connection(sys.argv[1])
mode = None
armed = True
c3 = 1500
dcrt = 0.0
buf = []
n = sink = 0
vs = []
while True:
    r = m.recv_match(type=["MODE", "ARM", "RCIN", "CTUN", "RFND"])
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
    elif ty == "RFND" and r.Orient == 25 and r.Instance == 0:
        buf.append((t, r.Dist))
        while buf and t - buf[0][0] > 0.5:
            buf.pop(0)
        if len(buf) < 3 or t - buf[0][0] < 0.4:
            continue
        v = (buf[-1][1] - buf[0][1]) / (buf[-1][0] - buf[0][0])
        if armed and mode == 29 and abs(c3 - 1500) <= 80 and 0.10 <= r.Dist <= 0.80 and buf[0][1] >= 0.10:
            n += 1
            vs.append(v)
            # the stick asks for a descent only outside THR_DZ 50
            asked_down = c3 < 1450
            if v < -0.1 and not asked_down:
                sink += 1
vs.sort()
q = (lambda p: vs[int(p * (len(vs) - 1))]) if vs else (lambda p: float("nan"))
print("%s: %d samples near centre stick at 0.10-0.80 m; true vertical speed p10/50/90 %+.2f/%+.2f/%+.2f m/s; "
      "sinking faster than 0.1 m/s unasked %.0f%%" % (os.path.basename(sys.argv[1]), n, q(0.1), q(0.5), q(0.9),
                                                       100.0 * sink / max(1, n)))
