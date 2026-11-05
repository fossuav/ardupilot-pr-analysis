#!/usr/bin/env python3
# Summarise tilt_recovery.py tables: stretches of 5 s or more against shorter ones.
import sys
rows = []
for path in sys.argv[1:]:
    for line in open(path):
        if line.startswith('#') or line.startswith('start'):
            continue
        p = line.replace('|', ' ').replace('(', ' ').replace(')', ' ').split()
        # start len c33 aidref aidflow rng stat hagl first_dt NI pass_dt rejects verr_s verr_l spd v2 v5 v10 p0 p10
        r = dict(log=path.split('_')[-1], start=float(p[0]), len=float(p[1]), first_dt=float(p[8]), ni=int(p[9]),
                 pass_dt=float(p[10]) if p[10] != '-' else float('nan'), rejects=int(p[11]),
                 verr_s=float(p[12]), verr_l=float(p[13]), spd=float(p[14]), v2=float(p[15]), v5=float(p[16]), v10=float(p[17]),
                 hagl=float(p[7]))
        rows.append(r)
for name, sel in (("5 s or more", lambda r: r['len'] >= 5.0), ("under 5 s", lambda r: r['len'] < 5.0)):
    s = [r for r in rows if sel(r)]
    acc = [r for r in s if r['ni'] < 100]
    rej = [r for r in s if r['ni'] >= 100]
    print("%s: %d stretches, %.1f-%.1f s; first update accepted %d, rejected %d" % (
        name, len(s), min(r['len'] for r in s), max(r['len'] for r in s), len(acc), len(rej)))
    print("  time to first accepted update: max %.1f s; rejected cases: %s" % (
        max(r['pass_dt'] for r in s), ', '.join('%s %.1f s tilt: %d rejects, %.1f s' % (r['log'][:5], r['len'], r['rejects'], r['pass_dt']) for r in rej)))
    print("  verr at level %.1f-%.1f m/s (start of stretch %.1f-%.1f), +2 s %.1f-%.1f, +10 s %.1f-%.1f" % (
        min(r['verr_l'] for r in s), max(r['verr_l'] for r in s), min(r['verr_s'] for r in s), max(r['verr_s'] for r in s),
        min(r['v2'] for r in s), max(r['v2'] for r in s), min(r['v10'] for r in s), max(r['v10'] for r in s)))
    print("  accepted first with verr at level over 8 m/s: %s" % ', '.join(
        '%s %.1f s: %.1f m/s at HAGL %.0f m, NI %d' % (r['log'][:5], r['len'], r['verr_l'], r['hagl'], r['ni']) for r in acc if r['verr_l'] > 8))
