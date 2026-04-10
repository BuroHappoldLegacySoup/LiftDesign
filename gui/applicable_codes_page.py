from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QGroupBox, QPushButton, QCheckBox, QComboBox,
    QScrollArea, QTableWidget, QTableWidgetItem, QHeaderView, QHBoxLayout, QLineEdit,
)
from PyQt5.QtCore import pyqtSignal, Qt
import sys


class ApplicableCodesPage(QWidget):
    next_clicked = pyqtSignal(dict)
    back_clicked = pyqtSignal()

    # Row indices — must match ``input_descriptions`` order in ``initUI``
    ROW_VANDALISM = 3
    ROW_FIRE_EMERGENCY_RETURN = 5
    ROW_EVACUATION_TYPE = 6
    ROW_EVACUATION_FUNCTIONS = 7
    ROW_SEISMIC = 8
    ROW_FIRE_RATING_CLASS = 10
    ROW_GREEN_BUILDING = 11

    _CHECKBOX_ROWS = frozenset(
        {0, 1, 2, 4, 5, 9}
    )  # emergency call, accessibilities, firefighter, fire return, fire doors (checkboxes)

    _COMBO_ROWS = frozenset({
        ROW_VANDALISM,
        ROW_EVACUATION_TYPE,
        ROW_EVACUATION_FUNCTIONS,
        ROW_SEISMIC,
        ROW_GREEN_BUILDING,
    })

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs['BuildingSystems'])
        self.initUI()

        if 'Compliance' in self.user_inputs:
            self.populate_from_input(self.user_inputs['Compliance'])

    def initUI(self):
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)

        scroll_layout = QVBoxLayout(scroll_widget)

        codes_box = QGroupBox("Applicable codes")
        codes_box.setObjectName("applicable_codes_box")
        codes_box.setStyleSheet(
            "#applicable_codes_box {background-color: white; border: 3px solid rgb(196, 214, 0); font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(codes_box)

        codes_layout = QVBoxLayout(codes_box)

        self.codes_table = QTableWidget()
        self.codes_table.setColumnCount(2)
        self.codes_table.setHorizontalHeaderLabels(['Description', 'Unit'])

        input_descriptions = [
            'EN81-28 emergency call', 
            'EN81-70 Accessibility', 
            'DIN EN17210 / 18040-1 Accessibility',
            'EN81-71 Vandalism category', 
            'EN81-72 Firefighter elevator', 
            'EN81-73 Fire emergency return',
            'EN81-76 Emergency Evacuation type',
            'EN81-76 Evacuation functions', 
            'EN81-77 Seismic category', 
            'EN81-58 Fire rated landing doors',
            'EN81-58 Fire rating class',
            'Green building certification compliance',
        ]

        self.codes_table.setRowCount(len(input_descriptions))

        for row, description in enumerate(input_descriptions):
            item = QTableWidgetItem(description)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.codes_table.setItem(row, 0, item)
            u_item = QTableWidgetItem('—')
            u_item.setFlags(u_item.flags() & ~Qt.ItemIsEditable)
            self.codes_table.setItem(row, 1, u_item)

        self.codes_table.horizontalHeader().setStretchLastSection(True)
        self.codes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.codes_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.codes_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        codes_layout.addWidget(self.codes_table)

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

    @staticmethod
    def _wrap_centered(inner: QWidget) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.addStretch()
        h.addWidget(inner)
        h.addStretch()
        h.setContentsMargins(0, 0, 0, 0)
        return w

    def _make_combo(self, items: list[str]) -> QComboBox:
        cb = QComboBox()
        cb.setEditable(False)
        cb.setInsertPolicy(QComboBox.NoInsert)
        for t in items:
            cb.addItem(t)
        return cb

    def initialize_lift_columns(self):
        for _ in range(self.number_of_lifts):
            self.add_lift_column()

    def add_lift_column(self):
        col_position = self.codes_table.columnCount()
        self.codes_table.insertColumn(col_position)
        self.codes_table.setHorizontalHeaderItem(col_position, QTableWidgetItem(f'Lift {col_position}'))

        for row in range(self.codes_table.rowCount()):
            if row == self.ROW_VANDALISM:
                w = self._wrap_centered(self._make_combo(['0', '1', '2', '3']))
            elif row == self.ROW_EVACUATION_TYPE:
                w = self._wrap_centered(self._make_combo(['no', 'yes, TYPE A', 'yes, TYPE B']))
            elif row == self.ROW_EVACUATION_FUNCTIONS:
                w = self._wrap_centered(self._make_combo(['Automatic', 'Remote', 'Assisted']))
            elif row == self.ROW_SEISMIC:
                w = self._wrap_centered(self._make_combo(['0', '1', '2', '3']))
            elif row == self.ROW_GREEN_BUILDING:
                w = self._wrap_centered(self._make_combo(['BREEAM', 'LEED', 'DGNB', 'NABERS']))
            elif row == self.ROW_FIRE_RATING_CLASS:
                w = self._wrap_centered(QLineEdit())
            elif row in self._CHECKBOX_ROWS:
                checkbox = QCheckBox()
                checkbox.setProperty("row", row)
                w = self._wrap_centered(checkbox)
            else:
                w = self._wrap_centered(QCheckBox())
            self.codes_table.setCellWidget(row, col_position, w)

    @staticmethod
    def _checkbox_in_cell(cell_widget):
        if isinstance(cell_widget, QCheckBox):
            return cell_widget
        if isinstance(cell_widget, QWidget):
            for child in cell_widget.findChildren(QCheckBox):
                return child
        return None

    @staticmethod
    def _combo_in_cell(cell_widget):
        if isinstance(cell_widget, QComboBox):
            return cell_widget
        if isinstance(cell_widget, QWidget):
            for child in cell_widget.findChildren(QComboBox):
                return child
        return None

    @staticmethod
    def _lineedit_in_cell(cell_widget):
        if isinstance(cell_widget, QLineEdit):
            return cell_widget
        if isinstance(cell_widget, QWidget):
            for child in cell_widget.findChildren(QLineEdit):
                return child
        return None

    def _set_combo_value(self, cell_widget, value):
        combo = self._combo_in_cell(cell_widget)
        if combo is None:
            return
        text = str(value).strip()
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        if isinstance(value, bool):
            idx = 1 if value else 0
            if idx < combo.count():
                combo.setCurrentIndex(idx)

    def populate_from_input(self, compliance_data):
        for col, compliance_entry in enumerate(compliance_data, start=2):
            for row in range(self.codes_table.rowCount()):
                description = self.codes_table.item(row, 0).text()
                if description not in compliance_entry:
                    continue
                cell_widget = self.codes_table.cellWidget(row, col)
                value = compliance_entry[description]

                if row in self._COMBO_ROWS:
                    self._set_combo_value(cell_widget, value)
                elif row == self.ROW_FIRE_RATING_CLASS:
                    le = self._lineedit_in_cell(cell_widget)
                    if le is not None:
                        if isinstance(value, bool):
                            le.setText('')
                        else:
                            le.setText('' if value is None else str(value))
                else:
                    cb = self._checkbox_in_cell(cell_widget)
                    if cb is not None:
                        cb.setChecked(bool(value))

    def sync_compliance_to_user_inputs(self):
        """Write applicable codes table into ``user_inputs``."""
        compliance_data = []
        for col in range(2, self.codes_table.columnCount()):
            compliance_entry = {}
            for row in range(self.codes_table.rowCount()):
                description = self.codes_table.item(row, 0).text()
                cell_widget = self.codes_table.cellWidget(row, col)

                if row in self._COMBO_ROWS:
                    combo = self._combo_in_cell(cell_widget)
                    value = combo.currentText() if combo is not None else ''
                elif row == self.ROW_FIRE_RATING_CLASS:
                    le = self._lineedit_in_cell(cell_widget)
                    value = le.text() if le is not None else ''
                else:
                    cb = self._checkbox_in_cell(cell_widget)
                    value = cb.isChecked() if cb is not None else False

                compliance_entry[description] = value

            compliance_data.append(compliance_entry)

        self.user_inputs['Compliance'] = compliance_data

    def collect_data_and_go_next(self):
        self.sync_compliance_to_user_inputs()
        self.next_clicked.emit(self.user_inputs)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    desc = [
        'EN81-28 emergency call', 'EN81-70 Accessibility', 'DIN EN17210 / 18040-1 Accessibility',
        'EN81-71 Vandalism category', 'EN81-72 Firefighter elevator', 'EN81-73 Fire emergency return',
        'EN81-76 Emergency Evacuation type', 'EN81-76 Evacuation functions', 'EN81-77 Seismic category',
        'EN81-58 Fire rated landing doors', 'EN81-58 Fire rating class',
        'Green building certification compliance',
    ]
    user_inputs = {
        'BuildingSystems': [{'Number': '1'}, {'Number': '2'}],
        'Compliance': [
            {d: ('2' if 'Vandalism' in d else 'A' if 'Evacuation Class' in d else '1' if 'Seismic' in d else True)
             for d in desc},
            {d: ('0' if 'Vandalism' in d else 'B' if 'Evacuation Class' in d else '3' if 'Seismic' in d else False)
             for d in desc},
        ],
    }
    window = ApplicableCodesPage(user_inputs)
    window.show()
    sys.exit(app.exec_())
