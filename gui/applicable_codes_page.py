from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGridLayout, QGroupBox, QPushButton, QCheckBox, QComboBox,
    QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QHBoxLayout, QLineEdit,
)
from PyQt5.QtCore import pyqtSignal, Qt
import sys

from .override_combobox import OverrideComboBox
from .custom_parameter_rows import (
    KEY_CUSTOM_COMPLIANCE,
    add_plus_minus_button_row,
    append_custom_row_two_column_headers,
    clear_rows_from,
    default_custom_name,
    meta_from_table,
    normalize_meta_list,
)
import copy


class ApplicableCodesPage(QWidget):
    next_clicked = pyqtSignal(dict)
    back_clicked = pyqtSignal()

    CODE_ROW_DESCRIPTIONS = (
        'EN81-28 emergency call',
        'EN81-70 Accessibility',
        'DIN EN17210 / 18040-1 Accessibility',
        'EN81-71 Vandalism category',
        'EN81-72 Firefighter elevator',
        'EN81-73 Fire emergency return',
        'EN81-76 Emergency Evacuation type',
        'EN81-76 Evacuation functions',
        'EN81-77 Seismic category',
        'EN81-58 Fire rated landing doors',
        'EN81-58 Fire rating class',
        'Green building certification compliance',
    )
    CODE_FIXED_KEYS = frozenset(CODE_ROW_DESCRIPTIONS)

    # Row indices — must match ``CODE_ROW_DESCRIPTIONS`` order in ``initUI``
    ROW_VANDALISM = 3
    ROW_FIRE_EMERGENCY_RETURN = 5
    ROW_EVACUATION_TYPE = 6
    ROW_EVACUATION_FUNCTIONS = 7
    ROW_SEISMIC = 8
    ROW_FIRE_RATING_CLASS = 10
    ROW_GREEN_BUILDING = 11

    _CHECKBOX_ROWS = frozenset(
        {0, 1, 2, 4, 5, 9}
    )  # emergency call, accessibilities, firefighter, fire return, fire doors (checkboxes)

    _COMBO_ROWS = frozenset({
        ROW_VANDALISM,
        ROW_EVACUATION_TYPE,
        ROW_EVACUATION_FUNCTIONS,
        ROW_SEISMIC,
    })

    # Green building row — one checkbox per scheme; stored in JSON as
    # ``{ "BREEAM": bool, "LEED": bool, ... }`` (or legacy string / list).
    GREEN_BUILDING_SCHEMES: tuple[str, ...] = ("BREEAM", "LEED", "DGNB", "NABERS")

    def _compliance_row_description(self, row: int) -> str:
        if row < len(self.CODE_ROW_DESCRIPTIONS):
            it = self.codes_table.item(row, 0)
            return it.text().strip() if it is not None else ''
        w = self.codes_table.cellWidget(row, 0)
        return w.text().strip() if isinstance(w, QLineEdit) else ''

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs['BuildingSystems'])
        self.initUI()

        comp = copy.deepcopy(self.user_inputs.get('Compliance') or [])
        while len(comp) < self.number_of_lifts:
            comp.append({})
        while len(comp) > self.number_of_lifts:
            comp.pop()
        self._rebuild_custom_compliance_rows(comp)
        self.populate_from_input(comp)

    def initUI(self):
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)

        scroll_layout = QVBoxLayout(scroll_widget)

        codes_box = QGroupBox("Applicable codes")
        codes_box.setObjectName("applicable_codes_box")
        codes_box.setStyleSheet(
            "#applicable_codes_box {background-color: white; border: 3px solid rgb(196, 214, 0); font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(codes_box)

        codes_layout = QVBoxLayout(codes_box)

        self.codes_table = QTableWidget()
        self.codes_table.setColumnCount(2)
        self.codes_table.setHorizontalHeaderLabels(['Description', 'Unit'])

        self.codes_table.setRowCount(len(self.CODE_ROW_DESCRIPTIONS))

        for row, description in enumerate(self.CODE_ROW_DESCRIPTIONS):
            item = QTableWidgetItem(description)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.codes_table.setItem(row, 0, item)
            u_item = QTableWidgetItem('—')
            u_item.setFlags(u_item.flags() & ~Qt.ItemIsEditable)
            self.codes_table.setItem(row, 1, u_item)

        self.codes_table.horizontalHeader().setStretchLastSection(True)
        self.codes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.codes_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.codes_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        codes_layout.addWidget(self.codes_table)
        add_plus_minus_button_row(
            codes_layout,
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

    @staticmethod
    def _wrap_centered(inner: QWidget) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.addStretch()
        h.addWidget(inner)
        h.addStretch()
        h.setContentsMargins(0, 0, 0, 0)
        return w

    def _make_combo(self, items: list[str]) -> QComboBox:
        cb = OverrideComboBox()
        cb.setInsertPolicy(QComboBox.NoInsert)
        cb.addItems(list(items))
        return cb

    def _make_green_building_widget(self) -> QWidget:
        """Four certification schemes as checkboxes in a 2×2 grid."""
        outer = QWidget()
        grid = QGridLayout(outer)
        grid.setContentsMargins(0, 0, 0, 0)
        for i, name in enumerate(self.GREEN_BUILDING_SCHEMES):
            cb = QCheckBox(name)
            cb.setObjectName(name)
            grid.addWidget(cb, i // 2, i % 2)
        return outer

    def initialize_lift_columns(self):
        for _ in range(self.number_of_lifts):
            self.add_lift_column()

    def add_lift_column(self):
        col_position = self.codes_table.columnCount()
        self.codes_table.insertColumn(col_position)
        self.codes_table.setHorizontalHeaderItem(
            col_position, QTableWidgetItem(f'Lift {col_position - 1}')
        )

        row_label_item = self.codes_table.item
        for row in range(self.codes_table.rowCount()):
            combo: OverrideComboBox | None = None
            if row == self.ROW_VANDALISM:
                combo = self._make_combo(['0', '1', '2', '3'])
                w = self._wrap_centered(combo)
            elif row == self.ROW_EVACUATION_TYPE:
                combo = self._make_combo(['no', 'yes, TYPE A', 'yes, TYPE B'])
                w = self._wrap_centered(combo)
            elif row == self.ROW_EVACUATION_FUNCTIONS:
                combo = self._make_combo(['Automatic', 'Remote', 'Assisted'])
                w = self._wrap_centered(combo)
            elif row == self.ROW_SEISMIC:
                combo = self._make_combo(['0', '1', '2', '3'])
                w = self._wrap_centered(combo)
            elif row == self.ROW_GREEN_BUILDING:
                w = self._wrap_centered(self._make_green_building_widget())
            elif row == self.ROW_FIRE_RATING_CLASS:
                w = self._wrap_centered(QLineEdit())
            elif row in self._CHECKBOX_ROWS:
                checkbox = QCheckBox()
                checkbox.setProperty("row", row)
                w = self._wrap_centered(checkbox)
            else:
                w = self._wrap_centered(QCheckBox())
            if combo is not None:
                label_item = row_label_item(row, 0)
                label = label_item.text() if label_item is not None else ""
                combo.set_override_context(label, col_position - 2)
            self.codes_table.setCellWidget(row, col_position, w)

        for row in range(len(self.CODE_ROW_DESCRIPTIONS), self.codes_table.rowCount()):
            self.codes_table.setCellWidget(
                row, col_position, self._wrap_centered(QLineEdit()),
            )

    def _infer_compliance_custom_meta(self, comp_list: list) -> list:
        meta = normalize_meta_list(self.user_inputs.get(KEY_CUSTOM_COMPLIANCE))
        if meta:
            return meta
        ordered: list[str] = []
        seen: set[str] = set()
        for entry in comp_list:
            if not isinstance(entry, dict):
                continue
            for k in entry:
                if k in self.CODE_FIXED_KEYS or k in seen:
                    continue
                seen.add(k)
                ordered.append(k)
        return [{"name": k, "unit": ""} for k in ordered]

    def _fill_custom_compliance_description_cell(self, row: int, col: int) -> None:
        self.codes_table.setCellWidget(row, col, self._wrap_centered(QLineEdit()))

    def _rebuild_custom_compliance_rows(self, comp_list: list) -> None:
        clear_rows_from(self.codes_table, len(self.CODE_ROW_DESCRIPTIONS))
        meta = self._infer_compliance_custom_meta(comp_list)
        used: set[str] = set()
        for entry in meta:
            raw_name = str(entry.get("name", "") or "").strip()
            unit = str(entry.get("unit", "") or "").strip()
            name = raw_name if raw_name else default_custom_name(used)
            used.add(name)
            append_custom_row_two_column_headers(
                self.codes_table,
                name=name,
                unit=unit,
                first_data_col=2,
                fill_data_cell=self._fill_custom_compliance_description_cell,
            )

    def _on_add_custom_parameter_row(self) -> None:
        used: set[str] = set()
        for r in range(len(self.CODE_ROW_DESCRIPTIONS), self.codes_table.rowCount()):
            w = self.codes_table.cellWidget(r, 0)
            if isinstance(w, QLineEdit) and w.text().strip():
                used.add(w.text().strip())
        name = default_custom_name(used)
        append_custom_row_two_column_headers(
            self.codes_table,
            name=name,
            unit="",
            first_data_col=2,
            fill_data_cell=self._fill_custom_compliance_description_cell,
        )

    def _on_remove_custom_parameter_row(self) -> None:
        if self.codes_table.rowCount() <= len(self.CODE_ROW_DESCRIPTIONS):
            return
        self.codes_table.removeRow(self.codes_table.rowCount() - 1)
        self.sync_compliance_to_user_inputs()

    @staticmethod
    def _checkbox_in_cell(cell_widget):
        if isinstance(cell_widget, QCheckBox):
            return cell_widget
        if isinstance(cell_widget, QWidget):
            for child in cell_widget.findChildren(QCheckBox):
                return child
        return None

    @staticmethod
    def _combo_in_cell(cell_widget):
        if isinstance(cell_widget, QComboBox):
            return cell_widget
        if isinstance(cell_widget, QWidget):
            for child in cell_widget.findChildren(QComboBox):
                return child
        return None

    @staticmethod
    def _lineedit_in_cell(cell_widget):
        if isinstance(cell_widget, QLineEdit):
            return cell_widget
        if isinstance(cell_widget, QWidget):
            for child in cell_widget.findChildren(QLineEdit):
                return child
        return None

    def _green_building_checkbox(self, cell_widget, scheme: str) -> QCheckBox | None:
        if not isinstance(cell_widget, QWidget):
            return None
        for child in cell_widget.findChildren(QCheckBox):
            if child.objectName() == scheme:
                return child
        return None

    def _read_green_building_value(self, cell_widget) -> dict[str, bool]:
        out: dict[str, bool] = {}
        for name in self.GREEN_BUILDING_SCHEMES:
            cb = self._green_building_checkbox(cell_widget, name)
            out[name] = cb.isChecked() if cb is not None else False
        return out

    def _apply_green_building_value(self, cell_widget, value) -> None:
        """Restore saved compliance: dict of bools, list of selected names, or legacy single string."""
        for name in self.GREEN_BUILDING_SCHEMES:
            cb = self._green_building_checkbox(cell_widget, name)
            if cb is None:
                continue
            if isinstance(value, dict):
                cb.setChecked(bool(value.get(name)))
            elif isinstance(value, (list, tuple)):
                picked = {str(x).strip() for x in value}
                cb.setChecked(name in picked)
            elif isinstance(value, str):
                s = value.strip()
                if not s:
                    cb.setChecked(False)
                else:
                    tokens = {t.strip() for t in s.replace(";", ",").split(",") if t.strip()}
                    cb.setChecked(name in tokens or s == name)
            else:
                cb.setChecked(False)

    def _set_combo_value(self, cell_widget, value):
        combo = self._combo_in_cell(cell_widget)
        if combo is None:
            return
        text = str(value).strip()
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        if isinstance(value, bool):
            idx = 1 if value else 0
            if idx < combo.count():
                combo.setCurrentIndex(idx)

    def populate_from_input(self, compliance_data):
        for col, compliance_entry in enumerate(compliance_data, start=2):
            for row in range(self.codes_table.rowCount()):
                description = self._compliance_row_description(row)
                if not description or description not in compliance_entry:
                    continue
                cell_widget = self.codes_table.cellWidget(row, col)
                value = compliance_entry[description]

                if row < len(self.CODE_ROW_DESCRIPTIONS) and row in self._COMBO_ROWS:
                    self._set_combo_value(cell_widget, value)
                elif row < len(self.CODE_ROW_DESCRIPTIONS) and row == self.ROW_GREEN_BUILDING:
                    self._apply_green_building_value(cell_widget, value)
                elif row < len(self.CODE_ROW_DESCRIPTIONS) and row == self.ROW_FIRE_RATING_CLASS:
                    le = self._lineedit_in_cell(cell_widget)
                    if le is not None:
                        if isinstance(value, bool):
                            le.setText('')
                        else:
                            le.setText('' if value is None else str(value))
                elif row < len(self.CODE_ROW_DESCRIPTIONS):
                    cb = self._checkbox_in_cell(cell_widget)
                    if cb is not None:
                        cb.setChecked(bool(value))
                else:
                    le = self._lineedit_in_cell(cell_widget)
                    if le is not None:
                        le.setText('' if value is None else str(value))

    def sync_compliance_to_user_inputs(self):
        """Write applicable codes table into ``user_inputs``."""
        compliance_data = []
        for col in range(2, self.codes_table.columnCount()):
            compliance_entry = {}
            for row in range(self.codes_table.rowCount()):
                description = self._compliance_row_description(row)
                if not description:
                    continue
                cell_widget = self.codes_table.cellWidget(row, col)

                if row < len(self.CODE_ROW_DESCRIPTIONS) and row in self._COMBO_ROWS:
                    combo = self._combo_in_cell(cell_widget)
                    value = combo.currentText() if combo is not None else ''
                elif row < len(self.CODE_ROW_DESCRIPTIONS) and row == self.ROW_GREEN_BUILDING:
                    value = self._read_green_building_value(cell_widget)
                elif row < len(self.CODE_ROW_DESCRIPTIONS) and row == self.ROW_FIRE_RATING_CLASS:
                    le = self._lineedit_in_cell(cell_widget)
                    value = le.text() if le is not None else ''
                elif row < len(self.CODE_ROW_DESCRIPTIONS):
                    cb = self._checkbox_in_cell(cell_widget)
                    value = cb.isChecked() if cb is not None else False
                else:
                    le = self._lineedit_in_cell(cell_widget)
                    value = le.text() if le is not None else ''

                compliance_entry[description] = value

            compliance_data.append(compliance_entry)

        self.user_inputs['Compliance'] = compliance_data
        self.user_inputs[KEY_CUSTOM_COMPLIANCE] = meta_from_table(
            self.codes_table,
            fixed_row_count=len(self.CODE_ROW_DESCRIPTIONS),
            has_unit_column=True,
        )

    def collect_data_and_go_next(self):
        self.sync_compliance_to_user_inputs()
        self.next_clicked.emit(self.user_inputs)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    desc = [
        'EN81-28 emergency call', 'EN81-70 Accessibility', 'DIN EN17210 / 18040-1 Accessibility',
        'EN81-71 Vandalism category', 'EN81-72 Firefighter elevator', 'EN81-73 Fire emergency return',
        'EN81-76 Emergency Evacuation type', 'EN81-76 Evacuation functions', 'EN81-77 Seismic category',
        'EN81-58 Fire rated landing doors', 'EN81-58 Fire rating class',
        'Green building certification compliance',
    ]
    user_inputs = {
        'BuildingSystems': [{'Number': '1'}, {'Number': '2'}],
        'Compliance': [
            {d: ('2' if 'Vandalism' in d else 'A' if 'Evacuation Class' in d else '1' if 'Seismic' in d else True)
             for d in desc},
            {d: ('0' if 'Vandalism' in d else 'B' if 'Evacuation Class' in d else '3' if 'Seismic' in d else False)
             for d in desc},
        ],
    }
    window = ApplicableCodesPage(user_inputs)
    window.show()
    sys.exit(app.exec_())
