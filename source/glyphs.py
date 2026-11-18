"""Parse Gloam glyph source files: blocks of '@ <name> <desc> [adv_adj] [lsb]' + bitmap rows."""
import os, re

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'glyphs')

NAMED = {'space': ' ', 'at': '@', 'hash': '#', 'dot': '.'}


def parse(path):
    glyphs = {}
    cur = None
    for raw in open(path, encoding='utf-8'):
        line = raw.rstrip('\n')
        if line.startswith('@ '):
            parts = line[2:].split()
            key = parts[0]
            if key.startswith('U+'):
                ch = chr(int(key[2:], 16))
            elif key in NAMED:
                ch = NAMED[key]
            else:
                ch = key
            desc = int(parts[1]) if len(parts) > 1 else 0
            adj = int(parts[2]) if len(parts) > 2 else 0
            cur = {'rows': [], 'desc': desc, 'adj': adj}
            glyphs[ch] = cur
        elif line.strip() == '' or line.startswith('//'):
            continue
        elif cur is not None:
            cur['rows'].append(line.replace(' ', ''))
    for ch, g in glyphs.items():
        w = max((len(r) for r in g['rows']), default=0)
        g['w'] = w
        g['rows'] = [r.ljust(w, '.') for r in g['rows']]
        g['h'] = len(g['rows'])
    return glyphs


def load_all():
    out = {}
    for fn in sorted(os.listdir(HERE)):
        if fn.endswith('.txt'):
            out.update(parse(os.path.join(HERE, fn)))
    return out


def pixels(g):
    """Yield (x, y) with y = pixel row above baseline (0 = row sitting on baseline)."""
    h, d = g['h'], g['desc']
    for r, row in enumerate(g['rows']):
        y = (h - 1 - r) - d
        for x, c in enumerate(row):
            if c == '#':
                yield x, y


def advance(g):
    if g['w'] == 0:
        return 4 + g['adj']
    return g['w'] + 1 + g['adj']
