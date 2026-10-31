"""Compass coupling to battery current, and a board-temperature term, from
flight data. Fits the logged (compensated) body field over flight windows as
    m = R^T Be + b0 + c * (T - 18) + a * I
with Be the earth field (NED), b0 a body offset, c a body vector per degC of
MCU temperature, a a body vector per reported amp (BAT.Curr), and R from the
EKF attitude (ATT). Linear least squares: attitude variety separates Be from
b0, and the board cooling in flight separates c from b0.

The compensation adds COMPASS_MOT x current to the field, so the coupling
the data implies, in the same sign convention and per reported amp, is
APPLIED - a. Pass APPLIED as 0,0,0 for a log flown with COMPASS_MOTCT 0.
REF is the vector to measure directions against (normally the current
COMPASS_MOT). The temperature term is given along REF divided by |REF|: the
current over-report per degC that would produce it.

Samples: rotation under 60 deg/s and |pitch| under 60 deg (ATT is
interpolated as Euler angles). Units are those of the log's own compass
calibration, so logs on different COMPASS_SCALE/DIA values differ by those.
usage: python3 ft_magcoupling.py LOG.pkl FROM:TO[,...] APPLIED_X,Y,Z REF_X,Y,Z
"""
import pickle
import sys
import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
fly = [tuple(float(x) for x in s.split(':')) for s in sys.argv[2].split(',')]
applied = np.array([float(x) for x in sys.argv[3].split(',')])
ref = np.array([float(x) for x in sys.argv[4].split(',')])
mag = {k: v[d['MAG']['I'] == 0] for k, v in d['MAG'].items() if isinstance(v, np.ndarray)}
bat = {k: v[d['BAT']['Inst'] == 0] for k, v in d['BAT'].items() if isinstance(v, np.ndarray)}
att, rate, mcu = d['ATT'], d['RATE'], d['MCU']
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
cur = np.interp(t, bat['t'], bat['Curr'])
m = np.stack([mag['MagX'], mag['MagY'], mag['MagZ']], axis=1)

sel = np.zeros_like(t, bool)
for a, b in fly:
    sel |= (t >= a) & (t <= b)
sel &= (w < 60) & (np.abs(np.degrees(p)) < 60)
n = sel.sum()
Rs = R[sel]
# unknowns Be(3), b0(3), c(3), a(3); three rows per sample
A = np.zeros((3 * n, 12))
for i in range(3):
    A[i::3, 0:3] = Rs[:, :, i]
    A[i::3, 3 + i] = 1.0
    A[i::3, 6 + i] = T[sel] - 18.0
    A[i::3, 9 + i] = cur[sel]
yv = m[sel].reshape(-1)
x, *_ = np.linalg.lstsq(A, yv, rcond=None)
res = (yv - A @ x).reshape(-1, 3)
Be, b0, c, a = x[0:3], x[3:6], x[6:9], x[9:12]
u = ref / np.linalg.norm(ref)
K = applied - a


def ang(v):
    return np.degrees(np.arccos(np.clip(np.dot(v, u) / np.linalg.norm(v), -1, 1)))


print(f'{n} samples, MCU {T[sel].min():.1f}-{T[sel].max():.1f} degC, reported current '
      f'{np.percentile(cur[sel], 5):.1f}-{np.percentile(cur[sel], 95):.1f} A (p5-p95)')
print(f'  earth field NED {Be.round(0)}  |B| {np.linalg.norm(Be):.0f}  horiz {np.hypot(Be[0], Be[1]):.0f}  '
      f'dip {np.degrees(np.arctan2(Be[2], np.hypot(Be[0], Be[1]))):.0f} deg')
print(f'  b0 at 18 degC {b0.round(0)} mG')
print(f'  leftover per reported amp {a.round(2)} mG/A: {np.dot(a, u):.2f} along REF')
print(f'  implied coupling APPLIED - a {K.round(2)} mG/A, |K| {np.linalg.norm(K):.1f}, '
      f'{ang(K):.0f} deg from REF (|REF| {np.linalg.norm(ref):.1f})')
kn = np.linalg.norm(K)
print(f'  temperature term {c.round(1)} mG/degC, |c| {np.linalg.norm(c):.1f}: {np.dot(c, K) / kn:.1f} along K '
      f'({np.degrees(np.arccos(np.clip(np.dot(c, K) / (kn * np.linalg.norm(c)), -1, 1))):.0f} deg from it) = '
      f'{np.dot(c, K) / kn ** 2:.2f} reported A/degC over-reported at this coupling')
A2 = np.delete(A, [6, 7, 8], axis=1)
x2, *_ = np.linalg.lstsq(A2, yv, rcond=None)
res2 = (yv - A2 @ x2).reshape(-1, 3)
print(f'  residual rms {np.sqrt(np.mean(res ** 2)):.1f} mG per axis ({np.sqrt(np.mean(res2 ** 2)):.1f} without the '
      f'temperature term); raw spread {np.std(m[sel], axis=0).round(0)}')
