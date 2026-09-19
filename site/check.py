"""Output verification suite. Run after a build: python3 site/check.py

scraper/verify.py asserts the DATA is right -- totals, team mapping, scoring rules.
This file asserts the SITE is right: the HTML and CSS that actually reach a phone.

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


def css_rules(css):
    """(selector, {prop: value}) for every selector in a flat stylesheet."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        decls = {}
        for decl in match.group(2).split(";"):
            if ":" in decl:
                prop, value = decl.split(":", 1)
                decls[prop.strip().lower()] = value.strip()
        for selector in match.group(1).split(","):
            yield " ".join(selector.split()), decls


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

    # Every file shipped should be reachable. DESIGN-SPEC ("The logo") says the reversed
    # wordmark is used once, at the foot of the rare-hit screen -- if it ships unreferenced,
    # either that screen lost it or the asset should not be copied.
    everything = "".join(pages.values())
    orphans = [str(p.relative_to(OUT)) for p in OUT.rglob("*")
               if p.is_file() and p.suffix in (".png", ".jpg", ".svg", ".css", ".js")
               and p.name not in everything]
    check("no unreferenced asset shipped", not orphans, str(orphans))
    if "rare-hit.html" in pages:
        check("rare-hit screen shows the reversed wordmark (DESIGN-SPEC)",
              "psdl-wordmark-white.png" in pages["rare-hit.html"], "not referenced")


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

    if re.search(r"@(media|supports|container)", css):
        # The rule parser is flat. An at-rule block would silently swallow its contents and
        # every colour inside it would go unchecked, so refuse rather than under-report.
        print("\n3. Contrast")
        check("stylesheet has no at-rule blocks the parser cannot see", False,
              "@media/@supports found -- css_rules() must learn to descend before trusting this suite")
        return

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

    backgrounds = {}
    for selector, decls in rules:
        raw = decls.get("background-color") or decls.get("background")
        if not raw:
            continue
        colour = resolve_var(raw.split()[0], variables)
        if colour.startswith("#"):
            backgrounds[strip_pseudo(selector).strip()] = normalise_hex(colour)

    def background_for(selector):
        """Nearest declared background walking up the selector's own ancestor prefix."""
        parts = strip_pseudo(selector).split()
        for cut in range(len(parts), 0, -1):
            prefix = " ".join(parts[:cut])
            if prefix in backgrounds:
                return [backgrounds[prefix]], prefix
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

    # Inline colours in the markup (the rare-hit screen sets a few). They sit inside .app, so
    # they are judged against the same arbitrary-content panels.
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
          any(sel == ".num" and decls.get("font-variant-numeric") == "tabular-nums"
              for sel, decls in css_rules(css)))


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
        for tag in re.findall(r"<(?:a|button)\b[^>]*>", markup):
            found = re.search(r'class="([^"]*)"', tag)
            if found:
                tappable.update(found.group(1).split())
    check("found the tappable classes in the output", bool(tappable), "none found")

    def targets_control(selector):
        parts = strip_pseudo(selector).split()
        if not parts:
            return False
        last = parts[-1]
        if re.fullmatch(r"(a|button|input)(\[[^\]]*\])*", last):
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

    # A row with no height at all must at least floor itself.
    rows = {sel: d for sel, d in css_rules(css) if sel in (".row", ".hit")}
    for selector, decls in rows.items():
        floor = decls.get("min-height", "")
        check(f"{selector} declares a min-height >= {MIN_TAP}px",
              bool(re.fullmatch(r"(\d+)px", floor)) and int(floor[:-2]) >= MIN_TAP,
              f"min-height:{floor or 'unset'}")

    check("tab bar is the 64px the spec asks for",
          any(sel == ".tabs a" and decls.get("height") == "64px"
              for sel, decls in css_rules(css)))

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
    rules = {sel: d for sel, d in css_rules(css)}
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
    rules = {sel: d for sel, d in css_rules(css)}
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
    boards = [n for n in pages if re.fullmatch(r"index\.html|division-\d\.html", n)]
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

    print(f"\n{'ALL CHECKS PASSED' if not failures else str(len(failures)) + ' CHECK(S) FAILED'}")
    if failures:
        for name in failures:
            print(f"  - {name}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
