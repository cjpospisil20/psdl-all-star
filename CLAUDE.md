# PSDL All Star app — conventions

A mobile-first web app for the Park Slope Dart League (Brooklyn, Tuesday nights) showing **All Star
Points** and the **league standings**. It opens out on a tablet or desktop too (2026-11-13). Replaces a 29-column spreadsheet site that, per the
commissioners, almost nobody reads — and 2–3 hours a week of commissioner data entry.

## Start here

- **`docs/ROADMAP.md`** — the plan for growing this stats app into the full PSDL website: the
  architecture, the decisions already made, and the numbered implementation steps. Work on **one
  step at a time**, in order, and tick the step off there when it is done.
- **`summary.md`** — the living handoff doc. Read it first: current state, the run commands, the
  data gotchas that were expensive to learn, and the session log. **Update it at the end of a
  working session.**
- **`README.md`** — the outward-facing description: what the site is, and how to run it locally.
- **`DESIGN-SPEC.md`** — the design contract. Colours, type, the stat vocabulary, the hard
  requirements, and exactly which numbers in the mockups are real vs. placeholder.
  Read it before writing UI.
- **`design/*.html`** — six static mockups of the finished screens. Open `design/index.html`
  in a browser to see them side by side. These are the visual target; match them. They are
  **not** application code — nothing imports them.
- **`brds/psdl-all-star-points-automation-2026-09-18.md`** — the BRD: scope, impact, the rulebook
  rules, the risks.
- **`docs/design-brief.md`** — the original brief from the league, with the research behind the
  design decisions.

## Stack

Python 3 **standard library only**. No dependencies, no package manager, no framework, no
bundler, no node_modules. Output is **static HTML** — a plain directory any static host will
serve. Do not introduce a dependency or a build toolchain without asking; the whole point is that
one volunteer can still run this in two years.

```
scraper/   data layer — DartConnect fetch, the rules engine, player data, verification
site/      presentation layer — design tokens, shared fragments, the page builder
public/    GENERATED. Never hand-edit; every build deletes and recreates it.
design/    the mockups and the two logo assets
data/      the archive: data/seasons/<id>/ per DartConnect season (recaps/, matches.json,
           standings.json, fixtures.json), and data/seasons.json listing every season of both leagues
docs/      rulebook, design brief, exports
```

| File | Role |
|---|---|
| `scraper/fetch.py` | **The only module that touches the network.** Both leagues (`LEAGUES`: Tuesday `ParkSDL`, Monday `ParkSlopeDLM`). Discovers each league's seasons into `data/seasons.json`; archives each recap to `data/seasons/<id>/recaps/` on first fetch; refreshes a season's `matches.json`, `standings.json` and `fixtures.json` while it is active. |
| `scraper/allstar.py` | Rules engine — Rulebook Section F applied to turn data. Emits individual hits. |
| `scraper/players.py` | Player → team, form stats recomputed from turns (`form_sums` per season, added up across seasons by `combined_form` for a player page's All Time), the per-division ranked table with PPL — points per leg played, legs from `legs_played` — the All Time table (`career_table`), who a name is across seasons (`identity`), nights played (GP) and playoff eligibility (`SEASON_NIGHTS`, `playoff_minimum`). |
| `scraper/awards.py` | Season-end award data — 171+ Club, Big Fish, R9 Club, C5+, largest checkout/check-in, division leaders. Pure functions over hits; build.py passes one night's hits (awards are per night, owner 2026-11-12). |
| `scraper/events.py` | `load_season(id)` — assembles one season from the archive (no id: the Tuesday league's current season); `load_all()` (merges eligible stages), `season_order()`, `base_label()`, `merge_stages()`, `registry()`, `current_id(league)`. The single entry point `site/` uses. |
| `scraper/fixtures.py` | Match nights still to come, from a season's `fixtures.json` — the Schedule tab. Also New York time (`eastern_offset`, `league_today`). Pure, offline. |
| `scraper/feed.py` | News feed events for both nights' current seasons, night by night; check-in and checkout records per night (matching Awards). Also `standings_by_night(season)` — cumulative standings from each side's own `points` field, used by verify. |
| `scraper/verify.py` | Assertion suite. Run before publishing. |
| `scraper/standings.py` | Terminal view of the same data the site renders. Debugging aid. |
| `site/tokens.py` | The palette and type from DESIGN-SPEC, in one place, emitted as `public/app.css`. The stylesheet is the phone layout, then a "wider screens" section of `@media (min-width)` rules (breakpoints `WIDE` 768 and `DESKTOP` 1024, column `MAIN` 880). |
| `site/components.py` | Shared fragments: page shell, header, sub-header (back links), status bar, the season/league picker, division nav, chips, icons, recap links. |
| `site/app.js` | Progressive enhancement only — search filter, long-table collapse, back-link history, the schedule's filters and live night, closing a picker on an outside tap or Escape. |
| `site/build.py` | Renders all pages into `public/`: every season's All-Stars boards (with the season picker) and All Time, one career page per player, the schedule, standings, team pages (reached from standings), awards, the feed. Every link and write goes through `board_href` / `player_href` / `team_href`. |

Run it:

```bash
python3 scraper/fetch.py     # pull any new matches — the only networked step
python3 scraper/verify.py    # assertion suite
python3 site/build.py        # regenerate public/, offline
open public/index.html
```

`fetch.py` → `verify.py` → `build.py`, in that order. **Never publish a build whose verify failed.**

## Non-negotiables — design

1. **Three colours only** — logo black `#211C1D`, gold `#C59940`, white. Shades of the black
   for surfaces. Do not add a colour without asking, and define every colour in
   **`site/tokens.py`** — never hardcode a hex in `build.py` or `components.py`.
2. **The logo is used unaltered**, on a white circular plate (its outline is near-black and
   would vanish on the dark ground).
3. **Never rank players across divisions.** Division 1 scores far more than Division 5.
   **Exceptions, both deliberate:** the Largest Checkout and Largest Check-In awards rank across
   divisions because the league awards them league-wide (the award pages say so); and the
   All-Stars **ALL** board (`all.html`, `players.league_table`) numbers every scoring player
   league-wide because the owner asked for it (2026-11-11). That board crowns nobody — no leader
   card, no gold top three — names each player's division on every row, and says a league rank
   reflects the division as much as the player. The same holds for every past season's ALL board,
   and for **All Time** (`all-stars-all-time.html`, `players.career_table`, 2026-11-12): every
   season of both nights on one list, with no division chips at all, because divisions change
   between seasons. Every other page still ranks within division only.
   The old "Division 1 scores roughly 2.5× Division 5" caption is gone at the owner's request
   (2026-11-12) — it was a week-1 figure — and `check.py` fails any page that brings it back.
4. **Never render an empty stat column.** The median player has hits in exactly one category.
   Show the hits they actually have, as chips (`components.chips_for`).
5. **Every number links to its DartConnect turn** (`components.recap_link`). Traceability is the
   feature that makes an automated number trustworthy to a sceptical captain.
6. Fonts are **Anton** (display/numbers) and **Archivo** (everything else). Not Inter, not Roboto.
   Every numeric element carries `font-variant-numeric: tabular-nums` (the `.num` class).
7. Real controls (`<a>`, `<button>`, `<input>`+`<label>`), 44px minimum targets, AA contrast.
   The muted grey `#8E8889` and the on-gold brown `#443112` both sit at the 4.5:1 floor —
   **do not lighten either.**
8. **The site must work with JavaScript off.** Every row is in the markup; `app.js` only filters
   and collapses what is already there.
9. **Phones first** (owner, 2026-11-13). The phone layout is the stylesheet's base layer. A tablet
   or desktop only *adds* to it: every wider-screen rule sits in the "wider screens" section at
   the end of `tokens.stylesheet()`, inside an `@media (min-width: …)` of 768px or more, so no
   phone ever sees one. The markup is the same on every screen — never emit a desktop-only copy
   of anything. The tab bar stays the last thing in `.app`; from 768px the grid lifts it into the
   header's row. `check.py` section 16 enforces all of this.

## Non-negotiables — data

1. **Only `fetch.py` reaches the network.** `verify.py` and `build.py` read the archive on disk and
   must stay offline and reproducible — you can run a build a hundred times and nothing changes.
2. **The archive is immutable.** A recap is fetched once and never re-fetched or hand-edited.
   DartConnect owes us nothing and could change or withdraw access; once archived, the season is ours.
3. **Hits are the unit of truth.** `allstar.score_match()` emits individual hits; totals come from
   `allstar.aggregate()`. Never accumulate a total alongside the hits — a displayed total must not be
   able to drift from the hits shown beneath it.
4. **01 and cricket use deliberately opposite rules. Do not unify them.**
   01 is computed from raw `turn_score` (DartConnect flags at 100+, PSDL's threshold is 95+, so
   trusting their flag silently drops every 95–99 all star). Cricket is read straight from `notable`,
   which is already DartConnect's count of marks that *counted*.
5. **DartConnect names are authoritative as-is.** No alias maps, no fuzzy matching against legacy
   names. Normalise display artifacts only (`players.clean_name`), and note that `Colin  Ratner`'s
   double space is real — preserve it, escape it for display (`components.esc`), wrap rather than
   truncate a long name. **One exception, by the owner (2026-11-12):** across seasons and nights, two
   names that differ only in spacing, punctuation or capitals are one player
   (`players.identity` — letters and digits, case ignored). DartConnect keeps a separate record per
   league, and eight people's Monday and Tuesday records differ that way (`Johnny  Colonna` /
   `Johnny Colonna`, `Angelo Oddo` / `Angelo Oddo |||`). Every page still *shows* each season's
   name as DartConnect has it; only the player page and All Time join them. A name that differs in
   any letter — a nickname, a misspelling — stays a separate player.
6. **Source the team list from standings competitors** (31 teams on Tuesday), never
   `schedule['teams']` (35, the filter dropdown) and never from played matches (30 with only Week 1
   archived — Division 1 has 7 teams, so someone has a bye). Likewise divisions: from standings
   `competitors`, never `leagueDivisions`, which keeps divisions that no longer have teams.
7. **Never match a team by name across feeds — use DartConnect's stable team `id`.** The archive is
   immutable, so a recap holds the team name from match night and carries no id; `standings.json` and
   `matches.json` are refetched every run and carry today's name plus the id. Three teams were renamed
   mid-season in Fall 2026. `players.resolve_sides()` joins a recap to its schedule row for the id and
   `players.canonical_teams()` resolves the id to the current name. This is not an alias map (see 5) —
   it is DartConnect's own identity, and it raises rather than guessing.
   Fixtures resolve the same way (`fixtures.upcoming()`).
8. **No bracketed placeholder may reach a real page.** `build.py` scans its own output and fails the
   build if one does. If a value is unknown, omit the element — see `ALL_STAR_CUT = None`, and
   `players.SEASON_NIGHTS`: a season it does not list shows GP with no playoff check marks.
9. `summary.md` holds the rest of the hard-won specifics (`ending_marks` is points not marks;
   `darts_thrown` only exists for the checkout player; averages are singles-only; a leg counts for
   every player in its turns, not just its opener, and DartConnect's set and game numbers are not a
   unique leg id). Read it before touching `players.py`.
10. **Future fixtures come from DartConnect's lineups feed, not `matches.json`.** `matches.json` only
    ever lists matches that have started; `POST api/league/ParkSDL/lineups/{season}` lists every match
    not yet complete, saved as `data/fixtures.json`. On the Schedule, HOME is the team DartConnect
    lists first (`left`) — DartConnect's own live view does the same, and the owner chose it
    (2026-11-11). That is a *scheduling* label: the side recorded as home on match night matches
    `left` only about half the time, so never use `left` to label a played match (ROADMAP finding #8).
    Whether a night is live comes from the clock in the browser — the site never rebuilds on a
    Tuesday night.
11. **Two leagues, many seasons — and DartConnect's API ignores the league in its URLs.** PSDL plays
    Tuesday (`ParkSDL`) and Monday (`ParkSlopeDLM`); DartConnect has both back to Fall 2025 and
    nothing older. `/api/league/ParkSDL/matches/25432` happily returns *Monday's* season 25432, so a
    season id is only ever requested under the league whose page listed it, and `fetch.py` checks
    standings, schedule, recaps and fixtures against that league before writing them; `verify.py` §12
    checks it again. Team ids are per season (resolve within the season). A Monday recap's
    `division_title` reads `"Division: PS Monday"` — hits take the schedule's division
    (`score_match(division=…)`). A week is a DartConnect round (`round_seq`), not a date: make-up
    nights gave Fall 2025 23 dates over 15 rounds. A league's **current** season is its latest with
    an archived recap (`events.current_id`) — not DartConnect's `active` flag, which a new season
    gets weeks before its first match night.
12. **`home_league_points` / `away_league_points` belong to the recorded home side, not to
    `left`.** A match's `left` is the side DartConnect lists first; `home` is the side recorded as
    home on match night, and that is `left` only about half the time. Use `left.points` /
    `right.points` — each side's own points field. `feed.standings_by_night()` and verify §14
    confirm this reproduces DartConnect's `league_points` and `matches` exactly across all six
    seasons.

## Data source

Scores come from **DartConnect**, the scoring system used at the board — no manual entry. Recap
pages are a Laravel/Inertia app, so the full match payload arrives as JSON — no HTML parsing, no
CSS selectors to break.

**But where that JSON sits is not stable.** Inertia embeds it two ways, and DartConnect has used
both: HTML-escaped in the root element's `data-page` **attribute**, and raw in the **body** of
`<script data-page="app" type="application/json">`. `recap.dartconnect.com` switched to the second
on 2026-10-28 while `tv.dartconnect.com` stayed on the first. `fetch._inertia_props()` tries both
and lets a successful JSON parse decide — **never infer the shape from the host, and never assume
the `data-page` attribute holds the payload** (on the new form it holds the literal string `"app"`,
so a regex on it still matches and then fails to parse).

Out of scope: login/accounts, score entry, live in-match updates. Historical seasons came into
scope on 2026-11-12 — as far back as DartConnect goes (Fall 2025), and no further.

## Where things stand

The site is **live** at <https://psdartleague.com/>, rebuilt the morning after each match night by
`.github/workflows/build.yml`. `site/build.py` generates **433 pages** from 519 archived matches
across six seasons of both nights — 347 player pages (one per player, every season they have
scored in), 38 team pages (31 Tuesday, 7 Monday), the current Tuesday season's 5 division
leaderboards + the ALL board, 17 boards for the other five seasons and All Time, 6 standings pages
(Tuesday's five, Monday's one), 2 awards indexes (one per night) and 14 award detail pages (7 per
night), two schedules (Tuesday, Monday), the feed, and three aliases: `index.html` /
`standings.html` (Division 1) and `matches.html` (the schedule, so links to the old Match tab
still work) — and `scraper/verify.py` and `site/check.py` both pass.

**PSDL plays two nights** (2026-11-12): Tuesday (`ParkSDL`, five divisions) and Monday
(`ParkSlopeDLM`, one division, "PS Monday"); most teams play both. Standings and the Schedule have a
**league picker** — Tuesday night first, as the tabs open — and each night's team pages are its own
(Monday's are `team/monday-…`). Awards are **per night** behind the LEAGUE picker (owner,
2026-11-12): `awards.html` for Tuesday, `awards-monday.html` for Monday, with award detail pages
at `award/<key>.html` and `award/monday-<key>.html`; Largest Check-In and Largest Checkout are
awarded separately for each night. The Feed is **the league at large**: both nights' current
seasons, grouped by night heading. The All-Stars tab has a **season picker**
above the division chips: All Time, then every season of both nights, newest first with Tuesday
before Monday inside each season (owner, 2026-11-12). Monday's Spring 2026 "Stage 1" and "Stage 2"
are merged into one season of 73 players (`events.merge_stages`); stages merge when same base label,
same league, none current, and the first stage has one division. The home page is still the
current Tuesday season's Division 1. A past season's boards say FINAL and that they are recomputed
by this site's rules; a player page covers every season, and a season's board opens that season's
section of it.

The tab bar is Standings · All-Stars · Schedule · Feed · Awards: at the bottom on a phone, at the
right of the header from 768px, where the content opens out into a centred column up to 880px
(2026-11-13; DESIGN-SPEC "Wider screens"). The Schedule tab
(2026-11-11) replaced the Match tab and its 131 per-match pages: it lists every match night still to
come — home v away, division by division, with a division menu and team search — and gilds tonight's
matches while they are on. There is no Teams tab or teams index any more (retired 2026-11-11): a team
page is opened by tapping its row on Standings (or a team on the Schedule), and lists the whole
roster — scorers first, then teammates with no all star hits yet — with each player's GP (league
nights played), singles '01 average and MPR, and a gold check mark beside every player who is playoff
eligible (Rulebook §H.2; the season length per division is `players.SEASON_NIGHTS`, confirmed by the
owner for Tuesday — Monday's is not known yet, so Monday team pages show GP with no ticks). The Feed
tab lists both nights' notable moments, newest night first.

GitHub Pages hosts the site; the domain is registered at Vercel, which serves its DNS and nothing
else. The domain is a repo setting (Settings → Pages), not a file — do not add a `CNAME` file, which
an Actions deploy ignores. The DNS records are listed in `README.md`.

The workflow commits the archive *before* the verify gate, on purpose. A side effect worth knowing:
**a broken gate is invisible from the site** — recaps keep accumulating in the repo while the
published pages freeze on the last good build. Check `gh run list`, not the site. This is exactly
what happened from 2026-09-21 to 2026-10-02; see `summary.md`'s session log.

Not done: **commissioner reconciliation** (the gate before the numbers become official), forfeit
exception handling, and `docs/ROADMAP.md` Steps 4–16 (the wider league website). Steps 2 (pipeline
hardening) and 3 (season-scoped archive) are complete.

`fetch.py` carries on past a recap it cannot fetch or parse and reports it at the end (ROADMAP
Step 2); the next run picks it up. The 2026-11-12 backfill showed why: DartConnect's recap server
timed out on 7 of 384 requests, and a second run fetched all 7 in seconds.

One design placeholder is still open and genuinely needs the league: **how many players per division
make All Star** (`ALL_STAR_CUT`). Team rosters and MPR, both previously listed as blockers, were
resolved from the data itself.
