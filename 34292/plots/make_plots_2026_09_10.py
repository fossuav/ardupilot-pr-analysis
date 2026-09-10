#!/usr/bin/env python3
"""Regenerate the discard-vs-zero plot from data/ab-2026-09-10-discard.

Three arms, all translating in ALT_HOLD at about 2.7 m on flow-only nav
with FLOW_HGT_MIN well above the vehicle, so the focus height check is
active for the whole window:

  zero_floor5       946708d630, the PR head: the sample is zeroed and fused
  discard_floor5    126cf753c7, this round: the sample is discarded
  discard_flooroff  126cf753c7 with FLOW_HGT_MIN=0, the control

The point of the figure is that neither floor arm tracks truth. Discarding
roughly doubles the tracked fraction and makes the filter admit it has lost
aiding (shaded), where zeroing keeps reporting healthy flow aiding on a
measurement it did not take.

Usage: python3 make_plots_2026_09_10.py
"""
import csv
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data', 'ab-2026-09-10-discard')

ARMS = [
    ('zero_floor5', 'zeroed (946708d630)', 'tab:red'),
    ('discard_floor5', 'discarded (126cf753c7)', 'tab:green'),
    ('discard_flooroff', 'floor off, control', 'tab:blue'),
]


def load(name):
    with open(os.path.join(DATA, name + '.csv')) as f:
        f.readline()  # provenance header
        rows = list(csv.DictReader(f))

    # the level translating phase only: the two floor arms fail their
    # land_and_disarm, and the descent would otherwise be swept in
    t_end, airborne = None, False
    for r in rows:
        d = float(r['rng_m']) if r['rng_m'] else 0.0
        if d > 2.5:
            airborne = True
        elif airborne and d < 2.0:
            t_end = float(r['t_s'])
            break

    t, truth, est, cp = [], [], [], []
    for r in rows:
        ts = float(r['t_s'])
        if t_end is not None and ts > t_end:
            break
        d = float(r['rng_m']) if r['rng_m'] else None
        if d is None or not (2.0 <= d <= 4.0):
            continue
        t.append(ts)
        truth.append(float(r['truth_speed_ms']))
        est.append(float(r['ekf_speed_ms']))
        cp.append(int(r['const_pos']) if r['const_pos'] else 0)
    t0 = t[0]
    return [x - t0 for x in t], truth, est, cp


def main():
    fig, axes = plt.subplots(len(ARMS), 1, figsize=(9, 8), sharex=True)
    for ax, (name, label, colour) in zip(axes, ARMS):
        t, truth, est, cp = load(name)
        moving = [(a, b) for a, b in zip(truth, est) if a > 1.0]
        ratio = (sum(b for _, b in moving) / sum(a for a, _ in moving))

        ax.fill_between(t, 0, max(truth) * 1.1, where=[c == 1 for c in cp],
                        color='grey', alpha=0.18, linewidth=0)
        ax.plot(t, truth, color='black', linewidth=1.2, label='truth (SIM2)')
        ax.plot(t, est, color=colour, linewidth=1.4,
                label='EKF (XKF1 core 0)')
        ax.set_ylabel('speed (m/s)')
        ax.set_title('%s - EKF tracks %.0f%% of truth above 1 m/s'
                     % (label, 100 * ratio), fontsize=10)
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(alpha=0.3)
        ax.set_ylim(0, max(truth) * 1.1)

    axes[-1].set_xlabel('seconds into the level translating phase')
    fig.suptitle('FLOW_HGT_MIN=5.0 while translating below the floor\n'
                 'shaded: EKF in constant position mode (XKF4.SS bit 7)',
                 fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    out = os.path.join(HERE, 'flow_hgt_min_discard_2026_09_10.png')
    fig.savefig(out, dpi=130)
    print('wrote %s' % out)


if __name__ == '__main__':
    main()
