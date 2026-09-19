#!/usr/bin/env python3
"""Read the OSD screen out of a DVR capture of the analog video downlink.

The overlay is drawn from the MAX7456-style font the firmware loads, so the
glyphs are known exactly: font0.bin holds 256 glyphs of 12x18 at 2 bits per
pixel (00 black, 10 white, 01/11 transparent - see OSD_pico.cpp).  Matching
the captured cells against the real font reads the screen back, which is how
the 10 s report lines and the pre-arm messages were recovered when no log was
pulled from the flight.

Two things the analog path does have to be modelled: the luma bandwidth
smears the 1-pixel glyph outline, so the templates are blurred to match, and
the capture's horizontal phase walks about a pixel a second, so the grid is
re-fitted on every window.

Usage:
    osd_video_ocr.py screen <video.mov> <blocks.npz> [font0.bin]
    osd_video_ocr.py line   <video.mov> <blocks.npz> <t0> <t1> <row>

"screen" prints every character row, one block per second of video.  "line"
spends more effort on one row over one range - per-field alignment, a
restricted alphabet, and a per-column vote - and is what to use on a message.
"""
import sys
from collections import Counter
import numpy as np
import cv2
from scipy.ndimage import gaussian_filter

FONT = '/home/andy/github/ardupilot-rpi/libraries/AP_OSD/fonts/font0.bin'
XP, YP, ROWS, COLS, CW, CH = 21.70, 36.0, 13, 30, 12, 18
BLACK, WHITE, TRANS = 0, 1, 2
ALPHA = set(' ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789=:.%/-+')


def load_font(path):
    raw = np.fromfile(path, dtype=np.uint8).reshape(256, 18, 3)
    out = np.full((256, 18, 12), TRANS, np.uint8)
    for b in range(3):
        for p in range(4):
            pair = (raw[:, :, b] >> (6 - 2 * p)) & 3
            out[:, :, b * 4 + p] = np.where(pair == 0, BLACK,
                                            np.where(pair == 2, WHITE, TRANS))
    return out


class Matcher:
    """Correlation over each glyph's own ink, scaled by sqrt(ink) so a glyph
    that explains more of the cell beats a small one that fits a bright spot."""

    def __init__(self, path=FONT, sx=0.8, sy=0.6, ascii_only=True, min_ink=8):
        f = load_font(path)
        W, B = (f == WHITE).astype(np.float32), (f == BLACK).astype(np.float32)
        ink = (W + B).reshape(256, -1).sum(1)
        cand = [c for c in range(256)
                if ink[c] >= min_ink and (not ascii_only or 32 <= c < 127)]
        self.cands = np.array(cand)
        img = np.where(f == WHITE, 1.0, np.where(f == BLACK, 0.0, 0.5)).astype(np.float32)
        T = np.stack([gaussian_filter(im, (sy, sx), mode='nearest') for im in img[self.cands]])
        M = np.clip(np.stack([gaussian_filter(m, (sy, sx), mode='nearest')
                              for m in (W + B)[self.cands]]), 0, 1)
        T, M = T.reshape(len(self.cands), -1), M.reshape(len(self.cands), -1)
        n = M.sum(1, keepdims=True)
        Tm = (T - (T * M).sum(1, keepdims=True) / n) * M
        self.Tn = (Tm / np.sqrt((Tm * Tm / np.maximum(M, 1e-6)).sum(1, keepdims=True))).T.copy()
        self.Mn = (M / n).T.copy()

    def score(self, cells):
        X = cells.reshape(len(cells), -1).astype(np.float32)
        mean = X @ self.Mn
        var = (X * X) @ self.Mn - mean ** 2
        return (X @ self.Tn) / np.sqrt(np.maximum(var, 1e-3))


def cells_at(gray, x0, y0):
    x1, y1 = int(round(x0 + XP * COLS)), int(round(y0 + YP * ROWS))
    roi = gray[int(y0):y1, int(x0):x1]
    if roi.shape[0] < 10 or roi.shape[1] < 10:
        return None
    small = cv2.resize(roi, (COLS * CW, ROWS * CH), interpolation=cv2.INTER_AREA)
    return (small.reshape(ROWS, CH, COLS, CW).transpose(0, 2, 1, 3)
                 .reshape(ROWS * COLS, CH, CW).astype(np.float32))


def fit_grid(m, frames, xs=range(34, 56), ys=(6, 7, 8, 9)):
    best = None
    for y0 in ys:
        for x0 in xs:
            tot = 0.0
            for g in frames:
                c = cells_at(g, x0, y0)
                if c is not None:
                    tot += float(np.sort(m.score(c).max(1))[-40:].sum())
            if best is None or tot > best[0]:
                best = (tot, x0, y0)
    return best[1], best[2]


def _vote(votes, S, cands, keep, min_score, min_margin, gate=None):
    o = np.argsort(-S, 1)
    b, s2 = o[:, 0], o[:, 1]
    sb, ss = S[np.arange(len(S)), b], S[np.arange(len(S)), s2]
    good = (sb >= min_score) & (sb - ss >= min_margin)
    if gate is not None:
        good &= gate
    for k in np.nonzero(good)[0]:
        votes[k][chr(int(cands[keep[b[k]]] if keep is not None else cands[b[k]]))] += 1


def screen(video, npz, font=FONT, win=60, min_score=5.5, min_margin=0.25,
           min_votes=0.3, min_ink=25):
    d = np.load(npz)
    ink, stats = d['ink'].astype(np.float32), d['stats']
    sys.path.insert(0, __file__.rsplit('/', 1)[0])
    from osd_video_blocks import classify
    cls = classify(stats)
    m = Matcher(font)
    cap = cv2.VideoCapture(video)
    buf, idx, i, wstart = [], [], 0, 0
    while True:
        ok, im = cap.read()
        if ok:
            if i < len(cls) and cls[i] == 0 and ink[i].sum() > 300:
                buf.append(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
                idx.append(i)
            i += 1
        if i - wstart >= win or (not ok and buf):
            if len(buf) >= 8:
                bx, by = fit_grid(m, buf[::max(1, len(buf) // 8)][:8])
                votes = [Counter() for _ in range(ROWS * COLS)]
                seen = np.zeros(ROWS * COLS, np.int32)
                for g, fi in zip(buf, idx):
                    c = cells_at(g, bx, by)
                    if c is None:
                        continue
                    gate = np.repeat(ink[fi].reshape(ROWS, 2).max(1), COLS) >= min_ink
                    seen += gate
                    _vote(votes, m.score(c), m.cands, None, min_score, min_margin, gate)
                out = []
                for r in range(ROWS):
                    s = ''
                    for c2 in range(COLS):
                        v = votes[r * COLS + c2]
                        need = max(4, min_votes * max(seen[r * COLS + c2], 1))
                        s += v.most_common(1)[0][0] if (v and v.most_common(1)[0][1] >= need) else ' '
                    out.append(s)
                if any(s.strip() for s in out):
                    print(f'=== {wstart/60:6.1f}-{i/60:6.1f}s  n={len(buf)} x0={bx} y0={by}')
                    for r, s in enumerate(out):
                        if s.strip():
                            print(f'  r{r:2d}|{s}|')
                    sys.stdout.flush()
            buf, idx, wstart = [], [], i
        if not ok:
            break
    cap.release()


def line(video, npz, t0, t1, row, font=FONT):
    d = np.load(npz)
    ink, stats = d['ink'].astype(np.float32), d['stats']
    sys.path.insert(0, __file__.rsplit('/', 1)[0])
    from osd_video_blocks import classify
    cls = classify(stats)
    m = Matcher(font)
    keep = np.array([i for i, c in enumerate(m.cands) if chr(int(c)) in ALPHA])
    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t0 * 60))
    votes = [Counter() for _ in range(COLS)]
    n = 0
    for fi in range(int(t0 * 60), int(t1 * 60)):
        ok, im = cap.read()
        if not ok:
            break
        if fi >= len(cls) or cls[fi] != 0 or ink[fi].reshape(ROWS, 2).max(1)[row] < 40:
            continue
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        best = None
        for y0 in (7, 8):
            for x0 in range(30, 52):
                c = cells_at(g, x0, y0)
                if c is None:
                    continue
                S = m.score(c)[row * COLS:(row + 1) * COLS][:, keep]
                tot = float(np.sort(S.max(1))[-18:].sum())
                if best is None or tot > best[0]:
                    best = (tot, S)
        _vote(votes, best[1], m.cands, keep, 5.0, 0.15)
        n += 1
    cap.release()
    txt = ''.join(v.most_common(1)[0][0] if (v and v.most_common(1)[0][1] >= max(3, 0.25 * n)) else ' '
                  for v in votes)
    print(f'{t0}-{t1}s row {row} ({n} fields): |{txt}|')


if __name__ == '__main__':
    if sys.argv[1] == 'screen':
        screen(*sys.argv[2:])
    else:
        line(sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5]), int(sys.argv[6]))
