"""Fetch PSDL season data from DartConnect.

Two public, unauthenticated endpoints supply everything:
  1. POST tv.dartconnect.com/api/league/{league}/matches/{season}  -> schedule + match ids
  2. GET  recap.dartconnect.com/games/{dc_match_id}                -> full turn-by-turn detail

Recap pages are a Laravel/Inertia app: the complete match payload is embedded as JSON in the
root element's data-page attribute, so there is no HTML parsing and no DOM selectors to break.

Payloads are archived to data/recaps/ on first fetch and never re-fetched. DartConnect owes us
nothing and could change or withdraw access at any time; once a match is archived, it is ours.
"""
import json, os, re, html, time, urllib.request, pathlib

LEAGUE    = "ParkSDL"
SEASON    = 25174                  # Fall 2026
UA        = "PSDL-AllStar/0.1 (Park Slope Dart League; league stats automation)"
ROOT      = pathlib.Path(__file__).resolve().parent.parent
DATA      = ROOT / "data"
RECAPS    = DATA / "recaps"
DELAY_SEC = 1.5                    # be a polite guest; ~180 requests per season total


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


def fetch_schedule(refresh=True):
    """Season schedule grouped division -> date -> matches. Each match carries dc_match_id."""
    path = DATA / "matches.json"
    if refresh or not path.exists():
        body = _request(f"https://tv.dartconnect.com/api/league/{LEAGUE}/matches/{SEASON}", b"{}")
        path.write_text(body, encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def iter_matches(schedule):
    for division, by_date in schedule.get("reg", {}).items():
        for date, matches in by_date.items():
            for m in matches:
                if m.get("dc_match_id"):
                    yield division, date, m


def fetch_recap(dc_match_id):
    """Return the recap props dict, fetching and archiving it if not already on disk."""
    path = RECAPS / f"{dc_match_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    page = _request(f"https://recap.dartconnect.com/games/{dc_match_id}")
    props = _inertia_props(page, f"recap {dc_match_id}")
    path.write_text(json.dumps(props), encoding="utf-8")
    time.sleep(DELAY_SEC)
    return props


def fetch_standings(refresh=True):
    """Standings page props -- the authoritative source for competing teams."""
    path = DATA / "standings.json"
    if refresh or not path.exists():
        page = _request(f"https://tv.dartconnect.com/league/{LEAGUE}/{SEASON}/standings")
        props = _inertia_props(page, f"standings for season {SEASON}")
        path.write_text(json.dumps(props), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def teams(standings):
    """Competing teams only -- 31 for Fall 2026.

    Two wrong sources to avoid:
      * schedule['teams'] is the filter DROPDOWN (35 entries) and includes non-competing
        entries such as "The H is O (Commish)" and "Farm.One".
      * Deriving from played matches undercounts, because a division with an odd number of
        teams gives someone a bye each week (Division 1 has 7 teams -> 30, not 31).
    The standings competitors list is the only authoritative source.
    """
    return {c["id"]: (c["team_name"], c["division"]) for c in standings["competitors"]}


if __name__ == "__main__":
    RECAPS.mkdir(parents=True, exist_ok=True)
    sched = fetch_schedule()
    all_matches = list(iter_matches(sched))
    print(f"season {SEASON}: {len(all_matches)} matches with results; "
          f"{len(teams(fetch_standings()))} competing teams")
    new = 0
    for division, date, m in all_matches:
        if not (RECAPS / f"{m['dc_match_id']}.json").exists():
            fetch_recap(m["dc_match_id"]); new += 1
            print(f"  fetched {division} {date} {m['left']['team_name']} v {m['right']['team_name']}")
    print(f"done — {new} newly fetched, {len(all_matches)} archived total")
