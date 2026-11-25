#!/usr/bin/env python3
"""Summarise compare.py's per-carry lines (cmp-*.out) across all throws."""
import glob
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
carries = []
cur = None
for path in sorted(glob.glob(os.path.join(HERE, 'cmp-*.out'))):
    log = None
    for line in open(path):
        m = re.match(r'== \d+ (.*): (\d+) XKFA rows', line)
        if m:
            log = m.group(1)
            continue
        m = re.match(r'\s+carry ([\d.]+)-([\d.]+) s \(([\d.]+) s\) range median ([\d.]+) m(.*)', line)
        if m:
            cur = {'log': log, 'dur': float(m.group(3)), 'rng': float(m.group(4)), 'thrown': 'disarm' not in m.group(5)}
            carries.append(cur)
            continue
        m = re.match(r'\s+([ARB]): AGL median ([\w.]+) m \(min [\w.]+, valid (\d+)%\), flow innov rms ([\w.]+)(.*)', line)
        if m and cur is not None:
            v = {'agl': float(m.group(2)), 'valid': int(m.group(3)), 'fi': float(m.group(4)) * 0.001}
            a = re.search(r'worst \|AGL-range\| ([\w.]+) m, within band at ([\w. ]+?), flow innov rms ([\w.]+)', m.group(5))
            if a:
                v['worst'] = float(a.group(1))
                v['settle'] = None if a.group(2) == 'never' else float(a.group(2).replace(' s', ''))
                v['fi_after'] = float(a.group(3)) * 0.001
            cur[m.group(1)] = v

with_agl = [c for c in carries if c['A']['agl'] == c['A']['agl']]   # AGL KF running (not NaN)
print("carries %d, with the AGL KF running %d, thrown %d" %
      (len(carries), len(with_agl), sum(1 for c in with_agl if c['thrown'])))


def med(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else float('nan')


tracking = [c for c in with_agl if c['A']['agl'] > 0.3]
print("carries where this PR's AGL KF tracked the range (median > 0.3 m): %d" % len(tracking))
for c in tracking:
    print("   %-16s %5.1f s range %.2f m: PR %.2f m (valid %d%%), R %.2f m, B %.2f m" % (
        c['log'], c['dur'], c['rng'], c['A']['agl'], c['A']['valid'], c['R']['agl'], c['B']['agl']))
print("R's AGL median through the carry, all %d carries: max %.2f m" % (len(with_agl), max(c['R']['agl'] for c in with_agl)))
for v in 'ARB':
    print("%s: carry flow innov rms median %.2f rad/s" % (v, med(c[v]['fi'] for c in with_agl)))
thrown = [c for c in with_agl if c['thrown'] and 'settle' in c['A']]
print("after release, %d throws:" % len(thrown))
for v in 'ARB':
    s = [c[v]['settle'] for c in thrown]
    print("  %s: AGL within 0.2 m + 20%% of range at median %.2f s, max %s; flow innov rms median %.2f rad/s, max %.2f" % (
        v, med(s), "never" if None in s else "%.2f s" % max(s), med(c[v]['fi_after'] for c in thrown),
        max(c[v]['fi_after'] for c in thrown)))
later = sum(1 for c in thrown if c['R']['settle'] is not None and c['A']['settle'] is not None and
            c['R']['settle'] > c['A']['settle'] + 0.1)
worse_fi = sum(1 for c in thrown if c['R']['fi_after'] > 2 * c['A']['fi_after'])
same_b = sum(1 for c in thrown if abs(c['B']['settle'] - c['A']['settle']) < 0.05 if c['B']['settle'] is not None and c['A']['settle'] is not None)
print("R reaches the range later than the PR on %d of %d throws; R's flow innov after release over twice the PR's on %d" %
      (later, len(thrown), worse_fi))
print("B reaches the range within 0.05 s of the PR on %d of %d throws" % (same_b, len(thrown)))
