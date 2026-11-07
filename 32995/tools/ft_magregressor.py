"""Which load signal explains the compass interference best? Fits the
uncompensated body field (MAG - MO) over flight windows as
    m = R^T Be + b0 [+ c (T - 18)] + a X
for X = reported current, throttle (MOTB.ThrOut, and CTUN.ThO, which is
motors->get_throttle(), what COMPASS_MOTCT 1 multiplies),
and the shape of the eRPM current model (summed eRPM^3), and
reports the residual rms per axis and the heading error each leaves.
usage: python3 ft_magregressor.py LOG.pkl FROM:TO[,...]
"""
import pickle
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
fly = [tuple(float(x) for x in s.split(':')) for s in sys.argv[2].split(',')]
mag = {k: v[d['MAG']['I'] == 0] for k, v in d['MAG'].items() if isinstance(v, np.ndarray)}
bat = {k: v[d['BAT']['Inst'] == 0] for k, v in d['BAT'].items() if isinstance(v, np.ndarray)}
att, rate, mcu, motb, esc = d['ATT'], d['RATE'], d['MCU'], d['MOTB'], d['ESC']
t = mag['t']


def iang(f):
    return np.interp(t, att['t'], np.unwrap(np.radians(att[f])))


r, p, y = iang('Roll'), iang('Pitch'), iang('Yaw')
cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
R = np.empty((len(t), 3, 3))
R[:, 0, 0] = cp * cy
R[:, 0, 1] = sr * sp * cy - cr * sy
R[:, 0, 2] = cr * sp * cy + sr * sy
R[:, 1, 0] = cp * sy
R[:, 1, 1] = sr * sp * sy + cr * cy
R[:, 1, 2] = cr * sp * sy - sr * cy
R[:, 2, 0] = -sp
R[:, 2, 1] = sr * cp
R[:, 2, 2] = cr * cp
w = np.sqrt(np.interp(t, rate['t'], rate['R']) ** 2 + np.interp(t, rate['t'], rate['P']) ** 2 +
            np.interp(t, rate['t'], rate['Y']) ** 2)
T = np.interp(t, mcu['t'], mcu['MTemp'])
m = np.stack([mag['MagX'] - mag['MOX'], mag['MagY'] - mag['MOY'], mag['MagZ'] - mag['MOZ']], axis=1)

# summed eRPM on a 0.1 s grid, then cubed: the shape of the eRPM current model
grid = np.arange(t.min(), t.max(), 0.1)
rs = np.zeros_like(grid)
for k in range(4):
    e = esc['Instance'] == k
    rs += np.interp(grid, esc['t'][e], esc['RPM'][e])
erpm = np.interp(t, grid, rs)
X = {
    'current': np.interp(t, bat['t'], bat['Curr']),
    'MOTB.Thr': np.interp(t, motb['t'], motb['ThrOut']),
    'CTUN.ThO': np.interp(t, d['CTUN']['t'], d['CTUN']['ThO']),
    'eRPM^3': (erpm / 1e4) ** 3,
}

sel = np.zeros_like(t, bool)
for a, b in fly:
    sel |= (t >= a) & (t <= b)
sel &= (w < 60) & (np.abs(np.degrees(p)) < 60)
n = sel.sum()
Rs = R[sel]
yv = m[sel].reshape(-1)
print(f'{n} samples, MCU {T[sel].min():.1f}-{T[sel].max():.1f} degC')


def fit(x, temp):
    cols = 12 if temp else 9
    A = np.zeros((3 * n, cols))
    for i in range(3):
        A[i::3, 0:3] = Rs[:, :, i]
        A[i::3, 3 + i] = 1.0
        if x is not None:
            A[i::3, 6 + i] = x[sel]
        if temp:
            A[i::3, 9 + i] = T[sel] - 18.0
    if x is None:
        A = A[:, [0, 1, 2, 3, 4, 5] + ([9, 10, 11] if temp else [])]
    sol, *_ = np.linalg.lstsq(A, yv, rcond=None)
    res = (yv - A @ sol).reshape(-1, 3)
    Be = sol[0:3]
    # heading error the residual leaves: residual rotated to NED, horizontal
    # component across the earth field's horizontal direction
    rn = np.einsum('nij,nj->ni', Rs, res)
    hdir = np.array([Be[0], Be[1]]) / np.hypot(Be[0], Be[1])
    cross = rn[:, 0] * -hdir[1] + rn[:, 1] * hdir[0]
    herr = np.degrees(np.arctan2(np.abs(cross), np.hypot(Be[0], Be[1])))
    coef = sol[6:9] if x is not None else None
    return np.sqrt(np.mean(res ** 2)), np.median(herr), np.percentile(herr, 90), coef


for name in ['none'] + list(X):
    for temp in (False, True):
        rms, hm, h90, coef = fit(None if name == 'none' else X[name], temp)
        print(f'  {name:9s} temp {"yes" if temp else "no ":3s}  residual {rms:5.1f} mG/axis'
              f'  heading error median {hm:4.1f} p90 {h90:4.1f} deg'
              + (f'  coef {coef.round(1)} |{np.linalg.norm(coef):.1f}|' if coef is not None else ''))
