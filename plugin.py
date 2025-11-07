"""Plugin entry point for on-demand DBID queries.

Returns list items for use in containers.
"""
from __future__ import annotations

import sys
from urllib.parse import parse_qs
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib.dbid_query import get_item_data_by_dbid


def main() -> None:
    """
    Plugin entry point for querying media details by DBID.
    Returns a single ListItem with all properties set.
    """

    addon_id = xbmcaddon.Addon().getAddonInfo("id")
    handle = int(sys.argv[1])

    # Parse plugin URL parameters
    if len(sys.argv) < 3:
        xbmc.log(f"{addon_id}: Plugin called with insufficient arguments", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    # sys.argv[2] is the query string
    query_string = sys.argv[2]
    if not query_string or query_string == "?":
        xbmc.log(f"{addon_id}: No query parameters provided", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    # Remove leading '?' if present
    if query_string.startswith("?"):
        query_string = query_string[1:]

    # Parse query parameters
    params = parse_qs(query_string)

    # Get parameters (parse_qs returns lists, so get first item)
    dbid = params.get("dbid", [""])[0]
    media_type = params.get("type", [""])[0]

    # Validate and sanitize DBID
    if not dbid:
        xbmc.log(f"{addon_id}: Missing required parameter 'dbid'", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    # Ensure DBID is a valid integer
    try:
        dbid = int(dbid)
        if dbid <= 0:
            raise ValueError("DBID must be positive")
    except (ValueError, TypeError) as e:
        xbmc.log(f"{addon_id}: Invalid DBID '{dbid}': {str(e)}", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    # Validate media type
    if not media_type:
        xbmc.log(f"{addon_id}: Missing required parameter 'type'", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    # Sanitize and validate media type (prevent injection, normalize)
    media_type = media_type.lower().strip()
    valid_types = ("movie", "tvshow", "season", "episode", "musicvideo", "artist", "album", "set")

    if media_type not in valid_types:
        xbmc.log(
            f"{addon_id}: Invalid media type '{media_type}', expected one of: {', '.join(valid_types)}",
            xbmc.LOGWARNING
        )
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    # Additional validation: Check max reasonable DBID value
    MAX_DBID = 999999
    if dbid > MAX_DBID:
        xbmc.log(f"{addon_id}: DBID {dbid} exceeds maximum reasonable value", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    # Log the query
    xbmc.log(
        f"{addon_id}: Querying {media_type} with DBID {dbid}",
        xbmc.LOGDEBUG
    )

    # Get the data (convert dbid back to string for compatibility with existing code)
    item_data = get_item_data_by_dbid(media_type, str(dbid))

    if not item_data:
        xbmc.log(f"{addon_id}: No data returned for {media_type} {dbid}", xbmc.LOGWARNING)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return

    # Create a ListItem
    list_item = xbmcgui.ListItem(label=item_data.get("Title", ""))

    # Set all properties and extract art in single loop for performance
    art_dict = {}
    for key, value in item_data.items():
        if value:  # Only process non-empty values
            if key.startswith("Art."):
                # Extract art type and add to art dict
                art_type = key.replace("Art.", "").lower()
                art_dict[art_type] = value
            else:
                # Set regular property
                list_item.setProperty(key, str(value))

    if art_dict:
        list_item.setArt(art_dict)

    # Add the item to the directory
    xbmcplugin.addDirectoryItem(handle, "", list_item, isFolder=False)
    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)


if __name__ == "__main__":
    main()
