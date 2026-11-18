"""Build Gloam (Regular, TTF/OTF/WOFF2) and Gloam Lantern (COLR/CPAL color font)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pathops
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.agl import UV2AGL
from fontTools.ttLib import TTFont
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from compose import build, KERN

PX = 100
UPM = 1600
VERSION = '1.100'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'fonts')
os.makedirs(OUT, exist_ok=True)

G = None


def use(style):
    global G
    G = build(style)


def gname(ch):
    cp = ord(ch)
    if ch == ' ':
        return 'space'
    if cp >= 0xE000 and cp <= 0xF8FF:
        return 'uni%04X' % cp
    n = UV2AGL.get(cp)
    if n and n.isascii():
        return n
    return 'uni%04X' % cp


def pixel_path(px, dx=0, dy=0):
    """Union of pixel squares -> pathops Path (outer contours counter-clockwise)."""
    p = pathops.Path()
    # merge horizontal runs first to keep the op cheap
    rows = {}
    for x, y in px:
        rows.setdefault(y, []).append(x)
    for y, xs in rows.items():
        xs.sort()
        start = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            x0, x1 = (start + dx) * PX, (prev + 1 + dx) * PX
            y0, y1 = (y + dy) * PX, (y + 1 + dy) * PX
            p.moveTo(x0, y0); p.lineTo(x1, y0); p.lineTo(x1, y1); p.lineTo(x0, y1); p.close()
            if x is not None:
                start = prev = x
    return pathops.simplify(p, clockwise=False)


def drop_collinear(rec):
    """Remove collinear points from a RecordingPen of straight segments."""
    out = RecordingPen()
    contour = []

    def flush():
        pts = contour[:]
        changed = True
        while changed and len(pts) > 3:
            changed = False
            for i in range(len(pts)):
                a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
                if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) == 0:
                    pts.pop(i)
                    changed = True
                    break
        if pts:
            out.moveTo(pts[0])
            for q in pts[1:]:
                out.lineTo(q)
            out.closePath()

    for op, args in rec.value:
        if op == 'moveTo':
            contour = [tuple(map(int, args[0]))]
        elif op == 'lineTo':
            pt = tuple(map(int, args[0]))
            if pt != contour[-1]:
                contour.append(pt)
        elif op in ('closePath', 'endPath'):
            if len(contour) > 1 and contour[-1] == contour[0]:
                contour.pop()
            flush()
            contour = []
    return out


def outline(px, dx=0, dy=0):
    rec = RecordingPen()
    if px:
        pixel_path(px, dx, dy).draw(rec)
    return drop_collinear(rec)


def tt_glyph(rec):
    pen = TTGlyphPen(None)
    rec.replay(ReverseContourPen(pen))  # TrueType: clockwise outers
    return pen.glyph()


def notdef_px():
    s = set()
    for y in range(0, 10):
        for x in range(0, 6):
            if x in (0, 5) or y in (0, 9):
                s.add((x, y))
    return s


def order():
    chars = sorted(G.keys(), key=ord)
    return chars


def kern_fea(scale=1):
    lines = ['languagesystem DFLT dflt;', 'languagesystem latn dflt;', 'feature kern {']
    for left, right, v in KERN:
        for a in left:
            for b in right:
                if a in G and b in G:
                    lines.append('  pos %s %s %d;' % (gname(a), gname(b), v * PX))
    lines.append('} kern;')
    return '\n'.join(lines)


NAMES = lambda fam, style, ps: {
    'familyName': fam,
    'styleName': style,
    'uniqueFontIdentifier': '%s-%s;%s' % (fam.replace(' ', ''), style, VERSION),
    'fullName': '%s %s' % (fam, style) if style != 'Regular' else fam,
    'psName': ps,
    'version': 'Version ' + VERSION,
    'copyright': 'Copyright 2026 Tuomas Taini.',
    'manufacturer': 'Tuomas Taini',
    'designerURL': 'https://github.com/taituo/gloam',
    'vendorURL': 'https://github.com/taituo/gloam',
    'designer': 'Tuomas Taini',
    'description': 'A broad-nib pixel typeface: every round is stressed like a pen stroke. Pixel-perfect at 16, 32, 48 px.',
    'licenseDescription': 'Copyright 2026 Tuomas Taini. All rights reserved.',
}


def build_regular(family='Gloam', ps='Gloam-Regular', cff=False, mono=False):
    chars = order()
    names = ['.notdef'] + [gname(c) for c in chars]
    cmap = {ord(c): gname(c) for c in chars}
    adv = {'.notdef': 7 * PX}
    recs = {'.notdef': outline(notdef_px())}
    for c in chars:
        g = G[c]
        adv[gname(c)] = g.adv * PX
        recs[gname(c)] = outline(g.px)

    fb = FontBuilder(UPM, isTTF=not cff)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap(cmap)
    if cff:
        cs = {}
        for n in names:
            pen = T2CharStringPen(adv[n], None)
            recs[n].replay(pen)  # CFF: counter-clockwise outers
            cs[n] = pen.getCharString()
        fb.setupCFF(ps, {'FullName': family, 'Notice': 'Copyright 2026 Tuomas Taini.', 'isFixedPitch': int(mono)}, cs, {})
    else:
        fb.setupGlyf({n: tt_glyph(recs[n]) for n in names})
    lsb = {}
    for n in names:
        xs = [pt[0] for op, args in recs[n].value for pt in args]
        lsb[n] = min(xs) if xs else 0
    fb.setupHorizontalMetrics({n: (adv[n], lsb[n]) for n in names})
    fb.setupHorizontalHeader(ascent=1300, descent=-300, lineGap=0)
    fb.setupNameTable(NAMES(family, 'Regular', ps))
    fb.setupOS2(sTypoAscender=1300, sTypoDescender=-300, sTypoLineGap=0,
                usWinAscent=1300, usWinDescent=300, sxHeight=700, sCapHeight=1000,
                version=4, achVendID='TTAI', fsType=0, usWeightClass=400,
                fsSelection=0x40 | 0x80)
    fb.setupPost(isFixedPitch=int(mono), underlinePosition=-150, underlineThickness=100)
    font = fb.font
    if not cff:
        from fontTools.ttLib import newTable
        gasp = newTable('gasp')
        gasp.gaspRange = {0xFFFF: 0x000A}  # grid-fit + symmetric smoothing, no AA artefacts on aligned sizes
        font['gasp'] = gasp
    if not mono:
        addOpenTypeFeaturesFromString(font, kern_fea())
    return font


# ---------- Lantern (COLRv0) ----------
PALETTES = [
    # shadow, outline, fill, highlight
    ('Ember', ['#0b0604', '#2a1405', '#f2c23a', '#fff1a8']),
    ('Moss',  ['#060b04', '#16260c', '#9fd14f', '#e8ffb4']),
    ('Frost', ['#03060f', '#0f1d38', '#6fbef0', '#e4f7ff']),
    ('Ghost', ['#07050c', '#22183a', '#c6b6f2', '#ffffff']),
    ('Blood', ['#0c0202', '#2e0707', '#e2453c', '#ffc0a8']),
    ('Bone',  ['#0a0907', '#2b251a', '#e9dfc4', '#ffffff']),
]


def dilate(px):
    out = set()
    for x, y in px:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                out.add((x + dx, y + dy))
    return out


def highlight(px):
    return {(x, y) for x, y in px if (x, y + 1) not in px}


def build_lantern(family='Gloam Lantern', ps='GloamLantern-Regular', first='Ember'):
    from fontTools.colorLib.builder import buildCOLR, buildCPAL
    chars = order()
    base_names = ['.notdef'] + [gname(c) for c in chars]
    layer_glyphs = {}
    layers = {}
    adv = {'.notdef': 8 * PX}
    recs = {'.notdef': outline(notdef_px(), 1, 0)}
    BOXES = set(range(0x2500, 0x25A0))
    for c in chars:
        g = G[c]
        n = gname(c)
        if ord(c) in BOXES:
            # box drawing keeps a strict grid: no halo, no extra advance
            adv[n] = g.adv * PX
            recs[n] = outline(g.px)
            hl = highlight(g.px)
            layer_glyphs[n + '.fill'] = outline(g.px)
            layer_glyphs[n + '.hi'] = outline(hl)
            layers[n] = [(n + '.fill', 2), (n + '.hi', 3)]
            continue
        adv[n] = (g.adv + 1) * PX if g.px else g.adv * PX
        sh = dilate(g.px)
        recs[n] = outline(sh, 1, 0)
        if not g.px:
            continue
        layer_glyphs[n + '.shadow'] = outline({(x + 1, y - 1) for x, y in sh}, 1, 0)
        layer_glyphs[n + '.halo'] = outline(sh, 1, 0)
        layer_glyphs[n + '.fill'] = outline(g.px, 1, 0)
        layer_glyphs[n + '.hi'] = outline(highlight(g.px), 1, 0)
        layers[n] = [(n + '.shadow', 0), (n + '.halo', 1), (n + '.fill', 2), (n + '.hi', 3)]

    names = base_names + sorted(layer_glyphs)
    allrecs = dict(recs)
    allrecs.update(layer_glyphs)
    for k in layer_glyphs:
        adv[k] = adv[k.rsplit('.', 1)[0]]
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap({ord(c): gname(c) for c in chars})
    fb.setupGlyf({n: tt_glyph(allrecs[n]) for n in names})
    lsb = {}
    for n in names:
        xs = [pt[0] for op, args in allrecs[n].value for pt in args]
        lsb[n] = min(xs) if xs else 0
    fb.setupHorizontalMetrics({n: (adv[n], lsb[n]) for n in names})
    fb.setupHorizontalHeader(ascent=1400, descent=-400, lineGap=0)
    fb.setupNameTable(NAMES(family, 'Regular', ps))
    fb.setupOS2(sTypoAscender=1400, sTypoDescender=-400, sTypoLineGap=0,
                usWinAscent=1500, usWinDescent=500, sxHeight=700, sCapHeight=1000,
                version=4, achVendID='TTAI', fsType=0, fsSelection=0x40 | 0x80)
    fb.setupPost()
    font = fb.font

    def hex2rgba(h):
        h = h.lstrip('#')
        return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, 1.0)
    pals = sorted(PALETTES, key=lambda p: p[0] != first)  # chosen palette becomes the default (index 0)
    font['CPAL'] = buildCPAL([[hex2rgba(c) for c in pal] for _, pal in pals])
    font['COLR'] = buildCOLR(layers, version=0)
    # kerning in lantern too
    addOpenTypeFeaturesFromString(font, kern_fea())
    return font


FAMILIES = [
    # style, family, PostScript name, kind
    ('gloam',       'Gloam',              'Gloam-Regular',            'outline'),
    ('gloam',       'Gloam Lantern',      'GloamLantern-Regular',     'lantern:Ember'),
    ('bone',        'Gloam Bone',         'GloamBone-Regular',        'outline'),
    ('bone-narrow', 'Gloam Bone Narrow',  'GloamBoneNarrow-Regular',  'outline'),
    ('bone-mono',   'Gloam Bone Mono',    'GloamBoneMono-Regular',    'fixed'),
    ('bone',        'Gloam Bone Lantern', 'GloamBoneLantern-Regular', 'lantern:Bone'),
]


def main():
    for style, family, ps, kind in FAMILIES:
        use(style)
        out = []
        if kind.startswith('lantern'):
            build_lantern(family, ps, kind.split(':')[1]).save(f'{OUT}/{ps}.ttf')
            out.append(f'{ps}.ttf')
        else:
            mono = kind == 'fixed'
            build_regular(family, ps, mono=mono).save(f'{OUT}/{ps}.ttf')
            build_regular(family, ps, cff=True, mono=mono).save(f'{OUT}/{ps}.otf')
            out += [f'{ps}.ttf', f'{ps}.otf']
        w = TTFont(f'{OUT}/{ps}.ttf')
        w.flavor = 'woff2'
        w.save(f'{OUT}/{ps}.woff2')
        out.append(f'{ps}.woff2')
        print(f'{family:20s}', len(G), 'chars  ', ' '.join(out))


if __name__ == '__main__':
    main()
