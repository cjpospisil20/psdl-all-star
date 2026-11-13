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


def base_label(label):
    """Strip a trailing ' Stage N' — 'Spring 2026 Stage 1' becomes 'Spring 2026'."""
    return re.sub(r"\s+[Ss]tage\s+\d+$", "", label)


def season_order(seasons):
    """The owner's order: newest season first, Tuesday before Monday inside each season.

    A season's group is its base label across both nights. Groups run newest first by the
    earliest start_date in the group; inside a group, Tuesday first (fetch.LEAGUES rank),
    then newest first. Three stable sorts, last key first.
    """
    league_rank = {league: i for i, (league, _night) in enumerate(fetch.LEAGUES)}
    group_date = {}
    for s in seasons:
        bl = base_label(s["label"])
        d = s.get("start_date") or ""
        if bl not in group_date or d < group_date[bl]:
            group_date[bl] = d

    ordered = sorted(seasons, key=lambda s: s.get("id", 0))
    ordered.sort(key=lambda s: league_rank.get(s.get("league", ""), len(league_rank)))
    ordered.sort(key=lambda s: group_date.get(base_label(s["label"]), ""), reverse=True)
    return ordered


def _display_order(entries):
    """season_order plus the home season forced to the front."""
    primary = current_id()
    ordered = season_order(entries)
    ordered.sort(key=lambda e: e["id"] != primary)
    return ordered


def _can_merge(parts):
    """Whether stage-labelled seasons should be merged: same league, none is current, first
    stage (chronologically) has one division. While a staged season is current, Standings, the
    Schedule, team pages, Awards and the Feed follow DartConnect's current stage, so it stays
    separate."""
    if not parts or len(parts) < 2:
        return False
    if any(e["id"] == current_id(e["league"]) for e in parts):
        return False
    first = min(parts, key=lambda e: e["start_date"] or "")
    divs = set()
    for c in json.loads((fetch.season_dir(first["id"]) / "standings.json")
                        .read_text(encoding="utf-8"))["competitors"]:
        divs.add(c["division"])
    return len(divs) == 1


def merge_stages(parts):
    """Build one season dict from stage seasons. `parts` must be sorted by start_date."""
    loaded = [load_season(e["id"]) for e in parts]
    first = loaded[0]
    label = base_label(first["label"])
    key = re.sub(r"[^a-z0-9]+", "-", f"{first['night']} {label}".lower()).strip("-")

    all_hits, all_matches, all_recaps, all_sided = [], [], [], []
    legs_by_player = collections.Counter()
    hit_nights_by_player = collections.defaultdict(set)
    nights_by_player = collections.defaultdict(set)
    all_dates = set()
    week_of = {}
    division = first["divisions"][0] if first.get("divisions") else divisions(first)[0]

    for stage in loaded:
        for h in stage["hits"]:
            copy = dict(h)
            copy["season"] = key
            copy["division"] = division
            all_hits.append(copy)
        for m in stage["matches"]:
            copy = dict(m)
            copy["season"] = key
            copy["division"] = division
            all_matches.append(copy)
        all_recaps.extend(stage["recaps"])
        all_sided.extend(stage["sided_recaps"])
        all_dates.update(stage["dates"])
        week_of.update(stage["week_of"])
        legs_by_player.update(stage["legs_by_player"])     # different matches, so legs add
        for player, nights in stage["hit_nights_by_player"].items():
            hit_nights_by_player[player].update(nights)
        for player, nights in stage["nights_by_player"].items():
            nights_by_player[player].update(nights)

    teams = players.team_map(all_sided)
    for h in all_hits:
        h["team"] = h["team"] or teams.get(h["player"])

    last = loaded[-1]
    return {
        "id":         parts[0]["id"],
        "league":     first["league"],
        "night":      first["night"],
        "label":      label,
        "key":        key,
        "start_date": first["start_date"],
        "active":     False,
        "primary":    first["primary"],
        "current":    False,
        "dir":        first["dir"],
        "schedule":   last["schedule"],
        "standings":  last["standings"],
        "recaps":     all_recaps,
        "sided_recaps": all_sided,
        "hits":       all_hits,
        "busts":      sum((s["busts"] for s in loaded), collections.Counter()),
        "matches":    all_matches,
        "teams":      teams,
        "dates":      sorted(all_dates),
        "week_of":    week_of,
        "latest_week": max((s["latest_week"] for s in loaded), default=0),
        "latest_date": max((s["latest_date"] for s in loaded if s["latest_date"]),
                           default=None),
        "legs_by_player": dict(legs_by_player),
        "hit_nights_by_player": dict(hit_nights_by_player),
        "nights_by_player": dict(nights_by_player),
        "season_nights": {},
        "missing":    [m for s in loaded for m in s["missing"]],
        "fixtures":   [],
        "stages":     loaded,
    }


def load_all():
    """Every season that has data, in display order. Stages of the same season are merged when
    eligible (same base label, same league, not current, first stage has one division)."""
    entries = [e for e in registry() if _has_recaps(e["id"])]
    ordered = _display_order(entries)

    league_rank = {league: i for i, (league, _night) in enumerate(fetch.LEAGUES)}
    groups = collections.OrderedDict()
    for e in ordered:
        bl = base_label(e["label"])
        gk = (e["league"], bl)
        groups.setdefault(gk, []).append(e)

    result = []
    for (league, bl), parts in groups.items():
        stage_parts = [e for e in parts if base_label(e["label"]) != e["label"]]
        if len(stage_parts) >= 2 and _can_merge(stage_parts):
            stage_parts.sort(key=lambda e: e["start_date"] or "")
            merged = merge_stages(stage_parts)
            non_stages = [e for e in parts if e not in stage_parts]
            for e in non_stages:
                result.append(load_season(e["id"]))
            result.append(merged)
        else:
            for e in parts:
                result.append(load_season(e["id"]))

    primary = current_id()
    result.sort(key=lambda s: s["id"] != primary)

    seen_keys = set()
    deduped = []
    for s in result:
        if s["key"] not in seen_keys:
            seen_keys.add(s["key"])
            deduped.append(s)
    return deduped


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
    # Legs each player threw in, every format -- what PPL (points per leg) divides by. See
    # players.legs_played.
    legs_by_player = collections.Counter()
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
        legs_by_player.update(players.legs_played(props))

        # The division comes from the schedule, which names it as standings does -- see
        # allstar.score_match on Monday's "Division: PS Monday".
        match_hits, match_busts = allstar.score_match(props, date=date, week=week_of[date],
                                                      teams=sides, division=division)
        for h in match_hits:
            h["player"] = players.clean_name(h["player"])
            h["season"] = key
            h["night"] = entry["night"]
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

    # How far the season has got: its latest DartConnect round, and the night most of that round
    # was played. Not the last date -- Monday's Fall 2026 played a round-7 make-up on Wednesday
    # 11 Nov, after round 9, and "WEEK 10 · WED 11 NOV" would be wrong twice over.
    rounds = [(m.get("round_seq") or week_of[date], date) for _div, date, m in entries]
    latest_week = max((r for r, _date in rounds), default=0)
    nights = collections.Counter(date for r, date in rounds if r == latest_week)
    latest_date = max(nights, key=lambda d: (nights[d], d)) if nights else None

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
        "latest_week": latest_week,
        "latest_date": latest_date,
        "legs_by_player": dict(legs_by_player),
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
    """Division labels in league order, from the standings feed. A merged season uses its
    first stage's divisions (all hits carry that one division)."""
    if "stages" in season:
        return divisions(season["stages"][0])
    seen = []
    for c in season["standings"]["competitors"]:
        if c["division"] not in seen:
            seen.append(c["division"])
    return sorted(seen)


def team_table(season, team_name):
    """A captain's roll-up: who scored, with each player's rank inside their division."""
    table = players.division_table(season["hits"], season["legs_by_player"])
    rows = []
    for division_rows in table.values():
        for row in division_rows:
            if row["team"] == team_name:
                rows.append(row)
    rows.sort(key=lambda r: -r["points"])
    return rows
