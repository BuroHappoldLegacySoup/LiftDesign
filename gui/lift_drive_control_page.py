from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGroupBox, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox, QCheckBox
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator
import sys

class LiftDriveControlPage(QWidget):
    next_clicked = pyqtSignal(dict)

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs['BuildingSystems'])
        self.initUI()
        
        # Populate data if LiftDrive exists in user_inputs
        if 'LiftDrive' in self.user_inputs:
            self.populate_from_input(self.user_inputs['LiftDrive'])

    def initUI(self):
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        
        scroll_layout = QVBoxLayout(scroll_widget)
        
        system_box = QGroupBox("Lift Drive Control Inputs")
        system_box.setObjectName("system_box")
        system_box.setStyleSheet(
            "#system_box {background-color: white; border: 3px solid rgb(196, 214, 0); font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(system_box)
        
        system_layout = QVBoxLayout(system_box)
        
        # Table for systems
        self.system_table = QTableWidget()
        self.system_table.setColumnCount(1)  # Start with one column for descriptions
        self.system_table.setHorizontalHeaderLabels(['Description'])
        
        input_descriptions = [
            'Drive/Motor location', 'Control / Operation panel location', 'Number of trips per hour (1/h)', 'Power network', 
            'Drive/Motor type', 'Duty cycle (motor) (%)', 'Drive/Motor Power (kW)', 'Connected rated power (kVA)', 
            'Rated current (A)', 'Starting current (factor ≈ 2) (A)', 'Diversity factor', 'Heat dissipation motor (kJ/h)', 
            'Energy recovery', 'Temperature machine room / shaft (°C)'
        ]
        
        self.system_table.setRowCount(len(input_descriptions))
        
        for row, description in enumerate(input_descriptions):
            item = QTableWidgetItem(description)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.system_table.setItem(row, 0, item)
        
        self.system_table.horizontalHeader().setStretchLastSection(True)
        self.system_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.system_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

        system_layout.addWidget(self.system_table)

        # Save and Proceed Button
        save_button = QPushButton('Save and Proceed')
        save_button.setStyleSheet("background-color: white;")
        save_button.clicked.connect(self.collect_data_and_go_next)
        scroll_layout.addWidget(save_button)

        # Initialize the table with the specified number of lifts
        self.initialize_lift_columns()

    def populate_from_input(self, drive_data):
        """Populate the table with existing lift drive control data"""
        for col, system_data in enumerate(drive_data, start=1):  # start=1 because column 0 is descriptions
            for row in range(self.system_table.rowCount()):
                description = self.system_table.item(row, 0).text()
                if description in system_data:
                    cell_widget = self.system_table.cellWidget(row, col)
                    value = system_data[description]
                    
                    if row == 12:  # Energy recovery (checkbox)
                        if isinstance(cell_widget, QCheckBox):
                            cell_widget.setChecked(bool(value))
                    elif isinstance(cell_widget, QLineEdit):
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

        # Add appropriate widgets to each row in the new column
        for row in range(self.system_table.rowCount()):
            if row == 12:  # Energy recovery
                widget = QCheckBox()
            elif row in [2, 5, 6, 7, 8, 11, 13]:  # Numeric input fields
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
            else:  # Text input fields
                widget = QLineEdit()
            self.system_table.setCellWidget(row, col_position, widget)

    def collect_data_and_go_next(self):
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
                elif isinstance(cell_widget, QCheckBox):
                    value = cell_widget.isChecked()
                
                system_data[description] = value
            systems_data.append(system_data)
        
        self.user_inputs['LiftDrive'] = systems_data
        self.next_clicked.emit(self.user_inputs)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    sample_input = {
    'BuildingSystems': [
        {'Number': '1', 'System Name': 'Lift A'},
        {'Number': '2', 'System Name': 'Lift B'}
    ],
    'LiftDrive': [
        {
            'Drive/Motor location': 'Top',
            'Control / Operation panel location': 'Front',
            'Number of trips per hour (1/h)': '120',
            'Power network': '400V',
            'Energy recovery': True,
            'Temperature machine room / shaft (°C)': '25'
        },
        {
            'Drive/Motor location': 'Bottom',
            'Control / Operation panel location': 'Side',
            'Number of trips per hour (1/h)': '100',
            'Power network': '400V',
            'Energy recovery': False,
            'Temperature machine room / shaft (°C)': '22'
        }
    ]
}
    ex = LiftDriveControlPage(sample_input)
    ex.show()
    sys.exit(app.exec_())
