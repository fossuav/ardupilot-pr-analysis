"""EKF yaw error from the accelerometer: body specific force rotated to NED
with the EKF attitude (ATT), plus gravity, against GPS acceleration (central
difference of GPS velocity). Returns EKF yaw - true yaw, positive when the
EKF heading is clockwise of true. Also EKF - GSF for the same windows.
usage: python3 ft_imuyaw.py LOG.pkl FROM TO [WIN]
"""
import pickle
import sys
import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
a, b = float(sys.argv[2]), float(sys.argv[3])
W = float(sys.argv[4]) if len(sys.argv) > 4 else 20.0


def sub(msg, k=None, v=None):
    m = d[msg]
    i = np.ones(len(m['t']), bool) if k is None else (m[k] == v)
    return {f: x[i] for f, x in m.items() if isinstance(x, np.ndarray)}


def wrap(x):
    return (x + 180.0) % 360.0 - 180.0


imu, att, g, ky, x1 = sub('IMU', 'I', 0), sub('ATT'), sub('GPS', 'I', 0), sub('XKY0', 'C', 0), sub('XKF1', 'C', 0)
vn = g['Spd'] * np.cos(np.radians(g['GCrs']))
ve = g['Spd'] * np.sin(np.radians(g['GCrs']))
ta = g['t'][1:-1]
an = (vn[2:] - vn[:-2]) / (g['t'][2:] - g['t'][:-2])
ae = (ve[2:] - ve[:-2]) / (g['t'][2:] - g['t'][:-2])
t = imu['t']


def iang(m, f, tt):
    return np.interp(tt, m['t'], np.unwrap(np.radians(m[f])))


r, p, y = iang(att, 'Roll', t), iang(att, 'Pitch', t), iang(att, 'Yaw', t)
cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
fx, fy, fz = imu['AccX'], imu['AccY'], imu['AccZ']
# body -> NED (321), north and east rows only
fn = cp * cy * fx + (sr * sp * cy - cr * sy) * fy + (cr * sp * cy + sr * sy) * fz
fe = cp * sy * fx + (sr * sp * sy + cr * cy) * fy + (cr * sp * sy - sr * cy) * fz
# average the IMU over each GPS central-difference span (t-0.2, t+0.2)
cs = np.concatenate([[0.0], np.cumsum(fn)])
ce = np.concatenate([[0.0], np.cumsum(fe)])
i0 = np.searchsorted(t, ta - 0.2)
i1 = np.searchsorted(t, ta + 0.2)
cnt = np.maximum(i1 - i0, 1)
in_ = (cs[i1] - cs[i0]) / cnt
ie_ = (ce[i1] - ce[i0]) / cnt
print(f'{"win":>11} {"n":>4} {"corr":>5} {"EKF-true":>8} {"gain":>5} {"EKF-GSF":>8}')
for w0 in np.arange(a, b - W + 1e-6, W / 2):
    k = (ta >= w0) & (ta < w0 + W) & (np.hypot(an, ae) > 0.7)
    if k.sum() < 8:
        continue
    gz = an[k] + 1j * ae[k]
    iz = in_[k] + 1j * ie_[k]
    z = np.sum(iz * np.conj(gz))
    corr = np.abs(z) / np.sqrt(np.sum(np.abs(gz) ** 2) * np.sum(np.abs(iz) ** 2))
    tt = np.arange(w0, w0 + W, 0.2)
    eg = np.median(wrap(np.degrees(iang(x1, 'Yaw', tt) - iang(ky, 'YC', tt))))
    print(f'{w0:5.0f}-{w0 + W:<5.0f} {k.sum():4d} {corr:5.2f} {np.degrees(np.angle(z)):8.1f} '
          f'{np.abs(z) / np.sum(np.abs(gz) ** 2):5.2f} {eg:8.1f}')
