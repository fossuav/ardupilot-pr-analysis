#!/usr/bin/env python3
'''Mirror of OSD_pico build_font_lut/build_blank_table/block_is_blank/render_block,
checking blank detection against rendered output for every glyph and half.'''
import sys
font = open(sys.argv[1], 'rb').read()
assert len(font) == 256 * 54, len(font)
pair_map = [1, 0, 3, 0]
lut = []
for b in range(256):
    bits = 0
    for i in range(4):
        bits = (bits << 2) | pair_map[(b >> (6 - 2 * i)) & 3]
    out = 0
    for i in range(8):
        out = (out << 1) | ((bits >> i) & 1)
    lut.append(out)
BLOCK_LINES, CELL_ROWS, CELL_BYTES, COLS = 9, 18, 3, 30
parts = CELL_ROWS // BLOCK_LINES
blank = [[0] * 8 for _ in range(parts)]
for c in range(256):
    g = font[c * 54:(c + 1) * 54]
    for part in range(parts):
        if all(lut[g[i]] == 0 for i in range(part * BLOCK_LINES * CELL_BYTES, (part + 1) * BLOCK_LINES * CELL_BYTES)):
            blank[part][c >> 5] |= 1 << (c & 31)

def is_blank_glyph(c, part):
    return bool(blank[part][c >> 5] & (1 << (c & 31)))

def render_half(c, part):
    g = font[c * 54:(c + 1) * 54]
    return [lut[g[r * 3 + k]] for r in range(part * 9, part * 9 + 9) for k in range(3)]

bad = 0
for c in range(256):
    for part in range(parts):
        rendered_blank = all(v == 0 for v in render_half(c, part))
        if rendered_blank != is_blank_glyph(c, part):
            bad += 1
print("mismatches:", bad)
print("space blank top/bottom:", is_blank_glyph(0x20, 0), is_blank_glyph(0x20, 1))
print("'_' blank top/bottom:", is_blank_glyph(ord('_'), 0), is_blank_glyph(ord('_'), 1))
print("'A' blank top/bottom:", is_blank_glyph(ord('A'), 0), is_blank_glyph(ord('A'), 1))
print("glyphs fully blank:", sum(1 for c in range(256) if is_blank_glyph(c, 0) and is_blank_glyph(c, 1)))
# block index -> row/part mapping as block_is_blank computes it
for block in (0, 1, 2, 25, 31):
    first = block * BLOCK_LINES
    print("block %d -> row %d part %d" % (block, first // CELL_ROWS, (first % CELL_ROWS) // BLOCK_LINES))
