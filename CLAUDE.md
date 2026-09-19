# PSDL All Star app — conventions

A mobile web app for the Park Slope Dart League (Brooklyn, Tuesday nights) showing **All Star
Points** and the **league standings**. Replaces a 29-column spreadsheet site that, per the
commissioners, almost nobody reads — and 2–3 hours a week of commissioner data entry.

## Start here

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
data/      archived DartConnect payloads (data/recaps/) plus schedule and standings
docs/      rulebook, design brief, exports
```

| File | Role |
|---|---|
| `scraper/fetch.py` | **The only module that touches the network.** Archives each recap to `data/recaps/` on first fetch. |
| `scraper/allstar.py` | Rules engine — Rulebook Section F applied to turn data. Emits individual hits. |
| `scraper/players.py` | Player → team, form stats recomputed from turns, the per-division ranked table. |
| `scraper/events.py` | `load_season()` — assembles the season from the archive. The single entry point `site/` uses. |
| `scraper/verify.py` | Assertion suite. Run before publishing. |
| `scraper/standings.py` | Terminal view of the same data the site renders. Debugging aid. |
| `site/tokens.py` | The palette and type from DESIGN-SPEC, in one place, emitted as `public/app.css`. |
| `site/components.py` | Shared fragments: page shell, header, status bar, division nav, chips, icons, recap links. |
| `site/app.js` | Progressive enhancement only — search filter, long-table collapse. |
| `site/build.py` | Renders all six screens into `public/`. |

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
3. **Never rank players across divisions.** Division 1 scores ~2.5× Division 5.
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
   truncate a long name.
6. **Source the team list from standings competitors** (31 teams), never `schedule['teams']` (35, the
   filter dropdown) and never from played matches (30 — Division 1 has 7 teams, so someone has a bye).
7. **No bracketed placeholder may reach a real page.** `build.py` scans its own output and fails the
   build if one does. If a value is unknown, omit the element — see `ALL_STAR_CUT = None`.
8. `summary.md` holds the rest of the hard-won specifics (`ending_marks` is points not marks;
   `darts_thrown` only exists for the checkout player; averages are singles-only). Read it before
   touching `players.py`.

## Data source

Scores come from **DartConnect**, the scoring system used at the board — no manual entry. Recap
pages are a Laravel/Inertia app, so the full match payload arrives as JSON in the page's
`data-page` attribute; there are no CSS selectors to break.

Out of scope: login/accounts, score entry, live in-match updates, historical seasons.

## Where things stand

The rules engine and the app both work. `site/build.py` generates **165 pages** from the archived
Week 1 data — 104 player pages, 15 match pages, 30 team pages, 5 division leaderboards, 5 standings
pages, three indexes and the rare-hit screen — and `scraper/verify.py` passes.

Not done: **hosting** (nothing is deployed), **commissioner reconciliation** (the gate before the
numbers become official), scheduled weekly runs, and forfeit exception handling.

One design placeholder is still open and genuinely needs the league: **how many players per division
make All Star** (`ALL_STAR_CUT`). Team rosters and MPR, both previously listed as blockers, were
resolved from the data itself.
