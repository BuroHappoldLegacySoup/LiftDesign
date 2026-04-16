"""
Electrical & HVAC — matches Excel ``VT Standard configs`` rows 73–87 (section row 72).
Derived power / current / energy / heat use the same formulas for every load column (M–U);
values differ via permissible persons (Excel row 21) and duty cycle (row 78).
"""
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QCheckBox, QComboBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator, QShowEvent
import os
import sys

from .project_lift_schema import merged_lift_at, normalize_project_lift_data

try:
    from .lift_types import ELECTRICAL_HVAC_DEFAULTS, electrical_hvac_derived_for_lift
except ImportError:  # running as ``python gui/Elecrical_HVAC.py``
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from gui.lift_types import ELECTRICAL_HVAC_DEFAULTS, electrical_hvac_derived_for_lift


class LiftDriveControlPage(QWidget):
    """Lift drive control / Electrical & HVAC; persisted under ``user_inputs['LiftDrive']``."""

    back_clicked = pyqtSignal()

    next_clicked = pyqtSignal(dict)

    # (json_key, label, unit). JSON stores ``json_key`` only.
    LIFT_DRIVE_ROWS: tuple[tuple[str, str, str], ...] = (
        ("Drive/Motor location", "Drive/Motor location", "—"),
        ("Control / Operation panel location", "Control / Operation panel location", "—"),
        ("Number of trips per hour", "Number of trips per hour", "1/h"),
        ("Drive/Motor type", "Drive/Motor type", "—"),
        ("Power grid voltage/type", "Power grid voltage/type", "V"),
        ("Duty cycle (motor)", "Duty cycle (motor)", "%"),
        ("Drive/Motor Power", "Drive/Motor Power", "kW"),
        ("Connected load", "Connected load", "kVA"),
        ("Rated current", "Rated current", "A"),
        ("Starting current (factor ≈ 2)", "Starting current (factor ≈ 2)", "A"),
        ("Energy recovery", "Energy recovery", "y/n"),
        ("Diversity factor", "Diversity factor", "—"),
        ("Energy consumption", "Energy consumption", "kWh"),
        ("Heat dissipation motor", "Heat dissipation motor", "kJ"),
        ("Temperature machine room / shaft", "Temperature machine room / shaft", "°C"),
    )

    DESCRIPTIONS = tuple(r[0] for r in LIFT_DRIVE_ROWS)

    _COMPUTED_VALUE_KEYS = frozenset(
        {
            "Drive/Motor Power",
            "Connected load",
            "Rated current",
            "Starting current (factor ≈ 2)",
            "Energy consumption",
            "Heat dissipation motor",
        }
    )

    ROW_DRIVE_MOTOR_LOCATION = 0
    ROW_DUTY_CYCLE = 5
    ROW_POWER_GRID = 4
    ROW_ENERGY_RECOVERY = 10
    ROW_NUMERIC = frozenset({5, 6, 7, 8, 9, 11, 12, 13})

    LOAD_CAPACITY_KEY = "Load capacity"
    PERSONS_KEY = "Permissible number of persons"

    # Older project files may use these labels
    _POPULATE_ALIASES = {
        "Power grid voltage/type": ("Power network", "Power grid voltage/type (V)"),
    }

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        normalize_project_lift_data(self.user_inputs)
        self.number_of_lifts = len(user_inputs["BuildingSystems"])
        self.initUI()

        if "LiftDrive" in self.user_inputs:
            self.populate_from_input(self.user_inputs["LiftDrive"])

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        for col in range(2, self.system_table.columnCount()):
            self._apply_computed_for_column(col)

    def _cell_value_for_description(self, system_data: dict, description: str):
        if description in system_data:
            return system_data[description]
        for alias in self._POPULATE_ALIASES.get(description, ()):
            if alias in system_data:
                return system_data[alias]
        return None

    @staticmethod
    def _choice_combo(labels: list[str]) -> QComboBox:
        """Non-editable dropdown with only real choices (no blank row / no user-typed entries)."""
        w = QComboBox()
        w.setEditable(False)
        w.setInsertPolicy(QComboBox.NoInsert)
        w.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        for t in labels:
            s = str(t).strip()
            if s:
                w.addItem(s)
        if w.count() > 0:
            w.setCurrentIndex(0)
        # Avoid an extra empty-looking line in the popup when the combo sits in a QTableWidget.
        w.setStyleSheet("QComboBox { combobox-popup: 0; }")
        return w

    def initUI(self):
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)

        scroll_layout = QVBoxLayout(scroll_widget)

        system_box = QGroupBox("Electrical & HVAC")
        system_box.setObjectName("electrical_hvac_box")
        system_box.setStyleSheet(
            "#electrical_hvac_box {background-color: white; border: 3px solid rgb(196, 214, 0); "
            "font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(system_box)

        system_layout = QVBoxLayout(system_box)

        self.system_table = QTableWidget()
        self.system_table.setColumnCount(2)
        self.system_table.setHorizontalHeaderLabels(["Description", "Unit"])
        self.system_table.setRowCount(len(self.LIFT_DRIVE_ROWS))

        for row, (_jk, label, unit) in enumerate(self.LIFT_DRIVE_ROWS):
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.system_table.setItem(row, 0, item)
            u_item = QTableWidgetItem(unit if unit else "—")
            u_item.setFlags(u_item.flags() & ~Qt.ItemIsEditable)
            self.system_table.setItem(row, 1, u_item)

        self.system_table.horizontalHeader().setStretchLastSection(True)
        self.system_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.system_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.system_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        system_layout.addWidget(self.system_table)

        save_button = QPushButton("Save and Proceed")
        save_button.setStyleSheet("background-color: white;")
        save_button.clicked.connect(self.collect_data_and_go_next)
        nav_row = QHBoxLayout()
        back_button = QPushButton("← Back to previous page")
        back_button.setStyleSheet("background-color: white;")
        back_button.clicked.connect(self.back_clicked.emit)
        nav_row.addWidget(back_button)
        nav_row.addStretch()
        nav_row.addWidget(save_button)
        scroll_layout.addLayout(nav_row)

        self.initialize_lift_columns()

    def populate_from_input(self, drive_data):
        for col, system_data in enumerate(drive_data, start=2):
            for row in range(self.system_table.rowCount()):
                jk = self.DESCRIPTIONS[row]
                value = self._cell_value_for_description(system_data, jk)
                if value is None:
                    continue
                cell_widget = self.system_table.cellWidget(row, col)
                if isinstance(cell_widget, QLineEdit):
                    cell_widget.setText(str(value))
                elif isinstance(cell_widget, QComboBox):
                    index = cell_widget.findText(str(value))
                    if index >= 0:
                        cell_widget.setCurrentIndex(index)
                elif row == self.ROW_ENERGY_RECOVERY and isinstance(cell_widget, QCheckBox):
                    cell_widget.setChecked(str(value).lower() in ("yes", "true", "1"))
            self._apply_defaults_for_column(col, overwrite_empty_only=True)
            self._apply_computed_for_column(col)

    def initialize_lift_columns(self):
        for _ in range(self.number_of_lifts):
            self.add_lift_column()

    def _apply_defaults_for_column(self, col, overwrite_empty_only=False):
        for row in range(self.system_table.rowCount()):
            jk = self.DESCRIPTIONS[row]
            w = self.system_table.cellWidget(row, col)
            if jk in ELECTRICAL_HVAC_DEFAULTS:
                dflt = ELECTRICAL_HVAC_DEFAULTS[jk]
                if isinstance(w, QLineEdit):
                    if not overwrite_empty_only or not w.text().strip():
                        w.setText(dflt)
                elif isinstance(w, QComboBox):
                    if not overwrite_empty_only or not w.currentText().strip():
                        i = w.findText(dflt)
                        if i >= 0:
                            w.setCurrentIndex(i)
            if row == self.ROW_ENERGY_RECOVERY and isinstance(w, QCheckBox):
                if not overwrite_empty_only:
                    w.setChecked(True)

    def add_lift_column(self):
        col_position = self.system_table.columnCount()
        self.system_table.insertColumn(col_position)
        self.system_table.setHorizontalHeaderItem(
            col_position, QTableWidgetItem(f"Lift {col_position - 1}")
        )

        for row in range(self.system_table.rowCount()):
            if row == self.ROW_DRIVE_MOTOR_LOCATION:
                widget = self._choice_combo(
                    [
                        "MRL top",
                        "Machine room top",
                        "Machine room side",
                        "Machine room bottom",
                    ]
                )
            elif row == self.ROW_POWER_GRID:
                widget = self._choice_combo(["400", "380"])
            elif row == self.ROW_ENERGY_RECOVERY:
                widget = QCheckBox()
                widget.setChecked(True)
            elif row in self.ROW_NUMERIC:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
                if row == self.ROW_DUTY_CYCLE:
                    widget.textChanged.connect(lambda *_a, cp=col_position: self._apply_computed_for_column(cp))
            else:
                widget = QLineEdit()
            self.system_table.setCellWidget(row, col_position, widget)

        self._apply_defaults_for_column(col_position, overwrite_empty_only=False)
        self._apply_computed_for_column(col_position)

    def _apply_computed_for_column(self, col):
        idx = col - 2
        lift = merged_lift_at(self.user_inputs, idx)
        if not lift:
            return
        load = lift.get(self.LOAD_CAPACITY_KEY, "")
        persons = lift.get(self.PERSONS_KEY, "")
        duty_w = self.system_table.cellWidget(self.ROW_DUTY_CYCLE, col)
        duty_txt = duty_w.text() if isinstance(duty_w, QLineEdit) else ""

        derived = electrical_hvac_derived_for_lift(load, persons, duty_txt)
        key_to_row = {d: i for i, d in enumerate(self.DESCRIPTIONS)}
        computed_keys = tuple(sorted(self._COMPUTED_VALUE_KEYS))
        lift_drive = self.user_inputs.get("LiftDrive") or []
        for key in computed_keys:
            r = key_to_row.get(key)
            if r is None:
                continue
            w = self.system_table.cellWidget(r, col)
            if not isinstance(w, QLineEdit):
                continue
            if key in derived:
                w.setText(derived[key])
            else:
                stored = None
                if 0 <= idx < len(lift_drive) and isinstance(lift_drive[idx], dict):
                    stored = self._cell_value_for_description(lift_drive[idx], key)
                if stored is not None and str(stored).strip() != "":
                    w.setText(str(stored))
                else:
                    w.setText("")

    def sync_lift_drive_to_user_inputs(self):
        """Write Electrical & HVAC table into ``user_inputs``."""
        existing = self.user_inputs.get("LiftDrive") or []
        systems_data = []
        for col in range(2, self.system_table.columnCount()):
            idx = col - 2
            merged = dict(existing[idx]) if idx < len(existing) and isinstance(existing[idx], dict) else {}
            for row in range(self.system_table.rowCount()):
                jk = self.DESCRIPTIONS[row]
                cell_widget = self.system_table.cellWidget(row, col)
                if isinstance(cell_widget, QLineEdit):
                    value = cell_widget.text()
                    v = value.strip()
                    if jk in self._COMPUTED_VALUE_KEYS:
                        if v != "":
                            merged[jk] = value
                        else:
                            prev = self._cell_value_for_description(merged, jk)
                            if prev is not None and str(prev).strip() != "":
                                merged[jk] = prev
                            else:
                                merged[jk] = ""
                    elif v != "" or cell_widget.isModified():
                        merged[jk] = value
                    else:
                        prev = self._cell_value_for_description(merged, jk)
                        merged[jk] = (
                            prev if prev is not None and str(prev).strip() != "" else ""
                        )
                elif isinstance(cell_widget, QComboBox):
                    merged[jk] = cell_widget.currentText()
                elif isinstance(cell_widget, QCheckBox):
                    merged[jk] = "yes" if cell_widget.isChecked() else "no"
                else:
                    merged[jk] = ""
            systems_data.append(merged)

        self.user_inputs["LiftDrive"] = systems_data

    def collect_data_and_go_next(self):
        self.sync_lift_drive_to_user_inputs()
        self.next_clicked.emit(self.user_inputs)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    sample_input = {
        "BuildingSystems": [{"Number": "1"}],
        "GeneralSpecification": [
            {
                "Load capacity": "630",
                "Permissible number of persons": "17",
            }
        ],
        "LayoutInformation": [{}],
        "LiftDrive": [],
    }
    ex = LiftDriveControlPage(sample_input)
    ex.show()
    sys.exit(app.exec_())
