# LeoBook

**Developer**: Materialless LLC
**Chief Engineer**: Emenike Chinenye James
**Powered by**: Rule Engine + Neural RL Stairway Engine
**Architecture**: v9.6.2 "Stairway Engine" (All files ≤500 lines · Fully Modular · Season-Aware RL Weighting · Data Contract)
**App Version**: 9.6.2 ([pubspec.yaml](leobookapp/pubspec.yaml) aligned with `LEOBOOK_VERSION` in `Core/Utils/constants.py` and [app_version.dart](leobookapp/lib/core/constants/app_version.dart))

---

## What Is LeoBook?

LeoBook is an **autonomous sports prediction and betting system** with two halves:

| Component     | Tech                               | Purpose                                                                                                                              |
| ------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `Leo.py`      | Python 3.12 + Playwright + PyTorch | Autonomous data extraction, **Rule Engine + Neural RL prediction** (no LLM), odds harvesting, automated bet placement, and dynamic task scheduling |
| `leobookapp/` | Flutter/Dart                       | Cross-platform dashboard with "Telegram-grade" UI density, Liquid Glass aesthetics, and real-time streaming                          |

**Leo.py** is an **autonomous orchestrator** powered by a **Supervisor-Worker Pattern** (`Core/System/supervisor.py`). Chapter/page execution functions live in `Core/System/pipeline.py`. The system enforces **Data Readiness Gates** (Prologue P1-P3) with **materialized readiness cache** for O(1) checks. **Chapter 1 Hardening (v9.5.7)** introduces **All-or-Nothing Transactions** with a **Strict Data Contract** — ensuring either a full league enrichment passes validation or zero data is persisted. Intelligence outputs now serialize **Rich Rationale** (Form, H2H, Standings) as structured JSON for transparency.

For the complete file inventory and step-by-step execution trace, see [docs/LeoBook_Technical_Master_Report.md](docs/LeoBook_Technical_Master_Report.md).

---

## System Architecture (v9.5 — Fully Modular · Streamer Independent)

```
Leo.py (Entry Point — 473 lines)
├── Core/System/pipeline.py (Chapter/Page execution functions)
│   ├── Startup: Push-Only Sync → Supabase (auto-bootstrap)
│   ├── Prologue (Materialized Readiness Gates):
│   │   ├── P1: Quantity & ID Gate (O(1) lookup)
│   │   ├── P2: History & Quality Gate — Job A (blocks) + Job B (RL tier)
│   │   └── P3: AI Readiness Gate (O(1) lookup)
│   ├── Chapter 1 (Data Hardening v9.5.7):
│   │   ├── Ch1 P1: URL Resolution & Direct Odds Harvesting
│   │   ├── Ch1 P2: Hardened Predictions (Strict Data Contract + Rich Rationale)
│   │   └── Ch1 P3: Recommendations & Final Chapter Sync (Odds 1.20–4.00)
│   └── Chapter 2 (Betting Automation):
│       ├── Ch2 P1: Automated Booking
│       └── Ch2 P2: Funds & Withdrawal Check
└── Live Streamer: **Independent OS process** — spawned with **Watchdog**
                   Automatically monitored and respawned by Supervisor if dead/stale.
                   Manual stopping: kill using CLI or process manager.
```

### Key Subsystems

- **Autonomous Task Scheduler**: Manages recurring tasks (Weekly enrichment, Monday 2:26am) and time-sensitive predictions (day-before match).
- **Data Readiness Gates**: Automated pre-flight checks with **Auto-Remediation** (30-minute timeout). P2 now has two jobs: Job A (internal consistency gate) + Job B (RL tier reporting: RULE_ENGINE / PARTIAL / FULL).
- **Season Completeness**: `CUP_FORMAT` status eliminates phantom COMPLETED seasons from cup finals/super cups. `data_richness_score` per league measures prior season depth.
- **Season-Aware RL Weighting**: `data_richness_score` [0.0, 1.0] scales `W_neural` dynamically. 0 prior seasons → `W_neural = 0.0` (pure Rule Engine). 3+ seasons → `W_neural = 0.3` (full configured weight). Score cached for 6h.
- **Standings VIEW**: High-performance standings computed directly from `schedules` via Postgres UNION ALL views. Zero storage, always fresh.
- **Batch Resume Checkpoint**: `fb_manager.py` saves `Data/Logs/batch_checkpoint.json` after each league batch. Restart skips already-completed batches.
- **Supabase Upsert Limits**: `predictions` capped at 200 rows/call (prevents 57014 timeout). `paper_trades.league_id` is `TEXT` (Flashscore IDs are strings — not integers).
- **Neural RL Engine** (`Core/Intelligence/rl/`): v9.1 "Stairway Engine" using a **30-dimensional action space** and **Poisson-grounded imitation learning**. 3-phase PPO training split across `trainer.py`, `trainer_phases.py`, `trainer_io.py`.

### Core Modules

- **`Core/Intelligence/`** — AI engine (rule-based prediction, **neural RL engine**, adaptive learning, AIGO self-healing)
- **`Core/System/`** — **Task Scheduler**, **Data Readiness Checker**, **Bet Safety Guardrails**, lifecycle, withdrawal
- **`Modules/Flashscore/`** — Schedule extraction (`fs_league_enricher.py`), live score streaming, match data processing
- **`Modules/FootballCom/`** — Betting platform automation (login, odds, booking, withdrawal, sequential extraction)
- **`Modules/Assets/`** — Asset sync: team crests, league crests, region flags (171 SVGs, 1,234 leagues)
- **`Data/Access/`** — **Computed Standings**, Supabase sync, season completeness, outcome review
- **`Scripts/`** — Shims + CLI tools (recommendation engine, RL diagnostics)
- **`leobookapp/`** — Flutter dashboard (DM Sans typography · UI Inspiration palette · Recommendation filters · Live countdown)

---

## Supported Betting Markets

1X2 · Double Chance · Draw No Bet · BTTS · Over/Under · Goal Ranges · Correct Score · Clean Sheet · Asian Handicap · Combo Bets · Team O/U

---

## Project Structure

```
LeoBook/
├── Leo.py                     # Entry point (473 lines)
├── Core/
│   ├── System/
│   │   ├── pipeline.py        # Chapter/page execution functions
│   │   ├── supervisor.py
│   │   ├── guardrails.py
│   │   ├── scheduler.py
│   │   ├── data_readiness.py  # P2 reports RL tier (v9.1)
│   │   ├── data_quality.py
│   │   ├── gap_resolver.py
│   │   └── withdrawal_checker.py
│   ├── Intelligence/
│   │   ├── prediction_pipeline.py
│   │   ├── ensemble.py        # data_richness_score RL weighting (v9.1)
│   │   ├── rule_engine.py
│   │   ├── rule_engine_manager.py
│   │   └── rl/
│   │       ├── trainer.py         # façade — RLTrainer core + mixin inheritance
│   │       ├── trainer_phases.py  # Phase 1/2/3 reward functions (mixin)
│   │       ├── trainer_io.py      # save/load/checkpoint (mixin)
│   │       ├── trainer_context.py # build_fixture_context()
│   │       ├── trainer_seasons.py # SeasonsMixin — season discovery & date selection
│   │       ├── feature_encoder.py
│   │       └── market_space.py
│   └── Utils/
│       └── constants.py
├── Modules/
│   ├── Flashscore/
│   │   ├── fs_league_enricher.py
│   │   ├── fs_league_extractor.py
│   │   ├── fs_league_hydration.py
│   │   ├── fs_league_images.py
│   │   ├── fs_live_streamer.py     # Independent process (subprocess.Popen)
│   │   └── fs_extractor.py
│   ├── FootballCom/
│   │   ├── fb_manager.py           # façade — batch resume checkpoint
│   │   ├── fb_workers.py           # _odds_worker(), _league_worker()
│   │   ├── fb_phase0.py            # Phase 0 calendar fixture discovery
│   │   ├── match_resolver.py       # FixtureResolver — Deterministic SQL matcher
│   │   ├── navigator.py
│   │   ├── odds_extractor.py
│   │   └── booker/
│   │       ├── placement.py
│   │       └── booking_code.py
├── Data/
│   ├── Access/
│   │   ├── league_db.py            # façade — re-exports all entity CRUD
│   │   ├── league_db_schema.py     # DDL, migrations, get_connection()
│   │   ├── league_db_leagues.py    # league CRUD
│   │   ├── league_db_teams.py      # team CRUD
│   │   ├── league_db_fixtures.py   # fixture CRUD
│   │   ├── league_db_predictions.py # prediction CRUD
│   │   ├── league_db_misc.py       # standings, audit_log, live_scores, helpers
│   │   ├── db_helpers.py
│   │   ├── market_evaluator.py
│   │   ├── paper_trade_helpers.py
│   │   ├── gap_scanner.py
│   │   ├── gap_models.py
│   │   ├── sync_manager.py
│   │   ├── sync_schema.py
│   │   ├── season_completeness.py
│   │   ├── supabase_client.py
│   │   ├── supabase_rls_setup.sql  # RLS setup — run once in Supabase SQL editor
│   │   ├── metadata_linker.py
│   │   └── outcome_reviewer.py
│   └── Store/
│       ├── leobook.db
│       ├── country.json            # Base country data (source for DB init)
│       └── models/
├── Scripts/
│   ├── recommend_bets.py
│   └── rl_diagnose.py
├── leobookapp/                     # Flutter dashboard
│   ├── pubspec.yaml                # version: aligned with LEOBOOK_VERSION in constants.py
│   └── lib/
│       ├── presentation/screens/   # search, league (6 tabs), match (3-col), team
│       ├── core/widgets/           # LeoLoadingIndicator, LeoShimmer, GlassContainer
│       ├── core/constants/         # AppColors (UI Inspiration palette), SpacingScale
│       ├── core/theme/             # LeoTypography (DM Sans), AppThemeV2
│       └── data/repositories/      # DataRepository (fetchLeagueSeasons, etc.)
└── .devcontainer/
    ├── devcontainer.json           # remoteEnv.PATH for Flutter/Android SDK
    └── setup.sh                    # Auto-installs Python deps, Flutter, Android SDK
```

---

## Quick Start (v9.5)

### Backend Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install -r requirements-rl.txt
playwright install chromium

# 2. Pull data from Supabase (first time / recovery)
python Leo.py --pull

# 3. Run data quality scan
python Leo.py --data-quality
```

### Sync & Operations Standards

To maintain parity between local SQLite and Supabase:

| Command | Direction | Frequency | Operation |
| :--- | :--- | :--- | :--- |
| `python Leo.py --sync` | **Pull then Push** | **Startups** | Bidirectional reconcile based on watermarks. |
| `python Leo.py --push` | **Local → Cloud** | **Work Progress** | Push incremental changes (e.g., every 5% workload). |
| `python Leo.py --pull` | **Cloud → Local** | **Recovery** | Full pull from Supabase to local SQLite (UPSERT). |

### Recommended Run Order (with existing DB)

```bash
# Step 1: Bidirectional sync (reconcile both storages)
python Leo.py --sync

# Step 2: Data quality scan + gap resolution
python Leo.py --data-quality

# Step 3: Enrich leagues (fills gaps in schedules/teams)
python Leo.py --enrich-leagues

# Step 4: Sync assets (crests, logos, flags)
python Leo.py --assets

# Step 5: Run the pipeline (Prologue → Ch1 → Ch2)
python Leo.py --prologue          # Data readiness gates
python Leo.py --chapter 1         # Odds + Predictions + Recommendations
python Leo.py --chapter 2         # Automated booking

# Step 6: Final Progress Push
python Leo.py --push
```

### Full CLI Reference

```bash
# ── Autonomous Mode ──
python Leo.py                            # Full cycle (Prologue → Ch1 → Ch2, loop)
python Leo.py --dry-run                  # Full pipeline, no real bets

# ── Sync & Data ──
python Leo.py --sync                     # Bidirectional reconcile (Pull then Push)
python Leo.py --push                     # Push local → Supabase (UPSERT)
python Leo.py --pull                     # Pull Supabase → local SQLite (Full)
python Leo.py --reset-sync TABLE         # Reset sync watermark for a table
python Leo.py --data-quality             # Gap scan + Invalid ID resolution
python Leo.py --season-completeness      # Print league-season coverage report

# ── Granular Execution ──
python Leo.py --prologue                 # All prologue pages (P1+P2+P3)
python Leo.py --prologue --page 1        # Prologue P1: Cloud Handshake & Review
python Leo.py --chapter 1               # Full Chapter 1 (Extraction → Predict → Sync)
python Leo.py --chapter 1 --page 1       # Ch1 P1: URL Resolution & Odds Harvesting
python Leo.py --chapter 1 --page 2       # Ch1 P2: Predictions (Rule Engine + RL)
python Leo.py --chapter 1 --page 3       # Ch1 P3: Recommendations & Final Sync
python Leo.py --chapter 2               # Full Chapter 2 (Booking & Withdrawal)

# ── Enrichment ──
python Leo.py --enrich-leagues           # Smart gap-driven enrichment
python Leo.py --refresh                  # Re-extract including processed (use with --enrich-leagues)
python Leo.py --enrich-leagues --seasons 2         # Last 2 past seasons build RL history

# ── Assets ──
python Leo.py --assets                   # Sync team/league crests + region flags
python Leo.py --logos                    # Download football logo packs
python Leo.py --upgrade-crests           # Upgrade crests to HQ logos

# ── Intelligence ──
python Leo.py --recommend                # Generate recommendations
python Leo.py --accuracy                 # Print accuracy report
python Leo.py --review                   # Outcome review (finished matches)

# ── Rule Engine ──
python Leo.py --rule-engine              # Show default engine
python Leo.py --rule-engine --backtest   # Progressive backtest

# ── RL Training ──
python Leo.py --train-rl                 # Train RL model
python Leo.py --diagnose-rl              # RL decision diagnostics

# ── Model Sync ──
python Leo.py --push-models              # Upload models → Supabase Storage
python Leo.py --pull-models              # Download models ← Supabase Storage

# ── Live Streaming ──
python Leo.py --streamer                 # Spawn live score streamer (detached)

# ── Full help ──
python Leo.py --help
```

### Flutter App

```bash
cd leobookapp
flutter pub get
flutter run -d chrome         # Web
flutter run -d android        # Android (connected device)
flutter build apk --release   # Production APK
```

### Download APK

[**📱 Download LeoBook APK (Android)**](https://jefoqzewyvscdqcpnjxu.supabase.co/storage/v1/object/public/app-releases/LeoBook-latest.apk)

### Deploy APK

```bash
# Build, rename (auto-versioned from pubspec.yaml), and upload to Supabase
./deploy_apk.sh

# Skip build, upload existing APK
./deploy_apk.sh --skip-build
```
---

### v9.5.9 auth and prediction update

- Mobile email verification, magic-link, reset, and OAuth flows now target the LeoBook app callback instead of localhost-style redirects.
- OTP requests now wait for real send success before navigating and fall back more safely between WhatsApp and SMS channels.
- Prediction rows now enrich schedule rows without blanking out fixtures, so dates with predictions continue rendering in the UI.
- Biometric app access can now be managed directly from the account/settings screen.

*Last updated: 2026-04-02 - v9.5.9 - Auth redirect repair, OTP delivery flow hardening, prediction merge fixes, and biometric settings controls.*
*LeoBook Engineering Team — Materialless LLC*

