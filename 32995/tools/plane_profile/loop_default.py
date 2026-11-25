#!/usr/bin/env python3
"""Print the compiled SCHED_LOOP_RATE default from an ArduPilot ARM ELF.

Usage: loop_default.py ELF...
Reads AP_Scheduler::var_info[1] (AP_Param::GroupInfo: name ptr, offset, def_value float,
flags u16, idx u8, type u8; 16 bytes on a 32-bit target) straight from the file.
"""
import struct
import subprocess
import sys


def sections(elf):
    out = subprocess.run(["arm-none-eabi-readelf", "-S", "-W", elf], capture_output=True, text=True).stdout
    secs = []
    for line in out.splitlines():
        p = line.replace("[ ", "[").split()
        if len(p) > 6 and p[0].startswith("[") and p[2] in ("PROGBITS",):
            secs.append((int(p[3], 16), int(p[4], 16), int(p[5], 16)))
    return secs


def read(elf, secs, addr, n):
    for va, off, size in secs:
        if va <= addr < va + size:
            with open(elf, "rb") as fh:
                fh.seek(off + addr - va)
                return fh.read(n)
    raise ValueError(f"{addr:#x} not in a PROGBITS section")


for elf in sys.argv[1:]:
    nm = subprocess.run(["arm-none-eabi-nm", elf], capture_output=True, text=True).stdout
    addr = next(int(l.split()[0], 16) for l in nm.splitlines() if l.endswith(" _ZN12AP_Scheduler8var_infoE"))
    secs = sections(elf)
    name_p, _off, dv, flags, idx, typ = struct.unpack("<IifHBB", read(elf, secs, addr + 16, 16))
    name = read(elf, secs, name_p, 16).split(b"\0")[0].decode()
    print(f"{elf}: var_info[1] {name} idx {idx} default {dv:g}")
