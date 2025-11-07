"""Multi-threaded artwork download queue."""
from __future__ import annotations

import os
from typing import Optional, Dict, Any
import xbmcvfs

from lib.infrastructure.workers import WorkerQueue
from lib.download.artwork import DownloadArtwork


class DownloadQueue(WorkerQueue):
    """
    Multi-threaded artwork download queue.

    Manages parallel downloads with statistics tracking, error handling,
    and progress callbacks. Each worker has its own DownloadArtwork instance.
    """

    def __init__(
        self,
        num_workers: Optional[int] = None,
        existing_file_mode: str = 'skip',
        abort_flag=None,
        task_context=None
    ):
        """
        Initialize download queue.

        Args:
            num_workers: Number of worker threads (auto-detect if None)
            existing_file_mode: 'skip', 'overwrite', or 'use_existing'
            abort_flag: Optional AbortFlag to check for cancellation
            task_context: Optional TaskContext for progress tracking
        """
        super().__init__(
            num_workers=num_workers,
            abort_flag=abort_flag,
            task_context=task_context
        )

        self.existing_file_mode = existing_file_mode
        self.artworks: Dict[int, DownloadArtwork] = {}

        self.stats_downloaded = 0
        self.stats_skipped = 0
        self.stats_failed = 0
        self.stats_bytes = 0
        self.stats_folders: Dict[str, int] = {}

    def add_download(
        self,
        url: str,
        local_path: str,
        artwork_type: str,
        title: str,
        alternate_path: Optional[str] = None,
        media_type: str = ''
    ) -> bool:
        """
        Queue an artwork download.

        Args:
            url: Image URL to download
            local_path: Base path WITHOUT extension
            artwork_type: Type of artwork (for logging)
            title: Media title (for logging)
            alternate_path: Optional alternate naming pattern to check
            media_type: Media type (for directory creation logic)

        Returns:
            True if queued, False if already processing
        """
        item = (url, local_path, artwork_type, title, alternate_path, media_type)
        dedupe_key = (url, local_path)
        return self.add_item(item, dedupe_key=dedupe_key)

    def get_stats(self) -> Dict:
        """
        Get current queue statistics.

        Returns:
            Dict with download-specific stats
        """
        base_stats = super().get_stats()
        base_stats.update({
            'downloaded': self.stats_downloaded,
            'skipped': self.stats_skipped,
            'failed': self.stats_failed,
            'bytes_downloaded': self.stats_bytes,
            'folder_counts': dict(self.stats_folders)
        })
        return base_stats

    def _process_item(self, item: Any, worker_id: int) -> Dict:
        """
        Process a single download.

        Args:
            item: Tuple of (url, local_path, artwork_type, title, alternate_path, media_type)
            worker_id: ID of worker processing the item

        Returns:
            Dict with result info
        """
        url, local_path, artwork_type, title, alternate_path, media_type = item

        if worker_id not in self.artworks:
            self.artworks[worker_id] = DownloadArtwork()

        downloader = self.artworks[worker_id]

        success, error, bytes_downloaded = downloader.download_artwork(
            url=url,
            local_path=local_path,
            artwork_type=artwork_type,
            existing_file_mode=self.existing_file_mode,
            alternate_path=alternate_path,
            media_type=media_type,
            abort_flag=self.abort_flag
        )

        if success:
            self.stats_downloaded += 1
            self.stats_bytes += bytes_downloaded
            validated_path = xbmcvfs.validatePath(local_path)
            folder_path = os.path.dirname(validated_path)
            if folder_path:
                self.stats_folders[folder_path] = self.stats_folders.get(folder_path, 0) + 1
        elif error is None:
            self.stats_skipped += 1
        else:
            self.stats_failed += 1

        return {
            'url': url,
            'local_path': local_path,
            'artwork_type': artwork_type,
            'title': title,
            'success': success,
            'error': error,
            'bytes_downloaded': bytes_downloaded
        }
