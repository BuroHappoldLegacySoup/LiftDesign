"""Dialog to edit lift column groups (name + number of consecutive lifts) on the Building System page."""
from __future__ import annotations

from typing import List

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.project_lift_schema import parse_lift_column_groups as parse_lift_groups


class LiftGroupsDialog(QDialog):
    """Edit group names and how many consecutive lifts each group spans."""

    def __init__(self, parent: QWidget | None, n_lifts: int, groups: List[dict]):
        super().__init__(parent)
        self._n_lifts = max(1, n_lifts)
        self._entries: list[tuple[QWidget, QLineEdit, QSpinBox, QPushButton]] = []
        self.setWindowTitle("Lift groups")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Combine consecutive lifts under one header. "
                "The numbers must add up to the total number of lifts."
            )
        )
        self._total_label = QLabel()
        self._total_label.setTextFormat(Qt.RichText)
        layout.addWidget(self._total_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._holder = QWidget()
        self._holder_layout = QVBoxLayout(self._holder)
        scroll.setWidget(self._holder)
        layout.addWidget(scroll)

        add_btn = QPushButton("Add group")
        add_btn.clicked.connect(self._add_group_row)
        layout.addWidget(add_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        parsed = parse_lift_groups(groups, self._n_lifts)
        if not parsed:
            parsed = [{"name": "Group 1", "count": self._n_lifts}]
        for g in parsed:
            self._append_row(str(g.get("name", "")), int(g.get("count", 1)))
        self._refresh_total_label()

    def _append_row(self, name: str, count: int) -> None:
        row_w = QWidget()
        hl = QHBoxLayout(row_w)
        hl.setContentsMargins(0, 4, 0, 4)
        nm = QLineEdit(name)
        sp = QSpinBox()
        sp.setMinimum(1)
        sp.setMaximum(max(1, self._n_lifts))
        sp.setValue(min(max(1, count), self._n_lifts))
        sp.valueChanged.connect(self._refresh_total_label)
        rm = QPushButton("Remove")
        hl.addWidget(QLabel("Name:"))
        hl.addWidget(nm, 1)
        hl.addWidget(QLabel("Lifts:"))
        hl.addWidget(sp)
        hl.addWidget(rm)
        self._holder_layout.addWidget(row_w)

        def remove() -> None:
            if len(self._entries) <= 1:
                return
            self._holder_layout.removeWidget(row_w)
            row_w.deleteLater()
            self._entries[:] = [e for e in self._entries if e[0] is not row_w]
            self._refresh_total_label()

        rm.clicked.connect(remove)
        self._entries.append((row_w, nm, sp, rm))

    def _add_group_row(self) -> None:
        n = len(self._entries) + 1
        self._append_row(f"Group {n}", 1)
        self._refresh_total_label()

    def _refresh_total_label(self) -> None:
        s = sum(e[2].value() for e in self._entries)
        ok = s == self._n_lifts
        color = "#0a0" if ok else "#c00"
        self._total_label.setText(
            f"<b>Total lifts in groups:</b> <span style='color:{color};'>{s}</span> "
            f"&nbsp; (required: {self._n_lifts})"
        )

    def _on_accept(self) -> None:
        if sum(e[2].value() for e in self._entries) != self._n_lifts:
            QMessageBox.warning(
                self,
                "Lift groups",
                f"The lift counts must add up to {self._n_lifts} (the number of lift columns).",
            )
            return
        self.accept()

    def groups_result(self) -> List[dict]:
        return [
            {"name": e[1].text().strip(), "count": int(e[2].value())}
            for e in self._entries
        ]
