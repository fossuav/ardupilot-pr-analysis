#!/usr/bin/env python3
"""Each change of XKFM.OGNM (core C, default 0) up to T seconds, with the core's
XKF1 yaw at the time and the EKF init / yaw alignment messages.
usage: still_onset.py <BIN> [T] [C]
"""
import sys
from pymavlink import mavutil

path = sys.argv[1]
tmax = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
core = int(sys.argv[3]) if len(sys.argv) > 3 else 0
m = mavutil.mavlink_connection(path, robust_parsing=True)
yaw = None
prev = None
while True:
    msg = m.recv_match(type=['XKFM', 'XKF1', 'MSG'])
    if msg is None:
        break
    t = msg.TimeUS * 1e-6
    if t > tmax:
        break
    typ = msg.get_type()
    if typ == 'MSG':
        if 'EKF3 IMU%d' % core in msg.Message:
            print("%7.2f MSG %s" % (t, msg.Message))
        continue
    if msg.C != core:
        continue
    if typ == 'XKF1':
        yaw = msg.Yaw
        continue
    if msg.OGNM != prev:
        print("%7.2f still %d (yaw %s)" % (t, msg.OGNM, yaw))
        prev = msg.OGNM
