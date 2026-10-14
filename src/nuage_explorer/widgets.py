"""Widgets personnalisés pour le glisser-déposer."""
from .common import *

class DragDropTableWidget(QTableWidget):
    """Tableau Nextcloud : accepte les fichiers Windows et permet de les glisser."""

    local_files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(0, 4, parent)

        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(
            QAbstractItemView.DragDropMode.DragDrop
        )
        self.setDropIndicatorShown(True)

    def dragEnterEvent(self, event):
        mime = event.mimeData()

        if (
            mime.hasUrls()
            and any(url.isLocalFile() for url in mime.urls())
        ):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return

        event.ignore()

    def dragMoveEvent(self, event):
        mime = event.mimeData()

        if (
            mime.hasUrls()
            and any(url.isLocalFile() for url in mime.urls())
        ):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return

        event.ignore()

    def dropEvent(self, event):
        paths = []

        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue

            path = Path(url.toLocalFile())

            # L'envoi direct ne concerne pour l'instant que les fichiers.
            if path.is_file():
                paths.append(str(path))

        if paths:
            self.local_files_dropped.emit(paths)
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def startDrag(self, supported_actions):
        """Expose les fichiers Nextcloud sélectionnés au glisser-déposer."""
        items = []
        rows = sorted({
            index.row()
            for index in self.selectionModel().selectedRows()
        })

        for row in rows:
            cell = self.item(row, 0)
            if cell is None:
                continue

            data = cell.data(Qt.ItemDataRole.UserRole)

            if data and not data.get("is_directory", False):
                items.append({
                    "url": data["url"],
                    "name": data["name"],
                    "is_directory": False,
                })

        if not items:
            return

        mime = QMimeData()
        mime.setData(
            "application/x-nuage-remote-items",
            json.dumps(items).encode("utf-8"),
        )

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class LocalDropTreeView(QTreeView):
    """Arborescence Windows : reçoit les fichiers glissés depuis Nextcloud."""

    remote_items_dropped = Signal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(
            QAbstractItemView.DragDropMode.DragDrop
        )


    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(
            "application/x-nuage-remote-items"
        ):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(
            "application/x-nuage-remote-items"
        ):
            index = self.indexAt(event.position().toPoint())

            if index.isValid():
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not event.mimeData().hasFormat(
            "application/x-nuage-remote-items"
        ):
            event.ignore()
            return

        index = self.indexAt(event.position().toPoint())

        if not index.isValid():
            event.ignore()
            return

        destination = self.model().filePath(index)

        if not Path(destination).is_dir():
            event.ignore()
            return

        try:
            items = json.loads(bytes(
                event.mimeData().data(
                    "application/x-nuage-remote-items"
                )
            ).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            event.ignore()
            return

        if not items:
            event.ignore()
            return

        self.remote_items_dropped.emit(items, destination)
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
