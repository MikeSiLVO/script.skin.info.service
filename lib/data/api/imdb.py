"""IMDb dataset handler - downloads and caches IMDb's public ratings dataset.

IMDb provides free daily dataset exports at https://datasets.imdbws.com/ for
personal, non-commercial use. This module handles downloading, caching, and
lookups from the title.ratings.tsv dataset.

Data is stored in SQLite for minimal RAM usage on low-end devices.
"""
from __future__ import annotations

import gzip
import xbmc
from typing import Optional

from lib.data.api.client import ApiSession
from lib.kodi.client import log
from lib.data.database._infrastructure import get_db
from lib.data.database import imdb as db_imdb

DATASET_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"
EPISODE_DATASET_URL = "https://datasets.imdbws.com/title.episode.tsv.gz"
BATCH_SIZE = 10000


class _ImportAborted(Exception):
    pass


class ApiImdbDataset:
    """Handles IMDb dataset download, caching, and lookup via SQLite."""

    def __init__(self):
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
            return db_imdb.get_rating_with_cursor(imdb_id, cursor)
        return db_imdb.get_rating(imdb_id)

    def get_ratings_batch(self, imdb_ids: list[str]) -> dict[str, dict[str, float | int]]:
        """
        Look up ratings for multiple IMDb IDs.

        Args:
            imdb_ids: List of IMDb IDs

        Returns:
            Dict mapping IMDb IDs to rating dicts (missing IDs not included)
        """
        return db_imdb.get_ratings_batch(imdb_ids)

    def is_dataset_available(self) -> bool:
        """Check if the dataset has been imported to the database."""
        return db_imdb.is_dataset_available()

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

            local_mod = db_imdb.get_meta_last_modified("ratings")

            if local_mod == remote_mod:
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
        return self._download_and_import(abort_flag, force=True)

    def get_stats(self) -> dict[str, int | float | str | bool | None]:
        """
        Get dataset statistics.

        Returns:
            Dict with entry count, last modified date, and downloaded timestamp
        """
        return db_imdb.get_dataset_stats()

    def _download_and_import(self, abort_flag=None, force: bool = False) -> bool:
        try:
            log("IMDb", f"Downloading dataset from {DATASET_URL}...")

            headers = None
            if not force:
                local_mod = db_imdb.get_meta_last_modified("ratings")
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

            count = self._stream_and_import_ratings(response, abort_flag)

            if last_mod:
                db_imdb.save_meta("ratings", last_mod, count)

            log("IMDb", f"Imported {count:,} ratings to database")
            return True

        except _ImportAborted:
            return False
        except Exception as e:
            log("IMDb", f"Failed to download dataset: {e}", xbmc.LOGERROR)
            return False

    def _stream_and_import_ratings(self, response, abort_flag=None) -> int:
        count = 0
        batch: list[tuple[str, float, int]] = []

        with get_db() as (_, cursor):
            db_imdb.import_ratings_begin(cursor)

            with gzip.open(response.raw, "rt", encoding="utf-8") as f:
                next(f)
                for line in f:
                    if abort_flag and abort_flag.is_requested():
                        log("IMDb", "Ratings import aborted by user")
                        raise _ImportAborted()

                    parts = line.strip().split("\t")
                    if len(parts) >= 3:
                        try:
                            batch.append((parts[0], float(parts[1]), int(parts[2])))
                            count += 1

                            if len(batch) >= BATCH_SIZE:
                                db_imdb.import_ratings_batch(cursor, batch)
                                batch = []
                        except ValueError:
                            continue

            if batch:
                db_imdb.import_ratings_batch(cursor, batch)

        return count

    def _get_remote_last_modified(self, abort_flag=None) -> Optional[str]:
        """Get Last-Modified header from remote server via HEAD request."""
        try:
            response = self.session.head(
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
            return db_imdb.get_episode_imdb_id_with_cursor(show_imdb_id, season, episode, cursor)
        return db_imdb.get_episode_imdb_id(show_imdb_id, season, episode)

    def get_episodes_for_show(self, show_imdb_id: str) -> dict[tuple[int, int], str]:
        """
        Get all episode IMDb IDs for a show.

        Args:
            show_imdb_id: IMDb ID of the TV show

        Returns:
            Dict mapping (season, episode) tuples to episode IMDb IDs
        """
        return db_imdb.get_episodes_for_show(show_imdb_id)

    def is_episode_dataset_available(self) -> bool:
        """Check if the episode dataset has been imported."""
        return db_imdb.is_episode_dataset_available()

    def get_episode_dataset_stats(self) -> dict[str, int | str | None]:
        """Get episode dataset statistics."""
        return db_imdb.get_episode_dataset_stats()

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

            count = self._stream_and_filter_episodes(response, user_show_ids, abort_flag)

            if last_mod:
                db_imdb.save_meta("episodes", last_mod, count, library_episode_count=library_episode_count)

            log("IMDb", f"Imported {count:,} episode IDs for {len(user_show_ids)} shows")
            return count

        except _ImportAborted:
            db_imdb.clear_meta("episodes")
            return -1
        except Exception as e:
            log("IMDb", f"Failed to download episode dataset: {e}", xbmc.LOGERROR)
            return -1

    def _stream_and_filter_episodes(
        self, response, user_show_ids: set[str], abort_flag=None
    ) -> int:
        """
        Stream gzip response and filter to user's shows.

        Processes the file line-by-line without loading entire dataset into memory.
        """
        count = 0
        batch: list[tuple[str, int, int, str]] = []

        with get_db() as (_, cursor):
            db_imdb.import_episodes_begin(cursor)

            with gzip.open(response.raw, "rt", encoding="utf-8") as f:
                next(f)

                for line in f:
                    if abort_flag and abort_flag.is_requested():
                        log("IMDb", "Episode import aborted by user")
                        raise _ImportAborted()

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
                                    db_imdb.import_episodes_batch(cursor, batch)
                                    batch = []
                            except ValueError:
                                continue

            if batch:
                db_imdb.import_episodes_batch(cursor, batch)

            db_imdb.import_episodes_finalize(cursor)

        return count

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
            local_mod, stored_ep_count = db_imdb.get_episode_meta()

            if stored_ep_count != library_episode_count:
                log("IMDb", f"Library episode count changed ({stored_ep_count} -> {library_episode_count})")
                return True

            response = self.session.head(
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


_imdb_dataset: ApiImdbDataset | None = None


def get_imdb_dataset() -> ApiImdbDataset:
    """Get the singleton IMDb dataset instance."""
    global _imdb_dataset
    if _imdb_dataset is None:
        _imdb_dataset = ApiImdbDataset()
    return _imdb_dataset
