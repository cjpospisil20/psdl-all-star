"""Print or export the All Star standings from archived recaps.

Usage:  python3 scraper/standings.py [--division "Division 1"] [--csv out.csv] [--top N]

This is the debugging view of exactly what the site renders -- both read the same hits.
"""
import argparse, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import allstar, events, players


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--division")
    ap.add_argument("--csv")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    season = events.load_season()
    for division, date, match_id in season["missing"]:
        print(f"  ! missing recap {match_id} ({division} {date}) -- run fetch.py", file=sys.stderr)

    table = players.division_table(season["hits"], season["weeks_by_player"])
    rows = [r for rows in table.values() for r in rows]
    if args.division:
        rows = [r for r in rows if r["division"] == args.division]
    rows.sort(key=lambda r: (-r["points"], r["player"]))

    hdr = (f"{'#':>3} {'PTS':>6} {'PPW':>7} {'AS':>3} {'DIV':<11} {'PLAYER':<24}"
           + "".join(f"{c:>6}" for c in allstar.COLUMNS))
    print(hdr)
    print("-" * len(hdr))
    for i, r in enumerate(rows[:args.top], 1):
        print(f"{i:>3} {r['points']:>6} {r['ppw']:>7.1f} {r['hits']:>3} {r['division']:<11} "
              f"{r['player'][:24]:<24}"
              + "".join(f"{(r['counts'].get(c) or ''):>6}" for c in allstar.COLUMNS))

    print(f"\n{len(rows)} players scoring | {sum(r['points'] for r in rows):,} points | "
          f"{sum(season['busts'].values())} busts excluded")

    if args.csv:
        import csv
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["rank", "player", "team", "division", "WP", "PPW", "AS", "PTS"] + allstar.COLUMNS)
            for i, r in enumerate(rows, 1):
                w.writerow([i, r["player"], r["team"], r["division"], r["weeks"], r["ppw"],
                            r["hits"], r["points"]] + [r["counts"].get(c, 0) for c in allstar.COLUMNS])
        print(f"wrote {args.csv}")


if __name__ == "__main__":
    main()
