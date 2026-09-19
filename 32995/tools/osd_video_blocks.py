#!/usr/bin/env python3
"""Measure OSD block losses from a DVR capture of the analog video downlink.

The RP2350 OSD writes a field as 26 blocks of 9 lines (NTSC, 13 character
rows of 12x18 glyphs, 30 columns).  A block the renderer misses goes out
transparent, so it is missing from the picture while the blocks around it are
not - and because a character row is two blocks, a miss cuts the glyphs in
half across the row.  A 60 fps capture of NTSC is one frame per field, so the
capture carries one sample of every block, every field.

Usage:
    osd_video_blocks.py extract <video.mov> <blocks.npz>
    osd_video_blocks.py report  <blocks.npz> [<motion.npy>]

Geometry was calibrated on VID3_CRSF.mov (2026-09-17, 720x480): the grid sits
at x=44.25, 21.70 px per column, y=7, 36.0 px per row.  A capture from other
hardware needs it re-fitted; osd_video_ocr.py has the search that does it.
"""
import sys
import numpy as np
import cv2

X0, XP, COLS = 44.25, 21.70, 30
Y0, BLOCK_PX, NBLOCK = 7, 18, 26
XA, XB = int(round(X0)), int(round(X0 + XP * COLS))


def extract(path, out):
    """Per field: white pixels per block, plus what the picture itself looked
    like, so fields with no usable video can be thrown out later."""
    cap = cv2.VideoCapture(path)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    ink = np.zeros((n, NBLOCK), np.int32)
    stats = np.zeros((n, 3), np.float32)
    i = 0
    while True:
        ok, im = cap.read()
        if not ok or i >= n:
            break
        w = im.min(2)[:, XA:XB] > 170            # OSD white, not sky
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        stats[i] = (g.mean(), g.std(),
                    float(np.abs(np.diff(g[::4].astype(np.int16), axis=1)).mean()))
        for b in range(NBLOCK):
            ya = Y0 + b * BLOCK_PX
            ink[i, b] = w[ya:ya + BLOCK_PX].sum()
        i += 1
    cap.release()
    np.savez_compressed(out, ink=ink[:i], stats=stats[:i])
    print(f'{path}: {i} fields -> {out}')


def classify(stats):
    """0 = usable picture, 1 = analog snow, 2 = flat/black."""
    lum, std, hf = stats[:, 0], stats[:, 1], stats[:, 2]
    cls = np.zeros(len(stats), np.int8)
    cls[hf > 20] = 1
    cls[(std < 12) & (hf < 20)] = 2
    return cls


def expected(ink, half=30):
    """What each block normally carries, from a rolling high percentile.  Text
    changes far more slowly than a field, so this separates a block that went
    missing from one that had nothing on it."""
    exp = np.zeros_like(ink)
    for i in range(len(ink)):
        exp[i] = np.percentile(ink[max(0, i - half):i + half + 1], 80, axis=0)
    return exp


def drops(ink, exp, cls, k=15, frac=0.25, back=0.5, min_expected=25.0):
    """A block that carried ink shortly before and shortly after, but not now.
    Requiring both sides keeps a value that simply left the screen out of the
    count, and caps the longest run this can measure at k fields."""
    present = ink >= back * exp
    miss = (exp >= min_expected) & (ink < frac * exp)
    before = np.zeros_like(miss)
    after = np.zeros_like(miss)
    for j in range(1, k + 1):
        before[j:] |= present[:-j]
        after[:-j] |= present[j:]
    okwin = cls == 0
    for j in (1, 2):
        okwin[j:] &= (cls == 0)[:-j]
        okwin[:-j] &= (cls == 0)[j:]
    live = (exp >= min_expected) & okwin[:, None]
    return live, miss & before & after & okwin[:, None]


def runs(mask):
    out, i = [], 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j + 1 < len(mask) and mask[j + 1]:
                j += 1
            out.append(j - i + 1)
            i = j + 1
        else:
            i += 1
    return out


def report(npz, motion=None):
    d = np.load(npz)
    ink, stats = d['ink'].astype(np.float32), d['stats']
    cls = classify(stats)
    exp = expected(ink)
    live, miss = drops(ink, exp, cls)
    solid = live & (exp > 150)            # a block carrying real text
    mo = np.load(motion)[:len(ink)] if motion else None
    print(f'{npz}: {len(ink)} fields, usable picture {(cls==0).mean()*100:.0f}%'
          f' (snow {(cls==1).mean()*100:.0f}%, black {(cls==2).mean()*100:.0f}%)')
    print(f'  text blocks {int(solid.sum())}, missing {int((miss&solid).sum())}'
          f' ({(miss&solid).sum()/max(solid.sum(),1)*100:.1f}%)')
    sel = solid.sum(1) >= 6
    nd, nl = (miss & solid).sum(1), solid.sum(1)
    print(f'  fields with >=6 text blocks: {int(sel.sum())}; drawn whole'
          f' {(sel & (nd==0)).sum()/max(sel.sum(),1)*100:.1f}%, part missing'
          f' {(sel & (nd>0) & (nd<nl)).sum()/max(sel.sum(),1)*100:.1f}%, all missing'
          f' {(sel & (nd==nl) & (nd>0)).sum()/max(sel.sum(),1)*100:.1f}%')
    half = full = 0
    for r in range(13):
        both = solid[:, 2*r] & solid[:, 2*r+1]
        half += int(((miss[:, 2*r] ^ miss[:, 2*r+1]) & both).sum())
        full += int((miss[:, 2*r] & miss[:, 2*r+1] & both).sum())
    print(f'  character rows losing one half only (a block-aligned cut): {half};'
          f' losing both halves: {full}')
    print('   t(s) usable  blocks  missing  motion')
    for s in range(0, len(ink) // 60, 10):
        sl = slice(s * 60, (s + 10) * 60)
        L = solid[sl].sum()
        if L < 200:
            continue
        m = f'{mo[sl][cls[sl]==0].mean():6.2f}' if mo is not None else '     -'
        print(f'   {s:4d} {int((cls[sl]==0).sum()):6d} {int(L):7d}'
              f' {(miss&solid)[sl].sum()/L*100:7.1f}% {m}')


if __name__ == '__main__':
    if sys.argv[1] == 'extract':
        extract(sys.argv[2], sys.argv[3])
    else:
        report(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
