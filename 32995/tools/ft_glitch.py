"""For each 'GPS Glitch or Compass error' message: receiver speed accuracy and
EKF test ratios in the 2 s before it, plus speed, load and board temperature.
usage: python3 ft_glitch.py LOG.pkl
"""
import pickle
import sys
import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))


def sel(msg, k, v):
    m = d[msg]
    i = m[k] == v
    return {f: x[i] for f, x in m.items() if isinstance(x, np.ndarray)}


gpa, gps, x4 = sel('GPA', 'I', 0), sel('GPS', 'I', 0), sel('XKF4', 'C', 0)
x3 = sel('XKF3', 'C', 0)
msg = d['MSG']
esc = d['ESC']
for t, text in zip(msg['t'], msg['Message']):
    if 'Glitch' not in str(text):
        continue
    w = lambda m: (m['t'] >= t - 2.0) & (m['t'] <= t)
    a, g, k, k3 = w(gpa), w(gps), w(x4), w(x3)
    krpm = sum(np.interp(t, esc['t'][esc['Instance'] == i], esc['RPM'][esc['Instance'] == i]) for i in range(4)) / 1e3
    print(f'{t:8.2f} s {str(text):28s} SAcc max {np.max(gpa["SAcc"][a]):4.2f} m/s  HAcc max {np.max(gpa["HAcc"][a]):4.2f} m  '
          f'SV max {np.max(x4["SV"][k]):4.2f}  SP max {np.max(x4["SP"][k]):4.2f}  SM max {np.max(x4["SM"][k]):4.2f}  '
          f'IV max {np.max(np.hypot(x3["IVN"][k3], x3["IVE"][k3])):4.1f} m/s  '
          f'spd {np.mean(gps["Spd"][g]):4.1f} m/s  sats {np.min(gps["NSats"][g]):.0f}  kRPM {krpm:4.0f}')
