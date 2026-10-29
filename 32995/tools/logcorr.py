"""Fit the battery current reading against MCU temperature in a dataflash log.
logcorr.py log.bin amp_per_volt [last_s]
Averages BAT.Curr over each MCU sample's interval, then fits Curr against
MCU.MTemp by least squares, over the whole log or its last last_s seconds.
Reports the slope in A/degC and, using amp_per_volt, in mV/degC at the pin."""
import sys
from pymavlink import mavutil

path, apv = sys.argv[1], float(sys.argv[2])
last_s = float(sys.argv[3]) if len(sys.argv) > 3 else None
log = mavutil.mavlink_connection(path)
bat, mcu = [], []
while True:
    msg = log.recv_match(type=['BAT', 'MCU'])
    if msg is None:
        break
    if msg.get_type() == 'BAT' and getattr(msg, 'Inst', 0) == 0:
        bat.append((msg.TimeUS * 1e-6, msg.Curr, msg.Volt))
    elif msg.get_type() == 'MCU':
        mcu.append((msg.TimeUS * 1e-6, msg.MTemp))
if not bat or not mcu:
    sys.exit('no BAT or MCU records (BAT %d, MCU %d)' % (len(bat), len(mcu)))
t_end = bat[-1][0]
if last_s is not None:
    bat = [b for b in bat if b[0] >= t_end - last_s]
    mcu = [x for x in mcu if x[0] >= t_end - last_s]
pairs = []
j = 0
for i in range(1, len(mcu)):
    t0, t1 = mcu[i - 1][0], mcu[i][0]
    vals = [b[1] for b in bat if t0 <= b[0] < t1]
    if vals:
        pairs.append(((mcu[i - 1][1] + mcu[i][1]) / 2, sum(vals) / len(vals), (t0 + t1) / 2))
n = len(pairs)
xs = [p[0] for p in pairs]
ys = [p[1] for p in pairs]
mx, my = sum(xs) / n, sum(ys) / n
sxx = sum((x - mx) ** 2 for x in xs)
sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
syy = sum((y - my) ** 2 for y in ys)
slope = sxy / sxx if sxx > 0 else float('nan')
r2 = (sxy * sxy) / (sxx * syy) if sxx > 0 and syy > 0 else float('nan')
print('samples %d over %.0f s; MTemp %.2f..%.2f degC; Curr %.3f..%.3f A' % (
    n, pairs[-1][2] - pairs[0][2], min(xs), max(xs), min(ys), max(ys)))
print('slope %.4f A/degC = %.2f mV/degC at the pin; R2 %.3f' % (slope, slope / apv * 1000, r2))
for k in range(0, n, max(1, n // 12)):
    print('  t=%6.0f  MTemp %.2f  Curr %.3f A (%.1f mV)' % (pairs[k][2] - pairs[0][2], pairs[k][0], pairs[k][1],
                                                         pairs[k][1] / apv * 1000))
