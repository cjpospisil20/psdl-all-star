"""Generate the PSDL All Star site into public/.

    python3 site/build.py

Reads only what fetch.py has archived, so builds are reproducible and work offline.
"""
import collections, datetime, pathlib, re, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scraper"))
sys.path.insert(0, str(ROOT / "site"))

import allstar, awards, events, feed, fixtures, players  # noqa: E402
import components as C, tokens                       # noqa: E402
from components import esc, icon                     # noqa: E402

OUT = ROOT / "public"

# How many players per division make All Star. The league has not set this yet; until they do,
# the cut line is omitted rather than shipped as a bracketed placeholder.
ALL_STAR_CUT = None

PREVIEW_ROWS = 10          # rows before "show all"

# The logo assets the pages use. design/assets/ also holds the reversed wordmark, which only the
# first-180 celebration screen used. That screen was retired on 2026-11-12 -- the Feed and Awards
# celebrate 180s now -- so the wordmark stays in design/ but is not shipped: check.py fails a build
# that ships an asset no page references.
SHIPPED_ASSETS = ("psdl-mark.png",)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


# ---------------------------------------------------------------- seasons, boards and links
#
# The archive holds every season of both nights (events.load_all). The Tuesday league's current
# season is the "home" season: it keeps the URLs the site has always had (index.html,
# division-N.html, all.html). Every other season's boards are all-stars-<season key>[-division].html,
# and All Time is all-stars-all-time.html. Every link and every write goes through these helpers,
# so a link can never point at a page the build did not write.

ALL_TIME = "all-time"

# Each player's page is one page for every season they have scored in, keyed by players.identity()
# -- so a player whose Monday and Tuesday names differ only in spacing, punctuation or capitals has
# one page. Filled by plan_sections() before any page that links a player is built:
#   SECTIONS  identity -> the season keys of the page's sections, in page order
#   SPELLING  (identity, season key) -> the name exactly as DartConnect has it that season
#   PAGE      identity -> the page's file name, from the name in its first section
SECTIONS, SPELLING, PAGE = {}, {}, {}

RECOMPUTED = (" A finished season is recomputed from DartConnect by this site&rsquo;s rules, so "
              "its points may differ from what the league awarded at the time.")


def is_home(season):
    """The Tuesday league's current season -- the one the site has always shown."""
    return bool(season) and season["primary"] and season["current"]


def board_href(season, division=None, up=""):
    """An All-Stars board. `season` None is All Time; `division` None is the season's ALL board,
    or its only board when it has a single division."""
    if season is None:
        return f"{up}all-stars-all-time.html"
    if is_home(season):
        return f"{up}{slug(division)}.html" if division else f"{up}all.html"
    if division is None or len(season["divisions"]) == 1:
        return f"{up}all-stars-{season['key']}.html"
    return f"{up}all-stars-{season['key']}-{slug(division)}.html"


def standings_href(season, division=None, up=""):
    """A league's standings page, for its current season. The Tuesday league keeps the names it
    always had (standings.html for Division 1, standings-division-N.html); another night's are
    standings-<night>.html, plus standings-<night>-<division>.html if it has several divisions."""
    if season["primary"]:
        return f"{up}standings-{slug(division)}.html" if division else f"{up}standings.html"
    base = f"standings-{season['night'].lower()}"
    if division is None or len(season["divisions"]) == 1:
        return f"{up}{base}.html"
    return f"{up}{base}-{slug(division)}.html"


def schedule_href(season, up=""):
    """A league's Schedule: schedule.html for Tuesday, schedule-<night>.html for another night."""
    return (f"{up}schedule.html" if season["primary"]
            else f"{up}schedule-{season['night'].lower()}.html")


def team_href(team, season, up=""):
    """Where a team's page lives. The standings link and the page write both come through here,
    so a link can never point at a file the build did not write. Another night's teams are
    prefixed with it (team/monday-…), so a team playing both nights under one name keeps two
    pages -- one per league, as DartConnect has it."""
    prefix = "" if season["primary"] else f"{season['night'].lower()}-"
    return f"{up}team/{prefix}{slug(team)}.html"


def league_picker(leagues, here, division, href):
    """The league picker on Standings and the Schedule: one option per night, each that league's
    current season. The current option is the page itself; the other opens that league's first
    page."""
    options = [(f"{s['night']} night", href(s, division if s is here else None), s is here)
               for s in leagues]
    return C.picker("LEAGUE", "League", here["night"].lower(), options)


def player_href(name, key=None, up=""):
    """A player's page, opened at the section for season `key`. The first section needs no
    fragment, so every link from the home season stays exactly as it always was."""
    who = players.identity(name)
    sections = SECTIONS.get(who) or []
    fragment = f"#{key}" if key and sections and key != sections[0] else ""
    return f"{up}player/{PAGE.get(who, slug(name))}.html{fragment}"


def season_name(season):
    return f"{esc(season['label'])} &middot; {season['night']}"


def season_status(season):
    """The status bar: the latest week while a season is live, FINAL once DartConnect closes it."""
    if season["active"]:
        return f"WEEK {season['latest_week']} · {events._pretty_date(season['latest_date'])}"
    return f"{season['label'].upper()} · {season['night'].upper()} · FINAL"


def plan_sections(seasons):
    """Which seasons each player's page has a section for, in display order, and what DartConnect
    called them in each. One identity under two names in ONE season would be two people or one
    person twice -- verify.py fails that, and the build refuses to guess which."""
    SECTIONS.clear(), SPELLING.clear(), PAGE.clear()
    for s in seasons:
        for rows in s["table"].values():
            for row in rows:
                who = players.identity(row["player"])
                if (who, s["key"]) in SPELLING:
                    raise RuntimeError(f"{row['player']!r} and {SPELLING[(who, s['key'])]!r} are "
                                       f"one player twice in {s['label']} {s['night']}")
                SPELLING[(who, s["key"])] = row["player"]
                SECTIONS.setdefault(who, []).append(s["key"])
                PAGE.setdefault(who, slug(row["player"]))


def picker_order(seasons):
    """The season picker's order: All Time, then each night's seasons, newest first -- Tuesday's
    first, as the primary league."""
    league_rank = {league: i for i, (league, _night) in enumerate(events.fetch.LEAGUES)}
    ordered = sorted(seasons, key=lambda s: s["id"])
    ordered.sort(key=lambda s: s["start_date"] or "", reverse=True)
    ordered.sort(key=lambda s: league_rank.get(s["league"], len(league_rank)))
    return ordered


def season_picker(seasons, here, division):
    """The All-Stars season picker for a board showing `here` (None: All Time) and `division`
    (None: an ALL board or All Time). Each option keeps the division when the other season has it,
    and otherwise opens that season's ALL board (or its only board)."""
    def target(season):
        if season is here:
            return board_href(here, division)
        if season is not None and division in season["divisions"]:
            return board_href(season, division)
        return board_href(season)

    options = [("All Time", target(None), here is None)]
    options += [(season_name(s), target(s), s is here) for s in picker_order(seasons)]
    return C.picker("SEASON", "Season", here["key"] if here else ALL_TIME, options)


# ---------------------------------------------------------------- all-stars

def find_box():
    return f"""  <label for="find" class="vh">Find a player</label>
  <div class="search">{icon("search", size=17)}
    <input id="find" type="search" placeholder="Find a player" autocomplete="off">
  </div>
"""


def show_all_button(label):
    return (f'  <button class="btn" id="show-all" type="button" hidden>{label}'
            f'{icon("chevron", tokens.COLOURS["gold"], 15)}</button>\n')


def build_all_stars(seasons, career):
    """Every season's boards, then All Time. The season picker on each links them all."""
    for season in seasons:
        build_season_boards(season, seasons)
    build_all_time(seasons, career)


def build_season_boards(season, seasons):
    """One season's boards: one per division, ranked within it, and -- when there is more than
    one division -- the ALL board. A one-division season (Monday's) is a single board."""
    table, divisions = season["table"], season["divisions"]
    several = len(divisions) > 1
    when = "this week" if season["active"] else "this season"
    recomputed = "" if season["active"] else RECOMPUTED
    named = "" if is_home(season) else f", {season['label']} {season['night']}"

    def top(current):
        parts = [C.header("ALL STAR POINTS"), C.statusbar(season_status(season)),
                 season_picker(seasons, season, current)]
        if several:
            parts.append(C.division_nav(divisions, current, lambda d: board_href(season, d),
                                        all_href=board_href(season)))
        return parts

    for division in divisions:
        rows = table.get(division, [])
        body = top(division)

        body.append(f"""  <div class="headline">
    <span><h1>{esc(division.upper())}</h1>
    <p>{len(rows)} player{'s' if len(rows) != 1 else ''} on the board {when}</p></span>
    <span class="note">RANKED WITHIN<br>DIVISION ONLY</span>
  </div>
""")
        body.append(find_box())

        for row in rows:
            if row["rank"] == 1:
                body.append(leader_card(row, key=season["key"]))
            else:
                body.append(player_row(row, extra=row["rank"] > PREVIEW_ROWS, key=season["key"]))
            if ALL_STAR_CUT and row["rank"] == ALL_STAR_CUT:
                body.append('  <div class="cutline"><b>ALL STAR CUT LINE</b><i></i></div>\n')

        body.append('  <p class="caption" id="no-match" hidden>No player by that name on the '
                    f'{esc(division)} board {when}.</p>\n')
        if len(rows) > PREVIEW_ROWS:
            body.append(show_all_button(f"SHOW ALL {len(rows)} IN {esc(division.upper())}"))

        ranked = ("This board ranks players against their own division only. " if several
                  else "")
        body.append(f'  <p class="caption">{ranked}Tap any player to see the turns behind the '
                    f'number.{recomputed}</p>\n')

        page = C.page(f"PSDL All Star — {division}{named}", "".join(body), "all-stars")
        write(board_href(season, division), page)
        if is_home(season) and division == divisions[0]:
            write("index.html", page)

    if not several:
        return

    # The ALL board: the one place a season's players are ranked across divisions, because the
    # owner asked for it. So it crowns nobody -- no leader card, no gold top three -- and every
    # row names its division, so a Division 1 total is never mistaken for a Division 5 one.
    everyone = players.league_table(table)
    body = top(None)
    body.append(f"""  <div class="headline">
    <span><h1>ALL DIVISIONS</h1>
    <p>{len(everyone)} player{'s' if len(everyone) != 1 else ''} on the board {when}</p></span>
    <span class="note">RANKED ACROSS<br>ALL DIVISIONS</span>
  </div>
""")
    body.append(find_box())
    for row in everyone:
        body.append(player_row(row, extra=row["league_rank"] > PREVIEW_ROWS,
                               rank="league", division=True, key=season["key"]))
    body.append('  <p class="caption" id="no-match" hidden>No player by that name on the '
                f'board {when}.</p>\n')
    if len(everyone) > PREVIEW_ROWS:
        body.append(show_all_button(f"SHOW ALL {len(everyone)} PLAYERS"))
    body.append('  <p class="caption">Every division on one board, highest points first. '
                'A league rank says as much about a player&rsquo;s division as about the player '
                '&mdash; pick a division above to compare like with like. Tap any player to see '
                f'the turns behind the number.{recomputed}</p>\n')
    write(board_href(season), C.page(f"PSDL All Star — All divisions{named}", "".join(body),
                                     "all-stars"))


def build_all_time(seasons, career):
    """All Time: every player's points from every season of both nights, on one list.

    Asked for by the owner (2026-11-12) as the first option of the season picker. Like the ALL
    board it ranks across divisions -- and across seasons and nights -- so it crowns nobody, names
    each player's division, and says so. It has no division chips: divisions change from season
    to season and players move between them, so "all-time Division 1" has no single meaning.
    """
    since = min(seasons, key=lambda s: (s["start_date"] or "", s["id"]))["label"]
    body = [C.header("ALL STAR POINTS"),
            C.statusbar(f"ALL TIME · SINCE {since.upper()}"),
            season_picker(seasons, None, None),
            f"""  <div class="headline">
    <span><h1>ALL TIME</h1>
    <p>{len(career)} player{'s' if len(career) != 1 else ''} since {esc(since)}, both nights</p></span>
    <span class="note">ALL SEASONS<br>BOTH NIGHTS</span>
  </div>
""", find_box()]
    for row in career:
        body.append(player_row(row, extra=row["league_rank"] > PREVIEW_ROWS,
                               rank="league", division=True))
    body.append('  <p class="caption" id="no-match" hidden>No player by that name on the '
                'All Time list.</p>\n')
    if len(career) > PREVIEW_ROWS:
        body.append(show_all_button(f"SHOW ALL {len(career)} PLAYERS"))
    body.append(f'  <p class="caption">Every season since {esc(since)}, Monday and Tuesday nights '
                'together, highest points first. A player&rsquo;s points from both nights count '
                'together, under the name DartConnect has for them. A rank here says as much about '
                'a player&rsquo;s division as about the player &mdash; pick a season above to '
                f'compare a division like with like.{RECOMPUTED} Tap any player to see the turns '
                'behind the number.</p>\n')
    write(board_href(None), C.page("PSDL All Star — All Time", "".join(body), "all-stars"))


def leader_card(row, up="", key=None):
    return f"""  <a class="leader" href="{player_href(row['player'], key, up)}"
     data-row="{esc(row['player'])} {esc(row['team'])}">
    <span class="leader-top">
      <span class="leader-rank num">{row['rank']}</span>
      <span class="leader-who">
        <b class="name">{esc(row['player'])}</b>
        <span class="name">{esc(row['team'])}</span>
      </span>
      <span class="leader-pts">
        <b class="num">{row['points']:,}</b>
        <span class="num">PPW {row['ppw']:g} &middot; AS {row['hits']}</span>
      </span>
    </span>
    <span class="chips">{C.chips_for(row['counts'], allstar.RARE)}</span>
  </a>
"""


def player_row(row, extra=False, up="", rank="division", division=False, key=None):
    """One leaderboard row.

    rank      what fills the rank column: "division" (the default; the top three are gold),
              "league" (the ALL board and All Time -- never gold, they crown nobody), or None to
              drop the column (the Awards index, where every row is a division leader).
    division  name the division beside the team, on any list that mixes divisions.
    key       the season the row is from, so the link opens that season's section of the
              player's page. None (All Time) opens the top of it.
    """
    rank_html = ""
    if rank == "division":
        top = " top" if row["rank"] <= 3 else ""
        rank_html = f'\n    <span class="row-rank num{top}">{row["rank"]}</span>'
    elif rank == "league":
        rank_html = f'\n    <span class="row-rank num wide">{row["league_rank"]}</span>'
    where = (f"{esc(row['division'])} &middot; {esc(row['team'])}" if division
             else esc(row["team"]))
    return f"""  <a class="row" href="{player_href(row['player'], key, up)}"
     data-row="{esc(row['player'])} {esc(row['team'])}"{' data-extra' if extra else ''}>{rank_html}
    <span class="row-main">
      <b class="name">{esc(row['player'])}</b>
      <small class="name">{where}</small>
      <span class="chips">{C.chips_for(row['counts'], allstar.RARE)}</span>
    </span>
    <span class="row-pts">
      <b class="num">{row['points']:,}</b>
      <span class="num">PPW {row['ppw']:g}</span>
    </span>
  </a>
"""


# ---------------------------------------------------------------- player

def build_players(seasons, career):
    """One page per player with an all star hit in any season of either night -- a player being
    a players.identity(), so names that differ only in spacing, punctuation or capitals share it.

    The page has a section per season (plan_sections), in display order: the current Tuesday
    season first when the player is in it, so every link from the home season needs no fragment.
    """
    rows = {s["key"]: {r["player"]: r for rs in s["table"].values() for r in rs} for s in seasons}
    hits = collections.defaultdict(list)
    for s in seasons:
        for h in s["hits"]:
            hits[(h["player"], s["key"])].append(h)
    by_key = {s["key"]: s for s in seasons}
    forms = {s["key"]: players.form_stats(s["recaps"]) for s in seasons}
    totals = {r["identity"]: r for r in career}
    since = min(seasons, key=lambda s: (s["start_date"] or "", s["id"]))["label"]

    for who, keys in SECTIONS.items():
        spelt = [SPELLING[(who, k)] for k in keys]
        sections = [(by_key[k], rows[k][name], sorted(hits[(name, k)], key=lambda h: -h["points"]))
                    for k, name in zip(keys, spelt)]
        form = forms[keys[0]].get(spelt[0], {})
        write(f"player/{PAGE[who]}.html",
              player_page(spelt[0], sections, form, totals[who], since))


def player_page(name, sections, form, total, since):
    """A player's page: every season they have scored in, one section each.

    `sections` is [(season, division-table row, hits)] in display order. The first section opens
    with the player's form for that season (singles averages, and MATCHES -- league nights played,
    the GP a team page shows, so the two always agree). Each section after it has the season's
    points and every hit behind them. A player with two or more seasons also gets an ALL TIME card.

    A player whose only section is the current Tuesday season gets the page they always had.
    """
    season, row, _hits = sections[0]
    named = len(sections) > 1 or not is_home(season)
    back_label = f"{row['division'].upper()} ALL-STARS"
    back_href = board_href(season, row["division"], up="../")
    # Every board that links here, so app.js can return to whichever the reader came from.
    back_from = [board_href(season, row["division"]), "index.html"]
    for s, r, _h in sections:
        for page in (board_href(s, r["division"]), board_href(s), board_href(None)):
            if page not in back_from:
                back_from.append(page)
    body = [C.subheader(back_label, back_href, back_from, up="../"),
            f"""  <div class="headline"><span>
    <h1 class="name">{esc(name)}</h1>
    <p class="name">{esc(row['division'])} &middot; {esc(row['team'])}</p>
  </span></div>
"""]

    if len(sections) > 1:
        body.append(f"""  <div class="card">
    <h2>ALL TIME &middot; {len(sections)} SEASONS</h2>
    <div class="statgrid three">
      <span class="stat"><b class="num">{total['points']:,}</b><small>POINTS</small></span>
      <span class="stat"><b class="num">{total['hits']}</b><small>HITS (AS)</small></span>
      <span class="stat"><b class="num">{total['ppw']:g}</b><small>PPW</small></span>
    </div>
    <p class="caption" style="margin:12px 0 0">Monday and Tuesday nights together, every season
    since {esc(since)}.</p>
  </div>
""")

    for i, (season, row, hits) in enumerate(sections):
        body.append(season_section(name, season, row, hits, form if i == 0 else None, named))
    return C.page(f"PSDL All Star — {name}", "".join(body), "all-stars", depth=1)


def season_section(name, season, row, hits, form, named):
    """One season of a player's page. `form` only for the first section; `named` heads the
    section with its season, which every page but a home-season-only one needs."""
    body = []
    if named:
        # A season whose DartConnect name differs from the page's (spacing, punctuation, capitals)
        # says so, because that season's board shows it under that name.
        listed = (f" &middot; listed as {esc(row['player'])}" if row["player"] != name else "")
        body.append(f"""  <div class="headline" id="{season['key']}"><span>
    <h2 class="section">{esc(season['label'].upper())} &middot; {season['night'].upper()}</h2>
    <p class="name">{esc(row['division'])} &middot; {esc(row['team'])}{listed}</p>
  </span></div>
""")
    nights = len(season["nights_by_player"].get(name, ()))
    if form:
        def stat(label, value, suffix=""):
            shown = "&mdash;" if value is None else f"{value}{suffix}"
            return f'<span class="stat"><b class="num">{shown}</b><small>{label}</small></span>'

        darts, days = (("THE DARTS &middot; SINGLES, SEASON TO DATE", "THIS SEASON")
                       if season["active"] else ("THE DARTS &middot; SINGLES", "THE SEASON"))
        body.append(f"""  <div class="card">
    <h2>{darts}</h2>
    <div class="statgrid">
      {stat("3-DART AVG", form.get("three_dart_avg"))}
      {stat("MARKS PER RD", form.get("mpr"))}
      {stat("FIRST 9", form.get("first_nine"))}
      {stat("CHECKOUT", form.get("checkout_pct"), "%")}
      {stat("LEG WINS", form.get("leg_win_pct"), "%")}
      {stat("OPP 3DA", form.get("opp_three_dart"))}
    </div>
  </div>
  <div class="card">
    <h2>{days}</h2>
    <div class="statgrid three">
      {stat("MATCHES", nights)}
      {stat("LEGS", form.get("legs"))}
      {stat("DARTS", f"{form.get('darts', 0):,}")}
    </div>
    <p class="caption" style="margin:12px 0 0">Averages cover singles legs only &mdash; in
    doubles the darts belong to the pair, so they cannot be split fairly. Checkout % counts
    turns taken with 170 or less remaining; that is our definition, not DartConnect&rsquo;s.</p>
  </div>
""")

    body.append(f"""  <div class="card">
    <h2>ALL STAR POINTS</h2>
    <div class="statgrid three">
      <span class="stat"><b class="num">{row['points']:,}</b><small>POINTS</small></span>
      <span class="stat"><b class="num">{row['hits']}</b><small>HITS (AS)</small></span>
      <span class="stat"><b class="num">{row['ppw']:g}</b><small>PPW</small></span>
    </div>
    <p class="caption" style="margin:12px 0 0">{ordinal(row['rank'])} of {row['of']} in
    {esc(row['division'])}. Ranked within division only.</p>
  </div>
""")

    body.append(f'  <div class="headline"><span><h2 class="section">THE {len(hits)} HIT'
                f'{"S" if len(hits) != 1 else ""}</h2>'
                f'<p>Tap any hit for the turn behind it</p></span></div>\n')

    best = max((h["turn_value"] for h in hits if h["game"] != "Cricket"), default=None)
    flagged = False
    for h in hits:
        detail = h["detail"]
        if not flagged and best and h["turn_value"] == best and h["game"] != "Cricket":
            detail, flagged = "Best turn of the season", True
        body.append(f"""  <div class="hit">
    <span class="chip{' rare' if h['rare'] else ''}">{esc(h['display'])}</span>
    <span class="hit-main">
      <b>{esc(detail)}</b>
      <small>{esc(h['game'])} &middot; {esc(events._pretty_date(h['date']))} &middot;
      {C.recap_link(h)}</small>
    </span>
    <span class="hit-val num">{h['points']}</span>
  </div>
""")
    return "".join(body)


def ordinal(n):
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


# ---------------------------------------------------------------- schedule

def build_schedule(season, leagues):
    """The Schedule tab for one night's league: every match night still to come, from
    DartConnect's lineups feed. Tuesday's is schedule.html, Monday's schedule-monday.html, and
    the league picker at the top switches between them (owner, 2026-11-12).

    Complete with JavaScript off -- every night and every fixture is in the markup, in date order.
    app.js adds the division and team filters, and works out from the clock which night is live
    (fixtures.py explains why a static build cannot know). Tonight is always the first night on
    the page, so a live night is already at the top: the script only gilds it, and hides nights
    that are over. That gilded first night is where a "watch live" link will go.

    Tuesday's is written to matches.html too, so links to the old Match tab still land somewhere
    useful. A one-division league keeps its division menu: app.js's filters hang on it.
    """
    nights = season["fixtures"]
    divisions = season["divisions"]
    to_play = sum(1 for night in nights for f in night["fixtures"] if "bye" not in f)
    picker = league_picker(leagues, season, None, lambda s, _d: schedule_href(s))
    # Each league's menu remembers its own last choice on this phone.
    store = "" if season["primary"] else f' data-store="psdl-schedule-division-{season["night"].lower()}"'

    def team_link(label, team, cls="fx-team"):
        return (f'<a class="{cls}" href="{team_href(team, season)}"><b class="name">{esc(team)}</b>'
                f'<small>{label}</small></a>')

    # Home on the left, away on the right, as on a scoreboard. Each team links to its page.
    def fixture_row(f):
        attrs = f'data-division="{slug(f["division"])}"'
        division = f'<small class="fx-div">{esc(f["division"].upper())}</small>'
        if "bye" in f:
            return (f'  <div class="fixture bye" {attrs} data-row="{esc(f["bye"])}">\n'
                    f'    {division}\n'
                    f'    <span class="fx-teams">{team_link("BYE", f["bye"])}</span>\n  </div>\n')
        return (f'  <div class="fixture" {attrs} data-row="{esc(f["home"])} {esc(f["away"])}">\n'
                f'    {division}\n'
                f'    <span class="fx-teams">{team_link("HOME", f["home"])}<span class="fx-v">v</span>'
                f'{team_link("AWAY", f["away"], "fx-team away")}</span>\n  </div>\n')

    if not nights:
        body = [C.header("MATCH SCHEDULE"),
                C.statusbar(season["standings"]["leagueInfo"]["season_label"].upper()),
                picker,
                '  <div class="headline"><span><h1>UPCOMING</h1>'
                '<p>No upcoming matches on the DartConnect schedule.</p></span></div>\n']
    else:
        first = nights[0]
        options = "\n      ".join(
            ['<option value="">All divisions</option>'] +
            [f'<option value="{slug(d)}">{esc(d)}</option>' for d in divisions])
        body = [C.header("MATCH SCHEDULE"),
                C.statusbar(f"NEXT · {events._pretty_date(first['date'])}"),
                picker,
                f"""  <div class="sched-controls" hidden>
  <div class="filter">
    <label for="division" class="vh">Division</label>
    <select id="division"{store}>
      {options}
    </select>
    <span class="chevron">{icon("chevron", tokens.COLOURS["muted"], 16)}</span>
  </div>
  <label for="team-find" class="vh">Find a team</label>
  <div class="search">{icon("search", size=17)}
    <input id="team-find" type="search" placeholder="Find a team" autocomplete="off">
  </div>
  </div>
  <div class="headline"><span><h1>UPCOMING</h1>
    <p><span id="fx-count" class="num">{to_play}</span> <span id="fx-noun">{"match" if to_play == 1 else "matches"}</span> still to play</p></span></div>
"""]
        for night in nights:
            when = fixtures.clock(night["time"])
            if night["week"]:
                when = f"WEEK {night['week']} &middot; {when}"
            body.append(f"""  <section class="night" data-start="{night['start']}">
  <div class="headline">
    <span><h2 class="section">{esc(events._pretty_date(night['date']))}</h2><p>{when}</p></span>
    <span class="note live-tag" hidden>LIVE NOW</span>
  </div>
""")
            body.extend(fixture_row(f) for f in night["fixtures"])
            body.append("  </section>\n")
        body.append('  <p class="caption" id="no-fixtures" hidden>No upcoming matches for that '
                    'selection.</p>\n')
        body.append('  <p class="caption">Straight from DartConnect&rsquo;s schedule. Home is the '
                    'team DartConnect lists first. Times are New York time. On match night, '
                    'tonight&rsquo;s matches turn gold from first darts until midnight. Tap a team '
                    'for its players.</p>\n')

    named = "" if season["primary"] else f", {season['night']}"
    page = C.page(f"PSDL All Star — Schedule{named}", "".join(body), "schedule")
    write(schedule_href(season), page)
    if season["primary"]:
        write("matches.html", page)


# ---------------------------------------------------------------- team

def build_teams(season, table, form):
    """One page per standings competitor of one night's current season, reached by tapping its
    row on that league's Standings.

    The list comes from standings (CLAUDE.md data rule 6), not from who has scored, so every
    standings row has a page to open -- including a team with no all star hits yet.

    Every roster row shows GP, the league nights the player has played, and a gold check mark
    once that reaches the playoff minimum for the division (players.playoff_minimum).
    """
    scored = {r["player"]: r for rows in table.values() for r in rows}

    # The roster is everyone who has thrown for the team, scorers or not. season["teams"] already
    # resolves renamed teams through DartConnect's id and leaves out the -SHORT- marker.
    team_of = dict(season["teams"])
    for player, row in scored.items():
        team_of.setdefault(player, row["team"])
    roster = collections.defaultdict(list)
    for player, team in team_of.items():
        roster[team].append(player)

    for c in season["standings"]["competitors"]:
        team = players.clean_team(c["team_name"])
        names = roster.get(team, [])
        rows = sorted((scored[p] for p in names if p in scored),
                      key=lambda r: (-r["points"], r["player"]))
        zero = sorted(p for p in names if p not in scored)
        played = {p: len(season["nights_by_player"].get(p, ())) for p in names}
        write(team_href(team, season), team_page(team, c["division"], rows, zero, form, played,
                                                 season["season_nights"].get(c["division"]),
                                                 season))


def roster_stats(nights, form):
    """GP, then the singles '01 average and cricket MPR -- labelled and formatted as on the
    standings rows a captain has just tapped through from (two decimals, as DartConnect prints
    them).

    GP is league nights played, and always present: the roster and the count come from the same
    turn records. The averages are omitted when neither is known (a doubles-only player); a single
    unknown is an em dash.
    """
    parts = [f"GP {nights}"]
    form = form or {}
    three, mpr = form.get("three_dart_avg"), form.get("mpr")
    if three is not None or mpr is not None:
        shown = lambda v: "&mdash;" if v is None else f"{v:.2f}"
        parts += [f"&rsquo;01 {shown(three)}", f"CRK {shown(mpr)}"]
    return f'\n      <small class="num">{" &middot; ".join(parts)}</small>'


def eligible_mark(nights, need):
    """The gold check mark after a playoff-eligible player's name, or nothing.

    Nothing at all while the season length is unknown (`need` is None) -- never a guessed one.
    The SVG is decoration; the words are for screen readers.
    """
    if need is None or nights < need:
        return ""
    return (f'<span class="eligible">{icon("check", tokens.COLOURS["gold"], 16)}'
            f'<span class="vh">, playoff eligible</span></span>')


def team_page(team, division, rows, zero, form, played, season_nights, season):
    """`played` maps each player on the roster to league nights played; `season_nights` is how
    many nights each team in the division plays this season, or None if nobody has said;
    `season` is the night's current season -- its standings are the back link, and each name
    opens that season's section of the player's page."""
    key = season["key"]
    need = players.playoff_minimum(season_nights) if season_nights else None
    total = sum(r["points"] for r in rows)
    hits  = sum(r["hits"] for r in rows)
    standings = standings_href(season, division)
    back_from = [standings] + [p for p in (standings_href(season),) if p != standings]
    body = [C.subheader(f"{division.upper()} STANDINGS", f"../{standings}",
                        back_from, up="../"),
            f"""  <div class="headline"><span>
    <h1 class="name">{esc(team)}</h1>
    <p>{esc(division)} &middot; captain&rsquo;s roll-up</p>
  </span></div>
  <div class="card"><div class="statgrid three">
    <span class="stat"><b class="num">{total:,}</b><small>TEAM PTS</small></span>
    <span class="stat"><b class="num">{hits}</b><small>HITS</small></span>
    <span class="stat"><b class="num">{len(rows)}</b><small>SCORED</small></span>
  </div></div>
"""]
    for r in rows:
        body.append(f"""  <a class="row" href="{player_href(r['player'], key, '../')}">
    <span class="row-rank num ordinal">{ordinal(r['rank'])}</span>
    <span class="row-main"><b class="name">{esc(r['player'])}{eligible_mark(played[r['player']], need)}</b>{roster_stats(played[r['player']], form.get(r['player']))}
      <span class="chips">{C.chips_for(r['counts'], allstar.RARE)}</span>
    </span>
    <span class="row-pts"><b class="num">{r['points']:,}</b><span>PTS</span></span>
  </a>
""")
    # Teammates who have thrown but not yet hit an all star. No player page exists for them, so
    # the row is not a link.
    for name in zero:
        body.append(f"""  <div class="row">
    <span class="row-rank num ordinal">&mdash;</span>
    <span class="row-main"><b class="name">{esc(name)}{eligible_mark(played[name], need)}</b>{roster_stats(played[name], form.get(name))}
      <small>No all star hits yet</small>
    </span>
    <span class="row-pts"><b class="num">0</b><span>PTS</span></span>
  </div>
""")
    if rows or zero:
        eligible = ""
        if need is not None:
            mark = f'<span class="eligible">{icon("check", tokens.COLOURS["gold"], 13)}</span>'
            eligible = (f' A gold check mark {mark} means '
                        f'playoff eligible: played at least {need} of the {season_nights} nights '
                        f'each {esc(division)} team plays (Rulebook &sect;H.2).')
        body.append(f'  <p class="caption">Ranks are within {esc(division)}. GP is league nights '
                    f'played &mdash; one game in a night counts.{eligible} &rsquo;01 and CRK '
                    'are singles averages &mdash; in doubles the darts belong to the pair, so '
                    'they cannot be split fairly. Tap a name for the turns behind the total.</p>\n')
    else:
        body.append('  <p class="caption">Nobody has thrown for this team yet.</p>\n')
    return C.page(f"PSDL All Star — {team}", "".join(body), "standings", depth=1)


# ---------------------------------------------------------------- standings

def dash(value):
    """A DartConnect figure, or an em dash when it is missing. The dash is markup, so it must not
    pass through esc() -- that would print a literal '&mdash;' on a team that has yet to play."""
    return esc(value) if value not in (None, "") else "&mdash;"


def build_standings(leagues):
    """Standings for the current season of each night. The league picker at the top switches
    between them (owner, 2026-11-12); Tuesday's are the pages the tab has always opened."""
    for season in leagues:
        build_league_standings(season, leagues)


def build_league_standings(season, leagues):
    competitors = season["standings"]["competitors"]
    div_meta = {d["division"]: d for d in season["standings"].get("leagueDivisions", [])}
    divisions = season["divisions"]

    for division in divisions:
        teams = sorted([c for c in competitors if c["division"] == division],
                       key=lambda c: c["rank"])
        meta = div_meta.get(division, {})
        body = [C.header("LEAGUE STANDINGS"),
                C.statusbar(f"{season['standings']['leagueInfo']['season_label'].upper()} "
                            f"· {season['night'].upper()}"),
                league_picker(leagues, season, division, standings_href)]
        if len(divisions) > 1:
            body.append(C.division_nav(divisions, division,
                                       lambda d: standings_href(season, d)))
        body.append(f"""  <div class="headline">
    <span><h1>{esc(division.upper())}</h1>
    <p>{len(teams)} teams</p></span>
    <span class="note">DIVISION AVERAGE<br>&rsquo;01 {dash(meta.get('ppr'))}
    &middot; CRK {dash(meta.get('mpr'))}</span>
  </div>
""")
        for c in teams:
            diff = c["leg_wins"] * 2 - c["leg_count"]
            played = c["matches"]
            team = players.clean_team(c["team_name"])
            body.append(f"""  <a class="row" href="{team_href(team, season)}">
    <span class="row-rank num{' top' if c['rank'] <= 3 else ''}">{c['rank']}</span>
    <span class="row-main">
      <b class="name">{esc(team)}</b>
      <small>MP {played} &middot; MW {c['win']} &middot;
      {f"LW {c['leg_win_perc']}% &middot; L {diff:+d}" if played else "yet to play"}</small>
      <small>&rsquo;01 {dash(c['ppr'])} &middot; CRK {dash(c['mpr'])}</small>
    </span>
    <span class="row-pts"><b class="num">{c['league_points']}</b><span>PTS</span></span>
  </a>
""")
        body.append('  <p class="caption">PTS league points &middot; MP matches played &middot; '
                    'MW matches won &middot; LW leg win rate &middot; L leg differential &middot; '
                    '&rsquo;01 and CRK are the team&rsquo;s scoring averages. '
                    'Straight from DartConnect. Tap a team to see its players.</p>\n')
        page = C.page(f"PSDL All Star — {division} standings", "".join(body), "standings")
        write(standings_href(season, division), page)
        # The league's own address -- standings.html for Tuesday -- is its first division.
        landing = standings_href(season)
        if division == divisions[0] and landing != standings_href(season, division):
            write(landing, page)


# ---------------------------------------------------------------- awards

def awards_href(season, up=""):
    """The Awards index for a night: awards.html for Tuesday, awards-monday.html for Monday."""
    if season["primary"]:
        return f"{up}awards.html"
    return f"{up}awards-{season['night'].lower()}.html"


def award_detail_href(season, key, up=""):
    """A single award's detail page: award/<key>.html for Tuesday, award/monday-<key>.html."""
    if season["primary"]:
        return f"{up}award/{key}.html"
    return f"{up}award/{season['night'].lower()}-{key}.html"


def award_hit(h, up="", lead="", extra=False):
    """One award entry: who threw it, for which team, the turn's value, and the recap behind it.

    `lead` sits left of the name -- a rank on a ranked table, a chip on a club list, or nothing.
    """
    return f"""  <div class="hit"{' data-extra' if extra else ''}>{lead}
    <span class="hit-main">
      <a href="{player_href(h['player'], h.get('season'), up)}"><b class="name">{esc(h['player'])}</b></a>
      <small class="name">{esc(h.get('team', ''))} &middot; {esc(h.get('division', ''))}</small>
      <small>{esc(h['game'])} &middot; {esc(events._pretty_date(h['date']))} &middot;
      {C.recap_link(h)}</small>
    </span>
    <span class="hit-val num">{h['turn_value']}</span>
  </div>
"""


def rank_lead(h):
    return f'\n    <span class="row-rank num{" top" if h["rank"] <= 3 else ""}">{h["rank"]}</span>'


def chip_lead(h):
    return f'\n    <span class="chip rare">{esc(h["display"])}</span>'


def both_nights(leagues):
    """The status bar for a page about both nights' current seasons: 'FALL 2026 · BOTH NIGHTS'."""
    labels = []
    for s in leagues:
        if s["label"].upper() not in labels:
            labels.append(s["label"].upper())
    return f"{' / '.join(labels)} · BOTH NIGHTS"


def build_awards(leagues):
    """The Awards tab: one page per night, behind the LEAGUE picker (owner, 2026-11-12).

    Each night's Awards page shows that night's holders only. Largest Check-In and Largest
    Checkout are awarded separately per night. The Awards tab opens Tuesday's page.
    """
    for season in leagues:
        build_league_awards(season, leagues)


def build_league_awards(season, leagues):
    """Awards index and detail pages for one night."""
    data = awards.compute_all(season["hits"], season["table"])
    leaders = [(season, d, season["table"].get(d, [])[:5]) for d in season["divisions"]]
    picker = league_picker(leagues, season, None, lambda s, _d: awards_href(s))

    body = [C.header("AWARDS"),
            C.statusbar(f"{season['label'].upper()} · {season['night'].upper()}"),
            picker,
            f'  <div class="headline"><span><h1>AWARDS</h1>'
            f'<p>Who holds each award, season to date &middot; all from '
            f'DartConnect</p></span></div>\n']

    for award in awards.AWARDS:
        key, kind, entries = award["key"], award["kind"], data[award["key"]]
        body.append(f'  <div class="headline"><span>'
                    f'<h2 class="section">{esc(award["title"].upper())}</h2>'
                    f'<p>{esc(award["blurb"])}</p></span></div>\n')
        holders, more = [], None
        if kind == "division":
            holders = [player_row(rows[0], rank=None, division=True, key=season["key"])
                       for _s, _d, rows in leaders if rows]
            depth = max((len(rows) for _s, _d, rows in leaders), default=0)
            if depth > 1:
                more = f"TOP {depth} IN EACH DIVISION"
        elif kind == "one":
            first = [h for h in entries if h["rank"] == 1]
            holders = [award_hit(h) for h in first]
            if len(entries) > len(first):
                more = "FULL LEAGUE TABLE"
        elif kind == "many":
            holders = [award_hit(h, lead=chip_lead(h)) for h in entries]

        if not holders:
            body.append('  <p class="caption">Nobody yet this season.</p>\n')
            continue
        body.extend(holders)
        if more:
            body.append(f'  <a class="btn" href="{award_detail_href(season, key)}">{more}'
                        f'{icon("chevron", tokens.COLOURS["gold"], 15)}</a>\n')

    body.append('  <p class="caption">Every number traces back to DartConnect &mdash; tap a '
                'name for the player&rsquo;s turns, or a set and game to open the match '
                'recap.</p>\n')
    named = "" if season["primary"] else f", {season['night']}"
    write(awards_href(season),
          C.page(f"PSDL All Star — Awards{named}", "".join(body), "awards"))

    for award in awards.AWARDS:
        key = award["key"]
        write(award_detail_href(season, key),
              award_page(award, data[key], leaders, season, leagues))


def award_page(award, entries, leaders, season, leagues):
    key = award["key"]
    kind = award["kind"]

    index = awards_href(season, up="../")
    back_from = [awards_href(s) for s in leagues]
    body = [C.subheader("AWARDS", index, back_from, up="../"),
            league_picker(leagues, season, None,
                          lambda s, _d: award_detail_href(s, key, up="../"))]

    if kind == "division":
        body.append(f'  <div class="headline"><span><h1>{esc(award["title"].upper())}</h1>'
                    f'<p>{esc(award["blurb"])}</p></span></div>\n')
        for _s, division, rows in leaders:
            body.append(f'  <div class="headline"><span>'
                        f'<h2 class="section">{esc(division.upper())}</h2>'
                        f'</span></div>\n')
            if not rows:
                body.append('  <p class="caption">No scores yet in this division.</p>\n')
                continue
            for row in rows:
                if row["rank"] == 1:
                    body.append(leader_card(row, up="../", key=season["key"]))
                else:
                    body.append(player_row(row, up="../", key=season["key"]))
            full = season["table"].get(division, [])
            if len(full) > len(rows):
                body.append(f'  <a class="btn" href="{board_href(season, division, up="../")}">'
                            f'FULL {esc(division.upper())} TABLE'
                            f'{icon("chevron", tokens.COLOURS["gold"], 15)}</a>\n')
    elif kind == "many":
        body.append(f'  <div class="headline"><span><h1>{esc(award["title"].upper())}</h1>'
                    f'<p>{esc(award["blurb"])}</p></span></div>\n')
        if not entries:
            body.append('  <p class="caption">Nobody yet this season. '
                        'Check back after more match nights.</p>\n')
        else:
            body.append(f'  <div class="headline"><span>'
                        f'<p>{len(entries)} qualifying hit{"s" if len(entries) != 1 else ""}</p>'
                        f'</span></div>\n')
            for h in entries:
                body.append(award_hit(h, up="../", lead=chip_lead(h)))
    elif kind == "one":
        body.append(f'  <div class="headline"><span><h1>{esc(award["title"].upper())}</h1>'
                    f'<p>{esc(award["blurb"])}</p></span></div>\n')
        if not entries:
            body.append('  <p class="caption">Nobody yet this season. '
                        'Check back after more match nights.</p>\n')
        else:
            body.append(f'  <p class="caption">Ranked across every {season["night"]} division '
                        '&mdash; each night awards its own. Ties share a place.</p>\n')
            for i, h in enumerate(entries):
                body.append(award_hit(h, up="../", lead=rank_lead(h), extra=i >= PREVIEW_ROWS))
            if len(entries) > PREVIEW_ROWS:
                body.append(show_all_button(f"SHOW ALL {len(entries)}"))

    named = "" if season["primary"] else f", {season['night']}"
    return C.page(f"PSDL All Star — {award['title']}{named}", "".join(body), "awards", depth=1)


# ---------------------------------------------------------------- feed

def feed_card(evt):
    href = evt["link_href"]
    is_external = href.startswith("http")
    target = ' target="_blank" rel="noopener"' if is_external else ""

    if evt["icon_type"] == "chip":
        rare = evt["icon_name"] in allstar.RARE
        icon_html = (f'\n    <span class="chip{" rare" if rare else ""}">'
                     f'{esc(evt["icon_name"])}</span>')
    else:
        icon_html = f'\n    {icon(evt["icon_name"], tokens.COLOURS["gold"], 20)}'

    div_label = f"{esc(evt['division'])}" if evt.get("division") else ""

    return f"""  <a class="feed-card" href="{href}"{target}>{icon_html}
    <span class="feed-body">
      <b>{esc(evt['headline'])}</b>
      <span>{esc(evt['body'])}</span>
      <small>{div_label}</small>
    </span>
  </a>
"""


def build_feed(leagues):
    """The Feed: the league at large -- the current season of both nights, grouped by night
    (owner, 2026-11-12). Leader cards link the right night's board and standings."""
    feed_events = feed.generate_events(
        leagues, board_href=lambda s, d: board_href(s, d),
        standings_href=lambda s, d: standings_href(s, d),
        award_href=lambda s, key: award_detail_href(s, key))

    body = [C.header("NEWS FEED"),
            C.statusbar(both_nights(leagues)),
            f'  <div class="headline"><span><h1>NEWS FEED</h1>'
            f'<p>{len(feed_events)} events this season, Monday and Tuesday</p>'
            f'</span></div>\n']

    if not feed_events:
        body.append('  <p class="caption">Nothing posted yet.</p>\n')
    else:
        current_group = None
        for evt in feed_events:
            group = (evt["date"], evt["night"])
            if group != current_group:
                current_group = group
                night_label = f"{evt['night'].upper()} NIGHT"
                date_label = events._pretty_date(evt["date"])
                week_label = f"Week {evt['week']}"
                actual_day = feed.weekday_name(evt["date"])
                if actual_day and actual_day != evt["night"]:
                    week_label += f" &middot; played on {actual_day}"
                body.append(f'  <div class="headline"><span>'
                            f'<h2 class="section">{night_label} &middot; '
                            f'{esc(date_label)}</h2>'
                            f'<p>{week_label}</p></span></div>\n')
            body.append(feed_card(evt))

    body.append('  <p class="caption">Every event is computed from DartConnect data. '
                'Achievement cards link to the turn behind them; leader changes link '
                'to the leaderboard.</p>\n')
    write("feed.html", C.page("PSDL All Star — Feed", "".join(body), "feed"))


# ---------------------------------------------------------------- output

_written = []


def write(relpath, content):
    """Write one page. A path written twice means two pages collided -- two players or teams whose
    names slug alike, or two seasons with one key -- and one would silently replace the other."""
    if relpath in _written:
        raise RuntimeError(f"{relpath} would be written twice -- two pages share a file name")
    path = OUT / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _written.append(relpath)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)                      # keeps builds byte-reproducible
    OUT.mkdir(parents=True)

    C.BUILD_DATE = datetime.date.today().isoformat()

    # Every season of both nights, the Tuesday league's current season first. That one is the
    # home season: the Schedule, Standings, team pages, Awards and the Feed show it.
    seasons = events.load_all()
    season = seasons[0]
    if not is_home(season):
        raise RuntimeError(f"expected the Tuesday league's current season first, got "
                           f"{season['label']} {season['night']}")
    for s in seasons:
        if s["missing"]:
            print(f"  ! {len(s['missing'])} match recaps missing from {s['label']} "
                  f"{s['night']} -- run scraper/fetch.py", file=sys.stderr)
        s["table"] = players.division_table(s["hits"], s["weeks_by_player"])
        s["divisions"] = events.divisions(s)
    career = players.career_table(seasons, {s["key"]: s["table"] for s in seasons})
    plan_sections(seasons)

    # The current season of each night -- Tuesday first. Standings, the Schedule and team pages
    # are per night (with a league picker); Awards and the Feed take both together.
    league_rank = {league: i for i, (league, _night) in enumerate(events.fetch.LEAGUES)}
    leagues = sorted((s for s in seasons if s["current"]),
                     key=lambda s: league_rank.get(s["league"], len(league_rank)))
    for s in leagues:
        if not s["season_nights"]:
            print(f"  ! no season length for {s['label']} {s['night']} in "
                  f"players.SEASON_NIGHTS -- its team pages show GP without playoff check marks",
                  file=sys.stderr)

    (OUT / "app.css").write_text(tokens.stylesheet(), encoding="utf-8")
    shutil.copy(ROOT / "site" / "app.js", OUT / "app.js")
    (OUT / "assets").mkdir()
    for asset in SHIPPED_ASSETS:
        shutil.copy(ROOT / "design" / "assets" / asset, OUT / "assets" / asset)

    build_all_stars(seasons, career)
    build_players(seasons, career)
    for s in leagues:
        build_schedule(s, leagues)
        build_teams(s, s["table"], players.form_stats(s["recaps"]))
    build_standings(leagues)
    build_awards(leagues)
    build_feed(leagues)

    # A bracketed placeholder must never reach a real page.
    leftovers = []
    for path in OUT.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        for marker in ("[TEAM NAME]", "[OPPONENT TEAM]", "[MPR]", "[ALL STAR CUT]"):
            if marker in text:
                leftovers.append(f"{path.relative_to(OUT)}: {marker}")
        if re.search(r"(?<![A-Za-z0-9])None(?![A-Za-z0-9])", text):
            leftovers.append(f"{path.relative_to(OUT)}: None")
    if leftovers:
        print("\n  ! placeholders left in output:", file=sys.stderr)
        for item in leftovers[:10]:
            print(f"      {item}", file=sys.stderr)
        return 1

    print(f"built {len(_written)} pages into {OUT}")
    print(f"  {len([r for r in _written if r.startswith('player/')])} players, "
          f"{len([r for r in _written if r.startswith('team/')])} teams, "
          f"{len([r for r in _written if r.startswith('award/')])} awards")
    for s in leagues:
        upcoming = [f for night in s["fixtures"] for f in night["fixtures"] if "bye" not in f]
        print(f"  {s['night']} schedule: {len(upcoming)} upcoming matches over "
              f"{len(s['fixtures'])} nights")
    print(f"  all-stars: {len(seasons)} seasons, "
          f"{len([r for r in _written if r.startswith('all-stars-')])} past-season and All Time "
          f"boards, {len(career)} players all time")
    return 0


if __name__ == "__main__":
    sys.exit(main())
