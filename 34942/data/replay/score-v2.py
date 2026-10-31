"""Score the reworked on-ground height test over replayed logs.

usage: score_new.py <loglist> <replay base dir containing <name>/logs/00000001.BIN and replay.out>
"""
import bisect
import os
import sys

from pymavlink import mavutil


def replay_series(path):
    m = mavutil.mavlink_connection(path, robust_parsing=True)
    hk = {}
    vd = {}
    while True:
        msg = m.recv_match(type=['XKFM', 'XKF1'])
        if msg is None:
            break
        t = msg.TimeUS * 1e-6
        if msg.get_type() == 'XKFM':
            if msg.C < 150:
                continue
            f = msg.OGNM
            # t, H, HE, VDM, OG, AID, init, filt, ipd, vd
            hk.setdefault(msg.C - 150, []).append(
                (t, f & 1, (f >> 1) & 1, (f >> 2) & 1, (f >> 3) & 1, (f >> 4) & 3, (f >> 6) & 1, msg.GLR, msg.GDR, msg.ADR))
        elif msg.C >= 100:
            vd.setdefault(msg.C - 100, []).append((t, msg.VD, msg.PD))
    return hk, vd


def flight(path):
    m = mavutil.mavlink_connection(path, robust_parsing=True)
    arms = []
    vd = {}
    while True:
        msg = m.recv_match(type=['ARM', 'XKF1'])
        if msg is None:
            break
        t = msg.TimeUS * 1e-6
        if msg.get_type() == 'ARM':
            arms.append((t, msg.ArmState))
        elif msg.C < 100:
            vd.setdefault(msg.C, []).append((t, msg.VD))
    return arms, vd


def at(lst, t):
    ts = [x[0] for x in lst]
    i = bisect.bisect_right(ts, t) - 1
    return lst[max(i, 0)]


AID = {0: 'ABS', 1: 'NONE', 2: 'REL'}
srcmap = {}
for line in open(sys.argv[1]):
    p = line.strip()
    if p:
        srcmap[os.path.basename(p)[:-4]] = p
base = sys.argv[2]
tot = dict(arms=0, refused=0, refused_vd_ge1=0, refused_vd_lt05=0, he_time=0.0, he_episodes=0, forced=0)
for name in sorted(srcmap):
    rp = os.path.join(base, name, 'logs', '00000001.BIN')
    if not os.path.exists(rp):
        print("== %s: no replay output" % name)
        continue
    hk, vdr = replay_series(rp)
    arms, vdf = flight(srcmap[name])
    if not hk:
        print("== %s: no verdict records" % name)
        continue
    print("== %s (cores %s)" % (name, sorted(hk)))
    for t, st in arms:
        if st != 1:
            continue
        tot['arms'] += 1
        cells = []
        refused = False
        maxvd = 0.0
        for c in sorted(hk):
            r = at(hk[c], t - 0.05)
            v = at(vdr[c], t - 0.05)[1] if c in vdr else float('nan')
            fv = at(vdf[c], t - 0.05)[1] if c in vdf else float('nan')
            if r[2]:
                refused = True
            maxvd = max(maxvd, abs(v))
            cells.append("c%d %s%s filt %5.2f VD replay %5.2f flight %5.2f%s%s" % (
                c, AID[r[5]], ' vDmeas' if r[3] else '', r[7], v, fv,
                ' HGT-ERROR' if r[2] else '', '' if r[1] else ' unhealthy'))
        if refused:
            tot['refused'] += 1
            if maxvd >= 1.0:
                tot['refused_vd_ge1'] += 1
            if maxvd < 0.5:
                tot['refused_vd_lt05'] += 1
        print("  arm %7.2f %s  %s" % (t, 'REFUSE' if refused else 'ok    ', ' || '.join(cells)))
    # time in height error while on the ground, core 0
    rows = hk[min(hk)]
    he_t = 0.0
    eps = []
    for k in range(1, len(rows)):
        if rows[k - 1][2] and rows[k - 1][4]:
            he_t += rows[k][0] - rows[k - 1][0]
        if rows[k][2] and not rows[k - 1][2]:
            eps.append(rows[k][0])
    nf = open(os.path.join(base, name, 'replay.out')).read().count('forced reset')
    tot['he_time'] += he_t
    tot['he_episodes'] += len(eps)
    tot['forced'] += nf
    print("  core %d: %.1f s in height error on the ground, %d episodes starting %s; forced resets %d" % (
        min(hk), he_t, len(eps), ', '.join('%.1f' % e for e in eps[:12]), nf))
print(tot)
