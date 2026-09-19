# PSDL All Star — Mobile App Design Brief

*Self-contained brief for a design session. Everything needed to design the app is in this
file plus `allstar-standings.csv`. No other project files are required.*

---

## What this app is

A mobile-first web app showing **All Star Points** for the Park Slope Dart League — a Brooklyn
pub darts league. Certain throws of significance earn points; at season's end, each division
crowns its All Stars.

Points are currently tallied on paper, emailed to two commissioners, and hand-typed into a
spreadsheet-style website that almost nobody reads. This app replaces that. Data is now pulled
automatically from DartConnect, the scoring system used at the board.

**The app's real job is to make these numbers worth looking at.** The data already existed; it
just lived somewhere nobody went.

## Who uses it, and where

- **Players** (~200 across 31 teams) — on a phone, **in a dimly lit bar, on a Tuesday night**,
  often one-handed while holding a drink. They want: *Did that count? Where am I? Am I going to
  make All Star?*
- **Team captains** — checking their team's totals, spotting anything that looks wrong.
- **Two commissioners** — Johnny Colonna and Mike Sheehan. They need to trust it and handle the
  occasional correction.

Design for the bar, not the desk. Dark environment, thumb reach, glanceable.

## The single most important design finding

The legacy site is a **29-column spreadsheet**. Do not rebuild that.

Measured from one real week of league play (104 players who scored):

| Non-zero stat columns | Players |
|---|---|
| exactly 1 | 68 |
| 2 | 25 |
| 3 | 10 |
| 4 | 1 |

**The median player has hits in exactly ONE stat category. The maximum anyone reached was four.**
A 29-column grid is displaying overwhelmingly empty cells. Two categories carry nearly everything:

```
95+    70 players  ███████████████████████████████████
R5     47          ███████████████████████
C3     12          ██████
R6     10          █████
R7      8          ████
171+    2          █
R8 / F90 / 180   1 each
R9 / C4 / C5 / C6 / S90   0  (rare — a handful per season, but a real thrill when they land)
```

So: **show a player's actual hits, not a row of zeroes.** The rare ones (180, R9, C6, S90)
deserve celebration when they happen, not a permanently empty column.

## Scale and shape of the data

- **5 divisions**, 31 teams, ~19–24 scoring players per division per week
- **Season:** 10–16 weeks, matches on **Tuesday nights**, ~15 matches a week
- **Points per player per week:** median 195, mean 195, max 835, min 95
- Top 10 players hold only ~24% of points — **the middle of the table is genuinely competitive**,
  which is an argument for showing a player their neighbors, not just the leaders
- Division 1 scores ~2.5× Division 5, so **never compare across divisions**; rank within division

## Real sample data (use this, not lorem ipsum)

| Rank | Player | Division | PTS | AS | Hits |
|---|---|---|---|---|---|
| 1 | Tom Lettieri | Division 1 | 835 | 8 | 95+ x5, R5 x1, C3 x2 |
| 2 | Jeff Jean-Louis | Division 1 | 680 | 6 | 95+ x2, R5 x2, R7 x2 |
| 3 | Anaelechi "Lay""" Owunwanne | Division 1 | 569 | 5 | 95+ x3, R5 x1, R6 x1 |
| 4 | Ron Belfon | Division 1 | 540 | 5 | 95+ x4, R5 x1 |
| 5 | Andrew Barnes | Division 2 | 440 | 4 | 95+ x2, R5 x1, R7 x1 |
| 6 | Cam "Jiminy" Green | Division 1 | 438 | 4 | 95+ x2, R5 x1, R7 x1 |
| 7 | Patrick OSullivan | Division 1 | 400 | 4 | R5 x4 |
| 8 | Tom Sievewright | Division 1 | 380 | 3 | 95+ x2, R7 x1 |
| 9 | Mike Speciale | Division 1 | 350 | 3 | 95+ x2, R5 x1 |
| 10 | Mike Sheehan | Division 3 | 340 | 3 | 95+ x1, R5 x1, C3 x1 |
| 11 | Erian Caballero | Division 2 | 323 | 3 | 95+ x1, R5 x1, C3 x1 |
| 12 | Scott Schilling | Division 2 | 320 | 3 | 95+ x1, R5 x1, R6 x1 |
Full ranked data for all 104 players: **`allstar-standings.csv`** — attach it alongside this brief.

Note `Anaelechi "Lay""" Owunwanne` — real names come from DartConnect and include nicknames,
stray quote marks, and inconsistent spacing (`Colin  Ratner`). **Long and messy names are the
norm, not the edge case.** Design for them.

## What the stats mean

Players talk in this vocabulary — use their words, not database column names.

**01 games** (501/701 — count down from a number to exactly zero):

| Code | Means | Points |
|---|---|---|
| `95+` | A turn (3 darts) scoring 95 or more — the bread and butter | face value of the turn |
| `180` | The maximum possible turn: three triple-20s. **The rarest thrill in darts.** | counts as its 95+ |
| `171+` | A turn of 171 or more | counts as its 95+ |
| `S90` | 90+ on the turn a team *starts* the game | face value |
| `F90` | 90+ on the turn a player *finishes* — a big checkout | value of the checkout |

**Cricket** (hit numbers 15–20 and bullseye three times each). A "mark" is one hit; a triple = 3
marks. Only marks that actually count toward scoring earn points.

| Code | Means | Points | | Code | Means | Points |
|---|---|---|---|---|---|---|
| `R5` | 5 marks in a turn | 100 | | `C3` | 3 bullseye marks | 100 |
| `R6` | 6 marks | 120 | | `C4` | 4 | 125 |
| `R7` | 7 marks | 140 | | `C5` | 5 | 150 |
| `R8` | 8 marks | 160 | | `C6` | 6 — extremely rare | 180 |
| `R9` | 9 marks (perfect turn) | 180 | | | | |

Two other terms on the leaderboard: **AS** = total all-star hits (a count), **PPW** = points per
week (the average — this is what season awards effectively hinge on, since it normalizes for
players who miss weeks).

## Screens to design

1. **Division leaderboard** — the home screen. Rank, player, team, points. Must handle ~20–25
   players per division and switching between 5 divisions. Consider surfacing PPW alongside total.
2. **Player page** — the screen a player screenshots and sends to their team chat. Their points,
   division rank, team, and *their actual hits* — ideally with the standout ones (a 180, a big
   checkout) given real visual weight.
3. **Match detail** — every all-star hit from one match night. **Each entry must link back to the
   DartConnect recap of the exact turn that earned it.** This traceability is non-negotiable: it is
   what convinces a skeptical captain that an automated number is right.
4. **Team view** — a captain's roll-up of their players.

## Hard requirements

- **Mobile first.** Desktop is a nice-to-have; the phone is the product.
- **Every number must be traceable** to the DartConnect turn behind it.
- **Never compare players across divisions.** Rank within division only.
- Rare achievements should feel like achievements.
- Names are long, quoted, and inconsistently spaced — **never truncate to the point of ambiguity.**

## Explicitly out of scope

Login/accounts, score entry (DartConnect does that at the board), live in-match updates, historical
seasons, and standings/wins-losses — this app is **only** All Star Points.

## Tone

A neighborhood pub league, not a pro sports broadcast. Warm and a little bit fun. Players are
friends who throw darts on Tuesdays and enjoy giving each other grief. Recognition is the point —
the old system's real failure was that "not everyone even looks at them."
