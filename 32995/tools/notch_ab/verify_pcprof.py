#!/usr/bin/env python3
"""Independent attribution of the flight pcprof dumps against the saved profile ELF.

usage: verify_pcprof.py ELF DIR [DIR ...]     each DIR holds pcprof0.txt and pcprof.txt
"""
import bisect
import os
import re
import subprocess
import sys

elf = sys.argv[1]
syms = []
base = None
for line in subprocess.check_output(["arm-none-eabi-nm", "-S", "-n", "-C", elf], text=True, errors="replace").splitlines():
    p = line.split(None, 3)
    if len(p) == 4 and p[2] in "tTwW":
        syms.append((int(p[0], 16) & ~1, int(p[1], 16), p[3]))
    elif len(p) == 3 and p[2] == "__vectors_base__":
        base = int(p[0], 16)
syms.sort()
starts = [s[0] for s in syms]
BASES = {"F": base, "S": 0x20000000, "C": 0x20080000, "o": 0}
print(f"ELF app base {base:#x}, {len(syms)} code symbols")


def func(addr):
    i = bisect.bisect_right(starts, addr) - 1
    if i < 0:
        return None
    a, size, name = syms[i]
    return name if addr < a + max(size, 1) else None


NOTCH = re.compile(r"(NotchFilter<.*>::(init_with_A_and_Q|calculate|init)|HarmonicNotchFilter<.*>::(update|set_center_frequency|expand)|"
                   r"^sinf$|^cosf$|__ieee754_rem_pio2f|__kernel_sinf|__kernel_cosf|calc_lowpass)")
LIBM = re.compile(r"^(sinf|cosf|__ieee754_rem_pio2f|__kernel_sinf|__kernel_cosf)$")

for d in sys.argv[2:]:
    print(f"=== {d}")
    for core, fn in ((0, "pcprof0.txt"), (1, "pcprof.txt")):
        text = open(os.path.join(d, fn), errors="replace").read()
        h = re.search(r"PROF c(\d) n=(\d+) drop=(\d+) idle=(\d+) top=(\d+)", text)
        n, drop, idle, top = map(int, h.groups()[1:])
        toks = [(x[0], int(x[1], 16), int(x[2])) for x in re.findall(r"\b([FSCo])([0-9a-fA-F]+):(\d+)", text)]
        busy = n - idle
        listed = sum(c for _, _, c in toks)
        reg = {g: sum(c for x, _, c in toks if x == g) for g in "FSCo"}
        by = {}
        unresolved = 0
        for g, off, c in toks:
            name = func(BASES[g] + off)
            if name is None:
                unresolved += c
            else:
                key = re.sub(r"\(.*", "", name)
                by.setdefault(key, [0, g])
                by[key][0] += c
        print(f" core{core}: n={n} ({n * 197e-6:.2f} s) busy {100 * busy / n:.1f}%; of busy: flash {100 * reg['F'] / busy:.1f}%, "
              f"SRAM {100 * reg['S'] / busy:.1f}%, scratch {100 * reg['C'] / busy:.1f}%, dropped {100 * drop / busy:.1f}%, "
              f"below top {top} {100 * (busy - listed - drop) / busy:.1f}%; unresolved {100 * unresolved / listed:.1f}% of listed")
        ranked = sorted(by.items(), key=lambda kv: -kv[1][0])
        flash = [(k, v[0]) for k, v in ranked if v[1] == "F"][:4]
        print("   top flash:", [(k[:34], round(100 * c / busy, 2)) for k, c in flash])
        if core == 1:
            libm = sum(v[0] for k, v in by.items() if LIBM.search(k))
            notch = sum(v[0] for k, v in by.items() if NOTCH.search(k))
            print(f"   sinf/cosf and helpers {100 * libm / busy:.2f}% of busy; notch update group {100 * notch / busy:.2f}%")
            print("   in that group:", [(k[:44], round(100 * v[0] / busy, 2)) for k, v in ranked if NOTCH.search(k)][:10])
