#!/usr/bin/env python3
"""Regenerate the PR #32270 VALT_POS_EXPO plot from the SITL BIN in ../data/.

valt_expo_ab.BIN is one run of the ModeVAltHold autotest. It holds both arms of
the blend A/B: the test climbs, holds the throttle stick full down for 5 s with
VALT_POS_EXPO = 0, climbs again, and repeats with VALT_POS_EXPO = 3.

The discriminating observable is PSCD.DPD (the desired position VALT writes)
against PSCD.PD (the estimate). With the hard cutoff, pos_desired is snapped to
the estimate on every loop the stick is off centre, so the two are identical.
With the blend, full deflection leaves pos_desired marching, which is the
position error that backstops a stuck velocity loop.

Two panels, each aligned on the start of its full-down hold:
  1) DPD and PD through the hold, for each arm
  2) |DPD - PD|, the quantity the autotest asserts on

Usage: python3 plots/make_plots.py    (run from the 32270/ directory)
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pymavlink import mavutil

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
BIN = os.path.join(DATA, 'valt_expo_ab.BIN')

COL = {0: '#eb6834', 3: '#2a78d6'}
LABEL = {0: 'VALT_POS_EXPO = 0 (hard cutoff)', 3: 'VALT_POS_EXPO = 3 (blend)'}
SURF, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e6e5e1'

HOLD_S = 5.0        # the test holds full down for 5 s
FULL_DOWN_PWM = 1050


def load():
    """Return {expo: (t_since_hold_start, DPD, PD)} for the two full-down holds."""
    m = mavutil.mavlink_connection(BIN)
    pscd, rcin, expo_changes = [], [], []
    while True:
        msg = m.recv_match(type=['PSCD', 'RCIN', 'PARM'])
        if msg is None:
            break
        ty = msg.get_type()
        if ty == 'PSCD':
            pscd.append((msg.TimeUS / 1e6, msg.DPD, msg.PD))
        elif ty == 'RCIN':
            rcin.append((msg.TimeUS / 1e6, msg.C3))
        elif ty == 'PARM' and msg.Name == 'VALT_POS_EXPO':
            expo_changes.append((msg.TimeUS / 1e6, float(msg.Value)))

    pscd = np.array(pscd, dtype=float)
    rcin = np.array(rcin, dtype=float)

    # the full-down holds the test makes: the two runs longer than 4 s that
    # follow a climb (earlier long full-down stretches are the RTL descents)
    holds, start, last = [], None, None
    for t, c in rcin:
        if c < FULL_DOWN_PWM:
            if start is None:
                start = t
            last = t
        else:
            if start is not None and 4.0 < last - start < 8.0:
                holds.append(start)
            start = None

    def expo_at(t):
        v = 0.0
        for ct, cv in expo_changes:
            if ct <= t:
                v = cv
        return v

    out = {}
    for h in holds:
        e = int(round(expo_at(h)))
        if e not in (0, 3):
            continue
        sel = (pscd[:, 0] >= h) & (pscd[:, 0] <= h + HOLD_S)
        out[e] = (pscd[sel, 0] - h, pscd[sel, 1], pscd[sel, 2])
    return out


def main():
    data = load()
    missing = [e for e in (0, 3) if e not in data]
    if missing:
        raise SystemExit('no full-down hold found for VALT_POS_EXPO=%s' % missing)

    plt.rcParams.update({'font.size': 10, 'text.color': INK, 'axes.labelcolor': INK2,
                         'xtick.color': INK2, 'ytick.color': INK2, 'axes.edgecolor': GRID})
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True, facecolor=SURF)
    fig.suptitle('VALT_POS_EXPO at full stick deflection (SITL, ModeVAltHold autotest, 5 s full-down hold)',
                 fontsize=10.5, color=INK)

    ax = axes[0]
    for e in (0, 3):
        t, _, pd = data[e]
        ax.plot(t, -(pd - pd[0]), color=COL[e], lw=2,
                label='%s (%.2f m in %.0f s)' % (LABEL[e], -(pd[-1] - pd[0]), HOLD_S))
    ax.set_ylabel('height lost during the hold (m)')
    ax.set_title('the commanded descent is unchanged by the blend',
                 loc='left', fontsize=10, color=INK2)
    ax.legend(frameon=False, loc='lower left', fontsize=8.5)

    ax = axes[1]
    for e in (0, 3):
        t, dpd, pd = data[e]
        err = np.abs(dpd - pd)
        ax.plot(t, err, color=COL[e], lw=2, label='%s (mean %.4f m)' % (LABEL[e], err.mean()))
    ax.axhline(0.02, color=INK2, lw=1, ls=':')
    ax.text(HOLD_S - 0.1, 0.0215, 'autotest gate 0.02 m', ha='right', fontsize=9, color=INK2)
    ax.set_ylabel('|DPD - PD| (m)')
    ax.set_xlabel('time since the stick reached full down (s)')
    ax.set_title('the position error the backstop depends on; zero by construction with the hard cutoff',
                 loc='left', fontsize=10, color=INK2)
    ax.legend(frameon=False, loc='upper left', fontsize=8.5)

    for ax in axes:
        ax.set_facecolor(SURF)
        ax.grid(True, color=GRID, lw=0.8)
        ax.spines[['top', 'right']].set_visible(False)
        ax.set_xlim(0, HOLD_S)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = os.path.join(HERE, 'A_valt_pos_expo_ab.png')
    fig.savefig(out, dpi=130, facecolor=SURF)
    for e in (0, 3):
        t, dpd, pd = data[e]
        err = np.abs(dpd - pd)
        print('VALT_POS_EXPO=%d  mean |DPD-PD| %.4f m  max %.4f m  (%d samples)'
              % (e, err.mean(), err.max(), len(err)))
    print('saved', out)


if __name__ == '__main__':
    main()
