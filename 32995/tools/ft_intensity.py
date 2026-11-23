#!/usr/bin/env python3
"""Reference numbers from the 2026-11-07 logs: how hard they flew, and any UART receive drops."""
import sys

from pymavlink import DFReader


def main(path):
    log = DFReader.DFReader_binary(path, zero_time_base=False)
    t0 = None
    tho = cur = spd = 0.0
    drops = []
    armed = False
    while True:
        m = log.recv_match(type=['PARM', 'EV', 'CTUN', 'BAT', 'GPS', 'UART'])
        if m is None:
            break
        kind = m.get_type()
        if t0 is None and hasattr(m, 'TimeUS'):
            t0 = m.TimeUS
        if kind == 'EV':
            armed = m.Id == 10 or (armed and m.Id != 11)
        elif kind == 'UART' and m.RxDp > 0:
            drops.append((round((m.TimeUS - t0) * 1e-6, 1), m.I, m.RxDp))
        elif armed and kind == 'CTUN':
            tho = max(tho, m.ThO)
        elif armed and kind == 'BAT':
            cur = max(cur, m.Curr)
        elif armed and kind == 'GPS':
            spd = max(spd, m.Spd)
    print(f'{path.rsplit("/", 1)[-1]}: armed ThO max {tho:.3f}, Curr max {cur:.1f} A, GPS spd max {spd:.1f} m/s; '
          f'UART drop rows {drops[:6]}')


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        main(arg)
