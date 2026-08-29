#!/usr/bin/env python3
"""Regenerate the PR #34210 A/B plot from the SITL BINs in ../data/.

Both BINs are the LandFailsafeRunaway autotest: no GPS (EK3_SRC1_POSXY/VELXY/
VELZ = 0), take-off in AltHold to 20 m, RC failsafe into LAND (FS_THR_ENABLE=3),
then SIM_ACC1/2/3_BIAS_Z = 3 m/s2 so the accelerometers report a descent that
is not happening. option_off.BIN has LAND_FS_OPTIONS = 0, option_on.BIN has
bit 0 set.

Three panels, aligned on LAND entry (MODE.ModeNum == 9):
  1) baro altitude relative to the hover, full scale (the fly-away)
  2) the same, zoomed to the protected run and its 10 m latch threshold
  3) throttle out (CTUN.ThO)

Usage: python3 plots/make_plots.py    (run from the 34210/ directory)
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pymavlink import mavutil

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')
COL = {'off': '#eb6834', 'on': '#2a78d6'}
LABEL = {'off': 'LAND_FS_OPTIONS = 0', 'on': 'LAND_FS_OPTIONS = 1'}
SURF, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e6e5e1'


def load(path):
    m = mavutil.mavlink_connection(path)
    t, balt, tho, land_t = [], [], [], None
    while True:
        msg = m.recv_match(blocking=False)
        if msg is None:
            break
        ty = msg.get_type()
        if ty == 'CTUN':
            t.append(msg.TimeUS / 1e6); balt.append(msg.BAlt); tho.append(msg.ThO)
        elif ty == 'MODE' and msg.ModeNum == 9 and land_t is None:
            land_t = msg.TimeUS / 1e6
    t, balt, tho = (np.array(x, dtype=float) for x in (t, balt, tho))
    t = t - land_t
    ref = balt[(t > -5) & (t < 0)].mean()
    return t, balt - ref, tho


def main():
    data = {v: load(os.path.join(DATA, 'option_%s.BIN' % v)) for v in ('off', 'on')}

    plt.rcParams.update({'font.size': 10, 'text.color': INK, 'axes.labelcolor': INK2,
                         'xtick.color': INK2, 'ytick.color': INK2, 'axes.edgecolor': GRID})
    fig, axes = plt.subplots(3, 1, figsize=(9, 8.5), sharex=True, facecolor=SURF)
    fig.suptitle('RC-failsafe LAND with a corrupt vertical estimate (SITL, no GPS, +3 m/s2 accel-Z bias injected at t=2 s)',
                 fontsize=10.5, color=INK)

    ax = axes[0]
    for v in ('off', 'on'):
        t, alt, _ = data[v]
        m = (t >= -5) & (t <= 75)
        ax.plot(t[m], alt[m], color=COL[v], lw=2, label=LABEL[v])
    ax.set_ylabel('baro altitude above hover (m)')
    ax.set_title('full scale: the fly-away', loc='left', fontsize=10, color=INK2)
    t, alt, _ = data['off']
    i = int(np.argmin(np.abs(t - 75)))
    ax.annotate('+%.0f m at 75 s, throttle saturated' % alt[i], (t[i], alt[i]), xytext=(-8, -14),
                textcoords='offset points', ha='right', va='top', fontsize=9, color=INK2)
    ax.legend(frameon=False, loc='upper left')

    ax = axes[1]
    for v in ('off', 'on'):
        t, alt, _ = data[v]
        m = (t >= -5) & (t <= 75)
        ax.plot(t[m], alt[m], color=COL[v], lw=2)
    ax.axhline(10, color=INK2, lw=1, ls=':')
    ax.text(74, 10.6, '10 m latch threshold', ha='right', fontsize=9, color=INK2)
    ax.set_ylim(-25, 30)
    ax.set_ylabel('baro altitude above hover (m)')
    ax.set_title('zoomed: with the option the ceiling latches at +10 m and the vehicle is brought down and lands',
                 loc='left', fontsize=10, color=INK2)
    t, alt, _ = data['on']
    j = int(np.argmax(alt))
    ax.annotate('peak +%.1f m' % alt[j], (t[j], alt[j]), xytext=(10, 6), textcoords='offset points', fontsize=9, color=INK2)
    k = np.where((t > 0) & (alt < -19))[0]
    if len(k):
        ax.annotate('on the ground', (t[k[0]], alt[k[0]]), xytext=(10, 6), textcoords='offset points', fontsize=9, color=INK2)

    ax = axes[2]
    for v in ('off', 'on'):
        t, _, tho = data[v]
        m = (t >= -5) & (t <= 75)
        ax.plot(t[m], tho[m], color=COL[v], lw=2)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel('throttle out')
    ax.set_xlabel('time since LAND entry (s)')
    ax.set_title('throttle: the governed ceiling replaces a saturated demand and winds the motors down on the ground',
                 loc='left', fontsize=10, color=INK2)

    for ax in axes:
        ax.set_facecolor(SURF)
        ax.grid(True, color=GRID, lw=0.8)
        ax.spines[['top', 'right']].set_visible(False)
        ax.set_xlim(-5, 75)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = os.path.join(HERE, 'A_runaway_ab.png')
    fig.savefig(out, dpi=130, facecolor=SURF)
    for v in ('off', 'on'):
        t, alt, _ = data[v]
        m = (t >= 0) & (t <= 75)
        print('option %-3s peak +%.1f m, at 75 s %+.1f m' % (v, alt[m].max(), alt[m][-1]))
    print('saved', out)


if __name__ == '__main__':
    main()
