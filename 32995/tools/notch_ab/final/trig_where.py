#!/usr/bin/env python3
"""Where the notch's trig functions live and how much of core1 each takes, on the bench A runs and in flight."""
import bisect
import glob
import os
import re
import subprocess
import sys

S = os.environ["NOTCH_AB_SCRATCH"]
BENCH = os.environ["NOTCH_AB_DATA"]
FLIGHT = os.environ["NOTCH_AB_FLIGHT_LOGS"]
NAMES = ("sinf", "cosf", "__kernel_sinf", "__kernel_cosf", "__ieee754_rem_pio2f", "____ieee754_rem_pio2f_veneer",
         "__sinf_veneer", "__cosf_veneer", "__kernel_sinf_veneer", "__kernel_cosf_veneer")


def load(elf):
    syms = []
    for line in subprocess.check_output(["arm-none-eabi-nm", "-S", "-n", "-C", elf], text=True, errors="replace").splitlines():
        p = line.split(None, 3)
        if len(p) == 4 and p[2] in "tTwW":
            syms.append((int(p[0], 16) & ~1, int(p[1], 16), re.sub(r"\(.*", "", p[3])))
    syms.sort()
    return syms, [s[0] for s in syms]


def region(addr):
    return "flash" if 0x10000000 <= addr < 0x20000000 else "SRAM" if addr < 0x20080000 else "scratch"


def at(table, pc):
    syms, starts = table
    i = bisect.bisect_right(starts, pc) - 1
    if i < 0:
        return None
    a, size, name = syms[i]
    return name if pc < a + max(size, 1) else None


elf = f"{S}/notch-ab/A/arducopter.elf"
table = load(elf)
print("placement in the alpha2 build:")
for a, size, name in table[0]:
    if name in NAMES or name.endswith("NotchFilter<Vector3<float> >::init_with_A_and_Q"):
        print(f"  {name:48s} {size:5d} B  {region(a):7s} {a:#x}")

counts, total = {}, 0
for d in glob.glob(f"{BENCH}/run*A"):
    for line in open(f"{d}/pcsr1.txt", errors="replace"):
        if line.startswith("#") or not line.strip():
            continue
        v = int(line.split()[0], 16)
        if v == 0xFFFFFFFF:
            continue
        total += 1
        n = at(table, v & ~1)
        counts[n] = counts.get(n, 0) + 1
print(f"\nbench, four boots of the unchanged build, {total} core1 samples (points of core1):")
tot_flash = tot_sram = 0
place = {name: region(a) for a, _, name in table[0]}
for n in NAMES:
    if n in counts:
        p = 100 * counts[n] / total
        print(f"  {n:34s} {p:6.2f}  {place[n]}")
        if place[n] == "flash":
            tot_flash += p
        else:
            tot_sram += p
print(f"  trig in flash {tot_flash:.2f}, trig in SRAM {tot_sram:.2f}, total {tot_flash + tot_sram:.2f}")

flight = load(f"{FLIGHT}/arducopter-profile.elf")
text = open(f"{FLIGHT}/high-speed/pcprof.txt", errors="replace").read()
h = re.search(r"n=(\d+) drop=(\d+) idle=(\d+)", text)
n = int(h[1])
base = {"S": 0x20000000, "C": 0x20080000}
vec = subprocess.check_output(["arm-none-eabi-nm", f"{FLIGHT}/arducopter-profile.elf"], text=True)
base["F"] = int(re.search(r"([0-9a-f]+) \w __vectors_base__", vec).group(1), 16)
fl = {}
for g, off, c in re.findall(r"\b([FSC])([0-9a-fA-F]+):(\d+)", text):
    name = at(flight, base[g] + int(off, 16))
    fl[name] = fl.get(name, 0) + int(c)
print("\nlog 15 in flight (points of core1):")
pl = {name: region(a) for a, _, name in flight[0]}
for x in NAMES:
    if x in fl:
        print(f"  {x:34s} {100 * fl[x] / n:6.2f}  {pl[x]}")
