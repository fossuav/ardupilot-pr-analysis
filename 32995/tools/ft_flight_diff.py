#!/usr/bin/env python3
"""What differed between the card's flights: parameters, the DisplayPort link, load by mode."""
import collections
import statistics
import sys

from pymavlink import DFReader

SKIP = ('STAT_', 'INS_GYR', 'INS_ACC', 'BARO', 'COMPASS_OFS', 'COMPASS_DEC', 'EK3_', 'RC_', 'GND_', 'MOT_THST_HOVER')
EV_ARM, EV_DISARM, EV_LAND, EV_NOT_LANDED = 10, 11, 18, 28
MODES = {0: 'Stabilize', 1: 'Acro', 2: 'AltHold', 5: 'Loiter'}


def read(path):
    log = DFReader.DFReader_binary(path, zero_time_base=False)
    out = dict(params=collections.defaultdict(list), rows=collections.defaultdict(list))
    t0 = None
    while True:
        m = log.recv_match(type=['PARM', 'EV', 'MODE', 'UART', 'RPLD', 'PM', 'FILE', 'RELY', 'AUXF'])
        if m is None:
            break
        kind = m.get_type()
        if kind == 'FILE':
            out['rows'][kind].append((None, m))
            continue
        if t0 is None and hasattr(m, 'TimeUS'):
            t0 = m.TimeUS
        t = (m.TimeUS - t0) * 1e-6
        if kind == 'PARM':
            values = out['params'][m.Name]
            if not values or values[-1][1] != m.Value:
                values.append((round(t, 1), m.Value))
        else:
            out['rows'][kind].append((t, m))
    return out


def main(paths):
    logs = {p.rsplit('/', 1)[-1][-6:-4]: read(p) for p in paths}
    names = sorted({n for d in logs.values() for n in d['params']})
    print('--- parameters that differ between logs, or change within one (calibration and stats groups skipped)')
    for name in names:
        series = {k: d['params'].get(name, []) for k, d in logs.items()}
        finals = {k: (v[-1][1] if v else None) for k, v in series.items()}
        changed = any(len(v) > 1 for v in series.values())
        if len(set(finals.values())) > 1 or changed:
            if name.startswith(SKIP) and name not in ('EK3_SRC1_POSZ',):
                continue
            print(f'  {name}:', {k: [round(x[1], 4) for x in v] for k, v in series.items()})
    for name in ('COMPASS_MOTCT', 'INS_HNTCH_OPTS', 'EK3_SRC1_POSZ', 'SERVO5_FUNCTION'):
        print(f'  {name} (time, value):', {k: d['params'].get(name) for k, d in logs.items()})

    print('--- SERIAL1 (DisplayPort): Tx and Rx B/s median, and first second with Rx above 100 B/s')
    for k, d in logs.items():
        rows = [(t, m) for t, m in d['rows']['UART'] if m.I == 1]
        first = next((round(t, 1) for t, m in rows if m.Rx > 100), None)
        share = 100 * sum(1 for _, m in rows if m.Rx > 100) / len(rows)
        print(f'  log {k}: Tx {statistics.median(m.Tx for _, m in rows):.0f} Rx {statistics.median(m.Rx for _, m in rows):.0f}, '
              f'Rx>100 in {share:.0f}% of rows, first at {first}; AUXF {[(round(t, 1), m.function, m.pos) for t, m in d["rows"]["AUXF"]]}')

    print('--- load by flight mode while flying (first 3 s after takeoff skipped)')
    for k, d in logs.items():
        ev = [(t, m.Id) for t, m in d['rows']['EV']]
        fly = next(t for t, i in ev if i == EV_NOT_LANDED)
        land = next(t for t, i in ev if i == EV_LAND and t > fly)
        modes = [(t, m.ModeNum) for t, m in d['rows']['MODE']]
        by = collections.defaultdict(list)
        for t, r in d['rows']['RPLD']:
            if fly + 3 <= t <= land:
                current = [n for mt, n in modes if mt <= t]
                by[current[-1]].append(r)
        print(f'  log {k}:', {MODES.get(n, n): (len(v), round(statistics.mean(x.C0 for x in v), 1),
                                                round(statistics.mean(x.C1 for x in v), 1)) for n, v in by.items()})
        arms = [t for t, i in ev if i == EV_ARM]
        dis = [t for t, i in ev if i == EV_DISARM]
        print(f'    armed total {sum(b - a for a, b in zip(arms, dis)):.2f} s over {len(arms)} arming(s)')
        low = [(round(t, 1), round(m.Mem / 1024, 1)) for t, m in d['rows']['PM']]
        base = statistics.median(x[1] for x in low)
        print(f'    PM.Mem median {base} KB, rows more than 1 KB below it: {[x for x in low if x[1] < base - 1]}')
        print(f'    FILE rows {len(d["rows"]["FILE"])}')


if __name__ == '__main__':
    main(sys.argv[1:])
