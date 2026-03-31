# All-or-Nothing Transaction with Strict Data Contract

Implement atomic league enrichment: either all data for a league passes validation and commits, or nothing is persisted.

## Proposed Changes

### Data Contract Module

#### [NEW] [data_contract.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/data_contract.py)

A formalized validation module defining the strict data contract. All validation logic is encapsulated in the `DataContract` class.

**League Metadata Contract** — per-league validation (from [enrich_single_league](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/fs_league_tab.py#255-443)):
| Field | Source | Status |
|:---|:---|:---:|
| `fs_league_id` | `EXTRACT_FS_LEAGUE_ID_JS` | **REQUIRED** |
| `current_season` | `EXTRACT_SEASON_JS` | **REQUIRED** |
| [crest](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/db_helpers.py#423-440) | `EXTRACT_CREST_JS` | **REQUIRED** |
| [region](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/asset_manager.py#284-414) | Breadcrumb / URL slug | **REQUIRED** |
| [region_flag](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/asset_manager.py#284-414) | Breadcrumb img | **REQUIRED** |
| `region_url` | Breadcrumb href | **REQUIRED** |

**Match Contract** — per-match atomic validation:
| Field | `results` tab | [fixtures](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Core/Intelligence/prediction_pipeline.py#67-102) tab |
|:---|:---:|:---:|
| `fixture_id` | **REQUIRED** | **REQUIRED** |
| [date](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/leobookapp/lib/logic/cubit/home_cubit.dart#377-489) | **REQUIRED** | **REQUIRED** |
| [time](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/leobookapp/lib/logic/cubit/home_cubit.dart#312-376) | **REQUIRED** | **REQUIRED** |
| `home_team_name` | **REQUIRED** | **REQUIRED** |
| `away_team_name` | **REQUIRED** | **REQUIRED** |
| `home_team_id` | **REQUIRED** | **REQUIRED** |
| `away_team_id` | **REQUIRED** | **REQUIRED** |
| `home_team_url` | **REQUIRED** | **REQUIRED** |
| `away_team_url` | **REQUIRED** | **REQUIRED** |
| `match_link` | **REQUIRED** | **REQUIRED** |
| `home_crest_url` | **REQUIRED** | **REQUIRED** |
| `away_crest_url` | **REQUIRED** | **REQUIRED** |
| [match_status](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/db_helpers.py#686-712) | **REQUIRED** | **REQUIRED** |
| `home_score` | **REQUIRED** | NULLABLE |
| `away_score` | **REQUIRED** | NULLABLE |
| `winner` | **REQUIRED** | NULLABLE |
| `league_stage` | NULLABLE | NULLABLE |
| `home_red_cards` | NULLABLE | NULLABLE |
| `away_red_cards` | NULLABLE | NULLABLE |
| [extra](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/fs_league_tab.py#50-253) | NULLABLE | NULLABLE |

Functions (encapsulated in `DataContract` class):
- `DataContract.validate_match(match: dict, tab: str) -> (bool, list[str])` — validates one match.
- `DataContract.validate_tab_extraction(scanned_count: int, matches: list, tab: str) -> (bool, str)` — validates row count + all matches.
- `DataContractViolation(Exception)` — raised on any contract failure to trigger retry/rollback.

---

### Tab Extraction (Transaction Boundary)

#### [MODIFY] [fs_league_tab.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/fs_league_tab.py)

1. **Pre-scan row count**: Before calling `EXTRACT_MATCHES_JS`, count DOM rows via `page.locator("[id^='g_1_']").count()`.
2. **Contract validation**: After JS extraction, call [validate_tab_extraction(scanned, matches, tab)](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/data_contract.py#106-147). If it fails, raise [DataContractViolation](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/data_contract.py#12-15).
3. **Remove individual commits**: [upsert_team()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/league_db.py#476-594) and [bulk_upsert_fixtures()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/league_db.py#685-742) must NOT commit. The commit happens at [enrich_single_league()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/fs_league_tab.py#255-443) level only.
4. **Bump retry**: Change `@aigo_retry(max_retries=2)` → `@aigo_retry(max_retries=3)` on [extract_tab()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/fs_league_tab.py#50-253).

#### [MODIFY] [fs_league_enricher.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/fs_league_enricher.py)

1. **Outer retry**: Wrap [enrich_single_league()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/fs_league_tab.py#255-443) call in a 2-retry loop inside [_worker()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/fs_league_enricher.py#172-243).
2. **Transaction boundary**: Call `conn.execute("BEGIN")` before [enrich_single_league()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Modules/Flashscore/fs_league_tab.py#255-443), `conn.commit()` on success, `conn.rollback()` on any failure.
3. **Failure tracking**: Maintain a `failed_leagues` list. On final failure, append league info. Do NOT persist any data.
4. **Supabase sync**: Move sync checkpoints to run only after the full batch completes successfully (post-loop).
5. **Summary**: Print failed leagues at the end.

---

### DB Layer (Remove Auto-Commit)

#### [MODIFY] [league_db.py](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/league_db.py)

Add `commit=True` parameter to [upsert_league()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/league_db.py#334-383), [upsert_team()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/league_db.py#476-594), [bulk_upsert_fixtures()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/league_db.py#685-742), and [mark_league_processed()](file:///c:/Users/Admin/Desktop/ProProjection/LeoBook/Data/Access/league_db.py#391-399). Default `True` preserves backward compatibility. The enricher will pass `commit=False`.

> [!IMPORTANT]
> This is a **backward-compatible** change. All existing callers (Ch1 pipeline, data quality, sync) continue to auto-commit. Only the enricher opts out.

---

## Verification Plan

### Automated Tests
1. `python -c "from Modules.Flashscore.data_contract import validate_match; ..."` — unit test with known good/bad match dicts.
2. Run `python Leo.py --enrich-leagues --limit 2` — verify:
   - Row count assertion fires (pre-scan vs extracted).
   - Contract violations are logged with field names.
   - Successful leagues commit; failed leagues rollback with no DB residue.

### Manual Verification
- Query `SELECT COUNT(*) FROM schedules WHERE fixture_id = ''` before and after a run to confirm no partial inserts.
