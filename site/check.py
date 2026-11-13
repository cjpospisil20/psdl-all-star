"""Output verification suite. Run after a build: python3 site/check.py

scraper/verify.py asserts the DATA is right -- totals, team mapping, scoring rules.
This file asserts the SITE is right: the HTML and CSS that actually reach a phone, and since
2026-11-13 the stylesheet's wider-screen layer that a tablet or desktop adds on top (section 16).

Everything here is a static check on public/. No browser is available, so anything that
genuinely needs layout or paint (does a 46px-tall control end up 46px after the font loads?
does the chip row wrap before it clips?) is NOT checked -- see the notes marked BROWSER-ONLY
rather than a check that pretends. The contrast maths is implemented from the WCAG formula and
sanity-checked against two published values before it is trusted for anything else.

Deliberately NOT checked, because a static reader cannot honestly answer them:

  - the rendered box of a control sized by padding and line-height (.leader, .row, .hit). The
    declared floors are checked; the painted result needs layout.
  - whether Anton and Archivo actually arrive, and what the fallback looks like if they do not.
  - reflow at 320px, and whether a long name wraps before it clips.
  - where the wide layout actually puts things: the tab bar lifted into the header's row, a
    player's paired cards, the schedule's two columns. Section 16 checks the rules that do it;
    the placement itself needs layout, so screenshots at 820, 1024 and 1440px check that.
  - focus rings, and keyboard order through the tab bar.
  - contrast of text over anything that is not a flat declared colour (nothing in the build
    does this today; if a gradient or image backdrop appears, this suite will not notice).
"""
import collections, html as _html, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT  = ROOT / "public"
sys.path.insert(0, str(ROOT / "site"))

import tokens                                       # noqa: E402

AA_TEXT     = 4.5      # WCAG 2.1 SC 1.4.3, normal-size text
AA_NON_TEXT = 3.0      # WCAG 2.1 SC 1.4.11, icons and control boundaries
MIN_TAP     = 44       # DESIGN-SPEC layout rule

# The player page (owner, 2026-11-12): the All Time section's id, how many of a season's hits show
# before the rest fold away, and the six singles figures every darts card carries, in order.
# Restated rather than imported from build.py: this suite judges the output, not the code.
ALL_TIME_ID  = "all-time"
TOP_HITS     = 3
DARTS_LABELS = ["3-DART AVG", "MARKS PER RD", "FIRST 9", "CHECKOUT", "LEG WINS", "OPP 3DA"]
SINGLES_NOTE = "Averages cover singles legs only"
NO_SINGLES   = "No singles legs"

# PPL, all star points per leg played, replaced PPW, points per week (owner, 2026-11-13). Every
# page that shows it says what it is, once.
PPL_NOTE = "PPL is points per leg played"
PPL      = r"\d+(?:\.\d)?"         # one decimal at most, as build.py prints it (`:g`)

failures = []


def check(name, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {name}{'  -- ' + detail if detail and not condition else ''}")
    if not condition:
        failures.append(name)


# ---------------------------------------------------------------- colour maths

def _channel(value):
    """One sRGB channel, 0-255, linearised. WCAG 2.1 relative luminance."""
    c = value / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour):
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def normalise_hex(value):
    h = value.strip().lstrip("#").upper()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h[:6]          # drop an alpha pair if one is ever written


# ---------------------------------------------------------------- reading the build

def read_pages():
    pages = {}
    for path in sorted(OUT.rglob("*.html")):
        pages[str(path.relative_to(OUT))] = path.read_text(encoding="utf-8")
    return pages


def text_nodes(markup):
    """Every text node, still HTML-escaped. Good enough: the build emits no script/style
    bodies inline, and app.js is an external file."""
    body = re.sub(r"<(script|style)\b.*?</\1>", "", markup, flags=re.S | re.I)
    return re.findall(r">([^<>]+)<", body)


def css_layers(css):
    """The stylesheet in source order as [(condition, text)]. The condition is None for the
    phone layer and the @media condition for each block's body.

    Since 2026-11-13 the stylesheet is the phone layout plus @media (min-width) blocks for wider
    screens. Each block is found by its braces, so the rules inside it keep their condition
    rather than reading as if they applied everywhere. Section 16 refuses any other at-rule, and
    an @media inside an @media, so one level is all there is to read.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    layers, start = [], 0
    for opening in re.finditer(r"@media\b([^{;]*)\{", css):
        if opening.start() < start:
            continue                    # nested inside a block already read; section 16 fails it
        layers.append((None, css[start:opening.start()]))
        depth, end = 1, opening.end()
        while depth and end < len(css):
            depth += {"{": 1, "}": -1}.get(css[end], 0)
            end += 1
        layers.append((" ".join(opening.group(1).split()), css[opening.end():end - 1]))
        start = end
    layers.append((None, css[start:]))
    return layers


def _rules(text):
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        decls = {}
        for decl in match.group(2).split(";"):
            if ":" in decl:
                prop, value = decl.split(":", 1)
                decls[prop.strip().lower()] = value.strip()
        for selector in match.group(1).split(","):
            yield " ".join(selector.split()), decls


def css_rules(css):
    """(selector, {prop: value}) for every rule in source order: the phone's and every wider
    screen's. A colour, a font or a control height declared only for a desktop is held to the
    same standard as the phone's."""
    for _condition, text in css_layers(css):
        yield from _rules(text)


def phone_rules(css):
    """(selector, {prop: value}) for the phone layer only: what a screen narrower than every
    @media sees."""
    for condition, text in css_layers(css):
        if condition is None:
            yield from _rules(text)


def merged_rules(css):
    """{selector: declarations}, merged across every layer in source order: what a selector ends
    up with on the widest screen. A plain dict would keep only a selector's last rule, so a
    desktop rule that sets one property would hide every property the phone's rule sets."""
    merged = {}
    for selector, decls in css_rules(css):
        merged.setdefault(selector, {}).update(decls)
    return merged


def strip_pseudo(selector):
    return re.sub(r"::?[a-zA-Z-]+(\([^)]*\))?", "", selector)


# ---------------------------------------------------------------- 0. trust the formula

def check_formula():
    print("\n0. The contrast formula itself")
    # Two published values. If either is wrong every contrast number below is noise, so this
    # section aborts the run rather than letting the suite report a comfortable lie.
    white_on_black = contrast("#FFFFFF", "#000000")
    grey_on_white  = contrast("#777777", "#FFFFFF")
    check("#FFFFFF on #000000 measures 21.00", round(white_on_black, 2) == 21.00,
          f"got {white_on_black:.4f}")
    check("#777777 on #FFFFFF measures 4.48", round(grey_on_white, 2) == 4.48,
          f"got {grey_on_white:.4f}")
    check("contrast is symmetric", contrast("#C59940", "#141112") == contrast("#141112", "#C59940"))
    check("3-digit and 6-digit hex agree", abs(luminance("#FFF") - luminance("#FFFFFF")) < 1e-12)


# ---------------------------------------------------------------- 1. links and images

def check_links(pages):
    print("\n1. Every internal reference resolves")
    broken, refs = [], 0
    for name, markup in pages.items():
        here = (OUT / name).parent
        for attr, url in re.findall(r'(href|src)="([^"]+)"', markup):
            if url.startswith(("http://", "https://", "mailto:", "data:", "#", "//")):
                continue
            refs += 1
            target = (here / _html.unescape(url).split("#")[0].split("?")[0]).resolve()
            if not target.exists() or not target.is_file():
                broken.append(f"{name} -> {url}")
    check(f"all {refs} local href/src targets exist", not broken,
          f"{len(broken)} broken: {broken[:4]}")

    missing_img, no_alt = [], []
    for name, markup in pages.items():
        here = (OUT / name).parent
        for tag in re.findall(r"<img\b[^>]*>", markup):
            src = re.search(r'src="([^"]+)"', tag)
            if not src or not (here / src.group(1)).resolve().is_file():
                missing_img.append(f"{name}: {tag[:70]}")
            if not re.search(r'alt="[^"]', tag):
                no_alt.append(f"{name}: {tag[:70]}")
    check("every <img src> resolves to a file", not missing_img, str(missing_img[:3]))
    check("every <img> has non-empty alt text", not no_alt, str(no_alt[:3]))

    # Every file shipped should be reachable. The reversed wordmark lost its only page when the
    # first-180 screen was retired (2026-11-12); build.SHIPPED_ASSETS stopped copying it, and
    # this is what would notice if it came back unreferenced.
    everything = "".join(pages.values())
    orphans = [str(p.relative_to(OUT)) for p in OUT.rglob("*")
               if p.is_file() and p.suffix in (".png", ".jpg", ".svg", ".css", ".js")
               and p.name not in everything]
    check("no unreferenced asset shipped", not orphans, str(orphans))
    # The owner retired the first-180 celebration screen: the Feed and Awards carry 180s now.
    stale = [n for n, m in pages.items() if "rare-hit.html" in m]
    check("the retired first-180 screen is gone and nothing links it",
          "rare-hit.html" not in pages and not stale, str(stale[:3]))


# ---------------------------------------------------------------- 2. placeholder leakage

def check_leakage(pages):
    print("\n2. No placeholder or format-string leakage")
    markers = ["[TEAM NAME]", "[OPPONENT TEAM]", "[MPR]", "[ALL STAR CUT]"]
    for marker in markers:
        hit = [n for n, m in pages.items() if marker in m]
        check(f"no {marker}", not hit, f"{len(hit)} pages, e.g. {hit[:2]}")

    # Any other ALL-CAPS bracketed token -- catches a placeholder nobody thought to list.
    stray = collections.Counter()
    for name, markup in pages.items():
        for token in re.findall(r"\[[A-Z][A-Z0-9 _-]{1,30}\]", markup):
            stray[f"{name}: {token}"] += 1
    check("no other bracketed ALL-CAPS placeholder", not stray, str(list(stray)[:4]))

    # 'None' / 'nan' only count as whole words in rendered text -- 'Brennan' and 'Nonesuch'
    # are legitimate names, and word boundaries are what tell them apart.
    for token in ("None", "nan", "NaN", "null", "undefined"):
        hit = []
        for name, markup in pages.items():
            for node in text_nodes(markup):
                if re.search(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", node):
                    hit.append(f"{name}: {node.strip()[:50]}")
        check(f"no literal '{token}' in rendered text", not hit, f"{len(hit)}x e.g. {hit[:2]}")

    # An unfilled f-string or .format() placeholder leaves its braces behind.
    braces = []
    for name, markup in pages.items():
        for found in re.findall(r"\{[^{}<>\"']{0,40}\}", markup):
            braces.append(f"{name}: {found}")
    check("no { } format-string leakage", not braces, f"{len(braces)}x e.g. {braces[:2]}")

    # A stat that has no value must be an em dash, never a bare empty element (DESIGN-SPEC
    # hard requirement 1: never render an empty stat column).
    empty = []
    for name, markup in pages.items():
        for tag in ("b", "small", "h1", "h2", "td"):
            for found in re.findall(rf"<{tag}\b[^>]*>\s*</{tag}>", markup):
                empty.append(f"{name}: {found[:40]}")
    check("no empty stat / heading element", not empty, f"{len(empty)}x e.g. {empty[:2]}")


# ---------------------------------------------------------------- 3 + 4. colour

# The only backgrounds that wrap arbitrary text. Every other painted surface in the
# stylesheet (the gold division chip, the gold hit chip, the raised chip, the statusbar, the
# card, the white logo plate) is reached by walking the selector's own ancestor prefix, so it
# is resolved exactly rather than guessed. If a new panel colour is added to tokens.py this
# list must grow with it -- the "every background is a token" check below will notice.
PANEL_TOKENS = ("ground", "surface")


def resolve_var(value, variables):
    """Substitute every var(--x) inline. Works for colours and for font stacks alike -- a
    `font-family: var(--body)` that has been repointed at Arial has to be visible to the font
    check, not hidden behind the indirection."""
    value = value.strip()
    for _ in range(10):                      # depth limit; --a: var(--b) is fine, cycles are not
        expanded = re.sub(r"var\((--[a-z0-9-]+)\)",
                          lambda m: variables.get(m.group(1), m.group(0)).strip(), value)
        if expanded == value:
            break
        value = expanded
    return value.strip()


def root_vars(css):
    return {prop: value for selector, decls in css_rules(css) if selector == ":root"
            for prop, value in decls.items() if prop.startswith("--")}


def check_colour(pages, css):
    rules = list(css_rules(css))
    variables = root_vars(css)
    palette = {normalise_hex(v): k for k, v in tokens.COLOURS.items()}

    # css_rules() reads inside the @media blocks for wider screens (2026-11-13), so every colour
    # declared for a desktop is judged here too. Section 16 refuses any at-rule it cannot read.

    # ---- which selectors actually ship ----
    classes, attrs = set(), set()
    for markup in pages.values():
        for value in re.findall(r'class="([^"]*)"', markup):
            classes.update(value.split())
        attrs.update(re.findall(r"\s([a-z-]+)=", markup))

    def used(selector):
        for cls in re.findall(r"\.([A-Za-z0-9_-]+)", selector):
            if cls not in classes:
                return False
        for attr in re.findall(r"\[([a-zA-Z-]+)", selector):
            if attr not in attrs:
                return False
        return True

    # Every background a selector declares, in any layer: a desktop rule that repaints a surface
    # adds a candidate rather than replacing the phone's, so text is judged against both.
    backgrounds = {}
    for selector, decls in rules:
        raw = decls.get("background-color") or decls.get("background")
        if not raw:
            continue
        colour = resolve_var(raw.split()[0], variables)
        if colour.startswith("#"):
            found = backgrounds.setdefault(strip_pseudo(selector).strip(), [])
            if normalise_hex(colour) not in found:
                found.append(normalise_hex(colour))

    def background_for(selector):
        """Nearest declared background walking up the selector's own ancestor prefix."""
        parts = strip_pseudo(selector).split()
        for cut in range(len(parts), 0, -1):
            prefix = " ".join(parts[:cut])
            if prefix in backgrounds:
                return backgrounds[prefix], prefix
        return [normalise_hex(tokens.COLOURS[t]) for t in PANEL_TOKENS], "panel (inherited)"

    print("\n3. Contrast -- every foreground/background pair the site actually paints")
    pairs, unresolved = {}, []
    for selector, decls in rules:
        if "color" not in decls or not used(selector):
            continue
        fg = resolve_var(decls["color"], variables)
        if not fg.startswith("#"):
            unresolved.append(f"{selector}: {decls['color']}")
            continue
        fg = normalise_hex(fg)
        candidates, where = background_for(selector)
        for bg in candidates:
            pairs.setdefault((fg, bg), []).append(f"{selector} on {where}")

    # Inline colours in the markup, should a page ever set one. They sit inside .app, so they are
    # judged against the same arbitrary-content panels.
    for name, markup in pages.items():
        for style in re.findall(r'style="([^"]*)"', markup):
            for value in re.findall(r"(?<!-)color:\s*([^;\"]+)", style):
                colour = resolve_var(value.strip(), variables)
                if colour.startswith("#"):
                    for token in PANEL_TOKENS:
                        pairs.setdefault((normalise_hex(colour), normalise_hex(tokens.COLOURS[token])),
                                         []).append(f"inline style in {name}")

    check("every colour declaration resolves to a hex", not unresolved, str(unresolved[:3]))

    worst = None
    for (fg, bg), where in sorted(pairs.items()):
        if fg == bg:
            check(f"{fg} is not painted on itself", False, where[0])
            continue
        ratio = contrast(fg, bg)
        label = f"{palette.get(fg, fg)} on {palette.get(bg, bg)}"
        check(f"{label} = {ratio:.2f}:1", ratio >= AA_TEXT,
              f"below {AA_TEXT}:1 -- used by {where[0]}")
        if worst is None or ratio < worst[0]:
            worst = (ratio, label)
    if worst:
        print(f"        ({len(pairs)} pairs checked; tightest is {worst[1]} at {worst[0]:.2f}:1)")

    print("\n   Icons and control edges (WCAG 1.4.11, 3:1 -- these are not text)")
    strokes = collections.Counter()
    for markup in pages.values():
        for value in re.findall(r'(?:stroke|fill)="(#[0-9A-Fa-f]{3,6})"', markup):
            strokes[normalise_hex(value)] += 1
    for stroke in sorted(strokes):
        for token in PANEL_TOKENS:
            bg = normalise_hex(tokens.COLOURS[token])
            ratio = contrast(stroke, bg)
            check(f"icon {palette.get(stroke, stroke)} on {token} = {ratio:.2f}:1",
                  ratio >= AA_NON_TEXT, f"below {AA_NON_TEXT}:1")

    print("\n4. No colour outside the token palette")
    # tokens.py documents exactly one correction (#4A3A16 -> #443112, the on-gold brown). That
    # correction is already IN the palette, so there is no value here that needs excusing: any
    # hex the build emits must be one of tokens.COLOURS.
    found = collections.Counter()
    sources = {"app.css": css, **pages}
    for name, text in sources.items():
        for value in re.findall(r"#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?\b", text):
            if normalise_hex(value) not in palette:
                found[(normalise_hex(value), name)] += 1
    check(f"{len(palette)} palette colours, nothing else", not found,
          "; ".join(f"{c} in {n}" for (c, n), _ in list(found.items())[:5]))

    named = set()
    for name, text in sources.items():
        for word in re.findall(r"(?:color|background|stroke|fill)\s*[:=]\s*[\"']?([a-z]{3,20})\b", text):
            if word not in ("var", "transparent", "none", "currentcolor", "inherit", "url"):
                named.add(f"{word} in {name}")
    check("no CSS named colours or rgb()/hsl() literals", not named, str(sorted(named)[:4]))

    # DESIGN-SPEC: three colours from the logo, everything else a shade of the logo black.
    # A token with a wide channel spread is a new hue, not a shade -- flag it.
    hues = []
    for name, value in tokens.COLOURS.items():
        if name in ("black", "gold", "white", "on_gold"):
            continue                        # the two logo chromatics and the on-gold brown
        r, g, b = (int(normalise_hex(value)[i:i + 2], 16) for i in (1, 3, 5))
        if max(r, g, b) - min(r, g, b) > 60:
            hues.append(f"{name} {value}")
    check("every non-logo token is a neutral shade, not a new hue", not hues, str(hues))


# ---------------------------------------------------------------- 5. type

def check_fonts(pages, css):
    print("\n5. Only Anton and Archivo")
    allowed = {"anton", "oswald", "archivo", "helvetica neue", "sans-serif"}
    banned  = ("inter", "roboto", "arial", "system-ui", "-apple-system", "segoe",
               "helvetica,", "times", "georgia", "verdana", "tahoma", "impact")

    # Every stack is resolved through the custom properties first. The stylesheet writes
    # `font-family: var(--body)` everywhere, so an unresolved scan would only ever see
    # "var(--body)" and would never notice --body being repointed at Arial.
    variables = root_vars(css)
    stacks = [resolve_var(decls["font-family"], variables)
              for _, decls in css_rules(css) if "font-family" in decls]
    stacks += [resolve_var(v, variables) for k, v in variables.items()
               if k in ("--display", "--body")]
    for markup in pages.values():
        for style in re.findall(r'style="([^"]*)"', markup):
            stacks.extend(resolve_var(s, variables)
                          for s in re.findall(r"font-family:\s*([^;\"]+)", style))

    bad_family = set()
    for stack in stacks:
        for family in stack.split(","):
            family = family.strip().strip("'\"").lower()
            if family and family not in allowed:
                bad_family.add(family)
    check("every font-family stack is Anton/Archivo (+ documented fallbacks)",
          not bad_family, str(sorted(bad_family)))

    # Scan only font-bearing text, with HTML entities stripped first. The whole raw document is
    # the wrong haystack: '&times;' -- which the chip counts emit for every '95+ x5' -- reads as
    # the Times font. That false alarm is exactly the kind that gets a suite ignored, so the
    # entity names are removed before matching and the scan is scoped to font declarations.
    font_text = " ".join(stacks).lower()
    for markup in pages.values():
        font_text += " " + " ".join(re.findall(r'href="(https://fonts\.[^"]*)"', markup)).lower()
    font_text += " " + " ".join(re.findall(r"@font-face[^}]*\}", css)).lower()
    font_text = re.sub(r"&[a-z]+;|&#x?[0-9a-f]+;", " ", font_text)
    present = [b for b in banned if b in font_text]
    check("Inter / Roboto / Arial and friends absent", not present, str(present))

    hrefs = set()
    for markup in pages.values():
        hrefs.update(re.findall(r'href="(https://fonts\.googleapis\.com[^"]*)"', markup))
    check("exactly one Google Fonts stylesheet URL", len(hrefs) == 1, str(sorted(hrefs)))
    families = set()
    for href in hrefs:
        families.update(f.split(":")[0] for f in re.findall(r"family=([^&\"]+)", href))
    check("Google Fonts requests only Anton and Archivo",
          families == {"Anton", "Archivo"}, str(sorted(families)))
    linked = [n for n, m in pages.items() if "fonts.googleapis.com" not in m]
    check("every page links the font stylesheet", not linked, f"{len(linked)} missing")

    check(".num sets font-variant-numeric: tabular-nums",
          merged_rules(css).get(".num", {}).get("font-variant-numeric") == "tabular-nums")


# ---------------------------------------------------------------- 6. document structure

def check_structure(pages):
    print("\n6. Document structure, every page")
    bad_h1 = {n: len(re.findall(r"<h1\b", m)) for n, m in pages.items()
              if len(re.findall(r"<h1\b", m)) != 1}
    check(f"all {len(pages)} pages have exactly one <h1>", not bad_h1,
          f"{len(bad_h1)} wrong: " + ", ".join(f"{n} has {c}" for n, c in
                                               list(bad_h1.items())[:4]))

    no_title = [n for n, m in pages.items()
                if not re.search(r"<title>\s*\S.*?</title>", m, re.S)]
    check("every page has a non-empty <title>", not no_title, f"{len(no_title)}: {no_title[:3]}")

    no_lang = [n for n, m in pages.items() if not re.search(r'<html[^>]*\blang="en"', m)]
    check('every page has <html lang="en">', not no_lang, f"{len(no_lang)}: {no_lang[:3]}")

    no_vp = [n for n, m in pages.items()
             if not re.search(r'<meta[^>]*name="viewport"[^>]*width=device-width', m)]
    check("every page has a device-width viewport", not no_vp, f"{len(no_vp)}: {no_vp[:3]}")

    no_charset = [n for n, m in pages.items() if not re.search(r'<meta charset="utf-8"', m, re.I)]
    check("every page declares utf-8", not no_charset, f"{len(no_charset)}: {no_charset[:3]}")

    no_doctype = [n for n, m in pages.items() if not m.lstrip().lower().startswith("<!doctype html")]
    check("every page starts with <!doctype html>", not no_doctype, str(no_doctype[:3]))

    # Heading order: an h2 before the page's h1 is a screen-reader trap.
    jumbled = [n for n, m in pages.items()
               if re.search(r"<h2\b", m)
               and (m.find("<h1") == -1 or m.find("<h2") < m.find("<h1"))]
    check("no <h2> before the <h1>", not jumbled, str(jumbled[:3]))

    unlabelled = [n for n, m in pages.items()
                  if re.search(r"<nav\b(?![^>]*aria-label)", m)]
    check("every <nav> is labelled", not unlabelled, f"{len(unlabelled)}: {unlabelled[:3]}")

    unlabelled_input = []
    for name, markup in pages.items():
        for tag in re.findall(r"<input\b[^>]*>", markup):
            ident = re.search(r'id="([^"]+)"', tag)
            if not ident or f'for="{ident.group(1)}"' not in markup:
                unlabelled_input.append(f"{name}: {tag[:50]}")
    check("every <input> has a <label for>", not unlabelled_input, str(unlabelled_input[:3]))

    # DESIGN-SPEC: no icon fonts, no emoji.
    emoji = [n for n, m in pages.items()
             if re.search(r"[\U0001F000-\U0001FAFF☀-➿]", m)]
    check("no emoji in the markup", not emoji, str(emoji[:3]))


# ---------------------------------------------------------------- 7. tap targets

def check_tap_targets(pages, css):
    print(f"\n7. Tap targets -- declared heights on links and buttons (>= {MIN_TAP}px)")
    # Which classes the build actually puts on an <a> or <button>. Derived from the output, so
    # a new tappable class is picked up automatically instead of needing a hand-kept list.
    tappable = set()
    for markup in pages.values():
        for tag in re.findall(r"<(?:a|button|summary)\b[^>]*>", markup):
            found = re.search(r'class="([^"]*)"', tag)
            if found:
                tappable.update(found.group(1).split())
    check("found the tappable classes in the output", bool(tappable), "none found")

    # <summary> is a control too: it opens the season and league pickers (2026-11-12).
    def targets_control(selector):
        parts = strip_pseudo(selector).split()
        if not parts:
            return False
        last = parts[-1]
        if re.fullmatch(r"(a|button|input|summary)(\[[^\]]*\])*", last):
            return True
        return any(cls in tappable for cls in re.findall(r"\.([A-Za-z0-9_-]+)", last))

    too_small, checked = [], 0
    for selector, decls in css_rules(css):
        if not targets_control(selector):
            continue
        for prop in ("height", "min-height", "max-height"):
            value = decls.get(prop, "")
            match = re.fullmatch(r"(\d+(?:\.\d+)?)px", value)
            if not match:
                continue
            checked += 1
            if float(match.group(1)) < MIN_TAP:
                too_small.append(f"{selector} {prop}:{value}")
    check(f"all {checked} declared control heights are >= {MIN_TAP}px", not too_small,
          str(too_small))

    # A row with no height at all must at least floor itself -- on every screen, so the rules are
    # merged across the layers: a desktop rule may add to a row, but not drop its floor.
    merged = merged_rules(css)
    rows = {sel: d for sel, d in merged.items() if sel in (".row", ".hit")}
    for selector, decls in rows.items():
        floor = decls.get("min-height", "")
        check(f"{selector} declares a min-height >= {MIN_TAP}px",
              bool(re.fullmatch(r"(\d+)px", floor)) and int(floor[:-2]) >= MIN_TAP,
              f"min-height:{floor or 'unset'}")

    # The phone's bar. From 768px the same links sit in the header, 80px tall (section 16).
    check("tab bar is the 64px the spec asks for",
          any(sel == ".tabs a" and decls.get("height") == "64px"
              for sel, decls in phone_rules(css)))

    # BROWSER-ONLY, deliberately not checked here: the *rendered* box of a control whose size
    # comes from padding + line-height (.leader, .row, .hit) cannot be measured without layout.
    # Static analysis can only confirm the declared floors above, which is what it does.


# ---------------------------------------------------------------- 8. names

def check_names(pages):
    print("\n8. Name integrity")
    everything = "".join(pages.values())

    # DartConnect really does send 'Colin  Ratner' with two spaces. components.esc() turns the
    # second into &nbsp; so HTML cannot collapse it.
    check("Colin's double space survives as 'Colin &nbsp;Ratner'",
          "Colin &nbsp;Ratner" in everything,
          "not found; a collapsed 'Colin Ratner' is the wrong name")
    check("the collapsed single-space form never appears",
          not re.search(r"Colin Ratner", everything),
          "found 'Colin Ratner' with one space")

    check("quoted nickname is HTML-escaped",
          "Anaelechi &quot;Lay&quot; Owunwanne" in everything,
          "expected &quot; around Lay")
    raw_quote = []
    for name, markup in pages.items():
        for node in text_nodes(markup):
            if '"' in node:
                raw_quote.append(f"{name}: {node.strip()[:50]}")
    check("no raw double quote in any text node", not raw_quote,
          f"{len(raw_quote)}x e.g. {raw_quote[:2]}")

    # Every genuine run of spaces must have been converted to " &nbsp;" by components.esc().
    # A literal run surviving in the markup means a space arrived at a template boundary --
    # usually an untrimmed value in the source data. It matters because .name is pre-wrap: the
    # run is not collapsed, it is drawn.
    # Indentation is skipped by comparing line by line -- the build pretty-prints its markup,
    # so a leading "\n      " is layout, not content.
    literal = []
    for name, markup in pages.items():
        for node in text_nodes(markup):
            for line in node.split("\n"):
                line = line.strip()
                if "  " in line and re.search(r"[A-Za-z]", line):
                    literal.append(f"{name}: {line[:60]!r}")
    check("no literal double space in rendered text (a real one must be &nbsp;)", not literal,
          f"{len(literal)}x e.g. {literal[:2]}")

    # DESIGN-SPEC hard requirement 5: wrap, never truncate.
    truncated = []
    for name, markup in pages.items():
        for node in re.findall(r'class="name"[^>]*>([^<]*)', markup):
            if node.rstrip().endswith(("...", "…")):
                truncated.append(f"{name}: {node.strip()[:60]}")
    check("no name ends in an ellipsis", not truncated, str(truncated[:3]))

    check("no name is clipped by a single-line ellipsis in the markup",
          not re.search(r"text-overflow|line-clamp", everything))

    # The double space is preserved by encoding, not by CSS, so assert the encoding happened at
    # all -- a build that silently stopped escaping would otherwise pass every check above.
    check("the &nbsp; encoding is present in the output", everything.count("&nbsp;") > 0,
          "no &nbsp; anywhere -- components.esc() may have stopped converting space runs")

    # The inverse guard. Whitespace preservation deliberately does NOT come from
    # white-space: pre-wrap on .name: the build pretty-prints its markup, so pre-wrap would
    # render the source indentation of any multi-line .name element as visible leading space.
    # Keeping .name free of raw indentation means that choice stays reversible.
    indented = []
    for name, markup in pages.items():
        for match in re.finditer(r'<(\w+)[^>]*\bclass="[^"]*\bname\b[^"]*"[^>]*>', markup):
            close = markup.find(f"</{match.group(1)}>", match.end())
            content = markup[match.end():close if close != -1 else match.end()]
            if re.search(r"\n[ \t]", content) or content != content.strip():
                indented.append(f"{name}: <{match.group(1)} class=name> "
                                f"{content[:50]!r}")
    check("no .name element carries raw source indentation", not indented,
          f"{len(indented)}x e.g. {indented[:2]}")


def check_names_css(css):
    print("\n   The CSS that keeps names readable")
    rules = merged_rules(css)
    name = rules.get(".name", {})
    # No white-space assertion here on purpose: the double space in 'Colin  Ratner' is preserved
    # by components.esc() encoding it as '&nbsp;', which HTML cannot collapse whatever
    # white-space says. Asserting pre-wrap would be asserting a mechanism the site does not use
    # -- and pre-wrap actively hurts, see the indentation guard in check_names().
    check(".name wraps long names instead of overflowing",
          name.get("overflow-wrap") in ("anywhere", "break-word"),
          f"overflow-wrap:{name.get('overflow-wrap')}")
    check(".name is styled at all", bool(name), "no .name rule in the stylesheet")
    check("no truncation anywhere in the stylesheet",
          not re.search(r"text-overflow\s*:\s*ellipsis|-webkit-line-clamp", css))


# ---------------------------------------------------------------- 9. tabular numerals

# Hit codes are excluded on purpose. '95+', '171+' and '180' are chip LABELS, not figures in a
# column -- chips sit in a wrapping flex row where tabular advance width buys nothing, and the
# codes they sit beside ('R5', 'C3') are not numeric at all.
NUMERIC_SLOTS = [
    (r'<span class="([^"]*\brow-rank\b[^"]*)"',      "row rank"),
    (r'<span class="([^"]*\bleader-rank\b[^"]*)"',   "leader rank"),
    (r'<span class="([^"]*\bhit-val\b[^"]*)"',       "hit value"),
]
PURE_NUMBER = re.compile(r"^[\s\d.,%+:/]*\d[\s\d.,%+:/]*$")


def check_numerals(pages):
    print("\n9. Numbers carry the tabular-nums class")
    for pattern, label in NUMERIC_SLOTS:
        bad = []
        for name, markup in pages.items():
            for classes in re.findall(pattern, markup):
                if "num" not in classes.split():
                    bad.append(f'{name}: class="{classes}"')
        check(f"every {label} has class num", not bad, f"{len(bad)}x e.g. {bad[:2]}")

    # The points column: <b> inside .row-pts / .leader-pts / .stat.
    for wrapper in ("row-pts", "leader-pts", "stat"):
        bad = []
        for name, markup in pages.items():
            for block in re.findall(rf'class="{wrapper}"[^>]*>(.*?)</span>\s*(?=<)', markup, re.S):
                for classes, text in re.findall(r'<b(?:\s+class="([^"]*)")?[^>]*>([^<]*)</b>', block):
                    if PURE_NUMBER.match(_html.unescape(text).strip() or "x") \
                       and "num" not in (classes or "").split():
                        bad.append(f"{name}: .{wrapper} <b>{text.strip()[:16]}</b>")
        check(f"every number in .{wrapper} has class num", not bad, f"{len(bad)}x e.g. {bad[:2]}")

    # Sweep: any element whose entire content is a bare number.
    missing = collections.Counter()
    tagged = 0
    for name, markup in pages.items():
        for tag, attrs, text in re.findall(r"<(b|span|small|i|em|strong|td|th)\b([^>]*)>([^<]*)</\1>",
                                           markup):
            content = _html.unescape(text).strip()
            if not content or not PURE_NUMBER.match(content):
                continue
            classes = re.search(r'class="([^"]*)"', attrs)
            classes = classes.group(1).split() if classes else []
            style = re.search(r'style="([^"]*)"', attrs)
            inline_tabular = style and "tabular-nums" in style.group(1)
            if "chip" in classes:
                continue          # hit code labels -- see the note above NUMERIC_SLOTS
            if "num" in classes or inline_tabular:
                tagged += 1
            else:
                missing[f'<{tag} class="{" ".join(classes)}">{content[:12]}'] += 1
    check(f"all {tagged} bare-number elements are tabular", not missing,
          f"{sum(missing.values())}x e.g. {list(missing)[:3]}")


# ---------------------------------------------------------------- 10. spec invariants

def check_spec_rules(pages, css):
    print("\n10. DESIGN-SPEC invariants visible in the output")
    rules = merged_rules(css)        # what each selector ends up with, on any screen
    gold  = normalise_hex(tokens.COLOURS["gold"])

    check("rare chips are gold-filled with black text",
          rules.get(".chip.rare", {}).get("background") == "var(--gold)"
          and rules.get(".chip.rare", {}).get("color") == "var(--black)",
          str(rules.get(".chip.rare")))
    check("common chips are raised grey with chip text",
          rules.get(".chip", {}).get("background") == "var(--raised)"
          and rules.get(".chip", {}).get("color") == "var(--chip-text)",
          str(rules.get(".chip")))

    # Never rank across divisions: a leaderboard page must say so on screen.
    # Every season's division boards, not only the current one's (season history, 2026-11-12).
    boards = [n for n, kind in all_stars_boards(pages).items() if kind == "division"]
    check("found the leaderboard pages", len(boards) >= 2, str(boards))
    silent = [n for n in boards if "division" not in pages[n].lower()
              or "only" not in pages[n].lower()]
    check("every leaderboard says ranking is within division only", not silent, str(silent))

    # Traceability: every hit row links to a DartConnect recap.
    hit_rows, linked = 0, 0
    for markup in pages.values():
        for block in re.findall(r'<div class="hit">(.*?)</div>', markup, re.S):
            hit_rows += 1
            if "recap.dartconnect.com" in block:
                linked += 1
    check(f"all {hit_rows} hit rows link to a DartConnect recap", hit_rows and hit_rows == linked,
          f"{hit_rows - linked} unlinked")
    external = []
    for markup in pages.values():
        for tag in re.findall(r'<a\b[^>]*target="_blank"[^>]*>', markup):
            if "noopener" not in tag:
                external.append(tag[:60])
    check("every target=_blank link sets rel=noopener", not external, str(external[:2]))

    # The cut line is a placeholder until the league sets it -- it must be absent, not bracketed.
    cut = [n for n, m in pages.items() if "cutline" in m]
    check("no cut line shipped while ALL_STAR_CUT is unset", not cut, str(cut[:3]))

    # Gold is a fill, not a text colour behind arbitrary text: only the logo black and the
    # on-gold brown clear AA on it, and the spec says so. Find every selector that paints a
    # gold background, then audit the colours declared on it and on its descendants.
    variables = root_vars(css)
    gold_hosts = [strip_pseudo(sel).strip() for sel, decls in css_rules(css)
                  if normalise_hex(resolve_var((decls.get("background-color")
                                                or decls.get("background") or "x").split()[0],
                                               variables) or "x") == gold
                  or (decls.get("background") or decls.get("background-color")) == "var(--gold)"]
    check("found the gold-filled selectors", bool(gold_hosts), "none -- did .chip.rare move?")
    wrong = []
    for selector, decls in css_rules(css):
        if "color" not in decls:
            continue
        clean = strip_pseudo(selector).strip()
        if not any(clean == host or clean.startswith(host + " ") for host in gold_hosts):
            continue
        colour = resolve_var(decls["color"], variables)
        if not colour.startswith("#") or contrast(normalise_hex(colour), gold) < AA_TEXT:
            wrong.append(f"{selector} -> {decls['color']}")
    check(f"all {len(gold_hosts)} gold fills carry only AA-safe text", not wrong, str(wrong))


# ---------------------------------------------------------------- 11. navigation and new views

TABS = ["standings.html", "index.html", "schedule.html", "feed.html", "awards.html"]


def check_navigation(pages):
    print("\n11. Navigation, team pages, the ALL board and the awards index")
    # Page names use the OS separator; compare them as URLs so this runs the same on Windows.
    site = {name.replace("\\", "/"): markup for name, markup in pages.items()}

    # The Team tab was retired for Feed (2026-11-11). Team pages are reached from Standings.
    # The Match tab became Schedule the same day (section 12).
    wrong_tabs = []
    for name, markup in site.items():
        nav = re.search(r'<nav aria-label="Sections" class="tabs">(.*?)</nav>', markup, re.S)
        found = [u.rsplit("/", 1)[-1] for u in re.findall(r'href="([^"]+)"', nav.group(1))] \
            if nav else []
        if found != TABS:
            wrong_tabs.append(f"{name}: {found}")
    check("every tab bar is Standings · All-Stars · Schedule · Feed · Awards", not wrong_tabs,
          f"{len(wrong_tabs)} pages, e.g. {wrong_tabs[:2]}")
    check("the Feed page exists", "feed.html" in site)
    stale = [n for n, m in site.items() if re.search(r'href="[^"]*teams(-division-\d)?\.html"', m)]
    check("nothing links the retired Teams index", not stale, str(stale[:3]))

    # ---- Standings -> team pages, both nights (2026-11-12) ----
    standings = standings_pages(site)
    check("found the standings pages", len(standings) >= 2, str(sorted(standings)))
    unlinked, reached = [], set()
    for name, markup in standings.items():
        for tag, attrs in re.findall(r'<(a|div) class="row"([^>]*)>', markup):
            href = re.search(r'href="(team/[^"]+\.html)"', attrs)
            if tag != "a" or not href:
                unlinked.append(name)
            else:
                reached.add(href.group(1))
    check("every standings row links to its team page", not unlinked,
          f"{len(unlinked)} plain rows, e.g. on {unlinked[:2]}")
    teams = {n for n in site if n.startswith("team/")}
    check(f"all {len(teams)} team pages are reached from Standings, and no more",
          teams == reached,
          f"unlinked {sorted(teams - reached)[:3]}, linked but unbuilt {sorted(reached - teams)[:3]}")

    # A team page's back link opens its own league's standings, at its own division.
    wrong_back, league_of = [], {}
    for name in sorted(teams):
        back = re.search(r'<a class="back" href="\.\./(standings[^"]*\.html)"', site[name])
        division = re.search(r"<p>(.*?) &middot; captain", site[name])
        target = standings.get(back.group(1)) if back else None
        heading = re.search(r"<h1>(.*?)</h1>", target) if target else None
        # A standings page with no league picker has no night; that is a failure here, not a
        # crash further down (section 14 then names the page).
        if not division or not heading or heading.group(1) != division.group(1).upper() \
                or not night_of(target):
            wrong_back.append(name)
        else:
            league_of[name] = night_of(target)
    check("every team page's back link returns to its own division's standings", not wrong_back,
          str(wrong_back[:3]))

    # The full roster, per night: every player on a league's current-season boards is listed on
    # exactly one of that league's team pages, so nobody is left off a team and nobody is credited
    # to two. (A player page covers every season, so a player from a past season alone has a page
    # but no team page -- team pages are the current season's. A player on both nights is on one
    # team page of each.)
    boards = all_stars_boards(site)
    for night in sorted(set(league_of.values())):
        key = current_season_key(standings, night)
        listed = collections.Counter()
        for name in (n for n, league in league_of.items() if league == night):
            listed.update(set(re.findall(r'href="\.\./(player/[^"#]+\.html)', site[name])))
        scorers = set()
        for name, kind in boards.items():
            if kind == "division" and season_scope(site[name]) == key:
                scorers.update(re.findall(r'<a class="(?:row|leader)" href="(player/[^"#]+\.html)',
                                          site[name]))
        off_roster = sorted(scorers - set(listed))
        doubled = sorted(p for p, c in listed.items() if c > 1)
        strays = sorted(set(listed) - scorers)
        check(f"all {len(scorers)} of {night.capitalize()}'s scorers appear on exactly one "
              f"{night.capitalize()} team page",
              scorers and not off_roster and not doubled and not strays,
              f"missing {off_roster[:3]}, on two {doubled[:3]}, not on a board {strays[:3]}")

    # ---- GP and the playoff check mark (2026-11-11) ----
    # The caption states the rule; every row must follow it. A page whose caption states no
    # minimum (season length unknown) must mark nobody.
    no_gp, wrong_mark, bad_rule, mute_mark = [], [], [], []
    roster_rows = 0
    for name in sorted(teams):
        markup = site[name]
        rule = re.search(r"played at least (\d+) of the (\d+) nights", markup)
        need = int(rule.group(1)) if rule else None
        if rule and need != (int(rule.group(2)) - 1) // 2:
            bad_rule.append(f"{name}: {rule.group(0)}")
        for _tag, row in re.findall(r'<(a|div) class="row"[^>]*>(.*?)</\1>', markup, re.S):
            roster_rows += 1
            gp = re.search(r'<small class="num">GP (\d+)\b', row)
            if not gp:
                no_gp.append(name)
                continue
            marked = 'class="eligible"' in row
            if marked != (need is not None and int(gp.group(1)) >= need):
                wrong_mark.append(f"{name}: GP {gp.group(1)}, minimum {need}, marked {marked}")
            if marked and not re.search(r'<span class="eligible"><svg[^>]*aria-hidden="true"'
                                        r'.*?</svg><span class="vh">[^<]+</span>', row):
                mute_mark.append(name)
    check(f"all {roster_rows} team-page roster rows show GP", roster_rows and not no_gp,
          f"{len(no_gp)} without, e.g. on {no_gp[:2]}")
    check("every stated playoff minimum is the largest whole number below half the season",
          not bad_rule, str(bad_rule[:2]))
    check("a player is marked playoff eligible exactly when GP reaches the stated minimum",
          not wrong_mark, f"{len(wrong_mark)}x e.g. {wrong_mark[:2]}")
    check("every check mark is an SVG with words for screen readers", not mute_mark,
          str(mute_mark[:3]))

    # ---- the ALL board: the owner-approved exception to never ranking across divisions ----
    board = site.get("all.html")
    check("the All-Stars ALL board exists", board is not None)
    if board:
        rows = re.findall(r'<a class="row".*?</a>', board, re.S)
        check("the ALL board lists players", bool(rows))
        check("the ALL board crowns nobody: no leader card", 'class="leader"' not in board)
        check("the ALL board crowns nobody: no gold rank",
              not re.search(r'class="row-rank[^"]*\btop\b', board))
        silent = [r[:60] for r in rows if not re.search(r'<small class="name">Division \d', r)]
        check("every ALL board row names its division", not silent, str(silent[:2]))
        check("the ALL board warns that a league rank reflects the division",
              "says as much about a player&rsquo;s division" in board)
        ranks = [int(n) for n in re.findall(r'<span class="row-rank[^"]*">(\d+)</span>', board)]
        check("the ALL board is numbered 1..N", ranks == list(range(1, len(rows) + 1)),
              f"{len(ranks)} ranks for {len(rows)} rows")
        points = [int(p.replace(",", "")) for p in
                  re.findall(r'<span class="row-pts">\s*<b class="num">([\d,]+)</b>', board)]
        check("the ALL board runs highest points first",
              len(points) == len(rows) and points == sorted(points, reverse=True))
    # The owner dropped the "Division 1 scores roughly 2.5x Division 5" caption (2026-11-12): it
    # was a week-1 figure, and the season has drifted from it.
    ratio = [n for n, m in site.items() if re.search(r"2\.5\s*(?:&times;|×|x\b)", m)]
    check("no page quotes the retired 2.5x division gap", not ratio, str(ratio[:3]))
    # PPW, points per week, became PPL, points per leg played (owner, 2026-11-13).
    ppw = [n for n, m in site.items() if re.search(r"\bPPW\b", m)]
    check("no page shows the retired PPW", not ppw, str(ppw[:3]))
    # A figure -- never None, never blank -- on every All-Stars row and leader card, on the boards
    # and on Awards, and on every player page's points card. Standings and team pages show PTS
    # alone in the same row-pts slot, and never had a PPW.
    scope = set(all_stars_boards(site)) | {
        n for n in site if re.fullmatch(r"(?:player|award)/.+\.html|awards(?:-[a-z]+)?\.html", n)}
    blank, blocks = [], 0
    for name in sorted(scope):
        found = (re.findall(r'<span class="(?:row|leader)-pts">.*?</span>\s*</span>', site[name],
                            re.S)
                 + re.findall(r'<h2>ALL STAR POINTS</h2>.*?</div>', site[name], re.S))
        blocks += len(found)
        blank += [name + ": " + " ".join(b.split())[:70] for b in found
                  if not re.search(rf'<span class="num">PPL {PPL}(?: &middot;|</span>)'
                                   rf'|<b class="num">{PPL}</b><small>PPL</small>', b)]
    check(f"all {blocks} All-Stars rows, leader cards and points cards show a PPL",
          blocks and not blank, f"{len(blank)}: {blank[:2]}")
    shows = [n for n, m in sorted(site.items()) if re.search(r">PPL [\d.]|<small>PPL<", m)]
    unexplained = [n for n in shows if site[n].count(PPL_NOTE) != 1]
    check(f"all {len(shows)} pages that show PPL say once what it is",
          shows and not unexplained, str(unexplained[:3]))
    boards = [n for n in site if re.fullmatch(r"index\.html|division-\d\.html", n)]
    no_chip = [n for n in boards if 'href="all.html"' not in site[n]]
    check("every division board offers the ALL chip", not no_chip, str(no_chip))
    # Past seasons too: wherever there are division chips, ALL is one of them.
    chipless = [n for n, kind in all_stars_boards(site).items()
                if 'class="divnav"' in site[n] and '<b class="num">ALL</b>' not in site[n]]
    check("every board with division chips offers ALL", not chipless, str(chipless[:3]))

    # ---- the awards index names who holds each award, per night ----
    awards_pages = {n: m for n, m in site.items()
                    if re.fullmatch(r"awards(-[a-z]+)?\.html", n)}
    for index_name, index_markup in sorted(awards_pages.items()):
        detail_prefix = "award/monday-" if "monday" in index_name else "award/"
        detail_pages = sorted(n for n in site if n.startswith(detail_prefix)
                              and ("monday-" in n) == ("monday" in index_name))
        missing = []
        for name in detail_pages:
            first = re.search(r'href="\.\./(player/[^"]+\.html(?:#[^"]*)?)"', site[name])
            if first and f'href="{first.group(1)}"' not in index_markup:
                missing.append(f"{name}: {first.group(1)}")
        check(f"{index_name} names the holder of every award that has one", not missing,
              str(missing[:3]))
    for index_name, index_markup in sorted(awards_pages.items()):
        section = re.search(r"ALL STAR POINTS LEADER</h2>(.*?)<h2", index_markup, re.S)
        order = [int(d) for d in re.findall(r'<small class="name">Division (\d)',
                                            section.group(1))] if section else []
        if order:
            check(f"{index_name} points leaders are listed in division order",
                  order == sorted(order), str(order))


# ---------------------------------------------------------------- 12. the schedule

def check_schedule(pages):
    """The Schedule tab (2026-11-11), which replaced the Match tab and its 137 match pages."""
    print("\n12. The schedule")
    site = {name.replace("\\", "/"): markup for name, markup in pages.items()}
    page = site.get("schedule.html")
    check("the Schedule page exists", page is not None)
    if page is None:
        return
    check("the old Match tab address still serves the schedule",
          site.get("matches.html") == page)
    stale = [n for n, m in site.items()
             if re.search(r'href="[^"]*(?:match/[^"]*|matches-division-\d\.html)"', m)]
    check("nothing links a retired match page or match-night list", not stale, str(stale[:3]))

    # Each night's Schedule (2026-11-12): Tuesday's schedule.html, Monday's schedule-monday.html.
    standings = standings_pages(site)
    pages_ = {n: m for n, m in schedule_pages(site).items() if n != "matches.html"}
    check("every night with standings has a Schedule",
          {night_of(m) for m in standings.values()} == {night_of(m) for m in pages_.values()},
          str(sorted(pages_)))
    for name, page in sorted(pages_.items()):
        night = night_of(page)
        # Live is decided by the clock in the browser, never baked in: a static page that said
        # LIVE would still be saying it on Wednesday.
        check(f"{name}: no night ships as live",
              not re.search(r'class="night live"', page)
              and all(" hidden" in tag for tag in re.findall(r"<span[^>]*live-tag[^>]*>", page)))

        starts = re.findall(r'<section class="night" data-start="([^"]*)">', page)
        malformed = [s for s in starts
                     if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:00[-+]\d\d:\d\d", s)]
        check(f"{name}: all {len(starts)} nights carry a first-darts time with its UTC offset",
              not malformed, str(malformed[:3]))
        # app.js gilds the FIRST live night in place, so tonight must come first: nights ascend.
        check(f"{name}: nights run in date order", starts == sorted(starts), str(starts))

        # The league's own divisions, from the h1 of each of its standings pages.
        divisions = {re.sub(r"[^a-z0-9]+", "-", re.search(r"<h1>(.*?)</h1>", m).group(1).lower())
                     .strip("-") for m in standings.values() if night_of(m) == night}
        select = re.search(r'<select id="division"[^>]*>(.*?)</select>', page, re.S)
        options = re.findall(r'<option value="([^"]*)">', select.group(1)) if select else []
        if starts:
            check(f"{name}: the division menu is All plus every {night} standings division",
                  options[:1] == [""] and sorted(options[1:]) == sorted(divisions),
                  f"options {options}, standings {sorted(divisions)}")

        wrong = []
        for cls, attrs, inner in re.findall(
                r'<div class="(fixture(?: bye)?)"([^>]*)>(.*?)\n  </div>', page, re.S):
            division = re.search(r'data-division="([^"]*)"', attrs)
            labels = re.findall(r'<a class="fx-team(?: away)?" href="team/[^"]+\.html">'
                                r'<b class="name">[^<]+</b><small>([A-Z]+)</small>', inner)
            expected = ["BYE"] if cls == "fixture bye" else ["HOME", "AWAY"]
            if labels != expected or not division or division.group(1) not in divisions:
                wrong.append(f"{cls}: {labels} {division.group(1) if division else None}")
        fixtures = len(re.findall(r'<div class="fixture', page))
        check(f"{name}: all {fixtures} fixtures link HOME then AWAY (or one BYE) to team pages, "
              "in a known division", not wrong, str(wrong[:3]))


# ---------------------------------------------------------------- 13. season history

# Every All-Stars board: the current Tuesday season's (index.html is division 1's alias), every
# other season's (all-stars-<season key>[-<division>].html), and All Time.
ALL_STARS_BOARD = re.compile(r"index\.html|division-\d+\.html|all\.html|all-stars-[a-z0-9-]+\.html")


def all_stars_boards(site):
    """{page: kind} for every All-Stars board. kind is "division" (ranked within one division --
    including a one-division season's only board), "all" (a season's ALL board) or "all-time"."""
    out = {}
    for name, markup in site.items():
        if not ALL_STARS_BOARD.fullmatch(name):
            continue
        if name == "all-stars-all-time.html":
            out[name] = "all-time"
        elif "<h1>ALL DIVISIONS</h1>" in markup:
            out[name] = "all"
        else:
            out[name] = "division"
    return out


def standings_pages(site):
    """Every standings page, both nights: standings.html, standings-division-N.html and
    another night's standings-<night>[-<division>].html."""
    return {n: m for n, m in site.items() if re.fullmatch(r"standings(-[a-z0-9-]+)?\.html", n)}


def schedule_pages(site):
    """Every Schedule page: schedule.html (and its matches.html alias), schedule-<night>.html."""
    return {n: m for n, m in site.items()
            if re.fullmatch(r"schedule(-[a-z0-9-]+)?\.html|matches\.html", n)}


def night_of(markup):
    """The night a Standings or Schedule page shows -- its league picker's scope, e.g. 'tuesday'."""
    found = re.search(r'<details class="picker" data-scope="([^"]+)">\s*<summary><small>LEAGUE',
                      markup)
    return found.group(1) if found else None


def season_scope(markup):
    """The season an All-Stars board shows -- its season picker's scope, e.g. 'monday-fall-2026'."""
    found = re.search(r'<details class="picker" data-scope="([^"]+)">\s*<summary><small>SEASON',
                      markup)
    return found.group(1) if found else None


def current_season_key(standings, night):
    """The season key of a night's current season, read off its standings' status bar
    ('FALL 2026 · MONDAY' -> 'monday-fall-2026'), so boards and team pages can be matched up."""
    for markup in standings.values():
        if night_of(markup) == night:
            bar = re.search(r'<div class="statusbar"><b>(.*?) · ', markup)
            if bar:
                return re.sub(r"[^a-z0-9]+", "-", f"{night} {bar.group(1)}".lower()).strip("-")
    return None


def points_on_page(page, fragment=None, all_time=False):
    """The total a player page shows: the ALL STAR POINTS card of the All Time section (`all_time`,
    on a page that has one -- multi-season pages do), of the season section at `fragment`, or of
    the page's first season. That first season is NOT the first card on a multi-season page: the
    All Time section sits above it (2026-11-12), and a link with no fragment means the first
    season."""
    if all_time and f'id="{ALL_TIME_ID}"' in page:
        start = page.find(f'id="{ALL_TIME_ID}"')
    elif fragment:
        start = page.find(f'id="{fragment}"')
        if start < 0:
            return None
    else:
        first = re.search(rf'<div class="headline" id="(?!{ALL_TIME_ID}")', page)
        start = first.start() if first else 0
    found = re.search(r'<h2>ALL STAR POINTS</h2>.*?<b class="num">([\d,]+)</b>',
                      page[start:], re.S)
    return int(found.group(1).replace(",", "")) if found else None


def check_season_history(pages):
    """The All-Stars season picker (2026-11-12): every season of both nights, and All Time."""
    print("\n13. All-Stars season history -- the picker, every season's boards, All Time")
    site = {name.replace("\\", "/"): markup for name, markup in pages.items()}
    boards = all_stars_boards(site)
    check(f"found {len(boards)} All-Stars boards, All Time among them",
          "all-stars-all-time.html" in boards and len(boards) > 7)

    # ---- the picker: one per board, a real link per season, the current one the page itself ----
    lists, wrong = set(), []
    for name in sorted(boards):
        markup = site[name]
        pickers = re.findall(r'<details class="picker"[^>]*>(.*?)</details>', markup, re.S)
        if len(pickers) != 1:
            wrong.append(f"{name}: {len(pickers)} pickers")
            continue
        nav = re.search(r'<nav aria-label="Season">(.*?)</nav>', pickers[0], re.S)
        shown = re.search(r"<summary><small>SEASON</small><b>(.*?)</b>", pickers[0])
        options = re.findall(r'<a href="([^"]+)"( aria-current="page")?>(.*?)</a>',
                             nav.group(1)) if nav else []
        current = [(href, text) for href, mark, text in options if mark]
        if not shown or len(current) != 1:
            wrong.append(f"{name}: {len(current)} current options")
            continue
        href, text = current[0]
        if site.get(href) != markup:
            wrong.append(f"{name}: its current option opens {href}")
        if shown.group(1) != text:
            wrong.append(f"{name}: shows {shown.group(1)!r} but marks {text!r}")
        lists.add(tuple(t for _h, _m, t in options))
    check(f"all {len(boards)} boards have one season picker whose current option is the page",
          not wrong, str(wrong[:3]))
    seasons = next(iter(lists)) if len(lists) == 1 else ()
    check("every board's picker lists the same seasons, All Time first",
          len(lists) == 1 and len(seasons) >= 3 and seasons[0] == "All Time",
          f"{len(lists)} different lists")
    home = re.search(r'<a href="[^"]+" aria-current="page">(.*?)</a>', site.get("index.html", ""))
    check("the home page is the picker's first Tuesday season",
          bool(home) and len(seasons) > 1 and home.group(1) == seasons[1] and "Tuesday" in seasons[1],
          home.group(1) if home else "no picker")
    if len(seasons) > 1:
        real = seasons[1:]
        nights = [("Tuesday" if "Tuesday" in s else "Monday") for s in real]
        labels = [_html.unescape(s).split(" · ")[0].strip() for s in real]
        contiguous = True
        for i in range(1, len(labels)):
            if labels[i] == labels[i - 1] and nights[i] == "Tuesday" and nights[i - 1] == "Monday":
                contiguous = False
        check("the picker runs season by season, Tuesday before Monday",
              contiguous, str(list(zip(labels, nights))))

    # ---- every board that ranks across divisions crowns nobody (CLAUDE.md non-negotiable 3) ----
    known = {_html.unescape(re.search(r"<h1>(.*?)</h1>", site[n]).group(1)).lower()
             for n, kind in boards.items() if kind == "division"}
    for name, kind in sorted(boards.items()):
        if kind == "division":
            continue
        board = site[name]
        rows = re.findall(r'<a class="row".*?</a>', board, re.S)
        problems = []
        if not rows:
            problems.append("no rows")
        if 'class="leader"' in board or re.search(r'class="row-rank[^"]*\btop\b', board):
            problems.append("crowns someone")
        ranks = [int(n) for n in re.findall(r'<span class="row-rank[^"]*">(\d+)</span>', board)]
        if ranks != list(range(1, len(rows) + 1)):
            problems.append("not numbered 1..N")
        points = [int(p.replace(",", "")) for p in
                  re.findall(r'<span class="row-pts">\s*<b class="num">([\d,]+)</b>', board)]
        if len(points) != len(rows) or points != sorted(points, reverse=True):
            problems.append("not highest points first")
        unnamed = [r for r in rows
                   if not (where := re.search(r'<small class="name">(.*?) &middot; ', r))
                   or _html.unescape(where.group(1)).lower() not in known]
        if unnamed:
            problems.append(f"{len(unnamed)} rows without a known division")
        if "says as much about a player&rsquo;s division" not in board:
            problems.append("no warning that a rank reflects the division")
        check(f"{name} crowns nobody, runs 1..N highest first, names every row's division",
              not problems, "; ".join(problems))

    # ---- a link into a page section lands on it, and every number matches its page ----
    unresolved = []
    for name, markup in site.items():
        here = (OUT / name).parent
        for path, fragment in re.findall(r'href="([^"#:]+\.html)#([^"]+)"', markup):
            target = (here / path).resolve().relative_to(OUT.resolve()).as_posix()
            if f'id="{fragment}"' not in site.get(target, ""):
                unresolved.append(f"{name} -> {path}#{fragment}")
    check("every #fragment link lands on an element with that id", not unresolved,
          str(unresolved[:3]))

    mismatched, compared = [], 0
    for name, kind in boards.items():
        for href, shown in re.findall(r'<a class="(?:row|leader)" href="(player/[^"]+)"[^>]*>'
                                      r'.*?<b class="num">([\d,]+)</b>', site[name], re.S):
            path, _hash, fragment = href.partition("#")
            got = points_on_page(site.get(path, ""), fragment or None, all_time=kind == "all-time")
            compared += 1
            if got != int(shown.replace(",", "")):
                mismatched.append(f"{name}: {href} shows {shown}, the page says {got}")
    check(f"all {compared} board rows show the same total as the player's own page",
          compared and not mismatched, str(mismatched[:3]))

    # ---- one page per player, every one of them on the All Time list exactly once ----
    listed = collections.Counter(re.findall(r'<a class="row" href="(player/[^"#]+\.html)',
                                            site.get("all-stars-all-time.html", "")))
    player_pages = {n for n in site if n.startswith("player/")}
    check(f"all {len(player_pages)} player pages are on the All Time list, each exactly once",
          set(listed) == player_pages and all(c == 1 for c in listed.values()),
          f"{len(player_pages - set(listed))} missing, "
          f"{sum(1 for c in listed.values() if c > 1)} twice")


# ---------------------------------------------------------------- 14. both nights

def awards_pages(site):
    """Every Awards page: awards.html, awards-monday.html, and every award/*.html."""
    return {n: m for n, m in site.items()
            if re.fullmatch(r"awards(-[a-z]+)?\.html", n) or n.startswith("award/")}


def check_both_nights(pages):
    """Standings, the Schedule and Awards per night, each with a league picker; the Feed groups
    cards under night headings (owner, 2026-11-12)."""
    print("\n14. Both nights -- the league picker on Standings, Schedule and Awards; the Feed")
    site = {name.replace("\\", "/"): markup for name, markup in pages.items()}
    standings, schedules = standings_pages(site), schedule_pages(site)
    awards = awards_pages(site)

    # ---- the league picker: Standings, Schedule and Awards indexes each have one ----
    chosen = {**standings, **schedules}
    awards_indexes = {n: m for n, m in awards.items() if not n.startswith("award/")}
    all_with_picker = {**chosen, **awards_indexes}
    lists, wrong = set(), []
    for name, page in sorted(all_with_picker.items()):
        pickers = re.findall(r'<details class="picker"[^>]*>(.*?)</details>', page, re.S)
        league_pickers = [p for p in pickers
                          if re.search(r'<summary><small>LEAGUE', p)]
        if len(league_pickers) != 1:
            wrong.append(f"{name}: {len(league_pickers)} league pickers")
            continue
        picker = league_pickers[0]
        nav = re.search(r'<nav aria-label="League">(.*?)</nav>', picker, re.S)
        shown = re.search(r"<summary><small>LEAGUE</small><b>(.*?)</b>", picker)
        options = re.findall(r'<a href="([^"]+)"( aria-current="page")?>(.*?)</a>',
                             nav.group(1)) if nav else []
        current = [(href, text) for href, mark, text in options if mark]
        if not shown or len(current) != 1:
            wrong.append(f"{name}: {len(current)} current options")
            continue
        href, text = current[0]
        resolved = (pathlib.Path(name).parent / href).as_posix()
        if site.get(resolved) != page and site.get(href) != page:
            wrong.append(f"{name}: its current option opens {href}")
        lists.add(tuple(t for _h, _m, t in options))
    check(f"all {len(all_with_picker)} Standings, Schedule and Awards pages have a league picker "
          "whose current option is the page", not wrong, str(wrong[:3]))
    nights = next(iter(lists)) if len(lists) == 1 else ()
    check("every league picker offers the same nights, Tuesday first",
          len(lists) == 1 and len(nights) >= 2 and nights[0] == "Tuesday night", str(lists))
    check("the Standings, Schedule and Awards tabs open Tuesday's",
          night_of(site.get("standings.html", "")) == "tuesday"
          and night_of(site.get("schedule.html", "")) == "tuesday"
          and "awards.html" in site)

    # ---- award detail pages each have a league picker ----
    detail_pages = {n: m for n, m in awards.items() if n.startswith("award/")}
    wrong_detail = []
    for name, markup in sorted(detail_pages.items()):
        league_pickers = [p for p in re.findall(r'<details class="picker"[^>]*>(.*?)</details>',
                                                 markup, re.S)
                          if re.search(r'<summary><small>LEAGUE', p)]
        if len(league_pickers) != 1:
            wrong_detail.append(f"{name}: {len(league_pickers)} league pickers")
    check(f"all {len(detail_pages)} award detail pages have a league picker",
          not wrong_detail, str(wrong_detail[:3]))

    # ---- a night's Standings and Schedule only ever link that night's teams ----
    team_night = {}
    for name in (n for n in site if n.startswith("team/")):
        back = re.search(r'<a class="back" href="\.\./(standings[^"]*\.html)"', site[name])
        team_night[name] = night_of(standings.get(back.group(1), "")) if back else None
    crossed = [f"{name} -> {href}" for name, page in chosen.items()
               for href in re.findall(r'href="(team/[^"]+\.html)"', page)
               if team_night.get(href) != night_of(page)]
    check("every team a Standings or Schedule page links plays on that page's night",
          not crossed, str(crossed[:3]))

    # ---- the Feed: grouped by night, every card under a heading ----
    feed = site.get("feed.html", "")
    night_names = re.findall(r'<h2 class="section">(TUESDAY|MONDAY) NIGHT', feed)
    check("the Feed has night headings", bool(night_names))
    check("both nights appear in the Feed",
          "TUESDAY" in night_names and "MONDAY" in night_names, str(set(night_names)))
    full_headings = re.findall(r'<h2 class="section">([^<]+)</h2>', feed)
    dup_headings = [full_headings[i] for i in range(1, len(full_headings))
                    if full_headings[i] == full_headings[i - 1]]
    check("no repeated Feed heading", not dup_headings, str(dup_headings[:3]))


# ---------------------------------------------------------------- 15. player pages

# What a player page is made of, in page order: the All Time heading (A) or a season's (S), a
# darts card (D), an ALL STAR POINTS card (P), and a hit list's heading (H).
PLAYER_PARTS = re.compile(r'<div class="headline" id="(?P<id>[^"]+)">'
                          r'|<h2>(?P<darts>THE DARTS &middot; SINGLES[^<]*)</h2>'
                          r'|<h2>(?P<points>ALL STAR POINTS)</h2>'
                          r'|<h2 class="section">THE (?P<hits>\d+) HITS?</h2>')


def darts_cards(page):
    """[(title, [(value, label)], body)] for every darts card on a player page, in page order."""
    cards = []
    for title, body in re.findall(r'<h2>(THE DARTS &middot; SINGLES[^<]*)</h2>(.*?)\n  </div>\n',
                                  page, re.S):
        stats = re.findall(r'<b class="num">([^<]*)</b><small>([^<]*)</small>', body)
        cards.append((title, stats, body))
    return cards


def figure(value):
    """A darts-card figure as a number -- None for the em dash."""
    value = _html.unescape(value).rstrip("%")
    return None if value == "—" else float(value)


def check_player_pages(pages):
    """The player page (owner, 2026-11-12): an All Time section with the singles averages and the
    points over the seasons the page shows; every season with its own averages; the THIS SEASON
    card gone; and a season's top three hits, the rest folded into a <details>."""
    print("\n15. Player pages -- All Time, every season's averages, the top three hits")
    site = {name.replace("\\", "/"): markup for name, markup in pages.items()}
    player_pages = {n: m for n, m in site.items() if n.startswith("player/")}
    check("found the player pages", len(player_pages) > 100, str(len(player_pages)))

    misshapen, stale, bad_darts, bad_caption, outside = [], [], [], [], []
    bad_fold, unsorted = [], []
    cards = lists = folds = compared = 0
    for name, page in sorted(player_pages.items()):
        # ---- shape: All Time (two or more seasons) then every season, each complete ----
        seq = "".join("A" if m["id"] == ALL_TIME_ID else "S" if m["id"] else
                      "D" if m["darts"] else "P" if m["points"] else "H"
                      for m in PLAYER_PARTS.finditer(page))
        top = re.search(rf'id="{ALL_TIME_ID}"><span>\s*<h2 class="section">ALL TIME &middot; '
                        r'(\d+) SEASONS</h2>', page)
        if not re.fullmatch(r"ADP(?:SDPH){2,}|S?DPH", seq) \
                or bool(top) != seq.startswith("A") \
                or (top and int(top.group(1)) != seq.count("H")):
            misshapen.append(f"{name}: {seq}")

        # ---- the retired card: MATCHES, LEGS, DARTS ----
        if re.search(r"<h2>TH(?:IS|E) SEASON</h2>|<small>(?:MATCHES|LEGS|DARTS)</small>", page):
            stale.append(name)

        # ---- every darts card: the six figures in order, or a line saying there are none ----
        found = darts_cards(page)
        cards += len(found)
        for title, stats, body in found:
            if stats and [label for _value, label in stats] != DARTS_LABELS \
                    or not stats and NO_SINGLES not in body:
                bad_darts.append(f"{name}: {_html.unescape(title)}")
        # The averages are explained once, on the first card with figures to explain.
        with_figures = [body for _title, stats, body in found if stats]
        if page.count(SINGLES_NOTE) != (1 if with_figures else 0) \
                or with_figures and SINGLES_NOTE not in with_figures[0]:
            bad_caption.append(name)

        # ---- All Time adds up the seasons below, so each of its figures lies between theirs ----
        # Not LEG WINS: it counts legs of every format (players.form_sums), so a season whose card
        # shows no singles figures -- and so no LEG WINS -- still adds its legs to All Time's.
        if seq.startswith("A") and found:
            (_t, career, _b), seasons = found[0], found[1:]
            for i, label in enumerate(DARTS_LABELS):
                if label == "LEG WINS":
                    continue
                values = [figure(stats[i][0]) for _t, stats, _b in seasons if stats]
                values = [v for v in values if v is not None]
                mine = figure(career[i][0]) if career else None
                compared += 1
                if (mine is None) != (not values) \
                        or values and not min(values) <= mine <= max(values):
                    outside.append(f"{name}: {label} {mine} vs seasons {values}")

        # ---- every hit list: the top three, the rest in one fold that counts them right ----
        for total, body in re.findall(r'<h2 class="section">THE (\d+) HITS?</h2>.*?</div>\n'
                                      r'(.*?)(?=<div class="headline"|<nav aria-label="Sections")',
                                      page, re.S):
            lists += 1
            total = int(total)
            shown, fold, rest = body.partition('<details class="more-hits">')
            more = re.fullmatch(r'\s*<summary>(\d+) MORE HIT(S?)<svg[^>]*>.*?</svg></summary>\n'
                                r'(.*)</details>\s*', rest, re.S)
            inside = more.group(3).count('<div class="hit">') if more else 0
            folds += bool(fold)
            if shown.count('<div class="hit">') != min(total, TOP_HITS) \
                    or bool(fold) != (total > TOP_HITS) \
                    or fold and not (more and int(more.group(1)) == inside == total - TOP_HITS
                                     and (more.group(2) == "S") == (inside != 1)):
                bad_fold.append(f"{name}: THE {total} HITS")
            values = [int(v) for v in re.findall(r'<span class="hit-val num">(\d+)</span>', body)]
            if len(values) != total or values != sorted(values, reverse=True):
                unsorted.append(f"{name}: {values[:6]}")

    check("every player page is All Time (two or more seasons) then each season, and each part "
          "has its averages, its points and its hits", not misshapen, str(misshapen[:3]))
    check("no player page keeps the retired THIS SEASON card (MATCHES, LEGS, DARTS)", not stale,
          str(stale[:3]))
    check(f"all {cards} darts cards show the six singles figures in order, or say there are no "
          "singles legs", cards and not bad_darts, str(bad_darts[:3]))
    check("the averages are explained once per page, on its first darts card with figures",
          not bad_caption, str(bad_caption[:3]))
    check(f"all {compared} All Time figures lie between the lowest and highest of the seasons "
          "the page shows", compared and not outside, str(outside[:3]))
    check(f"all {lists} hit lists show their top {TOP_HITS}, and the {folds} with more fold the "
          "rest into one <details> whose count is right", lists and folds and not bad_fold,
          str(bad_fold[:3]))
    check("every hit list runs most points first, every hit present", not unsorted,
          str(unsorted[:3]))


# ---------------------------------------------------------------- 16. wider screens

# The phone layout is the stylesheet's base layer. From this width up, @media rules may only add
# to it (owner, 2026-11-13). Restated rather than imported from tokens.py: this suite judges the
# output, not the code.
WIDE_FROM = 768


def check_wide_screens(pages, css):
    print(f"\n16. Wider screens -- phones keep the base layout; rules from {WIDE_FROM}px only add")
    plain = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    others = sorted(set(re.findall(r"@(?!media\b)[a-zA-Z-]+", plain)))
    check("the stylesheet's only at-rule is @media", not others,
          f"{others} -- css_layers() reads @media alone; teach it before using another")

    blocks = [(condition, text) for condition, text in css_layers(css) if condition is not None]
    check("found the wider-screen @media blocks", bool(blocks), "none -- the desktop layout is gone")
    nested = [condition for condition, text in blocks if "@" in text]
    check("no @media sits inside another", not nested, str(nested))

    # A max-width query, or a min-width under 768, would reach a phone: the one thing this layer
    # must never do.
    narrow = []
    for condition, _text in blocks:
        found = re.fullmatch(r"\(min-width:\s*(\d+)px\)", condition)
        if not found or int(found.group(1)) < WIDE_FROM:
            narrow.append(condition)
    check(f"every @media is a min-width of {WIDE_FROM}px or more, so no phone sees it",
          not narrow, str(narrow))

    bar = {}
    for selector, decls in phone_rules(css):
        if selector == ".tabs":
            bar.update(decls)
    check("on a phone the tab bar is fixed to the bottom of the screen",
          bar.get("position") == "fixed" and bar.get("bottom") == "0", str(bar))

    # The wide layout lifts the tab bar into the header's row with a grid on .app, so the bar must
    # be a child of .app. It must also come after the content: section 15 reads each hit list up to
    # the Sections nav.
    misplaced = [n for n, m in pages.items()
                 if not re.search(r'<nav aria-label="Sections" class="tabs">.*?</nav>\s*</div>\s*'
                                  r'</body>\s*</html>\s*$', m, re.S)]
    check(f"on all {len(pages)} pages the Sections nav is the last thing in .app", not misplaced,
          f"{len(misplaced)} pages, e.g. {misplaced[:3]}")


# ---------------------------------------------------------------- main

def main():
    if not OUT.is_dir():
        print(f"\n  no build found at {OUT} -- run python3 site/build.py first")
        return 1

    check_formula()
    if failures:
        print("\n  the contrast formula itself is wrong -- refusing to report contrast results")
        print(f"\n{len(failures)} CHECK(S) FAILED")
        return 2

    pages = read_pages()
    css_path = OUT / "app.css"
    if not css_path.is_file():
        print(f"\n  no stylesheet at {css_path}")
        return 1
    css = css_path.read_text(encoding="utf-8")
    print(f"\n  {len(pages)} pages, {len(css.splitlines())} lines of CSS")

    check_links(pages)
    check_leakage(pages)
    check_colour(pages, css)
    check_fonts(pages, css)
    check_structure(pages)
    check_tap_targets(pages, css)
    check_names(pages)
    check_names_css(css)
    check_numerals(pages)
    check_spec_rules(pages, css)
    check_navigation(pages)
    check_schedule(pages)
    check_season_history(pages)
    check_both_nights(pages)
    check_player_pages(pages)
    check_wide_screens(pages, css)

    print(f"\n{'ALL CHECKS PASSED' if not failures else str(len(failures)) + ' CHECK(S) FAILED'}")
    if failures:
        for name in failures:
            print(f"  - {name}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
