# BRD — PSDL All Star Points Automation

**Project:** Automated All Star Points tracking and public dashboard for the Park Slope Dart League
**Author:** cjpospisil20@gmail.com
**Date:** 2026-09-18
**Status:** Draft for commissioner review — rules validated, all §5.6 rulings resolved
**Season in scope:** Fall 2026 (season_id 25174), 5 divisions, 31 teams

---

> ## Implementation status update — 2026-09-18
>
> *Appended after the BRD was written. The sections below are unchanged: they record what was
> known and decided at the time, and the Section 2 impact numbers stand as measured. This block
> records only what has since been built.*
>
> **The app exists.** Phase 3 (Dashboard) is built, not pending. `site/build.py` generates a static
> mobile web app — **165 pages** from the archived Week 1 data: 104 player pages, 15 match pages,
> 30 team pages, 5 division leaderboards, 5 standings pages, three indexes and a rare-hit
> celebration screen. Python standard library only; no dependencies, no server-side component.
>
> **§4 auditability is implemented.** Every hit on every page links to the DartConnect recap of the
> match that produced it, naming the set and game — §5.4 test 5.
>
> **§5.4 tests 2 and 4 are automated.** `scraper/verify.py` asserts the validated baseline (104
> players, 20,326 points, 437 busts), that every player's hits sum to their displayed total, that a
> bust never yields a hit, that `171+` and `180` never pay more than face value, that cricket values
> match the rulebook table, and that every hit carries a recap link. Totals are now *derived* from
> individual hit records rather than accumulated, so a published total cannot drift from the hits
> shown beneath it. Builds read only the local archive, so they are offline and reproducible.
>
> **`[TEAM NAME]` is resolved, and needed nothing from the league.** The design had player→team
> flagged as blocked on a roster nobody held. A turn's side *is* the player's team, and
> `matchInfo.opponents[]` is in home/away order, so the mapping was already inside the recaps we
> archive: **174 players mapped, zero appearing under two teams, every team name matching the
> standings list.** Two of the other three design placeholders also closed — MPR is available
> (DartConnect reports `mpr` per cricket side) and form stats are recomputed from turn data because
> DartConnect's player-card endpoint returns 403 without a login.
>
> **Still outstanding, unchanged from the BRD:** hosting/deployment; Phase 2 commissioner
> reconciliation (§5.4 test 1), which remains the gate before automated numbers become official;
> scheduled weekly runs; forfeit exception handling (§5.2.4); and the exact Fall 2026 season length.
> One new league input is needed: **how many players per division make All Star**, so the cut line
> can be drawn. Until it is given, the cut line is omitted rather than guessed.

---

## 1. System & People Foundations

### Primary systems

| System | Role | Notes |
|---|---|---|
| **DartConnect** (`recap.dartconnect.com`, `tv.dartconnect.com`) | **System of record for all match play.** Every turn of every game is captured at the board. | Source of truth. Read-only to us. No vendor relationship required. |
| **New PSDL All Star site** | **To be built.** Ingests DartConnect data, applies PSDL scoring rules, publishes standings. | PSDL-owned and operated. |
| `yourleaguestats.com` | Legacy destination, manually keyed by commissioners. | **Out of scope, to be retired.** Referenced only as a model for layout and column definitions. No data migration from it. |

A deliberate decision: the legacy site's data is **not** migrated. Everything it displays originated in
DartConnect, so the new system re-derives it from the source rather than inheriting years of hand-keyed
entries and their errors.

### Key stakeholders

| Person / group | Relationship to this project |
|---|---|
| Project owner (this document's author) | Requester, approver, and ongoing operator of the new site. |
| **League Commissioners** — Johnny Colonna, Mike Sheehan | Feel the pain daily. Primary beneficiaries: this removes their data-entry burden entirely. |
| **Team captains** | Currently responsible for marking all stars on paper score sheets (Rulebook §F.1). Relieved of the task. |
| **Players (~31 teams)** | Consumers. Today most never see their all-star standings; the dashboard makes them visible. |

### Supporting materials

- **PSDL Rules & Regulations, Fall 2025** — Section F ("Scoring") defines every All Star Point rule used
  below. This is the authoritative rules source.
- **Legacy stats screenshots and column legend** from `yourleaguestats.com` — used to confirm the
  intended stat columns (WP, PPW, AS, 95+, R5–R9, 171+, 171+T, C3–C6, S90, F90, 180, PTS).
- **Working feasibility prototype** — validated against all 15 completed Week 1 matches (see §5).

---

## 2. The Core Problem & Business Impact

### The operational pain

All Star Points are tracked on paper, transcribed into email, and then hand-keyed into a website —
despite the fact that **every underlying dart throw is already captured electronically by DartConnect
at the moment it is thrown.** The league is manually re-entering data it already owns.

The chain today:

1. Captains mark all stars on a paper score sheet during play.
2. The sheet is emailed to the commissioners.
3. Commissioners read the sheets and type each player's points into `yourleaguestats.com`.

Every step is a transcription opportunity for error, and the rulebook itself concedes the fragility:
illegible sheets mean *"scores and all star points cannot be properly credited."*

### Who is affected

- **Directly:** League Commissioners (Johnny Colonna, Mike Sheehan) — the full data-entry burden.
- **Directly:** Team captains — per-match tallying and reporting.
- **Downstream:** Players — season-end All Star recognition depends on this data being right.
- **Downstream:** League governance — Rulebook §F.1 makes incorrect or missing all stars a
  disciplinary matter, so data quality carries real consequences.

### Quantified impact

| Measure | Value | Source |
|---|---|---|
| Commissioner data-entry time | **2–3 hours per week** (~30 min per division × 5 divisions) | Owner estimate |
| Per season (10–16 week seasons per Rulebook §G.2) | **~25–40 hours per season** | Derived |
| Annualized across two seasons | **~50–80 hours per year** of volunteer commissioner time | Derived |
| Matches to process | ~15 per week, **~180 per season** | DartConnect season schedule |
| Player rows to key per week | **107 players scored all-star points in Week 1 alone** | Prototype, measured |
| All-star points awarded, Week 1 | **21,226 across 5 divisions** | Prototype, measured |

Measured division split for Week 1 — confirming higher divisions carry disproportionate effort:

| Division | Points | Division | Points |
|---|---|---|---|
| Division 1 | 7,016 | Division 4 | 3,420 |
| Division 2 | 3,960 | Division 5 | 2,829 |
| Division 3 | 4,001 | | |

**Target: reduce the 2–3 hours per week to effectively zero**, with commissioner involvement limited to
exception handling (forfeits and corrections).

Beyond hours, there is an unquantified but real cost: *"not everyone even looks at them."* A season-long
recognition program that members cannot conveniently see is delivering a fraction of its intended value.

---

## 3. Historical Context ("How We Got Here")

**Why the process looks like this:** the PSDL rulebook is built around **paper score sheets**. Section F.2
defines All Star Points as *score sheet notations* — mark 95+, prefix a start with `S`, a finish with `F`,
circle anything 171+. The entire scheme presumes a human with a pen at the board.

DartConnect was subsequently adopted for scoring and standings, but **All Star tracking was never migrated
with it.** The paper process simply continued alongside the electronic one, producing today's duplication:
the same throws recorded twice, once by machine and once by hand.

**Why not an API:** PSDL formally requested API access from DartConnect and **received no response** — the
request was ghosted. This BRD's approach was chosen specifically because it requires no vendor cooperation
and no agreement that DartConnect could decline or withdraw.

**Decisions deliberately preserved:**

- Point values in §5 are taken verbatim from the Fall 2025 rulebook. This project **automates the existing
  rules; it does not reinterpret them.**
- Commissioner authority over corrections and forfeit credits is retained, not automated away.

---

## 4. Current State vs. Future State

### Current state (per match night)

| # | Step | Owner | Failure mode |
|---|---|---|---|
| 1 | Match played; DartConnect records every dart | Players / scorekeeper | — |
| 2 | Captain *separately* marks all stars on paper | Captain | Missed, misjudged, or illegible entries |
| 3 | Sheet emailed to commissioners | Captain | Late or never sent |
| 4 | Commissioner reads sheets, types into website | Commissioner | **2–3 hrs/week**; transcription errors |
| 5 | Standings visible on legacy site | — | Low awareness; few players look |
| 6 | Season-end All Stars determined per division | Commissioner | Depends on all of the above being right |

### Future state

| # | Step | Owner | Timing |
|---|---|---|---|
| 1 | Match played; DartConnect records every dart | Players / scorekeeper | Unchanged |
| 2 | System pulls completed matches from DartConnect | Automated | Nightly / post-match-night |
| 3 | Rules engine applies Rulebook §F to every turn | Automated | Seconds |
| 4 | Per-player, per-division standings published | Automated | Same night |
| 5 | Commissioner reviews exceptions only (forfeits, corrections) | Commissioner | Minutes, as needed |
| 6 | Players view live standings any time | Self-serve | Continuous |

**Steps 2, 3, and 4 of the current process are eliminated entirely.**

### Where the information lives

- **Player record** — season totals per stat column, division rank, PPW.
- **Division view** — the All Star leaderboard, the season-end award basis.
- **Match view** — every all-star event in a match, with a link back to the DartConnect recap so any
  number on the site can be traced to the exact turn that produced it. *This auditability is what earns
  captain and commissioner trust in an automated figure.*

---

## 5. Clear Business Rules

### 5.1 Source data — validated, not assumed

DartConnect's recap application embeds its complete match data as structured JSON within each page,
rather than rendering it only as HTML. This is **materially more robust than conventional screen
scraping** — there are no visual selectors to break when the site is restyled.

Two public, unauthenticated endpoints supply everything:

| Purpose | Endpoint |
|---|---|
| Season schedule + all match IDs | `POST tv.dartconnect.com/api/league/ParkSDL/matches/{season_id}` |
| Full turn-by-turn match detail | `GET recap.dartconnect.com/games/{dc_match_id}` |

Each turn provides player name, turn score, running score, and DartConnect's own event labels
(`TON`, `BUST`, `MISS`, `DO (n)`):

```json
{"name": "Josh Hollenberg", "turn_score": 125, "current_score": 219,
 "notable": 125, "color": "TON 25"}
```

> **Critical rule — do not trust DartConnect's highlighting.** DartConnect flags notable 01 turns at
> **100+** (a "TON"). **PSDL's threshold is 95+.** Relying on their highlight would silently drop every
> 95–99 all-star in the league. Because `turn_score` is present on *every* turn, the system **recomputes
> PSDL's rules from raw turn data** and never depends on the vendor's flag. This also insulates us from
> any future change to their highlighting logic.

> **Cricket is the exception — trust `notable` completely.** For cricket the field encodes *counted*
> marks and already matches PSDL's threshold exactly, so it is used directly. The two rules are
> deliberately opposite: **compute 01 ourselves, read cricket from DartConnect.**

> **Team list rule.** Source teams from the standings/competitors list (**31 teams**), *not* the match
> filter dropdown, which contains 35 entries including four non-competing entries (`E-Z Buttons (Denny's)`,
> `Farm.One`, `Lucky 7's`, `The H is O (Commish)`).

> **Player identity rule.** **DartConnect names are authoritative as-is.** No reconciliation against any
> legacy name list. Names are normalized only for display artifacts (e.g. stray quoting in
> `Anaelechi "Lay""" Owunwanne`).

### 5.2 Scoring rules (Rulebook §F)

**01 games (501 / 701)**

| Rule | Definition | Points awarded |
|---|---|---|
| **95+** | Any scoring turn of 95 or more | Face value of the turn |
| **S90+** | A 90+ score on the turn a side *gets ON* (double-in games) | Face value of the turn |
| **F90+** | A 90+ score on the turn a player *gets OFF* (checkout ≥ 90) | Value of the checkout |
| **171+** | Count of turns scoring 171 or more | *Sub-flag of 95+ — no separate points* |
| **171+T** | Sum of the scores of those 171+ turns | *Descriptive total* |
| **180** | Count of maximum turns | *Sub-flag of 95+ — no separate points* |

**Cricket** — fixed values per rulebook:

| Rounds | Points | Corks | Points |
|---|---|---|---|
| R5 | 100 | C3 | 100 |
| R6 | 120 | C4 | 125 |
| R7 | 140 | C5 | 150 |
| R8 | 160 | C6 | 180 |
| R9 | 180 | | |

**Exclusions and edge cases**

1. **Busts do not count.** A busted turn is void for all-star purposes (§F.1). *Validated: 437 busts
   correctly excluded in Week 1.*
2. **Cricket marks count only if they score.** Marks on a number the opponent has already closed earn
   nothing (§F.1). **No state machine required** — DartConnect's `notable` field (`5M`, `3B`) is already
   a count of marks that *counted*, not marks thrown, and it flags only at PSDL's own 5-mark threshold.
   *Validated both directions in Week 1 data:* a `T19, T16` turn (6 marks thrown) was flagged `5M`
   because the opponent held a mark on 19; a `T16, S15x2` turn (5 marks thrown) was **not flagged**
   because the opponent closed 16 earlier in the same round, leaving 4 counting marks.
3. **A side gets ON once.** In doubles, S90+ applies only to the turn the *side* doubles in — not to a
   partner's first turn. *This was a real defect found and fixed during prototyping.*
4. **Forfeits are not derivable from DartConnect.** Players on a signed forfeit sheet are credited at
   season end based on their points-per-week average (§F.3). **This remains a manual commissioner input.**

### 5.3 Must / must not

The system **must**:

- Recompute all points from raw turn data using PSDL thresholds, independent of DartConnect's flags.
- Exclude busted turns and non-scoring cricket marks.
- Attribute every point to a named player, division, match, and specific turn.
- Support commissioner override of any computed figure, with the override recorded and attributed.
- Be re-runnable and idempotent — reprocessing a match must never double-count.
- Handle DartConnect score edits (the `score_edits` field) by recomputing, not appending.

The system **must not**:

- Require credentials, payment, or any agreement with DartConnect.
- Award points for busts, dead cricket marks, or a partner's non-starting turn.
- Silently drop a match it failed to fetch — failures must surface visibly.

### 5.4 Proof of success

| # | Test | Criterion |
|---|---|---|
| 1 | **Manual reconciliation** | Two commissioners hand-score 3 matches (one per division tier); system output matches 100%. |
| 2 | **Rule unit tests** | Each rule in §5.2 covered by a fixture: bust excluded, dead cricket mark excluded, partner-start excluded, 95 counts, 94 does not. |
| 3 | **Full-season replay** | Every completed Fall 2026 match processes without error. |
| 4 | **Idempotency** | Reprocessing the full season twice yields identical totals. |
| 5 | **Auditability** | Any published figure traces to its DartConnect recap turn in one click. |
| 6 | **Acceptance** | Commissioners confirm a week's standings without touching a spreadsheet. |

### 5.5 Prototype status — already validated

A working engine has processed **all 15 completed Week 1 matches**, with every rule in §5.2 implemented:

- **104 players** scored all-star points; **20,326 points** awarded.
- **437 busts** correctly excluded.
- **76 get-on turns** correctly identified across 38 double-in games (exactly two per game).
- Sample output: `Tom Lettieri (Div 1) — 835 pts: 95+ ×5, R5 ×1, C3 ×2`.

**No rules logic remains outstanding.** An earlier draft of the engine counted all cricket marks thrown
and over-credited by 900 points across 3 extra players; adopting DartConnect's counted-mark field
corrected this and closed the last open logic item.

S90+ is implemented and verified but produced **zero hits in Week 1** (highest get-on turn: 86). A 90+
double-in is genuinely rare — expect only a handful per season.

Remaining work is **delivery, not rules**: persistent storage, the dashboard, scheduled runs, and
forfeit exception handling.

### 5.6 Rulings — resolved

| # | Question | Ruling |
|---|---|---|
| 1 | Does a 95+ 01 turn award its **face value**? | **Confirmed — face value.** Implemented. |
| 2 | Are `171+`, `171+T`, and `180` descriptive flags rather than extra points? | **Confirmed — descriptive only.** A 180 never pays twice. |
| 3 | Does **S90+ apply to 701 Triples**, or only 501 Doubles? | **Confirmed — applies to 701 Triples.** Implemented for all double-in formats. |
| 4 | Should the **paper score sheet be retired**, or run in parallel? | **Parallel — the league runs paper sheets regardless.** Validation is therefore free, and a rule amendment is optional rather than required. |

The only item still outstanding is the exact **Fall 2026 season length** (the rulebook permits 10, 14 or
16 weeks), which is needed for PPW and for the §G.2 eligibility minimums.

---

## 6. Risks & Target Timelines

### Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | **DartConnect changes its data structure without notice.** No agreement exists; they did not respond to the API request. | Medium | High — feed stops | Fetch raw JSON and **archive every match payload permanently on first fetch**. Even if the source changes or disappears, the season's data is already ours. Alert on parse failure rather than publishing wrong numbers. |
| 2 | **Terms-of-service exposure.** Automated retrieval of a third-party site after an unanswered API request. | Low | Medium | Data is publicly accessible without authentication and concerns PSDL's own league play. Keep request volume trivially low (~180 requests/season, rate-limited, identifying user-agent). Review DartConnect's ToS before go-live and document the finding. Retain the option to re-approach them with a working case. |
| 3 | ~~Cricket over-counting~~ **Resolved.** DartConnect's counted-mark field implements the rule exactly; verified in both directions. | — | — | Closed. Reconciliation (§5.4 test 1) still applies as a check, but this is no longer a go-live blocker. |
| 4 | **Silent scoring divergence** — automated totals quietly differ from what captains expect. | Medium | High — trust loss | Per-turn audit trail; **paper sheets already run in parallel regardless**, making cross-checking free; publish a visible reconciliation for Week 1. |
| 5 | **Forfeit credits forgotten**, since they are the one manual input. | Medium | Medium | Dashboard flags forfeited matches as *awaiting commissioner credit* until resolved. |
| 6 | **Adoption failure** — the new site is ignored as the old one was. | Medium | Medium — effort wasted | Announce at captains' meeting; share a division leaderboard link weekly; make player-level pages linkable. |
| 7 | **Bus factor of one.** A single owner builds and operates it. | High | Medium | Keep infrastructure boring and cheap; document the runbook; retain a commissioner-accessible export. |
| 8 | **Mid-season rules disputes** arising from newly visible data. | Low | Medium | Rulebook remains authoritative; commissioner override exists; audit trail resolves disputes factually. |

### Timeline

Go-live target is **as soon as possible**, mid-season Fall 2026. Week 1 (Sept 15) is already processed.

| Phase | Scope | Owner | Target |
|---|---|---|---|
| **0 — Validated** | Feed proven; rules engine drafted; Week 1 processed | Owner | ✅ Complete (2026-09-18) |
| **1 — Delivery groundwork** | ~~Rules~~ **complete.** Persistent storage; per-match archival; scheduled weekly runs | Owner | ~1 week |
| **2 — Reconciliation** | Commissioners hand-score 3 matches against system output (§5.4 test 1) | Commissioners | ~3 days after Phase 1 |
| **3 — Dashboard** | Division leaderboards, player pages, match detail with recap links | Owner | ~1–2 weeks |
| **4 — Soft launch** | Live to commissioners and captains; paper sheets continue in parallel | Owner + captains | Target: **late Oct 2026** |
| **5 — Full launch** | Announced league-wide; commissioner data entry ceases | Owner | Target: **Nov 2026** |
| **6 — Season close** | Forfeit credits applied; All Stars determined per division | Commissioners | End of Fall 2026 |
| **7 — Rule amendment** | Retire paper all-star notation in the next rulebook revision, if the parallel run succeeds | Commissioners | Spring 2027 rulebook |

### Backfill

Historical seasons are **out of scope for launch.** DartConnect exposes previous seasons
(`has_previous_seasons: true`), so backfill is technically available later at low cost. Prior seasons'
official results stand as recorded — a recomputation could contradict published history and should be a
deliberate commissioner decision, not a side effect of launch.

### Approval

Approved by the project owner, who also operates the resulting system. Commissioner sign-off is required
only at **Phase 2 (reconciliation)** — the point at which automated numbers become the league's official
record.
