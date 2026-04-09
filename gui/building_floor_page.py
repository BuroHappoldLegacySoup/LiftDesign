from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGroupBox, QScrollArea, QTableWidget, 
    QTableWidgetItem, QHeaderView, QLineEdit, QCheckBox, QPushButton, QMessageBox, QHBoxLayout,
    QFrame
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator
import sys

# Used by initUI and refresh; avoid QTableWidget.clear() — it strips horizontal headers (shows 1,2,3…).
FLOOR_TABLE_HEADERS = ['Lift', 'Floor', 'Floor Name', 'Height (m)', 'Entrances']

class EntranceTypeWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)  # Changed to QHBoxLayout for horizontal arrangement
        self.layout.setSpacing(10)  # Add some spacing between checkboxes
        self.layout.setContentsMargins(2, 2, 2, 2)

        self.none_cb = QCheckBox("None")
        self.front_cb = QCheckBox("Front")
        self.rear_cb = QCheckBox("Rear")
        self.side_cb = QCheckBox("Side")

        self.layout.addWidget(self.none_cb)
        self.layout.addWidget(self.front_cb)
        self.layout.addWidget(self.rear_cb)
        self.layout.addWidget(self.side_cb)
        self.layout.addStretch()

        self.none_cb.toggled.connect(self._on_none_toggled)
        self.front_cb.toggled.connect(self._on_direction_toggled)
        self.rear_cb.toggled.connect(self._on_direction_toggled)
        self.side_cb.toggled.connect(self._on_direction_toggled)
        self.none_cb.setChecked(True)

    def _on_none_toggled(self, checked: bool):
        if checked:
            self.front_cb.blockSignals(True)
            self.rear_cb.blockSignals(True)
            self.side_cb.blockSignals(True)
            self.front_cb.setChecked(False)
            self.rear_cb.setChecked(False)
            self.side_cb.setChecked(False)
            self.front_cb.blockSignals(False)
            self.rear_cb.blockSignals(False)
            self.side_cb.blockSignals(False)

    def _on_direction_toggled(self, checked: bool):
        if checked:
            self.none_cb.blockSignals(True)
            self.none_cb.setChecked(False)
            self.none_cb.blockSignals(False)

    def get_selected_entrances(self):
        if self.none_cb.isChecked():
            return []
        entrances = []
        if self.front_cb.isChecked():
            entrances.append("Front")
        if self.rear_cb.isChecked():
            entrances.append("Rear")
        if self.side_cb.isChecked():
            entrances.append("Side")
        return entrances

    def set_selected_entrances(self, entrances):
        if not isinstance(entrances, list):
            entrances = [entrances]  # Convert string to list for backward compatibility
        # Treat empty, explicit "None", or list containing only None as None
        norm = [str(e).strip() for e in entrances if e is not None and str(e).strip()]
        is_none = not norm or (len(norm) == 1 and norm[0].lower() == "none")
        if is_none:
            self.none_cb.setChecked(True)
            self.front_cb.setChecked(False)
            self.rear_cb.setChecked(False)
            self.side_cb.setChecked(False)
            return
        self.none_cb.setChecked(False)
        self.front_cb.setChecked("Front" in entrances)
        self.rear_cb.setChecked("Rear" in entrances)
        self.side_cb.setChecked("Side" in entrances)

class BuildingFloorPage(QWidget):
    next_clicked = pyqtSignal(dict)
    
    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        self.lifts_data = []
        self.process_lift_data()
        self.initUI()
        
        # Populate data if Floors exists in user_inputs
        if 'Floors' in self.user_inputs:
            self.populate_from_input(self.user_inputs['Floors'])

    def initUI(self):
        self.setMinimumWidth(1200)
        
        layout = QVBoxLayout(self)
        
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        
        scroll_layout = QVBoxLayout(scroll_widget)
        
        floor_box = QGroupBox("Building Floor Inputs")
        floor_box.setObjectName("floor_box")
        floor_box.setStyleSheet(
            "#floor_box {background-color: white; border: 3px solid rgb(196, 214, 0); "
            "font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(floor_box)
        
        floor_layout = QVBoxLayout(floor_box)
        
        # Create table
        self.floor_table = QTableWidget()
        self.floor_table.verticalHeader().setVisible(False)
        self.floor_table.setColumnCount(5)  # Lift, Floor, Name, Height, Entrance
        self.floor_table.setRowCount(self.total_rows)
        
        # Style the table
        self.floor_table.setStyleSheet("""
            QHeaderView::section {
                background-color: white;
                padding: 4px;
                border: 1px solid lightgray;
            }
            QTableWidget {
                gridline-color: lightgray;
            }
        """)
        
        # Set headers
        self.floor_table.setHorizontalHeaderLabels(FLOOR_TABLE_HEADERS)
        
        # Configure header behavior
        header = self.floor_table.horizontalHeader()
        for i in range(5):
            if i in [0, 1]:  # Lift and Floor columns
                header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
            else:
                header.setSectionResizeMode(i, QHeaderView.Stretch)
        
        # Initialize table content
        self.initialize_table()
        
        floor_layout.addWidget(self.floor_table)
        
        # Save and Proceed Button
        save_button = QPushButton('Save and Proceed')
        save_button.setStyleSheet("background-color: white;")
        save_button.clicked.connect(self.collect_data_and_go_next)
        scroll_layout.addWidget(save_button)

    def process_lift_data(self):
        for i, lift_system in enumerate(self.user_inputs['LiftSystems']):
            try:
                stops_value = lift_system.get('Stops (Stck.)', '')
                # Handle empty or invalid values
                if not stops_value:
                    stops = 1  # Default to 1 stop if empty
                else:
                    stops = int(stops_value)
                    if stops < 1:
                        stops = 1  # Ensure at least 1 stop
            except (ValueError, TypeError):
                stops = 1  # Default to 1 stop if conversion fails
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    f"Invalid number of stops for Lift {i+1}. Defaulting to 1 stop."
                )

            self.lifts_data.append({
                'lift_number': i + 1,
                'stops': stops
            })
        
        self.total_rows = sum(lift['stops'] for lift in self.lifts_data)

    def refresh_from_user_inputs(self):
        """Rebuild the floor table when LiftSystems (e.g. stops) changes after first load."""
        self.lifts_data = []
        self.process_lift_data()
        # clearContents() only — full clear() also removes header labels (Qt then shows numeric columns).
        self.floor_table.clearContents()
        self.floor_table.clearSpans()
        self.floor_table.setRowCount(self.total_rows)
        self.floor_table.setHorizontalHeaderLabels(FLOOR_TABLE_HEADERS)
        self.initialize_table()
        if 'Floors' in self.user_inputs:
            self.populate_from_input(self.user_inputs['Floors'])

    def populate_from_input(self, floors_data):
        """Populate the table with existing floor specification data"""
        current_row = 0

        for lift_idx, lift_data in enumerate(floors_data):
            if lift_idx >= len(self.lifts_data):
                break
            stops = self.lifts_data[lift_idx]['stops']
            # Each lift_data is a dictionary with one key like 'Lift 1'
            lift_number = list(lift_data.keys())[0]  # Get 'Lift 1'
            floors = lift_data[lift_number]  # List in ascending order: floor 0, 1, …

            for floor_idx, floor_data in enumerate(floors):
                # Table rows: top = highest floor index; saved list is ascending 0 … stops−1
                row = current_row + (stops - 1 - floor_idx)
                if row >= self.floor_table.rowCount() or row < current_row:
                    break

                # Populate Floor Name
                name_widget = self.floor_table.cellWidget(row, 2)
                if isinstance(name_widget, QLineEdit):
                    name_widget.setText(str(floor_data.get('Floor Name', '')))
                
                # Populate Height
                height_widget = self.floor_table.cellWidget(row, 3)
                if isinstance(height_widget, QLineEdit):
                    height_widget.setText(str(floor_data.get('Height (m)', '')))
                
                # Populate Entrances
                type_widget = self.floor_table.cellWidget(row, 4)
                if isinstance(type_widget, EntranceTypeWidget):
                    entrances = floor_data.get('Entrances', [])
                    type_widget.set_selected_entrances(entrances)

            current_row += stops

    def initialize_table(self):
        current_row = 0
        
        for lift in self.lifts_data:
            # Create merged cell for lift number
            lift_item = QTableWidgetItem(f"Lift {lift['lift_number']}")
            lift_item.setTextAlignment(Qt.AlignCenter)
            self.floor_table.setItem(current_row, 0, lift_item)
            self.floor_table.setSpan(current_row, 0, lift['stops'], 1)
            
            # Add floor numbers and input widgets for each floor (top row = highest; numbers 0 … stops−1)
            for floor in range(lift['stops']):
                row = current_row + floor
                display_floor = lift['stops'] - 1 - floor

                # Floor number
                floor_num = QTableWidgetItem(str(display_floor))
                floor_num.setTextAlignment(Qt.AlignCenter)
                floor_num.setFlags(floor_num.flags() & ~Qt.ItemIsEditable)
                self.floor_table.setItem(row, 1, floor_num)
                
                # Floor Name input
                floor_name = QLineEdit()
                self.floor_table.setCellWidget(row, 2, floor_name)
                
                # Height input
                height = QLineEdit()
                height.setValidator(QDoubleValidator())
                self.floor_table.setCellWidget(row, 3, height)
                
                # Entrance type checkboxes
                type_widget = EntranceTypeWidget()
                self.floor_table.setCellWidget(row, 4, type_widget)
            
            current_row += lift['stops']

    def collect_data_and_go_next(self):
        current_row = 0
        floors_data = []
        
        for lift in self.lifts_data:
            lift_floors = []
            # Read bottom-to-top so saved list stays ascending floor 0 … stops−1 (export / JSON order)
            for idx in range(lift['stops']):
                row = current_row + (lift['stops'] - 1 - idx)
                type_widget = self.floor_table.cellWidget(row, 4)
                floor_data = {
                    'Floor': self.floor_table.item(row, 1).text(),
                    'Floor Name': self.floor_table.cellWidget(row, 2).text(),
                    'Height (m)': self.floor_table.cellWidget(row, 3).text(),
                    'Entrances': type_widget.get_selected_entrances()
                }
                lift_floors.append(floor_data)
            
            floors_data.append({
                f'Lift {lift["lift_number"]}': lift_floors
            })
            current_row += lift['stops']
        
        self.user_inputs['Floors'] = floors_data
        self.next_clicked.emit(self.user_inputs)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    sample_input = {
    'LiftSystems': [
        {'Stops (Stck.)': '3'},
        {'Stops (Stck.)': '2'}
    ],
    'Floors': [
        {
            'Lift 1': [
                {'Floor': '0', 'Floor Name': 'Ground', 'Height (m)': '3.5', 'Entrances': ['Front', 'Side']},
                {'Floor': '1', 'Floor Name': 'First', 'Height (m)': '3.0', 'Entrances': ['Front']},
                {'Floor': '2', 'Floor Name': 'Second', 'Height (m)': '3.0', 'Entrances': ['Front', 'Rear', 'Side']}
            ]
        },
        {
            'Lift 2': [
                {'Floor': '0', 'Floor Name': 'Ground', 'Height (m)': '3.5', 'Entrances': ['Front', 'Rear']},
                {'Floor': '1', 'Floor Name': 'First', 'Height (m)': '3.0', 'Entrances': ['Side']}
            ]
        }
    ]
}

    ex = BuildingFloorPage(sample_input)
    ex.show()
    sys.exit(app.exec_())