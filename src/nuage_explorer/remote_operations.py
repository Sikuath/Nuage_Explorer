"""Méthodes de MainWindow regroupées par fonctionnalité."""
from .common import *
from .workers import (
    DownloadWorker, MultiDownloadWorker, UploadWorker, MultiUploadWorker,
    DeleteWorker, PreviewWorker, NewOfficeDocumentWorker, OfficeEditWorker,
    ResourceOperationWorker,
)
from .dialogs import ProfileDialog, PreviewDialog, RemoteFolderDialog
from .widgets import DragDropTableWidget, LocalDropTreeView

class RemoteOperationsMixin:
    def show_context_menu(self, position):
        clicked_item = self.table.itemAt(position)

        if clicked_item is not None:
            selected_rows = {
                index.row()
                for index in self.table.selectionModel().selectedRows()
            }

            if clicked_item.row() not in selected_rows:
                self.table.clearSelection()
                self.table.selectRow(clicked_item.row())
        else:
            self.table.clearSelection()

        items = self.selected_remote_items()

        has_items = bool(items)
        has_files = any(
            not item["is_directory"]
            for item in items
        )
        single_item = len(items) == 1

        menu = QMenu(self)

        # Création de documents LibreOffice
        new_office_menu = menu.addMenu("＋  Nouveau document LibreOffice")

        writer_action = new_office_menu.addAction("Document Writer (.odt)")
        calc_action = new_office_menu.addAction("Classeur Calc (.ods)")
        impress_action = new_office_menu.addAction("Présentation Impress (.odp)")

        writer_action.triggered.connect(
            lambda checked=False: self.create_office_document("writer")
        )
        calc_action.triggered.connect(
            lambda checked=False: self.create_office_document("calc")
        )
        impress_action.triggered.connect(
            lambda checked=False: self.create_office_document("impress")
        )

        menu.addSeparator()

        # Groupe 1 : ouvrir
        open_action = menu.addAction("📂  Ouvrir")
        open_action.setEnabled(single_item)
        open_action.triggered.connect(self.open_selected)

        menu.addSeparator()

        # Groupe 2 : presse-papiers et transferts
        cut_action = menu.addAction("✂  Couper")
        cut_action.setEnabled(has_items)
        cut_action.triggered.connect(self.cut_selected)

        copy_action = menu.addAction("📋  Copier")
        copy_action.setEnabled(has_items)
        copy_action.triggered.connect(self.copy_selected)

        move_action = menu.addAction("Déplacer vers…")
        move_action.setEnabled(has_items)
        move_action.triggered.connect(
            lambda checked=False: self.transfer_selected_to("move")
        )

        copy_to_action = menu.addAction("Copier vers…")
        copy_to_action.setEnabled(has_items)
        copy_to_action.triggered.connect(
            lambda checked=False: self.transfer_selected_to("copy")
        )

        menu.addSeparator()

        # Groupe 3 : gestion des éléments
        rename_action = menu.addAction("Renommer")
        rename_action.setEnabled(single_item)
        rename_action.triggered.connect(self.rename_selected)

        paste_action = menu.addAction("Coller dans le dossier")
        paste_action.setEnabled(bool(self.clipboard_items))
        paste_action.triggered.connect(self.paste_into_current_folder)

        menu.addSeparator()

        # Groupe 4 : suppression et téléchargement
        delete_action = menu.addAction("🗑  Supprimer")
        delete_action.setEnabled(has_items)
        delete_action.triggered.connect(self.delete_selected)

        download_action = menu.addAction("⬇  Télécharger")
        download_action.setEnabled(has_files)
        download_action.triggered.connect(self.download_selected)

        menu.exec(
            self.table.viewport().mapToGlobal(position)
        )
    def selected_remote_items(self):
        """Retourne les éléments sélectionnés dans le tableau."""
        rows = sorted({
            index.row()
            for index in self.table.selectionModel().selectedRows()
        })

        items = []

        for row in rows:
            name_item = self.table.item(row, 0)
            if name_item is None:
                continue

            data = name_item.data(Qt.ItemDataRole.UserRole)
            if data:
                items.append(dict(data))

        return items
    def open_selected(self):
        items = self.selected_remote_items()

        if len(items) != 1:
            return

        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.open_item(self.table.item(rows[0].row(), 0))
    def cut_selected(self):
        items = self.selected_remote_items()
        if not items:
            return

        self.clipboard_items = items
        self.clipboard_mode = "move"

        self.status_label.setText(
            f"{len(items)} élément(s) coupé(s) : prêts à être déplacés."
        )
    def copy_selected(self):
        items = self.selected_remote_items()
        if not items:
            return

        self.clipboard_items = items
        self.clipboard_mode = "copy"

        self.status_label.setText(
            f"{len(items)} élément(s) copié(s) dans le presse-papiers interne."
        )
    def build_transfer_operations(self, items, destination_folder_url, mode):
        """Prépare les opérations en vérifiant les destinations dangereuses."""
        destination_folder_url = destination_folder_url.rstrip("/") + "/"
        operations = []

        for item in items:
            target_url = urljoin(
                destination_folder_url,
                quote(item["name"], safe=""),
            )

            if item["is_directory"]:
                target_url = target_url.rstrip("/") + "/"

            source = urlsplit(item["url"])
            target = urlsplit(target_url)

            if source.netloc.lower() != target.netloc.lower():
                QMessageBox.warning(
                    self,
                    "Destination invalide",
                    "La source et la destination doivent être sur le même serveur.",
                )
                return None

            source_path = source.path.rstrip("/")
            target_path = target.path.rstrip("/")

            if source_path == target_path:
                QMessageBox.warning(
                    self,
                    "Destination invalide",
                    f"« {item['name']} » est déjà dans ce dossier "
                    "ou porte déjà ce nom à cet emplacement.",
                )
                return None

            if (
                item["is_directory"]
                and target_path.startswith(source_path + "/")
            ):
                QMessageBox.warning(
                    self,
                    "Destination invalide",
                    f"Impossible de copier ou déplacer « {item['name']} » "
                    "dans lui-même ou dans l'un de ses sous-dossiers.",
                )
                return None

            operations.append({
                "operation": mode,
                "url": item["url"],
                "destination_url": target_url,
                "name": item["name"],
                "is_directory": item["is_directory"],
            })

        return operations
    def transfer_selected_to(self, mode):
        """Ouvre le sélecteur de destination pour copier ou déplacer."""
        items = self.selected_remote_items()
        if not items:
            return

        if (
            self.transfer_worker is not None
            and self.transfer_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Opération en cours",
                "Attends la fin de l'opération WebDAV actuelle.",
            )
            return

        dialog = RemoteFolderDialog(self.profile, self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        operations = self.build_transfer_operations(
            items,
            dialog.destination_url,
            mode,
        )

        if operations is None or not operations:
            return

        label = (
            "Copie sur NUAGE"
            if mode == "copy"
            else "Déplacement sur NUAGE"
        )

        self.start_resource_operations(operations, label)
    def paste_into_current_folder(self):
        """Colle les éléments du presse-papiers dans le dossier ouvert."""
        if (
            not self.profile
            or not self.url_stack
            or not self.clipboard_items
            or self.clipboard_mode not in ("copy", "move")
        ):
            return

        if (
            self.transfer_worker is not None
            and self.transfer_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Opération en cours",
                "Attends la fin de l'opération WebDAV actuelle.",
            )
            return

        destination = self.url_stack[-1]

        operations = self.build_transfer_operations(
            self.clipboard_items,
            destination,
            self.clipboard_mode,
        )

        if operations is None or not operations:
            return

        label = (
            "Copie dans le dossier courant"
            if self.clipboard_mode == "copy"
            else "Déplacement dans le dossier courant"
        )

        self.start_resource_operations(
            operations,
            label,
            clear_clipboard=(self.clipboard_mode == "move"),
        )
    def rename_selected(self):
        """Renomme un seul fichier ou dossier sur le serveur."""
        items = self.selected_remote_items()

        if len(items) != 1:
            return

        item = items[0]
        current_name = item["name"]

        new_name, ok = QInputDialog.getText(
            self,
            "Renommer",
            "Nouveau nom :",
            QLineEdit.EchoMode.Normal,
            current_name,
        )

        if not ok:
            return

        new_name = new_name.strip()

        if not new_name or new_name == current_name:
            return

        if (
            new_name in (".", "..")
            or "/" in new_name
            or "\\" in new_name
            or any(ord(char) < 32 for char in new_name)
        ):
            QMessageBox.warning(
                self,
                "Nom invalide",
                "Le nom ne doit pas contenir de barre oblique "
                "ni de caractère de contrôle.",
            )
            return

        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            if name_item is None:
                continue

            data = name_item.data(Qt.ItemDataRole.UserRole)
            if not data or data["url"] == item["url"]:
                continue

            if data["name"].casefold() == new_name.casefold():
                QMessageBox.warning(
                    self,
                    "Nom déjà utilisé",
                    "Un fichier ou un dossier porte déjà ce nom.",
                )
                return

        operations = [{
            "operation": "rename",
            "url": item["url"],
            "name": current_name,
            "new_name": new_name,
            "is_directory": item["is_directory"],
        }]

        self.start_resource_operations(
            operations,
            "Renommage sur NUAGE",
        )
    def start_resource_operations(
        self,
        operations,
        action_label,
        clear_clipboard=False,
    ):
        """Lance les opérations sur un thread séparé."""
        if not operations:
            return

        if (
            self.transfer_worker is not None
            and self.transfer_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Opération en cours",
                "Attends la fin de l'opération WebDAV actuelle.",
            )
            return

        self.transfer_action_label = action_label
        self.clear_clipboard_after_transfer = clear_clipboard

        self.transfer_dialog = QProgressDialog(
            f"{action_label}…",
            None,
            0,
            100,
            self,
        )
        self.transfer_dialog.setWindowTitle("Nextcloud Explorer")
        self.transfer_dialog.setCancelButton(None)
        self.transfer_dialog.setWindowModality(
            Qt.WindowModality.WindowModal
        )
        self.transfer_dialog.setMinimumDuration(300)
        self.transfer_dialog.setValue(0)
        self.transfer_dialog.show()

        self.transfer_worker = ResourceOperationWorker(
            operations,
            self.profile["username"],
            self.profile["password"],
            self,
        )

        self.transfer_worker.progress.connect(
            self.resource_operation_progress
        )
        self.transfer_worker.completed.connect(
            self.resource_operation_completed
        )
        self.transfer_worker.finished.connect(
            self.resource_operation_thread_finished
        )
        self.transfer_worker.start()
    def resource_operation_progress(self, percent, name):
        if self.transfer_dialog is not None:
            self.transfer_dialog.setLabelText(
                f"{self.transfer_action_label} : {name}…"
            )
            self.transfer_dialog.setValue(percent)
    def resource_operation_completed(self, results):
        if self.transfer_dialog is not None:
            self.transfer_dialog.setValue(100)
            self.transfer_dialog.close()
            self.transfer_dialog = None

        successes = results["success"]
        failures = results["failed"]

        # Actualise le tableau et l'arborescence après les changements.
        self.rebuild_tree()
        self.refresh()

        summary = (
            f"Opérations réussies : {len(successes)}\n"
            f"Échecs : {len(failures)}"
        )

        if failures:
            details = "\n".join(
                f"• {name} : {message}"
                for name, message in failures
            )
            summary += f"\n\nDétails des erreurs :\n{details}"

        if (
            self.clear_clipboard_after_transfer
            and not failures
        ):
            self.clipboard_items = []
            self.clipboard_mode = None

        self.clear_clipboard_after_transfer = False

        self.status_label.setText(
            f"{self.transfer_action_label} terminé : "
            f"{len(successes)} réussite(s), {len(failures)} échec(s)."
        )

        if failures:
            QMessageBox.warning(
                self,
                "Bilan des opérations",
                summary,
            )
        else:
            QMessageBox.information(
                self,
                "Bilan des opérations",
                summary,
            )
    def resource_operation_thread_finished(self):
        self.transfer_worker = None
    def delete_selected(self):
        if not self.profile or not self.url_stack:
            return

        if self.delete_worker is not None and self.delete_worker.isRunning():
            QMessageBox.information(
                self,
                "Suppression en cours",
                "Attends la fin de la suppression actuelle.",
            )
            return

        rows = sorted({index.row() for index in self.table.selectionModel().selectedRows()})

        items = []

        for row in rows:
            name_item = self.table.item(row, 0)
            if name_item is None:
                continue

            data = name_item.data(Qt.ItemDataRole.UserRole)

            if data:
                items.append(
                    {
                        "url": data["url"],
                        "name": data["name"],
                        "is_directory": data["is_directory"],
                    }
                )

        if not items:
            QMessageBox.information(
                self,
                "Aucun élément",
                "Sélectionne au moins un fichier ou un dossier.",
            )
            return

        names = "\n".join(
            f"• {'[Dossier]' if item['is_directory'] else '[Fichier]'} " f"{item['name']}"
            for item in items[:10]
        )

        if len(items) > 10:
            names += f"\n… et {len(items) - 10} autre(s) élément(s)"

        answer = QMessageBox.warning(
            self,
            "Confirmer la suppression",
            f"Tu vas supprimer {len(items)} élément(s) de NUAGE :\n\n"
            f"{names}\n\n"
            "Attention : supprimer un dossier peut aussi supprimer "
            "son contenu selon le comportement du serveur.\n\n"
            "Cette opération peut être irréversible. Continuer ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.delete_dialog = QProgressDialog(
            "Suppression des éléments…",
            None,
            0,
            len(items),
            self,
        )
        self.delete_dialog.setWindowTitle("Suppression NUAGE")
        self.delete_dialog.setCancelButton(None)
        self.delete_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.delete_dialog.setMinimumDuration(300)
        self.delete_dialog.setValue(0)
        self.delete_dialog.show()

        self.delete_worker = DeleteWorker(
            items,
            self.profile["username"],
            self.profile["password"],
            self,
        )

        self.delete_worker.completed.connect(self.delete_completed)
        self.delete_worker.finished.connect(self.delete_thread_finished)
        self.delete_worker.start()
    def delete_completed(self, results):
        if self.delete_dialog is not None:
            self.delete_dialog.close()
            self.delete_dialog = None

        successes = results["success"]
        failures = results["failed"]

        self.refresh()

        summary = (
            f"Suppressions réussies : {len(successes)}\n" f"Échecs : {len(failures)}"
        )

        if failures:
            details = "\n".join(f"• {name} : {message}" for name, message in failures)
            summary += f"\n\nDétails des erreurs :\n{details}"

        self.status_label.setText(
            f"Suppression terminée : {len(successes)} supprimé(s), "
            f"{len(failures)} échec(s)."
        )

        if failures:
            QMessageBox.warning(
                self,
                "Bilan des suppressions",
                summary,
            )
        else:
            QMessageBox.information(
                self,
                "Bilan des suppressions",
                summary,
            )
    def delete_thread_finished(self):
        self.delete_worker = None
