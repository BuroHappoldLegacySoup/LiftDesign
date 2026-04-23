"""Reproduce: Saved LayoutInformation cabin width/depth get overwritten by formula."""
import sys, io, os, copy
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication, QLineEdit, QComboBox
app = QApplication.instance() or QApplication(sys.argv)

from gui.layout_information_page import LayoutInformationPage

ui = {
    "BuildingSystems": [{"Number": "1"}, {"Number": ""}, {"Number": "1"}],
    "GeneralSpecification": [
        {"Load capacity": "630",  "Counterweight location": "CWT-Left"},
        {"Load capacity": "630",  "Counterweight location": "CWT-Left"},
        {"Load capacity": "2000", "Counterweight location": "CWT-Right"},
    ],
    "LayoutInformation": [
        {"Cabin type/shape": "Deep", "Cabin width": "1100", "Cabin depth": "1400",
         "Clear cabin height": "2200", "Door width": "900", "Door height": "2100",
         "Shaft width suggested": "1750", "Shaft depth suggested": "1800"},
        {"Cabin type/shape": "Deep", "Cabin width": "1100", "Cabin depth": "1400",
         "Clear cabin height": "2200", "Door width": "900", "Door height": "2100",
         "Shaft width suggested": "1750", "Shaft depth suggested": "1800"},
        {"Cabin type/shape": "Deep", "Cabin width": "1500", "Cabin depth": "2700",
         "Clear cabin height": "2300", "Door width": "1300", "Door height": "2200",
         "Shaft width suggested": "2420", "Shaft depth suggested": "3160"},
    ],
}

original = copy.deepcopy(ui["LayoutInformation"])
page = LayoutInformationPage(ui)

checks = [("Cabin width", page.ROW_CABIN_WIDTH),
          ("Cabin depth", page.ROW_CABIN_DEPTH),
          ("Clear cabin height", page.ROW_CLEAR_CABIN_HEIGHT),
          ("Door width", page.ROW_DOOR_WIDTH),
          ("Door height", page.ROW_DOOR_HEIGHT),
          ("Shaft width suggested", page.ROW_SHAFT_WIDTH_SUGG),
          ("Shaft depth suggested", page.ROW_SHAFT_DEPTH_SUGG)]

fail = False
for col in range(2, page.layout_table.columnCount()):
    lift = col - 2
    print(f"--- Lift {lift+1} ---")
    for label, row in checks:
        w = page.layout_table.cellWidget(row, col)
        shown = w.text() if isinstance(w, QLineEdit) else (w.currentText() if isinstance(w, QComboBox) else "")
        saved = original[lift].get(label, "<missing>")
        ok = str(shown).strip() == str(saved).strip()
        mark = "OK  " if ok else "FAIL"
        print(f"  {mark} {label:<30s} saved={saved!r:<10} shown={shown!r}")
        if not ok:
            fail = True

print("\n" + ("OVERALL FAIL" if fail else "OVERALL PASS"))
