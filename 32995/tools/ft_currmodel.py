"""Fit pin = z0 + zT * MCU_temp + g * I_ref on one flight (plus its disarmed
periods), then predict the others. I_ref is the DEVELOPMENT.md eRPM model.
Reports the residual in amps, so it says whether a temperature-corrected
zero carries across flights and logs.

usage: python3 ft_currmodel.py FIT_LOG.pkl FIT_FROM:FIT_TO TEST_LOG.pkl:FROM:TO[,...]
"""
import os
import pickle
import sys

import numpy as np

# BATT_AMP_PERVLT and BATT_AMP_OFFSET the log was flown with
PERVLT = float(os.environ.get("PERVLT", 50))
OFFSET = float(os.environ.get("OFFSET", 0.0165))


def series(path, a, b):
    d = pickle.load(open(path, 'rb'))
    bat = {k: v[d['BAT']['Inst'] == 0] for k, v in d['BAT'].items() if isinstance(v, np.ndarray)}
    t = bat['t']
    s = (t >= a) & (t <= b)
    t = t[s]
    pin = (bat['Curr'][s] / PERVLT + OFFSET) * 1000.0
    esc = d['ESC']
    load = np.zeros_like(t)
    for i in range(4):
        j = esc['Instance'] == i
        load += (np.interp(t, esc['t'][j], esc['RPM'][j]) / 1000.0) ** 3
    iref = np.where(load > 0, 0.5 + 9.0e-4 * load, 0.5)
    mt = np.interp(t, d['MCU']['t'], d['MCU']['MTemp'])
    return pin, mt, iref


fpath = sys.argv[1]
fa, fb = (float(x) for x in sys.argv[2].split(':'))
pin, mt, iref = series(fpath, fa, fb)
X = np.stack([np.ones_like(pin), mt, iref], axis=1)
(z0, zT, g), *_ = np.linalg.lstsq(X, pin, rcond=None)
res = (pin - X @ np.array([z0, zT, g])) / g
print(f'fit on {fpath} {fa:.0f}-{fb:.0f}: pin = {z0:.1f} mV + {zT:.2f} mV/C x MCU + {g:.2f} mV/A x I')
print(f'  in-sample residual {np.sqrt(np.mean(res ** 2)):.2f} A rms')
for spec in sys.argv[3].split(','):
    path, a, b = spec.split(':')
    p, m, i = series(path, float(a), float(b))
    pred_i = (p - z0 - zT * m) / g
    err = pred_i - i
    print(f'  {path} {float(a):.0f}-{float(b):.0f}: corrected current median {np.median(pred_i):5.2f} A against '
          f'eRPM {np.median(i):5.2f} A; error median {np.median(err):+5.2f} A, rms {np.sqrt(np.mean(err ** 2)):.2f} A')
