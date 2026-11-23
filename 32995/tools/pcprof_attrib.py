#!/usr/bin/env python3
"""Attribute the RP2350 in-flight pcprof dumps to functions, split by memory region."""
import bisect
import collections
import re
import subprocess
import sys

BASES = {'S': 0x20000000, 'C': 0x20080000}
TOKEN = re.compile(r'([FSCo])([0-9a-fA-F]+):(\d+)')
HEADER = re.compile(r'PROF c(\d) n=(\d+) drop=(\d+) idle=(\d+) top=(\d+)')


def strip_sig(name):
    depth = 0
    for i, ch in enumerate(name):
        if ch == '<':
            depth += 1
        elif ch == '>':
            depth -= 1
        elif ch == '(' and depth == 0:
            return name[:i]
    return name


def load_symbols(elf):
    out = subprocess.check_output(['arm-none-eabi-nm', '-S', '-n', '-C', '--defined-only', elf], text=True)
    by_addr = {}
    for line in out.splitlines():
        cols = line.split(None, 3)
        if len(cols) != 4 or cols[2] not in 'tTwW':
            continue
        addr, size = int(cols[0], 16) & ~1, int(cols[1], 16)
        if size == 0:
            continue
        if addr not in by_addr or size > by_addr[addr][0]:
            by_addr[addr] = (size, strip_sig(cols[3]))
    starts = sorted(by_addr)
    return starts, by_addr


def flash_base(elf):
    out = subprocess.check_output(['arm-none-eabi-nm', elf], text=True)
    for line in out.splitlines():
        cols = line.split()
        if len(cols) == 3 and cols[2] == '__vectors_base__':
            return int(cols[0], 16)
    raise SystemExit('no __vectors_base__')


def region(addr):
    if 0x10000000 <= addr < 0x20000000:
        return 'flash'
    if 0x20080000 <= addr < 0x20082000:
        return 'scratch'
    if 0x20000000 <= addr < 0x20080000:
        return 'sram'
    return 'other'


def overlaps(starts, syms, addr, width):
    out = []
    i = max(bisect.bisect_right(starts, addr) - 1, 0)
    while i < len(starts) and starts[i] < addr + width:
        s = starts[i]
        size, name = syms[s]
        lo, hi = max(s, addr), min(s + size, addr + width)
        if hi > lo:
            out.append((s, hi - lo))
        i += 1
    return out


def registry_names(paths):
    names = set()
    for path in paths:
        for line in open(path):
            line = line.split('#', 1)[0].strip()
            if '|' in line:
                names.add(strip_sig(line.split('|', 1)[1].strip()))
    return names


def analyse(path, elf, starts, syms, fbase, registry):
    text = open(path).read()
    head = HEADER.search(text)
    core, n, drop, idle, top = (int(x) for x in head.groups())
    width = 16 if core == 0 else 8
    counts = collections.Counter()
    regions = collections.Counter()
    nosym = 0
    tokens = 0
    floor = None
    for line in text.splitlines()[1:]:
        for tag, off, cnt in TOKEN.findall(line):
            tokens += 1
            cnt = int(cnt)
            floor = cnt if floor is None else min(floor, cnt)
            addr = (fbase if tag == 'F' else BASES.get(tag, 0)) + int(off, 16)
            regions[region(addr)] += cnt
            hits = overlaps(starts, syms, addr, width)
            total = sum(b for _, b in hits)
            if not total:
                nosym += cnt
                continue
            for s, b in hits:
                counts[s] += cnt * b / total
    busy = n - idle
    listed = sum(regions.values())
    print(f'\n===== core{core}: n={n} busy={busy} ({100 * busy / n:.1f}%) idle={idle} dropped={drop} '
          f'({100 * drop / busy:.1f}% of busy) tokens={tokens}/{top} list floor={floor}/line')
    print(f'listed {listed} = {100 * listed / busy:.1f}% of busy; unlisted (below floor) '
          f'{busy - listed - drop} = {100 * (busy - listed - drop) / busy:.1f}%; no symbol {nosym}')
    for r in ('scratch', 'sram', 'flash', 'other'):
        print(f'  {r:8s} {regions[r]:7d}  {100 * regions[r] / busy:5.1f}% of busy  {100 * regions[r] / listed:5.1f}% of listed')
    worst = regions['flash'] + (busy - listed)
    print(f'  flash share of busy: {100 * regions["flash"] / busy:.1f}% listed, at most {100 * worst / busy:.1f}% '
          'if every dropped or unlisted sample were flash')
    print('--- hottest functions (share of busy)')
    for s, c in counts.most_common(24):
        size, name = syms[s]
        print(f'  {100 * c / busy:5.2f}% {region(s):7s} {size:6d} B  {name[:70]}')
    print('--- hottest functions in flash, with samples per byte')
    flash = [(s, c) for s, c in counts.items() if region(s) == 'flash']
    flash.sort(key=lambda kv: kv[1], reverse=True)
    for s, c in flash[:24]:
        size, name = syms[s]
        mark = ' [IN REGISTRY]' if name in registry else ''
        print(f'  {100 * c / busy:5.2f}% {size:6d} B {c / size:6.2f}/B  {name[:64]}{mark}')
    return core, counts, busy, floor, width


def main(prof0, prof1, elf, *regs):
    starts, syms = load_symbols(elf)
    fbase = flash_base(elf)
    registry = registry_names(regs)
    print(f'ELF {elf.rsplit("/", 1)[-1]}: {len(starts)} sized code symbols, flash base {fbase:#x}, {len(registry)} registry names')
    results = [analyse(p, elf, starts, syms, fbase, registry) for p in (prof0, prof1)]

    print('\n===== placed code (scratch and SRAM) that neither core listed')
    placed = [s for s in starts if region(s) in ('scratch', 'sram')]
    total_bytes = sum(syms[s][0] for s in placed)
    combined = collections.Counter()
    for _, counts, _, _, _ in results:
        combined.update(counts)
    cold = [s for s in placed if combined[s] == 0]
    print(f'placed functions {len(placed)}, {total_bytes} B; with no listed sample {len(cold)}, '
          f'{sum(syms[s][0] for s in cold)} B')
    for s in sorted(cold, key=lambda x: syms[x][0], reverse=True)[:22]:
        size, name = syms[s]
        reg = 'reg' if name in registry else '   '
        print(f'  {size:6d} B {region(s):7s} {reg} {name[:70]}')
    print('--- placed functions with the fewest samples per byte, over 64 B, with any samples')
    ranked = sorted((combined[s] / syms[s][0], s) for s in placed if combined[s] > 0 and syms[s][0] >= 64)
    for density, s in ranked[:16]:
        size, name = syms[s]
        print(f'  {density:6.2f}/B {size:6d} B {region(s):7s} {name[:64]}')
    print('--- flash functions with the most samples per byte, over 16 B, both cores')
    fl = sorted(((combined[s] / syms[s][0], s) for s in starts if region(s) == 'flash' and combined[s] > 0
                 and syms[s][0] >= 16), reverse=True)
    for density, s in fl[:24]:
        size, name = syms[s]
        c0 = results[0][1][s] / results[0][2] * 100
        c1 = results[1][1][s] / results[1][2] * 100
        print(f'  {density:6.2f}/B {size:6d} B c0 {c0:5.2f}% c1 {c1:5.2f}%  {name[:60]}')


if __name__ == '__main__':
    main(*sys.argv[1:])
