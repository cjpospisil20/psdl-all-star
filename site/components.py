"""Shared page fragments, lifted from the mockups so every screen stays consistent.

Icons are inline stroke SVG, copied from the mockups -- no icon font, no emoji (DESIGN-SPEC).
"""
import html as _html

import tokens

GOLD, MUTED = tokens.COLOURS["gold"], tokens.COLOURS["muted"]


def esc(text):
    """Escape for HTML but keep real double spaces visible.

    'Colin  Ratner' genuinely has two spaces in DartConnect. HTML collapses runs of whitespace,
    so the second becomes a non-breaking space. The .name class also sets white-space: pre-wrap.
    """
    if text is None:
        return ""
    return _html.escape(str(text)).replace("  ", " &nbsp;")


def icon(name, colour=None, size=20):
    colour = colour or MUTED
    paths = {
        "standings": '<rect x="3.5" y="4.5" width="17" height="15" rx="2"></rect>'
                     '<path d="M3.5 9.5 L20.5 9.5"></path><path d="M3.5 14.5 L20.5 14.5"></path>',
        "star":      '<path d="M12 3 L14.6 9.1 L21 9.7 L16.2 14 L17.6 20.3 L12 17 '
                     'L6.4 20.3 L7.8 14 L3 9.7 L9.4 9.1 Z"></path>',
        "match":     '<circle cx="12" cy="12" r="8.5"></circle><circle cx="12" cy="12" r="3.5"></circle>',
        "team":      '<circle cx="9" cy="8" r="3.2"></circle>'
                     '<path d="M3.5 19 C3.5 15.6 6 13.8 9 13.8 C12 13.8 14.5 15.6 14.5 19"></path>'
                     '<path d="M16 13.9 C18.6 14.2 20.5 15.9 20.5 19"></path>'
                     '<circle cx="16.8" cy="8.6" r="2.6"></circle>',
        "player":    '<circle cx="12" cy="8" r="3.6"></circle>'
                     '<path d="M5 19.5 C5 15.8 8.1 13.8 12 13.8 C15.9 13.8 19 15.8 19 19.5"></path>',
        "search":    '<circle cx="11" cy="11" r="7"></circle><path d="M16.5 16.5 L21 21"></path>',
        "chevron":   '<path d="M6 9 L12 15 L18 9"></path>',
        "external":  '<path d="M14 4 H20 V10"></path><path d="M20 4 L11 13"></path>'
                     '<path d="M18 14.5 V19 A1.5 1.5 0 0 1 16.5 20.5 H5.5 '
                     'A1.5 1.5 0 0 1 4 19 V8 A1.5 1.5 0 0 1 5.5 6.5 H10"></path>',
    }
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{colour}" stroke-width="2.2" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{paths[name]}</svg>')


def page(title, body, active, depth=0):
    """Full HTML document. `depth` is how many directories deep the page sits."""
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="theme-color" content="{tokens.COLOURS['surface']}">
<link rel="stylesheet" href="{tokens.FONTS_HREF}">
<link rel="stylesheet" href="{up}app.css">
<script src="{up}app.js" defer></script>
</head>
<body>
<div class="app">
{body}
{tabs(active, up)}
</div>
</body>
</html>
"""


def header(title, up=""):
    return f"""  <header class="hdr">
    <span class="hdr-plate"><img src="{up}assets/psdl-mark.png" alt="Park Slope Dart League"></span>
    <span class="hdr-txt">
      <span class="eyebrow">PARK SLOPE DART LEAGUE</span>
      <span class="hdr-title">{esc(title)}</span>
    </span>
  </header>
"""


def statusbar(left, right="SYNCED FROM DARTCONNECT"):
    return f'  <div class="statusbar"><b>{esc(left)}</b><span>{esc(right)}</span></div>\n'


def division_nav(divisions, current, url_for):
    out = ['  <nav aria-label="Division" class="divnav">']
    for d in divisions:
        number = d.replace("Division", "").strip()
        cur = ' aria-current="page"' if d == current else ""
        out.append(f'    <a href="{url_for(d)}"{cur}><small>DIV</small><b class="num">{esc(number)}</b></a>')
    out.append("  </nav>")
    return "\n".join(out) + "\n"


def chip(code, count=1, rare=False):
    label = f"{code} &times;{count}" if count > 1 else code
    return f'<span class="chip{" rare" if rare else ""}">{label}</span>'


def chips_for(counts, rare_set):
    """Chips for a player's actual hits.

    DESIGN-SPEC hard requirement 1: never render an empty stat column. The median player has
    hits in exactly one category, so a 29-column grid would be almost entirely zeroes.
    """
    order = ["180", "171+", "R9", "C6", "C5", "R8", "C4", "R7", "S90", "F90", "R6", "C3", "R5", "95+"]
    known = sorted(counts, key=lambda c: order.index(c) if c in order else 99)
    return "".join(chip(c, counts[c], c in rare_set) for c in known if counts[c])


def tabs(active, up=""):
    items = [("standings", "STANDINGS", "standings", f"{up}standings.html"),
             ("all-stars", "ALL-STARS", "star",      f"{up}index.html"),
             ("match",     "MATCH",     "match",     f"{up}matches.html"),
             ("team",      "TEAM",      "team",      f"{up}teams.html"),
             ("player",    "PLAYER",    "player",    f"{up}players.html")]
    out = ['  <nav aria-label="Sections" class="tabs">']
    for key, label, ico, href in items:
        cur = ' aria-current="page"' if key == active else ""
        colour = GOLD if key == active else MUTED
        out.append(f'    <a href="{href}"{cur}>{icon(ico, colour)}<span>{label}</span></a>')
    out.append("  </nav>")
    return "\n".join(out)


def recap_link(hit, label="view on DartConnect"):
    """Traceability. Every number on the site opens the turn that produced it.

    DartConnect has no per-turn anchor, so the link opens the match recap and the row names
    the set and game -- enough for a captain to find the exact turn at the board.
    """
    where = f"Set {hit['set_index']} &middot; Game {hit['game_number']}"
    return (f'<a href="{hit["recap"]}" target="_blank" rel="noopener" '
            f'title="{esc(label)}">{where} {icon("external", GOLD, 13)}</a>')
