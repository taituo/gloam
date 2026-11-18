import os
"""Turn source bitmaps into the full Gloam glyph set: accents, box drawing, blocks."""
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from glyphs import load_all, pixels, advance

# accent marks (top row first)
ACC = {
    'grave':  ["##..", "..##"],
    'acute':  ["..##", "##.."],
    'circ':   [".##.", "#..#"],
    'caron':  ["#..#", ".##."],
    'breve':  ["#..#", ".##."],
    'dier':   [".#..#", "#..#."],
    'tilde':  [".##.#", "#.##."],
    'ring':   [".##.", "#..#", ".##."],
    'dot':    [".#", "#."],
    'dacute': ["..#.#", ".#.#.", ],
    'macron': ["####"],
}
# caron and breve differ: caron is pointed
ACC['caron'] = ["#.#", ".#."]

BELOW = {
    'cedilla': [".#.", "..#", "##."],
    'commab':  [".#", "#."],
    'ogonek':  ["#.", ".##"],
}


def bm_pixels(rows, x0, ytop):
    out = set()
    for r, row in enumerate(rows):
        for x, c in enumerate(row):
            if c == '#':
                out.add((x0 + x, ytop - r))
    return out


def width_of(rows):
    return max(len(r) for r in rows)


class Glyph:
    def __init__(self, px, adv):
        self.px = set(px)
        self.adv = adv

    @property
    def xmin(self):
        return min((x for x, _ in self.px), default=0)

    @property
    def xmax(self):
        return max((x for x, _ in self.px), default=-1)


def build():
    src = load_all()
    G = {}
    for ch, g in src.items():
        G[ch] = Glyph(pixels(g), advance(g))

    def top_y(base):
        return max(y for _, y in G[base].px)

    def add_above(new, base, acc, lc=None, gap=1, dx=0):
        b = G[base]
        rows = ACC[acc]
        w = width_of(rows)
        bw = b.xmax + 1
        tb = top_y(base)
        ytop = tb + gap + len(rows)
        W = max(bw, w)
        bx = (W - bw) // 2
        ax = (W - w) // 2 + dx
        if bw >= w:
            ax = (bw - w + 1) // 2 + dx
        px = {(x + bx, y) for x, y in b.px} | bm_pixels(rows, ax, ytop)
        G[new] = Glyph(px, b.adv + (W - bw))

    def add_below(new, base, mark, at=None):
        b = G[base]
        rows = BELOW[mark]
        w = width_of(rows)
        bw = b.xmax + 1
        if at is None:
            at = (bw - w) // 2
        ytop = -1 if mark != 'commab' else -2
        G[new] = Glyph(b.px | bm_pixels(rows, at, ytop), b.adv)

    L = {
        'grave': 'ÀÈÌÒÙàèìòù', 'acute': 'ÁÉÍÓÚÝáéíóúýĆćŃńŚśŹźĹĺŔŕ',
        'circ': 'ÂÊÎÔÛâêîôûĈĉĜĝĤĥĴĵŜŝŴŵŶŷ', 'tilde': 'ÃÑÕãñõĨĩŨũ',
        'dier': 'ÄËÏÖÜäëïöüÿŸ', 'caron': 'ČčĎĚěŇňŘřŠšŽžǦǧŤ',
        'breve': 'ĂăĞğŬŭ', 'dot': 'ĊċĖėĠġİŻż', 'dacute': 'ŐőŰű',
        'macron': 'ĀāĒēĪīŌōŪū',
    }
    import unicodedata as ud
    for acc, chars in L.items():
        for c in chars:
            base = ud.normalize('NFD', c)[0]
            if base == 'i' or base == 'j':
                base = 'ı' if base == 'i' else 'j'
            if base == 'j':
                continue
            if base not in G:
                continue
            add_above(c, base, acc)
    # rings
    add_above('å', 'a', 'ring')
    add_above('ů', 'u', 'ring')
    add_above('Ů', 'U', 'ring')
    # Å ring sits on the apex
    add_above('Å', 'A', 'ring', gap=0)
    # ď ľ ť: caron as a right-side nib mark
    for new, base in (('ď', 'd'), ('ľ', 'l'), ('ť', 't')):
        b = G[base]
        x0 = b.xmax + 2
        ytop = top_y(base)
        G[new] = Glyph(b.px | bm_pixels([".#", "#."], x0, ytop), b.adv + 2)
    G['Ľ'] = Glyph(G['L'].px | bm_pixels([".#", "#."], 4, 9), G['L'].adv)
    # below marks
    for new, base in (('Ç', 'C'), ('ç', 'c'), ('Ş', 'S'), ('ş', 's'), ('Ţ', 'T'), ('ţ', 't')):
        add_below(new, base, 'cedilla')
    for new, base in (('Ș', 'S'), ('ș', 's'), ('Ț', 'T'), ('ț', 't')):
        add_below(new, base, 'commab')
    for new, base in (('Ą', 'A'), ('ą', 'a'), ('Ę', 'E'), ('ę', 'e'), ('Į', 'I'), ('į', 'ı'), ('Ų', 'U'), ('ų', 'u')):
        b = G[base]
        add_below(new, base, 'ogonek', at=b.xmax - 1)
    # ĳ-less; Đ đ
    G['Đ'] = Glyph(G['Ð'].px, G['Ð'].adv)
    d = G['d']
    G['đ'] = Glyph(d.px | {(x, 8) for x in range(2, 8)}, d.adv + 1)
    G['ħ'] = Glyph(G['h'].px | {(x, 8) for x in range(0, 4)}, G['h'].adv)

    # ---- box drawing: 8 px advance, full 16 px cell (y -3..12) ----
    Y0, Y1, MID = -3, 12, 4

    def hline(s, y, x0, x1):
        s |= {(x, y) for x in range(x0, x1 + 1)}

    def vline(s, x, y0, y1):
        s |= {(x, y) for y in range(y0, y1 + 1)}

    def light(arms):
        s = set()
        if 'L' in arms: hline(s, MID, 0, 4)
        if 'R' in arms: hline(s, MID, 3, 7)
        for x in (3, 4):
            if 'U' in arms: vline(s, x, MID, Y1)
            if 'D' in arms: vline(s, x, Y0, MID)
        return s

    box = {
        0x2500: light('LR'), 0x2502: light('UD'), 0x250C: light('RD'), 0x2510: light('LD'),
        0x2514: light('RU'), 0x2518: light('LU'), 0x251C: light('UDR'), 0x2524: light('UDL'),
        0x252C: light('LRD'), 0x2534: light('LRU'), 0x253C: light('LRUD'),
        0x2574: light('L'), 0x2576: light('R'), 0x2575: light('U'), 0x2577: light('D'),
    }
    # rounded corners
    for cp, arms, cut, add in ((0x256D, 'RD', [(3, 4), (4, 4), (3, 3)], [(5, 4)]),
                              (0x256E, 'LD', [(3, 4), (4, 4), (4, 3)], [(2, 4)]),
                              (0x256F, 'LU', [(3, 4), (4, 4), (4, 5)], [(2, 4)]),
                              (0x2570, 'RU', [(3, 4), (4, 4), (3, 5)], [(5, 4)])):
        s = light(arms) - set(cut)
        box[cp] = s

    def dbl(spec):
        s = set()
        for kind, a, b0, b1 in spec:
            (hline if kind == 'h' else vline)(s, a, b0, b1)
        return s
    box.update({
        0x2550: dbl([('h', 3, 0, 7), ('h', 5, 0, 7)]),
        0x2551: dbl([('v', 2, Y0, Y1), ('v', 5, Y0, Y1)]),
        0x2554: dbl([('h', 5, 2, 7), ('v', 2, Y0, 5), ('h', 3, 5, 7), ('v', 5, Y0, 3)]),
        0x2557: dbl([('h', 5, 0, 5), ('v', 5, Y0, 5), ('h', 3, 0, 2), ('v', 2, Y0, 3)]),
        0x255A: dbl([('h', 3, 2, 7), ('v', 2, 3, Y1), ('h', 5, 5, 7), ('v', 5, 5, Y1)]),
        0x255D: dbl([('h', 3, 0, 5), ('v', 5, 3, Y1), ('h', 5, 0, 2), ('v', 2, 5, Y1)]),
        0x2560: dbl([('v', 2, Y0, Y1), ('v', 5, 5, Y1), ('v', 5, Y0, 3), ('h', 5, 5, 7), ('h', 3, 5, 7)]),
        0x2563: dbl([('v', 5, Y0, Y1), ('v', 2, 5, Y1), ('v', 2, Y0, 3), ('h', 5, 0, 2), ('h', 3, 0, 2)]),
        0x2566: dbl([('h', 5, 0, 7), ('h', 3, 0, 2), ('h', 3, 5, 7), ('v', 2, Y0, 3), ('v', 5, Y0, 3)]),
        0x2569: dbl([('h', 3, 0, 7), ('h', 5, 0, 2), ('h', 5, 5, 7), ('v', 2, 5, Y1), ('v', 5, 5, Y1)]),
        0x256C: dbl([('h', 5, 0, 2), ('h', 5, 5, 7), ('h', 3, 0, 2), ('h', 3, 5, 7),
                     ('v', 2, 5, Y1), ('v', 5, 5, Y1), ('v', 2, Y0, 3), ('v', 5, Y0, 3)]),
    })
    full = {(x, y) for x in range(8) for y in range(Y0, Y1 + 1)}
    box[0x2588] = full
    box[0x2580] = {(x, y) for x, y in full if y > MID}
    box[0x2584] = {(x, y) for x, y in full if y <= MID}
    box[0x258C] = {(x, y) for x, y in full if x < 4}
    box[0x2590] = {(x, y) for x, y in full if x >= 4}
    box[0x2591] = {(x, y) for x, y in full if (x + 2 * (y % 2)) % 4 == 0}
    box[0x2592] = {(x, y) for x, y in full if (x + y) % 2 == 0}
    box[0x2593] = full - box[0x2591]
    for cp, s in box.items():
        G[chr(cp)] = Glyph(s, 8)

    G[' '] = Glyph(set(), G[' '].adv)
    return G


KERN = [
    # (left chars, right chars, px)
    ('T', 'acdegmnopqrsuvwxyz.,', -1),
    ('F', 'aeo.,', -1),
    ('P', '.,', -1),
    ('L', 'TVWY’\'"', -1),
    ('rfv', '.,', -1),
    ('Y', 'aeo.,', -1),
    ('AV', 'VA', -1),
]

if __name__ == '__main__':
    G = build()
    print(len(G), 'glyphs')
