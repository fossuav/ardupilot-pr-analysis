"""Counterfactual compass compensation: replace the logged motor offset with
COMPASS_MOT x a temperature-corrected current (and, separately, x the eRPM
model current) and repeat the heading-against-GPS-course check by load.

usage: python3 ft_compcf.py LOG.pkl FROM TO PERVLT OFFSET MOTX,MOTY,MOTZ Z0 ZT GAIN
  zero(T) = Z0 + ZT*T mV, GAIN mV/A (from currmodel.py)
"""
import pickle
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
a, b = float(sys.argv[2]), float(sys.argv[3])
pervlt, offset = float(sys.argv[4]), float(sys.argv[5])
mot = np.array([float(x) for x in sys.argv[6].split(',')])
z0, zt, gain = float(sys.argv[7]), float(sys.argv[8]), float(sys.argv[9])


def sub(msg, k=None, v=None):
    m = d[msg]
    i = np.ones(len(m['t']), bool) if k is None else (m[k] == v)
    return {f: x[i] for f, x in m.items() if isinstance(x, np.ndarray)}


def wrap(x):
    return (x + 180.0) % 360.0 - 180.0


mag, dcm, att, rate = sub('MAG', 'I', 0), sub('DCM'), sub('ATT'), sub('RATE')
gps, bat, esc = sub('GPS', 'I', 0), sub('BAT', 'Inst', 0), sub('ESC')
t = mag['t']
pin = (np.interp(t, bat['t'], bat['Curr']) / pervlt + offset) * 1000.0
mt = np.interp(t, d['MCU']['t'], d['MCU']['MTemp'])
i_corr = (pin - (z0 + zt * mt)) / gain
load = np.zeros_like(t)
for i in range(4):
    j = esc['Instance'] == i
    load += (np.interp(t, esc['t'][j], esc['RPM'][j]) / 1000.0) ** 3
i_rpm = np.where(load > 0, 0.5 + 9.0e-4 * load, 0.0)
krpm = np.zeros_like(t)
for i in range(4):
    j = esc['Instance'] == i
    krpm += np.interp(t, esc['t'][j], esc['RPM'][j]) / 1000.0
raw = np.stack([mag['MagX'] - mag['MOX'], mag['MagY'] - mag['MOY'], mag['MagZ'] - mag['MOZ']], axis=1)
logged = np.stack([mag['MagX'], mag['MagY'], mag['MagZ']], axis=1)
r = np.radians(np.interp(t, dcm['t'], dcm['Roll']))
p = np.radians(np.interp(t, dcm['t'], dcm['Pitch']))
cx, cy, cz = -np.sin(p), np.sin(r) * np.cos(p), np.cos(r) * np.cos(p)


def heading(B):
    fx, fy, fz = B[:, 0], B[:, 1], B[:, 2]
    hY = fy * cz - fz * cy
    hX = fx * (1 - cx * cx) - cx * (fy * cy + fz * cz)
    return np.degrees(np.arctan2(-hY, hX)) % 360.0, np.hypot(hX, hY)


variants = {
    'as flown': logged,
    'no compensation': raw,
    'temp-corrected current': raw + np.outer(i_corr, mot),
    'eRPM-model current': raw + np.outer(i_rpm, mot),
}
gs = (gps['t'] >= a) & (gps['t'] <= b) & (gps['Spd'] > 8)
tt, crs = gps['t'][gs], gps['GCrs'][gs]
pit = np.interp(tt, att['t'], att['Pitch'])
rol = np.interp(tt, att['t'], att['Roll'])
ww = np.sqrt(np.interp(tt, rate['t'], rate['R']) ** 2 + np.interp(tt, rate['t'], rate['P']) ** 2 +
             np.interp(tt, rate['t'], rate['Y']) ** 2)
ok = (pit < -15) & (np.abs(rol) < 30) & (ww < 90)
tt, crs = tt[ok], crs[ok]
kr = np.interp(tt, t, krpm)
print(f'{len(tt)} GPS samples; reported minus corrected current: median '
      f'{np.median((pin / 1000 - offset) * pervlt - i_corr):+.2f} A; corrected minus eRPM model: '
      f'median {np.median(i_corr[i_rpm > 0] - i_rpm[i_rpm > 0]):+.2f} A')
bins = ((0, 45), (45, 55), (55, 65), (65, 200))
print(f'{"variant":>24} {"median":>7} {"IQR":>13} {"|e|>45":>7}  ' + '  '.join(f'{lo}-{hi}k' for lo, hi in bins))
for name, B in variants.items():
    h, bh = heading(B)
    x = np.unwrap(np.radians(h))
    hh = np.degrees(np.interp(tt, t, x)) % 360.0
    e = wrap(hh - crs)
    cols = []
    for lo, hi in bins:
        k = (kr >= lo) & (kr < hi)
        cols.append(f'{np.median(np.abs(e[k])):5.1f}' if k.sum() >= 5 else '    -')
    print(f'{name:>24} {np.median(e):7.1f} {np.percentile(e, 25):6.1f}..{np.percentile(e, 75):5.1f} '
          f'{np.mean(np.abs(e) > 45) * 100:6.0f}%  ' + '   '.join(cols))
