"""Gloam Pico: a 4 x 8 px monospace terminal face (3 x 5 capitals, real lowercase).

Built for terminals such as Ghostty: one advance for every glyph, cell metrics that are
exact pixel multiples (UPM 800, 1 px = 100 units), isFixedPitch and PANOSE monospace set
so fontconfig reports spacing=mono.

    python3 source/pico.py          # writes fonts/GloamPico-Regular.{ttf,otf,woff2}
"""
import os, sys
import unicodedata as ud

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from glyphs import load_all, pixels                       # noqa: E402
from build import gname, outline, tt_glyph, NAMES, OUT    # noqa: E402
from fontTools.fontBuilder import FontBuilder              # noqa: E402
from fontTools.pens.t2CharStringPen import T2CharStringPen  # noqa: E402
from fontTools.ttLib import TTFont, newTable               # noqa: E402
from fontTools.ttLib.tables.O_S_2f_2 import Panose        # noqa: E402

PX, UPM = 100, 800
CELL_W, ASC, DESC = 4, 6, 2          # 4 px advance; 6 px above baseline, 2 below = 8 px cell
FAMILY, PS = 'Gloam Pico', 'GloamPico-Regular'

# one-row accents on the top row (y = 5)
ACC = {'grave': '#..', 'acute': '..#', 'circ': '.#.', 'dier': '#.#', 'tilde': '##.', 'ring': '.#.'}
COMPOSE = {
    'grave': 'ÀÈÌÒÙàèìòù', 'acute': 'ÁÉÍÓÚÝáéíóúý', 'circ': 'ÂÊÎÔÛâêîôû',
    'dier': 'ÄËÏÖÜäëïöüÿŸ', 'tilde': 'ÃÑÕãñõ', 'ring': 'Åå',
}


def glyph_set():
    src = load_all(('glyphs-pico',))
    G = {ch: set(pixels(g)) for ch, g in src.items()}
    # composed Latin-1 letters
    for acc, chars in COMPOSE.items():
        row = {(x, 5) for x, c in enumerate(ACC[acc]) if c == '#'}
        for c in chars:
            base = ud.normalize('NFD', c)[0]
            if base == 'i':
                base = 'ı'
            px = set(G[base])
            if acc == 'ring' and base == 'a':
                px |= {(0, 4), (2, 4)}          # å: a real ring, the a's top stays clear below it
                row = {(1, 5)}
            G[c] = px | row
    G['Ç'] = G['C'] | {(1, -1)}
    G['ç'] = G['c'] | {(1, -1)}
    G['—'] = {(x, 2) for x in range(4)}          # em dash runs cell to cell
    G[' '] = set()

    # box drawing, blocks, shades and Powerline separators on the 4 x 8 cell
    Y0, Y1, MX, MY = -DESC, ASC - 1, 1, 2
    full = {(x, y) for x in range(CELL_W) for y in range(Y0, Y1 + 1)}

    def light(arms):
        s = set()
        if 'L' in arms: s |= {(x, MY) for x in range(0, MX + 1)}
        if 'R' in arms: s |= {(x, MY) for x in range(MX, CELL_W)}
        if 'U' in arms: s |= {(MX, y) for y in range(MY, Y1 + 1)}
        if 'D' in arms: s |= {(MX, y) for y in range(Y0, MY + 1)}
        return s
    for cp, arms in {0x2500: 'LR', 0x2502: 'UD', 0x250C: 'RD', 0x2510: 'LD', 0x2514: 'RU', 0x2518: 'LU',
                     0x251C: 'UDR', 0x2524: 'UDL', 0x252C: 'LRD', 0x2534: 'LRU', 0x253C: 'LRUD'}.items():
        G[chr(cp)] = light(arms)
    for cp, arms in {0x256D: 'RD', 0x256E: 'LD', 0x256F: 'LU', 0x2570: 'RU'}.items():
        G[chr(cp)] = light(arms) - {(MX, MY)}
    G['█'] = full
    G['▀'] = {(x, y) for x, y in full if y > 1}
    G['▄'] = {(x, y) for x, y in full if y <= 1}
    G['▌'] = {(x, y) for x, y in full if x < 2}
    G['▐'] = {(x, y) for x, y in full if x >= 2}
    G['░'] = {(x, y) for x, y in full if (x + 2 * (y % 2)) % 4 == 0}
    G['▒'] = {(x, y) for x, y in full if (x + y) % 2 == 0}
    G['▓'] = full - G['░']
    widths = [1, 2, 3, 4, 4, 3, 2, 1]                  # rows top → bottom
    tri = {(x, Y1 - r) for r, w in enumerate(widths) for x in range(w)}
    G[''] = tri
    G[''] = {(CELL_W - 1 - x, y) for x, y in tri}
    G[''] = {(w - 1, Y1 - r) for r, w in enumerate(widths)}
    G[''] = {(CELL_W - w, Y1 - r) for r, w in enumerate(widths)}
    return G


def _panose(**kw):
    p = Panose()
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def notdef():
    return {(x, y) for x in range(3) for y in range(5) if x in (0, 2) or y in (0, 4)}


def build(cff=False):
    G = glyph_set()
    chars = sorted(G, key=ord)
    names = ['.notdef'] + [gname(c) for c in chars]
    recs = {'.notdef': outline(notdef())}
    recs.update({gname(c): outline(G[c]) for c in chars})
    adv = CELL_W * PX
    fb = FontBuilder(UPM, isTTF=not cff)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({ord(c): gname(c) for c in chars})
    if cff:
        cs = {}
        for n in names:
            pen = T2CharStringPen(adv, None)
            recs[n].replay(pen)
            cs[n] = pen.getCharString()
        fb.setupCFF(PS, {'FullName': FAMILY, 'isFixedPitch': 1, 'Notice': 'Copyright 2026 Tuomas Taini.'}, cs, {})
    else:
        fb.setupGlyf({n: tt_glyph(recs[n]) for n in names})
    lsb = {}
    for n in names:
        xs = [pt[0] for op, args in recs[n].value for pt in args]
        lsb[n] = min(xs) if xs else 0
    fb.setupHorizontalMetrics({n: (adv, lsb[n]) for n in names})
    fb.setupHorizontalHeader(ascent=ASC * PX, descent=-DESC * PX, lineGap=0)
    fb.setupNameTable(NAMES(FAMILY, 'Regular', PS))
    fb.setupOS2(version=4, sTypoAscender=ASC * PX, sTypoDescender=-DESC * PX, sTypoLineGap=0,
                usWinAscent=ASC * PX, usWinDescent=DESC * PX, sxHeight=4 * PX, sCapHeight=5 * PX,
                xAvgCharWidth=adv, achVendID='TTAI', fsType=0, usWeightClass=400,
                fsSelection=0x40 | 0x80,  # REGULAR | USE_TYPO_METRICS
                yStrikeoutPosition=2 * PX, yStrikeoutSize=PX,
                panose=_panose(bFamilyType=2, bSerifStyle=0, bWeight=5, bProportion=9,  # 9 = monospaced
                            bContrast=0, bStrokeVariation=0, bArmStyle=0, bLetterForm=0,
                            bMidline=0, bXHeight=0))
    fb.setupPost(isFixedPitch=1, underlinePosition=-150, underlineThickness=PX)
    font = fb.font
    if not cff:
        gasp = newTable('gasp')
        gasp.gaspRange = {0xFFFF: 0x000A}
        font['gasp'] = gasp
    return font, G


def main():
    ttf, G = build()
    ttf.save(f'{OUT}/{PS}.ttf')
    build(cff=True)[0].save(f'{OUT}/{PS}.otf')
    w = TTFont(f'{OUT}/{PS}.ttf')
    w.flavor = 'woff2'
    w.save(f'{OUT}/{PS}.woff2')
    print(FAMILY, len(G), 'chars ->', f'{PS}.ttf .otf .woff2')


if __name__ == '__main__':
    main()
