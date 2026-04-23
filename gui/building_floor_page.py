import copy

from .project_lift_schema import (
    KEY_FLOORS,
    KEY_GENERAL_SPECIFICATION,
    ensure_lift_section_slots,
    merged_lift_at,
    normalize_project_lift_data,
)

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGroupBox, QScrollArea, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QCheckBox, QPushButton, QMessageBox, QHBoxLayout,
    QFrame, QLabel, QComboBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator
import sys

# Used by initUI and table rebuild; avoid QTableWidget.clear() — it strips horizontal headers (shows 1,2,3…).
FLOOR_TABLE_HEADERS = ['Lift', 'Floor', 'Floor Name', 'Elevation (m)', 'Entrances']

# Absolute elevation of each floor slab above a project datum, in metres. The LD
# export maps this value (×1000 mm) directly to ``FLL.Level{i}.Z_POT``. Older saved
# projects stored the per-floor *height increment* under ``Height (m)`` — read paths
# fall back to that legacy key so they still load.
FLOOR_ELEVATION_KEY = 'Elevation (m)'
FLOOR_ELEVATION_LEGACY_KEY = 'Height (m)'


def _read_floor_elevation(floor_data: dict) -> str:
    """Return the floor's elevation, accepting the legacy ``Height (m)`` key."""
    v = floor_data.get(FLOOR_ELEVATION_KEY, '')
    if str(v).strip() == '':
        v = floor_data.get(FLOOR_ELEVATION_LEGACY_KEY, '')
    return str(v) if v is not None else ''

# General specification keys — table row count follows *Number of floors*; *Stops* is fallback for older JSON.
LS_KEY_NUM_FLOORS = 'Number of floors'
LS_KEY_STOPS = 'Stops'

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
        """Return JSON-serializable entrance list (``[\"None\"]`` when None is selected)."""
        if self.none_cb.isChecked():
            # Explicit marker so copy/load/save can distinguish from “unset” (empty list, all off).
            return ["None"]
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
        norm = [str(e).strip() for e in entrances if e is not None and str(e).strip()]
        if not norm:
            # Legacy / unset: no direction and not “None”.
            self.none_cb.setChecked(False)
            self.front_cb.setChecked(False)
            self.rear_cb.setChecked(False)
            self.side_cb.setChecked(False)
            return
        if len(norm) == 1 and norm[0].lower() == "none":
            self.none_cb.blockSignals(True)
            self.front_cb.blockSignals(True)
            self.rear_cb.blockSignals(True)
            self.side_cb.blockSignals(True)
            self.none_cb.setChecked(True)
            self.front_cb.setChecked(False)
            self.rear_cb.setChecked(False)
            self.side_cb.setChecked(False)
            self.none_cb.blockSignals(False)
            self.front_cb.blockSignals(False)
            self.rear_cb.blockSignals(False)
            self.side_cb.blockSignals(False)
            return
        self.none_cb.setChecked(False)
        self.front_cb.setChecked("Front" in entrances)
        self.rear_cb.setChecked("Rear" in entrances)
        self.side_cb.setChecked("Side" in entrances)

class BuildingFloorPage(QWidget):
    next_clicked = pyqtSignal(dict)
    back_clicked = pyqtSignal()

    @staticmethod
    def _lift_floor_key(lift_idx: int) -> str:
        return f"Lift {lift_idx + 1}"

    @staticmethod
    def _floor_rows_from_saved_lift_dict(lift_idx: int, lift_data: object) -> list:
        """Floor dict list for ``lift_idx`` — always use canonical key ``Lift N`` (not ``keys()[0]``)."""
        key = BuildingFloorPage._lift_floor_key(lift_idx)
        if not isinstance(lift_data, dict):
            return []
        if key in lift_data:
            v = lift_data[key]
            return list(v) if isinstance(v, list) else []
        # Legacy single-lift files sometimes used only ``Lift 1`` as the inner key.
        if lift_idx == 0 and len(lift_data) == 1:
            v = next(iter(lift_data.values()))
            return list(v) if isinstance(v, list) else []
        return []

    @staticmethod
    def _floor_row_count_from_lift_system(lift_system: dict) -> int:
        """
        Rows per lift = General specification **Number of floors** when set;
        otherwise **Stops** for legacy projects.
        Returns ``0`` when neither is set so callers can fall back to saved ``Floors`` JSON.
        """
        for key in (
            LS_KEY_NUM_FLOORS,
            LS_KEY_STOPS,
            'Number of floors (Stck.)',
            'Stops (Stck.)',
        ):
            raw = lift_system.get(key, '')
            if raw is None or not str(raw).strip():
                continue
            try:
                n = int(str(raw).strip())
                if n >= 1:
                    return n
            except (ValueError, TypeError):
                continue
        return 0

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        normalize_project_lift_data(self.user_inputs)
        self.lifts_data = []
        self.process_lift_data()
        self.initUI()
        
        # Populate data if Floors exists in user_inputs
        if KEY_FLOORS in self.user_inputs:
            self.populate_from_input(self.user_inputs[KEY_FLOORS])

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

        copy_row = QHBoxLayout()
        copy_row.addWidget(QLabel("Copy floor rows from"))
        self._copy_from_combo = QComboBox()
        self._copy_to_combo = QComboBox()
        copy_row.addWidget(self._copy_from_combo)
        copy_row.addWidget(QLabel("to"))
        copy_row.addWidget(self._copy_to_combo)
        self._copy_floors_btn = QPushButton("Copy")
        self._copy_floors_btn.setStyleSheet("background-color: white;")
        self._copy_floors_btn.clicked.connect(self._on_copy_floors_clicked)
        copy_row.addWidget(self._copy_floors_btn)
        self._populate_copy_lift_combos()
        copy_row.addStretch()
        floor_layout.addLayout(copy_row)

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
        
        # Save and Proceed / Back
        save_button = QPushButton('Save and Proceed')
        save_button.setStyleSheet("background-color: white;")
        save_button.clicked.connect(self.collect_data_and_go_next)
        nav_row = QHBoxLayout()
        back_button = QPushButton('← Back to previous page')
        back_button.setStyleSheet("background-color: white;")
        back_button.clicked.connect(self.back_clicked.emit)
        nav_row.addWidget(back_button)
        nav_row.addStretch()
        nav_row.addWidget(save_button)
        scroll_layout.addLayout(nav_row)

    def process_lift_data(self):
        self.lifts_data = []
        n_lifts = len(self.user_inputs.get('BuildingSystems') or [])
        floors_top = self.user_inputs.get(KEY_FLOORS) or []
        for i in range(n_lifts):
            lift_system = merged_lift_at(self.user_inputs, i)
            n = self._floor_row_count_from_lift_system(lift_system)
            if n < 1:
                saved = []
                if i < len(floors_top) and isinstance(floors_top[i], dict):
                    saved = self._floor_rows_from_saved_lift_dict(i, floors_top[i])
                n = len(saved) if saved else 0
            if n < 1:
                n = 1
            self.lifts_data.append({
                'lift_number': i + 1,
                'num_floors': n,
            })

        self.total_rows = sum(lift['num_floors'] for lift in self.lifts_data)

    def _rebuild_floor_table_from_stored_inputs(self):
        """Rebuild row structure and widgets, then fill from ``user_inputs['Floors']``."""
        self.floor_table.clearContents()
        self.floor_table.clearSpans()
        self.floor_table.setRowCount(self.total_rows)
        self.floor_table.setHorizontalHeaderLabels(FLOOR_TABLE_HEADERS)
        self.initialize_table()
        if KEY_FLOORS in self.user_inputs:
            self.populate_from_input(self.user_inputs[KEY_FLOORS])

    def refresh_from_project_data(self) -> None:
        """Re-read ``user_inputs['Floors']`` after JSON load or when revisiting this tab (same as page 2)."""
        normalize_project_lift_data(self.user_inputs)
        self.lifts_data = []
        self.process_lift_data()
        if self.floor_table.rowCount() != self.total_rows:
            self._rebuild_floor_table_from_stored_inputs()
        elif KEY_FLOORS in self.user_inputs:
            self.populate_from_input(self.user_inputs[KEY_FLOORS])
        self._populate_copy_lift_combos()

    def _populate_one_lift_from_floor_list(self, lift_idx: int, floors: list) -> None:
        """Apply floor dicts to one lift’s rows (same top-to-bottom mapping as populate_from_input)."""
        if lift_idx >= len(self.lifts_data):
            return
        current_row = sum(self.lifts_data[i]['num_floors'] for i in range(lift_idx))
        nf = self.lifts_data[lift_idx]['num_floors']
        for floor_idx, floor_data in enumerate(floors):
            if floor_idx >= nf:
                break
            row = current_row + (nf - 1 - floor_idx)
            if row >= self.floor_table.rowCount() or row < current_row:
                break
            name_widget = self.floor_table.cellWidget(row, 2)
            if isinstance(name_widget, QLineEdit):
                name_widget.setText(str(floor_data.get('Floor Name', '')))
            height_widget = self.floor_table.cellWidget(row, 3)
            if isinstance(height_widget, QLineEdit):
                height_widget.setText(_read_floor_elevation(floor_data))
            type_widget = self.floor_table.cellWidget(row, 4)
            if isinstance(type_widget, EntranceTypeWidget):
                type_widget.set_selected_entrances(floor_data.get('Entrances', []))

    def populate_from_input(self, floors_data):
        """Populate the table with existing floor specification data"""
        current_row = 0

        for lift_idx, lift_data in enumerate(floors_data):
            if lift_idx >= len(self.lifts_data):
                break
            nf = self.lifts_data[lift_idx]['num_floors']
            floors = self._floor_rows_from_saved_lift_dict(lift_idx, lift_data)

            for floor_idx, floor_data in enumerate(floors):
                # Table rows: top = highest floor index; saved list is ascending 0 … n−1
                row = current_row + (nf - 1 - floor_idx)
                if row >= self.floor_table.rowCount() or row < current_row:
                    break

                # Populate Floor Name
                name_widget = self.floor_table.cellWidget(row, 2)
                if isinstance(name_widget, QLineEdit):
                    name_widget.setText(str(floor_data.get('Floor Name', '')))
                
                # Populate Elevation (legacy projects may carry "Height (m)")
                height_widget = self.floor_table.cellWidget(row, 3)
                if isinstance(height_widget, QLineEdit):
                    height_widget.setText(_read_floor_elevation(floor_data))
                
                # Populate Entrances
                type_widget = self.floor_table.cellWidget(row, 4)
                if isinstance(type_widget, EntranceTypeWidget):
                    entrances = floor_data.get('Entrances', [])
                    type_widget.set_selected_entrances(entrances)

            current_row += nf

    def initialize_table(self):
        current_row = 0
        
        for lift in self.lifts_data:
            # Create merged cell for lift number
            lift_item = QTableWidgetItem(f"Lift {lift['lift_number']}")
            lift_item.setTextAlignment(Qt.AlignCenter)
            self.floor_table.setItem(current_row, 0, lift_item)
            self.floor_table.setSpan(current_row, 0, lift['num_floors'], 1)

            # Add floor numbers and input widgets for each floor (top row = highest; numbers 0 … n−1)
            for floor in range(lift['num_floors']):
                row = current_row + floor
                display_floor = lift['num_floors'] - 1 - floor

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
            
            current_row += lift['num_floors']

    def _floors_dict_from_table_rows(self, lifts_data_list):
        """Serialize the floor table using the given per-lift row geometry (same layout as ``populate_from_input``)."""
        current_row = 0
        floors_data = []
        for lift in lifts_data_list:
            lift_floors = []
            nf = lift['num_floors']
            for idx in range(nf):
                row = current_row + (nf - 1 - idx)
                if row >= self.floor_table.rowCount() or row < current_row:
                    break
                type_widget = self.floor_table.cellWidget(row, 4)
                floor_item = self.floor_table.item(row, 1)
                floor_num = floor_item.text() if floor_item is not None else str(idx)
                name_w = self.floor_table.cellWidget(row, 2)
                height_w = self.floor_table.cellWidget(row, 3)
                if isinstance(type_widget, EntranceTypeWidget):
                    entrances = type_widget.get_selected_entrances()
                else:
                    entrances = []
                floor_data = {
                    'Floor': floor_num,
                    'Floor Name': name_w.text() if isinstance(name_w, QLineEdit) else '',
                    FLOOR_ELEVATION_KEY: height_w.text() if isinstance(height_w, QLineEdit) else '',
                    'Entrances': entrances,
                }
                lift_floors.append(floor_data)

            floors_data.append({
                self._lift_floor_key(lift["lift_number"] - 1): lift_floors
            })
            current_row += nf
        return floors_data

    def _merge_floors_built_with_prior(self, built: list, prior: list, lifts_data_list: list) -> list:
        """If the table yielded no rows for a lift that should have ``nf`` floors, keep prior JSON for that lift."""
        if not prior:
            return built
        out = list(built)
        n = len(lifts_data_list)
        for i in range(n):
            nf = lifts_data_list[i]["num_floors"]
            key = self._lift_floor_key(i)
            new_list: list = []
            if i < len(out) and isinstance(out[i], dict):
                new_list = out[i].get(key)
                if not isinstance(new_list, list):
                    new_list = []
            if len(new_list) == 0 and nf > 0 and i < len(prior):
                old = prior[i]
                if isinstance(old, dict) and key in old:
                    old_list = old[key]
                    if isinstance(old_list, list) and len(old_list) > 0:
                        while len(out) <= i:
                            out.append({self._lift_floor_key(len(out)): []})
                        out[i] = {key: copy.deepcopy(old_list)}
        return out

    def sync_floors_to_user_inputs(self):
        """Write the floor table into ``user_inputs['Floors']`` (used when leaving this tab and before JSON save)."""
        normalize_project_lift_data(self.user_inputs)
        prior_floors = copy.deepcopy(self.user_inputs.get(KEY_FLOORS) or [])
        old_lifts = copy.deepcopy(self.lifts_data)
        self.process_lift_data()
        if self.floor_table.rowCount() != self.total_rows:
            # Persist widgets using the previous row layout so edits are not lost, then realign the grid.
            if old_lifts:
                self.user_inputs[KEY_FLOORS] = self._floors_dict_from_table_rows(old_lifts)
            self._rebuild_floor_table_from_stored_inputs()

        built = self._floors_dict_from_table_rows(self.lifts_data)
        self.user_inputs[KEY_FLOORS] = self._merge_floors_built_with_prior(
            built, prior_floors, self.lifts_data
        )

    def collect_data_and_go_next(self):
        self.sync_floors_to_user_inputs()
        self.next_clicked.emit(self.user_inputs)

    def _populate_copy_lift_combos(self):
        """Fill From/To combos with Lift 1 … Lift N (1-based item data)."""
        self._copy_from_combo.clear()
        self._copy_to_combo.clear()
        n = len(self.lifts_data)
        for i in range(n):
            self._copy_from_combo.addItem(f"Lift {i + 1}", i + 1)
            self._copy_to_combo.addItem(f"Lift {i + 1}", i + 1)
        if n >= 2:
            self._copy_to_combo.setCurrentIndex(1)
        else:
            self._copy_to_combo.setCurrentIndex(0)
        self._copy_floors_btn.setEnabled(n >= 2)

    def _read_lift_floor_data(self, lift_idx: int) -> list:
        """Collect floor dicts for one lift from the current table (same shape as JSON / collect_data)."""
        current_row = 0
        for i, lift in enumerate(self.lifts_data):
            if i == lift_idx:
                lift_floors = []
                nf = lift["num_floors"]
                for idx in range(nf):
                    row = current_row + (nf - 1 - idx)
                    tw = self.floor_table.cellWidget(row, 4)
                    floor_item = self.floor_table.item(row, 1)
                    floor_num = floor_item.text() if floor_item is not None else str(idx)
                    name_w = self.floor_table.cellWidget(row, 2)
                    height_w = self.floor_table.cellWidget(row, 3)
                    entrances = tw.get_selected_entrances() if isinstance(tw, EntranceTypeWidget) else []
                    lift_floors.append({
                        "Floor": floor_num,
                        "Floor Name": name_w.text() if isinstance(name_w, QLineEdit) else "",
                        FLOOR_ELEVATION_KEY: height_w.text() if isinstance(height_w, QLineEdit) else "",
                        "Entrances": entrances,
                    })
                return lift_floors
            current_row += lift["num_floors"]
        return []

    def _ensure_floors_list_length(self, min_len: int) -> None:
        floors = self.user_inputs.setdefault(KEY_FLOORS, [])
        while len(floors) < min_len:
            floors.append({f"Lift {len(floors) + 1}": []})

    def _on_copy_floors_clicked(self):
        from_no = self._copy_from_combo.currentData()
        to_no = self._copy_to_combo.currentData()
        if from_no is None or to_no is None:
            return
        if from_no == to_no:
            QMessageBox.information(
                self,
                "Copy floors",
                "Choose two different lifts.",
            )
            return
        self._copy_floor_rows_between_lifts(from_no - 1, to_no - 1)

    def _copy_floor_rows_between_lifts(self, from_idx: int, to_idx: int) -> None:
        """Copy table floor data from one lift to another and mirror **Number of floors** in GeneralSpecification."""
        # Persist every lift's current table into ``Floors`` first so the source lift is not lost
        # when updating the destination in ``user_inputs``.
        self.sync_floors_to_user_inputs()

        floors_list = self.user_inputs.get(KEY_FLOORS) or []
        if from_idx >= len(floors_list):
            QMessageBox.warning(
                self,
                "Copy floors",
                "No saved floor data for the source lift.",
            )
            return
        src_key = f"Lift {from_idx + 1}"
        src_entry = floors_list[from_idx]
        if src_key not in src_entry:
            QMessageBox.warning(
                self,
                "Copy floors",
                "No saved floor data for the source lift.",
            )
            return
        source_floors = copy.deepcopy(src_entry[src_key])
        if not source_floors:
            QMessageBox.warning(
                self,
                "Copy floors",
                "No floor rows found for the source lift.",
            )
            return

        ensure_lift_section_slots(
            self.user_inputs,
            len(self.user_inputs.get('BuildingSystems') or []),
        )
        gen = self.user_inputs[KEY_GENERAL_SPECIFICATION]
        src_sys = gen[from_idx]
        dst_sys = gen[to_idx]
        raw_nf = src_sys.get(LS_KEY_NUM_FLOORS, "")
        if raw_nf is not None and str(raw_nf).strip():
            dst_sys[LS_KEY_NUM_FLOORS] = str(raw_nf).strip()
        else:
            dst_sys[LS_KEY_NUM_FLOORS] = str(len(source_floors))

        self._ensure_floors_list_length(to_idx + 1)
        self.user_inputs[KEY_FLOORS][to_idx] = {
            f"Lift {to_idx + 1}": copy.deepcopy(source_floors),
        }

        old_nf = [lift["num_floors"] for lift in self.lifts_data]
        self.lifts_data = []
        self.process_lift_data()
        new_nf = [lift["num_floors"] for lift in self.lifts_data]
        if old_nf != new_nf or self.floor_table.rowCount() != self.total_rows:
            self._rebuild_floor_table_from_stored_inputs()
        else:
            self._populate_one_lift_from_floor_list(to_idx, source_floors)

        self._populate_copy_lift_combos()
        QMessageBox.information(
            self,
            "Copy floors",
            f"Copied floor rows from Lift {from_idx + 1} to Lift {to_idx + 1}. "
            f'"{LS_KEY_NUM_FLOORS}" was updated for Lift {to_idx + 1} (General specification).',
        )


if __name__ == '__main__':
    app = QApplication(sys.argv)
    sample_input = {
    'BuildingSystems': [{'Number': '1'}, {'Number': '2'}],
    'GeneralSpecification': [
        {'Number of floors': '3', 'Stops': '5'},
        {'Number of floors': '2', 'Stops': '4'},
    ],
    'LayoutInformation': [{}, {}],
    'Floors': [
        {
            'Lift 1': [
                {'Floor': '0', 'Floor Name': 'Ground', 'Elevation (m)': '0.0', 'Entrances': ['Front', 'Side']},
                {'Floor': '1', 'Floor Name': 'First', 'Elevation (m)': '3.5', 'Entrances': ['Front']},
                {'Floor': '2', 'Floor Name': 'Second', 'Elevation (m)': '6.5', 'Entrances': ['Front', 'Rear', 'Side']}
            ]
        },
        {
            'Lift 2': [
                {'Floor': '0', 'Floor Name': 'Ground', 'Elevation (m)': '0.0', 'Entrances': ['Front', 'Rear']},
                {'Floor': '1', 'Floor Name': 'First', 'Elevation (m)': '3.5', 'Entrances': ['Side']}
            ]
        }
    ]
}

    ex = BuildingFloorPage(sample_input)
    ex.show()
    sys.exit(app.exec_())