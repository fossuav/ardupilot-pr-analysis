#!/usr/bin/env python3
"""For each stretch where the tilt check withholds flow from an EKF3 core,
report how the flow lane recovers when the vehicle levels.

A stretch is a run of XKF1 records for the flow core with cos(roll)cos(pitch)
at or below 0.71 (EKF3's DCM33FlowMin). A flow update is an XKF5 record for
that core whose FIX/FIY/NI differ from the previous record (FuseOptFlow ran);
NI < 100 means both axes passed the innovation gate.

Velocity errors are the core against the reference core (a GPS lane).
XKF5 is logged at the flow rate (10 Hz on SFD-O4), so times are to 0.1 s.

usage: MAVLINK_DIR=<ardupilot>/modules/mavlink tilt_recovery.py LOG [--core 1] [--ref 0] [--min 0.5]
"""
import argparse
import math
import sys
import os
if os.environ.get('MAVLINK_DIR'):
    sys.path.insert(0, os.environ['MAVLINK_DIR'])  # an ArduPilot checkout's modules/mavlink
from pymavlink import DFReader

ap = argparse.ArgumentParser()
ap.add_argument('log')
ap.add_argument('--core', type=int, default=1)
ap.add_argument('--ref', type=int, default=0)
ap.add_argument('--min', type=float, default=0.5, help='shortest stretch to report, s')
args = ap.parse_args()

log = DFReader.DFReader_binary(args.log, zero_time_base=True)
att = []     # t, c33 for the flow core
vel = {args.core: [], args.ref: []}   # t, vn, ve, pn, pe
upd = []     # t, ni, passed
hagl = []    # t, HAGL for the flow core
aid = {args.core: [], args.ref: []}
rng = []     # t, dist, stat
gps = []     # t, vn, ve
msgs = []
armed = []
last5 = None
t0 = None
while True:
    m = log.recv_match(type=['XKF1', 'XKF4', 'XKF5', 'RFND', 'MSG', 'GPS', 'EV'])
    if m is None:
        break
    t = m.TimeUS * 1e-6
    typ = m.get_type()
    if typ == 'XKF1':
        if m.C == args.core:
            att.append((t, math.cos(math.radians(m.Roll)) * math.cos(math.radians(m.Pitch))))
        if m.C in vel:
            vel[m.C].append((t, m.VN, m.VE, m.PN, m.PE))
    elif typ == 'XKF4':
        if m.C in aid:
            aid[m.C].append((t, getattr(m, 'AID', -1) if 'AID' in m.get_fieldnames() else -1))
    elif typ == 'XKF5' and m.C == args.core:
        hagl.append((t, m.HAGL))
        key = (m.NI, m.FIX, m.FIY)
        if last5 is not None and key != last5:
            upd.append((t, m.NI, m.NI < 100))
        last5 = key
    elif typ == 'RFND':
        rng.append((t, m.Dist, m.Stat))
    elif typ == 'GPS':
        if m.Status >= 3:
            gps.append((t, m.Spd * math.cos(math.radians(m.GCrs)), m.Spd * math.sin(math.radians(m.GCrs))))
    elif typ == 'MSG':
        msgs.append((t, m.Message))
    elif typ == 'EV':
        armed.append((t, m.Id))


def at(series, t):
    """Last sample at or before t (series sorted by time)."""
    lo, hi = 0, len(series) - 1
    if not series or series[0][0] > t:
        return None
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if series[mid][0] <= t:
            lo = mid
        else:
            hi = mid - 1
    return series[lo]


def verr(t):
    a = at(vel[args.core], t)
    b = at(vel[args.ref], t)
    if a is None or b is None:
        return None
    return math.hypot(a[1] - b[1], a[2] - b[2]), math.hypot(b[1], b[2]), math.hypot(a[1], a[2])


def perr(t):
    a = at(vel[args.core], t)
    b = at(vel[args.ref], t)
    if a is None or b is None:
        return None
    return math.hypot(a[3] - b[3], a[4] - b[4])


# stretches
stretches = []
start = None
for t, c33 in att:
    if c33 <= 0.71:
        if start is None:
            start = t
    elif start is not None:
        stretches.append((start, t))
        start = None

dt5 = [upd[i + 1][0] - upd[i][0] for i in range(min(len(upd) - 1, 2000))]
print('# %s: %d flow updates, median spacing %.3f s; %d XKF1 for core %d' % (
    args.log.split('/')[-1], len(upd), sorted(dt5)[len(dt5) // 2] if dt5 else -1, len(att), args.core))
for t, s in msgs:
    if 'aiding' in s or 'flow' in s.lower():
        print('# MSG %.2f %s' % (t, s))
print('start   len   c33min  aidref aidflow rng(stat) hagl | first upd: dt  NI  | first pass dt | rejects | verr@start @level spd(ref) | verr+2 +5 +10 | perr@level +10 | timeouts')
for s, e in stretches:
    if e - s < args.min:
        continue
    c33min = min(c for t, c in att if s <= t <= e)
    after = [u for u in upd if u[0] > e]
    first = after[0] if after else None
    firstpass = next((u for u in after if u[2]), None)
    rejects = 0
    for u in after:
        if u[2]:
            break
        rejects += 1
    r = at(rng, e)
    ae = at(aid[args.ref], e)
    af = at(aid[args.core], e)
    v0 = verr(e)
    vs = [verr(e + d) for d in (2, 5, 10)]
    p0 = perr(e)
    p10 = perr(e + 10)
    tos = [m for m in msgs if s - 0.1 <= m[0] <= e + 10 and 'IMU%d' % args.core in m[1] and 'aiding' in m[1]]
    print('%7.2f %5.2f %6.2f  %3s     %3s   %5.1f(%d) %5.1f | %6.2f %4s | %7s | %3d | %5.2f %5.2f %5.1f | %s | %6.1f %6.1f | %s' % (
        s, e - s, c33min,
        ae[1] if ae else '-', af[1] if af else '-',
        r[1] if r else -1, r[2] if r else -1, (at(hagl, e) or (0, float('nan')))[1],
        (first[0] - e) if first else float('nan'), first[1] if first else '-',
        ('%.2f' % (firstpass[0] - e)) if firstpass else '-',
        rejects,
        (verr(s) or (float('nan'),))[0],
        v0[0] if v0 else float('nan'), v0[1] if v0 else float('nan'),
        ' '.join('%5.2f' % v[0] if v else '  -  ' for v in vs),
        p0 if p0 is not None else float('nan'), p10 if p10 is not None else float('nan'),
        '; '.join('%.1f %s' % (m[0], m[1]) for m in tos)))
