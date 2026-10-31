#!/usr/bin/env python3
"""Timeline of the replayed #34942 state (C 150 records) with flown and replayed
XKF1 VD and PD, the baro and range finder, between two times.
usage: timeline.py <Replay output BIN> <from s> <to s> [every Nth record]
"""
import bisect
import sys
from pymavlink import mavutil

path, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
every = int(sys.argv[4]) if len(sys.argv) > 4 else 1
rec, fl, rp, baro, rng, imu = [], [], [], [], [], []
m = mavutil.mavlink_connection(path, robust_parsing=True)
while True:
    msg = m.recv_match(type=['XKFM', 'XKF1', 'BARO', 'RFND', 'IMU'])
    if msg is None:
        break
    t = msg.TimeUS * 1e-6
    if t < t0 - 1 or t > t1:
        continue
    typ = msg.get_type()
    if typ == 'XKFM' and msg.C == 150:
        rec.append((t, msg.OGNM, msg.GLR, msg.ALR, msg.GDR, msg.ADR))
    elif typ == 'XKF1' and msg.C == 0:
        fl.append((t, msg.VD, msg.PD))
    elif typ == 'XKF1' and msg.C == 100:
        rp.append((t, msg.VD, msg.PD))
    elif typ == 'BARO' and msg.I == 0:
        baro.append((t, msg.Alt))
    elif typ == 'RFND':
        rng.append((t, msg.Dist))
    elif typ == 'IMU' and msg.I == 0:
        imu.append((t, (msg.AccX ** 2 + msg.AccY ** 2 + msg.AccZ ** 2) ** 0.5))


def at(s, t):
    i = bisect.bisect_right([r[0] for r in s], t) - 1
    return s[i] if i >= 0 else None


print("%8s %3s %3s %3s %3s %3s %7s %7s %7s %7s %7s %7s %6s %6s %5s" % (
    "t", "gnd", "stl", "chk", "fus", "err", "filt", "vdotf", "rVD", "fVD", "rPD", "fPD", "baro", "rng", "|a|"))
for k, r in enumerate(x for x in rec if t0 <= x[0] <= t1):
    if k % every:
        continue
    t, f = r[0], r[1]
    a, b, br, rf, im = at(fl, t), at(rp, t), at(baro, t), at(rng, t), at(imu, t)
    print("%8.2f %3d %3d %3d %3d %3d %7.2f %7.2f %7.2f %7.2f %7.2f %7.2f %6.2f %6.2f %5.1f" % (
        t, (f >> 3) & 1, (f >> 4) & 1, (f >> 5) & 1, (f >> 2) & 1, (f >> 7) & 1, r[2], r[3], b[1], a[1], b[2], a[2],
        br[1] if br else 0, rf[1] if rf else 0, im[1] if im else 0))
