#!/usr/bin/env python3
"""Regenerate the AGL KF landed hold figure.

The flights are resolved by name through ../../find_log.py (this public repo
may not carry them); they were flown without the hold, so they are the "before".
The "after" is a Replay of each through the branch with the hold, from the
log-analyze skill's replay_sweep.py:

    export AP_LOG_ROOTS=<wherever SFD-O4 lives>
    replay_sweep.py --label hold --keep-dir <dir> log27.bin log28.bin
    ./make_landed_hold_plots.py --hold27 <dir>/hold-log27.bin.BIN --hold28 <dir>/hold-log28.bin.BIN

Core 1 is the flow-only lane in the flights and core 101 its re-run in Replay.
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
LOGS = {"log27.bin": ("3408138", "564"), "log28.bin": ("3408138", "566")}

# validated categorical slots 1-2; ink and grid are text tokens
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


def resolve(name):
    acc, boot = LOGS[name]
    out = subprocess.run([sys.executable, FINDLOG, name, "--acc-id", acc, "--bootcnt", boot],
                         capture_output=True, text=True)
    for line in out.stdout.splitlines():
        if line.strip().endswith(name):
            return line.strip()
    raise SystemExit("could not resolve %s; set AP_LOG_ROOTS\n%s" % (name, out.stdout + out.stderr))


def xkfa(path, core):
    """XKFA rows (t, HAgl, BiasStd, Valid) for one core; the first message of any type is zero"""
    m = mavutil.mavlink_connection(path)
    t0 = None
    rows = []
    while True:
        msg = m.recv_match()
        if msg is None:
            break
        tus = getattr(msg, 'TimeUS', None)
        if tus is None:
            continue
        if t0 is None:
            t0 = tus
        if msg.get_type() == 'XKFA' and msg.C == core:
            rows.append(((tus - t0) * 1e-6, msg.HAgl, msg.BiasStd, msg.Valid))
    return np.array(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold27", required=True)
    ap.add_argument("--hold28", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "aglkf_landed_hold.png"))
    a = ap.parse_args()

    f27, h27 = xkfa(resolve("log27.bin"), 1), xkfa(a.hold27, 101)
    f28, h28 = xkfa(resolve("log28.bin"), 1), xkfa(a.hold28, 101)

    fig, axs = plt.subplots(3, 1, figsize=(8.5, 7.6))
    labels = ("flown, no hold", "Replay with the hold")

    # log27: landed at 148.7 s and sat armed until 169.8 s
    ax = axs[0]
    for d, colour, label in ((f27, ORANGE, labels[0]), (h27, BLUE, labels[1])):
        k = (d[:, 0] > 144) & (d[:, 0] < 170)
        ax.plot(d[k, 0], d[k, 1], color=colour, lw=2, label=label)
    ax.axvspan(148.7, 169.8, color=GRID, alpha=.3, lw=0)
    ax.text(149.2, 0.95, "landed, armed", color=INK2, fontsize=8, transform=ax.get_xaxis_transform(), va='top')
    ax.set_title("log27: AGL KF height after a landing, flow lane", loc='left', fontsize=10)
    ax.set_ylabel("height (m)")
    ax.legend(loc='center right', frameon=False, fontsize=8)
    style(ax)

    ax = axs[1]
    for d, colour, label in ((f27, ORANGE, labels[0]), (h27, BLUE, labels[1])):
        k = (d[:, 0] > 144) & (d[:, 0] < 170)
        ax.step(d[k, 0], d[k, 3], where='post', color=colour, lw=2, label=label)
    ax.axvspan(148.7, 169.8, color=GRID, alpha=.3, lw=0)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["invalid", "valid"])
    ax.set_ylim(-0.2, 1.2)
    ax.set_title("log27: AGL KF valid flag", loc='left', fontsize=10)
    ax.set_xlabel("time (s)")
    style(ax)

    # log28: landed at 78.4 s, took off again at 88.8 s without disarming
    ax = axs[2]
    for d, colour, label in ((f28, ORANGE, labels[0]), (h28, BLUE, labels[1])):
        k = (d[:, 0] > 76) & (d[:, 0] < 95)
        ax.plot(d[k, 0], d[k, 2], color=colour, lw=2, label=label)
        print("log28 %s: bias std at second takeoff +1 s %.3f" % (label, np.interp(89.8, d[:, 0], d[:, 2])))
    ax.axvspan(78.4, 88.8, color=GRID, alpha=.3, lw=0)
    ax.text(78.9, 0.95, "touch-and-go: landed, armed", color=INK2, fontsize=8,
            transform=ax.get_xaxis_transform(), va='top')
    ax.set_yscale('log')
    ax.set_title("log28: AGL KF bias std through a touch-and-go", loc='left', fontsize=10)
    ax.set_ylabel("bias std (m/s/s)")
    ax.set_xlabel("time (s)")
    style(ax)

    for d, name in ((f27, "log27 flown"), (h27, "log27 hold")):
        k = (d[:, 0] > 149) & (d[:, 0] < 169.8)
        print("%s: landed HAgl max %.2f m, invalid samples %u" % (name, d[k, 1].max(), int((d[k, 3] == 0).sum())))

    fig.suptitle("SFD-O4: with the range finder below its minimum on the ground, the AGL KF coasts and "
                 "times out after a landing", fontsize=10, color=INK, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(a.out, dpi=130)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
