from PyQt5.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QHeaderView, QHBoxLayout, QCheckBox, QComboBox, QWidget, QVBoxLayout, QGroupBox, QPushButton, QScrollArea, QLineEdit
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtCore import pyqtSignal, Qt
import sys

class LiftEmergencyPage(QWidget):
    next_clicked = pyqtSignal(dict)

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs['BuildingSystems'])
        self.initUI()
        
        # Populate data if Emergency exists in user_inputs
        if 'Emergency' in self.user_inputs:
            self.populate_from_input(self.user_inputs['Emergency'])

    def initUI(self):
        self.setMinimumSize(800, 600)  # Set fixed size for the page

        layout = QVBoxLayout(self)
        
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        
        scroll_layout = QVBoxLayout(scroll_widget)
        
        emergency_box = QGroupBox("Lift Emergency Inputs")
        emergency_box.setObjectName("emergency_box")
        emergency_box.setStyleSheet(
            "#emergency_box {background-color: white; border: 3px solid rgb(196, 214, 0); font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(emergency_box)
        
        emergency_layout = QVBoxLayout(emergency_box)
        
        # Table for emergency inputs
        self.emergency_table = QTableWidget()
        self.emergency_table.setColumnCount(1)  # Start with one column for descriptions
        self.emergency_table.setHorizontalHeaderLabels(['Description'])
        
        # Add rows for each input type with units in the description
        input_descriptions = [
            'Smoke extraction', 'Type of fire emergency return', 'Main evacuation floor', 'Alternate evacuation floor', 
            'Permanent emergency power (A)', 'Emergency power for evacuation (A)', 'Sequence evacuation control', 
            'Type of emergency power', 'Building automation signals', 'FCC signals from lift', 'CCTV', 
            'Access control', 'Emergency call', 'Design intention'
        ]
        
        self.emergency_table.setRowCount(len(input_descriptions))
        
        for row, description in enumerate(input_descriptions):
            item = QTableWidgetItem(description)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Make the description column non-editable
            self.emergency_table.setItem(row, 0, item)
        
        self.emergency_table.horizontalHeader().setStretchLastSection(True)
        self.emergency_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Fix the dimensions of the description column
        self.emergency_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

        emergency_layout.addWidget(self.emergency_table)

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
        col_position = self.emergency_table.columnCount()
        self.emergency_table.insertColumn(col_position)
        self.emergency_table.setHorizontalHeaderItem(col_position, QTableWidgetItem(f'Lift {col_position}'))

        # Add appropriate widgets to each row in the new column
        for row in range(self.emergency_table.rowCount()):
            if row in [0, 6]:
                checkbox = QCheckBox()
                checkbox.setProperty("row", row)  # Store row information for later access
                widget = QWidget()
                layout = QHBoxLayout(widget)
                layout.addStretch()
                layout.addWidget(checkbox)
                layout.addStretch()
                layout.setContentsMargins(0, 0, 0, 0)
                widget.setLayout(layout)
                self.emergency_table.setCellWidget(row, col_position, widget)
            elif row in [1, 7, 11, 12]:
                widget = QComboBox()
                if row == 1:
                    widget.addItems(['Option 1', 'Option 2', 'Option 3'])
                elif row == 7:
                    widget.addItems(['external battery'])
                elif row == 11:
                    widget.addItems(['hall card reader'])
                elif row == 12:
                    widget.addItems(['GSM'])
                self.emergency_table.setCellWidget(row, col_position, widget)
            else:
                widget = QLineEdit()
                if row in [4, 5]:
                    widget.setValidator(QDoubleValidator())
                self.emergency_table.setCellWidget(row, col_position, widget)

    def get_checkbox_from_cell_widget(self, cell_widget):
        """Helper method to get the checkbox from the cell widget."""
        if isinstance(cell_widget, QWidget):
            # Find the checkbox within the layout
            for child in cell_widget.children():
                if isinstance(child, QCheckBox):
                    return child
        return None

    def populate_from_input(self, emergency_data):
        """Populate the table with existing emergency data"""
        for col, emergency_entry in enumerate(emergency_data, start=1):  # start=1 because column 0 is descriptions
            for row in range(self.emergency_table.rowCount()):
                description = self.emergency_table.item(row, 0).text()
                if description in emergency_entry:
                    cell_widget = self.emergency_table.cellWidget(row, col)
                    value = emergency_entry[description]
                    
                    if row in [0, 6]:  # Checkbox rows
                        checkbox = self.get_checkbox_from_cell_widget(cell_widget)
                        if checkbox:
                            checkbox.setChecked(bool(value))
                    elif row in [1, 7, 11, 12]:  # ComboBox rows
                        if isinstance(cell_widget, QComboBox):
                            index = cell_widget.findText(value)
                            if index >= 0:
                                cell_widget.setCurrentIndex(index)
                    else:  # LineEdit rows
                        if isinstance(cell_widget, QLineEdit):
                            cell_widget.setText(str(value))

    def collect_data_and_go_next(self):
        emergency_data = []
        for col in range(1, self.emergency_table.columnCount()):
            emergency_entry = {}
            for row in range(self.emergency_table.rowCount()):
                description = self.emergency_table.item(row, 0).text()
                cell_widget = self.emergency_table.cellWidget(row, col)
                
                if row in [0, 6]:  # Checkbox rows
                    checkbox = self.get_checkbox_from_cell_widget(cell_widget)
                    value = checkbox.isChecked() if checkbox else False
                elif row in [1, 7, 11, 12]:  # ComboBox rows
                    value = cell_widget.currentText() if isinstance(cell_widget, QComboBox) else ""
                else:  # LineEdit rows
                    value = cell_widget.text() if isinstance(cell_widget, QLineEdit) else ""
                
                emergency_entry[description] = value
            
            emergency_data.append(emergency_entry)
        
        self.user_inputs['Emergency'] = emergency_data
        self.next_clicked.emit(self.user_inputs)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    user_inputs = {
        'BuildingSystems': ['Lift1', 'Lift2'],
        'Emergency': [
            {'Smoke extraction': True, 'Type of fire emergency return': 'Option 1', 'Main evacuation floor': '1', 'Alternate evacuation floor': '2', 'Permanent emergency power (A)': '10', 'Emergency power for evacuation (A)': '5', 'Sequence evacuation control': True, 'Type of emergency power': 'external battery', 'Building automation signals': 'Yes', 'FCC signals from lift': 'Yes', 'CCTV': 'Yes', 'Access control': 'hall card reader', 'Emergency call': 'GSM', 'Design intention': 'Standard'},
            {'Smoke extraction': False, 'Type of fire emergency return': 'Option 2', 'Main evacuation floor': '3', 'Alternate evacuation floor': '4', 'Permanent emergency power (A)': '20', 'Emergency power for evacuation (A)': '15', 'Sequence evacuation control': False, 'Type of emergency power': 'external battery', 'Building automation signals': 'No', 'FCC signals from lift': 'No', 'CCTV': 'No', 'Access control': 'hall card reader', 'Emergency call': 'GSM', 'Design intention': 'Custom'}
        ]
    }
    window = LiftEmergencyPage(user_inputs)
    window.show()
    sys.exit(app.exec_())
