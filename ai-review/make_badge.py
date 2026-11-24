#!/usr/bin/env python3
"""Build the "Andy's AI Review" badge from the SFD wordmark.

Usage: make_badge.py <sfd_logo2.png> [out_dir]

The logo is sfd_logo2.png from the SmallFastDrone repository. The S, F and
winged D are taken from it by connected-component area, which leaves out the
"SMALL FAST DRONE" strapline. The badge is rendered supersampled and written
as PNGs at the sizes GitHub shows, plus an SVG with the same geometry.
"""
import os
import sys

import cv2
import numpy as np

SS = 2048                       # supersampled canvas, pixels
SIZES = [512, 256, 128, 64, 40, 32, 24, 20]
MIN_GLYPH_AREA = 10000          # S and F+D are ~21k and ~51k px; strapline letters ~1k

INDIGO, VIOLET = '#4338CA', '#7C3AED'
GOLD = '#FBBF24'
# unit-canvas geometry shared by the PNGs and the SVG
WORD = (0.82, 0.50, 0.60)                               # width, centre x, centre y
SPARKS = [(0.80, 0.215, 0.155), (0.585, 0.17, 0.065)]   # centre x, centre y, radius
SQUIRCLE_P = 5.0                                        # superellipse exponent of the badge


def hexrgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255.0


def load_wordmark(path):
    gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        sys.exit(f'cannot read {path}')
    ink = (gray < 128).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, 8)
    keep = [i for i in range(1, n) if st[i][4] > MIN_GLYPH_AREA]
    sel = np.isin(lab, keep)
    ys, xs = np.where(sel)
    # grayscale ink keeps the source's own anti-aliasing for a smooth upscale
    inkf = 1.0 - gray.astype(np.float32) / 255.0
    inkf[~cv2.dilate(sel.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)] = 0
    return inkf[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def sparkle_pts(cx, cy, r, p=2.6, n=720):
    """Four-point sparkle: a superellipse with exponent > 1 has concave sides."""
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    return np.stack([cx + r * np.sign(c) * np.abs(c) ** p, cy + r * np.sign(s) * np.abs(s) ** p], 1)


def render(word):
    yy, xx = np.mgrid[0:SS, 0:SS].astype(np.float32)
    u = (xx + 0.5) / SS
    v = (yy + 0.5) / SS
    rgb = np.zeros((SS, SS, 3), np.float32)
    alpha = np.zeros((SS, SS), np.float32)

    def over(mask, color):
        nonlocal rgb, alpha
        m = mask[..., None]
        rgb = color * m + rgb * (1 - m)
        alpha = mask + alpha * (1 - mask)

    # badge: diagonal gradient squircle
    badge = ((np.abs(u - 0.5) / 0.5) ** SQUIRCLE_P + (np.abs(v - 0.5) / 0.5) ** SQUIRCLE_P <= 1.0)
    t = np.clip((u - 0.5 + v - 0.5) * 0.5 + 0.5, 0, 1)[..., None]
    over(badge.astype(np.float32), (1 - t) * hexrgb(INDIGO) + t * hexrgb(VIOLET))

    # wordmark in white
    w, cx, cy = WORD
    ww = int(w * SS)
    wh = int(round(ww * word.shape[0] / word.shape[1]))
    wm = (cv2.resize(word, (ww, wh), interpolation=cv2.INTER_CUBIC) > 0.5).astype(np.float32)
    m = np.zeros((SS, SS), np.float32)
    x0 = int(round(cx * SS - ww / 2))
    y0 = int(round(cy * SS - wh / 2))
    m[y0:y0 + wh, x0:x0 + ww] = wm
    over(m, hexrgb('#FFFFFF'))

    for sx, sy, sr in SPARKS:
        sm = np.zeros((SS, SS), np.uint8)
        cv2.fillPoly(sm, [(sparkle_pts(sx, sy, sr) * SS).astype(np.int32)], 1)
        over(sm.astype(np.float32), hexrgb(GOLD))
    return np.dstack([rgb, alpha])


def downscale(rgba, size):
    # premultiplied, so the edges do not fringe
    pm = rgba.copy()
    pm[..., :3] *= pm[..., 3:4]
    s = cv2.resize(pm, (size, size), interpolation=cv2.INTER_AREA)
    a = s[..., 3:4]
    return np.dstack([np.where(a > 1e-6, s[..., :3] / np.maximum(a, 1e-6), 0), a])


def save_png(rgba, path):
    cv2.imwrite(path, (np.clip(rgba[..., [2, 1, 0, 3]], 0, 1) * 255 + 0.5).astype(np.uint8))


def svg(word):
    V = 512

    def path_d(pts):
        return 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in pts) + ' Z'

    t = np.linspace(0, 2 * np.pi, 360, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    e = 2.0 / SQUIRCLE_P
    badge = np.stack([0.5 + 0.5 * np.sign(c) * np.abs(c) ** e, 0.5 + 0.5 * np.sign(s) * np.abs(s) ** e], 1) * V

    w, cx, cy = WORD
    up = cv2.resize(word, (word.shape[1] * 4, word.shape[0] * 4), interpolation=cv2.INTER_CUBIC)
    contours, _ = cv2.findContours((up > 0.5).astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    scale = w * V / word.shape[1] / 4.0
    ox = cx * V - w * V / 2
    oy = cy * V - (w * V * word.shape[0] / word.shape[1]) / 2
    glyphs = ' '.join(path_d(cv2.approxPolyDP(k, 1.2, True).reshape(-1, 2) * scale + [ox, oy]) for k in contours)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {V} {V}" width="{V}" height="{V}">',
             "<title>Andy's AI Review</title>",
             f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{INDIGO}"/>'
             f'<stop offset="1" stop-color="{VIOLET}"/></linearGradient></defs>',
             f'<path fill="url(#g)" d="{path_d(badge)}"/>',
             f'<path fill="#FFFFFF" fill-rule="evenodd" d="{glyphs}"/>']
    for sx, sy, sr in SPARKS:
        parts.append(f'<path fill="{GOLD}" d="{path_d(sparkle_pts(sx, sy, sr, n=96) * V)}"/>')
    parts.append('</svg>')
    return '\n'.join(parts) + '\n'


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(__file__))
    word = load_wordmark(sys.argv[1])
    big = render(word)
    for size in SIZES:
        save_png(downscale(big, size), os.path.join(out, f'ai-review-badge-{size}.png'))
    with open(os.path.join(out, 'ai-review-badge.svg'), 'w') as f:
        f.write(svg(word))


if __name__ == '__main__':
    main()
