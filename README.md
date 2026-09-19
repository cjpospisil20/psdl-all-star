# PSDL All Star Points

A static site that publishes **All Star Points** and the **league standings** for the
Park Slope Dart League — a Brooklyn pub darts league that plays Tuesday nights.

All Star Points reward throws of significance (95+ in 01, big cricket rounds, 180s,
9-marks). Section F of the PSDL rulebook defines them; at season's end each division
crowns its All Stars. This site replaces a 29-column spreadsheet that, per the
commissioners, almost nobody read.

Every number comes from **DartConnect**, the scoring system used at the board — there is
no manual entry — and every number on the site links back to the DartConnect turn that
produced it. That traceability is the feature: it is what makes an automated number
trustworthy to a sceptical captain.

## Running it locally

You need nothing but `python3`. There are **no third-party dependencies** — the scraper
and the site generator are pure standard library, deliberately, so any volunteer can run
this on any machine. There is no `requirements.txt` and no virtualenv to set up.

```sh
python3 scraper/fetch.py     # archive new matches from DartConnect
python3 site/build.py        # generate the site into public/
```

Then open `public/index.html` in a browser.

`fetch.py` skips every match it has already archived, so re-running it is cheap: it only
pulls what is new. A full season is roughly 180 matches, and requests are spaced 1.5
seconds apart to be a polite guest on DartConnect's servers.

`build.py` never touches the network. It reads only what `fetch.py` has archived, so a
build is offline and reproducible — you can rebuild the whole site on a plane.

## Verifying the numbers

```sh
python3 scraper/verify.py
```

This is the gate that stops wrong numbers being published. It asserts the season totals
against a validated baseline, checks that every player's individual hits sum to their
displayed total, that no player appears on two teams, that busts never score, that
cricket values match the rulebook table, and that every hit links to its recap. It exits
non-zero if anything fails.

The assertions encode the rules that were hard to get right and the bugs that were
actually found during development. They exist to stop those bugs coming back. **Run it
before publishing anything by hand, and never publish numbers it rejects.**

For a quick look at exactly what the site will render:

```sh
python3 scraper/standings.py --top 25
python3 scraper/standings.py --division "Division 1" --csv /tmp/div1.csv
```

## How the weekly automation works

`.github/workflows/build.yml` does the whole job on its own. It runs:

- **on a schedule** — 07:00 UTC Wednesday, which is 02:00–03:00 Wednesday morning in
  Brooklyn, a few hours after the last Tuesday-night board finishes. A second, identical
  pass runs Thursday at the same hour to cover the case where GitHub delays or drops the
  Wednesday run.
- **on demand** — the "Run workflow" button on the repository's Actions tab.
- **on push** to the default branch, so a code change republishes immediately.

Each run, in order:

1. `fetch.py` — archives any new match recaps.
2. **Commits the new archive files back to this repository.** This happens *before*
   verification, on purpose: see below.
3. `verify.py` — **if this fails, the run fails and nothing is deployed.**
4. `build.py` — generates `public/`.
5. Uploads `public/` and deploys it to GitHub Pages.

GitHub's cron is always in UTC and does not follow US daylight saving, so the run time
drifts by an hour against New York twice a year. The 07:00 UTC slot has hours of slack on
both sides, so the drift never matters. The reasoning is written out in comments at the
top of the workflow file.

### Repository setting this depends on

In **Settings → Pages**, the build and deployment **Source** must be set to
**GitHub Actions** (not "Deploy from a branch"). The workflow will fail at the deploy
step until that is done. This is a one-time, manual setting — a workflow cannot set it
for you.

## The archive is permanent — keep it committed

`data/recaps/*.json` holds the raw DartConnect payload for every match ever fetched. It
is committed to this repository and it must stay that way.

DartConnect owes this league nothing. It could change its page format or withdraw access
at any time, and the two endpoints the scraper uses are public and unauthenticated —
which is to say, not promised to anyone. Once a match payload is archived, it is ours
permanently, and everything the site publishes is recomputed from those files.

That is also why the automation commits the archive *before* running verification. A
failed check should block publishing, not throw away data that may be unfetchable later.
Committing is not publishing; the deploy is still gated on `verify.py` passing.

`public/` is generated and is **not** committed — `build.py` deletes and recreates the
whole directory on every run.

## Where the design contract lives

**`DESIGN-SPEC.md`** is the contract. Read it before changing any UI. It carries the
exact palette, the type choices, the stat vocabulary, the hard requirements, and — usefully
— an explicit list of which numbers in the mockups are real versus placeholder.

`design/*.html` are six static mockups of the finished screens; open `design/index.html`
to see them side by side. They are the visual target, not application code.

The non-negotiables, in short:

1. **Three colours only** — logo black `#211C1D`, gold `#C59940`, white, plus shades of
   the black for surfaces.
2. The logo is used **unaltered**, on a white circular plate.
3. **Never rank players across divisions.** Division 1 scores roughly 2.5× Division 5.
4. **Never render an empty stat column.** The median player has hits in exactly one
   category; show the hits they actually have, as chips.
5. **Every number links to its DartConnect turn.**
6. Fonts are **Anton** (display and numbers) and **Archivo** (everything else).
7. Real controls, 44px minimum touch targets, WCAG AA contrast.

The palette lives in code exactly once, in `site/tokens.py`. Change a colour there, not
in a template.

## What is where

```
scraper/
  fetch.py       DartConnect fetch + the permanent archive. League and season IDs live here.
  allstar.py     The All Star Points rules engine (Section F of the rulebook).
  events.py      Loads the archive and scores the whole season. Never touches the network.
  players.py     Team membership, form stats, division ranks.
  standings.py   Command-line view of the standings, for debugging.
  verify.py      The assertion suite. The publishing gate.
site/
  build.py       Generates public/.
  components.py  Shared page fragments, lifted from the mockups.
  tokens.py      The design system as code. The only place colours are defined.
data/
  recaps/*.json  The permanent archive, one file per match. Committed.
  matches.json   Season schedule. Refreshed each run.
  standings.json League standings. Refreshed each run.
design/          The six mockups and the logo assets.
docs/            The original design brief and the PSDL rulebook.
public/          Generated output. Not committed.
```

## Things an inheriting volunteer should know

**A new season needs a new season ID.** `scraper/fetch.py` opens with:

```python
LEAGUE = "ParkSDL"
SEASON = 25174                  # Fall 2026
```

When the league starts a new season, `SEASON` has to be bumped. Find the new number in
the DartConnect league URL. Nothing else in the pipeline is season-specific.

**`verify.py`'s baseline is a fixed one.** Its first three assertions compare the season
to a hand-validated week-1 snapshot:

```python
EXPECTED_WEEK1 = {"players": 104, "points": 20326, "busts": 437}
```

That is exactly right for the 15 matches archived today, and it is what makes the suite
trustworthy. But those three numbers grow every week the league plays. **The first time a
week-2 match is archived, those three checks will fail and the automation will refuse to
deploy.** That is the suite doing its job — an unexplained change in the totals *should*
stop a publish — but somebody has to then re-validate the new totals by hand and update
the baseline. Do not simply delete the check. Expect to do this, and budget a few minutes
for it on the first Wednesday of the season.

**Three questions are still open with the league**, and they are why some things are
absent rather than guessed at (`DESIGN-SPEC.md` lists them in full):

1. How many players per division make All Star? Until the league says, the cut line is
   omitted rather than shipped as a placeholder.
2. Full team rosters — which player is on which team.
3. Whether MPR comes through the DartConnect export.

**When a placeholder reaches a page, the build fails.** `build.py` scans its own output
for bracketed markers and exits non-zero if it finds one. A bracketed placeholder must
never reach a real page.
