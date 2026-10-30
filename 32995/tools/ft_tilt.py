"""Tilt checks: EKF and DCM roll/pitch against the accelerometer on still
segments, EKF tilt error over time, gyro range and clipping.

usage: python3 ft_tilt.py LOG.pkl STILL_FROM:STILL_TO[,...] FLY_FROM:FLY_TO
"""
import pickle
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
still = [tuple(float(x) for x in s.split(':')) for s in sys.argv[2].split(',')]
fa, fb = (float(x) for x in sys.argv[3].split(':'))

imu = {k: v[d['IMU']['I'] == 0] for k, v in d['IMU'].items() if isinstance(v, np.ndarray)}
att, dcm, ahr = d['ATT'], d['DCM'], d['AHR2']
x4 = {k: v[d['XKF4']['C'] == 0] for k, v in d['XKF4'].items() if isinstance(v, np.ndarray)}

print('still segments: roll/pitch in deg (accel = atan of mean specific force)')
print(f'{"seg":>11} {"acc R":>6} {"acc P":>6} {"EKF R":>6} {"EKF P":>6} {"DCM R":>6} {"DCM P":>6} '
      f'{"gyr sd":>7} {"errRP":>6}')
for a, b in still:
    i = (imu['t'] >= a) & (imu['t'] <= b)
    ax, ay, az = (np.mean(imu[k][i]) for k in ('AccX', 'AccY', 'AccZ'))
    gsd = max(np.std(imu[k][i]) for k in ('GyrX', 'GyrY', 'GyrZ'))
    ar = np.degrees(np.arctan2(-ay, -az))
    ap = np.degrees(np.arctan2(ax, np.hypot(ay, az)))
    j = (att['t'] >= a) & (att['t'] <= b)
    k = (dcm['t'] >= a) & (dcm['t'] <= b)
    e = (x4['t'] >= a) & (x4['t'] <= b)
    print(f'{a:5.0f}-{b:<5.0f} {ar:6.2f} {ap:6.2f} {np.mean(att["Roll"][j]):6.2f} {np.mean(att["Pitch"][j]):6.2f} '
          f'{np.mean(dcm["Roll"][k]):6.2f} {np.mean(dcm["Pitch"][k]):6.2f} {gsd:7.4f} {np.mean(x4["errRP"][e]):6.3f}')

i = (imu['t'] >= fa) & (imu['t'] <= fb)
print(f'\nflight {fa:.0f}-{fb:.0f}: IMU at {i.sum() / (fb - fa):.0f} Hz')
for k in ('GyrX', 'GyrY', 'GyrZ'):
    print(f'  max |{k}| {np.degrees(np.max(np.abs(imu[k][i]))):7.0f} deg/s')
for k in ('AccX', 'AccY', 'AccZ'):
    print(f'  max |{k}| {np.max(np.abs(imu[k][i])) / 9.81:5.1f} g')
v = d['VIBE']
j = (v['t'] >= fa) & (v['t'] <= fb) & (v['IMU'] == 0)
print(f'  VIBE X/Y/Z mean {np.mean(v["VibeX"][j]):.1f}/{np.mean(v["VibeY"][j]):.1f}/{np.mean(v["VibeZ"][j]):.1f}  '
      f'max {np.max(v["VibeX"][j]):.1f}/{np.max(v["VibeY"][j]):.1f}/{np.max(v["VibeZ"][j]):.1f}  '
      f'clip {np.min(v["Clip"][j]):.0f}->{np.max(v["Clip"][j]):.0f}')
e = (x4['t'] >= fa) & (x4['t'] <= fb)
print('  EKF errRP (tilt error, rad) by 10 s:')
for t0 in np.arange(fa, fb, 10):
    k = e & (x4['t'] >= t0) & (x4['t'] < t0 + 10)
    if k.any():
        print(f'    {t0:5.0f}: mean {np.mean(x4["errRP"][k]):.3f} max {np.max(x4["errRP"][k]):.3f}')
