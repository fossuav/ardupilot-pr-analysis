#!/usr/bin/env python3
"""XKF1.GZ (deg/s) and Yaw for core 0 and 1 at the first sample after each time given.
usage: gz_at.py <BIN> t1 [t2 ...]
"""
import sys
from pymavlink import mavutil

path = sys.argv[1]
times = sorted(float(x) for x in sys.argv[2:])
m = mavutil.mavlink_connection(path, robust_parsing=True)
pending = {c: list(times) for c in (0, 1)}
rows = []
while any(pending.values()):
    msg = m.recv_match(type=['XKF1'])
    if msg is None:
        break
    if msg.C not in pending or not pending[msg.C]:
        continue
    t = msg.TimeUS * 1e-6
    while pending[msg.C] and t >= pending[msg.C][0]:
        rows.append((pending[msg.C].pop(0), msg.C, msg.GZ, msg.Yaw))
for want, c, gz, yaw in sorted(rows):
    print("t>=%5.1f core %d GZ %7.2f deg/s yaw %6.1f" % (want, c, gz, yaw))
