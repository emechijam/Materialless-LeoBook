# FastAPI Backend Feasibility Report — LeoBook v9.3

## Executive Summary

LeoBook currently operates as a **script-driven system** where Python (Leo.py) pushes data to Supabase and the Flutter app reads from Supabase directly via anon key. There is **no central API layer**. Adding FastAPI is feasible and beneficial, but must be done surgically to avoid breaking the working orchestrator.

**Recommendation: Option C (Hybrid)** — FastAPI serves Flutter-facing endpoints while Leo.py retains internal orchestration. This is the lowest-risk, highest-value path.

Estimated effort: **~3–5 days for MVP**, zero disruption to current pipeline.

---

## Current Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Leo.py (Orchestrator)             │
│  Prologue → Chapter 1 → Chapter 2 (async pages)    │
│  - Enrichment, Predictions, Booking, Review         │
├─────────┬───────────────┬───────────────────────────┤
│ SQLite  │ sync_manager  │  supabase_client.py       │
│ (local) │ (watermarks)  │  (SERVICE_KEY — admin)    │
│         │  push/pull    │                           │
└────┬────┴───────┬───────┴───────────────────────────┘
     │            │
     │     ┌──────▼──────┐
     │     │  Supabase   │  ← Tables: predictions, schedules,
     │     │  (Postgres)  │    standings, teams, leagues, live_scores
     │     └──────┬──────┘
     │            │
     │     ┌──────▼──────┐
     │     │ Flutter App │  ← Uses ANON_KEY (public)
     │     │ leobookapp/ │  ← Direct Supabase queries
     │     │ data_repo   │  ← Realtime broadcast channels
     │     └─────────────┘
```

**Key observations:**
- Flutter uses `SUPABASE_ANON_KEY` (public) → queries 6 tables directly
- Python uses `SUPABASE_SERVICE_KEY` (admin) → bypasses RLS
- No authentication layer between Flutter and data — anyone with the anon key can read everything
- No rate limiting, no input validation, no custom business logic on the read path
- Realtime uses Supabase broadcast (works but limited to table-level events)

---

## Proposed Architecture (Option C — Hybrid)

```
┌─────────────────────────────────────────────────────┐
│                    Leo.py (Orchestrator)             │
│  Unchanged: Enrichment, Predictions, Booking        │
│  Still pushes to Supabase via SERVICE_KEY            │
├─────────┬───────────────┬───────────────────────────┤
│ SQLite  │ sync_manager  │  supabase_client.py       │
└────┬────┴───────┬───────┴───────────────────────────┘
     │            │
     │     ┌──────▼──────┐
     │     │  Supabase   │
     │     └──────┬──────┘
     │            │
     │     ┌──────▼──────────────┐
     │     │   FastAPI Server    │  ← NEW: api/ folder
     │     │   - /predictions    │  ← Cached, paginated
     │     │   - /recommendations│  ← Safety-gated
     │     │   - /standings      │  ← League-scoped
     │     │   - /stairway/bets  │  ← Stairway state
     │     │   - /ws/live        │  ← WebSocket stream
     │     │   - /auth/google    │  ← JWT validation
     │     └──────┬──────────────┘
     │            │
     │     ┌──────▼──────┐
     │     │ Flutter App │  ← Talks to FastAPI (not Supabase)
     │     │ No anon key │  ← JWT auth per request
     │     └─────────────┘
```

---

## Benefits Table

| Area | Benefit | Impact |
|------|---------|--------|
| **Security** | Anon key no longer exposed in Flutter app | 🔴 Critical |
| **Security** | JWT auth per request — row-level access control | 🔴 Critical |
| **Security** | Service key stays server-side only | 🔴 Critical |
| **Performance** | Server-side caching (Redis/in-memory) for predictions | 🟡 High |
| **Performance** | Pagination + filtered queries (not `.limit(2000)`) | 🟡 High |
| **Flutter UX** | Custom endpoints: `/recommendations`, `/stairway/bets` | 🟢 Medium |
| **Flutter UX** | Typed error responses instead of raw Supabase errors | 🟢 Medium |
| **Flutter UX** | WebSocket for live scores (lower latency than broadcast) | 🟡 High |
| **Safety** | Safety gate runs server-side — can't be bypassed | 🔴 Critical |
| **Safety** | Rate limiting prevents abuse | 🟢 Medium |
| **Stairway** | `/stairway/status` endpoint with balance, step, history | 🟢 Medium |
| **Ops** | Health endpoint (`/health`) for monitoring | 🟢 Medium |
| **Ops** | Structured logging + request tracing | 🟢 Medium |

---

## Trade-offs Table

| Factor | Risk | Assessment |
|--------|------|------------|
| **Migration effort** | Low–Medium | Option C reuses 100% of existing Leo.py; FastAPI is additive |
| **Hosting** | New infra needed | Railway / Fly.io / VPS — ~$5–10/mo for MVP |
| **Latency** | Extra hop (Flutter → FastAPI → Supabase) | Mitigated by caching; net effect is typically **faster** |
| **Supabase Realtime** | Must proxy or replace | WebSocket on FastAPI replaces broadcast; cleaner |
| **Maintenance** | One more service to deploy | Minimal — FastAPI is a single `uvicorn` process |
| **RLS changes** | Flutter stops using RLS directly | Simpler: lock down Supabase to service key only |
| **Leo.py disruption** | Zero | Leo.py keeps pushing via sync_manager unchanged |
| **Auth migration** | Low | Current Google Sign-In flow stays; FastAPI validates the Supabase JWT |

---

## Three Options Compared

| | Option A: Thin Wrapper | Option B: Full Migration | Option C: Hybrid (Recommended) |
|---|---|---|---|
| **Scope** | Wrap Leo.py functions as endpoints | Move all logic into FastAPI app | FastAPI for Flutter; Leo.py for jobs |
| **Effort** | 1–2 days | 2–4 weeks | 3–5 days |
| **Risk** | Low but limited value | High — rewrite risk | Low |
| **Leo.py** | Remains primary | Deprecated | Remains primary for orchestration |
| **Value** | Endpoints exist but no auth/caching | Maximum long-term | Maximum short-term |
| **Verdict** | Too thin — doesn't solve security | Too ambitious right now | ✅ **Best balance** |

---

## Recommended Option: C (Hybrid)

### MVP Scope — First 5 Endpoints

| Priority | Endpoint | Method | Source Table | Notes |
|----------|----------|--------|-------------|-------|
| P0 | `GET /predictions` | GET | predictions | Pagination, date filter, cached |
| P0 | `GET /recommendations` | GET | predictions | `recommendation_score > 0`, safety-gated |
| P0 | `GET /standings/{league}` | GET | standings | With team crests joined |
| P1 | `GET /leagues` | GET | leagues | Cached |
| P1 | `WS /ws/live` | WebSocket | live_scores | Push on change |

### Suggested Folder Structure

```
LeoBook/
├── api/                          # NEW — FastAPI app
│   ├── __init__.py
│   ├── main.py                   # FastAPI app factory, CORS, lifespan
│   ├── config.py                 # Settings (Supabase URL, keys, JWT secret)
│   ├── auth/
│   │   ├── __init__.py
│   │   └── jwt_handler.py        # Validate Supabase JWT from Flutter
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── predictions.py        # /predictions, /recommendations
│   │   ├── standings.py          # /standings/{league}
│   │   ├── leagues.py            # /leagues
│   │   ├── stairway.py           # /stairway/status, /stairway/bets
│   │   └── websocket.py          # /ws/live
│   ├── services/
│   │   ├── __init__.py
│   │   ├── prediction_service.py # Query Supabase + cache
│   │   ├── standings_service.py
│   │   └── live_service.py       # WebSocket manager
│   └── middleware/
│       ├── __init__.py
│       └── rate_limiter.py
├── Leo.py                        # UNCHANGED
├── Core/                         # UNCHANGED
├── Data/                         # UNCHANGED
└── Modules/                      # UNCHANGED
```

### Auth Strategy

1. Flutter keeps Google Sign-In → Supabase Auth (unchanged)
2. Supabase issues a JWT on sign-in (already happens)
3. Flutter sends `Authorization: Bearer <supabase_jwt>` to FastAPI
4. FastAPI validates JWT using Supabase's public JWT secret (`SUPABASE_JWT_SECRET`)
5. No new auth system needed — reuse existing Supabase auth

### Leo.py Coexistence

- Leo.py continues to run as a scheduled process (cron / supervisor)
- Leo.py pushes data to Supabase via `sync_manager` (unchanged)
- FastAPI reads from the same Supabase tables (read-only for MVP)
- No shared state between Leo.py and FastAPI — both talk to Supabase independently
- Eventually: Leo.py could POST to FastAPI endpoints to trigger jobs (Phase 2)

### Supabase RLS Changes

| Current | After FastAPI |
|---------|--------------|
| Anon key has SELECT on all tables | Anon key: **revoke all** (or restrict to auth-only) |
| Service key used by Python | Service key used by Python AND FastAPI |
| RLS policies for Flutter reads | RLS not needed — FastAPI handles auth |

---

## Next Concrete Step (If Approved)

1. `pip install fastapi uvicorn python-jose` in the LeoBook venv
2. Create `api/main.py` with a single `/health` endpoint
3. Add `GET /predictions` with Supabase query + in-memory cache
4. Test from Flutter by changing one [data_repository.dart](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/leobookapp/lib/data/repositories/data_repository.dart) method to hit FastAPI
5. If it works, expand to all 5 MVP endpoints

**No Flutter changes needed for testing** — can test FastAPI independently via browser/curl first.

> [!IMPORTANT]
> The single biggest win is **removing the anon key from the Flutter app**. Right now, anyone who decompiles the APK can read your entire Supabase database. FastAPI with JWT auth closes this hole immediately.
