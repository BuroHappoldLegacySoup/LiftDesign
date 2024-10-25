from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGroupBox, QPushButton, QCheckBox, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QCheckBox
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator
import sys

class ForceSpecPage(QWidget):
    next_clicked = pyqtSignal(dict)

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs['BuildingSystems'])
        self.initUI()
        
        # Populate data if Forces exists in user_inputs
        if 'Forces' in self.user_inputs:
            self.populate_from_input(self.user_inputs['Forces'])

    def populate_from_input(self, forces_data):
        """Populate the table with existing force specification data"""
        for col, force_data in enumerate(forces_data, start=1):  # start=1 because column 0 is descriptions
            for row in range(self.force_table.rowCount()):
                description = self.force_table.item(row, 0).text()
                if description in force_data:
                    cell_widget = self.force_table.cellWidget(row, col)
                    value = force_data[description]
                    
                    if row == 2:  # Counterweight safety gear (checkbox)
                        if isinstance(cell_widget, QCheckBox):
                            cell_widget.setChecked(bool(value))
                    elif isinstance(cell_widget, QLineEdit):
                        cell_widget.setText(str(value))

    def initUI(self):
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        
        scroll_layout = QVBoxLayout(scroll_widget)
        
        force_box = QGroupBox("Force Inputs")
        force_box.setObjectName("force_box")
        force_box.setStyleSheet(
            "#force_box {background-color: white; border: 3px solid rgb(196, 214, 0); font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(force_box)
        
        force_layout = QVBoxLayout(force_box)
        
        # Table for forces
        self.force_table = QTableWidget()
        self.force_table.setColumnCount(1)
        self.force_table.setHorizontalHeaderLabels(['Description'])
        
        input_descriptions = [
            'Force F1, F2 elevator rail segment (kN)', 'Force F3, each buffer (kN)', 'Counterweight safety gear', 
            'Force F4, per counterweight rail segment (kN)', 'Force F5, per counterweight buffer (kN)', 
            'Force F6, static shaft door (kN)', 'Force F7, static counterweight (kN)', 'Force F8, static cabin (kN)', 
            'Force Fx, cabin rail (kN)', 'Force Fy, cabin rail (kN)', 'Force Fx, counterweight rail (kN)', 
            'Force Fy, counterweight rail (kN)'
        ]
        
        self.force_table.setRowCount(len(input_descriptions))
        
        for row, description in enumerate(input_descriptions):
            item = QTableWidgetItem(description)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.force_table.setItem(row, 0, item)
        
        self.force_table.horizontalHeader().setStretchLastSection(True)
        self.force_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.force_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

        force_layout.addWidget(self.force_table)

        # Save and Proceed Button
        save_button = QPushButton('Save and Proceed')
        save_button.setStyleSheet("background-color: white;")
        save_button.clicked.connect(self.collect_data_and_go_next)
        scroll_layout.addWidget(save_button)

        # Initialize the table with the specified number of lifts
        self.initialize_lift_columns()

    def initialize_lift_columns(self):
        for _ in range(self.number_of_lifts):
            self.add_lift_column()

    def add_lift_column(self):
        col_position = self.force_table.columnCount()
        self.force_table.insertColumn(col_position)
        self.force_table.setHorizontalHeaderItem(col_position, QTableWidgetItem(f'Lift {col_position}'))

        # Add appropriate widgets to each row in the new column
        for row in range(self.force_table.rowCount()):
            if row == 2:  # Counterweight safety gear
                widget = QCheckBox()
            else:  # All other force inputs
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
            self.force_table.setCellWidget(row, col_position, widget)

    def collect_data_and_go_next(self):
        forces_data = []
        for col in range(1, self.force_table.columnCount()):
            force_data = {}
            for row in range(self.force_table.rowCount()):
                description = self.force_table.item(row, 0).text()
                cell_widget = self.force_table.cellWidget(row, col)
                
                if isinstance(cell_widget, QLineEdit):
                    value = cell_widget.text()
                elif isinstance(cell_widget, QCheckBox):
                    value = cell_widget.isChecked()
                
                force_data[description] = value
            forces_data.append(force_data)
        
        self.user_inputs['Forces'] = forces_data
        self.next_clicked.emit(self.user_inputs)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    sample_input = {
    'BuildingSystems': [
        {'Number': '1', 'System Name': 'Lift A'},
        {'Number': '2', 'System Name': 'Lift B'}
    ],
    'Forces': [
        {
            'Force F1, F2 elevator rail segment (kN)': '10.5',
            'Force F3, each buffer (kN)': '15.2',
            'Counterweight safety gear': True,
            'Force F4, per counterweight rail segment (kN)': '8.7',
            'Force Fx, cabin rail (kN)': '5.3',
            'Force Fy, cabin rail (kN)': '4.2'
        },
        {
            'Force F1, F2 elevator rail segment (kN)': '12.1',
            'Force F3, each buffer (kN)': '16.8',
            'Counterweight safety gear': False,
            'Force F4, per counterweight rail segment (kN)': '9.3',
            'Force Fx, cabin rail (kN)': '5.8',
            'Force Fy, cabin rail (kN)': '4.7'
        }
    ]
}
    ex = ForceSpecPage(sample_input) 
    ex.show()
    sys.exit(app.exec_())
