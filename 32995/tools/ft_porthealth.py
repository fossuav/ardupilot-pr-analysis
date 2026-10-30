"""RP2350 port health over armed segments.

usage: python3 ft_porthealth.py LOG.pkl FROM:TO[,...]
"""
import pickle
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
segs = [tuple(float(x) for x in s.split(':')) for s in sys.argv[2].split(',')]


def win(msg, a, b, k=None, v=None):
    m = d[msg]
    i = (m['t'] >= a) & (m['t'] <= b)
    if k is not None:
        i &= m[k] == v
    return {f: x[i] for f, x in m.items() if isinstance(x, np.ndarray)}


print('IMU instances:', sorted(set(d['IMU']['I'].astype(int))))
for a, b in segs:
    print(f'=== {a:.0f}-{b:.0f} s ({b - a:.0f} s)')
    r = win('RTDT', a, b)
    print(f'  rate loop: dtAvg {np.mean(r["dtAvg"]) * 1e6:.1f} us ({1 / np.mean(r["dtAvg"]):.0f} Hz), '
          f'dtMax worst {np.max(r["dtMax"]) * 1e3:.2f} ms, p99 {np.percentile(r["dtMax"], 99) * 1e3:.2f} ms, '
          f'dtMin {np.min(r["dtMin"]) * 1e6:.0f} us, '
          f'windows with dtMax>1ms: {np.mean(r["dtMax"] > 1e-3) * 100:.1f}%')
    p = win('PM', a, b)
    if len(p['t']):
        print(f'  PM: loop {np.min(p["LR"]):.0f}-{np.max(p["LR"]):.0f} Hz, long loops {np.sum(p["NLon"]):.0f} '
              f'of {np.sum(p["NL"]):.0f}, MaxT {np.max(p["MaxT"]) / 1000:.2f} ms, load {np.min(p["Load"]) / 10:.1f}-'
              f'{np.max(p["Load"]) / 10:.1f}%, mem {np.min(p["Mem"]):.0f}, ErrL {np.max(p["ErrL"]):.0f}, '
              f'InE {np.max(p["InE"]):.0f}')
    x = win('XKT', a, b, 'C', 0)
    if len(x['t']):
        print(f'  EKF timing: IMU dt {np.min(x["IMUMin"]) * 1e3:.2f}-{np.max(x["IMUMax"]) * 1e3:.2f} ms, '
              f'EKF dt {np.min(x["EKFMin"]) * 1e3:.2f}-{np.max(x["EKFMax"]) * 1e3:.2f} ms, '
              f'dAng dt {np.min(x["AngMin"]) * 1e3:.2f}-{np.max(x["AngMax"]) * 1e3:.2f} ms, '
              f'dVel dt {np.min(x["VMin"]) * 1e3:.2f}-{np.max(x["VMax"]) * 1e3:.2f} ms')
    ds = win('DSF', a, b)
    if len(ds['t']):
        print(f'  logging: dropped {np.max(ds["Dp"]) - np.min(ds["Dp"]):.0f} (total {np.max(ds["Dp"]):.0f}), '
              f'free min {np.min(ds["FMn"]):.0f} B')
    u = win('UART', a, b)
    for inst in sorted(set(u['I'].astype(int))):
        k = u['I'] == inst
        print(f'  UART{inst}: tx {np.mean(u["Tx"][k]):.0f} B/s, rx {np.mean(u["Rx"][k]):.0f} B/s, '
              f'rx dropped {np.max(u["RxDp"][k]) - np.min(u["RxDp"][k]):.0f}')
    e = win('ESC', a, b)
    for inst in range(4):
        k = e['Instance'] == inst
        if k.any():
            print(f'  ESC{inst}: {k.sum() / (b - a):.0f} Hz, RPM {np.min(e["RPM"][k]):.0f}-{np.max(e["RPM"][k]):.0f}, '
                  f'Err mean {np.mean(e["Err"][k]):.2f}% max {np.max(e["Err"][k]):.1f}%')
    m = win('MCU', a, b)
    print(f'  MCU temp {np.min(m["MTemp"]):.1f}-{np.max(m["MTemp"]):.1f} C')
    pw = win('POWR', a, b)
    print(f'  Vcc {np.min(pw["Vcc"]):.2f}-{np.max(pw["Vcc"]):.2f} V')
    rs = win('RSSI', a, b) if 'RSSI' in d else None
    rc = win('RCIN', a, b)
    print(f'  RCIN {len(rc["t"]) / (b - a):.0f} Hz logged, ch3 {np.min(rc["C3"]):.0f}-{np.max(rc["C3"]):.0f}')
    g = win('GPS', a, b, 'I', 0)
    ga = win('GPA', a, b, 'I', 0)
    print(f'  GPS: {len(g["t"]) / (b - a):.1f} Hz, sats {np.min(g["NSats"]):.0f}-{np.max(g["NSats"]):.0f} '
          f'(median {np.median(g["NSats"]):.0f}), HDop median {np.median(g["HDop"]):.2f}, '
          f'HAcc median {np.median(ga["HAcc"]):.2f} p95 {np.percentile(ga["HAcc"], 95):.2f} m, '
          f'SAcc median {np.median(ga["SAcc"]):.2f} p95 {np.percentile(ga["SAcc"], 95):.2f} m/s, '
          f'Delta {np.min(ga["Delta"]):.0f}-{np.max(ga["Delta"]):.0f} ms')
    ub = win('UBX2', a, b)
    if len(ub['t']):
        print(f'  UBX2 magI {np.min(ub["magI"]):.0f}-{np.max(ub["magI"]):.0f}, magQ {np.min(ub["magQ"]):.0f}-{np.max(ub["magQ"]):.0f}')
