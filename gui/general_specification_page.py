"""
General specification — inputs from System Type through Adjacent access (per lift).
"""
from __future__ import annotations

import copy
import json
import sys
from typing import Any

from PyQt5.QtCore import QLocale
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox,
    QPlainTextEdit, QCheckBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator, QFont

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

# Alternate keys sometimes found in older or hand-edited JSON (Unicode / spelling).
_GENERAL_SPEC_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    'Acceleration (m/s²)': ('Acceleration (m/s2)', 'Acceleration (m/s^2)'),
    'Jerk (m/s³)': ('Jerk (m/s3)', 'Jerk (m/s^3)'),
    'Acces type': ('Access type',),
    'Accesible rooms/cwt safety (y/n)': ('Accessible rooms/cwt safety (y/n)',),
}


class GeneralSpecificationPage(QWidget):
    next_clicked = pyqtSignal(dict)
    back_clicked = pyqtSignal()

    GENERAL_DESCRIPTIONS = [
        'System Type',
        'System Category',
        'Code Basis',
        'Control / Group',
        'Counterweight location',
        'Load capacity (kg)',
        'Permissible number of persons (Pers.)',
        'Speed (m/s)',
        'Acceleration (m/s²)',
        'Jerk (m/s³)',
        'Travel height (m)',
        'Stops (Stck.)',
        'Number of floors (Stck.)',
        'Number of shaft doors (Stck.)',
        'Acces type', 
        'Accesible rooms/cwt safety (y/n)'
    ]

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        normalize_project_lift_data(self.user_inputs)
        self.number_of_lifts = self._needed_lift_columns()
        self.initUI()

        systems = copy.deepcopy(self.user_inputs.get(KEY_GENERAL_SPECIFICATION) or [])
        if systems:
            self.populate_from_input(systems)
            self._apply_general_spec_widgets_to_lift_systems_merge(systems)
            self.user_inputs[KEY_GENERAL_SPECIFICATION] = systems
        else:
            self._sync_lift_systems_to_user_inputs()

        self._update_json_debug_panel()

    def _sync_lift_systems_to_user_inputs(self):
        """Keep general-spec columns in ``user_inputs['GeneralSpecification']`` aligned with the table."""
        existing = self.user_inputs.get(KEY_GENERAL_SPECIFICATION) or []
        systems_data = []
        for col in range(1, self.system_table.columnCount()):
            idx = col - 1
            merged = dict(existing[idx]) if idx < len(existing) else {}
            for row in range(self.system_table.rowCount()):
                description = self.system_table.item(row, 0).text()
                cell_widget = self.system_table.cellWidget(row, col)
                if isinstance(cell_widget, QLineEdit):
                    value = cell_widget.text()
                elif isinstance(cell_widget, QComboBox):
                    value = cell_widget.currentText()
                else:
                    value = ''
                merged[description] = value
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
    def _get_spec_value(system_data: dict, description: str) -> Any:
        if description in system_data:
            return system_data[description]
        for alt in _GENERAL_SPEC_KEY_ALIASES.get(description, ()):
            if alt in system_data:
                return system_data[alt]
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
        data_cols = max(0, self.system_table.columnCount() - 1)
        while data_cols < n:
            self.add_lift_column()
            data_cols += 1
        while data_cols > n and self.system_table.columnCount() > 1:
            self.system_table.removeColumn(self.system_table.columnCount() - 1)
            data_cols -= 1

    def _apply_general_spec_widgets_to_lift_systems_merge(self, systems: list) -> None:
        """Copy general-spec widgets into ``systems`` without letting empty line edits wipe stored numbers.

        ``QDoubleValidator`` + locale can leave ``text()`` empty even when JSON has a value; a full
        :meth:`_sync_lift_systems_to_user_inputs` after :meth:`populate_from_input` would then replace
        good dict entries with ``""`` while the file on disk still has the old data.
        """
        for col in range(1, self.system_table.columnCount()):
            idx = col - 1
            while len(systems) <= idx:
                systems.append({})
            base = systems[idx]
            for row in range(self.system_table.rowCount()):
                description = self.system_table.item(row, 0).text()
                cell_widget = self.system_table.cellWidget(row, col)
                if isinstance(cell_widget, QLineEdit):
                    v = cell_widget.text().strip()
                elif isinstance(cell_widget, QComboBox):
                    v = cell_widget.currentText().strip()
                else:
                    v = ''
                if v != '':
                    base[description] = v
                    continue
                stored = base.get(description)
                if stored not in (None, ''):
                    continue
                base[description] = ''

    def refresh_from_project_data(self) -> None:
        """Re-read ``user_inputs['GeneralSpecification']`` into the table (e.g. after JSON load or re-entry)."""
        normalize_project_lift_data(self.user_inputs)
        self.number_of_lifts = self._needed_lift_columns()
        self._ensure_lift_columns(self.number_of_lifts)
        systems = copy.deepcopy(self.user_inputs.get(KEY_GENERAL_SPECIFICATION) or [])
        self.populate_from_input(systems)
        self._apply_general_spec_widgets_to_lift_systems_merge(systems)
        self.user_inputs[KEY_GENERAL_SPECIFICATION] = systems
        self._update_json_debug_panel()

    def _update_json_debug_panel(self) -> None:
        if getattr(self, '_json_debug_edit', None) is None:
            return
        raw = self.user_inputs.get(KEY_GENERAL_SPECIFICATION)
        text = json.dumps(raw, ensure_ascii=False, indent=2)
        self._json_debug_edit.setPlainText(
            text if raw is not None else '(no GeneralSpecification in project data)'
        )

    def _on_json_debug_toggled(self, checked: bool) -> None:
        if getattr(self, '_json_debug_edit', None) is not None:
            self._json_debug_edit.setVisible(checked)
        self._update_json_debug_panel()

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
        self.system_table.setColumnCount(1)
        self.system_table.setHorizontalHeaderLabels(['Description'])
        self.system_table.setRowCount(len(self.GENERAL_DESCRIPTIONS))

        for row, description in enumerate(self.GENERAL_DESCRIPTIONS):
            item = QTableWidgetItem(description)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.system_table.setItem(row, 0, item)

        self.system_table.horizontalHeader().setStretchLastSection(True)
        self.system_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.system_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

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

        dbg_header = QHBoxLayout()
        self._json_debug_checkbox = QCheckBox('Show JSON debug (GeneralSpecification in project data)')
        self._json_debug_checkbox.setChecked(False)
        self._json_debug_checkbox.toggled.connect(self._on_json_debug_toggled)
        dbg_header.addWidget(self._json_debug_checkbox)
        dbg_header.addStretch()
        scroll_layout.addLayout(dbg_header)

        self._json_debug_edit = QPlainTextEdit()
        self._json_debug_edit.setReadOnly(True)
        self._json_debug_edit.setVisible(False)
        mono = QFont('Consolas', 9)
        if not mono.exactMatch():
            mono = QFont('Courier New', 9)
        self._json_debug_edit.setFont(mono)
        self._json_debug_edit.setPlaceholderText(
            'Shows GeneralSpecification in the live project dict (what Save writes). '
            'Enable the checkbox to view.'
        )

        self._json_debug_edit.setMaximumHeight(160)
        scroll_layout.addWidget(self._json_debug_edit)

        self.initialize_lift_columns()

    def populate_from_input(self, systems_data):
        # Avoid textChanged → _sync_lift_systems_to_user_inputs while only some columns are filled.
        blocked = []
        for col in range(1, self.system_table.columnCount()):
            for row in range(self.system_table.rowCount()):
                w = self.system_table.cellWidget(row, col)
                if w is not None:
                    w.blockSignals(True)
                    blocked.append(w)
        try:
            for col, system_data in enumerate(systems_data, start=1):
                load_widget = self.system_table.cellWidget(5, col)
                for row in range(self.system_table.rowCount()):
                    description = self.system_table.item(row, 0).text()
                    value = self._get_spec_value(system_data, description)
                    if value is _MISSING:
                        continue
                    if (
                        description == 'Accesible rooms/cwt safety (y/n)'
                        and isinstance(value, bool)
                    ):
                        value = 'yes' if value else 'no'
                    cell_widget = self.system_table.cellWidget(row, col)
                    if isinstance(cell_widget, QLineEdit):
                        cell_widget.setText(_line_edit_text_for_numeric_value(value))
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
        self.system_table.setHorizontalHeaderItem(col_position, QTableWidgetItem(f'Lift {col_position}'))

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
