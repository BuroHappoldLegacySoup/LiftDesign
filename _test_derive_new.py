"""Ensure the fix didn't break auto-derivation for NEW lifts with no saved LayoutInformation."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication, QLineEdit
app = QApplication.instance() or QApplication(sys.argv)

from gui.layout_information_page import LayoutInformationPage

ui = {
    "BuildingSystems": [{"Number": "1"}],
    "GeneralSpecification": [{"Load capacity": "2000", "Counterweight location": "CWT-Right"}],
    "LayoutInformation": [{}],
}

page = LayoutInformationPage(ui)
col = 2
cw = page.layout_table.cellWidget(page.ROW_CABIN_WIDTH, col).text()
cd = page.layout_table.cellWidget(page.ROW_CABIN_DEPTH, col).text()
print(f"New lift, load=2000, auto-derived Cabin width={cw!r}  Cabin depth={cd!r}")
assert cw == '1500', f"Expected 1500, got {cw!r}"
assert cd == '2700', f"Expected 2700, got {cd!r}"
print("PASS: derivation still fires when saved data is blank.")
