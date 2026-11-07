"""A DSF.Dp drop: per-type gaps in the
logged stream around it, and the rate thread and PM rows there.
usage: python3 ft_dropgap.py LOG.pkl FROM TO
"""
import pickle
import sys

import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
a, b = float(sys.argv[2]), float(sys.argv[3])
print('largest gap per type in the window (type: gap from-to, normal spacing)')
for name in sorted(d):
    m = d[name]
    if not isinstance(m, dict) or 't' not in m:
        continue
    tt = np.unique(m['t'][(m['t'] >= a) & (m['t'] <= b)])
    if len(tt) < 3:
        continue
    dt = np.diff(tt)
    k = np.argmax(dt)
    print(f'  {name:5s} {dt[k]:6.3f} s  {tt[k]:9.3f}-{tt[k + 1]:9.3f}  median {np.median(dt):.3f}')
r = d['RTDT']
i = (r['t'] >= a) & (r['t'] <= b)
print('\nRTDT dtMax over 1 ms:', [(round(float(x), 2), round(float(y) * 1e3, 2)) for x, y in zip(r['t'][i], r['dtMax'][i]) if y > 1e-3])
p = d['PM']
i = (p['t'] >= a - 10) & (p['t'] <= b + 10)
for k in np.where(i)[0]:
    print(f'  PM {p["t"][k]:8.2f}  NLon {p["NLon"][k]:.0f}  MaxT {p["MaxT"][k]} us  Load {p["Load"][k]}  Mem {p["Mem"][k]}')
