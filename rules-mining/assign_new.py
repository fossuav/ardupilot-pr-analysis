#!/usr/bin/env python3
"""Add newly mined principles to the existing themes, from the sorting agent's choices.

usage: assign_new.py [--check]
       (reads data/assign.json, written by an agent with assign_brief.md, and
        data/principles_all.json; adds each new id to its theme in
        data/clusters.json, creating the new themes it names)

A new id is one in principles_all.json that no theme holds yet. --check reports
problems and writes nothing.
"""
import argparse
import json
import os
import sys

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
KINDS = {'architecture', 'parameters', 'testing', 'process', 'style', 'logging_gcs'}

ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
ap.add_argument('--check', action='store_true', help='report problems and write nothing')
args = ap.parse_args()

clusters = json.load(open(D + '/clusters.json'))
allids = {r['id'] for r in json.load(open(D + '/principles_all.json'))}
held = {i for c in clusters for i in c['ids']}
new = allids - held
choice = json.load(open(D + '/assign.json'))
assign = {int(k): v for k, v in choice.get('assign', {}).items()}
themes = {c['key']: c for c in clusters}

problems = []
for t in choice.get('new_themes', []):
    if t.get('key') in themes:
        problems.append('new theme %s already exists' % t.get('key'))
    elif not t.get('key') or not t.get('rule') or t.get('kind') not in KINDS:
        problems.append('new theme needs a key, a rule and a kind in %s: %r' % (sorted(KINDS), t))
    else:
        themes[t['key']] = dict(t, ids=[])
missing = sorted(new - set(assign))
extra = sorted(set(assign) - new)
if missing:
    problems.append('new ids with no theme: %s' % missing)
if extra:
    problems.append('ids that are not new: %s' % extra)
unknown = sorted({k for i, k in assign.items() if k not in themes})
if unknown:
    problems.append('unknown theme keys: %s' % unknown)
unused = [t['key'] for t in choice.get('new_themes', []) if t.get('key') in themes and t['key'] not in assign.values()]
if unused:
    problems.append('new themes with no ids: %s' % unused)

if problems:
    print('\n'.join(problems))
    sys.exit(1)
print('%d new ids, %d new themes' % (len(new), len(choice.get('new_themes', []))))
if args.check:
    sys.exit(0)
for i, k in sorted(assign.items()):
    themes[k]['ids'].append(i)
with open(D + '/clusters.json', 'w') as fh:
    json.dump(list(themes.values()), fh, indent=1)
print('wrote clusters.json, %d themes' % len(themes))
