#!/usr/bin/env python3
'''Compare the replayed core 0 (C=100) XKF1 velocity and position between
Replay logs produced by different builds from the same flight log.

usage: replay_compare.py head.BIN revert.BIN fix.BIN
'''
import math
import sys
from pymavlink import mavutil


def load(f, core=100):
    m = mavutil.mavlink_connection(f)
    x = {}
    aid = []
    prev = None
    while True:
        r = m.recv_match(type=['XKF1', 'XKF4'])
        if r is None:
            break
        if r.C != core:
            continue
        if r.get_type() == 'XKF1':
            x[r.TimeUS] = (r.VN, r.VE, r.PN, r.PE)
        else:
            if prev is not None and r.AID != prev:
                aid.append((round(r.TimeUS*1e-6, 2), prev, r.AID))
            prev = r.AID
    return x, aid


def cmp(xa, xb, label):
    dv = dp = 0
    first = at = None
    for k in sorted(set(xa) & set(xb)):
        va, vb = xa[k], xb[k]
        d = math.hypot(va[0]-vb[0], va[1]-vb[1])
        e = math.hypot(va[2]-vb[2], va[3]-vb[3])
        if (d > 0 or e > 0) and first is None:
            first = round(k*1e-6, 2)
        if d > dv:
            dv, at = d, round(k*1e-6, 2)
        dp = max(dp, e)
    print('%s: max |dV| %.3f m/s at %s, max |dP| %.2f m, first difference %s' % (label, dv, at, dp, first))


head, revert, fix = (load(f) for f in sys.argv[1:4])
for name, r in (('head', head), ('revert', revert), ('fix', fix)):
    print(name, 'AID', r[1])
cmp(head[0], revert[0], 'head vs revert')
cmp(fix[0], revert[0], 'fix vs revert')
