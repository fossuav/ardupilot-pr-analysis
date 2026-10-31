"""Diff the parameters of DataFlash logs: first value and any in-log changes.
usage: python3 ft_pdiff.py A.BIN B.BIN [C.BIN ...]
"""
import sys
from pymavlink import DFReader


def params(path):
    log = DFReader.DFReader_binary(path, zero_time_base=False)
    first, changes, t0 = {}, [], None
    while True:
        m = log.recv_match(type=['PARM', 'MSG'])
        if m is None:
            break
        if t0 is None:
            t0 = m.TimeUS
        if m.get_type() != 'PARM':
            continue
        if m.Name not in first:
            first[m.Name] = m.Value
        elif abs(m.Value - first[m.Name]) > 1e-7 and (not changes or changes[-1][1:] != (m.Name, m.Value)):
            changes.append(((m.TimeUS - t0) * 1e-6, m.Name, m.Value))
    return first, changes


logs = sys.argv[1:]
ps = [params(p) for p in logs]
names = sorted(set().union(*[p[0].keys() for p in ps]))
print('differing first values:', ' | '.join(logs))
for n in names:
    vals = [p[0].get(n) for p in ps]
    ref = vals[0]
    if any(v is None or ref is None or abs(v - ref) > 1e-6 * max(1.0, abs(ref)) for v in vals):
        print(f'  {n:18s}', '  '.join('-' if v is None else f'{v:.6g}' for v in vals))
for path, (_, ch) in zip(logs, ps):
    for t, n, v in ch:
        print(f'  in {path.rsplit("/", 1)[-1]} at {t:.1f} s: {n} -> {v:.6g}')
