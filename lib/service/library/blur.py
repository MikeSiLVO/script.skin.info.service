"""Focus and audio player blur, plus the focused image's main color, each off-thread."""
from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Final, List, Optional

import xbmc

from lib.kodi.client import log
from lib.kodi.utilities import (
    LabelSnapshot, clear_prop, get_prop, gui_transition_settled, parse_pipe_list, set_prop,
    skin_bool,
)

_COLOR_PROP: Final = "SkinInfo.ImageColor.Main"
_COLOR_CACHE_SIZE: Final = 1000
_COLOR_SOURCE: Final = "ListItem.Art(poster)"
_VAR_TRIGGERS: Final = ("ListItem.DBID", "ListItem.DBType", "ListItem.Label",
                        "ListItem.FileNameAndPath", "Container.FolderPath", "System.CurrentWindow")


class BlurHandler:
    """Owns focus + player blur state and threads. Sets `SkinInfo.[prefix.]BlurredImage` props."""

    def __init__(self):
        self._focus_thread: Optional[threading.Thread] = None
        self._focus_last_source: Optional[str] = None
        self._player_thread: Optional[threading.Thread] = None
        self._player_last_source: Optional[str] = None
        self._player = xbmc.Player()
        self._warned_source = ""
        self._var_focus: Optional[tuple] = None
        self._var_source = ""

    @staticmethod
    def focus_labels() -> List[str]:
        """Infolabels the focus blur needs from the tick's batched read."""
        if get_prop("SkinInfo.BlurSourceVar"):
            return list(_VAR_TRIGGERS)
        return parse_pipe_list(get_prop("SkinInfo.BlurSource"))

    def handle_focus(self, labels: LabelSnapshot) -> None:
        """Handle a focus tick: blur the focused item's background."""
        if not skin_bool("SkinInfo.Blur"):
            if self._focus_last_source is not None:
                self._clear_props("SkinInfo.")
                self._focus_last_source = None
            return

        prefix = get_prop("SkinInfo.BlurPrefix")
        prop_base = f"SkinInfo.{prefix}." if prefix else "SkinInfo."

        self._process(
            setting="SkinInfo.Blur",
            source_property="SkinInfo.BlurSource",
            slot="focus",
            prop_base=prop_base,
            labels=labels,
        )

    def handle_player(self) -> None:
        """Run a blur pass for the playing audio's background, cleared once audio stops."""
        if not self._player.isPlayingAudio():
            if self._player_last_source is not None:
                self._clear_props("SkinInfo.Player.")
                self._player_last_source = None
            return

        current_file = xbmc.getInfoLabel("Player.Filenameandpath")

        self._process(
            setting="SkinInfo.Player.Blur",
            source_property="SkinInfo.Player.BlurSource",
            slot="player",
            prop_base="SkinInfo.Player.",
            cache_key_suffix=f"|{current_file}",
        )

    def _process(self, setting: str, source_property: str, slot: str, prop_base: str,
                 cache_key_suffix: str = "", labels: Optional[LabelSnapshot] = None) -> None:
        """Process one blur slot: start a blur of its resolved source, clearing when unset."""
        if not skin_bool(setting):
            if self._get_last(slot) is not None:
                self._clear_props(prop_base)
                self._set_last(slot, None)
            return

        blur_source_var = get_prop(source_property + "Var")
        if blur_source_var:
            var_path = self._resolve_var(blur_source_var, labels)
            if var_path is None:
                return
            source_path = var_path
        else:
            blur_source_infolabel = get_prop(source_property)
            if not blur_source_infolabel:
                if self._get_last(slot) is not None:
                    self._clear_props(prop_base)
                    self._set_last(slot, None)
                return

            if (blur_source_infolabel.startswith('$')
                    and blur_source_infolabel != self._warned_source):
                self._warned_source = blur_source_infolabel
                log("Blur",
                    f"{source_property} should not contain $INFO[], $VAR[], etc. "
                    f"Set raw infolabel instead. Got: {blur_source_infolabel}",
                    xbmc.LOGWARNING)

            source_path = self._resolve_with_fallbacks(
                blur_source_infolabel.split("|"), is_var=False, labels=labels
            )

        if not source_path:
            if self._get_last(slot) is not None:
                self._clear_props(prop_base)
                self._set_last(slot, None)
            return

        cache_key = f"{source_path}{cache_key_suffix}"
        if cache_key == self._get_last(slot):
            return

        existing_thread = self._get_thread(slot)
        if existing_thread is not None and existing_thread.is_alive():
            return

        self._set_last(slot, cache_key)
        new_thread = threading.Thread(
            target=self._worker,
            args=(source_path, prop_base, slot),
            daemon=True,
        )
        self._set_thread(slot, new_thread)
        new_thread.start()

    def _worker(self, source: str, prop_base: str, slot: str) -> None:
        """Blur one source off-thread and publish it, clearing the slot on failure."""
        try:
            from lib.infrastructure import blur

            blurred_path = blur.blur_image(source)

            if blurred_path:
                set_prop(f"{prop_base}BlurredImage", blurred_path)
                set_prop(f"{prop_base}BlurredImage.Original", source)
            else:
                self._clear_props(prop_base)

        except Exception as e:
            log("Blur", f"Failed to blur image: {e}", xbmc.LOGERROR)
            self._clear_props(prop_base)
            self._set_last(slot, None)
        finally:
            self._set_thread(slot, None)

    def _resolve_var(self, names: str, labels: Optional[LabelSnapshot]) -> Optional[str]:
        """Resolve skin variables, for the focus only once it moves; None while a window settles."""
        if labels is None:
            return self._resolve_with_fallbacks(names.split("|"), is_var=True)
        focus = (names, *(labels.get(label) for label in _VAR_TRIGGERS))
        if focus == self._var_focus:
            return self._var_source
        # a skin variable has no main-thread read
        if not gui_transition_settled():
            return None
        self._var_focus = focus
        self._var_source = self._resolve_with_fallbacks(names.split("|"), is_var=True)
        return self._var_source

    @staticmethod
    def _resolve_with_fallbacks(sources: List[str], is_var: bool,
                                labels: Optional[LabelSnapshot] = None) -> str:
        """Resolve the first non-empty source, reading plain labels from the batched read if any."""
        for source in sources:
            source = source.strip()
            if not source:
                continue
            if is_var:
                resolved = xbmc.getInfoLabel(f"$VAR[{source}]")
            elif labels is not None:
                resolved = labels.get(source)
            else:
                resolved = xbmc.getInfoLabel(source)
            if resolved:
                return resolved
        return ""

    @staticmethod
    def _clear_props(prop_base: str) -> None:
        """Clear a slot's blurred image properties."""
        clear_prop(f"{prop_base}BlurredImage")
        clear_prop(f"{prop_base}BlurredImage.Original")

    def _get_last(self, slot: str) -> Optional[str]:
        """Get the last blurred source for one slot."""
        return self._focus_last_source if slot == "focus" else self._player_last_source

    def _set_last(self, slot: str, value: Optional[str]) -> None:
        """Remember the last blurred source for one slot."""
        if slot == "focus":
            self._focus_last_source = value
        else:
            self._player_last_source = value

    def _get_thread(self, slot: str) -> Optional[threading.Thread]:
        """Get the thread running for one slot."""
        return self._focus_thread if slot == "focus" else self._player_thread

    def _set_thread(self, slot: str, thread: Optional[threading.Thread]) -> None:
        """Remember the running thread for one slot."""
        if slot == "focus":
            self._focus_thread = thread
        else:
            self._player_thread = thread


class ImageColorHandler:
    """Publisher of `SkinInfo.ImageColor.Main`, the main color of the focused item's image."""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._last_source: Optional[str] = None
        self._colors: "OrderedDict[str, str]" = OrderedDict()

    @staticmethod
    def focus_labels() -> List[str]:
        """Infolabels the color source names, for the tick's batched read."""
        return parse_pipe_list(get_prop("SkinInfo.ImageColorSource") or _COLOR_SOURCE)

    def handle_focus(self, labels: LabelSnapshot) -> None:
        """Handle a focus tick: publish the image's color, computing a new image's off-thread."""
        if not skin_bool("SkinInfo.ImageColor"):
            self._clear()
            return

        source = BlurHandler._resolve_with_fallbacks(self.focus_labels(), is_var=False,
                                                     labels=labels)
        if not source:
            self._clear()
            return
        if source == self._last_source:
            return

        color = self._colors.get(source)
        if color:
            self._last_source = source
            set_prop(_COLOR_PROP, color)
            return
        if self._thread is not None and self._thread.is_alive():
            return

        self._last_source = source
        self._thread = threading.Thread(target=self._worker, args=(source,), daemon=True)
        self._thread.start()

    def _worker(self, source: str) -> None:
        """Compute and remember one image's color, publishing it if still the latest requested."""
        try:
            from lib.infrastructure.blur import main_color
            color = main_color(source)
        except Exception as e:
            log("Blur", f"Failed to read image color: {e}", xbmc.LOGERROR)
            color = ""

        if color:
            self._colors[source] = color
            if len(self._colors) > _COLOR_CACHE_SIZE:
                self._colors.popitem(last=False)
        if source == self._last_source:
            set_prop(_COLOR_PROP, color)

    def _clear(self) -> None:
        """Clear the color once the feature is off or the item has no image."""
        if self._last_source is not None:
            clear_prop(_COLOR_PROP)
            self._last_source = None
