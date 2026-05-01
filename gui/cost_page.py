"""
Cost — per-lift cost estimation and calculation fields.
Persisted under ``user_inputs['Cost']`` as a list of dicts (one per lift).
"""
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QFileDialog,
    QLabel,
    QDialog,
    QDialogButtonBox,
    QComboBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
import os
import sys
from datetime import datetime
from typing import Optional

from gui.change_tracker import compute_changes, create_change_records
from gui.project_json import save_project_json
from gui.project_lift_schema import KEY_LIFT_COLUMN_GROUPS, normalize_project_lift_data
from gui.custom_parameter_rows import (
    KEY_CUSTOM_COST,
    add_plus_minus_button_row,
    append_custom_row_two_column_headers,
    clear_rows_from,
    default_custom_name,
    meta_from_table,
    normalize_meta_list,
)
import copy
from lift_designer_vt_derived import (
    DEFAULT_DOOR_MANUFACTURER,
    DOOR_MANUFACTURER_OPTIONS,
    normalize_door_manufacturer,
)


class DoorManufacturerDialog(QDialog):
    """
    Modal selector for the VT R277 ``Door manufacturer choice`` cell.

    The chosen value drives door RID, door depth and door/wall clearance lookups in
    both the LD and VT Schedules exports. The dialog defaults to the project's
    previously selected manufacturer (``user_inputs["DoorManufacturer"]``) so users
    only have to confirm on subsequent exports.
    """

    def __init__(self, current: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select door manufacturer")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Select the door manufacturer used for this export. The choice "
                "controls door RID lookups, door depths and door/wall clearance "
                "values in the exported workbook."
            )
        )

        self._combo = QComboBox()
        self._combo.addItems(DOOR_MANUFACTURER_OPTIONS)
        normalized = normalize_door_manufacturer(current) if current else DEFAULT_DOOR_MANUFACTURER
        idx = self._combo.findText(normalized)
        self._combo.setCurrentIndex(idx if idx >= 0 else 0)
        layout.addWidget(self._combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected(self) -> str:
        """Return the canonical manufacturer string chosen by the user."""
        return self._combo.currentText()


class CostPage(QWidget):
    next_clicked = pyqtSignal(dict)
    back_clicked = pyqtSignal()
    file_saved = pyqtSignal(str)

    DESCRIPTIONS = [
        'Cost estimation',
        'Cost calculation',
    ]
    COST_FIXED_KEYS = frozenset(DESCRIPTIONS)

    def _cost_json_key_for_row(self, row: int) -> str:
        if row < len(self.DESCRIPTIONS):
            return self.DESCRIPTIONS[row]
        w = self.cost_table.cellWidget(row, 0)
        return w.text().strip() if isinstance(w, QLineEdit) else ""

    def __init__(self, user_inputs, main_window=None):
        super().__init__()
        self._main_window = main_window
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs.get('BuildingSystems') or [])
        self.initUI()

    def initUI(self):
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)

        scroll_layout = QVBoxLayout(scroll_widget)

        cost_box = QGroupBox("Cost")
        cost_box.setObjectName("cost_box")
        cost_box.setStyleSheet(
            "#cost_box {background-color: white; border: 3px solid rgb(196, 214, 0); font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(cost_box)

        cost_layout = QVBoxLayout(cost_box)

        self.cost_table = QTableWidget()
        self.cost_table.setColumnCount(2)
        self.cost_table.setHorizontalHeaderLabels(['Description', 'Unit'])
        self.cost_table.setRowCount(len(self.DESCRIPTIONS))

        for row, description in enumerate(self.DESCRIPTIONS):
            item = QTableWidgetItem(description)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.cost_table.setItem(row, 0, item)
            u_item = QTableWidgetItem('—')
            u_item.setFlags(u_item.flags() & ~Qt.ItemIsEditable)
            self.cost_table.setItem(row, 1, u_item)

        self.cost_table.horizontalHeader().setStretchLastSection(True)
        self.cost_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cost_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.cost_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        cost_layout.addWidget(self.cost_table)
        add_plus_minus_button_row(
            cost_layout,
            self._on_add_custom_parameter_row,
            self._on_remove_custom_parameter_row,
        )

        ld_export_row = QHBoxLayout()
        ld_export_row.addWidget(QLabel("LD data transport"))
        self._door_manufacturer_btn = QPushButton()
        self._door_manufacturer_btn.setStyleSheet("background-color: white;")
        self._door_manufacturer_btn.clicked.connect(self._on_select_door_manufacturer)
        self._refresh_door_manufacturer_button()
        ld_export_row.addWidget(self._door_manufacturer_btn)
        self._ld_export_btn = QPushButton("LD data export")
        self._ld_export_btn.setStyleSheet("background-color: white;")
        self._ld_export_btn.clicked.connect(self._on_ld_data_export)
        ld_export_row.addWidget(self._ld_export_btn)
        self._schedule_export_btn = QPushButton("VT Schedules export")
        self._schedule_export_btn.setStyleSheet("background-color: white;")
        self._schedule_export_btn.clicked.connect(self._on_schedule_export)
        ld_export_row.addWidget(self._schedule_export_btn)
        ld_export_row.addStretch()
        cost_layout.addLayout(ld_export_row)

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
        self._ld_export_btn.setEnabled(self.number_of_lifts >= 1)
        self._schedule_export_btn.setEnabled(self.number_of_lifts >= 1)

        cost = copy.deepcopy(self.user_inputs.get('Cost') or [])
        while len(cost) < self.number_of_lifts:
            cost.append({})
        while len(cost) > self.number_of_lifts:
            cost.pop()
        self._rebuild_custom_cost_rows(cost)
        self.populate_from_input(cost)

    # --- Door manufacturer selection -----------------------------------------

    def _current_door_manufacturer(self) -> str:
        """Return the project's stored door manufacturer (defaults if unset/invalid)."""
        stored = ""
        if isinstance(self.user_inputs, dict):
            stored = self.user_inputs.get("DoorManufacturer", "") or ""
        return normalize_door_manufacturer(stored)

    def _refresh_door_manufacturer_button(self) -> None:
        """Sync the selector button label to the currently stored manufacturer."""
        current = self._current_door_manufacturer()
        self._door_manufacturer_btn.setText(f"Door manufacturer: {current}")

    def _on_select_door_manufacturer(self) -> None:
        """Open the manufacturer dialog and persist the result on Accept."""
        dlg = DoorManufacturerDialog(current=self._current_door_manufacturer(), parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        if not isinstance(self.user_inputs, dict):
            return
        self.user_inputs["DoorManufacturer"] = dlg.selected()
        self._refresh_door_manufacturer_button()

    def _ensure_door_manufacturer_selected(self, payload: dict) -> Optional[str]:
        """
        Prompt for the door manufacturer if one isn't already stored, then return
        the canonical value. Returns ``None`` if the user cancels the dialog so the
        caller can abort the export.
        """
        if not isinstance(payload, dict):
            return DEFAULT_DOOR_MANUFACTURER
        stored = payload.get("DoorManufacturer", "")
        if stored:
            normalized = normalize_door_manufacturer(stored)
            payload["DoorManufacturer"] = normalized
            self._refresh_door_manufacturer_button()
            return normalized
        dlg = DoorManufacturerDialog(current="", parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return None
        choice = dlg.selected()
        payload["DoorManufacturer"] = choice
        self._refresh_door_manufacturer_button()
        return choice

    def _default_ld_export_filename(self, payload: dict) -> str:
        fn = payload.get("FileName", "project")
        base = "LD_export"
        if isinstance(fn, str) and fn.strip():
            base = os.path.splitext(fn.strip())[0] or base
        return f"{base}_LD.xlsx"

    def _default_schedule_export_filename(self, payload: dict) -> str:
        fn = payload.get("FileName", "project")
        base = "VT_schedules"
        if isinstance(fn, str) and fn.strip():
            base = os.path.splitext(fn.strip())[0] or base
        return f"{base}_Schedules.xlsx"

    def _on_ld_data_export(self) -> None:
        if self.number_of_lifts < 1:
            QMessageBox.warning(
                self,
                "LD data export",
                "Add at least one lift in Building System Information first.",
            )
            return

        fw = QApplication.focusWidget()
        if fw is not None:
            fw.clearFocus()
        QApplication.processEvents()

        main = self._main_window_for_save()
        payload = self.user_inputs
        if main is not None:
            main._flush_project_data_from_pages_before_save()
            if getattr(main, "page1", None) is not None:
                payload = main.page1.user_inputs
                self.user_inputs = payload

        self.sync_cost_to_user_inputs()

        manufacturer = self._ensure_door_manufacturer_selected(payload)
        if manufacturer is None:
            return

        start_dir = os.path.join(os.path.expanduser("~"), "Documents")
        preferred = getattr(main, "project_file_path", None) if main is not None else None
        if preferred and str(preferred).strip():
            start_dir = os.path.dirname(os.path.abspath(str(preferred).strip()))

        default_name = self._default_ld_export_filename(payload)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save LD data export",
            os.path.join(start_dir, default_name),
            "Excel workbook (*.xlsx)",
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            from lift_designer_ld_export import build_ld_rows_per_lift, write_ld_exports_per_group
        except ImportError as e:
            QMessageBox.critical(
                self,
                "LD data export",
                f"Could not load export module (is openpyxl installed?).\n{e}",
            )
            return

        try:
            normalize_project_lift_data(payload)
            rows_by_lift = build_ld_rows_per_lift(
                payload,
                self.number_of_lifts,
                door_manufacturer=manufacturer,
            )
            written = write_ld_exports_per_group(
                path,
                rows_by_lift,
                payload.get(KEY_LIFT_COLUMN_GROUPS),
            )
            QMessageBox.information(
                self,
                "LD data export",
                "Saved:\n" + "\n".join(written),
            )
        except Exception as e:
            QMessageBox.critical(self, "LD data export", f"Export failed:\n{e}")

    def _on_schedule_export(self) -> None:
        """Export every VT parameter flagged with *yes* in column E to a schedules workbook."""
        if self.number_of_lifts < 1:
            QMessageBox.warning(
                self,
                "VT Schedules export",
                "Add at least one lift in Building System Information first.",
            )
            return

        fw = QApplication.focusWidget()
        if fw is not None:
            fw.clearFocus()
        QApplication.processEvents()

        main = self._main_window_for_save()
        payload = self.user_inputs
        if main is not None:
            main._flush_project_data_from_pages_before_save()
            if getattr(main, "page1", None) is not None:
                payload = main.page1.user_inputs
                self.user_inputs = payload

        self.sync_cost_to_user_inputs()

        try:
            from lift_designer_schedules_export import (
                TEMPLATE_MAX_LIFTS,
                TEMPLATE_REVISION_MAX_ROWS,
                write_schedule_workbook_from_template,
            )
        except ImportError as e:
            QMessageBox.critical(
                self,
                "VT Schedules export",
                f"Could not load schedules export module (is openpyxl installed?).\n{e}",
            )
            return

        manufacturer = self._ensure_door_manufacturer_selected(payload)
        if manufacturer is None:
            return

        overrides_by_lift = self._collect_schedule_overrides(main)

        # Revision / title-block dialog. Cancel here aborts the whole export
        # before we even prompt for a save path.
        from gui.schedule_revision_dialog import ScheduleRevisionDialog

        existing_revs = payload.get("ScheduleRevisions") if isinstance(payload, dict) else []
        if not isinstance(existing_revs, list):
            existing_revs = []

        rev_dialog = ScheduleRevisionDialog(existing_revs, parent=self)
        if rev_dialog.exec_() != rev_dialog.Accepted:
            return

        new_revision = rev_dialog.get_new_revision()
        if new_revision is not None:
            if not isinstance(payload.get("ScheduleRevisions"), list):
                payload["ScheduleRevisions"] = []
            payload["ScheduleRevisions"].append(new_revision)

        revisions_to_write = list(payload.get("ScheduleRevisions") or [])

        start_dir = os.path.join(os.path.expanduser("~"), "Documents")
        preferred = getattr(main, "project_file_path", None) if main is not None else None
        if preferred and str(preferred).strip():
            start_dir = os.path.dirname(os.path.abspath(str(preferred).strip()))

        default_name = self._default_schedule_export_filename(payload)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save VT Schedules export",
            os.path.join(start_dir, default_name),
            "Excel workbook (*.xlsx)",
        )
        if not path:
            # If the user cancels after already committing a new revision to the
            # payload, roll it back so the project isn't dirtied by an aborted export.
            if new_revision is not None and payload.get("ScheduleRevisions"):
                payload["ScheduleRevisions"].pop()
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            normalize_project_lift_data(payload)
            written = write_schedule_workbook_from_template(
                path,
                payload,
                self.number_of_lifts,
                revisions=revisions_to_write or None,
                overrides=overrides_by_lift or None,
                door_manufacturer=manufacturer,
            )
            msg_extras = []
            if self.number_of_lifts > TEMPLATE_MAX_LIFTS:
                msg_extras.append(
                    f"Note: the template supports {TEMPLATE_MAX_LIFTS} lifts; "
                    f"only the first {written} of {self.number_of_lifts} lifts "
                    "were written."
                )
            if len(revisions_to_write) > TEMPLATE_REVISION_MAX_ROWS:
                dropped = len(revisions_to_write) - TEMPLATE_REVISION_MAX_ROWS
                msg_extras.append(
                    f"Note: the title block holds {TEMPLATE_REVISION_MAX_ROWS} "
                    f"revisions; the {dropped} oldest entries were omitted."
                )
            if msg_extras:
                QMessageBox.information(
                    self,
                    "VT Schedules export",
                    f"Saved:\n{path}\n\n" + "\n\n".join(msg_extras),
                )
            else:
                QMessageBox.information(
                    self, "VT Schedules export", f"Saved:\n{path}"
                )
        except FileNotFoundError as e:
            QMessageBox.critical(self, "VT Schedules export", f"Export failed:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "VT Schedules export", f"Export failed:\n{e}")

    def _collect_schedule_overrides(self, main_window) -> dict:
        """
        Walk every :class:`OverrideComboBox` under the app and build
        ``{lift_index: [schedule_label, ...]}`` for the ones that are currently
        holding a non-standard value. Labels are passed through as-is; the
        writer normalizes them before matching to template column A.

        ``main_window`` is the application root. We prefer scanning from there
        so every page's combos are covered even when only the cost page is
        visible.
        """
        try:
            from gui.override_combobox import OverrideComboBox
        except ImportError:
            return {}

        root = main_window if main_window is not None else self.window()
        if root is None:
            return {}

        result: dict = {}
        try:
            combos = root.findChildren(OverrideComboBox)
        except Exception:
            combos = []
        for combo in combos:
            try:
                if not combo.is_override:
                    continue
                label = (combo.override_label or "").strip()
                idx = int(combo.override_lift_index)
            except Exception:
                continue
            if not label or idx < 0:
                continue
            labels = result.setdefault(idx, [])
            if label not in labels:
                labels.append(label)
        return result

    def _main_window_for_save(self):
        """Resolve the app main window so pre-save flush runs (parent chain, ``window()``, top-level scan)."""
        w = self._main_window
        if w is not None and hasattr(w, '_flush_project_data_from_pages_before_save') and getattr(w, 'page1', None) is not None:
            return w
        p = self.parent()
        while p is not None:
            if hasattr(p, '_flush_project_data_from_pages_before_save') and getattr(p, 'page1', None) is not None:
                return p
            p = p.parent()
        win = self.window()
        if hasattr(win, '_flush_project_data_from_pages_before_save') and getattr(win, 'page1', None) is not None:
            return win
        app = QApplication.instance()
        if app is not None:
            for tw in app.topLevelWidgets():
                if (
                    hasattr(tw, '_flush_project_data_from_pages_before_save')
                    and getattr(tw, 'page1', None) is not None
                ):
                    return tw
        return None

    def sync_cost_to_user_inputs(self):
        """Write the cost table into ``user_inputs['Cost']`` (used when leaving this tab and before JSON save)."""
        cost_data = []
        for col in range(2, self.cost_table.columnCount()):
            entry = {}
            for row in range(self.cost_table.rowCount()):
                key = self._cost_json_key_for_row(row)
                if not key:
                    continue
                w = self.cost_table.cellWidget(row, col)
                entry[key] = w.text() if isinstance(w, QLineEdit) else ''
            cost_data.append(entry)
        self.user_inputs['Cost'] = cost_data
        self.user_inputs[KEY_CUSTOM_COST] = meta_from_table(
            self.cost_table,
            fixed_row_count=len(self.DESCRIPTIONS),
            has_unit_column=True,
        )

    def _infer_cost_custom_meta(self, cost_list: list) -> list:
        meta = normalize_meta_list(self.user_inputs.get(KEY_CUSTOM_COST))
        if meta:
            return meta
        ordered: list[str] = []
        seen: set[str] = set()
        for entry in cost_list:
            if not isinstance(entry, dict):
                continue
            for k in entry:
                if k in self.COST_FIXED_KEYS or k in seen:
                    continue
                seen.add(k)
                ordered.append(k)
        return [{"name": k, "unit": ""} for k in ordered]

    def _fill_custom_cost_cell(self, row: int, col: int) -> None:
        w = QLineEdit()
        self.cost_table.setCellWidget(row, col, w)

    def _rebuild_custom_cost_rows(self, cost_list: list) -> None:
        clear_rows_from(self.cost_table, len(self.DESCRIPTIONS))
        meta = self._infer_cost_custom_meta(cost_list)
        used: set[str] = set()
        for entry in meta:
            raw_name = str(entry.get("name", "") or "").strip()
            unit = str(entry.get("unit", "") or "").strip()
            name = raw_name if raw_name else default_custom_name(used)
            used.add(name)
            append_custom_row_two_column_headers(
                self.cost_table,
                name=name,
                unit=unit,
                first_data_col=2,
                fill_data_cell=self._fill_custom_cost_cell,
            )

    def _on_add_custom_parameter_row(self) -> None:
        used: set[str] = set()
        for r in range(len(self.DESCRIPTIONS), self.cost_table.rowCount()):
            w = self.cost_table.cellWidget(r, 0)
            if isinstance(w, QLineEdit) and w.text().strip():
                used.add(w.text().strip())
        name = default_custom_name(used)
        append_custom_row_two_column_headers(
            self.cost_table,
            name=name,
            unit="",
            first_data_col=2,
            fill_data_cell=self._fill_custom_cost_cell,
        )

    def _on_remove_custom_parameter_row(self) -> None:
        if self.cost_table.rowCount() <= len(self.DESCRIPTIONS):
            return
        self.cost_table.removeRow(self.cost_table.rowCount() - 1)
        self.sync_cost_to_user_inputs()

    def sync_user_inputs(self, user_inputs):
        """Update shared project dict and refresh cells when revisiting this page."""
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs.get('BuildingSystems') or [])
        while self.cost_table.columnCount() > 2:
            self.cost_table.removeColumn(self.cost_table.columnCount() - 1)
        self.initialize_lift_columns()
        cost = copy.deepcopy(self.user_inputs.get('Cost') or [])
        while len(cost) < self.number_of_lifts:
            cost.append({})
        while len(cost) > self.number_of_lifts:
            cost.pop()
        self._rebuild_custom_cost_rows(cost)
        self.populate_from_input(cost)
        self._ld_export_btn.setEnabled(self.number_of_lifts >= 1)
        self._refresh_door_manufacturer_button()

    def initialize_lift_columns(self):
        for _ in range(self.number_of_lifts):
            self.add_lift_column()

    def add_lift_column(self):
        col_position = self.cost_table.columnCount()
        self.cost_table.insertColumn(col_position)
        self.cost_table.setHorizontalHeaderItem(
            col_position, QTableWidgetItem(f'Lift {col_position - 1}')
        )

        for row in range(len(self.DESCRIPTIONS)):
            w = QLineEdit()
            self.cost_table.setCellWidget(row, col_position, w)

        for row in range(len(self.DESCRIPTIONS), self.cost_table.rowCount()):
            self._fill_custom_cost_cell(row, col_position)

    def populate_from_input(self, cost_data):
        for col, entry in enumerate(cost_data, start=2):
            if col >= self.cost_table.columnCount():
                break
            for row in range(self.cost_table.rowCount()):
                key = self._cost_json_key_for_row(row)
                if not key or key not in entry:
                    continue
                cell = self.cost_table.cellWidget(row, col)
                if isinstance(cell, QLineEdit):
                    cell.setText(str(entry[key]))

    def _generate_file_name(self, base_path: str, prefix: str) -> str:
        date_str = datetime.now().strftime('%y%m%d')
        i = 1
        while True:
            file_name = f"{date_str}_{prefix}_{i}.json"
            full_path = os.path.join(base_path, file_name)
            if not os.path.exists(full_path):
                return full_path
            i += 1

    def collect_data_and_go_next(self):
        fw = QApplication.focusWidget()
        if fw is not None:
            fw.clearFocus()
        QApplication.processEvents()

        main = self._main_window_for_save()
        payload = self.user_inputs
        if main is not None:
            main._flush_project_data_from_pages_before_save()
            if getattr(main, 'page1', None) is not None:
                payload = main.page1.user_inputs
                self.user_inputs = payload

        self.sync_cost_to_user_inputs()

        baseline = payload.pop('_baseline', None)
        if baseline is not None:
            changes = compute_changes(baseline, payload)
            if changes:
                new_records = create_change_records(changes)
                existing_history = payload.get('ChangeHistory', [])
                payload['ChangeHistory'] = existing_history + new_records

        try:
            base_path = os.path.join(os.path.expanduser('~'), 'LiftDesigner', 'Projects')
            preferred = getattr(main, 'project_file_path', None) if main is not None else None
            if preferred and str(preferred).strip():
                file_path = str(preferred).strip()
                if not file_path.endswith('.json'):
                    file_path += '.json'
            elif 'FileName' in payload:
                file_name = payload['FileName']
                if not file_name.endswith('.json'):
                    file_name += '.json'
                file_path = os.path.join(base_path, file_name)
            else:
                file_path = self._generate_file_name(base_path, 'LiftDesigner')

            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            save_project_json(file_path, payload)

            self.file_saved.emit(file_path)
            QMessageBox.information(
                self,
                "Success",
                f"File successfully saved to:\n{file_path}",
            )
            self.next_clicked.emit(payload)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save data: {str(e)}",
            )


if __name__ == '__main__':
    app = QApplication(sys.argv)
    sample = {
        'BuildingSystems': [{'Number': '1'}, {'Number': '2'}],
        'Cost': [
            {'Cost estimation': '100000', 'Cost calculation': '95000'},
            {'Cost estimation': '120000', 'Cost calculation': '118000'},
        ],
    }
    w = CostPage(sample)
    w.show()
    sys.exit(app.exec_())
