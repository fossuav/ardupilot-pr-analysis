"""Score each arm event: A = refresh12 + logging (shadow fixed filter), B = the fix acting."""
import sys, os, bisect
from pymavlink import mavutil

def series(path, want_replay):
    m = mavutil.mavlink_connection(path, robust_parsing=True)
    hk = {}   # core -> list of (t, HIF, HIFX, HO, HN, H, OG, AID)
    vd = {}
    while True:
        msg = m.recv_match(type=['XKFM', 'XKF1'])
        if msg is None:
            break
        t = msg.TimeUS * 1e-6
        if msg.get_type() == 'XKFM':
            if msg.C < 150:
                continue
            c = msg.C - 150
            f = msg.OGNM
            # t, HIF, HIFX, HO, HN, H, OG, AID
            hk.setdefault(c, []).append((t, msg.GLR, msg.ALR, (f >> 1) & 1, (f >> 2) & 1, f & 1, (f >> 3) & 1, (f >> 4) & 3, (f >> 6) & 1))
        else:
            key = msg.C % 100 if (msg.C >= 100) == want_replay else 1000 + msg.C % 100
            vd.setdefault(key, []).append((t, msg.VD, msg.PD))
    return hk, vd

def at(lst, t):
    ts = [x[0] for x in lst]
    i = bisect.bisect_right(ts, t) - 1
    return lst[max(i, 0)]

def arms(src):
    m = mavutil.mavlink_connection(src, robust_parsing=True)
    out = []
    while True:
        msg = m.recv_match(type=['ARM'])
        if msg is None:
            break
        out.append((msg.TimeUS * 1e-6, msg.ArmState))
    return out

def unhealthy_since(lst, t, idx):
    # how long the verdict at index idx had been 0 continuously before t
    ts = [x[0] for x in lst]
    i = bisect.bisect_right(ts, t) - 1
    if i < 0 or lst[i][idx]:
        return 0.0
    j = i
    while j > 0 and not lst[j - 1][idx]:
        j -= 1
    return t - lst[j][0]

srcmap = {}
for line in open(sys.argv[1]):
    p = line.strip()
    srcmap[os.path.basename(p)[:-4]] = p
base = sys.argv[2]
tot = dict(arms=0, refuse=0, refuse_vd_small=0)
for name in sorted(srcmap):
    a = os.path.join(base, 'A', name, 'logs', '00000001.BIN')
    b = os.path.join(base, 'B', name, 'logs', '00000001.BIN')
    hkA, vdA = series(a, True)
    hkB, vdB = series(b, True)
    if not hkA:
        print(name, 'no XKHF')
        continue
    print("== %s (cores %s)" % (name, sorted(hkA)))
    for t, st in arms(srcmap[name]):
        if st != 1:
            continue
        tot['arms'] += 1
        cells = []
        refuse = False
        smallvd = True
        for c in sorted(hkA):
            ra = at(hkA[c], t - 0.05)
            va = at(vdA[c], t - 0.05)
            rb = at(hkB[c], t - 0.05)
            vb = at(vdB[c], t - 0.05)
            dur = unhealthy_since(hkA[c], t - 0.05, 4)
            if not ra[4]:
                refuse = True
            if abs(va[1]) > 0.5:
                smallvd = False
            fv = at(vdA[1000 + c], t - 0.05)[1] if (1000 + c) in vdA else float('nan')
            cells.append(("c%d: flight VD %5.2f " % (c, fv)) + "replay VD %5.2f | stock filt %5.2f %s | fixed filt %6.2f %s%s | B: VD %5.2f H %d" % (
                va[1], ra[1], 'ok ' if ra[3] else 'BAD', ra[2], 'ok' if ra[4] else 'REFUSE',
                (' (%.1fs)' % dur) if not ra[4] else '', vb[1], rb[5]))
        if refuse:
            tot['refuse'] += 1
            if smallvd:
                tot['refuse_vd_small'] += 1
        print("  arm %7.2f  %s" % (t, '  ||  '.join(cells)))
    for c in sorted(hkB):
        starts = [x[0] for k, x in enumerate(hkB[c]) if x[8] and (k == 0 or not hkB[c][k-1][8])]
        print("  B core %d (re)initialisations at: %s" % (c, ', '.join('%.1f' % v for v in starts)))
    for c in sorted(hkA):
        starts = [x[0] for k, x in enumerate(hkA[c]) if x[8] and (k == 0 or not hkA[c][k-1][8])]
        print("  A core %d (re)initialisations at: %s" % (c, ', '.join('%.1f' % v for v in starts)))
    nA = open(os.path.join(base, 'A', name, 'replay.out')).read().count('forced reset')
    nB = open(os.path.join(base, 'B', name, 'replay.out')).read().count('forced reset')
    print("  forced resets: A %d, B %d" % (nA, nB))
print(tot)
