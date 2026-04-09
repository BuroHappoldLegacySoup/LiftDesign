"""
Cost — per-lift cost estimation and calculation fields.
Persisted under ``user_inputs['Cost']`` as a list of dicts (one per lift).
"""
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QMessageBox,
)
from PyQt5.QtCore import pyqtSignal, Qt
import json
import os
import sys
from datetime import datetime

from gui.change_tracker import compute_changes, create_change_records


class CostPage(QWidget):
    next_clicked = pyqtSignal(dict)
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
        self.cost_table.setColumnCount(1)
        self.cost_table.setHorizontalHeaderLabels(['Description'])
        self.cost_table.setRowCount(len(self.DESCRIPTIONS))

        for row, description in enumerate(self.DESCRIPTIONS):
            item = QTableWidgetItem(description)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.cost_table.setItem(row, 0, item)

        self.cost_table.horizontalHeader().setStretchLastSection(True)
        self.cost_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cost_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

        cost_layout.addWidget(self.cost_table)

        save_button = QPushButton('Save and Proceed')
        save_button.setStyleSheet("background-color: white;")
        save_button.clicked.connect(self.collect_data_and_go_next)
        scroll_layout.addWidget(save_button)

        self.initialize_lift_columns()

    def sync_user_inputs(self, user_inputs):
        """Update shared project dict and refresh cells when revisiting this page."""
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs.get('BuildingSystems') or [])
        while self.cost_table.columnCount() > 1:
            self.cost_table.removeColumn(self.cost_table.columnCount() - 1)
        self.initialize_lift_columns()
        if 'Cost' in self.user_inputs:
            self.populate_from_input(self.user_inputs['Cost'])

    def initialize_lift_columns(self):
        for _ in range(self.number_of_lifts):
            self.add_lift_column()

    def add_lift_column(self):
        col_position = self.cost_table.columnCount()
        self.cost_table.insertColumn(col_position)
        self.cost_table.setHorizontalHeaderItem(col_position, QTableWidgetItem(f'Lift {col_position}'))

        for row in range(self.cost_table.rowCount()):
            w = QLineEdit()
            self.cost_table.setCellWidget(row, col_position, w)

    def populate_from_input(self, cost_data):
        for col, entry in enumerate(cost_data, start=1):
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
        # Commit any active table cell / line edit before reading widgets (Qt can leave edits pending).
        fw = QApplication.focusWidget()
        if fw is not None:
            fw.clearFocus()
        QApplication.processEvents()

        main = self._main_window or self.window()
        if main is not None and hasattr(main, "_flush_project_data_from_pages_before_save"):
            main._flush_project_data_from_pages_before_save()
        if main is not None and getattr(main, "page1", None) is not None:
            self.user_inputs = main.page1.user_inputs

        cost_data = []
        for col in range(1, self.cost_table.columnCount()):
            entry = {}
            for row, description in enumerate(self.DESCRIPTIONS):
                w = self.cost_table.cellWidget(row, col)
                entry[description] = w.text() if isinstance(w, QLineEdit) else ''
            cost_data.append(entry)

        self.user_inputs['Cost'] = cost_data

        baseline = self.user_inputs.pop('_baseline', None)
        if baseline is not None:
            changes = compute_changes(baseline, self.user_inputs)
            if changes:
                new_records = create_change_records(changes)
                existing_history = self.user_inputs.get('ChangeHistory', [])
                self.user_inputs['ChangeHistory'] = existing_history + new_records

        try:
            base_path = os.path.join(os.path.expanduser('~'), 'LiftDesigner', 'Projects')
            preferred = getattr(main, "project_file_path", None) if main is not None else None
            if preferred and str(preferred).strip():
                file_path = str(preferred).strip()
                if not file_path.endswith('.json'):
                    file_path += '.json'
            elif 'FileName' in self.user_inputs:
                file_name = self.user_inputs['FileName']
                if not file_name.endswith('.json'):
                    file_name += '.json'
                file_path = os.path.join(base_path, file_name)
            else:
                file_path = self._generate_file_name(base_path, 'LiftDesigner')

            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            with open(file_path, 'w') as json_file:
                json.dump(self.user_inputs, json_file)

            self.file_saved.emit(file_path)
            QMessageBox.information(
                self,
                "Success",
                f"File successfully saved to:\n{file_path}",
            )
            self.next_clicked.emit(self.user_inputs)
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
