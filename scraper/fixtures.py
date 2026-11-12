"""Upcoming fixtures for the Schedule tab -- pure functions over a season's fixtures.json.

fetch.py writes data/seasons/<id>/fixtures.json for each season DartConnect calls active (the only
networked step); this module only reads it, so a build stays offline and reproducible.

Three things here were not obvious:

  * HOME is the team DartConnect lists first (`left`). DartConnect's own live view labels it that
    way, and the owner chose to follow it (2026-11-11). It is NOT the side recorded as home on
    the board on match night: in played matches the recap's home side matched `left` only about
    half the time. Do not use `left` to label a PLAYED match -- that is ROADMAP finding #8.
  * The lineups feed keeps stale rows: each past week's Division 1 bye, a match that was never
    played, and status 'A' matches that finished but were not finalised. Everything dated before
    today (New York) is dropped. A postponed match therefore reappears only once the
    commissioners give it a new date in DartConnect.
  * "Today" is New York's date, not the build machine's. CI runs in UTC, where a Tuesday-night
    match is already on Wednesday.
"""
import collections, datetime, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import players


def _nth_sunday(year, month, n):
    first = datetime.date(year, month, 1)
    first_sunday = first + datetime.timedelta(days=(6 - first.weekday()) % 7)
    return first_sunday + datetime.timedelta(weeks=n - 1)


def eastern_offset(day):
    """New York's UTC offset on `day`: '-04:00' in daylight saving time, else '-05:00'.

    US rule since 2007: daylight saving runs from the second Sunday in March to the first Sunday
    in November, switching at 2am. Every PSDL match starts at 19:30, nowhere near 2am, so the date
    alone decides. Hand-rolled because zoneinfo needs the tzdata package on Windows, and this
    project is standard library only.
    """
    if isinstance(day, str):
        day = datetime.date.fromisoformat(day)
    start, end = _nth_sunday(day.year, 3, 2), _nth_sunday(day.year, 11, 1)
    return "-04:00" if start <= day < end else "-05:00"


def league_today(now=None):
    """Today's date in New York -- the league's clock, not the build machine's."""
    utc = (now or datetime.datetime.now(datetime.timezone.utc)).astimezone(datetime.timezone.utc)
    standard = utc - datetime.timedelta(hours=5)
    if eastern_offset(standard.date()) == "-04:00":
        return (utc - datetime.timedelta(hours=4)).date()
    return standard.date()


def start_iso(date, time):
    """'2026-11-17', '19:30' -> '2026-11-17T19:30:00-05:00', a moment any browser can parse."""
    return f"{date}T{time}:00{eastern_offset(date)}"


def clock(time):
    """'19:30' -> '7:30 PM'."""
    hours, minutes = (int(part) for part in time.split(":"))
    return f"{(hours - 1) % 12 + 1}:{minutes:02d} {'PM' if hours >= 12 else 'AM'}"


def upcoming(standings, today, path):
    """Match nights from `today` (a date, New York) on, earliest first.

        [{"date", "time", "start", "week",
          "fixtures": [{"id", "division", "home", "away"} | {"id", "division", "bye"}]}]

    Teams resolve through DartConnect's stable team id to their current standings name, exactly
    as played matches do (players.canonical_teams). An id standings does not know, or a row that
    is neither a bye with one team nor a match with two different teams, raises rather than guess.
    """
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing -- run scraper/fetch.py to fetch the schedule")
    rows = json.loads(path.read_text(encoding="utf-8"))["fixtures"]
    canonical = players.canonical_teams(standings)

    def team(row, side):
        tid = (row.get(side) or {}).get("id")
        if tid is None:
            return None
        if tid not in canonical:
            raise ValueError(f"fixture {row['id']} ({row['sched_date']}, {row['division']}): "
                             f"team id {tid} ({row[side].get('team_name')!r}) is not a "
                             f"standings competitor")
        return canonical[tid]

    by_date = collections.defaultdict(list)
    for row in rows:
        if row.get("status") == "C" or row["sched_date"] < today.isoformat():
            continue
        home, away = team(row, "left"), team(row, "right")
        if row.get("is_bye"):
            sides = [t for t in (home, away) if t]
            if len(sides) != 1:
                raise ValueError(f"fixture {row['id']}: a bye should name exactly one team, "
                                 f"got {len(sides)}")
            fixture = {"bye": sides[0]}
        else:
            if not home or not away or home == away:
                raise ValueError(f"fixture {row['id']}: a match needs two different teams, "
                                 f"got {home!r} v {away!r}")
            fixture = {"home": home, "away": away}
        fixture.update(id=row["id"], division=row["division"])
        by_date[row["sched_date"]].append((row, fixture))

    nights = []
    for date in sorted(by_date):
        night_rows = [row for row, _fixture in by_date[date]]
        time = min(row["sched_time"] for row in night_rows)
        # DartConnect's round number. On a regular night every row shares it; a make-up played on
        # an off night keeps its original round, which is the honest label for it.
        rounds = collections.Counter(row["round_seq"] for row in night_rows if row.get("round_seq"))
        fixtures = sorted((f for _row, f in by_date[date]),
                          key=lambda f: (f["division"], "bye" in f,
                                         (f.get("home") or f.get("bye")).lower()))
        nights.append({"date": date, "time": time, "start": start_iso(date, time),
                       "week": rounds.most_common(1)[0][0] if rounds else None,
                       "fixtures": fixtures})
    return nights
