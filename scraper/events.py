"""Season assembly: load archived recaps, attach week/date context, score everything.

This is the single entry point the site build uses. Nothing below reaches the network -- it
reads only what `fetch.py` has already archived, so a build is reproducible and works offline.
"""
import collections, datetime, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import allstar, fetch, players


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


def load_season():
    """Everything the site needs, in one pass over the archive."""
    schedule = json.loads((fetch.DATA / "matches.json").read_text(encoding="utf-8"))
    standings_props = json.loads((fetch.DATA / "standings.json").read_text(encoding="utf-8"))

    entries = list(fetch.iter_matches(schedule))
    dates   = sorted({date for _div, date, _m in entries})
    week_of = {date: i for i, date in enumerate(dates, 1)}

    recaps, hits, busts = [], [], collections.Counter()
    weeks_by_player = collections.defaultdict(set)
    matches = []
    missing = []

    for division, date, m in entries:
        path = fetch.RECAPS / f"{m['dc_match_id']}.json"
        if not path.exists():
            missing.append((division, date, m["dc_match_id"]))
            continue
        props = json.loads(path.read_text(encoding="utf-8"))
        recaps.append(props)

        match_hits, match_busts = allstar.score_match(props, date=date, week=week_of[date])
        for h in match_hits:
            h["player"] = players.clean_name(h["player"])
            weeks_by_player[h["player"]].add(date)
        hits.extend(match_hits)
        busts.update(match_busts)

        info = props["matchInfo"]
        matches.append({
            "id":       info["id"],
            "division": division,
            "date":     date,
            "pretty":   _pretty_date(date),
            "week":     week_of[date],
            "home":     players.clean_team((m.get("left")  or {}).get("team_name")),
            "away":     players.clean_team((m.get("right") or {}).get("team_name")),
            "teams":    allstar.teams_of(props),
            "recap":    allstar.RECAP_URL.format(match_id=info["id"]),
            "hits":     match_hits,
        })

    # Every player who threw gets a team, not just those who scored.
    teams = players.team_map(recaps)
    for h in hits:
        h["team"] = h["team"] or teams.get(h["player"])

    return {
        "schedule":   schedule,
        "standings":  standings_props,
        "recaps":     recaps,
        "hits":       hits,
        "busts":      busts,
        "matches":    matches,
        "teams":      teams,
        "dates":      dates,
        "week_of":    week_of,
        "latest_week": max(week_of.values()) if week_of else 0,
        "latest_date": dates[-1] if dates else None,
        "weeks_by_player": weeks_by_player,
        "missing":    missing,
    }


def divisions(season):
    """Division labels in league order, from the standings feed."""
    seen = []
    for c in season["standings"]["competitors"]:
        if c["division"] not in seen:
            seen.append(c["division"])
    return sorted(seen)


def first_rare_hit(hits):
    """The season's first genuinely rare moment -- a 180, a nine-mark round, a six-cork turn.

    Drives the celebration screen. Ordered by date then by the order hits were scored, so
    "first of the season" means what a player would mean by it.
    """
    headline = ("180", "R9", "C6")
    candidates = [h for h in hits if h["display"] in headline]
    if not candidates:
        return None
    return sorted(candidates, key=lambda h: (h["date"] or "", headline.index(h["display"])))[0]


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
