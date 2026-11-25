#!/usr/bin/env python3
"""Where would an AGL KF floor hold keyed on EKF3 onGround act in the air?

Since #35105 a Copter is onGround while armed whenever land_complete is set.
For every Copter log, rebuild land_complete from the EV events (LAND_COMPLETE
18, NOT_LANDED 28, with disarm forcing landed), and for each armed period with
land_complete set, measure what the downward range finder read: a good reading
well above its ground clearance means the vehicle was off the floor while the
EKF would have been told it was on the ground.

  landed_scan.py OUT.tsv LOG [LOG...]     (one line per armed-landed period)
"""
import sys
import os
from multiprocessing import Pool
from pymavlink import DFReader

COPTER_MODES = {0: 'STABILIZE', 1: 'ACRO', 2: 'ALT_HOLD', 3: 'AUTO', 4: 'GUIDED', 5: 'LOITER',
                6: 'RTL', 7: 'CIRCLE', 9: 'LAND', 16: 'POSHOLD', 17: 'BRAKE', 18: 'THROW'}


def scan(path):
    try:
        log = DFReader.DFReader_binary(path, zero_time_base=False)
    except Exception as ex:
        return [("ERR", path, str(ex))]
    params = {}
    is_copter = None
    armed = False
    landed = True
    mode = '?'
    rfrn_landed_seen = None   # None: no Flags2 field; False/True: field present, ever set
    periods = []
    cur = None                # dict for the current armed-landed period
    t = 0.0
    while True:
        try:
            m = log.recv_match(type=['PARM', 'EV', 'RFND', 'MODE', 'MSG', 'RFRN', 'ARM'])
        except Exception:
            break
        if m is None:
            break
        mt = m.get_type()
        if mt not in ('PARM', 'MSG'):
            try:
                t = m.TimeUS * 1e-6
            except AttributeError:
                pass
        if mt == 'PARM':
            params[m.Name] = m.Value
            continue
        if mt == 'MSG':
            if is_copter is None and ('ArduCopter' in m.Message or 'Copter' in m.Message.split(' ')[0]):
                is_copter = True
            elif is_copter is None and m.Message.startswith(('ArduPlane', 'ArduRover', 'ArduSub', 'Blimp')):
                is_copter = False
            continue
        if mt == 'RFRN':
            if hasattr(m, 'Flags2'):
                if rfrn_landed_seen is None:
                    rfrn_landed_seen = False
                if int(m.Flags2) & 1:
                    rfrn_landed_seen = True
            continue
        if mt == 'MODE':
            mode = COPTER_MODES.get(int(m.Mode), str(int(m.Mode)))
            if cur is not None:
                cur['modes'].add(mode)
            continue
        new_armed, new_landed = armed, landed
        if mt == 'EV':
            if m.Id == 10:
                new_armed = True
            elif m.Id == 11:
                new_armed, new_landed = False, True
            elif m.Id == 18:
                new_landed = True
            elif m.Id == 28:
                new_landed = False
        elif mt == 'ARM':
            new_armed = bool(m.ArmState)
            if not new_armed:
                new_landed = True
        elif mt == 'RFND':
            if cur is not None and getattr(m, 'Instance', 0) == 0:
                cur['n'] += 1
                if int(m.Stat) == 4:   # Good
                    cur['good'] += 1
                    d = float(m.Dist)
                    cur['maxd'] = max(cur['maxd'], d)
                    if d > cur['gnd'] + 0.5:
                        cur['high'] += 1
                        cur['high_t'] = cur['high_t'] or t
                elif int(m.Stat) == 3:  # OutOfRangeHigh
                    cur['oorh'] += 1
            continue
        if (new_armed and new_landed) and cur is None:
            cur = dict(start=t, modes={mode}, n=0, good=0, high=0, high_t=None, oorh=0, maxd=0.0,
                       gnd=(float(params['RNGFND1_GNDCLR']) if 'RNGFND1_GNDCLR' in params
                            else float(params.get('RNGFND1_GNDCLEAR', 10)) * 0.01))
        elif cur is not None and not (new_armed and new_landed):
            cur['end'] = t
            periods.append(cur)
            cur = None
        armed, landed = new_armed, new_landed
    if cur is not None:
        cur['end'] = t
        periods.append(cur)
    if is_copter is False:
        return [("NOTCOPTER", path)]
    opts = int(params.get('EK3_OPTIONS', 0))
    out = []
    for p in periods:
        out.append(("PERIOD", path, "%.1f" % p['start'], "%.1f" % (p['end'] - p['start']), ",".join(sorted(p['modes'])),
                    p['n'], p['good'], p['high'], p['oorh'], "%.2f" % p['maxd'], "%.2f" % p['gnd'],
                    int(params.get('FLOW_TYPE', 0)), opts, (opts >> 3) & 1, int(params.get('RNGFND1_TYPE', 0)),
                    rfrn_landed_seen))
    if not periods:
        out.append(("NOPERIOD", path, rfrn_landed_seen))
    return out


def main():
    outpath = sys.argv[1]
    logs = sys.argv[2:]
    if len(logs) == 1 and logs[0].startswith('@'):
        logs = [ln.rstrip('\n') for ln in open(logs[0][1:]) if ln.strip()]
    with Pool(min(16, os.cpu_count() or 4)) as pool, open(outpath, 'w') as f:
        f.write("kind\tlog\tstart_s\tdur_s\tmodes\trfnd_n\trfnd_good\tgood_above_gnd+0.5\toor_high\tmax_good_m"
                "\tgndclr\tFLOW_TYPE\tEK3_OPTIONS\taglkf\tRNGFND1_TYPE\trfrn_landed\n")
        for rows in pool.imap_unordered(scan, logs):
            for r in rows:
                f.write("\t".join(str(x) for x in r) + "\n")
            f.flush()


if __name__ == '__main__':
    main()
