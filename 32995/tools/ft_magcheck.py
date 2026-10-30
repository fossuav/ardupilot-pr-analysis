"""Compass interference and heading checks.

usage: python3 ft_magcheck.py LOG.pkl SEG_FROM:SEG_TO[,...]
For each segment: yaw-independent field components (horizontal magnitude and
earth-down component after tilt compensation with DCM roll/pitch) binned by
motor eRPM, and heading against GPS course in fast forward flight.
"""
import pickle
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
segs = [tuple(float(x) for x in s.split(':')) for s in sys.argv[2].split(',')]


def sel(msg, k, v):
    m = d[msg]
    idx = m[k] == v
    return {f: (a[idx] if isinstance(a, np.ndarray) else a) for f, a in m.items()}


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def iang(m, f, t):
    a = np.unwrap(np.radians(m[f]))
    return np.degrees(np.interp(t, m['t'], a)) % 360.0


mag = sel('MAG', 'I', 0)
dcm = d['DCM']
att = d['ATT']
rate = d['RATE']
x1 = sel('XKF1', 'C', 0)
ky = sel('XKY0', 'C', 0)
gps = sel('GPS', 'I', 0)
esc = d['ESC']
motb = d['MOTB']

t = mag['t']
r = np.radians(np.interp(t, dcm['t'], dcm['Roll']))
p = np.radians(np.interp(t, dcm['t'], dcm['Pitch']))
cx, cy, cz = -np.sin(p), np.sin(r) * np.cos(p), np.cos(r) * np.cos(p)
fx, fy, fz = mag['MagX'], mag['MagY'], mag['MagZ']
headY = fy * cz - fz * cy
headX = fx * (1 - cx * cx) - cx * (fy * cy + fz * cz)
Bh = np.hypot(headX, headY)
Bd = fx * cx + fy * cy + fz * cz
B = np.sqrt(fx ** 2 + fy ** 2 + fz ** 2)
magH = np.degrees(np.arctan2(-headY, headX)) % 360.0
MO = np.sqrt(mag['MOX'] ** 2 + mag['MOY'] ** 2 + mag['MOZ'] ** 2)
# body rotation rate at the sample, deg/s
w = np.sqrt(np.interp(t, rate['t'], rate['R']) ** 2 + np.interp(t, rate['t'], rate['P']) ** 2 +
            np.interp(t, rate['t'], rate['Y']) ** 2)
krpm = np.zeros_like(t)
for inst in range(4):
    i = esc['Instance'] == inst
    krpm += np.interp(t, esc['t'][i], esc['RPM'][i]) / 1000.0
thr = np.interp(t, motb['t'], motb['ThrOut'])

for (a, b) in segs:
    s = (t >= a) & (t <= b)
    print(f'=== segment {a:.0f}-{b:.0f} s: {s.sum()} MAG samples')
    calm = s & (w < 60)
    print(f'  low-rate samples (|w|<60 deg/s): {calm.sum()}')
    print(f'  {"kRPM bin":>10} {"n":>5} {"|B|":>7} {"Bh":>7} {"Bdown":>7} {"MO":>6} {"thr":>5}')
    edges = [0, 1, 30, 40, 50, 60, 70, 200]
    for lo, hi in zip(edges[:-1], edges[1:]):
        k = calm & (krpm >= lo) & (krpm < hi)
        if k.sum() < 3:
            continue
        print(f'  {lo:>4}-{hi:<5} {k.sum():5d} {np.median(B[k]):7.1f} {np.median(Bh[k]):7.1f} '
              f'{np.median(Bd[k]):7.1f} {np.median(MO[k]):6.1f} {np.median(thr[k]):5.2f}')
    if calm.sum() > 10 and np.std(krpm[calm]) > 1:
        c = np.polyfit(krpm[calm], B[calm], 1)
        print(f'  |B| fit: {c[1]:.1f} + {c[0]:.2f} per kRPM, r={np.corrcoef(krpm[calm], B[calm])[0, 1]:.2f}')

    # heading against GPS course: fast, nose-down, not rotating much
    gt = gps['t']
    gs = (gt >= a) & (gt <= b) & (gps['Spd'] > 8)
    if gs.sum() < 5:
        print('  too few fast GPS samples for a course check')
        continue
    tt = gt[gs]
    crs = gps['GCrs'][gs]
    pit = np.interp(tt, att['t'], att['Pitch'])
    rol = np.interp(tt, att['t'], att['Roll'])
    ww = np.sqrt(np.interp(tt, rate['t'], rate['R']) ** 2 + np.interp(tt, rate['t'], rate['P']) ** 2 +
                 np.interp(tt, rate['t'], rate['Y']) ** 2)
    ok = (pit < -15) & (np.abs(rol) < 30) & (ww < 90)
    tt, crs, = tt[ok], crs[ok]
    print(f'  course check: {ok.sum()} GPS samples at >8 m/s, nose down 15+ deg, |roll|<30, |w|<90')
    if ok.sum() < 5:
        continue
    mh = iang({'t': t, 'h': magH}, 'h', tt)
    ey = iang(x1, 'Yaw', tt)
    gy = iang(ky, 'YC', tt)
    kr = np.interp(tt, t, krpm)
    for name, h in (('compass', mh), ('EKF yaw', ey), ('GSF yaw', gy)):
        e = wrap(h - crs)
        print(f'    {name:8} - course: median {np.median(e):6.1f}  p25 {np.percentile(e, 25):6.1f}  '
              f'p75 {np.percentile(e, 75):6.1f}  |e|>45: {np.mean(np.abs(e) > 45) * 100:4.0f}%')
    e = wrap(mh - crs)
    for lo, hi in ((0, 45), (45, 55), (55, 65), (65, 200)):
        k = (kr >= lo) & (kr < hi)
        if k.sum() >= 3:
            print(f'    compass - course at {lo}-{hi} kRPM: n {k.sum():3d}  median |e| {np.median(np.abs(e[k])):5.1f}')
