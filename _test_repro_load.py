"""Reproduce: saved GeneralSpecification values are not shown when the UI reopens."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication, QLineEdit, QComboBox

app = QApplication.instance() or QApplication(sys.argv)

from gui.general_specification_page import GeneralSpecificationPage, GENERAL_SPEC_ROWS

# This replicates the user's JSON (trimmed to just the sections relevant to the gen-spec page).
ui = {
    "FileName": "Project 3",
    "BuildingSystems": [
        {"Number": "1", "Functions": "BS EN81"},
        {"Number": "", "Functions": "BS EN81"},
        {"Number": "1", "System Name": "mom", "Functions": "BS EN81"},
    ],
    "GeneralSpecification": [
        {
            "System Type": "Passenger Lift", "System Category": "Traction - MR",
            "Code Basis": "BS EN81", "Control / Group": "Simplex",
            "Counterweight location": "CWT-Left", "Load capacity": "630",
            "Permissible number of persons": "17", "Speed": "1,00",
            "Acceleration": "", "Jerk": "", "Travel height": "",
            "Stops": "2", "Number of floors": "3", "Number of shaft doors": "",
            "Access type": "Front", "Accessible rooms/cwt safety": "yes",
        },
        {
            "System Type": "Passenger Lift", "System Category": "Traction - MR",
            "Code Basis": "BS EN81", "Control / Group": "Simplex",
            "Counterweight location": "CWT-Left", "Load capacity": "630",
            "Permissible number of persons": "17", "Speed": "1,00",
            "Acceleration": "", "Jerk": "", "Travel height": "",
            "Stops": "", "Number of floors": "3", "Number of shaft doors": "",
            "Access type": "Front", "Accessible rooms/cwt safety": "yes",
        },
        {
            "System Type": "Passenger Lift", "System Category": "Traction - MR",
            "Code Basis": "BS EN81", "Control / Group": "Simplex",
            "Counterweight location": "CWT-Right", "Load capacity": "2000",
            "Permissible number of persons": "47", "Speed": "1,00",
            "Acceleration": "2", "Jerk": "2", "Travel height": "2",
            "Stops": "2", "Number of floors": "6", "Number of shaft doors": "2",
            "Access type": "Front", "Accessible rooms/cwt safety": "yes",
        },
    ],
    "LayoutInformation": [{}, {}, {}],
}

import copy as _copy
original = _copy.deepcopy(ui["GeneralSpecification"])
page = GeneralSpecificationPage(ui)

print(f"number_of_lifts = {page.number_of_lifts}")
print(f"table columns = {page.system_table.columnCount()} (first data col = 2)")
print()

# What does each cell widget display, per lift?
for col in range(2, page.system_table.columnCount()):
    lift_idx = col - 2
    print(f"--- Lift {lift_idx + 1}  (col={col}) ---")
    for row, (jk, _label, _unit) in enumerate(GENERAL_SPEC_ROWS):
        w = page.system_table.cellWidget(row, col)
        if isinstance(w, QLineEdit):
            shown = w.text()
        elif isinstance(w, QComboBox):
            shown = w.currentText()
        else:
            shown = "<no widget>"
        saved = original[lift_idx].get(jk, "<missing>")
        ok = str(shown).strip() == str(saved).strip() or (saved == "" and shown == "")
        mark = "OK  " if ok else "FAIL"
        print(f"  {mark} {jk:<32s}  saved={saved!r:<20}  shown={shown!r}")
