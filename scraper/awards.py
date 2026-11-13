"""Season-end award data, derived from hits and the division table.

Every award is computed from the same hits that build the leaderboards, so every entry
carries its DartConnect recap link and never drifts from the numbers on screen.

The two "largest" awards rank across divisions. The league awards them per night but
league-wide within a night, so this is a deliberate exception to the "never compare across
divisions" rule.

Awards are per night (owner, 2026-11-12): the site builds a separate Awards page for each
night, behind the LEAGUE picker. build.py passes one night's hits at a time.
"""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import players

# In the order the Awards page shows them -- the owner's order (2026-11-11).
AWARDS = [
    {
        "key":   "points-leader",
        "title": "All Star Points Leader",
        "blurb": "The top scorer in each division at season’s end.",
        "kind":  "division",
    },
    {
        "key":   "largest-checkin",
        "title": "Largest Check-In",
        "blurb": "The highest score on the turn a side gets on the board, across every "
                 "division this season.",
        "kind":  "one",
    },
    {
        "key":   "largest-checkout",
        "title": "Largest Checkout",
        "blurb": "The highest checkout across every division this season.",
        "kind":  "one",
    },
    {
        "key":   "big-fish",
        "title": "The Big Fish",
        "blurb": "Check out a perfect 170 and you’re in the club.",
        "kind":  "many",
    },
    {
        "key":   "171-plus",
        "title": "171+ Club",
        "blurb": "Every player who threw 171 or higher in a single turn.",
        "kind":  "many",
    },
    {
        # Was R8+ until the owner narrowed it to perfect rounds (2026-11-11).
        "key":   "r9",
        "title": "R9 Club",
        "blurb": "Throw a perfect 9 marks in a single turn of Cricket and you’re in the club.",
        "kind":  "many",
    },
    {
        "key":   "c5-plus",
        "title": "C5+",
        "blurb": "Five or more bullseye marks in a single turn of Cricket.",
        "kind":  "many",
    },
]


def points_leaders(table, n=5):
    """Top n players from each division table."""
    out = {}
    for division, rows in table.items():
        out[division] = rows[:n]
    return out


def club_171(hits):
    """Every turn of 171+. A 180 counts."""
    return sorted(
        [h for h in hits if h["code"] == "95+" and h["turn_value"] >= 171],
        key=lambda h: (-h["turn_value"], h["date"] or ""),
    )


def big_fish(hits):
    """Every 170 checkout."""
    return sorted(
        [h for h in hits if h["code"] == "F90" and h["turn_value"] == 170],
        key=lambda h: (h["date"] or "", h["player"]),
    )


def _best_per_player(hits, code):
    """Best single hit of the given code per player, across every division.

    Competition ranking: ties share a place (1, 1, 3). On equal values the earliest hit wins.
    A player is a players.identity(), so someone whose Monday and Tuesday names differ only in
    spacing, punctuation or capitals holds one row, not two.
    """
    best = {}
    for h in hits:
        if h["code"] != code:
            continue
        who = players.identity(h["player"])
        prev = best.get(who)
        if prev is None or h["turn_value"] > prev["turn_value"] \
                or (h["turn_value"] == prev["turn_value"]
                    and (h["date"] or "") < (prev["date"] or "")):
            best[who] = h
    rows = sorted(best.values(), key=lambda h: (-h["turn_value"], h["date"] or ""))
    ranked = []
    for i, row in enumerate(rows):
        if i == 0 or row["turn_value"] != rows[i - 1]["turn_value"]:
            rank = i + 1
        ranked.append({**row, "rank": rank})
    return ranked


def largest_checkouts(hits):
    return _best_per_player(hits, "F90")


def largest_checkins(hits):
    return _best_per_player(hits, "S90")


def club_r9(hits):
    """Every perfect nine-mark round in Cricket. An R8 does not count."""
    return sorted(
        [h for h in hits if h["code"] == "R9"],
        key=lambda h: (h["date"] or "", h["player"]),
    )


def club_c5(hits):
    """Every round of 5+ bullseye marks in Cricket."""
    return sorted(
        [h for h in hits if h["code"] in ("C5", "C6")],
        key=lambda h: (-h["turn_value"], h["date"] or ""),
    )


def compute_all(hits, table):
    """All award data in one call."""
    return {
        "points-leader":    points_leaders(table),
        "171-plus":         club_171(hits),
        "big-fish":         big_fish(hits),
        "largest-checkout": largest_checkouts(hits),
        "largest-checkin":  largest_checkins(hits),
        "r9":               club_r9(hits),
        "c5-plus":          club_c5(hits),
    }
