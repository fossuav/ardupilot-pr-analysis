#!/usr/bin/env python3
"""Regenerate the acro accel-Z bias figure for #32473.

Needs two Replay output BINs from log17, produced from a tree carrying this PR:

    # arm A, as flown: the DAL replays the flight's own inhibit events
    replay_sweep.py --label base --keep-dir <dir> log17.bin
    # arm B: NavEKF3::getInhibitAccelBiasLearning() patched to return false,
    # which removes only the acro inhibit and leaves the geometric gate alone
    replay_sweep.py --label noinhibit --keep-dir <dir> log17.bin

    ./make_plots.py --with-inhibit <dir>/base-log17.bin.BIN \
                    --without-inhibit <dir>/noinhibit-log17.bin.BIN

The flight itself is resolved by name through ../../find_log.py, so set
AP_LOG_ROOTS; its fingerprints are private (see REPLAY_LOGS.md).
"""
import argparse, os, subprocess, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pymavlink import mavutil

HERE = os.path.dirname(os.path.abspath(__file__))
FINDLOG = os.path.join(HERE, "..", "..", "find_log.py")
LOGS = {"log17.bin": ("3408138", "543")}

# validated categorical slots 1-2 (see the data-viz palette); ink and grid are text tokens
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#c9c8c3"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK,
                     "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})

ACRO_MODE_NUM = 1  # Copter ACRO


def style(ax):
    ax.grid(alpha=.25, lw=.6, color=GRID)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def series(path, core):
    """XKF2.AZ for one core, plus the ACRO window, on one clock.

    Zero is the first message of ANY type, which is what log_extract.py does;
    zeroing on the first XKF2 instead shifts the clock by however long the log
    ran before the EKF started and silently windows the wrong samples.
    The ACRO span is read from this file's own MODE records for the same reason.
    """
    m = mavutil.mavlink_connection(path)
    t, az, t0 = [], [], None
    acro_from = acro_to = None
    while True:
        msg = m.recv_match(type=["XKF2", "MODE"])
        if msg is None:
            break
        ts = getattr(msg, "TimeUS", None)
        if ts is None:
            continue
        ts *= 1e-6
        if t0 is None:
            t0 = ts
        ts -= t0
        if msg.get_type() == "MODE":
            if int(getattr(msg, "ModeNum", -1)) == ACRO_MODE_NUM:
                if acro_from is None:
                    acro_from = ts
            elif acro_from is not None and acro_to is None:
                acro_to = ts
        elif int(getattr(msg, "C", -1)) == core:
            t.append(ts)
            az.append(msg.AZ)
    return np.array(t), np.array(az), (acro_from, acro_to)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-inhibit", required=True)
    ap.add_argument("--without-inhibit", required=True)
    ap.add_argument("--core", type=int, default=100, help="replayed core (C+100)")
    ap.add_argument("--out", default=os.path.join(HERE, "acro_zbias_ab.png"))
    a = ap.parse_args()

    t_on, az_on, span = series(a.with_inhibit, a.core)
    t_off, az_off, span_off = series(a.without_inhibit, a.core)
    if span != span_off:
        raise SystemExit("arms disagree on the ACRO span: %s vs %s" % (span, span_off))
    ACRO_FROM, ACRO_TO = span
    if len(t_on) == 0 or len(t_off) == 0:
        raise SystemExit("no XKF2 for core %d; Replay writes re-run cores at C+100" % a.core)

    fig, ax = plt.subplots(figsize=(9, 3.6), dpi=150)
    ax.axvspan(ACRO_FROM, ACRO_TO, color=GRID, alpha=.30, lw=0)
    ax.plot(t_off, az_off, lw=2, color=ORANGE, label="learning left on")
    ax.plot(t_on, az_on, lw=2, color=BLUE, label="inhibit held (as flown)")
    # after the plots, so the limits are the ones the data set
    ax.annotate("ACRO, %.0f s" % (ACRO_TO - ACRO_FROM),
                xy=((ACRO_FROM + ACRO_TO) / 2, ax.get_ylim()[1]),
                xytext=(0, -6), textcoords="offset points",
                ha="center", va="top", color=INK2, fontsize=8)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("accel Z bias (m/s2)")
    ax.set_title("SFD-O4 log17: accel-Z bias through 134 s of acro, same sensor stream")
    ax.legend(frameon=False, loc="best")
    style(ax)
    fig.tight_layout()
    fig.savefig(a.out)
    print("wrote %s" % a.out)

    for name, t, az in (("inhibit held", t_on, az_on), ("learning on", t_off, az_off)):
        m = (t >= ACRO_FROM) & (t <= ACRO_TO)
        if m.any():
            print("%-14s acro: mean %+.4f  std %.4f  range %+.3f..%+.3f  drift %+.4f"
                  % (name, az[m].mean(), az[m].std(), az[m].min(), az[m].max(),
                     az[m][-1] - az[m][0]))


if __name__ == "__main__":
    main()
