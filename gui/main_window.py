from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, 
    QStackedWidget, QApplication, QLabel, QPushButton
)
from PyQt5.QtCore import Qt
import sys
import os
import json
from gui.change_history_dialog import ChangeHistoryDialog
from gui.project_json import load_project_json
from gui.change_tracker import prepare_baseline
from gui.building_system_page import BuildingSystemPage
from gui.general_specification_page import GeneralSpecificationPage
from gui.layout_information_page import LayoutInformationPage
from gui.Elecrical_HVAC import LiftDriveControlPage
from gui.Mechanical_Loading import ForceSpecPage
from gui.applicable_codes_page import ApplicableCodesPage
from gui.interfaces_page import InterfacesPage
from gui.cost_page import CostPage
from gui.building_floor_page import BuildingFloorPage


class MainWindow(QMainWindow):
    """
    MainWindow class that sets up the GUI.
    """
    def __init__(self):
        """
        Initialize the MainWindow.
        """
        super().__init__()
        self.setWindowTitle("Lift Design Toolbox_v0")
        self.project_file_path = None
        self.projects_base_path = os.path.join(os.path.expanduser('~'), 'LiftDesigner', 'Projects')
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout()
        self.central_widget.setLayout(self.layout)

        # Create a vertical layout for sidebar and project name
        self.sidebar_container = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar_container)
        self.sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar_layout.setSpacing(0)

        # Add project name label
        self.project_name_label = QLabel()
        self.project_name_label.setAlignment(Qt.AlignCenter)
        self.project_name_label.setStyleSheet("""
            QLabel {
                background-color: rgb(196, 214, 0);
                color: white;
                font-weight: bold;
                padding: 10px;
                border-bottom: 1px solid white;
            }
        """)
        self.sidebar_layout.addWidget(self.project_name_label)

        # Create and set up sidebar
        self.sidebar = QListWidget()
        self.sidebar.addItems([
            "1. Building System Information",
            "2. General specification",
            "3. Layout Information",
            "4. Electrical & HVAC",
            "5. Mechanical loading",
            "6. Applicable codes",
            "7. Technical Interfaces",
            "8. Building Floor Levels",
            "9. Cost",
        ])
        self.sidebar.currentRowChanged.connect(self.display_content)
        self.sidebar.setFixedWidth(300)  # Adjust the width of the sidebar here
        self.sidebar.setStyleSheet("background-color: rgb(196, 214, 0); color: white; font-weight: bold;")
        self.sidebar_layout.addWidget(self.sidebar)

        # Change History button
        self.change_history_btn = QPushButton("Change History")
        self.change_history_btn.setStyleSheet(
            "background-color: white; border: 3px solid rgb(196, 214, 0); "
            "font-weight: bold; padding: 8px;"
        )
        self.change_history_btn.clicked.connect(self.show_change_history)
        self.sidebar_layout.addWidget(self.change_history_btn)

        # Stack widget setup
        self.stack = QStackedWidget()
        self.page1 = BuildingSystemPage()
        self.page1.next_clicked.connect(self.go_to_general_specification_page)
        self.page2 = None
        self.page3 = None
        self.page4 = None
        self.page5 = None
        self.page6 = None
        self.page7 = None
        self.page8 = None
        self.page_cost = None
        self.stack.addWidget(self.page1)

        # Add widgets to main layout
        self.layout.addWidget(self.sidebar_container)
        self.layout.addWidget(self.stack)
        self.layout.setStretch(0, 1)  # Ensure sidebar takes up appropriate space
        self.layout.setStretch(1, 5)  # Ensure stack takes up the remaining space
        self.setStyleSheet("background-color: white;")

    def load_project(self, path_or_name: str, is_existing_file: bool):
        """
        Load project and display project name
        """
        while self.stack.count() > 1:
            w = self.stack.widget(self.stack.count() - 1)
            self.stack.removeWidget(w)
            w.deleteLater()
        self.page2 = None
        self.page3 = None
        self.page4 = None
        self.page5 = None
        self.page6 = None
        self.page7 = None
        self.page8 = None
        self.page_cost = None

        if is_existing_file:
            # For existing file, extract name from path without .json
            project_name = os.path.splitext(os.path.basename(path_or_name))[0]
            data = load_project_json(path_or_name)
            data['FileName'] = project_name
            data['_baseline'] = prepare_baseline(data)  # For change tracking
            self.page1 = BuildingSystemPage(data)
            # Remove old page and add new one to stack
            self.stack.removeWidget(self.stack.widget(0))
            self.stack.insertWidget(0, self.page1)
            # Reconnect the next_clicked signal
            self.page1.next_clicked.connect(self.go_to_general_specification_page)
        else:
            # For new file, remove .json if present
            project_name = os.path.splitext(path_or_name)[0]
            data = {}
            data['FileName'] = project_name
            self.page1 = BuildingSystemPage(data)
            # Remove old page and add new one to stack
            self.stack.removeWidget(self.stack.widget(0))
            self.stack.insertWidget(0, self.page1)
            # Reconnect the next_clicked signal
            self.page1.next_clicked.connect(self.go_to_general_specification_page)

        # Set project name and adjust label width
        self.project_name_label.setText(project_name)
        self.project_name_label.setFixedWidth(self.sidebar.width())

        # Store project file path for change tracking
        if is_existing_file:
            self.project_file_path = path_or_name
        else:
            file_name = path_or_name if path_or_name.endswith('.json') else path_or_name + '.json'
            self.project_file_path = os.path.join(self.projects_base_path, file_name)
        
        # Adjust label height based on content
        self.project_name_label.adjustSize()
        min_height = 40  # Minimum height for the label
        if self.project_name_label.height() < min_height:
            self.project_name_label.setFixedHeight(min_height)

    def json_to_dict(self, file_path):
        return load_project_json(file_path)

    def _truncate_wizard_stack_to_count(self, target_count: int) -> None:
        """Drop wizard pages after ``target_count`` so forward navigation can rebuild without duplicates.

        ``QStackedWidget.addWidget`` appends; going back then Save again used to leave old pages at
        indices 0..n while new pages were appended at the end, so ``setCurrentIndex`` showed stale UI
        and blocked progressing past the step you returned from.
        """
        while self.stack.count() > target_count:
            w = self.stack.widget(self.stack.count() - 1)
            self.stack.removeWidget(w)
            if w is self.page2:
                continue
            w.deleteLater()
        for attr in ('page3', 'page4', 'page5', 'page6', 'page7', 'page8', 'page_cost'):
            p = getattr(self, attr, None)
            if p is not None and self.stack.indexOf(p) < 0:
                setattr(self, attr, None)

    def _bind_wizard_pages_to_project_root(self):
        """Point every wizard page at ``page1.user_inputs`` so sync writes the dict we save to JSON.

        Always reassign (not only when ``is not root``): a page can otherwise keep a stale dict
        reference if anything desynchronised, and then only Building system (page1) would persist on save.
        """
        if self.page1 is None:
            return
        root = self.page1.user_inputs
        for attr in (
            'page2', 'page3', 'page4', 'page5', 'page6', 'page7', 'page8', 'page_cost',
        ):
            page = getattr(self, attr, None)
            if page is not None:
                page.user_inputs = root

    def _flush_project_data_from_pages_before_save(self):
        """Copy all wizard tables into the shared project dict before writing JSON."""
        fw = QApplication.focusWidget()
        if fw is not None:
            fw.clearFocus()
        QApplication.processEvents()

        self._bind_wizard_pages_to_project_root()
        if self.page1 is not None:
            self.page1.sync_to_user_inputs()
        if self.page2 is not None:
            self.page2._sync_lift_systems_to_user_inputs()
        if self.page3 is not None:
            self.page3.merge_layout_into_lift_systems()
        if self.page4 is not None:
            self.page4.sync_lift_drive_to_user_inputs()
        if self.page5 is not None:
            self.page5.sync_forces_to_user_inputs()
        if self.page6 is not None:
            self.page6.sync_compliance_to_user_inputs()
        if self.page7 is not None:
            self.page7.sync_emergency_to_user_inputs()
        if self.page8 is not None:
            self.page8.sync_floors_to_user_inputs()
        if self.page_cost is not None:
            self.page_cost.sync_cost_to_user_inputs()

    def _sync_wizard_page_at_stack_index(self, idx: int) -> None:
        """Persist one wizard page’s widgets into the shared ``user_inputs`` (same rules as pre-save flush)."""
        self._bind_wizard_pages_to_project_root()
        if idx == 0 and self.page1 is not None:
            self.page1.sync_to_user_inputs()
        elif idx == 1 and self.page2 is not None:
            self.page2._sync_lift_systems_to_user_inputs()
        elif idx == 2 and self.page3 is not None:
            self.page3.merge_layout_into_lift_systems()
        elif idx == 3 and self.page4 is not None:
            self.page4.sync_lift_drive_to_user_inputs()
        elif idx == 4 and self.page5 is not None:
            self.page5.sync_forces_to_user_inputs()
        elif idx == 5 and self.page6 is not None:
            self.page6.sync_compliance_to_user_inputs()
        elif idx == 6 and self.page7 is not None:
            self.page7.sync_emergency_to_user_inputs()
        elif idx == 7 and self.page8 is not None:
            self.page8.sync_floors_to_user_inputs()
        elif idx == 8 and self.page_cost is not None:
            self.page_cost.sync_cost_to_user_inputs()

    def display_content(self, i):
        """
        Display the content based on the selected index.
        """
        if i < 0 or i >= self.stack.count():
            return
        prev = self.stack.currentIndex()
        if prev >= 0 and prev != i:
            self._sync_wizard_page_at_stack_index(prev)
        if i == 1 and self.page2 is not None:
            self._bind_wizard_pages_to_project_root()
            self.page2.refresh_from_project_data()
        if i == 7 and self.page8 is not None:
            self._bind_wizard_pages_to_project_root()
            self.page8.refresh_from_project_data()
        if i == 8 and self.page_cost is not None:
            self.page_cost._main_window = self
        self.stack.setCurrentIndex(i)

    def go_to_general_specification_page(self, data):
        """Go to General specification page.

        Reuse a single ``page2`` instance. Truncate the stack to Building System only before
        re-attaching general spec so back-then-forward does not leave duplicate pages.
        """
        self._truncate_wizard_stack_to_count(1)
        if self.page2 is None:
            self.page2 = GeneralSpecificationPage(data)
            self.page2.setMinimumWidth(900)
            self.page2.next_clicked.connect(self.go_to_layout_information_page)
            self.page2.back_clicked.connect(self.go_back_one_wizard_step)
        else:
            self.page2.user_inputs = data
            self.page2.refresh_from_project_data()
        if self.stack.indexOf(self.page2) != 1:
            if self.stack.indexOf(self.page2) >= 0:
                self.stack.removeWidget(self.page2)
            self.stack.insertWidget(1, self.page2)
        self.stack.setCurrentIndex(1)
        self.sidebar.setCurrentRow(1)

    def go_to_layout_information_page(self, data):
        """Go to Layout Information page."""
        self._truncate_wizard_stack_to_count(2)
        self.page3 = LayoutInformationPage(data)
        self.page3.setMinimumWidth(900)
        self.page3.next_clicked.connect(self.go_to_lift_drive_control_page)
        self.page3.back_clicked.connect(self.go_back_one_wizard_step)
        self.stack.addWidget(self.page3)
        self.stack.setCurrentIndex(2)
        self.sidebar.setCurrentRow(2)

    def go_to_lift_drive_control_page(self, data):
        """Go to Electrical & HVAC (``LiftDriveControlPage``)."""
        self._truncate_wizard_stack_to_count(3)
        self.page4 = LiftDriveControlPage(data)
        self.page4.next_clicked.connect(self.go_to_force_spec_page)
        self.page4.back_clicked.connect(self.go_back_one_wizard_step)
        self.stack.addWidget(self.page4)
        self.stack.setCurrentIndex(3)
        self.sidebar.setCurrentRow(3)

    def go_to_force_spec_page(self, data):
        """
        Go to the ForceSpecPage.
        """
        self._truncate_wizard_stack_to_count(4)
        self.page5 = ForceSpecPage(data)
        self.page5.next_clicked.connect(self.go_to_applicable_codes_page)
        self.page5.back_clicked.connect(self.go_back_one_wizard_step)
        self.stack.addWidget(self.page5)
        self.stack.setCurrentIndex(4)
        self.sidebar.setCurrentRow(4)

    def go_to_applicable_codes_page(self, data):
        """
        Go to the Applicable codes page (``ApplicableCodesPage``).
        """
        self._truncate_wizard_stack_to_count(5)
        self.page6 = ApplicableCodesPage(data)
        self.page6.next_clicked.connect(self.go_to_interfaces_page)
        self.page6.back_clicked.connect(self.go_back_one_wizard_step)
        self.stack.addWidget(self.page6)
        self.stack.setCurrentIndex(5)
        self.sidebar.setCurrentRow(5)

    def go_to_interfaces_page(self, data):
        """
        Go to the Technical Interfaces page (``InterfacesPage``).
        """
        self._truncate_wizard_stack_to_count(6)
        self.page7 = InterfacesPage(data)
        self.page7.next_clicked.connect(self.go_to_building_floor_page)
        self.page7.back_clicked.connect(self.go_back_one_wizard_step)
        self.stack.addWidget(self.page7)
        self.stack.setCurrentIndex(6)
        self.sidebar.setCurrentRow(6)

    def go_to_building_floor_page(self, data):
        """
        Go to the BuildingFloorPage.
        """
        self._truncate_wizard_stack_to_count(7)
        if self.page8 is None:
            self.page8 = BuildingFloorPage(data)
            self.page8.setMinimumWidth(1100)
            self.page8.next_clicked.connect(self.go_to_cost_page)
            self.page8.back_clicked.connect(self.go_back_one_wizard_step)
        else:
            self.page8.user_inputs = data
            self.page8.refresh_from_project_data()
        if self.stack.indexOf(self.page8) < 0:
            self.stack.addWidget(self.page8)
        self.stack.setCurrentIndex(7)
        self.sidebar.setCurrentRow(7)

    def go_to_cost_page(self, data):
        """Cost is the last page; JSON is written here (not on Building Floor)."""
        self._truncate_wizard_stack_to_count(8)
        if self.page_cost is None:
            self.page_cost = CostPage(data, main_window=self)
            self.page_cost.setMinimumWidth(900)
            self.page_cost.file_saved.connect(self._on_project_saved)
            self.page_cost.back_clicked.connect(self.go_back_one_wizard_step)
        else:
            self.page_cost.sync_user_inputs(data)
        self.page_cost._main_window = self
        if self.stack.indexOf(self.page_cost) < 0:
            self.stack.addWidget(self.page_cost)
        self.stack.setCurrentIndex(8)
        self.sidebar.setCurrentRow(8)

    def _on_project_saved(self, file_path: str):
        """Update project file path when project is saved (e.g. new project with generated name)."""
        self.project_file_path = file_path

    def show_change_history(self):
        """Open the Change History dialog showing alterations to the loaded file."""
        change_history = []
        project_name = self.project_name_label.text() or ""

        if self.project_file_path and os.path.exists(self.project_file_path):
            try:
                data = load_project_json(self.project_file_path)
                change_history = data.get('ChangeHistory', [])
            except (json.JSONDecodeError, IOError):
                pass

        dialog = ChangeHistoryDialog(change_history, project_name, self)
        dialog.exec_()

    def go_back_one_wizard_step(self):
        """Return to the previous wizard page; current page is flushed to ``user_inputs`` like sidebar navigation."""
        cur = self.stack.currentIndex()
        if cur <= 0:
            return
        target = cur - 1
        self.display_content(target)
        self.sidebar.blockSignals(True)
        self.sidebar.setCurrentRow(target)
        self.sidebar.blockSignals(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
