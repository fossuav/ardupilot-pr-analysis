#!/usr/bin/env python3
"""Merge the per-chunk extraction outputs into one numbered list for clustering.

usage: merge_principles.py [--append]
       (reads data/extract/*.jsonl, writes data/principles_all.json and
        data/principles_compact.txt, one `id|reviewer|pr|principle` line each)

--append keeps the existing principles_all.json and its ids, which clusters.json
refers to, adds the new principles after them (skipping any already present), and
writes only the new ones to data/principles_new.txt for assign_new.py.
"""
import argparse
import collections
import glob
import json
import os

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
ap.add_argument('--append', action='store_true', help='add to the existing principles_all.json, keeping its ids')
args = ap.parse_args()

old = json.load(open(D + '/principles_all.json')) if args.append else []
seen = {(r.get('url'), r.get('principle')) for r in old}
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
            if (r.get('url'), r.get('principle')) in seen:
                continue
            seen.add((r.get('url'), r.get('principle')))
            r['chunk'] = os.path.splitext(os.path.basename(f))[0]
            allr.append(r)
first = max((r['id'] for r in old), default=-1) + 1
for i, r in enumerate(allr):
    r['id'] = first + i
with open(D + '/principles_all.json', 'w') as fh:
    json.dump(old + allr, fh)
with open(D + ('/principles_new.txt' if args.append else '/principles_compact.txt'), 'w') as fh:
    for r in allr:
        fh.write("%d|%s|%s|%s%s\n" % (r['id'], r.get('user', '?'), r.get('pr', '?'),
                                      r.get('principle', '').replace('\n', ' '),
                                      '' if r.get('general') else ' (generalised)'))
print(len(allr), 'principles,', bad, 'unparseable lines')
print(collections.Counter(r.get('user') for r in allr).most_common(8))
