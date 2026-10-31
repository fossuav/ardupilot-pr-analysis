#!/usr/bin/env python3
"""EKF vertical velocity while disarmed, per log and core (XKF1.VD, C 0 and 1).

For each log: the disarmed time, and per core the share of disarmed samples
with |VD| over 0.5 m/s and the range of VD, to compare a build with #34942
against one without on the same test.
usage: vd_disarmed.py <BIN>...
"""
import sys
from pymavlink import mavutil

for path in sys.argv[1:]:
    m = mavutil.mavlink_connection(path, robust_parsing=True)
    armed = False
    seen_arm = False
    per = {}
    while True:
        msg = m.recv_match(type=['ARM', 'XKF1'])
        if msg is None:
            break
        if msg.get_type() == 'ARM':
            armed = msg.ArmState != 0
            seen_arm = seen_arm or armed
            continue
        if armed or msg.C > 1:
            continue
        d = per.setdefault(msg.C, [0, 0, 1e9, -1e9])
        d[0] += 1
        if abs(msg.VD) > 0.5:
            d[1] += 1
        d[2] = min(d[2], msg.VD)
        d[3] = max(d[3], msg.VD)
    if not per:
        continue
    print("%s (armed in log: %s)" % (path.split('/')[-1], seen_arm))
    for c, d in sorted(per.items()):
        print("  core %d: %d disarmed samples, %d with |VD| > 0.5 m/s, VD %.2f to %.2f" % (c, d[0], d[1], d[2], d[3]))
