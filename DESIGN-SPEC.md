# PSDL All Star — design spec

Mobile-first web app showing **All Star Points** for the Park Slope Dart League, plus the
league standings pulled from DartConnect. Designed for a player on a phone, in a dim bar,
on a Tuesday night, one-handed, holding a drink. Since 2026-11-13 it also opens out on a tablet
or desktop (see **Wider screens** under Layout); the phone layout is unchanged by that.

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
the original letterforms, colour flipped. Its only page, the first-180 screen, was retired on
2026-11-12, so it is kept here but not shipped (`build.SHIPPED_ASSETS`).

## Layout

- Phone frame is **390px** wide. Screens are tall and scroll; the artboards are fixed-height
  snapshots of the full scroll.
- Bottom tab bar on a phone, 5 items, 64px tall: Standings · All-Stars · Schedule · Feed · Awards.
  (Feed replaced Team on 2026-11-11; team pages open from Standings. Schedule replaced Match the
  same day, with a calendar icon.) From 768px the same five sit in the header — see below.
- Every tappable target is **≥44px**.
- Icons are inline stroke SVG. No icon fonts, no emoji.
- Controls are real elements — `<a href>`, `<button>`, `<input>` + `<label>`, `<details>` +
  `<summary>`. Keep it that way.
- **Pickers** (2026-11-12): the All-Stars **season** picker, under the status bar and above the
  division chips — All Time, then each night's seasons, newest first. It is a `<details>` menu of
  plain links styled like the search box (46px summary, surface fill, hairline border, a muted
  chevron that turns over when open; 44px options, the current one in gold). It opens in the page
  flow rather than over it, and works with JavaScript off; `app.js` only closes it on an outside
  tap or Escape. Switching season keeps the division where the other season has it. The same
  component is the **league** picker at the top of Standings and the Schedule — "Tuesday night",
  "Monday night" — one league at a time, Tuesday first.
- **More hits** (2026-11-12): a player page lists each season's top three hits, and folds the rest
  into a `<details>` whose summary reads "9 MORE HITS". The summary is styled like the show-all
  button (46px, surface fill, hairline border, gold label and a gold chevron that turns over when
  open), and the hits open in place beneath it. Every hit is still in the markup, and the fold
  opens with JavaScript off; `app.js` plays no part in it.
- **Two nights.** Awards and the Feed show both nights together, so every entry names its night
  ("Westbury Inn · Division 1 · Tuesday"). A one-division league (Monday's "PS Monday") shows no
  division chips.
- **Wider screens** (owner, 2026-11-13). The phone layout is the design. A tablet or desktop gets
  the same pages, opened out, and nothing under 768px changes:
  - **From 768px** the page stops being a 430px column. The header and status strip run edge to
    edge, and the content sits in one centred column up to 880px, lined up with the header's
    logo. The five sections move from the bottom bar to the right of the header: the same icons
    above the same labels, 80px tall, the current one gold with a 2px gold rule along the
    header's bottom edge. Stat grids run three across. Hovering a row gives it the surface fill.
    On a detail page the logo plate comes first and the back link sits beside it.
  - **From 1024px** each section's label sits beside its icon. A player's darts card and points
    card sit side by side, the Schedule runs two fixtures across under each night's heading, and
    its division filter and team search share a row. Live is still a gold border and label, never
    a fill.
  - **The markup is the same on every screen.** Only the stylesheet changes: the rules live in
    the "wider screens" section at the end of `tokens.stylesheet()`, every one inside an
    `@media (min-width: …)` of 768px or more, and `check.py` section 16 holds that. Nothing is
    built twice for a desktop.
  - **Keyboard order follows the markup**, so on a desktop Tab reaches the five sections after
    the page's own links, as on a phone. `reading-flow: grid-rows` would reorder it but is
    deliberately not used: in Chrome 157 it skips a `<summary>` inside a grid item, which would
    leave the pickers and MORE HITS unreachable by keyboard.
  - There is no desktop mockup in `design/`. The real pages at 820, 1024 and 1440px were the
    reference.

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

**AS** = count of all-star hits. **PPL** = points per leg played: a player's all star points
divided by every leg they threw a turn in — singles, doubles and triples, '01 and cricket alike
(`players.legs_played`). It replaced **PPW**, points per week, on 2026-11-13 at the owner's request;
PPW divided by the weeks a player had hit an all star in. Every page that shows PPL says once what
it is, and `check.py` fails any page that shows PPW. The rulebook still says PPW for forfeit credit
(§F.3), which stays a commissioner's calculation.

### Chip styling — the one rule that carries the design

A hit chip is **gold-filled** (`#C59940` bg, `#211C1D` text) when the hit is rare, and
**grey** (`#2B2526` bg, `#E4E0E1` text) otherwise.

Rare = `R7` `R8` `R9` `C4` `C5` `C6` `171+` `180` `S90` `F90`.
Common = `95+` `R5` `R6` `C3`.

Because a gold *fill* means a rare hit, nothing else is gold-filled. **Live** — tonight's matches
on the Schedule, from first darts to midnight — is gold the other way round: a 1px gold border on
each match card, a gold division label, and a gold `LIVE NOW` label with a gold dot. No fill, no
red, no animation.

## Hard requirements

1. **Never rebuild the 29-column spreadsheet.** Measured over one real week: 68 of 104 scoring
   players had hits in exactly **one** category; the most anyone reached was four. Show a
   player's actual hits as chips, never a row of zeroes.
2. **Never compare players across divisions.** Division 1 scores far more than Division 5. Rank
   within division only. Say so on screen where it could be misread. **Exceptions:** the Largest
   Checkout and Largest Check-In awards are league-wide by rule; the award pages note this
   explicitly. And the All-Stars **ALL** board, added at the owner's request (2026-11-11), numbers
   every player league-wide — with no leader card and no gold top three, each row naming its
   division. The same goes for each past season's ALL board and for **All Time** (2026-11-12, the
   first option of the season picker), which adds up every season of both nights: no leader card,
   no gold top three, every row naming a division, and a line saying that a rank there reflects the
   division as much as the player. All Time has no division chips — divisions change between
   seasons and players move between them. Do not quote a ratio between divisions on screen: the
   old "2.5× Division 5" caption was a week-1 figure and was removed at the owner's request
   (2026-11-12).
3. **Every number is traceable.** Each hit links to the DartConnect recap of the exact turn
   behind it. This is what convinces a sceptical captain that an automated number is right.
   The mockups link to `https://recap.dartconnect.com/` as a stand-in.
4. **Rare achievements should feel like achievements** — hence the gold chips, and the Feed and
   Awards cards that celebrate them. (A dedicated first-180 screen did this until 2026-11-12.)
5. **Names are long, quoted and inconsistently spaced** (`Anaelechi "Lay" Owunwanne`,
   `Colin  Ratner` with a double space). They come from DartConnect as-is. Never truncate to
   the point of ambiguity — wrap instead.

## Out of scope

Login/accounts, score entry (DartConnect handles that at the board), live in-match updates.
(The Schedule marks tonight's matches live from the clock; it shows no scores.) Historical
seasons came into scope on 2026-11-12, at the owner's request, as far back as DartConnect goes —
Fall 2025 — and no further: nothing is imported from anywhere else.

## Tone

A neighbourhood pub league, not a pro broadcast. Warm, a little bit fun. Recognition is the
point — the old system's real failure was that nobody looked at it.

---

## Screens

| File | What it is |
|---|---|
| `design/standings.html` | League standings, straight from DartConnect. Division switcher, one division at a time. Since 2026-11-12 a league picker above it switches between the Tuesday and Monday leagues; the mockup predates it. |
| `design/all-stars.html` | All-star points leaderboard by division. The heart of the app. Since 2026-11-12 a season picker sits above the division chips (All Time, then every season of both nights); the mockup predates it. The mockup's PPW is PPL on the site since 2026-11-13 (see the stat vocabulary); its week-1 figures are not relabelled, because 835 points is not 835 per leg. |
| `design/player.html` | One player: DartConnect form stats, then all-star points and every hit. Since 2026-11-12 one page covers every season the player has scored in, and a past season's board opens its section. A player with two or more seasons gets an ALL TIME section first: the singles averages and the points over exactly the seasons below, the averages divided once from those seasons' added-up darts and points. Then each season, newest first, has its own singles averages, its points and rank, and its top three hits, with the rest folded behind "N MORE HITS". The mockup's activity strip (MATCHES, LEGS, DARTS) is not built: the owner removed it on 2026-11-12. The mockup's PPW is PPL on the site since 2026-11-13. The All Time PPL divides by the legs of the seasons below, as the averages do. |
| `design/match.html` | **Retired 2026-11-11.** One match night, both teams, every hit linking to its turn. The Match tab became the Schedule (upcoming home v away fixtures, no all-star points), which has no mockup; `site/build.py` `build_schedule()` is its reference. |
| `design/team.html` | Captain's roll-up of their players. Opened by tapping a team on Standings; lists the whole roster with GP (league nights played) and singles averages, and a gold check mark (inline SVG, never a glyph) after the name of each playoff-eligible player. |
| `design/rare-hit.html` | **Retired 2026-11-12.** The celebration screen for the season's first 180 / R9 / C6. The owner removed it: the Feed and Awards celebrate those hits now. |

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
4. Season length — the brief says 10–16 weeks. **Answered for Fall 2026** (owner, 2026-11-11):
   15 nights in Divisions 2–5, 12 in Division 1 (14 weeks, two byes). `players.SEASON_NIGHTS`.
