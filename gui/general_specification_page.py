"""
General specification — inputs from System Type through Adjacent access (per lift).
"""
from __future__ import annotations

import copy
import sys
import unicodedata
from typing import Any

from PyQt5.QtCore import QLocale
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator

from .lift_types import LOAD_CAPACITY_KG, LiftSystemType, permissible_persons_for_capacity
from .project_lift_schema import (
    KEY_GENERAL_SPECIFICATION,
    KEY_LAYOUT_INFORMATION,
    normalize_project_lift_data,
)

_MISSING = object()


def _general_spec_double_validator() -> QDoubleValidator:
    """Accept the same decimal forms as typical JSON (``.``) regardless of Windows locale."""
    v = QDoubleValidator()
    v.setLocale(QLocale(QLocale.English, QLocale.UnitedStates))
    v.setNotation(QDoubleValidator.StandardNotation)
    return v


def _line_edit_text_for_numeric_value(value: Any) -> str:
    """Normalize for ``QLineEdit`` + ``QDoubleValidator`` (comma decimals from JSON / Excel)."""
    s = str(value).strip() if value is not None else ''
    return s.replace(',', '.') if s else s


def _set_line_edit_text_bypassing_validator(widget: QLineEdit, text: str) -> None:
    """Programmatic load: validator can block ``setText`` for non-numeric strings."""
    v = widget.validator()
    widget.setValidator(None)
    widget.setText(text)
    widget.setValidator(v if v is not None else _general_spec_double_validator())

# Alternate keys sometimes found in older or hand-edited JSON (Unicode / spelling).
# Primary dict keys are canonical (no units in the key); legacy keys are migrated in
# ``gui.project_lift_schema.migrate_general_specification_dict``.
_GENERAL_SPEC_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    'Acceleration': (
        'Acceleration (m/s²)', 'Acceleration (m/s2)', 'Acceleration (m/s^2)',
    ),
    'Jerk': ('Jerk (m/s³)', 'Jerk (m/s3)', 'Jerk (m/s^3)'),
    'Access type': ('Acces type',),
    'Accessible rooms/cwt safety': (
        'Accesible rooms/cwt safety (y/n)',
        'Accessible rooms/cwt safety (y/n)',
    ),
}

# (json_key, description label, unit label). JSON uses ``json_key`` only — units are not part of the key.
GENERAL_SPEC_ROWS: tuple[tuple[str, str, str], ...] = (
    ('System Type', 'System Type', ''),
    ('System Category', 'System Category', ''),
    ('Code Basis', 'Code Basis', ''),
    ('Control / Group', 'Control / Group', ''),
    ('Counterweight location', 'Counterweight location', ''),
    ('Load capacity', 'Load capacity', 'kg'),
    ('Permissible number of persons', 'Permissible number of persons', 'Pers.'),
    ('Speed', 'Speed', 'm/s'),
    ('Acceleration', 'Acceleration', 'm/s²'),
    ('Jerk', 'Jerk', 'm/s³'),
    ('Travel height', 'Travel height', 'm'),
    ('Stops', 'Stops', 'Stck.'),
    ('Number of floors', 'Number of floors', 'Stck.'),
    ('Number of shaft doors', 'Number of shaft doors', 'Stck.'),
    ('Access type', 'Access type', ''),
    ('Accessible rooms/cwt safety', 'Accessible rooms / cwt safety', 'y/n'),
)


def _normalize_general_spec_key(s: str) -> str:
    """Unify Unicode so JSON keys match table labels (e.g. m/s² vs m/s2 after NFKC)."""
    t = unicodedata.normalize('NFKC', s)
    return t.strip()


class GeneralSpecificationPage(QWidget):
    next_clicked = pyqtSignal(dict)
    back_clicked = pyqtSignal()

    @staticmethod
    def _json_key_for_row(row: int) -> str:
        return GENERAL_SPEC_ROWS[row][0]

    def __init__(self, user_inputs):
        super().__init__()
        # Guard against re-entrant sync while the table is still being wired up. Creating the
        # cell widgets fires ``QLineEdit.textChanged`` / ``QComboBox.currentTextChanged`` for the
        # default values, which are connected to :meth:`_sync_lift_systems_to_user_inputs`. Without
        # the flag the very first ``setText`` (on the persons cell, via the load-combo default in
        # :meth:`add_lift_column`) triggers a sync that reads the blank-default widgets and
        # **overwrites** the just-loaded ``user_inputs['GeneralSpecification']`` with defaults —
        # so e.g. a saved ``Load capacity=2000`` silently becomes ``630`` on reopen.
        self._suppress_sync = True
        self.user_inputs = user_inputs
        normalize_project_lift_data(self.user_inputs)
        self.number_of_lifts = self._needed_lift_columns()
        self.initUI()

        try:
            # Always populate from ``GeneralSpecification`` (padded to column count). Do **not** branch on
            # ``if systems:`` — an empty list [] skipped populate and ran _sync, overwriting file-backed
            # values with default widgets (e.g. load 630 / persons 17).
            systems = copy.deepcopy(self.user_inputs.get(KEY_GENERAL_SPECIFICATION) or [])
            while len(systems) < self.number_of_lifts:
                systems.append({})
            while len(systems) > self.number_of_lifts:
                systems.pop()
            self.populate_from_input(systems)
            self._apply_general_spec_widgets_to_lift_systems_merge(systems)
            self.user_inputs[KEY_GENERAL_SPECIFICATION] = systems
        finally:
            self._suppress_sync = False

    def _sync_lift_systems_to_user_inputs(self):
        """Keep general-spec columns in ``user_inputs['GeneralSpecification']`` aligned with the table."""
        if getattr(self, '_suppress_sync', False):
            return
        existing = self.user_inputs.get(KEY_GENERAL_SPECIFICATION) or []
        systems_data = []
        for col in range(2, self.system_table.columnCount()):
            idx = col - 2
            merged = dict(existing[idx]) if idx < len(existing) else {}
            for row in range(self.system_table.rowCount()):
                json_key = self._json_key_for_row(row)
                cell_widget = self.system_table.cellWidget(row, col)
                if isinstance(cell_widget, QLineEdit):
                    value = cell_widget.text()
                elif isinstance(cell_widget, QComboBox):
                    value = cell_widget.currentText()
                else:
                    value = ''
                v = value.strip() if isinstance(value, str) else value
                if v != '':
                    merged[json_key] = value
                    continue
                if isinstance(cell_widget, QLineEdit):
                    stored = self._get_spec_value(merged, json_key)
                    if (
                        stored is not _MISSING
                        and stored not in (None, '')
                        and not cell_widget.isModified()
                    ):
                        merged[json_key] = stored
                        continue
                merged[json_key] = ''
            systems_data.append(merged)
        self.user_inputs[KEY_GENERAL_SPECIFICATION] = systems_data

    def _connect_cell_widget_sync(self, widget):
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(self._sync_lift_systems_to_user_inputs)
        elif isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(self._sync_lift_systems_to_user_inputs)

    def _needed_lift_columns(self) -> int:
        """Match table width to building lifts and/or saved general/layout lift entries."""
        b = len(self.user_inputs.get('BuildingSystems') or [])
        g = len(self.user_inputs.get(KEY_GENERAL_SPECIFICATION) or [])
        lay = len(self.user_inputs.get(KEY_LAYOUT_INFORMATION) or [])
        return max(b, g, lay, 1)

    @staticmethod
    def _get_spec_value(system_data: dict, json_key: str) -> Any:
        if json_key in system_data:
            return system_data[json_key]
        for alt in _GENERAL_SPEC_KEY_ALIASES.get(json_key, ()):
            if alt in system_data:
                return system_data[alt]
        nd = _normalize_general_spec_key(json_key)
        for k, v in system_data.items():
            if not isinstance(k, str):
                continue
            if _normalize_general_spec_key(k) == nd:
                return v
        for alt in _GENERAL_SPEC_KEY_ALIASES.get(json_key, ()):
            nad = _normalize_general_spec_key(alt)
            for k, v in system_data.items():
                if isinstance(k, str) and _normalize_general_spec_key(k) == nad:
                    return v
        return _MISSING

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: Any) -> None:
        s = str(value).strip() if value is not None else ''
        idx = combo.findText(s)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        swapped = s.replace('.', ',') if ',' not in s else s.replace(',', '.')
        if swapped != s:
            idx = combo.findText(swapped)
            if idx >= 0:
                combo.setCurrentIndex(idx)
                return
        combo.addItem(s)
        combo.setCurrentIndex(combo.count() - 1)

    def _ensure_lift_columns(self, n: int) -> None:
        """Add or remove data columns so the table matches ``n`` lifts."""
        data_cols = max(0, self.system_table.columnCount() - 2)
        while data_cols < n:
            self.add_lift_column()
            data_cols += 1
        while data_cols > n and self.system_table.columnCount() > 2:
            self.system_table.removeColumn(self.system_table.columnCount() - 1)
            data_cols -= 1

    def _apply_general_spec_widgets_to_lift_systems_merge(self, systems: list) -> None:
        """Copy general-spec widgets into ``systems`` without letting empty line edits wipe stored numbers.

        ``QDoubleValidator`` + locale can leave ``text()`` empty even when JSON has a value; a full
        :meth:`_sync_lift_systems_to_user_inputs` after :meth:`populate_from_input` would then replace
        good dict entries with ``""`` while the file on disk still has the old data.
        """
        for col in range(2, self.system_table.columnCount()):
            idx = col - 2
            while len(systems) <= idx:
                systems.append({})
            base = systems[idx]
            for row in range(self.system_table.rowCount()):
                json_key = self._json_key_for_row(row)
                cell_widget = self.system_table.cellWidget(row, col)
                if isinstance(cell_widget, QLineEdit):
                    v = cell_widget.text().strip()
                elif isinstance(cell_widget, QComboBox):
                    v = cell_widget.currentText().strip()
                else:
                    v = ''
                if v != '':
                    base[json_key] = v
                    continue
                stored = self._get_spec_value(base, json_key)
                if stored is not _MISSING and stored not in (None, ''):
                    base[json_key] = stored
                    continue
                base[json_key] = ''

    def refresh_from_project_data(self) -> None:
        """Re-read ``user_inputs['GeneralSpecification']`` into the table (e.g. after JSON load or re-entry)."""
        self._suppress_sync = True
        try:
            normalize_project_lift_data(self.user_inputs)
            self.number_of_lifts = self._needed_lift_columns()
            self._ensure_lift_columns(self.number_of_lifts)
            systems = copy.deepcopy(self.user_inputs.get(KEY_GENERAL_SPECIFICATION) or [])
            while len(systems) < self.number_of_lifts:
                systems.append({})
            while len(systems) > self.number_of_lifts:
                systems.pop()
            self.populate_from_input(systems)
            self._apply_general_spec_widgets_to_lift_systems_merge(systems)
            self.user_inputs[KEY_GENERAL_SPECIFICATION] = systems
        finally:
            self._suppress_sync = False

    def _apply_persons_for_load_column(self, col: int, load_text: str) -> None:
        """Row 21 persons from nominal load (kg) — Excel / VT standard table."""
        p = permissible_persons_for_capacity(load_text)
        if p is None:
            return
        w = self.system_table.cellWidget(6, col)
        if isinstance(w, QLineEdit):
            w.setText(p)

    def initUI(self):
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)

        scroll_layout = QVBoxLayout(scroll_widget)

        system_box = QGroupBox("General specification")
        system_box.setObjectName("general_spec_box")
        system_box.setStyleSheet(
            "#general_spec_box {background-color: white; border: 3px solid rgb(196, 214, 0); "
            "font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(system_box)

        system_layout = QVBoxLayout(system_box)

        self.system_table = QTableWidget()
        self.system_table.setColumnCount(2)
        self.system_table.setHorizontalHeaderLabels(['Description', 'Unit'])
        self.system_table.setRowCount(len(GENERAL_SPEC_ROWS))

        for row, (_jk, label, unit) in enumerate(GENERAL_SPEC_ROWS):
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.system_table.setItem(row, 0, item)
            u_item = QTableWidgetItem(unit if unit else '—')
            u_item.setFlags(u_item.flags() & ~Qt.ItemIsEditable)
            self.system_table.setItem(row, 1, u_item)

        self.system_table.horizontalHeader().setStretchLastSection(True)
        self.system_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.system_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.system_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        system_layout.addWidget(self.system_table)

        save_button = QPushButton('Save and Proceed')
        save_button.setStyleSheet("background-color: white;")
        save_button.clicked.connect(self.collect_data_and_go_next)
        nav_row = QHBoxLayout()
        back_button = QPushButton('← Back to previous page')
        back_button.setStyleSheet("background-color: white;")
        back_button.clicked.connect(self.back_clicked.emit)
        nav_row.addWidget(back_button)
        nav_row.addStretch()
        nav_row.addWidget(save_button)
        scroll_layout.addLayout(nav_row)

        self.initialize_lift_columns()

    def populate_from_input(self, systems_data):
        # Avoid textChanged → _sync_lift_systems_to_user_inputs while only some columns are filled.
        blocked = []
        for col in range(2, self.system_table.columnCount()):
            for row in range(self.system_table.rowCount()):
                w = self.system_table.cellWidget(row, col)
                if w is not None:
                    w.blockSignals(True)
                    blocked.append(w)
        try:
            for col, system_data in enumerate(systems_data, start=2):
                load_widget = self.system_table.cellWidget(5, col)
                for row in range(self.system_table.rowCount()):
                    json_key = self._json_key_for_row(row)
                    value = self._get_spec_value(system_data, json_key)
                    if value is _MISSING:
                        continue
                    if json_key == 'Accessible rooms/cwt safety' and isinstance(value, bool):
                        value = 'yes' if value else 'no'
                    cell_widget = self.system_table.cellWidget(row, col)
                    if isinstance(cell_widget, QLineEdit):
                        _set_line_edit_text_bypassing_validator(
                            cell_widget,
                            _line_edit_text_for_numeric_value(value),
                        )
                    elif isinstance(cell_widget, QComboBox):
                        self._set_combo_value(cell_widget, value)
                persons_w = self.system_table.cellWidget(6, col)
                if (
                    isinstance(persons_w, QLineEdit)
                    and not str(persons_w.text()).strip()
                    and isinstance(load_widget, QComboBox)
                ):
                    self._apply_persons_for_load_column(col, load_widget.currentText())
        finally:
            for w in blocked:
                w.blockSignals(False)

    def initialize_lift_columns(self):
        for _ in range(self.number_of_lifts):
            self.add_lift_column()

    def add_lift_column(self):
        col_position = self.system_table.columnCount()
        self.system_table.insertColumn(col_position)
        # Columns 0–1 are Description + Unit; first lift column is index 2 → label Lift 1.
        self.system_table.setHorizontalHeaderItem(
            col_position, QTableWidgetItem(f'Lift {col_position - 1}')
        )

        for row in range(self.system_table.rowCount()):
            if row == 0:
                widget = QComboBox()
                widget.addItems(list(LiftSystemType.ALL))
            elif row == 1:
                widget = QComboBox()
                widget.addItems(['Traction - MR', 'Traction - MRL', 'Hydraulic - MR', 'Hydraulic - MRL'])
            elif row == 2:
                widget = QComboBox()
                widget.addItems(['BS EN81'])
            elif row == 3:
                widget = QComboBox()
                widget.addItems(['Simplex', 'Duplex', 'Triplex', 'Quadplex'])
            elif row == 4:
                widget = QComboBox()
                widget.addItems(['CWT-Left', 'CWT-Right', 'CWT-Rear', 'no CWT'])
            elif row == 5:
                widget = QComboBox()
                widget.addItems([str(x) for x in LOAD_CAPACITY_KG])
                widget.currentTextChanged.connect(
                    lambda text, c=col_position: self._apply_persons_for_load_column(c, text)
                )
            elif row == 7:
                widget = QComboBox()
                widget.addItems(['1,00', '1,60', '2,00'])
            elif row == 14:
                widget = QComboBox()
                widget.addItems(['Front', 'Rear', 'Front + Rear', 'Front + Side', 'Front + Side + Rear'])
            elif row == 15:
                widget = QComboBox()
                widget.addItems(['yes', 'no'])
            else:
                widget = QLineEdit()
                widget.setValidator(_general_spec_double_validator())

            self.system_table.setCellWidget(row, col_position, widget)
            self._connect_cell_widget_sync(widget)

        load_w = self.system_table.cellWidget(5, col_position)
        if isinstance(load_w, QComboBox):
            self._apply_persons_for_load_column(col_position, load_w.currentText())

    def collect_data_and_go_next(self):
        self._sync_lift_systems_to_user_inputs()
        self.next_clicked.emit(self.user_inputs)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    sample = {
        'BuildingSystems': [{'Number': '1'}],
        'GeneralSpecification': [{'System Type': 'Passenger Lift'}],
    }
    w = GeneralSpecificationPage(sample)
    w.show()
    sys.exit(app.exec_())
