"""
Shared UI + JSON helpers for optional custom parameter rows on wizard tables.

Each page stores an ordered list of {name, unit?} under a dedicated top-level JSON key
and persists values inside the same per-lift dicts / lists used by that page.
"""
from __future__ import annotations

from typing import (
    AbstractSet,
    Any,
    Callable,
    Dict,
    List,
    MutableMapping,
    Optional,
)

from PyQt5.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QTableWidget

# Top-level project JSON keys for custom-row definitions (ordered display names + units).
KEY_CUSTOM_BUILDING_SYSTEM = "BuildingSystemCustomParameters"
KEY_CUSTOM_GENERAL_SPEC = "GeneralSpecificationCustomParameters"
KEY_CUSTOM_LAYOUT = "LayoutInformationCustomParameters"
KEY_CUSTOM_LIFT_DRIVE = "LiftDriveCustomParameters"
KEY_CUSTOM_FORCES = "ForcesCustomParameters"
KEY_CUSTOM_COMPLIANCE = "ComplianceCustomParameters"
KEY_CUSTOM_EMERGENCY = "EmergencyCustomParameters"
KEY_CUSTOM_COST = "CostCustomParameters"


def make_add_row_button(
    on_click: Callable[[], None],
    tooltip: str = "Add a custom parameter row",
) -> QPushButton:
    btn = QPushButton("+")
    btn.setToolTip(tooltip)
    btn.setFixedWidth(36)
    btn.clicked.connect(on_click)
    return btn


def make_remove_row_button(
    on_click: Callable[[], None],
    tooltip: str = "Remove last custom parameter row",
) -> QPushButton:
    btn = QPushButton("-")
    btn.setToolTip(tooltip)
    btn.setFixedWidth(36)
    btn.clicked.connect(on_click)
    return btn


def add_plus_minus_button_row(
    layout,
    on_add: Callable[[], None],
    on_remove: Callable[[], None],
) -> tuple[QPushButton, QPushButton]:
    """Place ``+`` / ``-`` controls below a table (remove drops the last custom row)."""
    row = QHBoxLayout()
    btn_add = make_add_row_button(on_add)
    btn_remove = make_remove_row_button(on_remove)
    row.addWidget(btn_add)
    row.addWidget(btn_remove)
    row.addStretch()
    layout.addLayout(row)
    return btn_add, btn_remove


def normalize_meta_list(raw: Any) -> List[MutableMapping[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: List[MutableMapping[str, Any]] = []
    for x in raw:
        if isinstance(x, dict):
            nm = str(x.get("name", "") or "").strip()
            unit = str(x.get("unit", "") or "").strip()
            out.append({"name": nm, "unit": unit})
        elif isinstance(x, str):
            out.append({"name": x.strip(), "unit": ""})
    return out


def default_custom_name(used: AbstractSet[str]) -> str:
    n = 1
    while True:
        s = f"Custom parameter {n}"
        if s not in used:
            return s
        n += 1


def meta_from_table(
    table: QTableWidget,
    *,
    fixed_row_count: int,
    has_unit_column: bool,
) -> List[Dict[str, str]]:
    """Serialize custom rows (row >= fixed_row_count) to JSON-friendly dicts."""
    out: List[Dict[str, str]] = []
    for row in range(fixed_row_count, table.rowCount()):
        w0 = table.cellWidget(row, 0)
        if isinstance(w0, QLineEdit):
            name = w0.text().strip()
        else:
            it = table.item(row, 0)
            name = it.text().strip() if it is not None else ""
        unit = ""
        if has_unit_column:
            w1 = table.cellWidget(row, 1)
            if isinstance(w1, QLineEdit):
                unit = w1.text().strip()
            else:
                u_it = table.item(row, 1)
                unit = u_it.text().strip() if u_it is not None else ""
        out.append({"name": name, "unit": unit})
    return out


def clear_rows_from(table: QTableWidget, first_row_to_remove: int) -> None:
    while table.rowCount() > first_row_to_remove:
        table.removeRow(table.rowCount() - 1)


def append_custom_row_two_column_headers(
    table: QTableWidget,
    *,
    name: str,
    unit: str,
    first_data_col: int,
    fill_data_cell: Callable[[int, int], None],
    on_change: Optional[Callable[[], None]] = None,
) -> int:
    """Append row with editable name/unit in cols 0–1 and call ``fill_data_cell(row, col)`` for lift columns."""
    row = table.rowCount()
    table.insertRow(row)
    ne = QLineEdit(name)
    table.setCellWidget(row, 0, ne)
    ue = QLineEdit(unit)
    table.setCellWidget(row, 1, ue)
    if on_change is not None:
        ne.textChanged.connect(lambda *_: on_change())
        ue.textChanged.connect(lambda *_: on_change())
    for c in range(first_data_col, table.columnCount()):
        fill_data_cell(row, c)
    return row


def append_custom_row_single_description_column(
    table: QTableWidget,
    *,
    name: str,
    first_data_col: int,
    fill_data_cell: Callable[[int, int], None],
    on_change: Optional[Callable[[], None]] = None,
) -> int:
    """Building System style: only col0 is description (no unit column)."""
    row = table.rowCount()
    table.insertRow(row)
    ne = QLineEdit(name)
    table.setCellWidget(row, 0, ne)
    if on_change is not None:
        ne.textChanged.connect(lambda *_: on_change())
    for c in range(first_data_col, table.columnCount()):
        fill_data_cell(row, c)
    return row


def refill_data_cells_for_row(
    table: QTableWidget,
    row: int,
    first_data_col: int,
    fill_data_cell: Callable[[int, int], None],
) -> None:
    for c in range(first_data_col, table.columnCount()):
        table.removeCellWidget(row, c)
        fill_data_cell(row, c)
