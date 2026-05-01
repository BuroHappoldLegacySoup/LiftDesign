from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QDialog,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator
import copy
import sys

from .override_combobox import OverrideComboBox
from .lift_groups_dialog import LiftGroupsDialog
from .project_lift_schema import KEY_LIFT_COLUMN_GROUPS, parse_lift_column_groups
from .custom_parameter_rows import (
    KEY_CUSTOM_BUILDING_SYSTEM,
    add_plus_minus_button_row,
    clear_rows_from,
    default_custom_name,
    meta_from_table,
    normalize_meta_list,
)

# Keys stored for fixed template rows — anything else in each lift dict is treated as custom on load.
BUILDING_SYSTEM_FIXED_KEYS = frozenset({
    'Number', 'System Name', 'Building Part', 'Building Section', 'Grid Position',
    'Plan Code', 'Drawing Number, Internal', 'Factory Number', 'System category', 'Functions',
    'Construction use', 'Brand',
})

class BuildingSystemPage(QWidget):
    next_clicked = pyqtSignal(dict)

    # Row 0 = merged group titles; row 1 = "Lift 1…" labels; row 2+ = parameter rows (template + custom).
    _group_row = 0
    _lift_label_row = 1
    _first_parameter_row = 2

    def __init__(self, input_data=None):
        super().__init__()
        self.user_inputs = input_data if input_data else {}
        self._lift_groups: list[dict] = []
        self.initUI()
        if input_data and 'BuildingSystems' in input_data:
            self.populate_from_input(input_data['BuildingSystems'])
        else:
            self._sync_custom_meta_only()
            if self.system_table.columnCount() <= 1:
                self.add_lift_column(from_populate=False)
            self._lift_groups = parse_lift_column_groups(
                self.user_inputs.get(KEY_LIFT_COLUMN_GROUPS),
                max(0, self.system_table.columnCount() - 1),
            )
            self._rebuild_lift_label_row()
            self._rebuild_group_header_row()

    def initUI(self):
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)

        scroll_layout = QVBoxLayout(scroll_widget)

        system_box = QGroupBox("Building System Inputs")
        system_box.setObjectName("system_box")
        system_box.setStyleSheet(
            "#system_box {background-color: white; border: 3px solid rgb(196, 214, 0); font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(system_box)

        system_layout = QVBoxLayout(system_box)

        button_layout = QHBoxLayout()
        add_lift_button = QPushButton('Add Lift')
        add_lift_button.clicked.connect(self.add_lift_column)
        remove_lift_button = QPushButton('Remove Lift')
        remove_lift_button.clicked.connect(self.remove_lift_column)
        self._configure_groups_btn = QPushButton('Lift groups…')
        self._configure_groups_btn.setToolTip(
            'Name groups and choose how many consecutive lifts belong to each group'
        )
        self._configure_groups_btn.clicked.connect(self._on_configure_lift_groups)
        button_layout.addWidget(add_lift_button)
        button_layout.addWidget(remove_lift_button)
        button_layout.addWidget(self._configure_groups_btn)
        button_layout.addStretch()
        system_layout.addLayout(button_layout)

        self.system_table = QTableWidget()
        self.system_table.setColumnCount(1)
        self.system_table.horizontalHeader().hide()

        input_descriptions = [
            'Number', 'System Name', 'Building Part', 'Building Section', 'Grid Position',
            'Plan Code', 'Drawing Number, Internal', 'Factory Number', 'System category', 'Functions',
            'Construction use', 'Brand',
        ]
        self._fixed_system_rows = len(input_descriptions)

        self.system_table.setRowCount(self._fixed_system_rows + self._first_parameter_row)

        g0 = QTableWidgetItem('Group')
        g0.setFlags(g0.flags() & ~Qt.ItemIsEditable)
        self.system_table.setItem(self._group_row, 0, g0)
        l0 = QTableWidgetItem('Lift')
        l0.setFlags(l0.flags() & ~Qt.ItemIsEditable)
        self.system_table.setItem(self._lift_label_row, 0, l0)

        for i, description in enumerate(input_descriptions):
            row = self._first_parameter_row + i
            item = QTableWidgetItem(description)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.system_table.setItem(row, 0, item)

        self.system_table.horizontalHeader().setStretchLastSection(True)
        self.system_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.system_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

        self.system_table.itemChanged.connect(self._on_table_item_changed)

        system_layout.addWidget(self.system_table)
        add_plus_minus_button_row(
            system_layout,
            self._on_add_custom_parameter_row,
            self._on_remove_custom_parameter_row,
        )

        save_button = QPushButton('Save and Proceed')
        save_button.setStyleSheet("background-color: white;")
        save_button.clicked.connect(self.collect_data_and_go_next)
        scroll_layout.addWidget(save_button)

    def _custom_meta_fixed_row_count(self) -> int:
        return self._first_parameter_row + self._fixed_system_rows

    def _lift_groups_from_table(self) -> list[dict]:
        """Derive ``[{"name","count"}, …]`` from merged cells on the group header row (source of truth)."""
        row = self._group_row
        max_c = self.system_table.columnCount()
        n_lift = max_c - 1
        if n_lift <= 0:
            return []
        out: list[dict] = []
        col = 1
        while col < max_c:
            span = max(1, self.system_table.columnSpan(row, col))
            it = self.system_table.item(row, col)
            name = it.text().strip() if it is not None else ""
            out.append({"name": name, "count": span})
            col += span
        if sum(g["count"] for g in out) != n_lift:
            return parse_lift_column_groups(self._lift_groups, n_lift)
        return out

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        if item.row() != self._group_row or item.column() <= 0:
            return
        self._lift_groups = self._lift_groups_from_table()
        self.user_inputs[KEY_LIFT_COLUMN_GROUPS] = copy.deepcopy(self._lift_groups)

    def _trim_last_lift_from_groups(self) -> None:
        if not self._lift_groups:
            self._lift_groups = [{'name': 'Group 1', 'count': 1}]
            return
        last = self._lift_groups[-1]
        if last.get('count', 1) > 1:
            last['count'] = int(last['count']) - 1
        else:
            self._lift_groups.pop()
        if not self._lift_groups:
            self._lift_groups = [{'name': 'Group 1', 'count': 1}]

    def _rebuild_lift_label_row(self) -> None:
        for c in range(1, self.system_table.columnCount()):
            cell = QTableWidgetItem(f'Lift {c}')
            cell.setTextAlignment(Qt.AlignCenter)
            cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
            self.system_table.setItem(self._lift_label_row, c, cell)

    def _rebuild_group_header_row(self) -> None:
        n_lift_cols = self.system_table.columnCount() - 1
        self.system_table.blockSignals(True)
        try:
            self.system_table.clearSpans()
            for c in range(1, self.system_table.columnCount()):
                it = self.system_table.takeItem(self._group_row, c)
                if it is not None:
                    del it

            if n_lift_cols <= 0:
                return

            self._lift_groups = parse_lift_column_groups(self._lift_groups, n_lift_cols)
            col = 1
            for g in self._lift_groups:
                cnt = int(g.get('count', 0))
                name = str(g.get('name', '') or '').strip()
                if cnt <= 0:
                    continue
                cell = QTableWidgetItem(name if name else ' ')
                cell.setTextAlignment(Qt.AlignCenter)
                cell.setFlags(
                    Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
                )
                self.system_table.setItem(self._group_row, col, cell)
                if cnt > 1:
                    self.system_table.setSpan(self._group_row, col, 1, cnt)
                col += cnt
                if col > self.system_table.columnCount():
                    break
        finally:
            self.system_table.blockSignals(False)

    def populate_from_input(self, systems_data):
        num_systems = len(systems_data)
        for _ in range(num_systems):
            self.add_lift_column(from_populate=True)

        self._lift_groups = parse_lift_column_groups(
            self.user_inputs.get(KEY_LIFT_COLUMN_GROUPS),
            num_systems,
        )

        self._rebuild_custom_rows_from_project(systems_data)

        for col, system_data in enumerate(systems_data, start=1):
            for row in range(self._first_parameter_row, self._first_parameter_row + self._fixed_system_rows):
                description = self.system_table.item(row, 0).text()
                if description in system_data:
                    widget = self.system_table.cellWidget(row, col)
                    if isinstance(widget, QLineEdit):
                        widget.setText(str(system_data[description]))
                    elif isinstance(widget, QComboBox):
                        index = widget.findText(system_data[description])
                        if index >= 0:
                            widget.setCurrentIndex(index)
            for row in range(self._custom_meta_fixed_row_count(), self.system_table.rowCount()):
                wn = self.system_table.cellWidget(row, 0)
                name = wn.text().strip() if isinstance(wn, QLineEdit) else ""
                if name and name in system_data:
                    w = self.system_table.cellWidget(row, col)
                    if isinstance(w, QLineEdit):
                        w.setText(str(system_data[name]))

        self._rebuild_lift_label_row()
        self._rebuild_group_header_row()

    def _infer_custom_meta_from_systems(self, systems_data) -> list:
        meta = normalize_meta_list(self.user_inputs.get(KEY_CUSTOM_BUILDING_SYSTEM))
        if meta:
            return meta
        keys_order = []
        seen = set()
        for sys in systems_data:
            if not isinstance(sys, dict):
                continue
            for k in sys:
                if k in BUILDING_SYSTEM_FIXED_KEYS or k in seen:
                    continue
                seen.add(k)
                keys_order.append(k)
        return [{"name": k, "unit": ""} for k in keys_order]

    def _rebuild_custom_rows_from_project(self, systems_data):
        clear_rows_from(self.system_table, self._custom_meta_fixed_row_count())
        meta = self._infer_custom_meta_from_systems(systems_data)
        used = set()
        for entry in meta:
            raw_name = str(entry.get("name", "") or "").strip()
            name = raw_name if raw_name else default_custom_name(used)
            used.add(name)
            self._append_custom_parameter_row(name)

    def _fill_custom_lift_cell(self, row: int, col: int):
        widget = QLineEdit()
        self.system_table.setCellWidget(row, col, widget)

    def _append_custom_parameter_row(self, name: str):
        row = self.system_table.rowCount()
        self.system_table.insertRow(row)
        self.system_table.setCellWidget(row, 0, QLineEdit(name))
        for col in range(1, self.system_table.columnCount()):
            self._fill_custom_lift_cell(row, col)

    def _on_add_custom_parameter_row(self):
        used = set()
        for r in range(self._custom_meta_fixed_row_count(), self.system_table.rowCount()):
            w = self.system_table.cellWidget(r, 0)
            if isinstance(w, QLineEdit) and w.text().strip():
                used.add(w.text().strip())
        name = default_custom_name(used)
        self._append_custom_parameter_row(name)
        self._sync_custom_meta_only()

    def _on_remove_custom_parameter_row(self) -> None:
        if self.system_table.rowCount() <= self._custom_meta_fixed_row_count():
            return
        self.system_table.removeRow(self.system_table.rowCount() - 1)
        self._sync_custom_meta_only()

    def _sync_custom_meta_only(self):
        self.user_inputs[KEY_CUSTOM_BUILDING_SYSTEM] = meta_from_table(
            self.system_table,
            fixed_row_count=self._custom_meta_fixed_row_count(),
            has_unit_column=False,
        )

    def add_lift_column(self, from_populate: bool = False):
        col_position = self.system_table.columnCount()
        self.system_table.insertColumn(col_position)

        if not from_populate:
            self._lift_groups.append({
                'name': f'Group {len(self._lift_groups) + 1}',
                'count': 1,
            })

        cell = QTableWidgetItem(f'Lift {col_position}')
        cell.setTextAlignment(Qt.AlignCenter)
        cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
        self.system_table.setItem(self._lift_label_row, col_position, cell)

        for row in range(self._first_parameter_row, self._first_parameter_row + self._fixed_system_rows):
            rel = row - self._first_parameter_row
            if rel == 0:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
            elif rel == 9:
                widget = OverrideComboBox()
                widget.addItems(['BS EN81'])
                label_item = self.system_table.item(row, 0)
                if label_item is not None:
                    widget.set_override_context(label_item.text(), col_position - 1)
            else:
                widget = QLineEdit()
            self.system_table.setCellWidget(row, col_position, widget)

        for row in range(self._custom_meta_fixed_row_count(), self.system_table.rowCount()):
            self._fill_custom_lift_cell(row, col_position)

        if not from_populate:
            self._rebuild_lift_label_row()
            self._rebuild_group_header_row()

    def remove_lift_column(self):
        col_position = self.system_table.columnCount() - 1
        if col_position <= 1:
            return
        self._trim_last_lift_from_groups()
        self.system_table.removeColumn(col_position)
        self._rebuild_lift_label_row()
        self._rebuild_group_header_row()

    def _on_configure_lift_groups(self) -> None:
        n = self.system_table.columnCount() - 1
        if n < 1:
            return
        dlg = LiftGroupsDialog(self, n, copy.deepcopy(self._lift_groups))
        if dlg.exec_() != QDialog.Accepted:
            return
        self._lift_groups = dlg.groups_result()
        self._rebuild_group_header_row()
        self.sync_to_user_inputs()

    def sync_to_user_inputs(self):
        """Write building-system table into ``user_inputs`` (used before final JSON save)."""
        systems_data = []
        for col in range(1, self.system_table.columnCount()):
            system_data = {}
            for row in range(self._first_parameter_row, self._first_parameter_row + self._fixed_system_rows):
                description = self.system_table.item(row, 0).text()
                if isinstance(self.system_table.cellWidget(row, col), QLineEdit):
                    value = self.system_table.cellWidget(row, col).text()
                elif isinstance(self.system_table.cellWidget(row, col), QComboBox):
                    value = self.system_table.cellWidget(row, col).currentText()
                system_data[description] = value
            for row in range(self._custom_meta_fixed_row_count(), self.system_table.rowCount()):
                wn = self.system_table.cellWidget(row, 0)
                name = wn.text().strip() if isinstance(wn, QLineEdit) else ""
                if not name:
                    continue
                w = self.system_table.cellWidget(row, col)
                if isinstance(w, QLineEdit):
                    system_data[name] = w.text()
                elif isinstance(w, QComboBox):
                    system_data[name] = w.currentText()
                else:
                    system_data[name] = ''
            systems_data.append(system_data)
        self.user_inputs['BuildingSystems'] = systems_data
        self._lift_groups = self._lift_groups_from_table()
        self.user_inputs[KEY_LIFT_COLUMN_GROUPS] = copy.deepcopy(self._lift_groups)
        self._sync_custom_meta_only()

    def collect_data_and_go_next(self):
        self.sync_to_user_inputs()
        self.next_clicked.emit(self.user_inputs)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    sample_input = {
        'BuildingSystems': [
            {
                'Number': '1',
                'System Name': 'Lift A',
                'Building Part': 'Wing 1',
                'Building Section': 'North',
                'Grid Position': 'A1',
                'Plan Code': 'PC001',
                'Drawing Number, Internal': 'DN001',
                'Factory Number': 'FN001'
            },
            {
                'Number': '2',
                'System Name': 'Lift B',
                'Building Part': 'Wing 2',
                'Building Section': 'South',
                'Grid Position': 'B2',
                'Plan Code': 'PC002',
                'Drawing Number, Internal': 'DN002',
                'Factory Number': 'FN002'
            }
        ]
    }
    ex = BuildingSystemPage(sample_input)
    ex.show()
    sys.exit(app.exec_())
