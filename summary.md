# PSDL All Star Points — Project Summary

> **Living document.** Update this at the end of any working session. It is the handoff file for
> future agent sessions — read it first, before exploring the code.

**Last updated:** 2026-11-11
**Owner:** cjpospisil20@gmail.com
**Status:** Live at <https://psdartleague.com/>, rebuilt weekly by GitHub
Actions — 300 static pages from 131 archived matches (9 match nights), plus the Schedule of every
match night still to come. Not yet reconciled with the commissioners. ROADMAP Steps 1–2 complete;
Step 15's domain and HTTPS done early; part of Step 10 (the Schedule) done early.

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

- **Future fixtures live on the lineups feed, not `matches.json`.** `POST .../matches/{season}` only
  ever lists matches that have *started* (true of every committed version). `POST
  tv.dartconnect.com/api/league/ParkSDL/lineups/{season}` — the JSON behind DartConnect's Lineups
  page — lists every match *not yet complete*: the rest of the season (16 rows a night: Division 1's
  3 matches + 1 bye, 3 each in Divisions 2–5; Division 1 ends a week early), plus stale rows.
  `fetch.fetch_fixtures()` trims it to schedule fields → `data/fixtures.json`.
- **A bye is a row with one side null** (`is_bye: true`, the other side's `id`/`team_name` null). So
  every past Division 1 bye lingers in the lineups feed with status `P` forever.
- **Status `A` lingers after a match ends.** `P` pending → `A` started → `C` complete, but a finished
  match stays `A` until it is finalised (three from 11-10 were still `A` the next afternoon). `A` is
  not "live". DartConnect's real live list is `POST .../matches/live/{season}` (empty off match night);
  unused, because the site never rebuilds on a Tuesday night.
- **On the Schedule, HOME = `left`, by owner decision (2026-11-11).** DartConnect's own live view maps
  `home: left, away: right`. But the side recorded as home *on the night* matched `left` in only
  64 of 127 played matches, and some teams are `left` in 2 of 12 fixtures — so `left` is a scheduling
  label, not who the tablet called home. Never use it to label a played match (ROADMAP finding #8).
- **A postponed match vanishes from the Schedule** until the commissioners give it a new date in
  DartConnect: `fixtures.upcoming()` drops every row dated before today (New York). One Division 5
  match from 11-10 is in that state now.

- **Team count is 31**, and there are two wrong ways to get it. `schedule['teams']` is the filter
  dropdown (35) and includes non-competing entries (`E-Z Buttons (Denny's)`, `Farm.One`, `Lucky 7's`,
  `The H is O (Commish)`). Deriving from played matches undercounts (30) because Division 1 has 7
  teams, so somebody has a bye every week. **Use the standings competitors list** — `fetch.teams()`.
- **In doubles, a *side* gets ON once**, not each player. Crediting S90+ per player wrongly credits a
  partner's first turn. (This was a real bug, found and fixed.)
- `score_edits` exists on games — commissioners can amend scores after the fact, so processing must
  recompute rather than append.
- **Player → team comes free from the recaps.** A turn's side (`home` / `away`) *is* the player's team;
  `matchInfo.opponents[]` is in home/away order. `scraper/players.py:team_map()` does this.
  No roster file needed from the league.
- **Teams get renamed mid-season, and a recap keeps the old name forever.** The archive is immutable,
  so `matchInfo.opponents[i].name` is the name as of match night — and a recap carries **no team id**.
  `standings.json` and `matches.json` are refetched every run, so they carry today's name *plus* the
  stable `id`. Three teams were renamed between week 1 and week 3 of Fall 2026:
  `Eagle Fang Darts (Finn's)` → `Eagle Fang Darts` (395251), `The Tickle Tickles (Pumps)` →
  `The Tickle Tickles` (395224), `Paddy's 2 (George)` → `Dart Day Afternoon` (395266).
  **Never compare team names across feeds — resolve through the id.**
  `players.resolve_sides()` joins each recap to its schedule row and reads `left.id` / `right.id`,
  then `players.canonical_teams()` asks standings what that id is called now.
  Note it does *not* assume `left` is the recap's home side — it was home in only 6 of week 1's 15
  matches — it identifies the sides by exact name match, then by elimination, then by score.
- **`-SHORT-` is not a person.** It is DartConnect's marker for a side playing short-handed (46 turns
  so far), and it legitimately appears for whichever team was a player down, so it looks exactly like
  someone on two teams. `players.SENTINEL_PLAYERS` filters it.
- **The Inertia payload moves.** Inertia can embed a page's JSON two ways and DartConnect has used
  both: HTML-escaped in the root element's `data-page` **attribute**, or raw in the **body** of
  `<script data-page="app" type="application/json">`. `recap.dartconnect.com` switched to the second
  on or before 2026-10-28; `tv.dartconnect.com` (schedule, standings) was still on the first.
  The nasty part: on the new form the attribute still exists and holds the literal string `"app"`,
  so a regex over it **still matches** and then dies with
  `JSONDecodeError: Expecting value: line 1 column 1` — a message that says nothing about formats.
  `fetch._inertia_props()` collects both candidates and lets a successful parse decide.
  Only the attribute form is HTML-escaped: unescaping a raw script body would silently turn a team
  genuinely called `Foo &amp; Bar` into `Foo & Bar`.
- **DartConnect's player-card endpoint returns 403** without a login, so form stats (3-dart average,
  first 9, MPR, leg win %, checkout %, opponent 3DA) are **recomputed from turn data** in
  `players.py:form_stats()`. Validated against DartConnect's own per-leg averages: 84 singles legs,
  mean delta 0.000.
- **`ending_marks` on a cricket side is the POINTS total, not marks.** Computing MPR from it is wrong;
  DartConnect supplies `mpr` per side directly. (Real bug, found and fixed.)
- **`darts_thrown` is only recorded for the player who checked out.** The loser never finishes
  mid-turn, so their count is exactly 3 × turns taken.
- **A leg's first turn names only one partner.** In doubles and triples the partners alternate
  turns, so anything keyed off `turns[0]` sees only whoever threw first — by week 9 that left 45
  players short of nights they had played. `players.throwers()` reads every turn; GP and the player
  page's MATCHES come from it.
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
data/recaps/*.json     archived match payloads — 120 matches, 8 match nights
docs/                  PSDL rulebook (PDF + extracted text)
docs/design-brief.md   self-contained brief for app/UI design sessions
docs/legacy/           stray legacy CSV files moved out of the way
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

**Build output, 7 match nights (as of 2026-10-28):** 390 pages — 238 player pages, 105 match pages,
31 team pages, 5 division leaderboards + 5 standings pages (plus `index.html` / `standings.html`
aliases to Division 1), a players index, a matches index, a teams index, and the rare-hit screen.
All 31 teams now have a page; with only Week 1 archived it was 30, because `The Craic` (Div 1) had
the bye. Rare-hit screen still shows Kevin O'Brien's 180 — it is billed as the *first* 180 of the
season, so it is a season-long landmark, not a weekly feature. Season to date: 238 players,
168,160 points across 105 matches, and four 180s now (O'Brien, Adam Feder, Caleb Newberg, Bill Jones).

---

## What's next

1. **Hosting** — **done.** Live at <https://psdartleague.com/> — GitHub Pages hosts it; the domain
   is registered at Vercel, which serves only its DNS (records in `README.md`). Published from
   `.github/workflows/build.yml`: `fetch.py` → commit the archive → `verify.py` → `build.py` →
   `check.py` → deploy, with the deploy job gated on the build job succeeding. Newly archived recaps
   are committed *before* verifying, so the archive survives a failed build.
   **Watch the Actions tab, not the site.** Because the archive is committed before the gate, a
   failing `verify.py` looks like nothing is wrong — data keeps accumulating in the repo while the
   published site silently freezes. That happened for 11 days (2026-09-21 to 10-02): four scheduled
   runs archived weeks 2 and 3 correctly and every one of them failed the gate, so the live site sat
   on its first build showing `MP 1`. `gh run list` is the fastest way to see it.
2. **Commissioner reconciliation** — two commissioners hand-score 3 matches (one per division tier)
   against system output. This is the gate before automated numbers become official. The per-match
   pages that were built for this were retired with the Match tab (2026-11-11); every hit on a
   player page still links to its DartConnect recap, naming set and game — and git history has
   `match_page()` if a commissioners-only per-match view is wanted back.
3. **Scheduled runs** — **done**, in `.github/workflows/build.yml`: Wednesday 07:00 UTC with a
   Thursday catch-up, since GitHub sometimes drops scheduled runs and `fetch.py` skips anything
   already archived. The order is `fetch.py` → `verify.py` → `build.py` → `check.py`; run it in that
   order by hand too, and never publish a build whose verify failed. The workflow runs
   `site/check.py` after the build; both gates fail the job and so block the deploy.
4. **Forfeit handling** — flag forfeited matches as *awaiting commissioner credit* so they can't be
   silently forgotten. Nothing in the app surfaces this yet.
5. **The All Star cut line** — `site/build.py:ALL_STAR_CUT` is `None`, so the cut line is simply
   omitted. Set it to a number once the league says how many per division make All Star; the dashed
   rule and its styling are already built and will appear.
6. **Persistent storage** — still unnecessary. Everything recomputes from the archived recaps on each
   run, which at ~180 matches/season takes seconds. Revisit only if that stops being true.
7. **Player-page LEGS, DARTS and LEG WINS credit only each leg's opener.** `form_stats` keys its
   activity counts off `turns[0]`, so a doubles or triples partner who threw second is missing from
   them, and the opener is credited with the whole side's darts. MATCHES had the same bug and now
   comes from `nights_by_player` (see the 2026-11-11 GP entry); the other three were left alone.

### Open questions

- Fall 2026 season length: **answered by the owner (2026-11-11)** — Divisions 2–5 play 15 nights;
  Division 1's seven teams play each other twice, 12 nights over 14 weeks with two byes each.
  DartConnect's lineups feed agrees exactly. It is `players.SEASON_NIGHTS` and drives the
  playoff-eligibility check marks (Rulebook §H.2 — earlier notes here said §G.2, which is wrong).
  **PPW still divides points by the number of weeks in which the player scored at least one hit**
  (`events.load_season` → `weeks_by_player`). That is a defensible mid-season figure, but it is not
  the same as dividing by nights played (`nights_by_player` now exists) or by season length, and the
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

---

### 2026-10-02 — Unblocking the weekly publish

**Symptom the owner reported:** the live site looked out of date. It was — by two weeks.
`curl -sI .../standings-division-4.html` returned `last-modified: Sat, 19 Sep 2026 04:10:41 GMT`,
the very first build, and every standings row read `MP 1`.

**The data was never the problem.** The archive had kept up perfectly: 45 recaps over three match
nights (09-15, 09-22, 09-29), all `status: "C"`, because the workflow commits the archive *before*
it verifies. Every scheduled run since 2026-09-21 had failed the gate, so nothing published.

Three `verify.py` failures, two root causes.

**1. One assertion was never scoped to week 1.** `verify.py` documents its own rule at the top —
the baseline is scoped to the 15 week-1 match IDs precisely so new weeks can't break it — and
`verify.py:78` broke it: `check("Tom Lettieri's hits sum to 835", lettieri == 835)` where
`by_player` accumulated **all** hits. 835 was his week-1 total; his 3-week total is 1215. The number
now lives in `EXPECTED_WEEK1["top"]` and is computed from `w1` hits only, like everything else there.
*Lesson, for the second time: any hardcoded total in `verify.py` must be scoped to the baseline
matches, and the label string must come from the same constant so the two cannot drift.*

**2. Three teams were renamed on DartConnect mid-season** — see the gotcha above. This is the
interesting one. The two failures it caused looked unrelated (`no player on two teams`, and
`all team names appear in standings`) and the FAIL line understated both: `verify.py` truncated the
ambiguous list with `[:3]`, so it reported 3 players when there were **17**, and only 2 of the 3
renamed teams appeared at all.

That last part was luck, and worth understanding because it is the kind of bug that hides.
`matches.json`'s `reg` dict is newest-date-first, so `hits` runs week 3 → week 1, and
`players.division_table` does `meta.setdefault(...)` — first hit wins, i.e. whichever week the player
most recently scored in. Players who scored again in week 2 or 3 silently picked up the new team name;
players who scored **only in week 1** stayed frozen on the old one. No Tickle Tickles player had
scored exclusively in week 1, so that rename stayed invisible. Nothing was *handling* the rename —
the data just happened not to expose it.

Fixed by resolving team identity through DartConnect's stable numeric team `id` instead of its display
name (`players.resolve_sides` / `canonical_teams`, called from `events.load_season`, which already has
the recap and its schedule row in the same loop iteration). `allstar.score_match` gained a `teams=`
override so the canonical name is stamped on **every hit at score time** — which is what makes
`division_table`'s first-hit-wins ordering harmless: all weeks now agree. `team_map` and
`ambiguous_teams` take `(props, sides)` pairs so they see canonicalised teams too.

This is not an alias map and not fuzzy matching (CLAUDE.md data rule 5 stands): no name is compared
approximately, nothing is hand-coded, and a match it cannot identify raises rather than guesses.

**Relaxing the two team assertions was never an option.** `build.py` keys team pages off `r["team"]`,
so `Eagle Fang Darts` and `Eagle Fang Darts (Finn's)` would have rendered as two team pages with half
a roster each, while standings linked only to the new name — orphan pages, no inbound link.

**Also found:** `-SHORT-` is a DartConnect short-handed marker, not a player, and was one of the 17
ambiguous entries (`DuckDown Darts` ×27, `Farrell's` ×19). `players.SENTINEL_PLAYERS` filters it.

**Verified:** `verify.py` all checks pass, with the week-1 baseline still reproducing exactly
(104 players / 20,326 points / 437 busts / Lettieri 835). `build.py` → 280 pages. `check.py` all
checks pass — this was its first run at 3-week scale, and it needed no changes. 31 team pages, one
per standings competitor. The three week-1-only players on renamed teams (Zach Desantis-Salavarria,
Adam Caballero, Keenan Ferguson) all land on the current team on both their player page and the team
page. `grep` for `(Finn's)`, `Paddy's 2`, `(Pumps)` and `-SHORT-` across `public/` returns nothing.

**Not done, deliberately:** ROADMAP Steps 2 and 3 (pipeline hardening, season-scoped archive). Step 3
still matters before next season — bumping `SEASON` breaks the week-1 verify baseline.
`events.load_season` still labels schedule `left` as home, which is wrong in most matches (ROADMAP
finding #8); the rename fix deliberately does not depend on that orientation.

---

### 2026-10-28 — DartConnect moved the Inertia payload

**Symptom the owner reported:** a question, not a bug — "when does the website update?" Checking to
answer it turned up that **that morning's run had failed 20 minutes earlier.** The site was on
`WEEK 6 · TUE 20 OCT`, published 10-22. Two match nights (10-20, 10-27) were unpublished.

Exactly the silent-freeze pattern the last session documented, and a good argument for the
`gh run list` habit: the site looked a week behind, not broken.

**A different fault, in a different place.** Not the verify gate this time — `fetch.py` crashing:

```
File "scraper/fetch.py", line 59, in fetch_recap
  props = json.loads(html.unescape(m.group(1)))["props"]
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Root cause: Inertia embeds the page payload two different ways, and `recap.dartconnect.com`
switched.** It used to be HTML-escaped JSON in the root element's `data-page` *attribute*. It is now
raw JSON in the *body* of `<script data-page="app" type="application/json">`.

What made this hard to read from the traceback: **the old regex still matched.** The attribute is
still on the page — it just holds the literal string `"app"` now. So the failure never surfaced as
"format changed"; it surfaced as a JSON decode error on a 3-character string.

A red herring on the way: the unfetched set included one match with `status: 'A'` rather than `'C'`
(`Boats & Hoes v Those Divas`, 1–10), which looked like the obvious culprit — ROADMAP finding #3 is
exactly about unfinished matches. It was not. Probing both an `'A'` and a `'C'` match returned the
*same* `data-page="app"`, which is what identified the real cause. For the record that match is
fully played — 11 games, 236 turns, 1,386 darts, a real 7:29–10:46 PM window, no `score_edits` — so
`'A'` is some administrative state, not an abandonment. It scores and renders fine. **What `'A'`
actually means is still unknown**, and `fetch.py` does not filter on status (ROADMAP Step 2).

**Fixed** with `fetch._inertia_props(page, source)`, used by both `fetch_recap` and
`fetch_standings`: collect both candidate locations, try to parse each, first one yielding a `props`
dict wins. Never infer the shape from the host — `tv.dartconnect.com` was *still on the old form* on
the same day, so the two endpoints genuinely disagreed. Whichever migrates next now costs nothing.

Only the attribute form gets `html.unescape`. On the raw script body unescaping is a no-op *by
luck* — verified the body carries raw `&`, not `&amp;` — but applying it would silently corrupt a
team genuinely named `Foo &amp; Bar`. Tested both directions.

The failure message now names what it tried and what it found, instead of surfacing a bare
`JSONDecodeError`.

**Verified:** 17 missing recaps fetched (105 archived total, complete through 10-27). `verify.py`
all checks pass with the week-1 baseline still reproducing exactly — the payload *structure* is
unchanged, only its location moved, so nothing downstream needed touching. `build.py` → 390 pages;
`check.py` passes; build is byte-for-byte reproducible. Homepage reads `WEEK 7 · TUE 27 OCT`,
Division 5 standings show `MP 7`, and the `status: 'A'` match page renders with both teams and its
9 hits. Helper unit-tested against both formats, both-present, and four failure modes.

**Still not done:** `fetch.py` aborts the whole run on the first unparseable match, so one bad recap
blocks the rest that night. The archive-before-verify commit means nothing fetched is lost (this run
had already saved 13 before dying), but the loop should be resilient — ROADMAP Step 2.

---

### 2026-11-09 — ROADMAP Step 2: Pipeline hardening

Six changes, all in service of making the weekly automation more robust.

**1. Status guard on `fetch.py`.** Only archives matches with `status == "C"`. Non-complete matches
are logged and skipped. `events.py` also only flags completed matches as missing, so a non-`C` match
won't fail the verify gate. Currently all 120 matches are `'C'`, but the guard prevents archiving a
mid-play match during a manual Tuesday-night run — the one real risk the ROADMAP identified.

**2. Resilient fetch loop.** `fetch.py` no longer aborts the run on the first bad match. Each fetch
is wrapped in try/except; failures are collected and reported at the end. The archive-before-verify
commit means nothing fetched is lost, and now the loop continues past a single failure to archive
everything it can.

**3. Cron moved off `:00`.** GitHub's scheduled-action queue is busiest at the top of each hour.
Changed from `0 7 * * 3,4` to `17 7 * * 3,4` — same effective time, lower queue contention.

**4. Build timestamp.** Every page now carries `<meta name="last-modified" content="YYYY-MM-DD">`
in the head. Set by `build.py` from `datetime.date.today()`, surfaced via `components.BUILD_DATE`.
The only deliberately non-reproducible element in the output — the ROADMAP's golden-build comparison
accounts for it.

**5. `None` check aligned with `check.py`.** `build.py`'s placeholder scan checked for the substring
`"None"` in raw HTML, which would false-positive on any word containing "None" or on CSS `none`
values. Now uses word boundaries (`r"(?<![A-Za-z0-9])None(?![A-Za-z0-9])"`) — the same approach
`check.py` uses on text nodes. The bracketed-placeholder checks (`[TEAM NAME]` etc.) are unchanged
since brackets are distinctive enough for substring matching.

**6. Slug collision check.** `verify.py` now checks that the `slug()` function produces unique
file paths for all 242 player names and all 31 team names. This guards against names that differ
only in characters stripped by slugification (e.g. `José` / `Jos` would both become `jos`). Both
pass today, but the check prevents a silent page overwrite if two colliding names ever appear.

**Also:** moved `Park Slope Dart League (PSDL) - Stats.csv` and `docs/allstar-standings.csv` to
`docs/legacy/` — they were stray files from the legacy era.

**Verified:** `verify.py` (all checks pass, including the new slug collision section), `build.py`
(409 pages), and `check.py` (all checks pass). Week-1 baseline still reproduces exactly.

### 2026-11-11 — Custom domain: psdartleague.com

CJ bought **psdartleague.com** on Vercel and asked for the site to move to it. That is ROADMAP Step 15's
domain and HTTPS items, brought forward at the owner's request; the rest of Step 15 (Twitch `parent`,
page titles, share tags, favicon) is still open. **No code changed.** Every link the build writes is
relative, `app.js`'s back link resolves against the page itself, and the workflow's environment URL
comes from `deploy-pages`, so the site works unchanged at the root of a new domain.

**Decision: Vercel holds the DNS, GitHub Pages keeps hosting.** ROADMAP §1 had already chosen Pages,
and moving the hosting would have added a Vercel token and the npm CLI to CI for no gain. The records
are in `README.md` → "Repository settings this depends on".

Gotchas worth keeping:
- **A `CNAME` file does nothing here.** GitHub ignores it on an Actions deploy. The domain lives only
  in Settings → Pages, or `gh api -X PUT repos/cjpospisil20/psdl-all-star/pages -f cname=…`.
- **Vercel DNS answers every name by default** — the apex, `www`, any made-up subdomain — with
  Vercel's own IPs. Those default records cannot be deleted; records you add override them. Check
  against the authoritative server, not your own resolver:
  `dig +short @ns1.vercel-dns.com psdartleague.com A` must return GitHub's four `185.199.x.153`.
- **CAA is already fine.** Vercel's default CAA records allow `letsencrypt.org`, which is where GitHub
  Pages gets its certificate.
- **The domain can go dark over paperwork.** If the registrant email differs from the Vercel account's,
  it must be verified within 15 days of purchase, or the registrar puts the domain on `clientHold` and
  DNS stops resolving. Auto-renew is on by default and needs a valid card on the Vercel account.
- **The domain verification belongs to CJ's personal GitHub account**, not to the repo, and it blocks
  every other owner — including a future PSDL organization — from publishing on the domain. Order for
  the org move: remove the verification → transfer the repo → re-verify under the org → repoint the
  `www` CNAME to `<org>.github.io`.
- **The machine you test from can lie for half an hour.** Anything that looked the domain up before
  the switch caches Vercel's default answer (TTL 1800 s). Here the Mac's system resolver kept returning
  Vercel's IPs — and Vercel's `DEPLOYMENT_NOT_FOUND` 404 — after every public resolver had moved on.
  Test with `curl --resolve psdartleague.com:443:185.199.108.153 https://psdartleague.com/` or
  `dig @1.1.1.1`, not a browser on that machine.
- **A Pages setting change needs a deploy to take effect.** The custom domain itself served at once,
  but after Enforce HTTPS was switched on, `http://` kept serving plain pages for 4½ minutes; a
  "Build and deploy" run applied it within 25 seconds of finishing. On an Actions-deployed site,
  re-run the workflow after changing anything in Settings → Pages.

**Cutover, same day (~16:00 UTC).** CJ verified the domain on the GitHub account and added the records
in Vercel. Both Vercel nameservers, 1.1.1.1 and 8.8.8.8 returned GitHub's IPs within minutes — Vercel's
defaults were overridden as documented. The custom domain was set through the Pages API; GitHub reported
it `verified`, its DNS health check passed for the apex and `www`, and the Let's Encrypt certificate
(both names, valid to 2027-02-09, renewed by GitHub) was approved within minutes. HTTPS enforced; the
repo's About link points at the domain.

**Verified:** `verify.py`, `build.py` (436 pages) and `check.py` pass unchanged. On the live domain,
every page type (division, player, match, team, award, standings) plus `app.css`, `app.js` and the
logo return 200, and a match page is byte-identical to the local build. `http://` → 301 to `https://`;
`www` → 301 to the apex; old `github.io` links land on the same path at `https://psdartleague.com`
(one or two hops — GitHub sometimes routes deep links via `http://` first). Run 43055123188 green.

### 2026-11-11 — Standings → team pages, Feed tab, the ALL board, award holders up front

Five changes the owner asked for, all in the generator (`site/`), plus one pure helper in
`players.py`. Not a ROADMAP step; done at the owner's request, like the Awards tab before it.

1. **Standings rows open the team page.** Every row is now a link. Team pages are built from the
   **standings competitors** (data rule 6), not from who has scored, so all 31 rows always have a
   page — this also settles ROADMAP finding #13. `build.team_href()` builds both the link and the
   file path, so they cannot drift. A team page lists the **whole roster**: scorers first (ordinal
   division rank, chips, points), then teammates who have thrown but have no all star hits yet
   (19 league-wide today) as plain, unlinked rows — no player page exists for them. Each row carries
   the singles `’01` average and MPR from `players.form_stats`, two decimals to match the standings
   rows. The back link returns to that team's division standings.
2. **Feed replaces Team in the tab bar** (Standings · All-Stars · Match · Feed · Awards). The Teams
   index (`teams.html`, `teams-division-N.html`) is gone — Standings is the way into a team now.
3. **The All-Stars ALL board** (`all.html`). Every scoring player, numbered 1–N league-wide, at the
   owner's explicit request — a second, documented exception to "never rank across divisions"
   (CLAUDE.md #3, DESIGN-SPEC hard requirement 2). It crowns nobody: no leader card, no gold top
   three, no rare-hit banner; every row names its division; the 2.5× gap is stated on screen.
   `players.league_table()` returns *copies* with a `league_rank`, so the division `rank` every other
   page shows can never be renumbered by it (verify.py asserts that).
4. **The Feed page** exists and says "Nothing posted yet." It cannot be literally blank: `check.py`
   requires exactly one `<h1>` per page.
5. **The Awards index names the holders**, in the owner's order: Points Leader → Largest Check-In →
   Largest Checkout → The Big Fish → 171+ Club. Division leaders are listed in division order, never
   by points (that would rank them across divisions — `check.py` asserts it). Ties show every holder
   (Largest Checkout is a 115 tie today). A club's holders are its whole membership. The detail pages
   are unchanged; the index links to them where they show more. The old index's "latest Brian Tuohy"
   was wrong — it took the *last item in value order*, not the latest by date — and is gone.

Gotchas worth keeping:
- **The 26px rank column only fits two digits.** Measured in Anton at 21px: `3rd` is 28px, `22nd`
  42px, `243` 31px. Team-page ordinals had always run into the names; `.row-rank.ordinal` (44px)
  and `.row-rank.wide` (32px, the ALL board) fix it — width only, no colour.
- **`esc(x or '&mdash;')` prints a literal `&mdash;`** — `esc()` escapes the fallback's ampersand.
  The standings rows and the division-average note did this for any team yet to play (invisible
  today, every team has played). `build.dash()` now emits the dash as markup.
- `.btn + .headline` / `.caption + .headline` get a 20px top margin so the five award sections read
  as five; the same rule loosens the points-leader detail page's division sections.

**Verified:** `verify.py` (new §9, the league table), `build.py` (432 pages = 436 − 6 team indexes +
`all.html` + `feed.html`) and `check.py` (new §11: tab bar on every page, every standings row links
a team page and every team page is reached, back links return to the right division, all 243
players on exactly one team page, the ALL board crowns nobody and runs 1..N by points, the awards
index names every holder, leaders in division order) all pass. Each new check was proved by
breaking a copy of the build nine different ways — all nine caught. Against the previous build, the
131 match pages, 6 match-night indexes, the rare-hit screen and 4 of 5 award detail pages are
byte-identical apart from the tab bar (the fifth differs only in the Check-In blurb). Walked in
Chrome: Standings → team → back, the ALL board's search and show-all, Feed, Awards; no console
errors.


### 2026-11-11 — The Match tab becomes the Schedule

At the owner's request (not a ROADMAP step in order — it delivers part of Step 10 early, and
corrects ROADMAP §2 finding 1 / §13 risk 1: DartConnect *does* publish future fixtures, on the lineups
feed). The owner didn't want all-star points per match; they wanted to see who plays whom next.
Decided with the owner: label DartConnect's first-listed team HOME, team names only (no bars — no
venue data exists); remove the per-match pages.

- **Removed:** the 131 `match/<id>.html` pages, the 6 match-night lists, `build_matches()` /
  `match_page()`, the week filter in `app.js`, the dartboard `match` icon. Every all-star hit is still
  traceable from player pages, each linking to its DartConnect recap.
- **`schedule.html`** (tab: SCHEDULE, calendar icon; also written to `matches.html` so old links
  land). Every match night from today on, in date order: `TUE 17 NOV · WEEK 10 · 7:30 PM`, then
  each fixture as home | v | away with HOME/AWAY under the names, both linking to their team pages,
  and Division 1's bye. A division menu and a team search (both `hidden` until `app.js` reveals them;
  the division is kept in `#division-N` and `localStorage`).
- **Live comes from the clock** (ROADMAP §7's decision): each night carries `data-start` with New
  York's offset (`2026-11-17T19:30:00-05:00`); from first darts until midnight (`LIVE_MS`, 4.5 h)
  `app.js` adds `.live` to that night — gold-bordered cards, gold `LIVE NOW` — and after midnight it
  hides the night. Tonight is always the first night, so live matches are already at the top. It
  re-checks every minute and when the phone returns to the page. `section.night.live` is the hook for
  ROADMAP Step 12's "watch live".
- **New York time by hand:** `fixtures.eastern_offset()` hard-codes the US DST rule (2nd Sunday of
  March → 1st Sunday of November) because `zoneinfo` needs `tzdata` on Windows; `league_today()`
  uses it so a manual Tuesday-night build (already Wednesday in UTC) keeps tonight's matches.
- **Week numbers on the Schedule are DartConnect's `round_seq`**, not the date position `week_of`
  uses: a make-up played on an off night keeps its round instead of shifting every later week. On
  regular nights they agree (round 9 = 11-10 = week 9).
- **The fixtures refresh never blocks archiving.** `fetch.py` runs it after the recap loop; a failure
  prints a GitHub `::warning::` and keeps the previous `fixtures.json`.

Gotchas: a local variable `schedule` (the `matches.json` dict) inside `load_season` shadowed a module
of the same name — hence `fixtures.py`. Headless Chrome won't render narrower than ~500px, so phone
screenshots go through a 390px iframe. `--dump-dom` needs script, so the JS-off state was checked as
the raw HTML (and screenshotted with `app.js` stripped).

**Verified:** `verify.py` (new §10: DST offsets at both 2026 changeovers, league timezone, nights in
order, every fixture between standings teams in a standings division), `build.py` (300 pages =
435 − 131 match pages − 6 lists + `schedule.html` + `matches.html`), `check.py` (new §12: the page
exists and `matches.html` matches it, nothing links a retired page, no night ships live, every
`data-start` has an offset, nights ascend, the menu is All + every standings division, all 92
fixtures link HOME then AWAY or one BYE to team pages) all pass; the new fixture check caught a real
markup change mid-session. In headless Chrome with a faked clock: 7:29 PM nothing live; 8:15 PM the
first night live; 12:30 AM it is gone (87 → 72 matches); `#division-3` → 18; "craic" → The Craic's
5; a nonsense search → the empty-state line.

### 2026-11-11 — GP and the playoff check mark on team pages

At the owner's request (not a ROADMAP step). Every roster row on a team page now reads
`GP 8 · ’01 51.24 · CRK 2.27`, and a gold check mark follows the name of every player who is playoff
eligible.

- **GP** is league nights played; one game in a night counts (Rulebook §H.2). `players.throwers()`
  reads every turn of every game, and `events.load_season` collects `nights_by_player` (sets of
  dates) beside `weeks_by_player` (nights with a hit).
- **The rule**, `players.playoff_minimum`: the largest whole number below half the nights a team
  plays. 10 → 4, 14 → 6, 15 → 7 are the rulebook's own examples, and `verify.py` asserts them. The
  owner's version ("half the nights, minus one"; "less than 7.5 is 7") is the same rule.
- **Season length**, `players.SEASON_NIGHTS`, keyed by season id. The owner confirmed 15 nights for
  Divisions 2–5 and 12 for Division 1 (seven teams × twice, over 14 weeks with two byes). Counting the
  nights a team *plays* gives Division 1 the rulebook's bye answer by itself: 14 weeks need 6, two
  byes count as one week, so 5 — and 12 nights give 5. The lineups feed that landed the same day
  agrees exactly: every Division 1 team has 12 fixtures and 2 byes, every other team 15. A season
  missing from the table shows GP with no marks and the build prints a note. It never guesses.
- **The mark** is an inline stroke SVG (check.py's emoji guard covers ✓), gold from the icon stroke,
  with visually hidden ", playoff eligible" for screen readers. The caption states the rule with the
  division's numbers. The UI says *eligible*, the rulebook's word: a player is eligible, but their
  team still has to make the playoffs.
- **Fixed: the player page's MATCHES undercounted 45 players.** `form_stats()["matches"]` counted
  only a leg's opener, so partners lost nights. Gerry Hernandez played 9 and was shown 5; Isaac
  Petroulis-Lessig played 5 and was shown 4; 3 players were not counted at all. MATCHES now reads
  `nights_by_player`, the same number as GP, and `form_stats` no longer returns `matches`. LEGS, DARTS
  and LEG WINS have the same bias and are left for later (What's next, item 7).

Worth knowing: the three 2026-11-10 matches still at status `'A'` (DuckDown Darts v The Monro Pub,
Commish 1 v Those Divas, Commish 2 v Bullseye Babes Double Trouble) are not archived yet, because of
Step 2's guard. Their six teams' players are one night short until DartConnect finalises them.

**Verified:** `verify.py` has a new §11: the rulebook examples hold, every rostered player has played
at least one night, every night with a hit counts as a night played, nobody is credited with a night
their team did not play, and the season length names exactly the standings divisions. `check.py`'s
§11 adds four checks: all 262 roster rows show GP, every stated minimum is (nights − 1) // 2, a row
is marked exactly when GP reaches it, and every mark is an SVG with words for screen readers. All
pass, and the build is still 300 pages. Against the previous build, only `app.css`, the 31 team
pages and the 36 player pages whose MATCHES was wrong changed. Six broken copies of the build were
all caught. Opener-only GP and a misspelt division both fail `verify.py`. An unknown season builds
clean with no marks. That Team marks CJ Pospisil (8), Chris Senior (9), Craig Hubler (8), Josh
Hollenberg (9) and Joe Bentham (7), but not Matt Knowlton (4) or Isaac Petroulis-Lessig (5). Every
Division 1 page states 5 of 12. In Chrome at phone width the mark sits after the name, and at 320px
it wraps with the last word of a long name; no console errors.


### 2026-11-11 — The R8+ award becomes the R9 Club

At the owner's request; not a ROADMAP step. The Awards page's **R8+** section listed every Cricket
turn of 8 or more marks. It is now the **R9 Club**, for perfect nine-mark rounds only. Asked whether
the Feed should follow the award, the owner said yes, so the Feed's cricket-round cards are R9-only too.

- `awards.club_r9()` replaces `club_r8()` and keeps `code == "R9"` only, earliest first like the Big
  Fish. Every entry is worth 9, so value order would mean nothing. The award key is `r9`, so the
  detail page is now `award/r9.html`. `award/r8-plus.html` is gone, and nothing linked to it: the
  index never links a club's detail page.
- Six players leave the list: Dave Bundren, Nick Hudak, Daniel Montoya, Ismael Cruz, Danny Kot and
  Lulu Bird. Each has an R8 and no R9. Four stay: Sam Masling, Josh Goldberg, Mack Diller and
  Stuart McCarthy.
- `feed._achievement_events()` posts R9s only (event type `r9`), so the Feed goes from 63 cards to 57.
- An R8 is still an all star hit worth 160 points. Leaderboards, player pages and team pages are
  unchanged.

Gotchas for phone screenshots in headless Chrome. `sips` ignores `--cropOffset` and always crops from
the centre, so centre the 390px iframe in the window and let the centre crop frame it. Calling
`scrollIntoView()` inside the iframe also scrolls the parent page, so set the iframe's `scrollTop`
instead. Wait for `document.fonts.ready` before scrolling, or the 8.5px tab labels sometimes don't
render.

**Verified:** `verify.py` §8 has two new checks: the R9 Club is exactly the R9 hits, and the feed
posts every R9 and no R8. Each was proved by letting the R8s back in on a scratch copy, and both
breaks were caught. `verify.py`, `build.py` (still 300 pages) and `check.py` all pass. Against the
previous build only `awards.html` and `feed.html` changed, plus `award/r8-plus.html` → `award/r9.html`.
Both pages were checked in headless Chrome at phone width.
