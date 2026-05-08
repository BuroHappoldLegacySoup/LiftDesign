from PyQt5.QtWidgets import (
    QApplication, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QScrollArea, QLineEdit,
)
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtCore import pyqtSignal, Qt
import copy
import sys

from .override_combobox import OverrideComboBox
from .project_lift_schema import LEGACY_EMERGENCY_KEY_TO_CANONICAL
from .custom_parameter_rows import (
    KEY_CUSTOM_EMERGENCY,
    add_plus_minus_button_row,
    append_custom_row_two_column_headers,
    clear_rows_from,
    default_custom_name,
    meta_from_table,
    normalize_meta_list,
)


class InterfacesPage(QWidget):
    next_clicked = pyqtSignal(dict)
    back_clicked = pyqtSignal()

    _YES_NO_ITEMS = ('', 'yes', 'no')
    _POWER_TYPE_ITEMS = ('', 'UPS', 'Generator')

    # Row indices — must match ``input_descriptions`` in ``initUI``
    _ROW_COMBO_YES_NO = frozenset(
        {2, 5, 6, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18}
    )
    _ROW_COMBO_POWER_TYPE = frozenset({7})
    _ROW_LINE_EDIT = frozenset({0, 1, 3, 4, 10, 19, 20})
    _ROW_LINE_EDIT_NUMERIC = frozenset({3, 4})

    # Older project keys → current JSON key (first match wins in populate)
    _POPULATE_ALIASES = {
        'other Security interfaces as per spec.': (
            'other Security interfaces as per spec (y/n)',
            'other Security interfaces as per spec. (y/n)',
        ),
    }

    # (json_key, label, unit)
    EMERGENCY_ROWS: tuple[tuple[str, str, str], ...] = (
        ('Smoke management type', 'Smoke management type', 'type'),
        ('Smoke extraction min. size netto', 'Smoke extraction min. size netto', 'mm²'),
        ('FAS interfaces as per spec', 'FAS interfaces as per spec', 'y/n'),
        ('Main evacuation floor fire return and EEL EN81-76', 'Main evacuation floor fire return and EEL EN81-76', 'floor no.'),
        ('Alternate evacuation floor', 'Alternate evacuation floor', 'floor no.'),
        ('Emergency power', 'Emergency power', 'y/n'),
        ('Cascading evacuation control', 'Cascading evacuation control', 'y/n'),
        ('Type of emergency power', 'Type of emergency power', 'type'),
        ('FCC panel interface as per spec', 'FCC panel interface as per spec', 'y/n'),
        ('2-way intercom firefighter lift', '2-way intercom firefighter lift', 'y/n'),
        ('self-rescue method firefighter lift', 'self-rescue method firefighter lift', 'type'),
        ('BMS interfaces as per spec', 'BMS interfaces as per spec', 'y/n'),
        ('lift monitoring', 'lift monitoring', 'y/n'),
        ('ICT/AV interfaces as per spec', 'ICT/AV interfaces as per spec', 'y/n'),
        ('In-car CCTV', 'In-car CCTV', '—'),
        ('Access Control interface as per spec', 'Access Control interface as per spec', 'y/n'),
        ('other Security interfaces as per spec.', 'other Security interfaces as per spec.', 'y/n'),
        ('PAVA alarm interface car', 'PAVA alarm interface car', 'y/n'),
        ('Sprinkler in shaft / Shunt trip', 'Sprinkler in shaft / Shunt trip', 'y/n'),
        ('Water management Firefighter and Evacuation lift', 'Water management Firefighter and Evacuation lift', 'type'),
        ('other functions', 'other functions', 'type'),
    )

    EMERGENCY_FIXED_KEYS = frozenset(r[0] for r in EMERGENCY_ROWS)

    def _emergency_json_key_for_row(self, row: int) -> str:
        if row < len(self.EMERGENCY_ROWS):
            return self.EMERGENCY_ROWS[row][0]
        w = self.interfaces_table.cellWidget(row, 0)
        return w.text().strip() if isinstance(w, QLineEdit) else ""

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs['BuildingSystems'])
        self.initUI()

        emergency = copy.deepcopy(self.user_inputs.get('Emergency') or [])
        while len(emergency) < self.number_of_lifts:
            emergency.append({})
        while len(emergency) > self.number_of_lifts:
            emergency.pop()
        self._rebuild_custom_emergency_rows(emergency)
        self.populate_from_input(emergency)

    @staticmethod
    def _choice_combo(items: tuple[str, ...]) -> QComboBox:
        w = OverrideComboBox()
        w.setInsertPolicy(QComboBox.NoInsert)
        w.set_base_style_sheet("QComboBox { combobox-popup: 0; }")
        w.addItems(list(items))
        return w

    def initUI(self):
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)

        scroll_layout = QVBoxLayout(scroll_widget)

        interfaces_box = QGroupBox("Technical Interfaces")
        interfaces_box.setObjectName("interfaces_box")
        interfaces_box.setStyleSheet(
            "#interfaces_box {background-color: white; border: 3px solid rgb(196, 214, 0); font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(interfaces_box)

        interfaces_layout = QVBoxLayout(interfaces_box)

        self.interfaces_table = QTableWidget()
        self.interfaces_table.setColumnCount(2)
        self.interfaces_table.setHorizontalHeaderLabels(['Description', 'Unit'])

        self.interfaces_table.setRowCount(len(self.EMERGENCY_ROWS))

        for row, (_jk, label, unit) in enumerate(self.EMERGENCY_ROWS):
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.interfaces_table.setItem(row, 0, item)
            u_item = QTableWidgetItem(unit if unit else '—')
            u_item.setFlags(u_item.flags() & ~Qt.ItemIsEditable)
            self.interfaces_table.setItem(row, 1, u_item)

        self.interfaces_table.horizontalHeader().setStretchLastSection(True)
        self.interfaces_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.interfaces_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.interfaces_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        interfaces_layout.addWidget(self.interfaces_table)
        add_plus_minus_button_row(
            interfaces_layout,
            self._on_add_custom_parameter_row,
            self._on_remove_custom_parameter_row,
        )

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

    def initialize_lift_columns(self):
        for _ in range(self.number_of_lifts):
            self.add_lift_column()

    def add_lift_column(self):
        col_position = self.interfaces_table.columnCount()
        self.interfaces_table.insertColumn(col_position)
        self.interfaces_table.setHorizontalHeaderItem(
            col_position, QTableWidgetItem(f'Lift {col_position - 1}')
        )

        for row in range(len(self.EMERGENCY_ROWS)):
            if row in self._ROW_COMBO_YES_NO:
                w = self._choice_combo(self._YES_NO_ITEMS)
                w.set_override_context(self.EMERGENCY_ROWS[row][1], col_position - 2)
            elif row in self._ROW_COMBO_POWER_TYPE:
                w = self._choice_combo(self._POWER_TYPE_ITEMS)
                w.set_override_context(self.EMERGENCY_ROWS[row][1], col_position - 2)
            elif row in self._ROW_LINE_EDIT:
                w = QLineEdit()
                if row in self._ROW_LINE_EDIT_NUMERIC:
                    w.setValidator(QDoubleValidator())
            else:
                w = QLineEdit()
            self.interfaces_table.setCellWidget(row, col_position, w)

        for row in range(len(self.EMERGENCY_ROWS), self.interfaces_table.rowCount()):
            self._fill_custom_emergency_cell(row, col_position)

    def _infer_emergency_custom_meta(self, emergency_list: list) -> list:
        meta = normalize_meta_list(self.user_inputs.get(KEY_CUSTOM_EMERGENCY))
        if meta:
            return meta
        ordered: list[str] = []
        seen: set[str] = set()
        for entry in emergency_list:
            if not isinstance(entry, dict):
                continue
            for k in entry:
                if k in self.EMERGENCY_FIXED_KEYS or k in seen:
                    continue
                seen.add(k)
                ordered.append(k)
        return [{"name": k, "unit": ""} for k in ordered]

    def _fill_custom_emergency_cell(self, row: int, col: int) -> None:
        w = QLineEdit()
        self.interfaces_table.setCellWidget(row, col, w)

    def _rebuild_custom_emergency_rows(self, emergency_list: list) -> None:
        clear_rows_from(self.interfaces_table, len(self.EMERGENCY_ROWS))
        meta = self._infer_emergency_custom_meta(emergency_list)
        used: set[str] = set()
        for entry in meta:
            raw_name = str(entry.get("name", "") or "").strip()
            unit = str(entry.get("unit", "") or "").strip()
            name = raw_name if raw_name else default_custom_name(used)
            used.add(name)
            append_custom_row_two_column_headers(
                self.interfaces_table,
                name=name,
                unit=unit,
                first_data_col=2,
                fill_data_cell=self._fill_custom_emergency_cell,
            )

    def _on_add_custom_parameter_row(self) -> None:
        used: set[str] = set()
        for r in range(len(self.EMERGENCY_ROWS), self.interfaces_table.rowCount()):
            w = self.interfaces_table.cellWidget(r, 0)
            if isinstance(w, QLineEdit) and w.text().strip():
                used.add(w.text().strip())
        name = default_custom_name(used)
        append_custom_row_two_column_headers(
            self.interfaces_table,
            name=name,
            unit="",
            first_data_col=2,
            fill_data_cell=self._fill_custom_emergency_cell,
        )

    def _on_remove_custom_parameter_row(self) -> None:
        if self.interfaces_table.rowCount() <= len(self.EMERGENCY_ROWS):
            return
        self.interfaces_table.removeRow(self.interfaces_table.rowCount() - 1)
        self.sync_emergency_to_user_inputs()

    @staticmethod
    def _combo_in_cell(cell_widget):
        if isinstance(cell_widget, QComboBox):
            return cell_widget
        return None

    def _value_for_description(self, emergency_entry: dict, json_key: str):
        if json_key in emergency_entry:
            return emergency_entry[json_key]
        for canon, aliases in self._POPULATE_ALIASES.items():
            if json_key == canon:
                for a in aliases:
                    if a in emergency_entry:
                        return emergency_entry[a]
        for old_k, new_k in LEGACY_EMERGENCY_KEY_TO_CANONICAL.items():
            if new_k == json_key and old_k in emergency_entry:
                return emergency_entry[old_k]
        return None

    @staticmethod
    def _set_yes_no_combo(combo: QComboBox, value) -> None:
        if isinstance(value, bool):
            text = 'yes' if value else 'no'
        else:
            text = str(value).strip() if value is not None else ''
        if not text:
            combo.setCurrentIndex(0)
            return
        idx = combo.findText(text)
        if idx < 0:
            low = text.lower()
            if low in ('yes', 'no'):
                idx = combo.findText(low)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    @staticmethod
    def _set_power_type_combo(combo: QComboBox, value) -> None:
        text = str(value).strip() if value is not None else ''
        if not text:
            combo.setCurrentIndex(0)
            return
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        # Legacy: single-option combo or other labels
        low = text.lower()
        if 'ups' in low:
            i = combo.findText('UPS')
            if i >= 0:
                combo.setCurrentIndex(i)
        elif 'generat' in low or text == 'Generator':
            i = combo.findText('Generator')
            if i >= 0:
                combo.setCurrentIndex(i)

    def populate_from_input(self, emergency_data):
        for col, emergency_entry in enumerate(emergency_data, start=2):
            for row in range(len(self.EMERGENCY_ROWS)):
                jk = self.EMERGENCY_ROWS[row][0]
                value = self._value_for_description(emergency_entry, jk)
                if value is None:
                    continue
                cell_widget = self.interfaces_table.cellWidget(row, col)

                if row in self._ROW_COMBO_YES_NO:
                    cb = self._combo_in_cell(cell_widget)
                    if cb is not None:
                        self._set_yes_no_combo(cb, value)
                elif row in self._ROW_COMBO_POWER_TYPE:
                    cb = self._combo_in_cell(cell_widget)
                    if cb is not None:
                        self._set_power_type_combo(cb, value)
                elif isinstance(cell_widget, QLineEdit):
                    cell_widget.setText(str(value))
            for row in range(len(self.EMERGENCY_ROWS), self.interfaces_table.rowCount()):
                jk = self._emergency_json_key_for_row(row)
                if not jk:
                    continue
                value = self._value_for_description(emergency_entry, jk)
                if value is None:
                    continue
                cell_widget = self.interfaces_table.cellWidget(row, col)
                if isinstance(cell_widget, QLineEdit):
                    cell_widget.setText(str(value))

    def sync_emergency_to_user_inputs(self):
        """Write technical interfaces table into ``user_inputs``."""
        emergency_data = []
        for col in range(2, self.interfaces_table.columnCount()):
            emergency_entry = {}
            for row in range(self.interfaces_table.rowCount()):
                jk = self._emergency_json_key_for_row(row)
                if not jk:
                    continue
                cell_widget = self.interfaces_table.cellWidget(row, col)

                if row < len(self.EMERGENCY_ROWS) and (
                    row in self._ROW_COMBO_YES_NO or row in self._ROW_COMBO_POWER_TYPE
                ):
                    cb = self._combo_in_cell(cell_widget)
                    value = cb.currentText() if cb is not None else ''
                elif isinstance(cell_widget, QLineEdit):
                    value = cell_widget.text()
                else:
                    value = ''

                emergency_entry[jk] = value

            emergency_data.append(emergency_entry)

        self.user_inputs['Emergency'] = emergency_data
        self.user_inputs[KEY_CUSTOM_EMERGENCY] = meta_from_table(
            self.interfaces_table,
            fixed_row_count=len(self.EMERGENCY_ROWS),
            has_unit_column=True,
        )

    def collect_data_and_go_next(self):
        self.sync_emergency_to_user_inputs()
        self.next_clicked.emit(self.user_inputs)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    user_inputs = {
        'BuildingSystems': [{'Number': '1'}, {'Number': '2'}],
        'Emergency': [],
    }
    window = InterfacesPage(user_inputs)
    window.show()
    sys.exit(app.exec_())
