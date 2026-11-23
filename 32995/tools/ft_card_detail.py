#!/usr/bin/env python3
"""Follow-up checks on the alpha2 card logs: flight intensity, UART drops, GPS glitch windows."""
import collections
import math
import statistics
import sys

from pymavlink import DFReader

TYPES = ['PARM', 'EV', 'UART', 'ATT', 'RATE', 'RCIN', 'GPS', 'GPA', 'XKF4', 'RSSI', 'BAT', 'CTUN', 'RCOU', 'STAK']
PORT_PARAMS = [f'SERIAL{i}_{s}' for i in range(0, 8) for s in ('PROTOCOL', 'BAUD')] + ['RSSI_TYPE']


def fmt(v):
    return f'{min(v):.1f}/{statistics.median(v):.1f}/{max(v):.1f}' if v else '-'


def main(path):
    log = DFReader.DFReader_binary(path, zero_time_base=False)
    data = collections.defaultdict(list)
    params = {}
    t0 = None
    while True:
        m = log.recv_match(type=TYPES)
        if m is None:
            break
        kind = m.get_type()
        if kind == 'PARM':
            if t0 is None:
                t0 = m.TimeUS
            if m.Name in PORT_PARAMS:
                params.setdefault(m.Name, m.Value)
            continue
        if hasattr(m, 'TimeUS') and t0 is not None:
            data[kind].append(((m.TimeUS - t0) * 1e-6, m))

    print(f'\n######## {path.rsplit("/", 1)[-1]}')
    print('ports', {k: int(v) for k, v in sorted(params.items()) if k.endswith('PROTOCOL') and v != 0})
    ev = [(t, m.Id) for t, m in data['EV']]
    fly = next(t for t, i in ev if i == 28)
    land = next(t for t, i in ev if i == 18 and t > fly)
    # the armed period holding the flight: a log can arm more than once
    arm = max(t for t, i in ev if i == 10 and t < fly)
    disarm = next(t for t, i in ev if i == 11 and t > land)

    def win(kind, a=fly, b=land):
        return [m for t, m in data[kind] if a <= t <= b]

    att = win('ATT')
    lean = [math.degrees(math.acos(max(-1, min(1, math.cos(math.radians(m.Roll)) * math.cos(math.radians(m.Pitch))))))
            for m in att]
    rate = win('RATE')
    print(f'flight {land - fly:.1f} s: lean max {max(lean):.1f} p95 {sorted(lean)[int(.95 * len(lean))]:.1f} deg; '
          f'rate max R {max(abs(m.R) for m in rate):.0f} P {max(abs(m.P) for m in rate):.0f} '
          f'Y {max(abs(m.Y) for m in rate):.0f} deg/s; ThO max {max(m.ThO for m in win("CTUN")):.3f}; '
          f'ThI max {max(m.ThI for m in win("CTUN")):.3f}; Curr max {max(m.Curr for m in win("BAT")):.1f} A; '
          f'GPS spd max {max(m.Spd for m in win("GPS")):.1f}; RCOU C1-4 max '
          f'{[max(getattr(m, c) for m in win("RCOU")) for c in ("C1", "C2", "C3", "C4")]}')

    print('--- UART per instance: rows, Rx B/s min/med/max, RxDp min/med/max, rows with drops, drop time span')
    for inst in sorted({m.I for _, m in data['UART']}):
        rows = [(t, m) for t, m in data['UART'] if m.I == inst]
        drops = [(t, m.RxDp) for t, m in rows if m.RxDp > 0]
        rx = [m.Rx for _, m in rows]
        in_flight = [d for t, d in drops if fly <= t <= land]
        armed = [d for t, d in drops if arm <= t <= disarm]
        span = f'{drops[0][0]:.1f}-{drops[-1][0]:.1f}' if drops else '-'
        print(f'  I={inst}: n={len(rows)} Rx {fmt(rx)} RxDp {fmt([m.RxDp for _, m in rows])} drop_rows={len(drops)} '
              f'in_flight={len(in_flight)} armed={len(armed)} span {span}')
        if drops:
            print('    first drop rows', [(round(t, 1), round(d, 1)) for t, d in drops[:14]])

    rssi = win('RSSI')
    print('RSSI RXLQ in flight', fmt([m.RXLQ for m in rssi]), 'RXRSSI', fmt([m.RXRSSI for m in rssi]))
    rcin = data['RCIN']
    gaps = [rcin[i + 1][0] - rcin[i][0] for i in range(len(rcin) - 1) if fly <= rcin[i][0] <= land]
    print(f'RCIN log gap max in flight {max(gaps) * 1e3:.0f} ms')

    print('--- GPS in flight')
    gps = win('GPS')
    gpa = win('GPA')
    print('  NSats', fmt([m.NSats for m in gps]), 'HDop', fmt([m.HDop for m in gps]), 'SAcc', fmt([m.SAcc for m in gpa]),
          'HAcc', fmt([m.HAcc for m in gpa]), 'VAcc', fmt([m.VAcc for m in gpa]))
    x4 = [m for m in win('XKF4') if m.C == 0]
    print('  XKF4 SV', fmt([m.SV for m in x4]), 'SP', fmt([m.SP for m in x4]), 'SH', fmt([m.SH for m in x4]),
          'SM', fmt([m.SM for m in x4]))


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        main(arg)
