from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, 
    QStackedWidget, QApplication, QLabel
)
from PyQt5.QtCore import Qt
import sys
import os
import json
from gui.building_system_page import BuildingSystemPage
from gui.lift_system_page import LiftSystemPage
from gui.lift_drive_control_page import LiftDriveControlPage
from gui.force_spec_page import ForceSpecPage
from gui.lift_compliance_page import LiftCompliancePage
from gui.lift_emergency_page import LiftEmergencyPage
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
            "2. Lift System Specifications",
            "3. Lift Drive and Control Specifications", 
            "4. Force Specifications",
            "5. Lift Compliance and Safety Standards",
            "6. Lift Emergency and Safety Systems",
            "7. Building Floor Levels"
        ])
        self.sidebar.currentRowChanged.connect(self.display_content)
        self.sidebar.setFixedWidth(300)  # Adjust the width of the sidebar here
        self.sidebar.setStyleSheet("background-color: rgb(196, 214, 0); color: white; font-weight: bold;")
        self.sidebar_layout.addWidget(self.sidebar)

        # Stack widget setup
        self.stack = QStackedWidget()
        self.page1 = BuildingSystemPage()
        self.page1.next_clicked.connect(self.go_to_lift_system_page)
        self.page2 = None
        self.page3 = None
        self.page4 = None
        self.page5 = None
        self.page6 = None
        self.page7 = None
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
        if is_existing_file:
            # For existing file, extract name from path without .json
            project_name = os.path.splitext(os.path.basename(path_or_name))[0]
            with open(path_or_name, 'r') as file:
                data = json.load(file)
            data['FileName'] = project_name
            self.page1 = BuildingSystemPage(data)
            # Remove old page and add new one to stack
            self.stack.removeWidget(self.stack.widget(0))
            self.stack.insertWidget(0, self.page1)
            # Reconnect the next_clicked signal
            self.page1.next_clicked.connect(self.go_to_lift_system_page)
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
            self.page1.next_clicked.connect(self.go_to_lift_system_page)

        # Set project name and adjust label width
        self.project_name_label.setText(project_name)
        self.project_name_label.setFixedWidth(self.sidebar.width())
        
        # Adjust label height based on content
        self.project_name_label.adjustSize()
        min_height = 40  # Minimum height for the label
        if self.project_name_label.height() < min_height:
            self.project_name_label.setFixedHeight(min_height)

    def json_to_dict(self,file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)
        return data

    def display_content(self, i):
        """
        Display the content based on the selected index.
        """
        if i == 6 and self.page7 is not None:
            self.stack.setCurrentIndex(6)
        else:
            self.stack.setCurrentIndex(i)

    def go_to_lift_system_page(self, data):
        """
        Go to the LiftSystemPage.
        """
        self.page2 = LiftSystemPage(data)
        self.page2.setMinimumWidth(900)
        self.page2.next_clicked.connect(self.go_to_lift_drive_control_page)
        self.stack.addWidget(self.page2)
        self.stack.setCurrentIndex(1)
        self.sidebar.setCurrentRow(1)

    def go_to_lift_drive_control_page(self, data):
        """
        Go to the LiftDriveControlPage.
        """
        self.page3 = LiftDriveControlPage(data)
        self.page3.next_clicked.connect(self.go_to_force_spec_page)
        self.stack.addWidget(self.page3)
        self.stack.setCurrentIndex(2)
        self.sidebar.setCurrentRow(2)

    def go_to_force_spec_page(self, data):
        """
        Go to the ForceSpecPage.
        """
        self.page4 = ForceSpecPage(data)
        self.page4.next_clicked.connect(self.go_to_lift_compliance_page)
        self.stack.addWidget(self.page4)
        self.stack.setCurrentIndex(3)
        self.sidebar.setCurrentRow(3)

    def go_to_lift_compliance_page(self, data):
        """
        Go to the LiftCompliancePage.
        """
        self.page5 = LiftCompliancePage(data)
        self.page5.next_clicked.connect(self.go_to_lift_emergency_page)
        self.stack.addWidget(self.page5)
        self.stack.setCurrentIndex(4)
        self.sidebar.setCurrentRow(4)

    def go_to_lift_emergency_page(self, data):
        """
        Go to the LiftEmergencyPage.
        """
        self.page6 = LiftEmergencyPage(data)
        self.page6.next_clicked.connect(self.go_to_building_floor_page)
        self.stack.addWidget(self.page6)
        self.stack.setCurrentIndex(5)
        self.sidebar.setCurrentRow(5)

    def go_to_building_floor_page(self, data):
        """
        Go to the BuildingFloorPage.
        """
        if self.page7 is None:
            self.page7 = BuildingFloorPage(data)
            self.page7.setMinimumWidth(1100)
            self.stack.addWidget(self.page7)
        self.stack.setCurrentIndex(6)
        self.sidebar.setCurrentRow(6)
        #self.page7.update_data(data)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
