# sync_pull.py: Supabase-to-SQLite pull methods for SyncManager.
# Part of LeoBook Data — Access Layer
#
# Split from sync_manager.py (v9.6.0)
# Class: SyncPullMixin — provides _bootstrap_from_remote, batch_pull,
#        _upsert_rows_to_sqlite

"""
Sync Pull Mixin
Supabase → local SQLite pull operations.
Intended to be mixed into SyncManager only.
"""

import asyncio
import logging
import sys
from datetime import datetime

from tqdm import tqdm

logger = logging.getLogger(__name__)


class SyncPullMixin:
    """Mixin providing Supabase → SQLite pull operations for SyncManager."""

    async def _bootstrap_from_remote(self, local_table: str, remote_table: str, key_field: str) -> int:
        """Legacy bootstrap — used only for empty-local startup fallback."""
        total_pulled = 0
        batch_size = 1000
        offset = 0
        while True:
            try:
                res = self.supabase.table(remote_table).select("*").order(
                    key_field, desc=False
                ).range(offset, offset + batch_size - 1).execute()
                rows = res.data
                if not rows:
                    break
                self._upsert_rows_to_sqlite(local_table, key_field, rows)
                total_pulled += len(rows)
                if len(rows) < batch_size:
                    break
                offset += batch_size
            except Exception as e:
                err_str = str(e)
                if 'PGRST205' in err_str or 'Could not find the table' in err_str:
                    logger.info(f"      [AUTO] Table '{remote_table}' not found — creating...")
                    if self._ensure_remote_table(remote_table):
                        continue
                    else:
                        break
                else:
                    logger.error(f"      [Bootstrap] Pull failed at offset {offset}: {e}")
                    break
        if total_pulled > 0:
            logger.info(f"    [BOOTSTRAP] Pulled {total_pulled} rows into {local_table}.")
        return total_pulled

    async def batch_pull(self, table_key: str) -> int:
        """Force full pull from Supabase — mirrors the push pipeline."""
        from Data.Access.sync_schema import TABLE_CONFIG
        conf = TABLE_CONFIG.get(table_key)
        if not conf or not self.supabase:
            return 0

        local_table = conf['local_table']
        remote_table = conf['remote_table']
        key_field = conf['key']

        remote_count = None
        try:
            count_res = self.supabase.table(remote_table).select("*", count="exact").limit(0).execute()
            remote_count = count_res.count or 0
        except Exception:
            remote_count = None

        if remote_count == 0:
            print(f"   [{remote_table}] [OK] Remote empty -- nothing to pull")
            return 0

        if remote_count is not None:
            print(f"   [{remote_table}] FORCE FULL PULL -- {remote_count:,} rows (from Supabase)")
        else:
            print(f"   [{remote_table}] FORCE FULL PULL -- counting... (paginating until exhausted)")

        total_pulled = 0
        page_size = 5000
        offset = 0
        disable_pbar = not logger.isEnabledFor(logging.INFO)
        _tqdm_stream = getattr(sys.stderr, '_streams', [sys.stderr])[0] \
            if hasattr(sys.stderr, '_streams') else sys.stderr
        pbar = tqdm(
            total=remote_count,
            desc=f"    Pulling {remote_table}",
            unit="row",
            disable=disable_pbar,
            file=_tqdm_stream,
            dynamic_ncols=True,
        )

        try:
            while True:
                max_retries = 3
                for attempt in range(max_retries + 1):
                    try:
                        res = self.supabase.table(remote_table).select("*").order(
                            key_field, desc=False
                        ).limit(page_size).offset(offset).execute()
                        rows = res.data
                        break
                    except Exception as batch_err:
                        err_str = str(batch_err)
                        if 'PGRST205' in err_str or 'Could not find the table' in err_str:
                            logger.info(f"    [AUTO] Table '{remote_table}' missing -- skipping.")
                            pbar.close()
                            return total_pulled
                        is_timeout = '57014' in err_str or 'timeout' in err_str.lower() or '500' in err_str
                        if is_timeout and attempt < max_retries:
                            wait = 2 ** (attempt + 1)
                            page_size = max(1000, page_size // 2)
                            logger.warning(f"    [RETRY {attempt+1}/{max_retries}] Timeout at offset {offset}, "
                                           f"retrying in {wait}s with page_size={page_size}")
                            await asyncio.sleep(wait)
                        else:
                            raise batch_err
                else:
                    break

                if not rows:
                    break

                self._upsert_rows_to_sqlite(local_table, key_field, rows)
                total_pulled += len(rows)
                pbar.update(len(rows))
                offset += len(rows)

            pbar.close()
            if total_pulled > 0:
                logger.info(f"    [SYNC] Pulled {total_pulled:,} rows from {remote_table}.")
                self._set_watermark(remote_table, datetime.utcnow().isoformat())
            else:
                print(f"   [{remote_table}] [OK] Remote empty -- nothing to pull")
            return total_pulled

        except Exception as e:
            if 'pbar' in locals() and pbar:
                pbar.close()
            print(f"    [x] Pull failed for {remote_table}: {e}")
            logger.error(f"    [x] Pull failed: {e}")
            return 0

    def _upsert_rows_to_sqlite(self, local_table: str, key_field: str, rows: list):
        """Bulk upsert rows from Supabase into local SQLite."""
        if not rows:
            return
        table_cols = [c[1] for c in self.conn.execute(
            f"PRAGMA table_info({local_table})"
        ).fetchall()]
        
        # Handle composite keys
        key_cols = [k.strip() for k in key_field.split(',')]
        
        for row in rows:
            if 'over_2.5' in row:
                row['over_2_5'] = row.pop('over_2.5')
            
            filtered = {k: v for k, v in row.items() if k in table_cols and v is not None}
            
            # Check if all key columns are present
            if not filtered or any(k not in filtered for k in key_cols):
                continue
                
            cols = list(filtered.keys())
            placeholders = ", ".join([f":{c}" for c in cols])
            col_str = ", ".join(cols)
            
            # Exclude all key columns from DO UPDATE SET
            updates = ", ".join([f"{c} = excluded.{c}" for c in cols if c not in key_cols])
            
            try:
                self.conn.execute(
                    f"INSERT INTO {local_table} ({col_str}) VALUES ({placeholders}) "
                    f"ON CONFLICT({key_field}) DO UPDATE SET {updates}",
                    filtered,
                )
            except Exception as e:
                logger.warning(f"      [Pull] Row insert failed: {e}")
        self.conn.commit()
