"""The project browser: levels, walls, doors and windows, in a tree."""

from __future__ import annotations

from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from brunelleschi import api
from brunelleschi.gui.document import Document

ID_ROLE = Qt.ItemDataRole.UserRole


class ProjectBrowser(QTreeWidget):
    """Selecting an item selects the element in the document, and the other way round."""

    def __init__(self, document: Document) -> None:
        super().__init__()
        self.document = document
        self.setHeaderHidden(True)
        self._updating = False
        document.changed.connect(self.rebuild)
        document.selection_changed.connect(self._follow_selection)
        self.itemSelectionChanged.connect(self._selected_in_tree)
        self.rebuild()

    def rebuild(self) -> None:
        self._updating = True
        try:
            self.clear()
            p = self.document.project
            groups = [
                (
                    "Levels",
                    [
                        (lv.id, f"{lv.name}   {lv.elevation:+.2f} m")
                        for lv in reversed(p.levels_by_elevation())
                    ],
                ),
                ("Walls", [(w.id, self._wall_text(p, w)) for w in p.walls]),
                ("Doors", [(d.id, self._hosted_text(d)) for d in p.doors]),
                ("Windows", [(w.id, self._hosted_text(w)) for w in p.windows]),
            ]
            for title, rows in groups:
                parent = QTreeWidgetItem([f"{title} ({len(rows)})"])
                parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self.addTopLevelItem(parent)
                for element_id, text in rows:
                    item = QTreeWidgetItem([text])
                    item.setData(0, ID_ROLE, str(element_id))
                    parent.addChild(item)
                parent.setExpanded(True)
        finally:
            self._updating = False
        self._follow_selection()

    @staticmethod
    def _wall_text(p: api.Project, w: api.Wall) -> str:
        base = p.level(w.base_level_id).name
        return f"Wall {api.short_id(w.id)}   {w.length:.2f} m, {base}"

    @staticmethod
    def _hosted_text(e: api.HostedElement) -> str:
        return f"{e.kind.capitalize()} {api.short_id(e.id)}   {e.width:.2f} x {e.height:.2f} m"

    def item_for(self, element_id: UUID) -> QTreeWidgetItem | None:
        for i in range(self.topLevelItemCount()):
            group = self.topLevelItem(i)
            if group is None:
                continue
            for k in range(group.childCount()):
                child = group.child(k)
                if child is not None and child.data(0, ID_ROLE) == str(element_id):
                    return child
        return None

    def _follow_selection(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            selected = self.document.selected
            item = self.item_for(selected) if selected else None
            self.clearSelection()
            if item is not None:
                item.setSelected(True)
                self.scrollToItem(item)
        finally:
            self._updating = False

    def _selected_in_tree(self) -> None:
        if self._updating:
            return
        items = self.selectedItems()
        value = items[0].data(0, ID_ROLE) if items else None
        self.document.select(UUID(value) if value else None)
