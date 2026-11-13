"""News feed event generation, computed from archived season data -- both nights.

Walks each season night by night, comparing the state after each match night to the one before.
Every event is generated at a night's end -- never mid-night -- so that the feed stays stable when
the app eventually reads real-time scores during a match night.

The Feed covers the current season of BOTH nights (owner, 2026-11-12: most teams play both),
grouped by night. Achievements, All Star leaders, standings leaders and records are per night,
because divisions are and because the league awards check-in and checkout records per night
(owner, 2026-11-12). A night heading separates each date's cards.

A night is a match date, labelled with DartConnect's round: a make-up on an off night is the
round it made up (Monday's Fall 2026 played round 7 on Wednesday 11 Nov). Standings add up the
matches actually played by each night, not by round, so a make-up counts on the night it was
played. Each side's own `points` field (`left.points`, `right.points`) is the source of truth --
NOT `home_league_points` / `away_league_points`, which belong to the recorded home side and that
is `left` only about half the time.

The single public entry point is generate_events(seasons).
"""
import collections, datetime, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import allstar, awards, fetch, players


def generate_events(seasons, board_href=None, standings_href=None, award_href=None):
    """All feed events for these seasons (the current one of each night), newest first.

    board_href(season, division), standings_href(season, division) and award_href(season, key)
    say where leader and record cards link; the site's own helpers are passed in so the Feed can
    never link a page that the build did not write.
    """
    board_href = board_href or (lambda _season, division: f"{_slug(division)}.html")
    standings_href = standings_href or (lambda _season, division:
                                        f"standings-{_slug(division)}.html")
    award_href = award_href or (lambda _season, _key: "awards.html")

    league_rank = {league: i for i, (league, _night) in enumerate(fetch.LEAGUES)}
    all_events = []
    for season in seasons:
        all_events.extend(_season_events(season, board_href, standings_href, award_href))

    all_events.sort(key=lambda e: (_type_order(e["type"]), e.get("division") or ""))
    all_events.sort(key=lambda e: league_rank.get(
        next((l for l, n in fetch.LEAGUES if n == e["night"]), ""), len(league_rank)))
    all_events.sort(key=lambda e: e["date"], reverse=True)
    return all_events


def standings_by_night(season):
    """Cumulative league standings after each match night, from each side's own points.

    Returns [(date, {division: {team_id: pts}}, {team_id: matches_played})] in date order.
    Each side carries its own `points` (`left.points`, `right.points`). Summed per team, those
    reproduce DartConnect's `league_points` and `matches` exactly: verified across all six
    seasons (26, 28, 8, 8, 31, 7 teams).
    """
    team_div = {c["id"]: c["division"] for c in season["standings"]["competitors"]}
    pts = collections.defaultdict(lambda: collections.defaultdict(int))
    played = collections.defaultdict(int)
    result = []
    for date in season["dates"]:
        changed = False
        for _div_name, by_date in season["schedule"].get("reg", {}).items():
            for match_date, matches in by_date.items():
                if match_date != date:
                    continue
                for m in matches:
                    if m.get("status") != "C":
                        continue
                    changed = True
                    left = m.get("left") or {}
                    right = m.get("right") or {}
                    for side in (left, right):
                        tid = side.get("id")
                        side_pts = side.get("points")
                        if tid and side_pts is not None:
                            div = team_div.get(tid)
                            if div:
                                pts[div][tid] += int(side_pts)
                            played[tid] += 1
        if changed:
            snapshot = {div: dict(teams) for div, teams in pts.items()}
            result.append((date, snapshot, dict(played)))
    return result


def _rounds_by_night(season):
    """{date: the round played that night} -- the round most of that night's matches belong to."""
    counts = collections.defaultdict(collections.Counter)
    for _division, date, m in fetch.iter_matches(season["schedule"]):
        counts[date][m.get("round_seq") or season["week_of"][date]] += 1
    return {date: c.most_common(1)[0][0] for date, c in counts.items()}


def _season_events(season, board_href, standings_href, award_href):
    """One night's league: achievements, All Star leaders, standings leaders and records."""
    if not season["dates"]:
        return []
    round_of = _rounds_by_night(season)
    night = season["night"]
    canonical = players.canonical_teams(season["standings"])
    team_div = {c["id"]: c["division"] for c in season["standings"]["competitors"]}

    prev_div_leaders = {}
    prev_standings = {}
    standings_pts = collections.defaultdict(lambda: collections.defaultdict(int))
    cum_hits = []
    prev_checkin = prev_checkout = None
    out = []

    for date in season["dates"]:
        week = round_of[date]
        night_hits = [h for h in season["hits"] if h["date"] == date]
        cum_hits.extend(night_hits)

        out.extend(_achievement_events(night_hits, week, date, night))

        # Leaders go on points alone, so the table needs no legs (its PPL stays None).
        table = players.division_table(cum_hits)
        out.extend(_allstar_leader_events(table, prev_div_leaders, week, date, night,
                                          lambda d: board_href(season, d)))
        for d, rows in table.items():
            if rows:
                top_pts = rows[0]["points"]
                prev_div_leaders[d] = frozenset(
                    r["player"] for r in rows if r["points"] == top_pts)

        _accumulate_standings(season["schedule"], date, standings_pts, team_div)
        out.extend(_standings_events(standings_pts, prev_standings, canonical, team_div,
                                     week, date, night, lambda d: standings_href(season, d)))
        for div in set(team_div.values()):
            div_teams = standings_pts.get(div, {})
            if div_teams:
                prev_standings[div] = _leader_set(div_teams)

        checkins = awards.largest_checkins(cum_hits)
        record_evts, prev_checkin = _record_events(
            checkins, prev_checkin, "checkin", week, date, night,
            award_href(season, "largest-checkin"))
        out.extend(record_evts)

        checkouts = awards.largest_checkouts(cum_hits)
        record_evts, prev_checkout = _record_events(
            checkouts, prev_checkout, "checkout", week, date, night,
            award_href(season, "largest-checkout"))
        out.extend(record_evts)

    return out


def _type_order(t):
    order = ["standings-leader", "allstar-leader", "checkin-record",
             "checkout-record", "180", "171-plus", "r9", "c5-plus", "big-fish"]
    return order.index(t) if t in order else len(order)


# ---------------------------------------------------------------- achievement events

def _achievement_events(week_hits, week, date, night):
    out = []
    for h in week_hits:
        if h["code"] == "95+" and h["turn_value"] == 180:
            out.append(_event(
                "180",
                f"{h['player']} throws a 180",
                f"In the {h['segment']} on {_pretty(h['date'])}, "
                f"{h['player']} hit three triple twenties for "
                f"{h['team']} in {h['division']}.",
                week, date, division=h["division"], hit=h,
                link_href=h["recap"], icon_type="chip", icon_name="180"))

        elif h["code"] == "95+" and h["turn_value"] >= 171:
            out.append(_event(
                "171-plus",
                f"{h['player']} fires a {h['turn_value']}",
                f"In the {h['segment']} on {_pretty(h['date'])}, "
                f"{h['player']} threw {h['turn_value']} for "
                f"{h['team']} in {h['division']}.",
                week, date, division=h["division"], hit=h,
                link_href=h["recap"], icon_type="chip", icon_name="171+"))

        if h["code"] == "F90" and h["turn_value"] == 170:
            out.append(_event(
                "big-fish",
                f"{h['player']} lands the Big Fish",
                f"In the {h['segment']} on {_pretty(h['date'])}, "
                f"{h['player']} checked out a perfect 170 for "
                f"{h['team']} in {h['division']}.",
                week, date, division=h["division"], hit=h,
                link_href=h["recap"], icon_type="chip", icon_name="F90"))

        if h["code"] == "R9":
            marks = h["turn_value"]
            out.append(_event(
                "r9",
                f"{h['player']} throws {marks} marks in a Cricket turn",
                f"In {h['segment']} on {_pretty(h['date'])}, "
                f"{h['player']} put up {marks} marks for "
                f"{h['team']} in {h['division']}.",
                week, date, division=h["division"], hit=h,
                link_href=h["recap"], icon_type="chip", icon_name=h["code"]))

        if h["code"] in ("C5", "C6"):
            marks = h["turn_value"]
            out.append(_event(
                "c5-plus",
                f"{h['player']} throws {marks} bullseye marks",
                f"In {h['segment']} on {_pretty(h['date'])}, "
                f"{h['player']} threw {marks} bullseye marks for "
                f"{h['team']} in {h['division']}.",
                week, date, division=h["division"], hit=h,
                link_href=h["recap"], icon_type="chip", icon_name=h["code"]))
    for e in out:
        e["night"] = night
    return out


# ---------------------------------------------------------------- leader changes

def _leader_set(scores):
    """Frozenset of keys tied at the highest value."""
    if not scores:
        return frozenset()
    top = max(scores.values())
    return frozenset(k for k, v in scores.items() if v == top)


def _names(named, canonical=None):
    """'A', 'A and B', 'A, B and C'. If canonical maps ids to names, resolve first."""
    if canonical:
        names = sorted(canonical.get(n, str(n)) for n in named)
    else:
        names = sorted(named)
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _allstar_leader_events(table, prev, week, date, night, href):
    out = []
    for div, rows in sorted(table.items()):
        if not rows:
            continue
        top_pts = rows[0]["points"]
        current = frozenset(r["player"] for r in rows if r["points"] == top_pts)
        old = prev.get(div)

        if old is None:
            if len(current) == 1:
                leader = next(iter(current))
                out.append(_event(
                    "allstar-leader",
                    f"{leader} leads {_short_div(div)} in All Star Points",
                    f"After Week {week}, {leader} ({top_pts:,} pts) is the first "
                    f"{div} all-star points leader of the season.",
                    week, date, division=div,
                    link_href=href(div),
                    icon_type="svg", icon_name="star"))
            else:
                out.append(_event(
                    "allstar-leader",
                    f"{_names(current)} share the {_short_div(div)} all-star lead",
                    f"After Week {week}, {_names(current)} are level on {top_pts:,} pts "
                    f"at the top of {div}.",
                    week, date, division=div,
                    link_href=href(div),
                    icon_type="svg", icon_name="star"))
        elif current != old:
            if len(current) == 1:
                leader = next(iter(current))
                if len(old) > 1:
                    out.append(_event(
                        "allstar-leader",
                        f"{leader} pulls clear at the top of {_short_div(div)}",
                        f"After Week {week}, {leader} ({top_pts:,} pts) breaks away "
                        f"from the shared lead in {div} All Star Points.",
                        week, date, division=div,
                        link_href=href(div),
                        icon_type="svg", icon_name="star"))
                else:
                    old_name = next(iter(old))
                    out.append(_event(
                        "allstar-leader",
                        f"{leader} takes the {_short_div(div)} all-star lead",
                        f"After Week {week}, {leader} ({top_pts:,} pts) overtakes "
                        f"{old_name} to lead {div} in All Star Points.",
                        week, date, division=div,
                        link_href=href(div),
                        icon_type="svg", icon_name="star"))
            else:
                out.append(_event(
                    "allstar-leader",
                    f"{_names(current)} share the {_short_div(div)} all-star lead",
                    f"After Week {week}, {_names(current)} are level on {top_pts:,} pts "
                    f"at the top of {div}.",
                    week, date, division=div,
                    link_href=href(div),
                    icon_type="svg", icon_name="star"))
    for e in out:
        e["night"] = night
    return out


def _record_events(entries, prev, record_type, week, date, night, link_href):
    """A record card when this night's best changes hands or rises. Returns (events, new_prev)."""
    if not entries:
        return [], prev
    best = entries[0]
    player, value = best["player"], best["turn_value"]
    hit = best

    if record_type == "checkin":
        label = "check-in"
        verb_new, verb_open = "raises the check-in record to", "opens the check-in record at"
    else:
        label = "checkout"
        verb_new, verb_open = "raises the checkout record to", "opens the checkout record at"

    new_prev = (player, value)

    if prev is None:
        event = _event(
            f"{record_type}-record",
            f"{player} {verb_open} {value}",
            f"In the {hit['segment']} on {_pretty(hit['date'])}, "
            f"{player} hit a {value} {label} for "
            f"{hit['team']} in {hit['division']}.",
            week, date, division=hit["division"], hit=hit,
            link_href=link_href, icon_type="svg", icon_name="award")
        event["night"] = night
        return [event], new_prev

    old_player, old_value = prev
    if value > old_value:
        if player == old_player:
            event = _event(
                f"{record_type}-record",
                f"{player} {verb_new} {value}",
                f"In the {hit['segment']} on {_pretty(hit['date'])}, "
                f"{player} hit a {value} {label} for {hit['team']} "
                f"in {hit['division']}, beating their own {old_value}.",
                week, date, division=hit["division"], hit=hit,
                link_href=link_href, icon_type="svg", icon_name="award")
        else:
            event = _event(
                f"{record_type}-record",
                f"{player} {verb_new} {value}",
                f"In the {hit['segment']} on {_pretty(hit['date'])}, "
                f"{player} hit a {value} {label} for {hit['team']} "
                f"in {hit['division']}, overtaking {old_player}'s {old_value}.",
                week, date, division=hit["division"], hit=hit,
                link_href=link_href, icon_type="svg", icon_name="award")
        event["night"] = night
        return [event], new_prev

    if value == old_value and player != old_player:
        event = _event(
            f"{record_type}-record",
            f"{player} {verb_new} {value}",
            f"In the {hit['segment']} on {_pretty(hit['date'])}, "
            f"{player} hit a {value} {label} for {hit['team']} "
            f"in {hit['division']}, overtaking {old_player}'s {old_value}.",
            week, date, division=hit["division"], hit=hit,
            link_href=link_href, icon_type="svg", icon_name="award")
        event["night"] = night
        return [event], new_prev

    return [], new_prev


# ---------------------------------------------------------------- standings changes

def _accumulate_standings(schedule, night, accum, team_div):
    """Add the league points of every match completed on `night` (a date).

    Uses each side's own `points` field -- NOT `home_league_points` / `away_league_points`,
    which belong to the side recorded as home on match night, and that is `left` only about
    half the time. Summed per team, `left.points` and `right.points` reproduce DartConnect's
    `league_points` and `matches` exactly across all six seasons.
    """
    for _div_name, by_date in schedule.get("reg", {}).items():
        for date, matches in by_date.items():
            if date != night:
                continue
            for m in matches:
                if m.get("status") != "C":
                    continue
                left = m.get("left") or {}
                right = m.get("right") or {}
                for side in (left, right):
                    tid = side.get("id")
                    pts = side.get("points")
                    if tid and pts is not None:
                        div = team_div.get(tid)
                        if div:
                            accum[div][tid] += int(pts)


def _standings_events(standings_pts, prev, canonical, team_div, week, date, night, href):
    out = []
    for div in sorted(set(team_div.values())):
        div_teams = standings_pts.get(div, {})
        if not div_teams:
            continue
        current = _leader_set(div_teams)
        top_pts = max(div_teams.values())
        old = prev.get(div)

        if old is None:
            if len(current) == 1:
                leader_id = next(iter(current))
                leader_name = canonical.get(leader_id, f"Team {leader_id}")
                out.append(_event(
                    "standings-leader",
                    f"{leader_name} leads {_short_div(div)} after Week {week}",
                    f"{leader_name} ({top_pts} league pts) is the first "
                    f"{div} standings leader of the season.",
                    week, date, division=div,
                    link_href=href(div),
                    icon_type="svg", icon_name="standings"))
            else:
                out.append(_event(
                    "standings-leader",
                    f"{_names(current, canonical)} share the {_short_div(div)} lead "
                    f"after Week {week}",
                    f"{_names(current, canonical)} are level on {top_pts} league pts "
                    f"at the top of {div} after the first night.",
                    week, date, division=div,
                    link_href=href(div),
                    icon_type="svg", icon_name="standings"))
        elif current != old:
            if len(current) == 1:
                leader_id = next(iter(current))
                leader_name = canonical.get(leader_id, f"Team {leader_id}")
                if len(old) > 1:
                    out.append(_event(
                        "standings-leader",
                        f"{leader_name} pulls clear at the top of {_short_div(div)}",
                        f"After Week {week}, {leader_name} ({top_pts} league pts) "
                        f"breaks away from the shared lead in {div}.",
                        week, date, division=div,
                        link_href=href(div),
                        icon_type="svg", icon_name="standings"))
                else:
                    old_id = next(iter(old))
                    old_name = canonical.get(old_id, f"Team {old_id}")
                    out.append(_event(
                        "standings-leader",
                        f"{leader_name} takes first in {_short_div(div)}",
                        f"After Week {week}, {leader_name} ({top_pts} league pts) "
                        f"moves past {old_name} to the top of {div}.",
                        week, date, division=div,
                        link_href=href(div),
                        icon_type="svg", icon_name="standings"))
            else:
                out.append(_event(
                    "standings-leader",
                    f"{_names(current, canonical)} share first in {_short_div(div)}",
                    f"After Week {week}, {_names(current, canonical)} are level on "
                    f"{top_pts} league pts at the top of {div}.",
                    week, date, division=div,
                    link_href=href(div),
                    icon_type="svg", icon_name="standings"))
    for e in out:
        e["night"] = night
    return out


# ---------------------------------------------------------------- helpers

_DAYS   = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _pretty(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso
    return f"{_DAYS[d.weekday()]} {d.day} {_MONTHS[d.month - 1]}"


def weekday_name(iso):
    """Full weekday name for a date string -- used by the site to detect off-night games."""
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    return _WEEKDAYS[d.weekday()]


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def _short_div(div):
    """"Division 3" -> "Div 3". Any other name -- Monday's "PS Monday" -- is short enough as it is
    (and "Monday D1" must not become a "Div 1" that reads as Tuesday's)."""
    m = re.fullmatch(r"Division\s*(\d+)", div)
    return f"Div {m.group(1)}" if m else div


def _event(type, headline, body, week, date, division=None, hit=None,
           link_href="", icon_type="svg", icon_name="star"):
    return {
        "type":       type,
        "headline":   headline,
        "body":       body,
        "week":       week,
        "date":       date,
        "night":      None,
        "division":   division,
        "hit":        hit,
        "link_href":  link_href,
        "link_label": headline,
        "icon_type":  icon_type,
        "icon_name":  icon_name,
    }
