# Project Stairway Safety Gate — Full Implementation Status Report

**Date:** 2026-03-17  
**Commits:** `68beaed` (safety gate), `5842eed` (await fix)  
**HEAD:** `5842eed` on `origin/main`

---

## 1. What Was Implemented

A centralized safety validation gate that enforces **all** Project Stairway v2 rules as hard constraints that **cannot be overridden** by model output, RL policy, or any other pipeline stage.

### Hard Rules Enforced

| Rule | Parameter | Value | Enforcement |
|------|-----------|-------|-------------|
| Single leg odds floor | `SINGLE_ODDS_MIN` | 1.20 | Rejects any leg below |
| Single leg odds ceiling | `SINGLE_ODDS_MAX` | 4.00 | Rejects any leg at or above |
| Accumulator total odds min | `ACCA_TOTAL_ODDS_MIN` | 3.50 | Rejects acca if total < 3.50 |
| Accumulator total odds max | `ACCA_TOTAL_ODDS_MAX` | 5.00 | Rejects acca if total > 5.00 |
| Max legs per accumulator | `ACCA_MAX_LEGS` | 4 | Truncates to top 4 by confidence |
| Minimum confidence per leg | `MIN_CONFIDENCE_PCT` | 70% | Rejects any leg below 70% |
| Fixed stake | `FIXED_STAKE` | ₦1,000 | Hard-locked; scales down only if balance < ₦10,000 |
| Selection priority | — | Confidence DESC | NOT Expected Value (EV) |

---

## 2. Files Created

### [NEW] [safety_gate.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/safety_gate.py)

Central safety module with 4 public functions:

| Function | Purpose |
|----------|---------|
| [is_stairway_safe(bet)](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/safety_gate.py#57-84) | Validates a single leg: odds range + min 70% confidence |
| [validate_accumulator(legs)](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/safety_gate.py#86-133) | Filters legs, sorts by confidence DESC, caps at 4, checks total odds |
| [get_stairway_stake(balance)](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/safety_gate.py#135-146) | Returns ₦1,000 fixed (or scaled if low balance) |
| [filter_and_rank_candidates(candidates)](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/safety_gate.py#148-170) | Entry point: filters + ranks all candidates by probability |

Also exports constants: `SINGLE_ODDS_MIN`, `SINGLE_ODDS_MAX`, `ACCA_TOTAL_ODDS_MIN`, `ACCA_TOTAL_ODDS_MAX`, `ACCA_MAX_LEGS`, `MIN_CONFIDENCE_PCT`, `FIXED_STAKE`.

### [NEW] [\_\_init\_\_.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/__init__.py)

Package init for `Core.Safety` module.

---

## 3. Files Modified

### [MODIFY] [placement.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/FootballCom/booker/placement.py)

| Change | Lines | Detail |
|--------|-------|--------|
| Import safety gate | L19–22 | Added [is_stairway_safe](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/safety_gate.py#57-84), [validate_accumulator](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/safety_gate.py#86-133), [get_stairway_stake](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/safety_gate.py#135-146), [filter_and_rank_candidates](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/safety_gate.py#148-170), `ACCA_MAX_LEGS` |
| Constants deferred | L199–207 | Old hardcoded constants replaced with re-exports from [safety_gate.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/safety_gate.py) (backward compat aliases) |
| Safety filter before accumulator | L269–277 | [filter_and_rank_candidates()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/safety_gate.py#148-170) runs before greedy loop; logs `STAIRWAY_SKIP` if all rejected |
| Max selections capped at 4 | L282 | Was `STAIRWAY_MAX_SELECTIONS = 8`, now `= 4` via `ACCA_MAX_LEGS` |
| Fixed stake | L329–332 | Replaced [StaircaseTracker().get_current_step_stake()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/System/guardrails.py#71-176) with [get_stairway_stake(current_balance)](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/safety_gate.py#135-146) — hard ₦1,000 |

**Console output added:**
- `[SAFETY REJECT] fixture=X reason=Y` for every rejected candidate
- `[STAIRWAY ACCEPT] fixture=X odds=Y conf=Z%` for every accepted candidate
- `[Stairway] No candidates passed safety gate.` when all rejected
- `[Stairway] Stake: ₦1,000 (fixed safety gate)` for stake confirmation

---

### [MODIFY] [betting_markets.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/betting_markets.py)

| Change | Lines | Detail |
|--------|-------|--------|
| Confidence threshold lowered | L240 | `>= 0.80` → `>= 0.70` to match Stairway 70% rule |
| 30-dim sort order | L333–335 | Changed from [(ev, prob)](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Scripts/fix_predictions_team_names.py#22-87) → [(prob, ev)](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Scripts/fix_predictions_team_names.py#22-87) — **probability-first, not EV** |

---

### [MODIFY] [market_space.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/rl/market_space.py)

| Change | Lines | Detail |
|--------|-------|--------|
| Min EV relaxed | L28 | `0.00` → `-0.10` — allows slightly negative EV if probability is very high (>80%) |
| Priority flag | L29 | Added `STAIRWAY_PRIORITY = "PROBABILITY"` as documentation constant |

---

### [MODIFY] [Leo.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Leo.py) + [pipeline.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/System/pipeline.py)

| Change | Detail |
|--------|--------|
| Restored `await` | [get_recommendations()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Scripts/recommend_bets.py#119-304) is wrapped by `@AIGOSuite.aigo_retry` which makes it a coroutine — must be awaited |

---

## 4. Architecture Diagram — Safety Gate Integration

```
  Candidates from match_odds DB
           │
           ▼
  ┌────────────────────────┐
  │ filter_and_rank_       │  ← Core/Safety/safety_gate.py
  │ candidates()           │
  │  • is_stairway_safe()  │  Per-leg: odds 1.20–4.00, conf ≥ 70%
  │  • Sort prob DESC      │  Confidence-first, not EV
  │  • Log ACCEPT/REJECT   │
  └──────────┬─────────────┘
             │ safe candidates only
             ▼
  ┌────────────────────────┐
  │ Greedy Accumulator     │  ← placement.py
  │  • Max 4 legs          │
  │  • Total odds ≤ 5.00   │
  │  • One per fixture     │
  └──────────┬─────────────┘
             │
             ▼
  ┌────────────────────────┐
  │ get_stairway_stake()   │  ← safety_gate.py
  │  • ₦1,000 fixed        │
  │  • Scale if balance    │
  │    < ₦10,000           │
  └──────────┬─────────────┘
             │
             ▼
        Place Bet
```

---

## 5. Verification Status

| Check | Status | Result |
|-------|--------|--------|
| `py_compile safety_gate.py` | ✅ | Clean |
| `py_compile placement.py` | ✅ | Clean |
| `py_compile betting_markets.py` | ✅ | Clean |
| `py_compile market_space.py` | ✅ | Clean |
| `py_compile Leo.py` | ✅ | Clean |
| `py_compile pipeline.py` | ✅ | Clean |
| `git push origin main` | ✅ | `68beaed` + `5842eed` |
| `Leo.py --recommend` dry run | ✅ | RuntimeWarning fixed by restoring `await` |
| Pyre2 lint errors | ⚠️ | All are **false positives** (Pyre can't resolve project-relative imports) |

---

## 6. What Was NOT Changed (By Design)

| Item | Reason |
|------|--------|
| [guardrails.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/System/guardrails.py) | Legacy kill switch / daily loss limits — still active, not replaced |
| [StaircaseTracker](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/System/guardrails.py#71-176) | Staircase step tracker in guardrails — bypassed in placement, not deleted (may be useful for tracking progress) |
| [rule_engine.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/rule_engine.py) | Prediction logic unchanged — safety gate filters AFTER predictions are made |
| [prediction_pipeline.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/prediction_pipeline.py) | No changes — predictions are generated before safety filtering |
| Kelly staking in [placement.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Scripts/quantify_misplacement.py) | `_calculate_kelly_stake()` still exists but is now dead code — [get_stairway_stake()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/safety_gate.py#135-146) overrides |

---

## 7. Remaining / Future Items

| Priority | Item | Status |
|----------|------|--------|
| P2 | Remove dead Kelly staking code from [placement.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Scripts/quantify_misplacement.py) | Not yet (low risk) |
| P2 | Add safety gate metrics to audit log (accept/reject counts) | Logged to console, not yet to DB |
| P3 | Unit tests for [safety_gate.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Safety/safety_gate.py) | Not yet |
| P3 | Integration test: run full Ch1 P3 with safety gate active | Pending next scheduled run |
