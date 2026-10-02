#!/usr/bin/env python3
"""Regenerate the landed EKF failsafe figure.

Two flights, resolved by name through ../../find_log.py (this public repo may not
carry them): log28 flown before the land_complete change, log30 after it. Both
landed with the optical flow lane primary, which gives up its position on the
ground below the sensor's focus height.

    export AP_LOG_ROOTS=<wherever SFD-O4 lives>
    ./make_landed_failsafe_plots.py
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
LOGS = {"log28.bin": ("3408138", "566"), "log30.bin": ("3408138", "571")}

BLUE = "#2a78d6"
CRIT = "#d03b3b"   # status: critical, always with a label
INK, INK2, GRID = "#0b0b0b", "#52514e", "#c9c8c3"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK,
                     "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})

EV_LAND_COMPLETE, EV_NOT_LANDED, EV_DISARMED = 18, 28, 11
ERR_FAILSAFE_EKFINAV = 17


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


def read(path):
    """primary-lane aiding mode, landed spans, failsafe and mode-change times"""
    m = mavutil.mavlink_connection(path)
    t0 = None
    aid = {}
    pi = []
    ev, fs, modes = [], [], []
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
        if ty == 'XKF4':
            aid.setdefault(msg.C, []).append((t, msg.AID))
            if msg.C == 0:
                pi.append((t, msg.PI))
        elif ty == 'EV':
            ev.append((t, msg.Id))
        elif ty == 'ERR' and msg.Subsys == ERR_FAILSAFE_EKFINAV and msg.ECode == 1:
            fs.append(t)
        elif ty == 'MODE':
            modes.append((t, msg.Mode))
    pi = np.array(pi)
    aid = {c: np.array(v) for c, v in aid.items()}
    # aiding mode of whichever lane was primary
    prim = []
    for t, a in aid[0]:
        lane = int(np.interp(t, pi[:, 0], pi[:, 1]) + 0.5)
        prim.append((t, np.interp(t, aid[lane][:, 0], aid[lane][:, 1])))
    landed, start = [], None
    for t, i in ev:
        if i == EV_LAND_COMPLETE and start is None:
            start = t
        elif i in (EV_NOT_LANDED, EV_DISARMED) and start is not None:
            landed.append((start, t))
            start = None
    return np.array(prim), landed, fs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "ekf_failsafe_landed.png"))
    a = ap.parse_args()

    cases = (("log28.bin", "log28, before: flow lane primary, landed", (115, 140)),
             ("log30.bin", "log30, after: flow lane primary, landed twice", (76, 135)))
    fig, axs = plt.subplots(2, 1, figsize=(8.5, 5.4))
    for ax, (name, title, (t0, t1)) in zip(axs, cases):
        prim, landed, fs = read(resolve(name))
        # AID: 0 absolute, 1 none, 2 relative; drawn top to bottom as absolute, relative, none
        level = {0: 2, 2: 1, 1: 0}
        k = (prim[:, 0] > t0) & (prim[:, 0] < t1)
        y = np.array([level[int(round(v))] for v in prim[k, 1]])
        ax.step(prim[k, 0], y, where='post', color=BLUE, lw=2)
        for s, e in landed:
            if e > t0 and s < t1:
                ax.axvspan(max(s, t0), min(e, t1), color=GRID, alpha=.3, lw=0)
                ax.text(max(s, t0) + 0.4, 0.97, "landed", color=INK2, fontsize=8,
                        transform=ax.get_xaxis_transform(), va='top')
        for t in fs:
            if t0 < t < t1:
                ax.axvline(t, color=CRIT, lw=1.5)
                ax.text(t + 0.4, 0.5, "EKF failsafe:\nLOITER -> ALT_HOLD", color=INK, fontsize=8, va='center')
        print("%s: failsafes in window %s, landed spans %s" %
              (name, [round(t, 1) for t in fs if t0 < t < t1],
               [(round(s, 1), round(e, 1)) for s, e in landed if e > t0 and s < t1]))
        ax.set_yticks([0, 1, 2])
        ax.set_yticklabels(["no aiding", "relative (flow)", "absolute"])
        ax.set_ylim(-0.4, 2.4)
        ax.set_xlim(t0, t1)
        ax.set_title(title, loc='left', fontsize=10)
        ax.set_xlabel("time (s)")
        style(ax)
    fig.suptitle("SFD-O4: the primary lane's aiding while landed in LOITER, and the EKF failsafe it "
                 "tripped", fontsize=10, color=INK, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(a.out, dpi=130)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
