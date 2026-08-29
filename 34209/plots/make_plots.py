#!/usr/bin/env python3
"""Regenerate the PR #34209 A/B plot from the SITL BINs in ../data/.

Both BINs are the EK3NoAidAccelBiasXY autotest's unaided flight: no GPS,
EK3_SRC1_POSXY/VELXY/VELZ = 0, a speed-squared baro static-port error
(SIM_BARO_WCF_FWD/BAK = 1.0), take-off in AltHold to 20 m, eight 8 s forward
pushes with 8 s level between them, then a 20 s hover. unaided_master.BIN is
master; unaided_fixed.BIN has the CovariancePrediction change.

Three panels, aligned on the first push (RCIN.C2 pitch stick):
  1) baro altitude relative to the hover (the dips are the static-port error)
  2) learned X accel bias, core 0 (XKF2.AX), master vs fixed
  3) pitch error against simulator truth (ATT.Pitch - SIM.Pitch)

Usage: python3 plots/make_plots.py    (run from the 34209/ directory)
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pymavlink import mavutil

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
COL = {'master': '#eb6834', 'fixed': '#2a78d6'}
SURF, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e6e5e1'


def load(path):
    m = mavutil.mavlink_connection(path)
    tb, bias, ta, patt, ts, psim, tr, rc2, tc, balt = ([] for _ in range(10))
    while True:
        msg = m.recv_match(blocking=False)
        if msg is None:
            break
        t = msg.get_type()
        if t == 'XKF2' and msg.C == 0:
            tb.append(msg.TimeUS / 1e6); bias.append(msg.AX)
        elif t == 'ATT':
            ta.append(msg.TimeUS / 1e6); patt.append(msg.Pitch)
        elif t == 'SIM':
            ts.append(msg.TimeUS / 1e6); psim.append(msg.Pitch)
        elif t == 'RCIN':
            tr.append(msg.TimeUS / 1e6); rc2.append(msg.C2)
        elif t == 'CTUN':
            tc.append(msg.TimeUS / 1e6); balt.append(msg.BAlt)
    tb, bias, ta, patt, ts, psim, tr, rc2, tc, balt = (np.array(x, dtype=float) for x in
                                                        (tb, bias, ta, patt, ts, psim, tr, rc2, tc, balt))
    perr = patt - np.interp(ta, ts, psim)
    t0 = tr[np.argmax(rc2 < 1400)]     # first forward push
    return dict(tb=tb - t0, bias=bias, ta=ta - t0, perr=perr, tc=tc - t0, balt=balt)


def main():
    data = {'master': load(os.path.join(DATA, 'unaided_master.BIN')),
            'fixed': load(os.path.join(DATA, 'unaided_fixed.BIN'))}

    plt.rcParams.update({'font.size': 10, 'text.color': INK, 'axes.labelcolor': INK2,
                         'xtick.color': INK2, 'ytick.color': INK2, 'axes.edgecolor': GRID})
    fig, axes = plt.subplots(3, 1, figsize=(9, 8.5), sharex=True, facecolor=SURF)
    fig.suptitle('Unaided flight (SITL, no GPS, baro static-port error): eight forward pushes, then hover',
                 fontsize=10.5, color=INK)

    ax = axes[0]
    d = data['fixed']
    ref = d['balt'][(d['tc'] > -5) & (d['tc'] < 0)].mean()
    ax.plot(d['tc'], d['balt'] - ref, color=INK2, lw=2)
    ax.set_ylabel('baro altitude (m, rel.)')
    ax.set_ylim(-1.5, 1.5)
    ax.set_title('the baro dips with airspeed on every push and recovers when level', loc='left', fontsize=10, color=INK2)

    ax = axes[1]
    for v in ('master', 'fixed'):
        d = data[v]
        ax.plot(d['tb'], d['bias'], color=COL[v], lw=2, label=v if v == 'master' else 'with this change')
    ax.set_ylabel('learned accel X bias (m/s2)')
    ax.set_title('the level pushes rectify the tilt-coupled baro error into a body-X bias', loc='left', fontsize=10, color=INK2)
    d = data['master']
    ax.annotate('%.2f m/s2' % d['bias'][-1], (d['tb'][-1], d['bias'][-1]), xytext=(-6, 6),
                textcoords='offset points', ha='right', fontsize=9, color=INK2)
    ax.legend(frameon=False, loc='upper left')

    ax = axes[2]
    for v in ('master', 'fixed'):
        d = data[v]
        ax.plot(d['ta'], d['perr'], color=COL[v], lw=2)
    ax.set_ylabel('pitch error vs SIM truth (deg)')
    ax.set_xlabel('time since first push (s)')
    ax.set_title('and the level estimate tilts with it', loc='left', fontsize=10, color=INK2)
    ax.set_ylim(-4, 4)

    for ax in axes:
        ax.set_facecolor(SURF)
        ax.grid(True, color=GRID, lw=0.8)
        ax.spines[['top', 'right']].set_visible(False)
        ax.set_xlim(-10, 155)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = os.path.join(HERE, 'A_xy_bias_ab.png')
    fig.savefig(out, dpi=130, facecolor=SURF)
    for v in ('master', 'fixed'):
        d = data[v]
        hover = d['ta'] > d['ta'][-1] - 20
        print('%-7s final X bias %.2f m/s2, hover pitch error %.2f deg' % (v, d['bias'][-1], d['perr'][hover].mean()))
    print('saved', out)


if __name__ == '__main__':
    main()
