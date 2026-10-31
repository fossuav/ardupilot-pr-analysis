#!/usr/bin/env python3
"""MAV_CMD_SET_EKF_SOURCE_SET logs: per core, a timeline of the stillness flag
(XKFM.OGNM and its four ratios), the aiding mode and yaw (XKF4.SS bits, XKF1.Yaw),
and the source set changes (EV or MSG), every SECONDS.
usage: srcset_timeline.py <BIN> [seconds]
"""
import sys
from pymavlink import mavutil

path = sys.argv[1]
step = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
m = mavutil.mavlink_connection(path, robust_parsing=True)
last = {}
xkf1 = {}
xkf4 = {}
while True:
    msg = m.recv_match(type=['XKFM', 'XKF1', 'XKF4', 'MSG'])
    if msg is None:
        break
    t = msg.TimeUS * 1e-6
    typ = msg.get_type()
    if typ == 'MSG':
        print("%8.2f MSG %s" % (t, msg.Message))
        continue
    if msg.C > 1:
        continue
    if typ == 'XKF1':
        xkf1[msg.C] = msg
        continue
    if typ == 'XKF4':
        xkf4[msg.C] = msg
        continue
    if t - last.get(msg.C, -1e9) < step:
        continue
    last[msg.C] = t
    k1 = xkf1.get(msg.C)
    k4 = xkf4.get(msg.C)
    print("%8.2f C%d still %d gyro %.2f accel %.2f gdiff %.2f adiff %.2f | yaw %s SS %s SM %s" % (
        t, msg.C, msg.OGNM, msg.GLR, msg.ALR, msg.GDR, msg.ADR,
        ("%.1f" % k1.Yaw) if k1 else "-", (k4.SS if k4 else "-"), ("%.2f" % k4.SM) if k4 else "-"))
