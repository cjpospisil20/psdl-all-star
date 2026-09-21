# PSDL Website — Architecture & Implementation Roadmap

**Written:** 2026-09-20 · **Status:** Step 1 in progress (see the tracker in §11)

This is the plan for turning the PSDL All Star stats app into the full Park Slope Dart League
website. It is written to be executed **one step at a time** with Claude Code by a technically
capable non-developer. Read `CLAUDE.md` and `summary.md` first; this file is the plan, those are the
rules and the history.

> **Rule for every session:** do the next unchecked step in §11 and nothing else. Do not start a
> later step early. Update the tracker and `summary.md` when a step is done.

---

## 1. Decisions already made (do not re-litigate)

| Topic | Decision |
|---|---|
| Approach | **Extend** the existing app; do not rewrite. Keep the scraper, archive, rules engine, verify/check gates and static generator. |
| Repository | **Public, and it already exists: <https://github.com/cjpospisil20/psdl-all-star>** (created by CJ 2026-09-19; one commit; Pages on; first Actions run green; site live at <https://cjpospisil20.github.io/psdl-all-star/>). **Do not create a second repo.** The owner is happy for the raw DartConnect archive to be downloadable; CJ's email (in `summary.md` and the BRD) and the legacy stats CSV are already public in its history. Plan to move the repo into a shared GitHub organization before the custom-domain step (Pages settings are owner-only on a personal account). The DartConnect ToS review from the BRD is still an open checklist item — see §12. |
| Hosting | **GitHub Pages** for launch. Moving to Cloudflare Pages later only changes the last two workflow steps. |
| Domain | Bought at **Namecheap**. DNS records are added there (Step 15). |
| Database | **Supabase, Free plan.** Used only for human-entered data (§5). Never in the stats path. |
| Streaming | **One PSDL-owned YouTube channel**, with a **separate stream key for each pub**. Twitch remains a supported alternative in the data model. |
| Launch | **Beta / "unofficial"** label until commissioners reconcile the numbers. |
| LIVE indicator | **Gold** (no red), consistent with the three-colour palette. |
| Season schedule | The owner will supply it as a **CSV**. The team → host-bar list is **still needed**. |
| Admins | The owner and **CJ** for now. Commissioners come later and are **not tech-savvy** — see §10. |

**Rules from `CLAUDE.md` this plan deliberately amends** (approved by choosing this plan):
1. "Only `fetch.py` touches the network" → "only `fetch.py` and `sync_managed.py`". `verify.py` and `build.py` stay offline.
2. "Works with JS off" → every page still renders without JS (Live shows a build-time snapshot; Join shows a mailto fallback), but Live refresh and the join forms need JS.
3. "No dependencies" is **kept**: plain `fetch()` against Supabase's REST API (no client library) and a small custom Markdown-subset renderer (no packages).
4. "Three colours only" is kept: LIVE is gold.
5. "Out of scope: historical seasons / live updates" → storage becomes per-season now; **no backfill**. "Live" means video, not scores.

---

## 2. Executive summary

The repo is a well-built stats product: a pure-Python-stdlib pipeline pulls DartConnect data into an
immutable archive, applies the rules engine, passes a verification gate, builds ~165 static pages,
passes an output check, and deploys through GitHub Actions. It is the right foundation.

Recommended architecture: keep it, and add **one** managed service (Supabase) for what people type in —
join forms, venues, future fixtures, livestream assignments, announcements. Stream with YouTube Live
under one PSDL channel; an admin pastes a video ID into a Supabase row and the Live page embeds it.

Three findings that shaped the plan:
1. **DartConnect exposes no future schedule and no venues** (confirmed against the live endpoint on 2026-09-20: Week 1 only, all `status: "C"`). Fixtures and team → bar come from PSDL.
2. **The UI is a phone-only 430px column with a 5-tab bar** (`site/tokens.py`). It needs a responsive shell and new navigation before any new page.
3. **The archive layout has landmines**: in-progress matches can freeze, no per-season structure, and bumping `SEASON` breaks `verify.py`.

```
DartConnect ──► fetch.py ──► data/seasons/<id>/recaps  (immutable, committed FIRST)
                                   │
Supabase (venues, fixtures,        ▼
 streams, announcements) ─► sync_managed.py ─► data/managed/*.json (committed)
                                   │
                    verify.py (stats gate: HARD fail)  +  managed-data check (SOFT fail)
                                   ▼
                    build.py (offline) ─► check.py ─► GitHub Pages ─► PSDL domain
Browser, at runtime: live.js reads streams/announcements · join forms insert to Supabase
```

---

## 3. Codebase assessment (as found 2026-09-20)

### 3.1 Architecture

| Layer | Files | Role |
|---|---|---|
| Network | `scraper/fetch.py` | Only networked module. POSTs the schedule, GETs each recap, parses the Inertia JSON from `data-page`. Archives each recap once, 1.5 s apart. |
| Rules | `scraper/allstar.py` | Section F engine; emits individual hits. 01 computed from `turn_score` (95+); cricket read from `notable`. |
| Assembly | `scraper/events.py`, `players.py` | `load_season()`, team map from turns, form stats recomputed from turns, per-division ranking. |
| Gate 1 | `scraper/verify.py` | Data assertions (week-1 baseline, hits sum to totals, no player on two teams, busts void, traceability). |
| Presentation | `site/tokens.py`, `components.py`, `build.py`, `app.js` | Palette/CSS as code, shared fragments, page renderer, progressive-enhancement JS. |
| Gate 2 | `site/check.py` | Output audit: links, contrast maths, palette, fonts, headings, tap targets, names, spec invariants. |
| Automation | `.github/workflows/build.yml` | fetch → **commit archive** → verify → build → check → upload → deploy (deploy `needs: build`). |

### 3.2 Data scraped and stored

| File | Contents | Notes |
|---|---|---|
| `data/recaps/<id>.json` ×15 (~100 KB each) | Full match payload, every turn of every game, per-side ppr/mpr, `score_edits` | ≈ 19 MB per 180-match season |
| `data/matches.json` | Schedule division → date → matches (`sched_date`, `sched_time` "19:30", teams, scores, points, `status`, `is_bye`, `dc_match_id`) | **Week 1 only. No venue field. Overwritten every run.** |
| `data/standings.json` | Standings page props: 31 competitors, division averages, `leagueInfo` (season label, timezone, `streaming_url: null`) | Includes DartConnect's route table (harmless noise; scanned, no secrets) |

DartConnect also exposes an `api/league/{league}/matches/live` route (future hook for live scores; not needed now).

### 3.3 Preserve unchanged
`allstar.py` rules, `players.form_stats` (validated: 84 legs, mean delta 0.000), `clean_name` /
`clean_team` / `esc`, archive-before-verify ordering, the offline build, palette and fonts, and every
existing `check.py` assertion. **Extend the checks; never loosen them.**

### 3.4 Findings

| # | Sev. | Finding | Action |
|---|---|---|---|
| 1 | Launch | Not a git repo, not deployed; no Python/git on the owner's Windows PC. | Step 1 |
| 2 | Launch | `events._pretty_date` used `strftime("%-d")` → `ValueError` on Windows. Bare `read_text()`/`write_text()` used the Windows code page. | **Fixed 2026-09-20** (Step 1) |
| 3 | Launch | `fetch.py` doesn't check `status == "C"`; a match archived mid-play would be frozen forever. | Step 2 |
| 4 | Before next season | Single-season assumptions (`SEASON` constant, flat `data/recaps`, week-1 baseline needs those IDs → bumping `SEASON` fails verify and blocks deploy). | Step 3 |
| 5 | Launch | Phone-only shell; `check.py` asserts the 5-tab bar and `index.html` / `division-N.html` URLs. | Step 5 |
| 6 | Before season end | Post-fetch score corrections (`score_edits`) are never re-fetched. | Phase 2 drift check |
| 7 | Should | `load_season` iterates `matches.json` (overwritten each run), not the archive. | Step 3 |
| 8 | Should | Schedule `left` is the recap's home team in only 6 of 15 matches; `events.py` labels `left` as "home". | Step 3 (use recap `opponents[0]`) |
| 9 | Should | Cron at `:00` (GitHub's high-load minute). Public-repo scheduled workflows are disabled after 60 days of no repo activity. | Step 2 / runbook |
| 10 | Should | Player identity is name-only; slugs strip non-`a-z0-9` ("José"/"Jos" collide). | Step 2 (verify check) |
| 11 | Should | Docs drifted (README baseline warning, CLAUDE.md "not done" list, summary.md). | Step 16 |
| 12 | Minor | `build.py` fails on raw substring `"None"`; `check.py` correctly uses word boundaries. | Step 2 |
| 13 | Minor | Teams index lists only teams with scoring players (30 of 31); team pages lack standings/results. | Step 5/7 |
| 14 | Minor | Stray legacy `Park Slope Dart League (PSDL) - Stats.csv` at repo root; duplicate `docs/allstar-standings.csv`. | Step 2 |
| 15 | Note | PPW definition and `ALL_STAR_CUT` open; forfeits not surfaced; not reconciled → launch as beta. | Step 16 |
| 16 | Note | BRD risk #2 (DartConnect ToS review) still open. | Step 16 checklist |
| 17 | Note | No synthetic rule tests (BRD §5.4 #2). | Phase 2 |

---

## 4. Production architecture

```
 STATS PATH (must never depend on Supabase)
 DartConnect ─► fetch.py [status=="C" only] ─► data/seasons/<id>/recaps/*.json
        ─► commit archive (always) ─► verify.py ─► build.py ─► check.py ─► deploy
                                       └ HARD gate: any failure = nothing publishes

 MANAGED PATH (human-entered; failure degrades gracefully)
 Supabase tables ─► sync_managed.py (public tables, anon key, read-only)
        ─► data/managed/{venues,team_venues,fixtures,streams,announcements}.json (committed)
        ─► managed check: SOFT gate — on error, build with last good snapshot and warn

 RUNTIME (visitor's browser; no server of ours)
 live.js       ─► Supabase REST (read)  ─► streams, announcements
 join forms    ─► Supabase REST (insert only) ─► signups_player, signups_venue (never publicly readable)
 embeds        ─► YouTube / Twitch iframes (we never host video)
```

Two gates, different strictness: a **stats** failure blocks every publish; a **managed-data** failure
(e.g. a typo in a fixture team name) publishes with the last good snapshot and raises a warning.

---

## 5. Data architecture and Supabase

| Category | Lives in | Why |
|---|---|---|
| **A. DartConnect archive** | Git: `data/seasons/<id>/recaps/*.json` | Permanent, versioned, vendor-independent. Never in a database. |
| **B. Derived stats** | Nowhere stored — recomputed each build from A | "Hits are the unit of truth"; a stored total can drift. |
| **C. Website content** | Git: `content/*.md`. Announcements in Supabase. | Reviewed and rollback-able; announcements must change in minutes. |
| **D. User submissions** | Supabase only, private | Contains emails/phones. **Never enters the public repo.** |
| **E. Livestream data** | Supabase `streams`; public fields snapshotted into git | Runtime edits plus a durable copy. |

**Conceptual tables** (no migrations yet — Step 8):
- `venues`: name, address, neighborhood, website, active.
- `team_venues`: season, team name **exactly as DartConnect spells it**, venue.
- `fixtures`: season, date, time (default 19:30), division, home team, away team, optional venue override, status (scheduled / postponed / cancelled). **Future matches only**; once played, DartConnect is the source of truth.
- `streams`: fixture (dropdown in Table Editor), platform (`youtube`/`twitch`), external ID, optional title, `featured`, `status_override` (nullable), optional `replay_url`.
- `announcements`: title, body, pinned, publish/expire dates.
- `signups_player`: name, email, phone (optional), experience, wants (join a team / be placed / info), preferred division/neighborhood, notes, status, timestamp.
- `signups_venue`: bar name, contact, email/phone, address, number of teams, board details, willing to stream, notes, status, timestamp.
- *Phase 2:* `venue_channels`.

**Never in the database:** recaps, hits, points, standings, players, teams, matches.

**Security:** Row-Level Security on every table. Public may `SELECT` venues / team_venues / fixtures /
streams / announcements, and `INSERT` (with length limits) into the two signup tables only. Signups are
not publicly readable. The build needs **no secrets** (anon key is public by design). **Never commit the
`service_role` key.** Turn on 2FA for every admin.

**Free-plan facts (verified 2026-09-20):** 500 MB DB, **no backups**, **projects pause after 1 week of
inactivity**, 5 GB egress. Mitigations: the scheduled build reads Supabase weekly (keep-alive); monthly
CSV export of signups; committed snapshots of everything else. Pro is $25/mo if it ever matters.

---

## 6. Hosting

GitHub Pages for launch. Free; workflow already written; every dynamic need is handled by Supabase
from the browser. Limits (verified): site ≤ 1 GB, ~100 GB/mo soft bandwidth. Custom domain + HTTPS
are free.

Revisit Cloudflare Pages only if a private repo is wanted, or server-side code becomes necessary
(spam protection, email). Cloudflare Pages free plan (verified): 500 builds/mo, 20,000 files, 25 MiB per
asset. Deploying a prebuilt `public/` from Actions means the migration is small.

Running cost: $0 hosting + $0 Supabase Free + domain at Namecheap (~$10–20/yr).

---

## 7. Livestream architecture

**Provider: YouTube Live** (free; viewers need no account; auto-archive; the replay is the same video
ID; up to 10 active streams per channel; API available later). Twitch supported via the same
`platform` + `external_id` columns. Twitch embeds require the `parent` parameter listing every domain
the site is served on, and cannot autoplay on mobile.

**Setup:** one PSDL-owned channel; a reusable **stream key per pub**. Pubs stream from a laptop with a
webcam, or a phone/camera on a tripod, using OBS or a free RTMP app. Roughly 3–4 Mbps upstream for 720p
— test on the pub's Wi-Fi. Each week the admin pre-creates a scheduled broadcast per streaming pub in
YouTube Studio and pastes the **video ID** into a `streams` row.

**To prove in the pilot (unverified):** how long a new channel takes to be enabled for live streaming;
whether laptop/RTMP streaming avoids the 50-subscriber requirement that applies to streaming from the
YouTube mobile app. The permanent `embed/live_stream?channel=ID` URL is **not** in Google's official
docs — do not build on it; use per-broadcast video IDs.

**Website behaviour (MVP):**
- Status is **derived from time**: Upcoming before start; **Live** from start (with grace) to start + ~4 h; then Ended. `status_override` handles exceptions.
- Featured stream = row flagged `featured`, else earliest-started live. Others: a grid of cards; load an iframe only on tap (multiple players would overload a phone).
- Nothing live: empty state + next 3 scheduled streams + link to Schedule.
- JS off: renders the build-time snapshot.

**Admin workflow:** Monday add a `streams` row per pub → Tuesday nothing (auto Live) → if needed set `status_override`.

**Later, same data model:** permanent `venue_channels` + auto-detect via YouTube API; replay links on
match pages (trivial once fixtures join to `dc_match_id`); multi-camera; DartConnect scores beside video.

---

## 8. Information architecture

**Desktop top bar:** Home · Schedule · Live · Standings · All-Stars · Teams · Players · About + gold **Join** button.
**Mobile bottom bar (5):** Home · Schedule · Live · Stats · More. "Stats" opens a sub-strip
(Standings / All-Stars / Teams / Players / Matches) using the existing division-chip pattern; "More"
holds About, Join, Venues.

```
/                         Home
/schedule/                Upcoming + results
/live/                    Live
/standings/division-1/    (default division)
/stats/all-stars/division-1/   /stats/rare-hits/   /stats/matches/
/teams/  /teams/<slug>/   /players/  /players/<slug>/   /matches/<id>/
/about/  /about/divisions/  /about/how-it-works/  /about/venues/
/join/   /join/player/   /join/venue/
```

Nothing is published yet, so there are no old URLs to preserve. Restructure now.

| Existing feature | Integration |
|---|---|
| Standings | `/standings/division-N/`; team names link to team pages; calculations untouched |
| All-Star leaderboards | `/stats/all-stars/…`; "ranked within division only" note stays |
| Player pages | `/players/<slug>/`; content untouched, new shell |
| Team pages | Extended with standings row, recent results, venue line |
| Match pages | `/matches/<id>/`; fix home/away title order; later a replay link |
| Rare-hit screen | Linked from Home and the All-Stars hub |
| Design components | Reused. Additions (top nav, responsive container, embed frame, status pill) use existing tokens only. |

---

## 9. Scope

**MVP (Version 1):** repo + CI + Pages + custom domain/HTTPS · hardened pipeline (status guard,
season-scoped archive, last-updated stamp) · responsive shell + new nav/URLs with all stats pages
migrated · Home, Schedule, Live, About, Join (player + venue), Venues · Supabase tables + RLS +
`sync_managed.py` · join forms with honeypot (admins use Table Editor) · one-pub pilot + one-page pub
streaming guide · announcements · **beta/unofficial banner** · refreshed docs + runbook.

**Phase 2:** signup email notification + Turnstile spam protection (needs one small function or
Cloudflare) · drift check with revision storage for `score_edits` · synthetic rule-test fixtures ·
forfeit "awaiting credit" flags · replay links on match pages · Supabase Pro · All-Star cut line ·
season selector + historical backfill (a commissioner decision) · **a commissioner-friendly admin
surface** (§10) · per-venue pages · analytics.

**Future (architected for, not built):** `venue_channels` + auto live-detection · multi-camera ·
DartConnect live scores beside video · player accounts / captain tools.

---

## 10. Administration

- **Now (owner + CJ):** Supabase Table Editor for signups, venues, fixtures, streams, announcements; GitHub web UI (or Claude Code) for `content/*.md`. Both admins get 2FA on GitHub and Supabase. Supabase free-plan seat/invite limits for a second admin are **unverified** — check at Step 8.
- **Later (commissioners, not tech-savvy):** the raw Table Editor is too easy to break. Phase 2 should give them a narrow surface — for example a small password-protected page for exactly two jobs (add/edit a stream; post an announcement), or Supabase saved views — plus a written runbook. Decide when they are onboarded; do not build it now.

---

## 11. Implementation plan and tracker

One step per Claude Code session, in order. Before any refactor, save a hash of every file in
`public/`; a pure refactor must reproduce it exactly (the "golden build").

- [ ] **Step 1 — Tools, repo, first deploy of the existing site** *(in progress 2026-09-20: Python 3.12.10 and Git installed; `verify.py`, `build.py` (165 pages) and `check.py` all pass locally on Windows; the repo already exists and is deployed; remaining: push the Windows fixes, `.gitattributes` and this roadmap to `main` and watch the run)*
  - Do: push the Windows fixes to CJ's existing repo (not a new one) and watch the deploy.
  - Verify: `verify.py`, `build.py`, `check.py` pass locally; Actions run is green; the `github.io` site loads on a phone.
  - Rollback: unpublish Pages; `git revert`.
- [ ] **Step 2 — Pipeline hardening.** Archive only `status == "C"` matches; move cron off `:00`; add a "last updated" stamp; align `build.py`'s `None` check with `check.py`; add a slug-collision check to `verify.py`; move the stray root CSV to `docs/legacy/`. Verify: golden build identical except the stamp; a fake non-`C` match is skipped. *Needs Step 1.*
- [ ] **Step 3 — Season-scoped archive.** `data/seasons/<id>/{recaps,matches.json,standings.json}` + `data/seasons.json` (current season); per-season verify baseline; derive matches from the archive plus a per-run schedule snapshot; use the recap's home/away, not `left`. Verify: golden build identical; a pretend new `SEASON` doesn't break old-season verification. *Needs Step 2.*
- [ ] **Step 4 — Mockups for new pages** in `design/`: Home, Schedule, Live (live / empty / multi-stream), About, Join (player, venue), a desktop layout of an existing page, the new nav; gold LIVE indicator; beta banner. Owner approves. *Needs Step 3.*
- [ ] **Step 5 — Responsive shell, navigation, URL restructure.** Widen at ≥768 px; top nav; mobile bottom bar with Stats/More; move existing pages to new URLs; update `check.py` invariants in step (never loosen). Verify: `check.py` passes; same 165 stats pages at new URLs, unchanged content; zero broken links. *Needs Step 4.*
- [ ] **Step 6 — About and content pages** from `content/*.md` with a small stdlib Markdown-subset renderer. *Needs Step 5.*
- [ ] **Step 7 — Homepage v1 (existing data only).** Schedule/Live sections omitted (not placeholdered) until data exists. *Needs Step 5.*
- [ ] **Step 8 — Supabase project + schema.** Create project (2FA), commit `supabase/schema.sql` with RLS, run it, copy URL + anon key into repo config. Verify with the anon key: insert into signups works; reading signups is **denied**; reading `streams` works. Check the admin-seat question (§10). *Needs Step 5.*
- [ ] **Step 9 — Join forms** (`/join/player/`, `/join/venue/`): validation, honeypot, success/failure states, mailto fallback. *Needs Step 8.*
- [ ] **Step 10 — Schedule import + Schedule page.** Owner supplies the CSV → import to `fixtures`; write `scraper/sync_managed.py` + soft managed-data check (team names must exist in standings); page merges upcoming fixtures with DartConnect results. Verify: a deliberate typo warns, doesn't block the deploy. *Needs Steps 8, 3.*
- [ ] **Step 11 — Venues.** Fill `venues` / `team_venues` (owner supplies the team → bar list), show venue on schedule cards, `/about/venues/`. *Needs Step 10.*
- [ ] **Step 12 — Live page.** `live.js` (plain `fetch`), derived status, featured player, tap-to-load grid, empty state, Home "live now" banner. Test first with a public non-PSDL video. *Needs Steps 10, 8.*
- [ ] **Step 13 — Real pub pilot.** Create the PSDL YouTube channel, enable live, issue one pub's stream key, stream a real match, test on cellular; draft the one-page pub guide. *Needs Step 12.*
- [ ] **Step 14 — Announcements** (table, runtime banner, Home feed). *Needs Step 8.*
- [ ] **Step 15 — Custom domain (Namecheap).** Set the domain in repo Pages settings; add DNS records in Namecheap → Advanced DNS; enable Enforce HTTPS; add the domain to any Twitch `parent`; page titles, share tags, favicon. Rollback: remove the custom domain — the `github.io` URL keeps working.
- [ ] **Step 16 — Docs, runbook, launch QA.** Refresh README / CLAUDE.md / summary.md / DESIGN-SPEC.md; write `docs/RUNBOOK.md` (weekly admin checklist, adding a stream, new season, backups, restore); real-device tests; beta/unofficial banner; complete the launch checklist in §12.

---

## 12. Launch checklist

**Claude can do:** code, SQL schema + policies, workflow edits, `sync_managed.py`, forms, Live page, docs, tests, the pub guide and runbook, the verify/build/check loop.

**The owner must do (external services / machines):**
- [ ] Install Python 3.12 and Git on the Windows PC.
- [ ] GitHub: the repo already exists (CJ's). Add the second admin as a collaborator now; move the repo into a shared organization before Step 15; both admins turn on 2FA.
- [ ] Namecheap: buy the domain; add DNS records as GitHub instructs; enable Enforce HTTPS.
- [ ] Supabase: create account + project, 2FA, run `schema.sql`, copy Project URL + **anon** key into the repo config. **Never commit the `service_role` key.**
- [ ] YouTube: create the PSDL channel, verify it, enable live streaming, generate a stream key per pub, pre-create scheduled broadcasts weekly.
- [ ] Supply the season schedule CSV and the team → bar list.
- [ ] **Review DartConnect's ToS and document the finding** (BRD risk #2) — the raw archive is public once the repo is.
- [ ] Line up one pilot pub; arrange commissioner reconciliation of 3 matches.
- [ ] Environment variables / API keys: **none required for MVP.**

---

## 13. Risks and unknowns

1. **Future fixtures in DartConnect?** Recheck after Week 2 posts (Wed 2026-09-23). If they appear, `fixtures` shrinks to overrides.
2. **Home team = host bar for every team?** The rulebook says the home team captain is responsible for the host establishment's court; no team → bar list exists yet.
3. **Season length / structure.** Fall 2025 rulebook: Division 1 = 8 teams / 14 weeks; Divisions 2–4 = 6 teams / 15 weeks. Fall 2026 has 7 teams in Division 1 (31 total). Confirm the current structure.
4. `competition_title` is "Park Slope Dart League - **Tuesday**" — is there, or will there be, another night?
5. Can the schedule feed ever list a `status` other than `C`? Step 2's guard protects against it.
6. YouTube live-enablement wait and the 50-subscriber rule for RTMP/laptop streaming — prove in the pilot.
7. Supabase Free: pausing after a week idle; admin seat limits; no backups.
8. GitHub disables scheduled workflows after 60 days without repo activity; assume bot commits don't count.
9. Nobody (including the author of this plan) has viewed the built site in a real browser — Steps 1 and 5 are its first real-device tests.
10. The PDF rulebook text is a word-per-line extraction; rule statements here come from `summary.md`, the BRD and targeted reads.

---

## 14. Verified vendor facts (2026-09-20)

- Supabase Free: 500 MB DB, 2 active projects, paused after 1 week of inactivity, no backups, 5 GB egress; Pro from $25/mo.
- GitHub: scheduled workflows in public repos are disabled after 60 days without repo activity; scheduled runs can be delayed or dropped at high-load times (start of the hour); shortest interval 5 minutes. Pages: ≤ 1 GB site, ~100 GB/mo soft bandwidth.
- Cloudflare Pages Free: 500 builds/mo, 20,000 files, 25 MiB per asset.
- Twitch embeds: `parent` param required; no login needed to watch; no autoplay on mobile.
- YouTube: mobile streaming needs 50+ subscribers and a verified channel; limit of 10 active streams per channel and 3 per stream key; `embed/live_stream?channel=` is undocumented in Google's player docs.
