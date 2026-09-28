"""Blur orchestration: focus blur and audio player blur, both async-threaded."""
from __future__ import annotations

import threading
from typing import List, Optional

import xbmc

from lib.kodi.client import log
from lib.kodi.utilities import set_prop, clear_prop, get_prop, skin_bool


class BlurHandler:
    """Owns focus + player blur state and threads. Sets `SkinInfo.[prefix.]BlurredImage` props."""

    def __init__(self):
        self._focus_thread: Optional[threading.Thread] = None
        self._focus_last_source: Optional[str] = None
        self._player_thread: Optional[threading.Thread] = None
        self._player_last_source: Optional[str] = None
        self._player = xbmc.Player()
        self._warned_source = ""

    def handle_focus(self) -> None:
        """Run a blur pass for the focused item's background."""
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

    def _process(self, setting: str, source_property: str, slot: str,
                 prop_base: str, cache_key_suffix: str = "") -> None:
        """Resolve one blur slot's source and publish its blurred art, clearing when unset."""
        if not skin_bool(setting):
            if self._get_last(slot) is not None:
                self._clear_props(prop_base)
                self._set_last(slot, None)
            return

        blur_source_var = get_prop(source_property + "Var")
        if blur_source_var:
            source_path = self._resolve_with_fallbacks(blur_source_var.split("|"), is_var=True)
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
                blur_source_infolabel.split("|"), is_var=False
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

    @staticmethod
    def _resolve_with_fallbacks(sources: List[str], is_var: bool) -> str:
        """Resolve the first source that gives a non-empty infolabel."""
        for source in sources:
            source = source.strip()
            if not source:
                continue
            resolved = xbmc.getInfoLabel(f"$VAR[{source}]") if is_var else xbmc.getInfoLabel(source)
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
