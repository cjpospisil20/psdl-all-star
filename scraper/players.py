"""Player-level data: team membership, form stats, division ranks.

Everything here is computed from the archived DartConnect recaps. DartConnect's own player-card
endpoint (3-dart average, first 9, checkout %) returns 403 without a login, so we recompute the
same figures from turn data instead. That was validated against DartConnect's per-leg averages
across 84 singles legs: mean delta 0.000, max 0.01 (rounding).

Recomputing has a second benefit beyond avoiding a login -- these numbers inherit the same
traceability as the all-star points, because they come from the same archived turns.
"""
import collections, re

import allstar


def clean_name(name):
    """Normalise DartConnect name artifacts.

    Two real cases from the league:
      * quoting artifacts from CSV round-trips, where a nickname ends up wrapped in a run of
        repeated double-quotes (Anaelechi "Lay" Owunwanne)
      * a genuine double space: 'Colin  Ratner' -- PRESERVED, it is part of the name as
        DartConnect holds it. HTML collapses it, so callers must escape it for display.
    """
    if not name:
        return name
    return re.sub(r'"{2,}', '"', name.strip())


def clean_team(name):
    """Team names as DartConnect stores them, minus surrounding whitespace.

    At least one team is stored as 'Prospect Darts and Chill ' with a trailing space.
    Both the recap feed and the standings feed must be normalised identically, or the
    same team appears as two.
    """
    return name.strip() if isinstance(name, str) else name


def standings_teams(standings_props):
    """Competing teams from the standings feed -- the authoritative list."""
    return {clean_team(c["team_name"]) for c in standings_props["competitors"]}


def canonical_teams(standings_props):
    """Stable DartConnect team id -> that team's CURRENT name.

    The id is the only durable team identity DartConnect gives us. The display name is not:
    see resolve_sides.
    """
    return {c["id"]: clean_team(c["team_name"]) for c in standings_props["competitors"]}


def resolve_sides(props, row, canonical):
    """{'home': name, 'away': name} for one match, keyed through stable team ids.

    Why this exists. An archived recap is immutable, so it carries each team's name as it stood
    on match night (`matchInfo.opponents[i].name`) -- and recaps carry no team id. `standings.json`
    and `matches.json` are refetched every run, so they carry today's name plus the stable id.
    Three teams were renamed mid-season in Fall 2026:

        395251  Eagle Fang Darts (Finn's)   -> Eagle Fang Darts
        395224  The Tickle Tickles (Pumps)  -> The Tickle Tickles
        395266  Paddy's 2 (George)          -> Dart Day Afternoon

    so the week-1 recaps disagree with standings permanently, and would disagree again after the
    next rename. Left alone that splits one team across two team pages with half a roster each.

    This is NOT an alias map and NOT fuzzy matching (CLAUDE.md data rule 5) -- no name is ever
    compared approximately and nothing is hand-coded. It reads DartConnect's own team identity
    out of the schedule row for the same match, then asks standings what that id is called now.

    Two independent signals, and a hard failure rather than a guess:
      1. exact-name match of a recap label against the row's left/right team_name
      2. elimination -- one label and one id left over can only pair with each other
      3. score orientation, for the case where BOTH teams were renamed
      4. otherwise raise: verify.py is a gate, and a wrong roster must never publish

    Deliberately does not assume row['left'] is the recap's home side. It usually is not --
    left was the recap's home team in only 6 of week 1's 15 matches.
    """
    labels = allstar.teams_of(props)
    row_side = {"left": (row.get("left") or {}), "right": (row.get("right") or {})}
    by_name  = {clean_team(s.get("team_name")): s.get("id")
                for s in row_side.values() if s.get("team_name")}

    out, unmatched = {}, []
    for side in ("home", "away"):
        label = clean_team(labels.get(side))
        if label in by_name:
            out[side] = by_name[label]
        else:
            unmatched.append(side)

    if unmatched:
        free = [i for i in by_name.values() if i not in out.values()]
        if len(unmatched) == 1 and len(free) == 1:
            out[unmatched[0]] = free[0]
        else:
            # Both labels are stale. Fall back to which side won, which the schedule states twice.
            left, right = row_side["left"], row_side["right"]
            home_score, away_score = row.get("home_score"), row.get("away_score")
            if left.get("score") == home_score and right.get("score") == away_score \
                    and home_score != away_score:
                pairing = {"home": left, "away": right}
            elif left.get("score") == away_score and right.get("score") == home_score \
                    and home_score != away_score:
                pairing = {"home": right, "away": left}
            else:
                raise ValueError(
                    f"cannot identify the teams in match {props['matchInfo']['id']}: recap says "
                    f"{sorted(filter(None, labels.values()))}, schedule says {sorted(by_name)}. "
                    f"Both teams appear to have been renamed and the match was drawn, so neither "
                    f"name nor score can tell the sides apart."
                )
            for side in unmatched:
                out[side] = pairing[side].get("id")

    unknown = [i for i in out.values() if i not in canonical]
    if unknown:
        raise ValueError(f"match {props['matchInfo']['id']} names team id(s) {unknown}, which are "
                         f"not standings competitors")
    return {side: canonical[tid] for side, tid in out.items()}


# DartConnect's marker for a side playing short-handed. Not a person: it has no team of its own
# and legitimately turns up for whichever side was a player down, so it must never be counted as
# a player on two teams, and must never reach a page.
SENTINEL_PLAYERS = {"-SHORT-"}


def _side_names(sided_recaps):
    """Yield (player, team) for every turn thrown, with teams already canonicalised."""
    for props, sides in sided_recaps:
        for g in allstar.games(props):
            for t in g["turns"]:
                for side in ("home", "away"):
                    name = clean_name(t[side].get("name"))
                    if name and name not in SENTINEL_PLAYERS and sides.get(side):
                        yield name, sides[side]


def team_map(sided_recaps):
    """player -> team, over (props, sides) pairs from events.load_season.

    A turn's side IS the player's team. Takes resolved sides rather than raw recaps so that a
    renamed team counts as one team and not two -- see resolve_sides.
    """
    seen = collections.defaultdict(collections.Counter)
    for name, team in _side_names(sided_recaps):
        seen[name][team] += 1
    return {name: counts.most_common(1)[0][0] for name, counts in seen.items()}


def ambiguous_teams(sided_recaps):
    """Players who appear under more than one team -- should always be empty.

    Teams are canonicalised first, so this no longer fires on a mid-season rename. What it still
    catches is the thing worth catching: one person genuinely credited to two different teams.
    """
    seen = collections.defaultdict(set)
    for name, team in _side_names(sided_recaps):
        seen[name].add(team)
    return {n: ts for n, ts in seen.items() if len(ts) > 1}


def _darts_thrown(g, side, turns):
    """Darts a side threw in a leg.

    DartConnect only records `darts_thrown` for the player who CHECKED OUT. The loser never
    finishes mid-turn, so their count is exactly 3 per turn taken.
    """
    recorded = g[side].get("darts_thrown")
    if recorded:
        return int(recorded)
    return 3 * sum(1 for t in turns
                   if t[side].get("turn_score") is not None or t[side].get("color"))


def form_stats(recaps):
    """Per-player form, computed from turn data. Season to date, SINGLES only.

    Singles only is deliberate, and matches the card DartConnect itself shows ("SINGLES 501
    SIDO"). In doubles and triples a leg's darts and points belong to the whole side, so there
    is no honest way to split them between partners -- crediting the side's figures to each
    player would inflate everyone's numbers.

    Validated against DartConnect's own per-leg averages: 84 singles legs, mean delta 0.000.
    """
    acc = collections.defaultdict(lambda: collections.defaultdict(float))
    opponents_faced = collections.defaultdict(set)
    matches_played  = collections.defaultdict(set)

    for props in recaps:
        match_id = props["matchInfo"]["id"]
        for g in allstar.games(props):
            turns = g["turns"]
            if not turns:
                continue
            singles = "Singles" in g["league_segment"]["label"]

            for side in ("home", "away"):
                other = "away" if side == "home" else "home"
                name  = clean_name(turns[0][side].get("name"))
                if not name:
                    continue

                darts = _darts_thrown(g, side, turns)
                won   = (g.get("winner_index") == (0 if side == "home" else 1))

                # Activity counts cover every format the player appeared in.
                a = acc[name]
                a["legs"] += 1
                a["all_darts"] += darts
                a["leg_wins"] += 1 if won else 0
                matches_played[name].add(match_id)
                opp_name = clean_name(turns[0][other].get("name"))
                if opp_name:
                    opponents_faced[name].add(opp_name)

                if not singles:
                    continue

                if g["score_type"] == "P":
                    scored = sum(t[side]["turn_score"] for t in turns
                                 if isinstance(t[side].get("turn_score"), int)
                                 and t[side].get("color") != "BUST")
                    a["points"] += scored
                    a["darts"]  += darts

                    # First 9 darts, expressed as a 3-dart average like every other figure.
                    first9 = sum(t[side]["turn_score"] for t in turns[:3]
                                 if isinstance(t[side].get("turn_score"), int)
                                 and t[side].get("color") != "BUST")
                    a["first9"] += first9
                    a["first9_legs"] += 1

                    # A checkout attempt is a turn taken with 170 or less remaining -- the
                    # highest score that can be checked out in three darts. This is our own
                    # definition, not DartConnect's, so the page labels it as ours.
                    start = 701 if "701" in g["game_name"] else 501
                    for i, t in enumerate(turns):
                        before = turns[i - 1][side]["current_score"] if i > 0 else start
                        took = t[side].get("turn_score") is not None or t[side].get("color")
                        if took and isinstance(before, int) and before <= 170:
                            a["co_attempts"] += 1
                    if won:
                        a["co_hits"] += 1

                    opp_scored = sum(t[other]["turn_score"] for t in turns
                                     if isinstance(t[other].get("turn_score"), int)
                                     and t[other].get("color") != "BUST")
                    a["opp_points"] += opp_scored
                    a["opp_darts"]  += _darts_thrown(g, other, turns)
                    a["legs_01"] += 1
                else:
                    # DartConnect reports marks-per-round per side. `ending_marks` is the
                    # POINTS total, not marks -- do not compute MPR from it.
                    mpr = g[side].get("mpr")
                    if mpr:
                        a["mpr_weighted"] += float(mpr) * darts
                        a["mpr_darts"]    += darts
                    a["legs_crk"] += 1

    out = {}
    for p, a in acc.items():
        out[p] = {
            "three_dart_avg": round(a["points"] / a["darts"] * 3, 2) if a["darts"] else None,
            "first_nine":     round(a["first9"] / a["first9_legs"] / 3, 2) if a["first9_legs"] else None,
            "mpr":            round(a["mpr_weighted"] / a["mpr_darts"], 2) if a["mpr_darts"] else None,
            "leg_win_pct":    round(a["leg_wins"] / a["legs"] * 100, 1) if a["legs"] else None,
            "checkout_pct":   round(a["co_hits"] / a["co_attempts"] * 100, 1) if a["co_attempts"] else None,
            "opp_three_dart": round(a["opp_points"] / a["opp_darts"] * 3, 2) if a["opp_darts"] else None,
            "singles_legs":   int(a["legs_01"] + a["legs_crk"]),
            "matches":        len(matches_played[p]),
            "legs":           int(a["legs"]),
            "darts":          int(a["all_darts"]),
            "opponents":      len(opponents_faced[p]),
        }
    return out


def division_table(hits, weeks_by_player=None):
    """Ranked all-star table per division. Ranking is ALWAYS within a division.

    Division 1 scores roughly 2.5x Division 5, so a league-wide ranking would be meaningless
    and actively misleading. See DESIGN-SPEC hard requirement 2.
    """
    stats = allstar.aggregate(hits)
    meta  = {}
    for h in hits:
        meta.setdefault(h["player"], {"division": h["division"], "team": h["team"]})

    by_div = collections.defaultdict(list)
    for player, counter in stats.items():
        info = meta[player]
        weeks = len(weeks_by_player.get(player, ())) if weeks_by_player else 1
        by_div[info["division"]].append({
            "player":   player,
            "team":     info["team"],
            "division": info["division"],
            "points":   counter["PTS"],
            "hits":     counter["AS"],
            "ppw":      round(counter["PTS"] / weeks, 1) if weeks else counter["PTS"],
            "weeks":    weeks,
            "counts":   {c: counter[c] for c in allstar.COLUMNS if counter[c]},
        })

    for division, rows in by_div.items():
        rows.sort(key=lambda r: (-r["points"], r["player"]))
        for i, row in enumerate(rows, 1):
            row["rank"] = i
            row["of"]   = len(rows)
    return dict(by_div)
