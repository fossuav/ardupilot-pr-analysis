#!/usr/bin/env python3
"""Group the core profiles by what the code is for, find who calls the 64-bit divide,
and read RPLD around disarm."""
import collections
import re
import subprocess
import sys

sys.path.insert(0, __file__.rsplit('/', 1)[0])
import pcprof_attrib as pa  # noqa: E402

from pymavlink import DFReader  # noqa: E402

GROUPS = {
    'notch apply': r'NotchFilter<.*>::apply$',
    'notch coefficient update': (r'NotchFilter<.*>::(init_with_A_and_Q|calculate_A_and_Q)|'
                                 r'HarmonicNotchFilter<.*>::(set_center_frequency|update)|'
                                 r'^(sinf|cosf|sincosf|__kernel_sinf|__kernel_cosf|__ieee754_rem_pio2f|__kernel_rem_pio2f)$'),
    'ESC RPM for the notch': r'AP_ESC_Telem::(get_rpm|get_motor_frequencies_hz)',
    'DShot': r'RCOutput_pico|dshot|RCOutput::',
    'motors and servo output': r'AP_Motors|SRV_Channel',
    '64-bit divide': r'__udivmoddi4|__aeabi_uldivmod|__aeabi_f2ulz',
    'veneers (flash stubs)': r'_veneer$',
    'kernel': r'^(ch[A-Z_]|ch_|vt_|__port|hrt_|_port|__sch|WithSemaphore|ChibiOS::Semaphore)',
    'EKF3': r'NavEKF3',
    'Attitude control': r'AC_AttitudeControl|AC_PID',
}


def groups(prof, elf, starts, syms, fbase):
    text = open(prof).read()
    core, n, _, idle, _ = (int(x) for x in pa.HEADER.search(text).groups())
    busy = n - idle
    width = 16 if core == 0 else 8
    totals = collections.Counter()
    flash = collections.Counter()
    for line in text.splitlines()[1:]:
        for tag, off, cnt in pa.TOKEN.findall(line):
            addr = (fbase if tag == 'F' else pa.BASES.get(tag, 0)) + int(off, 16)
            hits = pa.overlaps(starts, syms, addr, width)
            whole = sum(b for _, b in hits)
            for s, b in hits:
                name = syms[s][1]
                share = int(cnt) * b / whole
                for g, rx in GROUPS.items():
                    if re.search(rx, name):
                        totals[g] += share
                        if pa.region(s) == 'flash':
                            flash[g] += share
                        break
    print(f'\ncore{core} groups, % of busy samples (of which in flash):')
    for g, c in totals.most_common():
        print(f'  {100 * c / busy:6.2f}%  ({100 * flash[g] / busy:5.2f}%)  {g}')


def callers(elf):
    out = subprocess.check_output(['arm-none-eabi-objdump', '-d', '-C', elf], text=True)
    current = None
    found = collections.defaultdict(collections.Counter)
    head = re.compile(r'^([0-9a-f]{8}) <(.*)>:$')
    target = re.compile(r'\bb(?:l|\.w)?\s+[0-9a-f]+ <(__aeabi_uldivmod|__udivmoddi4|___aeabi_uldivmod_veneer|___udivmoddi4_veneer)')
    for line in out.splitlines():
        m = head.match(line)
        if m:
            current = (int(m.group(1), 16), pa.strip_sig(m.group(2)))
            continue
        t = target.search(line)
        if t and current:
            found[current][t.group(1)] += 1
    print('\nplaced (SRAM or scratch) functions that call the 64-bit divide:')
    for (addr, name), c in sorted(found.items()):
        if pa.region(addr) != 'flash':
            print(f'  {addr:#x} {pa.region(addr):7s} {name[:60]} {dict(c)}')
    print('flash callers:', sum(1 for (a, _) in found if pa.region(a) == 'flash'))


def disarm_load(path):
    log = DFReader.DFReader_binary(path, zero_time_base=False)
    arm = disarm = None
    rows = []
    while True:
        m = log.recv_match(type=['EV', 'RPLD'])
        if m is None:
            break
        if m.get_type() == 'EV':
            if m.Id == 10 and arm is None:
                arm = m.TimeUS
            elif m.Id == 11 and arm is not None and disarm is None:
                disarm = m.TimeUS
        else:
            rows.append(m)
    after = [m for m in rows if m.TimeUS > disarm + 5e6]
    late = [m for m in rows if arm + 15e6 < m.TimeUS < disarm - 2e6]
    mean = lambda v: sum(v) / len(v) if v else float('nan')
    print(f'{path.rsplit("/", 1)[-1]}: armed C0 {mean([m.C0 for m in late]):.1f} C1 {mean([m.C1 for m in late]):.1f}; '
          f'>5 s after disarm (n={len(after)}) C0 {mean([m.C0 for m in after]):.1f} C1 {mean([m.C1 for m in after]):.1f}')


def main(prof0, prof1, elf, *logs):
    starts, syms = pa.load_symbols(elf)
    fbase = pa.flash_base(elf)
    groups(prof0, elf, starts, syms, fbase)
    groups(prof1, elf, starts, syms, fbase)
    callers(elf)
    print()
    for path in logs:
        disarm_load(path)


if __name__ == '__main__':
    main(*sys.argv[1:])
