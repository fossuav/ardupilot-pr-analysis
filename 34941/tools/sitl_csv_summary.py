#!/usr/bin/env python3
# Tabulate OpticalFlowTiltRecovery.csv: master against PR, median (min-max) over runs.
import csv
import sys
from collections import defaultdict
path = sys.argv[1]
builds = {'master': sys.argv[2].split(','), 'PR': sys.argv[3].split(',')}
data = defaultdict(lambda: defaultdict(list))
order = []
FIELDS = ['tag', 'leg', 'tilt_s', 'stretches', 'c33min', 'verr_start', 'verr', 'verr_ne', 'speed', 'first_dt',
          'first_ni', 'pass_dt', 'rejects', 'verr2', 'verr5', 'verr10', 'disp10', 'timeouts']
for r in csv.DictReader(open(path)):
    for b, tags in builds.items():
        if r['tag'] in tags:
            if r['leg'] not in order:
                order.append(r['leg'])
            data[r['leg']][b].append(r)


def med(rows, k):
    v = sorted(float(r[k]) for r in rows)
    if not v:
        return '-'
    m = v[len(v) // 2]
    return '%.1f' % m if v[0] == v[-1] else '%.1f (%.1f-%.1f)' % (m, v[0], v[-1])


def first_ok(rows):
    return '%d/%d' % (sum(1 for r in rows if 0 <= int(r['first_ni']) < 100), len(rows))


print('| leg | build | runs | tilt s | verr at start | verr at level | first sample accepted | rejects | v+2 | v+5 | v+10 | disp at +10 | timeouts |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
for leg in order:
    for b in builds:
        rows = data[leg][b]
        if not rows:
            continue
        print('| %s | %s | %d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
            leg, b, len(rows), med(rows, 'tilt_s'), med(rows, 'verr_start'), med(rows, 'verr'), first_ok(rows), med(rows, 'rejects'),
            med(rows, 'verr2'), med(rows, 'verr5'), med(rows, 'verr10'), med(rows, 'disp10'), med(rows, 'timeouts')))
