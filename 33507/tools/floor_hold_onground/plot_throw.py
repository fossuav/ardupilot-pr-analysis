#!/usr/bin/env python3
"""One replayed throw: AGL KF height against the range finder, and the flow innovation, for this
PR (A) and a floor hold keyed on onGround alone (R).

  plot_throw.py IDX OUT.png [BEFORE_S AFTER_S]

Time is from the throw being detected (the log's NOT_LANDED event that ends the carry).
"""
import math
import os
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare  # noqa: E402

idx, out = sys.argv[1], sys.argv[2]
before = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0
after = float(sys.argv[4]) if len(sys.argv) > 4 else 4.0
which = int(sys.argv[5]) if len(sys.argv) > 5 else 0

HERE = os.path.dirname(os.path.abspath(__file__))
A = compare.load(os.path.join(HERE, 'run', 'A', idx, 'logs', '00000001.BIN'))
R = compare.load(os.path.join(HERE, 'run', 'R', idx, 'logs', '00000001.BIN'))
carries = [p for p in compare.periods(A) if p[3]]
carries = [p for p in carries if compare.median([r[1] for r in compare.window(A['rf'], p[0], p[1]) if r[2] == 4]) > 0.5]
t0, t1, _, _ = carries[which]
lo, hi = max(t0, t1 - before) - 1.0, t1 + after

SURFACE = '#fcfcfb'
INK = '#0b0b0b'
INK2 = '#52514e'
GRID = '#e4e3df'
REF = '#8a8984'
PR = '#2a78d6'
ONG = '#eb6834'

plt.rcParams.update({'font.size': 10, 'axes.edgecolor': GRID, 'axes.labelcolor': INK2,
                     'xtick.color': INK2, 'ytick.color': INK2, 'text.color': INK})
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True, gridspec_kw={'height_ratios': [3, 2]},
                               facecolor=SURFACE)
for ax in (ax1, ax2):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    ax.axvspan(max(t0, lo) - t1, 0, color='#efeeea', zorder=0)
    ax.axvline(0, color=INK2, linewidth=1, linestyle=(0, (3, 3)))

rf = [(t - t1, d) for t, d, st in A['rf'] if lo <= t <= hi and st == 4]
ax1.plot([x for x, _ in rf], [d for _, d in rf], 'o', color=REF, markersize=3, label='Range finder (Good readings)')
for d, col, name in ((A, PR, 'This PR'), (R, ONG, 'Hold on onGround alone')):
    pts = [(t - t1, h) for t, h, _ in d['xkfa'] if lo <= t <= hi]
    ax1.plot([x for x, _ in pts], [h for _, h in pts], color=col, linewidth=2, label=name)
    fi = [(t - t1, math.hypot(fx, fy) * 0.001) for t, fx, fy in d['xkf5'] if lo <= t <= hi]
    ax2.plot([x for x, _ in fi], [v for _, v in fi], color=col, linewidth=1.5, label=name)

ax1.set_ylabel('Height above ground (m)')
ax1.set_ylim(bottom=0)
ax1.text((max(t0, lo) - t1) + 0.15, ax1.get_ylim()[1] * 0.95, 'carried, vehicle reports landed',
         color=INK2, va='top', fontsize=9)
ax1.text(-0.1, ax1.get_ylim()[1] * 0.95, 'throw detected', color=INK2, va='top', ha='right', fontsize=9)
ax1.legend(loc='lower left', frameon=False, bbox_to_anchor=(0.0, 1.0), ncol=3, borderaxespad=0.2)
ax2.set_ylabel('Flow innovation (rad/s)')
ax2.set_xlabel('Time from throw detected (s)')
ax2.set_ylim(bottom=0)
fig.suptitle('AGL KF height through a hand-launched throw: this PR against a floor hold on onGround',
             x=0.01, ha='left', fontsize=11, color=INK)
fig.text(0.01, 0.925, 'Replay of a real throw, the landed flag taken from the log\'s LAND_COMPLETE / NOT_LANDED events',
         fontsize=9, color=INK2, ha='left')
fig.tight_layout(rect=(0, 0, 1, 0.91))
fig.savefig(out, dpi=130, facecolor=SURFACE)
print("carry %.1f-%.1f s, plotted %.1f to %.1f s" % (t0, t1, lo - t1, hi - t1))
