"""Window property manipulation utilities for skin integration."""
import xbmc


def copy_container_item(container, infolabels='', artwork='', prefix='', window='home'):
    """
    Copy container item properties to window properties.

    Allows access to selected item info outside the container context.

    Sets properties as:
    - SkinInfo.Selected.{label} or SkinInfo.Selected.{prefix}.{label} (no prefix/with prefix)
    - SkinInfo.Selected.Art({type}) or SkinInfo.Selected.{prefix}.Art({type})

    Args:
        container: Container ID or focus target
        infolabels: Pipe-separated list of infolabels to copy (e.g., "Title|Year|Rating")
        artwork: Pipe-separated list of art types to copy (e.g., "poster|fanart|clearlogo")
        prefix: Optional property suffix (default '', creates SkinInfo.Selected.*)
        window: Target window name or ID (default 'home')
    """
    if not container:
        return

    container_prefix = f'Container({container}).ListItem'
    prop_base = f'SkinInfo.Selected.{prefix}' if prefix else 'SkinInfo.Selected'

    if infolabels:
        labels = [label.strip() for label in infolabels.split('|') if label.strip()]
        for label in labels:
            value = xbmc.getInfoLabel(f'{container_prefix}.{label}')
            prop_name = f'{prop_base}.{label}'
            if value:
                xbmc.executebuiltin(f'SetProperty({prop_name},{value},{window})')
            else:
                xbmc.executebuiltin(f'ClearProperty({prop_name},{window})')

    if artwork:
        art_types = [art.strip() for art in artwork.split('|') if art.strip()]
        for art_type in art_types:
            value = xbmc.getInfoLabel(f'{container_prefix}.Art({art_type})')
            prop_name = f'{prop_base}.Art({art_type})'
            if value:
                xbmc.executebuiltin(f'SetProperty({prop_name},{value},{window})')
            else:
                xbmc.executebuiltin(f'ClearProperty({prop_name},{window})')


def aggregate_container_labels(container, infolabel, separator=' / ', prefix='SkinInfo', window='home'):
    """
    Aggregate an infolabel from all items in a container.

    Useful for collecting unique values across a container (e.g., all genres, all studios).

    Sets property as: {prefix}.{infolabel}s = aggregated_value
    Example: SkinInfo.Genres = "Action / Comedy / Drama"

    Args:
        container: Container ID
        infolabel: InfoLabel to aggregate from each item (e.g., "Genre", "Studio")
        separator: String to join values with (default ' / ')
        prefix: Property prefix (default 'SkinInfo')
        window: Target window name or ID (default 'home')
    """
    if not container or not infolabel:
        return

    num_items_str = xbmc.getInfoLabel(f'Container({container}).NumItems')
    try:
        num_items = int(num_items_str) if num_items_str else 0
    except (ValueError, TypeError):
        num_items = 0

    if num_items == 0:
        xbmc.executebuiltin(f'SetProperty({prefix}.{infolabel}s,,{window})')
        return

    values = []
    seen = set()

    for i in range(num_items):
        value = xbmc.getInfoLabel(f'Container({container}).ListItem({i}).{infolabel}')
        if value and value not in seen:
            values.append(value)
            seen.add(value)

    aggregated = separator.join(values) if values else ''
    prop_name = f'{prefix}.{infolabel}s'
    xbmc.executebuiltin(f'SetProperty({prop_name},{aggregated},{window})')


def refresh_counter(uid, prefix='SkinInfo'):
    """
    Increment a counter property for widget refresh triggers.

    Gets current value of {prefix}.{uid}, increments it, and sets it back.
    Useful for triggering widget refreshes via URL parameters.

    Args:
        uid: Unique identifier for this counter
        prefix: Property prefix (default 'SkinInfo')
    """
    window = 'home'
    prop_name = f'{prefix}.{uid}'
    current = xbmc.getInfoLabel(f'Window({window}).Property({prop_name})')

    try:
        value = int(current) if current else 0
    except (ValueError, TypeError):
        value = 0

    value += 1

    xbmc.executebuiltin(f'SetProperty({prop_name},{value},{window})')
