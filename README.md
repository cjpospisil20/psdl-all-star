# PSDL All Star Points

A static site that publishes **All Star Points** and the **league standings** for the
Park Slope Dart League — a Brooklyn pub darts league that plays two nights, Monday and
Tuesday, each its own league on DartConnect. Standings and the schedule show one night at a
time; the All-Stars boards go back through every season since Fall 2025, with an All Time list;
Awards and the news feed cover both nights together.

All Star Points reward throws of significance (95+ in 01, big cricket rounds, 180s,
9-marks). Section F of the PSDL rulebook defines them; at season's end each division
crowns its All Stars. This site replaces a 29-column spreadsheet that, per the
commissioners, almost nobody read.

Every number comes from **DartConnect**, the scoring system used at the board — there is
no manual entry — and every number on the site links back to the DartConnect turn that
produced it. That traceability is the feature: it is what makes an automated number
trustworthy to a sceptical captain.

It also carries the **schedule** — every match night still to come, home v away, by division,
with tonight's matches highlighted in gold while they are being played.

The site is live at **<https://psdartleague.com>**.

## Running it locally

You need nothing but `python3`. There are **no third-party dependencies** — the scraper
and the site generator are pure standard library, deliberately, so any volunteer can run
this on any machine. There is no `requirements.txt` and no virtualenv to set up.

```sh
python3 scraper/fetch.py     # archive new matches from DartConnect
python3 site/build.py        # generate the site into public/
```

Then open `public/index.html` in a browser.

`fetch.py` covers both of the league's nights — the Tuesday league (`ParkSDL` on
DartConnect) and the Monday league (`ParkSlopeDLM`) — and every season DartConnect still
lists for them, back to Fall 2025. It skips every match it has already archived, so
re-running it is cheap: it only pulls what is new. A Tuesday season is roughly 180 matches
and a Monday one about 30, and recap requests are spaced 1.5 seconds apart to be a polite
guest on DartConnect's servers. (A fresh clone already has the archive committed; fetching
every season from nothing would take about 15 minutes.)

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

### Repository settings this depends on

In **Settings → Pages**, the build and deployment **Source** must be set to
**GitHub Actions** (not "Deploy from a branch"). The workflow will fail at the deploy
step until that is done. This is a one-time, manual setting — a workflow cannot set it
for you.

The same screen holds the **custom domain**, `psdartleague.com`, with **Enforce HTTPS**
ticked. Do not add a `CNAME` file to `public/`: GitHub ignores it when a site deploys from
Actions, so that setting is the only place the domain lives. Old
`cjpospisil20.github.io/psdl-all-star/` links redirect to the domain. After changing anything
on that screen, re-run the workflow from the Actions tab: an Actions-deployed site only picks
up some settings, Enforce HTTPS among them, on its next deploy.

The domain is registered at **Vercel**, which only answers its DNS. Vercel hosts nothing
here, and the domain must not be added to a Vercel project. The records, under Vercel →
Domains → psdartleague.com → DNS Records:

| Type | Name | Value | Why |
|---|---|---|---|
| A ×4 | *(blank — the apex)* | `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153` | GitHub Pages |
| CNAME | `www` | `cjpospisil20.github.io` | `www` redirects to the apex |
| TXT | `_github-pages-challenge-cjpospisil20` | the code GitHub issued | verifies the domain for CJ's GitHub account, so no other account can claim it |

Vercel's own default records cannot be deleted; the records above override them. Its
default CAA records already allow Let's Encrypt, which is where GitHub gets the HTTPS
certificate, so leave them alone. Moving the repo to a GitHub organization means
re-verifying the domain first — see `docs/ROADMAP.md` §1.

## The archive is permanent — keep it committed

`data/seasons/<season id>/recaps/*.json` holds the raw DartConnect payload for every match
ever fetched, one directory per season of either league. It is committed to this repository
and it must stay that way.

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
3. **Never rank players across divisions.** Division 1 scores far more than Division 5.
   (Exceptions: the Largest Checkout and Largest Check-In awards are league-wide by rule, and the
   All-Stars ALL boards and All Time list everyone at the owner's request — no leader card,
   division on every row.)
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
  fetch.py       DartConnect fetch + the permanent archive. The two league IDs live here;
                 seasons are discovered from DartConnect on every run.
  allstar.py     The All Star Points rules engine (Section F of the rulebook).
  events.py      Loads the archive and scores the whole season. Never touches the network.
  fixtures.py    Match nights still to come, for the Schedule tab. New York time, by hand.
  feed.py        News feed events, week by week.
  awards.py      Season-end award data (171+ Club, Big Fish, largest checkout/check-in, leaders).
  players.py     Team membership, form stats, division ranks.
  standings.py   Command-line view of the standings, for debugging.
  verify.py      The assertion suite. The publishing gate.
site/
  build.py       Generates public/.
  components.py  Shared page fragments, lifted from the mockups.
  tokens.py      The design system as code. The only place colours are defined.
data/
  seasons.json   Every season of both leagues: id, league, night, label, start date.
  seasons/<id>/  One directory per DartConnect season, e.g. 25174 = Tuesday's Fall 2026:
    recaps/*.json  The permanent archive, one file per match. Committed.
    matches.json   Matches that have started (DartConnect lists nothing else here).
    standings.json League standings.
    fixtures.json  Every match not yet complete, from DartConnect's lineups feed.
                 The last three are refreshed each run while DartConnect calls the season
                 active, once more when it stops, and never again after that.
design/          The six mockups and the logo assets.
docs/            The original design brief and the PSDL rulebook.
public/          Generated output. Not committed.
```

## Things an inheriting volunteer should know

**A new season needs nothing from you.** `scraper/fetch.py` names the two leagues:

```python
LEAGUES = [("ParkSDL", "Tuesday"), ("ParkSlopeDLM", "Monday")]
```

and reads each league's season list from DartConnect on every run, so a new season is
archived as soon as DartConnect lists it, and becomes the one the site shows once its first
match is archived. Only a third night, or a league moving to a new DartConnect ID, means
editing that line.

**`verify.py`'s baseline is a fixed one, and stays fixed.** Its first assertions compare a
hand-validated snapshot — the 15 matches of week 1 of Tuesday's Fall 2026 (season 25174) —
with what the rules engine produces from them today:

```python
EXPECTED_WEEK1 = {"players": 104, "points": 20326, "busts": 437, "top": ("Tom Lettieri", 835)}
```

It is scoped to those 15 match IDs and that season, so new weeks and new seasons never move it.
If it ever fails, the scoring rules changed. That is the suite doing its job — find out why
before publishing, and do not simply delete the check.

**Three questions are still open with the league**, and they are why some things are
absent rather than guessed at (`DESIGN-SPEC.md` lists them in full):

1. How many players per division make All Star? Until the league says, the cut line is
   omitted rather than shipped as a placeholder.
2. Full team rosters — which player is on which team.
3. Whether MPR comes through the DartConnect export.

**When a placeholder reaches a page, the build fails.** `build.py` scans its own output
for bracketed markers and exits non-zero if it finds one. A bracketed placeholder must
never reach a real page.
