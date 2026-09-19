"""The design system, from DESIGN-SPEC.md.

The mockups carry these values as inline styles on every element. Here they exist once, as
CSS custom properties, so a colour can be changed in one place.

DO NOT introduce a colour that is not in this file. The palette is three colours sampled from
the league logo -- black, gold, white -- plus shades of the black. The muted grey and the
on-gold brown both sit at the 4.5:1 AA floor; lightening either breaks contrast.
"""

COLOURS = {
    "black":      "#211C1D",  # the logo's own black; text on gold fills
    "gold":       "#C59940",  # the logo's gold; accents, the current thing, rare hits
    "white":      "#FFFFFF",  # primary text, the logo plate
    "ground":     "#141112",  # page background
    "surface":    "#201B1C",  # cards, header, tab bar
    # Used by the mockups for the status strip, but missing from the DESIGN-SPEC table.
    # Named here so no raw hex appears in the stylesheet.
    "sunken":     "#1A1617",  # status strip under the header
    "raised":     "#2B2526",  # chips, code badges
    "hairline":   "#332C2E",  # borders on controls
    "rule":       "#241F20",  # list separators
    "edge":       "#3A3234",  # header / tab bar edges
    "text":       "#FFFFFF",
    "text2":      "#A6A2A3",  # supporting lines
    "muted":      "#8E8889",  # labels, captions -- AA floor, do not lighten
    "chip_text":  "#E4E0E1",  # text on raised
    # The spec lists #4A3A16 as 4.7:1 on gold, but it measures 4.20:1 -- below the 4.5 AA
    # floor for small text, and it is used on the 8px "DIV" label of the selected division
    # chip. #443112 is the same brown a shade darker and genuinely reaches 4.73:1.
    "on_gold":    "#443112",  # small text on a gold fill (4.73:1, verified)
}

FONTS_HREF = ("https://fonts.googleapis.com/css2?"
              "family=Anton&family=Archivo:wght@400;500;600;700&display=swap")

DISPLAY = "'Anton', 'Oswald', sans-serif"        # titles, rank numerals, every large number
BODY    = "'Archivo', 'Helvetica Neue', sans-serif"


def stylesheet():
    """One stylesheet for every page."""
    c = COLOURS
    return f"""
:root {{
  --black:{c['black']}; --gold:{c['gold']}; --white:{c['white']};
  --ground:{c['ground']}; --surface:{c['surface']}; --raised:{c['raised']};
  --hairline:{c['hairline']}; --rule:{c['rule']}; --edge:{c['edge']}; --sunken:{c['sunken']};
  --text:{c['text']}; --text2:{c['text2']}; --muted:{c['muted']};
  --chip-text:{c['chip_text']}; --on-gold:{c['on_gold']};
  --display:{DISPLAY}; --body:{BODY};
}}

* {{ box-sizing: border-box; }}

/* .row and .leader are flex, and display:flex overrides the hidden attribute.
   Without this, search-filtered rows would stay on screen. */
[hidden] {{ display: none !important; }}

html {{ background: var(--ground); }}

body {{
  margin: 0;
  background: var(--ground);
  font-family: var(--body);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
  -webkit-text-size-adjust: 100%;
}}

/* The mockups are fixed 390px artboards. A real phone is 320-430px, so the app is a fluid
   column that fills the device and centres on anything wider. */
.app {{
  max-width: 430px;
  margin: 0 auto;
  min-height: 100vh;
  background: var(--ground);
  display: flex;
  flex-direction: column;
  padding-bottom: calc(64px + env(safe-area-inset-bottom));
}}

a {{ color: var(--gold); text-decoration: none; }}
a:hover {{ color: var(--white); }}

.num {{ font-variant-numeric: tabular-nums; }}
.display {{ font-family: var(--display); font-weight: 400; letter-spacing: 0.02em; }}

/* Names arrive from DartConnect with real double spaces (Colin  Ratner). components.esc()
   encodes those as &nbsp; so HTML cannot collapse them.
   Deliberately NOT white-space: pre-wrap -- that would also render the source indentation
   inside a multi-line .name element as visible leading whitespace.
   Wrap rather than truncate: an ambiguous name is worse than a tall row. */
.name {{ overflow-wrap: anywhere; text-wrap: pretty; }}

.vh {{ position: absolute; width: 1px; height: 1px; overflow: hidden;
      clip: rect(0 0 0 0); white-space: nowrap; }}

/* ---------- header ---------- */
.hdr {{
  display: flex; align-items: center; gap: 12px; padding: 16px;
  background: var(--surface); border-bottom: 1px solid var(--edge);
}}
.hdr-plate {{
  width: 42px; height: 42px; border-radius: 50%; background: var(--white);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}}
.hdr-plate img {{ width: 36px; height: 36px; object-fit: contain; display: block; }}
.hdr-txt {{ display: flex; flex-direction: column; gap: 3px; min-width: 0; }}
.eyebrow {{ font-size: 9px; font-weight: 700; letter-spacing: 0.16em; color: var(--gold); }}
.hdr-title {{ font-family: var(--display); font-size: 23px; line-height: 1;
             letter-spacing: 0.02em; color: var(--white); }}

.statusbar {{
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 9px 16px; background: var(--sunken); border-bottom: 1px solid var(--raised);
}}
.statusbar b {{ font-size: 11px; font-weight: 700; letter-spacing: 0.1em; color: var(--white); }}
.statusbar span {{ font-size: 10px; font-weight: 600; letter-spacing: 0.08em; color: var(--gold); }}

/* ---------- division switcher ---------- */
.divnav {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr));
          gap: 6px; padding: 14px 16px 10px; }}
.divnav a {{
  height: 52px; border-radius: 8px; background: var(--surface);
  border: 1px solid var(--hairline); display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: 1px;
}}
.divnav a small {{ font-size: 8px; font-weight: 700; letter-spacing: 0.14em; color: var(--muted); }}
.divnav a b {{ font-family: var(--display); font-weight: 400; font-size: 21px;
              line-height: 1; color: var(--chip-text); }}
.divnav a[aria-current] {{ background: var(--gold); border-color: var(--gold); }}
.divnav a[aria-current] small {{ color: var(--on-gold); }}
.divnav a[aria-current] b {{ color: var(--black); }}

/* ---------- section heading ---------- */
.headline {{ display: flex; align-items: flex-end; justify-content: space-between;
            gap: 12px; padding: 6px 16px 12px; }}
.headline h1, .headline h2 {{ font-family: var(--display); font-weight: 400; font-size: 30px;
               line-height: 1; margin: 0 0 3px; color: var(--white); }}
/* Section headings sit under the page's one h1 -- same family, quieter size. */
.headline h2.section {{ font-size: 20px; }}
.headline p {{ margin: 0; font-size: 12px; font-weight: 500; color: var(--text2); }}
.headline .note {{ flex-shrink: 0; text-align: right; font-size: 10px; font-weight: 700;
                  letter-spacing: 0.06em; color: var(--gold); line-height: 1.4; }}

/* ---------- search ---------- */
.search {{
  display: flex; align-items: center; gap: 9px; margin: 0 16px 14px;
  padding: 0 12px; height: 46px; background: var(--surface);
  border: 1px solid var(--hairline); border-radius: 9px;
}}
.search input {{
  flex-grow: 1; min-width: 0; background: transparent; border: 0; outline: none;
  color: var(--white); font-family: var(--body); font-size: 15px;
}}
.search input::placeholder {{ color: var(--muted); }}

/* ---------- hit chips ---------- */
.chips {{ display: flex; flex-wrap: wrap; gap: 5px; }}
.chip {{
  padding: 4px 8px; border-radius: 4px; background: var(--raised); color: var(--chip-text);
  font-size: 11px; font-weight: 700; letter-spacing: 0.03em;
}}
.chip.rare {{ background: var(--gold); color: var(--black); }}

/* ---------- leaderboard rows ---------- */
.leader {{
  margin: 0 16px 12px; padding: 14px; background: var(--surface);
  border: 1px solid var(--gold); border-radius: 11px;
  display: flex; flex-direction: column; gap: 11px;
}}
.leader-top {{ display: flex; align-items: flex-start; gap: 12px; }}
.leader-rank {{ flex-shrink: 0; width: 30px; font-family: var(--display); font-size: 34px;
               line-height: 0.9; color: var(--gold); }}
.leader-who {{ flex-grow: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }}
.leader-who b {{ font-size: 19px; font-weight: 700; color: var(--white); line-height: 1.2; }}
.leader-who span {{ font-size: 12px; font-weight: 500; color: var(--text2); }}
.leader-pts {{ flex-shrink: 0; display: flex; flex-direction: column;
              align-items: flex-end; gap: 2px; }}
.leader-pts b {{ font-family: var(--display); font-weight: 400; font-size: 30px;
                line-height: 0.9; color: var(--white); }}
.leader-pts span {{ font-size: 10px; font-weight: 700; letter-spacing: 0.08em; color: var(--muted); }}

.row {{ display: flex; align-items: flex-start; gap: 12px; padding: 13px 16px;
       border-top: 1px solid var(--rule); min-height: 44px; }}
.row-rank {{ flex-shrink: 0; width: 26px; padding-top: 2px; font-family: var(--display);
            font-size: 21px; line-height: 1; color: var(--muted); }}
.row-rank.top {{ color: var(--gold); }}
.row-main {{ flex-grow: 1; min-width: 0; display: flex; flex-direction: column; gap: 7px; }}
.row-main b {{ font-size: 16px; font-weight: 600; color: var(--white); line-height: 1.25; }}
.row-main small {{ font-size: 11px; font-weight: 500; color: var(--text2); }}
.row-pts {{ flex-shrink: 0; display: flex; flex-direction: column; align-items: flex-end;
           gap: 3px; padding-top: 1px; }}
.row-pts b {{ font-family: var(--display); font-weight: 400; font-size: 22px;
             line-height: 1; color: var(--white); }}
.row-pts span {{ font-size: 10px; font-weight: 600; letter-spacing: 0.06em; color: var(--muted); }}

/* ---------- cards / stat grids ---------- */
.card {{ margin: 0 16px 14px; background: var(--surface); border: 1px solid var(--hairline);
        border-radius: 11px; padding: 14px; }}
.card h2 {{ margin: 0 0 12px; font-size: 10px; font-weight: 700; letter-spacing: 0.14em;
           color: var(--muted); }}
.statgrid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
.statgrid.three {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
.stat {{ display: flex; flex-direction: column; gap: 3px; }}
.stat b {{ font-family: var(--display); font-weight: 400; font-size: 26px; line-height: 1;
          color: var(--white); }}
.stat small {{ font-size: 9px; font-weight: 700; letter-spacing: 0.12em; color: var(--muted); }}

.caption {{ margin: 14px 16px 0; font-size: 11px; line-height: 1.55; color: var(--muted); }}

.btn {{
  margin: 14px 16px 0; height: 46px; border-radius: 9px; border: 1px solid var(--hairline);
  background: var(--surface); display: flex; align-items: center; justify-content: center;
  gap: 8px; font-size: 13px; font-weight: 700; letter-spacing: 0.06em; color: var(--gold);
}}

.cutline {{ display: flex; align-items: center; gap: 10px; padding: 10px 16px;
           border-top: 1px dashed var(--gold); }}
.cutline b {{ font-size: 10px; font-weight: 700; letter-spacing: 0.1em; color: var(--gold); }}
.cutline i {{ flex-grow: 1; height: 1px; background: var(--hairline); }}

/* ---------- hit list (traceability) ---------- */
.hit {{ display: flex; align-items: center; gap: 12px; padding: 12px 16px;
       border-top: 1px solid var(--rule); min-height: 44px; }}
.hit-main {{ flex-grow: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }}
.hit-main b {{ font-size: 15px; font-weight: 600; color: var(--white); }}
.hit-main small {{ font-size: 11px; color: var(--muted); }}
.hit-val {{ flex-shrink: 0; font-family: var(--display); font-weight: 400; font-size: 22px;
           color: var(--white); }}

/* ---------- tab bar ---------- */
.tabs {{
  position: fixed; bottom: 0; left: 0; right: 0; margin: 0 auto; max-width: 430px;
  display: grid; grid-template-columns: repeat(5, minmax(0, 1fr));
  background: var(--surface); border-top: 1px solid var(--edge);
  padding-bottom: env(safe-area-inset-bottom); z-index: 10;
}}
.tabs a {{ height: 64px; display: flex; flex-direction: column; align-items: center;
          justify-content: center; gap: 5px; }}
.tabs a span {{ font-size: 8.5px; font-weight: 700; letter-spacing: 0.04em; color: var(--muted); }}
.tabs a[aria-current] span {{ color: var(--gold); }}
"""
