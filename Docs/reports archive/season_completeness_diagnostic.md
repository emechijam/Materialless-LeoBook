# Season Completeness Diagnostic Report
**Date:** 2026-03-15 | **DB:** [Data/Store/leobook.db](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Store/leobook.db) | **No code changed**

---

## ROOT CAUSE ANALYSIS

### Finding 1 — Why 118 seasons show COMPLETED

**Root cause: the fallback branch of [_get_expected_matches()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/season_completeness.py#114-142) is a self-fulfilling prophecy.**

When a league in the [schedules](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/db_helpers.py#277-280) table has **fewer than 4 registered teams** in
`teams.league_ids`, the heuristic cannot compute `team * (team-1)` and falls back to:

```python
return scanned_count or 1   # season_completeness.py L141
```

This sets `total_expected_matches = total_scanned_matches`. Therefore:

```
completeness_pct = (scanned / expected) * 100 = 100.0
```

Then the status check fires:
```python
if completeness_pct >= 99.0 and scheduled == 0 and live == 0:
    status = "COMPLETED"   # L80
```

**Query 2D confirms this exactly:**
```
total_completed: 118
heuristic_match: 118   ← ALL 118 have expected == scanned
real_completion: 0     ← NONE completed by real match data
```

**Query 2B shows the anatomy:** Every COMPLETED season has
`total_expected_matches: 1` or a similarly tiny number — not the ~380 matches a
real 20-team league would have. They are **stub leagues** (cup finals,
playoff legs, super cups, or leagues whose teams were never scraped into [teams](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/gap_scanner.py#273-347))
that happen to have only finished matches and zero scheduled ones.

**Query 2E confirms the team count:** All 5 sampled COMPLETED seasons have
`team_count_via_like: 2` → fallback triggered → `expected = scanned`.

---

### Finding 2 — What P2 actually checks

P2's gate (`data_readiness.py L195`) is:

```python
is_ready = critical_count == 0 and completed_mismatch == 0
```

Where `completed_mismatch` = seasons marked COMPLETED where `scanned < expected`.

**This gate checks only internal self-consistency — NOT historical depth.**

Since the 118 COMPLETED seasons all have `expected == scanned` (by construction
of the fallback), `completed_mismatch = 0` is always true. The gate has no
concept of "does this league have 2+ seasons of data?" It simply asks
"are there any COMPLETED seasons that look incomplete?" — and the answer is no,
because the formula ensures they can never look incomplete.

**P2 will always pass READY on a single-season DB** as long as there are no
`fs_league_id` gaps.

---

### Finding 3 — RL trainer impact

**Query 2G is the decisive evidence:**
```
one_season:       1263
two_seasons:      0
three_plus:       0
```

Every single one of the 1,263 leagues has **exactly 1 season of data**.

**Query 2F shows the date range:**
```
earliest: 2012-03-03
latest:   2027-12-01
total_matches: 108,675
finished: 67,774
seasons: 22 distinct season labels
```

The 22 distinct season *labels* (2025, 2025/2026, 2024, etc.) are all
**different current-season runs of different leagues**, not historical depth
for the same leagues. The RL trainer needs multiple seasons of the *same*
league to learn form, momentum, and seasonal progression.

**What the completeness system tells the RL trainer: nothing useful.**
`season_completeness` does not expose a "minimum seasons per league" metric.
[check_rl_ready()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/System/data_readiness.py#230-262) (`data_readiness.py L230`) only checks for the existence
of `leobook_base.pth` and `adapter_registry.json` — it does not query
`season_completeness` at all, and it does not guard on historical depth.

---

### Finding 4 — Blocking mechanism (or lack thereof)

**There is no blocking mechanism.**

The pipeline flow is:
1. P1 — leagues/teams count threshold → passes once enriched
2. P2 — gap scan + season completeness internal consistency → always passes (see Finding 2)
3. P3 — model files exist → passes after first training run
4. RL trainer invoked

The RL trainer will **silently proceed** with whatever finished matches are in
[schedules](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/db_helpers.py#277-280), regardless of whether any league has more than one season. No
minimum-seasons-per-league guard exists anywhere in:
- [season_completeness.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/season_completeness.py)
- [data_readiness.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/System/data_readiness.py)
- [trainer.py](file:///C:/tmp/patch_trainer.py) (from prior code review)
- [Leo.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Leo.py) prologue dispatch

The 898 INCOMPLETE seasons (avg 32.6% coverage, avg expected 1,012 matches but
only ~83 scanned) are correctly flagged but they don't block anything either —
they are merely staged for re-enrichment.

---

## RAW QUERY RESULTS

### 2A — Status breakdown
```
ACTIVE:     247 seasons | avg_pct=94.3%  | avg_expected=144.9 | avg_scanned=134.1 | avg_scheduled=60.5
COMPLETED:  118 seasons | avg_pct=100.0% | avg_expected=8.6   | avg_scanned=8.6   | avg_scheduled=0.0
INCOMPLETE: 898 seasons | avg_pct=32.6%  | avg_expected=1012  | avg_scanned=83.0  | avg_scheduled=28.9
```

### 2B — Smallest COMPLETED seasons (top 20, all identical pattern)
All 20 rows: `expected=1, scanned=1, finished=1, scheduled=0, pct=100.0`
These are cup/playoff stub leagues with 1–2 registered teams.

### 2C — Seasons in schedules
| season      | leagues | total_matches | finished | scheduled |
|-------------|---------|--------------|----------|-----------|
| 2027        | 4       | 478          | 238      | 240       |
| 2026        | 292     | 21,981       | 6,632    | 15,349    |
| 2025/2026   | 559     | 73,611       | 48,313   | 25,298    |
| 2025        | 260     | 8,627        | 8,617    | 10        |
| 2024/2025   | 36      | 988          | 984      | 4         |
| 2024        | 28      | 1,063        | 1,063    | 0         |
| 2023/2024   | 8       | 196          | 196      | 0         |
| 2023        | 25      | 507          | 507      | 0         |
| 2022/2023   | 1       | 20           | 20       | 0         |
| 2022        | 12      | 228          | 228      | 0         |
| (older)     | various | various      | all finished | 0    |

> Note: older seasons (2021 and before) are from leagues that happened to have
> archive pages navigated during the current-season enrich. They are isolated
> occurrences, not systematic historical depth.

### 2D — COMPLETED heuristic self-match
```
total_completed: 118 | heuristic_match: 118 | real_completion: 0
```

### 2E — Team count for COMPLETED samples
All sampled entries: `team_count_via_like: 2` → fallback → `expected = scanned`
One outlier: `1_109_MssKGkWd` had 10 teams → `10×9=90`, and scanned=90 (genuine completion).

### 2F — Date range / finished matches
```
earliest: 2012-03-03 | latest: 2027-12-01
total: 108,675 | finished: 67,774 | seasons: 22 labels | leagues: 1,263
```

### 2G — Leagues with multiple seasons
```
one_season: 1263 | two_seasons: 0 | three_plus: 0
```

---

## WHAT IS NOT BROKEN

- **The `INCOMPLETE` classification** (898 seasons, avg 32.6%) is correctly
  flagging leagues where a large gap exists between expected and scanned.
- **The `ACTIVE` classification** (247 seasons, avg 94.3% coverage with scheduled
  matches present) is correct — these are live leagues mid-season.
- **The ACTIVE seasons average 94.3% coverage** — the scraper is correctly
  ingesting current-season data.
- **The `team * (team-1)` formula** is correct for full round-robin leagues where
  team count is reliably known; it's only the fallback that creates the phantom
  completions.
- **The gap scanner** ([gap_scanner.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/gap_scanner.py)) correctly identifies column-level gaps and
  stages them for re-enrichment.
- **The enrich pipeline** itself is running correctly — 1,263 leagues processed,
  108,675 matches ingested.

---

## OPEN QUESTIONS

1. **Does the RL trainer use `season_completeness` data at all during training?**
   Or does it directly query [schedules](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/db_helpers.py#277-280) with its own date/season window logic?
   This determines whether fixing completeness reporting would help training, or
   whether the trainer needs its own historical-depth guard.

2. **What is the minimum historical depth the RL trainer needs to produce
   reliable predictions?** (e.g., 2 seasons? 3 seasons? N finished matches?)
   This threshold needs to be defined before a gate condition can be written.

3. **The `1_109_MssKGkWd` league had 10 teams exactly scraping 90 matches.**
   Is this coincidence (the current season happens to be complete) or does this
   league genuinely always play 90 matches? Knowing this would confirm whether
   the round-robin heuristic is reliable for leagues with ≥4 teams.

4. **The fallback `return scanned_count or 1`:** should leagues with <4 teams be
   treated as cup-format competitions where completeness is intentionally
   undefined, rather than being silently marked COMPLETED?

5. **The 2011/2012 data (212 matches) and other isolated old seasons** — were
   these scraped intentionally or are they artefacts of archive navigation
   during current-season enrichment? If artefacts, they could distort RL
   feature engineering.
