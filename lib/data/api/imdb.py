"""IMDb dataset handler - downloads and caches IMDb's public ratings dataset.

IMDb provides free daily dataset exports at https://datasets.imdbws.com/ for
personal, non-commercial use. This module handles downloading, caching, and
lookups from the title.ratings.tsv dataset.

Data is stored in SQLite for minimal RAM usage on low-end devices.
"""
from __future__ import annotations

import os
import gzip
import xbmc
import xbmcvfs
from datetime import datetime
from typing import Optional

from lib.data.api.client import ApiSession
from lib.kodi.client import log
from lib.data.database._infrastructure import get_db

DATASET_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"
EPISODE_DATASET_URL = "https://datasets.imdbws.com/title.episode.tsv.gz"
BATCH_SIZE = 10000


class ApiImdbDataset:
    """Handles IMDb dataset download, caching, and lookup via SQLite."""

    def __init__(self):
        self._cache_dir = xbmcvfs.translatePath(
            "special://profile/addon_data/script.skin.info.service/imdb_dataset/"
        )
        self.session = ApiSession(
            service_name="IMDb Dataset",
            base_url="https://datasets.imdbws.com",
            timeout=(10.0, 120.0),
            max_retries=2,
            backoff_factor=1.0
        )

    def get_rating(self, imdb_id: str, cursor=None) -> Optional[dict[str, float | int]]:
        """
        Look up rating for an IMDb ID.

        Args:
            imdb_id: IMDb ID (e.g., "tt0111161")
            cursor: Optional cursor for bulk operations (avoids connection overhead)

        Returns:
            Dict with rating and votes, or None if not found:
            {"rating": 9.3, "votes": 2800000}
        """
        if cursor:
            cursor.execute(
                "SELECT rating, votes FROM imdb_ratings WHERE imdb_id = ?",
                (imdb_id,)
            )
            row = cursor.fetchone()
            if row:
                return {"rating": row["rating"], "votes": row["votes"]}
            return None

        with get_db() as (conn, cur):
            cur.execute(
                "SELECT rating, votes FROM imdb_ratings WHERE imdb_id = ?",
                (imdb_id,)
            )
            row = cur.fetchone()
            if row:
                return {"rating": row["rating"], "votes": row["votes"]}
        return None

    def get_ratings_batch(self, imdb_ids: list[str]) -> dict[str, dict[str, float | int]]:
        """
        Look up ratings for multiple IMDb IDs.

        Args:
            imdb_ids: List of IMDb IDs

        Returns:
            Dict mapping IMDb IDs to rating dicts (missing IDs not included)
        """
        if not imdb_ids:
            return {}

        results = {}
        with get_db() as (conn, cursor):
            placeholders = ",".join(["?" for _ in imdb_ids])
            cursor.execute(
                f"SELECT imdb_id, rating, votes FROM imdb_ratings WHERE imdb_id IN ({placeholders})",
                imdb_ids
            )
            for row in cursor.fetchall():
                results[row["imdb_id"]] = {"rating": row["rating"], "votes": row["votes"]}
        return results

    def is_dataset_available(self) -> bool:
        """Check if the dataset has been imported to the database."""
        with get_db() as (conn, cursor):
            cursor.execute("SELECT COUNT(*) as cnt FROM imdb_ratings")
            row = cursor.fetchone()
            return row["cnt"] > 0 if row else False

    def refresh_if_stale(self, abort_flag=None) -> bool:
        """
        Check for updates and download if remote is newer.

        Uses HTTP Last-Modified header to detect changes.

        Args:
            abort_flag: Optional abort flag for cancellation

        Returns:
            True if dataset was updated, False if already current or error
        """
        try:
            remote_mod = self._get_remote_last_modified(abort_flag)
            if not remote_mod:
                return False

            local_mod = self._get_local_last_modified()

            if local_mod == remote_mod:
                log("IMDb", "Dataset is current, no download needed")
                return False

            log("IMDb", f"Dataset update available (local: {local_mod}, remote: {remote_mod})")
            return self._download_and_import(abort_flag)

        except Exception as e:
            log("IMDb", f"Error checking for dataset updates: {e}", xbmc.LOGWARNING)
            return False

    def force_download(self, abort_flag=None) -> bool:
        """
        Force download the dataset regardless of cache state.

        Args:
            abort_flag: Optional abort flag for cancellation

        Returns:
            True if download succeeded, False otherwise
        """
        return self._download_and_import(abort_flag)

    def get_stats(self) -> dict[str, int | float | str | bool | None]:
        """
        Get dataset statistics.

        Returns:
            Dict with entry count, last modified date, and downloaded timestamp
        """
        stats: dict[str, int | float | str | bool | None] = {
            "entries": 0,
            "last_modified": None,
            "downloaded_at": None,
        }

        with get_db() as (conn, cursor):
            cursor.execute(
                "SELECT last_modified, downloaded_at, entry_count FROM imdb_meta WHERE dataset = ?",
                ("ratings",)
            )
            row = cursor.fetchone()
            if row:
                stats["last_modified"] = row["last_modified"]
                stats["downloaded_at"] = row["downloaded_at"]
                stats["entries"] = row["entry_count"] or 0

        return stats

    def _download_and_import(self, abort_flag=None) -> bool:
        """
        Download, extract, and import the dataset to SQLite.

        Args:
            abort_flag: Optional abort flag for cancellation

        Returns:
            True if successful, False otherwise
        """
        os.makedirs(self._cache_dir, exist_ok=True)
        gzip_path = os.path.join(self._cache_dir, "title.ratings.tsv.gz")
        tsv_path = os.path.join(self._cache_dir, "title.ratings.tsv")

        try:
            log("IMDb", f"Downloading dataset from {DATASET_URL}...")

            local_mod = self._get_local_last_modified()
            headers = {"If-Modified-Since": local_mod} if local_mod else None

            response = self.session.get_raw(
                "/title.ratings.tsv.gz",
                headers=headers,
                abort_flag=abort_flag,
                stream=True
            )

            if response is None:
                return False

            if response.status_code == 304:
                log("IMDb", "Dataset not modified (304), using cached version")
                return False

            last_mod = response.headers.get("Last-Modified")

            with open(gzip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if abort_flag and abort_flag.is_requested():
                        log("IMDb", "Download aborted by user")
                        return False
                    f.write(chunk)

            log("IMDb", "Extracting dataset...")
            with gzip.open(gzip_path, "rb") as gz:
                with open(tsv_path, "wb") as out:
                    out.write(gz.read())

            log("IMDb", "Importing to database...")
            count = self._import_tsv_to_db(tsv_path)

            if last_mod:
                self._save_local_last_modified(last_mod, count)

            log("IMDb", f"Imported {count:,} ratings to database")
            return True

        except Exception as e:
            log("IMDb", f"Failed to download dataset: {e}", xbmc.LOGERROR)
            return False

        finally:
            for path in (gzip_path, tsv_path):
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    def _import_tsv_to_db(self, tsv_path: str) -> int:
        """
        Import TSV file to SQLite database.

        Args:
            tsv_path: Path to the extracted TSV file

        Returns:
            Number of rows imported
        """
        count = 0
        batch: list[tuple[str, float, int]] = []

        with get_db() as (conn, cursor):
            cursor.execute("DELETE FROM imdb_ratings")

            with open(tsv_path, "r", encoding="utf-8") as f:
                next(f)  # Skip header
                for line in f:
                    parts = line.strip().split("\t")
                    if len(parts) >= 3:
                        try:
                            imdb_id = parts[0]
                            rating = float(parts[1])
                            votes = int(parts[2])
                            batch.append((imdb_id, rating, votes))
                            count += 1

                            if len(batch) >= BATCH_SIZE:
                                cursor.executemany(
                                    "INSERT INTO imdb_ratings (imdb_id, rating, votes) VALUES (?, ?, ?)",
                                    batch
                                )
                                batch = []
                        except ValueError:
                            continue

            if batch:
                cursor.executemany(
                    "INSERT INTO imdb_ratings (imdb_id, rating, votes) VALUES (?, ?, ?)",
                    batch
                )

        return count

    def _get_remote_last_modified(self, abort_flag=None) -> Optional[str]:
        """Get Last-Modified header from remote server."""
        try:
            response = self.session.get_raw(
                "/title.ratings.tsv.gz",
                abort_flag=abort_flag,
                timeout=(5.0, 10.0)
            )
            if response:
                return response.headers.get("Last-Modified")
            return None
        except Exception as e:
            log("IMDb", f"Failed to check remote Last-Modified: {e}", xbmc.LOGWARNING)
            return None

    def _get_local_last_modified(self) -> Optional[str]:
        """Get stored Last-Modified from previous download."""
        with get_db() as (conn, cursor):
            cursor.execute(
                "SELECT last_modified FROM imdb_meta WHERE dataset = ?",
                ("ratings",)
            )
            row = cursor.fetchone()
            if row and row["last_modified"]:
                return row["last_modified"]
        return None

    def _save_local_last_modified(self, last_mod: str, entry_count: int = 0) -> None:
        """Store Last-Modified and entry count in database."""
        with get_db() as (conn, cursor):
            cursor.execute(
                """INSERT OR REPLACE INTO imdb_meta
                   (dataset, last_modified, downloaded_at, entry_count)
                   VALUES (?, ?, ?, ?)""",
                ("ratings", last_mod, datetime.now().isoformat(), entry_count)
            )

    # Episode dataset methods

    def get_episode_imdb_id(
        self, show_imdb_id: str, season: int, episode: int, cursor=None
    ) -> Optional[str]:
        """
        Look up episode IMDb ID by show + season + episode.

        Args:
            show_imdb_id: IMDb ID of the TV show (e.g., "tt0944947")
            season: Season number
            episode: Episode number
            cursor: Optional cursor for bulk operations

        Returns:
            Episode IMDb ID (e.g., "tt4283088") or None if not found
        """
        if cursor:
            cursor.execute(
                "SELECT episode_id FROM imdb_episodes WHERE parent_id = ? AND season = ? AND episode = ?",
                (show_imdb_id, season, episode)
            )
            row = cursor.fetchone()
            return row["episode_id"] if row else None

        with get_db() as (conn, cur):
            cur.execute(
                "SELECT episode_id FROM imdb_episodes WHERE parent_id = ? AND season = ? AND episode = ?",
                (show_imdb_id, season, episode)
            )
            row = cur.fetchone()
            return row["episode_id"] if row else None

    def get_episodes_for_show(self, show_imdb_id: str) -> dict[tuple[int, int], str]:
        """
        Get all episode IMDb IDs for a show.

        Args:
            show_imdb_id: IMDb ID of the TV show

        Returns:
            Dict mapping (season, episode) tuples to episode IMDb IDs
        """
        result: dict[tuple[int, int], str] = {}
        with get_db() as (conn, cursor):
            cursor.execute(
                "SELECT season, episode, episode_id FROM imdb_episodes WHERE parent_id = ?",
                (show_imdb_id,)
            )
            for row in cursor.fetchall():
                result[(row["season"], row["episode"])] = row["episode_id"]
        return result

    def is_episode_dataset_available(self) -> bool:
        """Check if the episode dataset has been imported."""
        with get_db() as (conn, cursor):
            cursor.execute("SELECT COUNT(*) as cnt FROM imdb_episodes")
            row = cursor.fetchone()
            return row["cnt"] > 0 if row else False

    def get_episode_dataset_stats(self) -> dict[str, int | str | None]:
        """Get episode dataset statistics."""
        stats: dict[str, int | str | None] = {
            "entries": 0,
            "last_modified": None,
            "downloaded_at": None,
        }
        with get_db() as (conn, cursor):
            cursor.execute(
                "SELECT last_modified, downloaded_at, entry_count FROM imdb_meta WHERE dataset = ?",
                ("episodes",)
            )
            row = cursor.fetchone()
            if row:
                stats["last_modified"] = row["last_modified"]
                stats["downloaded_at"] = row["downloaded_at"]
                stats["entries"] = row["entry_count"] or 0
        return stats

    def refresh_episode_dataset(
        self,
        user_show_ids: set[str],
        library_episode_count: int = 0,
        progress_callback=None,
        abort_flag=None
    ) -> int:
        """
        Download episode dataset and filter to user's shows.

        Args:
            user_show_ids: Set of IMDb IDs for shows in user's library
            library_episode_count: Current total episode count from Kodi (for cache invalidation)
            progress_callback: Optional callback(status_text) for progress updates
            abort_flag: Optional abort flag for cancellation

        Returns:
            Number of episodes imported, or -1 on error
        """
        if not user_show_ids:
            return 0

        try:
            if progress_callback:
                progress_callback("Downloading episode data...")

            log("IMDb", f"Downloading episode dataset from {EPISODE_DATASET_URL}...")

            response = self.session.get_raw(
                "/title.episode.tsv.gz",
                abort_flag=abort_flag,
                stream=True,
                timeout=(10.0, 180.0)
            )

            if response is None:
                return -1

            last_mod = response.headers.get("Last-Modified")

            if progress_callback:
                progress_callback("Processing episodes...")

            count = self._stream_and_filter_episodes(response, user_show_ids, progress_callback, abort_flag)

            if count < 0:
                return -1

            if last_mod:
                self._save_episode_meta(last_mod, count, library_episode_count)

            log("IMDb", f"Imported {count:,} episode IDs for {len(user_show_ids)} shows")
            return count

        except Exception as e:
            log("IMDb", f"Failed to download episode dataset: {e}", xbmc.LOGERROR)
            return -1

    def _stream_and_filter_episodes(
        self, response, user_show_ids: set[str], progress_callback=None, abort_flag=None
    ) -> int:
        """
        Stream gzip response and filter to user's shows.

        Processes the file line-by-line without loading entire dataset into memory.
        """
        count = 0
        batch: list[tuple[str, int, int, str]] = []
        lines_processed = 0

        with get_db() as (conn, cursor):
            cursor.execute("DELETE FROM imdb_episodes")

            with gzip.open(response.raw, "rt", encoding="utf-8") as f:
                next(f)  # Skip header: tconst, parentTconst, seasonNumber, episodeNumber

                for line in f:
                    if abort_flag and abort_flag.is_requested():
                        log("IMDb", "Episode import aborted by user")
                        return -1

                    lines_processed += 1

                    if lines_processed % 500000 == 0 and progress_callback:
                        progress_callback(f"Processing... {lines_processed:,} rows checked")

                    parts = line.strip().split("\t")
                    if len(parts) >= 4:
                        ep_id, parent_id, season_str, episode_str = parts[0], parts[1], parts[2], parts[3]

                        if parent_id in user_show_ids and season_str != "\\N" and episode_str != "\\N":
                            try:
                                season = int(season_str)
                                episode = int(episode_str)
                                batch.append((parent_id, season, episode, ep_id))
                                count += 1

                                if len(batch) >= BATCH_SIZE:
                                    cursor.executemany(
                                        "INSERT OR REPLACE INTO imdb_episodes (parent_id, season, episode, episode_id) VALUES (?, ?, ?, ?)",
                                        batch
                                    )
                                    batch = []
                            except ValueError:
                                continue

            if batch:
                cursor.executemany(
                    "INSERT OR REPLACE INTO imdb_episodes (parent_id, season, episode, episode_id) VALUES (?, ?, ?, ?)",
                    batch
                )

        return count

    def _get_episode_meta(self) -> tuple[Optional[str], int]:
        """Get stored Last-Modified and library episode count for episode dataset."""
        with get_db() as (conn, cursor):
            cursor.execute(
                "SELECT last_modified, library_episode_count FROM imdb_meta WHERE dataset = ?",
                ("episodes",)
            )
            row = cursor.fetchone()
            if row:
                return row["last_modified"], row["library_episode_count"] or 0
            return None, 0

    def needs_episode_refresh(self, library_episode_count: int, abort_flag=None) -> bool:
        """
        Check if episode dataset needs refresh without downloading.

        Args:
            library_episode_count: Current total episode count from Kodi
            abort_flag: Optional abort flag for cancellation

        Returns:
            True if refresh needed, False if current
        """
        try:
            local_mod, stored_ep_count = self._get_episode_meta()

            if stored_ep_count != library_episode_count:
                log("IMDb", f"Library episode count changed ({stored_ep_count} -> {library_episode_count})")
                return True

            response = self.session.get_raw(
                "/title.episode.tsv.gz",
                abort_flag=abort_flag,
                timeout=(5.0, 10.0)
            )

            if response:
                remote_mod = response.headers.get("Last-Modified")
                if not local_mod or local_mod != remote_mod:
                    log("IMDb", "IMDb dataset updated")
                    return True

            return False

        except Exception as e:
            log("IMDb", f"Error checking episode dataset status: {e}", xbmc.LOGWARNING)
            return False

    def _save_episode_meta(self, last_mod: str, entry_count: int, library_episode_count: int) -> None:
        """Store Last-Modified and library episode count for episode dataset."""
        with get_db() as (conn, cursor):
            cursor.execute(
                """INSERT OR REPLACE INTO imdb_meta
                   (dataset, last_modified, downloaded_at, entry_count, library_episode_count)
                   VALUES (?, ?, ?, ?, ?)""",
                ("episodes", last_mod, datetime.now().isoformat(), entry_count, library_episode_count)
            )


_imdb_dataset: ApiImdbDataset | None = None


def get_imdb_dataset() -> ApiImdbDataset:
    """Get the singleton IMDb dataset instance."""
    global _imdb_dataset
    if _imdb_dataset is None:
        _imdb_dataset = ApiImdbDataset()
    return _imdb_dataset
