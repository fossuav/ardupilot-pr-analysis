#!/usr/bin/env python3
"""What does reporting a THROW carry as landed (#35105) do to the EKF through a real throw?

  landed_onoff.py [IDX...]

The same build (this PR) replayed twice: run/L0 with no landed flag (as these logs
were flown, before #35105) and run/A with the flag taken from the log's own
LAND_COMPLETE / NOT_LANDED events (as #35105 reports it). For each THROW carry
(armed with land_complete set, range finder Good median above 0.5 m) and the 5 s
after the throw is detected, per build:
  - flow innovation RMS (XKF5 FIX/FIY) and the share of flow samples whose test
    ratio exceeds 1 (XKF5 NI > 100), through the carry and after release
  - yaw innovation RMS (XKF3 IYAW) after release
and between the builds:
  - the largest horizontal velocity, yaw and position difference after release
  - EKF3 messages printed by one replay and not the other
"""
import importlib.util
import math
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    'replay_fleet', '/home/andy/github/smallfastdrone-beta/.claude/skills/log-analyze/replay_fleet.py')
rf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rf)
rf.WANT = ('XKF1', 'XKF5', 'XKF3', 'RFND', 'EV', 'MODE')
CORE = 100


def load(v, idx):
    raw = rf.parse_bin(os.path.join(HERE, 'run', v, idx, 'logs', '00000001.BIN'))
    d = {k: [] for k in ('ev', 'mode', 'rf', 'k1', 'k5', 'k3')}
    d['ev'] = [(r['TimeUS'] * 1e-6, r['Id']) for r in raw['EV']]
    d['mode'] = [(r['TimeUS'] * 1e-6, int(r['Mode'])) for r in raw['MODE']]
    d['rf'] = [(r['TimeUS'] * 1e-6, r['Dist'], int(r['Stat'])) for r in raw['RFND'] if r.get('Instance', 0) == 0]
    d['k1'] = {r['TimeUS']: r for r in raw['XKF1'] if r.get('C') == CORE and 'Yaw' in r}
    d['k5'] = [r for r in raw['XKF5'] if r.get('C') == CORE and 'FIY' in r]
    d['k3'] = [r for r in raw['XKF3'] if r.get('C') == CORE and 'IYAW' in r]
    out = open(os.path.join(HERE, 'run', v, idx, 'replay.out'), errors='replace').read().splitlines()
    d['msgs'] = Counter(ln.strip() for ln in out if 'EKF3' in ln)
    return d


def periods(d):
    events = sorted([(t, 'ev', i) for t, i in d['ev']] + [(t, 'mode', m) for t, m in d['mode']])
    armed, landed, mode, start, out = False, True, None, None, []
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
    return [p for p in out if p[2] == 18 and p[3]]


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else float('nan')


def flow_stats(k5, t0, t1):
    rows = [r for r in k5 if t0 <= r['TimeUS'] * 1e-6 <= t1]
    if not rows:
        return float('nan'), float('nan')
    rms = math.sqrt(sum((r['FIX'] * 1e-3) ** 2 + (r['FIY'] * 1e-3) ** 2 for r in rows) / len(rows))
    rej = sum(1 for r in rows if r['NI'] > 100) / len(rows)
    return rms, rej


def yaw_rms(k3, t0, t1):
    rows = [r['IYAW'] for r in k3 if t0 <= r['TimeUS'] * 1e-6 <= t1]
    return math.sqrt(sum(x * x for x in rows) / len(rows)) if rows else float('nan')


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def main():
    logs = [ln.rstrip('\n') for ln in open(os.path.join(HERE, 'throw_logs.txt'))]
    idxs = sys.argv[1:] or [str(i + 1) for i in range(len(logs))]
    rows = []
    for idx in idxs:
        off, on = load('L0', idx), load('A', idx)
        name = os.path.basename(logs[int(idx) - 1])
        only_on = on['msgs'] - off['msgs']
        only_off = off['msgs'] - on['msgs']
        print("== %s %s" % (idx, name))
        for m, c in sorted(only_on.items()):
            print("   only with landed: %dx %s" % (c, m))
        for m, c in sorted(only_off.items()):
            print("   only without landed: %dx %s" % (c, m))
        for t0, t1, _, _ in periods(on):
            rngs = [r[1] for r in on['rf'] if t0 <= r[0] <= t1 and r[2] == 4]
            if not rngs or med(rngs) < 0.5:
                continue
            fo_c = flow_stats(off['k5'], t0, t1)
            fn_c = flow_stats(on['k5'], t0, t1)
            fo_a = flow_stats(off['k5'], t1, t1 + 3)
            fn_a = flow_stats(on['k5'], t1, t1 + 3)
            common = sorted(set(off['k1']) & set(on['k1']))
            dv = dyaw = dpos = 0.0
            for t in common:
                if t1 <= t * 1e-6 <= t1 + 5:
                    a, b = off['k1'][t], on['k1'][t]
                    dv = max(dv, math.hypot(a['VN'] - b['VN'], a['VE'] - b['VE']))
                    dyaw = max(dyaw, abs(wrap180(a['Yaw'] - b['Yaw'])))
                    dpos = max(dpos, math.hypot(a['PN'] - b['PN'], a['PE'] - b['PE']))
            at_rel = [t for t in common if abs(t * 1e-6 - t1) < 0.1]
            vrel = None
            if at_rel:
                a, b = off['k1'][at_rel[0]], on['k1'][at_rel[0]]
                vrel = (math.hypot(a['VN'], a['VE']), math.hypot(b['VN'], b['VE']))
            yo, yn = yaw_rms(off['k3'], t1, t1 + 5), yaw_rms(on['k3'], t1, t1 + 5)
            rows.append(dict(log=name, dur=t1 - t0, fo_c=fo_c, fn_c=fn_c, fo_a=fo_a, fn_a=fn_a, dv=dv, dyaw=dyaw,
                             dpos=dpos, vrel=vrel, yo=yo, yn=yn))
            print("   carry %.1f s range %.2f m | carry flow rms off %.2f on %.2f, rejected off %.0f%% on %.0f%% | "
                  "after: flow rms off %.2f on %.2f, rejected off %.0f%% on %.0f%%, yaw innov rms off %.3f on %.3f | "
                  "speed at release off %s on %s | max diff in 5 s: vel %.2f m/s yaw %.1f deg pos %.2f m" % (
                      t1 - t0, med(rngs), fo_c[0], fn_c[0], 100 * fo_c[1], 100 * fn_c[1], fo_a[0], fn_a[0],
                      100 * fo_a[1], 100 * fn_a[1], yo, yn,
                      "%.2f" % vrel[0] if vrel else "-", "%.2f" % vrel[1] if vrel else "-", dv, dyaw, dpos))
    if rows:
        print("\nsummary over %d thrown carries:" % len(rows))
        for k, label in (('fo_c', 'carry flow rms / rejected'), ('fo_a', 'after-release flow rms / rejected')):
            kn = 'fn' + k[2:]
            print("  %s: off median %.2f rad/s / %.0f%%, on median %.2f rad/s / %.0f%%" % (
                label, med([r[k][0] for r in rows if r[k][0] == r[k][0]]),
                100 * med([r[k][1] for r in rows if r[k][1] == r[k][1]]),
                med([r[kn][0] for r in rows if r[kn][0] == r[kn][0]]),
                100 * med([r[kn][1] for r in rows if r[kn][1] == r[kn][1]])))
        print("  yaw innovation rms after release: off median %.3f, on median %.3f" % (
            med([r['yo'] for r in rows if r['yo'] == r['yo']]), med([r['yn'] for r in rows if r['yn'] == r['yn']])))
        for k, unit in (('dv', 'm/s'), ('dyaw', 'deg'), ('dpos', 'm')):
            xs = [r[k] for r in rows]
            print("  max difference in the 5 s after release, %s: median %.2f %s, max %.2f, over 1 on %d" % (
                k, med(xs), unit, max(xs), sum(1 for x in xs if x > 1)))


if __name__ == '__main__':
    main()
