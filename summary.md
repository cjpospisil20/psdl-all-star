# PSDL All Star Points — Project Summary

> **Living document.** Update this at the end of any working session. It is the handoff file for
> future agent sessions — read it first, before exploring the code.

**Last updated:** 2026-09-18
**Owner:** cjpospisil20@gmail.com
**Status:** Rules engine working and the mobile web app built — 165 static pages generated from
archived DartConnect data. Not yet hosted; not yet reconciled with the commissioners.

---

## What this project is

Automate All Star Points for the Park Slope Dart League (PSDL) and publish them on a PSDL-owned
dashboard, replacing 2–3 hours per week of manual commissioner data entry.

Full scope, impact numbers and timeline: **`brds/psdl-all-star-points-automation-2026-09-18.md`**.
The design contract for the app — colours, type, the stat vocabulary, the hard requirements:
**`DESIGN-SPEC.md`**, with six static mockup screens in `design/`. Project conventions: **`CLAUDE.md`**.

---

## Decisions already made — do not re-litigate these

| Decision | Detail |
|---|---|
| **Rebuild, don't integrate** | `yourleaguestats.com` is the legacy site being replaced. Do **not** pull data from it, migrate its data, or seek cooperation from whoever runs it. All its data originated in DartConnect anyway. It is referenced only as a model for column layout. |
| **DartConnect names are authoritative** | Whatever name DartConnect has is the name we use. **No** reconciliation, alias maps, or fuzzy matching against legacy names. Normalize display artifacts only (e.g. stray quoting in `Anaelechi "Lay""" Owunwanne`). |
| **No vendor relationship** | PSDL asked DartConnect for API access and was ghosted. The approach deliberately needs nothing from them. |
| **Paper sheets continue regardless** | The league runs them anyway, so parallel-running is free validation, not a cost. |
| **Owner approves and operates** | No board sign-off needed. Commissioner sign-off matters only at the reconciliation step. |
| **Go live ASAP**, mid-season Fall 2026 | Backfill of prior seasons is explicitly out of scope for launch. |

---

## How the data works

DartConnect's recap site is a **Laravel/Inertia app** — each page embeds its full match payload as
JSON in the root element's `data-page` attribute. This is *not* conventional screen scraping: there
are no CSS selectors or DOM structure to break when they restyle.

Two public, unauthenticated endpoints:

```
POST https://tv.dartconnect.com/api/league/ParkSDL/matches/25174   # schedule + dc_match_ids
GET  https://recap.dartconnect.com/games/{dc_match_id}             # full turn-by-turn detail
```

A turn record:

```json
{"name": "Josh Hollenberg", "turn_score": 125, "current_score": 219,
 "notable": 125, "color": "TON 25"}
```

### The two rules that matter most

**1. For 01 games, ignore DartConnect's `notable` flag — compute from `turn_score`.**
DartConnect flags 01 turns at **100+** ("TON"). PSDL's threshold is **95+**. Trusting their flag
silently drops every 95–99 all star in the league. `turn_score` exists on every turn, so we apply
PSDL's rules ourselves and are immune to changes in their highlighting.

**2. For cricket, do the opposite — trust `notable` completely.**
`notable` values like `5M` / `3B` are DartConnect's count of marks that **actually counted**, not
marks thrown. This exactly implements PSDL's "marks only count if they are included in the scoring"
rule, so we do not need our own open/closed state machine. Verified in both directions on real data:

- **Gerry Hernandez** threw `T19, T16` = 6 marks → flagged **`5M`**. The opponent already had a mark
  on 19, so only two of his three 19s counted.
- **CJ Pospisil** threw `T16, S15x2` = 5 marks → **not flagged at all**. His opponent closed 16
  earlier in the same round, leaving only 4 counting marks — below the threshold.

This discovery removed what had been the single largest piece of remaining build logic.

### Other data gotchas

- **Team count is 31**, and there are two wrong ways to get it. `schedule['teams']` is the filter
  dropdown (35) and includes non-competing entries (`E-Z Buttons (Denny's)`, `Farm.One`, `Lucky 7's`,
  `The H is O (Commish)`). Deriving from played matches undercounts (30) because Division 1 has 7
  teams, so somebody has a bye every week. **Use the standings competitors list** — `fetch.teams()`.
- **In doubles, a *side* gets ON once**, not each player. Crediting S90+ per player wrongly credits a
  partner's first turn. (This was a real bug, found and fixed.)
- `score_edits` exists on games — commissioners can amend scores after the fact, so processing must
  recompute rather than append.
- **Player → team comes free from the recaps.** A turn's side (`home` / `away`) *is* the player's team;
  `matchInfo.opponents[]` is in home/away order. `scraper/players.py:team_map()` does this — 174 players
  mapped from Week 1, zero appearing under two teams, every team name matching the standings list.
  No roster file needed from the league.
- **DartConnect's player-card endpoint returns 403** without a login, so form stats (3-dart average,
  first 9, MPR, leg win %, checkout %, opponent 3DA) are **recomputed from turn data** in
  `players.py:form_stats()`. Validated against DartConnect's own per-leg averages: 84 singles legs,
  mean delta 0.000.
- **`ending_marks` on a cricket side is the POINTS total, not marks.** Computing MPR from it is wrong;
  DartConnect supplies `mpr` per side directly. (Real bug, found and fixed.)
- **`darts_thrown` is only recorded for the player who checked out.** The loser never finishes
  mid-turn, so their count is exactly 3 × turns taken.
- **Averages are singles-only, deliberately.** In doubles and triples the darts and the points belong
  to the side, so there is no honest way to split them between partners — crediting the side's figures
  to each player inflates everyone. DartConnect's own card is captioned "SINGLES 501 SIDO" for the
  same reason.

---

## Scoring rules (PSDL Rulebook Fall 2025, Section F)

**01 games (501 / 701)** — points awarded at **face value** of the turn:

| Column | Rule |
|---|---|
| `95+` | Any scoring turn ≥ 95 → face value |
| `S90` | 90+ on the turn a **side** gets ON (double-in games, incl. 701 Triples) → face value |
| `F90` | 90+ checkout → value of the checkout |
| `171+` / `171+T` | Count of turns ≥ 171, and the sum of those scores — **descriptive only, no extra points** |
| `180` | Count of maximums — **descriptive only** |

**Cricket** — fixed values, read from `notable`:

| Rounds | | Corks | |
|---|---|---|---|
| R5 | 100 | C3 | 100 |
| R6 | 120 | C4 | 125 |
| R7 | 140 | C5 | 150 |
| R8 | 160 | C6 | 180 |
| R9 | 180 | | |

**Exclusions:** busts are void (§F.1). Forfeit credits are **not derivable** from DartConnect —
players on a signed forfeit sheet are credited at season end from their PPW average (§F.3). That
stays a manual commissioner input, forever.

---

## Current state of the code

Two layers, and the boundary between them matters: **`scraper/` touches the network exactly once**
(`fetch.py`), everything downstream reads only the archive on disk. So a build is offline,
reproducible, and safe to run as often as you like.

```
scraper/fetch.py       THE ONLY networked module. Season schedule + standings, and archives
                       each match recap to data/recaps/ on first fetch, never re-fetching.
scraper/allstar.py     rules engine — Section F applied to turn data. Emits INDIVIDUAL HITS;
                       totals are derived from them by aggregate(), never accumulated.
scraper/players.py     player → team from recaps; form stats recomputed from turns;
                       division_table() — the ranked all-star table, per division only.
scraper/events.py      season assembly — load_season(): one pass over the archive, attaches
                       week/date, scores everything. The single entry point the site uses.
scraper/verify.py      assertion suite. Run before publishing. All checks passing.
scraper/standings.py   the debugging view of what the site renders   (--division, --csv, --top)

site/tokens.py         design tokens from DESIGN-SPEC → one stylesheet (public/app.css)
site/components.py     shared fragments: page shell, header, tab bar, chips, icons, recap links
site/app.js            progressive enhancement only — search filter, long-table collapse.
                       Every page is complete and usable with JS off.
site/build.py          renders all six screens into public/. Offline; no network.
site/check.py          output verification — asserts the HTML and CSS are right (contrast
                       maths, structure). verify.py checks the DATA; this checks the SITE.

public/                the generated site — 165 pages. Regenerated from scratch each build
                       (the directory is deleted first, so builds stay reproducible).
design/*.html          six static mockups — the visual contract. Not application code.
design/assets/         psdl-mark.png, psdl-wordmark-white.png — copied into public/assets/
DESIGN-SPEC.md         the design contract: palette, type, stat vocabulary, hard requirements
CLAUDE.md              project conventions — read before touching site/ or scraper/
README.md              outward-facing description and local run instructions
.github/workflows/build.yml   weekly rebuild — Wed 07:00 UTC (small hours in Brooklyn,
                       hours after the last dart), with a Thursday catch-up pass

data/matches.json      season schedule (Fall 2026, season_id 25174)
data/standings.json    standings props — authoritative team list (31 teams)
data/allstar-standings.csv   latest computed standings export
data/recaps/*.json     archived match payloads — 15 matches, Week 1
docs/                  PSDL rulebook (PDF + extracted text)
docs/design-brief.md   self-contained brief for app/UI design sessions
docs/allstar-standings.csv   copy of latest standings, to attach alongside the brief
brds/                  the Business Requirements Document
```

Run it:

```bash
python3 scraper/fetch.py                                  # pull any new matches (only networked step)
python3 scraper/verify.py                                 # assertion suite — run before publishing
python3 site/build.py                                     # regenerate public/ (offline)
python3 site/check.py                                     # verify the built HTML/CSS
python3 scraper/standings.py --top 25 --csv data/out.csv  # standings in the terminal
open public/index.html                                    # look at it
```

**Verified output, Week 1 (15 matches, all 5 divisions):**
104 players scored · 189 hits · 20,326 points · 437 busts correctly excluded · 76 get-on turns
identified across 38 double-in games (exactly two per game). `verify.py` asserts all of it — the
totals baseline, that every player's hits sum to their displayed total, that no player appears on two
teams, that a bust never produces a hit, that `171+` / `180` never pay more than their face value,
that cricket values match the rulebook table, and that every hit carries a recap link.

Top of the table: `Tom Lettieri (Div 1) — 835 pts: 95+ ×5, R5 ×1, C3 ×2`.

Division split — confirms higher divisions carry more of the load:
Div 1: 7,016 · Div 3: 4,001 · Div 2: 3,960 · Div 4: 3,420 · Div 5: 2,829 *(pre-cricket-fix figures;
re-measure after any rules change).*

Players on the board per division: Div 1: 22 · Div 2: 20 · Div 3: 24 · Div 4: 19 · Div 5: 19.

**Hit mix, Week 1** — the number that shaped the whole design. 189 hits, and they are not spread
evenly: `95+` ×101, `R5` ×52, `C3` ×13, `R6` ×10, `R7` ×9, then `R8` ×1, `171+` ×1, `180` ×1,
`F90` ×1, and `S90` ×0. Two codes carry 81% of everything. This is why a 29-column grid would be
almost entirely zeroes, and why hits render as chips.

**Build output:** 165 pages — 104 player pages, 15 match pages, 30 team pages, 5 division
leaderboards + 5 standings pages (plus `index.html` / `standings.html` aliases to Division 1),
a players index, a matches index, a teams index, and the rare-hit screen. 30 team pages, not 31 —
`The Craic` (Div 1) had the Week 1 bye and has played nothing yet. Rare-hit screen currently shows
Kevin O'Brien's 180.

---

## What's next

1. **Hosting** — the deploy path is written: `.github/workflows/build.yml` publishes `public/` to
   **GitHub Pages**, gated on `verify.py` passing, and commits newly archived recaps back to the repo
   *before* verifying (the archive must survive a failed build). But **this folder is not a git repo
   yet** — nothing is pushed and nothing is live. Creating the repo and pushing is the one thing
   standing between the app and people being able to look at it.
2. **Commissioner reconciliation** — two commissioners hand-score 3 matches (one per division tier)
   against system output. This is the gate before automated numbers become official. The match pages
   are built for exactly this: every hit links to its DartConnect recap, naming set and game.
3. **Scheduled runs** — **done**, in `.github/workflows/build.yml`: Wednesday 07:00 UTC with a
   Thursday catch-up, since GitHub sometimes drops scheduled runs and `fetch.py` skips anything
   already archived. The order is `fetch.py` → `verify.py` → `build.py` → `check.py`; run it in that
   order by hand too, and never publish a build whose verify failed. Note the workflow does **not**
   yet run `site/check.py` — worth adding after the build step.
4. **Forfeit handling** — flag forfeited matches as *awaiting commissioner credit* so they can't be
   silently forgotten. Nothing in the app surfaces this yet.
5. **The All Star cut line** — `site/build.py:ALL_STAR_CUT` is `None`, so the cut line is simply
   omitted. Set it to a number once the league says how many per division make All Star; the dashed
   rule and its styling are already built and will appear.
6. **Persistent storage** — still unnecessary. Everything recomputes from the archived recaps on each
   run, which at ~180 matches/season takes seconds. Revisit only if that stops being true.

### Open questions

- Exact Fall 2026 season length (rulebook allows 10 / 14 / 16 weeks) — needed for PPW and for the
  eligibility minimums in §G.2. **PPW currently divides points by the number of weeks in which the
  player scored at least one hit** (`events.load_season` → `weeks_by_player`). That is a defensible
  mid-season figure, but it is not the same as dividing by weeks played or by season length, and the
  season-end award basis needs deciding before anyone treats PPW as official.
- **How many players per division make All Star** — still unanswered, still the one design placeholder
  the league has to fill. See item 5 above.
- Whether `S90` should apply to 701 Triples: **answered — yes**, and implemented.
- Whether a 95+ turn awards face value: **answered — yes**, and implemented.
- Team rosters: **resolved without the league** — derived from the recaps (see gotchas above).
- Whether MPR comes through the export: **resolved** — DartConnect gives `mpr` per cricket side, and
  it is on the player pages. 120 players have one.

---

## Session log

### 2026-09-18 — Scoping and feasibility
- Wrote the BRD via the `/brd` skill. Read the Fall 2025 rulebook; extracted all of Section F.
- Discovered DartConnect serves structured JSON (Inertia), not scrape-only HTML — a much stronger
  foundation than the web scraper originally envisioned.
- Built a working rules engine and validated it against all 15 Week 1 matches.
- Found and fixed the doubles S90 bug (per-player → per-side).
- **Owner corrected 35 → 31 teams**; root cause was reading the filter dropdown instead of standings.
  A second variant of the same bug then surfaced (deriving teams from played matches gave 30, missing
  the Division 1 bye) and was fixed by sourcing from standings competitors.
  *Lesson: verify counts against standings before stating them.*
- **Owner identified that cricket `notable` already encodes marks-that-count** — eliminating the need
  to build an open/closed state machine, and removing the last blocker from the BRD.
- Confirmed: face value for 95+, S90 extends to 701 Triples, paper sheets run in parallel regardless.
- Moved prototype into the project folder as the build's starting point.
- Wrote `docs/design-brief.md` for designing the mobile app in a separate session. Key finding
  driving the design: **the median player has hits in exactly ONE stat column (max 4)**, so the
  legacy 29-column spreadsheet should not be reproduced — 95+ and R5 carry nearly everything, and
  R9/C4/C5/C6/S90 are near-zero. Division 1 scores ~2.5x Division 5, so never rank across divisions.

### 2026-09-18 — Building the app

Design work had happened in a separate folder; this session moved it in and built the real thing.

- **Moved the design in** from `~/Desktop/New Darts Bar/`: `DESIGN-SPEC.md`, `CLAUDE.md`, and
  `design/` (six mockup screens + the two logo assets). The mockups are the visual contract; they
  are not application code and nothing imports them.
- **Refactored `allstar.py` from counters to hits.** It used to accumulate per-player totals; it now
  emits one record per hit — player, team, division, code, display label, points, turn value, game,
  segment, set and game number, date, week, recap URL, rare flag — and `aggregate()` derives totals
  from those hits. Every screen needs the hits themselves (the player page lists each turn and links
  it back to its recap), and deriving totals means a displayed total can never drift from the hits
  shown beneath it. **Totals verified unchanged across the refactor: 104 players, 20,326 points,
  437 busts.**
- **Resolved `[TEAM NAME]`, the design spec's biggest placeholder, without asking the league.** It had
  been flagged as blocked on a roster nobody had. But a turn's side *is* the player's team, and
  `matchInfo.opponents[]` is in home/away order — so the mapping was already in the data we had
  archived. 174 players, zero ambiguous, every team name matching the standings list.
- **Recomputed the form stats, because DartConnect's player card is login-gated** (403). 3-dart
  average, first 9, MPR, leg win %, checkout % and opponent 3DA are now computed from turn data.
  Restricted to **singles legs only**: in doubles the darts belong to the pair and cannot be split
  fairly between partners, and DartConnect's own card is captioned "SINGLES 501 SIDO" for the same
  reason. Validated against DartConnect's per-leg averages across **84 singles legs, mean delta
  0.000** (max 0.01, rounding).
- **Two real bugs in those stats, both found by that validation:**
  - MPR was being computed from `ending_marks`, which turns out to be the **points** total, not marks.
    DartConnect supplies `mpr` per cricket side directly — use it.
  - "First 9" was being reported as the total points scored in 9 darts rather than as a 3-dart
    average, so it read roughly 3× too high beside every other average on the card.
- **New `scraper/events.py`** — `load_season()` assembles the season in one pass over the archive and
  is the single entry point the site build uses. **New `scraper/verify.py`** — the assertion suite,
  encoding the rules that were hard to get right and the bugs that were actually found, so they
  cannot come back silently.
- **Built `site/`** — `tokens.py` turns the DESIGN-SPEC palette and type into one stylesheet,
  `components.py` holds the shared fragments (page shell, header, tab bar, chips, icons, recap links),
  `build.py` renders all six screens. **165 pages**: 104 players, 15 matches, 30 teams, 5 division
  leaderboards, 5 standings pages, three indexes and the rare-hit screen. `build.py` fails the build
  if a bracketed placeholder ever reaches a real page. `app.js` adds the player-search filter and the
  long-table collapse as **progressive enhancement only** — every row is in the markup, so every page
  is complete with JavaScript off.
- **Found and fixed a contrast bug in the design spec itself.** DESIGN-SPEC listed the on-gold brown
  `#4A3A16` as 4.7:1. Measured, it is **4.20:1** — below the 4.5 AA floor for small text, and it
  carries the 8px `DIV` label on the *selected* division chip, which every screen with a division
  switcher shows. Changed to `#443112`, the same brown a shade darker, which measures **4.73:1** —
  what the original value was evidently reaching for. DESIGN-SPEC.md notes the correction.
- Set `ALL_STAR_CUT = None` rather than shipping `[ALL STAR CUT]` on a live page. The cut line's
  markup and styling exist; it appears the moment the league gives a number.

### 2026-09-18 (later) — Parallel hardening

Four workstreams ran concurrently: deployment/CI, documentation, an output QA suite, and the
site's interactive layer. What the QA pass turned up, all now fixed:

- **Heading structure.** Match pages carried three `<h1>` and player pages two; three index
  pages had none. Section headings are now `<h2 class="section">`; every one of the 165 pages
  has exactly one `<h1>`.
- **`white-space: pre-wrap` on `.name` was a trap.** It preserved the genuine double space in
  `Colin  Ratner`, but it *also* rendered the source indentation of any multi-line `.name`
  element as visible leading whitespace — which it was doing on the rare-hit screen. Removed.
  `components.esc()` already encodes the real double space as `&nbsp;`, which HTML cannot
  collapse, so the requirement is met without the hazard. **Assert the outcome (the `&nbsp;`
  survives), not the mechanism.**
- **A second whitespace bug, from DartConnect.** One team is stored as
  `'Prospect Darts and Chill '` with a trailing space, which collided with the following word
  and read as a double space. Both the recap feed and the standings feed are now normalised
  through `players.clean_team()` — they must be normalised identically or one team appears as
  two. This is *unrelated* to the deliberate internal double space above.
- **Contrast.** `#4A3A16` was documented as 4.7:1 but measures **4.20:1**, below the AA floor,
  on the 8px `DIV` label. Now `#443112` (4.73:1). `#1A1617` was in the mockups but missing from
  the spec's colour table; it is now the named `sunken` token. Verify any contrast formula
  against known pairs (`#FFFFFF`/`#000000` = 21.00, `#777777`/`#FFFFFF` = 4.48) before trusting it.
- **The reversed wordmark** (`psdl-wordmark-white.png`) was shipped but never referenced; the
  spec calls for it at the foot of the rare-hit screen. Now used.
- **`verify.py`'s baseline would have broken the automation.** It asserted season-wide totals
  of 104 players / 20,326 points, which grow every week — so the first week-2 match would have
  failed the check and blocked the deploy. The baseline is now scoped to the 15 week-1 match
  IDs, so it stays a permanent regression guard on the scoring rules without ever going stale.

**Search matching** was tested against real names in JavaScriptCore (no browser was available).
The first implementation missed `cam green` → `Cam "Jiminy" Green` and `obrien` →
`Kevin O'Brien`. It now matches per-token against two indexes, one punctuation-spaced and one
punctuation-stripped.

**Still outstanding:** nobody has viewed the site in a real browser. The Chrome extension did
not respond during this session. Everything above is static analysis and headless testing.
