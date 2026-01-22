"""Database infrastructure for connections, migrations, and schema.

Core infrastructure shared across all database modules.
"""
from __future__ import annotations

import sqlite3
import uuid
import xbmc
import xbmcvfs
from contextlib import contextmanager
from typing import Generator, Tuple
from lib.kodi.client import log

DB_PATH = xbmcvfs.translatePath('special://profile/addon_data/script.skin.info.service/skininfo_v1.db')
DB_VERSION = 1


def _generate_guid() -> str:
    return uuid.uuid4().hex


def _ensure_addon_data_folder() -> None:
    folder = xbmcvfs.translatePath('special://profile/addon_data/script.skin.info.service/')
    if not xbmcvfs.exists(folder):
        xbmcvfs.mkdirs(folder)


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """
    Get database connection with row factory.

    Args:
        db_path: Path to database file (defaults to unified DB)

    Returns:
        SQLite connection with Row factory
    """
    _ensure_addon_data_folder()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


@contextmanager
def get_db(db_path: str = DB_PATH) -> Generator[Tuple[sqlite3.Connection, sqlite3.Cursor], None, None]:
    """
    Context manager for database connections.
    Ensures connection is always closed, even on exception.

    Args:
        db_path: Path to database file (defaults to unified DB)

    Usage:
        with get_db() as (conn, cursor):
            cursor.execute(...)
            conn.commit()
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        yield conn, cursor
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def _create_base_schema(cursor: sqlite3.Cursor) -> None:
    """
    Create unified schema with queue, cache, and operation history tables.
    """
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS art_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_type TEXT NOT NULL,
            dbid INTEGER NOT NULL,
            title TEXT,
            year TEXT,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 5,
            date_added TEXT DEFAULT CURRENT_TIMESTAMP,
            date_processed TEXT,
            scope TEXT DEFAULT '',
            scan_session_id INTEGER,
            guid TEXT,
            FOREIGN KEY(scan_session_id) REFERENCES scan_sessions(id) ON DELETE SET NULL,
            UNIQUE(media_type, dbid)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS art_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            queue_id INTEGER NOT NULL,
            art_type TEXT NOT NULL,
            selected_url TEXT,
            auto_applied INTEGER DEFAULT 0,
            review_mode TEXT DEFAULT 'missing',
            requires_manual INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            scan_session_id INTEGER,
            date_processed TEXT,
            FOREIGN KEY(queue_id) REFERENCES art_queue(id) ON DELETE CASCADE,
            UNIQUE(queue_id, art_type)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scan_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_type TEXT,
            status TEXT DEFAULT 'in_progress',
            started TEXT DEFAULT CURRENT_TIMESTAMP,
            last_activity TEXT,
            completed TEXT,
            stats TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_media_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            media_type TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES scan_sessions(id) ON DELETE CASCADE,
            UNIQUE(session_id, media_type)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_art_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            art_type TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES scan_sessions(id) ON DELETE CASCADE,
            UNIQUE(session_id, art_type)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS artwork_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_type TEXT NOT NULL,
            media_id TEXT NOT NULL,
            source TEXT NOT NULL,
            art_type TEXT NOT NULL,
            data TEXT NOT NULL,
            release_date TEXT,
            cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            UNIQUE(media_type, media_id, source, art_type)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS metadata_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_type TEXT NOT NULL,
            tmdb_id TEXT NOT NULL,
            data BLOB NOT NULL,
            release_date TEXT,
            cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            UNIQUE(media_type, tmdb_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS person_cache (
            person_id INTEGER PRIMARY KEY,
            data TEXT NOT NULL,
            cached_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS operation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            stats TEXT NOT NULL,
            completed INTEGER DEFAULT 1,
            scope TEXT
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_queue_status ON art_queue(status, priority)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_queue_media_type ON art_queue(media_type)')
    cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_queue_guid ON art_queue(guid)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_queue_scope ON art_queue(scope)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_queue_session ON art_queue(scan_session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_art_items_queue ON art_items(queue_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_art_items_status ON art_items(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_art_items_review_mode ON art_items(review_mode)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_art_items_queue_status_review ON art_items(queue_id, status, review_mode)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_person_cache_expires ON person_cache(expires_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_scan_type_activity ON scan_sessions(scan_type, last_activity DESC)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_media_types_session ON session_media_types(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_media_types_lookup ON session_media_types(session_id, media_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_art_types_session ON session_art_types(session_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_art_types_lookup ON session_art_types(session_id, art_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cache_lookup ON artwork_cache(media_type, media_id, source, art_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_cache_expires ON artwork_cache(expires_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_metadata_cache_lookup ON metadata_cache(media_type, tmdb_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_operation_history_lookup ON operation_history(operation, timestamp DESC)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings_api_usage (
            provider TEXT,
            api_key_hash TEXT,
            date TEXT,
            request_count INTEGER DEFAULT 0,
            limit_hit INTEGER DEFAULT 0,
            PRIMARY KEY (provider, api_key_hash, date)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings_update_history (
            media_type TEXT,
            media_id INTEGER,
            last_updated TEXT,
            sources_updated TEXT,
            PRIMARY KEY (media_type, media_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings_failures (
            media_type TEXT,
            media_id INTEGER,
            reason TEXT,
            last_attempt TEXT,
            retry_count INTEGER DEFAULT 0,
            PRIMARY KEY (media_type, media_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS provider_cache (
            provider TEXT NOT NULL,
            media_id TEXT NOT NULL,
            data TEXT NOT NULL,
            release_date TEXT,
            cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (provider, media_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS id_corrections (
            imdb_id TEXT PRIMARY KEY,
            tmdb_id INTEGER NOT NULL,
            media_type TEXT NOT NULL,
            cached_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ratings_usage_lookup ON ratings_api_usage(provider, api_key_hash, date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ratings_history_updated ON ratings_update_history(last_updated)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ratings_failures_attempt ON ratings_failures(last_attempt)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_provider_cache_lookup ON provider_cache(provider, media_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_provider_cache_expires ON provider_cache(cached_at)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS slideshow_pool (
            kodi_dbid INTEGER NOT NULL,
            media_type TEXT NOT NULL,
            title TEXT,
            fanart TEXT NOT NULL,
            description TEXT,
            year INTEGER,
            season INTEGER,
            episode INTEGER,
            last_synced INTEGER,
            PRIMARY KEY (media_type, kodi_dbid)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_slideshow_media ON slideshow_pool(media_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_slideshow_fanart ON slideshow_pool(fanart) WHERE fanart IS NOT NULL')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gif_cache (
            path TEXT PRIMARY KEY,
            mtime REAL NOT NULL,
            scanned_at TEXT NOT NULL
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_gif_cache_scanned ON gif_cache(scanned_at)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS imdb_ratings (
            imdb_id TEXT PRIMARY KEY,
            rating REAL NOT NULL,
            votes INTEGER NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS imdb_episodes (
            parent_id TEXT NOT NULL,
            season INTEGER NOT NULL,
            episode INTEGER NOT NULL,
            episode_id TEXT NOT NULL,
            PRIMARY KEY (parent_id, season, episode)
        )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_imdb_episodes_parent ON imdb_episodes(parent_id)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS imdb_meta (
            dataset TEXT PRIMARY KEY,
            last_modified TEXT,
            downloaded_at TEXT,
            entry_count INTEGER DEFAULT 0,
            library_episode_count INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS imdb_update_progress (
            media_type TEXT PRIMARY KEY,
            dataset_date TEXT NOT NULL,
            processed_ids TEXT NOT NULL,
            total_items INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            last_updated TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ratings_synced (
            media_type TEXT NOT NULL,
            dbid INTEGER NOT NULL,
            source TEXT NOT NULL,
            external_id TEXT,
            rating REAL NOT NULL,
            votes INTEGER NOT NULL,
            synced_at TEXT NOT NULL,
            PRIMARY KEY (media_type, dbid, source)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ratings_synced_lookup ON ratings_synced(media_type, dbid)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ratings_synced_external ON ratings_synced(source, external_id)')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS online_properties_cache (
            item_key TEXT PRIMARY KEY,
            data BLOB NOT NULL,
            cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_online_cache_expires ON online_properties_cache(expires_at)')


def init_database() -> None:
    """
    Initialize unified database schema (queue, cache, and operation history).
    Creates skininfo_v1.db with all tables.
    """
    conn = get_connection(DB_PATH)
    cursor = conn.cursor()

    try:
        _create_base_schema(cursor)
        conn.commit()

    except Exception as e:
        conn.rollback()
        log("Database", f"Initialization failed: {str(e)}", xbmc.LOGERROR)
        raise
    finally:
        conn.close()


def vacuum_database() -> None:
    with get_db(DB_PATH) as (conn, cursor):
        cursor.execute('VACUUM')
