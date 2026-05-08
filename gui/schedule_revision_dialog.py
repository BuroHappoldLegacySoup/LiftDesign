"""
Schedule Revision Dialog — shown right before the VT Schedules export is
saved. It displays the project's current revision history and offers the
option to append a new revision whose fields are written into the title
block of the exported workbook (columns L..AD, rows 2..10).

Contract:

- Input: the current list of revision dicts stored on the project payload
  under ``ScheduleRevisions`` (may be empty / missing).
- Output on accept: ``get_new_revision()`` returns either ``None`` (the user
  chose *not* to add a new revision and wants the current revision history
  unchanged) or a dict of the five revision fields as plain strings.
"""
from __future__ import annotations

from datetime import date
from typing import Any, List, Mapping, Optional

from PyQt5.QtCore import QDate, Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    # Reuse the export module's suggestion helper so dialog and writer stay in sync.
    from lift_designer_schedules_export import suggest_next_revision_code
except Exception:  # pragma: no cover - defensive fallback for stand-alone use
    def suggest_next_revision_code(existing):  # type: ignore[no-redef]
        return f"P{len(existing) + 1:02d}"


REVISION_COLUMN_LABELS = ("Revision", "Issue Purpose", "Date", "Design Eng.", "Checked")
REVISION_FIELD_KEYS = ("revision", "issue_purpose", "date", "design_eng", "checked")


class ScheduleRevisionDialog(QDialog):
    """
    Ask the user whether a new revision should be appended to the schedule's
    title block before exporting. Existing revisions are shown in a read-only
    table for context.
    """

    def __init__(
        self,
        existing_revisions: Optional[List[Mapping[str, Any]]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._existing: List[Mapping[str, Any]] = list(existing_revisions or [])
        self._result: Optional[dict] = None

        self.setWindowTitle("VT Schedules — Revision")
        self.setMinimumSize(720, 480)
        self._build_ui()

    # ---- UI construction ------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        intro = QLabel(
            "These revisions will be written into the title block of the "
            "exported workbook."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        root.addWidget(self._build_history_group())
        root.addWidget(self._build_new_revision_group())

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_history_group(self) -> QGroupBox:
        group = QGroupBox("Current revisions")
        group.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 2px solid rgb(196, 214, 0); "
            "border-radius: 6px; margin-top: 10px; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        layout = QVBoxLayout(group)

        if not self._existing:
            msg = QLabel(
                "No revisions recorded yet — the first entry below will become P01."
            )
            msg.setStyleSheet("color: gray; font-style: italic;")
            layout.addWidget(msg)
            return group

        table = QTableWidget(len(self._existing), len(REVISION_COLUMN_LABELS))
        table.setHorizontalHeaderLabels(REVISION_COLUMN_LABELS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.verticalHeader().setVisible(False)

        for r, rev in enumerate(self._existing):
            for c, key in enumerate(REVISION_FIELD_KEYS):
                val = rev.get(key, "") if isinstance(rev, Mapping) else ""
                item = QTableWidgetItem("" if val is None else str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                table.setItem(r, c, item)

        table.setMinimumHeight(min(220, 60 + 28 * len(self._existing)))
        layout.addWidget(table)
        return group

    def _build_new_revision_group(self) -> QGroupBox:
        group = QGroupBox("New revision")
        group.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 2px solid rgb(196, 214, 0); "
            "border-radius: 6px; margin-top: 10px; } "
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"
        )
        outer = QVBoxLayout(group)

        self._chk_add = QCheckBox(
            "Add a new revision (leave unchecked to keep the current revision)"
        )
        # Default: check only when there is no revision yet, so the first export
        # conveniently starts with P01 without the user needing to tick the box.
        self._chk_add.setChecked(not self._existing)
        self._chk_add.toggled.connect(self._on_toggle_add)
        outer.addWidget(self._chk_add)

        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setContentsMargins(20, 6, 6, 6)

        self._ed_revision = QLineEdit()
        self._ed_revision.setText(suggest_next_revision_code(self._existing))
        self._ed_revision.setMaximumWidth(120)

        self._ed_purpose = QLineEdit()

        self._ed_date = QDateEdit()
        self._ed_date.setCalendarPopup(True)
        self._ed_date.setDisplayFormat("yyyy-MM-dd")
        today = date.today()
        self._ed_date.setDate(QDate(today.year, today.month, today.day))
        self._ed_date.setMaximumWidth(160)

        self._ed_designer = QLineEdit()
        self._ed_checked = QLineEdit()

        form.addRow("Revision:", self._ed_revision)
        form.addRow("Issue Purpose:", self._ed_purpose)
        form.addRow("Date:", self._ed_date)
        form.addRow("Design Eng.:", self._ed_designer)
        form.addRow("Checked:", self._ed_checked)

        outer.addWidget(form_host)
        self._form_host = form_host
        self._on_toggle_add(self._chk_add.isChecked())
        return group

    # ---- Events ---------------------------------------------------------

    def _on_toggle_add(self, enabled: bool) -> None:
        self._form_host.setEnabled(enabled)

    def _on_accept(self) -> None:
        if not self._chk_add.isChecked():
            self._result = None
            self.accept()
            return

        rev_code = self._ed_revision.text().strip()
        if not rev_code:
            QMessageBox.warning(
                self,
                "VT Schedules — Revision",
                "Please fill in a revision code (e.g. P01) or uncheck "
                "'Add a new revision'.",
            )
            return

        self._result = {
            "revision": rev_code,
            "issue_purpose": self._ed_purpose.text().strip(),
            "date": self._ed_date.date().toString("yyyy-MM-dd"),
            "design_eng": self._ed_designer.text().strip(),
            "checked": self._ed_checked.text().strip(),
        }
        self.accept()

    # ---- Public API -----------------------------------------------------

    def get_new_revision(self) -> Optional[dict]:
        """
        Return the new revision dict the user entered, or ``None`` when the
        user chose to keep the existing revisions as-is. Only meaningful
        after the dialog was accepted.
        """
        return self._result
