#!/usr/bin/env python3
"""Regenerate the FLOW_HGT_MIN A/B plot from data/ab-2026-09-05.

Three arms of Copter.OpticalFlowFocusHeight, all hovering at 2.00 m on
flow-only nav with SIM_FLOW_OFS_X=1.0 injected as bad flow:

  floor_3m    FLOW_HGT_MIN=3.0, above the hover height, so the floor fires
  floor_off   FLOW_HGT_MIN=0,   the feature disabled: master's behaviour
  floor_1m    FLOW_HGT_MIN=1.0, below the hover height, so it must not fire

Taken at branch head 84ec31a99d on 2026-09-05.

The CSVs hold XKF1 core 0 only. To regenerate them, run
  Tools/autotest/autotest.py test.Copter.OpticalFlowFocusHeight
and extract from the three flight logs it leaves in logs/ (see the
Reproduce section of ../README.md).

Usage: python3 make_plots.py
"""
import csv
import math
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data', 'ab-2026-09-05')

ARMS = [
    ('floor_3m',  'FLOW_HGT_MIN=3.0 (floor active)',            'tab:green'),
    ('floor_off', 'FLOW_HGT_MIN=0 (disabled, master)',          'tab:red'),
    ('floor_1m',  'FLOW_HGT_MIN=1.0 (set below the vehicle)',   'tab:orange'),
]


def load(name):
    path = os.path.join(DATA, name + '.csv')
    with open(path) as f:
        header = f.readline()
        meta = dict(tok.split('=', 1) for tok in header.lstrip('#').split()
                    if '=' in tok)
        rows = list(csv.DictReader(f))
    t_on = float(meta['inject_on_s'])
    t_off = float(meta['inject_off_s'])
    t, spd = [], []
    for r in rows:
        ts = float(r['t_s'])
        if not (t_on <= ts <= t_off):
            continue
        t.append(ts - t_on)
        spd.append(math.hypot(float(r['VN']), float(r['VE'])))
    return t, spd


def main():
    fig, ax = plt.subplots(figsize=(9, 5))
    for name, label, colour in ARMS:
        t, spd = load(name)
        ax.plot(t, spd, color=colour, linewidth=1.4,
                label='%s - peak %.2f m/s' % (label, max(spd)))

    ax.axhline(0.5, color='grey', linestyle=':', linewidth=1)
    ax.axhline(0.8, color='grey', linestyle=':', linewidth=1)
    ax.text(0.2, 0.52, 'test upper bound, floor active', fontsize=7,
            color='grey')
    ax.text(0.2, 0.82, 'test lower bound, floor inactive', fontsize=7,
            color='grey')

    ax.set_xlabel('seconds since SIM_FLOW_OFS_X=1.0 injected')
    ax.set_ylabel('EKF horizontal speed, XKF1 core 0 (m/s)')
    ax.set_title('FLOW_HGT_MIN: bad flow at a 2.00 m hover on flow-only nav\n'
                 'branch head 84ec31a99d, 2026-09-05')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    out = os.path.join(HERE, 'flow_hgt_min_ab_2026_09_05.png')
    fig.savefig(out, dpi=130)
    print('wrote %s' % out)


if __name__ == '__main__':
    main()
