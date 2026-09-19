"""PSDL All Star Points rules engine.

Implements Section F of the PSDL Rules & Regulations against DartConnect turn data.

Two rules drive everything, and both were validated against real match data:

  01 games  -- computed from raw `turn_score`, NOT from DartConnect's `notable` flag.
               DartConnect flags 01 turns at 100+ ("TON"); PSDL's threshold is 95+.
               Trusting their flag would silently drop every 95-99 all star in the league.

  Cricket   -- taken directly FROM `notable` ("5M", "3B"), which is DartConnect's count of
               marks that actually COUNTED, not marks thrown. This exactly implements PSDL's
               "marks only count if they are included in the scoring" rule.
               Verified both directions in Week 1 data:
                 - Gerry Hernandez threw T19,T16 (6 marks) -> flagged 5M, because the opponent
                   had already taken a mark on 19, so only 2 of his three 19s counted.
                 - CJ Pospisil threw T16,S15x2 (5 marks) -> NOT flagged, because his opponent
                   closed 16 earlier in the same round, leaving only 4 counting marks.

The engine emits INDIVIDUAL HITS, not totals. Every screen in the app needs the hits themselves
-- the player page lists each of a player's turns and links it back to the DartConnect recap that
produced it. Totals are derived from hits by `aggregate()`, never accumulated separately, so a
displayed total can never drift from the hits shown beneath it.
"""
import re, collections

# Cricket point values -- Rulebook Section F.2
PTS_ROUND = {5: 100, 6: 120, 7: 140, 8: 160, 9: 180}
PTS_CORK  = {3: 100, 4: 125, 5: 150, 6: 180}

O1_THRESHOLD     = 95   # scoring turn counts as an all star
START_FINISH_MIN = 90   # S90+ / F90+ thresholds

# Rare hits get the gold chip (DESIGN-SPEC). Everything else is grey.
RARE = {"R7", "R8", "R9", "C4", "C5", "C6", "171+", "180", "S90", "F90"}

COLUMNS = ["95+", "R5", "R6", "R7", "R8", "R9", "171+", "171+T",
           "C3", "C4", "C5", "C6", "S90", "F90", "180"]

RECAP_URL = "https://recap.dartconnect.com/games/{match_id}"


def games(props):
    """Yield every game in a match recap."""
    for _set, entries in props["segments"].items():
        for entry in entries:
            yield from (entry if isinstance(entry, list) else [entry])


def teams_of(props):
    """Map turn side -> team name. A turn's side IS its team; opponents[] is in home/away order.

    Team names are stripped of surrounding whitespace: DartConnect stores at least one as
    'Prospect Darts and Chill ' with a trailing space, which would otherwise collide with a
    following word and read as a double space. Note this is NOT the same as the genuine
    double space inside a name like 'Colin  Ratner', which is preserved everywhere.
    """
    opponents = props["matchInfo"].get("opponents") or []

    def name_at(i):
        value = (opponents[i] if len(opponents) > i else {}).get("name")
        return value.strip() if isinstance(value, str) else value

    return {"home": name_at(0), "away": name_at(1)}


def score_match(props, date=None, week=None):
    """Score one match. Returns (hits, busts_by_player)."""
    info     = props["matchInfo"]
    ctx = {
        "division": info["division_title"],
        "match_id": info["id"],
        "date":     date or info.get("server_match_start_date"),
        "week":     week,
        "teams":    teams_of(props),
        "recap":    RECAP_URL.format(match_id=info["id"]),
    }

    hits, busts = [], collections.Counter()
    for g in games(props):
        if g["score_type"] == "P":
            _score_01(g, ctx, hits, busts)
        else:
            _score_cricket(g, ctx, hits)
    return hits, busts


def _score_01(g, ctx, hits, busts):
    turns        = g["turns"]
    start_points = 701 if "701" in g["game_name"] else 501
    double_in    = "DIDO" in g["game_name"]   # applies to 501 Doubles and 701 Triples alike
    started      = set()                       # SIDES that have doubled in -- a side gets ON once
    game         = "701" if start_points == 701 else "501"

    for i, t in enumerate(turns):
        for side in ("home", "away"):
            p = t[side]
            name = p.get("name")
            if not name:
                continue
            s, colour = p.get("turn_score"), p.get("color")

            if colour == "BUST":               # busts are void for all star purposes (F.1)
                busts[name] += 1
                continue
            if not isinstance(s, int) or s <= 0:
                continue

            before   = turns[i - 1][side]["current_score"] if i > 0 else start_points
            finished = p.get("current_score") == 0

            # S90+ : 90+ on the turn the SIDE gets ON. Crediting per player would wrongly
            # credit a partner's first turn in doubles.
            if double_in and side not in started:
                started.add(side)
                if s >= START_FINISH_MIN:
                    hits.append(_hit(ctx, g, side, name, "S90", s, s, game,
                                     detail=f"{s} to get on"))
                continue

            # F90+ : 90+ checkout. The value is what was left to throw at, not the turn score.
            if finished:
                if before >= START_FINISH_MIN:
                    hits.append(_hit(ctx, g, side, name, "F90", before, before, game,
                                     detail=f"{before} checkout"))
                continue

            if s >= O1_THRESHOLD:
                # 171+ and 180 describe the SAME hit as its 95+ -- they never pay twice.
                # They only change how the hit is labelled on screen.
                display = "180" if s == 180 else ("171+" if s >= 171 else "95+")
                detail  = {"180": "Three triple twenties",
                           "171+": "Big scoring turn"}.get(display, "Scoring turn")
                hits.append(_hit(ctx, g, side, name, "95+", s, s, game,
                                 detail=detail, display=display))


def _score_cricket(g, ctx, hits):
    for t in g["turns"]:
        for side in ("home", "away"):
            p = t[side]
            name = p.get("name")
            if not name:
                continue
            m = re.fullmatch(r"(\d+)([MB])", str(p.get("notable") or ""))
            if not m:
                continue
            count, kind = int(m.group(1)), m.group(2)
            if kind == "B":                                   # corks
                c = min(max(count, 3), 6)
                hits.append(_hit(ctx, g, side, name, f"C{c}", PTS_CORK[c], c, "Cricket",
                                 detail=f"{c} bullseye marks"))
            else:                                             # rounds
                r = min(max(count, 5), 9)
                hits.append(_hit(ctx, g, side, name, f"R{r}", PTS_ROUND[r], r, "Cricket",
                                 detail=f"{r} marks in a turn"))


def _hit(ctx, g, side, name, code, points, turn_value, game, detail="", display=None):
    display = display or code
    return {
        "player":      name,
        "team":        ctx["teams"].get(side),
        "division":    ctx["division"],
        "code":        code,          # the scoring column (95+ covers 171+ and 180)
        "display":     display,       # what the chip says on screen
        "points":      points,
        "turn_value":  turn_value,    # the number the player brags about
        "game":        game,
        "segment":     g["league_segment"]["label"],
        "set_index":   g.get("set_index"),
        "game_number": g.get("set_game_number"),
        "detail":      detail,
        "date":        ctx["date"],
        "week":        ctx["week"],
        "match_id":    ctx["match_id"],
        "recap":       ctx["recap"],
        "rare":        display in RARE,
    }


def aggregate(hits):
    """Derive per-player totals from hits. The only source of a player's numbers."""
    stats = collections.defaultdict(collections.Counter)
    for h in hits:
        c = stats[h["player"]]
        c[h["code"]] += 1
        c["PTS"]     += h["points"]
        c["AS"]      += 1
        if h["code"] == "95+":
            if h["turn_value"] >= 171:
                c["171+"]  += 1
                c["171+T"] += h["turn_value"]
            if h["turn_value"] == 180:
                c["180"] += 1
    return stats
