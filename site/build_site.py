"""Build docs/index.html: the Gloam specimen page, with fonts and a download kit embedded.

Run after source/build.py:  python3 site/build_site.py
"""
import base64, io, json, os, sys, zipfile
import unicodedata as ud

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'source'))
from compose import build  # noqa: E402
from build import gname    # noqa: E402

FONTS = os.path.join(ROOT, 'fonts')
PUA = {0xE000: 'key', 0xE001: 'potion', 0xE002: 'coin', 0xE003: 'shield', 0xE004: 'sword', 0xE005: 'lantern'}


def category(c):
    o = ord(c)
    if 'a' <= c <= 'z': return 'lower'
    if 'A' <= c <= 'Z': return 'upper'
    if '0' <= c <= '9': return 'fig'
    if 0x2500 <= o <= 0x259F: return 'box'
    if 0x2190 <= o <= 0x21FF or 0x25A0 <= o <= 0x27BF or 0xE000 <= o <= 0xF8FF: return 'icon'
    if c.isalpha(): return 'accent'
    return 'punct'


def glyph_data(style='gloam'):
    G = build(style)
    out = []
    for c in sorted(G, key=ord):
        g = G[c]
        if g.px:
            xs = [x for x, _ in g.px]; ys = [y for _, y in g.px]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            rows = [''.join('1' if (x, y) in g.px else '0' for x in range(x0, x1 + 1)) for y in range(y1, y0 - 1, -1)]
        else:
            x0, y1, rows = 0, 0, []
        name = PUA.get(ord(c)) or (ud.name(c, '') or gname(c)).lower()
        out.append([c, name, g.adv, x0, y1, rows, category(c)])
    return out


def kit_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for base, sub in (('fonts', ''), ('source', ''), ('source/glyphs', ''), ('source/glyphs-bone', '')):
            d = os.path.join(ROOT, base)
            for fn in sorted(os.listdir(d)):
                p = os.path.join(d, fn)
                if os.path.isfile(p) and not fn.endswith('.pyc'):
                    z.write(p, f'Gloam/{base}/{fn}')
        for fn in ('README.md', 'LICENSE'):
            p = os.path.join(ROOT, fn)
            if os.path.exists(p):
                z.write(p, f'Gloam/{fn}')
    return buf.getvalue()


def main():
    b64f = lambda fn: base64.b64encode(open(os.path.join(FONTS, fn), 'rb').read()).decode()
    t = open(os.path.join(ROOT, 'site', 'template.html'), encoding='utf-8').read()
    js = lambda st: json.dumps(glyph_data(st), ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    t = t.replace('{{GLYPHS}}', js('gloam')).replace('{{GLYPHS_BONE}}', js('bone'))
    t = t.replace('{{GLYPHS_BNAR}}', js('bone-narrow')).replace('{{GLYPHS_BMONO}}', js('bone-mono'))
    t = t.replace('{{BONE}}', b64f('GloamBone-Regular.woff2')).replace('{{BONEN}}', b64f('GloamBoneNarrow-Regular.woff2'))
    t = t.replace('{{BONEM}}', b64f('GloamBoneMono-Regular.woff2')).replace('{{BONEL}}', b64f('GloamBoneLantern-Regular.woff2'))
    t = t.replace('{{BTTF}}', b64f('GloamBone-Regular.ttf')).replace('{{BMTTF}}', b64f('GloamBoneMono-Regular.ttf'))
    t = t.replace('{{REG}}', b64f('Gloam-Regular.woff2')).replace('{{LAN}}', b64f('GloamLantern-Regular.woff2'))
    t = t.replace('{{ZIP}}', base64.b64encode(kit_zip()).decode())
    t = t.replace('{{TTF}}', b64f('Gloam-Regular.ttf')).replace('{{LTTF}}', b64f('GloamLantern-Regular.ttf'))
    os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
    out = os.path.join(ROOT, 'docs', 'index.html')
    open(out, 'w', encoding='utf-8').write(t)
    print(out, len(t) // 1024, 'KB')


if __name__ == '__main__':
    main()
