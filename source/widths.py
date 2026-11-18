"""Width transforms for the Bone variants: Narrow (drop a counter column) and Mono (8 px cells).

A column is only removed when the glyph keeps its connected parts, its counters,
and every white gap in a row stays at least `min_gap` pixels wide.
"""


def _components(px):
    seen, n = set(), 0
    for p in px:
        if p in seen:
            continue
        n += 1
        stack = [p]
        seen.add(p)
        while stack:
            x, y = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in px and q not in seen:
                        seen.add(q)
                        stack.append(q)
    return n


def _holes(px):
    if not px:
        return 0
    xs = [x for x, _ in px]
    ys = [y for _, y in px]
    x0, x1, y0, y1 = min(xs) - 1, max(xs) + 1, min(ys) - 1, max(ys) + 1
    bg = {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)} - px
    seen, n = set(), 0
    for p in bg:
        if p in seen:
            continue
        n += 1
        stack = [p]
        seen.add(p)
        while stack:
            x, y = stack.pop()
            for q in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if q in bg and q not in seen:
                    seen.add(q)
                    stack.append(q)
    return n - 1


def _min_gap(px):
    rows = {}
    for x, y in px:
        rows.setdefault(y, []).append(x)
    g = 99
    for xs in rows.values():
        xs.sort()
        for a, b in zip(xs, xs[1:]):
            if b - a > 1:
                g = min(g, b - a - 1)
    return g


def _runs(px):
    rows = {}
    for x, y in px:
        rows.setdefault(y, set()).add(x)
    return {y: sum(1 for x in xs if x - 1 not in xs) for y, xs in rows.items()}


def _drop_col(px, c):
    return {(x if x < c else x - 1, y) for x, y in px if x != c}


def squeeze(px, min_gap=2):
    """Remove the interior column that changes the drawing least; None if none is safe."""
    if not px:
        return None
    w = max(x for x, _ in px) + 1
    comp, holes, gap = _components(px), _holes(px), min(_min_gap(px), min_gap)
    runs = _runs(px)
    best = None
    for c in range(1, w - 1):
        n = _drop_col(px, c)
        if _components(n) != comp or _holes(n) != holes or _min_gap(n) < gap:
            continue
        if {y for _, y in n} != {y for _, y in px}:
            continue  # a stroke end would be cut off
        nr = _runs(n)
        if any(nr.get(y, 0) < k for y, k in runs.items() if any(x != c and y == yy for x, yy in px)):
            continue  # two strokes in a row would touch
        ink = sum(1 for x, _ in px if x == c)
        score = ink * 10 + abs(c - (w - 1) / 2)
        if best is None or score < best[0]:
            best = (score, n)
    return best and best[1]


def narrow_glyph(g, min_width=5):
    if not g.px or g.xmax + 1 < min_width:
        return
    n = squeeze(g.px)
    if n is not None:
        g.adv -= 1
        g.px = n


MONO = 8


def monospace(G, box_cps):
    """Every glyph into an 8 px cell (7 px of ink + 1 px gap), the same cell as box drawing."""
    box = {chr(c) for c in box_cps}
    for ch, g in G.items():
        if ch in box:
            continue
        px = set(g.px)
        while px and max(x for x, _ in px) + 1 > MONO - 1:
            n = squeeze(px, min_gap=1)
            if n is None:
                break
            px = n
        if px:
            xmin = min(x for x, _ in px)
            w = max(x for x, _ in px) + 1 - xmin
            off = max(0, (MONO - 1 - w) // 2) - xmin
            px = {(x + off, y) for x, y in px}
        g.px, g.adv = px, MONO
