from __future__ import annotations

from typing import Dict, List, Sequence
import xbmcgui


_CLOSE_ACTIONS = (
    xbmcgui.ACTION_NAV_BACK,
    xbmcgui.ACTION_PREVIOUS_MENU,
    92, 216, 247, 257, 275, 61467, 61448,
)


class DialogBase(xbmcgui.WindowXMLDialog):

    def set_properties(self, props: Dict[str, str]) -> None:
        for key, value in props.items():
            if value:
                self.setProperty(key, str(value))

    def clear_properties(self, keys: Sequence[str]) -> None:
        for key in keys:
            self.clearProperty(key)

    def populate_list(
        self, control_id: int, items: List[xbmcgui.ListItem]
    ) -> None:
        try:
            control: xbmcgui.ControlList = self.getControl(control_id)  # type: ignore[assignment]
        except Exception:
            return
        control.reset()
        if items:
            control.addItems(items)  # type: ignore[arg-type]

    def safe_focus(self, control_id: int) -> bool:
        try:
            self.setFocusId(control_id)
            return True
        except Exception:
            return False

    def is_close_action(self, action: xbmcgui.Action) -> bool:
        return action.getId() in _CLOSE_ACTIONS
