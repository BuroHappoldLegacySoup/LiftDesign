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
    QLabel, QComboBox, QFrame,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator
import sys

# Absolute elevation of each floor slab above a project datum, in metres. The LD
# export maps this value (×1000 mm) directly to ``FLL.Level{i}.Z_POT``. Older saved
# projects stored the per-floor *height increment* under ``Height (m)`` — read paths
# fall back to that legacy key so they still load.
FLOOR_ELEVATION_KEY = 'Elevation (m)'
FLOOR_ELEVATION_LEGACY_KEY = 'Height (m)'

ENTRANCE_SIDE1 = 'Side 1'
ENTRANCE_SIDE2 = 'Side 2'
ENTRANCE_NONE = 'None'
ENTRANCE_FRONT = 'Front'
ENTRANCE_BACK = 'Back'


def _read_floor_elevation(floor_data: dict) -> str:
    """Return the floor's elevation, accepting the legacy ``Height (m)`` key."""
    v = floor_data.get(FLOOR_ELEVATION_KEY, '')
    if str(v).strip() == '':
        v = floor_data.get(FLOOR_ELEVATION_LEGACY_KEY, '')
    return str(v) if v is not None else ''


class LiftEntrancesCell(QFrame):
    """Order in UI and JSON: None, Front, Back, Side 1, Side 2. ``None`` excludes other directions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(8)
        self.none_cb = QCheckBox('None')
        self.front_cb = QCheckBox('Front')
        self.back_cb = QCheckBox('Back')
        self.side1_cb = QCheckBox('Side 1')
        self.side2_cb = QCheckBox('Side 2')
        # Visual order: None, Front, Back, Side 1, Side 2
        lay.addWidget(self.none_cb)
        lay.addWidget(self.front_cb)
        lay.addWidget(self.back_cb)
        lay.addWidget(self.side1_cb)
        lay.addWidget(self.side2_cb)
        lay.addStretch()

        self.none_cb.toggled.connect(self._on_none_toggled)
        self.front_cb.toggled.connect(self._on_direction_toggled)
        self.back_cb.toggled.connect(self._on_direction_toggled)
        self.side1_cb.toggled.connect(self._on_direction_toggled)
        self.side2_cb.toggled.connect(self._on_direction_toggled)

    def _all_direction_checks(self):
        return (self.front_cb, self.back_cb, self.side1_cb, self.side2_cb)

    def _on_none_toggled(self, checked: bool) -> None:
        if checked:
            for cb in self._all_direction_checks():
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)

    def _on_direction_toggled(self, checked: bool) -> None:
        if checked:
            self.none_cb.blockSignals(True)
            self.none_cb.setChecked(False)
            self.none_cb.blockSignals(False)

    def entrances_to_json(self) -> list:
        """Checked values in canonical order: None, Front, Back, Side 1, Side 2."""
        if self.none_cb.isChecked():
            return [ENTRANCE_NONE]
        out = []
        if self.front_cb.isChecked():
            out.append(ENTRANCE_FRONT)
        if self.back_cb.isChecked():
            out.append(ENTRANCE_BACK)
        if self.side1_cb.isChecked():
            out.append(ENTRANCE_SIDE1)
        if self.side2_cb.isChecked():
            out.append(ENTRANCE_SIDE2)
        return out

    def set_entrances_from_json(self, entrances) -> None:
        """Restore from ``Floors`` JSON; map legacy Rear → Back, Side → both sides."""
        if not isinstance(entrances, list):
            entrances = [entrances] if entrances else []
        norm = [str(e).strip() for e in entrances if e is not None and str(e).strip()]
        for cb in (self.none_cb, self.front_cb, self.back_cb, self.side1_cb, self.side2_cb):
            cb.blockSignals(True)
        try:
            if len(norm) == 1 and norm[0].lower() == 'none':
                self.none_cb.setChecked(True)
                for cb in self._all_direction_checks():
                    cb.setChecked(False)
                return
            self.none_cb.setChecked(False)
            low = {x.lower() for x in norm}
            self.front_cb.setChecked(
                ENTRANCE_FRONT in norm or 'front' in low
            )
            self.back_cb.setChecked(
                ENTRANCE_BACK in norm or 'rear' in low or 'back' in low
            )
            has_side12 = ENTRANCE_SIDE1 in norm or ENTRANCE_SIDE2 in norm
            loose_side = any(str(x).strip() == 'Side' for x in norm) and not has_side12
            self.side1_cb.setChecked(ENTRANCE_SIDE1 in norm or loose_side)
            self.side2_cb.setChecked(ENTRANCE_SIDE2 in norm or loose_side)
        finally:
            for cb in (self.none_cb, self.front_cb, self.back_cb, self.side1_cb, self.side2_cb):
                cb.blockSignals(False)


# General specification keys — row count follows *Number of floors*; *Stops* is fallback for older JSON.
LS_KEY_NUM_FLOORS = 'Number of floors'
LS_KEY_STOPS = 'Stops'


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
        if lift_idx == 0 and len(lift_data) == 1:
            v = next(iter(lift_data.values()))
            return list(v) if isinstance(v, list) else []
        return []

    @staticmethod
    def _floor_row_count_from_lift_system(lift_system: dict) -> int:
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
        self.num_floor_rows = 1
        self.process_lift_data()
        self.initUI()

        if KEY_FLOORS in self.user_inputs:
            self.populate_from_input(self.user_inputs[KEY_FLOORS])

    def _build_horizontal_header_labels(self) -> list:
        n_lifts = len(self.lifts_data)
        labels = ['Floor', 'Floor Name', 'Elevation (m)']
        for i in range(n_lifts):
            labels.append(f'Lift {i + 1} - entrances')
        return labels

    def _col_entrances(self, lift_idx: int) -> int:
        return 3 + lift_idx

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

        n_lifts = max(len(self.lifts_data), 1)
        n_cols = 3 + n_lifts

        self.floor_table = QTableWidget()
        self.floor_table.verticalHeader().setVisible(False)
        self.floor_table.setColumnCount(n_cols)
        self.floor_table.setRowCount(self.num_floor_rows)

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

        self.floor_table.setHorizontalHeaderLabels(self._build_horizontal_header_labels())

        header = self.floor_table.horizontalHeader()
        for i in range(n_cols):
            if i < 3:
                header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
            else:
                header.setSectionResizeMode(i, QHeaderView.Stretch)

        self.initialize_table()

        floor_layout.addWidget(self.floor_table)

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
        nfs = []
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
            nfs.append(n)

        self.num_floor_rows = max(nfs) if nfs else 1
        # Keep column headers/widgets aligned when BuildingSystems is temporarily empty.
        if not self.lifts_data:
            self.lifts_data.append({'lift_number': 1, 'num_floors': self.num_floor_rows})

    def _set_table_geometry(self) -> None:
        """Column count and headers after lift list changes."""
        n_lifts = len(self.lifts_data)
        n_cols = 3 + n_lifts
        self.floor_table.setColumnCount(n_cols)
        self.floor_table.setHorizontalHeaderLabels(self._build_horizontal_header_labels())
        header = self.floor_table.horizontalHeader()
        for i in range(n_cols):
            if i < 3:
                header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
            else:
                header.setSectionResizeMode(i, QHeaderView.Stretch)

    def _rebuild_floor_table_from_stored_inputs(self) -> None:
        self.floor_table.clearContents()
        self.floor_table.clearSpans()
        self._set_table_geometry()
        self.floor_table.setRowCount(self.num_floor_rows)
        self.initialize_table()
        if KEY_FLOORS in self.user_inputs:
            self.populate_from_input(self.user_inputs[KEY_FLOORS])

    def refresh_from_project_data(self) -> None:
        normalize_project_lift_data(self.user_inputs)
        self.lifts_data = []
        self.process_lift_data()
        if self.floor_table.rowCount() != self.num_floor_rows or self.floor_table.columnCount() != 3 + len(self.lifts_data):
            self._rebuild_floor_table_from_stored_inputs()
        elif KEY_FLOORS in self.user_inputs:
            self.populate_from_input(self.user_inputs[KEY_FLOORS])
        self._populate_copy_lift_combos()

    def _global_row_for_lift_floor_index(self, lift_idx: int, floor_idx: int) -> int:
        """Map saved list index ``floor_idx`` (0 = lowest floor) to table row (top = highest)."""
        return self.num_floor_rows - 1 - floor_idx

    def _lift_serves_row(self, lift_idx: int, global_row: int) -> bool:
        nf = self.lifts_data[lift_idx]['num_floors']
        bottom_start = self.num_floor_rows - nf
        return global_row >= bottom_start

    def _populate_one_lift_from_floor_list(self, lift_idx: int, floors: list) -> None:
        if lift_idx >= len(self.lifts_data):
            return
        nf = self.lifts_data[lift_idx]['num_floors']
        for floor_idx, floor_data in enumerate(floors):
            if floor_idx >= nf:
                break
            row = self._global_row_for_lift_floor_index(lift_idx, floor_idx)
            if row < 0 or row >= self.floor_table.rowCount():
                continue
            cell = self.floor_table.cellWidget(row, self._col_entrances(lift_idx))
            if isinstance(cell, LiftEntrancesCell):
                cell.set_entrances_from_json(floor_data.get('Entrances', []))

    def populate_from_input(self, floors_data):
        # Shared floor name / elevation: take from the first lift that has each row.
        filled_shared = set()
        for lift_idx, lift_data in enumerate(floors_data):
            if lift_idx >= len(self.lifts_data):
                break
            nf = self.lifts_data[lift_idx]['num_floors']
            floors = self._floor_rows_from_saved_lift_dict(lift_idx, lift_data)
            for floor_idx, floor_data in enumerate(floors):
                if floor_idx >= nf:
                    break
                row = self._global_row_for_lift_floor_index(lift_idx, floor_idx)
                if row < 0 or row >= self.floor_table.rowCount() or row in filled_shared:
                    continue
                name_w = self.floor_table.cellWidget(row, 1)
                el_w = self.floor_table.cellWidget(row, 2)
                if isinstance(name_w, QLineEdit):
                    name_w.setText(str(floor_data.get('Floor Name', '')))
                if isinstance(el_w, QLineEdit):
                    el_w.setText(_read_floor_elevation(floor_data))
                filled_shared.add(row)

        for lift_idx, lift_data in enumerate(floors_data):
            if lift_idx >= len(self.lifts_data):
                break
            floors = self._floor_rows_from_saved_lift_dict(lift_idx, lift_data)
            self._populate_one_lift_from_floor_list(lift_idx, floors)

    def initialize_table(self):
        for row in range(self.num_floor_rows):
            display_floor = self.num_floor_rows - 1 - row
            floor_num = QTableWidgetItem(str(display_floor))
            floor_num.setTextAlignment(Qt.AlignCenter)
            floor_num.setFlags(floor_num.flags() & ~Qt.ItemIsEditable)
            self.floor_table.setItem(row, 0, floor_num)

            name_w = QLineEdit()
            self.floor_table.setCellWidget(row, 1, name_w)

            el_w = QLineEdit()
            el_w.setValidator(QDoubleValidator())
            self.floor_table.setCellWidget(row, 2, el_w)

            for lift_idx in range(len(self.lifts_data)):
                cell = LiftEntrancesCell()
                active = self._lift_serves_row(lift_idx, row)
                cell.setEnabled(active)
                self.floor_table.setCellWidget(row, self._col_entrances(lift_idx), cell)

    def _floors_dict_from_table_rows(self, lifts_data_list):
        floors_data = []
        for lift_idx, lift in enumerate(lifts_data_list):
            lift_floors = []
            nf = lift['num_floors']
            for idx in range(nf):
                row = self._global_row_for_lift_floor_index(lift_idx, idx)
                if row < 0 or row >= self.floor_table.rowCount():
                    break
                floor_item = self.floor_table.item(row, 0)
                floor_num = floor_item.text() if floor_item is not None else str(idx)
                name_w = self.floor_table.cellWidget(row, 1)
                height_w = self.floor_table.cellWidget(row, 2)
                cell = self.floor_table.cellWidget(row, self._col_entrances(lift_idx))
                entrances = cell.entrances_to_json() if isinstance(cell, LiftEntrancesCell) else []
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
        return floors_data

    def _merge_floors_built_with_prior(self, built: list, prior: list, lifts_data_list: list) -> list:
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
        normalize_project_lift_data(self.user_inputs)
        prior_floors = copy.deepcopy(self.user_inputs.get(KEY_FLOORS) or [])
        old_lifts = copy.deepcopy(self.lifts_data)
        self.process_lift_data()
        need_rebuild = (
            self.floor_table.rowCount() != self.num_floor_rows
            or self.floor_table.columnCount() != 3 + len(self.lifts_data)
        )
        if need_rebuild:
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
        if lift_idx >= len(self.lifts_data):
            return []
        lift_floors = []
        nf = self.lifts_data[lift_idx]["num_floors"]
        for idx in range(nf):
            row = self._global_row_for_lift_floor_index(lift_idx, idx)
            cell = self.floor_table.cellWidget(row, self._col_entrances(lift_idx))
            floor_item = self.floor_table.item(row, 0)
            floor_num = floor_item.text() if floor_item is not None else str(idx)
            name_w = self.floor_table.cellWidget(row, 1)
            height_w = self.floor_table.cellWidget(row, 2)
            entrances = cell.entrances_to_json() if isinstance(cell, LiftEntrancesCell) else []
            lift_floors.append({
                "Floor": floor_num,
                "Floor Name": name_w.text() if isinstance(name_w, QLineEdit) else "",
                FLOOR_ELEVATION_KEY: height_w.text() if isinstance(height_w, QLineEdit) else "",
                "Entrances": entrances,
            })
        return lift_floors

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
        if old_nf != new_nf or self.floor_table.rowCount() != self.num_floor_rows:
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
                    {'Floor': '0', 'Floor Name': 'Ground', 'Elevation (m)': '0.0', 'Entrances': ['None']},
                    {'Floor': '1', 'Floor Name': 'First', 'Elevation (m)': '3.5', 'Entrances': ['Front', 'Back', 'Side 1']},
                    {'Floor': '2', 'Floor Name': 'Second', 'Elevation (m)': '6.5', 'Entrances': ['Front', 'Side 2']},
                ]
            },
            {
                'Lift 2': [
                    {'Floor': '0', 'Floor Name': 'Ground', 'Elevation (m)': '0.0', 'Entrances': ['Front', 'Rear']},
                    {'Floor': '1', 'Floor Name': 'First', 'Elevation (m)': '3.5', 'Entrances': ['Side']},
                ]
            },
        ],
    }

    ex = BuildingFloorPage(sample_input)
    ex.show()
    sys.exit(app.exec_())
