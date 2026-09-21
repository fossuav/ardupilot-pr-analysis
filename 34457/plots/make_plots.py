#!/usr/bin/env python3
"""Regenerate the AGL KF floor figures.

The inputs are real flights, which this public repo may not carry, so they are
resolved by name through ../../find_log.py:

    export AP_LOG_ROOTS=<wherever SFD-O4 lives>
    ./make_plots.py

Figure 1 additionally needs two Replay output BINs, before and after the change,
produced from log9 by the log-analyze skill's replay_sweep.py:

    # on the branch without the fix, then with it
    replay_sweep.py --label before --keep-dir <dir> log9.bin
    replay_sweep.py --label after  --keep-dir <dir> log9.bin
    ./make_plots.py --replay-before <dir>/before-log9.bin.BIN \
                    --replay-after  <dir>/after-log9.bin.BIN

Without them figure 1 is skipped and says so; figure 2 always builds.
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
LOGS = {"log9.bin": ("3408138", "525"), "log12.bin": ("3408138", "532")}

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


def fig_replay_ab(before, after, log9, out):
    def series(path, core):
        h, a = [], []
        for ts, m in read(path, ["XKF1", "XKFA"], lambda m: getattr(m, "C", None) == 100 + core):
            (h if m.get_type() == "XKF1" else a).append(
                (ts, -m.PD if m.get_type() == "XKF1" else m.HAgl))
        return np.array(h), np.array(a)
    hb, ab = series(before, 0)
    ha, aa = series(after, 0)
    rf = np.array([(ts, m.Dist) for ts, m in read(log9, ["RFND"], lambda m: m.Stat == 4)])
    rf[:, 0] -= 1.06          # source-log clock to replay clock, anchored on the shared lift-off
    LIFT = 88.64
    fig, ax = plt.subplots(2, 1, figsize=(9, 6.4), sharex=True)
    for a_ in ax:
        style(a_); a_.set_xlim(87, 101); a_.set_ylim(-0.5, 7)
        a_.axvline(LIFT, color=INK2, ls=":", lw=1)
    ax[0].plot(rf[:, 0], rf[:, 1], lw=2, color=AQUA, label="rangefinder (truth)")
    ax[0].plot(hb[:, 0], hb[:, 1] - 0.46, lw=2, color=ORANGE, label="EKF height, before")
    ax[0].plot(ha[:, 0], ha[:, 1] - 0.46, lw=2, color=BLUE, label="EKF height, after")
    ax[0].set_ylabel("height above ground (m)")
    ax[0].text(LIFT + 0.12, -0.3, "lift-off", color=INK2, fontsize=8)
    ax[0].annotate("+2.21 m step", xy=(92.72, 3.3), xytext=(93.4, 1.2), color=INK2, fontsize=8,
                   arrowprops=dict(arrowstyle="->", color=INK2, lw=.9))
    ax[0].legend(loc="upper left", frameon=False, fontsize=8)
    ax[0].set_title("AGL KF floor fix, Replay of SFD-O4 log9 (one flight, code before vs after)",
                    loc="left", fontsize=10)
    ax[1].plot(rf[:, 0], rf[:, 1], lw=2, color=AQUA, label="rangefinder (truth)")
    ax[1].plot(ab[:, 0], ab[:, 1], lw=2, color=ORANGE, label="XKFA.HAgl, before")
    ax[1].plot(aa[:, 0], aa[:, 1], lw=2, color=BLUE, label="XKFA.HAgl, after")
    ax[1].set_ylabel("AGL KF height (m)"); ax[1].set_xlabel("replay time (s)")
    ax[1].annotate("pinned on the 0.05 m floor for 4 s", xy=(91.0, 0.1), xytext=(89.6, 2.6),
                   color=INK2, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2, lw=.9))
    ax[1].legend(loc="upper left", frameon=False, fontsize=8)
    plt.tight_layout(); plt.savefig(out, dpi=140); plt.close()


def fig_ground_windup(log9, log12, out):
    def ground(path, arm_t):
        v = np.array([(ts, m.VAgl) for ts, m in read(path, ["XKFA"], lambda m: m.C == 0)])
        v = v[(v[:, 0] > 3) & (v[:, 0] < arm_t)]
        v[:, 0] -= arm_t
        return v
    g9, g12 = ground(log9, 86.5), ground(log12, 494.2)
    fig, ax = plt.subplots(figsize=(9, 3.6)); style(ax)
    ax.plot(g9[:, 0], g9[:, 1], lw=2, color=ORANGE,
            label="log9, before the fix (88 s on the ground)")
    ax.plot(g12[:, 0], g12[:, 1], lw=2, color=BLUE,
            label="log12, after the fix (487 s on the ground)")
    ax.axhline(0, color=GRID, lw=.8)
    ax.set_xlim(-500, 2); ax.set_ylabel("AGL KF vertical velocity (m/s)")
    ax.set_xlabel("time before arming (s)")
    ax.set_title("The same airframe sitting still: the AGL KF velocity state on the ground",
                 loc="left", fontsize=10)
    ax.annotate("-7.2 m/s at lift-off", xy=(0, -7.2), xytext=(-170, -6.2), color=INK2, fontsize=8,
                arrowprops=dict(arrowstyle="->", color=INK2, lw=.9))
    ax.annotate("flat at -0.001 m/s over 5.5x the dwell", xy=(-240, 0), xytext=(-430, -2.6),
                color=INK2, fontsize=8, arrowprops=dict(arrowstyle="->", color=INK2, lw=.9))
    ax.legend(loc="lower left", frameon=False, fontsize=8)
    plt.tight_layout(); plt.savefig(out, dpi=140); plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay-before")
    ap.add_argument("--replay-after")
    args = ap.parse_args()
    log9, log12 = resolve("log9.bin"), resolve("log12.bin")
    if args.replay_before and args.replay_after:
        fig_replay_ab(args.replay_before, args.replay_after, log9,
                      os.path.join(HERE, "aglkf_1_replay_ab_log9.png"))
        print("wrote aglkf_1_replay_ab_log9.png")
    else:
        print("skipping figure 1: pass --replay-before/--replay-after (see the docstring)")
    fig_ground_windup(log9, log12, os.path.join(HERE, "aglkf_2_ground_windup.png"))
    print("wrote aglkf_2_ground_windup.png")


if __name__ == "__main__":
    sys.exit(main())
