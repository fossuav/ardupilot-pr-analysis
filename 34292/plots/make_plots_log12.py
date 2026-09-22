#!/usr/bin/env python3
"""Regenerate the log12 FLOW_HGT_MIN flight figure for #34292.

Needs two Replay output BINs from log12, produced from a tree carrying this PR:

    # arm A, as flown: FLOW_HGT_MIN 2.0 m, flow discarded below the floor
    replay_sweep.py --label base --keep-dir <dir> log12.bin
    # arm B: minHeight forced to rngOnGnd + 0.05, i.e. the floor cut to the
    # ground clearance, so flow fuses all the way down
    replay_sweep.py --label nofloor --keep-dir <dir> log12.bin

    ./make_plots_log12.py --floor-on <dir>/base-log12.bin.BIN \
                          --floor-off <dir>/nofloor-log12.bin.BIN

The flight is resolved by name through ../../find_log.py, so set AP_LOG_ROOTS;
its fingerprints are private (see REPLAY_LOGS.md).
"""
import argparse, math, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pymavlink import mavutil

HERE = os.path.dirname(os.path.abspath(__file__))
LOGS = {"log12.bin": ("3408138", "532")}

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#c9c8c3"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK,
                     "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})

FLOOR_M = 2.0


def style(ax):
    ax.grid(alpha=.25, lw=.6, color=GRID)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def read(path, core):
    """Replayed XKF1 velocity for one core, GPS velocity and RFND, one clock."""
    m = mavutil.mavlink_connection(path)
    ekf, gps, rng, t0 = [], [], [], None
    while True:
        msg = m.recv_match(type=["XKF1", "GPS", "RFND"])
        if msg is None:
            break
        ts = msg.TimeUS * 1e-6
        if t0 is None:
            t0 = ts
        ts -= t0
        ty = msg.get_type()
        if ty == "XKF1" and int(getattr(msg, "C", -1)) == core:
            ekf.append((ts, msg.VN, msg.VE))
        elif ty == "GPS" and int(getattr(msg, "I", 0)) == 0:
            crs = math.radians(msg.GCrs)
            ekf_ok = getattr(msg, "Status", 3) >= 3
            if ekf_ok:
                gps.append((ts, msg.Spd * math.cos(crs), msg.Spd * math.sin(crs)))
        elif ty == "RFND" and int(getattr(msg, "I", 0)) == 0:
            rng.append((ts, msg.Dist))
    return (np.array(ekf), np.array(gps), np.array(rng))


def velerr(ekf, gps):
    if len(ekf) == 0 or len(gps) == 0:
        return np.array([]), np.array([])
    vn = np.interp(gps[:, 0], ekf[:, 0], ekf[:, 1])
    ve = np.interp(gps[:, 0], ekf[:, 0], ekf[:, 2])
    return gps[:, 0], np.hypot(vn - gps[:, 1], ve - gps[:, 2])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--floor-on", required=True)
    ap.add_argument("--floor-off", required=True)
    ap.add_argument("--core", type=int, default=101, help="replayed flow core (C+100)")
    # log12 sat armed on the ground for 487 s before flying, so an unwindowed
    # comparison is dominated by ground dwell rather than by the descent this
    # parameter is about. NOT_LANDED and LAND_COMPLETE from the flight's events.
    ap.add_argument("--flight-from", type=float, default=501.4)
    ap.add_argument("--flight-to", type=float, default=590.2)
    ap.add_argument("--out", default=os.path.join(HERE, "flow_hgt_min_log12.png"))
    a = ap.parse_args()

    on = read(a.floor_on, a.core)
    off = read(a.floor_off, a.core)
    t_on, e_on = velerr(on[0], on[1])
    t_off, e_off = velerr(off[0], off[1])
    rng = on[2]

    fig, axes = plt.subplots(2, 1, figsize=(9, 5.6), dpi=150, sharex=True,
                             gridspec_kw={"height_ratios": [1, 1.3]})
    ax = axes[0]
    if len(rng):
        ax.plot(rng[:, 0], rng[:, 1], lw=1.5, color=INK2)
        ax.axhline(FLOOR_M, lw=1.5, ls="--", color=ORANGE)
        ax.annotate("FLOW_HGT_MIN 2.0 m", xy=(rng[-1, 0], FLOOR_M), xytext=(-4, 4),
                    textcoords="offset points", ha="right", color=ORANGE, fontsize=8)
    ax.set_ylabel("range finder (m)")
    ax.set_xlim(a.flight_from - 10, a.flight_to + 5)
    ax.set_title("SFD-O4 log12: flow discarded below the focus floor, and what that cost")
    style(ax)

    ax = axes[1]
    ax.plot(t_off, e_off, lw=1.6, color=ORANGE, label="floor cut to ground clearance")
    ax.plot(t_on, e_on, lw=1.6, color=BLUE, label="floor at 2.0 m (as flown)")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("core velocity error vs GPS (m/s)")
    ax.set_xlim(a.flight_from - 10, a.flight_to + 5)
    ax.legend(frameon=False, loc="best")
    style(ax)
    fig.tight_layout()
    fig.savefig(a.out)
    print("wrote %s" % a.out)

    # split on the mechanism: the two arms can only differ below the floor, so
    # above it is a built-in control rather than a second result
    if len(rng):
        h_on = np.interp(t_on, rng[:, 0], rng[:, 1])
        h_off = np.interp(t_off, rng[:, 0], rng[:, 1])
        air_on = (t_on >= a.flight_from) & (t_on <= a.flight_to)
        air_off = (t_off >= a.flight_from) & (t_off <= a.flight_to)
        for label, sel_on, sel_off in (
                ("airborne <%.1fm" % FLOOR_M, air_on & (h_on < FLOOR_M), air_off & (h_off < FLOOR_M)),
                ("airborne >%.1fm" % FLOOR_M, air_on & (h_on >= FLOOR_M), air_off & (h_off >= FLOOR_M)),
                ("on the ground", ~air_on, ~air_off)):
            a = e_on[sel_on]
            b = e_off[sel_off]
            if len(a) and len(b):
                print("%-12s  floor on RMS %.3f (n=%d)   floor off RMS %.3f (n=%d)"
                      % (label, float(np.sqrt((a ** 2).mean())), len(a),
                         float(np.sqrt((b ** 2).mean())), len(b)))
    for name, t, e in (("whole flight, floor 2.0 m", t_on, e_on), ("whole flight, floor off", t_off, e_off)):
        if len(e):
            print("%-26s RMS %.3f m/s over %d samples" % (name, float(np.sqrt((e ** 2).mean())), len(e)))


if __name__ == "__main__":
    main()
