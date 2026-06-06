#!/usr/bin/env python3
"""Regenerate the PR #33318 before/after plots from the SITL BINs in ../data/.

Both BINs are the LoiterFlowBrakeOvershoot autotest (optical flow, no GPS,
~2 m height, LOIT_ANG_MAX=30, deterministic forward jab + release). before.BIN
has the drag left in the feed-forward (pre-fix); after.BIN has the fix.

Each figure is 3 panels through the jab window (auto-detected from the RCIN.C2
pitch stick):
  1) actual North position (PN) vs controller target (TPN)
  2) actual North velocity (VN) vs commanded feed-forward velocity (DVN)
  3) demanded pitch (ANG.DesPitch)  [- forward / + brake]

Usage: python3 plots/make_plots.py    (run from the 33318/ directory)
"""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pymavlink import mavutil

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data')


def load(path):
    m = mavutil.mavlink_connection(path)
    T = []; C2 = []; TPN = []; PN = []; DVN = []; VN = []; DesP = []
    last = {'C2': 1500.0, 'DesP': 0.0}
    while True:
        msg = m.recv_match(blocking=False)
        if msg is None:
            break
        t = msg.get_type()
        if t == 'RCIN':
            last['C2'] = msg.C2
        elif t == 'ANG':
            last['DesP'] = msg.DesPitch
        elif t == 'PSCN':
            T.append(msg.TimeUS / 1e6); C2.append(last['C2'])
            TPN.append(msg.TPN); PN.append(msg.PN)
            DVN.append(msg.DVN); VN.append(msg.VN); DesP.append(last['DesP'])
    return (np.array(x) for x in (T, C2, TPN, PN, DVN, VN, DesP))


def make(path, out, label):
    T, C2, TPN, PN, DVN, VN, DesP = load(path)
    # auto-detect the jab: largest pitch-stick deflection, window +/-4 s around release
    dev = np.abs(C2 - 1500.0)
    pk = int(np.argmax(dev))
    rel_i = pk
    for i in range(pk, len(C2)):
        if dev[i] < 50:
            rel_i = i; break
    win = (T[rel_i] - 4.0, T[rel_i] + 4.0)

    sel = (T >= win[0]) & (T <= win[1])
    t = T[sel] - T[sel][0]
    C2, TPN, PN, DVN, VN, DesP = (a[sel] for a in (C2, TPN, PN, DVN, VN, DesP))

    dev = np.abs(C2 - 1500.0)
    hi = np.where(dev > 100)[0]
    rel = t[-1]
    if len(hi):
        for i in range(hi[-1], len(C2)):
            if dev[i] < 50:
                rel = t[i]; break

    fig, ax = plt.subplots(3, 1, figsize=(9, 8.5), sharex=True)
    fig.suptitle('AC_Loiter feed-forward over-drive - %s\n'
                 'SITL optical-flow Loiter, single forward stick + release' % label, fontsize=12)

    ax[0].plot(t, PN, color='C3', lw=1.9, label='actual position (PN)')
    ax[0].plot(t, TPN, color='C0', lw=1.9, ls='--', label='controller target (TPN)')
    ax[0].fill_between(t, PN, TPN, where=(PN > TPN), color='C3', alpha=0.15)
    io = int(np.argmax(PN - TPN))
    ax[0].annotate('actual runs %.2f m\npast its own target' % (PN[io] - TPN[io]),
                   xy=(t[io], PN[io]), xytext=(t[io] - 2.6, PN[io] - 0.15),
                   arrowprops=dict(arrowstyle='->'), fontsize=9)
    ax[0].set_ylabel('North position (m)'); ax[0].legend(loc='upper left', fontsize=9); ax[0].grid(alpha=0.3)

    ax[1].plot(t, VN, color='C3', lw=1.9, label='actual velocity (VN)')
    ax[1].plot(t, DVN, color='C2', lw=1.7, ls='--', label='commanded feed-forward velocity (DVN)')
    ax[1].axhline(0, color='k', lw=0.6)
    ipv = int(np.argmax(VN))
    ax[1].annotate('actual %.2f vs commanded %.2f m/s' % (VN[ipv], DVN[ipv]),
                   xy=(t[ipv], VN[ipv]), xytext=(t[ipv] - 2.9, VN[ipv] + 0.05),
                   arrowprops=dict(arrowstyle='->'), fontsize=9)
    ax[1].set_ylabel('North velocity (m/s)'); ax[1].legend(loc='lower left', fontsize=9); ax[1].grid(alpha=0.3)

    ax[2].plot(t, DesP, color='C1', lw=1.9, label='demanded pitch (ANG.DesPitch)')
    ax[2].axhline(0, color='k', lw=0.6)
    ipk = int(np.argmax(DesP))
    ax[2].annotate('+%.0f deg braking on release' % DesP[ipk], xy=(t[ipk], DesP[ipk]),
                   xytext=(t[ipk] - 3.0, DesP[ipk] - 2), arrowprops=dict(arrowstyle='->'), fontsize=9)
    ax[2].set_ylabel('pitch demand (deg)\n(- forward / + brake)'); ax[2].set_xlabel('time (s)')
    ax[2].legend(loc='upper left', fontsize=9); ax[2].grid(alpha=0.3)

    for a in ax:
        a.axvline(rel, color='gray', ls=':', lw=1.3)
    ax[0].text(rel + 0.05, ax[0].get_ylim()[1] * 0.88, 'stick released', fontsize=8, color='dimgray')

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(out, dpi=130)
    print('saved %s  | overshoot=%.2f m  peakBrake=%.0f deg'
          % (out, float(np.max(PN - TPN)), float(np.max(DesP))))


if __name__ == '__main__':
    make(os.path.join(DATA, 'before.BIN'), os.path.join(HERE, 'A_overshoot_before.png'), 'BEFORE fix')
    make(os.path.join(DATA, 'after.BIN'), os.path.join(HERE, 'B_overshoot_after.png'), 'AFTER fix')
