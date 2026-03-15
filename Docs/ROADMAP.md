# LeoBook ROADMAP

> **Version**: 1.0 · **Date**: 2026-03-15  
> Authored by: LeoBook Engineering Team — Materialless LLC  
> This is a living document. Update it when milestones shift.

---

## Architecture Principles (Non-Negotiable)

These constraints govern every milestone below:

1. **Data flows through SQLite first** — all pipelines write locally, then sync to Supabase.
2. **WAT everywhere** — all timestamps in `Africa/Lagos` (UTC+1) via `now_ng()`.
3. **≤500 lines per file** — split before you exceed the limit.
4. **Selectors live in `knowledge.json`** — zero hardcoded CSS selectors.
5. **Reuse before you build** — search for existing helpers first (§2.16).

---

## Current State (v9.2, March 2026)

| Area | Status |
|------|--------|
| Football – Flashscore enrichment | ✅ Fully modularised (4 sub-modules) |
| Football – Flashscore live streamer | ✅ Live |
| Football – Football.com odds + booking | ✅ Live |
| Prediction pipeline (Stairway Engine) | ✅ Live (Rule Engine + Poisson RL) |
| Bet safety guardrails (Tier 1) | ✅ All 6 live |
| Data sync (SQLite → Supabase) | ✅ Push-only watermark sync |
| Asset pipeline (crests, flags) | ✅ Live |
| Flutter app | 🔄 In progress |

---

## Milestone 1 — Multi-Source Odds + Basketball

**Target: Q2 2026**

### 1.1 Basketball Data Layer
- [ ] Build `Modules/Basketball/` parallel to `Modules/Flashscore/`
- [ ] NBA + EuroLeague league seeds in `Data/Store/leagues_basketball.json`
- [ ] Schedule enrichment via Flashscore `/basketball/` URLs
- [ ] Extend `schedules` table with `sport` column (default `football`)
- [ ] Market space mapping for basketball (1X2, OU, handicap — research needed)

### 1.2 Multi-Bookmaker Odds
- [ ] Abstract `OddsProvider` interface in `Modules/`
- [ ] Add Bet9ja parser alongside existing Football.com harvester
- [ ] Odds normalisation layer: convert fractional/decimal → implied probability
- [ ] Arbitrage detector: alert when same market has >3% EV across books

### 1.3 RL Market Expansion
- [ ] Extend `market_space.py` with basketball markets
- [ ] Phase 2 RL training run with multi-sport data
- [ ] Separate ensemble weights (`ensemble_weights_basketball.json`)

---

## Milestone 2 — API-First Data Layer

**Target: Q3 2026**

### 2.1 Replace Playwright Scraping (where possible)
- [ ] Evaluate Flashscore unofficial API vs scraping cost
- [ ] If available: `Modules/Flashscore/fs_api_client.py` using requests
- [ ] Fallback: keep Playwright for pages with no API equivalent
- [ ] Rate-limit controller: `Core/System/rate_limiter.py` (token bucket)

### 2.2 Supabase Edge Functions
- [ ] Move `propagate_crest_urls()` to a Supabase Edge Function (triggered on insert)
- [ ] Move `fill_all_country_codes()` to a Supabase Edge Function
- [ ] Remove these from enrichment critical path → 20% faster enrichment runs

### 2.3 Webhooks / Push Notifications
- [ ] Supabase Realtime → Flutter push for live score updates
- [ ] Remove polling in Flutter `LiveScoreNotifier`; subscribe to Realtime channel

---

## Milestone 3 — Production Hardening

**Target: Q4 2026**

### 3.1 Monitoring & Alerting
- [ ] `Core/System/health_monitor.py` — heartbeat to Supabase every 15 min
- [ ] Telegram/WhatsApp alert on: pipeline failure, gap scan > 500 critical, daily loss limit hit
- [ ] Dashboard: Supabase Metabase or custom Flutter admin screen

### 3.2 Multi-Instance Support
- [ ] Distribute enrichment across 2–3 VPS instances via range locks (`--limit START-END`)
- [ ] Shared watermark in Supabase (not local SQLite) for multi-node sync
- [ ] Conflict resolution: last-write-wins on `updated_at` timestamp

### 3.3 Model Versioning
- [ ] Tag model checkpoints with `YYYYMMDD-phase{N}` naming
- [ ] Auto-rollback if new model accuracy drops >5% vs previous checkpoint
- [ ] `Data/Access/model_sync.py` — already exists; extend with versioning

---

## Sports Priority Order

| Priority | Sport | Source | Status |
|----------|-------|--------|--------|
| 1 | Football | Flashscore + Football.com | ✅ Live |
| 2 | Basketball | Flashscore (NBA, EuroLeague) | Planned M1 |
| 3 | Tennis | Flashscore | Deferred |
| 4 | Cricket | Flashscore | Deferred |

---

## Bookmaker Priority Order

| Priority | Bookmaker | Market | Status |
|----------|-----------|--------|--------|
| 1 | Football.com | All markets | ✅ Live |
| 2 | Bet9ja | 1X2, OU, DC | Planned M1 |
| 3 | SportyBet | 1X2 | Deferred |

---

## Open Technical Questions

| Question | Owner | Deadline |
|----------|-------|----------|
| Does Flashscore have an unofficial JSON API we can use instead of Playwright? | Engineering | M2 |
| Basketball market space mapping — which OU lines are liquid on Bet9ja? | Research | M1 |
| What is the minimum data_richness_score to enable RL weights for basketball? | ML | M1 |
| Can Supabase Realtime handle 50+ concurrent Flutter clients without overload? | Infra | M3 |

---

*Last updated: 2026-03-15 (v1.0 — initial roadmap)*
