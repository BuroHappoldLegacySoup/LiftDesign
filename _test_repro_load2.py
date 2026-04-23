"""Instrumented repro: print values flowing into populate_from_input."""
import sys, io, os, copy
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication, QLineEdit, QComboBox
app = QApplication.instance() or QApplication(sys.argv)

import gui.general_specification_page as gsp

# Monkey-patch populate_from_input to print what it's being handed.
orig_populate = gsp.GeneralSpecificationPage.populate_from_input
def traced(self, systems_data):
    print("populate_from_input called with:")
    for i, s in enumerate(systems_data):
        keys_of_interest = ("Load capacity", "Counterweight location", "Stops",
                            "Permissible number of persons", "Acceleration")
        subset = {k: s.get(k, "<missing>") for k in keys_of_interest}
        print(f"  lift[{i}] = {subset}")
    print()
    orig_populate(self, systems_data)
gsp.GeneralSpecificationPage.populate_from_input = traced

orig_merge = gsp.GeneralSpecificationPage._apply_general_spec_widgets_to_lift_systems_merge
def traced_merge(self, systems):
    print("Before merge, systems[2] =", {k: systems[2].get(k, "<missing>") for k in
        ("Load capacity", "Counterweight location", "Stops")})
    orig_merge(self, systems)
    print("After merge, systems[2] =", {k: systems[2].get(k, "<missing>") for k in
        ("Load capacity", "Counterweight location", "Stops")})
gsp.GeneralSpecificationPage._apply_general_spec_widgets_to_lift_systems_merge = traced_merge

ui = {
    "BuildingSystems": [{"Number": "1"}, {"Number": ""}, {"Number": "1"}],
    "GeneralSpecification": [
        {"System Type": "Passenger Lift", "Load capacity": "630", "Counterweight location": "CWT-Left",
         "Stops": "2", "Permissible number of persons": "17", "Acceleration": ""},
        {"System Type": "Passenger Lift", "Load capacity": "630", "Counterweight location": "CWT-Left",
         "Stops": "", "Permissible number of persons": "17", "Acceleration": ""},
        {"System Type": "Passenger Lift", "Load capacity": "2000", "Counterweight location": "CWT-Right",
         "Stops": "2", "Permissible number of persons": "47", "Acceleration": "2"},
    ],
    "LayoutInformation": [{}, {}, {}],
}

page = gsp.GeneralSpecificationPage(ui)

for col in range(2, page.system_table.columnCount()):
    lift = col - 2
    load_w = page.system_table.cellWidget(5, col)
    cwt_w  = page.system_table.cellWidget(4, col)
    persons_w = page.system_table.cellWidget(6, col)
    print(f"Lift {lift+1}: Load={load_w.currentText()!r}, CWT={cwt_w.currentText()!r}, persons={persons_w.text()!r}")
