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
)
from PyQt5.QtCore import pyqtSignal, Qt
import os
import sys
from datetime import datetime

from gui.change_tracker import compute_changes, create_change_records
from gui.project_json import save_project_json
from gui.project_lift_schema import normalize_project_lift_data


class CostPage(QWidget):
    next_clicked = pyqtSignal(dict)
    back_clicked = pyqtSignal()
    file_saved = pyqtSignal(str)

    DESCRIPTIONS = [
        'Cost estimation',
        'Cost calculation',
    ]

    def __init__(self, user_inputs, main_window=None):
        super().__init__()
        self._main_window = main_window
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs.get('BuildingSystems') or [])
        self.initUI()

        if 'Cost' in self.user_inputs:
            self.populate_from_input(self.user_inputs['Cost'])

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

        ld_export_row = QHBoxLayout()
        ld_export_row.addWidget(QLabel("LD data transport"))
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
            from lift_designer_ld_export import build_ld_rows_per_lift, write_ld_workbook_multi
        except ImportError as e:
            QMessageBox.critical(
                self,
                "LD data export",
                f"Could not load export module (is openpyxl installed?).\n{e}",
            )
            return

        try:
            normalize_project_lift_data(payload)
            rows_by_lift = build_ld_rows_per_lift(payload, self.number_of_lifts)
            write_ld_workbook_multi(path, rows_by_lift)
            QMessageBox.information(self, "LD data export", f"Saved:\n{path}")
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
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            from lift_designer_schedules_export import (
                build_schedule_rows_per_lift,
                write_schedule_workbook_multi,
            )
        except ImportError as e:
            QMessageBox.critical(
                self,
                "VT Schedules export",
                f"Could not load schedules export module (is openpyxl installed?).\n{e}",
            )
            return

        try:
            normalize_project_lift_data(payload)
            rows_by_lift = build_schedule_rows_per_lift(payload, self.number_of_lifts)
            write_schedule_workbook_multi(path, rows_by_lift)
            QMessageBox.information(self, "VT Schedules export", f"Saved:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "VT Schedules export", f"Export failed:\n{e}")

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
            for row, description in enumerate(self.DESCRIPTIONS):
                w = self.cost_table.cellWidget(row, col)
                entry[description] = w.text() if isinstance(w, QLineEdit) else ''
            cost_data.append(entry)
        self.user_inputs['Cost'] = cost_data

    def sync_user_inputs(self, user_inputs):
        """Update shared project dict and refresh cells when revisiting this page."""
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs.get('BuildingSystems') or [])
        while self.cost_table.columnCount() > 2:
            self.cost_table.removeColumn(self.cost_table.columnCount() - 1)
        self.initialize_lift_columns()
        if 'Cost' in self.user_inputs:
            self.populate_from_input(self.user_inputs['Cost'])
        self._ld_export_btn.setEnabled(self.number_of_lifts >= 1)

    def initialize_lift_columns(self):
        for _ in range(self.number_of_lifts):
            self.add_lift_column()

    def add_lift_column(self):
        col_position = self.cost_table.columnCount()
        self.cost_table.insertColumn(col_position)
        self.cost_table.setHorizontalHeaderItem(
            col_position, QTableWidgetItem(f'Lift {col_position - 1}')
        )

        for row in range(self.cost_table.rowCount()):
            w = QLineEdit()
            self.cost_table.setCellWidget(row, col_position, w)

    def populate_from_input(self, cost_data):
        for col, entry in enumerate(cost_data, start=2):
            if col >= self.cost_table.columnCount():
                break
            for row, description in enumerate(self.DESCRIPTIONS):
                if description not in entry:
                    continue
                cell = self.cost_table.cellWidget(row, col)
                if isinstance(cell, QLineEdit):
                    cell.setText(str(entry[description]))

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
