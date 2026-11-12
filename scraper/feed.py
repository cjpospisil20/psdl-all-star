"""News feed event generation, computed from archived season data.

Walks through the season week by week, comparing end-of-week state to the previous week.
Every event is generated at a week boundary — never mid-week — so that the feed stays
stable when the app eventually reads real-time scores during a match night.

The single public entry point is generate_events(season).
"""
import collections, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import allstar, awards, fetch, players


def generate_events(season):
    """All feed events for the season, newest first."""
    week_of = season["week_of"]
    if not week_of:
        return []

    weeks_in_order = sorted(set(week_of.values()))
    date_for_week = {}
    for date, wk in week_of.items():
        if wk not in date_for_week or date > date_for_week[wk]:
            date_for_week[wk] = date

    canonical = players.canonical_teams(season["standings"])
    team_div = {c["id"]: c["division"] for c in season["standings"]["competitors"]}

    prev_div_leaders = {}
    prev_checkin = None
    prev_checkout = None
    prev_standings = {}
    standings_pts = collections.defaultdict(lambda: collections.defaultdict(int))

    cum_hits = []
    cum_weeks = collections.defaultdict(set)
    all_events = []

    for week_num in weeks_in_order:
        date = date_for_week[week_num]
        week_hits = [h for h in season["hits"] if h["week"] == week_num]
        cum_hits.extend(week_hits)
        for h in week_hits:
            cum_weeks[h["player"]].add(h["date"])

        all_events.extend(_achievement_events(week_hits, week_num, date))

        table = players.division_table(cum_hits, dict(cum_weeks))
        all_events.extend(
            _allstar_leader_events(table, prev_div_leaders, week_num, date))
        prev_div_leaders = {d: rows[0]["player"] for d, rows in table.items() if rows}

        checkins = awards.largest_checkins(cum_hits)
        all_events.extend(
            _record_events(checkins, prev_checkin, "checkin", week_num, date))
        prev_checkin = (checkins[0]["player"], checkins[0]["turn_value"]) if checkins else None

        checkouts = awards.largest_checkouts(cum_hits)
        all_events.extend(
            _record_events(checkouts, prev_checkout, "checkout", week_num, date))
        prev_checkout = (checkouts[0]["player"], checkouts[0]["turn_value"]) if checkouts else None

        _accumulate_standings(season["schedule"], week_num, standings_pts, team_div)
        all_events.extend(
            _standings_events(standings_pts, prev_standings, canonical, team_div,
                              week_num, date))
        for div in set(team_div.values()):
            div_teams = standings_pts.get(div, {})
            if div_teams:
                prev_standings[div] = max(div_teams, key=lambda t: div_teams[t])

    all_events.sort(key=lambda e: (-e["week"], _type_order(e["type"]),
                                    e.get("division") or ""))
    return all_events


def _type_order(t):
    order = ["standings-leader", "allstar-leader", "checkin-record",
             "checkout-record", "180", "171-plus", "r9", "c5-plus", "big-fish"]
    return order.index(t) if t in order else len(order)


# ---------------------------------------------------------------- achievement events

def _achievement_events(week_hits, week, date):
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
    return out


# ---------------------------------------------------------------- leader changes

def _allstar_leader_events(table, prev, week, date):
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
                link_href=f"{_slug(div)}.html",
                icon_type="svg", icon_name="star"))
        elif old != leader:
            out.append(_event(
                "allstar-leader",
                f"{leader} takes the {_short_div(div)} all-star lead",
                f"After Week {week}, {leader} ({pts:,} pts) overtakes "
                f"{old} to lead {div} in All Star Points.",
                week, date, division=div,
                link_href=f"{_slug(div)}.html",
                icon_type="svg", icon_name="star"))
    return out


def _record_events(entries, prev, record_type, week, date):
    if not entries:
        return []
    best = entries[0]
    player, value = best["player"], best["turn_value"]
    hit = best

    if record_type == "checkin":
        label = "check-in"
        verb_new, verb_open = "raises the check-in record to", "opens the check-in record at"
    else:
        label = "checkout"
        verb_new, verb_open = "raises the checkout record to", "opens the checkout record at"
    award_page = "awards.html"

    if prev is None:
        return [_event(
            f"{record_type}-record",
            f"{player} {verb_open} {value}",
            f"In the {hit['segment']} on {_pretty(hit['date'])}, "
            f"{player} hit a {value} {label} for "
            f"{hit['team']} in {hit['division']}.",
            week, date, division=hit["division"], hit=hit,
            link_href=award_page, icon_type="svg", icon_name="award")]

    old_player, old_value = prev
    if value > old_value or (value == old_value and player != old_player):
        return [_event(
            f"{record_type}-record",
            f"{player} {verb_new} {value}",
            f"In the {hit['segment']} on {_pretty(hit['date'])}, "
            f"{player} hit a {value} {label} for {hit['team']} "
            f"in {hit['division']}, overtaking {old_player}'s {old_value}.",
            week, date, division=hit["division"], hit=hit,
            link_href=award_page, icon_type="svg", icon_name="award")]
    return []


# ---------------------------------------------------------------- standings changes

def _accumulate_standings(schedule, week_num, accum, team_div):
    for _div_name, by_date in schedule.get("reg", {}).items():
        for _date, matches in by_date.items():
            for m in matches:
                if m.get("round_seq") != week_num or m.get("status") != "C":
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


def _standings_events(standings_pts, prev, canonical, team_div, week, date):
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
                link_href=f"standings-{_slug(div)}.html",
                icon_type="svg", icon_name="standings"))
        elif old_id != leader_id:
            old_name = canonical.get(old_id, f"Team {old_id}")
            out.append(_event(
                "standings-leader",
                f"{leader_name} takes first in {_short_div(div)}",
                f"After Week {week}, {leader_name} ({leader_pts} league pts) "
                f"moves past {old_name} to the top of {div}.",
                week, date, division=div,
                link_href=f"standings-{_slug(div)}.html",
                icon_type="svg", icon_name="standings"))
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
    m = re.search(r"\d+", div)
    return f"Div {m.group()}" if m else div


def _event(type, headline, body, week, date, division=None, hit=None,
           link_href="", icon_type="svg", icon_name="star"):
    return {
        "type":       type,
        "headline":   headline,
        "body":       body,
        "week":       week,
        "date":       date,
        "division":   division,
        "hit":        hit,
        "link_href":  link_href,
        "link_label": headline,
        "icon_type":  icon_type,
        "icon_name":  icon_name,
    }
