"""Estimate EKF yaw error in a position-controlled segment from the rotation
between the commanded acceleration (PSCN/PSCE TAN/TAE) and the acceleration
GPS measured, scanned over response lag.

usage: python3 ft_loiter_yaw.py LOG.pkl FROM TO
"""
import pickle
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
a, b = float(sys.argv[2]), float(sys.argv[3])
n, e = d['PSCN'], d['PSCE']
g = {k: v[d['GPS']['I'] == 0] for k, v in d['GPS'].items() if isinstance(v, np.ndarray)}
vn = g['Spd'] * np.cos(np.radians(g['GCrs']))
ve = g['Spd'] * np.sin(np.radians(g['GCrs']))
# GPS acceleration by central difference over two samples (0.4 s at 5 Hz)
ta = g['t'][1:-1]
an = (vn[2:] - vn[:-2]) / (g['t'][2:] - g['t'][:-2])
ae = (ve[2:] - ve[:-2]) / (g['t'][2:] - g['t'][:-2])
k = (ta >= a) & (ta <= b)
ta, an, ae = ta[k], an[k], ae[k]
best = None
print(f'{"lag s":>6} {"n":>4} {"corr":>6} {"rot deg":>8} {"gain":>5}')
for lag in np.arange(0.0, 0.81, 0.1):
    tc = ta - lag
    cn = np.interp(tc, n['t'], n['TAN'])
    ce = np.interp(tc, e['t'], e['TAE'])
    m = np.hypot(cn, ce) > 0.5
    if m.sum() < 10:
        continue
    zc = cn[m] + 1j * ce[m]
    zg = an[m] + 1j * ae[m]
    # least-squares complex gain: zg ~ c * zc; arg(c) is the rotation
    c = np.vdot(zc, zg) / np.vdot(zc, zc)
    corr = abs(np.vdot(zc, zg)) / np.sqrt(np.vdot(zc, zc).real * np.vdot(zg, zg).real)
    print(f'{lag:6.1f} {m.sum():4d} {corr:6.2f} {np.degrees(np.angle(c)):8.1f} {abs(c):5.2f}')
    if best is None or corr > best[0]:
        best = (corr, lag, np.degrees(np.angle(c)))
print(f'best: lag {best[1]:.1f} s, corr {best[0]:.2f}, measured accel rotated {best[2]:+.0f} deg from commanded '
      f'(positive = clockwise, i.e. EKF yaw reads that much anticlockwise of true)')
