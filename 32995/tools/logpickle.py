"""Load selected DataFlash messages into numpy arrays and pickle them.

usage: python3 logpickle.py LOG.BIN OUT.pkl
Times are seconds from the first TimeUS in the log (log_extract.py's base).
"""
import pickle
import sys
from collections import defaultdict

import numpy as np
from pymavlink import DFReader

WANT = {
    'ATT', 'DCM', 'AHR2', 'XKF1', 'XKF2', 'XKF3', 'XKF4', 'XKY0', 'XKFS', 'MAG', 'GPS', 'GPA',
    'BAT', 'CTUN', 'RCOU', 'RCIN', 'MODE', 'MSG', 'ESC', 'VIBE', 'PM', 'RTDT', 'XKT', 'DSF',
    'MCU', 'POWR', 'UBX2', 'UART', 'RATE', 'PSCN', 'PSCE', 'EV', 'ERR', 'MOTB', 'IMU', 'BARO', 'RSSI',
}

log = DFReader.DFReader_binary(sys.argv[1], zero_time_base=False)
rows = defaultdict(list)
cols = {}
t0 = None
while True:
    m = log.recv_msg()
    if m is None:
        break
    name = m.get_type()
    if name not in WANT:
        if t0 is None and hasattr(m, 'TimeUS'):
            t0 = m.TimeUS
        continue
    d = m.to_dict()
    if t0 is None and 'TimeUS' in d:
        t0 = d['TimeUS']
    if name not in cols:
        cols[name] = [k for k in d if k != 'mavpackettype']
    rows[name].append([d.get(k) for k in cols[name]])

out = {'t0': t0}
for name, r in rows.items():
    c = cols[name]
    arr = {}
    for i, k in enumerate(c):
        v = [x[i] for x in r]
        if k == 'TimeUS':
            arr['t'] = (np.array(v, dtype=float) - t0) * 1e-6
        try:
            arr[k] = np.array(v, dtype=float)
        except (TypeError, ValueError):
            arr[k] = v
    out[name] = arr
with open(sys.argv[2], 'wb') as f:
    pickle.dump(out, f)
print({k: len(v.get('t', [])) for k, v in out.items() if k != 't0'})
