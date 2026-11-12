"""Season assembly: load archived recaps, attach week/date context, score everything.

This is the single entry point the site build uses. Nothing below reaches the network -- it
reads only what `fetch.py` has already archived, so a build is reproducible and works offline.

The archive holds every season of both leagues (data/seasons.json lists them). load_season()
with no argument is the primary (Tuesday) league's current season -- what the site has always
shown; load_season(id) is any other; load_all() is every season with data, in display order.
"""
import collections, datetime, json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import allstar, fetch, fixtures, players


# ---------------------------------------------------------------- the registry

def registry():
    """Every season fetch.py knows about, as [{id, league, night, label, start_date, active}]."""
    return fetch.read_registry()


def _entry(season_id):
    for entry in registry():
        if entry["id"] == season_id:
            return entry
    raise KeyError(f"season {season_id} is not in {fetch.REGISTRY} -- run scraper/fetch.py")


def _has_recaps(season_id):
    return any((fetch.season_dir(season_id) / "recaps").glob("*.json"))


def season_key(entry):
    """'tuesday-fall-2025' -- stable, readable, and safe in a file name or an HTML id."""
    return re.sub(r"[^a-z0-9]+", "-", f"{entry['night']} {entry['label']}".lower()).strip("-")


def current_id(league=None):
    """A league's current season: the latest-starting one with at least one archived recap.

    Deliberately NOT DartConnect's `active` flag. DartConnect creates a season weeks before its
    first match night and calls it active at once; following the flag would turn the home page
    into an empty board for those weeks. The Schedule, which is about matches to come, uses
    `active` instead -- see build.py.
    """
    league = league or fetch.PRIMARY
    played = [e for e in registry() if e["league"] == league and _has_recaps(e["id"])]
    if not played:
        raise LookupError(f"no archived season for league {league} -- run scraper/fetch.py")
    return max(played, key=lambda e: (e["start_date"] or "", e["id"]))["id"]


def _display_order(entries):
    """The primary league's current season first; then newest first, then league order.

    Three stable sorts, last key first, so each tie falls through to the key before it.
    """
    league_rank = {league: i for i, (league, _night) in enumerate(fetch.LEAGUES)}
    primary = current_id()
    ordered = sorted(entries, key=lambda e: (league_rank.get(e["league"], len(league_rank)),
                                             e["id"]))
    ordered.sort(key=lambda e: e["start_date"] or "", reverse=True)
    ordered.sort(key=lambda e: e["id"] != primary)
    return ordered


def load_all():
    """Every season that has data, in display order -- see _display_order."""
    entries = [e for e in registry() if _has_recaps(e["id"])]
    return [load_season(e["id"]) for e in _display_order(entries)]


_DAYS   = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def _pretty_date(iso):
    # Built by hand, not with strftime: "%-d" is a Linux-only directive and raises ValueError on
    # Windows, and "%a"/"%b" follow the machine's locale. Fixed names keep the output identical
    # everywhere -- "TUE 15 SEP".
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso
    return f"{_DAYS[d.weekday()]} {d.day} {_MONTHS[d.month - 1]}"


def load_season(season_id=None):
    """Everything the site needs about one season, in one pass over its archive.

    `season_id` None is the primary league's current season (current_id) -- what every caller
    that predates the multi-season archive expects.
    """
    entry = _entry(season_id if season_id is not None else current_id())
    root = fetch.season_dir(entry["id"])
    key = season_key(entry)
    schedule = json.loads((root / "matches.json").read_text(encoding="utf-8"))
    standings_props = json.loads((root / "standings.json").read_text(encoding="utf-8"))

    entries = list(fetch.iter_matches(schedule))
    dates   = sorted({date for _div, date, _m in entries})
    week_of = {date: i for i, date in enumerate(dates, 1)}

    # Team names as they stand today, keyed by DartConnect's stable team id. A recap is immutable
    # and holds the name from match night, so these two drift apart whenever a team is renamed.
    # Ids are per season: DartConnect gives a team a new one every season.
    canonical = players.canonical_teams(standings_props)

    recaps, hits, busts = [], [], collections.Counter()
    sided_recaps = []
    # Weeks a player hit an all star in -- what PPW divides by. A week is DartConnect's round
    # (`round_seq`), not a date: a make-up night is a different date in the same round. Fall 2025
    # had 23 match dates over 15 rounds. (In Fall 2026 every round is one date, so it makes no
    # difference there.)
    weeks_by_player = collections.defaultdict(set)
    hit_nights_by_player = collections.defaultdict(set)   # dates with an all star hit
    nights_by_player = collections.defaultdict(set)       # nights played at all -- GP
    matches = []
    missing = []

    for division, date, m in entries:
        path = fetch.recap_path(entry["id"], m["dc_match_id"])
        if not path.exists():
            if m.get("status") == "C":
                missing.append((division, date, m["dc_match_id"]))
            continue
        props = json.loads(path.read_text(encoding="utf-8"))
        recaps.append(props)
        sides = players.resolve_sides(props, m, canonical)
        sided_recaps.append((props, sides))
        for name in players.throwers(props):
            nights_by_player[name].add(date)

        # The division comes from the schedule, which names it as standings does -- see
        # allstar.score_match on Monday's "Division: PS Monday".
        match_hits, match_busts = allstar.score_match(props, date=date, week=week_of[date],
                                                      teams=sides, division=division)
        round_no = m.get("round_seq") or week_of[date]
        for h in match_hits:
            h["player"] = players.clean_name(h["player"])
            h["season"] = key
            h["night"] = entry["night"]
            weeks_by_player[h["player"]].add(round_no)
            hit_nights_by_player[h["player"]].add(date)
        hits.extend(match_hits)
        busts.update(match_busts)

        info = props["matchInfo"]
        matches.append({
            "id":       info["id"],
            "season":   key,
            "division": division,
            "date":     date,
            "pretty":   _pretty_date(date),
            "week":     week_of[date],
            "home":     players.clean_team((m.get("left")  or {}).get("team_name")),
            "away":     players.clean_team((m.get("right") or {}).get("team_name")),
            "teams":    sides,
            "recap":    allstar.RECAP_URL.format(match_id=info["id"]),
            "hits":     match_hits,
        })

    # Every player who threw gets a team, not just those who scored.
    teams = players.team_map(sided_recaps)
    for h in hits:
        h["team"] = h["team"] or teams.get(h["player"])

    # Fixtures exist only for a season DartConnect still calls active. For that season a missing
    # file is an error, as it always was; an archived season simply has none to come.
    fixtures_path = root / "fixtures.json"
    if entry["active"] or fixtures_path.exists():
        upcoming = fixtures.upcoming(standings_props, fixtures.league_today(), fixtures_path)
    else:
        upcoming = []

    return {
        "id":         entry["id"],
        "league":     entry["league"],
        "night":      entry["night"],
        "label":      entry["label"],
        "key":        key,
        "start_date": entry["start_date"],
        "active":     entry["active"],
        "primary":    entry["league"] == fetch.PRIMARY,
        "current":    entry["id"] == current_id(entry["league"]),
        "dir":        root,
        "schedule":   schedule,
        "standings":  standings_props,
        "recaps":     recaps,
        "sided_recaps": sided_recaps,
        "hits":       hits,
        "busts":      busts,
        "matches":    matches,
        "teams":      teams,
        "dates":      dates,
        "week_of":    week_of,
        "latest_week": max(week_of.values()) if week_of else 0,
        "latest_date": dates[-1] if dates else None,
        "weeks_by_player": weeks_by_player,
        "hit_nights_by_player": hit_nights_by_player,
        # League nights each player has played (GP), and the nights each team plays this
        # season per division -- empty for a season nobody has told us about. Together they
        # decide playoff eligibility; see players.playoff_minimum.
        "nights_by_player": nights_by_player,
        "season_nights": players.SEASON_NIGHTS.get(entry["id"], {}),
        "missing":    missing,
        # Match nights still to come, for the Schedule tab -- from the lineups feed, since
        # matches.json only ever lists matches that have started. See fixtures.py.
        "fixtures":   upcoming,
    }


def divisions(season):
    """Division labels in league order, from the standings feed."""
    seen = []
    for c in season["standings"]["competitors"]:
        if c["division"] not in seen:
            seen.append(c["division"])
    return sorted(seen)


def team_table(season, team_name):
    """A captain's roll-up: who scored, with each player's rank inside their division."""
    table = players.division_table(season["hits"], season["weeks_by_player"])
    rows = []
    for division_rows in table.values():
        for row in division_rows:
            if row["team"] == team_name:
                rows.append(row)
    rows.sort(key=lambda r: -r["points"])
    return rows
