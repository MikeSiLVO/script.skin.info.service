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
from lib.data.database._infrastructure import (
    DB_PATH,
    DB_VERSION,
    get_connection,
    get_db,
    init_database,
    vacuum_database,
)

from lib.data.database.cache import (
    get_cache_ttl_hours,
    get_cached_artwork,
    get_cached_artwork_batch,
    cache_artwork,
    get_cached_metadata,
    cache_metadata,
    cache_person_data,
    get_cached_person_data,
    clear_expired_cache,
)

from lib.data.database.queue import (
    ARTITEM_REVIEW_MISSING,
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
    count_queue_items,
    count_pending_missing_art,
    prune_inactive_queue_items,
    restore_pending_queue_items,
    cleanup_old_queue_items,
)

from lib.data.database.workflow import (
    get_session_media_types,
    get_session_media_types_batch,
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
    'DB_PATH',
    'DB_VERSION',
    'get_connection',
    'get_db',
    'init_database',
    'vacuum_database',
    'get_cache_ttl_hours',
    'get_cached_artwork',
    'get_cached_artwork_batch',
    'cache_artwork',
    'get_cached_metadata',
    'cache_metadata',
    'cache_person_data',
    'get_cached_person_data',
    'clear_expired_cache',
    'ARTITEM_REVIEW_MISSING',
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
    'count_queue_items',
    'count_pending_missing_art',
    'prune_inactive_queue_items',
    'restore_pending_queue_items',
    'cleanup_old_queue_items',
    'get_session_media_types',
    'get_session_media_types_batch',
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
