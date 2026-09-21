#!/usr/bin/env python3
"""Regenerate the source-set-selects-lane figure.

Both inputs are real flights, which this public repo may not carry, so they are
resolved by name through ../../find_log.py:

    export AP_LOG_ROOTS=<wherever SFD-O4 lives>
    ./make_plots.py

log11 flew the code before the change and log14 the code after it, on the same
airframe with the same switch action, so the pair is a real before/after rather
than a simulation of one.
"""
import argparse, os, subprocess, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pymavlink import mavutil

HERE = os.path.dirname(os.path.abspath(__file__))
FINDLOG = os.path.join(HERE, "..", "..", "find_log.py")
# fingerprints are private (see REPLAY_LOGS.md); these identify the SFD-O4 airframe
LOGS = {"log11.bin": ("3408138", "530"), "log14.bin": ("3408138", "536")}

# validated categorical slots 1-3 (see the data-viz palette); ink and grid are text tokens
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#c9c8c3"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK,
                     "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})


def style(ax):
    ax.grid(alpha=.25, lw=.6, color=GRID)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def resolve(name):
    acc, boot = LOGS[name]
    out = subprocess.run([sys.executable, FINDLOG, name, "--acc-id", acc, "--bootcnt", boot],
                         capture_output=True, text=True)
    for line in out.stdout.splitlines():
        if line.strip().endswith(name):
            return line.strip()
    raise SystemExit("could not resolve %s; set AP_LOG_ROOTS\n%s" % (name, out.stdout + out.stderr))


_T0 = {}
def read(path, types, want=lambda m: True):
    """Series on the log's own clock: the first message of ANY type is zero.

    Taking the origin per message type puts each series on a different clock and
    slid an annotation 1.1 s off the event it pointed at.
    """
    if path not in _T0:
        m = mavutil.mavlink_connection(path)
        _T0[path] = 0
        while True:
            msg = m.recv_match()
            if msg is None:
                break
            if getattr(msg, "TimeUS", None) is not None:
                _T0[path] = msg.TimeUS
                break
    m = mavutil.mavlink_connection(path)
    out = []
    while True:
        msg = m.recv_match(type=types)
        if msg is None:
            break
        if want(msg):
            out.append(((msg.TimeUS - _T0[path]) / 1e6, msg))
    return out



def fig_srcset(log11, log14, out):
    def pi(path):
        return np.array([(ts, m.PI) for ts, m in read(path, ["XKF4"], lambda m: m.C == 0)])
    p11, p14 = pi(log11), pi(log14)
    fig, ax = plt.subplots(2, 1, figsize=(9, 5.0))
    for a_ in ax:
        style(a_); a_.set_ylim(-0.3, 1.3); a_.set_yticks([0, 1])
        a_.set_yticklabels(["core 0 (GPS)", "core 1 (flow)"]); a_.set_xlim(30, 70)
    ax[0].plot(p11[:, 0], p11[:, 1], lw=2, color=ORANGE)
    for t in (39.4, 46.3, 49.8):
        ax[0].axvline(t, color=INK2, ls=":", lw=1)
    ax[0].set_title("Before: log11, three source-set selections, primary never moves",
                    loc="left", fontsize=10)
    ax[0].text(50.3, 0.55, "sets 2, 3, 2 selected\n(each reported success)",
               color=INK2, fontsize=8)
    ax[1].plot(p14[:, 0], p14[:, 1], lw=2, color=BLUE)
    ax[1].axvline(46.5, color=INK2, ls=":", lw=1)
    ax[1].set_xlabel("time (s)")
    ax[1].set_title("After: log14, selecting set 2 moves the primary to the lane that runs it",
                    loc="left", fontsize=10)
    ax[1].text(47.2, 0.35, "set 2 selected ->\n\"EKF3 lane switch 1\" 4.6 ms later",
               color=INK2, fontsize=8)
    plt.tight_layout(); plt.savefig(out, dpi=140); plt.close()


def main():
    log11, log14 = resolve("log11.bin"), resolve("log14.bin")
    fig_srcset(log11, log14, os.path.join(HERE, "srcset_lane_before_after.png"))
    print("wrote srcset_lane_before_after.png")


if __name__ == "__main__":
    sys.exit(main())
