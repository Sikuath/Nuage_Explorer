"""Méthodes de MainWindow regroupées par fonctionnalité."""
from .common import *
from .workers import (
    DownloadWorker, MultiDownloadWorker, UploadWorker, MultiUploadWorker,
    DeleteWorker, PreviewWorker, NewOfficeDocumentWorker, OfficeEditWorker,
    ResourceOperationWorker,
)
from .dialogs import ProfileDialog, PreviewDialog, RemoteFolderDialog
from .widgets import DragDropTableWidget, LocalDropTreeView

class TransfersMixin:
    def download_selected(self):
        if not self.profile or not self.url_stack:
            return

        if (self.download_worker is not None and self.download_worker.isRunning()) or (
            self.multi_download_worker is not None
            and self.multi_download_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Téléchargement en cours",
                "Attends la fin du téléchargement actuel.",
            )
            return

        rows = sorted(
            {index.row() for index in self.table.selectionModel().selectedRows()}
        )

        files = []
        skipped_directories = 0

        for row in rows:
            item = self.table.item(row, 0)
            data = item.data(Qt.ItemDataRole.UserRole)

            if not data:
                continue

            if data["is_directory"]:
                skipped_directories += 1
                continue

            files.append(
                {
                    "url": data["url"],
                    "name": data["name"],
                }
            )

        if not files:
            QMessageBox.information(
                self,
                "Aucun fichier",
                "Sélectionne au moins un fichier à télécharger.",
            )
            return

        destination = QFileDialog.getExistingDirectory(
            self,
            "Choisir le dossier de destination",
        )
        if not destination:
            return

        # Vérifier les éventuels fichiers déjà présents.
        existing = [
            item
            for item in files
            if (Path(destination) / Path(item["name"]).name).exists()
        ]

        skipped_existing = 0

        if existing:
            answer = QMessageBox.question(
                self,
                "Fichiers déjà présents",
                f"{len(existing)} fichier(s) existent déjà dans "
                f"le dossier choisi.\n\n"
                "Oui : remplacer les fichiers existants.\n"
                "Non : conserver les fichiers existants et les ignorer.\n"
                "Annuler : abandonner le téléchargement.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.No,
            )

            if answer == QMessageBox.StandardButton.Cancel:
                return

            if answer == QMessageBox.StandardButton.No:
                existing_names = {item["name"] for item in existing}
                files = [item for item in files if item["name"] not in existing_names]
                skipped_existing = len(existing)

        if not files:
            QMessageBox.information(
                self,
                "Aucun téléchargement",
                "Tous les fichiers sélectionnés existent déjà.",
            )
            return

        self.multi_download_skipped = skipped_existing + skipped_directories

        self.multi_download_dialog = QProgressDialog(
            "Préparation du téléchargement…",
            None,
            0,
            100,
            self,
        )
        self.multi_download_dialog.setWindowTitle("Téléchargement multiple")
        self.multi_download_dialog.setCancelButton(None)
        self.multi_download_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.multi_download_dialog.setMinimumDuration(300)
        self.multi_download_dialog.setValue(0)
        self.multi_download_dialog.show()

        self.multi_download_worker = MultiDownloadWorker(
            files,
            destination,
            self.profile["username"],
            self.profile["password"],
            self,
        )

        self.multi_download_worker.progress.connect(self.multi_download_progress)
        self.multi_download_worker.current_file.connect(
            self.multi_download_current_file
        )
        self.multi_download_worker.completed.connect(self.multi_download_completed)
        self.multi_download_worker.finished.connect(self.multi_download_thread_finished)
        self.multi_download_worker.start()

        self.status_label.setText(f"Téléchargement de {len(files)} fichier(s)…")
    def multi_download_progress(self, percent):
        if self.multi_download_dialog is not None:
            self.multi_download_dialog.setValue(percent)
    def multi_download_current_file(self, name):
        if self.multi_download_dialog is not None:
            self.multi_download_dialog.setLabelText(f"Téléchargement de {name}…")
    def multi_download_completed(self, results):
        if self.multi_download_dialog is not None:
            self.multi_download_dialog.close()
            self.multi_download_dialog = None

        successes = results["success"]
        failures = results["failed"]
        skipped = self.multi_download_skipped

        summary = (
            f"Téléchargements réussis : {len(successes)}\n"
            f"Échecs : {len(failures)}\n"
            f"Éléments ignorés : {skipped}"
        )

        if failures:
            details = "\n".join(f"• {name} : {message}" for name, message in failures)
            summary += f"\n\nDétails des erreurs :\n{details}"

        self.status_label.setText(
            f"Téléchargement terminé : {len(successes)} réussi(s), "
            f"{len(failures)} échec(s)."
        )

        if failures:
            QMessageBox.warning(self, "Bilan des téléchargements", summary)
        else:
            QMessageBox.information(self, "Bilan des téléchargements", summary)
    def multi_download_thread_finished(self):
        self.multi_download_worker = None
    def download_progress(self, percent):
        if self.download_dialog is not None:
            self.download_dialog.setValue(percent)
    def download_succeeded(self, destination):
        if self.download_dialog is not None:
            self.download_dialog.setValue(100)
            self.download_dialog.close()
            self.download_dialog = None

        self.status_label.setText("✓  Téléchargement terminé")

        QMessageBox.information(
            self,
            "Téléchargement terminé",
            f"Fichier enregistré ici :\n\n{destination}",
        )
    def download_failed(self, message):
        if self.download_dialog is not None:
            self.download_dialog.close()
            self.download_dialog = None

        self.status_label.setText("Le téléchargement a échoué.")

        QMessageBox.warning(
            self,
            "Erreur de téléchargement",
            message,
        )
    def download_thread_finished(self):
        self.download_worker = None
    def upload_dropped_to_remote(self, paths):
        """Envoie les fichiers Windows déposés sur le tableau Nextcloud."""
        if not self.profile or not self.url_stack:
            QMessageBox.warning(
                self,
                "Compte non configuré",
                "Configure d'abord ton compte Nextcloud.",
            )
            return

        if (
            self.multi_upload_worker is not None
            and self.multi_upload_worker.isRunning()
        ) or (
            self.upload_worker is not None
            and self.upload_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Import en cours",
                "Attends la fin de l'import actuel.",
            )
            return

        if (
            self.multi_download_worker is not None
            and self.multi_download_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Transfert en cours",
                "Attends la fin du transfert actuel.",
            )
            return

        existing_names = {
            self.table.item(row, 0).data(
                Qt.ItemDataRole.UserRole
            )["name"].casefold()
            for row in range(self.table.rowCount())
            if self.table.item(row, 0) is not None
            and self.table.item(row, 0).data(
                Qt.ItemDataRole.UserRole
            )
        }

        conflicts = [
            Path(path).name
            for path in paths
            if Path(path).name.casefold() in existing_names
        ]

        overwrite_all = False
        skip_names = set()

        if conflicts:
            answer = QMessageBox.question(
                self,
                "Fichiers déjà présents",
                f"{len(conflicts)} fichier(s) existent déjà dans "
                "le dossier Nextcloud courant.\n\n"
                "Oui : remplacer les fichiers existants.\n"
                "Non : ignorer les fichiers déjà présents.\n"
                "Annuler : abandonner le transfert.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.No,
            )

            if answer == QMessageBox.StandardButton.Cancel:
                return

            if answer == QMessageBox.StandardButton.Yes:
                overwrite_all = True
            else:
                skip_names = {name.casefold() for name in conflicts}

        files = []

        for path in paths:
            source = Path(path)

            if not source.is_file():
                continue

            exists = source.name.casefold() in existing_names

            if exists and source.name.casefold() in skip_names:
                continue

            files.append({
                "source": str(source),
                "name": source.name,
                "overwrite": overwrite_all and exists,
            })

        if not files:
            self.status_label.setText(
                "Aucun fichier à envoyer."
            )
            return

        self.multi_upload_dialog = QProgressDialog(
            "Préparation de l'envoi…",
            None,
            0,
            100,
            self,
        )
        self.multi_upload_dialog.setWindowTitle(
            "Envoi vers Nextcloud"
        )
        self.multi_upload_dialog.setCancelButton(None)
        self.multi_upload_dialog.setWindowModality(
            Qt.WindowModality.WindowModal
        )
        self.multi_upload_dialog.setMinimumDuration(300)
        self.multi_upload_dialog.setValue(0)
        self.multi_upload_dialog.show()

        self.multi_upload_worker = MultiUploadWorker(
            files,
            self.url_stack[-1],
            self.profile["username"],
            self.profile["password"],
            self,
        )

        self.multi_upload_worker.progress.connect(
            self.multi_upload_progress
        )
        self.multi_upload_worker.current_file.connect(
            self.multi_upload_current_file
        )
        self.multi_upload_worker.completed.connect(
            self.multi_upload_completed
        )
        self.multi_upload_worker.finished.connect(
            self.multi_upload_thread_finished
        )
        self.multi_upload_worker.start()

        self.status_label.setText(
            f"Envoi de {len(files)} fichier(s) vers Nextcloud…"
        )
    def download_dropped_to_local(self, items, destination):
        """Télécharge les fichiers Nextcloud vers le dossier Windows visé."""
        if not self.profile:
            return

        if (
            self.multi_download_worker is not None
            and self.multi_download_worker.isRunning()
        ) or (
            self.download_worker is not None
            and self.download_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Téléchargement en cours",
                "Attends la fin du téléchargement actuel.",
            )
            return

        if (
            self.multi_upload_worker is not None
            and self.multi_upload_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Transfert en cours",
                "Attends la fin du transfert actuel.",
            )
            return

        # Seuls les fichiers sont téléchargés par ce glisser-déposer.
        files = [
            {
                "url": item["url"],
                "name": Path(item["name"]).name,
            }
            for item in items
            if not item.get("is_directory", False)
        ]

        if not files:
            QMessageBox.information(
                self,
                "Aucun fichier",
                "Glisse des fichiers Nextcloud vers un dossier Windows. "
                "Le téléchargement de dossiers entiers n'est pas encore "
                "pris en charge par ce glisser-déposer.",
            )
            return

        destination_path = Path(destination)

        conflicts = [
            item for item in files
            if (destination_path / item["name"]).exists()
        ]

        skipped = 0

        if conflicts:
            answer = QMessageBox.question(
                self,
                "Fichiers déjà présents",
                f"{len(conflicts)} fichier(s) existent déjà dans "
                "le dossier Windows choisi.\n\n"
                "Oui : remplacer les fichiers existants.\n"
                "Non : conserver les fichiers existants et les ignorer.\n"
                "Annuler : abandonner le transfert.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.No,
            )

            if answer == QMessageBox.StandardButton.Cancel:
                return

            if answer == QMessageBox.StandardButton.No:
                existing_names = {
                    item["name"].casefold()
                    for item in conflicts
                }
                files = [
                    item for item in files
                    if item["name"].casefold() not in existing_names
                ]
                skipped = len(conflicts)

        if not files:
            QMessageBox.information(
                self,
                "Aucun téléchargement",
                "Tous les fichiers existaient déjà dans le dossier.",
            )
            return

        self.multi_download_skipped = skipped

        self.multi_download_dialog = QProgressDialog(
            "Préparation du téléchargement…",
            None,
            0,
            100,
            self,
        )
        self.multi_download_dialog.setWindowTitle(
            "Téléchargement vers Windows"
        )
        self.multi_download_dialog.setCancelButton(None)
        self.multi_download_dialog.setWindowModality(
            Qt.WindowModality.WindowModal
        )
        self.multi_download_dialog.setMinimumDuration(300)
        self.multi_download_dialog.setValue(0)
        self.multi_download_dialog.show()

        self.multi_download_worker = MultiDownloadWorker(
            files,
            str(destination_path),
            self.profile["username"],
            self.profile["password"],
            self,
        )

        self.multi_download_worker.progress.connect(
            self.multi_download_progress
        )
        self.multi_download_worker.current_file.connect(
            self.multi_download_current_file
        )
        self.multi_download_worker.completed.connect(
            self.multi_download_completed
        )
        self.multi_download_worker.finished.connect(
            self.multi_download_thread_finished
        )
        self.multi_download_worker.start()

        self.status_label.setText(
            f"Téléchargement de {len(files)} fichier(s) vers "
            f"{destination_path}…"
        )
    def import_file(self):
        if not self.profile or not self.url_stack:
            QMessageBox.warning(
                self,
                "Compte non configuré",
                "Configure d'abord ton compte NUAGE.",
            )
            return

        if (self.upload_worker is not None and self.upload_worker.isRunning()) or (
            self.multi_upload_worker is not None
            and self.multi_upload_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Import en cours",
                "Attends la fin de l'import actuel.",
            )
            return

        sources, _ = QFileDialog.getOpenFileNames(
            self,
            "Choisir les fichiers à importer",
            "",
            "Tous les fichiers (*)",
        )

        if not sources:
            return

        files = []
        existing_names = {
            self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)["name"].casefold()
            for row in range(self.table.rowCount())
            if self.table.item(row, 0) is not None
            and self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            and not self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)[
                "is_directory"
            ]
        }

        overwrite_all = False
        skip_all = False

        for source in sources:
            filename = Path(source).name
            overwrite = False

            if filename.casefold() in existing_names:
                answer = QMessageBox.question(
                    self,
                    "Fichier déjà présent",
                    f"Le fichier « {filename} » existe déjà "
                    "dans ce dossier NUAGE.\n\n"
                    "Oui : remplacer ce fichier.\n"
                    "Non : ignorer ce fichier.\n"
                    "Annuler : abandonner tout l'import.",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.No,
                )

                if answer == QMessageBox.StandardButton.Cancel:
                    return

                if answer == QMessageBox.StandardButton.No:
                    continue

                overwrite = True

            files.append(
                {
                    "source": source,
                    "name": filename,
                    "overwrite": overwrite,
                }
            )

        if not files:
            QMessageBox.information(
                self,
                "Aucun fichier à importer",
                "Aucun fichier n'a été retenu pour l'envoi.",
            )
            return

        self.multi_upload_dialog = QProgressDialog(
            "Préparation de l'envoi…",
            None,
            0,
            100,
            self,
        )
        self.multi_upload_dialog.setWindowTitle("Import multiple vers NUAGE")
        self.multi_upload_dialog.setCancelButton(None)
        self.multi_upload_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.multi_upload_dialog.setMinimumDuration(300)
        self.multi_upload_dialog.setValue(0)
        self.multi_upload_dialog.show()

        self.multi_upload_worker = MultiUploadWorker(
            files,
            self.url_stack[-1],
            self.profile["username"],
            self.profile["password"],
            self,
        )

        self.multi_upload_worker.progress.connect(self.multi_upload_progress)
        self.multi_upload_worker.current_file.connect(self.multi_upload_current_file)
        self.multi_upload_worker.completed.connect(self.multi_upload_completed)
        self.multi_upload_worker.finished.connect(self.multi_upload_thread_finished)
        self.multi_upload_worker.start()

        self.status_label.setText(f"Envoi de {len(files)} fichier(s) vers NUAGE…")
    def multi_upload_progress(self, percent):
        if self.multi_upload_dialog is not None:
            self.multi_upload_dialog.setValue(percent)
    def multi_upload_current_file(self, name):
        if self.multi_upload_dialog is not None:
            self.multi_upload_dialog.setLabelText(f"Envoi de {name} vers NUAGE…")
    def multi_upload_completed(self, results):
        if self.multi_upload_dialog is not None:
            self.multi_upload_dialog.setValue(100)
            self.multi_upload_dialog.close()
            self.multi_upload_dialog = None

        successes = results["success"]
        failures = results["failed"]

        summary = f"Envois réussis : {len(successes)}\n" f"Échecs : {len(failures)}"

        if failures:
            details = "\n".join(f"• {name} : {message}" for name, message in failures)
            summary += f"\n\nDétails des erreurs :\n{details}"

        self.refresh()
        self.status_label.setText(
            f"Import terminé : {len(successes)} réussi(s), "
            f"{len(failures)} échec(s)."
        )

        if failures:
            QMessageBox.warning(
                self,
                "Bilan des imports",
                summary,
            )
        else:
            QMessageBox.information(
                self,
                "Bilan des imports",
                summary,
            )
    def multi_upload_thread_finished(self):
        self.multi_upload_worker = None
    def upload_progress(self, percent):
        if self.upload_dialog is not None:
            self.upload_dialog.setValue(percent)
    def upload_succeeded(self, destination_url):
        if self.upload_dialog is not None:
            self.upload_dialog.setValue(100)
            self.upload_dialog.close()
            self.upload_dialog = None

        self.status_label.setText("✓  Import terminé")
        self.refresh()

        QMessageBox.information(
            self,
            "Import terminé",
            "Le fichier a bien été envoyé vers NUAGE.",
        )
    def upload_failed(self, message):
        if self.upload_dialog is not None:
            self.upload_dialog.close()
            self.upload_dialog = None

        self.status_label.setText("L'import a échoué.")

        QMessageBox.warning(
            self,
            "Échec de l'import",
            message,
        )
    def upload_thread_finished(self):
        self.upload_worker = None
