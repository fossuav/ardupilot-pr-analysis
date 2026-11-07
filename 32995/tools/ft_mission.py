"""Auto mission, leg by leg: length, time, speed, position controller error,
altitude error, lean and current, from the 'Mission: N' / 'Reached command
#N' messages; then a 1 s trace of the mission's last item and after.

usage: python3 ft_mission.py LOG.pkl ORIGIN_LAT,ORIGIN_LNG WP.csv [TAIL_FROM TAIL_TO]
WP.csv holds one 'index,lat,lng,alt' line per NAV item with a location.
"""
import pickle
import re
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
olat, olng = (float(x) for x in sys.argv[2].split(','))
wps = {}
for line in open(sys.argv[3]):
    if line.strip():
        i, la, lo, al = line.split(',')
        wps[int(i)] = (float(la), float(lo), float(al))
R_E = 6378137.0


def ne(lat, lng):
    return (np.radians(lat - olat) * R_E, np.radians(lng - olng) * R_E * np.cos(np.radians(olat)))


x1 = {k: v[d['XKF1']['C'] == 0] for k, v in d['XKF1'].items() if isinstance(v, np.ndarray)}
pn, pe = d['PSCN'], d['PSCE']
ct, att, bat = d['CTUN'], d['ATT'], d['BAT']
g = {k: v[d['GPS']['I'] == 0] for k, v in d['GPS'].items() if isinstance(v, np.ndarray)}
msg = d['MSG']
events = []
for t, m in zip(msg['t'], msg['Message']):
    m = m.decode() if isinstance(m, bytes) else str(m)
    a = re.match(r'Mission: (\d+) (\w+)', m)
    b = re.match(r'Reached command #(\d+)', m)
    if a:
        events.append((t, 'start', int(a.group(1)), a.group(2)))
    elif b:
        events.append((t, 'reached', int(b.group(1)), ''))


def win(m, a, b):
    i = (m['t'] >= a) & (m['t'] <= b)
    return {k: v[i] for k, v in m.items() if isinstance(v, np.ndarray)}


print(' item  kind        start    time  length  mean/max spd  pos err max  alt err max  lean max  curr max  dist at reach')
starts = [(t, n, k) for t, e, n, k in events if e == 'start']
for j, (t0, n, kind) in enumerate(starts):
    t1 = next((t for t, e, m, _ in events if e == 'reached' and m == n), None)
    tend = t1 if t1 is not None else (starts[j + 1][0] if j + 1 < len(starts) else t0)
    if tend <= t0:
        print(f'  {n:3d}  {kind:10s} {t0:7.1f}  (no end)')
        continue
    gg = win(g, t0, tend)
    p1, p2 = win(pn, t0, tend), win(pe, t0, tend)
    k = min(len(p1['t']), len(p2['t']))
    perr = np.hypot(p1['TPN'][:k] - p1['PN'][:k], p2['TPE'][:k] - p2['PE'][:k])
    c = win(ct, t0, tend)
    aa = win(att, t0, tend)
    bb = win(bat, t0, tend)
    length = dist = float('nan')
    if n in wps:
        wn, we = ne(wps[n][0], wps[n][1])
        prev = max((m for m in wps if m < n), default=None)
        if prev is not None:
            qn, qe = ne(wps[prev][0], wps[prev][1])
            length = np.hypot(wn - qn, we - qe)
        if t1 is not None:
            dist = np.hypot(np.interp(t1, x1['t'], x1['PN']) - wn, np.interp(t1, x1['t'], x1['PE']) - we)
    lean = np.degrees(np.arccos(np.cos(np.radians(aa['Roll'])) * np.cos(np.radians(aa['Pitch']))))
    print(f'  {n:3d}  {kind:10s} {t0:7.1f} {tend - t0:6.1f}  {length:6.1f}   {np.mean(gg["Spd"]):5.1f}/{np.max(gg["Spd"]):5.1f}'
          f'     {np.max(perr) if k else float("nan"):6.2f}      {np.max(np.abs(c["DAlt"] - c["Alt"])):6.2f}'
          f'     {np.max(lean):5.1f}    {np.max(bb["Curr"]):5.1f}    {dist:6.1f}')

if len(sys.argv) > 5:
    a, b = float(sys.argv[4]), float(sys.argv[5])
    print('\n   t      N       E    dist   alt   DAlt   CRt  gspd  ThO   mode')
    mt, mm = d['MODE']['t'], d['MODE']['Mode']
    for tt in np.arange(a, b, 1.0):
        n_ = np.interp(tt, x1['t'], x1['PN'])
        e_ = np.interp(tt, x1['t'], x1['PE'])
        mode = int(mm[mt <= tt][-1]) if (mt <= tt).any() else -1
        print(f'  {tt:6.1f} {n_:6.1f} {e_:6.1f} {np.hypot(n_, e_):6.1f} {np.interp(tt, ct["t"], ct["Alt"]):5.1f}'
              f' {np.interp(tt, ct["t"], ct["DAlt"]):5.1f} {np.interp(tt, ct["t"], ct["CRt"]):5.1f}'
              f' {np.interp(tt, g["t"], g["Spd"]):5.1f} {np.interp(tt, ct["t"], ct["ThO"]):5.2f}  {mode}')
