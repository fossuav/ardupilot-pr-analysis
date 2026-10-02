#!/usr/bin/env python3
"""Regenerate the AGL KF floor gate figure for the offset-correction fix.

The inputs are Replay outputs of real flights, which this public repo may not
carry. Produce them with the log-analyze skill's replay_sweep.py, once on the
branch with the gate testing the corrected reading and once with the fix:

    replay_sweep.py --label old --keep-dir <old> log22.bin log25.bin
    replay_sweep.py --label fix --keep-dir <fix> log22.bin log25.bin
    ./make_floor_gate_plots.py --old22 <old>/old-log22.bin.BIN --fix22 <fix>/fix-log22.bin.BIN \
                               --old25 <old>/old-log25.bin.BIN --fix25 <fix>/fix-log25.bin.BIN

Core 101 is the re-run flow-only lane. Takeoff times are NOT_LANDED in each
log, on the log's own clock (first message of any type is zero).
"""
import argparse, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pymavlink import mavutil

HERE = os.path.dirname(os.path.abspath(__file__))
TAKEOFF = {"22": 129.44, "25": 51.7}

# validated categorical slots 1-2 (see 34457/plots/make_plots.py); ink and grid are text tokens
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#c9c8c3"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK,
                     "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})


def style(ax):
    ax.grid(alpha=.25, lw=.6, color=GRID)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def read(path):
    m = mavutil.mavlink_connection(path)
    t0 = None
    X, A, R = [], [], []
    while True:
        msg = m.recv_match()
        if msg is None:
            break
        tus = getattr(msg, 'TimeUS', None)
        if tus is None:
            continue
        if t0 is None:
            t0 = tus
        t = (tus - t0) * 1e-6
        ty = msg.get_type()
        if ty == 'XKF1' and msg.C == 101:
            X.append((t, msg.PD))
        elif ty == 'XKFA' and msg.C == 101:
            A.append((t, msg.BiasStd))
        elif ty == 'RFND' and msg.Instance == 0:
            R.append((t, msg.Dist))
    return np.array(X), np.array(A), np.array(R)


def height_error(X, R, tko, dt):
    p0 = np.interp(tko - 0.5, X[:, 0], X[:, 1])
    return -(np.interp(tko + dt, X[:, 0], X[:, 1]) - p0) - np.interp(tko + dt, R[:, 0], R[:, 1])


def main():
    ap = argparse.ArgumentParser()
    for k in ("old22", "fix22", "old25", "fix25"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "aglkf_floor_gate_offset.png"))
    a = ap.parse_args()

    fig, axs = plt.subplots(2, 2, figsize=(10, 6.2))
    for col, n in enumerate(("22", "25")):
        tko = TAKEOFF[n]
        for arm, path, colour, label in (("old", getattr(a, "old" + n), ORANGE, "gate on the corrected reading"),
                                         ("fix", getattr(a, "fix" + n), BLUE, "gate on the reading before correction")):
            X, A, R = read(path)
            k = A[:, 0] < tko + 20
            axs[0, col].plot(A[k, 0] - tko, A[k, 1], color=colour, lw=2, label=label)
            dt = np.arange(0, 18, 0.1)
            e = height_error(X, R, tko, dt)
            axs[1, col].plot(dt, e, color=colour, lw=2, label=label)
            print("log%s %s: bias std at liftoff %.3f, worst flow lane - range finder %+.2f m" %
                  (n, arm, np.interp(tko, A[:, 0], A[:, 1]), e[np.argmax(np.abs(e))]))
        ax = axs[0, col]
        ax.set_yscale('log')
        ax.axvline(0, color=INK2, lw=.8, ls='--')
        ax.text(0.5, 0.02, "liftoff", color=INK2, fontsize=8, transform=ax.get_xaxis_transform())
        ax.set_title("log%s: AGL KF bias std, flow lane (Replay)" % n, loc='left', fontsize=10)
        ax.set_ylabel("bias std (m/s/s)")
        ax.set_xlim(-120 if n == "22" else -45, 20)
        ax.set_xlabel("time from liftoff (s)")
        style(ax)
        ax = axs[1, col]
        ax.axhline(0, color=INK2, lw=.8)
        ax.set_title("log%s: flow lane height above takeoff - range finder" % n, loc='left', fontsize=10)
        ax.set_ylabel("error (m)")
        ax.set_xlim(0, 18)
        ax.set_xlabel("time from liftoff (s)")
        style(ax)
    axs[0, 0].legend(loc='center left', frameon=False, fontsize=8)
    fig.suptitle("SFD-O4, RNGFND1_POS_X -0.03: the floor gate never closed while the offset correction "
                 "moved the on-ground reading off the floor", fontsize=10, color=INK, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(a.out, dpi=130)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
