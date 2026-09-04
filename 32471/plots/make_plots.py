#!/usr/bin/env python3
"""Regenerate the PR #32471 A/B plots from the SITL logs in data/.

Usage: python3 make_plots.py [data_dir] [out_dir]

Height error is the EKF's own height (XKF1.PD, core 0, positive down) against
simulator truth (SIM.Alt), both re-zeroed at the ARM event so the comparison is
of drift accumulated during the climb rather than of datum choice.

The accel bias is XKF2.AZ on core 0. On the platform runs it is read just before
arming: that is the value the filter carries into a flight where the platform
that produced it no longer exists.
"""
import os
import sys

try:
    from pymavlink import mavutil
except ImportError:
    sys.path.insert(0, '/home/andy/github/ardupilot-master/modules/mavlink')
    from pymavlink import mavutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ARMED_EV = 10

# dataviz reference palette, categorical slots assigned in fixed order.
# validate_palette.js "#2a78d6,#eb6834,#1baf7a" --mode light -> all checks pass,
# with a contrast WARN on the aqua slot, so every series is direct-labelled.
BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'
SURFACE = '#fcfcfb'
INK, INK2, GRID = '#0b0b0b', '#52514e', '#dcdbd6'


def read_run(path):
    """-> (t_arm, [(t, ekf_down)], [(t, true_alt)], [(t, az)])"""
    m = mavutil.mavlink_connection(path)
    t_arm = None
    ekf, truth, az = [], [], []
    while True:
        msg = m.recv_match(type=['EV', 'XKF1', 'SIM', 'XKF2'])
        if msg is None:
            break
        t = msg.TimeUS * 1e-6
        typ = msg.get_type()
        if typ == 'EV':
            if msg.Id == ARMED_EV and t_arm is None:
                t_arm = t
        elif typ == 'XKF1' and msg.C == 0:
            ekf.append((t, msg.PD))
        elif typ == 'XKF2' and msg.C == 0:
            az.append((t, msg.AZ))
        elif typ == 'SIM':
            truth.append((t, msg.Alt))
    if t_arm is None:
        raise SystemExit("no ARM event in %s" % path)
    return t_arm, ekf, truth, az


def height_error(path, window=35.0):
    """-> ([dt], [ekf_height - true_height]), both zeroed at arm"""
    t_arm, ekf, truth, _ = read_run(path)
    if not ekf or not truth:
        raise SystemExit("missing XKF1/SIM in %s" % path)

    def sample(series, tt):
        prev = None
        for (t, v) in series:
            if t > tt:
                break
            prev = v
        return prev

    pd0, alt0 = sample(ekf, t_arm), sample(truth, t_arm)
    xs, ys = [], []
    for (t, pd) in ekf:
        dt = t - t_arm
        if dt < 0 or dt > window:
            continue
        alt = sample(truth, t)
        if alt is None:
            continue
        xs.append(dt)
        ys.append((-(pd - pd0)) - (alt - alt0))
    return xs, ys


def accel_bias(path, before=40.0, after=25.0):
    t_arm, _, _, az = read_run(path)
    xs = [t - t_arm for (t, _) in az if -before <= t - t_arm <= after]
    ys = [v for (t, v) in az if -before <= t - t_arm <= after]
    return xs, ys


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8, alpha=0.9)
    ax.set_axisbelow(True)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)


def label_end(ax, xs, ys, text, color):
    """direct label at the end of a line - the relief the contrast WARN requires"""
    if not xs:
        return
    ax.annotate(text, xy=(xs[-1], ys[-1]), xytext=(6, 0),
                textcoords='offset points', color=color, fontsize=9.5,
                fontweight='semibold', va='center')


def plot_vrf(data, out):
    runs = [('feature off', 'vrf_off.BIN', BLUE),
            ('ACC_ZBIAS_LEARN=2', 'vrf_use.BIN', ORANGE),
            ('ACC_ZBIAS_LEARN=6', 'vrf_use_inhibit.BIN', AQUA)]
    fig, ax = plt.subplots(figsize=(10, 5.2), facecolor=SURFACE)
    style(ax)
    for label, fname, color in runs:
        xs, ys = height_error(os.path.join(data, fname))
        ax.plot(xs, ys, color=color, linewidth=2.0, label=label, solid_capstyle='round')
        label_end(ax, xs, ys, label, color)
    ax.axhline(0, color=INK2, linewidth=1.0, alpha=0.5)
    ax.set_xlabel('seconds after arming', color=INK2, fontsize=10)
    ax.set_ylabel('EKF height - truth (m)', color=INK2, fontsize=10)
    ax.set_title('Carrying the learned bias over cuts height error 3x',
                 color=INK, fontsize=13, fontweight='semibold', loc='left', pad=24)
    ax.annotate('SITL, vibration rectification present (SIM_ACC_VRF_Z = 0.15), 10 m climb',
                xy=(0, 1), xycoords='axes fraction', xytext=(0, 8),
                textcoords='offset points', color=INK2, fontsize=10, va='bottom')
    ax.set_xlim(0, 46)
    fig.tight_layout()
    fig.savefig(os.path.join(out, 'ab_vrf_height_error.png'), dpi=130, facecolor=SURFACE)
    plt.close(fig)


def plot_platform(data, out):
    runs = [('bit 2 clear', 'plat_bit2_clear.BIN', ORANGE),
            ('bit 2 set', 'plat_bit2_set.BIN', BLUE)]
    fig, ax = plt.subplots(figsize=(10, 5.2), facecolor=SURFACE)
    style(ax)
    for label, fname, color in runs:
        xs, ys = accel_bias(os.path.join(data, fname))
        ax.plot(xs, ys, color=color, linewidth=2.0, label=label, solid_capstyle='round')
        label_end(ax, xs, ys, label, color)
    ax.axvline(0, color=INK2, linewidth=1.2, linestyle=(0, (4, 3)), alpha=0.8)
    ax.annotate('arm', xy=(0, ax.get_ylim()[1]), xytext=(4, -12),
                textcoords='offset points', color=INK2, fontsize=9.5, va='top')
    ax.axhline(0, color=INK2, linewidth=1.0, alpha=0.5)
    ax.set_xlabel('seconds relative to arming', color=INK2, fontsize=10)
    ax.set_ylabel('EKF Z accel bias, XKF2.AZ (m/s/s)', color=INK2, fontsize=10)
    ax.set_title('Without bit 2 the EKF invents 0.99 m/s/s of accel bias',
                 color=INK, fontsize=13, fontweight='semibold', loc='left', pad=24)
    ax.annotate('SITL, armed on a platform accelerating at 1 m/s/s (SIM_PLAT_ACC_Z = -1)',
                xy=(0, 1), xycoords='axes fraction', xytext=(0, 8),
                textcoords='offset points', color=INK2, fontsize=10, va='bottom')
    ax.set_xlim(-42, 33)
    fig.tight_layout()
    fig.savefig(os.path.join(out, 'ab_platform_accel_bias.png'), dpi=130, facecolor=SURFACE)
    plt.close(fig)


def plot_summary(data, out):
    # worst |height error| over the 35s after arming, from the same runs
    bars = [('feature off', 'vrf_off.BIN', BLUE),
            ('ACC_ZBIAS_LEARN=2', 'vrf_use.BIN', ORANGE),
            ('ACC_ZBIAS_LEARN=6', 'vrf_use_inhibit.BIN', AQUA)]
    names, vals, colors = [], [], []
    for label, fname, color in bars:
        _, ys = height_error(os.path.join(data, fname))
        names.append(label)
        vals.append(max(abs(v) for v in ys))
        colors.append(color)
    fig, ax = plt.subplots(figsize=(10, 3.6), facecolor=SURFACE)
    style(ax)
    ax.grid(True, axis='y', color=SURFACE)
    y = range(len(names))
    ax.barh(list(y), vals, color=colors, height=0.55)
    ax.set_yticks(list(y))
    ax.set_yticklabels(names, color=INK, fontsize=10)
    ax.invert_yaxis()
    for i, v in enumerate(vals):
        ax.annotate('%.2f m' % v, xy=(v, i), xytext=(6, 0), textcoords='offset points',
                    va='center', color=INK, fontsize=10, fontweight='semibold')
    ax.set_xlabel('worst |EKF height - truth| in the 35 s after arming (m)',
                  color=INK2, fontsize=10)
    ax.set_xlim(0, max(vals) * 1.18)
    ax.set_title('Worst height error by configuration',
                 color=INK, fontsize=13, fontweight='semibold', loc='left', pad=24)
    ax.annotate('SITL, vibration rectification present (SIM_ACC_VRF_Z = 0.15)',
                xy=(0, 1), xycoords='axes fraction', xytext=(0, 8),
                textcoords='offset points', color=INK2, fontsize=10, va='bottom')
    fig.tight_layout()
    fig.savefig(os.path.join(out, 'ab_summary_worst_error.png'), dpi=130, facecolor=SURFACE)
    plt.close(fig)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    data = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, '..', 'data', 'ab-2026-09-04')
    out = sys.argv[2] if len(sys.argv) > 2 else here
    plot_vrf(data, out)
    plot_platform(data, out)
    plot_summary(data, out)
    print("wrote 3 plots to %s" % out)


if __name__ == '__main__':
    main()
