"""Méthodes de MainWindow regroupées par fonctionnalité."""
from .common import *
from .workers import (
    DownloadWorker, MultiDownloadWorker, UploadWorker, MultiUploadWorker,
    DeleteWorker, PreviewWorker, NewOfficeDocumentWorker, OfficeEditWorker,
    ResourceOperationWorker,
)
from .dialogs import ProfileDialog, PreviewDialog, RemoteFolderDialog
from .widgets import DragDropTableWidget, LocalDropTreeView

class PreviewOfficeMixin:
    def open_item(self, item):
        name_item = self.table.item(item.row(), 0)
        if name_item is None:
            return

        data = name_item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data["is_directory"]:
            self.url_stack.append(data["url"].rstrip("/") + "/")
            self.refresh()
            return

        self.preview_file(data)
    def preview_file(self, data):
        if not self.profile:
            return

        suffix = Path(data["name"]).suffix.lower()

        if suffix in OFFICE_EXTENSIONS:
            self.edit_office_file(data)
            return
        if (
            suffix not in IMAGE_EXTENSIONS
            and suffix != ".pdf"
            and suffix not in OFFICE_EXTENSIONS
        ):
            QMessageBox.information(
                self,
                "Aperçu indisponible",
                f"Le format de « {data['name']} » "
                "n'est pas pris en charge.\n\n"
                "Utilise le menu contextuel pour télécharger ce fichier.",
            )
            return

        if (
            (suffix == ".pdf" or suffix in OFFICE_EXTENSIONS)
            and not PDF_PREVIEW_AVAILABLE
        ):
            QMessageBox.warning(
                self,
                "Lecteur PDF indisponible",
                "Le module PDF de PySide6 est nécessaire "
                "pour afficher les PDF et les documents bureautiques.",
            )
            return

        if (
            self.preview_worker is not None
            and self.preview_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Aperçu en cours",
                "Attends la fin de la préparation de l'aperçu actuel.",
            )
            return

        self.preview_item_name = data["name"]

        self.preview_progress_dialog = QProgressDialog(
            "Récupération temporaire du fichier…",
            None,
            0,
            100,
            self,
        )
        self.preview_progress_dialog.setWindowTitle("Préparation de l'aperçu")
        self.preview_progress_dialog.setCancelButton(None)
        self.preview_progress_dialog.setWindowModality(
            Qt.WindowModality.WindowModal
        )
        self.preview_progress_dialog.setMinimumDuration(300)
        self.preview_progress_dialog.setValue(0)
        self.preview_progress_dialog.show()

        self.preview_worker = PreviewWorker(
            data,
            self.profile,
            self,
        )

        self.preview_worker.progress.connect(
            self.preview_progress
        )
        self.preview_worker.succeeded.connect(
            self.preview_ready
        )
        self.preview_worker.failed.connect(
            self.preview_failed
        )
        self.preview_worker.finished.connect(
            self.preview_thread_finished
        )

        self.preview_worker.start()
    def edit_office_file(self, data):
        if (
            self.office_edit_worker is not None
            and self.office_edit_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Édition en cours",
                "Ferme le document LibreOffice actuel et attends "
                "la fin de la synchronisation avant d'en ouvrir un autre.",
            )
            return

        if find_libreoffice() is None:
            QMessageBox.warning(
                self,
                "LibreOffice introuvable",
                "LibreOffice n'a pas été détecté sur ce poste.\n\n"
                "Vérifie qu'il est installé et accessible.",
            )
            return

        self.office_edit_progress_dialog = QProgressDialog(
            f"Téléchargement de {data['name']}…",
            None,
            0,
            100,
            self,
        )
        self.office_edit_progress_dialog.setWindowTitle(
            "Ouverture dans LibreOffice"
        )
        self.office_edit_progress_dialog.setCancelButton(None)
        self.office_edit_progress_dialog.setWindowModality(
            Qt.WindowModality.WindowModal
        )
        self.office_edit_progress_dialog.setMinimumDuration(300)
        self.office_edit_progress_dialog.setValue(0)
        self.office_edit_progress_dialog.show()

        self.office_edit_worker = OfficeEditWorker(
            data,
            self.profile,
            self,
        )

        self.office_edit_worker.progress.connect(
            self.office_edit_progress
        )
        self.office_edit_worker.editor_started.connect(
            self.office_editor_started
        )
        self.office_edit_worker.sync_started.connect(
            self.office_sync_started
        )
        self.office_edit_worker.completed.connect(
            self.office_edit_completed
        )
        self.office_edit_worker.finished.connect(
            self.office_edit_thread_finished
        )

        self.office_edit_worker.start()
    def office_edit_progress(self, percent, message):
        self.status_label.setText(message)

        if self.office_edit_progress_dialog is not None:
            self.office_edit_progress_dialog.setLabelText(message)
            self.office_edit_progress_dialog.setValue(percent)
    def office_editor_started(self, name):
        if self.office_edit_progress_dialog is not None:
            self.office_edit_progress_dialog.close()
            self.office_edit_progress_dialog = None

        self.status_label.setText(
            f"{name} ouvert dans LibreOffice. "
            "Ferme LibreOffice pour synchroniser les modifications."
        )
    def office_sync_started(self, name):
        self.office_edit_progress_dialog = QProgressDialog(
            f"Envoi des modifications de {name} vers Nextcloud…",
            None,
            0,
            100,
            self,
        )
        self.office_edit_progress_dialog.setWindowTitle(
            "Synchronisation NUAGE"
        )
        self.office_edit_progress_dialog.setCancelButton(None)
        self.office_edit_progress_dialog.setWindowModality(
            Qt.WindowModality.WindowModal
        )
        self.office_edit_progress_dialog.setMinimumDuration(300)
        self.office_edit_progress_dialog.setValue(0)
        self.office_edit_progress_dialog.show()
    def office_edit_completed(self, result):
        if self.office_edit_progress_dialog is not None:
            self.office_edit_progress_dialog.close()
            self.office_edit_progress_dialog = None

        if result["ok"]:
            self.refresh()

            if result["changed"]:
                self.status_label.setText(
                    f"✓  Modifications de {result['name']} envoyées vers NUAGE."
                )
                QMessageBox.information(
                    self,
                    "Synchronisation terminée",
                    f"Les modifications de « {result['name']} » "
                    "ont été envoyées vers NUAGE.",
                )
            else:
                self.status_label.setText(
                    f"Aucune modification détectée dans {result['name']}."
                )
                QMessageBox.information(
                    self,
                    "Document fermé",
                    f"Aucune modification détectée dans « {result['name']} ».\n\n"
                    "Le fichier distant n'a pas été remplacé.",
                )

        else:
            self.status_label.setText(
                f"Échec de l'édition ou de la synchronisation : {result['name']}"
            )
            QMessageBox.warning(
                self,
                "Synchronisation impossible",
                f"Le document « {result['name']} » n'a pas pu être "
                f"synchronisé.\n\n{result['error']}",
            )
    def closeEvent(self, event):
        if (
            self.office_edit_worker is not None
            and self.office_edit_worker.isRunning()
        ):
            QMessageBox.warning(
                self,
                "Édition en cours",
                "Un document est encore ouvert dans LibreOffice "
                "ou sa synchronisation est en cours.\n\n"
                "Ferme LibreOffice et attends la fin de la "
                "synchronisation avant de quitter Nextcloud Explorer.",
            )
            event.ignore()
            return

        super().closeEvent(event)
    def office_edit_thread_finished(self):
        self.office_edit_worker = None
    def preview_progress(self, percent, message):
        if self.preview_progress_dialog is not None:
            self.preview_progress_dialog.setLabelText(message)
            self.preview_progress_dialog.setValue(percent)
    def preview_ready(self, preview_path, temp_dir):
        if self.preview_progress_dialog is not None:
            self.preview_progress_dialog.close()
            self.preview_progress_dialog = None

        try:
            dialog = PreviewDialog(
                self.preview_item_name,
                preview_path,
                temp_dir,
                self,
            )
            dialog.exec()

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Aperçu impossible",
                str(exc),
            )

        finally:
            # Nettoyage supplémentaire si la fenêtre n'a pas pu s'ouvrir.
            shutil.rmtree(temp_dir, ignore_errors=True)
    def preview_failed(self, message):
        if self.preview_progress_dialog is not None:
            self.preview_progress_dialog.close()
            self.preview_progress_dialog = None

        QMessageBox.warning(
            self,
            "Aperçu impossible",
            message,
        )
    def preview_thread_finished(self):
        self.preview_worker = None
    def create_office_document(self, document_type):
        document_types = {
            "writer": ("Document Writer", ".odt"),
            "calc": ("Classeur Calc", ".ods"),
            "impress": ("Présentation Impress", ".odp"),
        }

        if document_type not in document_types:
            return

        label, extension = document_types[document_type]

        filename, accepted = QInputDialog.getText(
            self,
            "Nouveau document LibreOffice",
            "Nom du fichier :",
            text=label + extension,
        )

        if not accepted:
            return

        filename = filename.strip()

        if "/" in filename or "\\" in filename:
            QMessageBox.warning(
                self,
                "Nom invalide",
                "Le nom ne doit pas contenir de séparateur de chemin.",
            )
            return
        
        if not filename:
            QMessageBox.warning(
                self,
                "Nom invalide",
                "Le nom du fichier ne peut pas être vide.",
            )
            return

        # Ajoute l'extension attendue si elle est absente.
        if not filename.lower().endswith(extension):
            filename += extension

        # Évite d'écraser un fichier déjà présent dans le dossier affiché.
        existing_names = {
            self.table.item(row, 0).text().strip().casefold()
            for row in range(self.table.rowCount())
            if self.table.item(row, 0) is not None
        }

        if filename.casefold() in existing_names:
            QMessageBox.warning(
                self,
                "Fichier déjà présent",
                f"Un élément nommé « {filename} » existe déjà dans ce dossier.",
            )
            return

        # Un seul nouveau document à la fois.
                # Un seul nouveau document à la fois.
        if (
            self.new_office_worker is not None
            and self.new_office_worker.isRunning()
        ):
            QMessageBox.information(
                self,
                "Création en cours",
                "Un nouveau document est déjà en cours de création.",
            )
            return

        self.new_office_worker = NewOfficeDocumentWorker(
            document_type=document_type,
            filename=filename,
            folder_url=self.url_stack[-1],
            username=self.profile["username"],
            password=self.profile["password"],
            parent=self,
        )

        self.new_office_worker.result_ready.connect(
            self.new_office_document_completed
        )
        self.new_office_worker.start()
    def new_office_document_completed(self, success, message):
        if success:
            self.refresh()
            QMessageBox.information(
                self,
                "Nouveau document",
                message,
            )
        else:
            QMessageBox.critical(
                self,
                "Nouveau document",
                message,
            )
