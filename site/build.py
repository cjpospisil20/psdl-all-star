"""Generate the PSDL All Star site into public/.

    python3 site/build.py

Reads only what fetch.py has archived, so builds are reproducible and work offline.
"""
import collections, pathlib, re, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scraper"))
sys.path.insert(0, str(ROOT / "site"))

import allstar, events, players                    # noqa: E402
import components as C, tokens                     # noqa: E402
from components import esc, icon                   # noqa: E402

OUT = ROOT / "public"

# How many players per division make All Star. The league has not set this yet; until they do,
# the cut line is omitted rather than shipped as a bracketed placeholder.
ALL_STAR_CUT = None

PREVIEW_ROWS = 10          # rows before "show all"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


# ---------------------------------------------------------------- all-stars

def build_all_stars(season, table, divisions, rare=None):
    for division in divisions:
        rows = table.get(division, [])
        body = [C.header("ALL STAR POINTS"),
                C.statusbar(f"WEEK {season['latest_week']} · "
                            f"{events._pretty_date(season['latest_date'])}"),
                C.division_nav(divisions, division, lambda d: f"{slug(d)}.html")]

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

        body.append(f"""  <label for="find" class="vh">Find a player</label>
  <div class="search">{icon("search", size=17)}
    <input id="find" type="search" placeholder="Find a player" autocomplete="off">
  </div>
""")

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
            # hidden until app.js confirms JS is running -- without it the full table stands
            body.append(f'  <button class="btn" id="show-all" type="button" hidden>'
                        f'SHOW ALL {len(rows)} IN {esc(division.upper())}'
                        f'{icon("chevron", tokens.COLOURS["gold"], 15)}</button>\n')

        body.append('  <p class="caption">Division 1 scores roughly 2.5&times; Division 5, so '
                    'players are only ever ranked against their own division. Tap any player to '
                    'see the turns behind the number.</p>\n')

        page = C.page(f"PSDL All Star — {division}", "".join(body), "all-stars")
        write(f"{slug(division)}.html", page)
        if division == divisions[0]:
            write("index.html", page)


def leader_card(row):
    return f"""  <a class="leader" href="player/{slug(row['player'])}.html"
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


def player_row(row, extra=False):
    top = " top" if row["rank"] <= 3 else ""
    return f"""  <a class="row" href="player/{slug(row['player'])}.html"
     data-row="{esc(row['player'])} {esc(row['team'])}"{' data-extra' if extra else ''}>
    <span class="row-rank num{top}">{row['rank']}</span>
    <span class="row-main">
      <b class="name">{esc(row['player'])}</b>
      <small class="name">{esc(row['team'])}</small>
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

    index = ['  <div class="headline"><span><h1>PLAYERS</h1>'
             f'<p>{len(rows)} scoring this season</p></span></div>\n']
    for name in sorted(rows):
        r = rows[name]
        index.append(f"""  <a class="row" href="player/{slug(name)}.html">
    <span class="row-main"><b class="name">{esc(name)}</b>
    <small class="name">{esc(r['team'])} &middot; {esc(r['division'])}</small></span>
    <span class="row-pts"><b class="num">{r['points']:,}</b><span>PTS</span></span>
  </a>
""")
    write("players.html", C.page("PSDL All Star — Players",
                                 C.header("PLAYERS") + "".join(index), "player"))


def player_page(name, row, hits, form):
    body = [C.header("ALL-STARS", up="../"),
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
    2.5&times; Division 5, so the tables are never compared.</p>
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
    return C.page(f"PSDL All Star — {name}", "".join(body), "player", depth=1)


def ordinal(n):
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


# ---------------------------------------------------------------- match

def build_matches(season):
    played = [m for m in season["matches"] if m["hits"]]
    played.sort(key=lambda m: (m["date"], m["division"]))

    index = [C.header("MATCH NIGHTS"),
             C.statusbar(f"WEEK {season['latest_week']} · "
                         f"{events._pretty_date(season['latest_date'])}"),
             f'  <div class="headline"><span><h1>MATCH NIGHTS</h1>'
             f'<p>{len(played)} matches with all star hits</p></span></div>\n']
    for m in played:
        pts = sum(h["points"] for h in m["hits"])
        index.append(f"""  <a class="row" href="match/{m['id']}.html">
    <span class="row-main"><b class="name">{esc(m['home'])} v {esc(m['away'])}</b>
    <small>{esc(m['division'])} &middot; {esc(m['pretty'])} &middot; {len(m['hits'])} hits</small></span>
    <span class="row-pts"><b class="num">{pts:,}</b><span>PTS</span></span>
  </a>
""")
    write("matches.html", C.page("PSDL All Star — Match nights",
                                 "".join(index), "match"))
    for m in played:
        write(f"match/{m['id']}.html", match_page(m))


def match_page(m):
    by_team = collections.defaultdict(list)
    for h in m["hits"]:
        by_team[h["team"]].append(h)

    body = [C.header("MATCH NIGHT", up="../"),
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

def build_teams(season, table):
    rows_by_team = collections.defaultdict(list)
    for rows in table.values():
        for r in rows:
            rows_by_team[r["team"]].append(r)

    index = [C.header("TEAMS"),
             f'  <div class="headline"><span><h1>TEAMS</h1>'
             f'<p>{len(rows_by_team)} teams on the board</p></span></div>\n']
    for team in sorted(rows_by_team, key=lambda t: -sum(r["points"] for r in rows_by_team[t])):
        rows = rows_by_team[team]
        index.append(f"""  <a class="row" href="team/{slug(team)}.html">
    <span class="row-main"><b class="name">{esc(team)}</b>
    <small>{esc(rows[0]['division'])} &middot; {len(rows)} scoring</small></span>
    <span class="row-pts"><b class="num">{sum(r['points'] for r in rows):,}</b><span>PTS</span></span>
  </a>
""")
    write("teams.html", C.page("PSDL All Star — Teams", "".join(index), "team"))

    for team, rows in rows_by_team.items():
        write(f"team/{slug(team)}.html", team_page(team, sorted(rows, key=lambda r: -r["points"])))


def team_page(team, rows):
    total = sum(r["points"] for r in rows)
    hits  = sum(r["hits"] for r in rows)
    body = [C.header("TEAM", up="../"),
            f"""  <div class="headline"><span>
    <h1 class="name">{esc(team)}</h1>
    <p>{esc(rows[0]['division'])} &middot; captain&rsquo;s roll-up</p>
  </span></div>
  <div class="card"><div class="statgrid three">
    <span class="stat"><b class="num">{total:,}</b><small>TEAM PTS</small></span>
    <span class="stat"><b class="num">{hits}</b><small>HITS</small></span>
    <span class="stat"><b class="num">{len(rows)}</b><small>SCORED</small></span>
  </div></div>
"""]
    for r in rows:
        body.append(f"""  <a class="row" href="../player/{slug(r['player'])}.html">
    <span class="row-rank num">{ordinal(r['rank'])}</span>
    <span class="row-main"><b class="name">{esc(r['player'])}</b>
      <span class="chips">{C.chips_for(r['counts'], allstar.RARE)}</span>
    </span>
    <span class="row-pts"><b class="num">{r['points']:,}</b><span>PTS</span></span>
  </a>
""")
    body.append(f'  <p class="caption">Ranks are within {esc(rows[0]["division"])}. '
                'Tap a name for the turns behind the total.</p>\n')
    return C.page(f"PSDL All Star — {team}", "".join(body), "team", depth=1)


# ---------------------------------------------------------------- standings

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
    <span class="note">DIVISION AVERAGE<br>&rsquo;01 {esc(meta.get('ppr', '&mdash;'))}
    &middot; CRK {esc(meta.get('mpr', '&mdash;'))}</span>
  </div>
"""]
        for c in teams:
            diff = c["leg_wins"] * 2 - c["leg_count"]
            played = c["matches"]
            body.append(f"""  <div class="row">
    <span class="row-rank num{' top' if c['rank'] <= 3 else ''}">{c['rank']}</span>
    <span class="row-main">
      <b class="name">{esc(players.clean_team(c['team_name']))}</b>
      <small>MP {played} &middot; MW {c['win']} &middot;
      {f"LW {c['leg_win_perc']}% &middot; L {diff:+d}" if played else "yet to play"}</small>
      <small>&rsquo;01 {esc(c['ppr'] or '&mdash;')} &middot; CRK {esc(c['mpr'] or '&mdash;')}</small>
    </span>
    <span class="row-pts"><b class="num">{c['league_points']}</b><span>PTS</span></span>
  </div>
""")
        body.append('  <p class="caption">PTS league points &middot; MP matches played &middot; '
                    'MW matches won &middot; LW leg win rate &middot; L leg differential &middot; '
                    '&rsquo;01 and CRK are the team&rsquo;s scoring averages. '
                    'Straight from DartConnect.</p>\n')
        page = C.page(f"PSDL All Star — {division} standings", "".join(body), "standings")
        write(f"standings-{slug(division)}.html", page)
        if division == divisions[0]:
            write("standings.html", page)


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
    build_matches(season)
    build_teams(season, table)
    build_standings(season, divs)

    # A bracketed placeholder must never reach a real page.
    leftovers = []
    for path in OUT.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        for marker in ("[TEAM NAME]", "[OPPONENT TEAM]", "[MPR]", "[ALL STAR CUT]", "None"):
            if marker in text:
                leftovers.append(f"{path.relative_to(OUT)}: {marker}")
    if leftovers:
        print("\n  ! placeholders left in output:", file=sys.stderr)
        for item in leftovers[:10]:
            print(f"      {item}", file=sys.stderr)
        return 1

    print(f"built {len(_written)} pages into {OUT}")
    print(f"  {len([r for r in _written if r.startswith('player/')])} players, "
          f"{len([r for r in _written if r.startswith('match/')])} matches, "
          f"{len([r for r in _written if r.startswith('team/')])} teams")
    if rare:
        print(f"  rare-hit screen: {rare['player']}'s {rare['display']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
