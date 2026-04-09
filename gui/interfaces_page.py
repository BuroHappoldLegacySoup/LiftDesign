from PyQt5.QtWidgets import (
    QApplication, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QWidget, QVBoxLayout, QGroupBox, QPushButton, QScrollArea, QLineEdit,
)
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtCore import pyqtSignal, Qt
import sys


class InterfacesPage(QWidget):
    next_clicked = pyqtSignal(dict)

    _YES_NO_ITEMS = ('', 'yes', 'no')
    _POWER_TYPE_ITEMS = ('', 'UPS', 'Generator')

    # Row indices — must match ``input_descriptions`` in ``initUI``
    _ROW_COMBO_YES_NO = frozenset(
        {2, 5, 6, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18}
    )
    _ROW_COMBO_POWER_TYPE = frozenset({7})
    _ROW_LINE_EDIT = frozenset({0, 1, 3, 4, 10, 19, 20})
    _ROW_LINE_EDIT_NUMERIC = frozenset({3, 4})

    # Older project keys → current description (first match wins in populate)
    _POPULATE_ALIASES = {
        'other Security interfaces as per spec. (y/n)': (
            'other Security interfaces as per spec (y/n)',
        ),
    }

    def __init__(self, user_inputs):
        super().__init__()
        self.user_inputs = user_inputs
        self.number_of_lifts = len(user_inputs['BuildingSystems'])
        self.initUI()

        if 'Emergency' in self.user_inputs:
            self.populate_from_input(self.user_inputs['Emergency'])

    @staticmethod
    def _choice_combo(items: tuple[str, ...]) -> QComboBox:
        w = QComboBox()
        w.setEditable(False)
        w.setInsertPolicy(QComboBox.NoInsert)
        w.setStyleSheet("QComboBox { combobox-popup: 0; }")
        for t in items:
            w.addItem(t)
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

        interfaces_box = QGroupBox("Technical Interfaces")
        interfaces_box.setObjectName("interfaces_box")
        interfaces_box.setStyleSheet(
            "#interfaces_box {background-color: white; border: 3px solid rgb(196, 214, 0); font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        scroll_layout.addWidget(interfaces_box)

        interfaces_layout = QVBoxLayout(interfaces_box)

        self.interfaces_table = QTableWidget()
        self.interfaces_table.setColumnCount(1)
        self.interfaces_table.setHorizontalHeaderLabels(['Description'])

        self._input_descriptions = [
            'Smoke management type (type)', 'Smoke extraction min. size netto (mm²)', 'FAS interfaces as per spec (y/n)',
            'Main evacuation floor fire return and EEL EN81-76 (floor no.)', 'Alternate evacuation floor (floor no.)',
            'Emergency power (y/n)', 'Cascading evacuation control (y/n)', 'Type of emergency power (type)',
            'FCC panel interface as per spec (y/n)', '2-way intercom firefighter lift (y/n)',
            'self-rescue method firefighter lift (type)', 'BMS interfaces as per spec (y/n)', 'lift monitoring (y/n)',
            'ICT/AV interfaces as per spec (y/n)', 'In-car CCTV', 'Access Control interface as per spec (y/n)',
            'other Security interfaces as per spec. (y/n)', 'PAVA alarm interface car (y/n)', 'Sprinkler in shaft / Shunt trip (y/n)',
            'Water management Firefighter and Evacuation lift (type)', 'other functions (type)',
        ]

        self.interfaces_table.setRowCount(len(self._input_descriptions))

        for row, description in enumerate(self._input_descriptions):
            item = QTableWidgetItem(description)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.interfaces_table.setItem(row, 0, item)

        self.interfaces_table.horizontalHeader().setStretchLastSection(True)
        self.interfaces_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.interfaces_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)

        interfaces_layout.addWidget(self.interfaces_table)

        save_button = QPushButton('Save and Proceed')
        save_button.setStyleSheet("background-color: white;")
        save_button.clicked.connect(self.collect_data_and_go_next)
        scroll_layout.addWidget(save_button)

        self.initialize_lift_columns()

    def initialize_lift_columns(self):
        for _ in range(self.number_of_lifts):
            self.add_lift_column()

    def add_lift_column(self):
        col_position = self.interfaces_table.columnCount()
        self.interfaces_table.insertColumn(col_position)
        self.interfaces_table.setHorizontalHeaderItem(col_position, QTableWidgetItem(f'Lift {col_position}'))

        for row in range(self.interfaces_table.rowCount()):
            if row in self._ROW_COMBO_YES_NO:
                w = self._choice_combo(self._YES_NO_ITEMS)
            elif row in self._ROW_COMBO_POWER_TYPE:
                w = self._choice_combo(self._POWER_TYPE_ITEMS)
            elif row in self._ROW_LINE_EDIT:
                w = QLineEdit()
                if row in self._ROW_LINE_EDIT_NUMERIC:
                    w.setValidator(QDoubleValidator())
            else:
                w = QLineEdit()
            self.interfaces_table.setCellWidget(row, col_position, w)

    @staticmethod
    def _combo_in_cell(cell_widget):
        if isinstance(cell_widget, QComboBox):
            return cell_widget
        return None

    def _value_for_description(self, emergency_entry: dict, description: str):
        if description in emergency_entry:
            return emergency_entry[description]
        for canon, aliases in self._POPULATE_ALIASES.items():
            if description == canon:
                for a in aliases:
                    if a in emergency_entry:
                        return emergency_entry[a]
        return None

    @staticmethod
    def _set_yes_no_combo(combo: QComboBox, value) -> None:
        if isinstance(value, bool):
            text = 'yes' if value else 'no'
        else:
            text = str(value).strip() if value is not None else ''
        if not text:
            combo.setCurrentIndex(0)
            return
        idx = combo.findText(text)
        if idx < 0:
            low = text.lower()
            if low in ('yes', 'no'):
                idx = combo.findText(low)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    @staticmethod
    def _set_power_type_combo(combo: QComboBox, value) -> None:
        text = str(value).strip() if value is not None else ''
        if not text:
            combo.setCurrentIndex(0)
            return
        idx = combo.findText(text)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        # Legacy: single-option combo or other labels
        low = text.lower()
        if 'ups' in low:
            i = combo.findText('UPS')
            if i >= 0:
                combo.setCurrentIndex(i)
        elif 'generat' in low or text == 'Generator':
            i = combo.findText('Generator')
            if i >= 0:
                combo.setCurrentIndex(i)

    def populate_from_input(self, emergency_data):
        for col, emergency_entry in enumerate(emergency_data, start=1):
            for row in range(self.interfaces_table.rowCount()):
                description = self.interfaces_table.item(row, 0).text()
                value = self._value_for_description(emergency_entry, description)
                if value is None:
                    continue
                cell_widget = self.interfaces_table.cellWidget(row, col)

                if row in self._ROW_COMBO_YES_NO:
                    cb = self._combo_in_cell(cell_widget)
                    if cb is not None:
                        self._set_yes_no_combo(cb, value)
                elif row in self._ROW_COMBO_POWER_TYPE:
                    cb = self._combo_in_cell(cell_widget)
                    if cb is not None:
                        self._set_power_type_combo(cb, value)
                elif isinstance(cell_widget, QLineEdit):
                    cell_widget.setText(str(value))

    def collect_data_and_go_next(self):
        emergency_data = []
        for col in range(1, self.interfaces_table.columnCount()):
            emergency_entry = {}
            for row in range(self.interfaces_table.rowCount()):
                description = self.interfaces_table.item(row, 0).text()
                cell_widget = self.interfaces_table.cellWidget(row, col)

                if row in self._ROW_COMBO_YES_NO or row in self._ROW_COMBO_POWER_TYPE:
                    cb = self._combo_in_cell(cell_widget)
                    value = cb.currentText() if cb is not None else ''
                elif isinstance(cell_widget, QLineEdit):
                    value = cell_widget.text()
                else:
                    value = ''

                emergency_entry[description] = value

            emergency_data.append(emergency_entry)

        self.user_inputs['Emergency'] = emergency_data
        self.next_clicked.emit(self.user_inputs)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    user_inputs = {
        'BuildingSystems': [{'Number': '1'}, {'Number': '2'}],
        'Emergency': [],
    }
    window = InterfacesPage(user_inputs)
    window.show()
    sys.exit(app.exec_())
