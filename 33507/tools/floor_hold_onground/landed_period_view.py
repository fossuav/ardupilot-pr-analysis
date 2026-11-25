#!/usr/bin/env python3
"""Show what a vehicle did around an armed-landed period.

  landed_period_view.py LOG START_S DUR_S

Prints events and mode changes from 5 s before to 3 s after, and at 0.5 s
steps the range finder, throttle out, climb rate and EKF vertical velocity.
"""
import sys
from pymavlink import DFReader

path, start, dur = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
t0, t1 = start - 5, start + dur + 3
log = DFReader.DFReader_binary(path, zero_time_base=False)
last = {}
step = t0
EVN = {10: 'ARMED', 11: 'DISARMED', 17: 'LAND_MAYBE', 18: 'LAND_COMPLETE', 28: 'NOT_LANDED'}
while True:
    m = log.recv_match(type=['EV', 'MODE', 'RFND', 'CTUN', 'XKF1', 'MSG', 'ATT'])
    if m is None:
        break
    try:
        t = m.TimeUS * 1e-6
    except AttributeError:
        continue
    if t < t0:
        continue
    if t > t1:
        break
    mt = m.get_type()
    if mt == 'EV' and m.Id in EVN:
        print("%8.2f  EV %s" % (t, EVN[m.Id]))
    elif mt == 'MODE':
        print("%8.2f  MODE %d" % (t, m.Mode))
    elif mt == 'MSG':
        print("%8.2f  MSG %s" % (t, m.Message))
    elif mt == 'RFND' and getattr(m, 'Instance', 0) == 0:
        last['rf'] = (m.Dist, m.Stat)
    elif mt == 'CTUN':
        last['thO'] = m.ThO
        last['crt'] = getattr(m, 'CRt', float('nan'))
    elif mt == 'XKF1' and m.C == 0:
        last['vd'] = m.VD
    elif mt == 'ATT':
        last['att'] = (m.Roll, m.Pitch)
    if t >= step and 'rf' in last:
        print("%8.2f     rf %.2f/%d thO %.2f crt %.2f ekfVD %.2f roll/pitch %.0f/%.0f" % (
            t, last['rf'][0], last['rf'][1], last.get('thO', float('nan')), last.get('crt', float('nan')),
            last.get('vd', float('nan')), *last.get('att', (float('nan'), float('nan')))))
        step += 0.5
