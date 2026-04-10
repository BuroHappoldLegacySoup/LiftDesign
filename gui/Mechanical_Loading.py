from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QCheckBox,
    QComboBox,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator, QShowEvent
import os
import sys

from .project_lift_schema import ensure_lift_section_slots, merged_lift_at

try:
    from .lift_types import (
        _parse_width_mm,
        load_profile_for_capacity,
        mechanical_loading_derived_for_lift,
        mechanical_rail_weight_car_kg_m,
        mechanical_rail_weight_cwt_kg_m,
    )
except ImportError:
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from gui.lift_types import (
        _parse_width_mm,
        load_profile_for_capacity,
        mechanical_loading_derived_for_lift,
        mechanical_rail_weight_car_kg_m,
        mechanical_rail_weight_cwt_kg_m,
    )


class ForceSpecPage(QWidget):
    """Mechanical loading — Excel ``VT Standard configs`` rows 90–105."""

    next_clicked = pyqtSignal(dict)
    back_clicked = pyqtSignal()

    FORCES_ROWS: tuple[tuple[str, str, str], ...] = (
        ("Rail weight car", "Rail weight car", "kg/m"),
        ("Force F1, F2 elevator rail segment", "Force F1, F2 elevator rail segment", "kN"),
        ("Number of car buffers", "Number of car buffers", "St."),
        ("Force F3, each buffer", "Force F3, each buffer", "kN"),
        ("Counterweight safety gear", "Counterweight safety gear", "—"),
        ("Number of cwt buffers", "Number of cwt buffers", "St."),
        ("Rail weight cwt", "Rail weight cwt", "kg/m"),
        ("Force F4, per counterweight rail segment", "Force F4, per counterweight rail segment", "kN"),
        ("Force F5, per counterweight buffer", "Force F5, per counterweight buffer", "kN"),
        ("Force F6, static shaft door", "Force F6, static shaft door", "kN"),
        ("Force F7, static counterweight", "Force F7, static counterweight", "kN"),
        ("Force F8, static cabin", "Force F8, static cabin", "kN"),
        ("Force Fx, cabin rail", "Force Fx, cabin rail", "kN"),
        ("Force Fy, cabin rail", "Force Fy, cabin rail", "kN"),
        ("Force Fx, counterweight rail", "Force Fx, counterweight rail", "kN"),
        ("Force Fy, counterweight rail", "Force Fy, counterweight rail", "kN"),
    )

    DESCRIPTIONS = tuple(r[0] for r in FORCES_ROWS)

    ROW_RAIL_CAR = 0
    ROW_CAR_BUFFERS = 2
    ROW_CWT_SAFETY = 4
    ROW_CWT_BUFFERS = 5
    ROW_RAIL_CWT = 6
    # Formula-driven line edits (Excel); rail weights = combos; buffers + checkbox = inputs.
    ROWS_COMPUTED_LINEEDIT = frozenset(
        {1, 3, 7, 8, 9, 10, 11, 12, 13, 14, 15}
    )

    LOAD_KEY = "Load capacity"
    TRAVEL_KEY = "Travel height"
    CABIN_W_KEY = "Cabin width"
    CABIN_D_KEY = "Cabin depth"
    CABIN_SHAPE_KEY = "Cabin type/shape"
    ACCESSIBLE_YN_KEY = "Accessible rooms/cwt safety"

    # Legacy saved keys → current description label
    _POPULATE_ALIASES = {
        "Number of cwt buffers": ("number of cwt buffers (kg/m)", "Number of cwt buffers (St.)"),
    }

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs.get("BuildingSystems") or [])
        ensure_lift_section_slots(self.user_inputs, self.number_of_lifts)
        self.initUI()

        if "Forces" in self.user_inputs:
            self.populate_from_input(self.user_inputs["Forces"])

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        for col in range(2, self.force_table.columnCount()):
            self._sync_derived_fields(col)

    def _lift_at_column(self, col: int) -> dict:
        i = col - 2
        return merged_lift_at(self.user_inputs, i)

    def _resolved_cabin_width_depth_mm(self, lift: dict):
        """
        Use layout table values when present; otherwise Excel-style defaults from
        ``Load capacity`` + ``Cabin type/shape`` (same as layout page logic).
        """
        w = _parse_width_mm(str(lift.get(self.CABIN_W_KEY, "") or ""))
        d = _parse_width_mm(str(lift.get(self.CABIN_D_KEY, "") or ""))
        if w is not None and d is not None:
            return w, d
        prof = load_profile_for_capacity(lift.get(self.LOAD_KEY, 0))
        # Layout page may not be saved yet; Excel template defaults to a cabin shape.
        shape = str(lift.get(self.CABIN_SHAPE_KEY, "") or "").strip() or "Deep"
        cw_s = prof.cabin_width_mm(shape)
        if cw_s is None:
            return None, None
        w2 = _parse_width_mm(str(cw_s))
        if w2 is None:
            return None, None
        cd_s = prof.cabin_depth_mm(str(w2))
        if cd_s is None:
            return None, None
        d2 = _parse_width_mm(str(cd_s))
        if d2 is None:
            return None, None
        return w2, d2

    def _cell_value_for_description(self, system_data: dict, description: str):
        if description in system_data:
            return system_data[description]
        for alias in self._POPULATE_ALIASES.get(description, ()):
            if alias in system_data:
                return system_data[alias]
        return None

    def _sync_derived_fields(self, col: int) -> None:
        idx = col - 2
        lift = self._lift_at_column(col)

        w_car = self.force_table.cellWidget(self.ROW_CAR_BUFFERS, col)
        w_cwt = self.force_table.cellWidget(self.ROW_CWT_BUFFERS, col)
        cb = self.force_table.cellWidget(self.ROW_CWT_SAFETY, col)

        n_car = w_car.text().strip() if isinstance(w_car, QLineEdit) else "2"
        n_cwt = w_cwt.text().strip() if isinstance(w_cwt, QLineEdit) else "2"
        cwt_yes = isinstance(cb, QCheckBox) and cb.isChecked()

        cw_i, cd_i = self._resolved_cabin_width_depth_mm(lift)
        cw_arg = str(cw_i) if cw_i is not None else lift.get(self.CABIN_W_KEY)
        cd_arg = str(cd_i) if cd_i is not None else lift.get(self.CABIN_D_KEY)

        derived = mechanical_loading_derived_for_lift(
            lift.get(self.LOAD_KEY),
            lift.get(self.TRAVEL_KEY),
            cw_arg,
            cd_arg,
            cwt_yes,
            n_car or "2",
            n_cwt or "2",
        )

        for row in range(self.force_table.rowCount()):
            if row not in self.ROWS_COMPUTED_LINEEDIT:
                continue
            jk = self.DESCRIPTIONS[row]
            w = self.force_table.cellWidget(row, col)
            if not isinstance(w, QLineEdit):
                continue
            if jk in derived:
                w.setText(derived[jk])
            else:
                forces = self.user_inputs.get("Forces") or []
                stored = None
                if 0 <= idx < len(forces) and isinstance(forces[idx], dict):
                    stored = forces[idx].get(jk)
                if stored is not None and str(stored).strip() != "":
                    w.setText(str(stored))
                else:
                    w.setText("")

    def populate_from_input(self, forces_data):
        for col, force_data in enumerate(forces_data, start=2):
            for row in range(self.force_table.rowCount()):
                jk = self.DESCRIPTIONS[row]
                value = self._cell_value_for_description(force_data, jk)
                if value is None:
                    continue
                cell_widget = self.force_table.cellWidget(row, col)
                if isinstance(cell_widget, QLineEdit):
                    cell_widget.setText(str(value))
                elif isinstance(cell_widget, QComboBox):
                    index = cell_widget.findText(str(value).strip())
                    if index >= 0:
                        cell_widget.setCurrentIndex(index)
                elif row == self.ROW_CWT_SAFETY and isinstance(cell_widget, QCheckBox):
                    cell_widget.setChecked(
                        str(value).lower() in ("yes", "true", "1")
                        or value is True
                    )
            self._sync_derived_fields(col)

    def initUI(self):
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)

        scroll_layout = QVBoxLayout(scroll_widget)

        force_box = QGroupBox("Mechanical loading")
        force_box.setObjectName("force_box")
        force_box.setStyleSheet(
            "#force_box {background-color: white; border: 3px solid rgb(196, 214, 0); font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(force_box)

        force_layout = QVBoxLayout(force_box)

        self.force_table = QTableWidget()
        self.force_table.setColumnCount(2)
        self.force_table.setHorizontalHeaderLabels(["Description", "Unit"])
        self.force_table.setRowCount(len(self.FORCES_ROWS))

        for row, (_jk, label, unit) in enumerate(self.FORCES_ROWS):
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.force_table.setItem(row, 0, item)
            u_item = QTableWidgetItem(unit if unit else "—")
            u_item.setFlags(u_item.flags() & ~Qt.ItemIsEditable)
            self.force_table.setItem(row, 1, u_item)

        self.force_table.horizontalHeader().setStretchLastSection(True)
        self.force_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.force_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.force_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        force_layout.addWidget(self.force_table)

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

    def initialize_lift_columns(self):
        for _ in range(self.number_of_lifts):
            self.add_lift_column()

    def add_lift_column(self):
        col_position = self.force_table.columnCount()
        self.force_table.insertColumn(col_position)
        self.force_table.setHorizontalHeaderItem(col_position, QTableWidgetItem(f"Lift {col_position}"))

        lift = self._lift_at_column(col_position)

        for row in range(self.force_table.rowCount()):
            if row == self.ROW_RAIL_CAR:
                widget = QComboBox()
                widget.setEditable(False)
                widget.setInsertPolicy(QComboBox.NoInsert)
                widget.addItems(["14", "18"])
                if lift is not None:
                    dflt = mechanical_rail_weight_car_kg_m(lift.get(self.LOAD_KEY))
                    if dflt is not None:
                        i = widget.findText(dflt)
                        if i >= 0:
                            widget.setCurrentIndex(i)
            elif row == self.ROW_RAIL_CWT:
                widget = QComboBox()
                widget.setEditable(False)
                widget.setInsertPolicy(QComboBox.NoInsert)
                widget.addItems(["4", "14", "18"])
                if lift is not None:
                    dflt = mechanical_rail_weight_cwt_kg_m(lift.get(self.LOAD_KEY))
                    if dflt is not None:
                        i = widget.findText(dflt)
                        if i >= 0:
                            widget.setCurrentIndex(i)
            elif row == self.ROW_CWT_SAFETY:
                widget = QCheckBox()
                if lift is not None:
                    yn = str(lift.get(self.ACCESSIBLE_YN_KEY, "") or "").strip().lower()
                    try:
                        cap = int(
                            round(
                                float(
                                    str(lift.get(self.LOAD_KEY, "") or "")
                                    .strip()
                                    .replace(",", ".")
                                )
                            )
                        )
                    except (ValueError, TypeError, OverflowError):
                        cap = None
                    # Excel template: column M (630 kg) uses ``yes``; other capacities ``no``.
                    widget.setChecked(cap == 630 or yn == "yes")
                widget.toggled.connect(lambda _c, cp=col_position: self._sync_derived_fields(cp))
            elif row in (self.ROW_CAR_BUFFERS, self.ROW_CWT_BUFFERS):
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
                widget.setText("2")
                widget.textChanged.connect(lambda _t, cp=col_position: self._sync_derived_fields(cp))
            elif row in self.ROWS_COMPUTED_LINEEDIT:
                widget = QLineEdit()
                widget.setReadOnly(True)
                widget.setPlaceholderText("—")

            self.force_table.setCellWidget(row, col_position, widget)

        self._sync_derived_fields(col_position)

    def sync_forces_to_user_inputs(self):
        """Write mechanical loading table into ``user_inputs``."""
        existing = self.user_inputs.get("Forces") or []
        forces_data = []
        for col in range(2, self.force_table.columnCount()):
            idx = col - 2
            merged = dict(existing[idx]) if idx < len(existing) and isinstance(existing[idx], dict) else {}
            for row in range(self.force_table.rowCount()):
                jk = self.DESCRIPTIONS[row]
                cell_widget = self.force_table.cellWidget(row, col)

                if isinstance(cell_widget, QLineEdit):
                    value = cell_widget.text()
                    v = value.strip()
                    if row in self.ROWS_COMPUTED_LINEEDIT:
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
                    merged[jk] = cell_widget.isChecked()
                else:
                    merged[jk] = ""

            forces_data.append(merged)

        self.user_inputs["Forces"] = forces_data

    def collect_data_and_go_next(self):
        self.sync_forces_to_user_inputs()
        self.next_clicked.emit(self.user_inputs)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    sample_input = {
        "BuildingSystems": [{"Number": "1", "System Name": "Lift A"}],
        "GeneralSpecification": [
            {
                "Load capacity": "630",
                "Travel height": "20",
                "Accessible rooms/cwt safety": "no",
            }
        ],
        "LayoutInformation": [
            {"Cabin width": "1100", "Cabin depth": "1400"},
        ],
        "Forces": [],
    }
    ex = ForceSpecPage(sample_input)
    ex.show()
    sys.exit(app.exec_())
