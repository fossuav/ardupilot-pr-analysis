#!/usr/bin/env python3
"""Height-error verdict and replayed VD at every arm (first arms included), for
two instrumented Replays of the same log (instrument_stale.py records, C 150).
Prints one line per arm whose verdict or VD differs, and a count.
usage: arm_verdicts.py <source log> <replay A BIN> <replay B BIN>
"""
import bisect
import sys
from pymavlink import mavutil


def records(path):
    m = mavutil.mavlink_connection(path, robust_parsing=True)
    out = []
    while True:
        msg = m.recv_match(type=['XKFM'])
        if msg is None:
            break
        if msg.C == 150:
            out.append((msg.TimeUS * 1e-6, (msg.OGNM >> 7) & 1, msg.GDR))
    return out


def at(rec, t):
    i = bisect.bisect_right([r[0] for r in rec], t) - 1
    return rec[i] if i >= 0 else None


m = mavutil.mavlink_connection(sys.argv[1], robust_parsing=True)
arms = []
while True:
    msg = m.recv_match(type=['ARM'])
    if msg is None:
        break
    if msg.ArmState != 0:
        arms.append(msg.TimeUS * 1e-6)
a, b = records(sys.argv[2]), records(sys.argv[3])
na = nb = 0
for t in arms:
    ra, rb = at(a, t - 0.05), at(b, t - 0.05)
    if ra is None or rb is None:
        continue
    na += ra[1]
    nb += rb[1]
    if ra[1] != rb[1] or abs(ra[2] - rb[2]) > 0.05:
        print("  arm %.2f: without fix %s VD %.2f, with fix %s VD %.2f" % (
            t, "REFUSED" if ra[1] else "allowed", ra[2], "REFUSED" if rb[1] else "allowed", rb[2]))
print("  %d arms; refused without fix %d, with fix %d" % (len(arms), na, nb))
