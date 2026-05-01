"""
Helpers for QLineEdit cells whose default value comes from a spreadsheet-style formula.

When the displayed text matches the current calculated value, the field uses the normal
background. When the user types a different value, the cell is highlighted (same amber
as :class:`~gui.override_combobox.OverrideComboBox`) and the tooltip explains why.
"""
from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import QLineEdit

from .override_combobox import OVERRIDE_HIGHLIGHT_CSS

FORMULA_OVERRIDE_QSS = f"QLineEdit {{ background-color: {OVERRIDE_HIGHLIGHT_CSS}; }}"

_TOOLTIP_OVERRIDE = "Manual value — differs from the calculated figure."


def values_equivalent_for_formula(current: str, computed: str) -> bool:
    """True if ``current`` should count as matching ``computed`` (numeric or plain string)."""
    a = (current or "").strip()
    b = (computed or "").strip()
    if a == b:
        return True
    if not a or not b:
        return False
    try:
        fa = float(a.replace(",", "."))
        fb = float(b.replace(",", "."))
        return abs(fa - fb) < 1e-9
    except ValueError:
        pass
    return a.casefold() == b.casefold()


def apply_formula_value(
    widget: QLineEdit,
    computed: Optional[str],
    *,
    base_style_sheet: str = "",
) -> None:
    """
    Apply the latest calculated string to a line edit without clobbering a manual override.

    If the user text matches the calculated value (including numeric equivalence), the cell
    is filled with the canonical ``computed`` text and shown with ``base_style_sheet`` (or
    default). If it differs, the existing text is kept and the override highlight is applied.
    """
    comp = (str(computed).strip() if computed is not None else "")
    cur = widget.text().strip()

    if not comp:
        if not cur:
            widget.setText("")
            _set_formula_style(widget, False, base_style_sheet)
        else:
            _set_formula_style(widget, True, base_style_sheet)
        return

    if not cur:
        widget.setText(comp)
        _set_formula_style(widget, False, base_style_sheet)
        return

    if values_equivalent_for_formula(cur, comp):
        widget.setText(comp)
        _set_formula_style(widget, False, base_style_sheet)
    else:
        _set_formula_style(widget, True, base_style_sheet)


def refresh_formula_style(widget: QLineEdit, computed: Optional[str], *, base_style_sheet: str = "") -> None:
    """Recompute override styling from current text and ``computed`` without changing text."""
    comp = (str(computed).strip() if computed is not None else "")
    cur = widget.text().strip()
    if not comp:
        _set_formula_style(widget, bool(cur), base_style_sheet)
        return
    if not cur:
        _set_formula_style(widget, False, base_style_sheet)
        return
    _set_formula_style(
        widget,
        not values_equivalent_for_formula(cur, comp),
        base_style_sheet,
    )


def _set_formula_style(widget: QLineEdit, is_override: bool, base_style_sheet: str) -> None:
    base = base_style_sheet or ""
    if is_override:
        widget.setStyleSheet(base + FORMULA_OVERRIDE_QSS)
        widget.setToolTip(_TOOLTIP_OVERRIDE)
    else:
        widget.setStyleSheet(base)
        widget.setToolTip("")


__all__ = [
    "FORMULA_OVERRIDE_QSS",
    "apply_formula_value",
    "refresh_formula_style",
    "values_equivalent_for_formula",
]
