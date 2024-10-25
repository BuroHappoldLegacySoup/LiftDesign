from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGroupBox, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QHBoxLayout, QLineEdit, QComboBox
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator
import sys

class BuildingSystemPage(QWidget):
    next_clicked = pyqtSignal(dict)

    def __init__(self, input_data=None):
        super().__init__()
        self.user_inputs = input_data if input_data else {}
        self.initUI()
        if input_data and 'BuildingSystems' in input_data:
            self.populate_from_input(input_data['BuildingSystems'])

    def initUI(self):
        self.setMinimumSize(800, 600)  # Set fixed size for the page

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
        
        # Add Lift and Remove Lift buttons
        button_layout = QHBoxLayout()
        add_lift_button = QPushButton('Add Lift')
        add_lift_button.clicked.connect(self.add_lift_column)
        remove_lift_button = QPushButton('Remove Lift')
        remove_lift_button.clicked.connect(self.remove_lift_column)
        button_layout.addWidget(add_lift_button)
        button_layout.addWidget(remove_lift_button)
        system_layout.addLayout(button_layout)
        
        # Table for systems
        self.system_table = QTableWidget()
        self.system_table.setColumnCount(1)  # Start with one column for descriptions
        self.system_table.setHorizontalHeaderLabels(['Description'])
        
        # Add rows for each input type
        input_descriptions = [
            'Number', 'System Name', 'Building Part', 'Building Section', 'Grid Position', 
            'Plan Code', 'Drawing Number, Internal', 'Factory Number'
        ]
        
        self.system_table.setRowCount(len(input_descriptions))
        
        for row, description in enumerate(input_descriptions):
            item = QTableWidgetItem(description)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make the description column non-editable
            self.system_table.setItem(row, 0, item)
        
        self.system_table.horizontalHeader().setStretchLastSection(True)
        self.system_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Fix the dimensions of the description column
        self.system_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

        system_layout.addWidget(self.system_table)

        # Save and Proceed Button
        save_button = QPushButton('Save and Proceed')
        save_button.setStyleSheet("background-color: white;")
        save_button.clicked.connect(self.collect_data_and_go_next)
        scroll_layout.addWidget(save_button)

        # If no input data, ensure there's at least one lift to start with
        if not self.user_inputs:
            self.add_lift_column()

    def populate_from_input(self, systems_data):
        # First, add the required number of columns
        num_systems = len(systems_data)
        for _ in range(num_systems):
            self.add_lift_column()
        
        # Now populate the data
        for col, system_data in enumerate(systems_data, start=1):  # start=1 because column 0 is descriptions
            for row in range(self.system_table.rowCount()):
                description = self.system_table.item(row, 0).text()
                if description in system_data:
                    widget = self.system_table.cellWidget(row, col)
                    if isinstance(widget, QLineEdit):
                        widget.setText(str(system_data[description]))
                    elif isinstance(widget, QComboBox):
                        index = widget.findText(system_data[description])
                        if index >= 0:
                            widget.setCurrentIndex(index)

    def add_lift_column(self):
        col_position = self.system_table.columnCount()
        self.system_table.insertColumn(col_position)
        self.system_table.setHorizontalHeaderItem(col_position, QTableWidgetItem(f'Lift {col_position}'))

        # Add appropriate widgets to each row in the new column
        for row in range(self.system_table.rowCount()):
            if row == 0:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
            elif row == 9:
                widget = QComboBox()
                widget.addItems(['BS EN81'])
            else:
                widget = QLineEdit()
            self.system_table.setCellWidget(row, col_position, widget)

    def remove_lift_column(self):
        col_position = self.system_table.columnCount() - 1
        if col_position > 1:  # Ensure there's always at least one lift column
            self.system_table.removeColumn(col_position)

    def collect_data_and_go_next(self):
        systems_data = []
        for col in range(1, self.system_table.columnCount()):
            system_data = {}
            for row in range(self.system_table.rowCount()):
                description = self.system_table.item(row, 0).text()
                if isinstance(self.system_table.cellWidget(row, col), QLineEdit):
                    value = self.system_table.cellWidget(row, col).text()
                elif isinstance(self.system_table.cellWidget(row, col), QComboBox):
                    value = self.system_table.cellWidget(row, col).currentText()
                system_data[description] = value
            systems_data.append(system_data)
        
        self.user_inputs['BuildingSystems'] = systems_data
        self.next_clicked.emit(self.user_inputs)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Example usage with input data
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