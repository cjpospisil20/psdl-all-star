"""Player-level data: team membership, form stats and records, division ranks.

Everything here is computed from the archived DartConnect recaps. DartConnect's own player-card
endpoint (3-dart average, first 9, checkout %) returns 403 without a login, so we recompute the
same figures from turn data instead -- over every leg a player threw in, singles, doubles and
triples, each turn credited to whoever threw it (turns_thrown). Two checks against DartConnect's
own numbers back that up: a team's players, added up, give the '01 and CRK averages DartConnect
shows on Standings (which count every leg too); and the cricket marks counted turn by turn match
DartConnect's per-turn `notable` flags and its per-leg `mpr`.

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


def identity(name):
    """Who a DartConnect name is, for joining one player's seasons and nights together.

    DartConnect keeps a separate player record per league, and eight players' Monday and Tuesday
    records (or two seasons of one) differ only in spacing, punctuation or capitals:
    'Johnny  Colonna' / 'Johnny Colonna', 'Jamell St Thomas' / 'Jamell  St. Thomas',
    'Angelo Oddo' / 'Angelo Oddo |||', 'Zach Desantis-Salavarria' / 'Zach DeSantis-Salavarria'.
    The owner decided (2026-11-12) that each is one player.

    This is the whole rule: keep only letters and digits, and ignore case. It is NOT an alias map
    and NOT fuzzy matching -- a name that differs in any letter (a nickname, a misspelling) stays
    a separate player, as CLAUDE.md data rule 5 requires. Display is untouched: every season still
    shows the name exactly as DartConnect has it there.
    """
    return re.sub(r"[\W_]+", "", name.casefold())


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


def _leg_names(g):
    """Yield (side, player) for every turn slot in one leg, -SHORT- left out."""
    for t in g["turns"]:
        for side in ("home", "away"):
            name = clean_name(t[side].get("name"))
            if name and name not in SENTINEL_PLAYERS:
                yield side, name


def _turn_names(props):
    """Yield (side, player) for every turn slot in a match, -SHORT- left out."""
    for g in allstar.games(props):
        yield from _leg_names(g)


def _side_names(sided_recaps):
    """Yield (player, team) for every turn thrown, with teams already canonicalised."""
    for props, sides in sided_recaps:
        for side, name in _turn_names(props):
            if sides.get(side):
                yield name, sides[side]


def throwers(props):
    """Everyone who played in a match: every name in its turn records.

    Every turn, not each leg's opening one. Partners alternate in doubles and triples, so a leg's
    first turn names only one of them. Counting from the opener alone left 45 players a night or
    more short by week 9 of Fall 2026, and 14 short of a night they had scored an all star on.
    """
    return {name for _side, name in _turn_names(props)}


def legs_played(props):
    """{player: legs} for one match: every leg each player threw at least one turn in.

    What PPL divides by (owner, 2026-11-13: points per leg, replacing points per week). Every
    format counts -- singles, doubles and triples, '01 and cricket -- because an all star can be
    hit in any of them. And every turn counts, not each leg's opening one, for the reason
    throwers() gives: a doubles partner who threw second played that leg too. Counting openers
    alone gave 226 of Fall 2026's 244 scorers the wrong count. form_sums counts a player's record
    from these same legs, so W-L and PPL can never disagree about how many legs someone played.

    A leg is counted by its place in the match, never by DartConnect's set and game numbers:
    those are not unique. Two archived matches number two different legs alike -- a 501 singles
    set with two "game 1"s (68eedeb5..., Fall 2025), and two cricket singles games both "set 6,
    game 1" (69b0b45c..., Spring 2026).
    """
    legs = collections.Counter()
    for g in allstar.games(props):
        legs.update({name for _side, name in _leg_names(g)})
    return legs


# Regular-season nights each team plays, per division, keyed by DartConnect season id. A league
# fact: matches.json lists only nights already played. Confirmed by the owner on 2026-11-11, and
# DartConnect's lineups feed agreed that day -- Division 1's seven teams play each other twice,
# 12 nights over 14 weeks with two byes each; every team in Divisions 2-5 plays 15.
# A season or division missing here gets GP but no playoff check mark: a guessed season length
# would mark the wrong players. It stays here in code, hand-entered, rather than in
# data/seasons.json: fetch.py rewrites that file from DartConnect on every run. Monday's lengths
# (season 25432, "PS Monday") are not known yet.
SEASON_NIGHTS = {
    25174: {"Division 1": 12, "Division 2": 15, "Division 3": 15,        # Fall 2026
            "Division 4": 15, "Division 5": 15},
}


def playoff_minimum(nights):
    """Nights a player must have played to be playoff eligible, in a season of `nights`.

    Rulebook Fall 2025 section H.2: the largest whole number below half the season -- 10 nights
    need 4, 14 need 6, 15 need 7. One game in a night counts as playing that night. The rulebook
    also counts two bye weeks as one week of eligibility; SEASON_NIGHTS holds the nights a team
    actually plays, so Division 1's 12 give 5 -- the rulebook's own answer for 14 weeks (6) less
    one for two byes.
    """
    return (nights - 1) // 2


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
    finishes mid-turn, so their count is exactly 3 per turn taken. turns_thrown splits the same
    count between the side's players, turn by turn.
    """
    recorded = g[side].get("darts_thrown")
    if recorded:
        return int(recorded)
    return 3 * sum(1 for t in turns if _taken(t[side]))


# ---------------------------------------------------------------- form: every leg, turn by turn

# The formats a leg can be, as (size, game), in the order a PSDL match plays them (Rulebook
# section D): singles 501, singles cricket, doubles 501, doubles cricket, then 701 triples. A
# player page's RECORD card lists them in this order. Monday plays no triples and nobody plays
# cricket triples yet; a format nobody has a leg in is simply left out.
FORMATS = [("singles", "01"), ("singles", "cricket"), ("doubles", "01"),
           ("doubles", "cricket"), ("triples", "01"), ("triples", "cricket")]
SIZES = ("singles", "doubles", "triples")


def leg_format(g):
    """(size, game) for one leg: ("doubles", "01") for a 501 Doubles leg.

    The size comes from the segment label ("501 Singles", "Cricket Doubles", "701 Triples"), the
    game from `score_type`, which is what the rules engine scores by. A label naming no size, or
    two, raises: a format nobody has seen must stop the build until someone looks.
    """
    label = g["league_segment"]["label"]
    sizes = [size for size in SIZES if size in label.lower()]
    if len(sizes) != 1:
        raise ValueError(f"cannot tell singles, doubles or triples from the segment {label!r}")
    return sizes[0], "01" if g["score_type"] == "P" else "cricket"


_DART = re.compile(r"([SDT])(\d+|B)(?:x(\d+))?")


def cricket_marks(turn_score):
    """{target: marks} for one cricket turn as DartConnect writes it: 'T20, S20', 'S19x2', 'SB'.

    A single is one mark, a double two, a triple three, and 'x2' is the same dart twice.
    DartConnect lists only the darts that landed on 15-20 or the bull. A token it has never used
    raises -- skipping it would quietly undercount somebody's marks.
    """
    marks = collections.Counter()
    for token in str(turn_score or "").split(","):
        token = token.strip()
        if not token:
            continue
        found = _DART.fullmatch(token)
        if not found:
            raise ValueError(f"unrecognised cricket dart {token!r} in {turn_score!r}")
        marks[found.group(2)] += ("SDT".index(found.group(1)) + 1) * int(found.group(3) or 1)
    return marks


def _taken(p):
    """Whether a side took this turn: a score, or a colour such as MISS, BUST or SKIP. The rows
    after a leg ends carry neither."""
    return p.get("turn_score") is not None or bool(p.get("color"))


def turns_thrown(g):
    """Every turn taken in one leg, in the order thrown, each credited to whoever threw it.

    In doubles and triples the partners take turns about, and every turn record names its
    thrower. So a side's darts, points and marks split exactly between its players: nothing is
    shared out and nothing counts twice, and a side's turns add up to the side's own figures
    (verify.py checks every leg). That is what lets the averages count every leg rather than
    singles only (owner, 2026-11-16) -- crediting each partner with the side's figures would have
    inflated everyone.

    Yields one dict per turn:
      side, name  the side and the thrower (clean_name). The -SHORT- marker keeps its own name:
                  DartConnect counts its SKIP turns as three darts in a team's averages.
      turn        which of the thrower's own turns in this leg it is, from 1
      darts       3, except the side's last turn. DartConnect records `darts_thrown` only for
                  the side that checked out, so that turn gets whatever the total leaves --
                  exactly as _darts_thrown counts the side.
      points      '01: the turn's score; 0 for a bust, or a miss before doubling in
      before      '01: what the side needed before this turn
      out         '01: the turn checked out
      marks       cricket: the marks that counted
      notable     cricket: DartConnect's own flag for the turn ("5M", "3B"), or None

    A cricket mark counts the way DartConnect counts it: always, unless the thrower's side has
    already closed that number and the other side has too, leaving nothing to score. The order of
    throwing matters for that, and the side `starting_opponent_index` names throws first in every
    round. This reproduces DartConnect's `notable` flag ("5M") on every flagged turn in the
    archive, and its `mpr` for every side of every leg but one, which it records as 0.00.
    """
    turns = g["turns"]
    first = "away" if g.get("starting_opponent_index") == 1 else "home"
    order = (first, "home" if first == "away" else "away")
    o1 = g["score_type"] == "P"
    start = 701 if "701" in g["game_name"] else 501
    taken = {side: sum(1 for t in turns if _taken(t[side])) for side in order}
    marked = {side: collections.Counter() for side in order}     # cricket marks per target
    seen, own = collections.Counter(), collections.Counter()
    for i, t in enumerate(turns):
        for side in order:
            p = t[side]
            if not _taken(p):
                continue
            other = "away" if side == "home" else "home"
            name = clean_name(p.get("name"))
            seen[side] += 1
            own[(side, name)] += 1
            darts = 3
            recorded = g[side].get("darts_thrown")
            if seen[side] == taken[side] and recorded:
                darts = int(recorded) - 3 * (taken[side] - 1)
            turn = {"side": side, "name": name, "turn": own[(side, name)], "darts": darts}
            if o1:
                score = p.get("turn_score")
                turn["points"] = score if isinstance(score, int) and p.get("color") != "BUST" else 0
                turn["before"] = turns[i - 1][side]["current_score"] if i > 0 else start
                turn["out"] = p.get("current_score") == 0
            else:
                counted = 0
                for target, marks in cricket_marks(p.get("turn_score")).items():
                    left = max(0, 3 - marked[side][target])
                    counted += min(marks, left) if marked[other][target] >= 3 else marks
                    marked[side][target] += marks
                turn["marks"] = counted
                turn["notable"] = p.get("notable")
            yield turn


def form_sums(recaps):
    """The raw sums behind every average and every record: {player: {format: Counter}}.

    Every value is a plain total, so two seasons' sums add up (combine) and each figure is
    divided once, at the end (form_figures). Keep it that way: a figure that does not add up
    across seasons, such as a count of distinct opponents, does not belong here.

    Every leg counts, in every format, for every player who threw a turn in it -- not only its
    opener, since partners take turns about:
      legs, wins          the leg, and whether their side won it (DartConnect's winner_index).
                          The players are the ones legs_played counts, so the record and PPL
                          count the same legs.
    '01 legs, from the player's own turns (turns_thrown):
      points, darts       every turn they took; a bust, or a miss before doubling in, scores 0
      first9_points, first9_darts   their first three turns of the leg
      co_attempts         turns they took with 170 or less left -- our definition, not
                          DartConnect's, and the page says so
      co_hits             their checkouts
      opp_points, opp_darts   the other side's whole leg
    Cricket legs:
      marks, marks_darts  the marks that counted, over the darts they threw
    """
    acc = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for props in recaps:
        for g in allstar.games(props):
            if not g["turns"]:
                continue
            fmt = leg_format(g)
            o1 = fmt[1] == "01"
            side_total = {"home": collections.Counter(), "away": collections.Counter()}
            for t in turns_thrown(g):
                side_total[t["side"]].update(points=t.get("points", 0), darts=t["darts"])
                if not t["name"] or t["name"] in SENTINEL_PLAYERS:
                    continue
                a = acc[t["name"]][fmt]
                if o1:
                    a["points"] += t["points"]
                    a["darts"] += t["darts"]
                    if t["turn"] <= 3:
                        a["first9_points"] += t["points"]
                        a["first9_darts"] += t["darts"]
                    if isinstance(t["before"], int) and t["before"] <= 170:
                        a["co_attempts"] += 1
                    if t["out"]:
                        a["co_hits"] += 1
                else:
                    a["marks"] += t["marks"]
                    a["marks_darts"] += t["darts"]

            for side, name in dict.fromkeys(_leg_names(g)):
                a = acc[name][fmt]
                a["legs"] += 1
                a["wins"] += int(g.get("winner_index") == (0 if side == "home" else 1))
                if o1:
                    other = side_total["away" if side == "home" else "home"]
                    a["opp_points"] += other["points"]
                    a["opp_darts"] += other["darts"]
    return {name: dict(by_format) for name, by_format in acc.items()}


def form_figures(by_format, formats=None):
    """One player's figures from their form_sums -- one season's, or several seasons' added up by
    combine(). `formats` keeps only those formats; None is every leg. Each figure is divided here,
    once, from the sums."""
    a = collections.Counter()
    for fmt, sums in (by_format or {}).items():
        if formats is None or fmt in formats:
            a.update(sums)
    return {
        "three_dart_avg": round(a["points"] / a["darts"] * 3, 2) if a["darts"] else None,
        "first_nine":     (round(a["first9_points"] / a["first9_darts"] * 3, 2)
                           if a["first9_darts"] else None),
        "mpr":            round(a["marks"] / a["marks_darts"] * 3, 2) if a["marks_darts"] else None,
        "leg_win_pct":    round(a["wins"] / a["legs"] * 100, 1) if a["legs"] else None,
        "checkout_pct":   round(a["co_hits"] / a["co_attempts"] * 100, 1) if a["co_attempts"] else None,
        "opp_three_dart": round(a["opp_points"] / a["opp_darts"] * 3, 2) if a["opp_darts"] else None,
        "legs":           int(a["legs"]),
    }


def record(by_format):
    """[(format, won, lost)] in match order, for every format the player has a leg in. Every leg
    is a point -- the two legs of a Division 1 or 2 singles 501 set are two (Rulebook section D)
    -- so the record adds up to LEG WINS."""
    out = []
    for fmt in FORMATS:
        sums = (by_format or {}).get(fmt)
        if sums and sums["legs"]:
            out.append((fmt, int(sums["wins"]), int(sums["legs"] - sums["wins"])))
    return out


def combine(parts):
    """Several seasons' form_sums for one player, added up format by format: a player page's All
    Time. form_figures then divides once, exactly as if form_sums had read every one of those
    seasons' legs in one pass, which verify.py checks. Season averages are never averaged: a
    season of 300 darts must not weigh as much as a season of 3,000."""
    total = collections.defaultdict(collections.Counter)
    for part in parts:
        for fmt, sums in (part or {}).items():
            total[fmt].update(sums)
    return dict(total)


def form_stats(recaps):
    """{player: form_figures} over every leg of these recaps -- what a team page shows beside each
    name."""
    return {name: form_figures(by_format) for name, by_format in form_sums(recaps).items()}


def division_table(hits, legs_by_player=None):
    """Ranked all-star table per division. Ranking is ALWAYS within a division.

    Division 1 scores far more than Division 5, so a league-wide ranking would be meaningless
    and actively misleading. See DESIGN-SPEC hard requirement 2. The one exception, approved by
    the owner, is the All-Stars ALL board -- see league_table(), which never touches these ranks.

    PPL is points per leg played, over the season's `legs_by_player` (events.load_season, from
    legs_played). Without them -- the Feed, which ranks by points alone -- every row's ppl is None,
    so no page can show a figure divided by anything else.
    """
    stats = allstar.aggregate(hits)
    meta  = {}
    for h in hits:
        meta.setdefault(h["player"], {"division": h["division"], "team": h["team"]})

    legs_by_player = legs_by_player or {}
    by_div = collections.defaultdict(list)
    for player, counter in stats.items():
        info = meta[player]
        legs = legs_by_player.get(player, 0)
        by_div[info["division"]].append({
            "player":   player,
            "team":     info["team"],
            "division": info["division"],
            "points":   counter["PTS"],
            "hits":     counter["AS"],
            "ppl":      round(counter["PTS"] / legs, 1) if legs else None,
            "legs":     legs,
            "counts":   {c: counter[c] for c in allstar.COLUMNS if counter[c]},
        })

    for division, rows in by_div.items():
        rows.sort(key=lambda r: (-r["points"], r["player"]))
        for i, row in enumerate(rows, 1):
            row["rank"] = i
            row["of"]   = len(rows)
    return dict(by_div)


def league_table(table):
    """Every division's rows on one list, for the All-Stars ALL board -- the one league-wide view.

    An exception to "never rank across divisions" that the owner asked for (2026-11-11). The page
    that shows it carries no leader card and no gold top three, names each player's division, and
    says a league rank reflects the division. Rows are COPIES with an added `league_rank`: their
    division `rank` is what every other page shows, so it must not change. Same tie order as
    division_table.
    """
    rows = sorted((r for rows in table.values() for r in rows),
                  key=lambda r: (-r["points"], r["player"]))
    return [{**row, "league_rank": i} for i, row in enumerate(rows, 1)]


def career_table(seasons):
    """All Time: one row per player across every season of both nights, highest points first.

    `seasons` in display order (events.load_all). The owner asked for it (2026-11-12) as the first
    option of the All-Stars season picker; like the ALL board it ranks across divisions, so the
    page crowns nobody and names each player's division.

    Totals come from allstar.aggregate() over every hit -- never by adding up the season rows -- so
    a career total cannot drift from the hits behind it (CLAUDE.md data rule 3). A player is an
    identity(): Monday and Tuesday points add up when the two names differ only in spacing,
    punctuation or capitals, and a name that differs in any letter is another player (data rule 5).
    The name shown is the one from the first season, in display order, the player threw a dart in
    -- the current Tuesday season when they are in it -- and so are the division and team. That is
    the season their page opens on.

    PPL divides by every leg the player has thrown, in every season of both nights, hit or not --
    the seasons their page covers, whose All Time averages and record count those same legs
    (owner, 2026-11-16). `seasons` lists them all.
    """
    stats = allstar.aggregate([{**h, "player": identity(h["player"])}
                               for s in seasons for h in s["hits"]])
    first, legs, played = {}, collections.Counter(), collections.defaultdict(list)
    for s in seasons:
        for player, n in s["legs_by_player"].items():
            who = identity(player)
            team = s["teams"].get(player)
            first.setdefault(who, (s, player, team, s["division_of"].get(team)))
            if s["key"] not in played[who]:
                played[who].append(s["key"])
            legs[who] += n

    out = []
    for who, counter in stats.items():
        s, player, team, division = first[who]
        out.append({
            "player":   player,
            "identity": who,
            "team":     team,
            "division": division,
            "night":    s["night"],
            "points":   counter["PTS"],
            "hits":     counter["AS"],
            "ppl":      round(counter["PTS"] / legs[who], 1) if legs[who] else None,
            "legs":     legs[who],
            "seasons":  played[who],
            "counts":   {c: counter[c] for c in allstar.COLUMNS if counter[c]},
        })
    out.sort(key=lambda r: (-r["points"], r["player"]))
    for i, row in enumerate(out, 1):
        row["league_rank"] = i
    return out
