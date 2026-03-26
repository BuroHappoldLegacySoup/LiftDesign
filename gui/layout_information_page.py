"""
Layout Information — from Cabin width through Lift vestibule depth (per lift).
Merges into existing user_inputs['LiftSystems'] from General specification.
"""
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGroupBox, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator
import sys

from .lift_types import (
    cabin_width_for_load_and_shape,
    cabin_depth_for_load_and_width,
)


class LayoutInformationPage(QWidget):
    next_clicked = pyqtSignal(dict)

    # Local row indices in layout_table (0-based), must match LAYOUT_DESCRIPTIONS order
    ROW_CABIN_TYPE = 0
    ROW_CABIN_WIDTH = 1
    ROW_CABIN_DEPTH = 2
    ROW_CLEAR_CABIN_HEIGHT = 4
    ROW_STRUCTURAL_CABIN_HEIGHT = 5
    ROW_DOOR_TYPE = 10
    ROW_DOOR_FIXATION = 11
    ROW_PERMISSIBLE_SILL = 12
    ROW_LOP = 13
    ROW_LIP = 14
    ROW_LIFT_MAINT_TYPE = 15
    ROW_SHAFT_EQUIP_FIX = 17

    LOAD_CAPACITY_KEY = 'Load capacity (kg)'
    _COMBO_OPTIONS = {
        ROW_DOOR_FIXATION: ['insert rail 40/22', 'insert rail 50/30', 'anchor bolts', 'steel structure'],
        ROW_PERMISSIBLE_SILL: ['ASME-A', 'ASME-B', 'ASME-C1', 'ASME-C2', 'EN81-40%', 'EN81-60%', 'EN81-85%'],
        ROW_LOP: ['in lift door frame L', 'in lift door frame R', 'flush wall panel L', 'flush wall panel R',
                  'wall-mounted panel L', 'wall-mounted panel R'],
        ROW_LIP: ['door frame side vertical', 'door frame above horizontal', 'panel above horizontal', 'panel side vertical'],
        ROW_LIFT_MAINT_TYPE: ['inside door jamb', 'segregated panel flush', 'segregated panel wall-mounted'],
        ROW_SHAFT_EQUIP_FIX: ['insert rail 40/22', 'insert rail 50/30', 'anchor bolts', 'steel structure'],
    }

    LAYOUT_DESCRIPTIONS = [
        'Cabin type/shape',
        'Cabin width (mm)', 'Cabin depth (mm)',
        'Cladding thickness each wall (mm)',
        'Clear cabin height (mm)', 'Structural cabin height (mm)', 'Door width (mm)',
        'Door structural opening width (mm)', 'Door height (mm)', 'Door structural opening height (mm)',
        'door type', 'door fixation type', 'Permissible sill load / Loading class', 'LOP type and locaion',
        'LIP type and location', 'Lift maintenance panel type', 'Lift maintenance panel location',
        'Shaft equipment fixation type', 'Shaft width suggested (mm)', 'Shaft width current planning (mm)',
        'Shaft division type', 'Shaft division width (mm)', 'Shaft depth suggested (mm)',
        'Shaft depth current planning (mm)', 'Shaft head suggested (mm)', 'Shaft head current planning (mm)',
        'Shaft pit suggested (mm)', 'Shaft pit current planning (mm)', 'Machine room width suggested (mm)',
        'Machine room width current planning (mm)', 'Machine room depth suggested (mm)',
        'Machine room depth current planning (mm)',
        'Machine room height suggested (mm)', 'Machine room height current planning (mm)',
        'Lift vestibule width (mm)', 'Lift vestibule depth (mm)',
    ]

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs['BuildingSystems'])
        self.initUI()

        if 'LiftSystems' in self.user_inputs:
            self.populate_from_input(self.user_inputs['LiftSystems'])

    def _parse_float(self, text):
        t = (text or '').strip()
        if not t:
            return None
        try:
            return float(t.replace(',', '.'))
        except ValueError:
            return None

    def _apply_cabin_width_for_column(self, col):
        lifts = self.user_inputs.get('LiftSystems') or []
        i, ww = col - 1, self.layout_table.cellWidget(self.ROW_CABIN_WIDTH, col)
        if not (0 <= i < len(lifts)) or not isinstance(ww, QLineEdit):
            return
        v = self._parse_float(str(lifts[i].get(self.LOAD_CAPACITY_KEY, '') or ''))
        if v is None:
            return
        tw = self.layout_table.cellWidget(self.ROW_CABIN_TYPE, col)
        s = tw.currentText().strip() if isinstance(tw, QComboBox) else ''
        cw = cabin_width_for_load_and_shape(v, s)
        if cw is not None:
            ww.setText(cw)
        self._apply_cabin_depth_for_column(col)

    def _apply_cabin_depth_for_column(self, col):
        lifts = self.user_inputs.get('LiftSystems') or []
        i = col - 1
        dw = self.layout_table.cellWidget(self.ROW_CABIN_DEPTH, col)
        ww = self.layout_table.cellWidget(self.ROW_CABIN_WIDTH, col)
        if not (0 <= i < len(lifts)) or not isinstance(dw, QLineEdit) or not isinstance(ww, QLineEdit):
            return
        v = self._parse_float(str(lifts[i].get(self.LOAD_CAPACITY_KEY, '') or ''))
        if v is None:
            return
        cd = cabin_depth_for_load_and_width(v, ww.text())
        if cd is not None:
            dw.setText(cd)

    def _door_type_from_cwt(self, i):
        L = self.user_inputs.get('LiftSystems') or []
        if not (0 <= i < len(L)):
            return 'Non std. CTW'
        return {'CWT-Left': '2L', 'CWT-Right': '2R'}.get(L[i].get('Counterweight location', ''), 'Non std. CTW')

    def _update_structural_cabin_height(self, col_position: int):
        clear_w = self.layout_table.cellWidget(self.ROW_CLEAR_CABIN_HEIGHT, col_position)
        struct_w = self.layout_table.cellWidget(self.ROW_STRUCTURAL_CABIN_HEIGHT, col_position)
        if not isinstance(clear_w, QLineEdit) or not isinstance(struct_w, QLineEdit):
            return
        v = self._parse_float(clear_w.text())
        if v is None:
            struct_w.setText('')
            return
        nv = v + 100
        struct_w.setText(str(int(nv)) if nv.is_integer() else str(nv))

    def initUI(self):
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)

        scroll_layout = QVBoxLayout(scroll_widget)

        system_box = QGroupBox("Layout Information")
        system_box.setObjectName("layout_info_box")
        system_box.setStyleSheet(
            "#layout_info_box {background-color: white; border: 3px solid rgb(196, 214, 0); "
            "font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(system_box)

        system_layout = QVBoxLayout(system_box)

        self.layout_table = QTableWidget()
        self.layout_table.setColumnCount(1)
        self.layout_table.setHorizontalHeaderLabels(['Description'])
        self.layout_table.setRowCount(len(self.LAYOUT_DESCRIPTIONS))

        for row, description in enumerate(self.LAYOUT_DESCRIPTIONS):
            item = QTableWidgetItem(description)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.layout_table.setItem(row, 0, item)

        self.layout_table.horizontalHeader().setStretchLastSection(True)
        self.layout_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.layout_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

        system_layout.addWidget(self.layout_table)

        save_button = QPushButton('Save and Proceed')
        save_button.setStyleSheet("background-color: white;")
        save_button.clicked.connect(self.collect_data_and_go_next)
        scroll_layout.addWidget(save_button)

        self.initialize_lift_columns()

    def populate_from_input(self, systems_data):
        for col, system_data in enumerate(systems_data, start=1):
            for row in range(self.layout_table.rowCount()):
                description = self.layout_table.item(row, 0).text()
                if description in system_data:
                    cell_widget = self.layout_table.cellWidget(row, col)
                    value = system_data[description]
                    if isinstance(cell_widget, QLineEdit):
                        cell_widget.setText(str(value))
                    elif isinstance(cell_widget, QComboBox):
                        index = cell_widget.findText(str(value))
                        if index >= 0:
                            cell_widget.setCurrentIndex(index)
            self._apply_cabin_width_for_column(col)

    def initialize_lift_columns(self):
        for _ in range(self.number_of_lifts):
            self.add_lift_column()

    def add_lift_column(self):
        col_position = self.layout_table.columnCount()
        self.layout_table.insertColumn(col_position)
        self.layout_table.setHorizontalHeaderItem(col_position, QTableWidgetItem(f'Lift {col_position}'))
        lift_index = col_position - 1

        for row in range(self.layout_table.rowCount()):
            if row == self.ROW_CABIN_TYPE:
                w = QComboBox()
                w.addItems(['Deep', 'Wide'])
                w.currentTextChanged.connect(lambda *_a, cp=col_position: self._apply_cabin_width_for_column(cp))
                widget = w
            elif row == self.ROW_CABIN_WIDTH:
                widget = QLineEdit()
                widget.textChanged.connect(
                    lambda *_a, cp=col_position: self._apply_cabin_depth_for_column(cp)
                )
            elif row == self.ROW_CABIN_DEPTH:
                widget = QLineEdit()
            elif row == self.ROW_CLEAR_CABIN_HEIGHT:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
                widget.textChanged.connect(lambda *_a, cp=col_position: self._update_structural_cabin_height(cp))
            elif row == self.ROW_STRUCTURAL_CABIN_HEIGHT:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
                p = self.layout_table.cellWidget(self.ROW_CLEAR_CABIN_HEIGHT, col_position)
                pv = self._parse_float(p.text()) if isinstance(p, QLineEdit) else None
                widget.setText(str(pv + 100) if pv is not None else '')
            elif row == self.ROW_DOOR_TYPE:
                widget = QLineEdit()
                widget.setText(self._door_type_from_cwt(lift_index))
            elif row in self._COMBO_OPTIONS:
                w = QComboBox()
                w.addItems(self._COMBO_OPTIONS[row])
                widget = w
            else:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
            self.layout_table.setCellWidget(row, col_position, widget)

        self._apply_cabin_width_for_column(col_position)

    def collect_data_and_go_next(self):
        systems_data = []
        existing = self.user_inputs.get('LiftSystems') or []

        for col in range(1, self.layout_table.columnCount()):
            merged = {}
            idx = col - 1
            if idx < len(existing):
                merged = dict(existing[idx])

            for row in range(self.layout_table.rowCount()):
                description = self.layout_table.item(row, 0).text()
                cell_widget = self.layout_table.cellWidget(row, col)
                if isinstance(cell_widget, QLineEdit):
                    value = cell_widget.text()
                elif isinstance(cell_widget, QComboBox):
                    value = cell_widget.currentText()
                else:
                    value = ''
                merged[description] = value

            systems_data.append(merged)

        self.user_inputs['LiftSystems'] = systems_data
        self.next_clicked.emit(self.user_inputs)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    sample = {
        'BuildingSystems': [{'Number': '1'}],
        'LiftSystems': [{
            'Counterweight location': 'CWT-Left',
            'Cabin width (mm)': '1100',
        }],
    }
    w = LayoutInformationPage(sample)
    w.show()
    sys.exit(app.exec_())
