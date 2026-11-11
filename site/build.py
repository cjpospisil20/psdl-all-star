"""Generate the PSDL All Star site into public/.

    python3 site/build.py

Reads only what fetch.py has archived, so builds are reproducible and work offline.
"""
import collections, datetime, pathlib, re, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scraper"))
sys.path.insert(0, str(ROOT / "site"))

import allstar, awards, events, feed, players         # noqa: E402
import components as C, tokens                       # noqa: E402
from components import esc, icon                     # noqa: E402

OUT = ROOT / "public"

# How many players per division make All Star. The league has not set this yet; until they do,
# the cut line is omitted rather than shipped as a bracketed placeholder.
ALL_STAR_CUT = None

PREVIEW_ROWS = 10          # rows before "show all"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


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


def build_all_stars(season, table, divisions, rare=None):
    def top(current):
        return [C.header("ALL STAR POINTS"),
                C.statusbar(f"WEEK {season['latest_week']} · "
                            f"{events._pretty_date(season['latest_date'])}"),
                C.division_nav(divisions, current, lambda d: f"{slug(d)}.html",
                               all_href="all.html")]

    for division in divisions:
        rows = table.get(division, [])
        body = top(division)

        body.append(f"""  <div class="headline">
    <span><h1>{esc(division.upper())}</h1>
    <p>{len(rows)} player{'s' if len(rows) != 1 else ''} on the board this week</p></span>
    <span class="note">RANKED WITHIN<br>DIVISION ONLY</span>
  </div>
""")
        # The season's standout moment gets a banner on its own division's board.
        if rare and rare["division"] == division:
            body.append(f"""  <a class="leader" href="rare-hit.html"
     style="border-color:var(--gold); background:var(--surface);">
    <span class="leader-top">
      <span class="chip rare" style="font-size:15px; padding:8px 12px;">{esc(rare['display'])}</span>
      <span class="leader-who">
        <b class="name">{esc(rare['player'])}</b>
        <span>First {esc(rare['display'])} of the season &middot; {esc(rare['detail'].lower())}</span>
      </span>
      {icon("chevron", tokens.COLOURS["gold"], 18)}
    </span>
  </a>
""")

        body.append(find_box())

        for row in rows:
            if row["rank"] == 1:
                body.append(leader_card(row))
            else:
                body.append(player_row(row, extra=row["rank"] > PREVIEW_ROWS))
            if ALL_STAR_CUT and row["rank"] == ALL_STAR_CUT:
                body.append('  <div class="cutline"><b>ALL STAR CUT LINE</b><i></i></div>\n')

        body.append('  <p class="caption" id="no-match" hidden>No player by that name on the '
                    f'{esc(division)} board this week.</p>\n')
        if len(rows) > PREVIEW_ROWS:
            body.append(show_all_button(f"SHOW ALL {len(rows)} IN {esc(division.upper())}"))

        body.append('  <p class="caption">Division 1 scores roughly 2.5&times; Division 5, so '
                    'this board ranks players against their own division only. Tap any player to '
                    'see the turns behind the number.</p>\n')

        page = C.page(f"PSDL All Star — {division}", "".join(body), "all-stars")
        write(f"{slug(division)}.html", page)
        if division == divisions[0]:
            write("index.html", page)

    # The ALL board: the one place players are ranked across divisions, because the owner asked
    # for it. So it crowns nobody -- no leader card, no gold top three, no rare-hit banner -- and
    # every row names its division, so a Division 1 total is never mistaken for a Division 5 one.
    everyone = players.league_table(table)
    body = top(None)
    body.append(f"""  <div class="headline">
    <span><h1>ALL DIVISIONS</h1>
    <p>{len(everyone)} player{'s' if len(everyone) != 1 else ''} on the board this week</p></span>
    <span class="note">RANKED ACROSS<br>ALL DIVISIONS</span>
  </div>
""")
    body.append(find_box())
    for row in everyone:
        body.append(player_row(row, extra=row["league_rank"] > PREVIEW_ROWS,
                               rank="league", division=True))
    body.append('  <p class="caption" id="no-match" hidden>No player by that name on the '
                'board this week.</p>\n')
    if len(everyone) > PREVIEW_ROWS:
        body.append(show_all_button(f"SHOW ALL {len(everyone)} PLAYERS"))
    body.append('  <p class="caption">Every division on one board, highest points first. '
                'Division 1 scores roughly 2.5&times; Division 5, so a league rank says as much '
                'about a player&rsquo;s division as about the player &mdash; pick a division '
                'above to compare like with like. Tap any player to see the turns behind the '
                'number.</p>\n')
    write("all.html", C.page("PSDL All Star — All divisions", "".join(body), "all-stars"))


def leader_card(row, up=""):
    return f"""  <a class="leader" href="{up}player/{slug(row['player'])}.html"
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


def player_row(row, extra=False, up="", rank="division", division=False):
    """One leaderboard row.

    rank      what fills the rank column: "division" (the default; the top three are gold),
              "league" (the ALL board -- never gold, it crowns nobody league-wide), or None to
              drop the column (the Awards index, where every row is a division leader).
    division  name the division beside the team, on any list that mixes divisions.
    """
    rank_html = ""
    if rank == "division":
        top = " top" if row["rank"] <= 3 else ""
        rank_html = f'\n    <span class="row-rank num{top}">{row["rank"]}</span>'
    elif rank == "league":
        rank_html = f'\n    <span class="row-rank num wide">{row["league_rank"]}</span>'
    where = (f"{esc(row['division'])} &middot; {esc(row['team'])}" if division
             else esc(row["team"]))
    return f"""  <a class="row" href="{up}player/{slug(row['player'])}.html"
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

def build_players(season, table, form):
    by_player = collections.defaultdict(list)
    for h in season["hits"]:
        by_player[h["player"]].append(h)

    rows = {r["player"]: r for rs in table.values() for r in rs}
    for name, row in rows.items():
        hits = sorted(by_player[name], key=lambda h: -h["points"])
        write(f"player/{slug(name)}.html", player_page(name, row, hits, form.get(name, {})))


def player_page(name, row, hits, form):
    back_label = f"{row['division'].upper()} ALL-STARS"
    back_href = f"../{slug(row['division'])}.html"
    back_from = [f"{slug(row['division'])}.html", "index.html"]
    body = [C.subheader(back_label, back_href, back_from, up="../"),
            f"""  <div class="headline"><span>
    <h1 class="name">{esc(name)}</h1>
    <p class="name">{esc(row['division'])} &middot; {esc(row['team'])}</p>
  </span></div>
"""]

    if form:
        def stat(label, value, suffix=""):
            shown = "&mdash;" if value is None else f"{value}{suffix}"
            return f'<span class="stat"><b class="num">{shown}</b><small>{label}</small></span>'

        body.append(f"""  <div class="card">
    <h2>THE DARTS &middot; SINGLES, SEASON TO DATE</h2>
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
    <h2>THIS SEASON</h2>
    <div class="statgrid three">
      {stat("MATCHES", form.get("matches"))}
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
    {esc(row['division'])}. Ranked within division only &mdash; Division 1 scores roughly
    2.5&times; Division 5.</p>
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
    return C.page(f"PSDL All Star — {name}", "".join(body), "all-stars", depth=1)


def ordinal(n):
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


# ---------------------------------------------------------------- match

def build_matches(season, divisions):
    played = [m for m in season["matches"] if m["hits"]]
    played.sort(key=lambda m: (-sum(h["points"] for h in m["hits"]), m["date"], m["division"]))

    weeks = sorted(season["week_of"].items(), key=lambda kv: kv[1])

    def match_row(m, up=""):
        pts = sum(h["points"] for h in m["hits"])
        return f"""  <a class="row" href="{up}match/{m['id']}.html"
     data-week="{m['week']}">
    <span class="row-main"><b class="name">{esc(m['home'])} v {esc(m['away'])}</b>
    <small>{esc(m['division'])} &middot; Week {m['week']} &middot; {esc(m['pretty'])} &middot; {len(m['hits'])} hits</small></span>
    <span class="row-pts"><b class="num">{pts:,}</b><span>PTS</span></span>
  </a>
"""

    def week_options():
        opts = ['<option value="">All weeks</option>']
        for date, wk in weeks:
            opts.append(f'<option value="{wk}">Week {wk} &middot; {esc(events._pretty_date(date))}</option>')
        return "\n      ".join(opts)

    def week_filter():
        return f"""  <div class="filter" hidden>
    <label for="week" class="vh">Filter by week</label>
    <select id="week">
      {week_options()}
    </select>
    <span class="chevron">{icon("chevron", tokens.COLOURS["muted"], 16)}</span>
  </div>
"""

    def matches_page(division, match_list, page_file):
        title = "ALL DIVISIONS" if division is None else division.upper()
        body = [C.header("MATCH NIGHTS"),
                C.statusbar(f"WEEK {season['latest_week']} · "
                            f"{events._pretty_date(season['latest_date'])}"),
                C.division_nav(divisions, division,
                               lambda d: f"matches-{slug(d)}.html",
                               all_href="matches.html"),
                f'  <div class="headline"><span><h1>{esc(title)}</h1>'
                f'<p><span id="match-count" class="num">{len(match_list)}</span> matches with all star hits</p></span></div>\n',
                week_filter()]
        for m in match_list:
            body.append(match_row(m))
        body.append('  <p class="caption" id="no-week" hidden>No matches for that week in this division.</p>\n')
        body.append('  <p class="caption">Division 1 scores roughly 2.5&times; Division 5. '
                    'Filter by division to compare like with like. Sorted by match points.</p>\n')
        write(page_file, C.page(f"PSDL All Star — Match nights", "".join(body), "match"))

    matches_page(None, played, "matches.html")
    for division in divisions:
        div_matches = [m for m in played if m["division"] == division]
        matches_page(division, div_matches, f"matches-{slug(division)}.html")

    for m in played:
        write(f"match/{m['id']}.html", match_page(m))


def match_page(m):
    by_team = collections.defaultdict(list)
    for h in m["hits"]:
        by_team[h["team"]].append(h)

    body = [C.subheader("MATCH NIGHTS", "../matches.html",
                        ["matches.html"] + [f"matches-division-{i}.html" for i in range(1, 6)],
                        up="../"),
            C.statusbar(f"{m['pretty']} · WEEK {m['week']} · {m['division'].upper()}"),
            f"""  <div class="headline"><span>
    <h1 class="name">{esc(m['home'])}<br>v {esc(m['away'])}</h1>
    <p>{len(m['hits'])} all star hits &middot; {sum(h['points'] for h in m['hits']):,} points
    &middot; every one links to its turn</p>
  </span></div>
"""]

    for team in (m["teams"].get("home"), m["teams"].get("away")):
        hits = sorted(by_team.get(team, []), key=lambda h: -h["points"])
        if not hits:
            continue
        body.append(f"""  <div class="headline"><span>
    <h2 class="section name">{esc(team)}</h2>
    <p>{sum(h['points'] for h in hits):,} PTS &middot; {len(hits)} HITS</p>
  </span></div>
""")
        for h in hits:
            body.append(f"""  <div class="hit">
    <span class="chip{' rare' if h['rare'] else ''}">{esc(h['display'])}</span>
    <span class="hit-main">
      <b class="name">{esc(h['player'])}</b>
      <small>{esc(h['game'])} &middot; {C.recap_link(h)}</small>
    </span>
    <span class="hit-val num">{h['points']}</span>
  </div>
""")

    body.append('  <p class="caption">Nothing here was typed by hand. Each row opens the '
                'DartConnect recap of that match &mdash; if a captain thinks a number is wrong, '
                'they can check it at the board.</p>\n')
    return C.page(f"PSDL All Star — {m['home']} v {m['away']}", "".join(body), "match", depth=1)


# ---------------------------------------------------------------- team

def team_href(team, up=""):
    """Where a team's page lives. The standings link and the page write both come through here,
    so a link can never point at a file the build did not write."""
    return f"{up}team/{slug(team)}.html"


def build_teams(season, table, form):
    """One page per standings competitor, reached by tapping its row on Standings.

    The list comes from standings (CLAUDE.md data rule 6), not from who has scored, so every
    standings row has a page to open -- including a team with no all star hits yet.
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
        write(team_href(team), team_page(team, c["division"], rows, zero, form))


def averages(form):
    """A player's singles '01 average and cricket MPR, labelled and formatted as on the standings
    rows a captain has just tapped through from (two decimals, as DartConnect prints them).

    Omitted when neither is known (a doubles-only player); a single unknown is an em dash.
    """
    form = form or {}
    three, mpr = form.get("three_dart_avg"), form.get("mpr")
    if three is None and mpr is None:
        return ""
    shown = lambda v: "&mdash;" if v is None else f"{v:.2f}"
    return f'\n      <small class="num">&rsquo;01 {shown(three)} &middot; CRK {shown(mpr)}</small>'


def team_page(team, division, rows, zero, form):
    total = sum(r["points"] for r in rows)
    hits  = sum(r["hits"] for r in rows)
    standings = f"standings-{slug(division)}.html"
    body = [C.subheader(f"{division.upper()} STANDINGS", f"../{standings}",
                        [standings, "standings.html"], up="../"),
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
        body.append(f"""  <a class="row" href="../player/{slug(r['player'])}.html">
    <span class="row-rank num ordinal">{ordinal(r['rank'])}</span>
    <span class="row-main"><b class="name">{esc(r['player'])}</b>{averages(form.get(r['player']))}
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
    <span class="row-main"><b class="name">{esc(name)}</b>{averages(form.get(name))}
      <small>No all star hits yet</small>
    </span>
    <span class="row-pts"><b class="num">0</b><span>PTS</span></span>
  </div>
""")
    if rows or zero:
        body.append(f'  <p class="caption">Ranks are within {esc(division)}. &rsquo;01 and CRK '
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


def build_standings(season, divisions):
    competitors = season["standings"]["competitors"]
    div_meta = {d["division"]: d for d in season["standings"].get("leagueDivisions", [])}

    for division in divisions:
        teams = sorted([c for c in competitors if c["division"] == division],
                       key=lambda c: c["rank"])
        meta = div_meta.get(division, {})
        body = [C.header("LEAGUE STANDINGS"),
                C.statusbar(f"{season['standings']['leagueInfo']['season_label'].upper()} "
                            f"· TUESDAY"),
                C.division_nav(divisions, division, lambda d: f"standings-{slug(d)}.html"),
                f"""  <div class="headline">
    <span><h1>{esc(division.upper())}</h1>
    <p>{len(teams)} teams</p></span>
    <span class="note">DIVISION AVERAGE<br>&rsquo;01 {dash(meta.get('ppr'))}
    &middot; CRK {dash(meta.get('mpr'))}</span>
  </div>
"""]
        for c in teams:
            diff = c["leg_wins"] * 2 - c["leg_count"]
            played = c["matches"]
            team = players.clean_team(c["team_name"])
            body.append(f"""  <a class="row" href="{team_href(team)}">
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
        write(f"standings-{slug(division)}.html", page)
        if division == divisions[0]:
            write("standings.html", page)


# ---------------------------------------------------------------- awards

def award_hit(h, up="", lead="", extra=False):
    """One award entry: who threw it, for which team, the turn's value, and the recap behind it.

    `lead` sits left of the name -- a rank on a ranked table, a chip on a club list, or nothing.
    """
    return f"""  <div class="hit"{' data-extra' if extra else ''}>{lead}
    <span class="hit-main">
      <a href="{up}player/{slug(h['player'])}.html"><b class="name">{esc(h['player'])}</b></a>
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


def build_awards(season, table, divisions):
    data = awards.compute_all(season["hits"], table)

    body = [C.header("AWARDS"),
            C.statusbar(f"WEEK {season['latest_week']} · "
                        f"{events._pretty_date(season['latest_date'])}"),
            f'  <div class="headline"><span><h1>AWARDS</h1>'
            f'<p>Who holds each award, season to date &middot; all from DartConnect</p>'
            f'</span></div>\n']

    # Who holds each award is on this page, so nobody has to tap in to find out. A detail page
    # link follows only where that page has more to show than the holders.
    for award in awards.AWARDS:
        key, kind, entries = award["key"], award["kind"], data[award["key"]]
        body.append(f'  <div class="headline"><span>'
                    f'<h2 class="section">{esc(award["title"].upper())}</h2>'
                    f'<p>{esc(award["blurb"])}</p></span></div>\n')
        holders, more = [], None
        if kind == "division":
            # In division order, never by points: sorting the leaders would rank them across
            # divisions, which is exactly what this award is careful not to do.
            holders = [player_row(entries[d][0], rank=None, division=True)
                       for d in divisions if entries.get(d)]
            depth = max((len(rows) for rows in entries.values()), default=0)
            if depth > 1:
                more = f"TOP {depth} IN EACH DIVISION"
        elif kind == "one":
            # Every entry ranked first, so a tie shows all of its holders.
            first = [h for h in entries if h["rank"] == 1]
            holders = [award_hit(h) for h in first]
            if len(entries) > len(first):
                more = "FULL LEAGUE TABLE"
        elif kind == "many":
            # A club's holders are all of its members.
            holders = [award_hit(h, lead=chip_lead(h)) for h in entries]

        if not holders:
            body.append('  <p class="caption">Nobody yet this season.</p>\n')
            continue
        body.extend(holders)
        if more:
            body.append(f'  <a class="btn" href="award/{key}.html">{more}'
                        f'{icon("chevron", tokens.COLOURS["gold"], 15)}</a>\n')

    body.append('  <p class="caption">Every number traces back to DartConnect &mdash; tap a '
                'name for the player&rsquo;s turns, or a set and game to open the match '
                'recap.</p>\n')
    write("awards.html", C.page("PSDL All Star — Awards", "".join(body), "awards"))

    for award in awards.AWARDS:
        key = award["key"]
        write(f"award/{key}.html",
              award_page(award, data[key], table, divisions, season))


def award_page(award, entries, table, divisions, season):
    key = award["key"]
    kind = award["kind"]

    body = [C.subheader("AWARDS", "../awards.html", ["awards.html"], up="../")]

    if kind == "division":
        body.append(f'  <div class="headline"><span><h1>{esc(award["title"].upper())}</h1>'
                    f'<p>{esc(award["blurb"])}</p></span></div>\n')
        for division in divisions:
            rows = entries.get(division, [])
            body.append(f'  <div class="headline"><span>'
                        f'<h2 class="section">{esc(division.upper())}</h2></span></div>\n')
            if not rows:
                body.append('  <p class="caption">No scores yet in this division.</p>\n')
                continue
            for row in rows:
                if row["rank"] == 1:
                    body.append(leader_card(row, up="../"))
                else:
                    body.append(player_row(row, up="../"))
            full = table.get(division, [])
            if len(full) > len(rows):
                body.append(f'  <a class="btn" href="../{slug(division)}.html">'
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
            body.append('  <p class="caption">Ranked across all divisions &mdash; '
                        'the league awards this one league-wide. '
                        'Ties share a place.</p>\n')
            for i, h in enumerate(entries):
                body.append(award_hit(h, up="../", lead=rank_lead(h), extra=i >= PREVIEW_ROWS))
            if len(entries) > PREVIEW_ROWS:
                body.append(show_all_button(f"SHOW ALL {len(entries)}"))

    return C.page(f"PSDL All Star — {award['title']}", "".join(body), "awards", depth=1)


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

    div_label = f" &middot; {esc(evt['division'])}" if evt.get("division") else ""

    return f"""  <a class="feed-card" href="{href}"{target}>{icon_html}
    <span class="feed-body">
      <b>{esc(evt['headline'])}</b>
      <span>{esc(evt['body'])}</span>
      <small>Week {evt['week']} &middot; {esc(events._pretty_date(evt['date']))}{div_label}</small>
    </span>
  </a>
"""


def build_feed(season, divisions):
    feed_events = feed.generate_events(season)

    body = [C.header("NEWS FEED"),
            C.statusbar(f"WEEK {season['latest_week']} · "
                        f"{events._pretty_date(season['latest_date'])}"),
            f'  <div class="headline"><span><h1>NEWS FEED</h1>'
            f'<p>{len(feed_events)} events through {season["latest_week"]} weeks</p>'
            f'</span></div>\n']

    if not feed_events:
        body.append('  <p class="caption">Nothing posted yet.</p>\n')
    else:
        for evt in feed_events:
            body.append(feed_card(evt))

    body.append('  <p class="caption">Every event is computed from DartConnect data. '
                'Achievement cards link to the turn behind them; leader changes link '
                'to the leaderboard.</p>\n')
    write("feed.html", C.page("PSDL All Star — Feed", "".join(body), "feed"))


# ---------------------------------------------------------------- rare hit

def build_rare_hit(season):
    hit = events.first_rare_hit(season["hits"])
    if not hit:
        return None
    gold = tokens.COLOURS["gold"]
    body = f"""  <div style="flex-grow:1; display:flex; flex-direction:column;
       align-items:center; justify-content:center; text-align:center; padding:48px 24px; gap:6px;">
    <h1 class="eyebrow" style="letter-spacing:0.22em; margin:0;">FIRST {esc(hit['display'])} OF THE SEASON</h1>
    <span class="display" style="font-size:104px; line-height:1; color:{gold};
          font-variant-numeric:tabular-nums;">{esc(hit['display'])}</span>
    <span style="font-size:11px; font-weight:700; letter-spacing:0.16em; color:var(--muted);">
      {esc(hit['detail'].upper())}</span>
    <b class="name" style="margin-top:22px; font-size:26px;">{esc(hit['player'])}</b>
    <span class="name" style="font-size:13px; color:var(--text2);">{esc(hit['team'])} &middot; {esc(hit['division'])}</span>
    <span style="margin-top:20px; font-size:11px; font-weight:700; letter-spacing:0.1em;
          color:var(--muted);">{esc(events._pretty_date(hit['date']))} &middot;
      {esc(hit['game'])} &middot; WEEK {hit['week']}</span>
    <span class="chip rare" style="margin-top:22px; font-size:14px; padding:8px 14px;">
      +{hit['points']} ALL STAR POINTS</span>
    <a class="btn" style="margin-top:28px;" href="player/{slug(hit['player'])}.html">
      SEE {esc(hit['player'].split()[0].upper())}&rsquo;S WEEK</a>
    <img src="assets/psdl-wordmark-white.png" alt="Park Slope Dart League"
         style="margin-top:40px; width:150px; max-width:60%; height:auto; opacity:0.75;">
  </div>
"""
    write("rare-hit.html", C.page("PSDL All Star — Rare hit", body, "all-stars"))
    return hit


# ---------------------------------------------------------------- output

_written = []


def write(relpath, content):
    path = OUT / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _written.append(relpath)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)                      # keeps builds byte-reproducible
    OUT.mkdir(parents=True)

    C.BUILD_DATE = datetime.date.today().isoformat()

    season = events.load_season()
    if season["missing"]:
        print(f"  ! {len(season['missing'])} match recaps missing -- run scraper/fetch.py",
              file=sys.stderr)

    table = players.division_table(season["hits"], season["weeks_by_player"])
    form  = players.form_stats(season["recaps"])
    divs  = events.divisions(season)

    (OUT / "app.css").write_text(tokens.stylesheet(), encoding="utf-8")
    shutil.copy(ROOT / "site" / "app.js", OUT / "app.js")
    shutil.copytree(ROOT / "design" / "assets", OUT / "assets")

    rare = build_rare_hit(season)
    build_all_stars(season, table, divs, rare)
    build_players(season, table, form)
    build_matches(season, divs)
    build_teams(season, table, form)
    build_standings(season, divs)
    build_awards(season, table, divs)
    build_feed(season, divs)

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
          f"{len([r for r in _written if r.startswith('match/')])} matches, "
          f"{len([r for r in _written if r.startswith('team/')])} teams, "
          f"{len([r for r in _written if r.startswith('award/')])} awards")
    if rare:
        print(f"  rare-hit screen: {rare['player']}'s {rare['display']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
