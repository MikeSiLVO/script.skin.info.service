"""Database package for queue management and API caching.

Unified database (skininfo_v1.db) containing:
- Queue management for artwork review workflow
- API response caching (TMDB, fanart.tv)
- Workflow tracking for sessions and operations

Modules:
- _infrastructure: Database connections and schema
- cache: API response caching and TTL management
- queue: Queue CRUD operations for artwork workflow
- workflow: Session and operation history tracking
"""
from resources.lib.database._infrastructure import (
    DB_PATH,
    DB_VERSION,
    get_connection,
    get_db,
    init_database,
    vacuum_database,
)

from resources.lib.database.cache import (
    DEFAULT_CACHE_TTL_HOURS,
    get_cache_ttl_hours,
    get_cached_artwork,
    cache_artwork,
    clear_expired_cache,
)

from resources.lib.database.queue import (
    ARTITEM_REVIEW_MISSING,
    ARTITEM_REVIEW_CANDIDATE,
    VALID_ARTITEM_REVIEW_MODES,
    clear_queue,
    clear_queue_for_media,
    add_to_queue,
    add_art_item,
    add_to_queue_batch,
    add_art_items_batch,
    get_next_batch,
    get_art_items_for_queue,
    get_art_items_for_queue_batch,
    update_queue_status,
    update_art_item,
    update_art_item_status,
    get_queue_stats,
    get_queue_breakdown_by_media,
    has_pending_queue,
    get_pending_media_counts,
    count_pending_missing_art,
    prune_inactive_queue_items,
    restore_pending_queue_items,
    cleanup_old_queue_items,
)

from resources.lib.database.workflow import (
    get_session_media_types,
    get_session_art_types,
    create_scan_session,
    update_session_stats,
    complete_session,
    pause_session,
    cancel_session,
    get_paused_sessions,
    get_session,
    get_last_manual_review_session,
    save_operation_stats,
    get_last_operation_stats,
)

__all__ = [
    # Infrastructure
    'DB_PATH',
    'DB_VERSION',
    'get_connection',
    'get_db',
    'init_database',
    'vacuum_database',
    # Cache
    'DEFAULT_CACHE_TTL_HOURS',
    'get_cache_ttl_hours',
    'get_cached_artwork',
    'cache_artwork',
    'clear_expired_cache',
    # Queue
    'ARTITEM_REVIEW_MISSING',
    'ARTITEM_REVIEW_CANDIDATE',
    'VALID_ARTITEM_REVIEW_MODES',
    'clear_queue',
    'clear_queue_for_media',
    'add_to_queue',
    'add_art_item',
    'add_to_queue_batch',
    'add_art_items_batch',
    'get_next_batch',
    'get_art_items_for_queue',
    'get_art_items_for_queue_batch',
    'update_queue_status',
    'update_art_item',
    'update_art_item_status',
    'get_queue_stats',
    'get_queue_breakdown_by_media',
    'has_pending_queue',
    'get_pending_media_counts',
    'count_pending_missing_art',
    'prune_inactive_queue_items',
    'restore_pending_queue_items',
    'cleanup_old_queue_items',
    # Workflow (sessions + operations)
    'get_session_media_types',
    'get_session_art_types',
    'create_scan_session',
    'update_session_stats',
    'complete_session',
    'pause_session',
    'cancel_session',
    'get_paused_sessions',
    'get_session',
    'get_last_manual_review_session',
    'save_operation_stats',
    'get_last_operation_stats',
]
