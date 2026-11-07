"""The compass arming check rebuilt from a log, with and without the motor
compensation (MAG.MO), and the GPS acquisition timeline.

AP_Arming::compass_checks() rotates the field to NED with the AHRS attitude,
subtracts the earth field and fails when max(|dN|, |dE|) exceeds
ARMING_MAGTHRESH. BE is the earth field in mG, NED, for example the one
ft_magcoupling.py fits from a flight at the same site.

Also prints the compass heading (Compass::calculate_heading(), no
declination) with and without MO, and the EKF yaw, per bin.

usage: python3 ft_magarm.py LOG.pkl BN,BE,BD [STEP]
"""
import pickle
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
BE = np.array([float(x) for x in sys.argv[2].split(',')])
step = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0

mag = {k: v[d['MAG']['I'] == 0] for k, v in d['MAG'].items() if isinstance(v, np.ndarray)}
att = d['ATT']
x1 = {k: v[d['XKF1']['C'] == 0] for k, v in d['XKF1'].items() if isinstance(v, np.ndarray)}
t = mag['t']


def iang(f):
    return np.radians(np.interp(t, att['t'], np.unwrap(att[f], period=360)))


def heading(m, roll, pitch):
    cx, cy, cz = -np.sin(pitch), np.sin(roll) * np.cos(pitch), np.cos(roll) * np.cos(pitch)
    hy = m[:, 1] * cz - m[:, 2] * cy
    hx = m[:, 0] * (1 - cx * cx) - cx * (m[:, 1] * cy + m[:, 2] * cz)
    return np.degrees(np.arctan2(-hy, hx)) % 360


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


r, p, y = iang('Roll'), iang('Pitch'), iang('Yaw')
cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
R = np.array([
    [cp * cy, sr * sp * cy - cr * sy, cr * sp * cy + sr * sy],
    [cp * sy, sr * sp * sy + cr * cy, cr * sp * sy - sr * cy],
    [-sp, sr * cp, cr * cp],
]).transpose(2, 0, 1)
mb = np.stack([mag['MagX'], mag['MagY'], mag['MagZ']], 1)
mo = np.stack([mag['MOX'], mag['MOY'], mag['MOZ']], 1)
ef = np.einsum('nij,nj->ni', R, mb)
ef0 = np.einsum('nij,nj->ni', R, mb - mo)
h, h0 = heading(mb, r, p), heading(mb - mo, r, p)
ey = np.interp(t, x1['t'], np.unwrap(x1['Yaw'], period=360)) % 360
cur = np.interp(t, d['BAT']['t'], d['BAT']['Curr'])
mt = np.interp(t, d['MCU']['t'], d['MCU']['MTemp'])

print('arming check xy diff = max(|dN|,|dE|) against', BE, 'mG; medians per bin')
print('   bin          MCU   curr   |MO|  xydiff  no-MO   hdg  no-MO  shift   EKF')
for a in np.arange(0.0, t.max(), step):
    i = (t >= a) & (t < a + step)
    if not i.any():
        continue
    dd = np.abs(ef[i, :2] - BE[:2]).max(1)
    d0 = np.abs(ef0[i, :2] - BE[:2]).max(1)
    print(f'  {a:6.0f}-{a + step:<6.0f} {mt[i].mean():5.1f} {cur[i].mean():5.1f} {np.linalg.norm(mo[i], axis=1).mean():6.0f}'
          f'  {np.median(dd):6.0f} {np.median(d0):6.0f}  {np.median(h[i]):5.0f} {np.median(h0[i]):5.0f}'
          f' {np.median(wrap(h[i] - h0[i])):+6.1f} {np.median(ey[i]):5.0f}')

g = {k: v[d['GPS']['I'] == 0] for k, v in d['GPS'].items() if isinstance(v, np.ndarray)}
ga = {k: v[d['GPA']['I'] == 0] for k, v in d['GPA'].items() if isinstance(v, np.ndarray)}
u = d['UBX2']
print('\nGPS per bin: status (min-max), sats, HDop, HAcc, SAcc, VAcc, UBX2 magI min')
for a in np.arange(0.0, g['t'].max(), step):
    i = (g['t'] >= a) & (g['t'] < a + step)
    j = (ga['t'] >= a) & (ga['t'] < a + step)
    m = (u['t'] >= a) & (u['t'] < a + step)
    if not i.any():
        continue
    print(f'  {a:6.0f}  st {int(g["Status"][i].min())}-{int(g["Status"][i].max())}'
          f'  sats {int(g["NSats"][i].min()):2d}-{int(g["NSats"][i].max()):2d}  hdop {np.median(g["HDop"][i]):5.2f}'
          f'  hacc {np.median(ga["HAcc"][j]):6.2f}  sacc {np.median(ga["SAcc"][j]):6.2f}  vacc {np.median(ga["VAcc"][j]):6.2f}'
          f'  magI {u["magI"][m].min() if m.any() else -1:4.0f}')
f3 = g['t'][g['Status'] >= 3]
print('first 3D fix at', round(float(f3[0]), 1) if len(f3) else None)
