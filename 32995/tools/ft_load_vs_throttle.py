#!/usr/bin/env python3
"""Per-core load against what the vehicle was doing, one RPLD row at a time.

For each 1 Hz RPLD row in the flight, average throttle, motor frequency and
current over the same second, then bin. Also reports the rate loop and the main
loop by the same bins, why each GPS glitch flag was raised, and the stacks over
the armed period that holds the flight (a log can arm more than once).
"""
import bisect
import collections
import statistics
import sys

from pymavlink import DFReader

TYPES = ['PARM', 'EV', 'ERR', 'RPLD', 'CTUN', 'ESC', 'BAT', 'RTDT', 'PM', 'GPA', 'XKF4', 'DSF', 'MODE', 'STAK',
         'VIBE', 'MAG', 'XKFS']
EV_ARM, EV_DISARM, EV_LAND, EV_NOT_LANDED = 10, 11, 18, 28
BINS = [(0.0, 0.15), (0.15, 0.20), (0.20, 0.30), (0.30, 0.45), (0.45, 1.01)]


def mean(values):
    return statistics.mean(values) if values else float('nan')


def within(rows, times, a, b):
    return rows[bisect.bisect_left(times, a):bisect.bisect_right(times, b)]


def main(path):
    log = DFReader.DFReader_binary(path, zero_time_base=False)
    data = collections.defaultdict(list)
    t0 = None
    while True:
        m = log.recv_match(type=TYPES)
        if m is None:
            break
        if t0 is None and hasattr(m, 'TimeUS'):
            t0 = m.TimeUS
        if m.get_type() != 'PARM' and hasattr(m, 'TimeUS'):
            data[m.get_type()].append(((m.TimeUS - t0) * 1e-6, m))
    times = {k: [t for t, _ in v] for k, v in data.items()}

    ev = [(t, m.Id) for t, m in data['EV']]
    fly = next(t for t, i in ev if i == EV_NOT_LANDED)
    land = next(t for t, i in ev if i == EV_LAND and t > fly)
    arm = max(t for t, i in ev if i == EV_ARM and t < fly)
    disarm = min(t for t, i in ev if i == EV_DISARM and t > land)
    print(f'\n{path.rsplit("/", 1)[-1]}: armed {arm:.1f}-{disarm:.1f}, flying {fly:.1f}-{land:.1f} ({land - fly:.1f} s)')
    print('modes', [(round(t, 1), m.Mode) for t, m in data['MODE']])

    rows = []
    for t, r in data['RPLD']:
        if not fly + 3 <= t <= land:
            continue
        ctun = within(data['CTUN'], times['CTUN'], t - 1, t)
        esc = within(data['ESC'], times['ESC'], t - 1, t)
        bat = within(data['BAT'], times['BAT'], t - 1, t)
        rtdt = within(data['RTDT'], times['RTDT'], t - 1, t)
        if not ctun or not esc:
            continue
        rows.append(dict(t=t, c0=r.C0, c1=r.C1, hit=r.XHit, acc=r.XAcc,
                         tho=mean([m.ThO for _, m in ctun]),
                         hz=mean([m.RPM / 60 for _, m in esc]),
                         cur=mean([m.Curr for _, m in bat]),
                         dt=max((m.dtMax for _, m in rtdt), default=float('nan')) * 1e3))
    print('throttle band   n   C0     C1    XHit  XAcc  motor Hz  A     worst rate gap ms')
    for lo, hi in BINS:
        b = [r for r in rows if lo <= r['tho'] < hi]
        if b:
            print(f'{lo:.2f}-{hi:.2f}  {len(b):4d}  {mean([r["c0"] for r in b]):5.1f}  {mean([r["c1"] for r in b]):5.1f}  '
                  f'{mean([r["hit"] for r in b]):5.1f} {mean([r["acc"] for r in b]):5.1f}  {mean([r["hz"] for r in b]):6.0f} '
                  f'{mean([r["cur"] for r in b]):5.1f}  {max(r["dt"] for r in b):.2f}')
    if len(rows) > 5:
        c1 = [r['c1'] for r in rows]
        print('corr C1 with throttle %.2f, motor Hz %.2f; C1 min %.1f max %.1f' % (
            statistics.correlation(c1, [r['tho'] for r in rows]),
            statistics.correlation(c1, [r['hz'] for r in rows]), min(c1), max(c1)))

    a = within(data['RTDT'], times['RTDT'], fly, land)
    pm = within(data['PM'], times['PM'], fly, land)
    dsf = within(data['DSF'], times['DSF'], arm, disarm)
    print(f'flight: worst rate gap {max(m.dtMax for _, m in a) * 1e3:.2f} ms; NLon {sum(m.NLon for _, m in pm)}; '
          f'MaxT {max(m.MaxT for _, m in pm) * 1e-3:.2f} ms; Load {min(m.Load for _, m in pm) * .1:.1f}-'
          f'{max(m.Load for _, m in pm) * .1:.1f}%; Mem {min(m.Mem for _, m in pm) / 1024:.1f}-'
          f'{max(m.Mem for _, m in pm) / 1024:.1f} KB; InE {sorted({m.InE for _, m in pm})}')
    print(f'armed: DSF.Dp {dsf[0][1].Dp} to {dsf[-1][1].Dp}, FMn lowest {min(m.FMn for _, m in dsf)}')
    after = [m for t, m in data['RPLD'] if t > disarm + 5]
    print(f'>5 s after disarm (n={len(after)}): C0 {mean([m.C0 for m in after]):.1f} C1 {mean([m.C1 for m in after]):.1f}')
    worst = sorted(((m.dtMax * 1e3, t) for t, m in a), reverse=True)[:5]
    print('worst rate gaps in flight (ms, t):', [(round(d, 2), round(t, 1)) for d, t in worst])
    armed_dt = within(data['RTDT'], times['RTDT'], arm, disarm)
    w = max(((m.dtMax * 1e3, t) for t, m in armed_dt))
    print(f'worst rate gap while armed {w[0]:.2f} ms at {w[1]:.1f} s')

    print('--- GPS glitch windows: receiver speed accuracy and test ratios')
    errs = [(t, m.ECode) for t, m in data['ERR'] if m.Subsys == 11]
    for i, (start, code) in enumerate(errs):
        if code != 2:
            continue
        end = next((t for t, c in errs[i + 1:] if c == 0), start + 5)
        lead = within(data['GPA'], times['GPA'], start - 3, start + 0.2)
        x4 = [m for _, m in within(data['XKF4'], times['XKF4'], start - 3, end) if m.C == 0]
        print(f'  {start:6.1f}-{end:6.1f}: SAcc max before flag {max((m.SAcc for _, m in lead), default=0):.2f} m/s, '
              f'SV max {max((m.SV for m in x4), default=0):.2f}, SP {max((m.SP for m in x4), default=0):.2f}, '
              f'SM {max((m.SM for m in x4), default=0):.2f}, FS {sorted({m.FS for m in x4})}')

    low = {}
    for t, m in data['STAK']:
        if arm <= t <= disarm and (m.Name not in low or m.Free < low[m.Name]):
            low[m.Name] = m.Free
    print('lowest stack free while armed:', {k: low[k] for k in ('OSD', 'rate', 'rcout', 'rcin', 'log_io', 'led',
                                                                  'ArduCopter', 'c1_main') if k in low})
    vibe = within(data['VIBE'], times['VIBE'], fly, land)
    print('VIBE max X/Y/Z', [round(max(getattr(m, f) for _, m in vibe), 1) for f in ('VibeX', 'VibeY', 'VibeZ')],
          'clip', max(m.Clip for _, m in vibe))
    fus = within(data['XKFS'], times['XKFS'], fly, land)
    print('MAG_FUSION states in flight', sorted({m.MAG_FUSION for _, m in fus if m.C == 0}))


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        main(arg)
