"""
OverrideComboBox — an editable QComboBox that warns the user (via a yellow
background and a tooltip listing the standard options) whenever the current
text is not one of the items currently in the dropdown.

This is the shared building block behind the "any UI field can be overridden"
behaviour. Pages that used to instantiate ``QComboBox`` should create one of
these instead; existing ``addItems(...)`` / ``addItem(...)`` setup code works
unchanged.

Design note — the "standard" set is derived on-the-fly from the combo's current
items list (``itemText(0..count-1)``). That means every value ever added to
the dropdown — whether through a single ``addItems`` call, a loop of
``addItem`` calls, ``insertItem``, or ``set_standard_options`` — counts as a
standard option. Only free text that the user types (and that doesn't match
any existing item) triggers the override warning.

Widgets can optionally carry ``override_label`` (the schedule-template column-A
label this combo maps to) and ``override_lift_index`` (0-based lift slot) so the
VT Schedules export can highlight the corresponding cells in the workbook when
the value is non-standard.
"""
from __future__ import annotations

from typing import List, Sequence

from PyQt5.QtWidgets import QComboBox, QCompleter


# Amber / pastel yellow used both for the UI background and the Excel fill so
# the two visual signals match. Hex is #FFF2CC (warm, low-saturation yellow).
OVERRIDE_HIGHLIGHT_HEX: str = "FFF2CC"
OVERRIDE_HIGHLIGHT_CSS: str = f"#{OVERRIDE_HIGHLIGHT_HEX}"


class OverrideComboBox(QComboBox):
    """
    Editable combo box that visually flags non-standard values.

    Key behaviour:

    - ``setEditable(True)`` by default — users can type any text.
    - Every item currently in the dropdown (added via any API) is treated as a
      standard option. Only values that don't match any item (and aren't empty)
      are flagged.
    - When flagged, the widget paints its background amber and sets a tooltip
      listing the allowed values; ``is_override`` is ``True``.
    - ``override_label`` / ``override_lift_index`` are optional metadata used
      by the VT Schedules export to locate the matching template cell.
    """

    _OVERRIDE_STYLE_TEMPLATE = (
        "QComboBox {{ background-color: {bg}; }}"
        "QComboBox QAbstractItemView {{ background-color: white; }}"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_style_sheet: str = ""
        self.override_label: str = ""
        self.override_lift_index: int = -1

        self.setEditable(True)
        # Case-insensitive completion over the standard options to preserve the
        # convenient "type to pick" behaviour while still allowing free text.
        completer = self.completer()
        if completer is not None:
            completer.setCaseSensitivity(0)  # Qt.CaseInsensitive
            completer.setCompletionMode(QCompleter.PopupCompletion)

        self.currentTextChanged.connect(self._refresh_override_state)
        self.editTextChanged.connect(self._refresh_override_state)

    # ---- Item management hooks (keep override state in sync) -----------

    def addItems(self, texts: Sequence[str]) -> None:  # type: ignore[override]
        super().addItems(list(texts))
        self._refresh_override_state()

    def addItem(self, *args, **kwargs) -> None:  # type: ignore[override]
        super().addItem(*args, **kwargs)
        self._refresh_override_state()

    def insertItem(self, *args, **kwargs) -> None:  # type: ignore[override]
        super().insertItem(*args, **kwargs)
        self._refresh_override_state()

    def insertItems(self, *args, **kwargs) -> None:  # type: ignore[override]
        super().insertItems(*args, **kwargs)
        self._refresh_override_state()

    def clear(self) -> None:  # type: ignore[override]
        super().clear()
        self._refresh_override_state()

    def set_standard_options(self, options: Sequence[str]) -> None:
        """Replace the combo's dropdown items (which equals the standard set)."""
        self.blockSignals(True)
        try:
            super().clear()
            for o in options:
                super().addItem(str(o))
        finally:
            self.blockSignals(False)
        self._refresh_override_state()

    def standard_options(self) -> List[str]:
        """Snapshot of every item currently in the dropdown (the standard set)."""
        return [self.itemText(i) for i in range(self.count())]

    # ---- Override-state plumbing ---------------------------------------

    @staticmethod
    def _norm(value) -> str:
        return "" if value is None else " ".join(str(value).split()).lower()

    def _current_standard_set(self) -> set:
        return {self._norm(self.itemText(i)) for i in range(self.count())}

    @property
    def is_override(self) -> bool:
        """
        True only when the current text is non-empty *and* doesn't match any
        item in the dropdown. An empty combo (no items yet) never counts as
        overridden — it hasn't been populated with standards to compare to.
        """
        txt = self._norm(self.currentText())
        if not txt:
            return False
        items = self._current_standard_set()
        if not items:
            return False
        return txt not in items

    def set_base_style_sheet(self, style: str) -> None:
        """Set a base stylesheet that is always applied, even on top of the override highlight."""
        self._base_style_sheet = style or ""
        self._refresh_override_state()

    def _refresh_override_state(self, *_args) -> None:
        if self.is_override:
            self.setStyleSheet(
                self._base_style_sheet
                + self._OVERRIDE_STYLE_TEMPLATE.format(bg=OVERRIDE_HIGHLIGHT_CSS)
            )
            opts = self.standard_options()
            display = ", ".join(opts) if opts else "(none)"
            self.setToolTip(
                "Non-standard value.\n"
                f"Standard options: {display}"
            )
        else:
            self.setStyleSheet(self._base_style_sheet)
            self.setToolTip("")

    # ---- Metadata helpers used by the VT Schedules export --------------

    def set_override_context(self, label: str, lift_index: int) -> None:
        """
        Attach the schedule-template column-A label and 0-based lift index this
        combo represents. Used by the export to highlight the corresponding cell
        when the widget is in the override state. Safe to call multiple times.
        """
        self.override_label = label or ""
        self.override_lift_index = int(lift_index) if lift_index is not None else -1


__all__ = ["OverrideComboBox", "OVERRIDE_HIGHLIGHT_HEX", "OVERRIDE_HIGHLIGHT_CSS"]
