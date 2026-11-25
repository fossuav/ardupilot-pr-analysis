#!/usr/bin/env python3
"""Compare the AGL KF floor hold variants on replayed throw logs.

  compare.py [IDX...]

For each replayed log (run/{A,R,B}/IDX/logs/00000001.BIN), each THROW carry
(armed with land_complete set, from the log's own events) and the 3 s after
the throw is detected (NOT_LANDED):
  - median range finder reading (Good only) and each build's median AGL KF
    height (XKFA, first replayed core) through the carry
  - each build's worst |AGL KF height - range| in the 3 s after release, and
    when it first comes within 0.2 m + 20 % of the range
  - RMS flow innovation (XKF5 FIX/FIY) through the carry and after release
  - worst horizontal velocity error against GPS in the 5 s after release,
    where the GPS has 6+ satellites
"""
import sys
import os
import math
from pymavlink import DFReader

HERE = os.path.dirname(os.path.abspath(__file__))
VARIANTS = ['A', 'R', 'B']
CORE = 100


def load(path):
    """the rows compare() needs, read with replay_fleet's parser, which copes with replayed records
    written in the build's format under the source log's FMT"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'replay_fleet', '/home/andy/github/smallfastdrone-beta/.claude/skills/log-analyze/replay_fleet.py')
    rf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rf)
    rf.WANT = ('XKF1', 'XKF5', 'GPS', 'MSG', 'XKFA', 'RFND', 'EV', 'MODE')
    raw = rf.parse_bin(path)
    d = {}
    d['ev'] = [(r['TimeUS'] * 1e-6, r['Id']) for r in raw['EV']]
    d['mode'] = [(r['TimeUS'] * 1e-6, int(r['Mode'])) for r in raw['MODE']]
    d['rf'] = [(r['TimeUS'] * 1e-6, r['Dist'], int(r['Stat'])) for r in raw['RFND'] if r.get('Instance', 0) == 0]
    d['gps'] = [(r['TimeUS'] * 1e-6, r['Spd'], r['GCrs'], r['NSats'], r['Status']) for r in raw['GPS'] if r.get('I', 0) == 0]
    d['xkfa'] = [(r['TimeUS'] * 1e-6, r['HAgl'], r.get('Valid', 0)) for r in raw['XKFA'] if r.get('C') == CORE and 'HAgl' in r]
    d['xkf5'] = [(r['TimeUS'] * 1e-6, r['FIX'], r['FIY']) for r in raw['XKF5'] if r['C'] == CORE]
    d['xkf1'] = [(r['TimeUS'] * 1e-6, r['VN'], r['VE']) for r in raw['XKF1'] if r['C'] == CORE]
    return d


def periods(d):
    """armed-landed THROW periods and the time each ended (NOT_LANDED), or None"""
    armed, landed = False, True
    mode = None
    events = sorted([(t, 'ev', i) for t, i in d['ev']] + [(t, 'mode', m) for t, m in d['mode']])
    out = []
    start = None
    for t, kind, v in events:
        if kind == 'mode':
            mode = v
            continue
        na, nl = armed, landed
        if v == 10:
            na = True
        elif v == 11:
            na, nl = False, True
        elif v == 18:
            nl = True
        elif v == 28:
            nl = False
        if na and nl and start is None:
            start = (t, mode)
        elif start is not None and not (na and nl):
            out.append((start[0], t, start[1], v == 28))
            start = None
        armed, landed = na, nl
    return [p for p in out if p[2] == 18]   # THROW


def window(rows, t0, t1):
    return [r for r in rows if t0 <= r[0] <= t1]


def median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else float('nan')


def rf_at(rf, t):
    """latest Good range at or before t, within 0.3 s"""
    best = None
    for r in rf:
        if r[0] > t:
            break
        if r[2] == 4:
            best = r
    if best is None or t - best[0] > 0.3:
        return None
    return best[1]


def rms_flow(rows):
    vals = [math.hypot(fx, fy) for _, fx, fy in rows]
    return math.sqrt(sum(v * v for v in vals) / len(vals)) if vals else float('nan')


def vel_err(d, t0, t1):
    worst = None
    gps = [g for g in window(d['gps'], t0, t1) if g[3] >= 6 and g[4] >= 3]
    if not gps:
        return None
    for t, vn, ve in window(d['xkf1'], t0, t1):
        g = min(gps, key=lambda g: abs(g[0] - t))
        if abs(g[0] - t) > 0.25:
            continue
        gvn = g[1] * math.cos(math.radians(g[2]))
        gve = g[1] * math.sin(math.radians(g[2]))
        e = math.hypot(vn - gvn, ve - gve)
        worst = e if worst is None else max(worst, e)
    return worst


def main():
    idxs = sys.argv[1:] or sorted(os.listdir(os.path.join(HERE, 'run', 'A')), key=int)
    logs = [ln.rstrip('\n') for ln in open(os.path.join(HERE, 'throw_logs.txt'))]
    for idx in idxs:
        data = {}
        for v in VARIANTS:
            p = os.path.join(HERE, 'run', v, idx, 'logs', '00000001.BIN')
            data[v] = load(p)
        base = data['A']
        name = os.path.basename(logs[int(idx) - 1])
        print("== %s %s: %d XKFA rows" % (idx, name, len(base['xkfa'])))
        for (t0, t1, mode, thrown) in periods(base):
            rngs = [r[1] for r in window(base['rf'], t0, t1) if r[2] == 4]
            if not rngs or median(rngs) < 0.5:
                continue
            line = "  carry %.1f-%.1f s (%.1f s) range median %.2f m%s" % (t0, t1, t1 - t0, median(rngs),
                                                                           "" if thrown else ", ended by disarm")
            print(line)
            for v in VARIANTS:
                dv = data[v]
                h = [r[1] for r in window(dv['xkfa'], t0, t1)]
                valid = [r[2] for r in window(dv['xkfa'], t0, t1)]
                carry = "AGL median %.2f m (min %.2f, valid %d%%), flow innov rms %.3f" % (
                    median(h), min(h) if h else float('nan'),
                    100 * sum(1 for x in valid if x) / len(valid) if valid else 0, rms_flow(window(dv['xkf5'], t0, t1)))
                after = ""
                if thrown:
                    errs = []
                    settle = None
                    for t, hg, _ in window(dv['xkfa'], t1, t1 + 3):
                        r = rf_at(base['rf'], t)
                        if r is None:
                            continue
                        e = abs(hg - r)
                        errs.append(e)
                        if settle is None and e < 0.2 + 0.2 * r:
                            settle = t - t1
                    ve = vel_err(dv, t1, t1 + 5)
                    after = " | after release: worst |AGL-range| %.2f m, within band at %s, flow innov rms %.3f, vel err %s" % (
                        max(errs) if errs else float('nan'),
                        "%.2f s" % settle if settle is not None else "never",
                        rms_flow(window(dv['xkf5'], t1, t1 + 3)),
                        "%.2f m/s" % ve if ve is not None else "no GPS")
                print("     %s: %s%s" % (v, carry, after))


if __name__ == '__main__':
    main()
