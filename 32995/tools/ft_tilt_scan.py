"""Scan for quasi-steady windows (slow, not accelerating, not rotating) and
compare EKF and DCM roll/pitch with the tilt the mean specific force gives.
AHRS_TRIM is removed so a correct estimator reads zero; TRIM_R/TRIM_P are
99F517D8's AHRS_TRIM_X/Y, change them for another board.

usage: python3 ft_tilt_scan.py LOG.pkl FROM TO [WIN]
"""
import pickle
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
a, b = float(sys.argv[2]), float(sys.argv[3])
W = float(sys.argv[4]) if len(sys.argv) > 4 else 2.0
TRIM_R, TRIM_P = np.degrees(-0.009999801), np.degrees(-0.0024632984)


def sub(msg, k=None, v=None):
    m = d[msg]
    i = np.ones(len(m['t']), bool) if k is None else (m[k] == v)
    return {f: x[i] for f, x in m.items() if isinstance(x, np.ndarray)}


imu, att, dcm, rate = sub('IMU', 'I', 0), sub('ATT'), sub('DCM'), sub('RATE')
g = sub('GPS', 'I', 0)
vn = g['Spd'] * np.cos(np.radians(g['GCrs']))
ve = g['Spd'] * np.sin(np.radians(g['GCrs']))
print(f'{"win":>11} {"spd":>4} {"dV":>4} {"wmax":>5} {"EKF-acc R":>9} {"P":>5} {"DCM-acc R":>9} {"P":>5}')
for w0 in np.arange(a, b - W, W / 2):
    w1 = w0 + W
    gi = (g['t'] >= w0) & (g['t'] <= w1)
    ri = (rate['t'] >= w0) & (rate['t'] <= w1)
    if gi.sum() < 3:
        continue
    spd = np.max(g['Spd'][gi])
    dv = np.hypot(vn[gi][-1] - vn[gi][0], ve[gi][-1] - ve[gi][0])
    wmax = np.max(np.sqrt(rate['R'][ri] ** 2 + rate['P'][ri] ** 2 + rate['Y'][ri] ** 2))
    if spd > 5 or dv > 1.0 or wmax > 60:
        continue
    i = (imu['t'] >= w0) & (imu['t'] < w1)
    fx, fy, fz = (np.mean(imu[k][i]) for k in ('AccX', 'AccY', 'AccZ'))
    ar = np.degrees(np.arctan2(-fy, -fz)) - TRIM_R
    ap = np.degrees(np.arctan2(fx, np.hypot(fy, fz))) - TRIM_P
    j = (att['t'] >= w0) & (att['t'] < w1)
    k = (dcm['t'] >= w0) & (dcm['t'] < w1)
    print(f'{w0:5.1f}-{w1:<5.1f} {spd:4.1f} {dv:4.1f} {wmax:5.0f} {np.mean(att["Roll"][j]) - ar:9.1f} '
          f'{np.mean(att["Pitch"][j]) - ap:5.1f} {np.mean(dcm["Roll"][k]) - ar:9.1f} {np.mean(dcm["Pitch"][k]) - ap:5.1f}')
