"""
Change History Dialog - displays when the loaded file was altered, which input changed, and what the change was.
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QGroupBox
)
from PyQt5.QtCore import Qt


class ChangeHistoryDialog(QDialog):
    """Dialog showing the change history of the loaded project file."""

    def __init__(self, change_history: list, project_name: str = "", parent=None):
        super().__init__(parent)
        self.change_history = change_history or []
        self.project_name = project_name
        self.setWindowTitle("Change History")
        self.setMinimumSize(800, 600)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Summary
        if self.project_name:
            title = QLabel(f"Change history for: {self.project_name}")
            title.setStyleSheet("font-weight: bold; font-size: 14px;")
            layout.addWidget(title)

        if not self.change_history:
            no_changes = QLabel("No changes have been recorded for this project yet.")
            no_changes.setStyleSheet("color: gray; font-style: italic;")
            layout.addWidget(no_changes)
        else:
            summary = QLabel(
                f"This file has been altered {len(self.change_history)} time(s). "
                "Below are the recorded changes."
            )
            summary.setWordWrap(True)
            layout.addWidget(summary)

            # Table of changes
            group = QGroupBox("Recorded Changes")
            group.setStyleSheet(
                "QGroupBox { font-weight: bold; border: 2px solid rgb(196, 214, 0); "
                "border-radius: 6px; margin-top: 10px; } "
                "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
            )
            group_layout = QVBoxLayout(group)

            self.table = QTableWidget()
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(["Date", "Page", "Input / Field", "Previous Value", "New Value"])
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self.table.setAlternatingRowColors(True)
            self.table.setWordWrap(True)
            self.table.setTextElideMode(Qt.ElideNone)
            self.table.setStyleSheet("""
                QTableWidget {
                    gridline-color: #e0e0e0;
                    color: black;
                    background-color: white;
                }
                QTableWidget::item {
                    padding: 6px;
                    color: black;
                }
                QTableWidget::item:alternate {
                    background-color: #f8f8f8;
                }
                QHeaderView::section {
                    background-color: rgb(196, 214, 0);
                    color: black;
                    padding: 8px;
                    font-weight: bold;
                }
            """)

            for row_idx, record in enumerate(self.change_history):
                self.table.insertRow(row_idx)
                values = [
                    record.get("date", ""),
                    record.get("page", ""),
                    record.get("field_display", record.get("field", "")),
                    str(record.get("old_value", "")),
                    str(record.get("new_value", "")),
                ]
                for col, val in enumerate(values):
                    item = QTableWidgetItem(str(val))
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    self.table.setItem(row_idx, col, item)

            group_layout.addWidget(self.table)
            layout.addWidget(group)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("background-color: rgb(196, 214, 0); padding: 6px 20px;")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)
