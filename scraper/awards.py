"""Season-end award data, derived from hits and the division table.

Every award is computed from the same hits that build the leaderboards, so every entry
carries its DartConnect recap link and never drifts from the numbers on screen.

The two "largest" awards rank across divisions. The league awards them league-wide, so
this is a deliberate exception to the "never compare across divisions" rule.
"""

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
        "blurb": "The highest score on the turn a side gets on the board, across the entire "
                 "league this season.",
        "kind":  "one",
    },
    {
        "key":   "largest-checkout",
        "title": "Largest Checkout",
        "blurb": "The highest checkout across the entire league this season.",
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
    """Best single hit of the given code per player, league-wide.

    Competition ranking: ties share a place (1, 1, 3). On equal values the earliest hit wins.
    """
    best = {}
    for h in hits:
        if h["code"] != code:
            continue
        prev = best.get(h["player"])
        if prev is None or h["turn_value"] > prev["turn_value"] \
                or (h["turn_value"] == prev["turn_value"]
                    and (h["date"] or "") < (prev["date"] or "")):
            best[h["player"]] = h
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


def compute_all(hits, table):
    """All award data in one call."""
    return {
        "points-leader":    points_leaders(table),
        "171-plus":         club_171(hits),
        "big-fish":         big_fish(hits),
        "largest-checkout": largest_checkouts(hits),
        "largest-checkin":  largest_checkins(hits),
    }
