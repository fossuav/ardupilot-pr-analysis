#!/usr/bin/env python3
"""While #34942's ground height test fires in a SITL log (instrument_stale.py
records, C 50+), why did no measured vertical velocity agree?

Prints, per core, how many samples had the height error set, and for those:
how many had a velD fused within 2 s, how many had |innovVelPos[2]| >= 0.5,
and how many had both of those fine (so velTestRatio >= 1 decided it), with
the first and last such time and the VD range.
usage: why_disagree.py <BIN>...
"""
import sys
from pymavlink import mavutil

for path in sys.argv[1:]:
    m = mavutil.mavlink_connection(path, robust_parsing=True)
    per = {}
    while True:
        msg = m.recv_match(type=['XKFM'])
        if msg is None:
            break
        if msg.C < 50 or msg.C > 60:
            continue
        f = msg.OGNM
        if not (f >> 7) & 1:
            continue
        d = per.setdefault(msg.C - 50, {'n': 0, 'stale': 0, 'innov': 0, 'ratio': 0, 't': [], 'vd': [], 'agl': 0})
        d['n'] += 1
        d['t'].append(msg.TimeUS * 1e-6)
        d['vd'].append(msg.GDR)
        if msg.GLR >= 2.0:
            d['stale'] += 1
        elif abs(msg.ALR) >= 0.5:
            d['innov'] += 1
        else:
            d['ratio'] += 1
    if not per:
        continue
    print(path.split('/')[-1])
    for c, d in sorted(per.items()):
        print("  core %d: %d samples with the height error, %.1f-%.1f s; no velD fused for 2 s: %d, |innov| >= 0.5: %d, "
              "fused and inside 0.5 (velTestRatio >= 1): %d; VD %.2f to %.2f" % (
                  c, d['n'], d['t'][0], d['t'][-1], d['stale'], d['innov'], d['ratio'], min(d['vd']), max(d['vd'])))
