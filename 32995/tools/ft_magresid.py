"""Uncompensated compass interference in the body frame.

The earth field is taken from a still, clean ground window (body field rotated
by the EKF attitude); in flight the expected body field is that earth field
rotated back by the EKF attitude, and the residual is what the compass saw
beyond it. Only samples where the EKF yaw is trusted (passed as windows) and
the vehicle is not flipping are used.

usage: python3 ft_magresid.py LOG.pkl GROUND_FROM:GROUND_TO FLY_FROM:FLY_TO[,...] MOTX,MOTY,MOTZ
"""
import pickle
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
ga, gb = (float(x) for x in sys.argv[2].split(':'))
fly = [tuple(float(x) for x in s.split(':')) for s in sys.argv[3].split(',')]
mot = np.array([float(x) for x in sys.argv[4].split(',')])

mag = {k: v[d['MAG']['I'] == 0] for k, v in d['MAG'].items() if isinstance(v, np.ndarray)}
att, rate, esc, bat = d['ATT'], d['RATE'], d['ESC'], d['BAT']
t = mag['t']


def iang(f):
    return np.interp(t, att['t'], np.unwrap(np.radians(att[f])))


r, p, y = iang('Roll'), iang('Pitch'), iang('Yaw')
cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
# body-to-NED rotation, 321 Euler
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
Bb = np.stack([mag['MagX'], mag['MagY'], mag['MagZ']], axis=1)
MO = np.stack([mag['MOX'], mag['MOY'], mag['MOZ']], axis=1)
Bn = np.einsum('nij,nj->ni', R, Bb)
g = (t >= ga) & (t <= gb)
Be = Bn[g].mean(axis=0)
print(f'earth field from {ga:.0f}-{gb:.0f} s (NED, mGauss): {Be.round(1)}  |B| {np.linalg.norm(Be):.1f}  '
      f'dip {np.degrees(np.arctan2(Be[2], np.hypot(Be[0], Be[1]))):.1f} deg')
pred = np.einsum('nji,j->ni', R, Be)
res = Bb - pred
w = np.sqrt(np.interp(t, rate['t'], rate['R']) ** 2 + np.interp(t, rate['t'], rate['P']) ** 2 +
            np.interp(t, rate['t'], rate['Y']) ** 2)
k3 = np.zeros_like(t)
for i in range(4):
    j = esc['Instance'] == i
    k3 += (np.interp(t, esc['t'][j], esc['RPM'][j]) / 10000.0) ** 3
cur = np.interp(t, bat['t'][bat['Inst'] == 0], bat['Curr'][bat['Inst'] == 0])
sel = np.zeros_like(t, bool)
for a, b in fly:
    sel |= (t >= a) & (t <= b)
sel &= (w < 60) & (np.abs(np.degrees(r)) < 50) & (np.abs(np.degrees(p)) < 50)
print(f'{sel.sum()} flight samples')
X = np.stack([np.ones(sel.sum()), k3[sel]], axis=1)
coef, *_ = np.linalg.lstsq(X, res[sel], rcond=None)
slope = coef[1]
fit = X @ coef
for ax, name in enumerate('XYZ'):
    c = np.corrcoef(k3[sel], res[sel, ax])[0, 1]
    print(f'  residual {name}: intercept {coef[0, ax]:6.1f}, per unit load {slope[ax]:6.1f} mG, r={c:.2f}')
u = -mot / np.linalg.norm(mot)
print(f'  residual slope direction {(slope / np.linalg.norm(slope)).round(2)}, '
      f'-COMPASS_MOT direction {u.round(2)}, angle between '
      f'{np.degrees(np.arccos(np.clip(np.dot(slope, u) / np.linalg.norm(slope), -1, 1))):.0f} deg')
print('  by load: median |residual|, applied |MO|, reported current, and residual along -COMPASS_MOT')
q = np.percentile(k3[sel], [0, 25, 50, 75, 95, 100])
for lo, hi in zip(q[:-1], q[1:]):
    m = sel & (k3 >= lo) & (k3 <= hi)
    along = res[m] @ u
    print(f'    load {lo:5.2f}-{hi:5.2f}: |res| {np.median(np.linalg.norm(res[m], axis=1)):6.1f}  '
          f'|MO| {np.median(np.linalg.norm(MO[m], axis=1)):5.1f}  BAT.Curr {np.median(cur[m]):4.1f} A  '
          f'along {np.median(along):6.1f} mG -> extra {np.median(along) / np.linalg.norm(mot):5.1f} A unaccounted')
