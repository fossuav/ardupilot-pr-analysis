#!/usr/bin/env python3
"""Per arm of the flight: the replayed #34942 verdict (instrument_latest.py
records, C 150) just before the arm, the replayed and flown XKF1 VD, and the
time since the previous disarm.
usage: arm_score.py <Replay output BIN> [exact windows as a-b,c-d in s]
"""
import bisect
import sys
from pymavlink import mavutil

path = sys.argv[1]
exact = []
if len(sys.argv) > 2:
    for w in sys.argv[2].split(','):
        a, b = w.split('-')
        exact.append((float(a), float(b)))
rec, flown, rep, arms = [], [], [], []
m = mavutil.mavlink_connection(path, robust_parsing=True)
while True:
    msg = m.recv_match(type=['XKFM', 'XKF1', 'ARM'])
    if msg is None:
        break
    t = msg.TimeUS * 1e-6
    typ = msg.get_type()
    if typ == 'XKFM' and msg.C == 150:
        rec.append((t, msg.OGNM, msg.GLR, msg.ALR, msg.GDR, msg.ADR))
    elif typ == 'XKF1' and msg.C == 0:
        flown.append((t, msg.VD))
    elif typ == 'XKF1' and msg.C == 100:
        rep.append((t, msg.VD))
    elif typ == 'ARM':
        arms.append((t, msg.ArmState))


def at(series, t):
    i = bisect.bisect_right([r[0] for r in series], t) - 1
    return series[i] if i >= 0 else None


print("%8s %7s %-8s %7s %7s %7s %5s %5s %6s %s" % (
    "arm s", "disarm", "verdict", "filt m", "rep VD", "fl VD", "still", "chkd", "resets", "replay"))
last_disarm = None
refused = 0
n = 0
for t, state in arms:
    if state == 0:
        last_disarm = t
        continue
    r = at(rec, t - 0.01)
    if r is None:
        continue
    n += 1
    flags = r[1]
    hgt_err = (flags >> 7) & 1
    refused += hgt_err
    still = (flags >> 4) & 1
    checked = (flags >> 5) & 1
    resets = int(r[5]) % 1000
    fl = at(flown, t)
    rp = at(rep, t)
    since = ("%6.2f" % (t - last_disarm)) if last_disarm is not None else "   -  "
    ex = "exact" if any(a <= t <= b for a, b in exact) else ("diverged" if exact else "")
    print("%8.2f %7s %-8s %7.2f %7.2f %7.2f %5d %5d %6d %s" % (
        t, since, "REFUSED" if hgt_err else "allowed", r[2], rp[1] if rp else float('nan'),
        fl[1] if fl else float('nan'), still, checked, resets, ex))
print("%d arms, %d refused on the height error" % (n, refused))
