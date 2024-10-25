# gui.py
from gui.main_window import MainWindow
from gui.initial_page import InitialPage
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont, QIcon

def main():
    app = QApplication([])
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    app.setWindowIcon(QIcon('Elevator.ico'))
    
    # Create both windows but only show initial page first
    initial_window = InitialPage()
    main_window = MainWindow()
    
    # Connect the signal from initial page to main window
    def handle_project_selection(path_or_name, is_existing_file):
        main_window.load_project(path_or_name, is_existing_file)
        main_window.show()
    
    initial_window.project_selected.connect(handle_project_selection)
    
    # Show initial window
    initial_window.show()
    
    app.exec_()

if __name__ == "__main__":
    main()