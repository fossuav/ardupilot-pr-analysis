#!/usr/bin/env python3
"""Where does the AGL KF floor hold change the height, and what was the vehicle doing?

  hold_segments.py fleet-A fleet-N

For every replayed log where this PR (A) and the no-hold build (N) give a
different AGL KF height on the first replayed core, split the differences into
segments (|dAGL| > 0.05 m, gaps under 1 s) and describe each from the original
log: armed, land_complete, mode, the range finder's status and Good reading,
and each build's median height.
"""
import glob
import importlib.util
import os
import pickle
import sys

spec = importlib.util.spec_from_file_location(
    'replay_fleet', '/home/andy/github/smallfastdrone-beta/.claude/skills/log-analyze/replay_fleet.py')
rf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rf)
rf.WANT = ('XKF1', 'XKF5', 'RFND', 'EV', 'MODE')
CORE = 100
STAT = {0: 'NotConn', 1: 'NoData', 2: 'TooLow', 3: 'TooHigh', 4: 'Good'}


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else float('nan')


def state_at(events, t):
    armed, landed, mode = False, True, None
    for te, kind, v in events:
        if te > t:
            break
        if kind == 'mode':
            mode = v
        elif v == 10:
            armed = True
        elif v == 11:
            armed, landed = False, True
        elif v == 18:
            landed = True
        elif v == 28:
            landed = False
    return armed, landed, mode


def main():
    da, dn = sys.argv[1], sys.argv[2]
    seen = set()
    for pa in sorted(glob.glob(os.path.join(da, '*.pkl'))):
        pn = os.path.join(dn, os.path.basename(pa))
        a = pickle.load(open(pa, 'rb'))
        b = pickle.load(open(pn, 'rb'))
        ha = {x['TimeUS']: x['HAgl'] for x in a.get('XKFA', []) if x.get('C') == CORE and 'HAgl' in x}
        hb = {x['TimeUS']: x['HAgl'] for x in b.get('XKFA', []) if x.get('C') == CORE and 'HAgl' in x}
        ts = sorted(set(ha) & set(hb))
        diff = [t for t in ts if abs(ha[t] - hb[t]) > 0.05]
        if not diff:
            continue
        size = os.path.getsize(a['log'])
        if size in seen:
            continue
        seen.add(size)
        raw = rf.parse_bin(a['log'])
        events = sorted([(r['TimeUS'], 'ev', r['Id']) for r in raw['EV']] +
                        [(r['TimeUS'], 'mode', int(r['Mode'])) for r in raw['MODE']])
        rng = [(r['TimeUS'], r['Dist'], int(r['Stat'])) for r in raw['RFND'] if r.get('Instance', 0) == 0]
        segs = []
        for t in diff:
            if segs and t - segs[-1][1] < 1e6:
                segs[-1][1] = t
            else:
                segs.append([t, t])
        print("== %s" % os.path.basename(a['log']))
        for s0, s1 in segs:
            if s1 - s0 < 0.2e6:
                continue
            arm, landed, mode = state_at(events, s0)
            rs = [r for r in rng if s0 <= r[0] <= s1]
            stats = {}
            for r in rs:
                stats[STAT.get(r[2], r[2])] = stats.get(STAT.get(r[2], r[2]), 0) + 1
            good = [r[1] for r in rs if r[2] == 4]
            print("   %7.1f s for %4.1f s: %s%s mode %s | range %s, Good median %.2f m | PR %.2f m, no hold %.2f m (max |d| %.2f m)" % (
                s0 * 1e-6, (s1 - s0) * 1e-6, 'armed' if arm else 'disarmed', ' landed' if landed and arm else '',
                mode, ",".join("%s %d" % kv for kv in sorted(stats.items())), med(good),
                med([ha[t] for t in ts if s0 <= t <= s1]), med([hb[t] for t in ts if s0 <= t <= s1]),
                max(abs(ha[t] - hb[t]) for t in ts if s0 <= t <= s1)))


if __name__ == '__main__':
    main()
