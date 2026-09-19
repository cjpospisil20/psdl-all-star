# PSDL All Star — design spec

Mobile-first web app showing **All Star Points** for the Park Slope Dart League, plus the
league standings pulled from DartConnect. Designed for a player on a phone, in a dim bar,
on a Tuesday night, one-handed, holding a drink.

The six screens in `design/` are static HTML mockups of the intended UI. Open any of them
in a browser. They are the visual contract, not application code.

---

## Colour

Three colours, all sampled from the league logo. **Do not introduce others** without asking.

| Token | Hex | Use |
|---|---|---|
| Logo black | `#211C1D` | the logo's own black; text on gold fills |
| Gold | `#C59940` | the logo's gold; accents, the current thing, rare hits |
| White | `#FFFFFF` | primary text, the logo plate |

Everything else is a shade of the logo black or white at reduced strength:

| Token | Hex | Use |
|---|---|---|
| Ground | `#141112` | page background |
| Surface | `#201B1C` | cards, header, tab bar |
| Sunken | `#1A1617` | status strip under the header — used by the mockups, originally missing from this table |
| Surface raised | `#2B2526` | chips, code badges |
| Hairline | `#332C2E` | borders on controls |
| Row rule | `#241F20` | list separators |
| Text primary | `#FFFFFF` | names, numbers |
| Text secondary | `#A6A2A3` | supporting lines |
| Text muted | `#8E8889` | labels, captions — **do not go lighter/darker**, this is the 4.5:1 floor |
| Chip text | `#E4E0E1` | text on `#2B2526` |
| On-gold secondary | `#443112` | small text on a gold fill (4.73:1, measured) |

All text meets WCAG AA against its own background. The muted grey and the on-gold brown are
both at the edge — don't lighten them.

> **Corrected during implementation.** The on-gold brown was originally `#4A3A16`, documented as
> 4.7:1. Measured, it is **4.20:1** — under the 4.5 AA floor, and it carries the 8px `DIV` label
> on the selected division chip. `#443112` is the same brown one shade darker and measures
> **4.73:1**, which is what the original value was reaching for. Contrast is re-checked by
> `site/check.py`, which verifies its own formula against known pairs before trusting a result.

## Type

Two families, both Google Fonts:

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anton&family=Archivo:wght@400;500;600;700&display=swap">
```

- **Anton** — `'Anton', 'Oswald', sans-serif`. Display: screen titles, rank numerals, every
  large number. Chosen because it matches the compressed weight of the logo wordmark.
- **Archivo** — `'Archivo', 'Helvetica Neue', sans-serif`. Everything else. Weights 400/500/600/700.

Every numeric element carries `font-variant-numeric: tabular-nums` so columns line up.

Do not substitute Inter, Roboto or Arial.

## The logo

`design/assets/psdl-mark.png` is the crest from the league's own logo file, with the white
background knocked out. It is used **unaltered**. Because its outline and laurel are near-black,
it always sits on a **white circular plate** (42px in the main header, 32px elsewhere).

`design/assets/psdl-wordmark-white.png` is the wordmark reversed to white for dark grounds —
the original letterforms, colour flipped. Used once, at the foot of the rare-hit screen.

## Layout

- Phone frame is **390px** wide. Screens are tall and scroll; the artboards are fixed-height
  snapshots of the full scroll.
- Bottom tab bar, 5 items, 64px tall: Standings · All-Stars · Match · Team · Player.
- Every tappable target is **≥44px**.
- Icons are inline stroke SVG. No icon fonts, no emoji.
- Controls are real elements — `<a href>`, `<button>`, `<input>` + `<label>`. Keep it that way.

---

## The all-star stat vocabulary

Players talk in codes. Use their words, never database column names.

**01 games** (501/701, count down to exactly zero)

| Code | Meaning | Points |
|---|---|---|
| `95+` | a turn (3 darts) scoring 95 or more — the bread and butter | face value of the turn |
| `171+` | a turn of 171 or more | counts as its 95+ |
| `180` | three triple-20s, the maximum turn — the rarest thrill | counts as its 95+ |
| `S90` | 90+ on the turn a team *starts* the game | face value |
| `F90` | 90+ on the turn a player *finishes* | value of the checkout |

**Cricket** (hit 15–20 and bull three times each; a mark is one hit, a triple is 3 marks)

| Code | Meaning | Points | | Code | Meaning | Points |
|---|---|---|---|---|---|---|
| `R5` | 5 marks in a turn | 100 | | `C3` | 3 bullseye marks | 100 |
| `R6` | 6 marks | 120 | | `C4` | 4 | 125 |
| `R7` | 7 marks | 140 | | `C5` | 5 | 150 |
| `R8` | 8 marks | 160 | | `C6` | 6 — extremely rare | 180 |
| `R9` | 9 marks (perfect turn) | 180 | | | | |

**AS** = count of all-star hits. **PPW** = points per week (the average — season awards
effectively hinge on this, because it normalises for players who miss weeks).

### Chip styling — the one rule that carries the design

A hit chip is **gold-filled** (`#C59940` bg, `#211C1D` text) when the hit is rare, and
**grey** (`#2B2526` bg, `#E4E0E1` text) otherwise.

Rare = `R7` `R8` `R9` `C4` `C5` `C6` `171+` `180` `S90` `F90`.
Common = `95+` `R5` `R6` `C3`.

## Hard requirements

1. **Never rebuild the 29-column spreadsheet.** Measured over one real week: 68 of 104 scoring
   players had hits in exactly **one** category; the most anyone reached was four. Show a
   player's actual hits as chips, never a row of zeroes.
2. **Never compare players across divisions.** Division 1 scores ~2.5× Division 5. Rank within
   division only. Say so on screen where it could be misread.
3. **Every number is traceable.** Each hit links to the DartConnect recap of the exact turn
   behind it. This is what convinces a sceptical captain that an automated number is right.
   The mockups link to `https://recap.dartconnect.com/` as a stand-in.
4. **Rare achievements should feel like achievements** — hence the gold chips and the
   dedicated 180 screen.
5. **Names are long, quoted and inconsistently spaced** (`Anaelechi "Lay" Owunwanne`,
   `Colin  Ratner` with a double space). They come from DartConnect as-is. Never truncate to
   the point of ambiguity — wrap instead.

## Out of scope

Login/accounts, score entry (DartConnect handles that at the board), live in-match updates,
historical seasons.

## Tone

A neighbourhood pub league, not a pro broadcast. Warm, a little bit fun. Recognition is the
point — the old system's real failure was that nobody looked at it.

---

## Screens

| File | What it is |
|---|---|
| `design/standings.html` | League standings, straight from DartConnect. Division switcher, one division at a time. |
| `design/all-stars.html` | All-star points leaderboard by division. The heart of the app. |
| `design/player.html` | One player: DartConnect form stats, then all-star points and every hit. |
| `design/match.html` | One match night, both teams, every hit linking to its turn. |
| `design/team.html` | Captain's roll-up of their players. |
| `design/rare-hit.html` | The celebration screen for a 180 / R9 / C6. |

## Data in the mockups — what's real and what isn't

**Real, verified against source:**

- All-star points, players, hit codes and counts — from `data/allstar-standings.csv`
  (week 1, 104 scoring players). Division 1 has 22 on the board, Division 3 has 24.
- League standings — the Fall 2026 DartConnect table, Division 1, typed verbatim:
  PTS, MP, MW, leg differential, LW%, '01, CRK, DCM, plus the 43.56 / 1.80 division
  average and the PER-LEG-PLAYER scoring rule.
- The form stats on the player page (3DA 43.35, First 9 53.04, avg finish 20.64,
  checkout 13.1%, leg wins 60.7%, opp 3DA 41.64, against-the-darts 56.3%, and the
  2026 activity counts) — CJ's own DartConnect card.
- Individual turn values inside a player's hit list are a decomposition that sums exactly
  to that player's real total (e.g. Tom Lettieri's five 95+ turns sum to 535, plus R5 100
  and two C3 at 100 each = 835).

**Placeholders — bracketed on purpose, fill these in:**

| Placeholder | What's missing |
|---|---|
| `[TEAM NAME]`, `[OPPONENT TEAM]` | No player→team mapping exists in the CSV. Real team names are known (see standings) but not who plays for whom. |
| `[ALL STAR CUT]` | Nobody has told us how many players per division make All Star. |
| `[MPR]` | The DartConnect card supplied was the 501 SIDO one; it carries no cricket stats. |

**Known fudges, flagged:**

- The player page is in CJ's name but the all-star half (835 pts, 8 hits, 1st of 22) is
  Tom Lettieri's real week — CJ isn't in the week-1 CSV.
- The team roster on `team.html` is a plausible Division 3 group assembled from real
  players with real numbers. They may not actually be teammates.
- The match on `match.html` pairs that group against four other real Division 3 players.
  Totals are internally consistent (1,364 + 892 = 2,256 across 20 hits) but the fixture
  is invented.

## Open questions for the league

1. How many players per division make All Star? (unblocks `[ALL STAR CUT]`)
2. Team rosters — which player is on which team?
3. Cricket stats: is MPR available from the DartConnect export?
4. Season length — the brief says 10–16 weeks.
