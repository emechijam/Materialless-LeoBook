# PROJECT STAIRWAY

**The Compounding Capital Strategy at the Heart of LeoBook**

> LeoBook Intelligence Framework · Materialless LLC · 2026
> Status: Active Development · Not yet publicly available

---

## 1. Why LeoBook Must Exist

Every day, across leagues on every continent, 100 to 500 football matches are played — and on weekends, that number climbs even higher. Each match is a data event: form, history, standings, odds, and momentum all collide into a predictable signal that most bettors never see clearly because they are looking at one or two matches at a time.

LeoBook was built on a different premise: what if a system could scan every match available on a given day, run each through a trained intelligence engine, and surface only those outcomes with genuine predictive confidence — then compound the returns from those selections systematically?

That premise is Project Stairway.

### The Core Conviction

- **Volume**: The sheer number of daily matches creates a rich selection environment. You do not need every match — you need the right ones.
- **Edge**: A prediction system with a true probabilistic edge over the bookmaker — even a modest one — generates long-run value when applied consistently.
- **Compounding**: Small, confident wins reinvested become exponential over a short series of steps.

---

## 2. The Stairway Structure

The staircase is a **7-step compounding sequence**, starting from a fixed base seed:

| Step | Stake | Odds Target | Payout | Cumulative Return |
|------|-------|-------------|--------|-------------------|
| 1 | ₦1,000 | ~4.0 | ₦4,000 | ₦4,000 |
| 2 | ₦4,000 | ~4.0 | ₦16,000 | ₦16,000 |
| 3 | ₦16,000 | ~4.0 | ₦64,000 | ₦64,000 |
| 4 | ₦64,000 | ~4.0 | ₦256,000 | ₦256,000 |
| 5 | ₦256,000 | ~4.0 | ₦1,024,000 | ₦1,024,000 |
| 6 | ₦1,024,000 | ~4.0 | ₦4,096,000 | ₦4,096,000 |
| 7 | ₦2,048,000 | ~4.0 | ₦2,187,000 (net) | ₦2,187,000 |

### Rules

1. **Start**: Every cycle begins with exactly ₦1,000.
2. **Win**: The full payout rolls into the next step's stake.
3. **Loss at any step**: The cycle resets to Step 1 with a fresh ₦1,000. Maximum loss per cycle: ₦1,000.
4. **Completion**: A full 7-step winning streak produces ~₦2,186,000 net profit from a ₦1,000 seed.

> **Implementation**: The staircase state machine is coded in `Core/System/guardrails.py` → `StaircaseTracker` class. State is persisted in the `stairway_state` SQLite table. Win → `advance()`, Loss → `reset()`. Current step, cycle count, and last result are tracked.
> Chapter/page execution (including Chapter 2 automated booking) is orchestrated via `Core/System/pipeline.py`. `Leo.py` is the entry point only.

---

## 3. The Mathematics — Honest and Complete

### 3.1 The Correct Framing of Accuracy

A common intuition in sports prediction is that selecting a small number of matches from a large pool somehow transfers the pool's aggregate accuracy to the selection. This is mathematically incorrect and must be stated clearly.

**The Correct Statement**: LeoBook scans 100–500 matches daily and surfaces only those where the prediction model's estimated true probability significantly exceeds the bookmaker's implied probability. The accuracy that matters is not the pool's aggregate accuracy — it is the **per-step win probability** of the specific bets LeoBook selects.

If a bookmaker prices a match at 4.0 odds, they imply a 25% win probability. If LeoBook's model estimates the true probability at 38%, that 13-percentage-point gap is the edge. That edge — consistently identified and consistently positive — is what drives long-run value.

### 3.2 Theoretical Win-Streak Probabilities

| Per-Step Win Prob. (p) | 7-Win Streak Prob. | Classification | Context |
|--|--|--|--|
| 25% (fair odds, no edge) | ~0.006% | Baseline / No Edge | Bookmaker's implied probability at 4.0 |
| 28% | ~0.028% | Marginal Edge | Slight model advantage |
| 32% | ~0.039% | Good Edge | Solid prediction system |
| 35% | ~0.064% | Strong Edge | Well-calibrated model |
| 40% | ~0.164% | Excellent Edge | High-performing system |
| 45% | ~0.373% | Exceptional Edge | World-class calibration |

### 3.3 Variance — The Honest Reality

- **Cycles will fail more often than they succeed.** This is expected and is not a signal of system failure.
- **The system's value is realised over many cycles** — the expected return across N cycles is what matters, not any single cycle.
- **The ₦1,000 reset is not a punishment — it is a feature.** It caps every cycle's loss and keeps the system running.
- **Patience and volume are structural requirements** of the strategy, not optional virtues.

### The Asymmetry That Drives the Vision

- **Worst case per cycle**: ₦1,000 lost. Cycle resets.
- **Best case per cycle**: ₦2,186,000 net profit from a ₦1,000 seed.
- **The ratio**: 2,186:1 return-to-risk per completed staircase.
- **The thesis**: The more matches LeoBook can scan, and the stronger the model's edge, the more often a cycle completes — and the ratio never changes.

---

## 4. Scale — Why Sports Plurality Matters

Football is the starting point, not the ceiling. The principle underlying Project Stairway is not football-specific — it is a function of match volume and prediction edge. Every sport that can be modelled, predicted, and placed on Football.com (or equivalent platforms) is a candidate for the staircase.

More sports means:
- More daily matches to scan for high-confidence selections.
- More diverse statistical environments for the model to learn from.
- More opportunities for the cycle to find its 7-step winning run.
- Reduced dependency on any single league, season, or sport's form patterns.

The long-term architecture of LeoBook is designed with this plurality in mind. The RL model's SharedTrunk + LoRA adapter design allows sport-specific and league-specific fine-tuning without rebuilding the core intelligence.

> **The Vision in One Sentence**: A system that sees every match, identifies every edge, and compounds every win — at scale, across sports, starting from ₦1,000.

---

## 5. Open Quests — What Pipeline Testing Will Reveal

LeoBook is in active development. The following are not gaps or weaknesses — they are the questions the system is being built to answer. When the data is available, this section will be updated with measured results.

1. What is LeoBook's actual per-step win probability on its selected bets at ~4.0 odds?
2. How does per-step win probability vary by league, sport, and season stage?
3. Is the optimal step target a single match at 4.0, or a 2–3 match accumulator that multiplies to 4.0?
4. What is the empirically observed calibration of the model?
5. What is the expected number of cycles before a full 7-step staircase completes?
6. How does the staircase perform when applied simultaneously across multiple sports?
7. What is the optimal confidence threshold gate for bet placement?
8. At what per-step win rate does Project Stairway become net-positive over 100 cycles?

These questions will be answered by data, not assumption.

---

## 6. Phase 1 Infrastructure — Temporary Design Disclaimer

> **This section exists because the current implementation is intentionally temporary.
> Understanding its constraints prevents false confidence in the architecture.**

### 6.1 What Phase 1 Is

Phase 1 of Project Stairway uses **Football.com** as its sole betting interface. This means:

- **Bet placement is browser-automated**: `Chapter2Worker` → `run_automated_booking()` navigates Football.com via Playwright, finds the correct match, selects the outcome, and places a stake through the UI.
- **Odds are harvested from Football.com**: The `run_odds_harvesting()` pipeline extracts live odds from Football.com match pages and stores them in `match_odds` (SQLite + Supabase).
- **Booking codes are scraped**: `harvest_booking_codes_for_recommendations()` navigates each recommended match's Football.com page to capture the share/booking code.

### 6.2 Why Phase 1 Is Temporary

Browser automation against a bookmaker UI is fragile by nature:

| Risk | Impact | Mitigation (Phase 1) |
|---|---|---|
| UI change / DOM update | Selectors break silently | `SelectorManager` centralises selectors; alerts on 0-outcome extracts |
| Session expiry / login prompt | Booking session fails | `load_or_create_session()` with retry; `is_streamer_alive()` watchdog |
| Rate limiting / CAPTCHA | Harvesting blocked | Semaphore-bounded concurrency (`MAX_CONCURRENCY`), per-page delays |
| Football.com ToS compliance | Account suspension | Single-user personal use; no commercial scraping |
| Odds latency | Stale odds at placement | `IMMINENT_MATCH_CUTOFF_HOURS` filter removes matches too close to kick-off |

**Football.com is used because it is accessible, scrape-friendly for personal use, and has a share-code mechanism that enables booking without exposing credentials in code. It is not the final destination.**

### 6.3 What Phase 1 Does Not Have

- No programmatic API access to odds or bet placement
- No bid/ask spread analysis (exchange-style)
- No live in-play betting
- No multi-bookmaker odds comparison
- No matched betting / arbitrage infrastructure

These capabilities require an exchange integration, which is the Phase 2 objective.

---

## 7. Phase 2 — Betfair & Smarkets Migration Plan

> **Goal**: Replace Football.com browser automation with a programmatic betting exchange
> integration that gives LeoBook real-time odds access, sub-second bet placement, and
> liquidity-aware stake sizing.

### 7.1 Why Betting Exchanges

Betting exchanges (Betfair, Smarkets) differ fundamentally from bookmakers:

| Feature | Bookmaker (Phase 1) | Exchange (Phase 2) |
|---|---|---|
| Odds source | Fixed by bookmaker | Market-driven, real-time |
| Bet placement | UI automation | REST API (`PlaceBets`) |
| Margin | 3–10% bookmaker overround | 2% commission on winnings only |
| Liquidity | Guaranteed (up to limit) | Depends on matched volume |
| In-play | Limited | Full real-time |
| Data access | Scraping required | Official streaming API |

For a system built on mathematical edge, the reduction in margin from ~8% bookmaker overround to ~2% exchange commission is not cosmetic — it is the difference between a borderline edge and a profitable one at scale.

### 7.2 Target Platforms

**Primary: Betfair Exchange**
- REST API: `api.betfair.com/exchange/betting/`
- Endpoints: `listMarketCatalogue`, `listMarketBook`, `placeOrders`, `listCurrentOrders`
- Authentication: App key + session token (login via API)
- Data: Soccer exchange markets available for most top-tier leagues globally
- Commission: 2% standard; reduced rate for high-volume accounts

**Secondary: Smarkets**
- REST API: `api.smarkets.com/v3/`
- Lighter regulatory overhead; better odds on select markets
- Useful as a fallback / arbitrage comparison source

### 7.3 Migration Architecture

The Phase 2 migration is designed to be **additive, not destructive**. The Phase 1 pipeline continues to run for leagues or matches where no exchange market exists.

```
Phase 1 (current)                Phase 2 (target)
──────────────────               ─────────────────────────────────
fs_live_streamer      ──────►  (unchanged — outcome tracking)
run_predictions       ──────►  (unchanged — model inference)
get_recommendations   ──────►  (unchanged — stairway selection)
                     │
run_odds_harvesting   ──X──►  ExchangeOddsHarvester
  (Football.com)                  - betfair_client.list_market_book()
                                  - Stores in match_odds with source='betfair'

run_automated_booking ──X──►  ExchangeBookingAgent
  (Football.com UI)               - betfair_client.place_orders()
                                  - StaircaseTracker.get_current_step_stake()
                                  - Kelly-scaled lay/back sizing
```

**New modules (Phase 2):**

| Module | Responsibility |
|---|---|
| `Modules/Exchange/betfair_client.py` | Auth, session keep-alive, `list_market_book()`, `place_orders()` |
| `Modules/Exchange/smarkets_client.py` | Smarkets REST client (secondary) |
| `Modules/Exchange/exchange_odds_harvester.py` | Replaces `run_odds_harvesting()` for mapped markets |
| `Modules/Exchange/exchange_booking_agent.py` | Replaces `run_automated_booking()` for exchange bets |
| `Core/Safety/exchange_guardrails.py` | Liquidity checks, minimum matched volume gate |

**Unchanged in Phase 2:**
- `fs_live_streamer.py` — outcome tracking is independent of where bets are placed
- `run_predictions()` — model inference is platform-agnostic
- `StaircaseTracker` — step/cycle/stake logic is unchanged
- Supabase schema — `match_odds.source` column distinguishes `'football.com'` vs `'betfair'`

### 7.4 Betfair-Specific Stairway Adjustments

The staircase structure is unchanged. The following Phase 1 constraints are lifted:

1. **Odds precision**: Exchange odds are decimal with 2dp — no rounding required.
2. **Stake floor**: Betfair minimum stake is £2.00. The ₦1,000 base seed must be maintained in NGN; exchange deposits will require SWIFT/IBAN FX conversion.
3. **Back/Lay option**: The exchange enables **laying** (betting against an outcome). The staircase remains a back-bet strategy; laying is reserved for hedging late in a cycle.
4. **Liquidity gate**: A minimum available-to-match volume threshold must be configured in `exchange_guardrails.py`. No bet is placed if available liquidity < 5× stake.
5. **In-play gate**: Exchange markets suspend briefly around kick-off. The `IMMINENT_MATCH_CUTOFF_HOURS` filter remains in place.

### 7.5 Trigger Conditions for Phase 2 Activation

Phase 2 migration is triggered when **all three** of the following conditions are met:

1. **Edge confirmation**: First full end-to-end pipeline test completes. Measured per-step win rate ≥ 32% across ≥ 50 placed selections.
2. **Regulatory clearance**: Betfair account verified, API key issued, and test sandbox bets confirmed end-to-end.
3. **Capital threshold**: Stairway capital allocated for Phase 2 testing is ring-fenced (separate from Phase 1 Football.com operational capital).

Until all three conditions are met, Football.com Phase 1 continues as the live system.

---

## 8. What Project Stairway Is Not

- **Not a guaranteed profit system.** No betting system can guarantee profit. The staircase is designed to extract value from a genuine prediction edge — without that edge, the math does not work in the long run.
- **Not a commercial product.** Project Stairway operates within the context of Football.com's platform (Phase 1) and its terms of service. This is a personal capital management strategy, not a service offered to third parties.
- **Not a claim of 95% accuracy.** No per-match or per-combo accuracy claim is made in this document. The system's accuracy is an open quest.
- **Not reckless.** The ₦1,000 base seed, the hard reset on loss, the confidence threshold gate, the audit logging, the dry-run testing mode — these are deliberate engineering decisions that treat capital preservation as seriously as capital growth.
- **Not a finished product (Phase 1).** The Football.com browser automation layer is temporary infrastructure. It is used because it works *now*. It will be replaced by an exchange API when edge is confirmed and regulatory conditions are met.

---

## 9. The Mission

> What is the probability that, out of 100–500 thoroughly analysed matches,
> a system can find 7 predictions in a row that are right?
> And what happens to ₦1,000 if it can?

The mathematical answer is: rare, but non-zero — and the rarity is precisely what makes the 2,186:1 return-to-risk ratio possible. The engineering answer is: build the best prediction system available, give it the richest data, train it on history, gate it on confidence, and run the staircase with discipline.

That is what LeoBook is. That is why it must exist.

If it fails — learn, improve, and move forward. If it succeeds — the outcome is life-changing. The risk is ₦1,000. The quest is everything beyond it.

---

**Document Status**
- Version: 1.5 — Schema version: v9.6 (2026-04-03)
- System Status: Active Development — v9.6 stable · Basketball modules added · IDataProvider interface complete
- Staircase State Machine: ✅ Implemented in `Core/System/guardrails.py`
- Chapter Execution: ✅ `Core/System/pipeline.py` (extracted from `Leo.py` in v9.1)
- Agentic Chapter Sequencing: ✅ `Core/System/supervisor.py` — time-of-day + prior-run gates
- Season-Aware RL: ✅ `data_richness_score` per league — scales RL weight with historical depth
- Phase 1 Infrastructure: ✅ Football.com browser automation (temporary, see §6)
- Phase 2 Plan: ✅ Betfair/Smarkets exchange migration documented (see §7)
- Subscription Tiers: ✅ Paystack (₦48,500/mo) + Stripe ($45/mo) implemented
- ML Filter Config: ✅ `user_rl_config` table + `RlConfigService` (Flutter ↔ Supabase)
- Performance Data: Pending — Full Pipeline Testing
- Next Update: Upon completion of first full end-to-end pipeline test
- Classification: Internal Development Document — Not for public distribution
