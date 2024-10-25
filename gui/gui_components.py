import re
from PyQt5.QtWidgets import QWidget, QLabel, QLineEdit, QComboBox, QCheckBox, QHBoxLayout
from PyQt5.QtGui import QDoubleValidator

class GuiComponents:
    def add_combobox(self, layout, label, options):
        widget = QWidget()
        widget_layout = QHBoxLayout()
        input_box = QComboBox()
        input_box.addItems(options)
        widget_layout.addWidget(QLabel(label))
        widget_layout.addWidget(input_box)
        widget.setLayout(widget_layout)
        layout.addWidget(widget)
        attribute_name =  re.sub(r'_+', '_',label.replace(' ', '_').replace('/', '_').replace('-', '_').replace(',', '_').replace('(', '_').replace(')', '_').replace('≈', '_').lower() + '_input')
        setattr(self, attribute_name, input_box)

    def add_number_edit(self, layout, label, unit):
        widget = QWidget()
        widget_layout = QHBoxLayout()
        input_box = QLineEdit()
        input_box.setValidator(QDoubleValidator())
        widget_layout.addWidget(QLabel(label))
        widget_layout.addWidget(input_box)
        widget_layout.addWidget(QLabel(unit))
        widget.setLayout(widget_layout)
        layout.addWidget(widget)
        attribute_name =  re.sub(r'_+', '_',label.replace(' ', '_').replace('/', '_').replace('-', '_').replace(',', '_').replace('(', '_').replace(')', '_').replace('≈', '_').lower() + '_input')
        setattr(self, attribute_name, input_box)

    def add_checkbox(self, layout, label):
        widget = QWidget()
        widget_layout = QHBoxLayout()
        input_box = QCheckBox()
        widget_layout.addWidget(QLabel(label))
        widget_layout.addWidget(input_box)
        widget.setLayout(widget_layout)
        layout.addWidget(widget)
        attribute_name =  re.sub(r'_+', '_',label.replace(' ', '_').replace('/', '_').replace('-', '_').replace(',', '_').replace('(', '_').replace(')', '_').replace('≈', '_').lower() + '_input')
        setattr(self, attribute_name, input_box)

    def add_text_edit(self, layout, label):
        widget = QWidget()
        widget_layout = QHBoxLayout()
        input_box = QLineEdit()
        widget_layout.addWidget(QLabel(label))
        widget_layout.addWidget(input_box)
        widget.setLayout(widget_layout)
        layout.addWidget(widget)
        attribute_name =  re.sub(r'_+', '_',label.replace(' ', '_').replace('/', '_').replace('-', '_').replace(',', '_').replace('(', '_').replace(')', '_').replace('≈', '_').lower() + '_input')
        setattr(self, attribute_name, input_box)