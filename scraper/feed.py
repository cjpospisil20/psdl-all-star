"""News feed event generation, computed from archived season data -- both nights.

Walks each season night by night, comparing the state after each match night to the one before.
Every event is generated at a night's end -- never mid-night -- so that the feed stays stable when
the app eventually reads real-time scores during a match night.

The Feed covers the current season of BOTH nights (owner, 2026-11-12: most teams play both), and
every event names its night. Achievements, All Star leaders and standings leaders are per night,
because divisions are. The check-in and checkout records are league-wide, exactly as the Awards
page holds them, so they come from one walk over both nights' hits in date order -- a record card
can never disagree with Awards.

A night is a match date, labelled with DartConnect's round: a make-up on an off night is the
round it made up (Monday's Fall 2026 played round 7 on Wednesday 11 Nov). Standings add up the
matches actually played by each night, not by round, so a make-up counts on the night it was
played.

The single public entry point is generate_events(seasons).
"""
import collections, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import allstar, awards, fetch, players


def generate_events(seasons, board_href=None, standings_href=None):
    """All feed events for these seasons (the current one of each night), newest first.

    board_href(season, division) and standings_href(season, division) say where a leader card
    links; the site's own helpers are passed in so the Feed can never link a page that the build
    did not write. The defaults are the home season's names.
    """
    board_href = board_href or (lambda _season, division: f"{_slug(division)}.html")
    standings_href = standings_href or (lambda _season, division:
                                        f"standings-{_slug(division)}.html")
    all_events = []
    for season in seasons:
        all_events.extend(_season_events(season, board_href, standings_href))
    all_events.extend(_league_records(seasons))

    # Newest night first; within a night, the usual order of card types, then division.
    all_events.sort(key=lambda e: (_type_order(e["type"]), e.get("division") or ""))
    all_events.sort(key=lambda e: e["date"], reverse=True)
    return all_events


def _rounds_by_night(season):
    """{date: the round played that night} -- the round most of that night's matches belong to."""
    counts = collections.defaultdict(collections.Counter)
    for _division, date, m in fetch.iter_matches(season["schedule"]):
        counts[date][m.get("round_seq") or season["week_of"][date]] += 1
    return {date: c.most_common(1)[0][0] for date, c in counts.items()}


def _season_events(season, board_href, standings_href):
    """One night's league: achievements, All Star leaders and standings leaders, night by night."""
    if not season["dates"]:
        return []
    round_of = _rounds_by_night(season)
    night = season["night"]
    canonical = players.canonical_teams(season["standings"])
    team_div = {c["id"]: c["division"] for c in season["standings"]["competitors"]}

    prev_div_leaders, prev_standings = {}, {}
    standings_pts = collections.defaultdict(lambda: collections.defaultdict(int))
    cum_hits, cum_weeks = [], collections.defaultdict(set)
    out = []

    for date in season["dates"]:
        week = round_of[date]
        night_hits = [h for h in season["hits"] if h["date"] == date]
        cum_hits.extend(night_hits)
        for h in night_hits:
            cum_weeks[h["player"]].add(h["date"])

        out.extend(_achievement_events(night_hits, week, date, night))

        table = players.division_table(cum_hits, dict(cum_weeks))
        out.extend(_allstar_leader_events(table, prev_div_leaders, week, date, night,
                                          lambda d: board_href(season, d)))
        prev_div_leaders = {d: rows[0]["player"] for d, rows in table.items() if rows}

        _accumulate_standings(season["schedule"], date, standings_pts, team_div)
        out.extend(_standings_events(standings_pts, prev_standings, canonical, team_div,
                                     week, date, night, lambda d: standings_href(season, d)))
        for div in set(team_div.values()):
            div_teams = standings_pts.get(div, {})
            if div_teams:
                prev_standings[div] = max(div_teams, key=lambda t: div_teams[t])
    return out


def _league_records(seasons):
    """The league-wide check-in and checkout records, over both nights' hits in date order --
    the same records the Awards page shows (awards.largest_checkins / largest_checkouts)."""
    round_of = {s["key"]: _rounds_by_night(s) for s in seasons}
    hits_by_date = collections.defaultdict(list)
    for s in seasons:
        for h in s["hits"]:
            hits_by_date[h["date"]].append(h)

    cum_hits, out = [], []
    prev_checkin = prev_checkout = None
    for date in sorted(hits_by_date):
        cum_hits.extend(hits_by_date[date])

        checkins = awards.largest_checkins(cum_hits)
        out.extend(_record_events(checkins, prev_checkin, "checkin", round_of, date))
        prev_checkin = (checkins[0]["player"], checkins[0]["turn_value"]) if checkins else None

        checkouts = awards.largest_checkouts(cum_hits)
        out.extend(_record_events(checkouts, prev_checkout, "checkout", round_of, date))
        prev_checkout = (checkouts[0]["player"], checkouts[0]["turn_value"]) if checkouts else None
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

        # Perfect rounds only: the feed follows the R9 Club award (owner, 2026-11-11).
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

def _allstar_leader_events(table, prev, week, date, night, href):
    out = []
    for div, rows in sorted(table.items()):
        if not rows:
            continue
        leader = rows[0]["player"]
        pts = rows[0]["points"]
        old = prev.get(div)
        if old is None:
            out.append(_event(
                "allstar-leader",
                f"{leader} leads {_short_div(div)} in All Star Points",
                f"After Week {week}, {leader} ({pts:,} pts) is the first "
                f"{div} all-star points leader of the season.",
                week, date, division=div,
                link_href=href(div),
                icon_type="svg", icon_name="star"))
        elif old != leader:
            out.append(_event(
                "allstar-leader",
                f"{leader} takes the {_short_div(div)} all-star lead",
                f"After Week {week}, {leader} ({pts:,} pts) overtakes "
                f"{old} to lead {div} in All Star Points.",
                week, date, division=div,
                link_href=href(div),
                icon_type="svg", icon_name="star"))
    for e in out:
        e["night"] = night
    return out


def _record_events(entries, prev, record_type, round_of, date):
    """A record card when the league-wide best changes hands or rises. `round_of` maps each
    season key to {date: round}, so the card carries the week of the night the record was set."""
    if not entries:
        return []
    best = entries[0]
    player, value = best["player"], best["turn_value"]
    hit = best
    week = round_of[hit["season"]][hit["date"]]

    if record_type == "checkin":
        label = "check-in"
        verb_new, verb_open = "raises the check-in record to", "opens the check-in record at"
    else:
        label = "checkout"
        verb_new, verb_open = "raises the checkout record to", "opens the checkout record at"
    award_page = "awards.html"

    if prev is None:
        event = _event(
            f"{record_type}-record",
            f"{player} {verb_open} {value}",
            f"In the {hit['segment']} on {_pretty(hit['date'])}, "
            f"{player} hit a {value} {label} for "
            f"{hit['team']} in {hit['division']}.",
            week, date, division=hit["division"], hit=hit,
            link_href=award_page, icon_type="svg", icon_name="award")
        event["night"] = hit["night"]
        return [event]

    old_player, old_value = prev
    if value > old_value or (value == old_value and player != old_player):
        event = _event(
            f"{record_type}-record",
            f"{player} {verb_new} {value}",
            f"In the {hit['segment']} on {_pretty(hit['date'])}, "
            f"{player} hit a {value} {label} for {hit['team']} "
            f"in {hit['division']}, overtaking {old_player}'s {old_value}.",
            week, date, division=hit["division"], hit=hit,
            link_href=award_page, icon_type="svg", icon_name="award")
        event["night"] = hit["night"]
        return [event]
    return []


# ---------------------------------------------------------------- standings changes

def _accumulate_standings(schedule, night, accum, team_div):
    """Add the league points of every match completed on `night` (a date). By date rather than
    by round, so a make-up counts on the night it was actually played."""
    for _div_name, by_date in schedule.get("reg", {}).items():
        for date, matches in by_date.items():
            if date != night:
                continue
            for m in matches:
                if m.get("status") != "C":
                    continue
                left = m.get("left") or {}
                right = m.get("right") or {}
                for side, pts_key in ((left, "home_league_points"),
                                       (right, "away_league_points")):
                    tid = side.get("id")
                    pts = m.get(pts_key)
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
        leader_id = max(div_teams, key=lambda t: div_teams[t])
        leader_pts = div_teams[leader_id]
        leader_name = canonical.get(leader_id, f"Team {leader_id}")
        old_id = prev.get(div)

        if old_id is None:
            out.append(_event(
                "standings-leader",
                f"{leader_name} leads {_short_div(div)} after Week {week}",
                f"{leader_name} ({leader_pts} league pts) is the first "
                f"{div} standings leader of the season.",
                week, date, division=div,
                link_href=href(div),
                icon_type="svg", icon_name="standings"))
        elif old_id != leader_id:
            old_name = canonical.get(old_id, f"Team {old_id}")
            out.append(_event(
                "standings-leader",
                f"{leader_name} takes first in {_short_div(div)}",
                f"After Week {week}, {leader_name} ({leader_pts} league pts) "
                f"moves past {old_name} to the top of {div}.",
                week, date, division=div,
                link_href=href(div),
                icon_type="svg", icon_name="standings"))
    for e in out:
        e["night"] = night
    return out


# ---------------------------------------------------------------- helpers

_DAYS   = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def _pretty(iso):
    import datetime
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso
    return f"{_DAYS[d.weekday()]} {d.day} {_MONTHS[d.month - 1]}"


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
        "night":      None,           # set by each event builder -- every card names its night
        "division":   division,
        "hit":        hit,
        "link_href":  link_href,
        "link_label": headline,
        "icon_type":  icon_type,
        "icon_name":  icon_name,
    }
