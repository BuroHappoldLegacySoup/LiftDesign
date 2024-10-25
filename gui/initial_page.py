# initial_page.py
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QInputDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
import sys
import os
from datetime import datetime
if __name__ != '__main__':
    from gui.gui_components import GuiComponents
else:
    from gui_components import GuiComponents

class InitialPage(QWidget, GuiComponents):
    # Define signals for project selection
    project_selected = pyqtSignal(str, bool)  # str: path/name, bool: is_existing_file

    def __init__(self):
        super().__init__()
        # Define the folder path for recent files
        self.recent_files_path = os.path.join(os.path.expanduser('~'), 'LiftDesigner', 'Projects')
        # Create directory if it doesn't exist
        os.makedirs(self.recent_files_path, exist_ok=True)
        self.selected_file = None
        self.initUI()
        self.load_recent_files()

    def initUI(self):
        self.setMinimumSize(800, 600)
        self.setWindowTitle("Lift Designer")
        layout = QVBoxLayout(self)

        # Recent Files Group
        recent_files_group = QGroupBox("Recent Files")
        recent_files_group.setObjectName("recent_files_group")
        recent_files_group.setStyleSheet(
            "#recent_files_group {background-color: white; border: 3px solid rgb(196, 214, 0); "
            "font-size: 15px; font-weight: bold; border-radius: 6px; margin-top: 12px;} "
            "QGroupBox::title {subcontrol-origin: margin; left: 3px; padding: 0px 0px 5px 0px;}"
        )
        recent_files_layout = QVBoxLayout(recent_files_group)

        # Create table for recent files
        self.files_table = QTableWidget()
        self.files_table.setColumnCount(3)
        self.files_table.setHorizontalHeaderLabels(['Project Name', 'Created', 'Modified'])
        self.files_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.files_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.files_table.setSelectionMode(QTableWidget.SingleSelection)
        self.files_table.setEditTriggers(QTableWidget.NoEditTriggers)
        recent_files_layout.addWidget(self.files_table)

        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        # Create New Button
        create_new_btn = QPushButton('Create New')
        create_new_btn.setStyleSheet("background-color: white;")
        create_new_btn.clicked.connect(self.create_new_file)
        
        # Open File Button
        open_file_btn = QPushButton('Open File')
        open_file_btn.setStyleSheet("background-color: white;")
        open_file_btn.clicked.connect(self.open_file)

        # Add buttons to layout
        buttons_layout.addStretch()
        buttons_layout.addWidget(create_new_btn)
        buttons_layout.addWidget(open_file_btn)

        # Add all layouts to main layout
        layout.addWidget(recent_files_group)
        layout.addLayout(buttons_layout)

    def load_recent_files(self):
        """Load and display recent files from the specified directory"""
        self.files_table.setRowCount(0)
        
        # Get all JSON files in the directory
        json_files = [f for f in os.listdir(self.recent_files_path) if f.endswith('.json')]
        
        # Create a list of tuples containing file info and modified time for sorting
        file_info = []
        for file in json_files:
            file_path = os.path.join(self.recent_files_path, file)
            created = datetime.fromtimestamp(os.path.getctime(file_path))
            modified = datetime.fromtimestamp(os.path.getmtime(file_path))
            file_info.append((file, file_path, created, modified))
        
        # Sort files by modified date (newest first)
        file_info.sort(key=lambda x: x[3], reverse=True)
        
        # Add sorted files to table
        for file, file_path, created, modified in file_info:
            row_position = self.files_table.rowCount()
            self.files_table.insertRow(row_position)
            
            # Set items
            project_name = QTableWidgetItem(file.replace('.json', ''))
            created_date = QTableWidgetItem(created.strftime('%Y-%m-%d %H:%M:%S'))
            modified_date = QTableWidgetItem(modified.strftime('%Y-%m-%d %H:%M:%S'))
            
            # Store file path in project name item
            project_name.setData(Qt.UserRole, file_path)
            
            self.files_table.setItem(row_position, 0, project_name)
            self.files_table.setItem(row_position, 1, created_date)
            self.files_table.setItem(row_position, 2, modified_date)

    def create_new_file(self):
        """Handle create new button click"""
        # Show input dialog for file name
        file_name, ok = QInputDialog.getText(self, 'Create New Project', 'Enter project name:')
        
        if ok and file_name:
            # Add .json extension if not present
            if not file_name.endswith('.json'):
                file_name += '.json'
            
            file_path = os.path.join(self.recent_files_path, file_name)
            
            # Check if file already exists
            if os.path.exists(file_path):
                QMessageBox.warning(self, 'Warning', 'A project with this name already exists.')
                return
            
            # Emit signal with new project name
            self.project_selected.emit(file_name, False)
            self.close()

    def open_file(self):
        """Handle open file button click"""
        # Check if a row is selected
        selected_rows = self.files_table.selectedItems()
        if selected_rows:
            # Get file path from the selected row
            row = selected_rows[0].row()
            file_path = self.files_table.item(row, 0).data(Qt.UserRole)
            self.project_selected.emit(file_path, True)
            self.close()
        else:
            # If no row is selected, open file dialog
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Open Project",
                self.recent_files_path,
                "JSON Files (*.json)"
            )
            
            if file_path:
                self.project_selected.emit(file_path, True)
                self.close()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = InitialPage()
    ex.show()
    sys.exit(app.exec_())