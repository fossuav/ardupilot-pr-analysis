"""1 s timeline of GPS, compass, EKF and attitude for an armed window.

usage: python3 ft_timeline.py LOG.pkl FROM TO [STEP]
"""
import pickle
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
t_from, t_to = float(sys.argv[2]), float(sys.argv[3])
step = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0


def sel(msg, cond=None):
    m = d[msg]
    if cond is None:
        return m
    k, v = cond
    idx = m[k] == v
    return {f: (a[idx] if isinstance(a, np.ndarray) else [x for x, i in zip(a, idx) if i]) for f, a in m.items()}


def interp(m, f, t):
    return np.interp(t, m['t'], m[f])


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def interp_angle(m, f, t):
    a = np.unwrap(np.radians(m[f]))
    return np.degrees(np.interp(t, m['t'], a)) % 360.0


mag = sel('MAG', ('I', 0))
att = d['ATT']
dcm = d['DCM']
x1 = sel('XKF1', ('C', 0))
x3 = sel('XKF3', ('C', 0))
x4 = sel('XKF4', ('C', 0))
gps = sel('GPS', ('I', 0))
gpa = sel('GPA', ('I', 0))
bat = sel('BAT', ('Inst', 0))
ky = sel('XKY0', ('C', 0))
ctun = d['CTUN']
esc = d['ESC']

# tilt-compensated heading as Compass::calculate_heading(), roll/pitch from DCM
r = np.radians(interp(dcm, 'Roll', mag['t']))
p = np.radians(interp(dcm, 'Pitch', mag['t']))
cx, cy, cz = -np.sin(p), np.sin(r) * np.cos(p), np.cos(r) * np.cos(p)
fx, fy, fz = mag['MagX'], mag['MagY'], mag['MagZ']
headY = fy * cz - fz * cy
headX = fx * (1 - cx * cx) - cx * (fy * cy + fz * cz)
mag['hdg'] = np.degrees(np.arctan2(-headY, headX)) % 360.0
mag['B'] = np.sqrt(fx * fx + fy * fy + fz * fz)
mag['Bh'] = np.sqrt(headX ** 2 + headY ** 2)
mag['MO'] = np.sqrt(mag['MOX'] ** 2 + mag['MOY'] ** 2 + mag['MOZ'] ** 2)

# total eRPM per ESC sample time, summed over 4 instances on a common grid
grid = np.arange(t_from, t_to + 1e-9, step)
rpm = np.zeros_like(grid)
for inst in range(4):
    idx = esc['Instance'] == inst
    if idx.any():
        rpm += np.interp(grid, esc['t'][idx], esc['RPM'][idx])

modes = d['MODE']


def mode_at(t):
    i = np.searchsorted(modes['t'], t, side='right') - 1
    return int(modes['ModeNum'][i]) if i >= 0 else -1


MN = {0: 'STAB', 1: 'ACRO', 2: 'AHLD', 5: 'LOIT', 6: 'RTL', 9: 'LAND'}

hdr = ('t', 'md', 'ThO', 'Curr', 'kRPM', 'GSt', 'Sat', 'HDop', 'HAcc', 'Spd', '|B|', 'MO',
       'magH', 'ekfY', 'gsfY', 'YCS', 'm-e', 'g-e', 'SV', 'SP', 'SM', 'IVN', 'IVE', 'dRol', 'dPit', 'Roll', 'Pit')
print(' '.join(f'{h:>6}' for h in hdr))
for t in grid:
    def at(m, f, w=step / 2):
        i = (m['t'] >= t - w) & (m['t'] < t + w)
        return np.mean(m[f][i]) if i.any() else np.interp(t, m['t'], m[f])

    def mx(m, f, w=step / 2):
        i = (m['t'] >= t - w) & (m['t'] < t + w)
        return np.max(np.abs(m[f][i])) if i.any() else np.nan
    mh = interp_angle(mag, 'hdg', t)
    ey = interp_angle(x1, 'Yaw', t)
    gy = interp_angle(ky, 'YC', t) if len(ky['t']) else np.nan
    i = (att['t'] >= t - step / 2) & (att['t'] < t + step / 2)
    j = (dcm['t'] >= t - step / 2) & (dcm['t'] < t + step / 2)
    droll = np.interp(att['t'][i], dcm['t'], dcm['Roll']) - att['Roll'][i]
    dpit = np.interp(att['t'][i], dcm['t'], dcm['Pitch']) - att['Pitch'][i]
    vals = (t, MN.get(mode_at(t), str(mode_at(t))), at(ctun, 'ThO'), at(bat, 'Curr'), np.interp(t, grid, rpm) / 1000,
            at(gps, 'Status'), at(gps, 'NSats'), at(gps, 'HDop'), at(gpa, 'HAcc'), at(gps, 'Spd'),
            at(mag, 'B'), at(mag, 'MO'), mh, ey, gy, at(ky, 'YCS') if len(ky['t']) else np.nan,
            wrap(mh - ey), wrap(gy - ey), mx(x4, 'SV'), mx(x4, 'SP'), mx(x4, 'SM'),
            mx(x3, 'IVN'), mx(x3, 'IVE'),
            np.max(np.abs(droll)) * np.sign(droll[np.argmax(np.abs(droll))]) if len(droll) else np.nan,
            np.max(np.abs(dpit)) * np.sign(dpit[np.argmax(np.abs(dpit))]) if len(dpit) else np.nan,
            at(att, 'Roll'), at(att, 'Pitch'))
    out = []
    for v in vals:
        if isinstance(v, str):
            out.append(f'{v:>6}')
        elif abs(v) >= 1000:
            out.append(f'{v:6.0f}')
        else:
            out.append(f'{v:6.1f}' if abs(v) >= 10 or v == 0 else f'{v:6.2f}')
    print(' '.join(out))
