"""
Layout Information — from Cabin width through Lift vestibule depth (per lift).
Persisted under ``user_inputs['LayoutInformation']`` (general spec is ``GeneralSpecification``).
"""
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QDoubleValidator, QShowEvent
import copy
import os
import sys
from typing import Optional

from .formula_line_edit import apply_formula_value
from .override_combobox import OverrideComboBox

# Lime-green accent used by the page borders / titles. Reused as the fill for
# cells the user must complete (here: Cabin type/shape) so they line up with
# the matching highlights on the General Specification page.
REQUIRED_FIELD_BG_CSS: str = "rgb(196, 214, 0)"
REQUIRED_FIELD_COMBO_QSS: str = (
    f"QComboBox {{ background-color: {REQUIRED_FIELD_BG_CSS}; }}"
    f"QComboBox QLineEdit {{ background-color: {REQUIRED_FIELD_BG_CSS}; }}"
)
from .project_lift_schema import (
    KEY_LAYOUT_INFORMATION,
    merged_lift_at,
    normalize_project_lift_data,
)
from .custom_parameter_rows import (
    KEY_CUSTOM_LAYOUT,
    add_plus_minus_button_row,
    append_custom_row_two_column_headers,
    clear_rows_from,
    default_custom_name,
    meta_from_table,
    normalize_meta_list,
)

try:
    from .lift_types import (
        cabin_width_for_load_and_shape,
        cabin_depth_for_load_and_width,
        load_profile_for_capacity,
    )
except ImportError:  # running as ``python gui/layout_information_page.py``
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from gui.lift_types import (
        cabin_width_for_load_and_shape,
        cabin_depth_for_load_and_width,
        load_profile_for_capacity,
    )


class LayoutInformationPage(QWidget):
    next_clicked = pyqtSignal(dict)
    back_clicked = pyqtSignal()

    # Local row indices in layout_table (0-based), must match ``LAYOUT_ROWS`` order
    ROW_CABIN_TYPE = 0
    ROW_CABIN_WIDTH = 1
    ROW_CABIN_DEPTH = 2
    ROW_CLADDING = 3
    ROW_CLEAR_CABIN_HEIGHT = 4
    ROW_STRUCTURAL_CABIN_HEIGHT = 5
    ROW_DOOR_WIDTH = 6
    ROW_DOOR_STRUCTURAL_WIDTH = 7
    ROW_DOOR_HEIGHT = 8
    ROW_DOOR_STRUCTURAL_HEIGHT = 9
    ROW_DOOR_TYPE = 10
    ROW_DOOR_FIXATION = 11
    ROW_PERMISSIBLE_SILL = 12
    ROW_LOP = 13
    ROW_LIP = 14
    ROW_LIFT_MAINT_TYPE = 15
    ROW_SHAFT_EQUIP_FIX = 17
    ROW_SHAFT_WIDTH_SUGG = 18
    ROW_SHAFT_DIVISION_TYPE = 20
    ROW_SHAFT_DEPTH_SUGG = 22
    ROW_SHAFT_HEAD_SUGG = 24
    ROW_SHAFT_PIT_SUGG = 26

    LOAD_CAPACITY_KEY = 'Load capacity'
    SPEED_KEY = 'Speed'
    CWT_KEY = 'Counterweight location'
    ACCESS_TYPE_KEY = 'Access type'
    ACCESSIBLE_YN_KEY = 'Accessible rooms/cwt safety'
    _COMBO_OPTIONS = {
        ROW_DOOR_FIXATION: ['insert rail 40/22', 'insert rail 50/30', 'anchor bolts', 'steel structure'],
        ROW_PERMISSIBLE_SILL: ['ASME-A', 'ASME-B', 'ASME-C1', 'ASME-C2', 'EN81-40%', 'EN81-60%', 'EN81-85%'],
        ROW_LOP: ['in lift door frame L', 'in lift door frame R', 'flush wall panel L', 'flush wall panel R',
                  'wall-mounted panel L', 'wall-mounted panel R'],
        ROW_LIP: ['door frame side vertical', 'door frame above horizontal', 'panel above horizontal', 'panel side vertical'],
        ROW_LIFT_MAINT_TYPE: ['inside door jamb', 'segregated panel flush', 'segregated panel wall-mounted'],
        ROW_SHAFT_EQUIP_FIX: ['insert rail 40/22', 'insert rail 50/30', 'anchor bolts', 'steel structure'],
        ROW_SHAFT_DIVISION_TYPE: ['structural wall', 'beam'],
    }

    # (json_key, description label, unit). JSON uses ``json_key`` only — units are in the Unit column.
    LAYOUT_ROWS: tuple[tuple[str, str, str], ...] = (
        ('Cabin type/shape', 'Cabin type/shape', '—'),
        ('Cabin width', 'Cabin width', 'mm'),
        ('Cabin depth', 'Cabin depth', 'mm'),
        ('Cladding thickness each wall', 'Cladding thickness each wall', 'mm'),
        ('Clear cabin height', 'Clear cabin height', 'mm'),
        ('Structural cabin height', 'Structural cabin height', 'mm'),
        ('Door width', 'Door width', 'mm'),
        ('Door structural opening width', 'Door structural opening width', 'mm'),
        ('Door height', 'Door height', 'mm'),
        ('Door structural opening height', 'Door structural opening height', 'mm'),
        ('door type', 'door type', '—'),
        ('door fixation type', 'door fixation type', '—'),
        ('Permissible sill load / Loading class', 'Permissible sill load / Loading class', '—'),
        ('LOP type and location', 'LOP type and location', '—'),
        ('LIP type and location', 'LIP type and location', '—'),
        ('Lift maintenance panel type', 'Lift maintenance panel type', '—'),
        ('Lift maintenance panel location', 'Lift maintenance panel location', '—'),
        ('Shaft equipment fixation type', 'Shaft equipment fixation type', '—'),
        ('Shaft width suggested', 'Shaft width suggested', 'mm'),
        ('Shaft width current planning', 'Shaft width current planning', 'mm'),
        ('Shaft division type', 'Shaft division type', '—'),
        ('Shaft division width', 'Shaft division width', 'mm'),
        ('Shaft depth suggested', 'Shaft depth suggested', 'mm'),
        ('Shaft depth current planning', 'Shaft depth current planning', 'mm'),
        ('Shaft head suggested', 'Shaft head suggested', 'mm'),
        ('Shaft head current planning', 'Shaft head current planning', 'mm'),
        ('Shaft pit suggested', 'Shaft pit suggested', 'mm'),
        ('Shaft pit current planning', 'Shaft pit current planning', 'mm'),
        ('Machine room width suggested', 'Machine room width suggested', 'mm'),
        ('Machine room width current planning', 'Machine room width current planning', 'mm'),
        ('Machine room depth suggested', 'Machine room depth suggested', 'mm'),
        ('Machine room depth current planning', 'Machine room depth current planning', 'mm'),
        ('Machine room height suggested', 'Machine room height suggested', 'mm'),
        ('Machine room height current planning', 'Machine room height current planning', 'mm'),
        ('Lift vestibule width', 'Lift vestibule width', 'mm'),
        ('Lift vestibule depth', 'Lift vestibule depth', 'mm'),
    )

    LAYOUT_FIXED_JSON_KEYS = frozenset(r[0] for r in LAYOUT_ROWS)

    def _layout_json_key_for_row(self, row: int) -> str:
        if row < len(self.LAYOUT_ROWS):
            return self.LAYOUT_ROWS[row][0]
        w = self.layout_table.cellWidget(row, 0)
        return w.text().strip() if isinstance(w, QLineEdit) else ""

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        normalize_project_lift_data(self.user_inputs)
        self.number_of_lifts = len(user_inputs['BuildingSystems'])
        self.initUI()

        systems = copy.deepcopy(self.user_inputs.get(KEY_LAYOUT_INFORMATION) or [])
        while len(systems) < self.number_of_lifts:
            systems.append({})
        while len(systems) > self.number_of_lifts:
            systems.pop()
        self._rebuild_custom_layout_rows(systems)
        self.populate_from_input(systems)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        for col in range(2, self.layout_table.columnCount()):
            self._apply_cabin_width_for_column(col)

    def _parse_float(self, text):
        t = (text or '').strip()
        if not t:
            return None
        try:
            return float(t.replace(',', '.'))
        except ValueError:
            return None

    def _apply_cabin_width_for_column(self, col):
        i, ww = col - 2, self.layout_table.cellWidget(self.ROW_CABIN_WIDTH, col)
        lift = merged_lift_at(self.user_inputs, i)
        if not lift or not isinstance(ww, QLineEdit):
            return
        v = self._parse_float(str(lift.get(self.LOAD_CAPACITY_KEY, '') or ''))
        if v is None:
            self._sync_derived_fields(col)
            return
        tw = self.layout_table.cellWidget(self.ROW_CABIN_TYPE, col)
        s = tw.currentText().strip() if isinstance(tw, QComboBox) else ''
        cw = cabin_width_for_load_and_shape(v, s)
        if cw is not None:
            apply_formula_value(ww, cw)
        self._apply_cabin_depth_for_column(col)

    def _apply_cabin_depth_for_column(self, col):
        i = col - 2
        lift = merged_lift_at(self.user_inputs, i)
        dw = self.layout_table.cellWidget(self.ROW_CABIN_DEPTH, col)
        ww = self.layout_table.cellWidget(self.ROW_CABIN_WIDTH, col)
        if not lift or not isinstance(dw, QLineEdit) or not isinstance(ww, QLineEdit):
            self._sync_derived_fields(col)
            return
        v = self._parse_float(str(lift.get(self.LOAD_CAPACITY_KEY, '') or ''))
        if v is None:
            self._sync_derived_fields(col)
            return
        cd = cabin_depth_for_load_and_width(v, ww.text())
        if cd is not None:
            apply_formula_value(dw, cd)
        self._sync_derived_fields(col)

    def _lift_at_column(self, col):
        i = col - 2
        lift = merged_lift_at(self.user_inputs, i)
        return lift if lift else None

    def _cladding_mm(self, col):
        w = self.layout_table.cellWidget(self.ROW_CLADDING, col)
        if not isinstance(w, QLineEdit):
            return 0.0
        v = self._parse_float(w.text())
        return float(v) if v is not None else 0.0

    def _accessible_rooms_yes(self, lift):
        return str(lift.get(self.ACCESSIBLE_YN_KEY, '') or '').strip().lower() == 'yes'

    def _sync_derived_fields(self, col):
        """
        Excel-dependent layout: row 35 cladding, 36 clear, 37 structural, 40–43 doors,
        44 door type, 53/57 shaft suggested, 59 shaft head suggested, 61 shaft pit suggested.
        """
        lift = self._lift_at_column(col)
        if lift is None:
            return
        load = self._parse_float(str(lift.get(self.LOAD_CAPACITY_KEY, '') or ''))
        prof = load_profile_for_capacity(load if load is not None else 0)

        _rows_written = (
            self.ROW_CLADDING,
            self.ROW_CLEAR_CABIN_HEIGHT,
            self.ROW_STRUCTURAL_CABIN_HEIGHT,
            self.ROW_DOOR_WIDTH,
            self.ROW_DOOR_STRUCTURAL_WIDTH,
            self.ROW_DOOR_HEIGHT,
            self.ROW_DOOR_STRUCTURAL_HEIGHT,
            self.ROW_DOOR_TYPE,
            self.ROW_SHAFT_WIDTH_SUGG,
            self.ROW_SHAFT_DEPTH_SUGG,
            self.ROW_SHAFT_HEAD_SUGG,
            self.ROW_SHAFT_PIT_SUGG,
        )
        _blocked = []
        for r in _rows_written:
            w = self.layout_table.cellWidget(r, col)
            if w is not None and hasattr(w, 'blockSignals'):
                w.blockSignals(True)
                _blocked.append(w)
        try:
            self._sync_derived_fields_core(col, prof)
        finally:
            for w in _blocked:
                w.blockSignals(False)

    def _sync_derived_fields_core(self, col, prof):
        lift = self._lift_at_column(col)
        if lift is None:
            return

        cw = self.layout_table.cellWidget(self.ROW_CABIN_WIDTH, col)
        clad_w = self.layout_table.cellWidget(self.ROW_CLADDING, col)
        depth_w = self.layout_table.cellWidget(self.ROW_CABIN_DEPTH, col)
        clear_w = self.layout_table.cellWidget(self.ROW_CLEAR_CABIN_HEIGHT, col)
        struct_w = self.layout_table.cellWidget(self.ROW_STRUCTURAL_CABIN_HEIGHT, col)
        door_w = self.layout_table.cellWidget(self.ROW_DOOR_WIDTH, col)
        door_sw = self.layout_table.cellWidget(self.ROW_DOOR_STRUCTURAL_WIDTH, col)
        door_h = self.layout_table.cellWidget(self.ROW_DOOR_HEIGHT, col)
        door_sh = self.layout_table.cellWidget(self.ROW_DOOR_STRUCTURAL_HEIGHT, col)
        door_type_w = self.layout_table.cellWidget(self.ROW_DOOR_TYPE, col)
        shaft_w = self.layout_table.cellWidget(self.ROW_SHAFT_WIDTH_SUGG, col)
        shaft_d = self.layout_table.cellWidget(self.ROW_SHAFT_DEPTH_SUGG, col)
        shaft_head_w = self.layout_table.cellWidget(self.ROW_SHAFT_HEAD_SUGG, col)
        shaft_pit_w = self.layout_table.cellWidget(self.ROW_SHAFT_PIT_SUGG, col)

        cabin_txt = cw.text() if isinstance(cw, QLineEdit) else ''

        c_thick = prof.cladding_thickness_mm()
        if c_thick is not None and isinstance(clad_w, QLineEdit):
            apply_formula_value(clad_w, c_thick)
        clad = self._cladding_mm(col)

        acc_yes = self._accessible_rooms_yes(lift)
        access = lift.get(self.ACCESS_TYPE_KEY, '')
        cwt = lift.get(self.CWT_KEY, '')

        ch = prof.clear_cabin_height_mm(cabin_txt)
        if isinstance(clear_w, QLineEdit):
            apply_formula_value(clear_w, ch)

        clear_txt = clear_w.text() if isinstance(clear_w, QLineEdit) else ''
        sh = prof.structural_cabin_height_mm(clear_txt)
        if isinstance(struct_w, QLineEdit):
            apply_formula_value(struct_w, sh)

        dw_i = prof.door_width_mm(cabin_txt)
        if isinstance(door_w, QLineEdit):
            apply_formula_value(door_w, dw_i)

        door_sw_computed: Optional[str] = None
        if isinstance(door_w, QLineEdit):
            odw = door_w.text().strip()
            try:
                dv = float(odw.replace(',', '.'))
                door_sw_computed = (
                    str(int(dv + 280)) if dv == int(dv) else str(dv + 280)
                )
            except ValueError:
                door_sw_computed = None
        if isinstance(door_sw, QLineEdit):
            apply_formula_value(door_sw, door_sw_computed)

        dhi = prof.door_height_mm(clear_txt)
        if isinstance(door_h, QLineEdit):
            apply_formula_value(door_h, dhi)

        door_ht_txt = door_h.text() if isinstance(door_h, QLineEdit) else ''
        dsh = prof.door_structural_opening_height_mm(door_ht_txt)
        if isinstance(door_sh, QLineEdit):
            apply_formula_value(door_sh, dsh)

        dt = prof.door_type_code(cabin_txt, cwt)
        if isinstance(door_type_w, QLineEdit):
            apply_formula_value(door_type_w, dt)

        sw = prof.shaft_width_suggested_mm(cabin_txt, clad, acc_yes)
        if isinstance(shaft_w, QLineEdit):
            apply_formula_value(shaft_w, sw)

        depth_txt = depth_w.text() if isinstance(depth_w, QLineEdit) else ''
        sd = prof.shaft_depth_suggested_mm(depth_txt, clad, access)
        if isinstance(shaft_d, QLineEdit):
            apply_formula_value(shaft_d, sd)

        struct_txt = struct_w.text() if isinstance(struct_w, QLineEdit) else ''
        door_w_txt = door_w.text() if isinstance(door_w, QLineEdit) else ''
        door_type_txt = (
            door_type_w.text() if isinstance(door_type_w, QLineEdit) else ''
        ).strip()
        speed_raw = lift.get(self.SPEED_KEY, '')

        head_s = prof.shaft_head_suggested_mm(
            struct_txt,
            speed_raw,
            cabin_txt,
            door_w_txt,
            door_type_txt,
            clad,
            acc_yes,
        )
        if isinstance(shaft_head_w, QLineEdit):
            apply_formula_value(shaft_head_w, head_s)

        pit_s = prof.shaft_pit_suggested_mm(speed_raw)
        if isinstance(shaft_pit_w, QLineEdit):
            apply_formula_value(shaft_pit_w, pit_s)

    def initUI(self):
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)

        scroll_layout = QVBoxLayout(scroll_widget)

        system_box = QGroupBox("Layout Information")
        system_box.setObjectName("layout_info_box")
        system_box.setStyleSheet(
            "#layout_info_box {background-color: white; border: 3px solid rgb(196, 214, 0); "
            "font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(system_box)

        system_layout = QVBoxLayout(system_box)

        self.layout_table = QTableWidget()
        self.layout_table.setColumnCount(2)
        self.layout_table.setHorizontalHeaderLabels(['Description', 'Unit'])
        self.layout_table.setRowCount(len(self.LAYOUT_ROWS))

        for row, (_jk, label, unit) in enumerate(self.LAYOUT_ROWS):
            item = QTableWidgetItem(label)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.layout_table.setItem(row, 0, item)
            u_item = QTableWidgetItem(unit if unit else '—')
            u_item.setFlags(u_item.flags() & ~Qt.ItemIsEditable)
            self.layout_table.setItem(row, 1, u_item)

        self.layout_table.horizontalHeader().setStretchLastSection(True)
        self.layout_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.layout_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.layout_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        system_layout.addWidget(self.layout_table)
        add_plus_minus_button_row(
            system_layout,
            self._on_add_custom_parameter_row,
            self._on_remove_custom_parameter_row,
        )

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

        self.initialize_lift_columns()

    def populate_from_input(self, systems_data):
        """Write saved LayoutInformation into the table without letting derivation cascades clobber it.

        Every ``setText`` on e.g. *Cabin width* fires ``textChanged`` which chains into
        :meth:`_apply_cabin_depth_for_column` → :meth:`_sync_derived_fields`, and a stray derived
        result (``"non-std.cabin depth"``) or a re-derived cabin width can overwrite the saved
        value the user painstakingly entered. Signals are blocked for the whole load so the table
        ends up with **exactly** the saved values. Derivation is then reapplied only for columns
        whose saved data left the key dimensions blank, preserving the auto-fill behaviour for
        brand-new projects while never trampling stored user input.
        """
        # Block signals across every cell widget for the duration of the load.
        blocked = []
        for col in range(2, self.layout_table.columnCount()):
            for row in range(self.layout_table.rowCount()):
                w = self.layout_table.cellWidget(row, col)
                if w is not None:
                    w.blockSignals(True)
                    blocked.append(w)
        try:
            for col, system_data in enumerate(systems_data, start=2):
                for row in range(len(self.LAYOUT_ROWS)):
                    jk = self._layout_json_key_for_row(row)
                    if jk in system_data:
                        cell_widget = self.layout_table.cellWidget(row, col)
                        value = system_data[jk]
                        if isinstance(cell_widget, QLineEdit):
                            cell_widget.setText(str(value))
                        elif isinstance(cell_widget, QComboBox):
                            index = cell_widget.findText(str(value))
                            if index >= 0:
                                cell_widget.setCurrentIndex(index)
                for row in range(len(self.LAYOUT_ROWS), self.layout_table.rowCount()):
                    jk = self._layout_json_key_for_row(row)
                    if not jk or jk not in system_data:
                        continue
                    cell_widget = self.layout_table.cellWidget(row, col)
                    if isinstance(cell_widget, QLineEdit):
                        cell_widget.setText(str(system_data[jk]))
        finally:
            for w in blocked:
                w.blockSignals(False)

        # Only auto-fill cabin width / depth for columns where the saved data did not provide them.
        for col, system_data in enumerate(systems_data, start=2):
            saved_width = str(system_data.get('Cabin width', '') or '').strip()
            if not saved_width:
                self._apply_cabin_width_for_column(col)

        # Refresh formula-driven cells: manual values are preserved and flagged when they differ.
        for col in range(2, self.layout_table.columnCount()):
            self._sync_derived_fields(col)

    def initialize_lift_columns(self):
        for _ in range(self.number_of_lifts):
            self.add_lift_column()

    def add_lift_column(self):
        col_position = self.layout_table.columnCount()
        self.layout_table.insertColumn(col_position)
        self.layout_table.setHorizontalHeaderItem(
            col_position, QTableWidgetItem(f'Lift {col_position - 1}')
        )

        for row in range(len(self.LAYOUT_ROWS)):
            if row == self.ROW_CABIN_TYPE:
                w = OverrideComboBox()
                w.addItems(['Deep', 'Wide'])
                w.currentTextChanged.connect(lambda *_a, cp=col_position: self._apply_cabin_width_for_column(cp))
                # Highlight as a required user-input field; ``set_base_style_sheet``
                # keeps the green fill while still letting the override (amber)
                # state win when a non-standard value is entered.
                w.set_base_style_sheet(REQUIRED_FIELD_COMBO_QSS)
                widget = w
            elif row == self.ROW_CABIN_WIDTH:
                widget = QLineEdit()
                widget.textChanged.connect(
                    lambda *_a, cp=col_position: self._apply_cabin_depth_for_column(cp)
                )
            elif row == self.ROW_CABIN_DEPTH:
                widget = QLineEdit()
                widget.textChanged.connect(lambda *_a, cp=col_position: self._sync_derived_fields(cp))
            elif row == self.ROW_CLADDING:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
                widget.textChanged.connect(lambda *_a, cp=col_position: self._sync_derived_fields(cp))
            elif row == self.ROW_CLEAR_CABIN_HEIGHT:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
                widget.textChanged.connect(lambda *_a, cp=col_position: self._sync_derived_fields(cp))
                
            elif row == self.ROW_STRUCTURAL_CABIN_HEIGHT:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())
                widget.textChanged.connect(
                    lambda *_a, cp=col_position: self._sync_derived_fields(cp)
                )
            elif row in (
                self.ROW_DOOR_WIDTH,
                self.ROW_DOOR_STRUCTURAL_WIDTH,
                self.ROW_DOOR_HEIGHT,
                self.ROW_DOOR_STRUCTURAL_HEIGHT,
            ):
                widget = QLineEdit()
                widget.textChanged.connect(
                    lambda *_a, cp=col_position: self._sync_derived_fields(cp)
                )
            elif row == self.ROW_DOOR_TYPE:
                widget = QLineEdit()
                widget.textChanged.connect(
                    lambda *_a, cp=col_position: self._sync_derived_fields(cp)
                )
            elif row in (
                self.ROW_SHAFT_WIDTH_SUGG,
                self.ROW_SHAFT_DEPTH_SUGG,
                self.ROW_SHAFT_HEAD_SUGG,
                self.ROW_SHAFT_PIT_SUGG,
            ):
                widget = QLineEdit()
                widget.textChanged.connect(
                    lambda *_a, cp=col_position: self._sync_derived_fields(cp)
                )
            elif row in self._COMBO_OPTIONS:
                w = OverrideComboBox()
                w.addItems(self._COMBO_OPTIONS[row])
                widget = w
            else:
                widget = QLineEdit()
                widget.setValidator(QDoubleValidator())

            if isinstance(widget, OverrideComboBox):
                widget.set_override_context(self.LAYOUT_ROWS[row][1], col_position - 2)

            self.layout_table.setCellWidget(row, col_position, widget)

        for row in range(len(self.LAYOUT_ROWS), self.layout_table.rowCount()):
            self._fill_custom_layout_value_cell(row, col_position)

        self._apply_cabin_width_for_column(col_position)

    def _infer_layout_custom_meta(self, systems: list) -> list:
        meta = normalize_meta_list(self.user_inputs.get(KEY_CUSTOM_LAYOUT))
        if meta:
            return meta
        ordered: list[str] = []
        seen: set[str] = set()
        for sys in systems:
            if not isinstance(sys, dict):
                continue
            for k in sys:
                if k in self.LAYOUT_FIXED_JSON_KEYS or k in seen:
                    continue
                seen.add(k)
                ordered.append(k)
        return [{"name": k, "unit": ""} for k in ordered]

    def _fill_custom_layout_value_cell(self, row: int, col: int) -> None:
        w = QLineEdit()
        self.layout_table.setCellWidget(row, col, w)

    def _rebuild_custom_layout_rows(self, systems: list) -> None:
        clear_rows_from(self.layout_table, len(self.LAYOUT_ROWS))
        meta = self._infer_layout_custom_meta(systems)
        used: set[str] = set()
        for entry in meta:
            raw_name = str(entry.get("name", "") or "").strip()
            unit = str(entry.get("unit", "") or "").strip()
            name = raw_name if raw_name else default_custom_name(used)
            used.add(name)
            append_custom_row_two_column_headers(
                self.layout_table,
                name=name,
                unit=unit,
                first_data_col=2,
                fill_data_cell=self._fill_custom_layout_value_cell,
            )

    def _on_add_custom_parameter_row(self) -> None:
        used: set[str] = set()
        for r in range(len(self.LAYOUT_ROWS), self.layout_table.rowCount()):
            w = self.layout_table.cellWidget(r, 0)
            if isinstance(w, QLineEdit) and w.text().strip():
                used.add(w.text().strip())
        name = default_custom_name(used)
        append_custom_row_two_column_headers(
            self.layout_table,
            name=name,
            unit="",
            first_data_col=2,
            fill_data_cell=self._fill_custom_layout_value_cell,
        )

    def _on_remove_custom_parameter_row(self) -> None:
        fixed = len(self.LAYOUT_ROWS)
        if self.layout_table.rowCount() <= fixed:
            return
        self.layout_table.removeRow(self.layout_table.rowCount() - 1)
        building = self.user_inputs.get('BuildingSystems') or []
        if len(building) > 0:
            self.merge_layout_into_lift_systems()
        else:
            self.user_inputs[KEY_CUSTOM_LAYOUT] = meta_from_table(
                self.layout_table,
                fixed_row_count=fixed,
                has_unit_column=True,
            )

    def merge_layout_into_lift_systems(self):
        """Write layout table columns into ``user_inputs['LayoutInformation']`` (one dict per lift)."""
        building = self.user_inputs.get('BuildingSystems') or []
        n = len(building)
        if n == 0:
            return

        existing = self.user_inputs.get(KEY_LAYOUT_INFORMATION) or []
        systems_data = []

        for idx in range(n):
            col = idx + 2
            merged = dict(existing[idx]) if idx < len(existing) else {}

            if col < self.layout_table.columnCount():
                for row in range(self.layout_table.rowCount()):
                    jk = self._layout_json_key_for_row(row)
                    if not jk:
                        continue
                    cell_widget = self.layout_table.cellWidget(row, col)
                    if isinstance(cell_widget, QLineEdit):
                        value = cell_widget.text()
                    elif isinstance(cell_widget, QComboBox):
                        value = cell_widget.currentText()
                    else:
                        value = ''
                    v = value.strip() if isinstance(value, str) else value
                    if v != '':
                        merged[jk] = value
                        continue
                    if isinstance(cell_widget, QLineEdit):
                        prev = merged.get(jk)
                        if (
                            prev is not None
                            and str(prev).strip() != ''
                            and not cell_widget.isModified()
                        ):
                            merged[jk] = prev
                            continue
                    merged[jk] = ''

            systems_data.append(merged)

        self.user_inputs[KEY_LAYOUT_INFORMATION] = systems_data
        self.user_inputs[KEY_CUSTOM_LAYOUT] = meta_from_table(
            self.layout_table,
            fixed_row_count=len(self.LAYOUT_ROWS),
            has_unit_column=True,
        )

    def collect_data_and_go_next(self):
        self.merge_layout_into_lift_systems()
        self.next_clicked.emit(self.user_inputs)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    sample = {
        'BuildingSystems': [{'Number': '1'}],
        'GeneralSpecification': [{'Load capacity': '630'}],
        'LayoutInformation': [{'Cabin width': '1100'}],
    }
    w = LayoutInformationPage(sample)
    w.show()
    sys.exit(app.exec_())
