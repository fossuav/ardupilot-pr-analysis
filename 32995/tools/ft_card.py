#!/usr/bin/env python3
"""Measure the RP2350 alpha2 flight card's 'What to compare' fields per log."""
import collections
import statistics
import sys

from pymavlink import DFReader

PARAMS = ['BRD_IDLE_STATS', 'LOG_BITMASK', 'OSD_TYPE', 'SCR_ENABLE', 'SCR_DEBUG_OPTS', 'SERVO5_FUNCTION',
          'LOG_FILE_BUFSIZE', 'COMPASS_MOTCT', 'EK3_SRC1_POSZ', 'NTF_LED_TYPES', 'STAT_BOOTCNT', 'SCR_HEAP_SIZE',
          'SCHED_LOOP_RATE', 'FSTRATE_ENABLE', 'LOG_DISARMED', 'INS_ACC_ID']
TYPES = ['VER', 'PARM', 'EV', 'MODE', 'MSG', 'ERR', 'RPLD', 'RTDT', 'PM', 'DSF', 'STAK', 'ESC', 'UART', 'VIBE',
         'BAT', 'MCU', 'GPS', 'XKF4', 'LEDC', 'SCR', 'CTUN', 'RCOU']
EV_ARM, EV_DISARM, EV_LAND, EV_NOT_LANDED = 10, 11, 18, 28


def pct(values, q):
    if not values:
        return float('nan')
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def summary(values, scale=1.0):
    if not values:
        return 'n=0'
    v = [x * scale for x in values]
    return (f'n={len(v)} min={min(v):.2f} p5={pct(v, .05):.2f} med={statistics.median(v):.2f} '
            f'p95={pct(v, .95):.2f} max={max(v):.2f}')


def windows(events):
    # the armed period holding the first flight: a log can arm more than once
    fly = next((t for t, i in events if i == EV_NOT_LANDED), None)
    land = next((t for t, i in events if i == EV_LAND and fly is not None and t > fly), None)
    arm = max((t for t, i in events if i == EV_ARM and fly is not None and t < fly), default=None)
    disarm = next((t for t, i in events if i == EV_DISARM and land is not None and t > land), None)
    return arm, disarm, fly, land


def main(path):
    log = DFReader.DFReader_binary(path, zero_time_base=False)
    data = collections.defaultdict(list)
    t0 = None
    params = {}
    ver = None
    while True:
        m = log.recv_match(type=TYPES)
        if m is None:
            break
        kind = m.get_type()
        if kind == 'VER':
            ver = m
            continue
        if kind == 'PARM':
            if m.Name in PARAMS:
                params.setdefault(m.Name, m.Value)
            if t0 is None:
                t0 = m.TimeUS
            continue
        if not hasattr(m, 'TimeUS'):
            continue
        if t0 is None:
            t0 = m.TimeUS
        data[kind].append(((m.TimeUS - t0) * 1e-6, m))

    print(f'\n######## {path.rsplit("/", 1)[-1]}')
    if ver is not None:
        print(f'VER GH={ver.GH:08x} FWS={ver.FWS} BU={ver.BU}')
    print('params', {k: params.get(k) for k in PARAMS})
    events = [(t, m.Id) for t, m in data['EV']]
    arm, disarm, fly, land = windows(events)
    first_arm = next(t for t, i in events if i == EV_ARM)
    print(f'armed {arm} to {disarm}; flying {fly} to {land}; flight {None if not fly or not land else land - fly:.1f} s')
    print('modes', [(round(t, 1), m.Mode) for t, m in data['MODE']])
    print('ERR', [(round(t, 1), m.Subsys, m.ECode) for t, m in data['ERR']])
    print('--- MSG')
    for t, m in data['MSG']:
        print(f'  {t:7.1f} {m.Message}')

    def between(kind, a, b):
        return [(t, m) for t, m in data[kind] if a <= t <= b]

    for name, a, b in (('FLIGHT', fly, land), ('ARMED', arm, disarm), ('DISARMED-BEFORE', 10.0, first_arm)):
        print(f'--- {name} {a:.1f}-{b:.1f}')
        rows = between('RPLD', a, b)
        for field in ('C0', 'C1', 'XHit', 'XAcc'):
            print(f'  RPLD.{field}', summary([getattr(m, field) for _, m in rows]))
        rows = between('RTDT', a, b)
        print('  RTDT.dtMax ms', summary([m.dtMax for _, m in rows], 1e3))
        print('  RTDT.dtAvg ms', summary([m.dtAvg for _, m in rows], 1e3))
        rows = between('PM', a, b)
        print('  PM.NLon sum', sum(m.NLon for _, m in rows), 'NL sum', sum(m.NL for _, m in rows),
              'InE', sorted({m.InE for _, m in rows}), 'ErrL', sorted({m.ErrL for _, m in rows}))
        print('  PM.MaxT ms', summary([m.MaxT for _, m in rows], 1e-3))
        print('  PM.Mem KB', summary([m.Mem for _, m in rows], 1 / 1024))
        print('  PM.Load %', summary([m.Load for _, m in rows], 0.1))
        rows = between('DSF', a, b)
        print('  DSF.Dp', (rows[0][1].Dp, rows[-1][1].Dp) if rows else None, 'FMn', summary([m.FMn for _, m in rows]))
        rows = between('VIBE', a, b)
        print('  VIBE X/Y/Z max', [round(max((getattr(m, f) for _, m in rows), default=0), 1)
                                  for f in ('VibeX', 'VibeY', 'VibeZ')],
              'clip', max((m.Clip for _, m in rows), default=0))
        rows = between('ESC', a, b)
        by_inst = collections.defaultdict(list)
        for _, m in rows:
            by_inst[m.Instance].append(m)
        span = max(b - a, 1e-3)
        print('  ESC', {i: (round(len(v) / span), f'errmax={max(x.Err for x in v):.2f}',
                            f'rpm={max(x.RPM for x in v):.0f}') for i, v in sorted(by_inst.items())})
        rows = between('BAT', a, b)
        if rows:
            print(f'  BAT V {rows[0][1].Volt:.2f} to {rows[-1][1].Volt:.2f}, min {min(m.Volt for _, m in rows):.2f}, '
                  f'curr max {max(m.Curr for _, m in rows):.1f}')
        rows = between('MCU', a, b)
        if rows:
            print(f'  MCU degC {min(m.MTemp for _, m in rows):.1f} to {max(m.MTemp for _, m in rows):.1f}')
        rows = between('XKF4', a, b)
        print('  XKF4 FS', sorted({m.FS for _, m in rows if m.C == 0}), 'TS', sorted({m.TS for _, m in rows if m.C == 0}))
        rows = between('CTUN', a, b)
        print('  CTUN.ThO', summary([m.ThO for _, m in rows]))
        rows = between('GPS', a, b)
        if rows:
            print('  GPS NSats', summary([m.NSats for _, m in rows]), 'status', sorted({m.Status for _, m in rows}),
                  'spd max', round(max(m.Spd for _, m in rows), 1))

    print('--- STAK lowest free in the whole log')
    low = {}
    for _, m in data['STAK']:
        key = m.Name
        if key not in low or m.Free < low[key][0]:
            low[key] = (m.Free, m.Total)
    print('  ', {k: f'{v[0]}/{v[1]}' for k, v in sorted(low.items())})
    drops = collections.defaultdict(int)
    for _, m in data['UART']:
        drops[m.I] = max(drops[m.I], m.RxDp)
    print('--- UART RxDp max', dict(drops))

    if data['LEDC']:
        print('--- LEDC', [(round(t, 1), m.On) for t, m in data['LEDC']])
        edges = [(t, m.On) for t, m in data['LEDC']]
        for label, a, b in (('FLIGHT', fly, land), ('ARMED', arm, disarm), ('DISARMED', 10.0, first_arm)):
            per = {0: collections.defaultdict(list), 1: collections.defaultdict(list)}
            pairs = []
            for i, (start, on) in enumerate(edges):
                end = edges[i + 1][0] if i + 1 < len(edges) else start + 15.0
                lo, hi = max(start + 3.0, a), min(end, b)
                if hi - lo < 5.0:
                    continue
                rows = between('RPLD', lo, hi)
                if not rows:
                    continue
                c0 = statistics.mean(m.C0 for _, m in rows)
                c1 = statistics.mean(m.C1 for _, m in rows)
                pairs.append((on, c0, c1))
                for f in ('C0', 'C1', 'XHit', 'XAcc'):
                    per[on][f].extend(getattr(m, f) for _, m in rows)
                dts = between('RTDT', lo, hi)
                per[on]['dtMax'].extend(m.dtMax * 1e3 for _, m in dts)
                pm = between('PM', lo, hi)
                per[on]['MaxT'].extend(m.MaxT * 1e-3 for _, m in pm)
                per[on]['NLon'].extend(m.NLon for _, m in pm)
            print(f'  {label}: windows on={sum(1 for p in pairs if p[0] == 1)} off={sum(1 for p in pairs if p[0] == 0)}')
            for on in (1, 0):
                print(f'    On={on}', {f: round(statistics.mean(v), 2) for f, v in per[on].items() if v})
            if per[1]['C0'] and per[0]['C0']:
                print('    on-off C0 %.2f C1 %.2f' % (statistics.mean(per[1]['C0']) - statistics.mean(per[0]['C0']),
                                                     statistics.mean(per[1]['C1']) - statistics.mean(per[0]['C1'])))
            adj = []
            for i in range(len(pairs) - 1):
                if pairs[i][0] != pairs[i + 1][0]:
                    on_p, off_p = (pairs[i], pairs[i + 1]) if pairs[i][0] == 1 else (pairs[i + 1], pairs[i])
                    adj.append((on_p[1] - off_p[1], on_p[2] - off_p[2]))
            if adj:
                print('    adjacent-window on-off C0', [round(x[0], 1) for x in adj],
                      'C1', [round(x[1], 1) for x in adj])
    if data['SCR']:
        rows = data['SCR']
        print('--- SCR', rows[0][1].get_fieldnames())
        for field in rows[0][1].get_fieldnames():
            if field in ('TimeUS', 'Name'):
                continue
            print(f'  {field}', summary([float(getattr(m, field)) for _, m in rows]))


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        main(arg)
