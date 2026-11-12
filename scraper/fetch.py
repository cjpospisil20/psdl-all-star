"""Fetch PSDL data from DartConnect: both leagues, every season DartConnect still lists.

PSDL plays two nights, and DartConnect runs each as its own league (LEAGUES below). Public,
unauthenticated endpoints supply everything:
  0. GET  tv.dartconnect.com/league/{league}                        -> the league's seasons
  1. POST tv.dartconnect.com/api/league/{league}/matches/{season}   -> played matches + match ids
  2. GET  recap.dartconnect.com/games/{dc_match_id}                 -> full turn-by-turn detail
  3. GET  tv.dartconnect.com/league/{league}/{season}/standings     -> the competing teams
  4. POST tv.dartconnect.com/api/league/{league}/lineups/{season}   -> fixtures still to be played

(1) only ever lists matches that have started, so the Schedule tab's future fixtures come from (4).

Recap pages are a Laravel/Inertia app: the complete match payload is embedded as JSON in the
page, so there is no HTML parsing and no DOM selectors to break (see _inertia_props).

The archive is per season: data/seasons/<season id>/{recaps/, matches.json, standings.json,
fixtures.json}, with data/seasons.json listing every season and its league. Recaps are archived on
first fetch and never re-fetched. DartConnect owes us nothing and could change or withdraw access
at any time; once a match is archived, it is ours.

DartConnect's API IGNORES THE LEAGUE in its URLs: /api/league/ParkSDL/matches/25432 returns the
Monday league's season 25432 just the same. So a season id is only ever requested under the league
whose own page listed it, and what comes back is checked against that league before it is written
(_check_standings, _check_schedule, the league_id check in fetch_recap, fetch_fixtures).
"""
import json, re, html, time, urllib.request, pathlib

# (DartConnect league id, the night it plays). The first is the primary league: the one the home
# page, Matches and the default views have always shown.
LEAGUES   = [("ParkSDL", "Tuesday"), ("ParkSlopeDLM", "Monday")]
PRIMARY   = LEAGUES[0][0]
NIGHT_OF  = dict(LEAGUES)
UA        = "PSDL-AllStar/0.1 (Park Slope Dart League; league stats automation)"
ROOT      = pathlib.Path(__file__).resolve().parent.parent
DATA      = ROOT / "data"
SEASONS   = DATA / "seasons"
REGISTRY  = DATA / "seasons.json"
DELAY_SEC = 1.5                    # be a polite guest between recap requests


def _request(url, data=None):
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": UA,
        "Accept": "application/json",
        **({"Content-Type": "application/json"} if data else {}),
    })
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")


def _inertia_props(page, source):
    """The `props` dict out of an Inertia page, however this DartConnect app embeds it.

    Inertia has shipped the page payload two different ways, and they are not interchangeable:

      1. HTML-ESCAPED JSON in the root element's data-page ATTRIBUTE
         <div id="app" data-page="{&quot;component&quot;:&quot;...&quot;}">
      2. RAW JSON in the BODY of the Inertia script tag
         <script data-page="app" type="application/json">{"component":"..."}</script>

    `recap.dartconnect.com` moved from (1) to (2) on or before 2026-10-28 and it broke every new
    fetch in a nasty way: the old attribute regex still MATCHED, because the attribute is still
    there -- it just holds the literal string "app" now. So the failure surfaced as an opaque
    `JSONDecodeError: Expecting value: line 1 column 1` rather than anything about the format.
    `tv.dartconnect.com` (schedule, standings) was still on (1) on that date.

    So: never infer the shape from the host, and never trust the attribute's presence. Collect
    both candidates, and let a successful JSON parse decide which one is real. That way whichever
    host migrates next costs nothing.

    Only the attribute form is HTML-escaped. Unescaping a raw script body would be wrong -- it
    would turn a team genuinely called `Foo &amp; Bar` into `Foo & Bar` -- so each candidate
    carries whether it needs unescaping.
    """
    candidates = []
    body = re.search(r'<script[^>]*\bdata-page\b[^>]*>(.*?)</script>', page, re.S)
    if body:
        candidates.append(("script body", body.group(1), False))
    attr = re.search(r'data-page="([^"]+)"', page)
    if attr:
        candidates.append(("data-page attribute", attr.group(1), True))

    tried = []
    for where, text, unescape in candidates:
        try:
            payload = json.loads(html.unescape(text) if unescape else text)
        except json.JSONDecodeError as exc:
            tried.append(f"{where}: not JSON ({exc.msg}); starts {text[:40]!r}")
            continue
        if isinstance(payload, dict) and isinstance(payload.get("props"), dict):
            return payload["props"]
        tried.append(f"{where}: JSON but no props key (keys: {list(payload)[:5]})")

    raise RuntimeError(
        f"no Inertia payload found for {source} -- the page format may have changed again. "
        f"Tried: {'; '.join(tried) if tried else 'nothing, no data-page anywhere on the page'}"
    )


# ---------------------------------------------------------------- the season registry

def season_dir(season_id):
    """Where one season's archive lives: data/seasons/<id>/."""
    return SEASONS / str(season_id)


def read_registry():
    """Every season ever archived, as [{id, league, night, label, start_date, active}]."""
    if not REGISTRY.exists():
        return []
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def write_registry(entries):
    """Sorted and key-sorted, so a run that finds nothing new leaves the file byte-identical."""
    rows = sorted(entries, key=lambda e: e["id"])
    REGISTRY.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def discover(league):
    """The seasons DartConnect lists on one league's page, active ones first.

    The page's leagueInfo must name the league asked for -- the one URL here that DOES respect the
    league id -- and every season on it must belong to that league.
    """
    page = _request(f"https://tv.dartconnect.com/league/{league}")
    props = _inertia_props(page, f"the {league} league page")
    if (props.get("leagueInfo") or {}).get("id") != league:
        raise RuntimeError(f"the {league} league page describes "
                           f"{(props.get('leagueInfo') or {}).get('id')!r}")
    found = []
    for key, active in (("activeSeasons", True), ("archivedSeasons", False)):
        for s in props.get(key) or []:
            if s.get("league_id") not in (None, league):
                raise RuntimeError(f"{league} lists season {s.get('id')} of league "
                                   f"{s.get('league_id')!r}")
            found.append({"id": int(s["id"]), "league": league, "night": NIGHT_OF[league],
                          "label": " ".join(str(s["season"]).split()),
                          "start_date": s.get("start_date"), "active": active})
    return found


def refresh_registry():
    """Merge what DartConnect lists today into data/seasons.json. Returns (before, after, errors).

    Merged, never replaced: a season DartConnect stops listing keeps its entry (marked inactive),
    because its archive is ours to keep. If a league's page cannot be read, that league's entries
    stay exactly as they were and the error is reported -- the run carries on with what it knows.
    """
    before = {e["id"]: e for e in read_registry()}
    after = dict(before)
    errors = []
    for league, _night in LEAGUES:
        try:
            found = discover(league)
        except Exception as exc:
            errors.append(f"{league}: {exc}")
            continue
        listed = {s["id"] for s in found}
        for sid, entry in before.items():
            if entry["league"] == league and sid not in listed:
                after[sid] = {**entry, "active": False}
        for s in found:
            after[s["id"]] = s
    write_registry(after.values())
    return before, sorted(after.values(), key=lambda e: e["id"]), errors


# ---------------------------------------------------------------- one season

def _check_standings(season, props):
    """Standings must be the season that was asked for, in the league that was asked for."""
    info = props.get("leagueInfo") or {}
    if info.get("id") != season["league"] or info.get("season_id") != season["id"]:
        raise RuntimeError(f"standings for {season['league']} season {season['id']} came back as "
                           f"{info.get('id')!r} season {info.get('season_id')!r}")


def _check_schedule(season, schedule, standings):
    """Every played match must sit in one of this season's standings divisions -- the schedule
    endpoint ignores the league in its URL, so this is what ties it to the league."""
    divisions = {c["division_id"] for c in standings.get("competitors", [])}
    stray = sorted({m.get("division_id") for _div, _date, m in iter_matches(schedule)}
                   - divisions)
    if stray:
        raise RuntimeError(f"the schedule for {season['league']} season {season['id']} has "
                           f"matches in division id(s) {stray}, which its standings do not list")


def fetch_standings(season, refresh=True):
    """Standings page props -- the authoritative source for competing teams."""
    path = season_dir(season["id"]) / "standings.json"
    if refresh or not path.exists():
        page = _request(f"https://tv.dartconnect.com/league/{season['league']}/{season['id']}"
                        f"/standings")
        props = _inertia_props(page, f"standings for season {season['id']}")
        _check_standings(season, props)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(props), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_schedule(season, standings, refresh=True):
    """Season schedule grouped division -> date -> matches. Each match carries dc_match_id."""
    path = season_dir(season["id"]) / "matches.json"
    if refresh or not path.exists():
        body = _request(f"https://tv.dartconnect.com/api/league/{season['league']}/matches/"
                        f"{season['id']}", b"{}")
        _check_schedule(season, json.loads(body), standings)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def iter_matches(schedule):
    for division, by_date in schedule.get("reg", {}).items():
        for date, matches in by_date.items():
            for m in matches:
                if m.get("dc_match_id"):
                    yield division, date, m


def recap_path(season_id, dc_match_id):
    return season_dir(season_id) / "recaps" / f"{dc_match_id}.json"


def fetch_recap(season, dc_match_id):
    """Return the recap props dict, fetching and archiving it if not already on disk.

    A recap names its own league (matchInfo.league_id); one from another league is refused rather
    than archived, because an archived recap can never be taken back.
    """
    path = recap_path(season["id"], dc_match_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    page = _request(f"https://recap.dartconnect.com/games/{dc_match_id}")
    props = _inertia_props(page, f"recap {dc_match_id}")
    league = (props.get("matchInfo") or {}).get("league_id")
    if league != season["league"]:
        raise RuntimeError(f"recap {dc_match_id} belongs to league {league!r}, "
                           f"not {season['league']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(props), encoding="utf-8")
    time.sleep(DELAY_SEC)
    return props


FIXTURE_FIELDS = ("id", "division", "sched_date", "sched_time", "round_seq", "is_bye",
                  "status", "dc_match_id")


def fetch_fixtures(season, standings):
    """Every fixture DartConnect has not yet marked complete, written to the season's
    fixtures.json.

    The matches endpoint above lists a match only once it has started on the board, so it never
    holds a future fixture. The lineups endpoint -- the one behind DartConnect's own Lineups page --
    lists every match that is not yet complete: the rest of the season, plus a few stale rows (old
    byes, an unplayed match, finished-but-unfinalised status 'A' matches) that schedule.py drops.

    Each row is trimmed to the schedule fields. The rosters, captains and DartConnect member ids it
    also carries are not needed for a schedule, and would churn the file every time a captain
    publishes a lineup. Sorted, so a rerun with nothing new leaves the file byte-identical.

    Like the matches endpoint, this one ignores the league in its URL, so every row must sit in one
    of the season's standings divisions before the file is replaced.
    """
    body = _request(f"https://tv.dartconnect.com/api/league/{season['league']}/lineups/"
                    f"{season['id']}", b"{}")
    rows = json.loads(body)["lineups"]

    def side(team):
        team = team or {}
        return {"id": team.get("id"), "team_name": team.get("team_name")}

    fixtures = [{**{k: r.get(k) for k in FIXTURE_FIELDS},
                 "left": side(r.get("left")), "right": side(r.get("right"))} for r in rows]
    fixtures.sort(key=lambda f: (f["sched_date"] or "", f["division"] or "", f["id"] or 0))
    divisions = {c["division"] for c in standings.get("competitors", [])}
    stray = sorted({f["division"] for f in fixtures} - divisions)
    if stray:
        raise RuntimeError(f"lineups for {season['league']} season {season['id']} name "
                           f"division(s) {stray}, which its standings do not list")
    path = season_dir(season["id"]) / "fixtures.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fixtures": fixtures}, indent=1) + "\n", encoding="utf-8")
    return fixtures


def teams(standings):
    """Competing teams only -- 31 for Tuesday's Fall 2026, 7 for Monday's.

    Two wrong sources to avoid:
      * schedule['teams'] is the filter DROPDOWN (35 entries on Tuesday) and includes
        non-competing entries such as "The H is O (Commish)" and "Farm.One".
      * Deriving from played matches undercounts, because a division with an odd number of
        teams gives someone a bye each week (Division 1 has 7 teams -> 30, not 31).
    The standings competitors list is the only authoritative source.
    """
    return {c["id"]: (c["team_name"], c["division"]) for c in standings["competitors"]}


def _match_label(division, date, m):
    return (f"{division} {date} {(m.get('left') or {}).get('team_name')} v "
            f"{(m.get('right') or {}).get('team_name')}")


if __name__ == "__main__":
    before, seasons, discovery_errors = refresh_registry()
    for message in discovery_errors:
        # Annotated on the Actions run. The registry keeps what it knew, so the run goes on.
        print(f"::warning::could not read the season list for {message}")
    # A season is refetched while DartConnect calls it active, and once more on the run it stops
    # being active, so its last night's results and final standings are kept.
    was_active = {sid for sid, entry in before.items() if entry.get("active")}

    new, errors, skipped, standings_of = 0, [], [], {}
    for season in seasons:
        name = f"{season['label']} · {season['night']} (season {season['id']})"
        refresh = season["active"] or season["id"] in was_active
        try:
            standings = fetch_standings(season, refresh)
            schedule = fetch_schedule(season, standings, refresh)
        except Exception as exc:
            errors.append(f"  {name}: {exc}")
            print(f"  FAILED {name}: {exc}")
            continue
        standings_of[season["id"]] = standings
        played = list(iter_matches(schedule))
        print(f"{name}: {len(played)} matches with results; {len(teams(standings))} competing teams")
        for division, date, m in played:
            mid = m["dc_match_id"]
            if recap_path(season["id"], mid).exists():
                continue
            status = m.get("status")
            if status != "C":
                skipped.append(f"  {_match_label(division, date, m)} (status={status!r})")
                continue
            try:
                fetch_recap(season, mid)
                new += 1
                print(f"  fetched {_match_label(division, date, m)}")
            except Exception as exc:
                errors.append(f"  {division} {date} {mid}: {exc}")
                print(f"  FAILED {division} {date} {mid}: {exc}")
    if skipped:
        print(f"\nskipped {len(skipped)} match(es) with non-complete status:")
        for line in skipped:
            print(line)
    if errors:
        print(f"\nFAILED to fetch {len(errors)}:")
        for line in errors:
            print(line)
    # Fixtures are refreshed last, and on their own terms: a fixtures problem must never cost us a
    # recap. On failure the previous fixtures.json stays in place (the Schedule tab goes stale, but
    # the page's script still hides nights that are over), and the ::warning:: line surfaces as an
    # annotation on the GitHub Actions run rather than passing silently. Only a season DartConnect
    # still calls active has fixtures to come.
    for season in seasons:
        if not season["active"] or season["id"] not in standings_of:
            continue
        try:
            upcoming = fetch_fixtures(season, standings_of[season["id"]])
            print(f"fixtures: {len(upcoming)} not-yet-complete rows for {season['label']} · "
                  f"{season['night']}")
        except Exception as exc:
            print(f"::warning::fixtures refresh failed for season {season['id']}, keeping the "
                  f"previous fixtures.json: {exc}")
    archived = len(list(SEASONS.glob("*/recaps/*.json")))
    print(f"\ndone — {new} newly fetched, {archived} archived total across {len(seasons)} seasons")
