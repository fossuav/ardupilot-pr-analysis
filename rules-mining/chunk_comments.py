#!/usr/bin/env python3
"""Filter collected review comments and split them into reviewer-tier chunks for extraction.

usage: chunk_comments.py   (reads data/comments.jsonl, writes data/chunks/{A,B,C}N.txt)

Drops comments tagged as AI review output, bots, short or approval-only remarks
and, for reviewers outside tiers A and B, anything under 200 characters.
Tier A is rmackay9 and peterbarker, tier B lthall and tridge.
"""
import collections
import json
import os
import re

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
TIER_A = {'rmackay9', 'peterbarker'}
TIER_B = {'lthall', 'tridge'}
SKIP = {'AP-Review', 'ap-review'}
TRIVIAL = re.compile(r"^\s*(lgtm|thanks?( you)?|merged|merging|nice|great|ok|done|approved?|looks good|"
                     r"ping|rebased?|bump|\+1|:\+1:)[\s.!,:)]*$", re.I)


def fmt(r):
    loc = (' ' + r['path']) if r.get('path') else ''
    return "PR#%d \"%s\" [%s %s%s] %s\n%s\n----\n" % (
        r['pr'], r['title'][:70], r['user'], r['kind'], loc, r['url'], r['body'][:4000])


def chunk(rs, prefix, maxw):
    rs = sorted(rs, key=lambda r: (r['user'], r['pr'], r['created']))
    out, cur, cw = [], [], 0
    for r in rs:
        w = len(r['body'].split())
        if cur and cw + w > maxw:
            out.append(cur)
            cur, cw = [], 0
        cur.append(r)
        cw += w
    if cur:
        out.append(cur)
    for i, c in enumerate(out):
        with open('%s/chunks/%s%d.txt' % (D, prefix, i + 1), 'w') as fh:
            fh.write(''.join(fmt(r) for r in c))
    return len(out)


kept = collections.defaultdict(list)
stats = collections.Counter()
with open(D + '/comments.jsonl') as fh:
    for line in fh:
        r = json.loads(line)
        u = r['user']
        if r['ai'] or u in SKIP or u.lower().endswith('bot'):
            stats['ai/bot'] += 1
            continue
        b = re.sub(r'\n{3,}', '\n\n', r['body']).strip()
        if TRIVIAL.match(b) or len(b) < 60:
            stats['short'] += 1
            continue
        tier = 'A' if u in TIER_A else 'B' if u in TIER_B else 'C'
        if tier == 'C' and len(b) < 200:
            stats['C-short'] += 1
            continue
        r['body'] = b
        kept[tier].append(r)

os.makedirs(D + '/chunks', exist_ok=True)
for t, maxw in (('A', 13000), ('B', 15000), ('C', 20000)):
    w = sum(len(r['body'].split()) for r in kept[t])
    print("tier %s: %d comments, %d words, %d chunks" % (t, len(kept[t]), w, chunk(kept[t], t, maxw)))
print(dict(stats))
