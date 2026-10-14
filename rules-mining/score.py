#!/usr/bin/env python3
"""Rank clustered review principles by repetition, weighting Randy and Peter highest.

usage: score.py [kind]   e.g. score.py architecture
"""
import json
import sys

import os
S = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
WEIGHT = {'rmackay9': 3, 'peterbarker': 3, 'lthall': 2, 'tridge': 2}
kind_filter = sys.argv[1] if len(sys.argv) > 1 else None

allr = {r['id']: r for r in json.load(open(S + '/principles_all.json'))}
clusters = json.load(open(S + '/clusters.json'))
seen = {}
for c in clusters:
    for i in c['ids']:
        seen[i] = seen.get(i, 0) + 1
missing = [i for i in allr if i not in seen]
dup = [i for i, n in seen.items() if n > 1]
print("themes %d, ids missing %d, ids duplicated %d" % (len(clusters), len(missing), len(dup)))

rows = []
for c in clusters:
    if c['key'] == 'misc':
        continue
    pairs = {(allr[i]['pr'], allr[i]['user']) for i in c['ids'] if i in allr}
    prs = {p for p, _ in pairs}
    users = {u for _, u in pairs}
    score = sum(WEIGHT.get(u, 1) for _, u in pairs)
    general = sum(1 for i in c['ids'] if allr.get(i, {}).get('general'))
    rows.append((score, len(prs), c, users, general))
rows.sort(key=lambda r: (-r[0], -r[1]))
for score, nprs, c, users, general in rows:
    if kind_filter and c.get('kind') != kind_filter:
        continue
    print("%3d  %2d PRs  %-12s %-34s %s" % (score, nprs, c.get('kind', '?'), c['key'][:34], ','.join(sorted(users))))
    print("      %s  [%d general]" % (c['rule'], general))
