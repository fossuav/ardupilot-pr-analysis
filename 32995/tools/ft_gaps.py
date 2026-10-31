"""List RTDT windows with dtMax over a threshold, with arm state, events
within 1 s and the nearest PM row (long loops, MaxT). A window is marked
armed from the ARMED event's timestamp, so the 0.1 s window that holds the
arming instant counts as armed.
usage: python3 ft_gaps.py LOG.pkl [THRESH_MS]
"""
import pickle
import sys
import numpy as np

d = pickle.load(open(sys.argv[1], 'rb'))
th = float(sys.argv[2]) * 1e-3 if len(sys.argv) > 2 else 1.0e-3
r = d['RTDT']
ev = d['EV']
# AP_Logger LogEvent values
EVN = {10: 'ARMED', 11: 'DISARMED', 15: 'AUTO_ARMED', 17: 'LAND_COMPLETE_MAYBE', 18: 'LAND_COMPLETE',
       25: 'SET_HOME', 28: 'NOT_LANDED', 56: 'INTERLOCK_DISABLED', 57: 'INTERLOCK_ENABLED',
       60: 'EKF_ALT_RESET', 62: 'EKF_YAW_RESET'}
arm_t = [t for t, i in zip(ev['t'], ev['Id']) if i == 10]
dis_t = [t for t, i in zip(ev['t'], ev['Id']) if i == 11]


def armed(t):
    a = [x for x in arm_t if x <= t]
    b = [x for x in dis_t if x <= t]
    return bool(a) and (not b or a[-1] > b[-1])


pm = d['PM']
for t, mx in zip(r['t'], r['dtMax']):
    if mx > th:
        near = [f'{EVN.get(int(i), int(i))}@{te:.2f}' for te, i in zip(ev['t'], ev['Id']) if abs(te - t) < 1.0]
        k = np.argmin(np.abs(pm['t'] - t))
        print(f'{t:8.2f} s dtMax {mx * 1e3:5.2f} ms armed={armed(t)} '
              f'PM@{pm["t"][k]:.1f}: NLon {pm["NLon"][k]} MaxT {pm["MaxT"][k] * 1e-3:.2f} ms  {" ".join(near)}')
