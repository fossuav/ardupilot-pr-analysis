#!/usr/bin/env python3
"""Count bl call targets from EKF functions in one or more ARM ELFs.

usage: outlined_calls.py OBJDUMP label=elf [label=elf ...]
Prints, per ELF, the number of bl calls from functions in the EKF classes,
and a table of call targets whose count differs between the ELFs.
"""
import collections
import re
import subprocess
import sys

EKF_FUNC = re.compile(r'NavEKF3_core::|NavEKF3::|NavEKF2_core::|NavEKF2::|EKFGSF_yaw::')
FUNC_HDR = re.compile(r'^[0-9a-f]+ <(.*)>:$')
BL = re.compile(r'\tbl\s+[0-9a-f]+ <(.*)>$')


def scan(objdump, elf):
    out = subprocess.run([objdump, '-d', '-C', '--no-show-raw-insn', elf],
                         check=True, capture_output=True, text=True).stdout
    targets = collections.Counter()
    in_ekf = False
    for line in out.splitlines():
        m = FUNC_HDR.match(line)
        if m:
            in_ekf = bool(EKF_FUNC.search(m.group(1)))
            continue
        if not in_ekf:
            continue
        m = BL.search(line)
        if m:
            t = re.sub(r'\+0x[0-9a-f]+$', '', m.group(1))
            targets[t] += 1
    return targets


def main():
    objdump = sys.argv[1]
    runs = [a.split('=', 1) for a in sys.argv[2:]]
    res = {label: scan(objdump, elf) for label, elf in runs}
    labels = [r[0] for r in runs]
    for label in labels:
        print(f'{label}: {sum(res[label].values())} bl calls from EKF functions')
    allt = set()
    for c in res.values():
        allt |= set(c)
    rows = [(t, [res[label][t] for label in labels]) for t in allt]
    rows = [r for r in rows if len(set(r[1])) > 1]
    rows.sort(key=lambda r: -max(r[1]))
    print('\t'.join(labels) + '\ttarget')
    for t, counts in rows:
        print('\t'.join(str(c) for c in counts) + '\t' + t)


if __name__ == '__main__':
    main()
