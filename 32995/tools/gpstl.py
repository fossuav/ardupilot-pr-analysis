"""GPS timeline: gpstl.py log.bin [step_s]
Prints GPS status/sats/time/position, GPA delta stats and UBX1/UBX2 fields every step_s."""
import sys
from pymavlink import mavutil
path = sys.argv[1]
step = float(sys.argv[2]) if len(sys.argv) > 2 else 20
log = mavutil.mavlink_connection(path)
last_t = -1e9
deltas = []
types_seen = {}
ubx = {}
while True:
    m = log.recv_match(type=['GPS', 'GPA', 'UBX1', 'UBX2', 'UBX3', 'GRAW', 'GRXH'])
    if m is None:
        break
    t = m.get_type()
    types_seen[t] = types_seen.get(t, 0) + 1
    if getattr(m, 'I', 0) != 0:
        continue
    if t == 'GPA':
        deltas.append(m.Delta)
    elif t in ('UBX1', 'UBX2', 'UBX3'):
        ubx[t] = m
    elif t == 'GPS':
        ts = m.TimeUS * 1e-6
        if ts - last_t >= step:
            last_t = ts
            d = ''
            if deltas:
                d = 'Delta mean %.0f max %d' % (sum(deltas) / len(deltas), max(deltas))
                deltas = []
            print('%6.0f s St %d NS %2d GWk %d GMS %d Lat %.5f Lng %.5f Alt %.0f HDop %.2f %s' % (
                ts, m.Status, m.NSats, m.GWk, m.GMS, m.Lat, m.Lng, m.Alt, m.HDop, d))
            for k, u in sorted(ubx.items()):
                print('        %s %s' % (k, {f: getattr(u, f) for f in u.get_fieldnames() if f not in ('TimeUS', 'Instance')}))
print('types', types_seen)
