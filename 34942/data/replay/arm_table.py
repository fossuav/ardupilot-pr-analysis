'''Per arm: flown EKF VD, and the replayed series verdict (height error, settling) and VD.
usage: arm_table.py <loglist> <replay base dir>'''
import bisect
import os
import sys
from pymavlink import mavutil


def at(lst, t):
    ts = [x[0] for x in lst]
    i = bisect.bisect_right(ts, t) - 1
    return lst[max(i, 0)] if lst else None


rows = []
for src in open(sys.argv[1]).read().split():
    name = os.path.basename(src)[:-4]
    m = mavutil.mavlink_connection(src, robust_parsing=True)
    arms, fvd = [], []
    while True:
        msg = m.recv_match(type=['ARM', 'XKF1'])
        if msg is None:
            break
        t = msg.TimeUS * 1e-6
        if msg.get_type() == 'ARM':
            arms.append((t, msg.ArmState))
        elif msg.C == 0:
            fvd.append((t, msg.VD))
    m = mavutil.mavlink_connection(os.path.join(sys.argv[2], name, 'logs', '00000001.BIN'), robust_parsing=True)
    v, rvd = [], []
    while True:
        msg = m.recv_match(type=['XKFM', 'XKF1'])
        if msg is None:
            break
        t = msg.TimeUS * 1e-6
        if msg.get_type() == 'XKFM' and msg.C == 150:
            v.append((t, (msg.OGNM >> 1) & 1, 0))
        elif msg.get_type() == 'XKF1' and msg.C == 100:
            rvd.append((t, msg.VD))
    last_dis = None
    for t, s in arms:
        if s == 0:
            last_dis = t
            continue
        r = at(v, t - 0.05)
        rows.append((name, t, t - last_dis if last_dis else None, at(fvd, t - 0.05)[1], at(rvd, t - 0.05)[1], r[1], r[2]))
n = len(rows)
stopped = [r for r in rows if r[5] or r[6]]
big = [r for r in rows if abs(r[3]) >= 1.0]
print("arms %d, stopped %d (height error %d, settling %d, both %d)" % (
    n, len(stopped), sum(1 for r in rows if r[5]), sum(1 for r in rows if r[6]), sum(1 for r in rows if r[5] and r[6])))
print("arms that went up with flown |VD| >= 1:")
for r in big:
    print("  %-24s %7.2f (%s) flown VD %5.2f -> replay VD %5.2f %s%s" % (
        r[0], r[1], ('%.1f s after disarm' % r[2]) if r[2] else 'first arm', r[3], r[4],
        'HGT-ERROR ' if r[5] else '', 'SETTLING' if r[6] else ''))
print("stopped arms with flown |VD| < 1:")
for r in stopped:
    if abs(r[3]) < 1.0:
        print("  %-24s %7.2f (%s) flown VD %5.2f replay VD %5.2f %s%s" % (
            r[0], r[1], ('%.1f s after disarm' % r[2]) if r[2] else 'first arm', r[3], r[4],
            'HGT-ERROR ' if r[5] else '', 'SETTLING' if r[6] else ''))
print("max |replay VD| at arms that are not stopped: %.2f" % max(abs(r[4]) for r in rows if not (r[5] or r[6])))
