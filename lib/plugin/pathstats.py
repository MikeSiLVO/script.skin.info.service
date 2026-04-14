"""Path statistics calculator for video library content."""
from __future__ import annotations

from typing import Dict, Any, List
from lib.kodi.client import request


def _process_items(stats: Dict[str, Any], items: List[dict]) -> None:
    """Count watched/unwatched/in-progress per item.

    TV show items use episode counts (no show-level resume). Movies and episodes
    use playcount/resume.
    """
    for item in items:
        if item.get('type') == 'tvshow':
            episode_count = item.get('episode', 0)
            watched_count = item.get('watchedepisodes', 0)
            stats['episodes'] += episode_count
            stats['watched_episodes'] += watched_count
            stats['tvshow_count'] += 1
            if watched_count > 0 and watched_count >= episode_count:
                stats['watched'] += 1
            elif watched_count > 0:
                stats['in_progress'] += 1
            else:
                stats['unwatched'] += 1
            continue

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

    if stats['episodes']:
        stats['unwatched_episodes'] = stats['episodes'] - stats['watched_episodes']


def get_path_statistics(path: str) -> Dict[str, Any]:
    """
    Calculate statistics for a video library path.

    Args:
        path: Video library path (videodb://, plugin://, special://, etc.)

    Returns:
        Dictionary containing:
        - count: Total items
        - watched: Fully watched items
        - unwatched: Untouched items
        - in_progress: Partially watched (episode count for shows, resume point otherwise)
        - tvshow_count: Number of shows (when path returns tvshow items)
        - episodes: Total episodes across all shows
        - watched_episodes: Watched episodes
        - unwatched_episodes: Unwatched episodes
    """
    stats = {
        'count': 0,
        'watched': 0,
        'unwatched': 0,
        'in_progress': 0,
        'tvshow_count': 0,
        'episodes': 0,
        'watched_episodes': 0,
        'unwatched_episodes': 0,
    }

    if not path:
        return stats

    result = request(
        'Files.GetDirectory',
        {
            'directory': path,
            'media': 'video',
            'properties': ['playcount', 'resume', 'episode', 'watchedepisodes'],
        }
    )

    if not result or 'result' not in result:
        return stats

    files = result['result'].get('files', [])
    stats['count'] = result['result'].get('limits', {}).get('total', len(files))

    _process_items(stats, files)

    return stats
