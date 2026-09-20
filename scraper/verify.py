"""Verification suite. Run before publishing: python3 scraper/verify.py

These assertions encode the rules that were hard to get right, and the two bugs that were
actually found and fixed during development. They exist to stop those bugs coming back.
"""
import collections, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import allstar, events, players

# The validated baseline. These totals were hand-checked against the rulebook for the 15
# matches of week 1, so they are a permanent regression guard on the scoring rules.
#
# The baseline is scoped to those 15 match IDs rather than to the whole season. Checking
# season-wide totals would have meant this suite failing every time a new week was archived
# -- and since the CI deploy is gated on it, a correct new week would have blocked the site.
WEEK1_MATCHES = {
    "6aa9d2dca9fb98f7d1de1b4f", "6aa9d7aea9fb98f7d1de299e", "6aa9d811a9fb98f7d1de2b0c",
    "6aa9d839a9fb98f7d1de2bb4", "6aa9d8a7a9fb98f7d1de2d45", "6aa9d96ba9fb98f7d1de3043",
    "6aa9d9aea9fb98f7d1de3129", "6aa9d9cca9fb98f7d1de319c", "6aa9da0ba9fb98f7d1de32be",
    "6aa9da46a9fb98f7d1de338e", "6aa9db0ea9fb98f7d1de36a4", "6aa9db7da9fb98f7d1de3838",
    "6aa9dc1da9fb98f7d1de3a6c", "6aa9de73a9fb98f7d1de436b", "6aa9e1ada9fb98f7d1de506b",
}
EXPECTED_WEEK1 = {"players": 104, "points": 20326, "busts": 437}

failures = []


def check(name, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {name}{'  -- ' + detail if detail and not condition else ''}")
    if not condition:
        failures.append(name)


def _busts_by_match(season):
    """Busts per match, so the week 1 baseline stays measurable as later weeks arrive."""
    import json
    out = {}
    for m in season["matches"]:
        props = json.loads((events.fetch.RECAPS / f"{m['id']}.json").read_text(encoding="utf-8"))
        _hits, busts = allstar.score_match(props)
        out[m["id"]] = sum(busts.values())
    return out


def main():
    season = events.load_season()
    hits   = season["hits"]
    table  = players.division_table(hits, season["weeks_by_player"])
    rows   = [r for rs in table.values() for r in rs]

    print("\n1. The hand-checked week 1 baseline still reproduces")
    archived = {m["id"] for m in season["matches"]}
    if not WEEK1_MATCHES <= archived:
        check("week 1 matches present", False,
              f"{len(WEEK1_MATCHES - archived)} of the baseline matches are not archived")
    else:
        w1 = [h for h in hits if h["match_id"] in WEEK1_MATCHES]
        w1_players = {h["player"] for h in w1}
        w1_busts = sum(c for mid, c in _busts_by_match(season).items() if mid in WEEK1_MATCHES)
        check("104 scoring players", len(w1_players) == EXPECTED_WEEK1["players"],
              f"got {len(w1_players)}")
        check("20,326 points", sum(h["points"] for h in w1) == EXPECTED_WEEK1["points"],
              f"got {sum(h['points'] for h in w1):,}")
        check("437 busts excluded", w1_busts == EXPECTED_WEEK1["busts"], f"got {w1_busts}")

    print(f"\n1b. Season to date: {len(rows)} players, "
          f"{sum(r['points'] for r in rows):,} points across "
          f"{len({h['match_id'] for h in hits})} matches")

    print("\n2. Every player's hits sum to their displayed total")
    by_player = collections.defaultdict(int)
    for h in hits:
        by_player[h["player"]] += h["points"]
    mismatched = [r["player"] for r in rows if by_player[r["player"]] != r["points"]]
    check(f"all {len(rows)} decompositions sum", not mismatched, f"{len(mismatched)} mismatched")
    lettieri = by_player.get("Tom Lettieri")
    check("Tom Lettieri's hits sum to 835", lettieri == 835, f"got {lettieri}")

    print("\n3. Team mapping is complete and unambiguous")
    ambiguous = players.ambiguous_teams(season["recaps"])
    check("no player on two teams", not ambiguous, str(list(ambiguous)[:3]))
    teamless = [r["player"] for r in rows if not r["team"]]
    check("every scoring player has a team", not teamless,
          f"{len(teamless)} without: {teamless[:3]}")
    known = players.standings_teams(season["standings"])
    unknown = {r["team"] for r in rows} - known
    check("all team names appear in standings", not unknown, str(sorted(unknown)))

    print("\n4. Scoring rules hold")
    # A bust must never produce a hit; DartConnect labels them explicitly.
    busted = [h for h in hits if h.get("detail") == "BUST"]
    check("no hit scored from a bust", not busted)
    # S90 applies to the side that gets ON, never a doubles partner's first turn.
    s90 = [h for h in hits if h["display"] == "S90"]
    check("S90 only in double-in games", all("Doubles" in h["segment"] or "Triples" in h["segment"]
                                             for h in s90), f"{len(s90)} S90 hits")
    # 180s and 171+ are labels on a 95+ hit -- they must never add points of their own.
    for h in hits:
        if h["display"] in ("180", "171+"):
            check(f"{h['display']} by {h['player']} scores its face value",
                  h["points"] == h["turn_value"], f"{h['points']} vs {h['turn_value']}")
    # Cricket values must come from the rulebook table.
    bad = [h for h in hits if h["code"].startswith("R")
           and h["points"] != allstar.PTS_ROUND.get(int(h["code"][1:]))]
    check("cricket round values match the rulebook", not bad, f"{len(bad)} wrong")

    print("\n5. Traceability")
    check("every hit links to its recap", all(h["recap"].startswith("https://recap.dartconnect.com/")
                                              for h in hits))
    check("every hit names its game and segment", all(h["game"] and h["segment"] for h in hits))

    print("\n6. Data completeness")
    check("no missing recap files", not season["missing"], str(season["missing"][:2]))

    print(f"\n{'ALL CHECKS PASSED' if not failures else str(len(failures)) + ' CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
