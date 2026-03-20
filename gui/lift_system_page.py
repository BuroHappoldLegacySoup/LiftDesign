from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGroupBox, QPushButton, QCheckBox, QScrollArea, 
    QTableWidget, QTableWidgetItem, QHeaderView, QHBoxLayout, QLineEdit, QComboBox
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator
import sys


class LiftSystemPage(QWidget):
    next_clicked = pyqtSignal(dict)

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs['BuildingSystems'])
        self.initUI()
        
        # Populate data if LiftSystems exists in user_inputs
        if 'LiftSystems' in self.user_inputs:
            self.populate_from_input(self.user_inputs['LiftSystems'])

    def initUI(self):
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        
        scroll_layout = QVBoxLayout(scroll_widget)
        
        system_box = QGroupBox("Lift System Inputs")
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
        
        # Updated input descriptions with new rows at the top
        input_descriptions = [
            'System Type', 'System Category', 'Code Basis',
            'Control / Group', 'Counterweight location', 'Load capacity (kg)', 
            'Permissible number of persons (people)', 'Speed (m/s)', 'Acceleration (m/s²)', 
            'Jerk (m/s³)', 'Travel height (mm)', 'Stops (pcs.)', 'Number of landing doors (pcs.)', 
            'Open-through', 'Adjacent access', 'Cabin width (mm)', 'Cabin depth (mm)', 
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
            'Lift vestibule width (mm)', 'Lift vestibule depth (mm)'
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

        # Initialize the table with the specified number of lifts
        self.initialize_lift_columns()

    def populate_from_input(self, systems_data):
        """Populate the table with existing lift system data"""
        for col, system_data in enumerate(systems_data, start=1):  # start=1 because column 0 is descriptions
            for row in range(self.system_table.rowCount()):
                description = self.system_table.item(row, 0).text()
                if description in system_data:
                    cell_widget = self.system_table.cellWidget(row, col)
                    value = system_data[description]
                    
                    if row in [13, 14]:  # Checkbox rows (Open-through and Adjacent access)
                        checkbox = self.get_checkbox_from_cell_widget(cell_widget)
                        if checkbox:
                            checkbox.setChecked(bool(value))
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
            if row == 0:  # System Type
                widget = QComboBox()
                widget.addItems(['Passenger Lift', 'Service Lift', 'Waste Lift', 'Freight Lift'])
            elif row == 1:  # System Category
                widget = QComboBox()
                widget.addItems(['Traction - MR', 'Traction - MRL', 'Hydraulic - MR', 'Hydraulic - MRL'])
            elif row == 2:  # Code Basis
                widget = QComboBox()
                widget.addItems(['BS EN81'])
            elif row == 3:  # Control / Group
                widget = QComboBox()
                widget.addItems(['Simplex', 'Duplex', 'Triplex', 'Quadplex'])
            elif row == 4:  # Counterweight location
                widget = QComboBox()
                widget.addItems(['CWT-Left', 'CWT-Right', 'CWT-Rear', 'no CWT'])
            elif row == 7:  # Speed (m/s)
                widget = QComboBox()
                widget.addItems(['1,00', '1,60', '2,00', '-'])
            elif row == 9:  # Door type
                # Set door type according to CWT position logic
                widget = QLineEdit()
                cwt_widget = self.system_table.cellWidget(4, col_position)
                cwt_value = None
                if cwt_widget and isinstance(cwt_widget, QComboBox):
                    cwt_value = cwt_widget.currentText()
                # Logic: if CWT-Left, "2L"; if CWT-Right, "2R"; else "Non std. CTW"
                if cwt_value == "CWT-Left":
                    widget.setText("2L")
                elif cwt_value == "CWT-Right":
                    widget.setText("2R")
                else:
                    widget.setText("Non std. CTW")
            elif row == 18:  # Structural cabin height
                # Row 18 (Structural cabin height) = Row 17 (Clear cabin height) + 100
                # To support this, we'll set the value in the QLineEdit based on the value of row 17
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
                prev_widget = self.system_table.cellWidget(17, col_position)
                prev_value = None
                if prev_widget and isinstance(prev_widget, QLineEdit):
                    try:
                        prev_value = float(prev_widget.text())
                    except (ValueError, AttributeError):
                        prev_value = None
                if prev_value is not None:
                    widget.setText(str(prev_value + 100))
                else:
                    widget.setText("")
            
            elif row == 24: # Door fixation type
                widget = QComboBox()
                widget.addItems(['insert rail 40/22', 'insert rail 50/30', 'anchor bolts', 'steel structure'])

            elif row == 25: # Permissable sill load / Loading class
                widget = QComboBox()
                widget.addItems(['ASME-A', 'ASME-B', 'ASME-C1', 'ASME-C2', 'EN81-40%', 'EN81-60%', 'EN81-85%'])
            
            elif row == 26: # LOP type and location
                widget = QComboBox()
                widget.addItems(['in lift door frame L','in lift door frame R', 
                'flush wall panel L', 'flush wall panel R', 'wall-mounted panel L', 'wall-mounted panel R'])
            
            elif row == 27: #LIP type and location
                widget = QComboBox()
                widget.addItems(['door frame side vertical', 'door frame above horizontal', 'panel above horizontal', 
                'panel side vertical'])

            elif row == 28: # Lift maintenance panel type
                widget = QComboBox()
                widget.addItems(['inside door jamb', 'segregated panel flush', 'segregated panel wall-mounted'])

                


            elif row in [13, 14]:  # Open-through and Adjacent access (checkboxes)
                checkbox = QCheckBox()
                checkbox.setProperty("row", row)
                widget = QWidget()
                layout = QHBoxLayout(widget)
                layout.addStretch()
                layout.addWidget(checkbox)
                layout.addStretch()
                layout.setContentsMargins(0, 0, 0, 0)
                widget.setLayout(layout)
            else:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
            
            self.system_table.setCellWidget(row, col_position, widget)

    def get_checkbox_from_cell_widget(self, cell_widget):
        """Helper method to get the checkbox from the cell widget."""
        if isinstance(cell_widget, QWidget):
            # Find the checkbox within the layout
            for child in cell_widget.children():
                if isinstance(child, QCheckBox):
                    return child
        return None

    def collect_data_and_go_next(self):
        systems_data = []
        for col in range(1, self.system_table.columnCount()):
            system_data = {}
            for row in range(self.system_table.rowCount()):
                description = self.system_table.item(row, 0).text()
                cell_widget = self.system_table.cellWidget(row, col)
                
                if row in [13, 14]:  # Checkbox rows
                    checkbox = self.get_checkbox_from_cell_widget(cell_widget)
                    value = checkbox.isChecked() if checkbox else False
                elif isinstance(cell_widget, QLineEdit):
                    value = cell_widget.text()
                elif isinstance(cell_widget, QComboBox):
                    value = cell_widget.currentText()
                
                system_data[description] = value
            systems_data.append(system_data)
        
        self.user_inputs['LiftSystems'] = systems_data
        self.next_clicked.emit(self.user_inputs)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Example usage with input data
    sample_input = {
        'BuildingSystems': [
            {'Number': '1', 'System Name': 'Lift A'},
            {'Number': '2', 'System Name': 'Lift B'}
        ],
        'LiftSystems': [
            {
                'System Type': 'Passenger Lift',
                'System Category': 'MRL',
                'Code Basis': 'BS EN81',
                'Control / Group': 'Duplex',
                'Counterweight location': 'Rear (2)',
                'Load capacity (kg)': '1000',
                'Permissible number of persons (people)': '13',
                'Speed (m/s)': '1.6',
                'Open-through': True,
                'Adjacent access': False,
                'Cabin width (mm)': '1600'
            },
            {
                'System Type': 'Service Lift',
                'System Category': 'MR',
                'Code Basis': 'BS EN81',
                'Control / Group': 'Simplex',
                'Counterweight location': 'Left (3)',
                'Load capacity (kg)': '1600',
                'Permissible number of persons (people)': '21',
                'Speed (m/s)': '1.0',
                'Open-through': False,
                'Adjacent access': True,
                'Cabin width (mm)': '2000'
            }
        ]
    }
    ex = LiftSystemPage(sample_input)
    ex.show()
    sys.exit(app.exec_())