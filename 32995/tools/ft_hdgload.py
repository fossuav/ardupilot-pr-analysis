"""Compass heading against EKF yaw in steady fast flight, by summed eRPM and by
reported current, where the EKF yaw is confirmed by GPS course (within 15 deg).
usage: python3 ft_hdgload.py LOG.pkl FROM:TO[,...]
"""
import pickle
import sys
import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
segs = [tuple(float(x) for x in s.split(':')) for s in sys.argv[2].split(',')]


def sub(msg, k=None, v=None):
    m = d[msg]
    i = np.ones(len(m['t']), bool) if k is None else (m[k] == v)
    return {f: x[i] for f, x in m.items() if isinstance(x, np.ndarray)}


def iang(m, f, t):
    return np.degrees(np.interp(t, m['t'], np.unwrap(np.radians(m[f])))) % 360.0


def wrap(x):
    return (x + 180.0) % 360.0 - 180.0


mag, dcm, att, rate = sub('MAG', 'I', 0), sub('DCM'), sub('ATT'), sub('RATE')
x1, gps, esc, bat = sub('XKF1', 'C', 0), sub('GPS', 'I', 0), sub('ESC'), sub('BAT', 'Inst', 0)
t = mag['t']
r = np.radians(np.interp(t, dcm['t'], dcm['Roll']))
p = np.radians(np.interp(t, dcm['t'], dcm['Pitch']))
cx, cy, cz = -np.sin(p), np.sin(r) * np.cos(p), np.cos(r) * np.cos(p)
fx, fy, fz = mag['MagX'], mag['MagY'], mag['MagZ']
hY = fy * cz - fz * cy
hX = fx * (1 - cx * cx) - cx * (fy * cy + fz * cz)
mh = np.degrees(np.arctan2(-hY, hX)) % 360.0
ey = iang(x1, 'Yaw', t)
crs = np.interp(t, gps['t'], np.degrees(np.unwrap(np.radians(gps['GCrs'])))) % 360.0
spd = np.interp(t, gps['t'], gps['Spd'])
w = np.sqrt(np.interp(t, rate['t'], rate['R']) ** 2 + np.interp(t, rate['t'], rate['P']) ** 2 +
            np.interp(t, rate['t'], rate['Y']) ** 2)
krpm = sum(np.interp(t, esc['t'][esc['Instance'] == i], esc['RPM'][esc['Instance'] == i]) for i in range(4)) / 1e3
cur = np.interp(t, bat['t'], bat['Curr'])
sel = np.zeros_like(t, bool)
for a, b in segs:
    sel |= (t >= a) & (t <= b)
sel &= (spd > 8) & (w < 45) & (np.abs(np.degrees(r)) < 30) & (np.degrees(p) < -10) & (np.degrees(p) > -65)
sel &= np.abs(wrap(ey - crs)) < 15
e = wrap(mh - ey)
print(f'{sel.sum()} samples: fast, steady, EKF yaw within 15 deg of course; compass - EKF yaw')
for lo, hi in ((0, 45), (45, 55), (55, 65), (65, 200)):
    k = sel & (krpm >= lo) & (krpm < hi)
    if k.sum() >= 3:
        print(f'  {lo:3d}-{hi:<3d} kRPM: n {k.sum():4d}  median |e| {np.median(np.abs(e[k])):5.1f}  p90 {np.percentile(np.abs(e[k]), 90):5.1f}'
              f'  current {np.median(cur[k]):4.1f} A')
for lo, hi in ((-5, 4), (4, 8), (8, 12), (12, 20), (20, 80)):
    k = sel & (cur >= lo) & (cur < hi)
    if k.sum() >= 3:
        print(f'  reported {lo:3d}-{hi:<3d} A: n {k.sum():4d}  median |e| {np.median(np.abs(e[k])):5.1f}  p90 {np.percentile(np.abs(e[k]), 90):5.1f}')
