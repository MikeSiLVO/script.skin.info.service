"""Path statistics calculator for video library content."""
from __future__ import annotations

from typing import Dict, Any, List
from lib.kodi.client import request


def _process_items_for_playback_stats(stats: Dict[str, Any], items: List[dict]) -> None:
    """Process items to count watched/unwatched/in-progress based on playcount and resume."""
    for item in items:
        playcount = item.get('playcount', 0)
        resume = item.get('resume', {})

        resume_position = 0
        if isinstance(resume, dict) and resume.get('total'):
            resume_position = resume.get('position', 0)

        if resume_position > 0:
            stats['in_progress'] += 1
        elif playcount > 0:
            stats['watched'] += 1
        else:
            stats['unwatched'] += 1


def get_path_statistics(path: str) -> Dict[str, Any]:
    """
    Calculate statistics for a video library path.

    Uses Files.GetDirectory for videodb:// paths to respect path-based filters
    (genres, years, actors, etc.). For TV shows, fetches episode counts to calculate
    show-level watched/in-progress status.

    Args:
        path: Video library path (videodb://, plugin://, special://, etc.)

    Returns:
        Dictionary containing:
        - count: Total items
        - watched: Items with playcount > 0
        - unwatched: Items with playcount == 0 and no resume
        - in_progress: Items with playcount == 0 and resume.position > 0
        - tvshow_count: (TV shows only) Number of shows
        - episodes: (TV shows only) Total episodes across all shows
        - watched_episodes: (TV shows only) Watched episodes
        - unwatched_episodes: (TV shows only) Unwatched episodes
    """
    stats = {
        'count': 0,
        'watched': 0,
        'unwatched': 0,
        'in_progress': 0,
        'tvshow_count': 0,
        'episodes': 0,
        'watched_episodes': 0,
        'unwatched_episodes': 0
    }

    if not path:
        return stats

    path_lower = path.lower()

    if path_lower.startswith('videodb://tvshows/'):
        _calculate_tvshow_stats(stats, path)
    else:
        _calculate_video_stats(stats, path)

    return stats


def _calculate_tvshow_stats(stats: Dict[str, Any], path: str) -> None:
    """
    Calculate statistics for TV show paths using Files.GetDirectory.

    Fetches episode counts to calculate show-level watched/in-progress status.
    Uses Files.GetDirectory to respect path-based filters (genres, years, etc.).
    """
    result = request(
        'Files.GetDirectory',
        {
            'directory': path,
            'media': 'video',
            'properties': ['episode', 'watchedepisodes']
        }
    )

    if not result or 'result' not in result:
        return

    tvshows = result['result'].get('files', [])
    stats['count'] = result['result'].get('limits', {}).get('total', len(tvshows))
    stats['tvshow_count'] = stats['count']

    total_episodes = 0
    total_watched_episodes = 0

    for show in tvshows:
        episode_count = show.get('episode', 0)
        watched_count = show.get('watchedepisodes', 0)

        total_episodes += episode_count
        total_watched_episodes += watched_count

        if watched_count > 0 and watched_count >= episode_count:
            stats['watched'] += 1
        elif watched_count > 0:
            stats['in_progress'] += 1
        else:
            stats['unwatched'] += 1

    stats['episodes'] = total_episodes
    stats['watched_episodes'] = total_watched_episodes
    stats['unwatched_episodes'] = total_episodes - total_watched_episodes


def _calculate_video_stats(stats: Dict[str, Any], path: str) -> None:
    """
    Calculate statistics for video paths using Files.GetDirectory.

    Fetches playcount and resume for accurate watched/in-progress detection.
    Used for movies, episodes, and generic video paths.
    """
    result = request(
        'Files.GetDirectory',
        {
            'directory': path,
            'media': 'video',
            'properties': ['playcount', 'resume']
        }
    )

    if not result or 'result' not in result:
        return

    files = result['result'].get('files', [])
    stats['count'] = result['result'].get('limits', {}).get('total', len(files))

    _process_items_for_playback_stats(stats, files)
