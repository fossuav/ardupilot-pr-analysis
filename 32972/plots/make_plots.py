#!/usr/bin/env python3
"""Regenerate the PR #32972 A/B plots from the SITL logs in data/.

Usage: python3 make_plots.py [data_dir] [out_dir]

Each run is one SITL flight; the EKF height is XKF1.PD (core 0, positive
down) plotted as -PD so up is up.  Time is re-zeroed at the ARM event.
GLOBAL_POSITION_INT/relative_alt is deliberately not used: AP_AHRS falls
back to the raw barometer whenever the EKF vertical position is
unhealthy, which is the state both of these runs create.
"""
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', 'ardupilot', 'modules', 'mavlink'))
try:
    from pymavlink import mavutil
except ImportError:
    sys.path.insert(0, '/home/andy/github/ardupilot/modules/mavlink')
    from pymavlink import mavutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ARMED_EV = 10


def read_run(path):
    """-> (t_arm_s, [(t,alt_ekf)], [(t,alt_baro)], [(t,alt_true)])"""
    m = mavutil.mavlink_connection(path)
    t_arm = None
    ekf, baro, truth = [], [], []
    while True:
        msg = m.recv_match(type=['EV', 'XKF1', 'BARO', 'SIM'])
        if msg is None:
            break
        t = msg.TimeUS * 1e-6
        typ = msg.get_type()
        if typ == 'EV':
            if msg.Id == ARMED_EV and t_arm is None:
                t_arm = t
        elif typ == 'XKF1' and msg.C == 0:
            ekf.append((t, -msg.PD))
        elif typ == 'BARO' and getattr(msg, 'I', 0) == 0:
            baro.append((t, msg.Alt))
        elif typ == 'SIM':
            truth.append((t, msg.Alt))
    if t_arm is None:
        raise SystemExit("no ARM event in %s" % path)
    return t_arm, ekf, baro, truth


def rezero(series, t0, tmax=None):
    out = [(t - t0, v) for (t, v) in series if t >= t0 - 2]
    if tmax is not None:
        out = [(t, v) for (t, v) in out if t <= tmax]
    return [p[0] for p in out], [p[1] for p in out]


def truth_rel(truth, t0, tmax):
    """SIM.Alt is AMSL; re-reference to its value at arm."""
    if not truth:
        return [], []
    base = min(truth, key=lambda p: abs(p[0] - t0))[1]
    t, v = rezero([(a, b - base) for (a, b) in truth], t0, tmax)
    return t, v


def plot_a(data, out):
    fig, ax = plt.subplots(figsize=(10, 5.2))
    runs = [
        ('A1_base_dz4',    'baseline (EK3_GND_EFF_DZ 4, today)', 'tab:red'),
        ('A2_branch_dzm5', 'this PR (EK3_GND_EFF_DZ -5)',        'tab:blue'),
    ]
    TMAX = 30
    for name, label, colour in runs:
        t_arm, ekf, baro, truth = read_run(data[name])
        t, v = rezero(ekf, t_arm, TMAX)
        ax.plot(t, v, colour, lw=1.8, label='EKF height, %s' % label)
        if name == runs[0][0]:
            tb, vb = rezero(baro, t_arm, TMAX)
            ax.plot(tb, vb, color='grey', lw=1.0, alpha=0.8,
                    label='barometer (both runs see the same spool-up dip)')
            tt, vt = truth_rel(truth, t_arm, TMAX)
            if tt:
                ax.plot(tt, vt, 'k--', lw=1.2, alpha=0.7, label='true altitude')
    ax.axvspan(0, 10, color='orange', alpha=0.10)
    ax.text(5, ax.get_ylim()[0], ' armed, idle, in ground effect',
            fontsize=8, va='bottom', color='darkorange')
    ax.axhline(0, color='k', lw=0.5, alpha=0.4)
    ax.set_xlabel('time since arm (s)')
    ax.set_ylabel('height above arm point (m)')
    ax.set_title('#32972 A: baro ground effect at takeoff (SIM_BARO_GEFF_M 5)')
    ax.grid(alpha=0.3)
    ax.annotate('baseline sags 0.85 m\nwhile still on the ground',
                xy=(11.5, -0.85), xytext=(14.5, -2.2), fontsize=8, color='tab:red',
                arrowprops=dict(arrowstyle='->', color='tab:red', lw=1))
    ax.legend(loc='lower right', fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out, 'ab_ground_effect_takeoff.png'), dpi=130)
    print('wrote ab_ground_effect_takeoff.png')


def plot_b(data, out):
    fig, ax = plt.subplots(figsize=(10, 5.2))
    runs = [
        ('B1_base',    'baseline: ResetHeight snaps onto the failed baro', 'tab:red'),
        ('B2_nobound', 'suppression, no bound: never recovers',            'tab:orange'),
        ('B3_branch',  'this PR: suppressed, then bounded reset',          'tab:blue'),
    ]
    TMAX = 45
    for name, label, colour in runs:
        t_arm, ekf, baro, truth = read_run(data[name])
        t, v = rezero(ekf, t_arm, TMAX)
        ax.plot(t, v, colour, lw=1.8, label=label)
        if name == 'B1_base':
            tb, vb = rezero(baro, t_arm, TMAX)
            ax.plot(tb, vb, color='grey', lw=1.4, ls=':', alpha=0.9,
                    label='barometer (fails 21.7 m low once the motors run)')
    ax.axhline(0, color='k', lw=0.5, alpha=0.4)
    ax.set_xlabel('time since arm (s)')
    ax.set_ylabel('EKF height above arm point (m)')
    ax.set_title('#32972 B: persistently failed baro in ground effect '
                 '(SIM_BARO_GEFF_M 30, vehicle never leaves the ground)')
    ax.annotate('bounded: 10 s to hgtTimeout,\n5 s window, reset at the next timeout',
                xy=(22, -14), xytext=(25.5, -18), fontsize=8, color='tab:blue',
                arrowprops=dict(arrowstyle='->', color='tab:blue', lw=1))
    ax.grid(alpha=0.3)
    ax.legend(loc='upper right', fontsize=8, framealpha=0.95)
    fig.tight_layout()
    fig.savefig(os.path.join(out, 'ab_reset_suppression_bound.png'), dpi=130)
    print('wrote ab_reset_suppression_bound.png')


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else 'data'
    out_dir = sys.argv[2] if len(sys.argv) > 2 else '.'
    data = {}
    for name in os.listdir(data_dir):
        if name.endswith('.BIN'):
            data[name[:-4]] = os.path.join(data_dir, name)
    missing = [k for k in ('A1_base_dz4', 'A2_branch_dzm5',
                           'B1_base', 'B2_nobound', 'B3_branch') if k not in data]
    if missing:
        raise SystemExit('missing runs: %s (have %s)' % (missing, sorted(data)))
    plot_a(data, out_dir)
    plot_b(data, out_dir)


if __name__ == '__main__':
    main()
