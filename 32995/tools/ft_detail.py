"""10 Hz detail of yaw, compass, GPS course and innovations in a window,
and a hover tilt check (mean specific force against EKF attitude).

usage: python3 ft_detail.py LOG.pkl FROM TO [hover]
"""
import pickle
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
a, b = float(sys.argv[2]), float(sys.argv[3])
hover = len(sys.argv) > 4


def sub(msg, k=None, v=None):
    m = d[msg]
    idx = np.ones(len(m['t']), bool) if k is None else (m[k] == v)
    return {f: x[idx] for f, x in m.items() if isinstance(x, np.ndarray)}


def iang(m, f, t):
    x = np.unwrap(np.radians(m[f]))
    return np.degrees(np.interp(t, m['t'], x)) % 360.0


def wrap(x):
    return (x + 180.0) % 360.0 - 180.0


mag, att, dcm, rate = sub('MAG', 'I', 0), sub('ATT'), sub('DCM'), sub('RATE')
x1, x3, x4, ky, gps = sub('XKF1', 'C', 0), sub('XKF3', 'C', 0), sub('XKF4', 'C', 0), sub('XKY0', 'C', 0), sub('GPS', 'I', 0)
fs = sub('XKFS', 'C', 0)
esc = sub('ESC')
t = mag['t']
r = np.radians(np.interp(t, dcm['t'], dcm['Roll']))
p = np.radians(np.interp(t, dcm['t'], dcm['Pitch']))
cx, cy, cz = -np.sin(p), np.sin(r) * np.cos(p), np.cos(r) * np.cos(p)
fx, fy, fz = mag['MagX'], mag['MagY'], mag['MagZ']
hY = fy * cz - fz * cy
hX = fx * (1 - cx * cx) - cx * (fy * cy + fz * cz)
magH = {'t': t, 'h': np.degrees(np.arctan2(-hY, hX)) % 360.0}

if not hover:
    print(f'{"t":>7} {"kRPM":>5} {"Spd":>5} {"crs":>5} {"magH":>5} {"ekfY":>5} {"gsfY":>5} {"m-c":>5} {"e-c":>5} '
          f'{"g-c":>5} {"SV":>5} {"SP":>5} {"SM":>5} {"IVN":>6} {"IVE":>6} {"MF":>3} {"ekfR":>6} {"dcmR":>6} {"ekfP":>6} {"dcmP":>6} {"wY":>5}')
    for tt in np.arange(a, b, 0.2):
        kr = sum(np.interp(tt, esc['t'][esc['Instance'] == i], esc['RPM'][esc['Instance'] == i]) for i in range(4)) / 1000
        g = np.argmin(np.abs(gps['t'] - tt))
        crs, spd = gps['GCrs'][g], gps['Spd'][g]
        mh, ey, gy = iang(magH, 'h', tt), iang(x1, 'Yaw', tt), iang(ky, 'YC', tt)
        k = np.argmin(np.abs(x4['t'] - tt))
        k3 = np.argmin(np.abs(x3['t'] - tt))
        kf = np.argmin(np.abs(fs['t'] - tt))
        print(f'{tt:7.1f} {kr:5.1f} {spd:5.1f} {crs:5.0f} {mh:5.0f} {ey:5.0f} {gy:5.0f} {wrap(mh - crs):5.0f} {wrap(ey - crs):5.0f} '
              f'{wrap(gy - crs):5.0f} {x4["SV"][k]:5.2f} {x4["SP"][k]:5.2f} {x4["SM"][k]:5.2f} {x3["IVN"][k3]:6.1f} {x3["IVE"][k3]:6.1f} '
              f'{fs["MAG_FUSION"][kf]:3.0f} {np.interp(tt, att["t"], att["Roll"]):6.1f} {np.interp(tt, dcm["t"], dcm["Roll"]):6.1f} '
              f'{np.interp(tt, att["t"], att["Pitch"]):6.1f} {np.interp(tt, dcm["t"], dcm["Pitch"]):6.1f} {np.interp(tt, rate["t"], rate["Y"]):5.0f}')
else:
    imu = sub('IMU', 'I', 0)
    print('hover tilt: mean specific force (corrected for mean EKF acceleration) against mean EKF/DCM attitude')
    print(f'{"win":>11} {"acc R":>6} {"acc P":>6} {"EKF R":>6} {"EKF P":>6} {"DCM R":>6} {"DCM P":>6} {"dVn":>5} {"dVe":>5}')
    for w0 in np.arange(a, b - 4.99, 5):
        w1 = w0 + 5
        i = (imu['t'] >= w0) & (imu['t'] < w1)
        j = (att['t'] >= w0) & (att['t'] < w1)
        k = (dcm['t'] >= w0) & (dcm['t'] < w1)
        # mean earth-frame acceleration from EKF velocity change, rotated into body with mean yaw
        vn0, vn1 = np.interp([w0, w1], x1['t'], x1['VN'])
        ve0, ve1 = np.interp([w0, w1], x1['t'], x1['VE'])
        an, ae = (vn1 - vn0) / 5, (ve1 - ve0) / 5
        yaw = np.radians(np.mean(iang(x1, 'Yaw', att['t'][j])))
        afwd = an * np.cos(yaw) + ae * np.sin(yaw)
        art = -an * np.sin(yaw) + ae * np.cos(yaw)
        # specific force = R^T (a - g); remove the horizontal acceleration part (small-angle)
        fxm = np.mean(imu['AccX'][i]) - afwd
        fym = np.mean(imu['AccY'][i]) - art
        fzm = np.mean(imu['AccZ'][i])
        ar = np.degrees(np.arctan2(-fym, -fzm))
        ap = np.degrees(np.arctan2(fxm, np.hypot(fym, fzm)))
        print(f'{w0:5.0f}-{w1:<5.0f} {ar:6.2f} {ap:6.2f} {np.mean(att["Roll"][j]):6.2f} {np.mean(att["Pitch"][j]):6.2f} '
              f'{np.mean(dcm["Roll"][k]):6.2f} {np.mean(dcm["Pitch"][k]):6.2f} {vn1 - vn0:5.1f} {ve1 - ve0:5.1f}')
