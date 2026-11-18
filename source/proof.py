"""Render pixel-exact proofs of Gloam straight from the glyph sources.

    python3 source/proof.py out.png "first line" "second line" [--scale 4] [--lantern ember] [--style bone]

--lantern draws the Gloam Lantern layer stack (shadow, halo, fill, highlight)
with one of the six palettes: ember moss frost ghost blood bone.
"""
import argparse, os, sys
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compose import build  # noqa: E402

PALETTES = {
    'ember': ['#0b0604', '#2a1405', '#f2c23a', '#fff1a8'],
    'moss':  ['#060b04', '#16260c', '#9fd14f', '#e8ffb4'],
    'frost': ['#03060f', '#0f1d38', '#6fbef0', '#e4f7ff'],
    'ghost': ['#07050c', '#22183a', '#c6b6f2', '#ffffff'],
    'blood': ['#0c0202', '#2e0707', '#e2453c', '#ffc0a8'],
    'bone':  ['#0a0907', '#2b251a', '#e9dfc4', '#ffffff'],
}
ASC, DESC = 13, 3


def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def layout(G, lines, extra_adv=0, gap=2):
    """Return set of ink pixels in image coordinates, and image size."""
    line_h = ASC + DESC + gap
    ink, width = set(), 0
    for li, ln in enumerate(lines):
        x0, base = 0, li * line_h + ASC
        for c in ln:
            g = G.get(c)
            if g is None:
                x0 += 4
                continue
            for x, y in g.px:
                ink.add((x0 + x, base - 1 - y))
            x0 += g.adv + (extra_adv if g.px else 0)
        width = max(width, x0)
    return ink, width, line_h * len(lines)


def render(lines, scale=4, fg='#ebe3cf', bg='#0b0910', pad=6, lantern=None, style='gloam'):
    G = build(style)
    ink, w, h = layout(G, lines, extra_adv=1 if lantern else 0)
    W, H = w + pad * 2, h + pad * 2
    img = Image.new('RGB', (W, H), rgb(bg))
    px = img.load()
    put = lambda pts, col: [px.__setitem__((x + pad, y + pad), rgb(col)) for x, y in pts if 0 <= x + pad < W and 0 <= y + pad < H]
    if lantern:
        sh, halo, fill, hi = PALETTES[lantern]
        dil = {(x + dx, y + dy) for x, y in ink for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
        put({(x + 1, y + 1) for x, y in dil}, sh)
        put(dil, halo)
        put(ink, fill)
        put({(x, y) for x, y in ink if (x, y - 1) not in ink}, hi)
    else:
        put(ink, fg)
    return img.resize((W * scale, H * scale), Image.NEAREST)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('lines', nargs='+')
    ap.add_argument('--scale', type=int, default=4)
    ap.add_argument('--lantern', choices=sorted(PALETTES))
    ap.add_argument('--fg', default='#ebe3cf')
    ap.add_argument('--bg', default='#0b0910')
    ap.add_argument('--style', default='gloam', choices=['gloam', 'bone', 'bone-narrow', 'bone-mono'])
    a = ap.parse_args()
    render(a.lines, a.scale, a.fg, a.bg, lantern=a.lantern, style=a.style).save(a.out)
