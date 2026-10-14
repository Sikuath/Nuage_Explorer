"""Méthodes de MainWindow regroupées par fonctionnalité."""
from .common import *
from .workers import (
    DownloadWorker, MultiDownloadWorker, UploadWorker, MultiUploadWorker,
    DeleteWorker, PreviewWorker, NewOfficeDocumentWorker, OfficeEditWorker,
    ResourceOperationWorker,
)
from .dialogs import ProfileDialog, PreviewDialog, RemoteFolderDialog
from .widgets import DragDropTableWidget, LocalDropTreeView

class FolderOperationsMixin:
    def create_folder(self):
        if not self.profile or not self.url_stack:
            QMessageBox.warning(
                self,
                "Compte non configuré",
                "Configure d'abord ton compte NUAGE.",
            )
            return

        name, ok = QInputDialog.getText(
            self,
            "Nouveau dossier",
            "Nom du dossier :",
        )

        if not ok:
            return

        name = name.strip()

        if not name:
            QMessageBox.warning(
                self,
                "Nom manquant",
                "Saisis un nom de dossier.",
            )
            return

        if (
            name in (".", "..")
            or "/" in name
            or "\\" in name
            or any(ord(char) < 32 for char in name)
        ):
            QMessageBox.warning(
                self,
                "Nom invalide",
                "Le nom ne doit pas contenir de barre oblique "
                "ni de caractère de contrôle.",
            )
            return

        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue

            data = item.data(Qt.ItemDataRole.UserRole)

            if data and data["name"].casefold() == name.casefold():
                QMessageBox.warning(
                    self,
                    "Nom déjà utilisé",
                    "Un fichier ou un dossier porte déjà ce nom.",
                )
                return

        try:
            create_directory(
                self.url_stack[-1],
                name,
                self.profile["username"],
                self.profile["password"],
            )
        except WebDAVError as exc:
            QMessageBox.warning(
                self,
                "Création impossible",
                str(exc),
            )
            return

        self.refresh()
        self.status_label.setText(f"✓  Dossier « {name} » créé sur NUAGE.")

        QMessageBox.information(
            self,
            "Dossier créé",
            f"Le dossier « {name} » a bien été créé.",
        )
