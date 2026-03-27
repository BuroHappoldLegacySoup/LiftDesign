"""
General specification — inputs from System Type through Adjacent access (per lift).
"""
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGroupBox, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator
import sys

from .lift_types import LOAD_CAPACITY_KG, LiftSystemType


class GeneralSpecificationPage(QWidget):
    next_clicked = pyqtSignal(dict)

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
        'Number of shaft doors (Stck.)',
        'Acces type', 
        'Accesible rooms/cwt safety (y/n)'
    ]

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs['BuildingSystems'])
        self.initUI()

        if 'LiftSystems' in self.user_inputs:
            self.populate_from_input(self.user_inputs['LiftSystems'])

        self._sync_lift_systems_to_user_inputs()

    def _sync_lift_systems_to_user_inputs(self):
        """Keep ``user_inputs['LiftSystems']`` aligned with the table so other pages see live updates."""
        systems_data = []
        for col in range(1, self.system_table.columnCount()):
            system_data = {}
            for row in range(self.system_table.rowCount()):
                description = self.system_table.item(row, 0).text()
                cell_widget = self.system_table.cellWidget(row, col)
                if isinstance(cell_widget, QLineEdit):
                    value = cell_widget.text()
                elif isinstance(cell_widget, QComboBox):
                    value = cell_widget.currentText()
                else:
                    value = ''
                system_data[description] = value
            systems_data.append(system_data)
        self.user_inputs['LiftSystems'] = systems_data

    def _connect_cell_widget_sync(self, widget):
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(self._sync_lift_systems_to_user_inputs)
        elif isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(self._sync_lift_systems_to_user_inputs)

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
        scroll_layout.addWidget(save_button)

        self.initialize_lift_columns()

    def populate_from_input(self, systems_data):
        for col, system_data in enumerate(systems_data, start=1):
            for row in range(self.system_table.rowCount()):
                description = self.system_table.item(row, 0).text()
                if description in system_data:
                    cell_widget = self.system_table.cellWidget(row, col)
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
            elif row == 7:
                widget = QComboBox()
                widget.addItems(['1,00', '1,60', '2,00'])
            elif row == 13:
                widget = QComboBox()
                widget.addItems(['Front', 'Rear', 'Front + Rear', 'Front + Side', 'Front + Side + Rear'])
            elif row == 14:
                widget = QComboBox()
                widget.addItems(['yes', 'no'])
            else:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())

            self.system_table.setCellWidget(row, col_position, widget)
            self._connect_cell_widget_sync(widget)

    def collect_data_and_go_next(self):
        self._sync_lift_systems_to_user_inputs()
        self.next_clicked.emit(self.user_inputs)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    sample = {
        'BuildingSystems': [{'Number': '1'}],
        'LiftSystems': [{'System Type': 'Passenger Lift', 'Open-through': True, 'Adjacent access': False}],
    }
    w = GeneralSpecificationPage(sample)
    w.show()
    sys.exit(app.exec_())
