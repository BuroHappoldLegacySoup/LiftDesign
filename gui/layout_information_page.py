"""
Layout Information — from Cabin width through Lift vestibule depth (per lift).
Merges into existing user_inputs['LiftSystems'] from General specification.
"""
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGroupBox, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QHBoxLayout, QLineEdit, QComboBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator
import sys


class LayoutInformationPage(QWidget):
    next_clicked = pyqtSignal(dict)

    # Local row indices in layout_table (0-based)
    ROW_CLEAR_CABIN_HEIGHT = 2
    ROW_STRUCTURAL_CABIN_HEIGHT = 3
    ROW_DOOR_TYPE = 8
    ROW_DOOR_FIXATION = 9
    ROW_PERMISSIBLE_SILL = 10
    ROW_LOP = 11
    ROW_LIP = 12
    ROW_LIFT_MAINT_TYPE = 13
    ROW_SHAFT_EQUIP_FIX = 15

    LAYOUT_DESCRIPTIONS = [
        'Cabin width (mm)', 'Cabin depth (mm)',
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

    def _door_type_from_cwt(self, lift_index: int) -> str:
        lifts = self.user_inputs.get('LiftSystems') or []
        if 0 <= lift_index < len(lifts):
            cwt = lifts[lift_index].get('Counterweight location', '')
            if cwt == 'CWT-Left':
                return '2L'
            if cwt == 'CWT-Right':
                return '2R'
        return 'Non std. CTW'

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

    def initialize_lift_columns(self):
        for _ in range(self.number_of_lifts):
            self.add_lift_column()

    def add_lift_column(self):
        col_position = self.layout_table.columnCount()
        self.layout_table.insertColumn(col_position)
        self.layout_table.setHorizontalHeaderItem(col_position, QTableWidgetItem(f'Lift {col_position}'))
        lift_index = col_position - 1

        for row in range(self.layout_table.rowCount()):
            # elif branches in ascending row order
            if row == self.ROW_CLEAR_CABIN_HEIGHT:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
                widget.textChanged.connect(
                    lambda _t, cp=col_position: self._update_structural_cabin_height(cp)
                )
            elif row == self.ROW_STRUCTURAL_CABIN_HEIGHT:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
                prev = self.layout_table.cellWidget(self.ROW_CLEAR_CABIN_HEIGHT, col_position)
                pv = None
                if prev and isinstance(prev, QLineEdit):
                    try:
                        pv = float(prev.text().replace(',', '.'))
                    except (ValueError, AttributeError):
                        pv = None
                widget.setText(str(pv + 100) if pv is not None else '')
            elif row == self.ROW_DOOR_TYPE:
                widget = QLineEdit()
                widget.setText(self._door_type_from_cwt(lift_index))
            elif row == self.ROW_DOOR_FIXATION:
                widget = QComboBox()
                widget.addItems(['insert rail 40/22', 'insert rail 50/30', 'anchor bolts', 'steel structure'])
            elif row == self.ROW_PERMISSIBLE_SILL:
                widget = QComboBox()
                widget.addItems([
                    'ASME-A', 'ASME-B', 'ASME-C1', 'ASME-C2',
                    'EN81-40%', 'EN81-60%', 'EN81-85%',
                ])
            elif row == self.ROW_LOP:
                widget = QComboBox()
                widget.addItems([
                    'in lift door frame L', 'in lift door frame R',
                    'flush wall panel L', 'flush wall panel R',
                    'wall-mounted panel L', 'wall-mounted panel R',
                ])
            elif row == self.ROW_LIP:
                widget = QComboBox()
                widget.addItems([
                    'door frame side vertical', 'door frame above horizontal',
                    'panel above horizontal', 'panel side vertical',
                ])
            elif row == self.ROW_LIFT_MAINT_TYPE:
                widget = QComboBox()
                widget.addItems([
                    'inside door jamb', 'segregated panel flush', 'segregated panel wall-mounted',
                ])
            elif row == self.ROW_SHAFT_EQUIP_FIX:
                widget = QComboBox()
                widget.addItems(['insert rail 40/22', 'insert rail 50/30', 'anchor bolts', 'steel structure'])
            else:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())

            self.layout_table.setCellWidget(row, col_position, widget)

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
