"""Boîtes de dialogue de l’application."""
from .common import *
from .style import STYLE
from .printing import print_pdf
from PySide6.QtWidgets import QHBoxLayout

class ProfileDialog(QDialog):
    def __init__(self, profile=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compte NUAGE")
        self.setMinimumWidth(550)

        profile = profile or {}
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("Connexion à NUAGE")
        title.setObjectName("appTitle")
        layout.addWidget(title)

        explanation = QLabel(
            "Configure ton accès WebDAV. Le mot de passe "
            "d'application sera conservé dans le coffre chiffré."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        form = QFormLayout()
        form.setSpacing(12)

        self.url = QLineEdit(profile.get("url", ""))
        self.url.setPlaceholderText("https://serveur/remote.php/dav/files/identifiant/")

        self.username = QLineEdit(profile.get("username", ""))

        self.password = QLineEdit(profile.get("password", ""))
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Mot de passe d'application")

        form.addRow("Adresse WebDAV", self.url)
        form.addRow("Identifiant", self.username)
        form.addRow("Mot de passe", self.password)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            "Tester et enregistrer"
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primary")
        buttons.accepted.connect(self.test_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def test_and_accept(self):
        url = self.url.text().strip()
        username = self.username.text().strip()
        password = self.password.text()

        if not url or not username or not password:
            QMessageBox.warning(
                self,
                "Informations manquantes",
                "Renseigne les trois champs.",
            )
            return

        if not url.startswith("https://"):
            QMessageBox.warning(
                self,
                "Adresse incorrecte",
                "L'adresse doit commencer par https://",
            )
            return

        url = url.rstrip("/") + "/"

        try:
            entries = list_directory(url, username, password)
        except WebDAVError as exc:
            QMessageBox.warning(self, "Connexion impossible", str(exc))
            return

        self.profile = {
            "name": "NUAGE",
            "url": url,
            "username": username,
            "password": password,
        }

        QMessageBox.information(
            self,
            "Connexion réussie",
            f"Connexion WebDAV validée.\n" f"{len(entries)} éléments reçus.",
        )
        self.accept()

class ZoomablePdfView(QPdfView):
    """Zoom avec Ctrl + molette, défilement normal sinon."""

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()

            if delta == 0:
                event.ignore()
                return

            current_zoom = self.zoomFactor()

            # Passer du zoom automatique au zoom manuel.
            if self.zoomMode() != QPdfView.ZoomMode.Custom:
                self.setZoomMode(QPdfView.ZoomMode.Custom)
                current_zoom = self.zoomFactor()

            # Zoom progressif, limité entre 25 % et 500 %.
            if delta > 0:
                new_zoom = current_zoom * 1.15
            else:
                new_zoom = current_zoom / 1.15

            new_zoom = max(0.25, min(5.0, new_zoom))
            self.setZoomFactor(new_zoom)

            event.accept()
            return

        # Sans Ctrl, comportement normal : défilement du document.
        super().wheelEvent(event)

class PreviewDialog(QDialog):
    """Affiche une image ou un document PDF dans une fenêtre intégrée."""

    def __init__(self, original_name, preview_path, temp_dir, parent=None):
        super().__init__(parent)

        self.original_name = original_name
        self.preview_path = Path(preview_path)
        self.temp_dir = Path(temp_dir)
        self.original_pixmap = None
        self.pdf_document = None
        
        self.setWindowTitle(f"Aperçu — {original_name}")
        self.setObjectName("previewDialog")
        self.setStyleSheet(STYLE)
        
        # Autoriser la maximisation et la minimisation de la fenêtre.
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )

        self.resize(1000, 750)
        self.setMinimumSize(500, 350)

        layout = QVBoxLayout(self)

        title = QLabel(original_name)
        title.setObjectName("sectionTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        suffix = self.preview_path.suffix.lower()

        if suffix in IMAGE_EXTENSIONS:
            self.image_scroll = QScrollArea()
            self.image_scroll.setWidgetResizable(False)

            self.image_label = QLabel()
            self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.image_scroll.setWidget(self.image_label)
            layout.addWidget(self.image_scroll, 1)

            self.original_pixmap = QPixmap(str(self.preview_path))

            if self.original_pixmap.isNull():
                raise RuntimeError(
                    "Qt ne peut pas afficher cette image."
                )

            self.update_image_preview()

        elif suffix == ".pdf":
            if not PDF_PREVIEW_AVAILABLE:
                raise RuntimeError(
                    "Le lecteur PDF de Qt n'est pas disponible. "
                    "Vérifie l'installation de PySide6."
                )

            self.pdf_document = QPdfDocument(self)
            status = self.pdf_document.load(str(self.preview_path))

            if status == QPdfDocument.Status.Error:
                raise RuntimeError(
                    "Le PDF n'a pas pu être ouvert. "
                    "Le fichier est peut-être endommagé ou protégé."
                )

            self.pdf_view = ZoomablePdfView()
            self.pdf_view.setDocument(self.pdf_document)
            self.pdf_view.setPageMode(
                QPdfView.PageMode.MultiPage
            )
            self.pdf_view.setZoomMode(
                QPdfView.ZoomMode.FitToWidth
            )

            layout.addWidget(self.pdf_view, 1)

        else:
            raise RuntimeError(
                f"Aucun aperçu disponible pour {suffix}."
            )

        
        # Boutons d'action de l'aperçu
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        if suffix == ".pdf":
            print_button = QPushButton("Imprimer")
            print_button.setObjectName("primary")
            print_button.clicked.connect(
                lambda: print_pdf(self.preview_path, self)
            )
            button_layout.addWidget(print_button)

        close_button = QPushButton("Fermer")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def update_image_preview(self):
        if self.original_pixmap is None:
            return

        viewport_size = self.image_scroll.viewport().size()

        if viewport_size.width() <= 0 or viewport_size.height() <= 0:
            return

        scaled = self.original_pixmap.scaled(
            viewport_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_image_preview()

    def done(self, result):
        # Les fichiers temporaires ne sont conservés que pendant l'aperçu.
        if self.pdf_document is not None:
            self.pdf_document.close()

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        super().done(result)


class RemoteFolderDialog(QDialog):
    """Permet de choisir un dossier de destination sur NUAGE."""

    def __init__(self, profile, parent=None):
        super().__init__(parent)

        self.profile = profile
        self.destination_url = None

        self.setWindowTitle("Choisir un dossier NUAGE")
        self.resize(480, 520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Sélectionne le dossier de destination :"))

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(18)
        self.tree.itemExpanded.connect(self.load_children)
        layout.addWidget(self.tree)

        root = QTreeWidgetItem(["☁  Mon Nextcloud"])
        root.setData(0, Qt.ItemDataRole.UserRole, profile["url"])
        root.setData(0, Qt.ItemDataRole.UserRole + 1, False)
        root.addChild(QTreeWidgetItem(["Chargement…"]))

        self.tree.addTopLevelItem(root)
        self.tree.setCurrentItem(root)
        root.setExpanded(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Choisir ce dossier"
        )
        buttons.accepted.connect(self.accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_children(self, item):
        """Charge les sous-dossiers lorsque l'utilisateur développe un dossier."""
        if item.data(0, Qt.ItemDataRole.UserRole + 1):
            return

        url = item.data(0, Qt.ItemDataRole.UserRole)
        if not url:
            return

        item.setData(0, Qt.ItemDataRole.UserRole + 1, True)
        item.takeChildren()

        try:
            entries = list_directory(
                url,
                self.profile["username"],
                self.profile["password"],
            )
        except WebDAVError as exc:
            item.setData(0, Qt.ItemDataRole.UserRole + 1, False)
            item.addChild(QTreeWidgetItem(["Chargement…"]))
            QMessageBox.warning(
                self,
                "Erreur WebDAV",
                str(exc),
            )
            return

        current = urlsplit(url)

        for entry in entries:
            if not entry.get("is_directory", False):
                continue

            href = entry.get("href", "")
            if not href:
                continue

            child_url = urljoin(url, href)
            parsed = urlsplit(child_url)

            # Ne pas sortir du serveur NUAGE ni réafficher le dossier courant.
            if parsed.netloc.lower() != current.netloc.lower():
                continue

            if parsed.path.rstrip("/") == current.path.rstrip("/"):
                continue

            if not child_url.endswith("/"):
                child_url += "/"

            name = entry.get("name") or parsed.path.rstrip("/").split("/")[-1]

            child = QTreeWidgetItem([f"📁  {name}"])
            child.setData(0, Qt.ItemDataRole.UserRole, child_url)
            child.setData(0, Qt.ItemDataRole.UserRole + 1, False)
            child.addChild(QTreeWidgetItem(["Chargement…"]))
            item.addChild(child)

    def accept_selection(self):
        item = self.tree.currentItem()

        if item is None:
            QMessageBox.warning(
                self,
                "Aucun dossier",
                "Sélectionne un dossier de destination.",
            )
            return

        url = item.data(0, Qt.ItemDataRole.UserRole)
        if not url:
            return

        self.destination_url = url.rstrip("/") + "/"
        self.accept()
