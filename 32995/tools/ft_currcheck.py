"""Is the analog current input usable? Compares the pin voltage reconstructed
from BAT.Curr (Curr / AMP_PERVLT + AMP_OFFSET) against two load references:
the DEVELOPMENT.md eRPM model and the pack voltage sag, per flight, on 0.5 s
differences so slow drift (temperature, discharge) drops out. Also reports
the disarmed zero against MCU temperature and VTX relay steps.

usage: python3 ft_currcheck.py LOG.pkl PERVLT OFFSET FLY_FROM:FLY_TO[,...] [RELAY_T,...]
"""
import pickle
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
pervlt, offset = float(sys.argv[2]), float(sys.argv[3])
segs = [tuple(float(x) for x in s.split(':')) for s in sys.argv[4].split(',')]
relays = [float(x) for x in sys.argv[5].split(',')] if len(sys.argv) > 5 else []

bat = {k: v[d['BAT']['Inst'] == 0] for k, v in d['BAT'].items() if isinstance(v, np.ndarray)}
t = bat['t']
vpin = (bat['Curr'] / pervlt + offset) * 1000.0  # mV at the pin
esc = d['ESC']
load = np.zeros_like(t)
for i in range(4):
    j = esc['Instance'] == i
    load += (np.interp(t, esc['t'][j], esc['RPM'][j]) / 1000.0) ** 3
irpm = 0.5 + 9.0e-4 * load
mt = np.interp(t, d['MCU']['t'], d['MCU']['MTemp'])
volt = bat['Volt']
ev = d['EV']
arm_t = ev['t'][ev['Id'] == 10]
dis_t = ev['t'][ev['Id'] == 11]


def diffs(x, tt, dt=0.5):
    tg = np.arange(tt[0], tt[-1] - dt, dt)
    xi = np.interp(tg, tt, x)
    return np.diff(xi)


print(f'BAT logged at {len(t) / (t[-1] - t[0]):.0f} Hz; pin = Curr/{pervlt:g} + {offset * 1000:.1f} mV')
for a, b in segs:
    s = (t >= a) & (t <= b)
    print(f'=== flight {a:.0f}-{b:.0f} s')
    print(f'  reported current: median {np.median(bat["Curr"][s]):.2f} A, range {np.min(bat["Curr"][s]):.2f}-'
          f'{np.max(bat["Curr"][s]):.2f}; pin {np.min(vpin[s]):.1f}-{np.max(vpin[s]):.1f} mV')
    print(f'  eRPM model:       median {np.median(irpm[s]):.2f} A, p95 {np.percentile(irpm[s], 95):.1f}, '
          f'max {np.max(irpm[s]):.1f}')
    print(f'  pack: {np.max(volt[s]):.2f} -> {np.min(volt[s]):.2f} V, MCU {np.min(mt[s]):.1f}-{np.max(mt[s]):.1f} C')
    tt = t[s]
    dp, di, dv = diffs(vpin[s], tt), diffs(irpm[s], tt), diffs(volt[s], tt)
    ok = np.abs(di) > 0  # keep all; report correlation and slope
    r_pi = np.corrcoef(dp, di)[0, 1]
    r_vi = np.corrcoef(-dv, di)[0, 1]
    r_pv = np.corrcoef(dp, -dv)[0, 1]
    g_pi = np.polyfit(di, dp, 1)[0]
    R = np.polyfit(di, -dv, 1)[0]
    g_pv = np.polyfit(-dv, dp, 1)[0]
    print(f'  0.5 s differences, n={len(dp)}:')
    print(f'    sag vs eRPM model:  r={r_vi:.2f}, implied pack+wiring resistance {R * 1000:.0f} mOhm')
    print(f'    pin vs eRPM model:  r={r_pi:.2f}, gain {g_pi:.2f} mV/A')
    print(f'    pin vs sag:         r={r_pv:.2f}, {g_pv:.1f} mV per V of sag -> {g_pv * R:.2f} mV/A at that resistance')
    # level, not differences: does the pin follow load across the flight?
    big = s & (irpm > np.percentile(irpm[s], 80))
    small = s & (irpm < np.percentile(irpm[s], 20))
    print(f'    level: top-20% load {np.median(irpm[big]):.1f} A -> pin {np.median(vpin[big]):.1f} mV; '
          f'bottom-20% {np.median(irpm[small]):.1f} A -> pin {np.median(vpin[small]):.1f} mV')
    ct = bat['CurrTot'][s]
    e_mah = np.trapezoid(irpm[s], tt) / 3.6
    print(f'  mAh in flight: logged {ct[-1] - ct[0]:.0f}, eRPM model {e_mah:.0f}')

# disarmed zero: pin and MCU temperature in still, disarmed periods with no load
print('=== disarmed zero (motors stopped)')
dis = np.ones_like(t, bool)
for a0 in arm_t:
    nxt = dis_t[dis_t > a0]
    b0 = nxt[0] if len(nxt) else t[-1]
    dis &= ~((t >= a0 - 1) & (t <= b0 + 1))
dis &= load == 0
for lo, hi in zip(np.arange(t[0], t[-1], 60), np.arange(t[0], t[-1], 60) + 60):
    k = dis & (t >= lo) & (t < hi)
    if k.sum() > 50:
        print(f'  {lo:5.0f}-{hi:<5.0f} pin {np.median(vpin[k]):5.1f} mV  MCU {np.median(mt[k]):4.1f} C  '
              f'pack {np.median(volt[k]):.2f} V')
if dis.sum() > 100:
    c = np.polyfit(mt[dis], vpin[dis], 1)
    print(f'  pin against MCU temperature, all disarmed: {c[0]:.2f} mV/C, r={np.corrcoef(mt[dis], vpin[dis])[0, 1]:.2f}')
for rt in relays:
    k0 = (t >= rt - 3) & (t < rt - 0.3)
    k1 = (t > rt + 0.3) & (t <= rt + 3)
    print(f'  relay2 change at {rt:.1f} s: pin {np.median(vpin[k0]):.1f} -> {np.median(vpin[k1]):.1f} mV, '
          f'pack {np.median(volt[k0]):.2f} -> {np.median(volt[k1]):.2f} V, armed '
          f'{bool(np.any((arm_t < rt) & ~np.array([np.any((dis_t > a1) & (dis_t < rt)) for a1 in arm_t])))}')
