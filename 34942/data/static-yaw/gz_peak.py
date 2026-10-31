#!/usr/bin/env python3
"""Largest |XKF1.GZ| (EKF Z gyro bias, deg/s) per core in each log, with its time,
and whether a core logged XKFM with OGNM 0 at any point before the first source
set change, i.e. whether the static yaw reference was ever taken at boot.
usage: gz_peak.py <BIN>...
"""
import sys
from pymavlink import mavutil

for path in sys.argv[1:]:
    m = mavutil.mavlink_connection(path, robust_parsing=True)
    peak = {}
    moved = {}
    while True:
        msg = m.recv_match(type=['XKF1', 'XKFM'])
        if msg is None:
            break
        if msg.C > 1:
            continue
        if msg.get_type() == 'XKFM':
            if msg.OGNM == 0:
                moved.setdefault(msg.C, msg.TimeUS * 1e-6)
            continue
        if abs(msg.GZ) > abs(peak.get(msg.C, (0, 0))[0]):
            peak[msg.C] = (msg.GZ, msg.TimeUS * 1e-6)
    if not peak:
        continue
    print(path.split('/')[-1] + ": " + "; ".join(
        "core %d peak GZ %.2f deg/s at %.1f s, first not-still %s" % (
            c, g, t, ("%.2f s" % moved[c]) if c in moved else "never")
        for c, (g, t) in sorted(peak.items())))
