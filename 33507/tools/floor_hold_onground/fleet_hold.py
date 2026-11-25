#!/usr/bin/env python3
"""Does the AGL KF floor hold change anything on real flights?

  fleet_hold.py fleet-A fleet-N

Per replayed log (fleet_run.py pickles), compare the replayed cores' XKFA height
and XKF1 horizontal velocity between this PR (A) and the same build with the
floor hold removed (N). A log where the two agree everywhere is one where the
hold never engaged, or engaged without effect.
"""
import glob
import math
import os
import pickle
import sys

OFFSET = 100


def rows(r, name, key):
    out = {}
    for x in r.get(name, []):
        if x.get('C', 0) >= OFFSET and key in x:
            out[(x['C'], x['TimeUS'])] = x
    return out


def main():
    da, dn = sys.argv[1], sys.argv[2]
    n_logs = n_agl = n_same = 0
    diffs = []
    errors = []
    for pa in sorted(glob.glob(os.path.join(da, '*.pkl'))):
        pn = os.path.join(dn, os.path.basename(pa))
        if not os.path.exists(pn):
            continue
        a = pickle.load(open(pa, 'rb'))
        b = pickle.load(open(pn, 'rb'))
        if a.get('rc', 0) != 0 or b.get('rc', 0) != 0 or 'error' in a or 'error' in b:
            errors.append(a.get('log'))
            continue
        n_logs += 1
        xa, xb = rows(a, 'XKFA', 'HAgl'), rows(b, 'XKFA', 'HAgl')
        if xa:
            n_agl += 1
        common = set(xa) & set(xb)
        dh = max((abs(xa[k]['HAgl'] - xb[k]['HAgl']) for k in common), default=0.0)
        va, vb = rows(a, 'XKF1', 'VN'), rows(b, 'XKF1', 'VN')
        cv = set(va) & set(vb)
        dv = max((math.hypot(va[k]['VN'] - vb[k]['VN'], va[k]['VE'] - vb[k]['VE']) for k in cv), default=0.0)
        missing = len(set(xa) ^ set(xb)) + len(set(va) ^ set(vb))
        if dh == 0 and dv == 0 and missing == 0:
            n_same += 1
        else:
            first = min((k[1] for k in common if abs(xa[k]['HAgl'] - xb[k]['HAgl']) > 0), default=None)
            diffs.append((a['log'], dh, dv, missing, first, len(xa)))
    print("logs compared %d (errors %d), with the AGL KF running %d" % (n_logs, len(errors), n_agl))
    print("identical in AGL height and velocity: %d" % n_same)
    print("differing: %d" % len(diffs))
    for log, dh, dv, missing, first, nx in sorted(diffs, key=lambda d: -d[1]):
        print("  max |dAGL| %.3f m, max |dV| %.3f m/s, rows in one run only %d, first AGL difference at %s, XKFA rows %d: %s" % (
            dh, dv, missing, "%.1f s" % (first * 1e-6) if first else "-", nx,
            os.path.basename(log)))


if __name__ == '__main__':
    main()
