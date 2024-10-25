from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGroupBox, QPushButton, QCheckBox, QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QHBoxLayout, QLineEdit
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator
import sys

class LiftCompliancePage(QWidget):
    next_clicked = pyqtSignal(dict)

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs['BuildingSystems'])
        self.initUI()
        
        # Populate data if Compliance exists in user_inputs
        if 'Compliance' in self.user_inputs:
            self.populate_from_input(self.user_inputs['Compliance'])

    def initUI(self):
        self.setMinimumSize(800, 600)  # Set fixed size for the page

        layout = QVBoxLayout(self)
        
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        
        scroll_layout = QVBoxLayout(scroll_widget)
        
        compliance_box = QGroupBox("Lift Compliance Inputs")
        compliance_box.setObjectName("compliance_box")
        compliance_box.setStyleSheet(
            "#compliance_box {background-color: white; border: 3px solid rgb(196, 214, 0); font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(compliance_box)
        
        compliance_layout = QVBoxLayout(compliance_box)
        
        # Table for compliance inputs
        self.compliance_table = QTableWidget()
        self.compliance_table.setColumnCount(1)  # Start with one column for descriptions
        self.compliance_table.setHorizontalHeaderLabels(['Description'])
        
        # Add rows for each input type with units in the description
        input_descriptions = [
            'EN81-70 Accessibility', 'EN81-71 Vandalism', 'EN81-72 Firefighter elevator', 
            'EN81-73 Fire emergency return', 'EN81-77 Seismic', 'EN81-58 Fire protection class for landing doors', 
            'EN81-76/BS 9999 Evacuation lift'
        ]
        
        self.compliance_table.setRowCount(len(input_descriptions))
        
        for row, description in enumerate(input_descriptions):
            item = QTableWidgetItem(description)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make the description column non-editable
            self.compliance_table.setItem(row, 0, item)
        
        self.compliance_table.horizontalHeader().setStretchLastSection(True)
        self.compliance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Fix the dimensions of the description column
        self.compliance_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

        compliance_layout.addWidget(self.compliance_table)

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
        col_position = self.compliance_table.columnCount()
        self.compliance_table.insertColumn(col_position)
        self.compliance_table.setHorizontalHeaderItem(col_position, QTableWidgetItem(f'Lift {col_position}'))

        # Add appropriate widgets to each row in the new column
        for row in range(self.compliance_table.rowCount()):
            if row in [0, 1, 2, 3, 4, 6]:
                checkbox = QCheckBox()
                checkbox.setProperty("row", row)  # Store row information for later access
                widget = QWidget()
                layout = QHBoxLayout(widget)
                layout.addStretch()
                layout.addWidget(checkbox)
                layout.addStretch()
                layout.setContentsMargins(0, 0, 0, 0)
                widget.setLayout(layout)
                self.compliance_table.setCellWidget(row, col_position, widget)
            elif row == 5:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
                self.compliance_table.setCellWidget(row, col_position, widget)

    def get_checkbox_from_cell_widget(self, cell_widget):
        """Helper method to get the checkbox from the cell widget."""
        if isinstance(cell_widget, QWidget):
            # Find the checkbox within the layout
            for child in cell_widget.children():
                if isinstance(child, QCheckBox):
                    return child
        return None

    def populate_from_input(self, compliance_data):
        """Populate the table with existing compliance data"""
        for col, compliance_entry in enumerate(compliance_data, start=1):  # start=1 because column 0 is descriptions
            for row in range(self.compliance_table.rowCount()):
                description = self.compliance_table.item(row, 0).text()
                if description in compliance_entry:
                    cell_widget = self.compliance_table.cellWidget(row, col)
                    value = compliance_entry[description]
                    
                    if row == 5:  # Fire protection class (LineEdit)
                        if isinstance(cell_widget, QLineEdit):
                            cell_widget.setText(str(value))
                    else:  # Checkbox rows
                        checkbox = self.get_checkbox_from_cell_widget(cell_widget)
                        if checkbox:
                            checkbox.setChecked(bool(value))

    def collect_data_and_go_next(self):
        compliance_data = []
        for col in range(1, self.compliance_table.columnCount()):
            compliance_entry = {}
            for row in range(self.compliance_table.rowCount()):
                description = self.compliance_table.item(row, 0).text()
                cell_widget = self.compliance_table.cellWidget(row, col)
                
                if row == 5:  # Fire protection class (LineEdit)
                    value = cell_widget.text() if cell_widget.text() else ""
                else:  # Checkbox rows
                    checkbox = self.get_checkbox_from_cell_widget(cell_widget)
                    if checkbox:
                        value = checkbox.isChecked()
                    else:
                        value = False  # Default value if checkbox not found
                
                compliance_entry[description] = value
            
            compliance_data.append(compliance_entry)
        
        self.user_inputs['Compliance'] = compliance_data
        self.next_clicked.emit(self.user_inputs)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    user_inputs = {
        'BuildingSystems': ['Lift1', 'Lift2'],
        'Compliance': [
            {'EN81-70 Accessibility': True, 'EN81-71 Vandalism': False, 'EN81-72 Firefighter elevator': True, 'EN81-73 Fire emergency return': False, 'EN81-77 Seismic': True, 'EN81-58 Fire protection class for landing doors': 'A', 'EN81-76/BS 9999 Evacuation lift': True},
            {'EN81-70 Accessibility': False, 'EN81-71 Vandalism': True, 'EN81-72 Firefighter elevator': False, 'EN81-73 Fire emergency return': True, 'EN81-77 Seismic': False, 'EN81-58 Fire protection class for landing doors': 'B', 'EN81-76/BS 9999 Evacuation lift': False}
        ]
    }
    window = LiftCompliancePage(user_inputs)
    window.show()
    sys.exit(app.exec_())