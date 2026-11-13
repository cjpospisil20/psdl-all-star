"""Verification suite. Run before publishing: python3 scraper/verify.py

These assertions encode the rules that were hard to get right, and the two bugs that were
actually found and fixed during development. They exist to stop those bugs coming back.
"""
import collections, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import allstar, events, players


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")

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
#
# EVERY expected value below must be scoped to those 15 matches. "top" is the week-1 leader and
# his week-1 total: a spot-check that one player's chips still decompose to the points shown
# above them. It was once asserted against his SEASON total, which grew with every new week and
# so blocked the deploy from 2026-09-21 to 2026-10-02.
EXPECTED_WEEK1 = {"players": 104, "points": 20326, "busts": 437, "top": ("Tom Lettieri", 835)}

failures = []


def check(name, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {name}{'  -- ' + detail if detail and not condition else ''}")
    if not condition:
        failures.append(name)


def _busts_by_match(season):
    """Busts per match, so the week 1 baseline stays measurable as later weeks arrive."""
    out = {}
    for props in season["recaps"]:
        _hits, busts = allstar.score_match(props)
        out[props["matchInfo"]["id"]] = sum(busts.values())
    return out


# The season the week-1 baseline belongs to: Tuesday's Fall 2026 (ParkSDL). Pinned by id, so a new
# season becoming current can never make the baseline look missing.
BASELINE_SEASON = 25174


def check_baseline(season):
    hits = season["hits"]
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
        top_player, top_points = EXPECTED_WEEK1["top"]
        got = sum(h["points"] for h in w1 if h["player"] == top_player)
        check(f"{top_player}'s week 1 hits sum to {top_points}", got == top_points, f"got {got}")


def check_season(season):
    """Sections 1b-11, for one season. Every season in the archive gets all of them."""
    hits   = season["hits"]
    table  = players.division_table(hits, season["weeks_by_player"])
    rows   = [r for rs in table.values() for r in rs]

    print(f"\n1b. Season to date: {len(rows)} players, "
          f"{sum(r['points'] for r in rows):,} points across "
          f"{len({h['match_id'] for h in hits})} matches")

    print("\n2. Every player's hits sum to their displayed total")
    by_player = collections.defaultdict(int)
    for h in hits:
        by_player[h["player"]] += h["points"]
    mismatched = [r["player"] for r in rows if by_player[r["player"]] != r["points"]]
    check(f"all {len(rows)} decompositions sum", not mismatched, f"{len(mismatched)} mismatched")

    print("\n3. Team mapping is complete and unambiguous")
    ambiguous = players.ambiguous_teams(season["sided_recaps"])
    check("no player on two teams", not ambiguous,
          f"{len(ambiguous)} players, e.g. {sorted(ambiguous)[:3]}")
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

    print("\n6. Slug collisions")
    player_slugs = {}
    collisions = []
    for r in rows:
        s = _slug(r["player"])
        if s in player_slugs and player_slugs[s] != r["player"]:
            collisions.append(f"{r['player']!r} and {player_slugs[s]!r} -> {s}")
        player_slugs[s] = r["player"]
    check(f"all {len(player_slugs)} player slugs are unique", not collisions,
          f"{len(collisions)} collision(s): {collisions[:3]}")
    # Within one season, two names that are one players.identity() would be one person twice
    # (or two people the site cannot tell apart) -- never something to merge silently.
    same = collections.defaultdict(set)
    for r in rows:
        same[players.identity(r["player"])].add(r["player"])
    twice = sorted(str(sorted(n)) for n in same.values() if len(n) > 1)
    check("no two names in this season are one player", not twice, str(twice[:3]))
    team_slugs = {}
    team_collisions = []
    for r in rows:
        if not r["team"]:
            continue
        s = _slug(r["team"])
        if s in team_slugs and team_slugs[s] != r["team"]:
            team_collisions.append(f"{r['team']!r} and {team_slugs[s]!r} -> {s}")
        team_slugs[s] = r["team"]
    check(f"all {len(team_slugs)} team slugs are unique", not team_collisions,
          f"{len(team_collisions)} collision(s): {team_collisions[:3]}")

    print("\n7. Data completeness")
    check("no missing recap files", not season["missing"], str(season["missing"][:2]))
    # A forfeit is entered in DartConnect as an 11-0 match with no games. It scores nothing here:
    # forfeit all stars are credited by hand at season's end (Rulebook F.3). Listed so a
    # commissioner can see which matches need that credit.
    recap_of = {p["matchInfo"]["id"]: p for p in season["recaps"]}
    for m in season["matches"]:
        if not any(allstar.games(recap_of[m["id"]])):
            print(f"  NOTE  {m['date']} {m['division']}: {m['home']} v {m['away']} has no games "
                  f"on DartConnect (a forfeit?) -- no all stars can be derived from it")

    print("\n8. Awards hold their definitions")
    import awards as awards_mod
    award_data = awards_mod.compute_all(hits, table)

    club = award_data["171-plus"]
    expected_171 = [h for h in hits if h["display"] in ("171+", "180")]
    check("171+ club equals hits with display 171+/180",
          len(club) == len(expected_171),
          f"club has {len(club)}, hits have {len(expected_171)}")

    # The R9 Club was R8+ until 2026-11-11; the owner narrowed it, and the feed with it.
    r9 = award_data["r9"]
    expected_r9 = [h for h in hits if h["code"] == "R9"]
    check("R9 Club equals the R9 hits -- no R8",
          len(r9) == len(expected_r9) and all(h["code"] == "R9" for h in r9),
          f"club has {len(r9)} {sorted({h['code'] for h in r9})}, hits have {len(expected_r9)}")

    fish = award_data["big-fish"]
    bad_fish = [h for h in fish if h["code"] != "F90" or h["turn_value"] != 170]
    check("every Big Fish entry is an F90 of exactly 170", not bad_fish,
          f"{len(bad_fish)} wrong")

    for key in ("largest-checkout", "largest-checkin"):
        lb = award_data[key]
        if not lb:
            continue
        check(f"{key} has one row per player",
              len(lb) == len({h["player"] for h in lb}),
              "duplicate players")
        check(f"{key} is sorted descending",
              all(lb[i]["turn_value"] >= lb[i + 1]["turn_value"] for i in range(len(lb) - 1)))
        check(f"{key} rank 1 equals the maximum",
              lb[0]["rank"] == 1)
        for i in range(1, len(lb)):
            if lb[i]["turn_value"] == lb[i - 1]["turn_value"]:
                check(f"{key} ties share a rank at position {i}",
                      lb[i]["rank"] == lb[i - 1]["rank"])

    leaders = award_data["points-leader"]
    for division, div_rows in leaders.items():
        if div_rows:
            check(f"points leader in {division} is rank 1",
                  div_rows[0]["rank"] == 1,
                  f"rank is {div_rows[0]['rank']}")

    print("\n9. The ALL board's league table -- the one league-wide ranking")
    league = players.league_table(table)
    check(f"holds all {len(rows)} scoring players exactly once",
          sorted(r["player"] for r in league) == sorted(r["player"] for r in rows),
          f"{len(league)} rows for {len(rows)} players")
    check("runs highest points first",
          all(league[i]["points"] >= league[i + 1]["points"] for i in range(len(league) - 1)))
    check("is numbered 1..N", [r["league_rank"] for r in league] == list(range(1, len(league) + 1)))
    division_rank = {r["player"]: r["rank"] for r in rows}
    check("leaves every division rank as it was",
          all(r["rank"] == division_rank[r["player"]] for r in league)
          and not any("league_rank" in r for r in rows),
          "league_table renumbered or mutated the division table")


    print("\n10. The schedule -- fixtures still to play, from DartConnect's lineups feed")
    timezone = season["standings"]["leagueInfo"].get("timezone")
    check("the league plays on New York time, as the live window assumes",
          timezone == "America/New_York", repr(timezone))

    nights = season["fixtures"]
    known = set(events.divisions(season))
    competitors = set(players.canonical_teams(season["standings"]).values())
    dates = [n["date"] for n in nights]
    # app.js gilds tonight in place, which only works if tonight is the first night.
    check("match nights run in date order, one entry per night",
          dates == sorted(set(dates)), str(dates))
    wrong = []
    for night in nights:
        for f in night["fixtures"]:
            teams = [f["bye"]] if "bye" in f else [f["home"], f["away"]]
            if f["division"] not in known or not set(teams) <= competitors \
                    or len(set(teams)) != len(teams):
                wrong.append(f"{night['date']} {f}")
    check("every fixture is in a standings division, between standings teams",
          not wrong, str(wrong[:2]))

    print("\n11. Nights played (GP) and playoff eligibility")
    check("the rulebook's examples hold: 10 nights need 4, 14 need 6, 15 need 7",
          [players.playoff_minimum(n) for n in (10, 14, 15)] == [4, 6, 7])
    played = season["nights_by_player"]
    unplayed = sorted(p for p in season["teams"] if not played.get(p))
    check(f"all {len(season['teams'])} rostered players have played at least one night",
          not unplayed, str(unplayed[:3]))
    # What catches GP regressing to each leg's opener: in doubles and triples the partners
    # alternate, and 14 scorers hit an all star on a night they never opened a leg.
    missed = sorted(p for p, dates in season["hit_nights_by_player"].items()
                    if not dates <= played.get(p, set()))
    check("every night with an all star hit counts as a night played", not missed,
          str(missed[:3]))
    team_nights = collections.defaultdict(set)
    for m in season["matches"]:
        for team in m["teams"].values():
            team_nights[team].add(m["date"])
    stray = sorted(p for p, dates in played.items()
                   if not dates <= team_nights[season["teams"].get(p)])
    check("nobody is credited with a night their team did not play", not stray, str(stray[:3]))
    lengths = season["season_nights"]
    if lengths:
        # A typo'd division would silently drop its check marks.
        check("the season length names exactly the standings divisions",
              set(lengths) == set(events.divisions(season)), str(sorted(lengths)))
        check("every season length is a whole number of nights",
              all(isinstance(n, int) and n > 0 for n in lengths.values()), str(lengths))
    elif season["current"]:
        print("  NOTE  no season length in players.SEASON_NIGHTS for this season -- team pages "
              "show GP without playoff check marks")


# Every game format the rules engine knows how to score. A new one (a 301, say) would be scored as
# whatever it superficially resembles, so it must stop the build until someone looks.
KNOWN_FORMATS = {("P", "501 SIDO"), ("P", "501 DIDO"), ("P", "701 DIDO"), ("M", "Cricket")}


def check_both_nights(seasons):
    """Section 13: Awards are per night (owner, 2026-11-12), and the Feed is correct."""
    print("\n13. Awards and the Feed, per night")
    import awards as awards_mod, feed as feed_mod
    leagues = [s for s in seasons if s["current"]]
    check("both nights have a current season",
          sorted(s["night"] for s in leagues) == sorted(n for _l, n in events.fetch.LEAGUES),
          str([s["key"] for s in leagues]))
    all_hits = [h for s in leagues for h in s["hits"]]
    check("every current hit names its night",
          all(h.get("night") in ("Monday", "Tuesday") for h in all_hits))

    for season in leagues:
        data = awards_mod.compute_all(season["hits"], {})
        night = season["night"]
        for key, code in (("largest-checkout", "F90"), ("largest-checkin", "S90")):
            rows = data[key]
            who = [players.identity(h["player"]) for h in rows]
            check(f"{night} {key}: one row per player, highest first",
                  len(who) == len(set(who))
                  and all(rows[i]["turn_value"] >= rows[i + 1]["turn_value"]
                          for i in range(len(rows) - 1)),
                  f"{len(rows)} rows, {len(set(who))} players")
            best = max((h["turn_value"] for h in season["hits"] if h["code"] == code),
                       default=None)
            check(f"{night} {key}: rank 1 is that night's best",
                  not rows or (rows[0]["rank"] == 1 and rows[0]["turn_value"] == best),
                  f"{rows[0]['turn_value'] if rows else None} v {best}")
        expected = [h for h in season["hits"] if h["display"] in ("171+", "180")]
        check(f"{night} 171+ Club equals that night's hits",
              len(data["171-plus"]) == len(expected),
              f"{len(data['171-plus'])} v {len(expected)}")
        check(f"{night} R9 Club equals that night's R9 hits, no R8",
              len(data["r9"]) == sum(1 for h in season["hits"] if h["code"] == "R9")
              and all(h["code"] == "R9" for h in data["r9"]))

    feed_events = feed_mod.generate_events(leagues)
    check(f"all {len(feed_events)} Feed cards name their night",
          feed_events and all(e["night"] in ("Monday", "Tuesday") for e in feed_events))
    cards = [e["hit"]["code"] for e in feed_events
             if e["hit"] and e["hit"]["code"] in ("R8", "R9")]
    check("the Feed posts every R9 of both nights and no R8",
          cards.count("R9") == sum(1 for h in all_hits if h["code"] == "R9")
          and "R8" not in cards,
          f"{cards.count('R9')} R9 and {cards.count('R8')} R8 cards")
    dates = [e["date"] for e in feed_events]
    check("the Feed runs newest night first", dates == sorted(dates, reverse=True))
    for season in leagues:
        night = season["night"]
        data = awards_mod.compute_all(season["hits"], {})
        night_events = [e for e in feed_events if e["night"] == night]
        for kind, key in (("checkin", "largest-checkin"), ("checkout", "largest-checkout")):
            latest = next((e for e in night_events if e["type"] == f"{kind}-record"), None)
            holder = data[key][0] if data[key] else None
            check(f"{night} Feed's latest {kind} record = Awards holder",
                  (latest is None and holder is None)
                  or (latest and holder and latest["hit"]["player"] == holder["player"]
                      and latest["hit"]["turn_value"] == holder["turn_value"]),
                  f"feed {latest and (latest['hit']['player'], latest['hit']['turn_value'])}, "
                  f"awards {holder and (holder['player'], holder['turn_value'])}")
        check(f"every {night} Feed card names {night}",
              all(e["night"] == night for e in night_events))
    no_repeat = True
    for season in leagues:
        night = season["night"]
        night_events = [e for e in feed_events if e["night"] == night]
        for kind in ("standings-leader", "allstar-leader"):
            by_div = collections.defaultdict(list)
            for e in night_events:
                if e["type"] == kind:
                    by_div[e["division"]].append(e["headline"])
            for div, headlines in by_div.items():
                for i in range(1, len(headlines)):
                    if headlines[i] == headlines[i - 1]:
                        check(f"no repeated {kind} card in {night} {div}", False, headlines[i])
                        no_repeat = False
    if no_repeat:
        check("no leader card repeats the one before it for the same division", True)


def check_feed_accuracy(seasons):
    """Section 14: the Feed's standings agree with DartConnect."""
    print("\n14. The Feed agrees with DartConnect")
    import feed as feed_mod
    for season in seasons:
        night = f"{season['label']} · {season['night']}"
        cumulative = feed_mod.standings_by_night(season)
        if not cumulative:
            continue
        _date, final_pts, final_played = cumulative[-1]
        dc = {c["id"]: c for c in season["standings"]["competitors"]}
        wrong_pts, wrong_mp = [], []
        for c in dc.values():
            tid = c["id"]
            div = c["division"]
            expect_pts = int(c["league_points"])
            expect_mp = int(c["matches"])
            got_pts = final_pts.get(div, {}).get(tid, 0)
            got_mp = final_played.get(tid, 0)
            if got_pts != expect_pts:
                wrong_pts.append(f"{players.clean_team(c['team_name'])}: "
                                 f"computed {got_pts}, DC {expect_pts}")
            if got_mp != expect_mp:
                wrong_mp.append(f"{players.clean_team(c['team_name'])}: "
                                f"computed {got_mp}, DC {expect_mp}")
        check(f"{night}: league points match DartConnect for all "
              f"{len(dc)} teams", not wrong_pts, str(wrong_pts[:3]))
        check(f"{night}: matches played match DartConnect for all "
              f"{len(dc)} teams", not wrong_mp, str(wrong_mp[:3]))


def check_archive(seasons):
    """Section 12: the seasons agree with each other and with the registry."""
    print("\n12. The season archive -- every season, both leagues")
    registered = {e["id"] for e in events.registry()}
    on_disk = {int(p.name) for p in events.fetch.SEASONS.iterdir()
               if p.is_dir() and p.name.isdigit()}
    check("every season directory on disk is in data/seasons.json",
          on_disk <= registered, str(sorted(on_disk - registered)))

    # DartConnect's API ignores the league in its URLs, so every file must say which it is.
    wrong = []
    for s in seasons:
        info = s["standings"].get("leagueInfo") or {}
        if info.get("id") != s["league"] or info.get("season_id") != s["id"]:
            wrong.append(f"{s['key']}: standings say {info.get('id')} {info.get('season_id')}")
        for props in s["recaps"]:
            if props["matchInfo"].get("league_id") != s["league"]:
                wrong.append(f"{s['key']}: recap {props['matchInfo']['id']} is "
                             f"{props['matchInfo'].get('league_id')}")
    check(f"all {len(seasons)} seasons' standings and recaps belong to their own league",
          not wrong, str(wrong[:3]))

    seen, twice = {}, []
    for s in seasons:
        for m in s["matches"]:
            if m["id"] in seen:
                twice.append(f"{m['id']} in {seen[m['id']]} and {s['key']}")
            seen[m["id"]] = s["key"]
    check(f"each of the {len(seen)} matches is in exactly one season", not twice, str(twice[:3]))

    # ROADMAP finding 7: a recap on disk that no schedule lists would silently drop out.
    orphans = []
    for s in seasons:
        listed = {m["dc_match_id"] for _d, _date, m in events.fetch.iter_matches(s["schedule"])}
        orphans += [f"{s['key']}: {p.stem}" for p in (s["dir"] / "recaps").glob("*.json")
                    if p.stem not in listed]
    check("every archived recap is on its season's schedule", not orphans, str(orphans[:3]))

    stray = []
    for s in seasons:
        divisions = set(events.divisions(s))
        stray += [f"{s['key']}: {d}" for d in sorted({h["division"] for h in s["hits"]})
                  if d not in divisions]
    check("every hit sits in one of its season's standings divisions", not stray, str(stray[:3]))

    formats = collections.Counter()
    for s in seasons:
        for props in s["recaps"]:
            for g in allstar.games(props):
                formats[(g["score_type"], g["game_name"])] += 1
    unknown = sorted(f for f in formats if f not in KNOWN_FORMATS)
    check(f"all {sum(formats.values()):,} games are in a format the rules engine scores",
          not unknown, str(unknown))

    keys = [s["key"] for s in seasons]
    check("every season has its own key", len(keys) == len(set(keys)), str(keys))

    # A player page spans every season, one per players.identity() (owner, 2026-11-12): names that
    # differ only in spacing, punctuation or capitals are one player. Two DIFFERENT identities that
    # slug alike (José / Jose) would overwrite each other's page.
    names = {h["player"] for s in seasons for h in s["hits"]}
    spellings = collections.defaultdict(set)
    for name in names:
        spellings[players.identity(name)].add(name)
    pages = collections.defaultdict(set)
    for who, spelt in spellings.items():
        pages[_slug(sorted(spelt)[0])].add(who)
    clashes = sorted(f"{sorted(w)} -> {page}" for page, w in pages.items() if len(w) > 1)
    check(f"all {len(spellings)} players across every season have a page of their own",
          not clashes, str(clashes[:3]))
    for who, spelt in sorted(spellings.items()):
        if len(spelt) > 1:
            print(f"  NOTE  one player, spelt {len(spelt)} ways on DartConnect: "
                  f"{' / '.join(repr(n) for n in sorted(spelt))}")

    # All Time comes from the hits themselves (data rule 3), never from adding up season rows --
    # but the two must agree.
    tables = {s["key"]: players.division_table(s["hits"], s["weeks_by_player"]) for s in seasons}
    career = players.career_table(seasons, tables)
    season_sum = collections.Counter()
    for t in tables.values():
        for rows in t.values():
            for r in rows:
                season_sum[players.identity(r["player"])] += r["points"]
    hit_sum = collections.Counter()
    for s in seasons:
        for h in s["hits"]:
            hit_sum[players.identity(h["player"])] += h["points"]
    off = [r["player"] for r in career
           if not r["points"] == season_sum[r["identity"]] == hit_sum[r["identity"]]]
    check(f"all {len(career)} All Time totals equal their hits, and their seasons' totals",
          not off and len(career) == len(spellings), f"{len(off)} wrong: {off[:3]}")
    check("All Time is numbered 1..N, highest points first",
          [r["league_rank"] for r in career] == list(range(1, len(career) + 1))
          and all(career[i]["points"] >= career[i + 1]["points"] for i in range(len(career) - 1)))

    # A player page's All Time singles averages (owner, 2026-11-12) add up the raw sums of the
    # seasons the page shows and divide once (players.combined_form) -- never an average of season
    # averages. So adding a player's per-season sums must equal one pass over all of those
    # seasons' legs together, however the seasons are split: this suite loads Monday's stages
    # separately, where the site merges them. A pooled pass knows a player by name, so this
    # covers everyone with one spelling; MPR may differ by a rounding step, as its sums are floats.
    sums = {s["key"]: players.form_sums(s["recaps"]) for s in seasons}
    by_key = {s["key"]: s for s in seasons}
    groups = collections.defaultdict(list)
    for r in career:
        if len(r["seasons"]) > 1 and len(spellings[r["identity"]]) == 1:
            groups[tuple(r["seasons"])].append(r["player"])
    wrong, compared = [], 0
    for keys, names in groups.items():
        pooled = players.form_stats([props for k in keys for props in by_key[k]["recaps"]])
        for name in names:
            compared += 1
            summed = players.combined_form(sums[k].get(name, {}) for k in keys)
            expect = pooled.get(name) or players.form_figures({})
            if any((a is None) != (b is None) or (a is not None and abs(a - b) > 0.011)
                   for a, b in ((summed[f], expect[f]) for f in expect)):
                wrong.append(name)
    check(f"all {compared} multi-season players' All Time averages add up their seasons' legs, "
          "never averaging the averages", compared and not wrong,
          f"{len(wrong)} wrong: {wrong[:3]}")

    for league, night in events.fetch.LEAGUES:
        current = [s["key"] for s in seasons if s["league"] == league and s["current"]]
        if any(s["league"] == league for s in seasons):
            check(f"the {night} league has exactly one current season", len(current) == 1,
                  str(current))

    # Informational: why PPW counts rounds, not dates.
    for s in seasons:
        dates = len({m["date"] for m in s["matches"]})
        rounds = len({m.get("round_seq") for _d, _date, m in events.fetch.iter_matches(s["schedule"])})
        print(f"  NOTE  {s['label']} · {s['night']}: {len(s['matches'])} matches over {dates} "
              f"dates and {rounds} rounds")


def main():
    print("\n0. Every season with archived recaps loads")
    seasons = []
    for entry in events.registry():
        if not events._has_recaps(entry["id"]):
            continue                      # listed by DartConnect, nothing played yet
        name = f"{entry['label']} · {entry['night']} (season {entry['id']})"
        try:
            seasons.append(events.load_season(entry["id"]))
            check(f"{name} loads", True)
        except Exception as exc:
            check(f"{name} loads", False, f"{type(exc).__name__}: {exc}")

    # New York's daylight-saving rule is hand-rolled (no zoneinfo on Windows), and the Schedule's
    # first-darts times hang on it. Pin both 2026 changeovers.
    import fixtures as fixtures_mod
    for day, offset in (("2026-03-07", "-05:00"), ("2026-03-08", "-04:00"),
                        ("2026-10-31", "-04:00"), ("2026-11-01", "-05:00"),
                        ("2026-11-17", "-05:00")):
        check(f"New York is UTC{offset} on {day}", fixtures_mod.eastern_offset(day) == offset,
              fixtures_mod.eastern_offset(day))

    baseline = [s for s in seasons if s["id"] == BASELINE_SEASON]
    if baseline:
        check_baseline(baseline[0])
    else:
        check(f"the baseline season {BASELINE_SEASON} is archived", False)

    for season in seasons:
        print(f"\n===== {season['label']} · {season['night']} (season {season['id']})"
              f"{' -- current' if season['current'] else ''} =====")
        check_season(season)

    check_both_nights(seasons)
    check_feed_accuracy(seasons)
    check_archive(seasons)

    print(f"\n{'ALL CHECKS PASSED' if not failures else str(len(failures)) + ' CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
