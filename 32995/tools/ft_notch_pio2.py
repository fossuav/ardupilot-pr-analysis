#!/usr/bin/env python3
"""How many harmonic notch centres need sinf/cosf's range reduction in flight.

NotchFilter::init_with_A_and_Q() takes sinf and cosf of 2*pi*f/fs. newlib calls
__ieee754_rem_pio2f once that angle is over pi/4, so for f above fs/8. Uses the
motor frequency from ESC.RPM, the harmonics in INS_HNTCH_HMNCS and the gyro rate
from ISBH. It ignores the double and triple notch spread.
"""
import statistics
import sys

from pymavlink import DFReader

EV_NOT_LANDED, EV_LAND = 28, 18


def main(path):
    log = DFReader.DFReader_binary(path, zero_time_base=False)
    rates = set()
    rows = []
    fly = land = None
    hmncs = base = None
    while True:
        m = log.recv_match(type=['PARM', 'EV', 'ISBH', 'ESC'])
        if m is None:
            break
        kind = m.get_type()
        if kind == 'PARM':
            if m.Name == 'INS_HNTCH_HMNCS' and hmncs is None:
                hmncs = int(m.Value)
            elif m.Name == 'INS_HNTCH_FREQ' and base is None:
                base = m.Value
        elif kind == 'EV':
            if m.Id == EV_NOT_LANDED and fly is None:
                fly = m.TimeUS
            elif m.Id == EV_LAND and fly is not None and land is None:
                land = m.TimeUS
        elif kind == 'ISBH':
            if m.type == 1:
                rates.add(m.smp_rate)
        else:
            rows.append((m.TimeUS, m.RPM))
    fs = statistics.median(rates)
    limit = fs / 8
    harmonics = [i + 1 for i in range(8) if hmncs & (1 << i)]
    motor_hz = [rpm / 60 for t, rpm in rows if fly <= t <= land]
    print(f'{path.rsplit("/", 1)[-1]}: gyro {fs:.0f} Hz, pi/4 at {limit:.0f} Hz, harmonics {harmonics}, '
          f'motor median {statistics.median(motor_hz):.0f} Hz (p5 {sorted(motor_hz)[len(motor_hz) // 20]:.0f}); '
          f'at the {base:.0f} Hz base the highest centre is {base * max(harmonics):.0f} Hz')
    shares = {h: 100 * sum(1 for f in motor_hz if f * h > limit) / len(motor_hz) for h in harmonics}
    print('  share of in-flight samples above pi/4, by harmonic:', {h: round(s, 1) for h, s in shares.items()},
          f'all harmonics {statistics.mean(shares.values()):.1f}%')


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        main(arg)
