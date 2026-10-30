'''For each accel pulse in a run: when baro rejection starts (XKF4.SH > 1), when the EKF attitude bit clears, when a height timeout resets'''
import sys
from pymavlink import mavutil

for path in sys.argv[1:]:
    m = mavutil.mavlink_connection(path, robust_parsing=True)
    pulses = []
    rows = []
    while True:
        msg = m.recv_match(type=['PARM', 'XKF4'])
        if msg is None:
            break
        t = msg.TimeUS * 1e-6
        if msg.get_type() == 'PARM':
            if msg.Name == 'SIM_ACC1_BIAS_Z':
                pulses.append((t, msg.Value))
        elif msg.C == 0:
            rows.append((t, msg.SH, msg.SS))
    starts = [t for t, v in pulses if v > 1]
    ends = [t for t, v in pulses if v == 0 and t > (starts[0] if starts else 0)]
    print("== %s" % path)
    for s in starts:
        e = min([x for x in ends if x > s] or [s])
        rej = next((t for t, sh, ss in rows if t > s and sh > 1), None)
        unh = next((t for t, sh, ss in rows if t > s and not (ss & 1)), None)
        print("  pulse %.1f-%.1f: rejection from +%s, attitude bit clear at +%s (times after pulse end)" % (
            s, e, ('%.1f' % (rej - e)) if rej else '-', ('%.1f' % (unh - e)) if unh else '-'))
