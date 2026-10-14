#!/usr/bin/env python3
"""Merge the per-chunk extraction outputs into one numbered list for clustering.

usage: merge_principles.py   (reads data/extract/*.jsonl, writes data/principles_all.json
                              and data/principles_compact.txt, one `id|reviewer|pr|principle` line each)
"""
import collections
import glob
import json
import os

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
allr = []
bad = 0
for f in sorted(glob.glob(D + '/extract/*.jsonl')):
    with open(f) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                bad += 1
                continue
            r['chunk'] = os.path.basename(f)[:2]
            allr.append(r)
for i, r in enumerate(allr):
    r['id'] = i
with open(D + '/principles_all.json', 'w') as fh:
    json.dump(allr, fh)
with open(D + '/principles_compact.txt', 'w') as fh:
    for r in allr:
        fh.write("%d|%s|%s|%s%s\n" % (r['id'], r.get('user', '?'), r.get('pr', '?'),
                                      r.get('principle', '').replace('\n', ' '),
                                      '' if r.get('general') else ' (generalised)'))
print(len(allr), 'principles,', bad, 'unparseable lines')
print(collections.Counter(r.get('user') for r in allr).most_common(8))
